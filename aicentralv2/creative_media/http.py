"""Small, product-local HTTP contract for Studio APIs."""
from __future__ import annotations

import logging
from uuid import uuid4

from flask import jsonify, request

from ..cadu_tool_billing import InsufficientToolCredits
from ..creative_modeling_generation import OpenRouterError
from ..creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from ..creative_modeling_service import CreativeModelingService

logger = logging.getLogger(__name__)


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _json(optional=False):
    payload = request.get_json(silent=True)
    if payload is None and optional:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Corpo JSON inválido.")
    return payload


def _error(message, status, extra=None):
    payload = {"success": False, "error": str(message)}
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def _run_extra(exc):
    run = getattr(exc, "run", None)
    return {"data": {"run": run}} if run else None


def _execute(callback):
    try:
        return callback()
    except CreativeNotFoundError as exc:
        return _error(exc, 404, _run_extra(exc))
    except CreativeConflictError as exc:
        return _error(exc, 409, _run_extra(exc))
    except InsufficientToolCredits as exc:
        return _error(exc, 402)
    except (ValueError, OpenRouterError) as exc:
        return _error(exc, 400, _run_extra(exc))
    except Exception as exc:
        error_id = uuid4().hex[:12]
        logger.exception("Erro no Studio error_id=%s path=%s", error_id, request.path)
        extra = _run_extra(exc) or {}
        extra["error_id"] = error_id
        return _error("Não foi possível concluir a solicitação.", 500, extra)


def _service():
    return CreativeModelingService()


def studio_http():
    """Keep the historic tuple contract while owning it inside Studio."""
    return _execute, _json, _ok, _service
