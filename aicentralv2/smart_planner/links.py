"""Link amigável do plano público: o nome do plano com hífens no lugar do token aleatório.

O link antigo continua funcionando: fica em ``public_token_aliases`` e redireciona para o novo.
"""

from __future__ import annotations

import logging

from .helpers import as_bool, as_dict, as_list, session_public_token, text
from .repository import update_session
from .share import friendly_token, is_friendly, share_payload

logger = logging.getLogger(__name__)


def plan_title(row: dict) -> str:
    dados = as_dict(row.get("dados_detectados"))
    folha = as_dict(dados.get("folha"))
    meta = as_dict(folha.get("meta") or as_dict(row.get("plan_content")).get("meta"))
    campanha = as_dict(dados.get("campanha"))
    return text(
        meta.get("title")
        or meta.get("campaign")
        or campanha.get("nome")
        or dados.get("nome_campanha")
        or row.get("titulo")
        or row.get("cliente")
        or meta.get("client")
    )


def ensure_friendly(row: dict) -> str:
    """Troca o token aleatório pelo link amigável (uma vez) e devolve o token atual do plano."""
    current = session_public_token(row)
    if not current or is_friendly(current):
        return current
    dados = as_dict(row.get("dados_detectados"))
    confidential = as_bool(dados.get("anunciante_confidencial"))
    title = plan_title(row)
    new = friendly_token(title, confidential)
    client = text(as_dict(as_dict(dados.get("folha")).get("meta")).get("client") or row.get("cliente"))
    share = share_payload(new, client, title, confidential)
    old_tokens = [current, text(dados.get("public_token"))]
    aliases = list(dict.fromkeys([text(t) for t in as_list(dados.get("public_token_aliases")) + old_tokens if text(t) and text(t) != new]))
    folha = as_dict(dados.get("folha"))
    if folha:
        folha["share"] = {**as_dict(folha.get("share")), **share}
        dados["folha"] = folha
    dados.update({"public_token": new, "public_token_aliases": aliases})
    fields = {"dados_detectados": dados}
    plan = as_dict(row.get("plan_content"))
    if plan:
        plan["share"] = {**as_dict(plan.get("share")), **share}
        fields["plan_content"] = plan
    update_session(text(row.get("session_token")), fields)
    logger.info("Smart Planner: link público %s trocado por %s", current, new)
    return new


def rename_all(dry_run: bool = False) -> list[tuple[str, str]]:
    """Troca todos os links públicos aleatórios pelos amigáveis; devolve (antigo, novo)."""
    from .repository import list_public_tokens

    done = []
    for row in list_public_tokens():
        current = session_public_token(row)
        if not current or is_friendly(current):
            continue
        if dry_run:
            dados = as_dict(row.get("dados_detectados"))
            done.append((current, friendly_token(plan_title(row), as_bool(dados.get("anunciante_confidencial")))))
            continue
        try:
            done.append((current, ensure_friendly(row)))
        except Exception:
            logger.exception("Falha ao trocar o link %s", current)
    return done
