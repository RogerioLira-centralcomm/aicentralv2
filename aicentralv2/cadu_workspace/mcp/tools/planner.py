"""Read-only Planner tools backed by the product's canonical services."""

import re

from werkzeug.exceptions import HTTPException

from ....cadu_planner import catalog, plans
from ...agent_v2.contracts import RequestContext
from ...agent_v2.investment_scenarios import simulate as simulate_investment
from ...agent_v2.media_plan_review import review_media_plan
from ..registry import ToolError, ToolInputError, register_tool


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
    name="planner.research_plan_inputs", capability="planner", effect="read",
    description=("Reúne referências atuais do catálogo Cadu para uma proposta de mídia: canais, "
                 "audiências, formatos e Places. Não cria nem altera um plano."),
    exposures=("internal",), version="1.0.0",
    input_schema={"type": "object", "required": ["query"], "properties": {
        "query": {"type": "string", "maxLength": 100},
        "city": {"type": "string", "maxLength": 80},
        "channel_scope": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 60},
                          "maxItems": 5, "uniqueItems": True},
    }, "additionalProperties": False},
    output_schema={"type": "object"},
)
def research_plan_inputs(context: RequestContext, arguments: dict) -> dict:
    """Return small, non-commercial catalog projections as planning evidence."""
    from ....cadu_planner import places

    query = " ".join(str(arguments.get("query") or "").split())[:100]
    city = " ".join(str(arguments.get("city") or "").split())[:80]
    from ...agent_v2.channel_scope import filter_channel_records, filter_scoped_records

    requested_scope = [" ".join(str(value).split())[:60] for value in arguments.get("channel_scope", [])
                       if str(value).strip()][:5]
    stop_words = {"plano", "planejamento", "midia", "campanha", "campanhas", "para", "com", "sobre",
                  "uma", "um", "dos", "das", "por", "que", "mais", "menos", "foco", "focada", "focado",
                  "brasil", "brasileiro", "brasileira", "online", "offline", "digital", "aprofundado",
                  "aprofundada", "detalhado", "detalhada", "rapido", "rapida", "direto", "direta",
                  "demografica", "demografico", "publico", "audiencia", "canais", "formatos"}
    terms = [term for term in re.findall(r"[\wÀ-ÿ-]{4,}", query.lower())
             if term not in stop_words and term not in city.lower().split()]
    search_queries = (list(dict.fromkeys(requested_scope)) if requested_scope
                      else list(dict.fromkeys(terms[-2:])) or [""])
    result = {}
    safe_fields = {
        "canais": ("id", "name", "description", "category", "audience"),
        "audiencias": ("id", "name", "description", "audience", "category", "subcategory", "platform",
                       "perfil_socioeconomico", "propensao_compra", "tamanho"),
        "formatos": ("id", "name", "description", "dimensions", "files", "format_type",
                     "platform_slug", "creative_category", "purpose"),
    }
    for kind, fields in safe_fields.items():
        try:
            candidates = {}
            for term in search_queries:
                for row in catalog.query(kind, term, 5):
                    if isinstance(row, dict):
                        candidates[str(row.get("id") or row.get("name"))] = row
            ranked = sorted(candidates.values(), key=lambda row: (
                -sum(term.casefold() in " ".join(str(row.get(key) or "") for key in fields).casefold()
                     for term in search_queries), str(row.get("name") or "").casefold()))[:5]
            if kind == "canais" and requested_scope:
                ranked, channels_status = filter_channel_records(ranked, requested_scope)
                result["channels_status"] = channels_status
            elif kind == "audiencias" and requested_scope:
                ranked = filter_scoped_records(ranked, requested_scope, ("platform", "channel"))
                if any(not (row.get("platform") or row.get("channel")) for row in ranked):
                    result["audience_scope_note"] = (
                        "Segmentos sem plataforma associada são referências genéricas, não validadas no canal solicitado."
                    )
            elif kind == "formatos" and requested_scope:
                ranked = filter_scoped_records(ranked, requested_scope, ("platform_slug",))
            projection = [{key: row.get(key) for key in fields if row.get(key) not in (None, "", [], {})}
                          for row in ranked]
            if kind == "audiencias":
                # Add only demographic characteristics; commercial rates,
                # pricing and internal reliability scores stay out of chat.
                for item, row in zip(projection, ranked):
                    detail = catalog.detail(kind, row["id"])
                    demographics = {
                        key: detail.get(key) for key in (
                            "demografia_homens", "demografia_mulheres", "idade_18_24", "idade_25_34",
                            "idade_35_44", "idade_45_mais",
                        ) if detail.get(key) not in (None, "", [], {})
                    }
                    item["demographics"] = demographics
            result[kind] = projection
        except HTTPException as exc:
            raise ToolError("Os catálogos do Planner não ficaram disponíveis.") from exc
        except Exception as exc:
            raise ToolError("Os catálogos do Planner não ficaram disponíveis.") from exc
    if requested_scope:
        result["places"] = []
        result["places_status"] = "not_applicable_to_channel_scope"
    else:
        try:
            result["places"] = [
                {key: row.get(key) for key in ("id", "name", "category", "city", "audience", "traffic", "traffic_label")
                 if row.get(key) not in (None, "", [], {})}
                for row in places.catalog(query="", city=city)[:5]
            ]
        except Exception:
            # Places is an optional source; planner proposal can still use the
            # channel/audience catalogs and clearly omit unavailable inventory.
            result["places"] = []
            result["places_status"] = "unavailable"
    result["query"] = query
    result["matched_terms"] = search_queries
    if requested_scope:
        result["requested_channel_scope"] = requested_scope
    result["source_note"] = "Referências do catálogo Cadu; não são cotação, disponibilidade ou garantia de desempenho."
    return result


@register_tool(
    name="planner.simulate_investment", capability="planner", effect="read",
    description="Calcula três distribuições ilustrativas de mídia, com totais exatos e sem prever resultados.",
    exposures=("internal",), version="1.0.0",
    input_schema={"type": "object", "required": ["query"], "properties": {
        "query": {"type": "string", "minLength": 3, "maxLength": 1000},
    }, "additionalProperties": False},
    output_schema={"type": "object"},
)
def simulate_investment_tool(context: RequestContext, arguments: dict) -> dict:
    return simulate_investment(arguments["query"])


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
    result = {key: plan.get(key) for key in ("id", "title", "objective", "status", "briefing", "items", "allocations", "readiness", "updated_at")}
    result["calculation_review"] = review_media_plan(result)
    return result
