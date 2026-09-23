"""Artifact persistence with optimistic versioning and tenant scoping."""

import json
import re
from html.parser import HTMLParser
from uuid import uuid4

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from ...db import get_db
from ..agent_v2.contracts import RequestContext
from .catalog import ALLOWED_TYPES, definition


ALLOWED_STATUS = {"draft", "active", "published", "archived"}


def _content(value, artifact_type: str) -> dict:
    if not isinstance(value, dict):
        raise BadRequest("O conteúdo do artefato precisa ser estruturado.")
    size = len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))
    maximum = definition(artifact_type).max_content_bytes
    if size > maximum:
        raise BadRequest(
            f"A entrega possui {size} bytes e excede o limite de {maximum}; "
            "o conteúdo foi recusado integralmente, sem cortes. Divida-o em blocos ou anexos."
        )
    return value


def create_draft(context: RequestContext, artifact_type: str, content: dict, *, title="", conversation_id=None) -> dict:
    if artifact_type not in ALLOWED_TYPES:
        raise BadRequest("Tipo de artefato inválido.")
    content = _content(content, artifact_type)
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
    artifact = get_artifact(context, artifact_id)
    materialize_artifact(artifact)
    return artifact


def get_artifact(context: RequestContext, artifact_id: str) -> dict:
    with get_db().cursor() as cur:
        cur.execute("""SELECT a.id, a.organization_id, a.client_id, a.project_ref, a.conversation_id, a.type, a.title, a.status,
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


def materialize_artifact(artifact: dict):
    from .workspace import materialize
    return materialize(artifact)


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
    if status is not None and status not in ALLOWED_STATUS:
        raise BadRequest("Status de artefato inválido.")
    try:
        expected_version = int(expected_version)
    except (TypeError, ValueError):
        raise BadRequest("Informe a versão atual do artefato.")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_version,type FROM cadu_workspace_artifacts
                            WHERE id = %s AND organization_id = %s AND client_id = %s FOR UPDATE""",
                        (str(artifact_id), context.organization_id, context.client_id))
            row = cur.fetchone()
            if not row:
                raise NotFound("Artefato indisponível.")
            content = _content(content, row.get("type") or "document")
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
    artifact = get_artifact(context, artifact_id)
    materialize_artifact(artifact)
    return artifact


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


class _DocumentText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored += 1
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "tr", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def _indexable_text(artifact: dict) -> str:
    content = artifact.get("content") or {}
    if content.get("html"):
        parser = _DocumentText()
        parser.feed(str(content["html"]))
        body = "".join(parser.parts)
    else:
        body = "\n\n".join(str(value) for value in [content.get("summary"),
            *[f"{field.get('key') or ''}\n{field.get('value') or ''}" for field in content.get("fields") or []]] if value)
    return "\n".join(line.strip() for line in body.splitlines() if line.strip())


def finalize_to_project(context: RequestContext, artifact_id: str, *, expected_version: int) -> dict:
    """Make the latest approved document the project's sole indexed snapshot."""
    from ...cadu_family import repository
    from ...cadu_skills.repository import charge_project_rag
    from .. import project_index_service, project_knowledge
    from ..project_resource_service import notify_change

    try:
        expected_version = int(expected_version)
    except (TypeError, ValueError) as exc:
        raise BadRequest("Informe a versão atual do documento para finalizar.") from exc
    if expected_version < 1:
        raise BadRequest("Informe uma versão válida do documento.")
    project_ref = str(context.project_ref or "")
    if not project_ref.startswith("ci:"):
        raise BadRequest("Selecione um projeto nativo para finalizar o documento.")
    if not repository.project_user_can_view(context.client_id, project_ref, context.user_id):
        raise NotFound("Projeto indisponível.")
    actor = repository.actor(context.user_id) or {}
    admin = int(actor.get("organization_id") or 0) == context.client_id and repository.account_role(actor) == "admin"
    roles = {item.get("role") for item in repository.project_access(context.client_id, project_ref)
             if int(item.get("user_id") or 0) == context.user_id}
    if not admin and not roles.intersection({"owner", "admin", "editor"}):
        raise BadRequest("Você não pode finalizar documentos neste projeto.")
    artifact = get_artifact(context, artifact_id)
    if artifact.get("project_ref") not in {None, project_ref}:
        raise BadRequest("O documento pertence a outro projeto.")
    if int(artifact["current_version"]) != int(expected_version):
        raise Conflict("O documento mudou. Reabra a versão recente antes de finalizar.")
    if not definition(artifact["type"]).indexable:
        raise BadRequest("Esta entrega pode permanecer vinculada ao projeto, mas não entra na base textual.")
    text = _indexable_text(artifact)
    if len(text) < 20:
        raise BadRequest("O documento precisa de conteúdo suficiente para entrar na base do projeto.")
    project_id = project_ref[3:]
    category = {"brief":"brief", "media_plan":"media_plan", "research":"research"}.get(artifact["type"], "other")
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                          AND classification_metadata->>'artifact_id'=%s
                          AND classification_metadata->>'artifact_version'=%s
                          AND purpose='knowledge_source' LIMIT 1""",
                       (context.client_id, project_id, str(artifact_id), str(expected_version)))
        already_indexed = cursor.fetchone()
    connection.rollback()
    if already_indexed:
        return {"artifact": artifact, "source_id": int(already_indexed["id"]), "indexed_version": int(expected_version), "already_finalized": True}

    chunks, embedding_tokens, embedding_model = project_knowledge.index(text)
    metadata = {"classifier":"artifact-final-v2", "artifact_id":str(artifact_id),
                "artifact_version":str(expected_version), "created_via":"document_finalization"}
    classification = {"category":category, "status":"manual", "confidence":1.0,
                      "reason":"Versão final confirmada no artefato."}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                           (f"cadu-artifact-index:{context.client_id}:{artifact_id}",))
            cursor.execute("""SELECT current_version FROM cadu_workspace_artifacts
                              WHERE id=%s AND client_id=%s AND organization_id=%s FOR UPDATE""",
                           (str(artifact_id), context.client_id, context.organization_id))
            current = cursor.fetchone()
            if not current or int(current["current_version"]) != int(expected_version):
                raise Conflict("O documento mudou durante a indexação. Tente finalizar novamente.")
            cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                              AND classification_metadata->>'artifact_id'=%s
                              AND classification_metadata->>'artifact_version'=%s
                              AND purpose='knowledge_source' LIMIT 1""",
                           (context.client_id, project_id, str(artifact_id), str(expected_version)))
            duplicate = cursor.fetchone()
            if duplicate:
                connection.commit()
                return {"artifact": get_artifact(context, artifact_id), "source_id": int(duplicate["id"]),
                        "indexed_version": expected_version, "already_finalized": True}
            cursor.execute("""SELECT id FROM cadu_ci_projeto_arquivos WHERE id_cliente=%s AND projeto_id=%s
                              AND classification_metadata->>'artifact_id'=%s
                              AND purpose='knowledge_source' FOR UPDATE""",
                           (context.client_id, project_id, str(artifact_id)))
            previous = [int(row["id"]) for row in cursor.fetchall()]
            charged = charge_project_rag(cursor, client_id=context.client_id, user_id=context.user_id,
                                         project_id=project_id, tokens=embedding_tokens, stage="indexacao",
                                         idempotency_key=f"artifact-final:{artifact_id}:v{expected_version}")
            source_id = project_index_service.persist_indexed_source(
                cursor, project_id=project_id, client_id=context.client_id, user_id=context.user_id,
                name=artifact["title"], mime="text/plain", size=len(text.encode("utf-8")),
                storage_path=f"workspace://artifact/{artifact_id}/v{expected_version}", source="artifact_final",
                content=text, chunks=chunks, embedding_model=embedding_model, charged_tokens=charged,
                classification=classification, metadata=metadata)
            if previous:
                cursor.execute("DELETE FROM cadu_ci_chunks WHERE id_cliente=%s AND projeto_id=%s AND arquivo_id=ANY(%s)",
                               (context.client_id, project_id, previous))
                cursor.execute("""UPDATE cadu_ci_projeto_arquivos SET purpose='project_attachment',
                                  indexing_status='superseded', updated_at=NOW()
                                  WHERE id_cliente=%s AND projeto_id=%s AND id=ANY(%s)""",
                               (context.client_id, project_id, previous))
                cursor.execute("""UPDATE cadu_ci_projetos
                                  SET total_arquivos=GREATEST(COALESCE(total_arquivos,0)-%s,0), updated_at=NOW()
                                  WHERE id=%s AND id_cliente=%s""",
                               (len(previous), project_id, context.client_id))
            cursor.execute("""UPDATE cadu_workspace_artifacts SET project_ref=%s, status='active', updated_at=NOW()
                              WHERE id=%s AND client_id=%s AND organization_id=%s""",
                           (project_ref, str(artifact_id), context.client_id, context.organization_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    try:
        notify_change(context.client_id, project_ref, "indexed", source_system="cadu_workspace_artifacts",
                      source_id=str(artifact_id), actor_id=context.user_id)
    except Exception:
        pass
    return {"artifact": get_artifact(context, artifact_id), "source_id": source_id,
            "indexed_version": int(expected_version), "already_finalized": False}


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
