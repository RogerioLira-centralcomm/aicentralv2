"""Cotação Seedance 2.5 a partir das dimensões reais."""

from __future__ import annotations

from datetime import datetime, timezone

from ..creative_modeling_fx import annotate_cost, usd_brl_rate
from .geometry import map_aspect, output_size
from .settings import FPS_FOR_QUOTE, MODEL, TOKEN_USD, TOKEN_USD_VIDEO_REF


def quote_video(
    *,
    duration: int,
    resolution: str,
    piece_ratio: str,
    has_video_reference: bool = False,
) -> dict:
    seedance = map_aspect(piece_ratio)
    width, height = output_size(resolution, seedance)
    seconds = max(4, min(int(duration or 8), 30))
    tokens = (width * height * FPS_FOR_QUOTE * seconds) / 1024
    rate = TOKEN_USD_VIDEO_REF if has_video_reference else TOKEN_USD
    usd = round(tokens * rate, 4)
    packed = annotate_cost({
        "estimated_cost_usd": usd,
        "model": MODEL,
        "passes": 1,
        "quality": resolution,
        "later": {"image": False, "video": True},
    })
    exchange, source = usd_brl_rate()
    packed.update({
        "width": width,
        "height": height,
        "duration": seconds,
        "aspect_ratio": seedance,
        "piece_ratio": piece_ratio,
        "fps_for_quote": FPS_FOR_QUOTE,
        "has_video_reference": bool(has_video_reference),
        "exchange_rate": exchange,
        "exchange_rate_source": source,
        "exchange_rate_at": datetime.now(timezone.utc).isoformat(),
        "estimated_cost_brl": packed.get("spent_brl"),
    })
    return packed
