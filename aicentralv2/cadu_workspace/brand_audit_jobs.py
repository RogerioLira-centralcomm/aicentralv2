"""Durable, at-most-once dispatch for slow Workspace brand audits.

Provider calls can charge credits, so a claimed job is never silently retried.
The existing retry action creates a new job from its saved evidence checkpoint.
"""
import base64
import json
import threading
import uuid

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


def enqueue_all_deep(*, include_completed=False):
    """Queue one deep audit for every active brand with an organization.

    This is intentionally database-driven and idempotent for queued/running
    jobs. It does not call providers; the supervised worker remains the only
    process allowed to spend credits.
    """
    conn = repository.get_db()
    queued = []
    skipped = []
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT c.id, c.crm_client_id, c.name, c.website_url,
                                  c.analysis_metadata,
                                  CASE WHEN NULLIF(BTRIM(c.logo_url), '') IS NOT NULL
                                             OR NULLIF(BTRIM(c.logo_upload_path), '') IS NOT NULL
                                             OR EXISTS (
                                                  SELECT 1 FROM cx_client_brand_assets a
                                                   WHERE a.client_id = c.id
                                                     AND a.status = 'approved'
                                                     AND a.role = 'logo'
                                                     AND (NULLIF(BTRIM(a.asset_path), '') IS NOT NULL
                                                       OR NULLIF(BTRIM(a.source_url), '') IS NOT NULL)
                                               ) THEN TRUE ELSE FALSE END AS has_valid_logo
                             FROM cx_clients c
                            WHERE c.crm_client_id IS NOT NULL
                              AND COALESCE(NULLIF(BTRIM(c.name), ''), '') <> ''
                            ORDER BY c.id''')
            brands = cur.fetchall()
            for brand in brands:
                brand_id = int(brand['id'])
                client_id = int(brand['crm_client_id'])
                if not brand['has_valid_logo'] or not str(brand.get('website_url') or '').strip():
                    skipped.append({
                        'brand_id': brand_id,
                        'name': str(brand.get('name') or ''),
                        'website_url': str(brand.get('website_url') or ''),
                        'reason': 'missing_valid_logo' if not brand['has_valid_logo'] else 'missing_website',
                    })
                    continue
                cur.execute('''SELECT 1
                                 FROM cadu_workspace_brand_audit_jobs
                                WHERE brand_id = %s AND analysis_mode = 'deep'
                                  AND status IN ('queued', 'running')
                                LIMIT 1''', (brand_id,))
                if cur.fetchone():
                    skipped.append(brand_id)
                    continue
                if not include_completed:
                    cur.execute('''SELECT 1
                                     FROM cadu_workspace_brand_audit_runs
                                    WHERE brand_id = %s AND analysis_mode = 'deep'
                                      AND status IN ('pending_approval', 'approved')
                                    LIMIT 1''', (brand_id,))
                    if cur.fetchone():
                        skipped.append(brand_id)
                        continue
                metadata = brand.get('analysis_metadata') or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (TypeError, ValueError):
                        metadata = {}
                social_links = list((metadata or {}).get('social_links') or [])
                job_id = str(uuid.uuid4())
                idempotency_key = (
                    f'brand-deep:{brand_id}:{uuid.uuid4()}' if include_completed
                    else f'brand-deep:{brand_id}:{brand.get("website_url") or ""}'
                )
                cur.execute('''SELECT 1
                                 FROM cadu_workspace_brand_audit_jobs
                                WHERE idempotency_key = %s
                                LIMIT 1''', (idempotency_key,))
                if cur.fetchone():
                    skipped.append(brand_id)
                    continue
                payload = {
                    'job_id': job_id, 'client_id': client_id, 'user_id': 0,
                    'brand_id': brand_id,
                    'website_url': str(brand.get('website_url') or ''),
                    'images': [], 'proposal': None, 'analysis_mode': 'deep',
                    'social_links': social_links,
                }
                cur.execute('''INSERT INTO cadu_workspace_brand_audit_jobs
                               (job_id, client_id, brand_id, payload, analysis_mode,
                                request_reason, idempotency_key)
                               VALUES (%s, %s, %s, %s::jsonb, 'deep', 'bulk_reprocess', %s)''',
                            (job_id, client_id, brand_id, json.dumps(_payload(payload)), idempotency_key))
                cur.execute('''INSERT INTO cadu_workspace_brand_audit_runs
                                   (job_id, client_id, brand_id, analysis_mode, status,
                                    input, request_reason, human_effort)
                                   VALUES (%s, %s, %s, 'deep', 'queued', %s::jsonb,
                                           'bulk_reprocess', %s::jsonb)
                                   ON CONFLICT (job_id) DO NOTHING''',
                                (job_id, client_id, brand_id,
                                 json.dumps({'website_url': payload['website_url'],
                                             'social_links': social_links,
                                             'analysis_mode': 'deep'}),
                                 json.dumps({'estimated_person_hours': 8})))
                queued.append({'job_id': job_id, 'client_id': client_id, 'brand_id': brand_id})
        conn.commit()
        return {'queued': queued, 'skipped': skipped}
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
    # A deep crawl can outlive the PostgreSQL idle connection used to claim
    # the job. Release it before recording completion so a provider failure
    # is never masked by an unrelated "connection is lost" error.
    from ..db import close_db
    close_db()
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
            analysis_mode=str(job.get('analysis_mode') or 'complete'),
            social_links=list(job.get('social_links') or []),
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


@click.command('brand-audit-enqueue-all-deep')
@click.option('--include-completed', is_flag=True, help='Enfileira novamente marcas já concluídas.')
@with_appcontext
def enqueue_all_deep_command(include_completed):
    """Mark every Workspace brand for one deep audit without calling providers."""
    result = enqueue_all_deep(include_completed=include_completed)
    click.echo(json.dumps({
        'queued_count': len(result['queued']),
        'skipped_count': len(result['skipped']),
        'queued_job_ids': [item['job_id'] for item in result['queued']],
        'skipped': result['skipped'],
    }, ensure_ascii=False))
