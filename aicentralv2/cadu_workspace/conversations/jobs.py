"""Postgres-backed, at-most-once dispatch. HTTP clients never own the worker.

Claimed jobs are deliberately NOT retried after a process crash: the provider
may already have charged for them. Reconciliation must resolve these explicitly.
"""
import json

import click
from flask import current_app
from flask.cli import with_appcontext

from ...cadu_family import repository


def enqueue(cur, run):
    # Same transaction as the run, bound context and user message.
    cur.execute('''INSERT INTO cadu_family_chat_jobs (run_id, payload)
                   VALUES (%s, %s::jsonb)''', (run['run_id'], json.dumps(run)))


def claim():
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''WITH next_job AS (
                SELECT j.run_id FROM cadu_family_chat_jobs j
                JOIN cadu_family_chat_runs r ON r.id = j.run_id
                WHERE j.claimed_at IS NULL AND r.status = 'running'
                ORDER BY j.created_at, j.run_id
                FOR UPDATE OF j SKIP LOCKED LIMIT 1
            ) UPDATE cadu_family_chat_jobs j SET claimed_at = NOW()
              FROM next_job n WHERE j.run_id = n.run_id RETURNING j.payload''')
            row = cur.fetchone()
        conn.commit()  # Claim is durable BEFORE any external call.
        return row['payload'] if row else None
    except Exception:
        conn.rollback()
        raise


def append_event(run_id, event):
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_chat_events (run_id, event)
                           VALUES (%s, %s::jsonb)''', (run_id, json.dumps(event)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def process_one():
    from .service import stream
    run = claim()
    if run is None:
        return False
    source = stream(run)
    try:
        for frame in source:
            append_event(run['run_id'], json.loads(frame.removeprefix('data: ')))
    finally:
        # An actual worker failure can stop its provider; browser disconnects
        # never reach this generator. Never auto-release the durable claim.
        source.close()
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE cadu_family_chat_jobs SET finished_at = NOW() WHERE run_id = %s', (run['run_id'],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def page(run_id, after=0):
    """Caller must authorize run ownership before calling this projection."""
    events = repository.rows('''SELECT id, event FROM cadu_family_chat_events
                               WHERE run_id = %s AND id > %s ORDER BY id LIMIT 100''', (run_id, after))
    return {'events': events, 'next_cursor': events[-1]['id'] if events else after}


def cancel_pending(run_id):
    """Caller already checked ownership. Serialize cancellation with claim()."""
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_family_chat_jobs SET claimed_at = NOW(), finished_at = NOW()
                           WHERE run_id = %s AND claimed_at IS NULL RETURNING run_id''', (run_id,))
            cancelled = cur.fetchone() is not None
            if cancelled:
                cur.execute('''UPDATE cadu_family_chat_runs SET status = 'stopped', finished_at = NOW()
                               WHERE id = %s AND status = 'running' ''', (run_id,))
        conn.commit()
        return cancelled
    except Exception:
        conn.rollback()
        raise


@click.command('chat-worker-once')
@with_appcontext
def worker_command():
    """Process at most one job; invoke from a supervised worker loop."""
    if not current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
        raise click.ClickException('CADU_CHAT_WORKER_ENABLED está desabilitado.')
    # Preflight before claiming; a missing provider config should not strand jobs.
    from ...cadu_family import dify
    dify.settings()
    click.echo('Processado.' if process_one() else 'Fila vazia.')
