"""Separate public MCP transport and the Workspace management screen."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from dataclasses import replace
from copy import deepcopy
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException

from ..auth import login_required
from ..cadu_family import repository
from ..cadu_tool_billing import InsufficientToolCredits
from ..cadu_workspace.agent_v2.contracts import RequestContext
from ..cadu_workspace.mcp.registry import ToolError, load_builtin_tools
from ..product_domains import product_url
from . import auth, oauth, usage
from ..cadu_workspace.mcp import context_runtime


bp = Blueprint("cadu_public_mcp", __name__)
PUBLIC_MCP_PATH = "/mcp/cadu/v1"
MCP_ICON_PATH = "/static/images/cadu/products/cadu-mcp-icon.svg"
MCP_PUBLIC_ICON_PATH = f"{PUBLIC_MCP_PATH}/icon.png"
MCP_FAVICON_PATH = f"{PUBLIC_MCP_PATH}/favicon.ico"
MCP_ASSET_DIR = Path(__file__).resolve().parents[1] / "static/images/cadu/products"
PROTOCOL_VERSION = "2026-07-28"


def _oauth_resource() -> str:
    return product_url("workspace", PUBLIC_MCP_PATH)


def _oauth_url(path: str) -> str:
    return product_url("workspace", path)


def _oauth_issuer() -> str:
    return _oauth_url("").rstrip("/")


def _mcp_icons() -> list[dict]:
    return [
        {"src": product_url("workspace", MCP_PUBLIC_ICON_PATH),
         "mimeType": "image/png", "sizes": ["512x512"]},
        {"src": product_url("workspace", MCP_ICON_PATH),
         "mimeType": "image/svg+xml", "sizes": ["any"]},
    ]


def _oauth_json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _oauth_error(exc: oauth.OAuthError):
    response = _oauth_json({"error": exc.error, "error_description": exc.description}, exc.status)
    if exc.status == 429:
        response.headers["Retry-After"] = "3600"
    return response


def _redirect_with_query(uri: str, **values) -> str:
    parsed = urlsplit(uri)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({key: value for key, value in values.items() if value is not None})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))

# The public surface is an intentional subset of internal capabilities. New
# internal tools do not become internet-facing by accident.
PUBLIC_TOOLS = frozenset({
    "intent.interpret",
    "intent.execute",
    "context.open",
    "context.get",
    "context.update",
    "context.close",
    "operations.get",
    "media.list_jobs",
    "media.get_job",
    "media.start_studio_session",
    "media.generate_image",
    "media.edit_image",
    "media.plan_video",
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
    "resources.inspect_input",
    "resources.add",
    "resources.get",
    "resources.capabilities",
    "resources.start_image_edit",
    "resources.create_editable_copy",
    "resources.list_versions",
    "resources.list_relations",
    "resources.relate",
    "resources.update_metadata",
    "resources.set_archived",
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
    "projects.list_tasks",
    "projects.create_task",
    "projects.create_tasks",
    "projects.create_initial_task_list",
    "projects.update_task",
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
    "brands.inspect_site",
    "brands.list_assets",
    "brands.create",
    "brands.update_identity",
    "brands.prepare_logo_upload",
    "brands.prepare_asset_upload",
    "brands.use_asset_as_logo",
    "brands.delete_asset",
    "brands.start_audit",
    "brands.audit_status",
    "artifacts.list",
    "artifacts.describe_types",
    "artifacts.get",
    "artifacts.create_draft",
    "artifacts.update_draft",
    "artifacts.list_versions",
    "artifacts.get_version",
    "artifacts.restore_version",
    "artifacts.finalize_to_project",
    "artifacts.move_project",
    "reports.list_project_reports",
    "reports.get_report_metrics",
    "reports.compare_report_to_plan",
})
PUBLIC_WRITE_TOOLS = frozenset({
    "intent.execute",
    "context.update",
    "context.close",
    "media.start_studio_session",
    "media.generate_image",
    "media.edit_image",
    "media.plan_video",
    "account.update_profile",
    "account.update_agency",
    "account.invite_team_member",
    "credits.purchase_package",
    "google.link_resource_to_project",
    "resources.add",
    "resources.start_image_edit",
    "resources.create_editable_copy",
    "resources.relate",
    "resources.update_metadata",
    "resources.set_archived",
    "projects.create_link_reference",
    "projects.create_note",
    "projects.prepare_source_upload",
    "projects.reindex_source",
    "projects.create_task",
    "projects.create_tasks",
    "projects.create_initial_task_list",
    "projects.update_task",
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
    "brands.prepare_asset_upload",
    "brands.use_asset_as_logo",
    "brands.delete_asset",
    "brands.start_audit",
    "artifacts.create_draft",
    "artifacts.update_draft",
    "artifacts.restore_version",
    "artifacts.finalize_to_project",
    "artifacts.move_project",
})

# Only these tools persist their result in cadu_mcp_operations. Other writes
# still receive an execution receipt, but must not promise generic recovery.
RECOVERABLE_OPERATION_TOOLS = frozenset({
    "intent.execute",
    "media.generate_image",
    "media.edit_image",
    "media.plan_video",
    "account.update_profile",
    "account.update_agency",
    "account.invite_team_member",
    "credits.purchase_package",
    "google.link_resource_to_project",
    "resources.create_editable_copy",
    "resources.start_image_edit",
    "resources.relate",
    "resources.update_metadata",
    "resources.set_archived",
    "projects.create_link_reference",
    "projects.prepare_source_upload",
    "projects.reindex_source",
    "projects.create_note",
    "projects.create_task",
    "projects.create_tasks",
    "projects.create_initial_task_list",
    "projects.update_task",
    "workspace.create_project",
    "workspace.update_project_context",
    "workspace.set_project_status",
    "workspace.link_current_brand",
    "workspace.set_project_visibility",
    "workspace.share_project_with_people",
    "workspace.share_project_with_team",
    "brands.use_asset_as_logo",
    "artifacts.create_draft",
    "artifacts.update_draft",
    "artifacts.restore_version",
    "artifacts.finalize_to_project",
    "artifacts.move_project",
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
        response.headers["WWW-Authenticate"] = (
            f'Bearer realm="cadu-mcp-public", resource_metadata="{_oauth_url("/.well-known/oauth-protected-resource/mcp/cadu/v1")}"'
        )
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
    if not context_runtime.available():
        tools = [item for item in tools if not item["name"].startswith("context.")]
    for item in tools:
        if item["name"] in PUBLIC_TOOLS and (item["name"].startswith(("projects.", "artifacts.", "resources.")) or
                                             item["name"] in {"media.start_studio_session", "media.generate_image", "media.edit_image", "media.plan_video"} or
                                             item["name"] in {"workspace.get_project_context", "workspace.search_project_content"}):
            item["inputSchema"] = deepcopy(item["inputSchema"])
            item["inputSchema"].setdefault("properties", {})["project_ref"] = {
                "type": "string", "description": "Projeto de destino no formato ci:ID; informe quando não houver projeto padrão."
            }
            if item["name"] in {"media.start_studio_session", "media.generate_image", "media.edit_image", "media.plan_video"}:
                item["inputSchema"]["properties"]["brand_ref"] = {
                    "type": "string", "description": "Marca ativa no formato studio:ID, quando não vier do projeto."
                }
        elif item["name"] in PUBLIC_TOOLS and item["name"].startswith("brands."):
            item["inputSchema"] = deepcopy(item["inputSchema"])
            item["inputSchema"].setdefault("properties", {})["brand_ref"] = {
                "type": "string", "description": "Marca ativa no formato studio:ID; use brand_id quando a ferramenta exigir."
            }
        if item["name"] in PUBLIC_TOOLS:
            security = [{"type": "oauth2", "scopes": [auth.required_scope(item["name"])]}]
            item["securitySchemes"] = security
            item.setdefault("_meta", {})["securitySchemes"] = security
    return [item for item in tools
            if item["name"] in PUBLIC_TOOLS
            and (item["name"] != "credits.purchase_package" or auth.can_purchase_credits(principal))
            and (
                auth.has_scope(principal, auth.required_scope(item["name"]))
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


@bp.get(MCP_PUBLIC_ICON_PATH)
def public_mcp_icon():
    return send_file(MCP_ASSET_DIR / "cadu-mcp-512.png",
                     mimetype="image/png", max_age=86400)


@bp.get(MCP_FAVICON_PATH)
def public_mcp_favicon():
    return send_file(MCP_ASSET_DIR / "cadu-mcp-favicon.ico",
                     mimetype="image/x-icon", max_age=86400)


@bp.get(PUBLIC_MCP_PATH)
def public_mcp_landing():
    # MCP clients may probe GET for an event stream. This stateless transport
    # uses POST; browser visitors get a branded explanation instead of a 405.
    if "text/html" not in request.headers.get("Accept", ""):
        return _headers(jsonify({"error": "Use POST para chamadas MCP."})), 405
    return render_template("cadu_workspace/mcp_public_landing.html", endpoint=_oauth_resource())


@bp.post(PUBLIC_MCP_PATH)
def public_rpc():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return _headers(jsonify(_error(None, -32600, "Requisição JSON-RPC inválida."))), 400
    request_id, method = payload.get("id"), payload.get("method")
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return _headers(jsonify(_error(request_id, -32602, "Parâmetros inválidos."))), 400
    protocol = request.headers.get("MCP-Protocol-Version", "")
    if protocol.startswith("2026-"):
        if request.headers.get("Mcp-Method") != method:
            return _headers(jsonify(_error(request_id, -32600, "O header Mcp-Method não corresponde ao corpo."))), 400
        if method == "tools/call" and request.headers.get("Mcp-Name") != params.get("name"):
            return _headers(jsonify(_error(request_id, -32600, "O header Mcp-Name não corresponde ao corpo."))), 400
    try:
        principal = auth.authenticate(_request_context_for_auth(params))
    except auth.PublicMcpAuthError as exc:
        challenge = (
            f'Bearer realm="cadu-mcp-public", error="invalid_token", '
            f'resource_metadata="{_oauth_url("/.well-known/oauth-protected-resource/mcp/cadu/v1")}"'
        )
        response = jsonify(_error(request_id, -32001, str(exc), {
            "_meta": {"mcp/www_authenticate": [challenge]},
        }))
        response.status_code = 401
        response.headers["WWW-Authenticate"] = challenge
        response.headers["X-Cadu-MCP-Auth"] = "oauth2, api-key-legacy"
        return _headers(response)

    try:
        registry = load_builtin_tools()
        current = principal.context
        if method in {"initialize", "server/discover"}:
            result = {
                "protocolVersion": params.get("protocolVersion") if isinstance(params.get("protocolVersion"), str) else PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cadu", "title": "Cadu", "version": "1.0.0",
                               "description": "Projetos, marcas e documentos da sua conta Cadu.",
                               "icons": _mcp_icons()},
                "instructions": (
                    "O Cadu entende pedidos naturais em português do Brasil. Use intent.interpret para frases como "
                    "'joga isso no projeto', 'faz um documento disso' ou 'não salva ainda'. Quando 'isso' se referir "
                    "a conteúdo criado pelo host, envie source.content ou uma referência Cadu explícita. "
                    "Use intent.execute com confirmed=true e request_id único para criar ou salvar o documento de forma idempotente. "
                    "Para preservar projeto, marca, artefatos e operações entre chamadas, use context.open e "
                    "reenvie o context_handle retornado nas ferramentas seguintes. "
                    "Use project_ref no nível params ou configure um projeto padrão na chave. "
                    "O projeto é um inventário multiplataforma, não apenas uma base de conhecimento. "
                    "Prefira resources.add como entrada única: mode=editable, external_link ou file_upload. "
                    "Para uma entrega editável — inclusive uma página HTML — use artifacts.create_draft com type=html, document, research ou outro tipo suportado. "
                    "Para texto que deve virar fonte pesquisável, use projects.create_note. Para um recurso mantido em outra plataforma, "
                    "use projects.create_link_reference e informe resource_kind, platform, external_id, description e tags quando disponíveis. "
                    "Inclua user_message com a mensagem final e factual da pessoa para que o Cadu gere contexto e timeline; "
                    "não envie raciocínio interno, prompts de sistema ou instruções ocultas do agente. "
                    "Uma referência pertence ao projeto e pode virar activity, task ou decision no campo project_item_kind; "
                    "atalhos da dock são preferências separadas e nunca substituem a referência do projeto. "
                    "Para acompanhamento dentro do Cadu use projects.list_tasks, projects.create_task, projects.create_tasks, projects.create_initial_task_list e projects.update_task; "
                    "tarefas de plataformas externas devem preservar provider, URL e identificador, sem prometer sincronização quando não houver conector. "
                    "Quando receber um convite colado do Meet, Teams ou Zoom, envie o bloco a projects.classify_intake(text) e preserve "
                    "o objeto meeting retornado em projects.create_link_reference. "
                    "Antes de oferecer edição, consulte resources.capabilities: PDF e referências sem conexão são somente leitura; "
                    "para derivar uma entrega use resources.create_editable_copy, que preserva e relaciona a origem; "
                    "para imagens use resources.start_image_edit, que prepara uma cópia no Studio sem alterar o original. "
                    "Para pesquisar o projeto inteiro, incluindo direção, metadados, biblioteca, atividades, tarefas, links e fontes, "
                    "use workspace.search_project_content; confira evidence_level, unavailable_scopes e resource_index_pending. "
                    "Metadados de links não comprovam o conteúdo do destino. Para aprofundar trechos de arquivos indexados, "
                    "use projects.search_knowledge e depois projects.get_source_chunks com o source_id retornado; cite nome da fonte e chunk_id. "
                    "Para arquivos já existentes, imagens geradas e HTML binário, use projects.prepare_source_upload sem use_as_knowledge "
                    "e envie o binário ao upload_url com upload_token e project_ref; inclua description factual para imagens sem texto. "
                    "O Cadu classificará, indexará o conteúdo pesquisável e preservará o restante como ativo. "
                    "projects.list_resources inclui metadata.icon para links do projeto; status ready indica URL de ícone utilizável. "
                    "Para gerações do Cadu Media, use media.list_jobs e media.get_job. O download_url dos ativos "
                    "aceita a mesma chave Bearer do MCP no cabeçalho Authorization, respeitando conta, usuário e escopo resources:read. "
                    "Para a marca atual, liste a biblioteca com brands.list_assets; troque o site com "
                    "brands.update_identity(changes.website_url), ou defina um asset aprovado como logo com "
                    "brands.use_asset_as_logo. Em brands.start_audit escolha analysis_mode complete ou deep e, "
                    "se desejar, informe existing_asset_ids da mesma biblioteca. A auditoria pertence à marca, não ao projeto: "
                    "brand_id ou brand_ref identifica o alvo e tem prioridade mesmo quando project_ref aponta para outro projeto; "
                    "não use context.update nem altere o vínculo do projeto para executar a auditoria. "
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
            if name.startswith(("projects.", "artifacts.", "resources.")) or name in {"workspace.get_project_context", "workspace.search_project_content", "media.start_studio_session", "media.generate_image", "media.edit_image", "media.plan_video"}:
                arguments.pop("project_ref", None)
            if name in {"media.start_studio_session", "media.generate_image", "media.edit_image", "media.plan_video"}:
                arguments.pop("brand_ref", None)
            if name.startswith("brands."):
                arguments.pop("brand_ref", None)
            if name in PUBLIC_WRITE_TOOLS and "request_id" not in arguments:
                # JSON-RPC ids may be numbers or arbitrary strings. Command
                # idempotency uses a separate UUID that remains portable.
                arguments["request_id"] = usage.new_request_id()
            tool_request_id = usage.new_request_id(arguments.get("request_id") or request_id)
            started_at = monotonic()
            credit_cost = usage.tool_cost(name)
            usage.authorize_credits(client_id=principal.client_id, user_id=principal.user_id, tool_name=name)
            usage.record(
                key_id=principal.key_id, credential_type=principal.credential_type,
                client_id=principal.client_id, user_id=principal.user_id,
                client_type=principal.client_type, method=method, tool_name=name,
                request_id=tool_request_id, status="started", credit_cost=credit_cost,
                started_at=started_at, input_bytes=len(request.get_data(cache=True) or b""),
            )
            try:
                value = context_runtime.execute(principal, name, arguments, "customer_agent", registry)
                reported_cost = usage.reported_tokens(value)
                if name == "brands.create" and isinstance(value, dict):
                    nested = value.get("uploads") if isinstance(value.get("uploads"), dict) else {}
                    value = {**value, "uploads": {
                        key: {**item, "upload_url": product_url("workspace", f"{PUBLIC_MCP_PATH}/brand-uploads")}
                        for key, item in nested.items() if isinstance(item, dict)
                    }}
                if name in {"projects.prepare_source_upload", "resources.add", "brands.prepare_logo_upload", "brands.prepare_asset_upload"} and isinstance(value, dict) and value.get("upload_url"):
                    value = {**value, "upload_url": product_url(
                        "workspace", f"{PUBLIC_MCP_PATH}/{'brand-uploads' if name.startswith('brands.') else 'uploads'}")}
                usage.charge_credits(
                    client_id=principal.client_id, user_id=principal.user_id,
                    tool_name=name, idempotency_key=f"{principal.key_id}:{tool_request_id}",
                    charged_tokens=reported_cost if reported_cost > 0 else None,
                    metadata={"client_type": principal.client_type},
                )
                encoded = json.dumps(value, ensure_ascii=False, default=str)
                if name in PUBLIC_WRITE_TOOLS and isinstance(value, dict):
                    value = dict(value)
                    value["_receipt"] = {
                        "operation_id": tool_request_id,
                        "tool": name,
                        "status": "completed",
                    }
                    if name in RECOVERABLE_OPERATION_TOOLS:
                        value["_receipt"]["recover_with"] = "operations.get"
                    encoded = json.dumps(value, ensure_ascii=False, default=str)
                usage.record(
                    key_id=principal.key_id, credential_type=principal.credential_type,
                    client_id=principal.client_id, user_id=principal.user_id,
                    client_type=principal.client_type, method=method, tool_name=name,
                    request_id=tool_request_id, status="completed",
                    credit_cost=reported_cost or credit_cost,
                    started_at=started_at, output_bytes=len(encoded.encode("utf-8")),
                )
                result = {"content": [{"type": "text", "text": encoded}], "structuredContent": value, "isError": False}
            except Exception as exc:
                usage.record(
                    key_id=principal.key_id, credential_type=principal.credential_type,
                    client_id=principal.client_id, user_id=principal.user_id,
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
        credits_url = product_url("workspace", "/creditos")
        message = f"{exc} Para continuar, adicione créditos em {credits_url}"
        return _headers(jsonify(_error(request_id, -32020, message, {
            "code": "credits_insufficient", "credits_url": credits_url,
        }))), 402
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
        handle = str(request.form.get("context_handle") or "")
        if handle:
            principal = replace(
                principal,
                context=context_runtime.resolve_context(principal, handle, "customer_agent"),
            )
    except auth.PublicMcpAuthError as exc:
        return None, (jsonify(error=str(exc)), 401)
    except ToolError as exc:
        return None, (jsonify(error=str(exc)), 400)
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
    return jsonify(logo=value, asset=value), 201


@bp.get("/.well-known/oauth-protected-resource")
@bp.get("/.well-known/oauth-protected-resource/mcp/cadu/v1")
def oauth_protected_resource_metadata():
    return _oauth_json({
        "resource": _oauth_resource(),
        "authorization_servers": [_oauth_issuer()],
        "scopes_supported": list(auth.CLIENT_SCOPES),
        "resource_documentation": _oauth_url("/workspace/app/integracoes/agents"),
        "bearer_methods_supported": ["header"],
    })


@bp.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata():
    return _oauth_json({
        "issuer": _oauth_issuer(),
        "authorization_endpoint": _oauth_url("/oauth/authorize"),
        "token_endpoint": _oauth_url("/oauth/token"),
        "registration_endpoint": _oauth_url("/oauth/register"),
        "revocation_endpoint": _oauth_url("/oauth/revoke"),
        "scopes_supported": list(auth.CLIENT_SCOPES),
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "authorization_response_iss_parameter_supported": True,
    })


@bp.post("/oauth/register")
def oauth_register_client():
    try:
        registration_ip = request.remote_addr or None
        return _oauth_json(oauth.register_client(request.get_json(silent=True) or {},
                                                 registration_ip=registration_ip), 201)
    except oauth.OAuthError as exc:
        return _oauth_error(exc)


@bp.route("/oauth/authorize", methods=["GET", "POST"])
@login_required
def oauth_authorize():
    session.setdefault("family_csrf", secrets.token_urlsafe(32))
    values = request.values
    try:
        authorization = oauth.validate_authorization_request(values)
        if authorization["resource"] != _oauth_resource():
            raise oauth.OAuthError("invalid_target", "O resource solicitado não pertence ao MCP público do Cadu.")
    except oauth.OAuthError as exc:
        return render_template("cadu_workspace/mcp_oauth_error.html", error=exc), exc.status

    if request.method == "POST":
        if not _workspace_api_csrf():
            abort(403, description="Atualize a página e tente novamente.")
        if request.form.get("decision") != "authorize":
            return redirect(_redirect_with_query(authorization["redirect_uri"],
                                                  error="access_denied", state=authorization["state"],
                                                  iss=_oauth_issuer()))
        approved = [scope for scope in authorization["scopes"]
                    if request.form.get(f"scope:{scope}") == "on"]
        if not approved:
            return render_template("cadu_workspace/mcp_oauth_consent.html", authorization=authorization,
                                   projects=[], csrf=session["family_csrf"],
                                   error="Selecione ao menos uma permissão."), 400
        client_id, user_id = _session_scope()
        actor = repository.actor(user_id) or {}
        if "account:write" in approved and (
            int(actor.get("organization_id") or 0) != client_id
            or repository.account_role(actor) != "admin"
        ):
            approved.remove("account:write")
        if not approved:
            client_id, _ = _session_scope()
            projects = [item for item in repository.entities(client_id) if item.get("kind") == "project"]
            return render_template("cadu_workspace/mcp_oauth_consent.html", authorization=authorization,
                                   projects=projects, csrf=session["family_csrf"],
                                   error="Sua função não permite as permissões selecionadas."), 403
        default_project_ref = request.form.get("default_project_ref") or None
        if default_project_ref:
            projects = {item["ref"] for item in repository.entities(client_id) if item.get("kind") == "project"}
            if default_project_ref not in projects:
                abort(400, description="O projeto selecionado não pertence a esta conta.")
        code = oauth.create_authorization_code(
            authorization=authorization, client_id=client_id, user_id=user_id,
            scopes=approved, default_project_ref=default_project_ref,
        )
        return redirect(_redirect_with_query(authorization["redirect_uri"], code=code,
                                              state=authorization["state"], iss=_oauth_issuer()))

    client_id, _ = _session_scope()
    projects = [item for item in repository.entities(client_id) if item.get("kind") == "project"]
    return render_template("cadu_workspace/mcp_oauth_consent.html", authorization=authorization,
                           projects=projects, csrf=session["family_csrf"], error=None)


@bp.post("/oauth/token")
def oauth_token():
    grant_type = str(request.form.get("grant_type") or "")
    try:
        if grant_type == "authorization_code":
            tokens = oauth.exchange_code(
                code=str(request.form.get("code") or ""),
                client_id=str(request.form.get("client_id") or ""),
                redirect_uri=str(request.form.get("redirect_uri") or ""),
                code_verifier=str(request.form.get("code_verifier") or ""),
                resource=str(request.form.get("resource") or ""),
            )
        elif grant_type == "refresh_token":
            tokens = oauth.refresh_tokens(
                refresh_token=str(request.form.get("refresh_token") or ""),
                client_id=str(request.form.get("client_id") or ""),
                resource=str(request.form.get("resource") or ""),
            )
        else:
            raise oauth.OAuthError("unsupported_grant_type", "grant_type não suportado.")
        return _oauth_json(tokens)
    except oauth.OAuthError as exc:
        return _oauth_error(exc)


@bp.post("/oauth/revoke")
def oauth_revoke():
    try:
        oauth.revoke_token(str(request.form.get("token") or ""))
    except Exception:
        current_app.logger.exception("Falha operacional ao revogar token OAuth do MCP")
        return _oauth_json({"error": "temporarily_unavailable",
                            "error_description": "Não foi possível concluir a revogação."}, 503)
    return _oauth_json({})


@bp.get("/.well-known/cadu-mcp-public")
def public_metadata():
    """Stable bootstrap metadata for MCP clients and the Workspace UI."""
    return jsonify({
        "name": "cadu",
        "version": "1.0.0",
        "endpoint": product_url("workspace", PUBLIC_MCP_PATH),
        "icon_url": product_url("workspace", MCP_PUBLIC_ICON_PATH),
        "favicon_url": product_url("workspace", MCP_FAVICON_PATH),
        "icons": _mcp_icons(),
        "title": "Cadu",
        "description": "Projetos, marcas, documentos e mídia da sua conta Cadu.",
        "authentication": {"type": "oauth2", "legacy_api_key_supported": auth._available()},
        "oauth": {
            "status": "ready" if oauth.available() else "pending_migration",
            "protected_resource_metadata": _oauth_url("/.well-known/oauth-protected-resource/mcp/cadu/v1"),
            "authorization_server_metadata": _oauth_url("/.well-known/oauth-authorization-server"),
            "pkce_methods": ["S256"],
        },
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
    grants = oauth.list_grants(client_id=client_id, user_id=user_id)
    return render_template(
        "cadu_workspace/mcp_agents.html",
        keys=auth.list_keys(client_id=client_id, user_id=user_id),
        grants=grants,
        projects=projects,
        usage=usage.summary(client_id=client_id, user_id=user_id),
        credit=credit,
        endpoint=product_url("workspace", PUBLIC_MCP_PATH),
        metadata_url=product_url("workspace", "/.well-known/cadu-mcp-public"),
        client_types=auth.CLIENT_TYPES,
        mcp_ready=auth._available(),
        oauth_ready=oauth.available(),
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


@bp.post("/workspace/app/integracoes/agents/grants/<grant_id>/revoke")
@login_required
def revoke_agent_grant(grant_id):
    if not _workspace_api_csrf():
        abort(403, description="Atualize a página e tente novamente.")
    client_id, user_id = _session_scope()
    try:
        changed = oauth.revoke_grant(grant_id=grant_id, client_id=client_id, user_id=user_id)
    except oauth.OAuthError as exc:
        return jsonify({"success": False, "error": exc.description}), exc.status
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
