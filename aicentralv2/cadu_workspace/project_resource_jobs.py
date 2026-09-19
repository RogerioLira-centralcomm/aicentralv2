"""Durable worker for contextual project resource reconciliation."""

import click
from flask.cli import with_appcontext

from ..db import get_db
from .project_resource_service import reconcile


def claim(max_attempts=5):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""WITH candidate AS (
                SELECT id FROM cadu_project_resource_jobs
                 WHERE status IN ('queued','failed') AND attempts < %s
                 ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            ) UPDATE cadu_project_resource_jobs job
                 SET status='running', attempts=attempts+1, started_at=NOW(), error_message=NULL
                FROM candidate WHERE job.id=candidate.id
            RETURNING job.id::text,job.client_id,job.project_ref,job.event_type""", (max_attempts,))
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
    connection = get_db()
    try:
        reconcile(job["client_id"], job["project_ref"])
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_project_resource_jobs
                                  SET status='completed',finished_at=NOW() WHERE id=%s""", (job["id"],))
        connection.commit()
    except Exception as exc:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_project_resource_jobs SET status='failed',
                                  error_message=%s,finished_at=NOW() WHERE id=%s""", (str(exc)[:500], job["id"]))
        connection.commit()
        raise
    return True


@click.command("resource-registry-worker-once")
@with_appcontext
def worker_command():
    """Processa no máximo uma reconciliação do registro contextual."""
    click.echo("Processado." if process_one() else "Fila vazia.")
