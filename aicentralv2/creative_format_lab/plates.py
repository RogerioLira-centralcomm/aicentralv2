"""Kit de placas HTML de uma marca: cena 1, texto-piloto e recorte de produto."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..creative_modeling_generation import _json_content
from .brand_context import build_brand_context
from .catalog import (
    CTA_DEFAULTS,
    FAMILY_CANONICAL,
    plate_family_of,
    plate_kit_formats,
)
from .engineer import build_spec, normalize_knobs
from .html_builder import (
    apply_copy_layers,
    apply_css_vars,
    apply_patches,
    apply_product_layer,
    build_scene_html,
)
from .router import route_format

_JSON = re.compile(r"\{[\s\S]*\}")
PLATE_PASSES = 3
PLATE_MODEL = os.getenv("CREATIVE_FORMAT_MOCKUP_MODEL", "openai/gpt-5-nano")
_LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
_PRODUCT_PROMPT = (
    "Isolated product or service still for {name}: {product}. "
    "Studio beauty cutout, no text, no logo, no environment, "
    "seamless light studio backdrop, PNG."
)


def build_plate_kit(
    client,
    bindings=None,
    text_callable=None,
    image_callable=None,
    product=None,
    refine=True,
    passes=None,
    assets=None,
):
    brand = build_brand_context(client)
    chosen = str(product or "").strip()
    copy = starter_copy(brand, text_callable=text_callable, product=chosen)
    saved = _binding_map(bindings if bindings is not None else _stored_bindings(client))
    dna = brand.get("brand_dna") if isinstance(brand.get("brand_dna"), dict) else {}
    cutouts = build_product_cutouts(brand, copy.get("product") or chosen, image_callable)
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
        product_url = product_url_for(entry, cutouts)
        extra = assets if isinstance(assets, dict) else {}
        html = build_scene_html(
            spec,
            scene,
            dna=dna,
            assets={
                "logo_url": brand.get("logo_url") or "",
                "product_url": product_url,
                "cast_url": extra.get("cast_url") or "",
                "ground_url": extra.get("ground_url") or "",
                "field": extra.get("field") or "",
                "chips": extra.get("chips"),
                "meta": extra.get("meta") or "",
                "lockup": extra.get("lockup") or "",
            },
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
            "family": plate_family_of(entry),
            "adapter": entry.get("adapter") or route.get("adapter"),
            "scene_id": scene.id,
            "canvas": dict(entry["canvas"]),
            "channels": channels,
            "selected_channels": selected,
            "checked": bool(selected),
            "product_url": product_url,
            "html": html,
        })
    attempts = max(1, min(3, int(passes or PLATE_PASSES)))
    reports = []
    if refine and text_callable:
        for family in ("horizontal", "box", "vertical"):
            for attempt in range(1, attempts + 1):
                reports.append(
                    refine_plate_family(
                        plates,
                        family,
                        brand=brand,
                        copy=copy,
                        attempt=attempt,
                        attempts=attempts,
                        text_callable=text_callable,
                        images=[url for url in cutouts.values() if url][:2],
                    )
                )
    return {
        "name": kit_auto_name(brand.get("name") or "Marca"),
        "product": copy.get("product") or chosen,
        "brand": {
            "id": brand.get("id"),
            "name": brand.get("name") or "",
            "logo_url": brand.get("logo_url") or "",
            "palette": brand.get("palette") or [],
            "products": list(brand.get("products_services") or []),
            "fonts": (dna.get("fonts") if isinstance(dna.get("fonts"), dict) else {}),
        },
        "campaign": copy,
        "product_assets": cutouts,
        "plates": plates,
        "passes": reports,
        "pass_count": attempts if reports else 0,
        "checked_count": sum(1 for item in plates if item["checked"]),
    }


def starter_copy(brand, text_callable=None, product=None):
    facts = _facts_copy(brand if isinstance(brand, dict) else {}, product=product)
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
                        "Use só fatos da marca e do produto. Sem HTML."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "name": facts["brand_name"],
                            "product": facts.get("product") or "",
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
        "product": facts.get("product") or "",
        "offer": str(parsed.get("offer") or facts["offer"])[:160],
        "headline": str(parsed["headline"])[:80],
        "support": str(parsed.get("support") or facts["support"])[:160],
        "cta": str(parsed.get("cta") or facts["cta"])[:40],
    }


def _safe_product_cutout(image_callable, prompt, aspect_ratio):
    try:
        return _as_data_url(
            image_callable(prompt, aspect_ratio=aspect_ratio, background="opaque")
        )
    except Exception:
        return ""


def build_product_cutouts(brand, product, image_callable):
    name = str((brand or {}).get("name") or "the brand")
    item = str(product or "").strip()
    if not item or not callable(image_callable):
        return {"horizontal": "", "vertical": ""}
    prompt = _PRODUCT_PROMPT.format(name=name, product=item)
    return {
        "horizontal": _safe_product_cutout(image_callable, prompt, "16:9"),
        "vertical": _safe_product_cutout(image_callable, prompt, "9:16"),
    }


def product_url_for(entry, cutouts):
    cutouts = cutouts if isinstance(cutouts, dict) else {}
    orientation = str((entry or {}).get("orientation") or "")
    if orientation in {"vertical", "square"}:
        return cutouts.get("vertical") or cutouts.get("horizontal") or ""
    return cutouts.get("horizontal") or cutouts.get("vertical") or ""


def refine_plate_family(
    plates,
    family,
    *,
    brand,
    copy,
    attempt,
    attempts=PLATE_PASSES,
    text_callable=None,
    images=None,
):
    members = [item for item in plates if item.get("family") == family]
    report = {
        "family": family,
        "attempt": attempt,
        "model": PLATE_MODEL,
        "patches": [],
        "css_vars": {},
    }
    if not members or not callable(text_callable):
        return report
    canonical_key = FAMILY_CANONICAL.get(family)
    sample = next((item for item in members if item.get("key") == canonical_key), members[0])
    payload = {
        "task": f"Pass {attempt}/{attempts}: refine the IAB {family} scene 1 HTML for this brand.",
        "rules": [
            "Return JSON only: {passed, score, defects[], patches[{layer_id,text,css}], css_vars{}}.",
            "Do not return a new HTML document.",
            "Keep layer IDs. Keep the native canvas. Keep the black plate.",
            "Use brand ink, accent and the brand typeface. Do not invent a layout.",
            "Scene 1 only. No extra scenes. No player chrome.",
            "Product stays smaller than the rectangle. contain, no full-bleed.",
            "Thin banners: one line, hide support, product tiny at the far end.",
            "Vertical: type on top, product in the lower third.",
            "Box: type left, object right, stay inside the safe area.",
            "No uppercase headlines. No pill buttons.",
        ],
        "attempt": attempt,
        "family": family,
        "format": sample.get("key"),
        "canvas": sample.get("canvas"),
        "brand": {
            "name": brand.get("name"),
            "palette": brand.get("palette"),
            "tone": brand.get("tone_of_voice"),
            "fonts": (brand.get("brand_dna") or {}).get("fonts")
            if isinstance(brand.get("brand_dna"), dict)
            else brand.get("fonts"),
            "logo_url": brand.get("logo_url"),
        },
        "campaign": {
            "headline": copy.get("headline"),
            "support": copy.get("support"),
            "cta": copy.get("cta"),
            "offer": copy.get("offer"),
            "product": copy.get("product"),
        },
        "layer_ids": [
            "layer-brand",
            "layer-headline",
            "layer-support",
            "layer-cta",
            "layer-key-visual",
        ],
    }
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    for url in images or []:
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
    try:
        response = text_callable(
            [
                {
                    "role": "system",
                    "content": (
                        "You refine IAB plate HTML. Patches only. "
                        "Native canvas. GPT-5-nano fidelity pass. Scene 1."
                    ),
                },
                {"role": "user", "content": content},
            ],
            model=PLATE_MODEL,
            max_tokens=900,
            temperature=0.15,
        )
        raw = _parse_copy(response)
    except Exception:
        return report
    patches = raw.get("patches") if isinstance(raw.get("patches"), list) else []
    css_vars = raw.get("css_vars") if isinstance(raw.get("css_vars"), dict) else {}
    report["patches"] = patches
    report["css_vars"] = css_vars
    for plate in members:
        plate["html"] = apply_patches(plate.get("html"), patches)
        if css_vars:
            plate["html"] = apply_css_vars(plate["html"], css_vars)
    return report


def patch_plate_kit(kit, payload=None, text_callable=None):
    kit = dict(kit or {})
    payload = payload if isinstance(payload, dict) else {}
    plates = [dict(item) for item in kit.get("plates") or []]
    copy = dict(kit.get("campaign") or {})
    incoming = {
        key: str(payload.get(key) or "").strip()
        for key in ("headline", "support", "cta", "offer")
        if key in payload
    }
    copy.update({key: value for key, value in incoming.items() if value or key == "support"})
    apply_all = bool(payload.get("apply_to_all"))
    format_key = str(payload.get("format_key") or payload.get("key") or "").strip()
    css_vars = {}
    if payload.get("product_scale") not in (None, ""):
        css_vars["--product-scale"] = str(payload.get("product_scale"))
    if payload.get("product_x") not in (None, ""):
        css_vars["--product-x"] = _offset(payload.get("product_x"))
    if payload.get("product_y") not in (None, ""):
        css_vars["--product-y"] = _offset(payload.get("product_y"))
    position_keys = {"--product-x", "--product-y"}
    shared_vars = {key: value for key, value in css_vars.items() if key not in position_keys}
    local_vars = dict(css_vars)
    for plate in plates:
        target = apply_all or not format_key or plate.get("key") == format_key
        if not target:
            continue
        if incoming:
            plate["html"] = apply_copy_layers(plate.get("html"), copy)
        vars_for = local_vars if plate.get("key") == format_key or apply_all else shared_vars
        if plate.get("key") != format_key and not apply_all:
            vars_for = shared_vars
        if vars_for:
            plate["html"] = apply_css_vars(plate.get("html"), vars_for)
    if payload.get("product_url") and (apply_all or format_key):
        url = str(payload.get("product_url") or "")
        for plate in plates:
            if apply_all or plate.get("key") == format_key:
                plate["html"] = apply_product_layer(plate.get("html"), url)
                plate["product_url"] = url
    reports = list(kit.get("passes") or [])
    if payload.get("refine") and text_callable:
        families = {item.get("family") for item in plates}
        if format_key and not apply_all:
            current = next((item for item in plates if item.get("key") == format_key), None)
            families = {current.get("family")} if current else families
        next_attempt = max((item.get("attempt") or 0) for item in reports) + 1 if reports else 1
        for family in ("horizontal", "box", "vertical"):
            if family not in families:
                continue
            reports.append(
                refine_plate_family(
                    plates,
                    family,
                    brand=kit.get("brand") or {},
                    copy=copy,
                    attempt=next_attempt,
                    attempts=next_attempt,
                    text_callable=text_callable,
                    images=[
                        url
                        for url in (kit.get("product_assets") or {}).values()
                        if url
                    ][:2],
                )
            )
    kit["campaign"] = copy
    kit["plates"] = plates
    kit["passes"] = reports
    kit["pass_count"] = len(reports)
    kit["checked_count"] = sum(1 for item in plates if item.get("checked"))
    return kit


def apply_bindings(kit, bindings):
    kit = dict(kit or {})
    mapped = normalize_bindings({"bindings": bindings})
    plates = []
    for plate in kit.get("plates") or []:
        item = dict(plate)
        allowed = {channel["key"] for channel in item.get("channels") or []}
        selected = [key for key in mapped.get(item["key"], item.get("selected_channels") or []) if key in allowed]
        item["selected_channels"] = selected
        item["checked"] = bool(selected)
        plates.append(item)
    kit["plates"] = plates
    kit["checked_count"] = sum(1 for item in plates if item.get("checked"))
    return kit


def kit_auto_name(brand_name, when=None):
    stamp = (when or datetime.now(_LOCAL_TZ)).strftime("%Y-%m-%d %H:%M")
    name = str(brand_name or "Marca").strip() or "Marca"
    return f"{name} · IAB base · {stamp}"


def kit_summary(kit):
    kit = kit if isinstance(kit, dict) else {}
    copy = kit.get("campaign") if isinstance(kit.get("campaign"), dict) else {}
    if not copy and isinstance(kit.get("copy"), dict):
        copy = kit["copy"]
    return {
        "id": kit.get("id"),
        "client_id": kit.get("client_id"),
        "name": kit.get("name") or "",
        "product": kit.get("product") or "",
        "headline": kit.get("headline") or copy.get("headline") or "",
        "created_at": kit.get("created_at"),
        "pass_count": kit.get("pass_count") or len(kit.get("passes") or []),
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


def _facts_copy(brand, product=None):
    name = str(brand.get("name") or "Sua marca").strip() or "Sua marca"
    products = brand.get("products_services") or []
    chances = brand.get("campaign_opportunities") or []
    chosen = str(product or "").strip() or str(products[0] if products else name)
    offer = str(chances[0] if chances else chosen)
    summary = str(
        brand.get("brand_summary")
        or brand.get("tone_of_voice")
        or "Uma linha que o retângulo aguenta."
    )
    return {
        "brand_name": name,
        "product": chosen[:160],
        "offer": offer[:160],
        "headline": _short_line(offer or chosen, 6),
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
                "id": "scene_01",
                "headline": copy.get("headline") or "",
                "support": copy.get("support") or "",
                "cta": copy.get("cta") or "",
            }
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
        try:
            return _json_content(raw)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


def _short_line(text, words):
    parts = str(text or "").replace("\n", " ").split()
    if not parts:
        return ""
    return " ".join(parts[:words]).rstrip(".,;:")


def _as_data_url(raw):
    if not raw:
        return ""
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith(("data:image/", "http://", "https://")):
            return text
        return ""
    if isinstance(raw, (bytes, bytearray)):
        encoded = base64.b64encode(bytes(raw)).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return ""


def _offset(value):
    text = str(value or "0").strip()
    if text.endswith("%") or text.endswith("px"):
        return text
    try:
        number = float(text)
    except (TypeError, ValueError):
        return "0"
    return f"{number}%"
