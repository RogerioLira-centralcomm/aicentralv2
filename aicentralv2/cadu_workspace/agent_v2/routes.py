"""Versioned backend contract consumed by the React Conversations V2 UI."""

import json
import re
import secrets
from dataclasses import replace
from html import escape as html_escape
from uuid import uuid4

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, session, stream_with_context, url_for
from werkzeug.exceptions import HTTPException

from ...cadu_family import context as family_context, repository
from .request_context import resolve
from .response_policy import budget_for, policy_for
from .router import route_request
from .guardrails import _clean_runtime_html
from .contracts import execution_mode_for
from ..mcp.registry import load_builtin_tools
from ..mcp.authorization import MAX_AGE_SECONDS, issue
from ..artifacts import attach_to_project, create_draft, get_artifact, get_public_artifact, get_version, list_versions, materialize_artifact, patch_artifact, publish_artifact, unpublish_artifact
from ..artifacts.service import finalize_to_project
from .service import prepare as prepare_message, stream as stream_message
from .provider import ProviderUnavailable
from . import journal, long_jobs, observability
from .long_jobs import LongJobSpec
from . import action_executor
from . import turn_queue
from .conversation_runtime import RuntimeRollout
from ..mcp.registry import ToolError
from ..conversations import attachments
from ...cadu_planner import docs
from ...creative_modeling_storage import ClientLogoStorage, CreativeAssetStorage, public_studio_asset_url
from ...product_domains import product_url


bp = Blueprint("cadu_agent_v2", __name__, url_prefix="/workspace/api/v2")
lab_bp = Blueprint("cadu_agent_v2_lab", __name__)
public_bp = Blueprint("cadu_public_artifacts", __name__)
_CREDIT_ERROR = re.compile(
    r"Saldo insuficiente:\s*(?:esta execução estima|a execução usou)\s*(\d+)\s+tokens?\s+e há\s*(\d+)\s+disponíveis\.?",
    re.IGNORECASE,
)


@lab_bp.get("/workspace/conversas-v2-lab")
@lab_bp.get("/chat")
def conversations_v2_lab():
    if not session.get("user_id"):
        abort(401)
    # This screen belongs to its own blueprint, so it does not pass through the
    # Workspace hook that normally creates the shared Cadu CSRF token.
    session.setdefault("family_csrf", secrets.token_urlsafe(32))
    dock_brands = []
    menu_projects = []
    rollout_client_id = session.get("client_id")
    try:
        current = resolve()
        rollout_client_id = current.client_id
        from ..routes import _workspace_brands, _workspace_common_dock_items, _workspace_projects
        from ...cadu_skills.repository import credit_position
        links = repository.project_brand_links(current.client_id)
        project_counts = {}
        for link in links:
            ref = str(link.get("brand_ref") or "")
            project_counts[ref] = project_counts.get(ref, 0) + 1
        brands = _workspace_brands(current.client_id)
        projects = _workspace_projects(current.client_id)
        dock_brands = [{
            "id": str(brand["id"]), "kind": "brand", "brandRef": f"studio:{brand['id']}",
            "title": str(brand.get("name") or "Marca"), "name": str(brand.get("name") or "Marca"),
            "logoUrl": str(brand.get("display_logo") or ""),
            "visualInitials": str(brand.get("display_initials") or "M"),
            "visualColor": str(brand.get("display_color") or "#176b5e"),
            "href": url_for("cadu_workspace.clean_brand_detail", brand_id=int(brand["id"])),
            "projectCount": project_counts.get(f"studio:{brand['id']}", 0),
        } for brand in brands]
        menu_projects = [{
            "id": f"ci:{project.get('id')}", "kind": "project", "projectRef": f"ci:{project.get('id')}",
            "ref": f"ci:{project.get('id')}", "brandRef": str(project.get('brand_ref') or ""),
            "related_refs": list(project.get('related_refs') or []),
            "title": str(project.get("nome") or "Projeto"), "name": str(project.get("nome") or "Projeto"),
            "href": url_for("cadu_workspace.clean_project_detail", project_id=str(project.get("id"))),
            "previewUrl": str(project.get("thumbnail_url") or ""), "dockLogoUrl": str(project.get("brand_logo_url") or ""),
            "brandName": str(project.get("thumbnail_label") or ""),
        } for project in projects]
        dock_items = _workspace_common_dock_items(current.client_id, int(session.get("user_id") or 0), projects=projects, brands=brands)
        usage_percent = round(float((credit_position(current.client_id) or {}).get('monthly_usage_percentage') or 0), 1)
    except Exception:
        current_app.logger.exception("Não foi possível preparar marcas para a dock do Chat")
        dock_items = []
        usage_percent = 0
    conversation_rollout = RuntimeRollout.current(
        client_id=rollout_client_id,
        user_id=session.get("user_id"),
        is_internal=bool(session.get("is_centralcomm")),
    ).public_metadata()
    if not conversation_rollout["shell_v2"]:
        return render_template(
            "cadu_workspace/conversations.html",
            conversation_runtime_v2=conversation_rollout["runtime_v2"],
        )
    return render_template(
        "cadu_workspace/conversations_v2_lab.html",
        chat_brands=dock_brands, chat_projects=menu_projects, dock_items=dock_items,
        usage_percent=usage_percent, conversation_rollout=conversation_rollout,
    )


@lab_bp.get("/workspace/observabilidade")
def observability_page():
    if not session.get("user_id"):
        abort(401)
    if session.get("user_type") not in {"admin", "superadmin"}:
        abort(403)
    client_id = resolve().client_id
    return render_template("cadu_workspace/observability.html", telemetry=observability.dashboard(client_id))


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
        message = str(exc.description or "Não foi possível concluir a operação.")
        payload = {"error": message}
        credit_error = _CREDIT_ERROR.search(message)
        if credit_error:
            payload.update(
                code="credits_insufficient",
                credits_url=product_url("workspace", "/creditos"),
                details={
                    "required_tokens": int(credit_error.group(1)),
                    "available_tokens": int(credit_error.group(2)),
                },
            )
        return jsonify(**payload), exc.code
    if isinstance(exc, ProviderUnavailable):
        current_app.logger.exception("Runtime Cadu indisponível")
        return jsonify(error="O agente desta conversa está temporariamente indisponível. Tente novamente em instantes."), 503
    current_app.logger.exception("Falha na API Cadu Conversations V2")
    if request.path.endswith("/uploads"):
        return jsonify(error="Não foi possível anexar o arquivo agora. Tente novamente em instantes."), 503
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
    current = resolve(conversation_id=data.get("conversation_id"), request_id=data.get("request_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"),
                      project_ref=data.get("project_ref"), brand_ref=data.get("brand_ref"))
    return jsonify(token=issue(current, exposure), expires_in=MAX_AGE_SECONDS,
                   endpoint="/workspace/mcp", exposure=exposure, context=current.to_dict())


@bp.get("/brands/<int:brand_id>/identity")
def brand_identity(brand_id):
    """Return a read-only identity artifact for a brand selected in Chat."""
    current = resolve(surface=request.args.get("surface") or "conversations")
    brand_ref = f"studio:{brand_id}"
    allowed = {item["ref"] for item in repository.entities(current.client_id)}
    if brand_ref not in allowed:
        abort(404, description="Marca não encontrada neste ambiente.")
    from ..routes import _workspace_brands, _workspace_projects
    brand = next((item for item in _workspace_brands(current.client_id) if int(item.get("id") or 0) == brand_id), None)
    if not brand:
        abort(404, description="Identidade da marca indisponível.")
    profile = brand.get("brand_profile") or {}
    colors = profile.get("color_palette") or []
    if not isinstance(colors, list):
        colors = []
    colors = [str(color).strip() for color in colors if str(color).strip()][:8]
    for color in (brand.get("primary_color"), brand.get("secondary_color")):
        if color and color not in colors:
            colors.append(str(color))
    fonts = profile.get("fonts") or []
    if isinstance(fonts, str):
        fonts = [fonts]
    fonts = [str(font).strip() for font in fonts if str(font).strip()][:6]
    analysis = brand.get("analysis_metadata") or {}
    review_pack = analysis.get("review_pack") if isinstance(analysis, dict) else {}
    review_pack = review_pack if isinstance(review_pack, dict) else {}
    analysis_profile = review_pack.get("analysis") if isinstance(review_pack.get("analysis"), dict) else {}

    def identity_value(value):
        if isinstance(value, dict):
            preferred = value.get("name") or value.get("label") or value.get("family") or value.get("text")
            if preferred:
                return str(preferred).strip()
            return "; ".join(f"{key}: {item}" for key, item in value.items() if item not in (None, ""))[:1200]
        if isinstance(value, (list, tuple)):
            values = [identity_value(item) for item in value]
            return " · ".join(item for item in values if item)[:1200]
        return str(value or "").strip()[:1200]

    detail_sources = [
        ("Segmento", "sector", brand),
        ("Posicionamento", "positioning", profile),
        ("Tom de voz", "tone_of_voice", {**brand, **profile}),
        ("Público prioritário", "target_audience", profile),
        ("Valores", "brand_values", profile),
        ("Produtos e serviços", "products_services", profile),
        ("Diferenciais", "differentiators", profile),
        ("Direção criativa", "creative_guidelines", profile),
        ("Elementos obrigatórios", "mandatory_elements", profile),
        ("O que evitar", "forbidden_elements", profile),
        ("Arquétipo", "archetype", profile),
        ("Personas", "personas", profile),
    ]
    details = []
    for label, key, source in detail_sources:
        value = source.get(key) or analysis_profile.get(key)
        rendered = identity_value(value)
        if rendered and rendered.lower() not in {"ainda não definido", "ainda não definido."}:
            details.append({"label": label, "value": rendered})
    website = str(brand.get("website_url") or "").strip()
    project_refs = {str(link.get("project_ref") or "") for link in repository.project_brand_links(current.client_id)
                    if str(link.get("brand_ref") or "") == brand_ref}
    projects = [{"ref": f"ci:{item.get('id')}", "name": str(item.get("nome") or "Projeto")}
                for item in _workspace_projects(current.client_id, status="ativos")
                if f"ci:{item.get('id')}" in project_refs]
    return jsonify(
        projects=projects,
        artifact={
            "type": "brand_identity", "title": f"Identidade — {brand.get('name') or 'Marca'}",
            "content": {
                "name": brand.get("name"), "logo_url": brand.get("display_logo"), "summary": profile.get("brand_summary") or profile.get("positioning") or brand.get("display_summary") or "Identidade da marca disponível para orientar esta conversa.",
                "colors": colors, "fonts": fonts,
                "website_url": website, "asset_count": int(brand.get("asset_count") or 0),
                "audit_url": f"/workspace/marcas/{brand_id}#brand-status",
                "audit_status": str((brand.get("analysis_metadata") or {}).get("review_pack", {}).get("status") or ""),
                "details": details,
                "projects": projects,
            },
        },
    )


@bp.get("/projects/<path:project_ref>/resources")
def project_resource_map(project_ref):
    """Expose the canonical Resource Registry as a navigable Chat artifact."""
    current = resolve(surface=request.args.get("surface") or "conversations", project_ref=project_ref)
    if current.project_ref != project_ref:
        abort(404, description="Projeto não encontrado neste ambiente.")
    from types import SimpleNamespace
    from .. import project_resource_service
    from .service import _project_map_content
    registry = project_resource_service.list_for_context(current)
    entities = {item["ref"]: item for item in repository.entities(current.client_id)}
    project_name = str((entities.get(project_ref) or {}).get("name") or "Projeto")
    content = _project_map_content({
        "context": current,
        "resolved_context": SimpleNamespace(values={"projects.list_resources": registry}),
    }, {"title": f"Recursos — {project_name}"})
    return jsonify(artifact={"type": "project_map", "title": content["title"], "content": content})


@bp.get("/studio/library")
def studio_library():
    """Return the Studio shelf in the same shape used by Conversations."""
    current = resolve(surface=request.args.get("surface") or "conversations",
                      project_ref=request.args.get("project_ref"), brand_ref=request.args.get("brand_ref"))
    from .. import project_resource_service
    resources = project_resource_service.list_for_context(current) if current.project_ref else {"resources": []}
    personal_assets = []
    if not current.project_ref:
        from ...creative_media.studio import _creation_history
        history = _creation_history()
        user_id = session.get("user_id")
        if history and user_id:
            personal_assets = history.personal_assets(current.client_id, user_id)
    brand_assets = []
    if current.brand_ref and str(current.brand_ref).startswith("studio:"):
        try:
            with repository.get_db().cursor() as cursor:
                cursor.execute("""SELECT id::text AS id, role, asset_path, source_url, metadata
                                   FROM cx_client_brand_assets
                                  WHERE client_id=%s
                               ORDER BY is_primary DESC NULLS LAST, id DESC""",
                               (str(current.brand_ref)[7:],))
                brand_assets = [dict(row) for row in cursor.fetchall()]
                for asset in brand_assets:
                    raw_path = asset.get("asset_path") or asset.get("source_url") or ""
                    try:
                        if str(raw_path).startswith("/static/") and ClientLogoStorage().absolute_public_path(raw_path) is None:
                            asset["display_url"] = ""
                        else:
                            asset["display_url"] = public_studio_asset_url(raw_path)
                    except ValueError:
                        asset["display_url"] = ""
        except Exception:
            current_app.logger.exception("Falha ao carregar ativos da marca para a biblioteca do Studio")
    return jsonify(scope="project" if current.project_ref else "personal",
                   project_ref=current.project_ref, brand_ref=current.brand_ref,
                   resources=resources.get("resources", []) if isinstance(resources, dict) else [],
                   brand_assets=brand_assets,
                   personal_assets=personal_assets)


@bp.post("/images/organize")
def organize_image():
    """Run OCR and persist a user-requested title/summary for an owned local image."""
    data = request.get_json(silent=True) or {}
    current = resolve(surface="conversations", project_ref=data.get("project_ref"), brand_ref=data.get("brand_ref"))
    source = str(data.get("source") or "")[:40]
    source_id = str(data.get("source_id") or data.get("id") or "")[:160]
    title = str(data.get("title") or "imagem.png")[:220]
    raw_id = source_id.split(":", 1)[-1]
    connection = repository.get_db()
    owned = None
    with connection.cursor() as cursor:
        if source == "brand" and raw_id.isdigit() and current.brand_ref:
            cursor.execute("""SELECT id, COALESCE(asset_path, source_url) AS asset_url
                                FROM cx_client_brand_assets WHERE id=%s AND client_id=%s""",
                           (int(raw_id), int(str(current.brand_ref).removeprefix("studio:"))))
            owned = cursor.fetchone()
        elif source == "reference":
            cursor.execute("""SELECT id, asset_url FROM cx_studio_assets
                                WHERE id::text=%s AND client_id=%s AND owner_user_id=%s
                                  AND deleted_at IS NULL""", (raw_id, current.client_id, current.user_id))
            owned = cursor.fetchone()
        elif source == "personal":
            cursor.execute("""SELECT id, result->>'image_url' AS asset_url
                                FROM cx_studio_image_generations
                               WHERE id::text=%s AND client_id=%s AND user_id=%s
                                 AND deleted_at IS NULL""", (raw_id, current.client_id, current.user_id))
            owned = cursor.fetchone()
        elif source == "studio" and current.project_ref:
            cursor.execute("""SELECT item.id, item.asset_url
                                FROM cx_studio_project_items item
                                JOIN cx_studio_projects project ON project.id=item.project_id
                               WHERE item.id::text=%s AND project.client_id=%s
                                 AND project.document->>'external_project_id'=%s""",
                           (raw_id, current.client_id, str(current.project_ref).removeprefix("ci:")))
            owned = cursor.fetchone()
        elif source == "workspace_images" and raw_id.isdigit() and current.project_ref:
            cursor.execute("""SELECT id, file_bytes, file_path AS asset_url
                                FROM cadu_docs_client_images
                               WHERE id=%s AND id_cliente=%s AND projeto_id=%s AND ativo=true""",
                           (int(raw_id), current.client_id, str(current.project_ref).removeprefix("ci:")))
            owned = cursor.fetchone()
    if not owned:
        abort(404, description="Não foi possível localizar esta imagem no contexto autorizado.")
    image_bytes = owned.get("file_bytes") if isinstance(owned, dict) else None
    if not image_bytes:
        image_bytes = CreativeAssetStorage().read_public_bytes(str(owned.get("asset_url") or ""))
    if not image_bytes:
        abort(422, description="Esta imagem ainda não possui uma cópia local disponível para OCR.")
    from .. import project_sources
    ocr_text, processing = project_sources._ocr_image(image_bytes)
    if not ocr_text.strip():
        abort(422, description="Não encontramos texto suficiente nesta imagem para organizar o arquivo.")
    organized = project_sources.organize_image_source(title, ocr_text)
    metadata = {
        "visual_title": organized["visual_title"], "visual_summary": organized["visual_summary"],
        "ocr_text": ocr_text[:12000], "ocr_processing": processing,
        "original_name": organized["original_name"], "renamed_by_indexer": organized["renamed_by_indexer"],
    }
    try:
        with connection.cursor() as cursor:
            updated = None
            if source == "brand":
                cursor.execute("""UPDATE cx_client_brand_assets
                                      SET metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb, updated_at=NOW()
                                    WHERE id=%s AND client_id=%s RETURNING id""",
                               (json.dumps({**metadata, "display_name": organized["name"]}, ensure_ascii=False),
                                int(raw_id), int(str(current.brand_ref).removeprefix("studio:"))))
                updated = cursor.fetchone()
            elif source in {"personal", "reference"}:
                table = "cx_studio_assets" if source == "reference" else "cx_studio_image_generations"
                if table == "cx_studio_assets":
                    cursor.execute("""UPDATE cx_studio_assets SET title=%s,
                                          metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb
                                        WHERE id::text=%s AND client_id=%s AND owner_user_id=%s RETURNING id""",
                                   (organized["name"], json.dumps(metadata, ensure_ascii=False), raw_id,
                                    current.client_id, current.user_id))
                else:
                    cursor.execute("""UPDATE cx_studio_image_generations
                                          SET result=COALESCE(result,'{}'::jsonb) || %s::jsonb
                                        WHERE id::text=%s AND client_id=%s AND user_id=%s RETURNING id""",
                                   (json.dumps({**metadata, "title": organized["name"]}, ensure_ascii=False), raw_id,
                                    current.client_id, current.user_id))
                updated = cursor.fetchone()
            elif source == "studio":
                cursor.execute("""UPDATE cx_studio_project_items item SET title=%s,
                                      metadata=COALESCE(item.metadata,'{}'::jsonb) || %s::jsonb, updated_at=NOW()
                                     FROM cx_studio_projects project
                                    WHERE item.id::text=%s AND item.project_id=project.id
                                      AND project.client_id=%s AND project.document->>'external_project_id'=%s
                                RETURNING item.id""",
                               (organized["name"], json.dumps(metadata, ensure_ascii=False), raw_id,
                                current.client_id, str(current.project_ref).removeprefix("ci:")))
                updated = cursor.fetchone()
            elif source == "workspace_images":
                cursor.execute("""UPDATE cadu_docs_client_images SET title=%s
                                    WHERE id=%s AND id_cliente=%s AND projeto_id=%s AND ativo=true
                                RETURNING id""", (organized["name"], int(raw_id), current.client_id,
                                                   str(current.project_ref).removeprefix("ci:")))
                updated = cursor.fetchone()
                cursor.execute("""UPDATE cadu_project_resources
                                      SET title=%s, metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb,
                                          source_updated_at=NOW(), last_seen_at=NOW()
                                    WHERE client_id=%s AND project_ref=%s
                                      AND source_system='workspace_images' AND source_id=%s""",
                               (organized["name"], json.dumps(metadata, ensure_ascii=False), current.client_id,
                                current.project_ref, raw_id))
            if not updated:
                abort(404, description="Não foi possível localizar esta imagem no contexto autorizado.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(ok=True, title=organized["name"], summary=organized["visual_summary"],
                   renamed=organized["renamed_by_indexer"], processing=processing)


@bp.post("/route")
def route_preview():
    data = request.get_json(silent=True) or {}
    message = " ".join(str(data.get("message") or "").split())
    if not 1 <= len(message) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"),
                      project_ref=data.get("project_ref"), brand_ref=data.get("brand_ref"))
    route = route_request(
        message, current.surface, bool(current.project_ref),
        current.active_object.type if current.active_object else "", bool(current.brand_ref),
    )
    execution_mode = execution_mode_for(route, data.get("execution_mode") or data.get("depth") or data.get("mode"))
    return jsonify(
        route=route.to_dict(), execution_mode=execution_mode, context=current.to_dict(), policy=policy_for(route),
        budget=budget_for(route, execution_mode).__dict__,
    )


@bp.post("/conversations/messages")
def conversation_message():
    # The authenticated V2 screen is now a published Workspace surface. Runtime
    # credentials still fail closed in provider.py, but an exposed UI must not
    # answer with a rollout 404 before admission reaches the agent.
    payload = request.get_json(silent=True) or {}
    rollout = RuntimeRollout.current(
        client_id=session.get("client_id") or session.get("cliente_id"), user_id=session.get("user_id"),
        is_internal=bool(session.get("is_centralcomm")),
    )
    if not rollout.runtime_v2:
        # Resolve the authoritative tenant before entering the legacy runtime;
        # this also rejects a foreign or missing supplied conversation.
        resolve(
            conversation_id=payload.get("conversation_id"), request_id=payload.get("request_id"),
            surface=str(payload.get("surface") or "conversations"),
            active_object=payload.get("active_object"), project_ref=payload.get("project_ref"),
            brand_ref=payload.get("brand_ref"),
        )
        from ..conversations import service as legacy_service
        requested_depth = payload.get("depth") or payload.get("execution_mode") or "analysis"
        legacy_payload = {
            **payload,
            "profile": "workspace",
            "depth": requested_depth if requested_depth in {"focus", "analysis", "deep"} else "analysis",
        }
        legacy_run = legacy_service.prepare(legacy_payload, family_context.resolve())
        return Response(
            stream_with_context(legacy_service.stream(legacy_run)), mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        )
    run = prepare_message(payload)
    spec = long_jobs.spec_for_message(run.get("message") or payload.get("message"))
    if spec:
        try:
            job = long_jobs.create(
                run["context"], run["conversation_id"], spec, run_id=run["run_id"],
                idempotency_key=f"conversation:{run['run_id']}",
            )
        except Exception:
            connection = repository.get_db()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""UPDATE cadu_family_chat_runs SET status='failed',finished_at=NOW(),
                        terminal_error_code='long_job_admission_failed' WHERE id=%s AND status='running'""",
                        (run["run_id"],))
                connection.commit()
            except Exception:
                connection.rollback()
                current_app.logger.exception("Falha ao encerrar run após erro de admissão do trabalho longo.")
            raise
        from .long_job_worker import dispatch as dispatch_long_job
        dispatch_long_job(job["id"])

        def admitted_long_job():
            def event(kind, **payload):
                return "data: " + json.dumps({"event": kind, **payload}, ensure_ascii=False, default=str) + "\n\n"
            yield event("run.started", run_id=run["run_id"], conversation_id=run["conversation_id"],
                        resolved_context=run["context"].to_dict())
            yield event("route.selected", route=run["route"], policy={**run["policy"], "long_job": True})
            yield event("long_job.created", job={"id": job["id"], "title": spec.title, "kind": spec.kind,
                                                   "source_target": spec.source_target,
                                                   "token_budget": spec.token_budget})
            response = {"answer": "Iniciei o trabalho em segundo plano. O conteúdo será construído por etapas e o artefato aparecerá assim que a primeira versão estiver pronta.",
                        "confidence": "high", "assumptions": [], "questions": [], "actions": [],
                        "artifact_patch": None, "citations": [], "blocks": []}
            yield event("answer.completed", response=response)
            connection = repository.get_db()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""UPDATE cadu_family_chat_runs SET status='completed',finished_at=NOW()
                        WHERE id=%s AND status='running'""", (run["run_id"],))
                connection.commit()
                journal.record(run["run_id"], "long_job.created", {"job_id": job["id"], "title": spec.title})
                journal.record(run["run_id"], "run.completed", {"status": "completed", "long_job_id": job["id"]})
            except Exception:
                connection.rollback()
                raise
            yield event("run.completed", status="completed", conversation_id=run["conversation_id"],
                        long_job_id=job["id"])

        return Response(stream_with_context(admitted_long_job()), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    return Response(stream_with_context(stream_message(run)), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.get("/conversations/<conversation_id>/queue")
def queued_turns(conversation_id):
    current = resolve(conversation_id=conversation_id)
    try:
        return jsonify(items=turn_queue.list_items(conversation_id, current))
    except ValueError as exc:
        abort(404, description=str(exc))


def _active_run(conversation_id, current):
    rows = repository.rows("""SELECT run.id::text,run.status,run.execution_mode,run.created_at
        FROM cadu_family_chat_runs run
        JOIN cadu_conversations conversation ON conversation.id=run.conversation_id
        WHERE run.conversation_id=%s AND run.user_id=%s AND run.client_id=%s
          AND conversation.id_contato_cliente=%s AND conversation.id_cliente=%s
          AND run.runtime_version='v2'
          AND (run.status='running' OR EXISTS (
                SELECT 1 FROM cadu_agent_run_steps step
                 WHERE step.run_id=run.id AND step.kind='action'
                   AND step.status='waiting_confirmation'))
        ORDER BY run.created_at DESC LIMIT 1""",
        (conversation_id, current.user_id, current.client_id, current.user_id, current.client_id))
    active = rows[0] if rows else None
    if active:
        active["actions"] = journal.waiting_actions(active["id"], current.client_id, current.user_id)
    return active


@bp.get("/conversations/<conversation_id>/bootstrap")
def conversation_bootstrap(conversation_id):
    """Restore one conversation in one bounded request after reload."""
    current = resolve(conversation_id=conversation_id)
    actor = family_context.identity()
    messages = repository.conversation_messages(
        current.user_id, current.client_id, conversation_id, limit=100,
    )
    if messages is None:
        abort(404, description="Conversa não encontrada.")
    rows = repository.rows("""SELECT titulo AS title,updated_at,status
        FROM cadu_conversations WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s""",
        (conversation_id, current.user_id, current.client_id))
    conversation = rows[0] if rows else {"title": "Conversa"}
    try:
        queued = turn_queue.list_items(conversation_id, current)
    except ValueError:
        queued = []
    entities = family_context.inventory(current.client_id)
    return jsonify(
        conversation={"id": conversation_id, **conversation},
        context=current.to_dict(), entities=entities,
        conversations=repository.conversation_history(actor, current.client_id, limit=30),
        messages=messages, queue=queued, active_run=_active_run(conversation_id, current),
    )


@bp.get("/conversations/<conversation_id>/active-run")
def active_conversation_run(conversation_id):
    current = resolve(conversation_id=conversation_id)
    return jsonify(run=_active_run(conversation_id, current))


@bp.post("/conversations/<conversation_id>/queue")
def queue_turn(conversation_id):
    current = resolve(conversation_id=conversation_id)
    try:
        return jsonify(item=turn_queue.create(conversation_id, current, request.get_json(silent=True) or {})), 201
    except OverflowError as exc:
        abort(409, description=str(exc))
    except ValueError as exc:
        abort(400, description=str(exc))


@bp.put("/conversations/<conversation_id>/queue")
def replace_queued_turns(conversation_id):
    current = resolve(conversation_id=conversation_id)
    try:
        return jsonify(items=turn_queue.replace(conversation_id, current, (request.get_json(silent=True) or {}).get("items")))
    except ValueError as exc:
        abort(400, description=str(exc))


@bp.delete("/conversations/<conversation_id>/queue/<uuid:item_id>")
def delete_queued_turn(conversation_id, item_id):
    current = resolve(conversation_id=conversation_id)
    if not turn_queue.remove(conversation_id, str(item_id), current):
        abort(404, description="Item da fila não encontrado.")
    return jsonify(deleted=True)


@bp.post("/conversations/<conversation_id>/long-jobs")
def create_long_job(conversation_id):
    current = resolve(conversation_id=conversation_id)
    if not repository.rows("""SELECT id FROM cadu_conversations
        WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s AND status IN ('ativa','active')""",
        (conversation_id, current.user_id, current.client_id)):
        abort(404, description="Conversa não encontrada.")
    data = request.get_json(silent=True) or {}
    try:
        spec = LongJobSpec(
            kind=str(data.get("kind") or "long_document"),
            title=str(data.get("title") or ""),
            objective=str(data.get("objective") or ""),
            source_target=data.get("source_target", 5),
            max_agent_calls=data.get("max_agent_calls", 8),
            max_extractor_calls=data.get("max_extractor_calls", 40),
            token_budget=data.get("token_budget", 40_000),
        )
        job = long_jobs.create(current, conversation_id, spec, run_id=data.get("run_id"),
                               artifact_id=data.get("artifact_id"),
                               idempotency_key=str(data.get("idempotency_key") or ""))
        return jsonify(job=job), 201
    except ValueError as exc:
        abort(400, description=str(exc))


@bp.get("/long-jobs/<uuid:job_id>")
def long_job_state(job_id):
    current = resolve()
    try:
        return jsonify(long_jobs.snapshot(str(job_id), current))
    except ValueError as exc:
        abort(404, description=str(exc))


@bp.post("/long-jobs/<uuid:job_id>/cancel")
def cancel_long_job(job_id):
    current = resolve()
    if not long_jobs.cancel(str(job_id), current):
        abort(409, description="O trabalho já foi encerrado ou não está disponível.")
    return jsonify(cancelled=True)


@bp.post("/uploads")
def upload():
    current = resolve(surface="conversations")
    if not repository.family_table_available("cadu_family_chat_uploads"):
        abort(409, description="O armazenamento de anexos ainda não está disponível.")
    attachments.bound_multipart_request(request)
    files = request.files.getlist("file")
    if len(files) != 1 or len(request.files) != 1:
        abort(400, description="Envie um arquivo de cada vez.")
    validated, kind, size = attachments.validate(files[0])
    from . import provider
    execution_mode = str(request.form.get("execution_mode") or "analysis").strip().lower()
    if execution_mode not in {"fast", "analysis", "agentic"}:
        abort(400, description="Modo de execução inválido para o anexo.")
    provider_id = provider.upload_file(validated, "user-" + str(current.user_id), execution_mode)
    upload_id = str(uuid4())
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO cadu_family_chat_uploads
                (id, user_id, client_id, provider_id, name, kind)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (upload_id, current.user_id, current.client_id, provider_id, validated.filename, kind))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return jsonify(file={"id": upload_id, "name": validated.filename, "kind": kind, "size": size}), 201


@bp.post("/resources/<uuid:resource_id>/editable-copy")
def resource_editable_copy(resource_id):
    current = resolve(surface="conversations")
    rows = repository.rows(
        """SELECT project_ref, source_id, title FROM cadu_project_resources
             WHERE id = %s AND organization_id = %s AND client_id = %s
               AND source_system = 'workspace' AND source_id LIKE 'file:%%'""",
        (str(resource_id), current.organization_id, current.client_id),
    )
    if not rows:
        abort(404, description="Arquivo indisponível para conversão.")
    resource = rows[0]
    source_id = str(resource["source_id"])[5:]
    project_ref = str(resource.get("project_ref") or "")
    if not source_id.isdigit() or not project_ref.startswith("ci:"):
        abort(409, description="Este arquivo não possui uma versão editável disponível.")
    sources = repository.rows(
        """SELECT nome_arquivo, extracted_text FROM cadu_ci_projeto_arquivos
             WHERE id = %s AND id_cliente = %s AND projeto_id = %s""",
        (int(source_id), current.client_id, project_ref[3:]),
    )
    text = str(sources[0].get("extracted_text") or "").strip() if sources else ""
    if not text:
        abort(409, description="O arquivo precisa terminar a indexação antes de virar documento editável.")
    document = docs.create_document(current.client_id, current.user_id, {
        "title": resource.get("title") or sources[0].get("nome_arquivo") or "Documento importado",
        "type": "documento",
        "project_id": project_ref[3:],
        "html": docs.markdown_to_safe_html(text),
    })
    return jsonify(document={
        "id": str(document["id"]),
        "title": document.get("title"),
        "editor_url": f"/workspace/docs/{document['id']}",
    }), 201


@bp.get("/runs/<uuid:run_id>/events")
def run_events(run_id):
    current = resolve()
    return jsonify(events=journal.events(str(run_id), current.client_id, current.user_id))


@bp.get("/runs/<uuid:run_id>/state")
def run_state(run_id):
    current = resolve()
    try:
        return jsonify(journal.state(str(run_id), current.client_id, current.user_id))
    except ValueError as exc:
        abort(404, description=str(exc))


@bp.post("/runs/<uuid:run_id>/steps/<uuid:step_id>/decision")
def run_step_decision(run_id, step_id):
    current = resolve()
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("approved"), bool):
        abort(400, description="Informe approved como verdadeiro ou falso.")
    try:
        step = journal.decide_step(str(run_id), str(step_id), current.client_id, current.user_id,
                                   data["approved"], data.get("note"))
        if data["approved"] and step.get("kind") == "action":
            try:
                receipt = action_executor.execute(step, current)
                step = journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                             receipt=receipt)
            except ToolError as exc:
                journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                      error_code=exc.code)
                abort(409, description=str(exc))
            except Exception:
                journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                      error_code="action_failed")
                raise
        return jsonify(step=step, state=journal.state(str(run_id), current.client_id, current.user_id))
    except ValueError as exc:
        abort(409, description=str(exc))


@bp.get("/observability/runs/<uuid:run_id>")
def observability_run(run_id):
    if session.get("user_type") not in {"admin", "superadmin"}:
        abort(403)
    current = resolve()
    try:
        return jsonify(observability.run_detail(current.client_id, str(run_id)))
    except ValueError as exc:
        abort(404, description=str(exc))


@bp.post("/runs/<uuid:run_id>/stop")
def stop_run(run_id):
    current = resolve()
    rows = repository.rows(
        """SELECT task_id, status, execution_mode FROM cadu_family_chat_runs
             WHERE id = %s AND user_id = %s AND client_id = %s AND runtime_version = 'v2'""",
        (str(run_id), current.user_id, current.client_id),
    )
    if not rows:
        abort(404)
    if rows[0]["status"] != "running":
        return jsonify(stopped=True)
    if not rows[0].get("task_id"):
        abort(409, description="A geração ainda está iniciando. Tente novamente.")
    from . import provider
    provider.stop(rows[0]["task_id"], "user-" + str(current.user_id),
                  rows[0].get("execution_mode") or "analysis")
    conn = repository.get_db()
    with conn.cursor() as cur:
        cur.execute("""UPDATE cadu_family_chat_runs SET status = 'cancelled', finished_at = NOW()
                       WHERE id = %s AND user_id = %s AND client_id = %s AND status = 'running'""",
                    (str(run_id), current.user_id, current.client_id))
    conn.commit()
    try:
        journal.record(str(run_id), "run.cancelled", {"user_id": current.user_id})
    except Exception:
        current_app.logger.exception("Falha ao registrar cancelamento do Turn %s", run_id)
    return jsonify(stopped=True)


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


@bp.get("/artifacts/<uuid:artifact_id>/render")
def artifact_render(artifact_id):
    current = resolve()
    artifact = get_artifact(current, str(artifact_id))
    requested_version = request.args.get("version", type=int)
    if requested_version and requested_version != int(artifact["current_version"]):
        selected = get_version(current, str(artifact_id), requested_version)
        artifact = {**artifact, "current_version": selected["version"], "content": selected["content"]}
    target = materialize_artifact(artifact)
    if target is None:
        abort(400, description="Este tipo de artefato usa um editor dedicado.")
    response = Response(target.read_text(encoding="utf-8"), mimetype="text/html")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "font-src 'self' data:; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'"
    )
    return response


@bp.get("/artifacts/<uuid:artifact_id>/versions")
def artifact_versions(artifact_id):
    return jsonify(versions=list_versions(resolve(), str(artifact_id)))


@bp.get("/artifacts/<uuid:artifact_id>/versions/<int:version>")
def artifact_version(artifact_id, version):
    return jsonify(version=get_version(resolve(), str(artifact_id), version))


@bp.patch("/artifacts/<uuid:artifact_id>")
def artifact_patch(artifact_id):
    data = request.get_json(silent=True) or {}
    artifact = patch_artifact(resolve(conversation_id=data.get("conversation_id")), str(artifact_id),
                              data.get("content"), expected_version=data.get("expected_version"),
                              title=data.get("title"), status=data.get("status"),
                              change_summary=data.get("change_summary"))
    return jsonify(artifact=artifact)


@bp.post("/artifacts/<uuid:artifact_id>/save-project")
def artifact_save_project(artifact_id):
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"))
    project_ref = str(data.get("project_ref") or current.project_ref or "").strip()
    allowed = {str(item.get("ref") or "") for item in family_context.inventory(current.client_id)
               if item.get("kind") == "project"}
    if project_ref not in allowed:
        abort(404, description="Projeto não encontrado neste ambiente.")
    artifact = attach_to_project(replace(current, project_ref=project_ref), str(artifact_id), project_ref)
    return jsonify(artifact=artifact)


@bp.post("/artifacts/<uuid:artifact_id>/finalize-project")
def artifact_finalize_project(artifact_id):
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      project_ref=data.get("project_ref"))
    result = finalize_to_project(current, str(artifact_id), expected_version=data.get("expected_version"))
    return jsonify(**result)


@bp.post("/artifacts/<uuid:artifact_id>/publish")
def artifact_publish(artifact_id):
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"))
    artifact = publish_artifact(current, str(artifact_id))
    public_url = url_for("cadu_public_artifacts.public_artifact", artifact_id=str(artifact_id), _external=True)
    return jsonify(artifact=artifact, url=public_url)


@bp.post("/artifacts/<uuid:artifact_id>/unpublish")
def artifact_unpublish(artifact_id):
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"))
    artifact = unpublish_artifact(current, str(artifact_id))
    return jsonify(artifact=artifact)


@public_bp.get("/public/cadu/artifacts/<uuid:artifact_id>")
def public_artifact(artifact_id):
    artifact = get_public_artifact(str(artifact_id))
    content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
    title = html_escape(str(artifact.get("title") or "Cadu"), quote=True)
    css = str(content.get("css") or "").replace("</style", "<\\/style")
    javascript = str(content.get("js") or "").replace("</script", "<\\/script")
    body = _clean_runtime_html(content.get("html"), 100_000)
    logo = str(content.get("logo_url") or "").strip()
    if not (logo.startswith("https://") or logo.startswith("/")):
        logo = ""
    logo = html_escape(logo, quote=True)
    def brand_color(value):
        value = str(value or "").strip()
        return value if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value) else ""
    primary_color = brand_color(content.get("primary_color"))
    secondary_color = brand_color(content.get("secondary_color"))
    theme = ";".join(item for item in (
        f"--cadu-brand-primary:{primary_color}" if primary_color else "",
        f"--cadu-brand-secondary:{secondary_color}" if secondary_color else "",
    ) if item)
    public_origin = request.host_url.rstrip("/")
    artifact_stylesheet = f"{public_origin}/static/css/tailwind/artifact.css"
    favicon = f'<link rel="icon" href="{logo}">' if logo else ""
    brand_name = html_escape(str(content.get("title") or title or "Cadu"), quote=True)
    brand_header = ""
    if logo and not re.search(r"<img\b", body, flags=re.IGNORECASE):
        brand_header = f'<header data-cadu-brand-header class="mx-auto flex w-full max-w-6xl items-center gap-3 border-b border-slate-200 px-6 py-4" style="border-bottom-color:var(--cadu-brand-primary,#176b5e)"><img src="{logo}" alt="" class="h-8 w-auto object-contain"><span class="text-sm font-semibold text-slate-700">{brand_name}</span></header>'
    document = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta http-equiv="Content-Security-Policy" content="sandbox allow-scripts; default-src 'self'; img-src 'self' https: data: blob:; style-src 'self' 'unsafe-inline' {public_origin}; script-src 'unsafe-inline'; connect-src 'none'; font-src https: data:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
{favicon}<link rel="stylesheet" href="{artifact_stylesheet}"><style>:root{{{theme}}}html,body{{margin:0;min-height:100%;background:#f8fafc}}{css}</style></head>
<body>{brand_header}{body}<script>{javascript}</script></body></html>"""
    response = Response(document, mimetype="text/html")
    response.headers["Content-Security-Policy"] = f"sandbox allow-scripts; default-src 'self'; img-src 'self' https: data: blob:; style-src 'self' 'unsafe-inline' {public_origin}; script-src 'unsafe-inline'; connect-src 'none'; font-src https: data:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
