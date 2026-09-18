"""python -m aicentralv2.creative_media.queue_worker [--drain]

PostgreSQL is the generation queue. Export requests are durable local records.
Run under systemd in production; --drain is an on-demand independent process.
"""
import argparse
import json
import logging
import os
import time
from pathlib import Path

from .file_lock import file_claim

log = logging.getLogger(__name__)


def drain_exports(root):
    from .studio import _render_job
    count = 0
    for path in sorted(root.glob('studio/*/export-*.json')):
        with file_claim(path.with_suffix('.lock')) as acquired:
            if not acquired:
                continue
            try:
                row = json.loads(path.read_text())
                if row.get('status') not in {'queued','rendering'} or not row.get('work'):
                    continue
                work = row['work']
                _render_job(path.parent, row['id'], Path(work['source']), work['edit'],
                            Path(work['sound']) if work.get('sound') else None, release_slot=False)
                count += 1
            except Exception:
                log.exception('Export record could not be processed: %s',path.name)
    return count


def drain_tasks(root):
    from .studio_tasks import run_task
    count=0
    for path in sorted(root.glob('studio/*/task-*.json')):
        with file_claim(path.with_suffix('.lock')) as acquired:
            if not acquired:continue
            try:
                row=json.loads(path.read_text())
                if row.get('status') not in {'queued','processing'}:continue
                run_task(path.parent,row['id']);count+=1
            except Exception:log.exception('Media task record could not be processed')
    return count


def run_once(app):
    from .storage import media_root
    count = 0
    with app.app_context():
        root = media_root()
        # Two local worker lanes cap CPU use. Deploy all workers against the
        # same media volume, as required by the existing asset storage.
        for lane in range(2):
            with file_claim(root / f'worker-{lane}.lock') as acquired:
                if not acquired:
                    continue
                count += drain_tasks(root)
                count += drain_exports(root)
                try:
                    if app.config.get('STUDIO_PROJECTS_POSTGRES', False):
                        from .. import db
                        from .schema import ensure_schema
                        from .studio_maintenance import drain_studio_maintenance
                        connection = db.get_db()
                        ensure_schema(connection)
                        maintenance = drain_studio_maintenance(connection, limit=10)
                        count += maintenance['emails'] + maintenance['assets'] + maintenance['failed']
                except Exception:
                    log.exception('Studio delivery or cleanup queue unavailable')
                try:
                    from ..creative_modeling_routes import _service
                    service = _service()._format_lab()._animate()
                    from .studio_push import deliver
                    deliver(root,service.repository)
                    for ident in service.repository.runnable_jobs():
                        try:
                            service._run(ident)
                            count += 1
                        except Exception:
                            log.exception('Generation job failed: %s', ident)
                    deliver(root,service.repository)
                except Exception:
                    log.exception('Generation queue unavailable')
                return count
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--drain',action='store_true',help='Exit after processing available work')
    parser.add_argument('--check',action='store_true',help='Check queue and storage without running any job')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from .. import create_app
    app = create_app()
    if os.getenv('MEDIA_INSTANCE_PATH'):
        app.instance_path = os.environ['MEDIA_INSTANCE_PATH']
    if args.check:
        try:
            with app.app_context():
                from ..creative_modeling_routes import _service
                from .storage import media_root
                repository=_service()._format_lab()._media_repository()
                repository.runnable_jobs()
                test=media_root()/'.worker-check';test.write_text('ok');test.unlink()
            print('Queue database and media storage ready. No jobs executed.')
        except Exception:
            print('Queue database or media storage unavailable. No jobs executed.')
            raise SystemExit(1)
        return
    idle_since = time.monotonic()
    while True:
        count = run_once(app)
        if count:
            idle_since = time.monotonic()
        if args.drain and time.monotonic()-idle_since >= 30:
            return
        time.sleep(5)


if __name__ == '__main__':
    main()
