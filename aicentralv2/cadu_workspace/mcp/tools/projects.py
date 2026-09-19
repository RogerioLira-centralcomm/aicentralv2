"""Project-source tools. Binary transfer uses a short-lived upload intent."""

from werkzeug.exceptions import HTTPException

from ...agent_v2.contracts import RequestContext
from ... import project_source_service
from ... import project_resource_service
from ..registry import ToolInputError, register_tool


def _domain(call):
    try:
        return call()
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc


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
