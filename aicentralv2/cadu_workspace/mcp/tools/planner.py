"""Read-only Planner tools backed by the product's canonical services."""

from werkzeug.exceptions import HTTPException

from ....cadu_planner import catalog, plans
from ...agent_v2.contracts import RequestContext
from ..registry import ToolInputError, register_tool


@register_tool(
    name="planner.list_plans", capability="planner", effect="read",
    description="Lista os planos de mídia que o usuário pode abrir no cliente selecionado.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    }, "additionalProperties": False},
)
def list_plans(context: RequestContext, arguments: dict) -> dict:
    limit = int(arguments.get("limit") or 20)
    records = plans.list_plans(context.client_id, context.user_id)[:limit]
    fields = ("id", "title", "objective", "status", "campaign_name", "updated_at", "readiness")
    return {"plans": [{key: row.get(key) for key in fields} for row in records]}


@register_tool(
    name="planner.search_catalog", capability="planner", effect="read",
    description="Pesquisa audiências, canais, formatos ou formatos interativos do Planner.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["kind"], "properties": {
        "kind": {"type": "string", "enum": sorted(catalog.KINDS)},
        "query": {"type": "string", "maxLength": 100},
        "limit": {"type": "integer", "minimum": 1, "maximum": 30},
    }, "additionalProperties": False},
)
def search_catalog(context: RequestContext, arguments: dict) -> dict:
    try:
        records = catalog.query(arguments["kind"], arguments.get("query", ""), arguments.get("limit", 20))
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc
    return {"kind": arguments["kind"], "records": records}


@register_tool(
    name="planner.get_brief", capability="planner",
    description="Obtém o briefing de um plano autorizado ou lista os briefings disponíveis.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"plan_id": {"type": "string", "maxLength": 100}},
        "additionalProperties": False,
    },
)
def get_brief(context: RequestContext, arguments: dict) -> dict:
    plan_id = str(arguments.get("plan_id") or "").strip()
    if plan_id:
        plan = plans.get_plan(context.client_id, context.user_id, plan_id)
        return {"plan_id": str(plan["id"]), "title": plan.get("title"), "objective": plan.get("objective"),
                "briefing": plan.get("briefing") or {}, "readiness": plan.get("readiness")}
    records = plans.list_plans(context.client_id, context.user_id)
    return {"plans": [{key: row.get(key) for key in ("id", "title", "objective", "status", "updated_at")} for row in records[:20]]}


@register_tool(
    name="planner.get_media_plan", capability="planner",
    description="Obtém estrutura, itens e distribuição de um plano de mídia autorizado.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object", "required": ["plan_id"],
        "properties": {"plan_id": {"type": "string", "minLength": 1, "maxLength": 100}},
        "additionalProperties": False,
    },
)
def get_media_plan(context: RequestContext, arguments: dict) -> dict:
    plan_id = str(arguments.get("plan_id") or "").strip()
    if not plan_id:
        raise ToolInputError("Informe o plano que deve ser consultado.")
    plan = plans.get_plan(context.client_id, context.user_id, plan_id)
    # Commercial quote data is intentionally outside the first MCP domain.
    return {key: plan.get(key) for key in ("id", "title", "objective", "status", "briefing", "items", "allocations", "readiness", "updated_at")}
