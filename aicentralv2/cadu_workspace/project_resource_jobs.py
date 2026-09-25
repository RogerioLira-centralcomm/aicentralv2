"""Durable worker for contextual project resource reconciliation."""

import time

import click
from flask import current_app
from flask.cli import with_appcontext

from ..db import close_db, get_db
from .project_resource_service import reconcile


def claim(max_attempts=5, *, client_id=None, project_ref=None):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""WITH candidate AS (
                SELECT id FROM cadu_project_resource_jobs
                 WHERE (status IN ('queued','failed') OR
                        (status='running' AND started_at < NOW()-INTERVAL '10 minutes'))
                   AND attempts < %s AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
                   AND (%s::bigint IS NULL OR client_id=%s)
                   AND (%s::text IS NULL OR project_ref=%s)
                 ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            ) UPDATE cadu_project_resource_jobs job
                 SET status='running', attempts=attempts+1, started_at=NOW(), finished_at=NULL,
                     next_attempt_at=NULL, error_message=NULL
                FROM candidate WHERE job.id=candidate.id
            RETURNING job.id::text,job.client_id,job.project_ref,job.event_type,job.actor_id""",
                           (max_attempts, client_id, client_id, project_ref, project_ref))
            row = cursor.fetchone()
        connection.commit()
        return dict(row) if row else None
    except Exception:
        connection.rollback()
        raise


def process_one(*, client_id=None, project_ref=None):
    job = claim(client_id=client_id, project_ref=project_ref)
    if not job:
        return False
    connection = get_db()
    try:
        reconcile(job["client_id"], job["project_ref"], job.get("actor_id"))
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_project_resource_jobs
                                  SET status='completed',finished_at=NOW() WHERE id=%s""", (job["id"],))
        connection.commit()
    except Exception as exc:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_project_resource_jobs SET status='failed',
                                  error_message=%s,finished_at=NOW(),
                                  next_attempt_at=NOW()+make_interval(mins => LEAST(attempts*2,60))
                                WHERE id=%s""", (str(exc)[:500], job["id"]))
        connection.commit()
        raise
    return True


@click.command("resource-registry-worker-once")
@with_appcontext
def worker_command():
    """Processa no máximo uma reconciliação do registro contextual."""
    click.echo("Processado." if process_one() else "Fila vazia.")


@click.command("resource-registry-worker-loop")
@with_appcontext
def worker_loop_command():
    """Continuously reconcile queued project resources under a supervisor."""
    while True:
        try:
            if not process_one():
                close_db()
                time.sleep(2)
        except Exception:
            current_app.logger.exception("Reconciliação de recursos do projeto falhou")
            close_db()
            time.sleep(5)
