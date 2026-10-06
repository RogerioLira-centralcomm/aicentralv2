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


# Read-only projections for agents: public descriptive fields only. Commercial values (investment labels, prices,
# internal extras) never leave through the MCP, so the Planner data can be used freely to enrich research and notes.
_CATALOG_FIELDS = {
    "canais": ("id", "slug", "name", "description", "category", "audience"),
    "audiencias": ("id", "name", "description", "audience", "category", "subcategory", "platform",
                   "perfil_socioeconomico", "propensao_compra", "tamanho"),
    "formatos": ("id", "name", "description", "dimensions", "files", "format_type", "platform_slug",
                 "platform", "creative_category", "purpose"),
    "interativos": ("id", "name", "description", "dimensions", "files", "format_type", "platform_slug",
                    "platform", "creative_category", "purpose"),
    "portais": ("id", "name", "domain", "category", "description", "audience_estimate", "audience_period",
                "scope", "uf", "monthly_visits", "avg_time_seconds", "metrics_period", "ads_txt_status",
                "programmatic_status"),
    "places": ("id", "slug", "name", "code", "operator", "description", "category", "city", "audience",
               "traffic", "traffic_label", "points", "public_url"),
}


def _public_url(path):
    """Absolute URL for a stored media path, so the agent can render it outside the Cadu pages."""
    from ....product_domains import product_url
    value = str(path or "").strip()
    if value.startswith(("http://", "https://")):
        return value
    return product_url("planner", value) if value.startswith("/static/") else ""


def _logo_for(kind, row):
    if kind == "canais":
        from ....cadu_planner.channels import _channel_logo
        return _channel_logo(row.get("slug"), row.get("logo_path"))
    if kind == "portais":
        return row.get("favicon_url") or ""
    return row.get("platform_logo") or ""


def _cadu_url(kind, row):
    from ....product_domains import product_url
    if kind == "places":
        return product_url("planner", f"/places/{row.get('slug')}") if row.get("slug") else ""
    return product_url("planner", f"/{kind}/{row.get('id')}") if row.get("id") else ""


def _card(kind, item):
    """Markdown the agent can paste as is: image, name, key facts and the link to open it in the Cadu."""
    lines = []
    if item.get("image_url"):
        lines.append(f"![{item.get('name') or kind}]({item['image_url']})")
    title = f"**{item.get('name') or ''}**"
    if item.get("logo_url"):
        title = f"![logo]({item['logo_url']}) " + title
    facts = [str(item[key]) for key in ("category", "subcategory", "platform", "city", "audience",
                                        "audience_estimate", "dimensions") if item.get(key)]
    lines.append(title + (" · " + " · ".join(facts[:4]) if facts else ""))
    description = " ".join(str(item.get("description") or "").split())
    if description:
        lines.append(description[:220] + ("…" if len(description) > 220 else ""))
    if item.get("cadu_url"):
        lines.append(f"[Abrir no Cadu]({item['cadu_url']})")
    return "\n".join(lines)


def _project(records, kind):
    fields = _CATALOG_FIELDS[kind]
    projected = []
    for row in records:
        if not isinstance(row, dict):
            continue
        item = {key: row.get(key) for key in fields}
        item["image_url"] = _public_url(row.get("image_url"))
        item["logo_url"] = _public_url(_logo_for(kind, row))
        item["cadu_url"] = _cadu_url(kind, row)
        item["card"] = _card(kind, item)
        projected.append(item)
    return projected


@register_tool(
    name="planner.search_catalog", capability="planner", effect="read",
    description=("Pesquisa o catálogo do Planner: audiências, canais, formatos, formatos interativos, portais e Places. "
                 "Somente leitura e sem custo: use para enriquecer pesquisas, anotações e planejamentos sem abrir o Cadu. "
                 "Cada registro traz image_url, logo_url, cadu_url e card (markdown pronto): mostre o card à pessoa para ela ver o item na conversa, "
                 "com imagem e logo. Não traz valores comerciais."),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["kind"], "properties": {
        "kind": {"type": "string", "enum": sorted(_CATALOG_FIELDS)},
        "query": {"type": "string", "maxLength": 100},
        "limit": {"type": "integer", "minimum": 1, "maximum": 30},
    }, "additionalProperties": False},
)
def search_catalog(context: RequestContext, arguments: dict) -> dict:
    kind = arguments["kind"]
    query = str(arguments.get("query") or "").strip()[:100]
    limit = int(arguments.get("limit") or 20)
    try:
        if kind == "portais":
            from ....cadu_planner import portals
            records = portals.catalog(query=query, limit=limit)["records"]
        elif kind == "places":
            from ....cadu_planner import places
            records = places.catalog(query=query)[:limit]
        else:
            records = catalog.query(kind, query, limit)
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc
    return {"kind": kind, "records": _project(records, kind)}


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
