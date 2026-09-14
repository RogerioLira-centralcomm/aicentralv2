"""Loop curto LLM → tool do Agente Imersão."""

import json

from ..services.openrouter_service import chat_completion
from .prompts import SYSTEM_PROMPT, wrap_untrusted
from .providers import DEFAULT_TEXT_MODEL, usage_cost
from .tools import (
    TOOL_DEFINITIONS,
    apply_to_session,
    classify_attachment,
    compose_slide,
    edit_text,
    format_for_session,
    generate_image,
    research_market,
    fontes_block,
)


MAX_TOOL_CALLS = 4


class TrainingAgentError(RuntimeError):
    pass


def _content(message):
    content = (message or {}).get("content") or ""
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict)
        )
    return str(content).strip()


def run_chat(
    providers,
    message,
    selection,
    document,
    fontes,
    guia_estilo,
    buscar_web=False,
    page_html="",
    surface="",
    history=None,
):
    web_state = "ligada" if buscar_web else "desligada"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history or []:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        prefix = ""
        if item.get("tool_used") and role == "assistant":
            prefix = f"[{item.get('tool_used')}] "
        if item.get("surface"):
            prefix = f"{prefix}({item.get('surface')}) "
        messages.append({"role": role, "content": f"{prefix}{content[:800]}"})
    messages.append(
        {
            "role": "user",
            "content": (
                f"{message}\n\n"
                f"Busca na internet: {web_state}. "
                "Se estiver desligada, não chame pesquisar_mercado.\n"
                f"Página em foco: {surface or 'roteiro'}.\n\n"
                f"Seleção atual:\n{selection or '(nenhuma)'}\n\n"
                f"{wrap_untrusted('pagina', (page_html or '')[:5000])}\n\n"
                f"{wrap_untrusted('documento', (document or '')[:4000])}\n\n"
                f"{fontes_block(fontes)}"
            ),
        }
    )
    costs = []
    last_tool = None
    last_payload = None
    for _ in range(MAX_TOOL_CALLS + 1):
        response = chat_completion(
            messages,
            tools=TOOL_DEFINITIONS,
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1600,
            temperature=0.4,
        )
        costs.append(
            {
                "kind": "texto",
                "model": response.get("model") or DEFAULT_TEXT_MODEL,
                "usage": response.get("usage") or {},
                "cost_usd": usage_cost(response.get("usage")),
                "provider": "openai" if str(response.get("model") or "").startswith(("gpt-", "openai/")) else "openrouter",
            }
        )
        assistant = response.get("message") or {}
        messages.append(assistant)
        tool_calls = assistant.get("tool_calls") or []
        if not tool_calls:
            return {
                "content": _content(assistant) or "Pronto.",
                "tool_used": last_tool or "edicao",
                "payload": last_payload,
                "costs": costs,
                "apply": bool((last_payload or {}).get("apply")),
            }
        applied = False
        for call in tool_calls:
            function = call.get("function") or {}
            name = function.get("name")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = _run_tool(
                name,
                arguments,
                providers,
                selection,
                document,
                fontes,
                guia_estilo,
                message,
                buscar_web,
                page_html,
            )
            last_tool = result.get("tool_used") or name
            last_payload = result
            costs.append(
                {
                    "kind": result.get("kind") or "texto",
                    "model": result.get("model"),
                    "usage": result.get("usage") or {},
                    "cost_usd": result.get("cost_usd") or 0,
                    "provider": result.get("provider") or "openai",
                }
            )
            tool_content = (
                result.get("content")
                or result.get("html")
                or result.get("prompt")
                or "ok"
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": str(tool_content)[:4000],
                }
            )
            if result.get("apply") or name == "criar_sessao":
                applied = True
        if applied:
            return {
                "content": (last_payload or {}).get("content") or "Aplicado.",
                "tool_used": last_tool,
                "payload": last_payload,
                "costs": costs,
                "apply": bool((last_payload or {}).get("apply")),
            }
    return {
        "content": (last_payload or {}).get("content") or "Consulta concluída.",
        "tool_used": last_tool or "edicao",
        "payload": last_payload,
        "costs": costs,
        "apply": bool((last_payload or {}).get("apply")),
    }


def _run_tool(
    name,
    arguments,
    providers,
    selection,
    document,
    fontes,
    guia_estilo,
    message,
    buscar_web,
    page_html="",
):
    if name == "editar_texto":
        return edit_text(
            providers,
            arguments.get("acao") or "reescrever",
            selection,
            document,
            fontes,
            arguments.get("instrucao") or "",
        )
    if name == "pesquisar_mercado":
        return research_market(
            providers, arguments.get("query") or message, selection, buscar_web
        )
    if name == "gerar_imagem":
        return generate_image(
            providers,
            arguments.get("prompt") or selection or message,
            guia_estilo,
            selection,
        )
    if name == "formatar_para_sessao":
        return format_for_session(
            providers,
            arguments.get("texto") or selection or message,
            arguments.get("bloco") or "",
            document,
        )
    if name == "aplicar_na_sessao":
        return apply_to_session(
            arguments.get("html") or selection,
            arguments.get("modo") or "anexar",
        )
    if name == "organizar_anexo":
        return classify_attachment(
            providers,
            arguments.get("texto") or selection,
            arguments.get("filename") or "",
        )
    if name in {"gerar_slide", "reorganizar_slide"}:
        return compose_slide(
            providers,
            arguments.get("instrucao") or selection or message,
            page_html,
            arguments.get("layout") or "",
            arguments.get("instrucao") or "",
            "gerar" if name == "gerar_slide" else "reorganizar",
        )
    if name == "criar_sessao":
        return {
            "content": arguments.get("titulo") or "Nova sessão",
            "tool_used": "sessao",
            "kind": "texto",
            "create_session": {
                "titulo": arguments.get("titulo") or "Nova sessão",
                "horario_inicio": arguments.get("horario_inicio") or "",
                "horario_fim": arguments.get("horario_fim") or "",
                "apos_slug": arguments.get("apos_slug") or "",
                "conteudo_html": arguments.get("html") or "",
                "tipo": "fonte",
            },
            "model": None,
            "usage": {},
            "cost_usd": 0,
        }
    raise TrainingAgentError("Ferramenta não permitida.")
