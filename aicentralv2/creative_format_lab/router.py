"""Router barato: escolhe a skill de formato sem carregar o catálogo."""

from __future__ import annotations

import json
import os
import re

from .catalog import format_entry

ROUTER_MODEL = os.getenv("CREATIVE_FORMAT_ROUTER_MODEL", "openai/gpt-5-nano")
DEFAULT_FORMAT = "video-linear-15"
_QR = re.compile(r"\b(qr|companion|youtube|aponte|scan|c[aâ]mera)\b", re.IGNORECASE)
_CTA = re.compile(r"\b(cta|call to action|bot[aã]o|saiba mais)\b", re.IGNORECASE)
_NETFLIX = re.compile(r"\bnetflix\b", re.IGNORECASE)


def route_format(message="", format_key=None, files=None, text_callable=None):
    """Devolve {format, adapter, platform_label} sem carregar skills."""
    explicit = format_entry(format_key)
    if explicit:
        adapter = _adapter_hint(message, explicit)
        return {
            "format": explicit["key"],
            "adapter": adapter,
            "platform_label": _platform_for(adapter, explicit),
        }
    text = " ".join(
        [
            str(message or ""),
            " ".join(str(item.get("name") or item.get("kind") or "") for item in (files or []) if isinstance(item, dict)),
        ]
    )
    key = _heuristic(text)
    if key is None and text_callable:
        key = _llm_route(text, text_callable)
    entry = format_entry(key or DEFAULT_FORMAT) or format_entry(DEFAULT_FORMAT)
    adapter = _adapter_hint(text, entry)
    return {
        "format": entry["key"],
        "adapter": adapter,
        "platform_label": _platform_for(adapter, entry),
    }


def _heuristic(text):
    if _QR.search(text or ""):
        return "video-qr-15"
    if _CTA.search(text or ""):
        return "video-cta-15"
    if text and text.strip():
        return DEFAULT_FORMAT
    return None


def _adapter_hint(text, entry):
    if _NETFLIX.search(text or "") and not str(entry["key"]).endswith("qr-15"):
        return "netflix"
    return entry["adapter"]


def _platform_for(adapter, entry):
    if adapter == "netflix":
        return "NETFLIX"
    if adapter == "youtube_ctv":
        return "YOUTUBE CTV"
    return entry.get("platform_label") or "16:9"


def _llm_route(text, text_callable):
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "Escolha só um formato 15s horizontal. "
                    "Responda JSON {\"format\":\"video-linear-15\"|\"video-qr-15\"|\"video-cta-15\"}."
                ),
            },
            {"role": "user", "content": text or "video linear 15s"},
        ],
        model=ROUTER_MODEL,
        max_tokens=80,
        temperature=0,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        key = raw.get("format")
    else:
        try:
            key = json.loads(str(raw)).get("format")
        except Exception:
            key = None
    return key if format_entry(key) else DEFAULT_FORMAT
