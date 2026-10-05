"""Image bytes for the Lab live in PostgreSQL (cx_lab_files), served by token.

The database is shared between every environment while disks are not; keeping the bytes next to the
rows means a run executed anywhere has the same public URL everywhere. Outputs are stored as WEBP
(lossless for references with text, high quality for outputs) and every image gets a 384px thumbnail.
"""

from __future__ import annotations

import base64
import hashlib
import io
import secrets
from urllib.parse import urljoin

from flask import current_app, has_app_context
from PIL import Image, ImageOps

from ..db import get_db

THUMB_SIDE = 384
MAX_SIDE = 2048
PROVIDER_SIDE = 1536


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def open_image(payload: bytes) -> Image.Image:
    from ..creative_media import svg_raster
    if svg_raster.is_svg(payload):
        try:
            payload = svg_raster.rasterize(payload)  # an SVG reference is stored as pixels, never as SVG
        except RuntimeError as exc:  # no Cairo on this server: a clear 400, not a 500
            raise ValueError(str(exc)) from exc
    image = Image.open(io.BytesIO(payload))
    image.load()
    image = ImageOps.exif_transpose(image)
    return image


def _encode(image: Image.Image, *, side: int, quality: int, lossless: bool = False) -> bytes:
    image = image.copy()
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    out = io.BytesIO()
    image.save(out, "WEBP", quality=quality, lossless=lossless, method=5)
    return out.getvalue()


def _insert(client_id: int, kind: str, content: bytes, width: int, height: int, digest: str) -> dict:
    token = secrets.token_urlsafe(24)
    with get_db().cursor() as cursor:
        cursor.execute(
            """INSERT INTO cx_lab_files (token, client_id, kind, mime, content, byte_size, width, height, sha256)
               VALUES (%s, %s, %s, 'image/webp', %s, %s, %s, %s, %s) RETURNING id, token""",
            (token, client_id, kind, content, len(content), width, height, digest),
        )
        return dict(cursor.fetchone())


def store_image(client_id: int, payload: bytes, *, kind: str, lossless: bool = False) -> dict:
    """Store an image and its thumbnail. Returns ids, tokens, size and the sha256 of the original bytes."""
    digest = sha256(payload)
    image = open_image(payload)
    main = _encode(image, side=MAX_SIDE, quality=92, lossless=lossless)
    main_image = open_image(main)
    thumb = _encode(image, side=THUMB_SIDE, quality=82)
    stored = _insert(client_id, kind, main, main_image.width, main_image.height, digest)
    thumb_row = _insert(client_id, "thumb", thumb, *open_image(thumb).size, digest)
    return {
        "file_id": stored["id"], "token": stored["token"],
        "thumb_file_id": thumb_row["id"], "thumb_token": thumb_row["token"],
        "width": image.width, "height": image.height, "sha256": digest,
    }


def read_file(token: str) -> dict | None:
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id, token, mime, content, width, height FROM cx_lab_files WHERE token = %s", (str(token)[:48],))
        row = cursor.fetchone()
    return dict(row) if row else None


def read_file_by_id(file_id: int) -> dict | None:
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id, token, mime, content, width, height FROM cx_lab_files WHERE id = %s", (int(file_id),))
        row = cursor.fetchone()
    return dict(row) if row else None


def file_path(token: str) -> str:
    return f"/lab/files/{token}.webp" if token else ""


def public_url(token: str) -> str:
    """Canonical public URL on the Studio host (works from any environment once the row exists)."""
    if not token:
        return ""
    base = str(current_app.config.get("STUDIO_URL") or "").strip() if has_app_context() else ""
    return urljoin(base.rstrip("/") + "/", file_path(token).lstrip("/")) if base else file_path(token)


def provider_data_url(file_id: int, *, side: int = PROVIDER_SIDE) -> str:
    """Data URL for providers, independent of the public host being reachable.

    PNG keeps transparency for logos; photos go as high-quality JPEG to keep the request small.
    """
    row = read_file_by_id(file_id)
    if not row:
        raise ValueError("Arquivo do Lab não encontrado.")
    image = open_image(bytes(row["content"]))
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 250:
        image.save(out, "PNG", optimize=True)
        mime = "image/png"
    else:
        image.convert("RGB").save(out, "JPEG", quality=93)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(out.getvalue()).decode("ascii")


def jpeg_data_url(file_id: int, *, side: int = 768) -> str:
    """Small JPEG for the vision observer (cheap tokens)."""
    row = read_file_by_id(file_id)
    if not row:
        raise ValueError("Arquivo do Lab não encontrado.")
    image = open_image(bytes(row["content"])).convert("RGB")
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
