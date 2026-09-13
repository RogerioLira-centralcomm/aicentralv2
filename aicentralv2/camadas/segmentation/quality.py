"""Qualidade por máscara. Sem cast_ok global."""

from __future__ import annotations

from ...creative_format_lab.split_layers import _mask_quality

REVIEW = frozenset({"review_edge", "leak", "incomplete", "text_overlap", "low_res"})

_REASON_STATUS = {
    "empty": "incomplete",
    "tiny": "incomplete",
    "full-frame": "leak",
    "paper": "leak",
    "field-garment": "review_edge",
}


def assess_mask(mask, source, engine="yolo"):
    raw = _mask_quality(mask, source, engine)
    if not raw.get("ok"):
        reason = raw.get("reason") or "incomplete"
        status = _REASON_STATUS.get(reason, "review_edge")
        include = reason not in {"empty", "full-frame", "field-garment"}
        return {
            "ok": False,
            "reason": reason,
            "coverage": raw.get("coverage") or 0.0,
            "status": status,
            "include": include,
        }
    status = "review_edge" if (raw.get("coverage") or 0) < 0.04 else "reliable"
    return {
        "ok": True,
        "reason": "",
        "coverage": raw.get("coverage") or 0.0,
        "status": status,
        "include": True,
    }
