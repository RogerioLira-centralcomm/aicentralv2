"""Loop curto LLM → tool do Agente Imersão."""

import json

from ..services.openrouter_service import chat_completion
from .prompts import SYSTEM_PROMPT, wrap_untrusted
from .providers import DEFAULT_TEXT_MODEL, usage_cost
from .tools import (
    TOOL_DEFINITIONS,
    edit_text,
    generate_image,
    research_market,
    fontes_block,
)


MAX_TOOL_CALLS = 3


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


def run_chat(providers, message, selection, document, fontes, guia_estilo):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{message}\n\n"
                f"Seleção atual:\n{selection or '(nenhuma)'}\n\n"
                f"{wrap_untrusted('documento', (document or '')[:6000])}\n\n"
                f"{fontes_block(fontes)}"
            ),
        },
    ]
    costs = []
    last_tool = None
    last_payload = None
    for _ in range(MAX_TOOL_CALLS + 1):
        response = chat_completion(
            messages,
            tools=TOOL_DEFINITIONS,
            model=DEFAULT_TEXT_MODEL,
            max_tokens=1400,
            temperature=0.4,
        )
        costs.append(
            {
                "kind": "texto",
                "model": response.get("model") or DEFAULT_TEXT_MODEL,
                "usage": response.get("usage") or {},
                "cost_usd": usage_cost(response.get("usage")),
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
            }
        for call in tool_calls[:1]:
            function = call.get("function") or {}
            name = function.get("name")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if name == "editar_texto":
                result = edit_text(
                    providers,
                    arguments.get("acao") or "reescrever",
                    selection,
                    document,
                    fontes,
                    arguments.get("instrucao") or "",
                )
                last_tool = "edicao"
            elif name == "pesquisar_mercado":
                result = research_market(
                    providers, arguments.get("query") or message, selection
                )
                last_tool = "pesquisa"
            elif name == "gerar_imagem":
                result = generate_image(
                    providers,
                    arguments.get("prompt") or selection or message,
                    guia_estilo,
                    selection,
                )
                last_tool = "imagem"
            else:
                raise TrainingAgentError("Ferramenta não permitida.")
            last_payload = result
            costs.append(
                {
                    "kind": result.get("kind") or "texto",
                    "model": result.get("model"),
                    "usage": result.get("usage") or {},
                    "cost_usd": result.get("cost_usd") or 0,
                }
            )
            tool_content = result.get("content") or result.get("prompt") or "ok"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": str(tool_content)[:4000],
                }
            )
    return {
        "content": (last_payload or {}).get("content") or "Consulta concluída.",
        "tool_used": last_tool or "edicao",
        "payload": last_payload,
        "costs": costs,
    }
