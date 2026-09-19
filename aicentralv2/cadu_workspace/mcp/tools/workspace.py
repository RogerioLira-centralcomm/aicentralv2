"""Workspace tools.  Every query remains scoped to RequestContext.client_id."""

import json

from ....cadu_family import repository
from ...agent_v2.contracts import RequestContext
from ...conversations.service import project_knowledge_context
from ..registry import ToolInputError, register_tool


@register_tool(
    name="workspace.get_current_context", capability="workspace",
    description="Retorna o contexto autorizado atual sem carregar conteúdo amplo do workspace.",
    exposures=("internal", "customer_agent"),
)
def get_current_context(context: RequestContext, arguments: dict) -> dict:
    return context.to_dict()


@register_tool(
    name="workspace.list_projects", capability="workspace",
    description="Lista projetos visíveis no workspace atual.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string", "maxLength": 120}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        "additionalProperties": False,
    },
)
def list_projects(context: RequestContext, arguments: dict) -> dict:
    query = " ".join(str(arguments.get("query") or "").split()).casefold()
    try:
        limit = min(50, max(1, int(arguments.get("limit") or 20)))
    except (TypeError, ValueError):
        raise ToolInputError("Limite inválido.")
    records = [row for row in repository.entities(context.client_id) if row.get("kind") == "project"]
    if query:
        records = [row for row in records if query in str(row.get("name") or "").casefold()]
    return {"projects": [{key: row.get(key) for key in ("ref", "name", "source")} for row in records[:limit]]}


@register_tool(
    name="workspace.get_project_context", capability="workspace", requires_project=True,
    description="Obtém o contexto salvo do projeto atual e fontes diretamente relacionadas.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {"query": {"type": "string", "maxLength": 400}}, "additionalProperties": False},
)
def get_project_context(context: RequestContext, arguments: dict) -> dict:
    raw = project_knowledge_context(context.project_ref, context.brand_ref, context.client_id,
                                    str(arguments.get("query") or ""))
    try:
        return json.loads(raw) if raw else {"project_ref": context.project_ref}
    except (TypeError, ValueError):
        return {"project_ref": context.project_ref}


@register_tool(
    name="workspace.search_project_content", capability="workspace", requires_project=True,
    description="Pesquisa somente no conteúdo indexado e nos dados do projeto atual.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["query"],
        "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 400}},
        "additionalProperties": False,
    },
)
def search_project_content(context: RequestContext, arguments: dict) -> dict:
    query = " ".join(str(arguments.get("query") or "").split())
    if len(query) < 2:
        raise ToolInputError("Informe o que deve ser pesquisado no projeto.")
    packet = get_project_context(context, {"query": query})
    return {
        "project_ref": context.project_ref,
        "query": query,
        "project": packet.get("projeto") or {},
        "results": packet.get("fontes_verificadas") or [],
    }
