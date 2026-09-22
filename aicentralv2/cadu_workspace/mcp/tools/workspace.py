"""Workspace tools.  Every query remains scoped to RequestContext.client_id."""

import json
import re
from dataclasses import replace
from uuid import uuid4

from ....cadu_family import repository
from ....db import get_db
from ...agent_v2.contracts import RequestContext
from ...conversations.service import project_knowledge_context
from ...project_portfolio_service import attach_summaries
from ... import project_source_service, workspace_ingestion_service
from .. import operations
from ..registry import ToolInputError, register_tool


def _native_project_id(context: RequestContext) -> str:
    project_ref = str(context.project_ref or "")
    if not project_ref.startswith("ci:"):
        raise ToolInputError("Selecione um projeto nativo do Cadu para realizar esta ação.")
    project_id = project_ref[3:]
    records = repository.rows(
        "SELECT id FROM cadu_ci_projetos WHERE id=%s AND id_cliente=%s AND status <> 'deletado'",
        (project_id, context.client_id),
    )
    if not records:
        raise ToolInputError("Projeto indisponível.")
    return project_id


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
            "visibility": {"type": "string", "enum": ["private", "team", "restricted"]},
            "people": {"type": "array", "maxItems": 50, "items": {"type": "object", "required": ["user_id", "role"], "properties": {
                "user_id": {"type": "integer", "minimum": 1}, "role": {"type": "string", "enum": ["admin", "editor", "member", "viewer"]},
            }, "additionalProperties": False}},
            "links": {"type": "array", "maxItems": 20, "items": {"type": "object", "required": ["url"], "properties": {
                "url": {"type": "string", "minLength": 8, "maxLength": 2000}, "title": {"type": "string", "maxLength": 180},
            }, "additionalProperties": False}},
            "notes": {"type": "array", "maxItems": 10, "items": {"type": "object", "required": ["title", "content"], "properties": {
                "title": {"type": "string", "minLength": 2, "maxLength": 180}, "content": {"type": "string", "minLength": 20, "maxLength": 50000},
                "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
            }, "additionalProperties": False}},
            "file_uploads": {"type": "array", "maxItems": 10, "items": {"type": "object", "properties": {
                "use_as_knowledge": {"type": "boolean"}, "category": {"type": "string", "enum": sorted(project_source_service.CATEGORIES)},
            }, "additionalProperties": False}},
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
        "idempotency_key": str(arguments["request_id"]),
    }
    visibility = str(arguments.get("visibility") or "private")
    people = list(arguments.get("people") or [])
    links = list(arguments.get("links") or [])
    notes = list(arguments.get("notes") or [])
    file_uploads = list(arguments.get("file_uploads") or [])
    if people:
        visibility = "restricted"
    if visibility != "private" or people:
        actor = repository.actor(context.user_id) or {}
        if repository.account_role(actor) != "admin":
            raise ToolInputError("Somente administradores podem criar um projeto compartilhado.")
        if int(actor.get("organization_id") or 0) != context.organization_id:
            raise ToolInputError("A conta não pertence a esta organização.")
        active_team = {int(item["id"]) for item in repository.team(context.organization_id) if item.get("status")}
        if any(int(item["user_id"]) not in active_team for item in people):
            raise ToolInputError("Todas as pessoas precisam pertencer à equipe ativa.")
    operation_payload = {**payload, "visibility": visibility, "people": people,
                         "links": links, "notes": notes,
                         "file_uploads": file_uploads}

    def create():
        try:
            project_ref = repository.create_entity(context.client_id, context.user_id, payload)
        except ValueError as exc:
            raise ToolInputError(str(exc)) from exc
        repository.seed_project_owner(context.client_id, project_ref, context.user_id)
        repository.set_project_visibility(context.client_id, context.user_id, project_ref, visibility)
        for item in people:
            repository.grant_project_access(context.client_id, project_ref, int(item["user_id"]), item["role"], context.user_id)
        project_context = replace(context, project_ref=project_ref)
        resources = {"links": [], "notes": [], "uploads": [], "errors": []}
        for item in links:
            try:
                resources["links"].append(workspace_ingestion_service.ingest_link(
                    project_context, url=item["url"], title=item.get("title", ""),
                    origin="mcp", request_id=str(uuid4()),
                ))
            except Exception as exc:
                resources["errors"].append({"type": "link", "value": item.get("url"), "error": str(exc)[:240]})
        for item in notes:
            try:
                resources["notes"].append(project_source_service.create_note(project_context, **item))
            except Exception as exc:
                resources["errors"].append({"type": "note", "value": item.get("title"), "error": str(exc)[:240]})
        for item in file_uploads:
            try:
                resources["uploads"].append(project_source_service.prepare_upload(
                    project_context, request_id=str(uuid4()),
                    use_as_knowledge=bool(item.get("use_as_knowledge", True)), category=item.get("category"),
                ))
            except Exception as exc:
                resources["errors"].append({"type": "file_upload", "error": str(exc)[:240]})
        result = {"project_ref": project_ref, "name": payload["name"], "status": "created"}
        if links or notes or file_uploads or people or visibility != "private":
            result.update({"visibility": visibility, "shared_count": len(people), "resources": resources})
        return result

    return operations.execute(arguments["request_id"], context, "workspace.create_project", operation_payload, create)


@register_tool(
    name="workspace.update_project_context", capability="workspace", effect="write", requires_project=True,
    description="Atualiza campos de contexto do projeto atual após confirmação explícita.",
    exposures=("internal",),
    input_schema={
        "type": "object", "required": ["request_id", "confirmed"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "confirmed": {"type": "boolean", "enum": [True]},
            "name": {"type": "string", "minLength": 2, "maxLength": 150},
            "description": {"type": "string", "maxLength": 4000},
            "instructions": {"type": "string", "maxLength": 12000},
            "tone_of_voice": {"type": "string", "maxLength": 4000},
            "audience": {"type": "string", "maxLength": 4000},
            "positioning": {"type": "string", "maxLength": 4000},
            "color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
        }, "additionalProperties": False,
    },
)
def update_project_context(context: RequestContext, arguments: dict) -> dict:
    project_id = _native_project_id(context)
    fields = ("name", "description", "instructions", "tone_of_voice", "audience", "positioning", "color")
    payload = {key: arguments[key] for key in fields if key in arguments}
    if not payload:
        raise ToolInputError("Informe ao menos um campo do projeto para atualizar.")
    if "name" in payload:
        payload["name"] = " ".join(str(payload["name"]).split())[:150]
        if len(payload["name"]) < 2:
            raise ToolInputError("O projeto precisa de um nome com ao menos dois caracteres.")
    if "color" in payload and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(payload["color"])):
        raise ToolInputError("Use uma cor hexadecimal válida para o projeto.")
    column = {"name": "nome", "description": "descricao", "instructions": "instrucoes",
              "tone_of_voice": "tom_de_voz", "audience": "publico", "positioning": "posicionamento",
              "color": "cor"}

    def update():
        assignments = ", ".join(f"{column[key]}=%s" for key in payload)
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE cadu_ci_projetos SET {assignments}, updated_at=NOW() "
                    "WHERE id=%s AND id_cliente=%s RETURNING id,nome,updated_at",
                    (*payload.values(), project_id, context.client_id),
                )
                result = cursor.fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return {"project_ref": context.project_ref, "project_id": str(result["id"]),
                "name": result["nome"], "updated_fields": sorted(payload), "status": "updated"}

    return operations.execute(arguments["request_id"], context, "workspace.update_project_context", payload, update)


@register_tool(
    name="workspace.set_project_status", capability="workspace", effect="write", requires_project=True,
    description="Arquiva ou reativa o projeto atual após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "status"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "status": {"type": "string", "enum": ["ativo", "arquivado"]},
    }, "additionalProperties": False},
)
def set_project_status(context: RequestContext, arguments: dict) -> dict:
    project_id = _native_project_id(context)
    status = arguments["status"]

    def update():
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE cadu_ci_projetos SET status=%s,updated_at=NOW() "
                               "WHERE id=%s AND id_cliente=%s RETURNING nome,status",
                               (status, project_id, context.client_id))
                result = cursor.fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return {"project_ref": context.project_ref, "name": result["nome"],
                "status": result["status"]}

    return operations.execute(arguments["request_id"], context, "workspace.set_project_status", {"status": status}, update)


@register_tool(
    name="workspace.link_current_brand", capability="workspace", effect="write", requires_project=True,
    description="Vincula ou desvincula a marca selecionada ao projeto atual após confirmação.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "linked"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "linked": {"type": "boolean"},
    }, "additionalProperties": False},
)
def link_current_brand(context: RequestContext, arguments: dict) -> dict:
    _native_project_id(context)
    brand_ref = str(context.brand_ref or "")
    entities = {item.get("ref"): item for item in repository.entities(context.client_id)}
    if not brand_ref or (entities.get(brand_ref) or {}).get("kind") != "brand":
        raise ToolInputError("Selecione uma marca válida antes de alterar o vínculo do projeto.")
    linked = bool(arguments["linked"])

    def update():
        repository.set_project_brand_link(context.client_id, context.user_id, context.project_ref, brand_ref, linked)
        return {"project_ref": context.project_ref, "brand_ref": brand_ref,
                "brand_name": entities[brand_ref].get("name"), "linked": linked,
                "status": "linked" if linked else "unlinked"}

    return operations.execute(arguments["request_id"], context, "workspace.link_current_brand", {"linked": linked}, update)


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
    name="workspace.list_project_shares", capability="workspace", requires_project=True,
    description="Lista a visibilidade e as pessoas com acesso ao projeto atual.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def list_project_shares(context: RequestContext, arguments: dict) -> dict:
    _native_project_id(context)
    if not repository.project_user_can_view(context.client_id, context.project_ref, context.user_id):
        raise ToolInputError("Você não tem acesso a este projeto.")
    visibility = repository.project_visibility(context.client_id, context.project_ref)
    members = repository.project_access(context.client_id, context.project_ref)
    return {
        "project_ref": context.project_ref,
        "visibility": visibility.get("visibility", "private"),
        "members": [{"user_id": str(item.get("user_id")), "name": item.get("name") or "Pessoa da equipe",
                     "email": item.get("email") or "", "role": item.get("role"),
                     "source": item.get("source"), "status": "active" if item.get("status") else "inactive"}
                    for item in members],
    }


@register_tool(
    name="workspace.set_project_visibility", capability="workspace", effect="write", requires_project=True,
    description="Altera a visibilidade do projeto atual após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "visibility"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "visibility": {"type": "string", "enum": ["private", "team", "restricted"]},
    }, "additionalProperties": False},
)
def set_project_visibility(context: RequestContext, arguments: dict) -> dict:
    _native_project_id(context)
    actor = repository.actor(context.user_id) or {}
    if repository.account_role(actor) != 'admin':
        raise ToolInputError("Somente administradores podem alterar o compartilhamento do projeto.")
    visibility = arguments["visibility"]

    def update():
        repository.set_project_visibility(context.client_id, context.user_id, context.project_ref, visibility)
        return {"project_ref": context.project_ref, "visibility": visibility, "status": "updated"}

    return operations.execute(arguments["request_id"], context, "workspace.set_project_visibility", {"visibility": visibility}, update)


@register_tool(
    name="workspace.share_project_with_people", capability="workspace", effect="write", requires_project=True,
    description="Concede acesso direto a pessoas ativas da equipe após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "people"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "people": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "object", "required": ["user_id", "role"], "properties": {
            "user_id": {"type": "integer", "minimum": 1}, "role": {"type": "string", "enum": ["admin", "editor", "member", "viewer"]},
        }, "additionalProperties": False}},
    }, "additionalProperties": False},
)
def share_project_with_people(context: RequestContext, arguments: dict) -> dict:
    _native_project_id(context)
    actor = repository.actor(context.user_id) or {}
    if repository.account_role(actor) != 'admin':
        raise ToolInputError("Somente administradores podem compartilhar o projeto.")
    team = {int(item['id']) for item in repository.team(actor['organization_id']) if item.get('status')}
    people = arguments['people']
    if any(int(item['user_id']) not in team for item in people):
        raise ToolInputError("Todas as pessoas precisam pertencer à equipe ativa.")

    def update():
        for item in people:
            repository.grant_project_access(context.client_id, context.project_ref, int(item['user_id']), item['role'], context.user_id)
        repository.set_project_visibility(context.client_id, context.user_id, context.project_ref, 'restricted')
        return {"project_ref": context.project_ref, "visibility": "restricted", "shared_count": len(people), "status": "updated"}

    return operations.execute(arguments["request_id"], context, "workspace.share_project_with_people", {"people": people}, update)


@register_tool(
    name="workspace.share_project_with_team", capability="workspace", effect="write", requires_project=True,
    description="Compartilha o projeto com a equipe ativa após confirmação explícita.",
    exposures=("internal",),
    input_schema={"type": "object", "required": ["request_id", "confirmed"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
    }, "additionalProperties": False},
)
def share_project_with_team(context: RequestContext, arguments: dict) -> dict:
    _native_project_id(context)
    actor = repository.actor(context.user_id) or {}
    if repository.account_role(actor) != 'admin':
        raise ToolInputError("Somente administradores podem compartilhar o projeto.")

    def update():
        repository.set_project_visibility(context.client_id, context.user_id, context.project_ref, 'team')
        return {"project_ref": context.project_ref, "visibility": "team", "status": "updated"}

    return operations.execute(arguments["request_id"], context, "workspace.share_project_with_team", {}, update)


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
