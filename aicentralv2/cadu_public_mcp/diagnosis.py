"""Per-step state of an agent connection, derived from what the server knows.

The server cannot see whether a host registered the `cadu` server locally, so
that step is only marked done once a grant proves the host reached the Cadu.
Nothing here reads tokens, headers or prompts.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Iterable

from ..cadu_mcp_catalog import module_for_tool, normalize_modules
from . import auth

PENDING, DONE, FAILED = "pendente", "concluida", "falhou"


def tools_for_grant(public_tools: Iterable[str], scopes, modules) -> list[str]:
    principal = SimpleNamespace(scopes=tuple(scopes or ()))
    enabled = set(normalize_modules(modules))
    return sorted(
        name for name in public_tools
        if module_for_tool(name) in enabled and auth.has_scope(principal, auth.required_scope(name))
    )


def _step(step_id: str, label: str, status: str, detail: str, action: str = "") -> dict:
    return {"id": step_id, "label": label, "status": status, "detail": detail, "action": action}


def diagnose(*, oauth_ready: bool, grants: list[dict], public_tools: Iterable[str]) -> dict:
    """Return the ordered steps and the connection they describe (the newest active grant)."""
    active = [grant for grant in grants if grant.get("status") == "active"]
    grant = active[0] if active else None
    revoked_only = bool(grants) and not active
    tool_names = tools_for_grant(public_tools, grant.get("scopes"), grant.get("modules")) if grant else []

    steps = [
        _step("infra", "Login do Cadu disponível", DONE if oauth_ready else FAILED,
              "O login por conta Cadu está ativo neste ambiente." if oauth_ready else
              "O login por conta Cadu ainda não foi habilitado neste ambiente.",
              "" if oauth_ready else "Peça à equipe do Cadu para aplicar a migração do MCP público."),
        _step("registered", "Cadu adicionado no aplicativo", DONE if grant or revoked_only else PENDING,
              "O aplicativo já chegou ao Cadu." if grant or revoked_only else
              "Ainda não recebemos nenhum pedido de um aplicativo.",
              "" if grant or revoked_only else "Execute os comandos do passo 1 e confirme que `cadu` aparece na lista do aplicativo."),
        _step("consent", "Login e consentimento", DONE if grant else FAILED if revoked_only else PENDING,
              "Conta e permissões aprovadas." if grant else
              "A última conexão foi revogada." if revoked_only else "Aguardando você autorizar no navegador.",
              "" if grant else "Conecte de novo no aplicativo e aprove as permissões."),
        _step("tools", "Ferramentas disponíveis", DONE if tool_names else FAILED if grant else PENDING,
              f"{len(tool_names)} ferramentas liberadas para esta conexão." if tool_names else
              "A conexão está ativa, mas nenhum módulo ou permissão libera ferramentas." if grant else
              "Depende da conexão aprovada.",
              "" if tool_names or not grant else "Ative ao menos um módulo ou amplie as permissões."),
        _step("first_use", "Primeira consulta", DONE if grant and grant.get("last_used_at") else PENDING,
              "O aplicativo já usou o Cadu." if grant and grant.get("last_used_at") else
              "Ainda sem uso.", "" if grant and grant.get("last_used_at") else
              "Abra uma nova conversa no aplicativo e peça para listar seus projetos do Cadu."),
    ]
    return {
        "steps": steps,
        "connected": bool(grant and tool_names),
        "tool_count": len(tool_names),
        "grant_id": grant.get("id") if grant else None,
    }
