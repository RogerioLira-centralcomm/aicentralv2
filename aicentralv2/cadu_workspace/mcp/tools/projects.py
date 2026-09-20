"""Project-source tools. Binary transfer uses a short-lived upload intent."""

from werkzeug.exceptions import HTTPException

from ...agent_v2.contracts import RequestContext
from ... import project_source_service
from ... import project_index_service
from ... import project_resource_service
from .. import operations
from ..registry import ToolInputError, register_tool


def _domain(call):
    try:
        return call()
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc


@register_tool(
    name="projects.list_sources", capability="workspace", effect="read", requires_project=True,
    description="Lista arquivos anexados ao projeto e informa quais participam da base de conhecimento.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    }, "additionalProperties": False},
)
def list_sources(context: RequestContext, arguments: dict) -> dict:
    return {"sources": _domain(lambda: project_source_service.list_sources(
        context, limit=arguments.get("limit", 50),
    ))}


@register_tool(
    name="projects.list_resources", capability="workspace", effect="read", requires_project=True,
    description="Organiza e lista arquivos, artifacts, planos, relatórios, imagens, vídeos e links do projeto.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def list_project_resources(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: project_resource_service.list_for_context(context))


@register_tool(
    name="projects.inspect_file_support", capability="workspace", effect="read", requires_project=True,
    description="Informa se um formato pode ser indexado, apenas anexado ou precisa de um adapter.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["filename"], "properties": {
        "filename": {"type": "string", "minLength": 1, "maxLength": 220},
        "mime_type": {"type": "string", "maxLength": 160},
    }, "additionalProperties": False},
)
def inspect_file_support(context: RequestContext, arguments: dict) -> dict:
    return project_source_service.inspect_file_support(arguments["filename"], arguments.get("mime_type", ""))


@register_tool(
    name="projects.classify_intake", capability="workspace", effect="read",
    description="Classifica arquivo, link ou texto antes de salvar: sugere destino, categoria e se indexação precisa de confirmação.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "filename": {"type": "string", "maxLength": 220},
        "mime_type": {"type": "string", "maxLength": 160},
        "url": {"type": "string", "maxLength": 2000},
        "text": {"type": "string", "maxLength": 5000},
        "requested_purpose": {"type": "string", "enum": ["conversation", "knowledge_source", "project_attachment", "artifact"]},
    }, "additionalProperties": False},
)
def classify_intake(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: project_source_service.classify_intake(**arguments))


@register_tool(
    name="projects.prepare_source_upload", capability="workspace", effect="draft", requires_project=True,
    description="Prepara upload privado de arquivo. O usuário escolhe se ele será indexado como fonte de dados.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "use_as_knowledge"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "use_as_knowledge": {"type": "boolean"},
        "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
    }, "additionalProperties": False},
)
def prepare_source_upload(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: project_source_service.prepare_upload(
        context, request_id=arguments["request_id"],
        use_as_knowledge=arguments["use_as_knowledge"], category=arguments.get("category"),
    ))


@register_tool(
    name="projects.reindex_source", capability="workspace", effect="write", requires_project=True,
    description="Reprocessa uma fonte de conhecimento do projeto após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "source_id"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "source_id": {"type": "integer", "minimum": 1},
    }, "additionalProperties": False},
)
def reindex_source(context: RequestContext, arguments: dict) -> dict:
    if not context.project_ref or not context.project_ref.startswith("ci:"):
        raise ToolInputError("Selecione um projeto nativo do Cadu para reprocessar uma fonte.")
    project_id = context.project_ref[3:]
    source_id = int(arguments["source_id"])
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "projects.reindex_source", {"source_id": source_id},
        lambda: project_index_service.reindex_source(context.client_id, project_id, source_id, context.user_id),
    ))


@register_tool(
    name="projects.create_note", capability="workspace", effect="write", requires_project=True,
    description="Cria uma nota como fonte de conhecimento do projeto após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "title", "content"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "title": {"type": "string", "minLength": 2, "maxLength": 180},
        "content": {"type": "string", "minLength": 20, "maxLength": 50000},
        "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
    }, "additionalProperties": False},
)
def create_note(context: RequestContext, arguments: dict) -> dict:
    payload = {key: arguments[key] for key in ("title", "content", "category") if key in arguments}
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "projects.create_note", payload,
        lambda: project_source_service.create_note(context, **payload),
    ))
