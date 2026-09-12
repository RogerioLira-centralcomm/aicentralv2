"""Contratos internos da Camadas. Lab OFF: o default continua o baseline."""

from __future__ import annotations

import importlib.util

CLIENT_INJECTIONS = ("predictor", "text_callable", "image_callable")

STATUSES = (
    "unavailable",
    "not_run",
    "not_found",
    "succeeded",
    "rejected",
    "failed",
    "timed_out",
)

ENGINE_IDS = {
    "rembg": "rembg_u2net_human",
    "yolo": "yolo_person",
    "python": "field_predictor",
    "custom": "custom",
    "image2": "image2_well",
}

BASELINE_VERSION = "1"


def strip_client_injections(payload):
    """Callables só existem em injeção interna. HTTP não entrega executável."""
    clean = dict(payload or {})
    for key in CLIENT_INJECTIONS:
        clean.pop(key, None)
    return clean


def probe_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def list_capabilities():
    """Registry sem baixar pesos e sem importar torch."""
    return [
        {
            "engine_id": "rembg_u2net_human",
            "task": "segment",
            "available": probe_module("rembg"),
            "optional": True,
            "weights": "u2net_human_seg",
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "yolo_person",
            "task": "segment",
            "available": probe_module("ultralytics"),
            "optional": True,
            "weights": "yolov8n-seg.pt",
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "field_predictor",
            "task": "segment",
            "available": True,
            "optional": False,
            "weights": "",
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "openrouter_read",
            "task": "ocr",
            "available": True,
            "optional": True,
            "weights": "",
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "wash",
            "task": "ground",
            "available": True,
            "optional": False,
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "leftover",
            "task": "ground",
            "available": True,
            "optional": False,
            "version": BASELINE_VERSION,
        },
        {
            "engine_id": "image2_well",
            "task": "ground_fill",
            "available": True,
            "optional": True,
            "limitation": "no_mask",
            "version": BASELINE_VERSION,
        },
    ]


def engine_id_for(engine):
    return ENGINE_IDS.get(str(engine or ""), str(engine or "field_predictor"))


def split_summary(result):
    result = result if isinstance(result, dict) else {}
    return {
        "engine_id": result.get("engine_id") or engine_id_for(result.get("engine")),
        "cast_ok": bool(result.get("cast_ok")),
        "cast_status": result.get("cast_status") or "",
        "cast_reason": result.get("cast_reason") or "",
        "cast_score_raw": result.get("cast_score_raw"),
        "cast_confidence": result.get("cast_confidence"),
        "ground_kind": result.get("ground_kind"),
        "width": result.get("width"),
        "height": result.get("height"),
    }


def geometry_compatible(result, width, height):
    if not isinstance(result, dict):
        return False
    if result.get("width") != width or result.get("height") != height:
        return False
    for item in result.get("layers") or []:
        box = item.get("box") if isinstance(item, dict) else None
        if not isinstance(box, dict):
            continue
        if box.get("w", 0) < 0 or box.get("h", 0) < 0:
            return False
        if box.get("x", 0) + box.get("w", 0) > 100.5:
            return False
    return True


def compare_segmenters(image, candidate=None, *, predictor=None):
    """Compara um candidato fake ao baseline. Não entra no request default."""
    from .split_layers import split_still

    baseline = split_still(image, predictor=predictor)
    report = {"baseline": split_summary(baseline), "candidate": None}
    if candidate is None:
        return report
    if not callable(candidate):
        report["candidate"] = {"status": "unavailable"}
        return report
    try:
        other = split_still(image, predictor=candidate)
    except Exception:
        report["candidate"] = {"status": "failed"}
        return report
    summary = split_summary(other)
    if not geometry_compatible(other, baseline.get("width"), baseline.get("height")):
        summary["status"] = "failed"
        summary["cast_reason"] = "geometry"
    report["candidate"] = summary
    return report
