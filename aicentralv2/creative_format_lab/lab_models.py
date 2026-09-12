"""Modelos reais da Mesa — o ledger cobra o mesmo slug que o OpenRouter recebe."""

from __future__ import annotations

import os

from ..services.openrouter_service import resolve_chat_model, resolve_image_model

ENGINEER_MODEL = (
    os.getenv("CREATIVE_FORMAT_ENGINEER_MODEL")
    or os.getenv("CREATIVE_TEXT_MODEL")
    or "openai/gpt-5.4"
)
MOCKUP_MODEL = os.getenv("CREATIVE_FORMAT_MOCKUP_MODEL", "openai/gpt-4o-mini")
QA_MODEL = os.getenv("CREATIVE_FORMAT_QA_MODEL") or MOCKUP_MODEL
IMAGE_MODEL = os.getenv("CREATIVE_IMAGE_MODEL", "openai/gpt-image-2")
ENGINEER_TEMPERATURE = float(os.getenv("CREATIVE_FORMAT_ENGINEER_TEMPERATURE", "0.05"))
MOCKUP_TEMPERATURE = float(os.getenv("CREATIVE_FORMAT_MOCKUP_TEMPERATURE", "0.1"))
QA_TEMPERATURE = float(os.getenv("CREATIVE_FORMAT_QA_TEMPERATURE", "0.0"))
JSON_OBJECT = {"type": "json_object"}


def lab_chat_model(kind="storyboard"):
    key = str(kind or "storyboard").strip().lower()
    if key == "close":
        return resolve_image_model(IMAGE_MODEL)
    if key == "mockup":
        return resolve_chat_model(MOCKUP_MODEL)
    if key in {"qa", "scene", "html", "patch"}:
        return resolve_chat_model(QA_MODEL)
    return resolve_chat_model(ENGINEER_MODEL)
