"""Tabela HTML, tema Tailwind e specimen da marca."""

from __future__ import annotations

from html import escape

from .schema import compile_css_vars, dump_system, parse_system, token_table_rows


def css_root(system):
    parsed = parse_system(system)
    lines = [f"  {key}: {value};" for key, value in (parsed.css_vars or compile_css_vars(parsed.tokens)).items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


def tailwind_theme(system):
    return parse_system(system).tailwind


def table_html(system):
    parsed = parse_system(system)
    rows = []
    for item in token_table_rows(parsed):
        tw = f"<code>{escape(item['tw_class'])}</code>" if item["tw_class"] else "—"
        rows.append(
            "<tr>"
            f"<th scope='row'>{escape(item['id'])}</th>"
            f"<td>{escape(item['role'])}</td>"
            f"<td><code>{escape(item['css_var'])}</code></td>"
            f"<td>{tw}</td>"
            f"<td>{escape(str(item['value'] or ''))}</td>"
            "</tr>"
        )
    return (
        "<table class='dsa-table'>"
        "<caption>Design System Ads</caption>"
        "<thead><tr>"
        "<th>Token</th><th>Papel</th><th>CSS</th><th>Tailwind</th><th>Valor</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _google_fonts(system):
    parsed = parse_system(system)
    families = []
    for key in ("font-display", "font-body"):
        family = str(parsed.tokens.get(key) or "").strip()
        if family and family not in {"Inter", "ui-sans-serif", "sans-serif"}:
            families.append(family.replace(" ", "+"))
    if "Inter" in {parsed.tokens.get("font-display"), parsed.tokens.get("font-body")}:
        families.insert(0, "Inter:wght@400;600;700")
    if not families:
        families = ["Inter:wght@400;600;700"]
    unique = []
    for item in families:
        if item not in unique:
            unique.append(item)
    query = "&".join(f"family={item}" for item in unique)
    return f"https://fonts.googleapis.com/css2?{query}&display=swap"


def render_format_specimen(system, stack, *, standalone=True, highlight=None):
    parsed = parse_system(system)
    token_patch = (stack or {}).get("tokens")
    if token_patch:
        data = dump_system(parsed)
        data["tokens"] = {**(data.get("tokens") or {}), **token_patch}
        parsed = parse_system(data)
    fmt = (stack or {}).get("format") or {}
    layers = (stack or {}).get("layers") or []
    width = int(fmt.get("width") or 970)
    height = int(fmt.get("height") or 250)
    density = escape(str(fmt.get("density") or "wide"))
    name = escape(parsed.name or "Design System Ads")
    copy = parsed.ad_copy or {}
    logo = escape(parsed.logo_url or "")
    stage_layers = []
    for item in sorted(layers, key=lambda row: int(row.get("z") or 0)):
        role = str(item.get("role") or "")
        parked = bool(item.get("parked"))
        text = escape(item.get("text") or "")
        focus = " is-focus" if highlight and str(item.get("id") or "") == str(highlight) else ""
        parked_class = f" is-parked{focus}" if parked else focus
        style = (
            f"left:{item.get('x')}%;top:{item.get('y')}%;"
            f"width:{item.get('w')}%;height:{item.get('h')}%;"
            f"z-index:{item.get('z') or 1}"
        )
        inner = ""
        asset = escape(str(item.get("asset_url") or ""))
        if asset and role != "logo":
            inner = f"<img class='dsa-cutout' src='{asset}' alt='{escape(item.get('label') or role)}'>"
        elif parked or role.startswith("ornament") or role in {"visual", "product", "ground"}:
            inner = ""
        elif role == "logo" and parsed.logo_url:
            inner = f"<img src='{logo}' alt='{name}'>"
        elif role == "headline":
            inner = f"<p class='dsa-ad-headline'>{text or escape(copy.get('headline') or '')}</p>"
        elif role == "support":
            inner = f"<p class='dsa-ad-support'>{text or escape(copy.get('support') or '')}</p>"
        elif role == "cta":
            inner = f"<span class='dsa-ad-cta'>{text or escape(copy.get('cta') or '')}</span>"
        elif role == "legal":
            inner = f"<p class='dsa-ad-legal'>{text or escape(copy.get('legal') or '')}</p>"
        stage_layers.append(
            f"<div class='dsa-layer is-{escape(role)}{parked_class}' data-role='{escape(role)}' style='{style}'>{inner}</div>"
        )
    safe = (stack or {}).get("safe") or {}
    pad_x = safe.get("x", 5)
    pad_y = safe.get("y", 5)
    sheet = f"""
<section class="dsa-ad is-{density}" style="--dsa-ad-w:{width};--dsa-ad-h:{height};{_sheet_style(parsed)}">
  <div class="dsa-ad-stage" role="img" aria-label="{escape(fmt.get('label') or 'formato')}">
    {''.join(stage_layers)}
    <div class="dsa-safe" style="left:{pad_x}%;top:{pad_y}%;width:{100 - 2 * float(pad_x)}%;height:{100 - 2 * float(pad_y)}%"></div>
  </div>
  <p class="dsa-ad-meta">{escape(fmt.get('label') or '')} · {escape(fmt.get('size_label') or '')} · {len(layers)} camadas</p>
</section>
"""
    if not standalone:
        return sheet.strip()
    return _standalone_document(
        parsed,
        sheet,
        title=f"{name} · {fmt.get('size_label') or ''}",
        stage=True,
    )


def render_specimen(system, *, standalone=True, stack=None, highlight=None):
    if stack is None:
        from .adapt import adapt_system
        from .components import ARCHETYPE_FORMAT

        parsed = parse_system(system)
        fmt = ARCHETYPE_FORMAT.get(parsed.archetype or "brand") or "iab-billboard"
        adapted, stack = adapt_system(parsed, fmt, 6)
        return render_format_specimen(
            adapted, stack, standalone=standalone, highlight=highlight
        )
    return render_format_specimen(
        system, stack, standalone=standalone, highlight=highlight
    )


def _standalone_document(system, body, title="", stage=False):
    parsed = parse_system(system)
    config = tailwind_theme(parsed)
    name = escape(title or parsed.name or "Design System Ads")
    page_bg = "#d7dee6" if stage else "#f8fafc"
    tailwind = "" if stage else f"""
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config = {_js_theme(config)};</script>"""
    return f"""<!doctype html>
<html lang="pt-BR" class="{'dsa-ad-doc' if stage else 'dsa-sheet-doc'}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="{_google_fonts(parsed)}">
{tailwind}
  <style>
    {css_root(parsed)}
    html, body {{ margin: 0; min-height: 100%; background: {page_bg}; color: var(--dsa-ink); }}
    .dsa-sheet {{
      min-height: 100vh;
      box-sizing: border-box;
      padding: var(--dsa-safe, 6%);
      font-family: var(--dsa-font-body), Inter, sans-serif;
      background: var(--dsa-paper);
    }}
    .dsa-lockup {{
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 2.5rem;
    }}
    .dsa-logo {{ height: 48px; width: auto; display: block; }}
    .dsa-headline {{
      margin: 0 0 1rem;
      font-family: var(--dsa-font-display), Inter, sans-serif;
      font-size: var(--dsa-type-headline);
      font-weight: var(--dsa-weight-display, 700);
      letter-spacing: var(--dsa-tracking, -0.015em);
      line-height: 1.05;
      max-width: 16ch;
    }}
    .dsa-support {{
      margin: 0 0 2rem;
      font-size: var(--dsa-type-support);
      line-height: 1.35;
      max-width: 36ch;
    }}
    .dsa-cta {{
      display: inline-block;
      background: var(--dsa-accent);
      color: var(--dsa-cta-ink);
      border-radius: var(--dsa-cta-radius);
      padding: var(--dsa-cta-pad, 0.85rem 1.4rem);
      font-size: var(--dsa-type-cta);
      font-weight: var(--dsa-weight-cta, 600);
      box-shadow: var(--dsa-cta-shadow, none);
      text-decoration: none;
    }}
    .dsa-cta:focus-visible {{ outline: 3px solid var(--dsa-highlight); outline-offset: 3px; }}
    .dsa-legal {{ margin: 2.5rem 0 0; font-size: var(--dsa-type-legal); color: var(--dsa-muted); }}
    .dsa-ad {{
      min-height: 100vh;
      box-sizing: border-box;
      padding: 2rem 1.5rem;
      display: grid;
      align-content: center;
      justify-items: center;
    }}
    .dsa-ad-stage {{
      position: relative;
      width: min(100%, calc(var(--dsa-ad-w) * 1px));
      aspect-ratio: var(--dsa-ad-w) / var(--dsa-ad-h);
      height: auto;
      overflow: hidden;
      background-color: var(--dsa-paper);
      background-image: var(--dsa-ground-image, none);
      background-size: var(--dsa-ground-fit, cover);
      background-position: center;
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
    }}
    .dsa-ad-stage::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: var(--dsa-overlay, transparent);
      pointer-events: none;
      z-index: 1;
    }}
    .dsa-ad-stage::after {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 2;
      opacity: var(--dsa-grain, 0);
      mix-blend-mode: multiply;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.55'/%3E%3C/svg%3E");
    }}
    .dsa-safe {{
      position: absolute;
      pointer-events: none;
      border: 1px dashed color-mix(in srgb, var(--dsa-ink) 22%, transparent);
      z-index: 80;
    }}
    .dsa-layer {{
      position: absolute;
      box-sizing: border-box;
      overflow: hidden;
    }}
    .dsa-layer.is-focus {{
      outline: 2px solid var(--dsa-highlight);
      outline-offset: -2px;
      z-index: 90;
    }}
    .dsa-layer.is-ground {{ background: var(--dsa-paper); }}
    .dsa-layer.is-visual {{ background: color-mix(in srgb, var(--dsa-ink) 14%, var(--dsa-paper)); }}
    .dsa-layer.is-product,
    .dsa-layer.is-icon,
    .dsa-layer.is-chip,
    .dsa-layer.is-parked,
    .dsa-layer[class*="is-ornament"] {{
      background: color-mix(in srgb, var(--dsa-highlight) 22%, transparent);
    }}
    .dsa-layer.is-chip {{
      border: 1px solid var(--dsa-hairline, color-mix(in srgb, var(--dsa-ink) 18%, transparent));
      border-radius: var(--dsa-cta-radius);
    }}
    .dsa-layer.is-logo {{
      display: grid;
      place-items: center;
    }}
    .dsa-layer.is-logo img {{
      display: block;
      width: auto;
      height: 100%;
      max-width: 100%;
      object-fit: contain;
      object-position: left center;
    }}
    .dsa-layer img.dsa-cutout {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      object-position: center;
    }}
    .dsa-layer.is-visual img.dsa-cutout {{
      object-fit: cover;
    }}
    .dsa-ad-headline,
    .dsa-ad-support,
    .dsa-ad-legal {{
      margin: 0;
      padding: 0;
      color: var(--dsa-ink);
      font-family: var(--dsa-font-display), Inter, sans-serif;
      line-height: 1.12;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .dsa-ad-headline {{
      font-size: var(--dsa-type-headline);
      font-weight: var(--dsa-weight-display, 700);
      letter-spacing: var(--dsa-tracking, -0.015em);
      -webkit-line-clamp: 2;
    }}
    .dsa-ad.is-thin .dsa-ad-headline {{
      -webkit-line-clamp: 1;
      line-height: 1;
    }}
    .dsa-ad-support {{
      font-size: var(--dsa-type-support);
      color: var(--dsa-muted);
      -webkit-line-clamp: 2;
    }}
    .dsa-ad-legal {{
      font-size: var(--dsa-type-legal);
      color: var(--dsa-muted);
      -webkit-line-clamp: 1;
    }}
    .dsa-ad-cta {{
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      width: 100%;
      box-sizing: border-box;
      padding: var(--dsa-cta-pad, 0 0.7em);
      background: var(--dsa-accent);
      color: var(--dsa-cta-ink);
      border-radius: var(--dsa-cta-radius);
      font-size: var(--dsa-type-cta);
      font-weight: var(--dsa-weight-cta, 600);
      box-shadow: var(--dsa-cta-shadow, none);
      font-family: var(--dsa-font-body), Inter, sans-serif;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .dsa-ad-meta {{
      margin: 0.85rem 0 0;
      color: #475569;
      font-size: 0.78rem;
      letter-spacing: 0.01em;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _sheet_style(system):
    parsed = parse_system(system)
    tokens = parsed.tokens or {}
    ground = str(tokens.get("ground") or "").strip()
    image = f"url('{ground}')" if ground else "none"
    return (
        f"background: var(--dsa-paper, {tokens.get('paper')});"
        f"color: var(--dsa-ink, {tokens.get('ink')});"
        f"--dsa-ground-image:{image};"
        f"--dsa-ground-fit:{tokens.get('ground-fit') or 'cover'};"
        f"--dsa-overlay:{tokens.get('overlay') or 'transparent'};"
        f"--dsa-grain:{tokens.get('grain') or '0'};"
        f"--dsa-wash-strength:{tokens.get('wash-strength') or '16%'};"
    )


def _js_theme(config):
    import json

    theme = (config or {}).get("theme") or {}
    return json.dumps({"theme": theme}, ensure_ascii=False)
