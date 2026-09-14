"""Link público e QR do planejamento — documento Centralcomm."""

from __future__ import annotations

import io
import os
import re
import secrets

from flask import has_request_context, url_for

from .helpers import text

HOUSE = {
    "name": "Centralcomm",
    "logo": "/static/images/cc_logo.png",
    "site": "https://centralcomm.media",
    "label": "Planejamento de mídia",
}


def make_public_token() -> str:
    return secrets.token_urlsafe(10)


def public_path(public_token: str) -> str:
    return f"/smart-planner/p/{text(public_token)}"


def public_document_path(public_token: str, document: str) -> str:
    suffix = "plano" if text(document) == "full_plan" else "proposta"
    return f"{public_path(public_token)}/{suffix}"


def public_sheet_url(public_token: str) -> str:
    token = text(public_token)
    if not token:
        return ""
    if has_request_context():
        try:
            return url_for("smart_planner.publico", public_token=token, _external=True)
        except Exception:
            pass
    base = text(os.getenv("BASE_URL")).rstrip("/")
    path = public_path(token)
    return f"{base}{path}" if base else path


def public_document_url(public_token: str, document: str) -> str:
    token = text(public_token)
    if not token:
        return ""
    suffix = "plano" if text(document) == "full_plan" else "proposta"
    if has_request_context():
        try:
            return url_for(f"smart_planner.publico_{suffix}", public_token=token, _external=True)
        except Exception:
            pass
    base = text(os.getenv("BASE_URL")).rstrip("/")
    path = public_document_path(token, document)
    return f"{base}{path}" if base else path


def share_payload(public_token: str, client: str = "") -> dict:
    token = text(public_token) or make_public_token()
    url = public_sheet_url(token)
    return {
        "public_token": token,
        "path": public_path(token),
        "url": url,
        "proposal_url": public_document_url(token, "proposal"),
        "full_plan_url": public_document_url(token, "full_plan"),
        "label": "Abrir o planejamento",
        "pdf_label": "Salvar PDF",
        "title": text(client) or "Página única",
    }


def qr_svg(data: str, scale: int = 4) -> str:
    payload = text(data)
    if not payload:
        return ""
    try:
        import segno
    except ImportError:
        return ""
    qr = segno.make(payload, error="m")
    if hasattr(qr, "svg_inline"):
        return qr.svg_inline(scale=scale, border=2, dark="#111111", light="#ffffff")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", xmldecl=False, scale=scale, border=2, dark="#111111", light="#ffffff")
    return buffer.getvalue().decode("utf-8")


def slug_token(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text(value).lower()).strip("-")
    return slug[:32] or make_public_token()
