"""Separate public MCP transport and the Workspace management screen."""

from __future__ import annotations

import json
import secrets
from copy import deepcopy
from time import monotonic

from flask import Blueprint, abort, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException

from ..auth import login_required
from ..cadu_family import repository
from ..cadu_tool_billing import InsufficientToolCredits
from ..cadu_workspace.agent_v2.contracts import RequestContext
from ..cadu_workspace.mcp.registry import ToolError, load_builtin_tools
from ..product_domains import product_url
from . import auth, usage


bp = Blueprint("cadu_public_mcp", __name__)
PUBLIC_MCP_PATH = "/mcp/cadu/v1"
MCP_ICON_PATH = "/static/images/cadu/products/cadu-mcp-icon.svg"
PROTOCOL_VERSION = "2026-07-28"

# The public surface is an intentional subset of internal capabilities. New
# internal tools do not become internet-facing by accident.
PUBLIC_TOOLS = frozenset({
    "media.list_jobs",
    "media.get_job",
    "media.start_studio_session",
    "media.generate_image",
    "media.creation_capabilities",
    "planner.list_plans",
    "planner.search_catalog",
    "planner.list_link_tests",
    "planner.get_link_test",
    "planner.get_brief",
    "planner.get_media_plan",
    "web.search",
    "web.read",
    "account.get",
    "account.update_profile",
    "account.update_agency",
    "account.list_team",
    "account.invite_team_member",
    "credits.get_balance",
    "credits.list_packages",
    "credits.purchase_package",
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
    "projects.search_knowledge",
    "projects.get_source_chunks",
    "projects.inspect_link",
    "projects.ingestion_status",
    "projects.list_resources",
    "projects.inspect_file_support",
    "projects.classify_intake",
    "projects.create_link_reference",
    "projects.create_note",
    "projects.prepare_source_upload",
    "projects.reindex_source",
    "workspace.create_project",
    "workspace.update_project_context",
    "workspace.set_project_status",
    "workspace.link_current_brand",
    "workspace.list_projects",
    "workspace.get_project_context",
    "workspace.search_project_content",
    "workspace.list_project_shares",
    "workspace.set_project_visibility",
    "workspace.share_project_with_people",
    "workspace.share_project_with_team",
    "brands.list",
    "brands.get_context",
    "brands.list_assets",
    "brands.create",
    "brands.update_identity",
    "brands.prepare_logo_upload",
    "brands.use_asset_as_logo",
    "brands.start_audit",
    "brands.audit_status",
    "artifacts.list",
    "artifacts.get",
    "artifacts.create_draft",
    "artifacts.update_draft",
    "artifacts.list_versions",
    "artifacts.finalize_to_project",
    "reports.list_project_reports",
    "reports.get_report_metrics",
    "reports.compare_report_to_plan",
})
PUBLIC_WRITE_TOOLS = frozenset({
    "media.start_studio_session",
    "media.generate_image",
    "account.update_profile",
    "account.update_agency",
    "account.invite_team_member",
    "credits.purchase_package",
    "google.link_resource_to_project",
    "projects.create_link_reference",
    "projects.create_note",
    "projects.prepare_source_upload",
    "projects.reindex_source",
    "workspace.create_project",
    "workspace.update_project_context",
    "workspace.set_project_status",
    "workspace.link_current_brand",
    "workspace.set_project_visibility",
    "workspace.share_project_with_people",
    "workspace.share_project_with_team",
    "brands.create",
    "brands.update_identity",
    "brands.prepare_logo_upload",
    "brands.use_asset_as_logo",
    "brands.start_audit",
    "artifacts.create_draft",
    "artifacts.update_draft",
    "artifacts.finalize_to_project",
})


@bp.get(f"{PUBLIC_MCP_PATH}/media/assets/<asset_id>/content")
def media_asset_content(asset_id):
    """Bearer-authenticated media delivery with tenant and creator checks."""
    try:
        principal = auth.authenticate({})
        auth.ensure_scope(principal, "media.get_job")
    except auth.PublicMcpAuthError:
        response = jsonify({"error": "Acesso não autorizado."})
        response.status_code = 401
        response.headers["WWW-Authenticate"] = 'Bearer realm="cadu-mcp-public"'
        return _headers(response)
    from ..creative_media.storage import read_path
    from ..db import get_db
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT a.storage_key, a.mime_type
                            FROM cx_media_assets a
                            JOIN cx_media_jobs j ON j.id=a.job_id
                            JOIN cx_clients brand ON brand.id=j.client_id
                           WHERE a.public_id=%s AND brand.crm_client_id=%s AND j.user_id=%s""",
                       (asset_id, principal.client_id, principal.user_id))
        asset = cursor.fetchone()
    if not asset:
        abort(404)
    path = read_path(asset["storage_key"])
    if path is None:
        abort(404)
    response = send_file(path, mimetype=asset["mime_type"], conditional=True, as_attachment=True,
                         download_name=path.name)
    response.headers["Cache-Control"] = "private, no-store"
    return _headers(response)


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


def _public_catalog(principal, exposure: str = "customer_agent") -> list[dict]:
    tools = load_builtin_tools().list(principal.context, exposure)
    for item in tools:
        if item["name"] in PUBLIC_TOOLS and (item["name"].startswith(("projects.", "artifacts.")) or
                                             item["name"] in {"media.start_studio_session", "media.generate_image"} or
                                             item["name"] in {"workspace.get_project_context", "workspace.search_project_content"}):
            item["inputSchema"] = deepcopy(item["inputSchema"])
            item["inputSchema"].setdefault("properties", {})["project_ref"] = {
                "type": "string", "description": "Projeto de destino no formato ci:ID; informe quando não houver projeto padrão."
            }
            if item["name"] in {"media.start_studio_session", "media.generate_image"}:
                item["inputSchema"]["properties"]["brand_ref"] = {
                    "type": "string", "description": "Marca ativa no formato studio:ID, quando não vier do projeto."
                }
        elif item["name"] in PUBLIC_TOOLS and item["name"].startswith("brands."):
            item["inputSchema"] = deepcopy(item["inputSchema"])
            item["inputSchema"].setdefault("properties", {})["brand_ref"] = {
                "type": "string", "description": "Marca ativa no formato studio:ID; use brand_id quando a ferramenta exigir."
            }
    return [item for item in tools
            if item["name"] in PUBLIC_TOOLS
            and (item["name"] != "credits.purchase_package" or auth.can_purchase_credits(principal))
            and (
                auth.required_scope(item["name"]) in principal.scopes or
                (auth.required_scope(item["name"]) == "projects:content_write" and "projects:write" in principal.scopes)
            )]


def _request_context_for_auth(params: dict) -> dict:
    value = dict(params or {})
    # A tools/call request nests the execution arguments, but context remains
    # at params level so the public schema is compatible with MCP hosts.
    if not value.get("project_ref") and isinstance(value.get("arguments"), dict):
        value["project_ref"] = value["arguments"].get("project_ref")
    if not value.get("brand_ref") and isinstance(value.get("arguments"), dict):
        value["brand_ref"] = value["arguments"].get("brand_ref")
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
                "serverInfo": {"name": "cadu-public-mcp", "title": "Cadu", "version": "1.0.0",
                               "description": "Projetos, marcas e documentos da sua conta Cadu.",
                               "icons": [{"src": product_url("workspace", MCP_ICON_PATH),
                                          "mimeType": "image/svg+xml", "sizes": ["any"]}]},
                "instructions": (
                    "Use project_ref no nível params ou configure um projeto padrão na chave. "
                    "Para adicionar texto ao projeto, use projects.create_note; para links, projects.create_link_reference. "
                    "Para consultar a base RAG de um projeto, use projects.search_knowledge e depois "
                    "projects.get_source_chunks com o source_id retornado; cite nome da fonte e chunk_id. "
                    "Para arquivos, imagens geradas e HTML, use projects.prepare_source_upload sem use_as_knowledge "
                    "e envie o binário ao upload_url com upload_token e project_ref; inclua description factual para imagens sem texto. "
                    "O Cadu classificará, indexará o conteúdo pesquisável e preservará o restante como ativo. "
                    "projects.list_resources inclui metadata.icon para links do projeto; status ready indica URL de ícone utilizável. "
                    "Para gerações do Cadu Media, use media.list_jobs e media.get_job. O download_url dos ativos "
                    "aceita a mesma chave Bearer do MCP no cabeçalho Authorization, respeitando conta, usuário e escopo resources:read. "
                    "Para a marca atual, liste a biblioteca com brands.list_assets; troque o site com "
                    "brands.update_identity(changes.website_url), ou defina um asset aprovado como logo com "
                    "brands.use_asset_as_logo. Em brands.start_audit escolha analysis_mode complete ou deep e, "
                    "se desejar, informe existing_asset_ids da mesma biblioteca. "
                    "Para créditos, credits.purchase_package apenas cria um pedido pendente; mostre confirmation_url "
                    "ao administrador e aguarde a confirmação autenticada no Cadu."
                ),
            }
        elif method == "tools/list":
            result = {"tools": _public_catalog(principal)}
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
            if name.startswith(("projects.", "artifacts.")) or name in {"workspace.get_project_context", "workspace.search_project_content", "media.start_studio_session", "media.generate_image"}:
                arguments.pop("project_ref", None)
            if name in {"media.start_studio_session", "media.generate_image"}:
                arguments.pop("brand_ref", None)
            if name.startswith("brands."):
                arguments.pop("brand_ref", None)
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
                if name in {"projects.prepare_source_upload", "brands.prepare_logo_upload"} and isinstance(value, dict):
                    value = {**value, "upload_url": product_url(
                        "workspace", f"{PUBLIC_MCP_PATH}/{'uploads' if name.startswith('projects.') else 'brand-uploads'}")}
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


def _multipart_principal(tool_name: str):
    try:
        principal = auth.authenticate(request.form.to_dict())
        auth.ensure_scope(principal, tool_name)
    except auth.PublicMcpAuthError as exc:
        return None, (jsonify(error=str(exc)), 401)
    return principal, None


@bp.post(f"{PUBLIC_MCP_PATH}/uploads")
def public_upload_project_source():
    from ..cadu_workspace import project_source_service

    principal, error = _multipart_principal("projects.prepare_source_upload")
    if error:
        return error
    context = principal.context
    if not context.project_ref or not repository.project_user_can_view(context.client_id, context.project_ref, context.user_id):
        return jsonify(error="Projeto indisponível para esta chave."), 403
    actor = repository.actor(context.user_id) or {}
    admin = int(actor.get("organization_id") or 0) == context.client_id and repository.account_role(actor) == "admin"
    roles = {item.get("role") for item in repository.project_access(context.client_id, context.project_ref)
             if int(item.get("user_id") or 0) == context.user_id}
    if not admin and not roles.intersection({"owner", "admin", "editor"}):
        return jsonify(error="Você não pode alterar este projeto."), 403
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify(error="Envie o arquivo no campo file."), 400
    try:
        value = project_source_service.save_upload(context, request.form.get("upload_token", ""), uploaded)
    except HTTPException as exc:
        return jsonify(error=exc.description), exc.code
    return jsonify(source=value), 201


@bp.post(f"{PUBLIC_MCP_PATH}/brand-uploads")
def public_upload_brand_logo():
    from ..cadu_workspace import brand_mcp_service

    principal, error = _multipart_principal("brands.prepare_logo_upload")
    if error:
        return error
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify(error="Envie o logo no campo file."), 400
    try:
        value = brand_mcp_service.save_logo_upload(principal.context, request.form.get("upload_token", ""), uploaded)
    except HTTPException as exc:
        return jsonify(error=exc.description), exc.code
    return jsonify(logo=value), 201


@bp.get("/.well-known/cadu-mcp-public")
def public_metadata():
    """Stable bootstrap metadata while OAuth 2.1 is being added."""
    return jsonify({
        "name": "cadu-public-mcp",
        "version": "1.0.0",
        "endpoint": product_url("workspace", PUBLIC_MCP_PATH),
        "icon_url": product_url("workspace", MCP_ICON_PATH),
        "icons": [{"src": product_url("workspace", MCP_ICON_PATH),
                   "mimeType": "image/svg+xml", "sizes": ["any"]}],
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
        mcp_ready=auth._available(),
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
    if str(data.get("scope_brand_write") or "").lower() in {"1", "true", "on", "yes"}:
        requested_scopes = list(requested_scopes) + ["brands:write"]
    if str(data.get("scope_artifact_write") or "").lower() in {"1", "true", "on", "yes"}:
        requested_scopes = list(requested_scopes) + ["artifacts:write"]
    if str(data.get("scope_account_write") or "").lower() in {"1", "true", "on", "yes"}:
        requested_scopes = list(requested_scopes) + ["account:write"]
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


@bp.route("/workspace/app/integracoes/agents/compras/<int:purchase_id>", methods=["GET", "POST"])
@login_required
def confirm_agent_purchase(purchase_id):
    from ..cadu_workspace.credit_purchase_service import pending_extra, purchase_extra

    session.setdefault("family_csrf", secrets.token_urlsafe(32))
    client_id, user_id = _session_scope()
    context = RequestContext(organization_id=client_id, client_id=client_id, user_id=user_id,
                             conversation_id=None, surface="workspace", project_ref=None,
                             capabilities=("workspace",))
    try:
        purchase = pending_extra(context, purchase_id)
    except HTTPException as exc:
        abort(exc.code, description=exc.description)
    result = None
    if request.method == "POST":
        if not _workspace_api_csrf():
            abort(403, description="Atualize a página e tente novamente.")
        if purchase["status"] != "pending":
            abort(409, description="Este pedido já foi processado.")
        try:
            result = purchase_extra(context, purchase["package_name"], purchase["billing_mode"],
                                    purchase.get("note") or "", pending_request_id=purchase_id)
        except HTTPException as exc:
            abort(exc.code, description=exc.description)
        purchase["status"] = "approved"
    return render_template("cadu_workspace/mcp_credit_approval.html", purchase=purchase, result=result)
