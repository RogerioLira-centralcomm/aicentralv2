"""Image 2 limpa o poço de uma foto. Não recorta pessoa."""

from __future__ import annotations

import base64

CAST_PROMPT = (
    "Extract only the people from this advertisement as one group cutout. "
    "Keep every face, body, pose, hair and garment exactly. "
    "Remove the background, typography, logos, prices, buttons and decorations. "
    "Clean figure only. No new people. No text."
)
GROUND_PROMPT = (
    "Recreate only the background of this advertisement as an empty photographic well. "
    "No people, no faces, no typography, no logos, no prices, no buttons. "
    "Clean empty field ready for HTML type. Same colors as the source."
)


def decompose_creative(image_url, image_callable=None, field="", aspect_ratio="16:9"):
    if not image_url or not callable(image_callable):
        return {"cast_url": "", "ground_url": "", "field": str(field or "")}
    refs = [image_url]
    ratio = aspect_ratio or "16:9"
    ground = _as_data_url(
        image_callable(
            GROUND_PROMPT,
            aspect_ratio=ratio,
            background="opaque",
            input_references=refs,
        )
    )
    return {
        "cast_url": "",
        "ground_url": ground,
        "field": str(field or ""),
    }


def _as_data_url(raw):
    if isinstance(raw, dict):
        raw = raw.get("b64_json") or raw.get("url") or raw.get("data_url") or ""
    if isinstance(raw, (bytes, bytearray)):
        return "data:image/png;base64," + base64.b64encode(bytes(raw)).decode("ascii")
    text = str(raw or "").strip()
    if text.startswith(("data:image/", "https://", "http://")):
        return text
    if text:
        return "data:image/png;base64," + text
    return ""
