"""Checagens no specimen HTML. Playwright opt-in; sem browser o render fica skipped."""

from __future__ import annotations

import os
import re

from .adapt import adapt_system
from .components import P0_ROLES
from .render import render_specimen
from .schema import MIN_CONTRAST, contrast_ratio, parse_system
from .validate import ValidationReport, build_validation_report, mark_format_state

INSPECT_JS = """() => {
  const stage = document.querySelector('.dsa-ad-stage');
  const stageBox = stage ? stage.getBoundingClientRect() : {width: 0, height: 0, left: 0, top: 0, right: 0, bottom: 0};
  const layers = {};
  document.querySelectorAll('.dsa-layer[data-role]').forEach((node) => {
    const role = node.getAttribute('data-role') || '';
    const box = node.getBoundingClientRect();
    const parked = node.classList.contains('is-parked');
    const intersects = box.width > 1 && box.height > 1
      && box.right > stageBox.left && box.left < stageBox.right
      && box.bottom > stageBox.top && box.top < stageBox.bottom;
    layers[role] = {
      present: true,
      parked,
      visible: Boolean(intersects && !parked),
      clipped: Boolean(!parked && (box.bottom > stageBox.bottom + 1.5 || box.right > stageBox.right + 1.5)),
      width: box.width,
      height: box.height,
    };
  });
  const cta = document.querySelector('.dsa-ad-cta');
  const ctaStyle = cta ? getComputedStyle(cta) : null;
  const paperStyle = stage ? getComputedStyle(stage) : null;
  return {
    stage: { width: stageBox.width, height: stageBox.height },
    layers,
    cta: ctaStyle ? {
      color: ctaStyle.color,
      background: ctaStyle.backgroundColor,
      paper: paperStyle ? paperStyle.backgroundColor : '',
    } : {},
  };
}"""


def render_validate_enabled():
    return str(os.getenv("DSA_RENDER_VALIDATE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def playwright_available():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except Exception:
        return False


def parse_css_color(value):
    text = str(value or "").strip()
    match = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
        text,
        flags=re.I,
    )
    if match:
        red, green, blue = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return f"#{red:02X}{green:02X}{blue:02X}"
    from .schema import normalize_hex

    return normalize_hex(text)


def evaluate_render_metrics(metrics, *, width, height):
    """Checagens puras. Usadas com Playwright ou fixture."""
    data = metrics if isinstance(metrics, dict) else {}
    defects = []
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    stage_w = float(stage.get("width") or 0)
    stage_h = float(stage.get("height") or 0)
    if abs(stage_w - float(width)) > 4 or abs(stage_h - float(height)) > 4:
        defects.append("O frame não bate com o formato (resize).")
    layers = data.get("layers") if isinstance(data.get("layers"), dict) else {}
    for role in P0_ROLES:
        layer = layers.get(role) if isinstance(layers.get(role), dict) else {}
        if not layer.get("visible"):
            defects.append(f"P0 {role} não está visível no retângulo.")
    legal = layers.get("legal") if isinstance(layers.get("legal"), dict) else {}
    if legal.get("present") and legal.get("clipped"):
        defects.append("Legal cortado.")
    cta = data.get("cta") if isinstance(data.get("cta"), dict) else {}
    ink = parse_css_color(cta.get("color"))
    fill = parse_css_color(cta.get("background")) or parse_css_color(cta.get("paper"))
    if ink and fill and contrast_ratio(ink, fill) < MIN_CONTRAST:
        defects.append("CTA abaixo de 4.5:1 no specimen.")
    return defects


def inspect_specimen(html, width, height):
    from ..creative_html_compose import _browser_instance

    page = _browser_instance().new_page(
        viewport={
            "width": max(int(width) + 160, 480),
            "height": max(int(height) + 160, 360),
        },
        device_scale_factor=1,
    )
    try:
        page.set_content(html, wait_until="load", timeout=15000)
        page.evaluate("() => document.fonts && document.fonts.ready")
        return page.evaluate(INSPECT_JS)
    finally:
        page.close()


def validate_render(
    system,
    *,
    format_key="iab-billboard",
    layer_count=6,
    force=False,
    metrics=None,
):
    parsed = parse_system(system)
    adapted, stack = adapt_system(parsed, format_key or "iab-billboard", layer_count or 6)
    fmt = (stack or {}).get("format") or {}
    width = int(fmt.get("width") or 970)
    height = int(fmt.get("height") or 250)
    report = build_validation_report(adapted)
    if metrics is None:
        if not force and not render_validate_enabled():
            dumped = report.model_dump()
            dumped["render"] = "skipped"
            dumped["notes"] = list(dumped.get("notes") or []) + ["Render opt-in desligado."]
            return ValidationReport.model_validate(dumped), stack
        if not playwright_available():
            dumped = report.model_dump()
            dumped["render"] = "skipped"
            dumped["notes"] = list(dumped.get("notes") or []) + ["Playwright ausente."]
            return ValidationReport.model_validate(dumped), stack
        html = render_specimen(adapted, standalone=True, stack=stack)
        observed = inspect_specimen(html, width, height)
    else:
        observed = metrics
    defects = list(report.defects) + evaluate_render_metrics(
        observed, width=width, height=height
    )
    render_state = "failed" if defects else "passed"
    formats = dict(report.formats)
    key = str(fmt.get("key") or format_key or "")
    if key:
        formats[key] = "ok" if render_state == "passed" else "stale"
    return ValidationReport(
        passed=not defects,
        score=1.0 if render_state == "passed" else 0.35,
        defects=defects[:8],
        notes=["Specimen conferido no browser."]
        if render_state == "passed"
        else defects[:4],
        fingerprint=report.fingerprint,
        fingerprint_short=report.fingerprint_short,
        checked_formats=sorted({*report.checked_formats, key} - {""}),
        formats=formats,
        stale_count=sum(1 for state in formats.values() if state == "stale"),
        render=render_state,
    ), stack


def apply_render_report(system, report, format_key):
    if report.render != "passed":
        return mark_format_state(system, format_key, "stale") if format_key else system
    return mark_format_state(system, format_key, "ok")
