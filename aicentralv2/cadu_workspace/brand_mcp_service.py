"""Tenant-scoped brand workflows shared by Cadu's internal MCP transport."""

from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4
import json
import re

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from ..cadu_family import repository as family_repository
from ..db import get_db
from .agent_v2.contracts import RequestContext


UPLOAD_MAX_AGE = 600


def _request_id(value) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise BadRequest("Identificador da operação inválido.") from exc


def _require_admin(context: RequestContext) -> None:
    actor = family_repository.actor(context.user_id)
    if not actor or int(actor.get("organization_id") or 0) != context.client_id:
        raise Forbidden("A conta não pertence a esta organização.")
    if family_repository.account_role(actor) != "admin":
        raise Forbidden("Somente administradores podem iniciar a auditoria da marca.")


def _brand(context: RequestContext, brand_id) -> dict:
    try:
        value = int(brand_id)
    except (TypeError, ValueError) as exc:
        raise BadRequest("Marca inválida.") from exc
    from .routes import _workspace_brand
    brand = _workspace_brand(context.client_id, value)
    if not brand:
        raise NotFound("Marca indisponível.")
    return brand


def _website(value: str) -> str:
    url = str(value or "").strip()[:2000]
    if url and not re.match(r"^https?://", url, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
            raise BadRequest("Informe uma URL http ou https válida.")
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    if not url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BadRequest("Informe o site oficial da marca.")
    return url


def list_brands(context: RequestContext, query: str = "", limit: int = 30) -> list[dict]:
    from .routes import _workspace_brands
    records = _workspace_brands(context.client_id, str(query or "")[:100])
    return [{
        "brand_id": int(item["id"]), "brand_ref": f"studio:{item['id']}",
        "name": item.get("name"), "sector": item.get("sector"),
        "website_url": item.get("website_url"), "logo_url": item.get("display_logo"),
        "has_audit": bool(item.get("analysis_metadata")),
    } for item in records[:min(50, max(1, int(limit or 30)))]]


def brand_context(context: RequestContext, brand_id) -> dict:
    """Return the same source-aware context consumed by Workspace surfaces."""
    brand = _brand(context, brand_id)
    profile = dict(brand.get("brand_profile") or {})
    metadata = dict(brand.get("analysis_metadata") or {})
    from .routes import _brand_campaigns
    return {
        "brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
        "name": brand.get("name"), "website_url": brand.get("website_url"),
        "logo_url": brand.get("display_logo") or brand.get("logo_url"),
        "colors": {"primary": brand.get("primary_color"), "secondary": brand.get("secondary_color"),
                   "palette": profile.get("color_palette") or []},
        "fonts": profile.get("fonts") or [],
        "identity": {key: profile.get(key) for key in ("brand_summary", "tone_of_voice", "target_audience", "positioning", "mandatory_elements", "forbidden_elements", "visual_motifs")},
        "market": {key: profile.get(key) for key in ("products_services", "differentiators", "proof_points", "competitors")},
        "campaigns": _brand_campaigns(context.client_id, int(brand["id"]), profile.get("campaigns") or []),
        "sources": list(metadata.get("sources") or [])[:20], "social_links": list(metadata.get("social_links") or [])[:12],
        "field_provenance": profile.get("field_provenance") or {},
    }


def create_brand(context: RequestContext, *, request_id, name: str, website_url: str, sector: str = "") -> dict:
    operation_id = _request_id(request_id)
    website_url = _website(website_url)
    name = " ".join(str(name or "").split())[:150]
    if len(name) < 2:
        raise BadRequest("Informe um nome de marca com ao menos dois caracteres.")
    profile = {"mcp_request_id": operation_id, "created_via": "cadu_mcp"}
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("cadu-brand:" + operation_id,))
            cursor.execute(
                """SELECT id, name, website_url FROM cx_clients
                     WHERE crm_client_id = %s AND brand_profile->>'mcp_request_id' = %s LIMIT 1""",
                (context.client_id, operation_id),
            )
            existing = cursor.fetchone()
            if existing:
                connection.commit()  # Release the idempotency advisory lock before related reads.
                links = family_repository.project_brand_links(context.client_id)
                project_ref = next((str(item.get("project_ref") or "") for item in links
                                    if str(item.get("brand_ref") or "") == f"studio:{existing['id']}"), None)
                return {"brand_id": int(existing["id"]), "brand_ref": f"studio:{existing['id']}",
                        "project_ref": project_ref, "name": existing["name"],
                        "website_url": existing["website_url"], "created": False}
            cursor.execute(
                """INSERT INTO cx_clients
                       (crm_client_id, name, sector, website_url, brand_profile, analysis_metadata, price_policy)
                    VALUES (%s, %s, %s, %s, %s::jsonb, '{}'::jsonb, 'hide_price') RETURNING id""",
                (context.client_id, name, " ".join(str(sector or "").split())[:80] or None,
                 website_url, json.dumps(profile)),
            )
            brand_id = int(cursor.fetchone()["id"])
            project_id = str(uuid4())
            cursor.execute(
                """INSERT INTO cadu_ci_projetos
                       (id, id_cliente, criado_por, nome, descricao, instrucoes, tipo, cor, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'projeto', '#176b5e', 'ativo')""",
                (project_id, context.client_id, context.user_id, name,
                 f"Dossiê operacional da marca {name}.",
                 "Contexto de marca vinculado; decisões de campanha devem ser registradas neste projeto."),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    project_ref = f"ci:{project_id}"
    try:
        family_repository.set_project_brand_link(
            context.client_id, context.user_id, project_ref, f"studio:{brand_id}", True,
        )
    except Exception:
        current_app.logger.exception("Marca %s criada via MCP sem vínculo ao dossiê %s", brand_id, project_id)
        project_ref = None
    return {"brand_id": brand_id, "brand_ref": f"studio:{brand_id}", "project_ref": project_ref,
            "name": name, "website_url": website_url, "created": True}


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="cadu-mcp-brand-logo-v1")


def prepare_logo_upload(context: RequestContext, brand_id) -> dict:
    brand = _brand(context, brand_id)
    token = _serializer().dumps({"client_id": context.client_id, "user_id": context.user_id,
                                 "brand_id": int(brand["id"])})
    return {"upload_token": token, "upload_url": "/workspace/mcp/brand-uploads", "method": "POST",
            "field": "file", "accepted": [".png", ".jpg", ".jpeg", ".webp"],
            "max_bytes": 5 * 1024 * 1024, "expires_in": UPLOAD_MAX_AGE}


def save_logo_upload(context: RequestContext, token: str, uploaded) -> dict:
    try:
        claims = _serializer().loads(str(token or ""), max_age=UPLOAD_MAX_AGE)
    except SignatureExpired as exc:
        raise BadRequest("A autorização de upload expirou.") from exc
    except BadSignature as exc:
        raise BadRequest("Autorização de upload inválida.") from exc
    if not isinstance(claims, dict) or (claims.get("client_id"), claims.get("user_id")) != (context.client_id, context.user_id):
        raise BadRequest("A autorização de upload não pertence a este contexto.")
    brand = _brand(context, claims.get("brand_id"))
    if not uploaded or not uploaded.filename:
        raise BadRequest("Envie o logo no campo file.")
    from ..creative_modeling_service import CreativeModelingService
    try:
        assets = CreativeModelingService().upload_client_brand_assets(int(brand["id"]), [uploaded], True, "logo")
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "status": "uploaded", "assets": assets or []}


def start_audit(context: RequestContext, *, request_id, brand_id, website_url: str = "", analysis_mode: str = "complete", social_links=None, confirmed_cost: bool = False) -> dict:
    _require_admin(context)
    operation_id = _request_id(request_id)
    if not confirmed_cost:
        raise BadRequest("Confirme o custo estimado antes de iniciar a auditoria.")
    analysis_mode = "deep" if str(analysis_mode).lower() == "deep" else "complete"
    social_links = [str(item).strip()[:500] for item in (social_links or []) if str(item).strip()][:12]
    estimate = {"estimated_tokens": 150000 if analysis_mode == "deep" else 75000,
                "estimated_credits": 150000 if analysis_mode == "deep" else 75000,
                "estimated_time": "6–12 min" if analysis_mode == "deep" else "3–8 min"}
    brand = _brand(context, brand_id)
    from .routes import _ensure_brand_audit_credit, _start_brand_review_job
    website_url = _website(website_url or brand.get("website_url") or "")
    metadata = dict(brand.get("analysis_metadata") or {})
    current = metadata.get("review_pack") if isinstance(metadata.get("review_pack"), dict) else {}
    if current.get("request_id") == operation_id:
        return {"brand_id": int(brand["id"]), "job_id": current.get("job_id"),
                "status": current.get("status"), "queued": False}
    if current.get("status") in {"queued", "running"}:
        raise Conflict("Esta marca já possui uma auditoria em andamento.")
    _ensure_brand_audit_credit(context.client_id)
    job_id = uuid4().hex
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT analysis_metadata FROM cx_clients WHERE id = %s AND crm_client_id = %s FOR UPDATE",
                           (int(brand["id"]), context.client_id))
            locked = cursor.fetchone()
            if not locked:
                raise NotFound("Marca indisponível.")
            metadata = locked.get("analysis_metadata") or {}
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            current = metadata.get("review_pack") if isinstance(metadata.get("review_pack"), dict) else {}
            if current.get("request_id") == operation_id:
                connection.rollback()
                return {"brand_id": int(brand["id"]), "job_id": current.get("job_id"),
                        "status": current.get("status"), "queued": False}
            if current.get("status") in {"queued", "running"}:
                raise Conflict("Esta marca já possui uma auditoria em andamento.")
            metadata["review_pack"] = {
                "job_id": job_id, "request_id": operation_id, "status": "queued", "stage": "queued",
                "index": 0, "total": 4, "message": "A auditoria entrou na fila.", "error": "",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "input": {"website_url": website_url, "has_images": False, "include_project_sources": False, "analysis_mode": analysis_mode, "social_links": social_links, "cost_confirmed": True, **estimate},
                "analysis": {}, "reviews": [],
            }
            cursor.execute("""UPDATE cx_clients SET website_url = %s, analysis_metadata = %s::jsonb
                               WHERE id = %s AND crm_client_id = %s RETURNING id""",
                           (website_url, json.dumps(metadata), int(brand["id"]), context.client_id))
            if not cursor.fetchone():
                raise NotFound("Marca indisponível.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    _start_brand_review_job(context.client_id, context.user_id, int(brand["id"]), job_id, website_url, [], analysis_mode=analysis_mode, social_links=social_links)
    return {"brand_id": int(brand["id"]), "job_id": job_id, "status": "queued", "queued": True,
            "analysis_mode": analysis_mode, "cost_authorized": True, **estimate,
            "status_url": f"/workspace/app/marcas/{brand['id']}/auditoria/status"}


def audit_status(context: RequestContext, brand_id) -> dict:
    brand = _brand(context, brand_id)
    from .routes import _brand_review_pack
    pack = _brand_review_pack(brand)
    return {"brand_id": int(brand["id"]), "status": pack.get("status") or "not_started",
            "stage": pack.get("stage") or "", "progress": {"current": pack.get("index", 0), "total": pack.get("total", 4)},
            "message": pack.get("message") or "", "error": pack.get("error") or ""}
