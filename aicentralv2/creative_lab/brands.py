"""Workspace brands and their audit as Lab payload (read-only).

``brand_snapshot`` gathers everything the Workspace knows about a brand — profile, the latest status
of every audited field, approved assets with public URLs — and ``readiness`` judges whether that is
enough to test with or whether the brand needs a new audit first. The snapshot is frozen into each
experiment so later audits never change old results.
"""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from flask import current_app

from ..db import get_db

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
AUDIT_MAX_AGE_DAYS = 180
TEXT_FIELDS = ("brand_summary", "tone_of_voice", "target_audience", "positioning", "creative_guidelines")
LIST_FIELDS = ("products_services", "differentiators", "mandatory_elements", "forbidden_elements", "visual_motifs")


def plain(value, limit=600) -> str:
    """Readable text from the mixed shapes the audit stores (str, list of dicts, python repr strings)."""
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith(("[{", "{'")):
            try:
                return plain(ast.literal_eval(raw), limit)
            except (ValueError, SyntaxError):
                pass
        return raw[:limit]
    if isinstance(value, dict):
        for key in ("value", "label", "segment", "name", "family", "address"):
            if value.get(key):
                return plain(value[key], limit)
        return ""
    if isinstance(value, (list, tuple)):
        parts = [plain(item, limit) for item in value]
        return "; ".join(part for part in parts if part)[:limit]
    return "" if value is None else str(value)[:limit]


def plain_list(value, limit=10, item_limit=200) -> list[str]:
    if isinstance(value, str) and value.strip().startswith(("[", "{")):
        try:
            value = ast.literal_eval(value.strip())
        except (ValueError, SyntaxError):
            return [value.strip()[:item_limit]]
    if isinstance(value, str):
        return [value.strip()[:item_limit]] if value.strip() else []
    if not isinstance(value, (list, tuple)):
        return []
    items = [plain(item, item_limit) for item in value]
    return [item for item in dict.fromkeys(items) if item][:limit]


def palette(profile: dict, row: dict) -> list[dict]:
    colors = []
    for item in profile.get("color_palette") or []:
        if isinstance(item, dict) and HEX.match(str(item.get("hex") or "")):
            colors.append({"hex": item["hex"].upper(), "name": plain(item.get("name"), 60),
                           "usage": plain(item.get("usage"), 120), "confidence": item.get("confidence")})
        elif isinstance(item, str) and HEX.match(item):
            colors.append({"hex": item.upper(), "name": "", "usage": "", "confidence": None})
    for key, name in (("primary_color", "primária"), ("secondary_color", "secundária")):
        value = str(row.get(key) or "")
        if HEX.match(value) and value.upper() not in {color["hex"] for color in colors}:
            colors.append({"hex": value.upper(), "name": name, "usage": "", "confidence": None})
    return colors[:8]


def fonts(profile: dict) -> list[dict]:
    items = []
    for item in profile.get("fonts") or []:
        if isinstance(item, dict) and item.get("family"):
            items.append({"family": plain(item["family"], 60), "role": plain(item.get("role"), 40)})
        elif isinstance(item, str) and item.strip():
            items.append({"family": item.strip()[:60], "role": ""})
    return items[:4]


def asset_public_url(path_or_url: str) -> str:
    value = str(path_or_url or "").strip()
    if value.startswith(("https://", "http://")):
        return value
    if value.startswith("/static/"):
        base = str(current_app.config.get("STUDIO_URL") or "").strip()
        return urljoin(base.rstrip("/") + "/", value.lstrip("/")) if base else value
    return ""


def list_brands(client_id: int) -> list[dict]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT c.id, c.name, c.sector, c.primary_color, c.secondary_color,
                      COALESCE(c.logo_upload_path, c.logo_url) AS logo,
                      (SELECT count(DISTINCT f.field_name) FROM cadu_workspace_brand_identity_fields f
                        WHERE f.brand_id = c.id AND f.client_id = c.crm_client_id AND f.status = 'verified') AS verified_fields,
                      (SELECT count(*) FROM cadu_workspace_brand_audit_runs r WHERE r.brand_id = c.id) AS audits,
                      (SELECT max(r.created_at) FROM cadu_workspace_brand_audit_runs r WHERE r.brand_id = c.id) AS last_audit_at,
                      (SELECT count(*) FROM cx_client_brand_assets a WHERE a.client_id = c.id AND a.status = 'approved') AS assets
                 FROM cx_clients c
                WHERE c.crm_client_id = %s
                ORDER BY verified_fields DESC, audits DESC, c.name""",
            (client_id,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    for row in rows:
        row["logo_url"] = asset_public_url(row.pop("logo"))
        row["sector"] = plain(row.get("sector"), 80)
        row["last_audit_at"] = row["last_audit_at"].isoformat() if row.get("last_audit_at") else None
    return rows


def _identity_fields(cursor, client_id: int, brand_id: int) -> dict:
    cursor.execute(
        """SELECT DISTINCT ON (field_name) field_name, status, confidence, evidence_count, last_verified_at
             FROM cadu_workspace_brand_identity_fields
            WHERE client_id = %s AND brand_id = %s
            ORDER BY field_name, last_verified_at DESC NULLS LAST, id DESC""",
        (client_id, brand_id),
    )
    return {row["field_name"]: {
        "status": row["status"],
        "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
        "evidence": row["evidence_count"],
    } for row in cursor.fetchall()}


def role_is_logo(asset) -> bool:
    return str(asset.get("role") or "") == "logo"


def brand_snapshot(client_id: int, brand_id: int) -> dict:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, name, sector, website_url, primary_color, secondary_color, logo_url, logo_upload_path,
                      brand_profile, analysis_metadata
                 FROM cx_clients WHERE id = %s AND crm_client_id = %s""",
            (brand_id, client_id),
        )
        row = cursor.fetchone()
        if not row:
            raise LookupError("Marca não encontrada nesta organização.")
        row = dict(row)
        fields = _identity_fields(cursor, client_id, brand_id)
        cursor.execute(
            """SELECT id, role, COALESCE(asset_path, source_url) AS path, width, height, is_primary, metadata
                 FROM cx_client_brand_assets
                WHERE client_id = %s AND status = 'approved'
                  AND COALESCE(metadata->>'logo_variant', '') = ''
                ORDER BY (role = 'logo') DESC, is_primary DESC, score DESC NULLS LAST, id""",
            (brand_id,),
        )
        assets = []
        for asset in cursor.fetchall():
            url = asset_public_url(asset["path"])
            if url and (role_is_logo(asset) or not url.lower().split("?")[0].endswith(".svg")):
                assets.append({"asset_id": asset["id"], "role": asset["role"], "url": url,
                               "is_primary": asset["is_primary"], "width": asset["width"], "height": asset["height"]})
        cursor.execute(
            """SELECT job_id, analysis_mode, status, created_at, completed_at
                 FROM cadu_workspace_brand_audit_runs WHERE client_id = %s AND brand_id = %s
                ORDER BY created_at DESC LIMIT 1""",
            (client_id, brand_id),
        )
        audit = cursor.fetchone()
    profile = dict(row.get("brand_profile") or {})
    logo_path = row.get("logo_upload_path") or row.get("logo_url") or ""
    logo_url = asset_public_url(logo_path)
    # An SVG logo stays: the Studio rasterizes it (CairoSVG) to compose it; a raster logo of the brand wins when it has one.
    if logo_url.lower().split("?")[0].endswith(".svg"):
        raster = next((item["url"] for item in assets if item["role"] == "logo"
                       and not item["url"].lower().split("?")[0].endswith(".svg")), "")
        logo_url = raster or logo_url
    if not logo_url:
        logo_url = next((item["url"] for item in assets if item["role"] == "logo"), "")
    snapshot = {
        "brand_id": brand_id, "name": row["name"], "sector": plain(row.get("sector"), 80),
        "website_url": row.get("website_url") or "",
        "logo_url": logo_url,
        "palette": palette(profile, row),
        "fonts": fonts(profile),
        "text": {key: plain(profile.get(key), 700) for key in TEXT_FIELDS},
        "lists": {key: plain_list(profile.get(key)) for key in LIST_FIELDS},
        "fields": fields,
        "assets": assets,
        "audit": {
            "job_id": audit["job_id"], "mode": audit["analysis_mode"], "status": audit["status"],
            "created_at": audit["created_at"].isoformat(),
        } if audit else None,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }
    snapshot["readiness"] = readiness(snapshot)
    return snapshot


def field_status(snapshot: dict, name: str) -> str:
    return (snapshot.get("fields", {}).get(name) or {}).get("status") or "unknown"


def readiness(snapshot: dict) -> dict:
    """Deterministic gate: is there enough brand to judge brand fidelity in a generated image?"""
    checks = []

    def check(key, label, ok, required, detail=""):
        checks.append({"key": key, "label": label, "ok": bool(ok), "required": required, "detail": detail})

    verified = sorted(name for name, item in snapshot.get("fields", {}).items() if item.get("status") == "verified")
    colors = snapshot.get("palette") or []
    audit = snapshot.get("audit") or {}
    age_days = None
    if audit.get("created_at"):
        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(audit["created_at"])).days
    check("logo", "Logo oficial em imagem (PNG/JPG/WEBP)", snapshot.get("logo_url"), True,
          "" if snapshot.get("logo_url") else "Sem logo raster; SVG externo não serve de referência.")
    check("palette", "Paleta com 2+ cores", len(colors) >= 2, True, f"{len(colors)} cor(es)")
    check("summary", "Resumo da marca", snapshot["text"].get("brand_summary"), True)
    check("audit", "Auditoria executada", audit, True, f"há {age_days} dias" if age_days is not None else "nunca")
    check("verified", "5+ campos verificados", len(verified) >= 5, False, f"{len(verified)} verificados")
    check("guidelines", "Diretriz criativa ou elementos obrigatórios",
          snapshot["text"].get("creative_guidelines") or snapshot["lists"].get("mandatory_elements"), False)
    check("forbidden", "Elementos proibidos", snapshot["lists"].get("forbidden_elements"), False)
    check("tone", "Tom de voz", snapshot["text"].get("tone_of_voice"), False)
    check("fresh", f"Auditoria com menos de {AUDIT_MAX_AGE_DAYS} dias",
          age_days is not None and age_days <= AUDIT_MAX_AGE_DAYS, False)
    check("references", "Imagens de referência aprovadas", any(item["role"] != "logo" for item in snapshot.get("assets", [])), False)

    missing_required = [item["label"] for item in checks if item["required"] and not item["ok"]]
    optional_ok = sum(1 for item in checks if not item["required"] and item["ok"])
    optional_total = sum(1 for item in checks if not item["required"])
    if missing_required:
        level, summary = "needs_audit", "Precisa de nova auditoria: " + ", ".join(missing_required).lower() + "."
    elif optional_ok < optional_total - 2:
        level, summary = "partial", "Dá para testar, mas a fidelidade de marca será julgada com pouca evidência."
    else:
        level, summary = "ready", "Pronta para testes de fidelidade de marca."
    return {"level": level, "summary": summary, "checks": checks, "verified_fields": verified,
            "score": round((sum(1 for item in checks if item["ok"]) / len(checks)) * 100)}


def payload_fields(snapshot: dict, policy: str = "verified_and_probable") -> dict:
    """The brand text that reaches the prompt, filtered by audit status (a test variable)."""
    allowed = {"verified"} if policy == "verified_only" else {"verified", "probable", "partial"} if policy == "verified_and_probable" else None

    def keep(name):
        return allowed is None or field_status(snapshot, name) in allowed or field_status(snapshot, name) == "unknown"

    data = {"name": snapshot["name"], "palette": [color["hex"] for color in snapshot.get("palette", [])],
            "fonts": [item["family"] for item in snapshot.get("fonts", [])]}
    for key, value in snapshot.get("text", {}).items():
        if value and keep(key):
            data[key] = value
    for key, value in snapshot.get("lists", {}).items():
        if value and keep(key):
            data[key] = value
    return data
