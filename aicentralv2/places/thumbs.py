"""Resized copies of the Places photo library.

The curated gallery keeps the originals (some are 6,500 px and 2-3 MB). Cards and
fiches only need a fraction of that, so they ask for a width and get a WebP made
once and kept on disk next to the originals.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, current_app, redirect, send_file

bp = Blueprint("places_thumbs", __name__)

GALLERY_PREFIX = "/static/images/places/gallery/"
WIDTHS = (640, 1600)
QUALITY = 78


STATIC_GALLERY = Path(__file__).resolve().parents[1] / "static" / "images" / "places" / "gallery"


def _gallery_dir() -> Path:
    return Path(current_app.static_folder) / "images" / "places" / "gallery"


def thumb_url(url: str, width: int) -> str:
    """URL of the resized copy for a gallery photo; any other URL is returned unchanged.

    Once the copy exists it is a plain static file (served by the web server, no app hooks);
    until then the URL points to the route that makes it.
    """
    value = str(url or "")
    if width not in WIDTHS or not value.startswith(GALLERY_PREFIX):
        return value
    filename = value[len(GALLERY_PREFIX):]
    if "/" in filename:
        return f"/media/places/{width}/{filename}"
    folder = STATIC_GALLERY / "_thumbs" / str(width)
    if (folder / f"{Path(filename).stem}.webp").is_file():
        return f"{GALLERY_PREFIX}_thumbs/{width}/{Path(filename).stem}.webp"
    if (folder / f"{Path(filename).stem}.failed").is_file():
        return value  # unreadable photo: the original, without a round trip through the route
    return f"/media/places/{width}/{filename}"


def make_thumb(source: Path, width: int) -> Path:
    """Write (or reuse) the WebP copy of one gallery photo at ``width`` and return its path."""
    target = source.parent / "_thumbs" / str(width) / f"{source.stem}.webp"
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    # A photo that already failed is not decoded again on every visit (a 6,500 px JPEG costs seconds of CPU);
    # replacing the file makes it newer than the marker and retries.
    failed = target.with_suffix(".failed")
    if failed.is_file() and failed.stat().st_mtime >= source.stat().st_mtime:
        raise OSError(f"miniatura já falhou antes: {source.name}")
    from PIL import Image, ImageOps

    # Truncated photos raise here (never flip Pillow's global LOAD_TRUNCATED_IMAGES: uploads rely on it);
    # the route then serves the original instead.
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(f".{os.getpid()}.tmp")
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.thumbnail((width, width * 2))
            image.save(partial, "WEBP", quality=QUALITY, method=4)
    except Exception:
        partial.unlink(missing_ok=True)
        failed.touch()
        raise
    os.replace(partial, target)  # atomic: concurrent requests never read half a file
    failed.unlink(missing_ok=True)
    return target


@bp.get("/media/places/<int:width>/<path:filename>")
def thumbnail(width: int, filename: str):
    if width not in WIDTHS or "/" in filename or filename.startswith("."):
        abort(404)
    source = _gallery_dir() / filename
    if not source.is_file():
        abort(404)
    try:
        target = make_thumb(source, width)
    except Exception:  # noqa: BLE001 — an unreadable photo still shows, at full size
        current_app.logger.warning("Miniatura de Places falhou: %s", filename, exc_info=True)
        return redirect(f"{GALLERY_PREFIX}{filename}")
    return send_file(target, mimetype="image/webp", max_age=60 * 60 * 24 * 30)
