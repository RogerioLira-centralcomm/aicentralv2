"""Slug público, preview token e QR da one-page Places."""

from __future__ import annotations

import io
import os
import re
import secrets

from flask import has_request_context, url_for


def text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def make_preview_token() -> str:
    return secrets.token_urlsafe(12)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text(value).lower()).strip("-")
    return slug[:80] or secrets.token_urlsafe(6).lower()


def public_path(slug: str) -> str:
    return f"/places/p/{text(slug)}"


def preview_path(token: str) -> str:
    return f"/places/preview/{text(token)}"


def public_url(slug: str) -> str:
    token = text(slug)
    if not token:
        return ""
    if has_request_context():
        try:
            return url_for("places.publico", slug=token, _external=True)
        except Exception:
            pass
    base = text(os.getenv("BASE_URL")).rstrip("/")
    path = public_path(token)
    return f"{base}{path}" if base else path


def preview_url(token: str) -> str:
    value = text(token)
    if not value:
        return ""
    if has_request_context():
        try:
            return url_for("places.preview", token=value, _external=True)
        except Exception:
            pass
    base = text(os.getenv("BASE_URL")).rstrip("/")
    path = preview_path(value)
    return f"{base}{path}" if base else path


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
        return qr.svg_inline(scale=scale, border=2, dark="#1E4D4F", light="#ffffff")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", xmldecl=False, scale=scale, border=2, dark="#1E4D4F", light="#ffffff")
    return buffer.getvalue().decode("utf-8")
