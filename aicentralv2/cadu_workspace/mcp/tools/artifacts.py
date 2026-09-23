"""Versioned artifact tools shared by Cadu and delegated customer agents."""

from werkzeug.exceptions import HTTPException

from ...agent_v2.contracts import RequestContext
from ...artifacts import service
from ...artifacts.catalog import definition, describe
from .. import operations
from ..registry import ToolInputError, register_tool


def _domain(call):
    try:
        return call()
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc


@register_tool(
    name="artifacts.describe_types", capability="artifacts", effect="read",
    description="Lista as entregas reais suportadas, seus editores e capacidades; não inclui superfícies visuais temporárias.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def describe_types(_context: RequestContext, _arguments: dict) -> dict:
    return {"types": describe()}


@register_tool(
    name="artifacts.list", capability="artifacts", effect="read",
    description="Lista artefatos visíveis no projeto ou workspace atual.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "type": {"type": "string", "enum": sorted(service.ALLOWED_TYPES)},
        "status": {"type": "string", "enum": sorted(service.ALLOWED_STATUS)},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    }, "additionalProperties": False},
)
def list_artifacts(context: RequestContext, arguments: dict) -> dict:
    return {"artifacts": _domain(lambda: service.list_artifacts(
        context, artifact_type=arguments.get("type"), status=arguments.get("status"),
        limit=arguments.get("limit", 20),
    ))}


@register_tool(
    name="artifacts.get", capability="artifacts", effect="read",
    description="Obtém o conteúdo e a versão atual de um artefato autorizado.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["artifact_id"], "properties": {
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
    }, "additionalProperties": False},
)
def get_artifact(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.get_artifact(context, arguments["artifact_id"]))


@register_tool(
    name="artifacts.create_draft", capability="artifacts", effect="draft",
    description="Cria no projeto uma entrega editável e versionada, incluindo página HTML interativa (type=html), documento, pesquisa, resumo, plano ou nota, sem publicá-la.",
    exposures=("internal", "customer_agent"), requires_project=True,
    input_schema={"type": "object", "required": ["request_id", "type", "title", "content"], "properties": {
        "request_id": {"type": "string", "minLength": 16, "maxLength": 80},
        "type": {"type": "string", "enum": sorted(service.ALLOWED_TYPES)},
        "title": {"type": "string", "minLength": 1, "maxLength": 180},
        "content": {"type": "object"},
    }, "additionalProperties": False},
)
def create_draft(context: RequestContext, arguments: dict) -> dict:
    payload = {key: arguments[key] for key in ("type", "title", "content")}
    return _domain(lambda: operations.execute(arguments["request_id"], context, "artifacts.create_draft", payload,
        lambda: service.create_draft(context, arguments["type"], arguments["content"], title=arguments["title"],
                                     conversation_id=context.conversation_id)))


@register_tool(
    name="artifacts.update_draft", capability="artifacts", effect="draft",
    description="Atualiza um rascunho usando controle otimista de versão.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "artifact_id", "expected_version", "content"], "properties": {
        "request_id": {"type": "string", "minLength": 16, "maxLength": 80},
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "expected_version": {"type": "integer", "minimum": 1},
        "title": {"type": "string", "minLength": 1, "maxLength": 180},
        "content": {"type": "object"},
        "change_summary": {"type": "string", "maxLength": 500},
    }, "additionalProperties": False},
)
def update_draft(context: RequestContext, arguments: dict) -> dict:
    current = _domain(lambda: service.get_artifact(context, arguments["artifact_id"]))
    if current["status"] not in {"draft", "active"}:
        raise ToolInputError("Somente artefatos em rascunho ou ativos podem ser editados por esta ferramenta.")
    if not definition(current["type"]).agent_editable:
        raise ToolInputError("Este tipo de entrega é uma referência somente para leitura.")
    payload = {key: arguments[key] for key in ("artifact_id", "expected_version", "content")}
    payload.update({key: arguments[key] for key in ("title", "change_summary") if key in arguments})
    return _domain(lambda: operations.execute(arguments["request_id"], context, "artifacts.update_draft", payload,
        lambda: service.patch_artifact(context, arguments["artifact_id"], arguments["content"],
            expected_version=arguments["expected_version"], title=arguments.get("title"),
            change_summary=arguments.get("change_summary") or "Atualização via MCP")))


@register_tool(
    name="artifacts.list_versions", capability="artifacts", effect="read",
    description="Lista o histórico de versões sem retornar todo o conteúdo de cada versão.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["artifact_id"], "properties": {
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    }, "additionalProperties": False},
)
def artifact_versions(context: RequestContext, arguments: dict) -> dict:
    return {"versions": _domain(lambda: service.list_versions(
        context, arguments["artifact_id"], limit=arguments.get("limit", 50),
    ))}


@register_tool(
    name="artifacts.get_version", capability="artifacts", effect="read",
    description="Obtém uma versão imutável específica para comparação ou revisão.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["artifact_id", "version"], "properties": {
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "version": {"type": "integer", "minimum": 1},
    }, "additionalProperties": False},
)
def artifact_version(context: RequestContext, arguments: dict) -> dict:
    return {"version": _domain(lambda: service.get_version(
        context, arguments["artifact_id"], arguments["version"],
    ))}


@register_tool(
    name="artifacts.restore_version", capability="artifacts", effect="draft",
    description="Restaura uma versão anterior criando uma nova versão; nunca apaga o histórico.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "artifact_id", "version", "expected_version"],
                  "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "version": {"type": "integer", "minimum": 1},
        "expected_version": {"type": "integer", "minimum": 1},
    }, "additionalProperties": False},
)
def restore_artifact_version(context: RequestContext, arguments: dict) -> dict:
    payload = {key: arguments[key] for key in ("artifact_id", "version", "expected_version")}
    def restore():
        return service.restore_version(
            context, arguments["artifact_id"], arguments["version"],
            expected_version=arguments["expected_version"],
        )
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "artifacts.restore_version", payload, restore,
    ))


@register_tool(
    name="artifacts.finalize_to_project", capability="artifacts", effect="write", requires_project=True,
    description="Confirma a versão atual de um documento, vincula ao projeto e substitui sua versão anterior no índice de conhecimento.",
    exposures=("internal", "customer_agent"),
    input_schema={"type":"object", "required":["request_id", "confirmed", "artifact_id", "expected_version"], "properties":{
        "request_id":{"type":"string", "minLength":36, "maxLength":36},
        "confirmed":{"type":"boolean", "enum":[True]},
        "artifact_id":{"type":"string", "minLength":1, "maxLength":80},
        "expected_version":{"type":"integer", "minimum":1},
    }, "additionalProperties":False},
)
def finalize_artifact(context: RequestContext, arguments: dict) -> dict:
    payload = {"artifact_id": arguments["artifact_id"], "expected_version": arguments["expected_version"]}
    return _domain(lambda: operations.execute(arguments["request_id"], context,
        "artifacts.finalize_to_project", payload,
        lambda: service.finalize_to_project(context, arguments["artifact_id"],
                                            expected_version=arguments["expected_version"])))


@register_tool(
    name="artifacts.archive", capability="artifacts", effect="write",
    description="Arquiva um artefato de forma recuperável. Disponível inicialmente apenas para agentes internos.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "artifact_id", "expected_version", "content"], "properties": {
        "request_id": {"type": "string", "minLength": 16, "maxLength": 80},
        "artifact_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "expected_version": {"type": "integer", "minimum": 1},
        "content": {"type": "object"},
    }, "additionalProperties": False},
)
def archive_artifact(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: service.patch_artifact(
        context, arguments["artifact_id"], arguments["content"],
        expected_version=arguments["expected_version"], status="archived",
        change_summary="Arquivado via MCP",
    ))
