"""Durable asynchronous checkpoints for the rebuildable memory projection."""

import click
from flask import current_app
from flask.cli import with_appcontext

from ...cadu_family import repository


MAX_ATTEMPTS = 3


def schedule(**values):
    """Coalesce a checkpoint request in Postgres without running it in HTTP."""
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_conversation_memory_jobs
                (conversation_id,organization_id,client_id,user_id)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    organization_id=EXCLUDED.organization_id,
                    client_id=EXCLUDED.client_id,user_id=EXCLUDED.user_id,
                    requested_at=NOW(),
                    claimed_at=cadu_conversation_memory_jobs.claimed_at,
                    finished_at=NULL,
                    attempts=CASE WHEN cadu_conversation_memory_jobs.claimed_at IS NULL
                                  THEN 0 ELSE cadu_conversation_memory_jobs.attempts END,
                    last_error=NULL''', (
                values['conversation_id'], values['organization_id'],
                values['client_id'], values['user_id'],
            ))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def claim():
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''WITH next_job AS (
                SELECT conversation_id FROM cadu_conversation_memory_jobs
                WHERE finished_at IS NULL AND claimed_at IS NULL AND attempts < %s
                ORDER BY requested_at,conversation_id
                FOR UPDATE SKIP LOCKED LIMIT 1
            ) UPDATE cadu_conversation_memory_jobs job
                SET claimed_at=NOW(),attempts=attempts+1
                FROM next_job next
                WHERE job.conversation_id=next.conversation_id
                RETURNING job.conversation_id,job.organization_id,job.client_id,
                          job.user_id,job.attempts''', (MAX_ATTEMPTS,))
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise


def process_one():
    job = claim()
    if not job:
        return False
    conn = repository.get_db()
    try:
        from ..conversations import conversation_memory
        conversation_memory.checkpoint(
            conversation_id=job['conversation_id'], organization_id=job['organization_id'],
            client_id=job['client_id'], user_id=job['user_id'],
        )
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_conversation_memory_jobs SET
                finished_at=CASE WHEN requested_at > claimed_at THEN NULL ELSE NOW() END,
                claimed_at=NULL,
                attempts=CASE WHEN requested_at > claimed_at THEN 0 ELSE attempts END,
                last_error=NULL WHERE conversation_id=%s''',
                        (job['conversation_id'],))
        conn.commit()
        return True
    except Exception as exc:
        conn.rollback()
        message = str(exc)[:1000] or exc.__class__.__name__
        try:
            with conn.cursor() as cur:
                cur.execute('''UPDATE cadu_conversation_memory_jobs SET
                    claimed_at=NULL,
                    finished_at=CASE WHEN attempts >= %s THEN NOW() ELSE NULL END,
                    last_error=%s WHERE conversation_id=%s''',
                            (MAX_ATTEMPTS, message, job['conversation_id']))
            conn.commit()
        except Exception:
            conn.rollback()
        current_app.logger.exception(
            "Checkpoint de memória falhou; conversa=%s tentativa=%s",
            job['conversation_id'], job['attempts'],
        )
        raise


@click.command('conversation-memory-worker-once')
@with_appcontext
def worker_command():
    """Process at most one durable memory projection job."""
    click.echo('Processado.' if process_one() else 'Fila vazia.')
