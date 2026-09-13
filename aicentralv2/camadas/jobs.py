"""Jobs da análise. Sem Celery: thread daemon + polling."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

STAGES = {
    "queued": ("queued", 0, "Enviando original"),
    "reading_creative": ("running", 20, "Lendo o criativo"),
    "finding_objects": ("running", 40, "Encontrando objetos"),
    "extracting_elements": ("running", 72, "Separando elementos do criativo"),
    "assembling_scene": ("running", 80, "Montando HTML"),
    "preparing_review": ("running", 95, "Preparando revisão"),
    "done": ("done", 100, "Análise pronta"),
    "failed": ("failed", 100, "A análise falhou"),
}


def stage_payload(name, message=None):
    status, progress, default = STAGES.get(name) or STAGES["queued"]
    return {
        "status": status,
        "stage": name,
        "progress": progress,
        "message": message or default,
    }


def spawn(analyze_fn, job_id, creative_id):
    """Roda a análise fora do request. Sem app context, executa na hora."""
    from flask import current_app, has_app_context

    if not has_app_context():
        analyze_fn(job_id, creative_id)
        return None

    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            try:
                analyze_fn(job_id, creative_id)
            except Exception:
                logger.exception("Job Camadas V2 falhou: %s", job_id)
            finally:
                try:
                    from ..db import close_db

                    close_db()
                except Exception:
                    pass

    thread = threading.Thread(
        target=runner,
        daemon=True,
        name=f"camadas-{job_id}",
    )
    thread.start()
    return thread
