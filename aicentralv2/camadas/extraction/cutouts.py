"""Monta elementos de imagem e o fundo a partir das máscaras."""

from __future__ import annotations

from ..segmentation.contours import contours_from_mask
from ..segmentation.quality import REVIEW as _REVIEW

ROLE_LABELS = {
    "person": "Pessoa",
    "product": "Produto",
    "logo": "Logo",
    "graphic": "Grafismo",
    "badge": "Selo",
    "illustration": "Ilustração",
    "background": "Fundo",
    "decoration": "Grafismo",
}


def extract_image_elements(source, detections, reading, storage, creative_id):
    from PIL import Image, ImageChops

    from ...creative_format_lab.split_layers import (
        _cutout,
        _field_rgb,
        _ground,
        classify_ground,
    )

    rows = []
    counts = {}
    union = Image.new("L", source.size, 0)
    accepted = 0
    z_index = 20
    for detection in detections or []:
        mask = detection.get("mask")
        if mask is None or mask.getbbox() is None:
            continue
        crop, box = _cutout(source, mask)
        role = detection.get("role") or "product"
        counts[role] = counts.get(role, 0) + 1
        label = _numbered(role, counts[role])
        quality = detection.get("quality") or {}
        png_path = storage.save_png(creative_id, f"{role}-{counts[role]}", crop)
        mask_path = storage.save_png(creative_id, f"{role}-{counts[role]}-mask", mask.convert("L"))
        thumb_path = storage.save_thumb(creative_id, f"{role}-{counts[role]}", crop)
        geometry = contours_from_mask(mask)
        status = quality.get("status") or "review_edge"
        rows.append({
            "role": role,
            "label": label,
            "layer_type": "image",
            "bbox": box,
            "quality": status,
            "coverage": quality.get("coverage"),
            "needs_review": status in _REVIEW,
            "provenance": "recorte_original",
            "z_index": z_index,
            "png_path": png_path,
            "mask_path": mask_path,
            "thumb_path": thumb_path,
            "metadata": {
                "engine": detection.get("engine") or "",
                "coverage": quality.get("coverage"),
                "reason": quality.get("reason") or "",
                "contours": geometry["contours"],
                "points": geometry["points"],
            },
        })
        union = ImageChops.lighter(union, mask)
        accepted += 1
        z_index += 10
    rows.extend(_logo_crops(source, reading, storage, creative_id, z_index, counts))
    field_rgb = _field_rgb(source, union)
    kind = classify_ground(source, field_rgb)
    ground, field = _ground(source, union, field_rgb, kind, cast_ok=accepted > 0)
    ground_path = storage.save_png(creative_id, "background", ground)
    ground_thumb = storage.save_thumb(creative_id, "background", ground)
    rows.insert(0, {
        "role": "background",
        "label": "Fundo",
        "layer_type": "image",
        "bbox": {"x": 0, "y": 0, "w": 100, "h": 100},
        "quality": "reliable",
        "coverage": 1.0,
        "needs_review": False,
        "provenance": "extracted" if kind == "image" and accepted else "reconstructed",
        "z_index": 0,
        "png_path": ground_path,
        "thumb_path": ground_thumb,
        "metadata": {
            "ground_kind": kind,
            "field": field,
        },
    })
    return rows, field, kind


def detection_to_row(source, detection, storage, creative_id, index=1):
    from ...creative_format_lab.split_layers import _cutout

    mask = detection["mask"]
    crop, box = _cutout(source, mask)
    role = detection.get("role") or "product"
    quality = detection.get("quality") or {}
    png_path = storage.save_png(creative_id, f"{role}-click-{index}", crop)
    mask_path = storage.save_png(creative_id, f"{role}-click-{index}-mask", mask.convert("L"))
    thumb_path = storage.save_thumb(creative_id, f"{role}-click-{index}", crop)
    geometry = contours_from_mask(mask)
    status = quality.get("status") or "review_edge"
    return {
        "role": role,
        "label": _numbered(role, index),
        "layer_type": "image",
        "bbox": box,
        "quality": status,
        "coverage": quality.get("coverage"),
        "needs_review": status in _REVIEW,
        "provenance": "recorte_original",
        "z_index": 40,
        "png_path": png_path,
        "mask_path": mask_path,
        "thumb_path": thumb_path,
        "metadata": {
            "engine": detection.get("engine") or "click",
            "coverage": quality.get("coverage"),
            "contours": geometry["contours"],
            "points": geometry["points"],
        },
    }


def _logo_crops(source, reading, storage, creative_id, z_index, counts):
    from ...creative_format_lab.split_layers import _cutout

    rows = []
    parsed = reading if isinstance(reading, dict) else {}
    width, height = source.size
    for item in parsed.get("elements") or []:
        if not isinstance(item, dict) or item.get("role") not in {"logo", "badge"}:
            continue
        mask = _mask_from_box(item, width, height)
        if mask is None:
            continue
        crop, box = _cutout(source, mask)
        role = item.get("role")
        counts[role] = counts.get(role, 0) + 1
        png_path = storage.save_png(creative_id, f"{role}-{counts[role]}", crop)
        mask_path = storage.save_png(creative_id, f"{role}-{counts[role]}-mask", mask)
        thumb_path = storage.save_thumb(creative_id, f"{role}-{counts[role]}", crop)
        rows.append({
            "role": role,
            "label": ROLE_LABELS.get(role, role),
            "layer_type": "image",
            "bbox": box,
            "quality": "reliable",
            "coverage": None,
            "needs_review": False,
            "provenance": "recorte_original",
            "z_index": z_index,
            "png_path": png_path,
            "mask_path": mask_path,
            "thumb_path": thumb_path,
            "text_content": str(item.get("text") or ""),
            "metadata": {"engine": "ocr-box"},
        })
        z_index += 10
    return rows


def _mask_from_box(item, width, height):
    from PIL import Image, ImageDraw

    box = item.get("bbox") if isinstance(item.get("bbox"), dict) else {}
    if all(key in box for key in ("x", "y", "w", "h")):
        left = int(width * float(box["x"]) / 100)
        top = int(height * float(box["y"]) / 100)
        right = int(width * (float(box["x"]) + float(box["w"])) / 100)
        bottom = int(height * (float(box["y"]) + float(box["h"])) / 100)
    else:
        raw = item.get("bbox_px")
        if not (isinstance(raw, (list, tuple)) and len(raw) == 4):
            return None
        left, top, right, bottom = (int(value) for value in raw)
    if right <= left or bottom <= top:
        return None
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rectangle([left, top, right, bottom], fill=255)
    return mask


def _numbered(role, index):
    base = ROLE_LABELS.get(role, role)
    if role in {"person", "product", "graphic", "logo"}:
        return f"{base} {index:02d}"
    return base
