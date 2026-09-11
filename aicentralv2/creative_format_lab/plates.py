"""Kit de placas HTML de uma marca: um texto-piloto em todos os retângulos."""

from __future__ import annotations

import json
import re

from .brand_context import build_brand_context
from .catalog import CTA_DEFAULTS, plate_kit_formats
from .engineer import build_spec, normalize_knobs
from .html_builder import build_scene_html
from .router import route_format

_JSON = re.compile(r"\{[\s\S]*\}")


def build_plate_kit(client, bindings=None, text_callable=None):
    brand = build_brand_context(client)
    copy = starter_copy(brand, text_callable=text_callable)
    saved = _binding_map(bindings if bindings is not None else _stored_bindings(client))
    dna = brand.get("brand_dna") if isinstance(brand.get("brand_dna"), dict) else {}
    assets = {"logo_url": brand.get("logo_url") or ""}
    plates = []
    for entry in plate_kit_formats():
        route = route_format(format_key=entry["key"])
        spec = build_spec(
            route=route,
            intent="create",
            brand_name=brand.get("name") or "",
            campaign=_campaign_payload(copy, brand),
            brand_context=brand,
            knobs=normalize_knobs({
                "scene_count": 4,
                "cta": copy["cta"],
                "offer": copy["offer"],
            }),
        )
        scene = spec.scenes[0]
        html = build_scene_html(
            spec,
            scene,
            dna=dna,
            assets=assets,
            render=True,
            logo_visible=True,
        )
        channels = list(entry.get("channels") or [])
        selected = [key for key in saved.get(entry["key"], []) if key in entry.get("channel_keys", [])]
        plates.append({
            "key": entry["key"],
            "label": entry["label"],
            "size_label": entry["size_label"],
            "aspect_ratio": entry["aspect_ratio"],
            "orientation": entry["orientation"],
            "kind": entry["kind"],
            "canvas": dict(entry["canvas"]),
            "channels": channels,
            "selected_channels": selected,
            "checked": bool(selected),
            "html": html,
        })
    return {
        "brand": {
            "id": brand.get("id"),
            "name": brand.get("name") or "",
            "logo_url": brand.get("logo_url") or "",
            "palette": brand.get("palette") or [],
        },
        "campaign": copy,
        "plates": plates,
        "checked_count": sum(1 for item in plates if item["checked"]),
    }


def starter_copy(brand, text_callable=None):
    facts = _facts_copy(brand if isinstance(brand, dict) else {})
    if not text_callable:
        return facts
    try:
        raw = text_callable(
            [
                {
                    "role": "system",
                    "content": (
                        "Escreva uma campanha-piloto curta em português do Brasil. "
                        "JSON só: {\"offer\",\"headline\",\"support\",\"cta\"}. "
                        "Headline até 6 palavras. Support até 12. CTA 2 palavras. "
                        "Use só fatos da marca. Sem HTML."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "name": facts["brand_name"],
                            "offer": facts["offer"],
                            "summary": facts["support"],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=160,
            temperature=0.3,
        )
        parsed = _parse_copy(raw)
    except Exception:
        return facts
    if not parsed.get("headline"):
        return facts
    return {
        "brand_name": facts["brand_name"],
        "offer": str(parsed.get("offer") or facts["offer"])[:160],
        "headline": str(parsed["headline"])[:80],
        "support": str(parsed.get("support") or facts["support"])[:160],
        "cta": str(parsed.get("cta") or facts["cta"])[:40],
    }


def normalize_bindings(payload, allowed=None):
    raw = payload if isinstance(payload, dict) else {}
    incoming = raw.get("bindings") if isinstance(raw.get("bindings"), dict) else raw
    allowed = allowed if isinstance(allowed, dict) else {
        item["key"]: set(item.get("channel_keys") or [])
        for item in plate_kit_formats()
    }
    clean = {}
    for key, values in incoming.items():
        format_key = str(key or "").strip()
        if format_key not in allowed:
            continue
        keys = []
        for item in values if isinstance(values, (list, tuple)) else []:
            channel = str(item or "").strip()
            if channel in allowed[format_key] and channel not in keys:
                keys.append(channel)
        clean[format_key] = keys
    return clean


def _facts_copy(brand):
    name = str(brand.get("name") or "Sua marca").strip() or "Sua marca"
    products = brand.get("products_services") or []
    chances = brand.get("campaign_opportunities") or []
    product = str(products[0] if products else name)
    offer = str(chances[0] if chances else product)
    summary = str(
        brand.get("brand_summary")
        or brand.get("tone_of_voice")
        or "Uma linha que o retângulo aguenta."
    )
    return {
        "brand_name": name,
        "offer": offer[:160],
        "headline": _short_line(offer or product, 6),
        "support": _short_line(summary, 12),
        "cta": CTA_DEFAULTS.get("iab-medium") or "Saiba mais",
    }


def _campaign_payload(copy, brand):
    return {
        "brand_name": copy.get("brand_name") or brand.get("name") or "",
        "cta": copy.get("cta") or "Saiba mais",
        "offer": copy.get("offer") or "",
        "scenes": [
            {
                "id": f"scene_0{index}",
                "headline": copy.get("headline") or "",
                "support": copy.get("support") or "",
                "cta": copy.get("cta") or "",
            }
            for index in range(1, 5)
        ],
    }


def _stored_bindings(client):
    profile = client.get("brand_profile") if isinstance(client, dict) else {}
    if not isinstance(profile, dict):
        return {}
    raw = profile.get("plate_channels")
    return raw if isinstance(raw, dict) else {}


def _binding_map(value):
    if not isinstance(value, dict):
        return {}
    return {
        str(key): [str(item) for item in items]
        for key, items in value.items()
        if isinstance(items, (list, tuple))
    }


def _parse_copy(raw):
    if isinstance(raw, dict):
        content = raw.get("message", {}).get("content") if isinstance(raw.get("message"), dict) else raw
        if isinstance(content, dict):
            return content
        raw = content
    text = str(raw or "").strip()
    match = _JSON.search(text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _short_line(text, words):
    parts = str(text or "").replace("\n", " ").split()
    if not parts:
        return ""
    return " ".join(parts[:words]).rstrip(".,;:")
