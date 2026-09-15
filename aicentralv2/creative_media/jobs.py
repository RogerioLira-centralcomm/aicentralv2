"""Dispatch persistent jobs to a process independent of the web worker."""
import os
import subprocess
import sys
from pathlib import Path
from flask import current_app, has_app_context


def worker_mode():
    return current_app.config.get('MEDIA_WORKER_MODE', os.getenv('MEDIA_WORKER_MODE','process')) if has_app_context() else 'inline'


def wake_worker():
    # A supervised worker uses the same database queue. In supervised mode no
    # subprocess is created by HTTP requests.
    if worker_mode() == 'supervised':
        return None
    from .storage import media_root
    log_path = media_root() / 'worker.log'
    env = dict(os.environ)
    env['MEDIA_INSTANCE_PATH'] = current_app.instance_path
    with log_path.open('ab') as log:
        return subprocess.Popen([sys.executable, '-m', 'aicentralv2.creative_media.queue_worker', '--drain'],
            cwd=Path(__file__).resolve().parents[2], env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True, close_fds=True)


def spawn(run_fn, job_id):
    if worker_mode() == 'inline':
        return run_fn(job_id)
    if worker_mode() == 'thread':
        import threading
        app = current_app._get_current_object()
        def runner():
            with app.app_context():
                run_fn(job_id)
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return thread
    return wake_worker()
