"""Project-source tools. Binary transfer uses a short-lived upload intent."""

from werkzeug.exceptions import HTTPException

from ...agent_v2.contracts import RequestContext
from ... import project_source_service
from ... import project_index_service
from ... import project_resource_service
from ... import workspace_ingestion_service
from ...conversations.service import project_knowledge_context
from ....db import get_db
import json
from .. import operations
from ..registry import ToolError, ToolInputError, register_tool


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
    name="projects.search_knowledge", capability="workspace", effect="read", requires_project=True,
    description="Pesquisa a base RAG indexada do projeto (busca híbrida lexical e semântica), com trechos citáveis, IDs de fonte e recurso.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["query"], "properties": {
        "query": {"type": "string", "minLength": 2, "maxLength": 400},
        "limit": {"type": "integer", "minimum": 1, "maximum": 12}}, "additionalProperties": False},
)
def search_knowledge(context: RequestContext, arguments: dict) -> dict:
    if not str(context.project_ref or "").startswith("ci:"):
        raise ToolInputError("Selecione um projeto nativo do Cadu para pesquisar fontes indexadas.")
    query = " ".join(arguments["query"].split())
    if len(query) < 2:
        raise ToolInputError("Informe o que deve ser pesquisado nas fontes do projeto.")
    try:
        packet = json.loads(project_knowledge_context(context.project_ref, context.brand_ref,
                                                      context.client_id, query,
                                                      result_limit=arguments.get("limit", 8),
                                                      strict_retrieval=True) or "{}")
    except Exception as exc:
        raise ToolError("A busca indexada está indisponível; não trate isto como ausência de resultados.") from exc
    if not packet.get("projeto"):
        raise ToolInputError("Projeto indisponível para esta conta.")
    return {"project_ref": context.project_ref, "query": query,
            "results": packet.get("fontes_verificadas") or [],
            "retrieval_mode": "hybrid_with_lexical_fallback",
            "next_step": "Use projects.get_source_chunks com source_id para ler o contexto adicional."}


@register_tool(
    name="projects.get_source_chunks", capability="workspace", effect="read", requires_project=True,
    description="Lê trechos paginados de uma fonte indexada do projeto, com IDs citáveis e sem expor caminhos de armazenamento.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["source_id"], "properties": {
        "source_id": {"type": "integer", "minimum": 1},
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "additionalProperties": False},
)
def get_source_chunks(context: RequestContext, arguments: dict) -> dict:
    if not str(context.project_ref or "").startswith("ci:"):
        raise ToolInputError("Selecione um projeto nativo do Cadu para ler fontes indexadas.")
    source_id = arguments["source_id"]
    project_id = context.project_ref[3:]
    limit, offset = arguments.get("limit", 10), arguments.get("offset", 0)
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT id, nome_arquivo AS name, mime AS mime_type, indexing_status,
                                 category, word_count, created_at
                            FROM cadu_ci_projeto_arquivos
                           WHERE id=%s AND projeto_id=%s AND id_cliente=%s
                             AND purpose='knowledge_source' AND indexing_status <> 'superseded'""",
                       (source_id, project_id, context.client_id))
        row = cursor.fetchone()
        if not row:
            raise ToolInputError("Fonte indexada indisponível neste projeto.")
        source = dict(row)
        cursor.execute("""SELECT COUNT(*) AS total FROM cadu_ci_chunks
                           WHERE arquivo_id=%s AND projeto_id=%s AND id_cliente=%s""",
                       (source_id, project_id, context.client_id))
        total = int((cursor.fetchone() or {}).get("total") or 0)
        cursor.execute("""SELECT id AS chunk_id, ordem AS position, titulo AS title,
                                 conteudo AS content, content_hash, embedding_model
                            FROM cadu_ci_chunks
                           WHERE arquivo_id=%s AND projeto_id=%s AND id_cliente=%s
                        ORDER BY ordem, id LIMIT %s OFFSET %s""",
                       (source_id, project_id, context.client_id, limit, offset))
        chunks = [dict(item) for item in cursor.fetchall()]
    from ...project_resource_service import resource_id_for_source
    return {"project_ref": context.project_ref, "source": source,
            "resource_id": resource_id_for_source(context.client_id, context.project_ref, "workspace", f"file:{source_id}"),
            "chunks": chunks, "total": total, "next_offset": offset + len(chunks) if offset + len(chunks) < total else None}


@register_tool(
    name="projects.list_resources", capability="workspace", effect="read", requires_project=True,
    description="Lista o inventário central do projeto: arquivos, artefatos versionados, planos, relatórios, mídia e referências de plataformas externas.",
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
    name="projects.inspect_link", capability="workspace", effect="read",
    description="Identifica plataforma, tipo provável, acesso e possibilidade segura de preview antes de salvar um link.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["url"], "properties": {
        "url": {"type": "string", "minLength": 8, "maxLength": 2000},
        "title": {"type": "string", "maxLength": 180},
    }, "additionalProperties": False},
)
def inspect_link(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: project_source_service.describe_link(
        arguments["url"], arguments.get("title", ""),
    ))


@register_tool(
    name="projects.ingestion_status", capability="workspace", effect="read", requires_project=True,
    description="Consulta o andamento real de classificação e extração das entradas recentes do projeto.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    }, "additionalProperties": False},
)
def ingestion_status(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: workspace_ingestion_service.list_recent(
        context, limit=arguments.get("limit", 20),
    ))


@register_tool(
    name="projects.create_link_reference", capability="workspace", effect="write", requires_project=True,
    description="Adiciona ao projeto um recurso de qualquer plataforma por URL, preservando tipo, origem, identificador externo, descrição e etiquetas sem copiar ou indexar o conteúdo remoto.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "url"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "url": {"type": "string", "minLength": 8, "maxLength": 2000},
        "title": {"type": "string", "maxLength": 180},
        "resource_kind": {"type": "string", "enum": sorted(project_source_service.EXTERNAL_RESOURCE_KINDS)},
        "platform": {"type": "string", "maxLength": 120},
        "external_id": {"type": "string", "maxLength": 512},
        "description": {"type": "string", "maxLength": 4000},
        "tags": {"type": "array", "maxItems": 20, "items": {"type": "string", "minLength": 1, "maxLength": 64}},
    }, "additionalProperties": False},
)
def create_link_reference(context: RequestContext, arguments: dict) -> dict:
    payload = {key: arguments[key] for key in (
        "url", "title", "resource_kind", "platform", "external_id", "description", "tags"
    ) if key in arguments}
    return _domain(lambda: operations.execute(
        arguments["request_id"], context, "projects.create_link_reference", payload,
        lambda: workspace_ingestion_service.ingest_link(
            context, **payload, origin="mcp", request_id=arguments["request_id"],
        ),
    ))


@register_tool(
    name="projects.prepare_source_upload", capability="workspace", effect="draft", requires_project=True,
    description="Prepara upload privado de qualquer arquivo aceito, incluindo HTML, documentos, planilhas, apresentações, imagens, áudio, vídeo e pacotes criativos. Sem use_as_knowledge, preserva o arquivo no inventário e só indexa formatos pesquisáveis quando apropriado.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "use_as_knowledge": {"type": "boolean"},
        "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
        "description": {"type": "string", "maxLength": 4000, "description": "Descrição factual do item, especialmente útil para indexar imagens geradas sem texto ou arquivos criativos."},
    }, "additionalProperties": False},
)
def prepare_source_upload(context: RequestContext, arguments: dict) -> dict:
    return _domain(lambda: project_source_service.prepare_upload(
        context, request_id=arguments["request_id"],
        use_as_knowledge=arguments.get("use_as_knowledge"), category=arguments.get("category"),
        description=arguments.get("description", ""),
    ))


@register_tool(
    name="projects.reindex_source", capability="workspace", effect="write", requires_project=True,
    description="Reprocessa uma fonte de conhecimento do projeto após confirmação explícita.",
    exposures=("internal", "customer_agent"),
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
    description="Adiciona texto produzido na conversa como fonte indexada do projeto, classificando a categoria automaticamente se não for informada.",
    exposures=("internal", "customer_agent"),
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
