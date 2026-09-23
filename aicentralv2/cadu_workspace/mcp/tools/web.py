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
            "limit": {"type": "integer", "minimum": 3, "maximum": 12},
            "depth": {"type": "string", "enum": ["fast", "analysis", "agentic"]},
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


@register_tool(
    name="web.read",
    capability="research",
    effect="read",
    description=(
        "Lê um ou vários links HTTPS fornecidos pelo usuário, remove o ruído das páginas e devolve "
        "o conteúdo principal com metadados para análise, citação ou refinamento na conversa."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": [],
        "properties": {
            "url": {"type": "string", "minLength": 12, "maxLength": 2000},
            "urls": {"type": "array", "items": {"type": "string", "minLength": 12, "maxLength": 2000}, "minItems": 1, "maxItems": 8},
            "request_id": {"type": ["string", "null"], "maxLength": 120},
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
            "result_type": {"type": "string"},
        },
    },
)
def read_web(context: RequestContext, arguments: dict) -> dict:
    try:
        return web_search.read(context, arguments)
    except web_search.WebSearchUnavailable as exc:
        raise ToolError("Não consegui extrair conteúdo legível deste link.") from exc
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
