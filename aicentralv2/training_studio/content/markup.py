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
