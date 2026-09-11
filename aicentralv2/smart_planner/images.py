"""Arte da página única — GPT Image 2 no OpenRouter."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re

from flask import current_app, has_app_context

from ..services.openrouter_service import generate_image
from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)

IMAGE_MODEL = os.getenv("CREATIVE_IMAGE_MODEL", "openai/gpt-image-2")


def apply_sheet_art(plan: dict, force: bool = False) -> dict:
    """Gera fundo exclusivo e criativo no canal via GPT Image 2."""
    if not isinstance(plan, dict):
        return plan
    theme = as_dict(plan.get("theme"))
    meta = as_dict(plan.get("meta"))
    branding = as_dict(plan.get("branding"))
    hero = as_dict(branding.get("hero"))
    slug = _slug(meta.get("client") or hero.get("name") or theme.get("id") or "folha")
    if force or _needs_exclusive_bg(theme):
        prompt = text(theme.get("bg_prompt")) or _default_bg_prompt(theme, meta)
        theme["bg_url"] = _render(prompt, f"{slug}-bg", aspect_ratio="16:9")
        theme["bg_model"] = IMAGE_MODEL
        plan["theme"] = theme
    creative = _creative_card(plan)
    if creative and (force or not text(creative.get("image_url"))):
        prompt = text(creative.get("image_prompt")) or _default_creative_prompt(creative, meta, hero)
        ratio = "4:3" if text(creative.get("surface")) == "app" else "16:9"
        creative["image_url"] = _render(prompt, f"{slug}-creative", aspect_ratio=ratio)
        creative["image_model"] = IMAGE_MODEL
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
    client = text(hero.get("name") or meta.get("client") or "the brand")
    surface = text(card.get("surface") or "display")
    body = text(card.get("body") or "an ad in the channel")
    return (
        f"Photoreal {surface} mockup of {client} advertising in-channel: {body}. "
        "The ad is inserted in the medium, not a loose banner. No agency logos."
    )


def _render(prompt: str, stem: str, aspect_ratio: str) -> str:
    result = generate_image(
        prompt,
        aspect_ratio=aspect_ratio,
        quality="high",
        output_format="png",
        resolution="2K",
        model=IMAGE_MODEL,
    )
    raw = base64.b64decode(result["b64_json"])
    digest = hashlib.sha1(raw).hexdigest()[:8]
    filename = f"{stem}-{digest}.png"
    dest_dir = _art_dir()
    path = os.path.join(dest_dir, filename)
    with open(path, "wb") as handle:
        handle.write(raw)
    logger.info("Arte da página única gravada: %s (%s)", filename, result.get("model") or IMAGE_MODEL)
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
