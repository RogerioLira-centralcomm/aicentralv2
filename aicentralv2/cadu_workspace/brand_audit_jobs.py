"""Durable, at-most-once dispatch for slow Workspace brand audits.

Provider calls can charge credits, so a claimed job is never silently retried.
The existing retry action creates a new job from its saved evidence checkpoint.
"""
import base64
import json
import threading

import click
from flask import current_app
from flask.cli import with_appcontext

from ..cadu_family import repository


def _payload(job: dict) -> dict:
    safe = dict(job)
    safe['images'] = [
        {
            'filename': str(item.get('filename') or 'referencia'),
            'content_type': item.get('content_type'),
            'content_b64': base64.b64encode(item.get('content') or b'').decode('ascii'),
        }
        for item in (job.get('images') or [])
    ]
    return safe


def _restore(job: dict) -> dict:
    restored = dict(job)
    restored['images'] = [
        {
            'filename': item.get('filename') or 'referencia',
            'content_type': item.get('content_type'),
            'content': base64.b64decode(item.get('content_b64') or ''),
        }
        for item in (job.get('images') or [])
    ]
    return restored


def enqueue(job: dict):
    """Persist before a worker can call a provider; duplicate IDs are harmless."""
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''INSERT INTO cadu_workspace_brand_audit_jobs
                   (job_id, client_id, brand_id, payload)
                   VALUES (%s, %s, %s, %s::jsonb)
                   ON CONFLICT (job_id) DO NOTHING''',
                (job['job_id'], job['client_id'], job['brand_id'], json.dumps(_payload(job))),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def claim():
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''WITH next_job AS (
                       SELECT job_id FROM cadu_workspace_brand_audit_jobs
                        WHERE status = 'queued'
                        ORDER BY created_at, job_id
                        FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   UPDATE cadu_workspace_brand_audit_jobs j
                      SET status = 'running', claimed_at = NOW(), heartbeat_at = NOW(), attempts = attempts + 1
                     FROM next_job n
                    WHERE j.job_id = n.job_id
                RETURNING j.payload'''
            )
            row = cur.fetchone()
        conn.commit()  # Durable claim before any Firecrawl/model request.
        return _restore(row['payload']) if row else None
    except Exception:
        conn.rollback()
        raise


def finish(job_id: str, success: bool):
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''UPDATE cadu_workspace_brand_audit_jobs
                      SET status = %s, finished_at = NOW(), heartbeat_at = NOW()
                    WHERE job_id = %s''',
                ('completed' if success else 'failed', job_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def process_one():
    job = claim()
    if job is None:
        return False
    from .routes import _start_brand_review_job
    # The brand record remains the browser's source of progress.  Keep its
    # timestamp alive while a slow crawl or model call is in flight so that a
    # healthy ten-minute audit is never presented as an abandoned request.
    stop_heartbeat = threading.Event()
    app = current_app._get_current_object()

    def heartbeat():
        from .routes import _save_brand_review_job
        with app.app_context():
            while not stop_heartbeat.wait(45):
                try:
                    _save_brand_review_job(
                        int(job['client_id']), int(job['brand_id']), str(job['job_id']),
                    )
                except Exception:
                    app.logger.exception('Não foi possível atualizar o heartbeat da auditoria %s', job['job_id'])

    pulse = threading.Thread(target=heartbeat, daemon=True, name=f'brand-audit-heartbeat-{str(job["job_id"])[:12]}')
    pulse.start()
    success = False
    try:
        success = bool(_start_brand_review_job(
            int(job['client_id']), int(job['user_id']), int(job['brand_id']),
            str(job['job_id']), str(job['website_url']), list(job.get('images') or []),
            proposal=job.get('proposal'), background=False,
        ))
    except Exception:
        current_app.logger.exception('Worker interrompido na auditoria de marca %s', job['job_id'])
    finally:
        stop_heartbeat.set()
        pulse.join(timeout=1)
        finish(str(job['job_id']), success)
    return True


@click.command('brand-audit-worker-once')
@with_appcontext
def worker_command():
    """Process one brand-audit job; run this from a supervised worker loop."""
    if not current_app.config.get('CADU_BRAND_AUDIT_WORKER_ENABLED', True):
        raise click.ClickException('CADU_BRAND_AUDIT_WORKER_ENABLED está desabilitado.')
    click.echo('Processado.' if process_one() else 'Fila vazia.')
