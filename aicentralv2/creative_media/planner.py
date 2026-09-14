"""Plano imutável do job. Still achatado ou cena protegida."""

from __future__ import annotations

import hashlib
import json

from .composition.scene_snapshot import snapshot_fingerprint, validate_snapshot
from .geometry import map_aspect, output_size
from .prompts import build_prompt
from .quoting import merge_video_tts_quote, quote_tts, quote_video
from .settings import (
    DRAFT_RESOLUTION,
    DURATIONS,
    MAX_DURATION,
    MODEL,
    PRODUCTION_RESOLUTION,
    TTS_MODEL,
)
from .voiceover import (
    PACES,
    VOICES,
    assert_fits,
    budget_words,
    normalize_script,
    resolve_voice,
    word_count,
)

AUDIO_MODES = ("silence", "ambient", "music", "voice", "voiceover")
MOTION_PRESETS = ("live", "camera", "people", "product", "transition", "free")
DELIVERIES = ("master", "small_mp4", "gif")


def build_plan(payload=None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    mode = str(source.get("mode") or data.get("source_mode") or "flattened_still")
    if mode not in {"flattened_still", "protected_scene", "transition_ab"}:
        raise ValueError("Modo de origem inválido.")
    snapshot = _ready_snapshot(data.get("scene_snapshot") or source.get("snapshot"))
    snapshot_a = _ready_snapshot(data.get("snapshot_a") or source.get("snapshot_a"))
    snapshot_b = _ready_snapshot(data.get("snapshot_b") or source.get("snapshot_b"))
    if mode == "protected_scene" and snapshot:
        snapshot = validate_snapshot(snapshot)
    if mode == "transition_ab":
        piece_b = str(data.get("to_aspect_ratio") or source.get("to_aspect_ratio") or "")
        if piece_b and map_aspect(piece_b) != map_aspect(
            str(data.get("aspect_ratio") or source.get("aspect_ratio") or "16:9")
        ):
            raise ValueError("As duas peças precisam do mesmo formato.")
        to_id = str(source.get("to_id") or data.get("to_id") or (data.get("extra_ids") or [None])[0] or "")
        if data.get("require_to") and not to_id:
            raise ValueError("Selecione a versão B da transição.")
    quality = str(data.get("quality") or "draft")
    resolution = str(
        data.get("resolution")
        or (PRODUCTION_RESOLUTION if quality == "production" else DRAFT_RESOLUTION)
    )
    if resolution not in {"480p", "720p"}:
        raise ValueError("Resolução inválida. Use 480p ou 720p.")
    duration = int(data.get("duration") or 8)
    if duration not in DURATIONS or duration > MAX_DURATION:
        raise ValueError("Duração inválida. Use 5, 8, 10, 15, 20 ou 30 segundos.")
    piece = str(data.get("aspect_ratio") or source.get("aspect_ratio") or "16:9")
    seedance = map_aspect(piece)
    width, height = output_size(resolution, seedance)
    motion = data.get("motion") if isinstance(data.get("motion"), dict) else {}
    audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
    audio_mode = str(audio.get("mode") or data.get("audio_mode") or "silence")
    if audio_mode not in AUDIO_MODES:
        raise ValueError("Modo de som inválido.")
    voiceover_script = ""
    voiceover_voice = "male"
    voiceover_pace = "normal"
    if audio_mode == "voiceover":
        required = data.get("require_voiceover") is not False
        voiceover_script = normalize_script(
            audio.get("script") or audio.get("voiceover_script") or data.get("voiceover_script"),
            required=required,
        )
        voiceover_voice = str(audio.get("voice") or data.get("voiceover_voice") or "male")
        if voiceover_voice not in VOICES:
            raise ValueError("Voz inválida. Use homem ou mulher.")
        voiceover_pace = str(audio.get("pace") or data.get("voiceover_pace") or "normal")
        if voiceover_pace not in PACES:
            raise ValueError("Ritmo inválido. Use normal ou rápida.")
        if voiceover_script and required:
            assert_fits(voiceover_script, duration)
    preset = str(motion.get("preset") or data.get("motion") or ("transition" if mode == "transition_ab" else "live"))
    if preset not in MOTION_PRESETS:
        raise ValueError("Preset de movimento inválido.")
    delivery = [
        item for item in list(data.get("delivery") or ["master", "small_mp4"])
        if item in DELIVERIES
    ]
    if "master" not in delivery:
        delivery.insert(0, "master")
    gif_window = str(data.get("gif_window") or "first")
    if gif_window not in {"first", "last"}:
        gif_window = "first"
    if audio.get("reference") or data.get("audio_reference"):
        raise ValueError("Áudio de referência não entra com first frame. Descreva a música no texto.")
    plan = {
        "source": {
            "mode": mode,
            "base_id": str(source.get("base_id") or data.get("base_id") or ""),
            "to_id": str(source.get("to_id") or data.get("to_id") or (data.get("extra_ids") or [None])[0] or ""),
            "run_id": str(data.get("run_id") or ""),
            "piece_ratio": piece,
            "camadas_creative_id": str(
                source.get("camadas_creative_id")
                or data.get("camadas_creative_id")
                or (snapshot or snapshot_a or {}).get("creative_id")
                or ""
            ),
            "snapshot": snapshot,
            "snapshot_a": snapshot_a,
            "snapshot_b": snapshot_b,
        },
        "model": MODEL,
        "duration": duration,
        "resolution": resolution,
        "quality": quality,
        "aspect_ratio": seedance,
        "piece_ratio": piece,
        "width": width,
        "height": height,
        "size": f"{width}x{height}",
        "motion_preset": preset,
        "motion_intensity": str(motion.get("intensity") or "subtle"),
        "motion_note": str(motion.get("note") or data.get("motion_note") or ""),
        "audio_mode": audio_mode,
        "voice_note": str(audio.get("prompt") or audio.get("voice_note") or data.get("voice_note") or ""),
        "music_note": str(audio.get("music_note") or data.get("music_note") or ""),
        "voiceover_script": voiceover_script,
        "voiceover_voice": voiceover_voice,
        "voiceover_pace": voiceover_pace,
        "voiceover_provider_voice": resolve_voice(voiceover_voice) if audio_mode == "voiceover" else "",
        "tts_model": TTS_MODEL if audio_mode == "voiceover" else "",
        "generate_audio": audio_mode != "silence",
        "delivery": delivery,
        "gif_window": gif_window,
        "seed": data.get("seed"),
        "keep_aspect": data.get("keep_aspect") is not False,
    }
    plan["prompt"] = build_prompt(plan)
    quote = quote_video(
        duration=duration,
        resolution=resolution,
        piece_ratio=piece,
    )
    if audio_mode == "voiceover" and voiceover_script:
        quote = merge_video_tts_quote(quote, quote_tts(voiceover_script))
        quote["voiceover_words"] = word_count(voiceover_script)
        quote["voiceover_budget"] = budget_words(duration, voiceover_pace)
        quote["voiceover_fits"] = quote["voiceover_words"] <= quote["voiceover_budget"]
    plan["quote"] = quote
    plan["plan_hash"] = hashlib.sha256(
        json.dumps(_hashable(plan), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:32]
    return plan


def public_quote(plan: dict) -> dict:
    quote = plan.get("quote") if isinstance(plan.get("quote"), dict) else {}
    return {
        "model": plan.get("model"),
        "width": plan.get("width"),
        "height": plan.get("height"),
        "duration": plan.get("duration"),
        "resolution": plan.get("resolution"),
        "aspect_ratio": plan.get("aspect_ratio"),
        "estimated_cost_usd": quote.get("estimated_cost_usd"),
        "estimated_cost_brl": quote.get("estimated_cost_brl") or quote.get("spent_brl"),
        "video_estimated_cost_usd": quote.get("video_estimated_cost_usd"),
        "tts_estimated_cost_usd": quote.get("tts_estimated_cost_usd"),
        "tts_model": plan.get("tts_model") or quote.get("tts_model"),
        "voiceover_words": quote.get("voiceover_words"),
        "voiceover_budget": quote.get("voiceover_budget"),
        "voiceover_fits": quote.get("voiceover_fits"),
        "exchange_rate": quote.get("exchange_rate"),
        "exchange_rate_at": quote.get("exchange_rate_at"),
    }


def _hashable(plan):
    skip = {"quote", "prompt"}
    return {key: value for key, value in plan.items() if key not in skip}


def _ready_snapshot(raw):
    if not isinstance(raw, dict) or not raw:
        return None
    data = dict(raw)
    if data.get("creative_id") and data.get("elements"):
        validate_snapshot(data)
    if not data.get("fingerprint"):
        data["fingerprint"] = snapshot_fingerprint(data)
    return data
