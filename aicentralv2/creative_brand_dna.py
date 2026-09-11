"""DNA da marca como contrato, não como painel decorativo.

Fica em JSON (brand_profile.brand_dna e creative_brief.bancada.brand_dna).
Não cria tabela — a migration fica para quando o time pedir.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

SCENE_ROLES = (
    "gancho",
    "contexto",
    "beneficio",
    "fechamento",
    "prova",
    "unico",
)

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _text(value, default="", limit=240):
    text = str(value or "").strip()
    return (text or default)[:limit]


def _hex(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not raw.startswith("#") and re.fullmatch(r"[0-9a-fA-F]{3,6}", raw):
        raw = f"#{raw}"
    return raw if _HEX.match(raw) else ""


def _palette(items):
    colors = []
    for item in items or []:
        if isinstance(item, dict):
            color = _hex(item.get("hex") or item.get("color") or item.get("value"))
        else:
            color = _hex(item)
        if color and color.upper() not in {c.upper() for c in colors}:
            colors.append(color)
        if len(colors) >= 8:
            break
    return colors


def _fonts_from_profile(profile):
    fonts = profile.get("fonts") if isinstance(profile, dict) else []
    if not isinstance(fonts, list):
        fonts = []
    primary = ""
    fallback = ""
    for item in fonts:
        if not isinstance(item, dict):
            continue
        family = _text(item.get("family"), limit=80)
        role = str(item.get("role") or "").strip().lower()
        if not family:
            continue
        if role in {"display", "heading", "headline", "title", "primary"} and not primary:
            primary = family
        elif not fallback:
            fallback = family
    if not primary and fonts:
        first = fonts[0]
        primary = _text(first.get("family") if isinstance(first, dict) else first, limit=80)
    return primary, fallback or primary


def materialize_brand_dna(client=None, profile=None, existing=None):
    """Monta um DNA versionado a partir do cliente / perfil / snapshot já gravado."""
    client = client if isinstance(client, dict) else {}
    profile = profile if isinstance(profile, dict) else (client.get("brand_profile") or {})
    if not isinstance(profile, dict):
        profile = {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    previous = existing if isinstance(existing, dict) else (profile.get("brand_dna") or {})
    if not isinstance(previous, dict):
        previous = {}

    prev_colors = previous.get("colors") if isinstance(previous.get("colors"), dict) else {}
    palette = _palette(
        prev_colors.get("palette")
        or line.get("color_palette")
        or profile.get("color_palette")
    )
    if client.get("primary_color"):
        palette = _palette([client.get("primary_color"), *palette])
    if client.get("secondary_color"):
        palette = _palette([*palette, client.get("secondary_color")])
    accent = _hex(
        (previous.get("colors") or {}).get("accent")
        if isinstance(previous.get("colors"), dict)
        else ""
    ) or (palette[1] if len(palette) > 1 else (palette[0] if palette else "#1E4D4F"))

    prev_fonts = previous.get("fonts") if isinstance(previous.get("fonts"), dict) else {}
    primary, fallback = _fonts_from_profile(profile)
    primary = _text(prev_fonts.get("primary") or primary or "Manrope", default="Manrope", limit=80)
    fallback = _text(prev_fonts.get("fallback") or fallback or primary or "Manrope", default=primary, limit=80)

    prev_logo = previous.get("logo") if isinstance(previous.get("logo"), dict) else {}
    logo_url = _text(
        prev_logo.get("asset_url")
        or client.get("logo_upload_path")
        or client.get("logo_url"),
        limit=500,
    )
    positions = prev_logo.get("allowed_positions") or ["top-right", "top-left"]
    if not isinstance(positions, list) or not positions:
        positions = ["top-right", "top-left"]

    prev_limits = previous.get("text_limits") if isinstance(previous.get("text_limits"), dict) else {}
    try:
        headline_max = max(8, min(80, int(prev_limits.get("headline_max_chars") or 42)))
    except (TypeError, ValueError):
        headline_max = 42
    try:
        subhead_max = max(8, min(140, int(prev_limits.get("subhead_max_chars") or 72)))
    except (TypeError, ValueError):
        subhead_max = 72

    client_id = client.get("id") or previous.get("client_id") or "marca"
    version = int(previous.get("version") or 1)
    dna_id = _text(previous.get("id") or f"dna-{client_id}-v{version}", default=f"dna-{client_id}-v1", limit=80)

    return {
        "id": dna_id,
        "version": version,
        "client_id": client_id,
        "fonts": {"primary": primary, "fallback": fallback},
        "colors": {"palette": palette or ["#183436", "#1E4D4F"], "accent": accent},
        "logo": {
            "asset_url": logo_url,
            "min_clear_space": float(prev_logo.get("min_clear_space") or 8),
            "allowed_positions": [str(item)[:32] for item in positions[:6]],
        },
        "voice_tone": _text(
            previous.get("voice_tone")
            or client.get("tone_of_voice")
            or profile.get("brand_summary")
            or line.get("signature_summary"),
            default="Tom da marca.",
            limit=400,
        ),
        "text_limits": {
            "headline_max_chars": headline_max,
            "subhead_max_chars": subhead_max,
        },
    }


def clamp_copy(text, max_chars):
    value = str(text or "").strip()
    limit = max(1, int(max_chars or 42))
    if len(value) <= limit:
        return value
    clipped = value[:limit].rstrip()
    if " " in clipped and limit > 8:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped


def apply_brand_dna_to_layers(layers, dna):
    """Propaga fonte, logo e teto de caracteres para todas as camadas da cena."""
    dna = materialize_brand_dna(existing=dna)
    fonts = dna["fonts"]
    logo_url = dna["logo"]["asset_url"]
    limits = dna["text_limits"]
    applied = []
    for item in layers or []:
        if not isinstance(item, dict):
            continue
        layer = dict(item)
        content = dict(layer.get("content") or {})
        tipo = str(layer.get("tipo") or "").strip().lower()
        if tipo in {"texto", "anotacao"}:
            content["font"] = fonts["primary"]
            if content.get("text"):
                content["text"] = clamp_copy(content["text"], limits["headline_max_chars"])
        elif tipo in {"cta", "overlay"}:
            content["font"] = fonts["fallback"] or fonts["primary"]
            if content.get("text"):
                content["text"] = clamp_copy(content["text"], limits["subhead_max_chars"])
        elif tipo == "logo" and logo_url:
            content["src"] = logo_url
        layer["content"] = content
        layer["brand_dna_id"] = dna["id"]
        applied.append(layer)
    return applied


_SAFE_NEUTRALS = {"#FFF", "#FFFFFF", "#000", "#000000"}


def _color_near_palette(color, palette, tolerance=28):
    sample = _hex(color)
    if not sample or not palette:
        return True
    if sample.upper() in _SAFE_NEUTRALS:
        return True
    if any(sample.upper() == _hex(item).upper() for item in palette):
        return True

    def rgb(value):
        raw = _hex(value).lstrip("#")
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))

    try:
        sr, sg, sb = rgb(sample)
    except ValueError:
        return True
    for item in palette:
        try:
            pr, pg, pb = rgb(item)
        except ValueError:
            continue
        if abs(sr - pr) + abs(sg - pg) + abs(sb - pb) <= tolerance * 3:
            return True
    return False


def check_brand_dna(layers, dna, format_rect=None):
    """Gate determinístico. Cada violação tem motivo específico."""
    dna = materialize_brand_dna(existing=dna)
    fonts = {dna["fonts"]["primary"].lower(), dna["fonts"]["fallback"].lower()}
    fonts.discard("")
    limits = dna["text_limits"]
    palette = list(dna["colors"]["palette"] or []) + [dna["colors"]["accent"]]
    logo_url = dna["logo"]["asset_url"]
    violations = []
    for index, item in enumerate(layers or []):
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or "").lower()
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        label = str(item.get("id") or tipo or f"camada-{index + 1}")
        if tipo in {"texto", "cta", "overlay", "anotacao"}:
            used = str(content.get("font") or "").strip()
            if used and used.lower() not in fonts:
                violations.append(f"{label}: fonte {used} não é {dna['fonts']['primary']}.")
            text = str(content.get("text") or "")
            limit = limits["headline_max_chars"] if tipo in {"texto", "anotacao"} else limits["subhead_max_chars"]
            if len(text) > limit:
                violations.append(f"{label}: texto com {len(text)} caracteres ultrapassa {limit}.")
        if tipo == "logo" and logo_url:
            src = str(content.get("src") or "")
            if src and src != logo_url:
                violations.append(f"{label}: logo não é o asset do DNA.")
        color = content.get("color") or content.get("fill")
        if color and tipo in {"texto", "cta", "overlay", "forma", "fundo"} and not _color_near_palette(color, palette):
            violations.append(f"{label}: cor {color} fora da paleta.")
        try:
            x = float(item.get("x") or 0)
            y = float(item.get("y") or 0)
            w = float(item.get("w") or 0)
            h = float(item.get("h") or 0)
        except (TypeError, ValueError):
            continue
        if x < -0.5 or y < -0.5 or x + w > 100.5 or y + h > 100.5:
            violations.append(f"{label}: bounding box fora do retângulo do formato.")
    if format_rect and isinstance(format_rect, dict):
        pass
    return {
        "passed": not violations,
        "violations": violations,
        "brand_dna_id": dna["id"],
    }


def scene_role_for_index(index, total):
    if total <= 1:
        return "unico"
    order = ("gancho", "contexto", "beneficio", "fechamento")
    if index >= len(order):
        return "prova" if index < total - 1 else "fechamento"
    if total <= 4:
        return order[index]
    return order[index] if index < 4 else ("prova" if index < total - 1 else "fechamento")


def attach_brand_dna_to_scenes(scenes, dna, regenerate=None):
    dna = materialize_brand_dna(existing=dna)
    cards = []
    total = len([item for item in (scenes or []) if isinstance(item, dict)])
    for index, item in enumerate(scenes or []):
        if not isinstance(item, dict):
            continue
        card = dict(item)
        card["brand_dna_id"] = dna["id"]
        card["role"] = card.get("role") or scene_role_for_index(index, total)
        card["layers"] = apply_brand_dna_to_layers(card.get("layers") or [], dna)
        if regenerate and not card.get("regenerate"):
            card["regenerate"] = list(regenerate)
        cards.append(card)
    return cards
