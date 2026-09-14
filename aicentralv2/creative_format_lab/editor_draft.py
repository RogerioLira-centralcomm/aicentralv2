"""Bounded, versioned draft for the still editor; independent of generated versions."""

import math

FIELD_LIMITS = {
    "mcSwapHeadline": 80, "mcSwapSupport": 160, "mcTrocrSubtitle": 80,
    "mcTrocrDates": 80, "mcTrocrVenue": 80, "mcTrocrPrice": 40,
    "mcSwapCta": 40, "mcTrocrCta2": 40, "mcTrocrLogo": 40,
    "mcTrocrDisclaimer": 160, "mcSwapNote": 500, "mcTrocrPrompt": 16000,
}
GROUPS = {"mcTrocrPreserve", "mcTrocrAlter", "mcTrocrAnalysis"}
RATIOS = {"16:9", "9:16", "4:5", "1:1"}


def normalize_editor_draft(raw):
    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("Versão de edição inválida. Recarregue o editor.")
    base = raw.get("base_id")
    if not isinstance(base, str) or not base or len(base) > 64:
        raise ValueError("A edição precisa de uma versão base válida.")
    values = raw.get("values") or {}
    checks = raw.get("checks") or {}
    if not isinstance(values, dict) or not isinstance(checks, dict):
        raise ValueError("Campos de edição inválidos.")
    clean_values = {}
    for key, limit in FIELD_LIMITS.items():
        if key not in values:
            continue
        value = values[key]
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"Campo {key} excede o limite de {limit} caracteres.")
        clean_values[key] = value
    clean_checks = {}
    for key in GROUPS:
        if key not in checks:
            continue
        items = checks[key]
        if not isinstance(items, list) or len(items) > 32 or any(not isinstance(item, str) or len(item) > 32 for item in items):
            raise ValueError("Seleção de elementos inválida.")
        clean_checks[key] = list(dict.fromkeys(items))
    ratio = raw.get("aspect_ratio", "16:9")
    if ratio not in RATIOS:
        raise ValueError("Formato da edição inválido.")
    region = raw.get("region")
    if region is not None:
        if not isinstance(region, dict) or region.get("field") not in {"headline", "secondary", "price", "cta"}:
            raise ValueError("Região de edição inválida.")
        box = region.get("box")
        width, height = region.get("ref_width"), region.get("ref_height")
        numbers = [width, height] + (box if isinstance(box, list) else [])
        if len(numbers) != 6 or any(type(n) not in (int, float) or not math.isfinite(n) for n in numbers):
            raise ValueError("Coordenadas da região inválidas.")
        if not (0 < width <= 20000 and 0 < height <= 20000 and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
            raise ValueError("A região deve ficar dentro da imagem.")
        region = {"field": region["field"], "box": list(box), "ref_width": width, "ref_height": height}
    return {
        "version": 1, "base_id": base, "values": clean_values, "checks": clean_checks,
        "aspect_ratio": ratio, "region": region,
        "quality": "production" if raw.get("quality") == "production" else "draft",
        "brand_context": raw.get("brand_context") is True,
        "prompt_edited": raw.get("prompt_edited") is True,
        "prompt_locked": raw.get("prompt_locked") is True,
        "force_image": raw.get("force_image") is True,
    }
