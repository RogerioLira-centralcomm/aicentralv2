"""Versioned backend contract consumed by the future Conversations V2 UI."""

import secrets

from flask import Blueprint, Response, abort, current_app, jsonify, request, session, stream_with_context
from werkzeug.exceptions import HTTPException

from .request_context import resolve
from .response_policy import budget_for, policy_for
from .router import route_request
from ..mcp.registry import load_builtin_tools
from ..mcp.authorization import MAX_AGE_SECONDS, issue
from ..artifacts import create_draft, get_artifact, patch_artifact
from .service import prepare as prepare_message, stream as stream_message


bp = Blueprint("cadu_agent_v2", __name__, url_prefix="/workspace/api/v2")


@bp.before_request
def protect():
    if not session.get("user_id"):
        abort(401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = session.get("family_csrf")
        if not token or not secrets.compare_digest(token, request.headers.get("X-CSRF-Token", "")):
            abort(403, description="Atualize a página e tente novamente.")


@bp.errorhandler(Exception)
def api_error(exc):
    if isinstance(exc, HTTPException):
        return jsonify(error=exc.description), exc.code
    current_app.logger.exception("Falha na API Cadu Conversations V2")
    return jsonify(error="Não foi possível concluir a operação."), 503


@bp.get("/capabilities")
def capabilities():
    current = resolve(surface=request.args.get("surface") or "conversations")
    return jsonify(runtime="v2", context=current.to_dict(), tools=load_builtin_tools().list(current))


@bp.post("/mcp-token")
def mcp_token():
    data = request.get_json(silent=True) or {}
    exposure = str(data.get("exposure") or "internal")
    if exposure not in {"internal", "customer_agent"}:
        abort(400, description="Perfil de agente inválido.")
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"))
    return jsonify(token=issue(current, exposure), expires_in=MAX_AGE_SECONDS,
                   endpoint="/workspace/mcp", exposure=exposure, context=current.to_dict())


@bp.post("/route")
def route_preview():
    data = request.get_json(silent=True) or {}
    message = " ".join(str(data.get("message") or "").split())
    if not 1 <= len(message) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"))
    route = route_request(message, current.surface, bool(current.project_ref))
    return jsonify(
        route=route.to_dict(), context=current.to_dict(), policy=policy_for(route),
        budget=budget_for(route).__dict__,
    )


@bp.post("/conversations/messages")
def conversation_message():
    if not current_app.config.get("CADU_CONVERSATIONS_V2_ENABLED", False):
        abort(404)
    run = prepare_message(request.get_json(silent=True) or {})
    return Response(stream_with_context(stream_message(run)), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.post("/artifacts")
def artifact_create():
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"))
    artifact = create_draft(current, str(data.get("type") or ""), data.get("content"),
                            title=data.get("title"), conversation_id=data.get("conversation_id"))
    return jsonify(artifact=artifact), 201


@bp.get("/artifacts/<uuid:artifact_id>")
def artifact_get(artifact_id):
    return jsonify(artifact=get_artifact(resolve(), str(artifact_id)))


@bp.patch("/artifacts/<uuid:artifact_id>")
def artifact_patch(artifact_id):
    data = request.get_json(silent=True) or {}
    artifact = patch_artifact(resolve(conversation_id=data.get("conversation_id")), str(artifact_id),
                              data.get("content"), expected_version=data.get("expected_version"),
                              title=data.get("title"), status=data.get("status"),
                              change_summary=data.get("change_summary"))
    return jsonify(artifact=artifact)
