"""Thread daemon, igual Camadas V2."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def spawn(run_fn, job_id):
    from flask import current_app, has_app_context

    if not has_app_context():
        run_fn(job_id)
        return None

    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            try:
                run_fn(job_id)
            except Exception:
                logger.exception("Job de animação falhou: %s", job_id)
            finally:
                try:
                    from ..db import close_db

                    close_db()
                except Exception:
                    pass

    thread = threading.Thread(target=runner, daemon=True, name=f"animate-{job_id}")
    thread.start()
    return thread
