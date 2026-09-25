"""Read-only checks for campaign metrics explicitly supplied in chat."""

from ...agent_v2.contracts import RequestContext
from ...agent_v2.performance_review import review_supplied_metrics
from ..registry import register_tool


@register_tool(
    name="campaign.review_supplied_metrics", capability="reports", effect="read",
    description="Normaliza métricas citadas na mensagem e calcula relações condicionais sem consultar plataformas.",
    exposures=("internal",), version="1.0.0",
    input_schema={"type": "object", "required": ["query"], "properties": {
        "query": {"type": "string", "minLength": 3, "maxLength": 2000},
    }, "additionalProperties": False},
    output_schema={"type": "object"},
)
def review_campaign_metrics(context: RequestContext, arguments: dict) -> dict:
    return review_supplied_metrics(arguments["query"])
