"""Provider-neutral resource tools backed by registry and indexed content."""

import json

from ...agent_v2.contracts import RequestContext
from ... import project_resource_service
from ...conversations.service import project_knowledge_context
from ..registry import ToolInputError, register_tool


def _project_resource(context: RequestContext, resource_id: str) -> dict:
    resource = project_resource_service.get_resource(
        context.client_id, context.project_ref or "", resource_id,
    )
    if not resource:
        raise ToolInputError("Recurso indisponível neste projeto.")
    return resource


@register_tool(
    name="resources.search",
    capability="workspace",
    effect="read",
    requires_project=True,
    description="Pesquisa recursos do projeto sem exigir que o agente conheça o provedor de origem.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 400},
            "resource_type": {"type": "string", "maxLength": 40},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "additionalProperties": False,
    },
)
def search_resources(context: RequestContext, arguments: dict) -> dict:
    try:
        resources = project_resource_service.search_resources(
            context.client_id,
            context.project_ref or "",
            arguments["query"],
            limit=arguments.get("limit", 20),
            resource_type=arguments.get("resource_type"),
        )
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
    indexed_content = []
    try:
        packet = json.loads(project_knowledge_context(
            context.project_ref, context.brand_ref, context.client_id, arguments["query"],
        ) or "{}")
        indexed_content = packet.get("fontes_verificadas") or []
    except (TypeError, ValueError, KeyError):
        indexed_content = []
    return {
        "project_ref": context.project_ref,
        "query": arguments["query"],
        "resources": resources,
        "indexed_content": indexed_content,
        "search_mode": "resource_metadata_plus_hybrid_index",
    }


@register_tool(
    name="resources.get",
    capability="workspace",
    effect="read",
    requires_project=True,
    description="Obtém um recurso canônico e seus metadados no projeto atual.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["resource_id"],
        "properties": {"resource_id": {"type": "string", "minLength": 1, "maxLength": 80}},
        "additionalProperties": False,
    },
)
def get_resource(context: RequestContext, arguments: dict) -> dict:
    resource = _project_resource(context, arguments["resource_id"])
    return {"project_ref": context.project_ref, "resource": resource}


@register_tool(
    name="resources.capabilities",
    capability="workspace",
    effect="read",
    requires_project=True,
    description="Informa quais ações são realmente suportadas para um recurso, sem presumir capacidades do provedor.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["resource_id"],
        "properties": {"resource_id": {"type": "string", "minLength": 1, "maxLength": 80}},
        "additionalProperties": False,
    },
)
def resource_capabilities(context: RequestContext, arguments: dict) -> dict:
    resource = _project_resource(context, arguments["resource_id"])
    return {"project_ref": context.project_ref,
            "capabilities": project_resource_service.resource_capabilities(resource)}
