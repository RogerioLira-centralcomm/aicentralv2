"""Lightweight native project tasks; external task systems remain references."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from ..db import get_db
from .agent_v2.contracts import RequestContext


STATUSES = {"todo", "in_progress", "blocked", "done"}
PRIORITIES = {"low", "normal", "high"}


def _available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('public.cadu_project_tasks') IS NOT NULL AS available")
    return bool((cursor.fetchone() or {}).get("available"))


def _date(value, field: str):
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BadRequest(f"{field} possui data inválida.") from exc


def _assignee(value):
    if value in (None, ""):
        return None
    try:
        assignee_id = int(value)
    except (TypeError, ValueError) as exc:
        raise BadRequest("Responsável inválido.") from exc
    if assignee_id <= 0:
        raise BadRequest("Responsável inválido.")
    return assignee_id


def _normalized_task(payload: dict) -> dict:
    title = " ".join(str(payload.get("title") or "").split())[:180]
    if len(title) < 2:
        raise BadRequest("Informe um título para a tarefa.")
    status, priority = str(payload.get("status") or "todo"), str(payload.get("priority") or "normal")
    if status not in STATUSES or priority not in PRIORITIES:
        raise BadRequest("Status ou prioridade inválida.")
    starts_at, due_at = _date(payload.get("starts_at"), "Início"), _date(payload.get("due_at"), "Prazo")
    if starts_at and due_at and due_at < starts_at:
        raise BadRequest("O prazo não pode ser anterior ao início.")
    return {
        "id": str(uuid4()), "title": title,
        "description": str(payload.get("description") or "").strip()[:4000],
        "status": status, "priority": priority, "starts_at": starts_at, "due_at": due_at,
        "assignee_id": _assignee(payload.get("assignee_id")),
        "origin": str(payload.get("origin") or "workspace")[:32],
        "resource_refs": [str(item) for item in (payload.get("resource_refs") or [])][:20],
        "evidence": str(payload.get("evidence") or "").strip()[:2000],
    }


def _validate_assignee(cursor, context: RequestContext, assignee_id):
    if not assignee_id:
        return
    cursor.execute("SELECT 1 FROM tbl_contato_cliente WHERE id_contato_cliente=%s AND pk_id_tbl_cliente=%s AND status=TRUE",
                   (assignee_id, context.client_id))
    if not cursor.fetchone():
        raise BadRequest("A pessoa responsável não pertence a esta conta.")


def _insert_task(cursor, context: RequestContext, task: dict, *, user_instruction="", context_summary=""):
    cursor.execute(
        """INSERT INTO cadu_project_tasks
           (id,organization_id,client_id,project_ref,title,description,status,priority,
            starts_at,due_at,assignee_id,source_provider,external_url,external_id,
            created_by,metadata,completed_at,created_at,updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'cadu',NULL,NULL,%s,%s,
                   CASE WHEN %s='done' THEN NOW() ELSE NULL END,NOW(),NOW())""",
        (task["id"], context.client_id, context.client_id, context.project_ref, task["title"],
         task["description"], task["status"], task["priority"], task["starts_at"], task["due_at"],
         task["assignee_id"], context.user_id, Json({
             "origin": task["origin"], "resource_refs": task["resource_refs"],
             "evidence": task["evidence"], "user_instruction": str(user_instruction or "")[:4000],
             "context_summary": str(context_summary or "")[:4000],
         }), task["status"]),
    )


def _created_task(task: dict, *, user_instruction="", context_summary="") -> dict:
    return {
        **{key: task[key] for key in ("id", "title", "description", "status", "priority",
                                      "starts_at", "due_at", "assignee_id")},
        "source_provider": "cadu", "assignee_name": None,
        "metadata": {"origin": task["origin"], "resource_refs": task["resource_refs"],
                     "evidence": task["evidence"], "user_instruction": str(user_instruction or "")[:4000],
                     "context_summary": str(context_summary or "")[:4000]},
    }


def _validate_resource_refs(cursor, context: RequestContext, tasks: list[dict]):
    refs = {ref for task in tasks for ref in task["resource_refs"]}
    if not refs:
        return
    try:
        normalized = {str(UUID(ref)) for ref in refs}
    except ValueError as exc:
        raise BadRequest("Uma das fontes relacionadas é inválida.") from exc
    cursor.execute("""SELECT id::text FROM cadu_project_resources
                       WHERE client_id=%s AND project_ref=%s AND id::text=ANY(%s)
                         AND status <> 'archived'""",
                   (context.client_id, context.project_ref, list(normalized)))
    found = {str(row["id"]) for row in cursor.fetchall()}
    if found != normalized:
        raise BadRequest("Uma das fontes relacionadas não pertence a este projeto ou não está disponível.")


def list_tasks(context: RequestContext) -> dict:
    with get_db().cursor() as cursor:
        if not _available(cursor):
            return {"available": False, "tasks": []}
        cursor.execute(
            """SELECT task.id::text,task.title,task.description,task.status,task.priority,
                      task.starts_at,task.due_at,task.completed_at,task.assignee_id,
                      assignee.nome_completo AS assignee_name,task.source_provider,
                      task.external_url,task.external_id,task.created_by,
                      creator.nome_completo AS creator_name,task.metadata,task.created_at,task.updated_at
                 FROM cadu_project_tasks task
            LEFT JOIN tbl_contato_cliente assignee ON assignee.id_contato_cliente=task.assignee_id
            LEFT JOIN tbl_contato_cliente creator ON creator.id_contato_cliente=task.created_by
                WHERE task.organization_id=%s AND task.client_id=%s
                  AND task.project_ref=%s AND task.archived_at IS NULL
             ORDER BY CASE task.status WHEN 'in_progress' THEN 0 WHEN 'todo' THEN 1 WHEN 'blocked' THEN 2 ELSE 3 END,
                      task.due_at NULLS LAST,task.created_at DESC""",
            (context.client_id, context.client_id, context.project_ref),
        )
        return {"available": True, "tasks": [dict(row) for row in cursor.fetchall()]}


def create_task(context: RequestContext, payload: dict) -> dict:
    task, connection = _normalized_task(payload), get_db()
    try:
        with connection.cursor() as cursor:
            if not _available(cursor):
                raise BadRequest("A lista de tarefas ainda não foi ativada neste ambiente.")
            _validate_assignee(cursor, context, task["assignee_id"])
            _insert_task(cursor, context, task)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _created_task(task)


def create_tasks(context: RequestContext, payloads: list[dict], *, require_empty=False,
                 user_instruction="", context_summary="") -> dict:
    if not isinstance(payloads, list) or not payloads:
        raise BadRequest("Informe ao menos uma tarefa.")
    if len(payloads) > 50:
        raise BadRequest("Crie no máximo 50 tarefas por operação.")
    tasks = [_normalized_task(item if isinstance(item, dict) else {}) for item in payloads]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            if not _available(cursor):
                raise BadRequest("A lista de tarefas ainda não foi ativada neste ambiente.")
            if require_empty:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                               (f"cadu-project-tasks:{context.client_id}:{context.project_ref}",))
                cursor.execute("""SELECT 1 FROM cadu_project_tasks WHERE organization_id=%s AND client_id=%s
                                  AND project_ref=%s AND archived_at IS NULL LIMIT 1 FOR UPDATE""",
                               (context.client_id, context.client_id, context.project_ref))
                if cursor.fetchone():
                    raise Conflict("Este projeto já possui uma lista de tarefas. Use a criação em lote para adicionar novos itens.")
            for assignee_id in sorted({task["assignee_id"] for task in tasks if task["assignee_id"]}):
                _validate_assignee(cursor, context, assignee_id)
            _validate_resource_refs(cursor, context, tasks)
            for task in tasks:
                _insert_task(cursor, context, task, user_instruction=user_instruction,
                             context_summary=context_summary)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    created = [_created_task(task, user_instruction=user_instruction, context_summary=context_summary)
               for task in tasks]
    return {"created": len(created), "tasks": created, "initial_list": bool(require_empty)}


def update_task(context: RequestContext, task_id: str, payload: dict) -> dict:
    try:
        task_id = str(UUID(str(task_id)))
    except ValueError as exc:
        raise NotFound("Tarefa não encontrada.") from exc
    allowed = {"title", "description", "status", "priority", "starts_at", "due_at", "assignee_id",
               "resource_refs", "evidence", "user_instruction"}
    changes = {key: value for key, value in payload.items() if key in allowed}
    if not changes:
        raise BadRequest("Informe uma alteração para a tarefa.")
    if "title" in changes:
        changes["title"] = " ".join(str(changes["title"] or "").split())[:180]
        if len(changes["title"]) < 2:
            raise BadRequest("Informe um título para a tarefa.")
    if "description" in changes:
        changes["description"] = str(changes["description"] or "").strip()[:4000]
    if "status" in changes and changes["status"] not in STATUSES:
        raise BadRequest("Status inválido.")
    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise BadRequest("Prioridade inválida.")
    for field, label in (("starts_at", "Início"), ("due_at", "Prazo")):
        if field in changes:
            changes[field] = _date(changes[field], label)
    if "assignee_id" in changes:
        changes["assignee_id"] = _assignee(changes["assignee_id"])
    metadata_changes = {key: changes.pop(key) for key in ("resource_refs", "evidence", "user_instruction")
                        if key in changes}
    if "resource_refs" in metadata_changes:
        metadata_changes["resource_refs"] = [str(item) for item in (metadata_changes["resource_refs"] or [])][:20]
    if "evidence" in metadata_changes:
        metadata_changes["evidence"] = str(metadata_changes["evidence"] or "").strip()[:2000]
    if "user_instruction" in metadata_changes:
        metadata_changes["user_instruction"] = str(metadata_changes["user_instruction"] or "").strip()[:4000]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            if not _available(cursor):
                raise BadRequest("A lista de tarefas ainda não foi ativada neste ambiente.")
            cursor.execute(
                """SELECT starts_at,due_at,metadata FROM cadu_project_tasks
                    WHERE id=%s AND organization_id=%s AND client_id=%s
                      AND project_ref=%s AND archived_at IS NULL FOR UPDATE""",
                (task_id, context.client_id, context.client_id, context.project_ref),
            )
            current = cursor.fetchone()
            if not current:
                raise NotFound("Tarefa não encontrada.")
            effective_start = changes.get("starts_at", current.get("starts_at"))
            effective_due = changes.get("due_at", current.get("due_at"))
            if effective_start and effective_due and effective_due < effective_start:
                raise BadRequest("O prazo não pode ser anterior ao início.")
            _validate_assignee(cursor, context, changes.get("assignee_id"))
            if "resource_refs" in metadata_changes:
                _validate_resource_refs(cursor, context, [{"resource_refs": metadata_changes["resource_refs"]}])
            assignments = [f"{key}=%s" for key in changes]
            values = list(changes.values())
            if metadata_changes:
                metadata = {**(current.get("metadata") or {}), **metadata_changes}
                assignments.append("metadata=%s")
                values.append(Json(metadata))
            if changes.get("status") == "done":
                assignments.append("completed_at=NOW()")
            elif "status" in changes:
                assignments.append("completed_at=NULL")
            cursor.execute(
                f"UPDATE cadu_project_tasks SET {', '.join(assignments)},updated_at=NOW() "
                "WHERE id=%s AND organization_id=%s AND client_id=%s AND project_ref=%s AND archived_at IS NULL",
                tuple(values) + (task_id, context.client_id, context.client_id, context.project_ref),
            )
            if not cursor.rowcount:
                raise NotFound("Tarefa não encontrada.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return next(item for item in list_tasks(context)["tasks"] if item["id"] == task_id)
