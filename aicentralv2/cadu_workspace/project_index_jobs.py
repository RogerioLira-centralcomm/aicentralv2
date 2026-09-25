"""Durable worker for incremental project-source reindexing."""
from __future__ import annotations

import click
from flask.cli import with_appcontext
from uuid import uuid4

from ..db import get_db
from .project_index_service import reindex_source


def enqueue(client_id: int, project_id: str, source_id: int, actor_id: int | None = None) -> str | None:
    job_id = str(uuid4())
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s) AS relation", ("public.cadu_project_index_jobs",))
            if not (cursor.fetchone() or {}).get("relation"):
                connection.rollback()
                return None
            cursor.execute(
                """INSERT INTO cadu_project_index_jobs
                       (id, client_id, project_ref, source_id, operation, actor_id, status, created_at)
                    VALUES (%s, %s, %s, %s, 'reindex', %s, 'queued', NOW())
                 ON CONFLICT (client_id, project_ref, source_id, operation)
                    WHERE status IN ('queued','running') DO NOTHING
                 RETURNING id::text""",
                (job_id, client_id, f"ci:{project_id}", source_id, actor_id),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    """UPDATE cadu_ci_projeto_arquivos
                          SET indexing_status=CASE WHEN indexing_status='completed' THEN 'completed' ELSE 'queued' END,
                              erro_msg=NULL, updated_at=NOW()
                        WHERE id=%s AND projeto_id=%s AND id_cliente=%s""",
                    (source_id, project_id, client_id),
                )
            else:
                cursor.execute(
                    """SELECT id::text FROM cadu_project_index_jobs
                        WHERE client_id=%s AND project_ref=%s AND source_id=%s
                          AND operation='reindex' AND status IN ('queued','running')
                        ORDER BY created_at DESC LIMIT 1""",
                    (client_id, f"ci:{project_id}", source_id),
                )
                row = cursor.fetchone()
        connection.commit()
        return str(row["id"]) if row else job_id
    except Exception:
        connection.rollback()
        raise


def claim(max_attempts: int = 5):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """WITH candidate AS (
                       SELECT id FROM cadu_project_index_jobs
                        WHERE (status IN ('queued','failed') OR
                               (status='running' AND started_at < NOW()-INTERVAL '10 minutes'))
                          AND attempts < %s
                          AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
                        ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                   ) UPDATE cadu_project_index_jobs job
                      SET status='running', attempts=attempts+1, started_at=NOW(),
                          finished_at=NULL, next_attempt_at=NULL, error_message=NULL
                     FROM candidate WHERE job.id=candidate.id
                 RETURNING job.id::text, job.client_id, job.project_ref, job.source_id,
                           job.operation, job.actor_id, job.attempts""",
                (max_attempts,),
            )
            row = cursor.fetchone()
        connection.commit()
        return dict(row) if row else None
    except Exception:
        connection.rollback()
        raise


def process_one():
    job = claim()
    if not job:
        return False
    project_ref = str(job["project_ref"])
    project_id = project_ref[3:] if project_ref.startswith("ci:") else project_ref
    actor_id = int(job.get("actor_id") or 0)
    try:
        reindex_source(int(job["client_id"]), project_id, int(job["source_id"]), actor_id,
                       billable=job.get("operation") != "rebuild_v2")
        _finish(job["id"], "completed")
    except Exception as exc:
        _fail(job["id"], str(exc)[:500])
        raise
    return True


def _finish(job_id: str, status: str):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cadu_project_index_jobs SET status=%s, finished_at=NOW() WHERE id=%s",
                           (status, job_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _fail(job_id: str, error: str):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_project_index_jobs
                      SET status='failed', error_message=%s, finished_at=NOW(),
                          next_attempt_at=NOW()+make_interval(mins => LEAST(attempts*2,60))
                    WHERE id=%s""",
                (error, job_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


@click.command("project-index-worker-once")
@with_appcontext
def worker_command():
    """Processa no máximo uma reindexação de fonte."""
    click.echo("Processado." if process_one() else "Fila vazia.")
