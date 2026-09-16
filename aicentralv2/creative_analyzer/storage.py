"""Storage privado para fontes e derivados do Analyzer."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path

from flask import current_app, has_app_context
from werkzeug.utils import secure_filename

MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class AnalyzerStorage:
    def __init__(self, root=None):
        self._root = Path(root) if root else None

    def root(self):
        if self._root is not None:
            path = self._root
        elif has_app_context():
            path = Path(current_app.instance_path) / "creative_analyzer"
        else:
            path = Path.cwd() / "instance" / "creative_analyzer"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_image(self, public_id, upload):
        payload = upload.stream.read(MAX_IMAGE_BYTES + 1)
        upload.stream.seek(0)
        if not payload:
            raise ValueError("O criativo está vazio.")
        if len(payload) > MAX_IMAGE_BYTES:
            raise ValueError("Envie uma imagem de até 15 MB.")
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception as exc:
            raise ValueError("O arquivo enviado não é uma imagem válida.") from exc
        detected = (Image.MIME.get(image.format) or "").lower()
        if detected not in ALLOWED_IMAGE_MIMES:
            raise ValueError("Formato inválido. Use PNG, JPG ou WEBP.")
        width, height = image.size
        if width < 32 or height < 32 or width * height > 60_000_000:
            raise ValueError("Use uma imagem entre 32 px e 60 megapixels.")
        folder = self.root() / _safe_id(public_id)
        folder.mkdir(parents=True, exist_ok=True)
        extension = EXTENSIONS[detected]
        source = folder / f"source{extension}"
        source.write_bytes(payload)
        thumb = folder / "thumbnail.jpg"
        preview = image.convert("RGB")
        preview.thumbnail((720, 720))
        preview.save(thumb, format="JPEG", quality=84, optimize=True)
        return {
            "original_name": secure_filename(upload.filename or f"criativo{extension}")[:255],
            "mime_type": detected,
            "format": extension.lstrip(".").upper(),
            "source_key": str(source),
            "thumbnail_key": str(thumb),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "width": width,
            "height": height,
            "data_url": f"data:{detected};base64,{base64.b64encode(payload).decode('ascii')}",
        }

    def read(self, public_id, kind):
        folder = self.root() / _safe_id(public_id)
        if kind == "thumbnail":
            path = folder / "thumbnail.jpg"
            mime = "image/jpeg"
        elif kind == "source":
            matches = [path for path in folder.glob("source.*") if path.suffix in {".jpg", ".png", ".webp"}]
            path = matches[0] if len(matches) == 1 else None
            mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(path.suffix if path else "")
        else:
            return None, None
        if path is None or not path.is_file():
            return None, None
        try:
            path.resolve().relative_to(self.root().resolve())
        except ValueError:
            return None, None
        return path, mime

    def remove(self, public_id):
        folder = self.root() / _safe_id(public_id)
        if folder.parent != self.root() or not folder.is_dir():
            return
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()
        folder.rmdir()


def _safe_id(value):
    text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in {"-", "_"})
    return text[:64] or "invalid"
