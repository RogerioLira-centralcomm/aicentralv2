"""Black-and-white composition masks for ad creatives.

A mask is a deterministic function of (format, family, logo, cta): the same inputs always draw
the same wireframe and the same written zone spec. Zones are stored as fractions of the canvas, so the
picture and the prompt text can never disagree, and one family unfolds consistently across formats.

Visual language (no colour, no words, nothing a model could mistake for artwork):
  hatched mid-grey block ....... main subject / image area
  white block with black frame . flat text panel (only in "split" family)
  stacked black bars ........... headline
  black pill ................... CTA button
  dashed empty rectangle ....... logo space (kept clean; the Studio applies the logo afterwards)
  light grey ................... scene / background that continues full-bleed
"""
from __future__ import annotations

import io
import math
import re

from PIL import Image, ImageDraw

# key -> (label, width, height, group). Dimensions match the Studio format catalog (creative_format_registry).
FORMATS = {
    "feed-4x5": ("Feed 4:5", 1080, 1350, "social"),
    "feed-1x1": ("Feed 1:1", 1080, 1080, "social"),
    "story-9x16": ("Stories e Reels 9:16", 1080, 1920, "social"),
    "linkedin-1200x627": ("LinkedIn 1.91:1", 1200, 627, "social"),
    "youtube-16x9": ("YouTube in-feed 16:9", 1920, 1080, "social"),
    "iab-300x250": ("IAB 300×250", 300, 250, "iab"),
    "display-300x300": ("Display 300×300", 300, 300, "iab"),
    "iab-300x600": ("IAB 300×600", 300, 600, "iab"),
    "iab-160x600": ("IAB 160×600", 160, 600, "iab"),
    "iab-970x250": ("IAB 970×250", 970, 250, "iab"),
    "iab-728x90": ("IAB 728×90", 728, 90, "iab"),
    "iab-320x50": ("IAB 320×50", 320, 50, "iab"),
    "iab-336x280": ("IAB 336×280", 336, 280, "iab"),
    "display-250x250": ("Display 250×250", 250, 250, "iab"),
    "display-200x200": ("Display 200×200", 200, 200, "iab"),
    "display-180x150": ("Display 180×150", 180, 150, "iab"),
    "display-240x400": ("Display 240×400", 240, 400, "iab"),
    "iab-300x1050": ("IAB 300×1050", 300, 1050, "iab"),
    "iab-120x600": ("IAB 120×600", 120, 600, "iab"),
    "display-120x240": ("Display 120×240", 120, 240, "iab"),
    "iab-970x90": ("IAB 970×90", 970, 90, "iab"),
    "iab-468x60": ("IAB 468×60", 468, 60, "iab"),
    "iab-234x60": ("IAB 234×60", 234, 60, "iab"),
    "iab-320x100": ("IAB 320×100", 320, 100, "iab"),
    "iab-300x50": ("IAB 300×50", 300, 50, "iab"),
    "display-300x100": ("Display 300×100", 300, 100, "iab"),
    "interstitial-320x480": ("Intersticial 320×480", 320, 480, "iab"),
    "interstitial-480x320": ("Intersticial 480×320", 480, 320, "iab"),
}

# Entry in the Studio format registry that defines each format's required/forbidden elements.
REGISTRY_KEYS = {
    "feed-4x5": "feed-4x5", "feed-1x1": "feed-1x1", "story-9x16": "story-9x16",
    "linkedin-1200x627": "linkedin-landscape", "youtube-16x9": "youtube-infeed",
    "iab-300x250": "iab-medium", "display-300x300": "display-300x300", "iab-300x600": "iab-halfpage",
    "iab-160x600": "iab-skyscraper", "iab-970x250": "iab-billboard", "iab-728x90": "iab-leaderboard",
    "iab-320x50": "iab-mobile",
    "iab-336x280": "iab-large-rectangle", "display-250x250": "display-250x250", "display-200x200": "display-200x200",
    "display-180x150": "display-180x150", "display-240x400": "display-240x400", "iab-300x1050": "iab-portrait",
    "iab-120x600": "iab-skyscraper-120", "display-120x240": "display-120x240", "iab-970x90": "iab-large-leaderboard",
    "iab-468x60": "iab-full-banner", "iab-234x60": "iab-half-banner", "iab-320x100": "iab-large-mobile",
    "iab-300x50": "iab-mobile-300", "display-300x100": "display-300x100",
    "interstitial-320x480": "interstitial-320x480", "interstitial-480x320": "interstitial-480x320",
}

# Extra rules that go into the written contract, from the format's platform constraints.
FORMAT_NOTES = {
    "story-9x16": "The top 12% and the bottom 20% of the canvas are covered by the app interface: no text, button or logo there, but the photograph continues full-bleed behind them.",
    "youtube-16x9": "This placement uses the headline only: do not draw any button, pill, price or call-to-action.",
    "iab-728x90": "Compact banner: use only a calm, plain background image; no product, no people, no small print.",
    "iab-320x50": "Compact banner: use only a calm, plain background image; no product, no people, no small print.",
    **{key: "Compact banner: use only a calm, plain background image; no product, no people, no small print."
       for key in ("iab-970x90", "iab-468x60", "iab-234x60", "iab-320x100", "iab-300x50", "display-300x100")},
}

# Providers only accept a few ratios; formats beyond this spread are generated at the closest
# supported ratio and finished by the Studio (see `strategy`).
PROVIDER_RATIOS = ((1, 1), (3, 2), (2, 3), (4, 3), (3, 4), (16, 9), (9, 16), (21, 9))

# family -> (label, description)
FAMILIES = {
    "foto-texto-base": ("Foto com texto na base", "Imagem full-bleed; título e CTA ocupam a parte calma de baixo."),
    "foto-texto-topo": ("Foto com texto no topo", "Título no alto, assunto no meio, CTA embaixo."),
    "assunto-na-base": ("Assunto na base", "Texto no alto sobre cena calma; assunto ancora a parte inferior."),
    "split": ("Painel de texto + imagem", "Painel chapado de texto de um lado, imagem do outro."),
    "produto-destaque": ("Produto em destaque", "Assunto centralizado e grande, título acima, CTA abaixo."),
    "tipografico": ("Tipográfico", "Título domina a peça; assunto pequeno e de apoio."),
    "visual-puro": ("Visual puro", "Só imagem, sem título nem CTA."),
    "compacto": ("Banner compacto", "Título, CTA e logo sobre fundo calmo; sem produto nem pessoas."),
    "texto-central": ("Texto central", "Cena full-bleed; título e CTA centralizados no meio da peça."),
    "cartao-flutuante": ("Cartão flutuante", "Cartão chapado com título e CTA flutuando sobre a foto."),
    "faixa-inferior": ("Faixa inferior", "Foto em cima; faixa chapada embaixo com o texto."),
    "texto-direita": ("Texto à direita", "Assunto à esquerda, texto alinhado à direita."),
    "minimalista": ("Minimalista", "Muito respiro; assunto pequeno e título discreto."),
    "compacto-central": ("Banner compacto central", "Título centralizado com CTA à esquerda; sem produto nem pessoas."),
    "compacto-logo-esquerda": ("Banner compacto com logo à esquerda", "Logo à esquerda, título ao centro, CTA à direita."),
}

LOGO_OPTIONS = {"none": "Sem logo", "bottom-right": "Logo embaixo à direita", "top-left": "Logo em cima à esquerda"}

ZONE_NAMES = {"subject": "MAIN SUBJECT", "panel": "TEXT PANEL", "headline": "HEADLINE", "cta": "CTA BUTTON", "logo": "LOGO SPACE"}

CTA_SCALE_W, CTA_SCALE_H = 0.68, 0.72
LOGO_WIDTH, LOGO_HEIGHT = 0.16, 0.07  # share of canvas width / height, same as the Studio applies

# Zones as (x, y, w, h) fractions of the SAFE rectangle, per layout class.
# vertical: ratio < 0.95 · square: 0.95–1.3 · landscape: 1.3–2.4 · wide: > 2.4
_LAYOUTS = {
    "foto-texto-base": {
        "vertical": {"subject": (0, 0.04, 1, 0.52), "headline": (0, 0.60, 0.9, 0.18), "cta": (0, 0.83, 0.5, 0.1)},
        "square": {"subject": (0, 0, 1, 0.58), "headline": (0, 0.62, 0.9, 0.2), "cta": (0, 0.85, 0.4, 0.12)},
        "landscape": {"subject": (0.5, 0, 0.5, 0.74), "headline": (0, 0.46, 0.44, 0.3), "cta": (0, 0.8, 0.24, 0.15)},
        "wide": {"subject": (0.52, 0, 0.48, 1), "headline": (0, 0.14, 0.48, 0.5), "cta": (0, 0.7, 0.18, 0.24)},
    },
    "foto-texto-topo": {
        "vertical": {"headline": (0, 0.02, 0.9, 0.2), "subject": (0, 0.28, 1, 0.52), "cta": (0, 0.86, 0.5, 0.1)},
        "square": {"headline": (0, 0, 0.9, 0.22), "subject": (0, 0.28, 1, 0.52), "cta": (0, 0.86, 0.4, 0.12)},
        "landscape": {"headline": (0, 0.04, 0.44, 0.3), "subject": (0.5, 0, 0.5, 0.82), "cta": (0, 0.42, 0.22, 0.16)},
        "wide": {"subject": (0, 0, 0.4, 1), "headline": (0.46, 0.14, 0.4, 0.5), "cta": (0.46, 0.7, 0.18, 0.24)},
    },
    "assunto-na-base": {
        "vertical": {"headline": (0, 0.04, 0.9, 0.2), "cta": (0, 0.27, 0.5, 0.09), "subject": (0, 0.42, 1, 0.56)},
        "square": {"headline": (0, 0.02, 0.85, 0.26), "cta": (0, 0.31, 0.34, 0.11), "subject": (0, 0.48, 1, 0.5)},
        "landscape": {"subject": (0, 0.06, 0.52, 0.88), "headline": (0.58, 0.14, 0.42, 0.36), "cta": (0.58, 0.58, 0.22, 0.16)},
        "wide": {"subject": (0, 0, 0.45, 1), "headline": (0.52, 0.14, 0.4, 0.5), "cta": (0.52, 0.7, 0.18, 0.24)},
    },
    "split": {
        "vertical": {"subject": (0, 0, 1, 0.56), "panel": (0, 0.6, 1, 0.4), "headline": (0.05, 0.65, 0.9, 0.14), "cta": (0.05, 0.84, 0.46, 0.09)},
        "square": {"panel": (0, 0, 0.5, 1), "subject": (0.5, 0, 0.5, 1), "headline": (0.05, 0.16, 0.4, 0.38), "cta": (0.05, 0.64, 0.3, 0.12)},
        "landscape": {"panel": (0, 0, 0.42, 1), "subject": (0.42, 0, 0.58, 1), "headline": (0.04, 0.16, 0.34, 0.4), "cta": (0.04, 0.66, 0.2, 0.16)},
        "wide": {"panel": (0, 0, 0.4, 1), "subject": (0.4, 0, 0.6, 1), "headline": (0.03, 0.14, 0.34, 0.5), "cta": (0.03, 0.7, 0.16, 0.24)},
    },
    "produto-destaque": {
        "vertical": {"headline": (0, 0.02, 0.9, 0.14), "subject": (0.08, 0.2, 0.84, 0.6), "cta": (0.2, 0.84, 0.6, 0.1)},
        "square": {"headline": (0, 0, 1, 0.16), "subject": (0.15, 0.2, 0.7, 0.58), "cta": (0.28, 0.84, 0.44, 0.13)},
        "landscape": {"headline": (0, 0.1, 0.28, 0.45), "subject": (0.3, 0.04, 0.4, 0.78), "cta": (0, 0.66, 0.26, 0.16)},
        "wide": {"headline": (0, 0.14, 0.3, 0.5), "subject": (0.34, 0, 0.3, 1), "cta": (0, 0.7, 0.18, 0.24)},
    },
    "tipografico": {
        "vertical": {"headline": (0, 0.05, 1, 0.5), "subject": (0.3, 0.6, 0.7, 0.26), "cta": (0, 0.88, 0.5, 0.09)},
        "square": {"headline": (0, 0.04, 1, 0.5), "subject": (0.45, 0.58, 0.55, 0.28), "cta": (0, 0.84, 0.36, 0.13)},
        "landscape": {"headline": (0, 0.06, 0.7, 0.52), "subject": (0.62, 0.3, 0.38, 0.6), "cta": (0, 0.7, 0.2, 0.16)},
        "wide": {"headline": (0, 0.1, 0.62, 0.8), "subject": (0.68, 0, 0.32, 1), "cta": (0.0, 0.0, 0, 0)},
    },
    "compacto": {
        "wide": {"headline": (0, 0.12, 0.5, 0.76), "cta": (0.54, 0.2, 0.22, 0.6)},
    },
    "compacto-central": {
        "wide": {"headline": (0.25, 0.12, 0.5, 0.76), "cta": (0, 0.2, 0.18, 0.6)},
    },
    "compacto-logo-esquerda": {
        "wide": {"headline": (0.2, 0.12, 0.5, 0.76), "cta": (0.74, 0.2, 0.2, 0.6)},
    },
    "texto-central": {
        "vertical": {"headline": (0.08, 0.36, 0.84, 0.18), "cta": (0.3, 0.6, 0.4, 0.08)},
        "square": {"headline": (0.08, 0.34, 0.84, 0.2), "cta": (0.3, 0.6, 0.4, 0.11)},
        "landscape": {"headline": (0.15, 0.28, 0.7, 0.26), "cta": (0.38, 0.62, 0.24, 0.15)},
        "wide": {"headline": (0.2, 0.12, 0.6, 0.5), "cta": (0.4, 0.68, 0.2, 0.24)},
    },
    "cartao-flutuante": {
        "vertical": {"subject": (0, 0, 1, 0.48), "panel": (0.06, 0.52, 0.88, 0.34), "headline": (0.12, 0.57, 0.76, 0.14), "cta": (0.12, 0.75, 0.46, 0.07)},
        "square": {"subject": (0.25, 0, 0.75, 0.55), "panel": (0.05, 0.5, 0.62, 0.44), "headline": (0.1, 0.55, 0.52, 0.2), "cta": (0.1, 0.8, 0.3, 0.1)},
        "landscape": {"subject": (0.5, 0, 0.5, 0.85), "panel": (0.04, 0.18, 0.44, 0.64), "headline": (0.08, 0.26, 0.36, 0.3), "cta": (0.08, 0.64, 0.2, 0.12)},
        "wide": {"subject": (0.5, 0, 0.5, 1), "panel": (0.02, 0.1, 0.42, 0.8), "headline": (0.05, 0.18, 0.36, 0.4), "cta": (0.05, 0.64, 0.16, 0.22)},
    },
    "faixa-inferior": {
        "vertical": {"subject": (0, 0, 1, 0.66), "panel": (0, 0.7, 1, 0.3), "headline": (0.05, 0.74, 0.9, 0.12), "cta": (0.05, 0.88, 0.4, 0.08)},
        "square": {"subject": (0, 0, 1, 0.62), "panel": (0, 0.66, 1, 0.34), "headline": (0.04, 0.7, 0.6, 0.14), "cta": (0.04, 0.86, 0.3, 0.1)},
        "landscape": {"subject": (0, 0, 1, 0.62), "panel": (0, 0.66, 1, 0.34), "headline": (0.03, 0.72, 0.55, 0.2), "cta": (0.62, 0.74, 0.18, 0.16)},
    },
    "texto-direita": {
        "vertical": {"headline": (0.3, 0.04, 0.7, 0.2), "cta": (0.5, 0.27, 0.5, 0.08), "subject": (0, 0.42, 1, 0.56)},
        "square": {"subject": (0, 0, 0.5, 1), "headline": (0.55, 0.14, 0.45, 0.38), "cta": (0.55, 0.62, 0.3, 0.12)},
        "landscape": {"subject": (0, 0, 0.5, 1), "headline": (0.56, 0.12, 0.44, 0.38), "cta": (0.56, 0.58, 0.22, 0.15)},
        "wide": {"subject": (0, 0, 0.45, 1), "headline": (0.5, 0.12, 0.36, 0.5), "cta": (0.5, 0.7, 0.16, 0.24)},
    },
    "minimalista": {
        "vertical": {"subject": (0.35, 0.2, 0.5, 0.36), "headline": (0, 0.7, 0.6, 0.1), "cta": (0, 0.84, 0.36, 0.07)},
        "square": {"subject": (0.45, 0.1, 0.45, 0.45), "headline": (0, 0.68, 0.55, 0.12), "cta": (0, 0.85, 0.28, 0.1)},
        "landscape": {"subject": (0.6, 0.1, 0.3, 0.6), "headline": (0, 0.6, 0.45, 0.18), "cta": (0, 0.82, 0.16, 0.13)},
        "wide": {"subject": (0.7, 0.1, 0.25, 0.8), "headline": (0, 0.3, 0.45, 0.4), "cta": (0, 0.75, 0.14, 0.2)},
    },
    "visual-puro": {
        "vertical": {"subject": (0, 0, 1, 1)},
        "square": {"subject": (0, 0, 1, 1)},
        "landscape": {"subject": (0, 0, 1, 1)},
        "wide": {"subject": (0, 0, 1, 1)},
    },
}


def ratio_label(width, height):
    """Reduced W:H label such as '4:5' (falls back to the exact pixels for odd shapes)."""
    divisor = math.gcd(int(width), int(height))
    w, h = int(width) // divisor, int(height) // divisor
    return f"{w}:{h}" if max(w, h) <= 32 else f"{width}:{height}"


def layout_class(width, height):
    ratio = width / height
    return "vertical" if ratio < 0.95 else "square" if ratio < 1.3 else "landscape" if ratio < 2.4 else "wide"


def provider_ratio(width, height):
    """Closest ratio an image provider accepts, as 'W:H'."""
    target = width / height
    best = min(PROVIDER_RATIOS, key=lambda item: abs(math.log(target / (item[0] / item[1]))))
    return f"{best[0]}:{best[1]}"


def strategy(width, height):
    """'native' when the provider ratio is close; 'compose' when the Studio must finish the piece."""
    target = width / height
    provider = provider_ratio(width, height)
    w, h = (int(part) for part in provider.split(":"))
    return "native" if abs(math.log(target / (w / h))) <= math.log(1.45) else "compose"


def _safe_rect(width, height):
    """Safe area as fractions of the canvas: 8% of the short side, plus story UI bands."""
    margin = 0.08 * min(width, height)
    margin_x = max(margin, 0.035 * width) if layout_class(width, height) == "wide" else margin
    left, right = margin_x / width, 1 - margin_x / width
    top, bottom = margin / height, 1 - margin / height
    if height / width >= 1.7 and height >= 1500:  # story / reels interface overlays
        top, bottom = max(top, 0.12), min(bottom, 0.80)
    return left, top, right, bottom


def _logo_rect(width, height, corner, safe):
    """Logo slot anchored flush to the corner of the safe frame (fractions of the canvas)."""
    left, top, right, bottom = safe
    if layout_class(width, height) == "wide":
        w, h = 0.16, 0.45
    else:
        w, h = LOGO_WIDTH, LOGO_HEIGHT
    w, h = min(w, 0.4), min(h, 0.4)
    x = left if corner.endswith("left") else right - w
    y = top if corner.startswith("top") else bottom - h
    return (x, y, w, h)


def _intersects(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _clear_logo(zone_name, rect, logo, corner, gap=0.012):
    """Move or trim a zone so the logo corner stays calm."""
    if not logo or not _intersects(rect, logo):
        return rect
    x, y, w, h = rect
    if zone_name == "panel":
        return rect  # the logo space sits on top of the flat panel
    if corner.startswith("bottom"):
        if zone_name == "subject":
            return (x, y, w, max(0.05, logo[1] - gap - y))
        return (x, y, max(0.05, min(w, logo[0] - gap - x)), h)
    bottom = logo[1] + logo[3] + gap
    if zone_name in {"headline", "cta"}:
        return (x, bottom, w, max(0.04, min(h, y + h - bottom)))
    return (x, bottom, w, max(0.05, y + h - bottom))


def build_spec(format_key, family, logo="bottom-right", cta=True):
    """Resolve one mask to named zones (fractions of the canvas) plus metadata."""
    if format_key not in FORMATS:
        raise ValueError("Formato de máscara desconhecido.")
    if family not in FAMILIES:
        raise ValueError("Família de máscara desconhecida.")
    if logo not in LOGO_OPTIONS:
        raise ValueError("Posição de logo inválida.")
    label, width, height, group = FORMATS[format_key]
    klass = layout_class(width, height)
    left, top, right, bottom = _safe_rect(width, height)
    sw, sh = right - left, bottom - top
    logo_rect = _logo_rect(width, height, logo, (left, top, right, bottom)) if logo != "none" else None
    zones = {}
    layout = _LAYOUTS[family].get(klass)
    if not layout:
        raise ValueError("Esta família de máscara não existe para este formato.")
    for name, (fx, fy, fw, fh) in layout.items():
        if fw <= 0 or fh <= 0 or (name == "cta" and not cta):
            continue
        if name == "cta" and width / height < 0.45:
            # Skyscrapers are too narrow for a short pill: the button spans the safe width.
            fx, fw, fy, fh = 0.0, 1.0, fy + fh * (1 - CTA_SCALE_H) / 2, fh * CTA_SCALE_H
        elif name == "cta" and klass != "wide":
            # Keep the button compact: about 70% of the drawn size, anchored where it was drawn.
            new_w, new_h = fw * CTA_SCALE_W, fh * CTA_SCALE_H
            fx = fx + (fw - new_w) / 2 if 0.4 <= fx + fw / 2 <= 0.6 else fx
            fy, fw, fh = fy + (fh - new_h) / 2, new_w, new_h
        rect = (left + fx * sw, top + fy * sh, fw * sw, fh * sh)
        zones[name] = _clear_logo(name, rect, logo_rect, logo)
    if logo_rect:
        zones["logo"] = logo_rect
    return {
        "id": f"{format_key}:{family}:{logo}:{'cta' if cta else 'nocta'}",
        "format": format_key, "format_label": label, "group": group,
        "width": width, "height": height, "ratio": provider_ratio(width, height),
        "strategy": strategy(width, height), "class": klass, "notes": FORMAT_NOTES.get(format_key, ""),
        "family": family, "family_label": FAMILIES[family][0], "logo": logo, "cta": bool(cta),
        "safe": (left, top, sw, sh),
        "zones": {name: tuple(round(value, 4) for value in rect) for name, rect in zones.items()},
    }


def catalog():
    return {
        "formats": [
            {"key": key, "label": label, "width": width, "height": height, "group": group,
             "provider_ratio": provider_ratio(width, height), "strategy": strategy(width, height)}
            for key, (label, width, height, group) in FORMATS.items()
        ],
        "families": [{"key": key, "label": label, "description": text} for key, (label, text) in FAMILIES.items()],
        "logos": [{"key": key, "label": label} for key, label in LOGO_OPTIONS.items()],
    }


def parse_mask_id(value):
    """'feed-4x5:foto-texto-base:bottom-right:cta' -> build_spec arguments."""
    match = re.fullmatch(r"([a-z0-9-]+):([a-z-]+):(none|bottom-right|top-left):(cta|nocta)", str(value or ""))
    if not match:
        raise ValueError("Identificador de máscara inválido.")
    return match.group(1), match.group(2), match.group(3), match.group(4) == "cta"


def all_specs(format_key=None):
    """Every combination the system can unfold: family × logo × CTA for each format."""
    for key in ([format_key] if format_key else FORMATS):
        for family in FAMILIES:
            has_text = family != "visual-puro"
            for logo in LOGO_OPTIONS:
                for cta in ((True, False) if has_text else (False,)):
                    try:
                        yield build_spec(key, family, logo, cta)
                    except ValueError:
                        continue  # family not drawn for this layout class


# -- drawing -----------------------------------------------------------------------------------

_BG, _SAFE, _INK = 238, 130, 12


def provider_frame(spec, provider_size=None):
    """Where the delivered canvas sits inside the provider canvas, as fractions (x, y, w, h).

    Providers return fixed sizes (e.g. 2:3); the Studio trims the result to the delivery ratio, so the
    wireframe is drawn on the provider canvas with the final frame marked inside it.
    """
    if not provider_size:
        return (0.0, 0.0, 1.0, 1.0)
    target, source = spec["width"] / spec["height"], provider_size[0] / provider_size[1]
    if abs(target - source) < 0.01:
        return (0.0, 0.0, 1.0, 1.0)
    if source < target:  # provider canvas is taller: top and bottom are trimmed
        height = source / target
        return (0.0, (1 - height) / 2, 1.0, height)
    width = target / source  # provider canvas is wider: left and right are trimmed
    return ((1 - width) / 2, 0.0, width, 1.0)


def _mapped(rect, frame):
    return (frame[0] + rect[0] * frame[2], frame[1] + rect[1] * frame[3], rect[2] * frame[2], rect[3] * frame[3])


def _px(canvas_size, rect):
    width, height = canvas_size
    return (round(rect[0] * width), round(rect[1] * height), round((rect[0] + rect[2]) * width) - 1, round((rect[1] + rect[3]) * height) - 1)


def _dashed_rect(draw, box, fill, width, dash):
    x0, y0, x1, y1 = box
    for start in range(x0, x1, dash * 2):
        draw.line((start, y0, min(start + dash, x1), y0), fill=fill, width=width)
        draw.line((start, y1, min(start + dash, x1), y1), fill=fill, width=width)
    for start in range(y0, y1, dash * 2):
        draw.line((x0, start, x0, min(start + dash, y1)), fill=fill, width=width)
        draw.line((x1, start, x1, min(start + dash, y1)), fill=fill, width=width)


def render_mask(spec, longest_side=1200, provider_size=None):
    """Draw the wireframe as a PNG; its ratio is the delivery format, or the provider canvas when given."""
    frame = provider_frame(spec, provider_size)
    canvas_w, canvas_h = (provider_size if provider_size and frame != (0.0, 0.0, 1.0, 1.0) else (spec["width"], spec["height"]))
    scale = longest_side / max(canvas_w, canvas_h)
    size = (max(8, round(canvas_w * scale)), max(8, round(canvas_h * scale)))
    canvas = Image.new("L", size, _BG)
    draw = ImageDraw.Draw(canvas)
    line = max(1, round(longest_side / 600))
    zones = {name: _mapped(rect, frame) for name, rect in spec["zones"].items()}
    if frame != (0.0, 0.0, 1.0, 1.0):  # strips that will be trimmed are darker and left without zones
        draw.rectangle((0, 0, size[0], size[1]), fill=206)
        draw.rectangle(_px(size, frame), fill=_BG)

    if "panel" in zones:
        box = _px(size, zones["panel"])
        draw.rectangle(box, fill=255, outline=_INK, width=line * 2)
    if "subject" in zones:
        box = _px(size, zones["subject"])
        draw.rectangle(box, fill=168)
        step = max(8, round(longest_side / 70))
        x0, y0, x1, y1 = box
        for offset in range(-(y1 - y0), x1 - x0, step):  # 45° hatch marks "image area"
            ax, ay, bx, by = x0 + offset, y1, x0 + offset + (y1 - y0), y0
            if ax < x0:
                ay, ax = y1 - (x0 - ax), x0
            if bx > x1:
                by, bx = y0 + (bx - x1), x1
            if ax <= x1 and by <= y1:
                draw.line((ax, ay, bx, by), fill=140, width=line)
    if "headline" in zones:
        x0, y0, x1, y1 = _px(size, zones["headline"])
        area_w, area_h = x1 - x0, y1 - y0
        bars = 3 if area_h > 0.2 * size[1] else 2 if area_h > 0.1 * size[1] else 1
        bar_h = max(2, round(area_h / (bars * 2 - 1))) if bars > 1 else max(2, round(area_h * 0.7))
        for index, share in enumerate((1.0, 0.86, 0.6)[:bars]):
            top = y0 + index * bar_h * 2
            draw.rectangle((x0, top, x0 + round(area_w * share), min(top + bar_h, y1)), fill=_INK)
    if "cta" in zones:
        x0, y0, x1, y1 = _px(size, zones["cta"])
        draw.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) // 2, fill=_INK)
        inset_x, inset_y = round((x1 - x0) * 0.26), round((y1 - y0) * 0.38)
        if x1 - x0 > 8 and y1 - y0 > 6:
            draw.rectangle((x0 + inset_x, y0 + inset_y, x1 - inset_x, y1 - inset_y), fill=235)
    if "logo" in zones:
        box = _px(size, zones["logo"])
        draw.rounded_rectangle(box, radius=max(2, (box[3] - box[1]) // 6), fill=255)
        _dashed_rect(draw, box, _INK, line * 2, max(4, round(longest_side / 150)))
    _dashed_rect(draw, _px(size, _mapped(spec["safe"], frame)), _SAFE, line, max(4, round(longest_side / 120)))
    output = io.BytesIO()
    canvas.save(output, "PNG", optimize=True)
    return output.getvalue()


# -- prompt contract -----------------------------------------------------------------------------

def _range(start, size):
    return f"{round(start * 100)}–{round((start + size) * 100)}%"


def zone_lines(spec, frame=(0.0, 0.0, 1.0, 1.0)):
    lines = []
    for name in ("subject", "panel", "headline", "cta", "logo"):
        if name not in spec["zones"]:
            continue
        x, y, w, h = _mapped(spec["zones"][name], frame)
        lines.append(f"- {ZONE_NAMES[name]}: x {_range(x, w)}, y {_range(y, h)}")
    return lines


def final_check(spec, provider_size=None, text_free=False):
    """Closing reminder that repeats the zone coordinates; models weigh the end of the prompt heavily."""
    frame = provider_frame(spec, provider_size)
    zones = "; ".join(line.removeprefix("- ") for line in zone_lines(spec, frame))
    if text_free:
        return f"FINAL CHECK: the image contains no text, button or logo at all; these zones stay calm and empty for typography: {zones}."
    return f"FINAL LAYOUT CHECK: before finishing, verify the zones exactly: {zones}. If any element is elsewhere, recompose."


def safe_line(spec, frame):
    x, y, w, h = _mapped(spec["safe"], frame)
    return (
        f"SAFE FRAME: every letter of text, the button and the logo must sit strictly inside x {_range(x, w)} and y {_range(y, h)} of the canvas; "
        "outside it the photograph keeps going edge to edge (never a flat band, frame or empty strip). Start text lines at the left edge of the headline zone, never closer to the edge."
    )


def layout_contract(spec, image_index=1, provider_size=None, text_free=False):
    """Text that makes a model treat the wireframe as binding geometry (not artwork)."""
    has_cta, has_logo = "cta" in spec["zones"], "logo" in spec["zones"]
    frame = provider_frame(spec, provider_size)
    trimmed = frame != (0.0, 0.0, 1.0, 1.0)
    canvas_label = f"{provider_size[0]}x{provider_size[1]} px" if trimmed else f"{spec['width']}x{spec['height']} px"
    lines = [
        f"LAYOUT (binding): IMAGE {image_index} is a black-and-white layout wireframe of exactly this canvas ({canvas_label}, "
        f"{spec['family_label'].lower()}). It is a guide, not artwork: never draw its grey tones, hatching, bars, pill, dashed boxes or lines.",
        "How to read it: hatched mid-grey = area of the main subject; stacked black bars = headline text block; black pill = CTA button; "
        "white box with dashed border = logo space, keep that area clean and empty; white block with a black frame = flat text panel; light grey = the scene or background, which continues full-bleed behind everything; "
        "the thin dashed rectangle is the safe margin: no text or logo outside it.",
        *(["The slightly lighter inner area is the final frame; the darker strips outside it are trimmed away afterwards. Continue the scene into those strips, but put no text, logo, button or key subject there."] if trimmed else []),
        "PRIORITY: these zones override any placement written anywhere else in this prompt (briefing or creative direction). "
        "If the text below asks for the headline, button or logo somewhere else, ignore that part and follow these zones.",
        "Zones as percentage of the canvas (x from the left, y from the top):",
        *zone_lines(spec, frame),
        safe_line(spec, frame),
        "FULL BLEED: the picture fills the whole canvas edge to edge as one continuous image; the text sits on a calm part of the scene unless a TEXT PANEL zone exists.",
    ]
    if spec.get("notes"):
        lines.append(spec["notes"])
    if text_free:
        lines.append(
            "TEXT-FREE VISUAL: render no text, letters, numbers, button, pill or logo anywhere. The HEADLINE and CTA zones "
            "must be calm, low-detail background (soft gradient, sky, wall, out-of-focus area) with good contrast: the Studio "
            "sets the typography and the button there afterwards."
        )
        return "\n".join(lines)
    lines.append(
        "Render a solid, high-contrast CTA button with a readable label inside the CTA zone." if has_cta
        else "There is NO call-to-action button: do not draw any button, arrow or action label."
    )
    lines.append(
        "Leave the LOGO SPACE empty; the official logo is applied afterwards." if has_logo
        else "There is NO logo: do not draw any logo, wordmark or brand mark."
    )
    if "headline" not in spec["zones"]:
        lines.append("There is NO headline or any other text in this piece: render a pure visual.")
    return "\n".join(lines)


# -- pilot set served to the Studio ------------------------------------------------------------

MASK_URL_PREFIX = "/static/images/cadu/studio/references/layouts/"

BR, NONE, TL = "bottom-right", "none", "top-left"

# Ten deliberately different creatives per social format: layout family × logo × CTA.
_SOCIAL = (
    ("foto-texto-base", BR, True),
    ("foto-texto-topo", NONE, True),
    ("split", BR, True),
    ("produto-destaque", BR, False),
    ("assunto-na-base", BR, False),
    ("texto-central", NONE, True),
    ("cartao-flutuante", BR, True),
    ("faixa-inferior", NONE, False),
    ("texto-direita", BR, True),
    ("minimalista", NONE, False),
)
_DISPLAY = (
    ("foto-texto-base", BR, True),
    ("foto-texto-topo", NONE, True),
    ("split", BR, True),
    ("produto-destaque", BR, False),
    ("texto-central", NONE, True),
    ("cartao-flutuante", BR, True),
    ("faixa-inferior", BR, True),
    ("texto-direita", NONE, False),
)
_COMPACT = (
    ("compacto", BR, True),
    ("compacto", NONE, False),
    ("compacto", BR, False),
    ("compacto-central", NONE, True),
    ("compacto-logo-esquerda", TL, True),
)

_NARROW = (
    ("foto-texto-base", BR, True),
    ("foto-texto-topo", NONE, True),
    ("produto-destaque", BR, True),
    ("texto-central", NONE, False),
    ("faixa-inferior", BR, True),
    ("minimalista", NONE, False),
)

# format -> (family, logo, cta) set. YouTube in-feed forbids a CTA and the compact banners carry no
# product or people (creative_format_registry); every format has at least five clearly different layouts.
MASK_SETS = {
    "feed-4x5": _SOCIAL,
    "feed-1x1": _SOCIAL,
    "story-9x16": _SOCIAL,
    "linkedin-1200x627": _SOCIAL,
    "youtube-16x9": (
        ("foto-texto-base", BR, False),
        ("foto-texto-topo", NONE, False),
        ("split", NONE, False),
        ("tipografico", BR, False),
        ("texto-central", NONE, False),
        ("faixa-inferior", BR, False),
        ("texto-direita", BR, False),
        ("minimalista", NONE, False),
    ),
    "iab-300x250": _DISPLAY,
    "display-300x300": _DISPLAY,
    "iab-300x600": _DISPLAY,
    "iab-160x600": _NARROW,
    "iab-970x250": (
        ("foto-texto-base", BR, True),
        ("foto-texto-topo", NONE, True),
        ("split", BR, True),
        ("texto-direita", BR, False),
        ("cartao-flutuante", NONE, True),
        ("texto-central", BR, True),
        ("minimalista", NONE, False),
    ),
    "iab-728x90": _COMPACT,
    "iab-320x50": _COMPACT,
    "iab-336x280": _DISPLAY,
    "display-250x250": _DISPLAY,
    "display-200x200": _DISPLAY,
    "display-180x150": _DISPLAY,
    "display-240x400": _DISPLAY,
    "interstitial-320x480": _DISPLAY,
    "interstitial-480x320": _DISPLAY,
    "iab-300x1050": _NARROW,
    "iab-120x600": _NARROW,
    "display-120x240": _NARROW,
    "iab-970x90": _COMPACT,
    "iab-468x60": _COMPACT,
    "iab-234x60": _COMPACT,
    "iab-320x100": _COMPACT,
    "iab-300x50": _COMPACT,
    "display-300x100": _COMPACT,
}


def served_specs():
    """Every mask the Studio serves, format by format."""
    return [build_spec(key, family, logo, cta) for key, entries in MASK_SETS.items() for family, logo, cta in entries]


def mask_filename(spec):
    return spec["id"].replace(":", "__") + ".png"


def spec_from_url(url):
    """Rebuild the spec of a served mask from its URL, or None when it is not one of ours."""
    value = str(url or "").split("?", 1)[0]
    if not value.startswith(MASK_URL_PREFIX):
        return None
    name = value[len(MASK_URL_PREFIX):]
    if not name.endswith(".png") or "/" in name:
        return None
    try:
        return build_spec(*parse_mask_id(name[:-4].replace("__", ":")))
    except ValueError:
        return None


def write_masks(directory):
    """Draw every served mask; returns their specs."""
    from pathlib import Path
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    specs = served_specs()
    for spec in specs:
        (target / mask_filename(spec)).write_bytes(render_mask(spec, longest_side=max(1200, spec["width"], spec["height"])))
    return specs
