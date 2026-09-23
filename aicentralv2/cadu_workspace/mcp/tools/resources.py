"""Provider-neutral resource tools backed by registry and indexed content."""

import json
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException

from ...agent_v2.contracts import RequestContext
from ... import project_resource_service, project_source_service, workspace_ingestion_service
from ...artifacts import service as artifact_service
from ...artifacts.catalog import ALLOWED_TYPES, definition
from ...conversations.service import project_knowledge_context
from .. import operations
from ..registry import ToolInputError, register_tool


EDITABLE_COPY_TYPES = tuple(sorted(
    artifact_type for artifact_type in ALLOWED_TYPES
    if definition(artifact_type).agent_editable and artifact_type != "project_map"
))
RESOURCE_ADD_MODES = ("editable", "external_link", "file_upload")


def _project_resource(context: RequestContext, resource_id: str) -> dict:
    resource = project_resource_service.get_resource(
        context.client_id, context.project_ref or "", resource_id,
    )
    if not resource:
        raise ToolInputError("Recurso indisponível neste projeto.")
    return resource


def _image_suffix(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"RIFF") and len(payload) >= 12 and payload[8:12] == b"WEBP":
        return ".webp"
    raise ToolInputError("O recurso não contém uma imagem PNG, JPG ou WebP válida.")


def _studio_image_reference(context: RequestContext, resource: dict, request_id: str) -> dict:
    """Copy an authorized project image into Studio-owned reference storage."""
    from ....creative_modeling_storage import CreativeAssetStorage
    from ... import project_sources

    locator = str(resource.get("locator") or "").strip()
    title = str(resource.get("title") or "imagem").strip()[:180]
    source_system = str(resource.get("source_system") or "")
    source_id = str(resource.get("source_id") or "")
    payload = None

    if source_system == "workspace" and source_id.startswith("file:"):
        if not locator.startswith("workspace_project_sources/"):
            raise ToolInputError("A imagem do projeto não possui uma cópia privada disponível.")
        root = str(current_app.config.get("WORKSPACE_SOURCE_STORAGE_DIR") or current_app.instance_path)
        path = project_sources.resolve_private_path(root, locator)
        if path.is_file():
            payload = path.read_bytes()
    elif source_system == "workspace_images" and source_id.isdigit():
        from ....db import get_db
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT file_bytes,file_path FROM cadu_docs_client_images
                                WHERE id=%s AND id_cliente=%s AND projeto_id=%s AND ativo=true""",
                           (int(source_id), context.client_id,
                            str(context.project_ref or "").removeprefix("ci:")))
            owned = cursor.fetchone()
        if owned:
            payload = owned.get("file_bytes") or CreativeAssetStorage().read_public_bytes(
                str(owned.get("file_path") or "")
            )
    elif locator.startswith(("/static/uploads/creative_", "https://", "http://")):
        payload = CreativeAssetStorage().read_public_bytes(locator)

    if not payload:
        raise ToolInputError("Não foi possível preparar esta imagem para edição no Studio.")
    if len(payload) > 5 * 1024 * 1024:
        raise ToolInputError("A imagem excede 5 MB e precisa ser otimizada antes da edição no Studio.")

    suffix = _image_suffix(bytes(payload))
    upload = FileStorage(
        stream=BytesIO(payload), filename=f"{Path(title).stem or 'imagem'}{suffix}",
        content_type={".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg"),
    )
    storage_id = uuid5(
        NAMESPACE_URL,
        f"cadu-studio-reference:{context.client_id}:{context.project_ref}:{resource.get('id')}:{request_id}",
    ).hex
    saved = CreativeAssetStorage().save_reference(upload, storage_id=storage_id)
    return {**saved, "title": title, "source_resource_id": str(resource.get("id") or "")}


@register_tool(
    name="resources.inspect_input", capability="workspace", effect="read",
    description="Classifica texto, URL ou arquivo e indica o mode correto de resources.add sem salvar nada.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "filename": {"type": "string", "maxLength": 220},
        "mime_type": {"type": "string", "maxLength": 160},
        "url": {"type": "string", "maxLength": 2000},
        "text": {"type": "string", "maxLength": 5000},
        "requested_purpose": {"type": "string", "enum": ["conversation", "knowledge_source", "project_attachment", "artifact"]},
    }, "additionalProperties": False},
)
def inspect_input(_context: RequestContext, arguments: dict) -> dict:
    try:
        result = project_source_service.classify_intake(**arguments)
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
    mode = {"link": "external_link", "file": "file_upload", "text": "editable"}.get(result.get("input_type"))
    return {**result, "recommended_tool": "resources.add", "recommended_mode": mode}


@register_tool(
    name="resources.add", capability="workspace", effect="draft", requires_project=True,
    description=(
        "Entrada unificada do projeto. Use mode=editable para texto/HTML editável, external_link para recursos de outras plataformas "
        "e file_upload para preparar o envio privado de arquivos. Nunca declara o upload concluído antes do binário."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "mode"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "mode": {"type": "string", "enum": RESOURCE_ADD_MODES},
        "title": {"type": "string", "maxLength": 180},
        "url": {"type": "string", "maxLength": 2000},
        "resource_kind": {"type": "string", "enum": sorted(project_source_service.EXTERNAL_RESOURCE_KINDS)},
        "platform": {"type": "string", "maxLength": 120},
        "external_id": {"type": "string", "maxLength": 512},
        "description": {"type": "string", "maxLength": 4000},
        "tags": {"type": "array", "maxItems": 20, "items": {"type": "string", "minLength": 1, "maxLength": 64}},
        "type": {"type": "string", "enum": EDITABLE_COPY_TYPES},
        "content": {"type": "object"},
        "source_resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "use_as_knowledge": {"type": "boolean"},
        "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
    }, "additionalProperties": False},
)
def add_resource(context: RequestContext, arguments: dict) -> dict:
    mode = arguments["mode"]
    request_id = arguments["request_id"]
    if mode == "file_upload":
        result = project_source_service.prepare_upload(
            context, request_id=request_id, use_as_knowledge=arguments.get("use_as_knowledge"),
            category=arguments.get("category"), description=arguments.get("description", ""),
        )
        return {**result, "status": "awaiting_upload", "resource_created": False}

    if mode == "external_link":
        if not str(arguments.get("url") or "").strip():
            raise ToolInputError("Informe a URL do recurso externo.")
        payload = {key: arguments[key] for key in (
            "url", "title", "resource_kind", "platform", "external_id", "description", "tags"
        ) if key in arguments}
        return operations.execute(
            request_id, context, "resources.add", {"mode": mode, **payload},
            lambda: workspace_ingestion_service.ingest_link(
                context, **payload, origin="mcp", request_id=request_id,
            ),
        )

    if not str(arguments.get("title") or "").strip() or not isinstance(arguments.get("content"), dict):
        raise ToolInputError("Informe title e content para criar uma entrega editável.")
    artifact_type = str(arguments.get("type") or "document")
    source_resource_id = str(arguments.get("source_resource_id") or "")
    if source_resource_id:
        source = _project_resource(context, source_resource_id)
        capabilities = project_resource_service.resource_capabilities(source)
        if not capabilities.get("actions", {}).get("create_editable_copy"):
            limitation = next(iter(capabilities.get("limitations") or []), "A fonte não permite cópia editável.")
            raise ToolInputError(limitation)
    artifact_id = str(uuid5(
        NAMESPACE_URL, f"cadu-resource-add:{context.client_id}:{context.project_ref}:{request_id}",
    ))
    payload = {key: arguments[key] for key in ("mode", "title", "type", "content", "source_resource_id") if key in arguments}

    def create_editable():
        artifact = artifact_service.create_draft(
            context, artifact_type, arguments["content"], title=arguments["title"],
            conversation_id=context.conversation_id, artifact_id=artifact_id,
        )
        project_resource_service.reconcile(context.client_id, context.project_ref, context.user_id)
        resource_id = project_resource_service.resource_id_for_source(
            context.client_id, context.project_ref, "cadu_workspace_artifacts", artifact_id,
        )
        relation = None
        if source_resource_id:
            relation = project_resource_service.relate_resources(
                context.client_id, context.project_ref, resource_id, source_resource_id, "derived_from",
                metadata={"artifact_id": artifact_id, "preserved_original": True},
            )
        return {"status": "created", "resource_created": True, "resource_id": resource_id,
                "artifact": artifact, "relation": relation, "preserved_original": bool(source_resource_id)}

    return operations.execute(request_id, context, "resources.add", payload, create_editable)


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
            "include_archived": {"type": "boolean"},
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
            include_archived=arguments.get("include_archived", False),
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
    return {"project_ref": context.project_ref, "resource": resource,
            "capabilities": project_resource_service.resource_capabilities(resource)}


@register_tool(
    name="resources.capabilities",
    capability="workspace",
    effect="read",
    requires_project=True,
    description="Informa modo de edição, editor, cópia editável, derivações, sincronização e ações realmente autorizadas, sem presumir escrita no provedor.",
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


@register_tool(
    name="resources.start_image_edit", capability="workspace", effect="write", requires_project=True,
    description=(
        "Prepara uma imagem do projeto no armazenamento do Studio, cria uma sessão retomável de edição e preserva o original. "
        "Não gera nem altera pixels e não consome créditos."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object", "required": ["request_id", "resource_id", "prompt"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "prompt": {"type": "string", "minLength": 3, "maxLength": 4000},
            "title": {"type": "string", "maxLength": 160},
            "brand_id": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    },
)
def start_image_edit(context: RequestContext, arguments: dict) -> dict:
    from ....creative_media.studio import _session_store
    from . import media

    resource = _project_resource(context, arguments["resource_id"])
    capabilities = project_resource_service.resource_capabilities(resource)
    if capabilities.get("editor") != "studio" or not capabilities.get("actions", {}).get("open_in_editor"):
        limitation = next(iter(capabilities.get("limitations") or []), "Este recurso não pode ser aberto no Studio.")
        raise ToolInputError(limitation)

    fingerprint = {key: arguments.get(key) for key in ("resource_id", "prompt", "title", "brand_id")}

    def prepare():
        reference = _studio_image_reference(context, resource, arguments["request_id"])
        session = media.start_studio_session(context, {
            "kind": "image_edit", "prompt": arguments["prompt"],
            "title": arguments.get("title") or f"Editar {resource.get('title') or 'imagem'}",
            "source_url": reference["asset_path"], "source_id": arguments["resource_id"],
            "brand_id": arguments.get("brand_id"), "request_id": arguments["request_id"],
        })
        store = _session_store(int(session["creative_client_id"]))
        store.accept(int(session["creative_client_id"]), context.user_id, session["session_id"], {
            "role": "base", "kind": "image", "source_type": "workspace_resource",
            "source_id": arguments["resource_id"], "title": reference["title"],
            "asset_url": reference["asset_path"], "storage_key": reference["asset_path"],
            "metadata": {"origin": "workspace_project", "project_ref": context.project_ref,
                         "resource_id": arguments["resource_id"], "preserved_original": True},
        })
        return {**session, "status": "ready", "source_resource_id": arguments["resource_id"],
                "source_asset_url": reference["asset_path"], "preserved_original": True,
                "generation_status": "not_started", "credits_consumed": False}

    return operations.execute(
        arguments["request_id"], context, "resources.start_image_edit", fingerprint, prepare,
    )


@register_tool(
    name="resources.create_editable_copy", capability="workspace", effect="draft", requires_project=True,
    description=(
        "Cria no Cadu uma entrega editável e versionada derivada de um recurso legível, preservando o original e registrando a relação. "
        "Não edita PDF nem provedor externo. Para imagens, use o Studio."
    ),
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object", "required": ["request_id", "source_resource_id", "type", "title", "content"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "source_resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "type": {"type": "string", "enum": EDITABLE_COPY_TYPES},
            "title": {"type": "string", "minLength": 1, "maxLength": 180},
            "content": {"type": "object"},
        },
        "additionalProperties": False,
    },
)
def create_editable_copy(context: RequestContext, arguments: dict) -> dict:
    source = _project_resource(context, arguments["source_resource_id"])
    capabilities = project_resource_service.resource_capabilities(source)
    if capabilities.get("editor") == "studio":
        raise ToolInputError("Imagens devem ser preparadas e editadas pelo Studio; use resources.start_image_edit.")
    if not capabilities.get("actions", {}).get("create_editable_copy"):
        limitation = next(iter(capabilities.get("limitations") or []), "O recurso não permite cópia editável.")
        raise ToolInputError(limitation)
    artifact_id = str(uuid5(
        NAMESPACE_URL,
        f"cadu-editable-copy:{context.client_id}:{context.project_ref}:{arguments['request_id']}",
    ))
    payload = {key: arguments[key] for key in ("source_resource_id", "type", "title", "content")}

    def create():
        artifact = artifact_service.create_draft(
            context, arguments["type"], arguments["content"], title=arguments["title"],
            conversation_id=context.conversation_id, artifact_id=artifact_id,
        )
        project_resource_service.reconcile(context.client_id, context.project_ref, context.user_id)
        target_resource_id = project_resource_service.resource_id_for_source(
            context.client_id, context.project_ref, "cadu_workspace_artifacts", artifact_id,
        )
        relation = project_resource_service.relate_resources(
            context.client_id, context.project_ref, target_resource_id,
            arguments["source_resource_id"], "derived_from",
            metadata={"artifact_id": artifact_id, "preserved_original": True},
        )
        return {
            "artifact": artifact, "resource_id": target_resource_id,
            "source_resource_id": arguments["source_resource_id"], "relation": relation,
            "preserved_original": True, "edit_mode": "native",
        }

    return operations.execute(
        arguments["request_id"], context, "resources.create_editable_copy", payload, create,
    )


@register_tool(
    name="resources.list_versions", capability="workspace", effect="read", requires_project=True,
    description="Lista versões reais de um recurso. Para fontes sem histórico acessível, retorna apenas a versão conhecida e explicita a limitação.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object", "required": ["resource_id"], "properties": {
            "resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        }, "additionalProperties": False,
    },
)
def list_versions(context: RequestContext, arguments: dict) -> dict:
    resource = _project_resource(context, arguments["resource_id"])
    if resource.get("source_system") == "cadu_workspace_artifacts":
        versions = artifact_service.list_versions(
            context, str(resource.get("source_id") or ""), limit=arguments.get("limit", 50),
        )
        return {"resource_id": arguments["resource_id"], "versions": versions,
                "version_source": "cadu", "complete": True}
    current = int(resource.get("version") or 1)
    return {
        "resource_id": arguments["resource_id"],
        "versions": [{"version": current, "known_at": resource.get("source_updated_at") or resource.get("last_seen_at")}],
        "version_source": "registry_snapshot", "complete": False,
        "limitation": "A origem ainda não oferece histórico de versões ao Cadu.",
    }


@register_tool(
    name="resources.list_relations", capability="workspace", effect="read", requires_project=True,
    description="Lista origens, derivações e dependências conhecidas de um recurso no projeto.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["resource_id"], "properties": {
        "resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
    }, "additionalProperties": False},
)
def list_relations(context: RequestContext, arguments: dict) -> dict:
    _project_resource(context, arguments["resource_id"])
    return {"resource_id": arguments["resource_id"], "relations": project_resource_service.list_resource_relations(
        context.client_id, context.project_ref, arguments["resource_id"],
    )}


@register_tool(
    name="resources.relate", capability="workspace", effect="draft", requires_project=True,
    description="Relaciona dois recursos do mesmo projeto de forma idempotente, sem mover, copiar ou alterar seus conteúdos.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": [
        "request_id", "source_resource_id", "target_resource_id", "relation_type",
    ], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "source_resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "target_resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "relation_type": {"type": "string", "enum": ["derived_from", "references", "uses", "revises", "exports"]},
        "description": {"type": "string", "maxLength": 500},
    }, "additionalProperties": False},
)
def relate(context: RequestContext, arguments: dict) -> dict:
    _project_resource(context, arguments["source_resource_id"])
    _project_resource(context, arguments["target_resource_id"])
    payload = {key: arguments[key] for key in (
        "source_resource_id", "target_resource_id", "relation_type", "description"
    ) if key in arguments}
    return operations.execute(
        arguments["request_id"], context, "resources.relate", payload,
        lambda: project_resource_service.relate_resources(
            context.client_id, context.project_ref, arguments["source_resource_id"],
            arguments["target_resource_id"], arguments["relation_type"],
            metadata={"description": str(arguments.get("description") or "")[:500]},
        ),
    )


@register_tool(
    name="resources.update_metadata", capability="workspace", effect="draft", requires_project=True,
    description="Atualiza título, descrição ou etiquetas na fonte canônica do recurso; nunca escreve diretamente no inventário reconstruível.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "resource_id", "changes"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "changes": {"type": "object", "minProperties": 1, "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 180},
            "description": {"type": "string", "maxLength": 4000},
            "tags": {"type": "array", "maxItems": 20, "items": {"type": "string", "minLength": 1, "maxLength": 64}},
        }, "additionalProperties": False},
    }, "additionalProperties": False},
)
def update_metadata(context: RequestContext, arguments: dict) -> dict:
    changes = arguments["changes"]
    if not changes:
        raise ToolInputError("Informe ao menos uma alteração de metadados.")
    try:
        return operations.execute(
            arguments["request_id"], context, "resources.update_metadata",
            {"resource_id": arguments["resource_id"], "changes": changes},
            lambda: project_resource_service.update_resource_metadata(
                context, arguments["resource_id"], changes,
            ),
        )
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc


@register_tool(
    name="resources.set_archived", capability="workspace", effect="write", requires_project=True,
    description="Arquiva ou restaura um artefato ou referência externa sem apagar conteúdo, versões ou relações. Exige confirmação explícita.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "resource_id", "archived"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "resource_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "archived": {"type": "boolean"},
    }, "additionalProperties": False},
)
def set_archived(context: RequestContext, arguments: dict) -> dict:
    payload = {"resource_id": arguments["resource_id"], "archived": arguments["archived"]}
    try:
        return operations.execute(
            arguments["request_id"], context, "resources.set_archived", payload,
            lambda: project_resource_service.set_resource_archived(
                context, arguments["resource_id"], arguments["archived"],
            ),
        )
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc
