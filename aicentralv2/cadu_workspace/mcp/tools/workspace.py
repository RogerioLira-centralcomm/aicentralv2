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
from ... import project_context_service, project_source_service, workspace_ingestion_service
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
    if not repository.project_user_can_view(context.client_id, project_ref, context.user_id):
        raise ToolInputError("Você não tem acesso a este projeto.")
    return project_id


def _require_project_editor(context: RequestContext) -> None:
    _native_project_id(context)
    actor = repository.actor(context.user_id) or {}
    if int(actor.get("organization_id") or 0) == context.client_id and repository.account_role(actor) == "admin":
        return
    roles = {item.get("role") for item in repository.project_access(context.client_id, context.project_ref)
             if int(item.get("user_id") or 0) == context.user_id}
    if not roles.intersection({"owner", "admin", "editor"}):
        raise ToolInputError("Você não pode editar este projeto.")


@register_tool(
    name="workspace.create_project", capability="workspace", effect="write",
    description="Cria um projeto nativo no Workspace. Só pode ser executado após confirmação explícita.",
    exposures=("internal", "customer_agent"),
    input_schema={
        "type": "object",
        "required": ["request_id", "name", "confirmed"],
        "properties": {
            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
            "name": {"type": "string", "minLength": 2, "maxLength": 150},
            "description": {"type": "string", "maxLength": 4000},
            "instructions": {"type": "string", "maxLength": 12000},
            "tone_of_voice": {"type": "string", "maxLength": 4000},
            "audience": {"type": "string", "maxLength": 4000},
            "positioning": {"type": "string", "maxLength": 4000},
            "color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
            "custom_fields": {"type": "array", "maxItems": 40, "items": {"type": "object", "required": ["key", "value"], "properties": {
                "key": {"type": "string", "minLength": 1, "maxLength": 80},
                "label": {"type": "string", "maxLength": 120},
                "type": {"type": "string", "enum": ["text", "list", "number", "currency", "date", "url"]},
                "value": {},
            }, "additionalProperties": False}},
            "brand_ref": {"type": "string", "minLength": 3, "maxLength": 120},
            "brand_name": {"type": "string", "minLength": 2, "maxLength": 150},
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
    direction_fields = {
        key: arguments[key] for key in ("tone_of_voice", "audience", "positioning", "color")
        if key in arguments
    }
    custom_fields = list(arguments.get("custom_fields") or [])
    try:
        normalized_custom_fields = project_context_service._custom_fields(custom_fields)
    except project_context_service.ProjectContextError as exc:
        raise ToolInputError(str(exc)) from exc
    if direction_fields.get("color") and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(direction_fields["color"])):
        raise ToolInputError("Use uma cor hexadecimal válida.")
    brand_ref = str(arguments.get("brand_ref") or "").strip()
    brand_name = " ".join(str(arguments.get("brand_name") or "").split())
    brands = ([item for item in repository.entities(context.client_id) if item.get("kind") == "brand"]
              if brand_ref or brand_name else [])
    if brand_ref:
        if not any(str(item.get("ref")) == brand_ref for item in brands):
            raise ToolInputError("A marca informada não existe neste workspace.")
    elif brand_name:
        matches = [item for item in brands if str(item.get("name") or "").casefold() == brand_name.casefold()]
        if len(matches) != 1:
            raise ToolInputError("Informe brand_ref: o nome da marca não foi encontrado de forma única.")
        brand_ref = str(matches[0]["ref"])
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
                         "file_uploads": file_uploads, "direction": direction_fields,
                         "custom_fields": custom_fields, "brand_ref": brand_ref or None}
    payload.update(direction_fields)
    if normalized_custom_fields:
        payload["custom_fields"] = normalized_custom_fields

    def create():
        try:
            project_ref, created = repository.create_entity(
                context.client_id, context.user_id, payload, return_created=True,
            )
        except ValueError as exc:
            raise ToolInputError(str(exc)) from exc
        try:
            repository.seed_project_owner(context.client_id, project_ref, context.user_id)
            repository.set_project_visibility(context.client_id, context.user_id, project_ref, visibility)
            if brand_ref:
                repository.set_project_brand_link(
                    context.client_id, context.user_id, project_ref, brand_ref, True,
                )
            for item in people:
                repository.grant_project_access(context.client_id, project_ref, int(item["user_id"]), item["role"], context.user_id)
        except Exception:
            # A retry may return a pre-existing idempotent project; never remove
            # that record. Only compensate the entity created by this attempt.
            if created:
                repository.discard_created_entity(context.client_id, project_ref)
            raise
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
        result = {
            "project_ref": project_ref, "name": payload["name"], "status": "created",
            "description": payload["description"], "instructions": payload["instructions"],
            "visibility": visibility,
        }
        if links or notes or file_uploads or people or visibility != "private":
            result.update({"shared_count": len(people), "resources": resources})
        if direction_fields or normalized_custom_fields:
            result["direction"] = {**direction_fields, "custom_fields": normalized_custom_fields}
        if brand_ref:
            result["brand_ref"] = brand_ref
        return result

    return operations.execute(arguments["request_id"], context, "workspace.create_project", operation_payload, create)


@register_tool(
    name="workspace.update_project_context", capability="workspace", effect="write", requires_project=True,
    description="Atualiza campos de contexto do projeto atual após confirmação explícita.",
    exposures=("internal", "customer_agent"),
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
            "custom_fields": {"type": "array", "maxItems": 40, "items": {"type": "object", "required": ["key", "value"], "properties": {
                "key": {"type": "string", "minLength": 1, "maxLength": 80},
                "label": {"type": "string", "maxLength": 120},
                "type": {"type": "string", "enum": ["text", "list", "number", "currency", "date", "url"]},
                "value": {},
            }, "additionalProperties": False}},
            "replace_custom_fields": {"type": "boolean"},
            "remove_custom_fields": {"type": "array", "maxItems": 40, "items": {"type": "string", "maxLength": 80}},
            "expected_revision": {"type": "integer", "minimum": 1},
        }, "additionalProperties": False,
    },
)
def update_project_context(context: RequestContext, arguments: dict) -> dict:
    _require_project_editor(context)
    fields = ("name", "description", "instructions", "tone_of_voice", "audience", "positioning", "color")
    payload = {key: arguments[key] for key in fields if key in arguments}
    custom_fields = arguments.get("custom_fields") or []
    remove_custom_fields = arguments.get("remove_custom_fields") or []
    operation_payload = {**payload, "custom_fields": custom_fields,
                         "remove_custom_fields": remove_custom_fields,
                         "replace_custom_fields": bool(arguments.get("replace_custom_fields"))}

    def update():
        try:
            return project_context_service.update_context(
                client_id=context.client_id, actor_id=context.user_id, project_ref=context.project_ref,
                standard_fields=payload, custom_fields=custom_fields,
                remove_custom_fields=remove_custom_fields,
                replace_custom_fields=bool(arguments.get("replace_custom_fields")),
                expected_revision=arguments.get("expected_revision"), source="conversation",
            )
        except project_context_service.ProjectContextError as exc:
            raise ToolInputError(str(exc)) from exc

    return operations.execute(arguments["request_id"], context, "workspace.update_project_context", operation_payload, update)


@register_tool(
    name="workspace.set_project_status", capability="workspace", effect="write", requires_project=True,
    description="Arquiva ou reativa o projeto atual após confirmação explícita.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "status"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "status": {"type": "string", "enum": ["ativo", "arquivado"]},
    }, "additionalProperties": False},
)
def set_project_status(context: RequestContext, arguments: dict) -> dict:
    _require_project_editor(context)
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
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "linked"], "properties": {
        "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "confirmed": {"type": "boolean", "enum": [True]},
        "linked": {"type": "boolean"},
    }, "additionalProperties": False},
)
def link_current_brand(context: RequestContext, arguments: dict) -> dict:
    _require_project_editor(context)
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
    native_ids = [str(row.get("ref"))[3:] for row in records if str(row.get("ref") or "").startswith("ci:")]
    directions = {}
    if native_ids:
        try:
            rows = repository.rows(
                """SELECT id,nome,descricao,instrucoes,tom_de_voz,publico,posicionamento,cor,
                          COALESCE(campos_personalizados,'{}'::jsonb) AS campos_personalizados,
                          context_revision,updated_at
                     FROM cadu_ci_projetos WHERE id_cliente=%s AND id::text=ANY(%s) AND status <> 'deletado'""",
                (context.client_id, native_ids),
            )
            directions = {f"ci:{row['id']}": project_context_service._snapshot(row) for row in rows}
        except Exception:
            directions = {}
    enriched = []
    for row in records:
        direction = directions.get(str(row.get("ref")))
        item = {key: row.get(key) for key in ("ref", "name", "source")}
        if direction:
            item.update({"context_revision": direction["revision"],
                         "context_items": project_context_service.context_items(direction)})
        enriched.append(item)
    if query:
        enriched = [row for row in enriched if query in (
            f"{row.get('name') or ''} " + " ".join(
                f"{item.get('label')} {item.get('display_value')}" for item in row.get("context_items") or []
            )
        ).casefold()]
    selected = enriched[:limit]
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
    exposures=("internal", "customer_agent"),
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
    exposures=("internal", "customer_agent"),
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
    exposures=("internal", "customer_agent"),
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
        packet = json.loads(raw) if raw else {"project_ref": context.project_ref}
    except (TypeError, ValueError):
        packet = {"project_ref": context.project_ref}
    try:
        direction = project_context_service.get_context(context.client_id, context.project_ref)
        packet.update({"direction": direction, "context_items": project_context_service.context_items(direction)})
    except project_context_service.ProjectContextError:
        pass
    return packet


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
    direction = packet.get("direction") or {}
    context_results = project_context_service.search_context(direction, query)
    source_results = [{**item, "result_type": "indexed_source"}
                      for item in (packet.get("fontes_verificadas") or [])]
    return {
        "project_ref": context.project_ref,
        "query": query,
        "revision": direction.get("revision"),
        "project": packet.get("projeto") or {},
        "context_results": context_results,
        "source_results": source_results,
        "results": [*context_results, *source_results],
    }
