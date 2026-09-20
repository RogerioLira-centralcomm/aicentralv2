"""MCP tools backed by the global Cadu ↔ Google connector."""

from ...agent_v2.contracts import RequestContext
from ....services import cadu_google_connector
from .. import operations
from ..registry import ToolInputError, register_tool


connector = cadu_google_connector.connector


def _domain(call):
    try:
        return call()
    except cadu_google_connector.CaduGoogleConnectorError as exc:
        raise ToolInputError(str(exc)) from exc


@register_tool(
    name="google.get_connector_status",
    capability="workspace",
    effect="read",
    description="Mostra o estado seguro da conexão Google global, dos serviços e do contexto atual de usuário e projeto.",
    exposures=("internal", "customer_agent"),
)
def get_connector_status(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: connector.status(context))


@register_tool(
    name="google.list_project_resources",
    capability="workspace",
    effect="read",
    requires_project=True,
    description="Lista os arquivos e links Google já associados ao projeto atual do Cadu.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
        "additionalProperties": False,
    },
)
def list_project_resources(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: connector.list_project_resources(
        context, limit=arguments.get("limit", 100),
    ))


@register_tool(
    name="google.list_calendar_events",
    capability="workspace",
    effect="read",
    description="Lista eventos do Calendar da organização para contextualizar reuniões e entregas.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        "additionalProperties": False,
    },
)
def list_calendar_events(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: connector.list_calendar_events(
        context, limit=arguments.get("limit", 50),
    ))


@register_tool(
    name="google.list_meet_records",
    capability="workspace",
    effect="read",
    description="Lista registros recentes do Meet sem baixar transcrições ou gravações automaticamente.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        "additionalProperties": False,
    },
)
def list_meet_records(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: connector.list_meet_records(
        context, limit=arguments.get("limit", 50),
    ))


@register_tool(
    name="google.link_resource_to_project",
    capability="workspace",
    effect="write",
    requires_project=True,
    description="Vincula um recurso Google ao projeto atual após confirmação explícita do usuário.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["request_id", "confirmed", "resource_id"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "confirmed": {"type": "boolean", "enum": [True]},
            "resource_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "purpose": {"type": "string", "enum": ["project_knowledge", "project_attachment", "reference"]},
        },
        "additionalProperties": False,
    },
)
def link_resource_to_project(context: RequestContext, arguments: dict) -> dict:
    payload = {
        "resource_id": arguments["resource_id"],
        "purpose": arguments.get("purpose", "project_knowledge"),
    }
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "google.link_resource_to_project", payload,
        lambda: connector.link_resource(context, **payload),
    ))


@register_tool(
    name="google.sync_workspace",
    capability="workspace",
    effect="write",
    description="Atualiza os recursos da conta Google global após confirmação explícita; pode retornar sucesso parcial quando Ads não estiver pronto.",
    exposures=("internal",),
    input_schema={
        "type": "object",
        "required": ["request_id", "confirmed"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "confirmed": {"type": "boolean", "enum": [True]},
            "drive_limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            "ads_limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
)
def sync_workspace(context: RequestContext, arguments: dict) -> dict:
    payload = {
        "drive_limit": arguments.get("drive_limit", 200),
        "ads_limit": arguments.get("ads_limit", 100),
    }
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "google.sync_workspace", payload,
        lambda: connector.sync(context, **payload),
    ))
