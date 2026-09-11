"""Troca rápida: uma referência + GPT Image 2. Sem roteiro de 15s."""

from __future__ import annotations

import base64

from ..creative_modeling_fx import annotate_cost

SWAP_MODEL = "openai/gpt-image-2"
SWAP_ESTIMATE_USD = 0.22


def quote_swap():
    return annotate_cost({
        "estimated_cost_usd": SWAP_ESTIMATE_USD,
        "model": SWAP_MODEL,
        "passes": 1,
        "later": {"image": True, "video": False},
    })


def build_swap_prompt(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    name = str(payload.get("brand_name") or brand.get("name") or "").strip()
    headline = str(payload.get("headline") or "").strip()
    support = str(payload.get("support") or "").strip()
    cta = str(payload.get("cta") or "").strip()
    note = str(payload.get("note") or payload.get("message") or "").strip()
    color = str(
        payload.get("color")
        or brand.get("primary_color")
        or ""
    ).strip()
    lines = [
        "Edit the attached advertising reference. Keep the same composition, crop, hierarchy and number of frames.",
        "Swap only the advertised brand, product and copy. Do not redesign the layout.",
        "All visible text must be Brazilian Portuguese.",
        "Do not add player chrome, app UI or extra frames that are not in the reference.",
    ]
    if name:
        lines.append(f"New brand: {name}.")
    if color:
        lines.append(f"Brand color: {color}.")
    if headline:
        lines.append(f"Headline: {headline}.")
    if support:
        lines.append(f"Support: {support}.")
    if cta:
        lines.append(f"CTA: {cta}.")
    if note:
        lines.append(note)
    return " ".join(lines)


def swap_reference(payload=None, *, brand=None, image_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    reference = _reference(payload)
    if not reference:
        raise ValueError("Envie uma imagem de referência.")
    if image_callable is None:
        raise ValueError("Gerador de imagem indisponível.")
    prompt = build_swap_prompt(payload, brand)
    result = image_callable(
        prompt,
        input_references=[reference],
        aspect_ratio=str(payload.get("aspect_ratio") or "16:9"),
        background="opaque",
    )
    png = _png_bytes(result)
    if not png:
        raise ValueError("O GPT Image 2 não devolveu o still.")
    return {
        "prompt": prompt,
        "reference": reference[:80],
        "model": SWAP_MODEL,
        "png_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "quote": quote_swap(),
    }


def _reference(payload):
    for key in ("reference", "image", "reference_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("https://", "http://", "data:image/")):
            return value
    return ""


def _png_bytes(result):
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    if not isinstance(result, dict):
        return b""
    raw = result.get("b64_json") or ""
    if raw:
        return base64.b64decode(raw)
    url = result.get("png_data_url") or ""
    if url.startswith("data:image") and "," in url:
        return base64.b64decode(url.split(",", 1)[-1])
    return b""
