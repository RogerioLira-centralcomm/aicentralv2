"""Separate public MCP transport and the Workspace management screen."""

from __future__ import annotations

import json
import secrets
from time import monotonic

from flask import Blueprint, abort, jsonify, render_template, request, session

from ..auth import login_required
from ..cadu_family import repository
from ..cadu_tool_billing import InsufficientToolCredits
from ..cadu_workspace.agent_v2.contracts import RequestContext
from ..cadu_workspace.mcp.registry import ToolError, load_builtin_tools
from ..product_domains import product_url
from . import auth, usage


bp = Blueprint("cadu_public_mcp", __name__)
PUBLIC_MCP_PATH = "/mcp/cadu/v1"
PROTOCOL_VERSION = "2026-07-28"

# The public surface is an intentional subset of internal capabilities. New
# internal tools do not become internet-facing by accident.
PUBLIC_TOOLS = frozenset({
    "google.get_connector_status",
    "google.list_project_resources",
    "google.list_calendar_events",
    "google.list_meet_records",
    "google.list_meet_artifacts",
    "google.link_resource_to_project",
    "resources.search",
    "resources.get",
    "resources.capabilities",
    "projects.list_sources",
    "projects.list_resources",
    "projects.inspect_file_support",
    "projects.classify_intake",
    "projects.create_link_reference",
    "brands.list",
    "reports.list_project_reports",
    "reports.get_report_metrics",
    "reports.compare_report_to_plan",
})
PUBLIC_WRITE_TOOLS = frozenset({
    "google.link_resource_to_project",
    "projects.create_link_reference",
})


def _error(request_id, code, message, data=None):
    value = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data:
        value["error"]["data"] = data
    return value


def _headers(response):
    response.headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Cadu-MCP-Endpoint"] = "public-v1"
    return response


def _public_catalog(context: RequestContext, exposure: str = "customer_agent") -> list[dict]:
    return [item for item in load_builtin_tools().list(context, exposure) if item["name"] in PUBLIC_TOOLS]


def _request_context_for_auth(params: dict) -> dict:
    value = dict(params or {})
    # A tools/call request nests the execution arguments, but context remains
    # at params level so the public schema is compatible with MCP hosts.
    if not value.get("project_ref") and isinstance(value.get("arguments"), dict):
        value["project_ref"] = value["arguments"].get("project_ref")
    return value


def _workspace_api_csrf() -> bool:
    """Check the same session-bound token used by Workspace APIs."""
    token = session.get("family_csrf")
    supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("_csrf", "")
    return bool(token and secrets.compare_digest(token, supplied))


@bp.post(PUBLIC_MCP_PATH)
def public_rpc():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return _headers(jsonify(_error(None, -32600, "Requisição JSON-RPC inválida."))), 400
    request_id, method = payload.get("id"), payload.get("method")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return _headers(jsonify(_error(request_id, -32602, "Parâmetros inválidos."))), 400
    try:
        principal = auth.authenticate(_request_context_for_auth(params))
    except auth.PublicMcpAuthError as exc:
        response = jsonify(_error(request_id, -32001, str(exc)))
        response.status_code = 401
        response.headers["WWW-Authenticate"] = 'Bearer realm="cadu-mcp-public", error="invalid_token"'
        response.headers["X-Cadu-MCP-Auth"] = "api-key-beta"
        return _headers(response)

    try:
        registry = load_builtin_tools()
        current = principal.context
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion") if isinstance(params.get("protocolVersion"), str) else PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cadu-public-mcp", "version": "1.0.0"},
                "instructions": "Use project_ref no nível params ou configure um projeto padrão na chave.",
            }
        elif method == "tools/list":
            result = {"tools": _public_catalog(current)}
        elif method == "tools/call":
            name = str(params.get("name") or "")
            if name not in PUBLIC_TOOLS:
                raise ToolError("Esta ferramenta não faz parte da superfície pública do Cadu.")
            try:
                auth.ensure_scope(principal, name)
            except auth.PublicMcpAuthError as exc:
                raise ToolError(str(exc)) from exc
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ValueError("Os argumentos da ferramenta precisam ser um objeto.")
            arguments = dict(arguments)
            if name in PUBLIC_WRITE_TOOLS and "request_id" not in arguments:
                arguments["request_id"] = request_id
            tool_request_id = usage.new_request_id(arguments.get("request_id") or request_id)
            started_at = monotonic()
            credit_cost = usage.tool_cost(name)
            usage.authorize_credits(client_id=principal.client_id, user_id=principal.user_id, tool_name=name)
            usage.record(
                key_id=principal.key_id, client_id=principal.client_id, user_id=principal.user_id,
                client_type=principal.client_type, method=method, tool_name=name,
                request_id=tool_request_id, status="started", credit_cost=credit_cost,
                started_at=started_at, input_bytes=len(request.get_data(cache=True) or b""),
            )
            try:
                value = registry.execute(name, arguments, current, "customer_agent")
                usage.charge_credits(
                    client_id=principal.client_id, user_id=principal.user_id,
                    tool_name=name, idempotency_key=f"{principal.key_id}:{tool_request_id}",
                    metadata={"client_type": principal.client_type},
                )
                encoded = json.dumps(value, ensure_ascii=False, default=str)
                usage.record(
                    key_id=principal.key_id, client_id=principal.client_id, user_id=principal.user_id,
                    client_type=principal.client_type, method=method, tool_name=name,
                    request_id=tool_request_id, status="completed", credit_cost=credit_cost,
                    started_at=started_at, output_bytes=len(encoded.encode("utf-8")),
                )
                result = {"content": [{"type": "text", "text": encoded}], "structuredContent": value, "isError": False}
            except Exception as exc:
                usage.record(
                    key_id=principal.key_id, client_id=principal.client_id, user_id=principal.user_id,
                    client_type=principal.client_type, method=method, tool_name=name,
                    request_id=tool_request_id, status="failed", credit_cost=0,
                    started_at=started_at, error_code=type(exc).__name__,
                )
                raise
        else:
            response = jsonify(_error(request_id, -32601, "Método não suportado."))
            response.status_code = 404
            return _headers(response)
    except InsufficientToolCredits as exc:
        return _headers(jsonify(_error(request_id, -32020, str(exc), {"code": "credits_insufficient"}))), 402
    except ToolError as exc:
        return _headers(jsonify({"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": str(exc)}],
            "structuredContent": {"error": {"code": getattr(exc, "code", "tool_failed"), "message": str(exc)}},
            "isError": True,
        }}))
    except ValueError as exc:
        return _headers(jsonify(_error(request_id, -32602, str(exc)))), 400
    return _headers(jsonify({"jsonrpc": "2.0", "id": request_id, "result": result}))


@bp.get("/.well-known/cadu-mcp-public")
def public_metadata():
    """Stable bootstrap metadata while OAuth 2.1 is being added."""
    return jsonify({
        "name": "cadu-public-mcp",
        "version": "1.0.0",
        "endpoint": product_url("workspace", PUBLIC_MCP_PATH),
        "authentication": {"type": "bearer_api_key", "header": "Authorization", "prefix": auth.KEY_PREFIX},
        "oauth": {"status": "planned", "discovery": None},
        "scopes": list(auth.CLIENT_SCOPES),
        "credit_policy": "Cada tools/call bem-sucedido consome a tarifa pública compartilhada do Cadu.",
    })


def _session_scope() -> tuple[int, int]:
    return int(session.get("cliente_id") or 0), int(session.get("user_id") or 0)


@bp.get("/workspace/app/integracoes/agents")
@login_required
def agents_page():
    session.setdefault("family_csrf", secrets.token_urlsafe(32))
    client_id, user_id = _session_scope()
    projects = [item for item in repository.entities(client_id) if item.get("kind") == "project"]
    credit = {}
    try:
        from ..cadu_skills.repository import credit_position
        credit = credit_position(client_id)
    except Exception:
        credit = {"available": 0, "monthly": 0, "monthly_usage_percentage": 0}
    return render_template(
        "cadu_workspace/mcp_agents.html",
        keys=auth.list_keys(client_id=client_id, user_id=user_id),
        projects=projects,
        usage=usage.summary(client_id=client_id, user_id=user_id),
        credit=credit,
        endpoint=product_url("workspace", PUBLIC_MCP_PATH),
        metadata_url=product_url("workspace", "/.well-known/cadu-mcp-public"),
        client_types=auth.CLIENT_TYPES,
    )


@bp.post("/workspace/app/integracoes/agents/keys")
@login_required
def create_agent_key():
    if not _workspace_api_csrf():
        abort(403, description="Atualize a página e tente novamente.")
    client_id, user_id = _session_scope()
    data = request.get_json(silent=True) or request.form
    requested_scopes = data.get("scopes") if hasattr(data, "get") else None
    if not requested_scopes:
        requested_scopes = list(auth.DEFAULT_SCOPES)
    if str(data.get("scope_write") or "").lower() in {"1", "true", "on", "yes"}:
        requested_scopes = list(requested_scopes) + ["google:write"]
    if str(data.get("scope_project_write") or "").lower() in {"1", "true", "on", "yes"}:
        requested_scopes = list(requested_scopes) + ["projects:write"]
    try:
        key = auth.create_key(
            client_id=client_id, user_id=user_id,
            label=data.get("label"), client_type=data.get("client_type"),
            default_project_ref=data.get("default_project_ref") or None,
            scopes=requested_scopes,
        )
    except auth.PublicMcpAuthError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "key": key, "endpoint": product_url("workspace", PUBLIC_MCP_PATH)})


@bp.post("/workspace/app/integracoes/agents/keys/<key_id>/revoke")
@login_required
def revoke_agent_key(key_id):
    if not _workspace_api_csrf():
        abort(403, description="Atualize a página e tente novamente.")
    client_id, user_id = _session_scope()
    try:
        changed = auth.revoke_key(key_id=key_id, client_id=client_id, user_id=user_id)
    except auth.PublicMcpAuthError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "revoked": changed})
