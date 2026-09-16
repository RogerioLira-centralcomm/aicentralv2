"""Payload do job para o browser. Sem polling_url."""

from __future__ import annotations

from .settings import UI_STAGES


def job_payload(row, *, scene_ahead=False):
    row = row if isinstance(row, dict) else {}
    plan = row.get("plan_json") if isinstance(row.get("plan_json"), dict) else {}
    quote = row.get("quote_json") if isinstance(row.get("quote_json"), dict) else {}
    version = row.get("version_payload") if isinstance(row.get("version_payload"), dict) else None
    mode = (plan.get("source") or {}).get("mode") or "flattened_still"
    source = plan.get("source") or {}
    has_overlay = mode == "protected_scene" or (
        mode == "transition_ab" and bool(source.get("snapshot_a") or source.get("snapshot_b"))
    )
    has_voiceover = plan.get("audio_mode") == "voiceover"
    stages = [
        {"id": key, "label": label}
        for key, label in UI_STAGES
        if (has_overlay or key != "compositing") and (has_voiceover or key not in {"tts", "mix"})
    ]
    return {
        "job_id": row.get("public_id"),
        "client_id": row.get("client_id"),
        "created_at": row.get("created_at").isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
        "preview_images": plan.get("preview_images") or [],
        "status": row.get("status") or "queued",
        "stage": row.get("stage") or "queued",
        "progress": int(row.get("progress") or 0),
        "message": row.get("message") or "",
        "stages": list(row.get("stages") or []),
        "error": row.get("error_message") or "",
        "quote": {
            "estimated_tokens": quote.get("estimated_tokens"),
            "estimated_cost_usd": quote.get("estimated_cost_usd"),
            "tts_estimated_cost_usd": quote.get("tts_estimated_cost_usd"),
        },
        "eta": {"minimum_seconds": 120, "maximum_seconds": 360},
        "plan": {
            "model": plan.get("model"),
            "duration": plan.get("duration"),
            "resolution": plan.get("resolution"),
            "aspect_ratio": plan.get("aspect_ratio"),
            "piece_ratio": plan.get("piece_ratio"),
            "audio_mode": plan.get("audio_mode"),
            "source": {key:source[key] for key in ("mode","base_id","ref_ids","to_id","camadas_creative_id") if key in source},
        },
        "ui_stages": stages,
        "scene_ahead": bool(scene_ahead),
        "version": version,
    }


def asset_url(asset_id):
    if not asset_id:
        return ""
    return f"/parametros/api/media/assets/{asset_id}/content"
