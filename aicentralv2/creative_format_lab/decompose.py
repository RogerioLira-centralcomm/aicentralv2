"""Image 2 parte o criativo: fundo de um lado, pessoas do outro."""

from __future__ import annotations

import base64

CAST_PROMPT = (
    "Extract only the people from this advertisement as one group cutout. "
    "Keep every face, body, pose, hair and garment exactly. "
    "Remove the background, bunting, typography, name pills, dates, logos "
    "and decorative pattern. Transparent PNG. No new people. No text."
)
GROUND_PROMPT = (
    "Recreate only the background of this advertisement: the flat color field "
    "and the repeating pennant bunting. "
    "No people, no faces, no typography, no name pills, no logos, no dates. "
    "Clean empty field ready for HTML type. Same colors as the source."
)


def decompose_creative(image_url, image_callable=None, field=""):
    if not image_url or not callable(image_callable):
        return {"cast_url": "", "ground_url": "", "field": str(field or "")}
    refs = [image_url]
    cast = _as_data_url(
        image_callable(
            CAST_PROMPT,
            aspect_ratio="1:1",
            background="opaque",
            input_references=refs,
        )
    )
    ground = _as_data_url(
        image_callable(
            GROUND_PROMPT,
            aspect_ratio="1:1",
            background="opaque",
            input_references=refs,
        )
    )
    return {
        "cast_url": cast,
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
