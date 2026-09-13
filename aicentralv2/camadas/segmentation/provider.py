"""Resolve o motor e devolve uma máscara por objeto."""

from __future__ import annotations

import logging

from .interactive import flood_from_points
from .matting import mask_contains
from .quality import assess_mask

logger = logging.getLogger(__name__)

PERSON_LABELS = {"person"}
PRODUCT_LABELS = {
    "bottle",
    "cup",
    "wine glass",
    "cell phone",
    "book",
    "laptop",
    "tv",
    "remote",
    "handbag",
    "backpack",
    "suitcase",
    "umbrella",
    "clock",
    "vase",
    "teddy bear",
    "sports ball",
    "scissors",
    "keyboard",
    "mouse",
    "toothbrush",
    "bowl",
    "fork",
    "knife",
    "spoon",
    "banana",
    "apple",
    "orange",
    "cake",
    "donut",
    "pizza",
    "hot dog",
    "sandwich",
}
GRAPHIC_LABELS = {
    "tie",
    "frisbee",
    "kite",
    "traffic light",
    "stop sign",
    "parking meter",
}


def probe_yolo():
    try:
        import importlib.util

        return importlib.util.find_spec("ultralytics") is not None
    except (ImportError, ValueError):
        return False


def probe_sam2():
    return False


def sam2_segment_all(_source, _reading=None):
    return []


def sam2_segment_at(_source, _points, _negative=None):
    return None


def resolve_predictor(predictor=None):
    if callable(predictor):
        return predictor, "custom"
    try:
        from ...creative_format_lab.split_layers import _load_yolo

        return _load_yolo(), "yolo"
    except Exception:
        logger.info("YOLO ausente. Field predictor como fallback.")
    from ...creative_format_lab.split_layers import field_predictor

    return field_predictor, "python"


def segment_all(source, reading=None, predictor=None):
    from ...creative_format_lab.split_layers import _normalize_detections

    predict, engine = resolve_predictor(predictor)
    raw = predict(source.convert("RGB") if hasattr(source, "convert") else source)
    detections = []
    for item in _normalize_detections(raw, source.size):
        role = role_for_label(item.get("label"))
        quality = assess_mask(item["mask"], source, engine)
        if not quality["include"]:
            continue
        detections.append({
            "role": role,
            "label": item.get("label") or role,
            "mask": item["mask"],
            "quality": quality,
            "engine": engine,
        })
    return detections


def segment_at(source, positive_points, negative_points=None, predictor=None, existing=None):
    point = (positive_points or [{}])[0]
    for item in existing or []:
        mask = item.get("mask")
        if mask is not None and mask_contains(mask, point.get("x"), point.get("y")):
            return {**item, "hit": True}
    for detection in segment_all(source, predictor=predictor):
        if mask_contains(detection["mask"], point.get("x"), point.get("y")):
            return {**detection, "hit": False}
    mask = flood_from_points(source, positive_points, negative_points)
    if mask is None:
        return None
    quality = assess_mask(mask, source, "click")
    if not quality["include"]:
        return None
    return {
        "role": "product",
        "label": "object",
        "mask": mask,
        "quality": quality,
        "engine": "click",
        "hit": False,
    }


def role_for_label(label):
    name = str(label or "").strip().lower()
    if name in PERSON_LABELS:
        return "person"
    if name in {"logo", "badge"}:
        return name
    if name in GRAPHIC_LABELS:
        return "graphic"
    if name in PRODUCT_LABELS or name == "object":
        return "product"
    return "product" if name else "graphic"
