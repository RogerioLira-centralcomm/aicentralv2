"""Preenche o protótipo CTV. O modelo não redesenha a mecânica."""

from __future__ import annotations

import html
import re
from pathlib import Path

from .catalog import (
    ADAPTERS,
    CTA_DEFAULTS,
    SCENE_FILES,
    format_entry,
    is_cta_format,
    is_end_card,
    is_qr_format,
    plate_for,
    scene_timecode,
)
from .spec import CreativeFormatSpec

PROTOTYPE_ROOT = (
    Path(__file__).resolve().parent.parent / "templates" / "format_prototypes"
)
_BODY_RE = re.compile(r"<body([^>]*)>", re.IGNORECASE)
_LINK_CSS = '<link rel="stylesheet" href="styles.css">'


def prototype_dir(adapter):
    name = str(adapter or "generic_ctv")
    entry = ADAPTERS.get(name) or ADAPTERS["generic_ctv"]
    relative = entry.get("prototype") or f"ctv/{name}"
    path = PROTOTYPE_ROOT / relative
    if path.is_dir():
        return path
    return PROTOTYPE_ROOT / "ctv" / "generic_ctv"


def load_prototype_html(adapter, scene_id, brand_prototypes=None):
    custom = _brand_override(brand_prototypes, adapter, scene_id)
    if custom:
        return custom
    filename = SCENE_FILES.get(scene_id)
    if not filename:
        raise ValueError("Cena sem protótipo.")
    path = prototype_dir(adapter) / filename
    if not path.is_file():
        raise FileNotFoundError(f"Protótipo ausente: {adapter}/{filename}")
    return path.read_text(encoding="utf-8")


def build_scene_html(
    spec,
    scene,
    dna=None,
    assets=None,
    brand_prototypes=None,
    render=True,
    base_html=None,
    logo_visible=True,
    mockup=False,
):
    spec = spec if isinstance(spec, CreativeFormatSpec) else CreativeFormatSpec.model_validate(spec)
    source_id = "scene_01" if mockup else scene.id
    html_text = load_prototype_html(spec.adapter, source_id, brand_prototypes)
    css = (prototype_dir(spec.adapter) / "styles.css").read_text(encoding="utf-8")
    extras = _brand_css(dna, assets)
    if mockup:
        extras += _mockup_css()
    inherited = brand_style_from_base(base_html) if base_html and not mockup else ""
    html_text = html_text.replace(
        _LINK_CSS,
        f"<style>\n{css}\n{_canvas_css(spec)}\n{extras}\n{inherited}\n</style>",
    )
    html_text = ensure_system_layers(html_text, qr=is_qr_format(spec.format))
    html_text = apply_stage_shape(html_text, spec)
    if render:
        html_text = _BODY_RE.sub(lambda match: _body_tag(match.group(1)), html_text, count=1)
    html_text = _replace_text(html_text, "layer-platform", spec.platform_label)
    if logo_visible:
        html_text = _replace_brand(html_text, spec.brand_name or "SUA MARCA", dna)
    html_text = apply_logo_visibility(html_text, logo_visible)
    html_text = _replace_inner(html_text, "layer-headline", _headline_html(scene.headline))
    html_text = _replace_inner(html_text, "layer-support", html.escape(scene.support or ""))
    count = len(spec.scenes) if getattr(spec, "scenes", None) else None
    last = is_end_card(scene.purpose, scene.id, count)
    show_cta = bool(scene.cta) or is_cta_format(spec.format) or last
    if show_cta:
        cta = scene.cta or CTA_DEFAULTS.get(spec.format) or "Saiba mais"
        html_text = _replace_text(html_text, "layer-cta", cta)
    html_text = apply_cta_visibility(html_text, show_cta)
    if scene.tip:
        html_text = _replace_text(html_text, "layer-tip", scene.tip)
    count = len(spec.scenes) if getattr(spec, "scenes", None) else 4
    timecode, progress = scene_timecode(scene.id, count, qr=is_qr_format(spec.format))
    if scene.timecode:
        timecode = scene.timecode if "/" in scene.timecode else f"{scene.timecode} / 00:15"
    html_text = re.sub(
        r'(<div class="time">)([^<]*)(</div>)',
        rf"\g<1>{html.escape(timecode)}\g<3>",
        html_text,
        count=1,
    )
    html_text = re.sub(
        r'(<div class="bar"><span style="width:)(\d+%)("></span></div>)',
        rf"\g<1>{int(progress)}%\g<3>",
        html_text,
        count=1,
    )
    qr_url = (assets or {}).get("qr_url")
    if qr_url and "id=\"layer-qr\"" in html_text:
        html_text = html_text.replace(
            'id="layer-qr"',
            'id="layer-qr" class="layer qr has-asset"',
            1,
        )
        html_text = html_text.replace("<style>", f"<style>\n.qr.has-asset{{--qr:url('{_css_url(qr_url)}');}}\n", 1)
    html_text = _apply_scene_photo(html_text, (assets or {}).get("scene_image"))
    html_text = apply_plate_layout(html_text, plate_for(scene.purpose))
    return html_text


def apply_patches(html_text, patches):
    text = str(html_text or "")
    for patch in patches or []:
        layer_id = str(getattr(patch, "layer_id", None) or patch.get("layer_id") or "")
        if not layer_id:
            continue
        replacement = getattr(patch, "text", None)
        if replacement is None and isinstance(patch, dict):
            replacement = patch.get("text")
        css = getattr(patch, "css", None)
        if css is None and isinstance(patch, dict):
            css = patch.get("css")
        if replacement not in (None, ""):
            text = _replace_text(text, layer_id, str(replacement))
            if layer_id in {"layer-headline", "layer-support"}:
                text = _replace_inner(text, layer_id, html.escape(str(replacement)))
        if css:
            text = _append_style(text, layer_id, str(css))
    return text


def _brand_override(brand_prototypes, adapter, scene_id):
    if not isinstance(brand_prototypes, dict):
        return ""
    pack = brand_prototypes.get(adapter) or brand_prototypes.get(scene_id)
    if isinstance(pack, str) and "<" in pack:
        return pack
    if isinstance(pack, dict):
        html_text = pack.get(scene_id) or pack.get(SCENE_FILES.get(scene_id, ""))
        if isinstance(html_text, str) and html_text.strip():
            return html_text
    return ""


def _css_url(url):
    return str(url or "").replace("\\", "\\\\").replace("'", "%27")


def _canvas_css(spec):
    width = int(getattr(spec.canvas, "width", 1920) or 1920)
    height = int(getattr(spec.canvas, "height", 1080) or 1080)
    return f":root{{--stage-ratio:{width} / {height};--stage-w:{width}px;--stage-h:{height}px}}"


def apply_stage_shape(html_text, spec):
    width = int(getattr(spec.canvas, "width", 1920) or 1920)
    height = int(getattr(spec.canvas, "height", 1080) or 1080)
    extras = []
    if height <= 100:
        extras.append("is-thin")
    if width / max(height, 1) >= 3:
        extras.append("is-wide")
    if height > width:
        extras.append("is-tall")
    entry = format_entry(spec.format) or {}
    if entry.get("kind") == "banner":
        extras.append("is-banner")
    if not extras:
        return html_text

    def _swap(match):
        classes = match.group(1)
        for name in extras:
            if name not in classes.split():
                classes = f"{classes} {name}"
        return f'class="{classes}"'

    return re.sub(r'class="(stage[^"]*)"', _swap, str(html_text or ""), count=1)


def apply_plate_layout(html_text, layout):
    name = str(layout or "split").strip().lower()
    if name not in {"split", "hero", "center"}:
        name = "split"
    cls = f"plate-{name}"

    def _swap(match):
        classes = re.sub(r"\s*plate-(?:split|hero|center)", "", match.group(1))
        return f'class="{classes} {cls}"'

    return re.sub(r'class="(stage[^"]*)"', _swap, str(html_text or ""), count=1)


def _apply_scene_photo(html_text, url):
    if not url:
        return html_text
    html_text = ensure_system_layers(html_text)
    css = (
        f"#layer-key-visual{{background-image:url('{_css_url(url)}')}}"
        ".stage.has-photo{background:#111}"
        ".stage.has-photo .visual,.stage.has-photo .sun,.stage.has-photo .city,"
        ".stage.has-photo .sofa,.stage.has-photo .screen-box,"
        ".stage.has-photo .silhouette-person,.stage.has-photo .plant{opacity:.12}"
    )
    html_text = html_text.replace("<style>", f"<style>\n{css}\n", 1)
    if not re.search(r'class="stage[^"]*has-photo', html_text):
        html_text = re.sub(r'class="stage"', 'class="stage has-photo"', html_text, count=1)
    return html_text


def brand_style_from_base(base_html):
    text = str(base_html or "")
    match = re.search(r"<style>([\s\S]*?)</style>", text, re.IGNORECASE)
    if not match:
        return ""
    css = match.group(1)
    keep = []
    for chunk in css.split("}"):
        block = chunk.strip()
        if not block:
            continue
        if any(token in block for token in ("--brand-", "--logo", "layer-key-visual", "is-mockup", "body.render .stage")):
            keep.append(block + "}")
    return "\n".join(keep)


def ensure_system_layers(html_text, qr=False):
    text = str(html_text or "")
    if 'id="layer-cta"' not in text:
        text = text.replace(
            "</main>",
            '<div class="layer cta" id="layer-cta" hidden>CTA</div>\n  </main>',
            1,
        )
    if 'id="layer-key-visual"' not in text:
        text = text.replace(
            '<main class="stage">',
            '<main class="stage">\n    <div class="layer key-visual" id="layer-key-visual"></div>',
            1,
        )
        if 'id="layer-key-visual"' not in text:
            text = text.replace(
                'class="stage"',
                'class="stage"',
                1,
            )
            text = re.sub(
                r'(<main class="stage"[^>]*>)',
                r'\1<div class="layer key-visual" id="layer-key-visual"></div>',
                text,
                count=1,
            )
    if qr and 'id="layer-qr"' not in text:
        text = text.replace(
            "</main>",
            '<div class="layer qr" id="layer-qr"></div>\n  </main>',
            1,
        )
    return text


def apply_logo_visibility(html_text, visible):
    text = str(html_text or "")
    hidden = "none" if not visible else "flex"
    rule = f"#layer-brand,.brand{{display:{hidden} !important}}"
    if not visible:
        text = re.sub(
            r'(id="layer-brand"[^>]*)>',
            lambda match: match.group(1).rstrip() + " hidden>",
            text,
            count=1,
        )
    else:
        text = text.replace('id="layer-brand" hidden', 'id="layer-brand"')
        text = re.sub(r'(id="layer-brand"[^>]*) hidden', r"\1", text, count=1)
    return _append_style(text, "layer-brand", rule)


def apply_cta_visibility(html_text, visible):
    text = str(html_text or "")
    if visible:
        text = text.replace('id="layer-cta" hidden', 'id="layer-cta"')
        return _append_style(text, "layer-cta", "#layer-cta{display:inline-flex}")
    text = re.sub(
        r'(id="layer-cta")(?![^>]*hidden)',
        r'\1 hidden',
        text,
        count=1,
    )
    return _append_style(text, "layer-cta", "#layer-cta{display:none !important}")


def _mockup_css():
    return (
        "body.render .stage,.stage.is-mockup{background:#111}"
        "#layer-key-visual,.key-visual{z-index:3;background-size:contain;"
        "background-repeat:no-repeat;background-position:center right}"
        "body.render .platform,body.render .timeline,body.render .header,"
        "body.render .note,body.render .layers{display:none}"
        ".copy,.cta,.brand{z-index:12}"
        ".cta{border-radius:0;background:transparent}"
    )


def _brand_css(dna, assets):
    dna = dna if isinstance(dna, dict) else {}
    colors = dna.get("colors") if isinstance(dna.get("colors"), dict) else {}
    palette = colors.get("palette") or []
    ink = "#EDE6D6"
    accent = colors.get("accent") or (palette[0] if palette else "#C4A574")
    if _is_dark(accent) and len(palette) > 1 and not _is_dark(palette[1]):
        accent = palette[1]
    logo = ""
    logo_data = dna.get("logo") if isinstance(dna.get("logo"), dict) else {}
    logo_url = (assets or {}).get("logo_url") or logo_data.get("asset_url")
    if logo_url:
        logo = f"url('{_css_url(logo_url)}')"
    fonts = dna.get("fonts") if isinstance(dna.get("fonts"), dict) else {}
    family = fonts.get("headline") or fonts.get("family") or ""
    if not family and isinstance(dna.get("fonts"), list) and dna["fonts"]:
        first = dna["fonts"][0]
        family = first.get("family") if isinstance(first, dict) else str(first)
    fallback = '"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif'
    face = f"'{family}', {fallback}" if family else fallback
    muted = "#8A8174"
    return (
        f":root{{--brand-ink:{ink};--brand-accent:{accent};--brand-paper:#EDE6D6;"
        f"--brand-muted:{muted};--logo:{logo or 'none'};--brand-face:{face};}}"
        f"body.render,.copy h2{{font-family:var(--brand-face);}}"
        f"body.render .stage:not(.has-photo){{background:"
        f"radial-gradient(120% 80% at 72% 38%,{accent}40,#0E0D0C)}}"
    )


def _is_dark(hex_color):
    raw = str(hex_color or "").lstrip("#")
    if len(raw) != 6:
        return False
    try:
        red, green, blue = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return False
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) < 90


def _body_tag(attrs):
    attrs = attrs or ""
    if "class=" in attrs:
        replaced = attrs.replace('class="', 'class="render ', 1)
        return "<body" + replaced + ">"
    return '<body class="render"' + attrs + ">"


def _headline_html(text):
    value = str(text or "").strip()
    if not value:
        return ""
    if "<br" in value.lower():
        return value
    words = value.split()
    if len(words) <= 3:
        return html.escape(value)
    chunks = []
    line = []
    for word in words:
        line.append(word)
        if len(" ".join(line)) >= 12:
            chunks.append(html.escape(" ".join(line)))
            line = []
    if line:
        chunks.append(html.escape(" ".join(line)))
    return "<br>".join(chunks)


def _replace_text(html_text, layer_id, value):
    pattern = re.compile(
        rf'(id="{re.escape(layer_id)}"[^>]*>)([^<]*)',
        re.IGNORECASE,
    )
    if not pattern.search(html_text):
        return html_text
    return pattern.sub(rf"\g<1>{html.escape(str(value or ''))}", html_text, count=1)


def _replace_inner(html_text, layer_id, inner_html):
    pattern = re.compile(
        rf'(id="{re.escape(layer_id)}"[^>]*>)([\s\S]*?)(</h2>|</p>)',
        re.IGNORECASE,
    )
    if not pattern.search(html_text):
        return html_text
    return pattern.sub(rf"\g<1>{inner_html}\g<3>", html_text, count=1)


def _replace_brand(html_text, name, dna):
    pattern = re.compile(
        r'(id="layer-brand"[^>]*>)([\s\S]*?)(</div>)',
        re.IGNORECASE,
    )

    def _swap(match):
        block = match.group(2)
        mark = re.search(r"<span class=\"brand-mark\"[^>]*>.*?</span>", block, re.I | re.S)
        mark_html = mark.group(0) if mark else '<span class="brand-mark" id="layer-brand-mark"></span>'
        logo = (dna or {}).get("logo") if isinstance(dna, dict) else {}
        if isinstance(logo, dict) and logo.get("asset_url") and "has-logo" not in mark_html:
            mark_html = mark_html.replace('class="brand-mark"', 'class="brand-mark has-logo"')
        return f"{match.group(1)}{mark_html}{html.escape(name)}{match.group(3)}"

    return pattern.sub(_swap, html_text, count=1)


def _append_style(html_text, layer_id, css):
    declaration = css if "{" in css else f"#{layer_id}{{{css}}}"
    return html_text.replace("</style>", f"{declaration}\n</style>", 1)

