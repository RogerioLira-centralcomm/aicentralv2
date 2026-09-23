"""Tenant-scoped brand workflows shared by Cadu's internal MCP transport."""

from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4
import json
import re

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from ..cadu_family import repository as family_repository
from ..db import get_db
from ..product_domains import product_url
from .agent_v2.contracts import RequestContext


UPLOAD_MAX_AGE = 600

BRAND_IDENTITY_TEXT_FIELDS = frozenset({
    "brand_summary", "positioning", "target_audience", "tone_of_voice",
    "creative_guidelines",
})
BRAND_IDENTITY_LIST_FIELDS = frozenset({
    "products_services", "differentiators", "proof_points", "ad_segments",
    "campaign_opportunities", "visual_motifs", "mandatory_elements",
    "forbidden_elements",
})


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


def _current_brand_id(context: RequestContext, brand_id=None) -> int:
    if brand_id is not None:
        try:
            return int(brand_id)
        except (TypeError, ValueError) as exc:
            raise BadRequest("Marca inválida.") from exc
    if str(context.brand_ref or "").startswith("studio:"):
        try:
            return int(str(context.brand_ref)[7:])
        except ValueError as exc:
            raise BadRequest("Marca ativa inválida.") from exc
    if context.project_ref:
        linked = {str(item.get("brand_ref") or "") for item in family_repository.project_brand_links(context.client_id)
                  if str(item.get("project_ref") or "") == context.project_ref}
        if len(linked) == 1:
            ref = next(iter(linked))
            if ref.startswith("studio:") and ref[7:].isdigit():
                return int(ref[7:])
    raise BadRequest("Informe brand_id ou selecione uma marca ativa.")


def list_assets(context: RequestContext, brand_id=None, limit: int = 50) -> dict:
    brand = _brand(context, _current_brand_id(context, brand_id))
    from .routes import _existing_brand_asset_url
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT id, role, source_kind, source_url, asset_path, mime_type,
                                 is_primary, status, metadata
                            FROM cx_client_brand_assets
                           WHERE client_id=%s AND status='approved'
                        ORDER BY is_primary DESC, id DESC LIMIT %s""",
                       (int(brand["id"]), min(100, max(1, int(limit or 50)))))
        rows = cursor.fetchall()
    assets = []
    for row in rows:
        metadata = row.get("metadata") or {}
        metadata = metadata if isinstance(metadata, dict) else {}
        assets.append({"asset_id": int(row["id"]), "role": row.get("role"),
                       "is_primary": bool(row.get("is_primary")), "mime_type": row.get("mime_type"),
                       "display_name": metadata.get("display_name") or metadata.get("alt_text") or "",
                       "preview_url": _existing_brand_asset_url(row.get("asset_path") or row.get("source_url"))})
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}", "assets": assets}


def use_asset_as_logo(context: RequestContext, *, brand_id, asset_id) -> dict:
    _require_admin(context)
    brand = _brand(context, _current_brand_id(context, brand_id))
    from ..creative_modeling_repository import CreativeNotFoundError
    from ..creative_modeling_service import CreativeModelingService
    try:
        selected = CreativeModelingService().promote_client_brand_asset_to_logo(int(brand["id"]), int(asset_id))
    except (CreativeNotFoundError, ValueError) as exc:
        raise BadRequest("Escolha uma imagem aprovada da biblioteca desta marca.") from exc
    from .routes import _existing_brand_asset_url
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "asset_id": int(asset_id), "status": "primary_logo",
            "logo_url": _existing_brand_asset_url(selected.get("asset_path")), "asset": selected}


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


def inspect_site(context: RequestContext, website_url: str = "", logo_url: str = "", brand_id=None) -> dict:
    # Context is intentionally required even though this read does not persist anything:
    # transports must still authenticate and scope the caller to the tenant.
    if not str(website_url or "").strip():
        brand = _brand(context, _current_brand_id(context, brand_id))
        website_url = brand.get("website_url") or ""
        logo_url = logo_url or brand.get("display_logo") or brand.get("logo_url") or ""
    from .brand_site_inspector import inspect_brand_site
    return inspect_brand_site(website_url, logo_url=logo_url)


def create_brand(context: RequestContext, *, request_id, name: str, website_url: str, sector: str,
                 official_logo_url: str = "", reference_urls=None) -> dict:
    _require_admin(context)
    operation_id = _request_id(request_id)
    website_url = _website(website_url)
    name = " ".join(str(name or "").split())[:150]
    if len(name) < 2:
        raise BadRequest("Informe um nome de marca com ao menos dois caracteres.")
    sector = " ".join(str(sector or "").split())[:80]
    if len(sector) < 2:
        raise BadRequest("Informe o segmento da marca.")
    official_logo_url = _website(official_logo_url) if str(official_logo_url or "").strip() else ""
    reference_urls = list(dict.fromkeys(
        _website(item) for item in (reference_urls or []) if str(item or "").strip()
    ))[:12]
    # A retry with the same request id must not depend on the external site
    # still being online. The transaction repeats this check under a lock to
    # protect simultaneous first attempts.
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, name, website_url FROM cx_clients
                 WHERE crm_client_id = %s AND brand_profile->>'mcp_request_id' = %s LIMIT 1""",
            (context.client_id, operation_id),
        )
        replay = cursor.fetchone()
    if replay:
        uploads = {"logo": prepare_asset_upload(context, int(replay["id"]), "logo"),
                   "reference": prepare_asset_upload(context, int(replay["id"]), "reference")}
        return {"brand_id": int(replay["id"]), "brand_ref": f"studio:{replay['id']}",
                "project_ref": None, "name": replay["name"], "website_url": replay["website_url"],
                "created": False, "detail_url": product_url("workspace", f"/marcas/{replay['id']}"),
                "artifact": {"type": "brand_identity", "brand_ref": f"studio:{replay['id']}",
                             "title": f"Identidade — {replay['name']}"}, "uploads": uploads}
    inspection = inspect_site(context, website_url, official_logo_url)
    explicit_logo = inspection.get("explicit_logo") or {}
    if explicit_logo.get("unsafe"):
        raise BadRequest("O link informado para a logo não aponta para um endereço público seguro.")
    inspection_status = ("verified" if inspection.get("ready_for_analysis")
                         and (not official_logo_url or explicit_logo.get("valid_image")) else "pending")
    profile = {"mcp_request_id": operation_id, "created_via": "cadu_mcp",
               "market_seed": {"sector": sector, "priorities": ["market", "audience", "competitors", "category_context"]}}
    metadata = {"sources": [website_url, *reference_urls], "site_inspection": {**inspection, "status": inspection_status},
                "submitted_assets": {"official_logo_url": official_logo_url or None,
                                     "reference_urls": reference_urls,
                                     "status": "awaiting_upload_or_verification"},
                "analysis_seed": {"sector": sector, "prioritize": ["market", "audience", "competitors", "category_context"]}}
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
                uploads = {"logo": prepare_asset_upload(context, int(existing["id"]), "logo"),
                           "reference": prepare_asset_upload(context, int(existing["id"]), "reference")}
                return {"brand_id": int(existing["id"]), "brand_ref": f"studio:{existing['id']}",
                        "project_ref": None, "name": existing["name"],
                        "website_url": existing["website_url"], "created": False,
                        "detail_url": product_url("workspace", f"/marcas/{existing['id']}"),
                        "artifact": {"type": "brand_identity", "brand_ref": f"studio:{existing['id']}",
                                     "title": f"Identidade — {existing['name']}"},
                        "uploads": uploads}
            cursor.execute(
                """INSERT INTO cx_clients
                       (crm_client_id, name, sector, website_url, brand_profile, analysis_metadata, price_policy)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, 'hide_price') RETURNING id""",
                (context.client_id, name, sector, website_url, json.dumps(profile), json.dumps(metadata)),
            )
            brand_id = int(cursor.fetchone()["id"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    detail_url = product_url("workspace", f"/marcas/{brand_id}")
    uploads = {"logo": prepare_asset_upload(context, brand_id, "logo"),
               "reference": prepare_asset_upload(context, brand_id, "reference")}
    return {"brand_id": brand_id, "brand_ref": f"studio:{brand_id}", "project_ref": None,
            "name": name, "website_url": website_url, "created": True,
            "detail_url": detail_url,
            "artifact": {"type": "brand_identity", "brand_ref": f"studio:{brand_id}",
                         "title": f"Identidade — {name}"},
            "uploads": uploads, "site_inspection": inspection,
            "onboarding": {
                "current_step": "logo",
                "steps": ["brand_created", "primary_logo", "audit_mode", "audit_review"],
                "audit_modes": ["complete", "deep"],
                "message": "Marca criada. Envie o logo principal e escolha a auditoria completa ou profunda.",
            }}


def update_identity(context: RequestContext, *, request_id, brand_id, changes: dict) -> dict:
    """Apply an explicit partial identity patch without replacing other fields."""
    _require_admin(context)
    operation_id = _request_id(request_id)
    brand = _brand(context, brand_id)
    if not isinstance(changes, dict) or not changes:
        raise BadRequest("Informe ao menos um campo da identidade para alterar.")
    allowed = {"name", "sector", "website_url", "primary_color", "secondary_color"} | BRAND_IDENTITY_TEXT_FIELDS | BRAND_IDENTITY_LIST_FIELDS
    unknown = sorted(set(changes) - allowed)
    if unknown:
        raise BadRequest("Campos de identidade não reconhecidos: " + ", ".join(unknown))

    normalized = {}
    for field, value in changes.items():
        if field == "name":
            value = " ".join(str(value or "").split())[:150]
            if len(value) < 2:
                raise BadRequest("O nome da marca precisa ter ao menos dois caracteres.")
        elif field == "sector":
            value = " ".join(str(value or "").split())[:80] or None
        elif field == "website_url":
            value = _website(value) if str(value or "").strip() else None
        elif field in {"primary_color", "secondary_color"}:
            value = str(value or "").strip().upper() or None
            if value and not re.fullmatch(r"#[0-9A-F]{6}", value):
                raise BadRequest("Use cores no formato hexadecimal, como #176B5E.")
        elif field in BRAND_IDENTITY_TEXT_FIELDS:
            value = str(value or "").strip()[:4000]
        elif field in BRAND_IDENTITY_LIST_FIELDS:
            if not isinstance(value, list):
                raise BadRequest(f"O campo {field} precisa ser uma lista.")
            value = [" ".join(str(item).split())[:300] for item in value if str(item).strip()][:12]
        normalized[field] = value

    columns = {field: normalized[field] for field in ("name", "sector", "website_url", "primary_color", "secondary_color") if field in normalized}
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            # Serialize partial edits and build the patch from the latest row.
            # Reading before the transaction allowed two edits to different
            # fields to replace each other's profile/history snapshots.
            cursor.execute(
                """SELECT brand_profile, analysis_metadata
                     FROM cx_clients
                    WHERE id = %s AND crm_client_id = %s
                    FOR UPDATE""",
                (int(brand["id"]), context.client_id),
            )
            locked = cursor.fetchone()
            if not locked:
                raise NotFound("Marca indisponível.")
            profile = locked.get("brand_profile") or {}
            metadata = locked.get("analysis_metadata") or {}
            if isinstance(profile, str):
                profile = json.loads(profile)
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            profile = dict(profile) if isinstance(profile, dict) else {}
            metadata = dict(metadata) if isinstance(metadata, dict) else {}
            history = list(metadata.get("identity_edit_history") or [])
            if any(item.get("request_id") == operation_id for item in history if isinstance(item, dict)):
                connection.commit()
                return {"brand_id": int(brand["id"]), "updated_fields": sorted(normalized), "updated": False}
            for field in BRAND_IDENTITY_TEXT_FIELDS | BRAND_IDENTITY_LIST_FIELDS:
                if field in normalized:
                    profile[field] = normalized[field]
            profile["last_edited_via"] = "cadu_mcp"
            if "name" in normalized:
                profile["name_autogenerated"] = False
            history.append({"request_id": operation_id, "source": "cadu_mcp", "user_id": context.user_id,
                            "fields": sorted(normalized), "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
            metadata["identity_edit_history"] = history[-50:]
            cursor.execute(
                """UPDATE cx_clients
                      SET name = COALESCE(%s, name), sector = CASE WHEN %s THEN %s ELSE sector END,
                          website_url = CASE WHEN %s THEN %s ELSE website_url END,
                          primary_color = CASE WHEN %s THEN %s ELSE primary_color END,
                          secondary_color = CASE WHEN %s THEN %s ELSE secondary_color END,
                          tone_of_voice = CASE WHEN %s THEN %s ELSE tone_of_voice END,
                          brand_profile = %s::jsonb, analysis_metadata = %s::jsonb, updated_at = NOW()
                    WHERE id = %s AND crm_client_id = %s RETURNING id""",
                (columns.get("name"), "sector" in columns, columns.get("sector"),
                 "website_url" in columns, columns.get("website_url"),
                 "primary_color" in columns, columns.get("primary_color"),
                 "secondary_color" in columns, columns.get("secondary_color"),
                 "tone_of_voice" in normalized, normalized.get("tone_of_voice"),
                 json.dumps(profile), json.dumps(metadata), int(brand["id"]), context.client_id),
            )
            if not cursor.fetchone():
                raise NotFound("Marca indisponível.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "updated_fields": sorted(normalized), "updated": True}


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="cadu-mcp-brand-logo-v1")


def prepare_logo_upload(context: RequestContext, brand_id) -> dict:
    return prepare_asset_upload(context, brand_id, "logo")


BRAND_ASSET_ROLES = frozenset({"logo", "reference", "creative", "background", "support", "icon"})


def prepare_asset_upload(context: RequestContext, brand_id, role: str = "reference") -> dict:
    _require_admin(context)
    brand = _brand(context, brand_id)
    role = str(role or "reference").strip().lower()
    if role not in BRAND_ASSET_ROLES:
        raise BadRequest("Tipo de ativo de marca inválido.")
    token = _serializer().dumps({"client_id": context.client_id, "user_id": context.user_id,
                                 "brand_id": int(brand["id"]), "role": role})
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "upload_token": token, "upload_url": "/workspace/mcp/brand-uploads", "method": "POST",
            "field": "file", "accepted": [".png", ".jpg", ".jpeg", ".webp"],
            "max_bytes": 5 * 1024 * 1024, "expires_in": UPLOAD_MAX_AGE,
            "role": role, "purpose": ("replace_primary_logo" if brand.get("display_logo") or brand.get("logo_url")
                                       else "set_primary_logo") if role == "logo" else "add_brand_asset"}


def save_logo_upload(context: RequestContext, token: str, uploaded) -> dict:
    _require_admin(context)
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
        raise BadRequest("Envie o ativo no campo file.")
    role = str(claims.get("role") or "logo").lower()
    if role not in BRAND_ASSET_ROLES:
        raise BadRequest("Tipo de ativo de marca inválido.")
    from ..creative_modeling_service import CreativeModelingService
    try:
        assets = CreativeModelingService().upload_client_brand_assets(
            int(brand["id"]), [uploaded], role == "logo", role,
        )
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "status": "uploaded", "role": role, "assets": assets or []}


def delete_asset(context: RequestContext, *, brand_id, asset_id) -> dict:
    _require_admin(context)
    brand = _brand(context, brand_id)
    from ..creative_modeling_service import CreativeModelingService
    try:
        CreativeModelingService().delete_brand_asset(int(brand["id"]), int(asset_id))
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "asset_id": int(asset_id), "deleted": True}


def start_audit(context: RequestContext, *, request_id, brand_id=None, website_url: str = "", analysis_mode: str = "complete", social_links=None, additional_sources=None, excluded_sources=None, confirmed_cost: bool = False, existing_asset_ids=None) -> dict:
    _require_admin(context)
    operation_id = _request_id(request_id)
    if not confirmed_cost:
        raise BadRequest("Confirme o custo estimado antes de iniciar a auditoria.")
    analysis_mode = "deep" if str(analysis_mode).lower() == "deep" else "complete"
    social_links = [str(item).strip()[:500] for item in (social_links or []) if str(item).strip()][:12]
    additional_sources = list(dict.fromkeys(_website(item) for item in (additional_sources or []) if str(item).strip()))[:12]
    excluded_sources = list(dict.fromkeys(_website(item) for item in (excluded_sources or []) if str(item).strip()))[:12]
    estimate = {"estimated_tokens": 150000 if analysis_mode == "deep" else 75000,
                "estimated_credits": 150000 if analysis_mode == "deep" else 75000,
                "estimated_time": "6–12 min" if analysis_mode == "deep" else "3–8 min"}
    brand = _brand(context, _current_brand_id(context, brand_id))
    selected_asset_ids = None
    if existing_asset_ids is None:
        approved_assets = [item for item in (brand.get("assets") or [])
                           if str(item.get("status") or "").lower() == "approved"
                           and (item.get("asset_path") or item.get("source_url"))]
        approved_assets.sort(key=lambda item: (not bool(item.get("is_primary")),
                                               -float(item.get("score") or 0), -int(item.get("id") or 0)))
        if approved_assets:
            selected_asset_ids = [int(item["id"]) for item in approved_assets[:12 if analysis_mode == "deep" else 8]]
    else:
        try:
            selected_asset_ids = list(dict.fromkeys(int(value) for value in existing_asset_ids))[:12]
        except (TypeError, ValueError) as exc:
            raise BadRequest("Informe IDs válidos de imagens da biblioteca.") from exc
        if any(value <= 0 for value in selected_asset_ids):
            raise BadRequest("Informe IDs válidos de imagens da biblioteca.")
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT id FROM cx_client_brand_assets
                               WHERE client_id=%s AND status='approved' AND id=ANY(%s)""",
                           (int(brand["id"]), selected_asset_ids))
            owned_ids = {int(row["id"]) for row in cursor.fetchall()}
            if owned_ids != set(selected_asset_ids):
                raise BadRequest("Uma das imagens não pertence à biblioteca aprovada desta marca.")
            if selected_asset_ids:
                cursor.execute("""SELECT id FROM cx_client_brand_assets
                                   WHERE client_id=%s AND status='approved' AND role='logo'
                                     AND is_primary=true ORDER BY id DESC LIMIT 1""", (int(brand["id"]),))
                primary = cursor.fetchone()
                if primary and int(primary["id"]) not in owned_ids:
                    selected_asset_ids = selected_asset_ids[:11] + [int(primary["id"])]
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
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "input": {"website_url": website_url, "has_images": bool(selected_asset_ids), "include_project_sources": False, "analysis_mode": analysis_mode, "social_links": social_links, "additional_sources": additional_sources, "excluded_sources": excluded_sources, "existing_asset_ids": selected_asset_ids, "cost_confirmed": True, **estimate},
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
    _start_brand_review_job(context.client_id, context.user_id, int(brand["id"]), job_id, website_url, [], analysis_mode=analysis_mode, social_links=social_links, additional_sources=additional_sources, excluded_sources=excluded_sources, existing_asset_ids=selected_asset_ids)
    return {"brand_id": int(brand["id"]), "brand_ref": f"studio:{brand['id']}",
            "brand_name": brand.get("name"), "scope": "brand", "project_context_changed": False,
            "job_id": job_id, "status": "queued", "queued": True,
            "analysis_mode": analysis_mode, "additional_sources": additional_sources, "excluded_sources": excluded_sources, "existing_asset_ids": selected_asset_ids, "cost_authorized": True, **estimate,
            "status_url": f"/workspace/app/marcas/{brand['id']}/auditoria/status"}


def audit_status(context: RequestContext, brand_id) -> dict:
    brand = _brand(context, brand_id)
    from .routes import (
        BRAND_ANALYSIS_ENRICHMENT_TARGET,
        BRAND_ANALYSIS_PUBLICATION_THRESHOLD,
        _brand_audit_history,
        _brand_review_pack,
    )
    pack = _brand_review_pack(brand)
    status = pack.get("status") or "not_started"
    metadata = brand.get("analysis_metadata") if isinstance(brand.get("analysis_metadata"), dict) else {}
    decision = metadata.get("automatic_decision") if isinstance(metadata.get("automatic_decision"), dict) else {}
    history = _brand_audit_history(context.client_id, int(brand["id"])) if status not in {"not_started", "queued", "running"} else []
    latest = next((item for item in history if not pack.get("job_id") or item.get("job_id") == pack.get("job_id")), history[0] if history else {})
    return {"brand_id": int(brand["id"]), "status": status,
            "stage": pack.get("stage") or "", "progress": {"current": pack.get("index", 0), "total": pack.get("total", 4)},
            "message": pack.get("message") or "", "error": pack.get("error") or "",
            "result": "ready_for_use" if status == "approved" else "enrichment_recommended" if status == "insufficient_evidence" else status,
            "published": status == "approved", "analysis_mode": latest.get("analysis_mode") or (pack.get("input") or {}).get("analysis_mode"),
            "quality_level": decision.get("quality_level"),
            "publication_threshold": decision.get("publication_threshold", BRAND_ANALYSIS_PUBLICATION_THRESHOLD),
            "enrichment_target": decision.get("enrichment_target", BRAND_ANALYSIS_ENRICHMENT_TARGET),
            "costs": latest.get("costs") or {}}
