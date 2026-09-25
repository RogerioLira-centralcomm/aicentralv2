"""Durable, at-most-once dispatch for slow Workspace brand audits.

Provider calls can charge credits, so a claimed job is never silently retried.
The existing retry action creates a new job from its saved evidence checkpoint.
"""
import base64
import json
import signal
import threading
import uuid

import click
from flask import current_app
from flask.cli import with_appcontext

from ..cadu_family import repository


_WORKER_STOP = threading.Event()
_WORKER_ID = str(uuid.uuid4())


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
                   (job_id, client_id, brand_id, payload, analysis_mode, request_reason, requested_by, job_type)
                   VALUES (%s, %s, %s, %s::jsonb, %s, %s, NULLIF(%s, 0), %s)
                   ON CONFLICT (job_id) DO NOTHING''',
                (job['job_id'], job['client_id'], job['brand_id'], json.dumps(_payload(job)),
                 str(job.get('analysis_mode') or 'complete'), str(job.get('request_reason') or 'manual'),
                 int(job.get('user_id') or 0), str(job.get('job_type') or 'audit')),
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


def claim(max_running=2):
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            # Enforce a global provider concurrency limit even if the service
            # manager accidentally starts more than one worker process.
            cur.execute('SELECT pg_advisory_xact_lock(27131, 609)')
            cur.execute("SELECT COUNT(*) AS total FROM cadu_workspace_brand_audit_jobs WHERE status='running'")
            if int((cur.fetchone() or {}).get('total') or 0) >= max_running:
                conn.commit()
                return None
            cur.execute(
                '''WITH next_job AS (
                       SELECT job_id FROM cadu_workspace_brand_audit_jobs
                        WHERE status = 'queued'
                        ORDER BY created_at, job_id
                        FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   UPDATE cadu_workspace_brand_audit_jobs j
                      SET status = 'running', claimed_at = NOW(), heartbeat_at = NOW(),
                          attempts = attempts + 1, worker_id = %s
                     FROM next_job n
                    WHERE j.job_id = n.job_id
                RETURNING j.payload, j.job_type''', (_WORKER_ID,)
            )
            row = cur.fetchone()
        conn.commit()  # Durable claim before any Firecrawl/model request.
        if not row:
            return None
        restored = _restore(row['payload'])
        restored['job_type'] = row.get('job_type') or 'audit'
        return restored
    except Exception:
        conn.rollback()
        raise


def renew_lease(job_id: str):
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_workspace_brand_audit_jobs
                              SET heartbeat_at = NOW()
                            WHERE job_id = %s AND status = 'running' AND worker_id = %s''',
                        (job_id, _WORKER_ID))
            active = cur.rowcount == 1
        conn.commit()
        return active
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
                      SET status = %s, finished_at = NOW(), heartbeat_at = NOW(),
                          payload = '{}'::jsonb,
                          error_message = CASE WHEN %s THEN NULL ELSE 'Worker terminou sem concluir.' END
                    WHERE job_id = %s AND status = 'running' AND worker_id = %s''',
                ('completed' if success else 'failed', success, job_id, _WORKER_ID),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def fail_stale(job_id: str = None):
    """Close expired worker leases; provider calls are never auto-replayed."""
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''UPDATE cadu_workspace_brand_audit_jobs
                      SET status = 'failed', finished_at = NOW(),
                          payload = '{}'::jsonb,
                          error_message = 'Worker interrompido antes de concluir.'
                    WHERE status = 'running'
                      AND heartbeat_at < NOW() - INTERVAL '15 minutes'
                      AND (%s::varchar IS NULL OR job_id = %s)
                RETURNING job_id, client_id, brand_id''',
                (job_id, job_id),
            )
            stale = [dict(row) for row in cur.fetchall()]
            for row in stale:
                cur.execute(
                    '''UPDATE cadu_workspace_brand_audit_runs
                          SET status = 'failed', updated_at = NOW(), completed_at = NOW(),
                              collected_data = jsonb_set(
                                  COALESCE(collected_data, '{}'::jsonb), '{error}',
                                  to_jsonb('Worker expirado antes da conclusão.'::text), TRUE
                              )
                        WHERE job_id = %s AND status IN ('queued', 'running')''',
                    (row['job_id'],),
                )
        conn.commit()
        if stale:
            from .routes import _save_brand_review_job
            for row in stale:
                _save_brand_review_job(
                    int(row['client_id']), int(row['brand_id']), str(row['job_id']),
                    status='failed', stage='failed',
                    message='A auditoria foi interrompida antes de terminar.',
                    error='O worker perdeu a lease. Nenhuma repetição automática foi iniciada.',
                )
        return len(stale)
    except Exception:
        conn.rollback()
        raise


def process_one():
    fail_stale()
    job = claim()
    if job is None:
        return False
    from .routes import _run_brand_module_review_job, _start_brand_review_job
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
                    app.logger.exception('Não foi possível atualizar o progresso da auditoria %s', job['job_id'])
                try:
                    renew_lease(str(job['job_id']))
                except Exception:
                    app.logger.exception('Não foi possível renovar a lease da auditoria %s', job['job_id'])

    pulse = threading.Thread(target=heartbeat, daemon=True, name=f'brand-audit-heartbeat-{str(job["job_id"])[:12]}')
    pulse.start()
    success = False
    try:
        if job.get('job_type') == 'module_review':
            success = bool(_run_brand_module_review_job(
                int(job['client_id']), int(job['user_id']), int(job['brand_id']),
                str(job['job_id']), str(job['module_id']), job.get('analysis') or {},
            ))
        else:
            success = bool(_start_brand_review_job(
                int(job['client_id']), int(job['user_id']), int(job['brand_id']),
                str(job['job_id']), str(job['website_url']), list(job.get('images') or []),
                proposal=job.get('proposal'), background=False,
                analysis_mode=str(job.get('analysis_mode') or 'complete'),
                social_links=list(job.get('social_links') or []),
                additional_sources=list(job.get('additional_sources') or []),
                excluded_sources=list(job.get('excluded_sources') or []),
                existing_asset_ids=job.get('existing_asset_ids'),
            ))
    except Exception as exc:
        current_app.logger.exception('Worker interrompido na auditoria de marca %s', job['job_id'])
        if job.get('job_type') == 'module_review':
            from .routes import _save_brand_review_job
            try:
                _save_brand_review_job(
                    int(job['client_id']), int(job['brand_id']), str(job['job_id']),
                    status='failed', stage='failed', message='O parecer não foi atualizado.',
                    error=str(exc)[:360],
                )
            except Exception:
                current_app.logger.exception('Não foi possível registrar a falha do parecer %s', job['job_id'])
    finally:
        stop_heartbeat.set()
        pulse.join(timeout=5)
        finish(str(job['job_id']), success)
    return True


@click.command('brand-audit-worker-once')
@with_appcontext
def worker_command():
    """Process one brand-audit job; run this from a supervised worker loop."""
    if not current_app.config.get('CADU_BRAND_AUDIT_WORKER_ENABLED', True):
        raise click.ClickException('CADU_BRAND_AUDIT_WORKER_ENABLED está desabilitado.')
    click.echo('Processado.' if process_one() else 'Fila vazia.')


@click.command('brand-audit-worker-loop')
@with_appcontext
def worker_loop_command():
    """Long-running supervised worker with lease reaping and graceful stop."""
    if not current_app.config.get('CADU_BRAND_AUDIT_WORKER_ENABLED', True):
        raise click.ClickException('CADU_BRAND_AUDIT_WORKER_ENABLED está desabilitado.')
    _WORKER_STOP.clear()
    previous_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[sig] = signal.getsignal(sig)
        signal.signal(sig, lambda *_: _WORKER_STOP.set())
    try:
        while not _WORKER_STOP.is_set():
            try:
                if not process_one():
                    from ..db import close_db
                    close_db()
                    _WORKER_STOP.wait(2)
            except Exception:
                current_app.logger.exception('Ciclo do worker de auditoria de marca falhou')
                from ..db import close_db
                close_db()
                _WORKER_STOP.wait(5)
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


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
