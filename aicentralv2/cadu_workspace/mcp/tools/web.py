"""Public-web discovery exposed to the Cadu agent registry."""

from ...agent_v2.contracts import RequestContext
from ... import web_search
from ..registry import ToolError, ToolInputError, register_tool


@register_tool(
    name="web.search",
    capability="research",
    effect="read",
    description=(
        "Pesquisa fontes públicas atuais e lê seletivamente os melhores resultados para responder "
        "ao pedido com contexto, links e distinção entre fato e interpretação. Não pesquisa o projeto."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 3, "maxLength": 400},
            "request_id": {"type": ["string", "null"], "maxLength": 120},
            "limit": {"type": "integer", "minimum": 3, "maximum": 8},
            "recency": {"type": "string", "enum": ["", "day", "week", "month", "year"]},
            "include_domains": {"type": "array", "items": {"type": "string", "maxLength": 180}, "maxItems": 10},
            "exclude_domains": {"type": "array", "items": {"type": "string", "maxLength": 180}, "maxItems": 10},
            "include_content": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "sources": {"type": "array"},
            "source_count": {"type": "integer"},
            "sources_read": {"type": "integer"},
            "search_mode": {"type": "string"},
        },
    },
)
def search_web(context: RequestContext, arguments: dict) -> dict:
    try:
        return web_search.search(context, arguments)
    except web_search.WebSearchUnavailable as exc:
        raise ToolError("A pesquisa online não ficou disponível nesta resposta.") from exc
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
