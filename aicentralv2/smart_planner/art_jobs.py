"""Geração das artes do plano fora da requisição HTTP.

Três artes e as versões dos canais passam fácil dos 300 s do Gunicorn e do nginx; a requisição
caía com uma página de erro e a tela só dizia "tente de novo". Agora a requisição só inicia o
trabalho, o estado fica em dados_detectados["geracao_artes"] e a tela acompanha por consulta.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from datetime import datetime, timezone

from ..services.openrouter_service import OpenRouterError
from .cost import bound_session
from .helpers import as_dict, text
from .images import regenerate_creative
from .processor import _stale_processing as _stale
from .repository import get_by_token, merge_dados, update_session

logger = logging.getLogger(__name__)

KEY = "geracao_artes"


def job_view(row: dict) -> dict:
    job = as_dict(as_dict((row or {}).get("dados_detectados")).get(KEY))
    if job.get("status") == "running" and (_stale(job) or _worker_gone(job)):
        # Worker reciclado (max_requests) ou reiniciado no meio: sem isto a tela esperaria para sempre.
        return {**job, "status": "error", "error": "A geração foi interrompida no servidor. Gere de novo."}
    return job or {"status": "idle"}


def _worker_gone(job: dict) -> bool:
    """O processo que gera ainda existe? Só dá para saber na mesma máquina."""
    if job.get("host") != socket.gethostname() or not isinstance(job.get("pid"), int):
        return False
    try:
        os.kill(job["pid"], 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def start(token: str, folha: dict, *, references: list[str], channels: list, count: int, shape: str, plan_mode: str) -> dict:
    current = job_view(get_by_token(token))
    if current.get("status") == "running":
        return current
    job = _mark(token, "running", "prep", count=count, shape=shape, startedAt=_now(), pid=os.getpid(), host=socket.gethostname())

    from flask import current_app, has_app_context
    args = (token, folha, references, channels, count, shape, plan_mode, job)
    if not has_app_context():
        _run(*args)
    else:
        app = current_app._get_current_object()

        def runner():
            with app.app_context():
                _run(*args)

        threading.Thread(target=runner, daemon=True, name=f"sp-arts-{token[:12]}").start()
    return job


def _run(token, folha, references, channels, count, shape, plan_mode, job) -> None:
    extra = {key: job.get(key) for key in ("count", "shape", "startedAt", "pid", "host")}
    try:
        _mark(token, "running", "arts", **extra)
        with bound_session(token):
            folha = regenerate_creative(
                folha, uploaded_references=references, channels=channels, count=count, shape=shape,
                on_variants=lambda: _mark(token, "running", "variants", **extra),
            )
        merge_dados(token, {"folha": folha})
        if plan_mode != "completo":
            update_session(token, {"plan_content": folha})
        _mark(token, "done", "done", **extra)
    except Exception as exc:
        logger.exception("Falha ao gerar as artes do plano: %s", token)
        try:
            _mark(token, "error", "error", error=error_message(exc), **extra)
        except Exception:
            logger.exception("Não foi possível gravar a falha da geração de artes: %s", token)
    finally:
        try:
            from ..db import close_db
            close_db()
        except Exception:
            pass


def error_message(exc: Exception) -> str:
    """O motivo real para a tela; erro interno ganha o tipo, para quem for investigar."""
    if isinstance(exc, (ValueError, OpenRouterError)) and text(str(exc)):
        return text(str(exc))
    detail = text(str(exc))[:200]
    return f"Erro interno ao gerar as artes ({type(exc).__name__}{': ' + detail if detail else ''})."


def _mark(token: str, status: str, step: str, **extra) -> dict:
    job = {"status": status, "step": step, "updatedAt": _now(), **extra}
    merge_dados(token, {KEY: job})
    return job


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
