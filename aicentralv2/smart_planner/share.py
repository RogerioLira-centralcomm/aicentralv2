"""Link público e QR do quadro no CentralX."""

from __future__ import annotations

import io
import os
import re
import secrets

from flask import has_request_context, url_for

from .helpers import text


def make_public_token() -> str:
    return secrets.token_urlsafe(10)


def public_path(public_token: str) -> str:
    return f"/smart-planner/p/{text(public_token)}"


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


def share_payload(public_token: str, client: str = "") -> dict:
    token = text(public_token) or make_public_token()
    url = public_sheet_url(token)
    return {
        "public_token": token,
        "path": public_path(token),
        "url": url,
        "label": "Quadro completo",
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
