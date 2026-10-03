"""CreativeSpec → Director Prompt → AdaptationPlan + model prompt + payload parameters.

The plan says, before any call, which references go to the model natively, which become text, which
are applied afterwards by the Composer and which are dropped — and which parameters were applied,
transformed or dropped. Nothing is adapted silently.
"""

from __future__ import annotations

ROLE_TEXT = {
    "BASE": "the image to edit — keep everything that is not explicitly changed",
    "COMPOSITION": "layout reference — follow its composition and element placement",
    "PRODUCT": "product reference — reproduce this exact product faithfully (shape, colors, materials, markings)",
    "PERSON": "person reference — keep this person's identity: face, hair, skin tone, body type",
    "STYLE": "style reference — borrow its lighting, color treatment and mood, not its content or text",
    "LOGO": "official brand logo — reproduce it exactly, never redraw or restyle it",
    "OTHER": "visual reference",
}
OPENAI_SIZES = {
    "1:1": "1024x1024", "6:5": "1536x1280", "5:6": "1280x1536", "1:2": "768x1536", "2:1": "1536x768", "3:4": "1152x1536", "4:3": "1536x1152", "2:3": "1024x1536", "3:2": "1536x1024",
    "4:5": "1232x1536", "5:4": "1536x1232", "9:16": "864x1536", "16:9": "1536x864", "21:9": "1536x656",
}
# Output image tokens for 1024x1024 by quality (OpenAI image models); scaled by area.
OPENAI_OUTPUT_TOKENS = {"low": 272, "medium": 1056, "high": 4160, "auto": 1056}
OPENAI_REFERENCE_TOKENS = 1100
PROMPT_TOKENS_PER_CHAR = 0.27


def _ratio_value(value: str) -> float:
    try:
        width, height = (float(part) for part in str(value).split(":"))
        return width / height
    except (ValueError, ZeroDivisionError):
        return 0.0


def nearest_ratio(requested: str, allowed: list[str]) -> str:
    choices = [item for item in allowed if item != "auto" and _ratio_value(item)]
    if not choices:
        return requested
    target = _ratio_value(requested) or 1.0
    return min(choices, key=lambda item: abs(_ratio_value(item) - target))


def _quoted(items) -> str:
    return ", ".join(f'"{item}"' for item in items)


COPY_LEVELS = [
    ("kicker", "KICKER (small uppercase line above the headline)"),
    ("headline", "HEADLINE (heavy sans, large)"),
    ("highlight", "HERO (2–4× the headline size, in the ACCENT color)"),
    ("support", "SUPPORT (regular weight, one or two lines)"),
    ("cta", "CTA (inside a solid button)"),
    ("seal", "SEAL (inside a circular urgency seal)"),
    ("tagline", "TAGLINE (signature sentence near the logo)"),
    ("legal", "LEGAL (smallest text, bottom edge)"),
]


def _hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _luma(value):
    red, green, blue = _hex_rgb(value)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _saturation(value):
    rgb = _hex_rgb(value)
    return max(rgb) - min(rgb)


def color_roles(palette: list[str]) -> dict:
    """Background = first brand color (the audit lists the institutional one first); accent = the most
    saturated color that contrasts with it; text = white on dark, near-black on light."""
    colors = [color for color in palette if isinstance(color, str) and len(color) == 7]
    if not colors:
        return {}
    background = colors[0]
    others = [color for color in colors[1:] if abs(_luma(color) - _luma(background)) > 0.25] or colors[1:] or [background]
    accent = max(others, key=_saturation)
    text = "#FFFFFF" if _luma(background) < 0.55 else "#111111"
    rest = [color for color in others if color != accent]
    return {"background": background, "accent": accent, "text": text, "cta": rest[0] if rest else accent}


def has_brief(spec: dict) -> bool:
    brief = spec.get("brief") or {}
    return bool(brief.get("archetype") or any((brief.get("copy") or {}).values())
                or (spec.get("task") == "edit" and brief.get("format_key")))


def copy_strings(brief: dict) -> list[str]:
    copy = brief.get("copy") or {}
    return [str(copy[key]).strip() for key, _ in COPY_LEVELS if str(copy.get(key) or "").strip()]


def director_prompt_v2(spec: dict, brand: dict | None) -> str:
    """Briefing v2 → a diagrammed ad: archetype zones per format, copy hierarchy, color roles, casting."""
    from .archetypes import archetype, format_info, zones_for_ratio
    brief = spec.get("brief") or {}
    kind = archetype(brief.get("archetype"))
    fmt = format_info(brief.get("format_key"))
    ratio = spec["aspect_ratio"]
    brand_name = (brand or {}).get("name") or "the brand"
    lines = []
    if spec["task"] == "edit":
        label = f" ({fmt['label']})" if fmt else ""
        lines.append(f"TASK: Recompose the supplied ad (image 1) into a new {ratio} format{label}. "
                     "Same campaign, same piece — an adaptation, not a new creative.")
        lines.append("KEEP IDENTICAL: every text string (letters, accents, punctuation), every person (face, pose, clothes), "
                     "the product, the logo and the exact colors. Do not add or remove any copy.")
        lines.append(f"RE-LAYOUT FOR {ratio}: {zones_for_ratio(ratio)}. Extend the background naturally where the canvas grows; "
                     "move text blocks instead of shrinking them below legibility; never crop a face, the logo or any text.")
        if spec.get("alter"):
            lines.append(f"ALSO: {spec['alter']}")
    else:
        lines.append(f"TASK: Design a finished {spec.get('objective') or 'advertising piece'} for {brand_name}, "
                     f"{fmt['label'] + ' ' if fmt else ''}{ratio}. This is a graphic-design ad layout made of flat color fields, "
                     "cut-out people and typography — not a photograph with text placed on top.")
        if kind:
            lines.append(f"LAYOUT ({kind['label']}): {kind['layout']}")
        lines.append(f"ZONES FOR {ratio}: {zones_for_ratio(ratio)}.")
        copy = brief.get("copy") or {}
        written = [(label, str(copy.get(key)).strip()) for key, label in COPY_LEVELS if str(copy.get(key) or "").strip()]
        if written:
            lines.append("COPY — Brazilian Portuguese, render each string exactly once, in this hierarchy, and no other words:")
            lines.extend(f"- {label}: \"{value}\"" for label, value in written)
        if brief.get("offer"):
            lines.append(f"OFFER CONTEXT: {brief['offer']}")
        if brief.get("audience"):
            lines.append(f"AUDIENCE: {brief['audience']}")
        casting = [item for item in brief.get("casting") or [] if str(item).strip()]
        if casting:
            lines.append("PEOPLE (Brazilian, real-looking, cleanly cut out, no background scene behind them): "
                         + " | ".join(casting))
        roles = color_roles((brand or {}).get("palette") or [])
        if roles:
            lines.append(f"COLOR ROLES: background {roles['background']} as a flat field; hero/accent {roles['accent']}; "
                         f"text {roles['text']}; CTA button {roles['cta']}. No other dominant colors.")
        devices = [kind["devices"]] if kind else []
        devices += [str(item) for item in brief.get("devices") or [] if str(item).strip()]
        if brand and brand.get("visual_motifs"):
            devices.append("brand motifs: " + "; ".join(brand["visual_motifs"][:3]))
        if devices:
            lines.append("GRAPHIC DEVICES: " + "; ".join(devices) + ".")
        lines.append("SIGNATURE: a solid band along the bottom edge in a brand color; the logo sits at its right end.")
    avoid = list(spec.get("avoid") or [])
    if brand and spec["task"] == "generate":
        avoid += (brand.get("forbidden_elements") or [])[:4]
    avoid += ["neon light trails", "server racks", "generic tech glow", "lorem ipsum", "extra words", "watermarks", "invented logos"]
    lines.append("AVOID: " + "; ".join(dict.fromkeys(avoid)) + ".")
    return "\n".join(lines)


def director_prompt(spec: dict, brand: dict | None) -> str:
    """Provider-agnostic creative direction. v2 when there is a structured briefing, v1 otherwise. Editable in the Lab."""
    if has_brief(spec):
        return director_prompt_v2(spec, brand)
    lines = []
    if spec["task"] == "edit":
        lines.append(f"TASK: Edit the supplied base image ({spec.get('objective') or 'advertising piece'}).")
        lines.append(f"CHANGE ONLY: {spec.get('alter') or spec['instruction']}")
        if spec.get("preserve"):
            lines.append("PRESERVE EXACTLY: " + "; ".join(spec["preserve"]) + ". Everything not listed as a change must stay identical.")
    else:
        brand_name = (brand or {}).get("name") or "the brand"
        lines.append(f"TASK: Create a finished {spec.get('objective') or 'advertising image'} for {brand_name}.")
    lines.append(f'BRIEF (pt-BR, from the art director): "{spec["instruction"]}"')
    lines.append(f"FORMAT: aspect ratio {spec['aspect_ratio']}, full-bleed, no borders, no mockup frame.")
    if spec.get("must_include_text"):
        lines.append("TEXT: render exactly these strings in Brazilian Portuguese, with correct accents and punctuation, "
                     "and no other words: " + _quoted(spec["must_include_text"]) + ".")
    elif spec["task"] == "generate":
        lines.append("TEXT: no text, letters or numbers in the image.")
    if brand and spec["task"] == "generate":
        if brand.get("palette"):
            lines.append("BRAND COLORS: " + ", ".join(brand["palette"][:6]) + ".")
        if brand.get("creative_guidelines"):
            lines.append("BRAND DIRECTION: " + brand["creative_guidelines"][:500])
        if brand.get("mandatory_elements"):
            lines.append("MUST HAVE: " + "; ".join(brand["mandatory_elements"][:5]) + ".")
        if brand.get("visual_motifs"):
            lines.append("VISUAL MOTIFS: " + "; ".join(brand["visual_motifs"][:4]) + ".")
        if brand.get("tone_of_voice"):
            lines.append("TONE: " + brand["tone_of_voice"][:200])
    avoid = list(spec.get("avoid") or [])
    if brand and spec["task"] == "generate":
        avoid += (brand.get("forbidden_elements") or [])[:5]
    avoid += ["extra text", "watermarks", "invented logos"]
    lines.append("AVOID: " + "; ".join(dict.fromkeys(avoid)) + ".")
    return "\n".join(lines)


def plan(spec: dict, manifest: dict, caps: dict, references: list[dict]) -> dict:
    """``references``: [{ref_id, role, label}] in the order the user gave them."""
    result = {
        "model_key": manifest["model_key"], "provider": manifest["provider"],
        "provider_model_id": manifest["provider_model_id"], "profile_version": manifest["profile_version"],
        "task": spec["task"], "sent": [], "converted_to_text": [], "post_processed": [], "dropped": [],
        "parameters": {"applied": {}, "transformed": [], "dropped": []}, "blocked": None,
    }
    if not caps.get("available"):
        result["blocked"] = caps.get("reason") or "Modelo indisponível no catálogo."
    max_refs = int(caps.get("max_references") or 0)
    if spec["task"] == "edit" and max_refs < 1 and not result["blocked"]:
        result["blocked"] = "O modelo não aceita imagem de entrada: não edita."

    policy = manifest["reference_policy"]
    order = {role: index for index, role in enumerate(policy["order"])}
    candidates = []
    for ref in references:
        role = ref["role"]
        if role == "LOGO" and spec.get("logo_mode") == "composer":
            result["post_processed"].append({**ref, "how": "composer_overlay"})
            continue
        if role == "LOGO" and spec.get("logo_mode") == "none":
            result["dropped"].append({**ref, "reason": "a peça não leva logo"})
            continue
        candidates.append(ref)
    candidates.sort(key=lambda ref: (order.get(ref["role"], 99), references.index(ref)))
    slots = max_refs
    if spec.get("pipeline") == "studio":
        # The Studio sends at most three images, and its composition mask (the "mockup") takes the first slot.
        slots = min(slots, 3)
        mockup = spec.get("mockup") or {}
        requested = mockup.get("mode") if mockup.get("id") and spec["task"] == "generate" else "none"
        effective = "none"
        if requested == "image" and slots >= 1:
            effective, slots = "image", slots - 1
        elif requested in ("image", "text"):
            effective = "text"
        result["pipeline"] = "studio"
        result["mockup"] = {"id": mockup.get("id") or None, "requested": requested, "effective": effective,
                            "degraded": requested == "image" and effective == "text"}
    for ref in candidates:
        if len(result["sent"]) < slots:
            result["sent"].append({**ref, "how": "native_input_reference", "order": len(result["sent"]) + 1})
        elif policy.get("overflow") == "describe_in_prompt" and ref["role"] != "BASE":
            result["converted_to_text"].append({**ref, "how": "described_in_prompt",
                                                "reason": f"o modelo aceita {slots} referência(s)"})
        else:
            result["dropped"].append({**ref, "reason": f"o modelo aceita {slots} referência(s)"})

    params = result["parameters"]
    requested_ratio = spec["aspect_ratio"]
    if manifest["provider"] == "openai_direct":
        size = OPENAI_SIZES.get(requested_ratio, "1024x1024")
        params["applied"]["size"] = size
        params["transformed"].append({"param": "aspect_ratio", "from": requested_ratio, "to": size,
                                      "reason": "a rota direta usa tamanho exato"})
    else:
        ratios = caps.get("aspect_ratios") or []
        ratio = requested_ratio if requested_ratio in ratios or not ratios else nearest_ratio(requested_ratio, ratios)
        params["applied"]["aspect_ratio"] = ratio
        if ratio != requested_ratio:
            params["transformed"].append({"param": "aspect_ratio", "from": requested_ratio, "to": ratio,
                                          "reason": "ratio fora do catálogo do modelo"})
            result["post_processed"].append({"ref_id": None, "role": "FORMAT", "label": f"recorte para {requested_ratio}",
                                             "how": "crop_to_format"})
    tier = manifest["quality_map"].get(spec.get("quality") or "standard", {})
    for key, value in {**tier, **manifest.get("fixed_params", {})}.items():
        allowed = {"quality": caps.get("qualities"), "resolution": caps.get("resolutions"),
                   "background": caps.get("backgrounds")}.get(key)
        if manifest["provider"] == "openai_direct":
            if key == "quality":
                params["applied"][key] = value
            continue
        if allowed is not None and allowed and value not in allowed:
            params["dropped"].append({"param": key, "value": value, "reason": "valor fora do catálogo"})
        elif allowed is not None and not allowed:
            params["dropped"].append({"param": key, "value": value, "reason": "parâmetro não suportado"})
        elif key not in {"quality", "resolution", "background"} and key not in (caps.get("parameters") or []):
            params["dropped"].append({"param": key, "value": value, "reason": "parâmetro não suportado"})
        else:
            params["applied"][key] = value
    for key, value in (manifest.get("passthrough") or {}).items():
        if key in (caps.get("passthrough") or []):
            params["applied"][key] = value
        else:
            params["dropped"].append({"param": key, "value": value, "reason": "passthrough não aceito"})

    total = len(references)
    result["summary"] = (
        f"{len(result['sent'])}/{total} referência(s) nativas"
        + (f" · {len(result['converted_to_text'])} em texto" if result["converted_to_text"] else "")
        + (f" · logo pelo Composer" if result["post_processed"] else "")
        + (f" · {len(result['dropped'])} descartada(s)" if result["dropped"] else "")
        + (f" · {len(params['transformed'])} parâmetro(s) ajustado(s)" if params["transformed"] else "")
    ) if total else "Sem referências" + (f" · {len(params['transformed'])} parâmetro(s) ajustado(s)" if params["transformed"] else "")
    return result


def model_prompt(director: str, adaptation: dict, manifest: dict) -> str:
    """Director prompt + the model's own preamble + reference roles, bounded by the model's budget."""
    profile = manifest["prompt_profile"]
    parts = [profile.get("preamble", "").strip()]
    if adaptation["sent"]:
        parts.append("INPUT IMAGES:\n" + "\n".join(
            f"- Image {ref['order']} ({ref['role']}, {ref.get('label') or 'reference'}): {ROLE_TEXT.get(ref['role'], ROLE_TEXT['OTHER'])}."
            for ref in adaptation["sent"]))
    if adaptation["converted_to_text"]:
        parts.append("NOT SUPPLIED AS IMAGES (describe faithfully from this text):\n" + "\n".join(
            f"- {ref['role']}: {ref.get('label') or 'reference'}" for ref in adaptation["converted_to_text"]))
    if adaptation["post_processed"]:
        parts.append("LOGO: do not draw any logo, wordmark or brand name; keep the bottom-right corner calm and empty — "
                     "the official logo is placed there afterwards.")
    parts.append(director.strip())
    text = "\n\n".join(part for part in parts if part)
    limit = int(profile.get("max_chars") or 4000)
    if len(text) <= limit:
        return text
    # Drop the least critical brand lines first, never the task, text or references.
    lines = text.split("\n")
    for prefix in ("VISUAL MOTIFS:", "TONE:", "MUST HAVE:", "BRAND DIRECTION:", "AUDIENCE:", "OFFER CONTEXT:",
                   "GRAPHIC DEVICES:", "AVOID:", "ZONES FOR"):
        if len("\n".join(lines)) <= limit:
            break
        lines = [line for line in lines if not line.startswith(prefix)]
    return "\n".join(lines)[:limit]


def _price(pricing, billable, variant=None):
    rows = [row for row in pricing or [] if row.get("billable") == billable]
    if variant:
        for row in rows:
            tag = str(row.get("variant") or row.get("resolution") or row.get("quality") or "").lower()
            if tag and tag == str(variant).lower():
                return row
    plain_rows = [row for row in rows if not (row.get("variant") or row.get("resolution") or row.get("quality"))]
    return (plain_rows or rows or [None])[0]


def estimate_cost(adaptation: dict, caps: dict, prompt: str) -> dict:
    """Best estimate before the call. Token-priced models are marked variable."""
    pricing = caps.get("pricing") or []
    applied = adaptation["parameters"]["applied"]
    refs = len(adaptation["sent"])
    out_row = _price(pricing, "output_image", applied.get("resolution") or applied.get("quality"))
    if not out_row:
        return {"usd": None, "variable": True, "basis": "sem preço no catálogo"}
    if out_row.get("unit") == "token":
        size = applied.get("size") or OPENAI_SIZES.get(applied.get("aspect_ratio", "1:1"), "1024x1024")
        width, height = (int(part) for part in size.split("x"))
        area = (width * height) / (1024 * 1024)
        out_tokens = OPENAI_OUTPUT_TOKENS.get(applied.get("quality", "medium"), 1056) * area
        text_row = _price(pricing, "input_text")
        image_row = _price(pricing, "input_image")
        usd = out_tokens * float(out_row["cost_usd"])
        usd += len(prompt) * PROMPT_TOKENS_PER_CHAR * float((text_row or {}).get("cost_usd") or 0)
        usd += refs * OPENAI_REFERENCE_TOKENS * float((image_row or {}).get("cost_usd") or 0)
        return {"usd": round(usd, 5), "variable": True, "basis": "tokens estimados por área e qualidade"}
    usd = float(out_row["cost_usd"])
    image_row = _price(pricing, "input_image")
    if image_row and image_row.get("unit") == "image":
        usd += refs * float(image_row["cost_usd"])
    return {"usd": round(usd, 5), "variable": False, "basis": "preço por imagem do catálogo"}
