"""Workspace tools.  Every query remains scoped to RequestContext.client_id."""

import json

from ....cadu_family import repository
from ...agent_v2.contracts import RequestContext
from ...conversations.service import project_knowledge_context
from ...project_portfolio_service import attach_summaries
from .. import operations
from ..registry import ToolInputError, register_tool


@register_tool(
    name="workspace.create_project", capability="workspace", effect="write",
    description="Cria um projeto nativo no Workspace. Só pode ser executado após confirmação explícita.",
    exposures=("internal",),
    input_schema={
        "type": "object",
        "required": ["request_id", "name"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "name": {"type": "string", "minLength": 2, "maxLength": 150},
            "description": {"type": "string", "maxLength": 4000},
            "instructions": {"type": "string", "maxLength": 12000},
            "confirmed": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
)
def create_project(context: RequestContext, arguments: dict) -> dict:
    """Keep project creation in the family repository, never as a chat artifact."""
    if arguments.get("confirmed") is not True:
        raise ToolInputError("Confirme a criação do projeto antes de continuar.")
    name = " ".join(str(arguments.get("name") or "").split())
    if len(name) < 2:
        raise ToolInputError("Informe um nome de projeto com ao menos dois caracteres.")
    payload = {
        "kind": "project", "name": name[:150],
        "description": str(arguments.get("description") or "").strip()[:4000],
        "instructions": str(arguments.get("instructions") or "").strip()[:12000],
    }

    def create():
        try:
            project_ref = repository.create_entity(context.client_id, context.user_id, payload)
        except ValueError as exc:
            raise ToolInputError(str(exc)) from exc
        return {"project_ref": project_ref, "name": payload["name"], "status": "created"}

    return operations.execute(arguments["request_id"], context, "workspace.create_project", payload, create)


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
    selected = [{key: row.get(key) for key in ("ref", "name", "source")} for row in records[:limit]]
    try:
        selected = attach_summaries(context.client_id, selected)
    except Exception:
        # The project directory remains available during additive migrations.
        pass
    return {"projects": selected}


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
