"""HTML curto do roteiro — sem markdown no documento."""


def esc(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def h2(title):
    return f"<h2>{esc(title)}</h2>"


def h3(title):
    return f"<h3>{esc(title)}</h3>"


def p(*parts):
    return "".join(f"<p>{part}</p>" for part in parts)


def ul(items):
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def figure(src, alt, css="ts-hero"):
    if not src:
        return ""
    return (
        f'<figure class="ts-inline-image {css}">'
        f'<img src="{esc(src)}" alt="{esc(alt)}"></figure>'
    )


def notes(text):
    return f'<aside class="ts-instructor-notes" data-bloco="nota_instrutor"><p>{text}</p></aside>'


def sources(*lines):
    items = "".join(f"<li>{line}</li>" for line in lines)
    return f'<footer class="ts-sources" data-bloco="fonte"><p>Fontes</p><ul>{items}</ul></footer>'


def block(kind, html):
    return f'<section class="ts-block" data-bloco="{esc(kind)}">{html}</section>'


def art_slot():
    return '<figure class="ts-page-art" data-slot="ilustracao"></figure>'


def metrics_row(items):
    cards = "".join(
        (
            '<article class="ts-metric">'
            f'<p class="ts-metric-value">{esc(item["value"])}</p>'
            f'<p class="ts-metric-label">{esc(item["label"])}</p>'
            + (f'<p class="ts-metric-note">{esc(item["note"])}</p>' if item.get("note") else "")
            + "</article>"
        )
        for item in items
    )
    return f'<div class="ts-metrics">{cards}</div>'


def page(layout, copy, art=None):
    layout = layout or "copy"
    parts = [f'<div class="ts-page-copy">{copy}</div>']
    if layout in ("split", "media"):
        parts.append(art if art else art_slot())
    elif art:
        parts.append(art)
    return (
        f'<article class="ts-page" data-layout="{esc(layout)}">'
        + "".join(parts)
        + "</article>"
    )
