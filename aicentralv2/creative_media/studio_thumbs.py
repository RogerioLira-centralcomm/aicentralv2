"""Reduced copies of Studio images, so shelves and cards do not download the originals.

Generated and reference images are often 1-3 MB. A card needs a few hundred pixels, so the library lists point at
a WebP copy made once and kept in the instance folder. The copy is served by the same route (and the same login
check) as the original: ``?w=480`` on the protected routes, ``/media/studio/<width>/<folder>/<file>`` for the files
that already lived under ``static/uploads``.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
import threading
from pathlib import Path

from flask import Blueprint, abort, current_app, send_file

from ..places.thumbs import make_thumb

bp = Blueprint("studio_thumbs", __name__)
logger = logging.getLogger(__name__)

WIDTH = 480
WIDTHS = (240, WIDTH)
STATIC_FOLDERS = ("creative_generated", "creative_references")
STATIC_PREFIX = "/static/uploads/"
STILL_PREFIX = "/parametros/api/format-lab/swap/still/"
ASSET_PATH = re.compile(r"^/parametros/api/media/assets/[^/?#]+/content$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,160}$")
_IMAGE_SUFFIX = (".png", ".jpg", ".jpeg", ".webp")
# A library page asks for up to two dozen uncached copies at once; decoding a multi-MB image costs seconds of CPU,
# so only a few run together and the rest wait a little before falling back to the original.
_slots = threading.BoundedSemaphore(4)
SLOT_WAIT_SECONDS = 8
_reported: set[str] = set()


def thumb_url_for(url, width: int = WIDTH) -> str:
    """Address of the reduced copy of a Studio image; anything else comes back unchanged."""
    text = str(url or "").strip()
    if not text or "?" in text or text.startswith(("data:", "blob:", "http://", "https://")):
        return text
    if ASSET_PATH.match(text):
        return f"{text}?w={width}"
    if text.startswith(STILL_PREFIX) and text.lower().endswith(_IMAGE_SUFFIX):
        return f"{text}?w={width}"
    if text.startswith(STATIC_PREFIX):
        folder, _, name = text[len(STATIC_PREFIX):].partition("/")
        if folder in STATIC_FOLDERS and _NAME.match(name) and name.lower().endswith(_IMAGE_SUFFIX):
            return f"/media/studio/{width}/{folder}/{name}"
    return text


def with_thumbs(items):
    """Lists of library items with a real ``thumb_url`` wherever it was missing or the full image itself."""
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        source = next((str(item[key]).strip() for key in ("image_url", "asset_url", "url") if item.get(key)), "")
        thumb = thumb_url_for(source)
        current = str(item.get("thumb_url") or "").strip()
        out.append({**item, "thumb_url": thumb} if thumb != source and (not current or current == source) else item)
    return out


def _cache_root(source: Path) -> Path:
    # One folder per source file: the same stem with another extension, or the same name elsewhere, never shares a copy.
    return Path(current_app.instance_path) / "studio_thumbs" / hashlib.sha1(str(source).encode()).hexdigest()[:16]


def _report_failure(source: Path) -> None:
    """Log an image that could not be reduced once per process, not on every card of every page load."""
    key = str(source)
    if key in _reported or len(_reported) >= 2000:
        return
    _reported.add(key)
    logger.warning("Miniatura do Studio falhou: %s", source.name, exc_info=True)


def send_resized(path, mime, width):
    """Send the file, or its reduced copy when ``width`` is one of the supported widths.

    Unsupported widths, non-image content and any failure to resize all fall back to the original.
    """
    source = Path(path)
    kind = str(mime or "")
    if width in WIDTHS and kind.startswith("image/") and kind != "image/svg+xml":
        if _slots.acquire(timeout=SLOT_WAIT_SECONDS):
            try:
                target = make_thumb(source, width, _cache_root(source))
                return send_file(target, mimetype="image/webp", max_age=60 * 60 * 24 * 30, conditional=True)
            except Exception:  # noqa: BLE001 - an unreadable image still shows, at full size
                _report_failure(source)
            finally:
                _slots.release()
    return send_file(source, mimetype=mime, max_age=86400, conditional=True)


@bp.get("/media/studio/<int:width>/<folder>/<filename>")
def studio_thumbnail(width: int, folder: str, filename: str):
    if width not in WIDTHS or folder not in STATIC_FOLDERS or not _NAME.match(filename):
        abort(404)
    source = Path(current_app.root_path) / "static" / "uploads" / folder / filename
    if not source.is_file():
        abort(404)
    return send_resized(source, mimetypes.guess_type(filename)[0] or "image/png", width)
