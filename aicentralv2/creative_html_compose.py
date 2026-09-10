"""Compositor HTML do Estúdio: template + screenshot Playwright no filme 16:9."""

from __future__ import annotations

import base64
import os
import threading
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .creative_compose_library import clamp_params, sanitize_compose_regions, schema_for_family
from .creative_format_compose import APP_FONT, compose_native_result
from .creative_format_geometry import compose_layout

HTML_COMPOSE_FAMILIES = frozenset({
    "sequence_16x9",
    "square_1x1",
    "rectangle",
    "wide_banner",
    "half_page",
    "story_9x16",
    "landscape_social",
    "slate_16x9",
})
HTML_COMPOSE_TEMPLATES = {
    "sequence_16x9": "sequence_16x9.html",
    "square_1x1": "square_1x1.html",
}
LAYOUT_SLOT_ROLES = {
    "visual": "photo",
    "headline": "headline",
    "cta": "cta",
    "logo": "logo",
    "legal": "legal",
}
HTML_COMPOSE_FLAG = "CREATIVE_HTML_COMPOSE"
HTML_FONT_NAME = "OpenSans-Regular.ttf"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "creative_compose"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)
_lock = threading.Lock()
_playwright = None
_browser = None


PHOTO_REGION_TYPES = frozenset({"foto_pessoa", "foto_produto", "visual", "foto"})
TEXT_REGION_TYPES = {
    "headline": "headline",
    "cta": "cta",
    "preco": "price",
    "beneficios": "legal",
    "legal": "legal",
}


def html_compose_enabled():
    raw = os.environ.get(HTML_COMPOSE_FLAG)
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def layout_slots(family, size):
    """Usa a geometria do formato quando o extrator ainda não gravou o mapa."""
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        return []
    slots = []
    for tipo, box in compose_layout(family, (width, height)).items():
        role = LAYOUT_SLOT_ROLES.get(tipo)
        if not role or not box or len(box) != 4:
            continue
        x, y, w, h = box
        px = max(0.0, min(100.0, 100.0 * x / width))
        py = max(0.0, min(100.0, 100.0 * y / height))
        pw = max(0.0, min(100.0, 100.0 * w / width))
        ph = max(0.0, min(100.0, 100.0 * h / height))
        if pw <= 0 or ph <= 0:
            continue
        slots.append({
            "tipo": tipo,
            "role": role,
            "x": px,
            "y": py,
            "w": pw,
            "h": ph,
            "style": f"left:{px}%;top:{py}%;width:{pw}%;height:{ph}%;",
        })
    return slots


def region_slots(params=None):
    """Converte o mapa extraído em slots absolutos para o template HTML."""
    slots = []
    for item in sanitize_compose_regions((params or {}).get("regions")):
        tipo = item["tipo"]
        if tipo in PHOTO_REGION_TYPES:
            role = "photo"
        elif tipo == "logo":
            role = "logo"
        elif tipo == "fundo":
            role = "background"
        else:
            role = TEXT_REGION_TYPES.get(tipo, "other")
        slots.append({
            **item,
            "role": role,
            "style": (
                f"left:{item['x']}%;top:{item['y']}%;"
                f"width:{item['w']}%;height:{item['h']}%;"
            ),
        })
    return slots


def can_html_compose(family, flow_kind=None):
    if not html_compose_enabled():
        return False
    if str(flow_kind or "") == "unfold":
        return False
    return str(family or "") in HTML_COMPOSE_FAMILIES


def _data_url(data, mime="image/png"):
    if not data:
        return ""
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _font_data_url():
    if APP_FONT.is_file():
        return _data_url(APP_FONT.read_bytes(), "font/ttf")
    return ""


def render_compose_html(geometry, copy=None, still_url="", logo_url="", font_url=""):
    geometry = geometry if isinstance(geometry, dict) else {}
    copy = copy if isinstance(copy, dict) else {}
    family = str(geometry.get("family") or "sequence_16x9")
    size = geometry.get("size") or (1920, 1080)
    width, height = int(size[0]), int(size[1])
    cta = "" if copy.get("omit_cta") else str(copy.get("cta") or "").strip()
    template = HTML_COMPOSE_TEMPLATES.get(family) or "studio.html"
    params = clamp_params(schema_for_family(family), copy.get("compose_params"))
    if not params.get("regions"):
        extra = sanitize_compose_regions(copy.get("regions"))
        if extra:
            params = dict(params)
            params["regions"] = extra
    mapped = region_slots(params)
    if not mapped and family not in HTML_COMPOSE_TEMPLATES:
        mapped = layout_slots(family, (width, height))
    return _env.get_template(template).render(
        family=family,
        width=width,
        height=height,
        brand_color=copy.get("brand_color") or "#1E4D4F",
        still_url=still_url or "",
        logo_url=logo_url or "",
        font_url=font_url or _font_data_url(),
        headline=str(copy.get("headline") or ""),
        cta=cta,
        legal=str(copy.get("legal") or "").strip(),
        price=str(copy.get("price") or copy.get("price_value") or "").strip(),
        photo_side=params.get("photo_side") or "right",
        headline_font_size=params.get("headline_font_size") or 26,
        cta_gap=params.get("cta_gap") or 12,
        regions=mapped,
    )


def _browser_instance():
    global _playwright, _browser
    if _browser is not None:
        return _browser
    with _lock:
        if _browser is not None:
            return _browser
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        return _browser


def screenshot_html(html, width, height):
    page = _browser_instance().new_page(
        viewport={"width": int(width), "height": int(height)},
        device_scale_factor=1,
    )
    try:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts && document.fonts.ready")
        return page.screenshot(type="png", omit_background=False)
    finally:
        page.close()


def compose_html_result(source_bytes, geometry, copy=None, logo_bytes=None):
    geometry = geometry if isinstance(geometry, dict) else {}
    family = geometry.get("family")
    size = geometry.get("size")
    if family not in HTML_COMPOSE_FAMILIES or not size:
        raise ValueError("HTML compose só cobre as famílias nativas do Estúdio.")
    html = render_compose_html(
        geometry,
        copy,
        still_url=_data_url(source_bytes),
        logo_url=_data_url(logo_bytes) if logo_bytes else "",
    )
    png = screenshot_html(html, size[0], size[1])
    return {
        "png": png,
        "logo_applied": bool(logo_bytes),
        "composed": True,
        "font": HTML_FONT_NAME,
        "require_logo": bool((copy or {}).get("require_logo")),
        "size": (int(size[0]), int(size[1])),
        "renderer": "html",
    }


def compose_studio_result(source_bytes, geometry, copy=None, logo_bytes=None, flow_kind=None):
    if can_html_compose((geometry or {}).get("family"), flow_kind):
        try:
            return compose_html_result(source_bytes, geometry, copy, logo_bytes)
        except Exception:
            pass
    result = compose_native_result(source_bytes, geometry, copy, logo_bytes)
    result["renderer"] = result.get("renderer") or "pillow"
    return result
