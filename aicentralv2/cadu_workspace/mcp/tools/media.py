"""Cadu Media metadata for external agents, with bearer-authenticated downloads."""

import hashlib
import json
from flask import current_app

from ...agent_v2.contracts import RequestContext
from ....db import get_db
from ....product_domains import product_url
from .. import operations
from ..registry import ToolForbidden, ToolInputError, register_tool
from urllib.parse import urlencode


_CREATION_CONTRACTS = {
    "image": {"required": ["request_id", "confirmed", "confirmed_cost", "prompt"],
              "optional": ["brand_id", "aspect_ratio", "quality"],
              "review": "O diretor prepara uma direção; o MCP gera após confirmação explícita e a sessão permite revisão posterior.",
              "prompt_pipeline": ["studio_prompt.optimize_prompt", "studio_create.create", "studio_create.create_image"]},
    "ad": {"required": ["request_id", "confirmed", "confirmed_cost", "prompt", "brand_id"],
           "optional": ["aspect_ratio", "quality"],
           "review": "Anúncio exige marca validada; o diretor prepara uma direção antes da geração confirmada.",
           "prompt_pipeline": ["studio_prompt.optimize_prompt", "studio_create.create", "studio_create.create_image"]},
    "image_edit": {"required": ["request_id", "confirmed", "confirmed_cost", "prompt", "source_url"],
                   "optional": ["brand_id", "aspect_ratio", "quality"],
                   "review": "Editar preserva a imagem base fora da alteração solicitada.",
                   "prompt_pipeline": ["studio_prompt.optimize_prompt", "studio_create.create", "studio_create.create_image"]},
    "video": {"required": ["request_id", "confirmed_cost", "kind=video", "prompt"],
              "optional": ["brand_id", "source_id", "duration"],
              "source_rule": "Para gerar, selecione no Studio uma imagem da biblioteca ou duas ou mais cenas.",
              "review": "Roteiro e plano de vídeo são revisados antes do job assíncrono.",
              "prompt_pipeline": ["studio_agent.plan_request", "Video Studio review", "AnimateService.submit"]},
    "video_edit": {"required": ["request_id", "confirmed_cost", "kind=video_edit", "prompt"],
                   "one_of": ["source_id", "source_url"], "optional": ["brand_id", "duration"],
                   "review": "A edição considera o vídeo base, suas cenas e áudio; não recria livremente o filme.",
                   "prompt_pipeline": ["studio_agent.plan_request", "Video Studio review", "Studio export"]},
}


@register_tool(
    name="media.creation_capabilities", capability="workspace", effect="read",
    description="Descreve payload mínimo e pipeline criativo suportado para criar ou editar imagem, anúncio e vídeo no Cadu Studio.",
    exposures=("internal", "customer_agent"),
)
def creation_capabilities(context: RequestContext, arguments: dict) -> dict:
    return {"operations": _CREATION_CONTRACTS, "session_tool": "media.start_studio_session",
            "generation_available_via_mcp": ["image", "image_edit"],
            "generation_tools": {"image": "media.generate_image", "image_edit": "media.edit_image"},
            "video_plan_tool": "media.plan_video",
            "note": "Imagem pode ser criada ou editada pelo MCP. O vídeo tem plano otimizado no MCP, mas a geração exige selecionar uma imagem ou stills no Studio; não informe que a mídia foi criada antes do job concluir."}


@register_tool(
    name="media.generate_image", capability="workspace", effect="write",
    description="Gera uma imagem no Cadu Studio com cobrança real de créditos, resultado persistido e repetição idempotente. Exige confirmação explícita do custo.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "confirmed_cost", "prompt"],
                  "properties": {"request_id": {"type": "string", "minLength": 36, "maxLength": 36},
                                 "confirmed": {"type": "boolean", "enum": [True]},
                                 "confirmed_cost": {"type": "boolean", "enum": [True]},
                                 "prompt": {"type": "string", "minLength": 3, "maxLength": 4000},
                                 "brand_id": {"type": "integer", "minimum": 1},
                                 "aspect_ratio": {"type": "string", "enum": ["1:1", "4:5", "9:16", "16:9"]},
                                 "quality": {"type": "string", "enum": ["econômica", "padrão", "alta"]}},
                  "additionalProperties": False},
)
def generate_image(context: RequestContext, arguments: dict) -> dict:
    from ...brand_mcp_service import _brand, _current_brand_id
    from ...media_creation_service import generate_studio_image

    if context.project_ref:
        from ....cadu_family import repository as family_repository
        if not family_repository.project_user_can_view(context.client_id, context.project_ref, context.user_id):
            raise ToolForbidden("Você não tem acesso ao projeto selecionado.")
        actor = family_repository.actor(context.user_id) or {}
        admin = (int(actor.get("organization_id") or 0) == context.client_id
                 and family_repository.account_role(actor) == "admin")
        roles = {item.get("role") for item in family_repository.project_access(context.client_id, context.project_ref)
                 if int(item.get("user_id") or 0) == context.user_id}
        if not admin and not roles.intersection({"owner", "admin", "editor"}):
            raise ToolForbidden("Você não pode criar materiais neste projeto.")

    brand_id = arguments.get("brand_id")
    if brand_id is None:
        try:
            brand_id = _current_brand_id(context)
        except Exception:
            if context.brand_ref:
                raise
    if brand_id is not None:
        _brand(context, brand_id)
        arguments = {**arguments, "brand_id": brand_id}
    fingerprint = {key: arguments.get(key) for key in ("prompt", "brand_id", "aspect_ratio", "quality")}
    return operations.execute(arguments["request_id"], context, "media.generate_image", fingerprint,
                              lambda: generate_studio_image(context, arguments))


@register_tool(
    name="media.edit_image", capability="workspace", effect="write",
    description=("Edita uma imagem no Studio preservando a imagem base fora do pedido. "
                 "Usa otimização de prompt, diretor criativo e geração cobrada; retorna a imagem e o link da sessão."),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed", "confirmed_cost", "prompt", "source_url"],
                  "properties": {"request_id": {"type": "string", "minLength": 36, "maxLength": 36},
                                 "confirmed": {"type": "boolean", "enum": [True]},
                                 "confirmed_cost": {"type": "boolean", "enum": [True]},
                                 "prompt": {"type": "string", "minLength": 3, "maxLength": 4000},
                                 "source_url": {"type": "string", "minLength": 8, "maxLength": 2000},
                                 "brand_id": {"type": "integer", "minimum": 1},
                                 "aspect_ratio": {"type": "string", "enum": ["1:1", "4:5", "9:16", "16:9"]},
                                 "quality": {"type": "string", "enum": ["econômica", "padrão", "alta"]}},
                  "additionalProperties": False},
)
def edit_image(context: RequestContext, arguments: dict) -> dict:
    from ...brand_mcp_service import _brand, _current_brand_id
    from ...media_creation_service import generate_studio_image
    from ....cadu_family import repository as family_repository
    source = str(arguments["source_url"])
    if not (source.startswith("/static/uploads/creative_") or source.startswith("https://")):
        raise ToolInputError("Use uma imagem salva no Studio ou um URL HTTPS público.")
    if context.project_ref:
        if not family_repository.project_user_can_view(context.client_id, context.project_ref, context.user_id):
            raise ToolForbidden("Você não tem acesso ao projeto selecionado.")
        actor = family_repository.actor(context.user_id) or {}
        admin = (int(actor.get("organization_id") or 0) == context.client_id
                 and family_repository.account_role(actor) == "admin")
        roles = {item.get("role") for item in family_repository.project_access(context.client_id, context.project_ref)
                 if int(item.get("user_id") or 0) == context.user_id}
        if not admin and not roles.intersection({"owner", "admin", "editor"}):
            raise ToolForbidden("Você não pode editar materiais neste projeto.")
    brand_id = arguments.get("brand_id")
    if brand_id is None:
        try:
            brand_id = _current_brand_id(context)
        except Exception:
            if context.brand_ref:
                raise
    if brand_id is not None:
        _brand(context, brand_id)
        arguments = {**arguments, "brand_id": brand_id}
    fingerprint = {key: arguments.get(key) for key in ("prompt", "source_url", "brand_id", "aspect_ratio", "quality")}
    return operations.execute(arguments["request_id"], context, "media.edit_image", fingerprint,
                              lambda: generate_studio_image(context, arguments))


@register_tool(
    name="media.plan_video", capability="workspace", effect="write",
    description=("Interpreta um pedido de criação ou edição de vídeo com o prompt e a skill oficiais "
                 "do Video Studio, salva o plano numa sessão e retorna link para revisão. "
                 "Não submete job nem informa vídeo pronto."),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["request_id", "confirmed_cost", "kind", "prompt"],
                  "properties": {"request_id": {"type": "string", "minLength": 36, "maxLength": 36},
                                 "confirmed_cost": {"type": "boolean", "enum": [True]},
                                 "kind": {"type": "string", "enum": ["video", "video_edit"]},
                                 "prompt": {"type": "string", "minLength": 3, "maxLength": 2000},
                                 "brand_id": {"type": "integer", "minimum": 1},
                                 "source_id": {"type": "string", "maxLength": 180},
                                 "source_url": {"type": "string", "maxLength": 2000},
                                 "duration": {"type": "integer", "enum": [4, 5, 8, 10, 15, 20, 30]}},
                  "additionalProperties": False},
)
def plan_video(context: RequestContext, arguments: dict) -> dict:
    from ....cadu_credit_connector import CaduCreditConnector
    from ....creative_media.studio_agent import plan_request
    from ....creative_media.studio import _session_store
    from ....creative_modeling_service import CreativeModelingService
    from ....services.cadu_ai_connector import CaduAIConnector

    def run():
        session = start_studio_session(context, arguments)
        studio_client_id = (int(str(session["brand_ref"])[7:]) if session.get("brand_ref")
                            else int(CreativeModelingService().repository.resolve_client_id(context.client_id, "crm")))
        connector = CaduAIConnector(CaduCreditConnector())

        def metered_plan(messages, **options):
            return connector.complete(
                messages, client_id=context.client_id, user_id=context.user_id,
                idempotency_key=f"studio:mcp-video-plan:{arguments['request_id']}",
                app="Cadu Studio", stage="video_agent_plan", estimated_tokens=2400,
                metadata={"studio_client_id": studio_client_id,
                          "studio_session_id": session["session_id"], "billing_class": "agent"},
                **options)

        source_id = str(arguments.get("source_id") or "")
        plan = plan_request(arguments["prompt"], {
            "generation_mode": "single_image" if source_id and arguments["kind"] == "video" else "storyboard",
            "duration": arguments.get("duration") or 8,
            "selected_scene": {"id": source_id} if arguments["kind"] == "video" else {},
            "has_clip": arguments["kind"] == "video_edit",
            "clip": {"id": source_id} if arguments["kind"] == "video_edit" else {},
        }, text_callable=metered_plan)
        store = _session_store(studio_client_id)
        saved = store.read(studio_client_id, context.user_id, session["session_id"])
        store.save(studio_client_id, context.user_id, session["session_id"], {
            "expected_revision": saved["revision"], "status": "active",
            "metadata": {**(saved.get("metadata") or {}), "video_plan": plan},
        })
        return {**session, "plan": plan, "generation_status": "not_started",
                "required_next_step": "Revise o plano e selecione a imagem, as cenas ou o clipe no Video Studio antes de gerar."}

    fingerprint = {key: arguments.get(key) for key in ("kind", "prompt", "brand_id", "source_id", "source_url", "duration")}
    return operations.execute(arguments["request_id"], context, "media.plan_video", fingerprint, run)


def _asset(row):
    asset_id = row.get("public_id")
    return {key: row.get(key) for key in (
        "public_id", "kind", "mime_type", "sha256", "size_bytes", "width", "height",
        "duration", "has_audio", "created_at",
    )} | {"content_access": "mcp_bearer", "download_url": product_url(
        "workspace", f"/mcp/cadu/v1/media/assets/{asset_id}/content") if asset_id else ""}


def _job(row):
    return {key: row.get(key) for key in (
        "public_id", "status", "stage", "progress", "message", "created_at", "updated_at", "completed_at",
    )}


@register_tool(
    name="media.list_jobs", capability="workspace", effect="read",
    description="Lista até 50 gerações recentes do Cadu Media pertencentes ao usuário da chave; retorna estado e metadados dos ativos, sem caminhos privados.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                  "additionalProperties": False},
)
def list_media_jobs(context: RequestContext, arguments: dict) -> dict:
    limit = arguments.get("limit", 20)
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT j.id, j.public_id, j.status, j.stage, j.progress, j.message,
                                 j.created_at, j.updated_at, j.completed_at
                            FROM cx_media_jobs j JOIN cx_clients brand ON brand.id=j.client_id
                           WHERE brand.crm_client_id=%s AND j.user_id=%s
                        ORDER BY j.created_at DESC LIMIT %s""", (context.client_id, context.user_id, limit))
        jobs = [dict(row) for row in cursor.fetchall()]
        if jobs:
            cursor.execute("""SELECT job_id, public_id, kind, mime_type, sha256, size_bytes,
                                     width, height, duration, has_audio, created_at
                                FROM cx_media_assets WHERE job_id=ANY(%s) ORDER BY id""",
                           ([row["id"] for row in jobs],))
            assets = [dict(row) for row in cursor.fetchall()]
        else:
            assets = []
    by_job = {row["id"]: {**_job(row), "assets": []} for row in jobs}
    for asset in assets:
        by_job[asset["job_id"]]["assets"].append(_asset(asset))
    return {"jobs": [by_job[row["id"]] for row in jobs], "content_access": "mcp_bearer"}


@register_tool(
    name="media.get_job", capability="workspace", effect="read",
    description="Consulta uma geração do Cadu Media e seus ativos pelo ID público, limitada ao usuário e à conta da chave.",
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["job_id"], "properties": {
        "job_id": {"type": "string", "minLength": 1, "maxLength": 40}}, "additionalProperties": False},
)
def get_media_job(context: RequestContext, arguments: dict) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT j.id, j.public_id, j.status, j.stage, j.progress, j.message,
                                 j.created_at, j.updated_at, j.completed_at
                            FROM cx_media_jobs j JOIN cx_clients brand ON brand.id=j.client_id
                           WHERE j.public_id=%s AND brand.crm_client_id=%s AND j.user_id=%s""",
                       (arguments["job_id"], context.client_id, context.user_id))
        row = cursor.fetchone()
        if not row:
            raise ToolInputError("Geração do Cadu Media indisponível para esta chave.")
        job = dict(row)
        cursor.execute("""SELECT public_id, kind, mime_type, sha256, size_bytes, width, height,
                                 duration, has_audio, created_at
                            FROM cx_media_assets WHERE job_id=%s ORDER BY id""", (job["id"],))
        assets = [_asset(dict(asset)) for asset in cursor.fetchall()]
    return {"job": {**_job(job), "assets": assets}, "content_access": "mcp_bearer"}


@register_tool(
    name="media.start_studio_session", capability="workspace", effect="write",
    description=("Cria uma sessão retomável de imagem, anúncio ou vídeo no Studio e devolve seu link. "
                 "Não gera mídia nem consome créditos; a direção, aprovação e geração ocorrem no Studio."),
    exposures=("internal", "customer_agent"),
    input_schema={"type": "object", "required": ["kind", "prompt"], "properties": {
        "kind": {"type": "string", "enum": ["image", "ad", "image_edit", "video", "video_edit"]},
        "prompt": {"type": "string", "minLength": 3, "maxLength": 4000},
        "title": {"type": "string", "maxLength": 160},
        "source_url": {"type": "string", "maxLength": 2000},
        "source_id": {"type": "string", "maxLength": 180},
        "brand_id": {"type": "integer", "minimum": 1},
        "request_id": {"type": "string", "maxLength": 160},
    }, "additionalProperties": False},
)
def start_studio_session(context: RequestContext, arguments: dict) -> dict:
    from ....cadu_family import repository as family_repository
    from ....creative_media.studio import _session_store
    from ....creative_modeling_service import CreativeModelingService
    from ...brand_mcp_service import _brand, _current_brand_id

    kind = arguments["kind"]
    source_url = str(arguments.get("source_url") or "").strip()
    source_id = str(arguments.get("source_id") or "").strip()
    if kind == "image_edit" and not source_url:
        raise ToolInputError("Informe a imagem de origem para editar.")
    if kind == "video_edit" and not (source_url or source_id):
        raise ToolInputError("Informe a imagem ou o vídeo de origem para editar.")
    if source_url and not (source_url.startswith("https://") or source_url.startswith("/static/")):
        raise ToolInputError("A origem deve ser um URL HTTPS ou um ativo do Studio.")
    if context.project_ref:
        if not family_repository.project_user_can_view(context.client_id, context.project_ref, context.user_id):
            raise ToolForbidden("Você não tem acesso ao projeto selecionado.")
        actor = family_repository.actor(context.user_id) or {}
        admin = (int(actor.get("organization_id") or 0) == context.client_id
                 and family_repository.account_role(actor) == "admin")
        roles = {item.get("role") for item in family_repository.project_access(context.client_id, context.project_ref)
                 if int(item.get("user_id") or 0) == context.user_id}
        if not admin and not roles.intersection({"owner", "admin", "editor"}):
            raise ToolForbidden("Você não pode criar materiais neste projeto.")
    brand_id = None
    try:
        brand_id = _current_brand_id(context, arguments.get("brand_id"))
    except Exception:
        if arguments.get("brand_id") or context.brand_ref:
            raise
    if brand_id is not None:
        _brand(context, brand_id)
    if kind == "ad" and brand_id is None:
        raise ToolInputError("Selecione uma marca para criar um anúncio.")
    studio_client_id = brand_id or int(CreativeModelingService().repository.resolve_client_id(context.client_id, "crm"))
    title = str(arguments.get("title") or "").strip() or {
        "image": "Criação de imagem", "ad": "Criação de anúncio", "image_edit": "Edição de imagem",
        "video": "Criação de vídeo", "video_edit": "Edição de vídeo",
    }[kind]
    request_id = str(arguments.get("request_id") or "")[:160]
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in arguments.items()
                                               if key != "request_id"}, sort_keys=True,
                                              ensure_ascii=False).encode("utf-8")).hexdigest()
    # Workspace ci: references are not Studio project UUIDs. Keep the requested
    # destination in metadata without claiming that indexing already occurred.
    payload = {"studio_type": "edit" if kind.endswith("_edit") else "create",
               "title": title, "original_prompt": arguments["prompt"],
               "metadata": {"source": "cadu_mcp", "media_kind": kind,
                            "mcp_request_id": request_id, "mcp_fingerprint": fingerprint,
                            "workspace_project_ref": context.project_ref or "",
                            "brand_id": brand_id, "source_url": source_url, "source_id": source_id}}
    store = _session_store(studio_client_id)
    created = None
    if request_id and not current_app.testing:
        # Serialize retries from the same MCP key/request before creating a
        # Studio session. The repository create commits this transaction.
        with get_db().cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                           (f"cadu-media:{studio_client_id}:{context.user_id}:{request_id}",))
            cursor.execute("""SELECT id::text AS id, metadata->>'mcp_fingerprint' AS fingerprint
                                FROM cx_studio_sessions
                               WHERE client_id=%s AND user_id=%s
                                 AND metadata->>'mcp_request_id'=%s
                            ORDER BY created_at DESC LIMIT 1""",
                           (studio_client_id, context.user_id, request_id))
            previous = cursor.fetchone()
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise ToolInputError("Este request_id já foi usado para outra sessão.")
            created = store.read(studio_client_id, context.user_id, previous["id"])
    if created is None:
        created = store.create(studio_client_id, context.user_id, payload)
    path = {"image": "/criar", "ad": "/criar", "image_edit": "/imagem",
            "video": "/video", "video_edit": "/video"}[kind]
    query = urlencode({"studio_session_id": created["id"], "creative_client_id": studio_client_id})
    return {"session_id": created["id"], "studio_url": product_url("studio", f"{path}?{query}"),
            "status": created.get("status"), "destination": "project_pending_link" if context.project_ref else "personal",
            "project_ref": context.project_ref, "generation_status": "not_started", "indexed": False,
            "supported_payload": _CREATION_CONTRACTS[kind]}
