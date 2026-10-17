"""Cadu Análise no MCP: revisão de um plano de mídia enviado pelo agente (v1, sem cobrança)."""

import base64
import binascii

from ....cadu_review import access, service
from ....cadu_review.media_plan_parser import MAX_FILE_BYTES, PlanParseError
from ...agent_v2.contracts import RequestContext
from ..registry import ToolError, ToolInputError, register_tool

_CONTEXT_PROPERTIES = {
    name: {"type": "string", "maxLength": 600, "description": description}
    for name, description in (
        ("objetivo", "Objetivo da campanha, se o arquivo não trouxer."),
        ("publico", "Público-alvo."),
        ("kpi", "KPI principal."),
        ("periodo", "Período da campanha, ex.: 01/11/2026 a 30/11/2026."),
        ("verba", "Verba aprovada, ex.: R$ 250.000."),
        ("praca", "Praças ou regiões."),
        ("cliente", "Anunciante."),
        ("campanha", "Nome da campanha."),
    )
}


def agent_view(result: dict) -> dict:
    """O que o agente precisa: parecer, critérios e o texto pronto, sem repetir todas as linhas lidas."""
    return {
        "summary": result["summary"],
        "file": result["file"],
        "context": result["context"],
        "findings": [{key: item.get(key) for key in ("id", "label", "group", "status", "detail", "suggestion", "lines")}
                     for item in result["findings"]],
        "markdown": result["markdown"],
        "billing": {"mode": "free_v1", "tokens_cobrados": 0},
        "instruction": "Mostre o `markdown` à pessoa. O plano não foi alterado; não diga que corrigiu nada.",
    }


def decode_content(arguments: dict) -> bytes:
    if arguments.get("content_base64"):
        try:
            raw = base64.b64decode(str(arguments["content_base64"]), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolInputError("content_base64 inválido.") from exc
    elif arguments.get("content_text"):
        raw = str(arguments["content_text"]).encode("utf-8")
    else:
        raise ToolInputError("Envie o arquivo em content_base64 ou o CSV em content_text.")
    if len(raw) > MAX_FILE_BYTES:
        raise ToolInputError("O arquivo deve ter até 5 MB.")
    return raw


@register_tool(
    name="review.media_plan", capability="planner",
    description=("Revisa um plano de mídia (XLSX, CSV ou PDF de qualquer agência): confere verba, conta de entrega, "
                 "período, concentração e custos no código e julga canais, público, funil e mensuração com o TypeSafe. "
                 "Devolve parecer (aprovar, aprovar com ajustes, refazer), nota e ajustes. Não altera o plano."),
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "maxLength": 200, "description": "Nome com extensão: plano.xlsx, plano.csv ou plano.pdf."},
            "content_base64": {"type": "string", "maxLength": 7_200_000, "description": "Arquivo em base64 (até 5 MB)."},
            "content_text": {"type": "string", "maxLength": 2_000_000, "description": "Alternativa: o plano como CSV em texto."},
            **_CONTEXT_PROPERTIES,
        },
        "required": ["filename"],
        "additionalProperties": False,
    },
)
def review_media_plan(context: RequestContext, arguments: dict) -> dict:
    if not access.allowed_for_user(context.user_id):
        error = ToolError(access.INTERNAL_ONLY_MESSAGE)
        error.code = "review_not_available"
        raise error
    filename = str(arguments.get("filename") or "").strip()
    if arguments.get("content_text") and not arguments.get("content_base64") and not filename.lower().endswith(".csv"):
        filename = (filename.rsplit(".", 1)[0] or "plano") + ".csv"
    raw = decode_content(arguments)
    try:
        result = service.review_media_plan(raw, filename, context=arguments, channel="mcp",
                                           client_id=context.client_id, user_id=context.user_id)
    except PlanParseError as exc:
        raise ToolInputError(str(exc)) from exc
    return agent_view(result)
