"""Authenticated JSON-RPC transport for the internal Cadu MCP."""

from flask import Blueprint, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .authorization import MCPUnauthorized, authorize
from .registry import ToolError, load_builtin_tools


bp = Blueprint("cadu_workspace_mcp", __name__, url_prefix="/workspace/mcp")
CURRENT_PROTOCOL_VERSION = "2026-07-28"


def _error(request_id, code, message, data=None):
    value = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data:
        value["error"]["data"] = data
    return value


@bp.before_request
def protect_internal_mcp():
    payload = request.get_json(silent=True) or {}
    params = payload.get("params") if isinstance(payload, dict) else {}
    protocol = request.headers.get("MCP-Protocol-Version", "")
    if protocol.startswith("2026-"):
        if request.headers.get("Mcp-Method") != payload.get("method"):
            return jsonify(_error(payload.get("id"), -32600, "O header Mcp-Method não corresponde ao corpo.")), 400
        if payload.get("method") == "tools/call" and request.headers.get("Mcp-Name") != params.get("name"):
            return jsonify(_error(payload.get("id"), -32600, "O header Mcp-Name não corresponde ao corpo.")), 400
    try:
        g.cadu_mcp_principal = authorize(params if isinstance(params, dict) else {})
    except MCPUnauthorized as exc:
        return jsonify(_error(None, -32001, str(exc))), 401


@bp.after_request
def protocol_headers(response):
    response.headers["MCP-Protocol-Version"] = CURRENT_PROTOCOL_VERSION
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("")
def rpc():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return jsonify(_error(None, -32600, "Requisição JSON-RPC inválida.")), 400
    request_id, method = payload.get("id"), payload.get("method")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return jsonify(_error(request_id, -32602, "Parâmetros inválidos.")), 400
    try:
        principal = g.cadu_mcp_principal
        current = principal.context
        registry = load_builtin_tools()
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if isinstance(requested, str) else CURRENT_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cadu-workspace", "version": "2.0"},
            }
        elif method == "tools/list":
            result = {"tools": registry.list(current, principal.exposure)}
        elif method == "tools/call":
            name = str(params.get("name") or "")
            value = registry.execute(name, params.get("arguments") or {}, current, principal.exposure)
            result = {"content": [{"type": "text", "text": __import__("json").dumps(value, ensure_ascii=False, default=str)}],
                      "structuredContent": value, "isError": False}
        else:
            return jsonify(_error(request_id, -32601, "Método não suportado.")), 404
    except ToolError as exc:
        if method == "tools/call":
            return jsonify({"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": str(exc)}],
                "structuredContent": {"error": {"code": exc.code, "message": str(exc)}},
                "isError": True,
            }})
        return jsonify(_error(request_id, -32010, str(exc), {"code": exc.code})), 400
    except ValueError as exc:
        return jsonify(_error(request_id, -32602, str(exc))), 400
    return jsonify({"jsonrpc": "2.0", "id": request_id, "result": result})


@bp.post("/uploads")
def upload_project_source():
    """Multipart companion endpoint for upload intents issued by an MCP tool."""
    from .. import project_source_service
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify(error="Envie o arquivo no campo file."), 400
    try:
        value = project_source_service.save_upload(
            g.cadu_mcp_principal.context, request.form.get("upload_token", ""), uploaded,
        )
    except HTTPException as exc:
        return jsonify(error=exc.description), exc.code
    return jsonify(source=value), 201
