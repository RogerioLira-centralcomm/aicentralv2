"""Artifact persistence with optimistic versioning and tenant scoping."""

import json
from uuid import uuid4

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from ...db import get_db
from ..agent_v2.contracts import RequestContext


ALLOWED_TYPES = {
    "brief", "document", "note", "executive_summary", "media_plan", "scenario", "research",
    "project_map", "html", "meeting_summary", "meeting_agenda", "link_reader",
}
ALLOWED_STATUS = {"draft", "active", "published", "archived"}
MAX_CONTENT_BYTES = 256_000


def _content(value) -> dict:
    if not isinstance(value, dict):
        raise BadRequest("O conteúdo do artefato precisa ser estruturado.")
    if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > MAX_CONTENT_BYTES:
        raise BadRequest("O artefato excede o tamanho permitido.")
    return value


def create_draft(context: RequestContext, artifact_type: str, content: dict, *, title="", conversation_id=None) -> dict:
    if artifact_type not in ALLOWED_TYPES:
        raise BadRequest("Tipo de artefato inválido.")
    content = _content(content)
    artifact_id, version_id = str(uuid4()), str(uuid4())
    title = " ".join(str(title or "").split())[:180] or "Novo artefato"
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO cadu_workspace_artifacts
                (id, organization_id, client_id, project_ref, conversation_id, type, title, status,
                 current_version, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', 1, %s, NOW(), NOW())""",
                (artifact_id, context.organization_id, context.client_id, context.project_ref,
                 conversation_id or context.conversation_id, artifact_type, title, context.user_id))
            cur.execute("""INSERT INTO cadu_workspace_artifact_versions
                (id, artifact_id, version, content, change_summary, created_by, created_at)
                VALUES (%s, %s, 1, %s, %s, %s, NOW())""",
                (version_id, artifact_id, Json(content), "Rascunho criado", context.user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if context.project_ref:
        try:
            from ..project_resource_service import notify_change
            notify_change(context.client_id, context.project_ref, "created", source_system="cadu_workspace_artifacts",
                          source_id=artifact_id, actor_id=context.user_id)
        except Exception:
            pass
    return get_artifact(context, artifact_id)


def get_artifact(context: RequestContext, artifact_id: str) -> dict:
    with get_db().cursor() as cur:
        cur.execute("""SELECT a.id, a.project_ref, a.conversation_id, a.type, a.title, a.status,
                              a.current_version, a.created_by, a.created_at, a.updated_at, v.content
                         FROM cadu_workspace_artifacts a
                         JOIN cadu_workspace_artifact_versions v
                           ON v.artifact_id = a.id AND v.version = a.current_version
                        WHERE a.id = %s AND a.organization_id = %s AND a.client_id = %s""",
                    (str(artifact_id), context.organization_id, context.client_id))
        row = cur.fetchone()
    if not row:
        raise NotFound("Artefato indisponível.")
    return dict(row)


def list_artifacts(context: RequestContext, *, artifact_type=None, status=None, limit=20) -> list[dict]:
    if artifact_type is not None and artifact_type not in ALLOWED_TYPES:
        raise BadRequest("Tipo de artefato inválido.")
    if status is not None and status not in ALLOWED_STATUS:
        raise BadRequest("Status de artefato inválido.")
    limit = min(50, max(1, int(limit or 20)))
    filters = ["a.organization_id = %s", "a.client_id = %s"]
    params = [context.organization_id, context.client_id]
    if context.project_ref:
        filters.append("a.project_ref = %s")
        params.append(context.project_ref)
    if artifact_type:
        filters.append("a.type = %s")
        params.append(artifact_type)
    if status:
        filters.append("a.status = %s")
        params.append(status)
    params.append(limit)
    with get_db().cursor() as cur:
        cur.execute(f"""SELECT a.id, a.project_ref, a.conversation_id, a.type, a.title, a.status,
                               a.current_version, a.created_by, a.created_at, a.updated_at
                          FROM cadu_workspace_artifacts a
                         WHERE {' AND '.join(filters)}
                      ORDER BY a.updated_at DESC, a.id DESC LIMIT %s""", tuple(params))
        return [dict(row) for row in cur.fetchall()]


def list_versions(context: RequestContext, artifact_id: str, *, limit=50) -> list[dict]:
    # Resolve the artifact first so a foreign-tenant ID remains indistinguishable from a missing ID.
    get_artifact(context, artifact_id)
    limit = min(100, max(1, int(limit or 50)))
    with get_db().cursor() as cur:
        cur.execute("""SELECT v.id, v.version, v.change_summary, v.created_by, v.created_at
                         FROM cadu_workspace_artifact_versions v
                        WHERE v.artifact_id = %s
                     ORDER BY v.version DESC LIMIT %s""", (str(artifact_id), limit))
        return [dict(row) for row in cur.fetchall()]


def get_version(context: RequestContext, artifact_id: str, version: int) -> dict:
    get_artifact(context, artifact_id)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise BadRequest("Versão inválida.")
    with get_db().cursor() as cur:
        cur.execute("""SELECT v.id, v.version, v.content, v.change_summary, v.created_by, v.created_at
                         FROM cadu_workspace_artifact_versions v
                        WHERE v.artifact_id = %s AND v.version = %s""", (str(artifact_id), version))
        row = cur.fetchone()
    if not row:
        raise NotFound("Versão indisponível.")
    return dict(row)


def patch_artifact(context: RequestContext, artifact_id: str, content: dict, *, expected_version: int,
                   title=None, status=None, change_summary="") -> dict:
    content = _content(content)
    if status is not None and status not in ALLOWED_STATUS:
        raise BadRequest("Status de artefato inválido.")
    try:
        expected_version = int(expected_version)
    except (TypeError, ValueError):
        raise BadRequest("Informe a versão atual do artefato.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_version FROM cadu_workspace_artifacts
                            WHERE id = %s AND organization_id = %s AND client_id = %s FOR UPDATE""",
                        (str(artifact_id), context.organization_id, context.client_id))
            row = cur.fetchone()
            if not row:
                raise NotFound("Artefato indisponível.")
            if int(row["current_version"]) != expected_version:
                raise Conflict("O artefato foi alterado. Atualize antes de salvar novamente.")
            next_version = expected_version + 1
            cur.execute("""INSERT INTO cadu_workspace_artifact_versions
                (id, artifact_id, version, content, change_summary, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                (str(uuid4()), str(artifact_id), next_version, Json(content),
                 str(change_summary or "Atualização")[:500], context.user_id))
            cur.execute("""UPDATE cadu_workspace_artifacts
                               SET current_version = %s,
                                   title = COALESCE(%s, title), status = COALESCE(%s, status), updated_at = NOW()
                             WHERE id = %s""",
                        (next_version, " ".join(str(title).split())[:180] if title is not None else None,
                         status, str(artifact_id)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if context.project_ref:
        try:
            from ..project_resource_service import notify_change
            notify_change(context.client_id, context.project_ref, "versioned", source_system="cadu_workspace_artifacts",
                          source_id=str(artifact_id), actor_id=context.user_id)
        except Exception:
            pass
    return get_artifact(context, artifact_id)


def attach_to_project(context: RequestContext, artifact_id: str, project_ref: str) -> dict:
    """Attach a session draft to an already authorized project without changing its text."""
    project_ref = " ".join(str(project_ref or "").split())[:120]
    if not project_ref.startswith("ci:"):
        raise BadRequest("Selecione um projeto válido para salvar este documento.")
    # The caller resolves project membership before reaching this service. The
    # artifact lookup still enforces the tenant boundary before any mutation.
    get_artifact(context, artifact_id)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET project_ref = %s, updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (project_ref, str(artifact_id), context.organization_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    try:
        from ..project_resource_service import notify_change
        notify_change(context.client_id, project_ref, "attached", source_system="cadu_workspace_artifacts",
                      source_id=str(artifact_id), actor_id=context.user_id)
    except Exception:
        pass
    return get_artifact(context, artifact_id)


def publish_artifact(context: RequestContext, artifact_id: str) -> dict:
    """Make an HTML artifact available through its opaque public UUID URL."""
    artifact = get_artifact(context, artifact_id)
    if artifact.get("type") != "html":
        raise BadRequest("Somente artefatos HTML podem ser publicados como página pública.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET status = 'published', updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (str(artifact_id), context.organization_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_artifact(context, artifact_id)


def unpublish_artifact(context: RequestContext, artifact_id: str) -> dict:
    """Revoke the public URL while keeping the HTML artifact and its versions."""
    artifact = get_artifact(context, artifact_id)
    if artifact.get("type") != "html":
        raise BadRequest("Somente artefatos HTML podem ser retirados da publicação.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE cadu_workspace_artifacts
                              SET status = 'draft', updated_at = NOW()
                            WHERE id = %s AND organization_id = %s AND client_id = %s""",
                        (str(artifact_id), context.organization_id, context.client_id))
            if cur.rowcount != 1:
                raise NotFound("Artefato indisponível.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_artifact(context, artifact_id)


def get_public_artifact(artifact_id: str) -> dict:
    """Read only published HTML; intentionally has no session or tenant input."""
    with get_db().cursor() as cur:
        cur.execute("""SELECT a.id, a.type, a.title, a.status, a.current_version,
                              a.created_at, a.updated_at, v.content
                         FROM cadu_workspace_artifacts a
                         JOIN cadu_workspace_artifact_versions v
                           ON v.artifact_id = a.id AND v.version = a.current_version
                        WHERE a.id = %s AND a.type = 'html' AND a.status = 'published'""",
                    (str(artifact_id),))
        row = cur.fetchone()
    if not row:
        raise NotFound("Página pública indisponível.")
    return dict(row)
