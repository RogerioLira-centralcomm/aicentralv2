"""Placeholder inteligente: anatomia do formato, não um retângulo vazio."""

from __future__ import annotations

from html import escape

from .creative_format_registry import DISCLAIMER, entry, public_label_for


ELEMENT_LABELS = {
    "logo": "LOGO",
    "headline": "HEADLINE",
    "support": "APOIO",
    "cta": "CTA",
    "product": "PRODUTO / IMAGEM",
    "lifestyle": "LIFESTYLE",
    "legal": "LEGAL",
    "image": "IMAGEM",
    "qr": "QR",
    "cta_instruction": "INSTRUÇÃO",
    "hotspot": "HOTSPOT",
    "card_front": "FRENTE",
    "card_back": "VERSO",
    "cover": "CAPA",
    "reveal": "REVELAÇÃO",
    "before": "ANTES",
    "after": "DEPOIS",
    "handle": "ARRASTE",
    "question": "PERGUNTA",
    "choices": "ESCOLHAS",
    "result": "RESULTADO",
    "thumbnail": "THUMBNAIL",
}


def render_placeholder(format_key, brand_label=None):
    item = entry(format_key)
    if not item:
        return {
            "status": "blocked",
            "code": "PLACEMENT_NOT_DEFINED",
            "format_key": str(format_key or ""),
            "html": "",
            "public_label": public_label_for("smart_placeholder"),
        }
    width = item["width"]
    height = item["height"]
    zone = (item["placement_zones"] or ["poço"])[0]
    channels = ", ".join(item["channels"])
    inset = int((item.get("safe_areas") or {}).get("inset_pct") or 0)
    required = item["required_elements"]
    optional = item["optional_elements"]
    brand = escape(brand_label or "MARCA DEMONSTRATIVA")
    boxes = []
    for role in required:
        boxes.append(_box(role, required=True))
    for role in optional:
        boxes.append(_box(role, required=False))
    html = (
        f'<article class="cx-format-ph" data-format="{escape(item["format_key"])}" '
        f'data-zone="{escape(str(zone))}" data-density="{escape(item["density"])}" '
        f'style="width:{width}px;height:{height}px;--ph-inset:{inset}%;">'
        f'<header class="cx-format-ph-meta">'
        f'<strong>{escape(item["label"])}</strong>'
        f'<span>{width}×{height}</span>'
        f'<span>{escape(channels)}</span>'
        f'<span>{escape(str(zone))}</span>'
        f'<em>{escape(item["density"])}</em>'
        f'</header>'
        f'<div class="cx-format-ph-safe" aria-hidden="true"></div>'
        f'<div class="cx-format-ph-brand">{brand}</div>'
        f'<div class="cx-format-ph-anatomy">{"".join(boxes)}</div>'
        f'<footer class="cx-format-ph-seal">'
        f'{escape(public_label_for("smart_placeholder"))} · conteúdo demonstrativo'
        f'</footer>'
        f'<small class="cx-format-ph-disclaimer">{escape(DISCLAIMER)}</small>'
        f'</article>'
    )
    return {
        "status": "ok",
        "format_key": item["format_key"],
        "width": width,
        "height": height,
        "html": html,
        "public_label": public_label_for("smart_placeholder"),
        "disclaimer": DISCLAIMER,
        "required_elements": list(required),
        "optional_elements": list(optional),
    }


def _box(role, required):
    kind = "required" if required else "optional"
    return (
        f'<section class="cx-format-ph-box is-{kind} is-{escape(role)}" data-role="{escape(role)}">'
        f'<span>{escape(ELEMENT_LABELS.get(role, role.upper()))}</span>'
        f'</section>'
    )


PLACEHOLDER_CSS = """
.cx-format-ph{position:relative;display:flex;flex-direction:column;gap:4px;box-sizing:border-box;
  padding:8px;background:#f4f1ea;color:#1b1b1b;border:1px dashed #8a8373;overflow:hidden;
  font:11px/1.25 ui-sans-serif,system-ui,sans-serif}
.cx-format-ph-meta{display:flex;flex-wrap:wrap;gap:6px;font-size:10px;letter-spacing:.04em;text-transform:uppercase}
.cx-format-ph-safe{position:absolute;inset:var(--ph-inset,0);border:1px dotted rgba(196,23,12,.35);pointer-events:none}
.cx-format-ph-brand{font-weight:700;font-size:12px}
.cx-format-ph-anatomy{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:4px;min-height:0}
.cx-format-ph-box{display:grid;place-items:center;border:1px solid #c4bba8;background:#fff;min-height:22px}
.cx-format-ph-box.is-optional{border-style:dashed;color:#666}
.cx-format-ph-box.is-headline{grid-column:1/-1}
.cx-format-ph-box.is-product,.cx-format-ph-box.is-image,.cx-format-ph-box.is-lifestyle{grid-column:1/-1;min-height:36px}
.cx-format-ph-box.is-cta{background:#1b1b1b;color:#fff}
.cx-format-ph-seal{font-size:9px;text-transform:uppercase;letter-spacing:.06em}
.cx-format-ph-disclaimer{font-size:9px;color:#666}
"""
