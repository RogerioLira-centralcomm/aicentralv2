"""Bounded, durable processing for brand-inspired external link icons."""

import threading
import time

import click
from flask import current_app
from flask.cli import with_appcontext

from ..db import close_db, get_db
from .dock_icon_service import _patch_metadata, generate_dock_icon


def enqueue(cursor, *, job_id, client_id, user_id, target_type, target_id, project_id, host):
    """Called inside the same transaction that marks a shortcut as queued."""
    cursor.execute('''SELECT COUNT(*) AS total FROM cadu_workspace_link_icon_jobs
                       WHERE client_id=%s AND status IN ('queued','running')''', (client_id,))
    if int((cursor.fetchone() or {}).get('total') or 0) >= 50:
        raise ValueError('Há muitos ícones aguardando. Tente novamente em alguns minutos.')
    cursor.execute('''INSERT INTO cadu_workspace_link_icon_jobs
                      (id, client_id, user_id, target_type, target_id, project_id, host)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                   (job_id, client_id, user_id, target_type, target_id, project_id or None, host))


def reap_stale():
    """Do not replay a possibly charged provider call after worker loss."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('''UPDATE cadu_workspace_link_icon_jobs
                                 SET status='failed', finished_at=NOW(),
                                     error_message='Worker interrompido antes de concluir.'
                               WHERE status='running'
                                 AND heartbeat_at < NOW()-INTERVAL '15 minutes'
                           RETURNING id::text, client_id, user_id, target_id::text, project_id''')
            stale = [dict(row) for row in cursor.fetchall()]
            for row in stale:
                if row['project_id']:
                    cursor.execute('''UPDATE cadu_ci_projeto_links
                                         SET icon_metadata=icon_metadata || %s::jsonb
                                       WHERE id=%s AND projeto_id=%s AND id_cliente=%s
                                         AND icon_metadata->>'icon_job_id'=%s''',
                                   ('{"icon_status":"failed","icon_error":"Worker interrompido."}',
                                    row['target_id'], row['project_id'], row['client_id'], row['id'].replace('-', '')))
                else:
                    cursor.execute('''UPDATE cadu_workspace_dock_shortcuts
                                         SET metadata=metadata || %s::jsonb
                                       WHERE id=%s AND client_id=%s AND user_id=%s
                                         AND metadata->>'icon_job_id'=%s''',
                                   ('{"icon_status":"failed","icon_error":"Worker interrompido."}',
                                    row['target_id'], row['client_id'], row['user_id'], row['id'].replace('-', '')))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def claim(max_running=2):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(27131, 608)')
            cursor.execute("SELECT COUNT(*) AS total FROM cadu_workspace_link_icon_jobs WHERE status='running'")
            if int((cursor.fetchone() or {}).get('total') or 0) >= max_running:
                connection.commit()
                return None
            cursor.execute('''WITH candidate AS (
                                SELECT id FROM cadu_workspace_link_icon_jobs
                                 WHERE status='queued' ORDER BY created_at, id
                                 FOR UPDATE SKIP LOCKED LIMIT 1
                              ) UPDATE cadu_workspace_link_icon_jobs job
                                   SET status='running', claimed_at=NOW(), heartbeat_at=NOW()
                                  FROM candidate WHERE job.id=candidate.id
                            RETURNING job.id::text, job.client_id, job.user_id,
                                      job.target_type, job.target_id::text, job.project_id, job.host''')
            row = cursor.fetchone()
        connection.commit()
        return dict(row) if row else None
    except Exception:
        connection.rollback()
        raise


def heartbeat(job_id):
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('''UPDATE cadu_workspace_link_icon_jobs SET heartbeat_at=NOW()
                               WHERE id=%s AND status='running' ''', (job_id,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def finish(job_id, success):
    close_db()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute('''UPDATE cadu_workspace_link_icon_jobs
                                 SET status=%s, finished_at=NOW(), heartbeat_at=NOW()
                               WHERE id=%s AND status='running' ''',
                           ('completed' if success else 'failed', job_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def process_one():
    reap_stale()
    job = claim()
    if not job:
        return False
    job_id = str(job['id'])
    target_id = str(job['target_id'])
    project_id = str(job.get('project_id') or '')
    client_id, user_id = int(job['client_id']), int(job['user_id'])
    # Metadata uses the compact UUID form written by the API route.
    metadata_job_id = job_id.replace('-', '')
    stop = threading.Event()
    app = current_app._get_current_object()

    def pulse():
        with app.app_context():
            while not stop.wait(30):
                try:
                    heartbeat(job_id)
                except Exception:
                    app.logger.exception('Heartbeat do ícone %s falhou', job_id)

    thread = threading.Thread(target=pulse, daemon=True, name=f'link-icon-heartbeat-{job_id[:8]}')
    thread.start()
    success = False
    try:
        if not _patch_metadata(client_id, user_id, target_id, metadata_job_id,
                               {'icon_status': 'running'}, project_id=project_id):
            current_app.logger.info('Link removido ou alterado antes da geração do ícone %s', job_id)
            return True
        close_db()
        success = bool(generate_dock_icon(client_id=client_id, user_id=user_id,
                                          shortcut_id=target_id, job_id=metadata_job_id,
                                          host=str(job['host']), project_id=project_id))
    except Exception:
        current_app.logger.exception('Falha no worker de ícone %s', job_id)
        try:
            _patch_metadata(client_id, user_id, target_id, metadata_job_id,
                            {'icon_status': 'failed', 'icon_error': 'Falha no worker.'}, project_id=project_id)
        except Exception:
            current_app.logger.exception('Falha ao registrar erro de ícone %s', job_id)
    finally:
        stop.set()
        thread.join(timeout=1)
        finish(job_id, success)
    return True


@click.command('link-icon-worker-once')
@with_appcontext
def worker_command():
    """Processa no máximo um ícone; executar em loop supervisionado."""
    click.echo('Processado.' if process_one() else 'Fila vazia.')


@click.command('link-icon-worker-loop')
@with_appcontext
def worker_loop_command():
    """Loop supervisionado; a fila limita a dois processos ativos globalmente."""
    while True:
        try:
            if not process_one():
                time.sleep(3)
        except Exception:
            current_app.logger.exception('Worker de ícones interrompeu um ciclo')
            close_db()
            time.sleep(10)
