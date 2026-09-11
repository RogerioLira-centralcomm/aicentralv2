"""Mapeia extract-design-system (normalized.json) para tokens de anúncio."""

from __future__ import annotations

from .schema import contrast_ratio, normalize_hex, relative_luminance

PILL_RADIUS = ("999px", "9999px", "50%", "100vh")


def ingest_extracted(extracted, *, client=None):
    """Aceita normalized.json / tokens.json da extract e devolve patches --dsa-*."""
    data = extracted if isinstance(extracted, dict) else {}
    if isinstance(data.get("colors"), dict) or data.get("typography") or data.get("radius"):
        payload = data
    elif isinstance(data.get("tokens"), dict):
        payload = data["tokens"]
    else:
        payload = data
    colors = _color_map(payload)
    typography = payload.get("typography") if isinstance(payload.get("typography"), dict) else {}
    radius = payload.get("radius") if isinstance(payload.get("radius"), dict) else {}
    if not radius and isinstance(payload.get("borderRadius"), dict):
        radius = payload["borderRadius"]
    paper = _light_surface(colors)
    ink = _readable_ink(colors, paper)
    accent = _cta_fill(colors, paper, ink)
    highlight = _highlight(colors, accent)
    muted = _muted(colors, paper, ink)
    display, body = _typefaces(typography)
    cta_radius = _button_radius(radius)
    voice = compile_ad_voice(payload, colors=colors, typography=typography)
    source = (payload.get("source") or {}) if isinstance(payload.get("source"), dict) else {}
    url = str(source.get("url") or (client or {}).get("website_url") or "").strip()
    tokens = {
        "paper": paper,
        "ink": ink,
        "accent": accent,
        "muted": muted,
        "cta_ink": "#FFFFFF" if contrast_ratio("#FFFFFF", accent) >= 4.5 else "#0F172A",
        "highlight": highlight,
        "font-display": display,
        "font-body": body,
        "cta-radius": cta_radius,
        **voice["tokens"],
    }
    evidence = {
        "source": "extract-design-system",
        "url": url,
        "palette": list(colors.get("palette") or [])[:8],
        "headingFont": typography.get("headingFont"),
        "bodyFont": typography.get("bodyFont"),
        "radius_scale": list(radius.get("scale") or [])[:6],
        "voice": voice["voice"],
        "mapped": {
            "paper": "colors.background",
            "ink": "colors.foreground|primary",
            "accent": "colors.primary se passar 4.5:1, senão ink",
            "highlight": "colors.accent se não for o CTA",
            "cta-radius": "radius.scale sem pílula",
            "weight-display": "typography.styles.weight ou densidade",
            "tracking": "typography.styles.letterSpacing ou densidade",
            "cta-shadow": "shadows.scale se não for card SaaS",
            "cta-pad": "spacing.scale → compact|regular|airy",
            "hairline": "colors.border | cssVariables",
        },
    }
    return {"tokens": tokens, "evidence": evidence, "source_url": url}


def merge_extracted_tokens(base, extracted, *, client=None):
    base = dict(base or {})
    ingested = ingest_extracted(extracted, client=client)
    for key, value in ingested["tokens"].items():
        if value:
            base[key] = value
    return base, ingested["evidence"]


def _color_map(payload):
    colors = payload.get("colors") if isinstance(payload.get("colors"), dict) else {}
    if not colors and isinstance(payload.get("color"), dict):
        colors = payload["color"]
    flat = {}
    for key, value in colors.items():
        if key in {"palette", "cssVariables"}:
            flat[key] = value
            continue
        color = _unwrap_color(value)
        if color:
            flat[key] = color
    if isinstance(colors.get("palette"), list):
        flat["palette"] = [_unwrap_color(item) or item for item in colors["palette"]]
    if isinstance(colors.get("cssVariables"), dict):
        flat["cssVariables"] = colors["cssVariables"]
    return flat


def _unwrap_color(value):
    if isinstance(value, dict):
        value = value.get("$value") or value.get("value") or value.get("hex") or value.get("color")
    return normalize_hex(value, "")


def _light_surface(colors):
    background = _unwrap_color(colors.get("background"))
    if background and relative_luminance(background) >= 0.72:
        return background
    for item in colors.get("palette") or []:
        color = _unwrap_color(item)
        if color and relative_luminance(color) >= 0.85:
            return color
    return "#FFFFFF"


def _readable_ink(colors, paper):
    for key in ("foreground", "primary", "text", "brand"):
        color = _unwrap_color(colors.get(key))
        if color and contrast_ratio(color, paper) >= 4.5:
            return color
    css = colors.get("cssVariables") if isinstance(colors.get("cssVariables"), dict) else {}
    for value in css.values():
        color = _unwrap_color(value)
        if color and relative_luminance(color) <= 0.18 and contrast_ratio(color, paper) >= 4.5:
            return color
    return "#1E4D4F"


def _cta_fill(colors, paper, ink):
    primary = _unwrap_color(colors.get("primary"))
    if primary and contrast_ratio("#FFFFFF", primary) >= 4.5 and primary.upper() != paper.upper():
        return primary
    if contrast_ratio("#FFFFFF", ink) >= 4.5:
        return ink
    return "#1E4D4F"


def _highlight(colors, accent):
    for key in ("accent", "secondary", "highlight"):
        color = _unwrap_color(colors.get(key))
        if color and color.upper() != accent.upper():
            return color
    primary = _unwrap_color(colors.get("primary"))
    if primary and primary.upper() != accent.upper():
        return primary
    return "#F3B71B"


def _muted(colors, paper, ink):
    secondary = _unwrap_color(colors.get("secondary"))
    if secondary and contrast_ratio(secondary, paper) >= 4.5 and secondary.upper() != ink.upper():
        return secondary
    return "#3D4451"


def _typefaces(typography):
    display = str(typography.get("headingFont") or "").strip() or "Inter"
    body = str(typography.get("bodyFont") or display).strip() or display
    styles = typography.get("styles") if isinstance(typography.get("styles"), list) else []
    if display == "Inter" and styles:
        first = styles[0] if isinstance(styles[0], dict) else {}
        family = str(first.get("family") or "").strip()
        if family:
            display = family
            body = str(typography.get("bodyFont") or family).strip() or family
    return display[:80], body[:80]


def _button_radius(radius):
    scale = radius.get("scale") if isinstance(radius.get("scale"), list) else []
    if not scale and isinstance(radius.get("values"), list):
        scale = radius["values"]
    for item in scale:
        value = str(item or "").strip()
        if not value or value.lower() in PILL_RADIUS:
            continue
        if value in {"0", "0px", "0rem"}:
            continue
        return value[:16]
    return "0.25rem"


def compile_ad_voice(payload, *, colors=None, typography=None):
    """Primitivas da extract viram voz de anúncio — sem navbar, card ou sombra de página."""
    payload = payload if isinstance(payload, dict) else {}
    colors = colors if isinstance(colors, dict) else {}
    typography = typography if isinstance(typography, dict) else (
        payload.get("typography") if isinstance(payload.get("typography"), dict) else {}
    )
    spacing = _scale_of(payload.get("spacing"), "commonValues")
    shadows = _scale_of(payload.get("shadows"), "values")
    step = _spacing_step(spacing)
    density = "compact" if step <= 5 else ("airy" if step >= 12 else "regular")
    shadow = _cta_shadow(shadows)
    display_weight, cta_weight = _type_weights(typography)
    tracking = _tracking(typography, density)
    tokens = {
        "weight-display": display_weight,
        "weight-cta": cta_weight,
        "tracking": tracking,
        "cta-pad": {
            "compact": "0.55em 0.95em",
            "airy": "0.9em 1.55em",
            "regular": "0.7em 1.2em",
        }[density],
        "cta-shadow": shadow,
        "hairline": _hairline(colors),
        "safe": {"compact": "4%", "airy": "8%", "regular": "6%"}[density],
    }
    return {
        "tokens": tokens,
        "voice": {
            "density": density,
            "elevation": "lifted" if shadow != "none" else "flat",
            "step_px": step,
        },
    }


def _scale_of(bucket, extra_key):
    data = bucket if isinstance(bucket, dict) else {}
    scale = list(data.get("scale") or [])
    if not scale and isinstance(data.get(extra_key), list):
        for item in data[extra_key]:
            if isinstance(item, dict):
                scale.append(item.get("px") or item.get("value") or item.get("$value"))
            else:
                scale.append(item)
    if not scale and isinstance(bucket, list):
        scale = bucket
    return [str(item).strip() for item in scale if item]


def _spacing_step(scale):
    values = []
    for item in scale:
        px = _to_px(item)
        if px is not None and 2 <= px <= 32:
            values.append(px)
    return min(values) if values else 8.0


def _to_px(value):
    text = str(value or "").strip().lower()
    try:
        if text.endswith("rem"):
            return float(text[:-3]) * 16
        if text.endswith("px"):
            return float(text[:-2])
        return float(text)
    except (TypeError, ValueError):
        return None


def _type_weights(typography):
    styles = typography.get("styles") if isinstance(typography.get("styles"), list) else []
    heading = 700
    cta = 600
    for index, item in enumerate(styles):
        if not isinstance(item, dict):
            continue
        weight = _weight(item.get("weight") or item.get("fontWeight") or item.get("font-weight"))
        if weight is None:
            continue
        if index == 0 or str(item.get("role") or "").lower() in {"heading", "display", "headline"}:
            heading = weight
        if str(item.get("role") or "").lower() in {"cta", "button", "action"}:
            cta = weight
    return str(max(500, min(800, heading))), str(max(500, min(700, cta)))


def _weight(value):
    text = str(value or "").strip().lower()
    named = {"medium": 500, "semibold": 600, "bold": 700, "extrabold": 800}
    if text in named:
        return named[text]
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _tracking(typography, density):
    styles = typography.get("styles") if isinstance(typography.get("styles"), list) else []
    for item in styles:
        if not isinstance(item, dict):
            continue
        raw = item.get("letterSpacing") or item.get("letter-spacing") or item.get("tracking")
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if text.endswith("em") or text.endswith("px"):
            return text[:12]
        try:
            number = float(text)
        except (TypeError, ValueError):
            continue
        return f"{max(-0.04, min(0.06, number))}em"
    return {"compact": "-0.03em", "airy": "0", "regular": "-0.015em"}[density]


def _cta_shadow(scale):
    generic = (".1)", "0.1)", "0.08)", "0.05)", "0 1px 2px", "0 1px 3px")
    for item in scale:
        text = str(item or "").strip()
        if not text or text.lower() == "none" or "inset" in text.lower():
            continue
        low = text.lower()
        if any(hint in low for hint in generic):
            continue
        blur = _shadow_blur(text)
        if blur is not None and (blur < 4 or blur > 20):
            continue
        return text[:160]
    return "none"


def _shadow_blur(value):
    numbers = []
    current = ""
    for char in str(value):
        if char.isdigit() or char in ".-":
            current += char
            continue
        if current:
            try:
                numbers.append(float(current))
            except ValueError:
                pass
            current = ""
    if current:
        try:
            numbers.append(float(current))
        except ValueError:
            pass
    if len(numbers) >= 3:
        return abs(numbers[2])
    return None


def _hairline(colors):
    for key in ("border", "hairline", "line", "stroke"):
        color = _unwrap_color(colors.get(key))
        if color:
            return color
    css = colors.get("cssVariables") if isinstance(colors.get("cssVariables"), dict) else {}
    for key, value in css.items():
        name = str(key).lower()
        if "border" in name or name.endswith("line") or "stroke" in name:
            color = _unwrap_color(value)
            if color:
                return color
    muted = _unwrap_color(colors.get("secondary") or colors.get("muted"))
    return muted or "#3D4451"
