"""Arte da página única — GPT Image 2 no OpenRouter."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re

from flask import current_app, has_app_context

from ..services.openrouter_service import generate_image, resolve_image_model
from .cost import record as record_cost
from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)


def apply_sheet_art(plan: dict, force: bool = False) -> dict:
    """Gera somente a imagem conceitual principal da proposta.

    Fundos existentes continuam válidos, mas um fundo exclusivo deixou de ser
    uma geração automática. Vídeo, áudio, animação e lotes ficam fora daqui.
    """
    if not isinstance(plan, dict):
        return plan
    theme = as_dict(plan.get("theme"))
    meta = as_dict(plan.get("meta"))
    branding = as_dict(plan.get("branding"))
    hero = as_dict(branding.get("hero"))
    slug = _slug(meta.get("client") or hero.get("name") or theme.get("id") or "folha")
    background_enabled = os.getenv("SMART_PLANNER_GENERATE_BACKGROUND", "").strip().lower() in {"1", "true", "yes"}
    if force or (background_enabled and _needs_exclusive_bg(theme)):
        prompt = text(theme.get("bg_prompt")) or _default_bg_prompt(theme, meta)
        theme["bg_url"] = _render(prompt, f"{slug}-bg", aspect_ratio="16:9")
        theme["bg_model"] = resolve_image_model()
        plan["theme"] = theme
    creative = _creative_card(plan)
    if creative and (force or not text(creative.get("image_url"))):
        prompt = text(creative.get("image_prompt")) or _default_creative_prompt(creative, meta, hero)
        ratio = "4:3" if text(creative.get("surface")) == "app" else "16:9"
        creative["image_url"] = _render(prompt, f"{slug}-creative", aspect_ratio=ratio, references=_brand_references(branding, hero))
        creative["image_model"] = resolve_image_model()
    return plan


def regenerate_creative(plan: dict) -> dict:
    """Gera só o criativo no canal — sem fundo e sem wallpaper no editor."""
    if not isinstance(plan, dict):
        return plan
    meta = as_dict(plan.get("meta"))
    branding = as_dict(plan.get("branding"))
    hero = as_dict(branding.get("hero"))
    theme = as_dict(plan.get("theme"))
    creative = _creative_card(plan)
    if not creative:
        return plan
    slug = _slug(meta.get("client") or hero.get("name") or theme.get("id") or "folha")
    prompt = text(creative.get("image_prompt")) or _default_creative_prompt(creative, meta, hero)
    ratio = "4:3" if text(creative.get("surface")) == "app" else "16:9"
    creative["image_url"] = _render(prompt, f"{slug}-creative", aspect_ratio=ratio, references=_brand_references(branding, hero))
    creative["image_model"] = resolve_image_model()
    return plan


def _needs_exclusive_bg(theme: dict) -> bool:
    url = text(theme.get("bg_url"))
    if not url:
        return True
    return "/smart_planner/bg-" in url and "/generated/" not in url


def _creative_card(plan: dict) -> dict | None:
    for section in as_list(plan.get("sections")):
        for card in as_list(as_dict(section).get("cards")):
            if text(as_dict(card).get("type")) == "creative":
                return card
    return None


def _default_bg_prompt(theme: dict, meta: dict) -> str:
    market = text(theme.get("label") or theme.get("id") or "media")
    client = text(meta.get("client") or "the advertiser")
    return (
        f"Abstract atmospheric background wash for a printed media leave-behind about {client}. "
        f"Market mood: {market}. Low contrast, no text, no logos, no people, no UI. "
        "Painterly photographic blur, 16:9, so a paper sheet can overlay."
    )


def _default_creative_prompt(card: dict, meta: dict, hero: dict) -> str:
    client = text(meta.get("client") or hero.get("name"))
    surface = text(card.get("surface") or "display")
    body = text(card.get("body") or "an ad in the channel")
    if not client:
        return (
            f"Photoreal planning-support image for a {surface} media proposal: {body}. "
            "Show the relevant persona, place, product-use moment or action. "
            "No invented brand, logo, campaign copy or agency identity."
        )
    return (
        f"Premium, photoreal campaign key visual for {client}, shown as a real {surface} advertising placement. "
        f"Campaign context: {body}. Use the supplied brand reference as the exact identity source: preserve its logo, "
        "palette and product cues; do not invent a substitute logo or typography. Show a believable Brazilian audience, "
        "place and product-use moment, with the ad naturally integrated into the screen or editorial environment. "
        "This must look like art-directed commercial photography, not an abstract background, bokeh wallpaper, generic "
        "AI illustration or dashboard. Keep the composition simple, with one focal scene and clear negative space. "
        "No agency marks, no readable promotional copy, no prices, no QR code and no watermark."
    )


def _brand_references(branding: dict, hero: dict) -> list[str]:
    client = as_dict(branding.get("client"))
    refs = as_list(client.get("image_references"))
    if not refs:
        refs = as_list(as_dict(branding.get("brand")).get("image_references"))
    logo = text(client.get("logo_url") or hero.get("logo_url"))
    if logo:
        refs.insert(0, logo)
    return list(dict.fromkeys(text(item) for item in refs if text(item)))[:2]


def _render(prompt: str, stem: str, aspect_ratio: str, references: list[str] | None = None) -> str:
    result = generate_image(
        prompt,
        aspect_ratio=aspect_ratio,
        quality="high",
        output_format="png",
        resolution="2K",
        model=resolve_image_model(),
        input_references=references or None,
    )
    record_cost(result.get("usage"), kind="image", model=text(result.get("model")))
    raw = base64.b64decode(result["b64_json"])
    digest = hashlib.sha1(raw).hexdigest()[:8]
    filename = f"{stem}-{digest}.png"
    dest_dir = _art_dir()
    path = os.path.join(dest_dir, filename)
    with open(path, "wb") as handle:
        handle.write(raw)
    logger.info(
        "Arte da página única gravada: %s (%s)",
        filename,
        result.get("model") or resolve_image_model(),
    )
    return f"/static/images/smart_planner/generated/{filename}"


def _art_dir() -> str:
    if has_app_context() and current_app.static_folder:
        root = current_app.static_folder
    else:
        root = os.path.join(os.path.dirname(__file__), "..", "static")
    dest = os.path.abspath(os.path.join(root, "images", "smart_planner", "generated"))
    os.makedirs(dest, exist_ok=True)
    return dest


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text(value).lower()).strip("-")
    return (slug or "folha")[:40]
