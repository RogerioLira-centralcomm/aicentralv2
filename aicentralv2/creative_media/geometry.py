"""Mapa de proporção do Trocar → Seedance e frame técnico 4:5."""

from __future__ import annotations

from io import BytesIO

from .settings import SEEDANCE_RATIOS, SIZES


def map_aspect(piece_ratio: str) -> str:
    raw = str(piece_ratio or "16:9").strip()
    if raw == "4:5":
        return "3:4"
    if raw in SEEDANCE_RATIOS:
        return raw
    return "16:9"


def output_size(resolution: str, seedance_ratio: str) -> tuple[int, int]:
    table = SIZES.get(resolution) or SIZES["720p"]
    return table.get(seedance_ratio) or table["16:9"]


def needs_safe_area(piece_ratio: str) -> bool:
    return str(piece_ratio or "") == "4:5"


def prepare_frame(image_bytes: bytes, piece_ratio: str, resolution: str) -> bytes:
    """4:5 vira canvas 3:4 com a peça centrada (safe area). Outros ratios só reencodam JPEG."""
    from PIL import Image

    seedance = map_aspect(piece_ratio)
    width, height = output_size(resolution, seedance)
    source = Image.open(BytesIO(image_bytes)).convert("RGB")
    canvas = Image.new("RGB", (width, height), (8, 8, 10))
    if needs_safe_area(piece_ratio):
        safe_w, safe_h = width, int(round(width * 5 / 4))
        if safe_h > height:
            safe_h = height
            safe_w = int(round(height * 4 / 5))
        fitted = _fit(source, safe_w, safe_h)
        left = (width - fitted.width) // 2
        top = (height - fitted.height) // 2
        canvas.paste(fitted, (left, top))
    else:
        canvas.paste(_fit(source, width, height), (0, 0))
    out = BytesIO()
    canvas.save(out, format="JPEG", quality=90)
    return out.getvalue()


def crop_box_4x5(width: int, height: int) -> tuple[int, int, int, int]:
    """left, top, crop_w, crop_h no canvas técnico 3:4."""
    target_h = int(round(int(width) * 5 / 4))
    if target_h > height:
        target_h = int(height)
        target_w = int(round(target_h * 4 / 5))
        left = (int(width) - target_w) // 2
        return left, 0, target_w, target_h
    top = (int(height) - target_h) // 2
    return 0, top, int(width), target_h


def crop_4x5(image) -> object:
    """Recorta o canvas 3:4 de volta para 4:5 (centro)."""
    left, top, crop_w, crop_h = crop_box_4x5(*image.size)
    return image.crop((left, top, left + crop_w, top + crop_h))


def _fit(image, width, height):
    fitted = image.copy()
    fitted.thumbnail((width, height))
    if fitted.size == (width, height):
        return fitted
    canvas = image.resize((width, height))
    return canvas
