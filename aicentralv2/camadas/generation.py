"""Decodifica o PNG gerado e calcula o aspect da placa."""

from __future__ import annotations

import base64
import io


def aspect_of(width, height):
    ratio = float(width or 0) / max(1, float(height or 0))
    if ratio >= 1.45:
        return "16:9"
    if ratio <= 0.75:
        return "9:16"
    return "1:1"


def image_from_generation(raw):
    if raw is None:
        return None
    if hasattr(raw, "convert"):
        return raw.convert("RGBA")
    payload = raw
    if isinstance(raw, dict):
        payload = raw.get("b64_json") or raw.get("url") or raw.get("data_url") or raw.get("data") or ""
    if isinstance(payload, (bytes, bytearray)):
        return _open_bytes(payload)
    text = str(payload or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        return None
    if text.startswith("data:image/"):
        text = text.split(",", 1)[-1]
    try:
        return _open_bytes(base64.b64decode(text))
    except Exception:
        return None


def _open_bytes(raw):
    from PIL import Image

    return Image.open(io.BytesIO(raw)).convert("RGBA")
