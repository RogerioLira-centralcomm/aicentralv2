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
    description="Mostra o estado seguro da autorização Google deste usuário no cliente atual.",
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
    description="Lista eventos do Calendar da conta Google autorizada por este usuário no cliente atual.",
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
    name="google.create_project_meeting",
    capability="workspace",
    effect="write",
    requires_project=True,
    description="Cria evento com Google Meet e envia o convite à equipe ativa do projeto após confirmação explícita.",
    exposures=("internal",),
    input_schema={
        "type": "object",
        "required": ["request_id", "confirmed", "title", "starts_at", "ends_at"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "confirmed": {"type": "boolean", "enum": [True]},
            "title": {"type": "string", "minLength": 2, "maxLength": 300},
            "description": {"type": "string", "maxLength": 8000},
            "starts_at": {"type": "string", "minLength": 16, "maxLength": 40},
            "ends_at": {"type": "string", "minLength": 16, "maxLength": 40},
            "timezone": {"type": "string", "enum": ["America/Sao_Paulo"]},
        },
        "additionalProperties": False,
    },
)
def create_project_meeting(context: RequestContext, arguments: dict) -> dict:
    payload = {
        "summary": arguments["title"], "description": arguments.get("description", ""),
        "starts_at": arguments["starts_at"], "ends_at": arguments["ends_at"],
        "event_timezone": arguments.get("timezone", "America/Sao_Paulo"),
        "request_id": arguments["request_id"],
    }
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "google.create_project_meeting", payload,
        lambda: connector.create_project_meeting(context, **payload),
    ))


@register_tool(
    name="google.list_meet_records",
    capability="workspace",
    effect="read",
    description="Lista registros recentes do Meet desta conta autorizada, sem baixar transcrições ou gravações automaticamente.",
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
    name="google.list_meet_artifacts",
    capability="workspace",
    effect="read",
    description="Pesquisa artefatos do Google Meet desta conta, sem importar gravações ou transcrições automaticamente.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        "additionalProperties": False,
    },
)
def list_meet_artifacts(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: connector.list_meet_artifacts(
        context, limit=arguments.get("limit", 25),
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
    description="Atualiza os recursos da conta Google autorizada por este usuário neste cliente após confirmação explícita.",
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
