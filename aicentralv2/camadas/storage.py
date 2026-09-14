"""Arquivos do criativo original e dos recortes."""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/octet-stream",
}
MAX_STILL_SIZE = 15 * 1024 * 1024
PUBLIC_PREFIX = "/static/uploads/camadas/"


class CamadasStorage:
    def __init__(self, root=None):
        self._root = Path(root) if root else None

    def root(self):
        if self._root is not None:
            return self._root
        path = Path(current_app.root_path) / "static" / "uploads" / "camadas"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_original(self, file_storage, creative_id):
        extension, mime = validate_still(file_storage)
        folder = self.root() / _safe_id(creative_id)
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"original{extension}"
        path = folder / filename
        file_storage.stream.seek(0)
        file_storage.save(str(path))
        content = path.read_bytes()
        width, height = _image_size(content)
        return {
            "asset_path": f"{PUBLIC_PREFIX}{_safe_id(creative_id)}/{filename}",
            "absolute_path": str(path),
            "original_name": secure_filename(file_storage.filename or filename),
            "mime_type": mime,
            "sha256": hashlib.sha256(content).hexdigest(),
            "width": width,
            "height": height,
        }

    def absolute_path(self, public_path):
        relative = str(public_path or "")
        if not relative.startswith(PUBLIC_PREFIX):
            return None
        name = relative[len(PUBLIC_PREFIX) :]
        parts = Path(name).parts
        if len(parts) != 2 or parts[0] != _safe_id(parts[0]):
            return None
        path = self.root() / parts[0] / parts[1]
        return path if path.is_file() else None

    def save_png(self, creative_id, name, image):
        folder = self.root() / _safe_id(creative_id)
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{_safe_file(name)}.png"
        path = folder / filename
        image.save(str(path), format="PNG")
        return f"{PUBLIC_PREFIX}{_safe_id(creative_id)}/{filename}"

    def save_thumb(self, creative_id, name, image, size=96):
        return self.save_png(creative_id, f"{_safe_file(name)}-th", make_thumb(image, size))

    def save_text_thumb(self, creative_id, name, text, size=96):
        return self.save_png(creative_id, f"{_safe_file(name)}-th", make_text_thumb(text, size))

    def open_image(self, public_path):
        path = self.absolute_path(public_path)
        if path is None:
            return None
        try:
            from PIL import Image
        except ImportError:
            return None
        return Image.open(path).convert("RGBA")

    def sha256_of(self, public_path):
        path = self.absolute_path(public_path)
        if path is None:
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def as_data_url(self, public_path):
        path = self.absolute_path(public_path)
        if path is None:
            return ""
        raw = path.read_bytes()
        suffix = path.suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        import base64

        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def validate_still(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("Envie um criativo.")
    original = secure_filename(file_storage.filename)
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato inválido. Use PNG, JPG ou WEBP.")
    mime = (file_storage.mimetype or "").lower() or {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(extension, "application/octet-stream")
    if mime not in ALLOWED_MIMES and not mime.startswith("image/"):
        raise ValueError("O arquivo enviado não é uma imagem válida.")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        raise ValueError("O criativo está vazio.")
    if size > MAX_STILL_SIZE:
        raise ValueError("O criativo deve ter no máximo 15 MB.")
    return extension, mime


def _safe_id(value):
    text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch == "_")
    return text[:40] or "unknown"


def _safe_file(value):
    text = "".join(ch for ch in str(value or "layer") if ch.isalnum() or ch in {"-", "_"})
    return text[:80] or "layer"


THUMB_WELL = (15, 19, 24, 255)
THUMB_INK = (215, 221, 210, 255)


def make_thumb(image, size=96):
    from PIL import Image

    size = max(32, int(size or 96))
    canvas = Image.new("RGBA", (size, size), THUMB_WELL)
    if image is None:
        return canvas
    work = image.convert("RGBA")
    work.thumbnail((size, size), Image.LANCZOS)
    left = (size - work.width) // 2
    top = (size - work.height) // 2
    canvas.alpha_composite(work, (left, top))
    return canvas


def make_text_thumb(text, size=96):
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (size, size), THUMB_WELL)
    draw = ImageDraw.Draw(canvas)
    words = str(text or "").strip().split()
    line = " ".join(words[:4]) or "HTML"
    draw.text((8, size // 3), line[:18], fill=THUMB_INK)
    return canvas


def _image_size(content):
    try:
        from PIL import Image
    except ImportError:
        return 0, 0
    try:
        image = Image.open(io.BytesIO(content))
    except Exception:
        return 0, 0
    return image.size[0], image.size[1]
