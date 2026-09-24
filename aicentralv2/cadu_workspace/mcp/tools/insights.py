"""Composite evidence-led market insights tool for the Cadu chat plugin."""

from ...insights_research import InsightsEvidenceUnavailable, research_market
from ...agent_v2.contracts import RequestContext
from ..registry import ToolError, register_tool


@register_tool(
    name="insights.research_market",
    description=(
        "Busca evidências recentes na internet e no Perplexity, cria um insight de mercado para marketing, "
        "comunicação e mídia e faz revisão factual independente antes de responder."
    ),
    capability="research",
    effect="read",
    version="0.3.0",
    exposures=("internal",),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 4, "maxLength": 400},
            "request_id": {"type": "string", "maxLength": 180},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    output_schema={"type": "object"},
)
def research_market_tool(context: RequestContext, arguments: dict) -> dict:
    try:
        return research_market(context, arguments["query"], arguments.get("request_id"))
    except InsightsEvidenceUnavailable as exc:
        raise ToolError(str(exc)) from exc
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:
        raise ToolError("A pesquisa de mercado não ficou disponível nesta resposta.") from exc
