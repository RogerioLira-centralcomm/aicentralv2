"""Compila cena sanitizada. O iframe não recebe esta string — só JSON via postMessage."""

from __future__ import annotations

from html import escape

from .sanitizer import sanitize_canvas, sanitize_layer, sanitize_operations, sanitize_scene


def compile_scene(raw):
    scene = sanitize_scene(raw)
    canvas = scene["canvas"]
    width = int(canvas.get("width") or 800)
    height = int(canvas.get("height") or 450)
    background = escape(str(canvas.get("background") or "#000000"), quote=True)
    parts = [
        "<!DOCTYPE html>",
        "<html lang=\"pt-BR\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<style>html,body{margin:0;height:100%;}#board{position:relative;width:100%;height:100%;overflow:hidden;}",
        ".layer{position:absolute;margin:0;box-sizing:border-box;overflow:hidden;}",
        "img.layer{object-fit:contain;pointer-events:none;}</style></head>",
        f"<body><div id=\"board\" style=\"background:{background};aspect-ratio:{width}/{height}\">",
    ]
    for layer in scene["layers"]:
        if layer.get("visible") is False:
            continue
        parts.append(_compile_layer(layer))
    parts.append("</div></body></html>")
    return "".join(parts)


def apply_operations(raw, operations):
    scene = sanitize_scene(raw)
    layers = {item["id"]: dict(item) for item in scene["layers"]}
    canvas = dict(scene["canvas"])
    for item in sanitize_operations(operations):
        kind = item["operation"]
        props = item.get("properties") or {}
        if kind == "set_canvas":
            canvas.update(props)
            canvas = sanitize_canvas(canvas)
            continue
        layer = layers.get(item["layer_id"])
        if not layer:
            raise ValueError("Camada da cena não encontrada.")
        if kind == "hide":
            layer["visible"] = False
        elif kind == "show":
            layer["visible"] = True
        elif kind == "move":
            layer["x"] = props.get("x", layer.get("x"))
            layer["y"] = props.get("y", layer.get("y"))
        elif kind == "resize":
            layer["width"] = props.get("width", layer.get("width"))
            layer["height"] = props.get("height", layer.get("height"))
        elif kind == "replace":
            if layer.get("type") != "image":
                raise ValueError("Só imagem pode trocar ativo.")
            layer["asset_path"] = props.get("asset_path", layer.get("asset_path"))
            layer["asset_id"] = props.get("asset_id", layer.get("asset_id"))
        elif kind == "reorder":
            layer["z_index"] = props.get("z_index", layer.get("z_index"))
        else:
            if "style" in props and layer.get("type") == "text":
                style = dict(layer.get("style") or {})
                style.update(props.get("style") or {})
                layer["style"] = style
                props = {key: value for key, value in props.items() if key != "style"}
            layer.update(props)
        cleaned = sanitize_layer(layer)
        if not cleaned:
            raise ValueError("Camada da cena inválida.")
        layers[cleaned["id"]] = cleaned
    scene["canvas"] = sanitize_canvas(canvas)
    scene["layers"] = sorted(layers.values(), key=lambda item: int(item.get("z_index") or 0))
    return sanitize_scene(scene)


def _compile_layer(layer):
    left = _css_pct(layer.get("x"), 0)
    top = _css_pct(layer.get("y"), 0)
    width = _css_pct(layer.get("width"), 100 if layer.get("type") == "image" else 40)
    height = _css_pct(layer.get("height"), None)
    rotation = layer.get("rotation") or 0
    z_index = int(layer.get("z_index") or 0)
    ident = escape(layer["id"], quote=True)
    style = (
        f"left:{left};top:{top};width:{width};z-index:{z_index};"
        f"transform:rotate({rotation}deg)"
    )
    if height is not None:
        style += f";height:{height}"
    if layer.get("type") == "text":
        look = layer.get("style") or {}
        style += (
            f";font-family:{escape(str(look.get('font_family') or 'Arial, sans-serif'), quote=True)}"
            f";font-size:{float(look.get('font_size') or 32)}px"
            f";font-weight:{int(look.get('font_weight') or 400)}"
            f";line-height:{float(look.get('line_height') or 1.05)}"
            f";letter-spacing:{float(look.get('letter_spacing') or 0)}em"
            f";color:{escape(str(look.get('color') or '#FFFFFF'), quote=True)}"
            f";text-align:{escape(str(look.get('text_align') or 'left'), quote=True)}"
        )
        return (
            f"<p class=\"layer\" data-layer=\"{ident}\" data-role=\"{escape(layer.get('role') or '', quote=True)}\" "
            f"style=\"{style}\">{escape(layer.get('text') or '')}</p>"
        )
    src = escape(layer.get("asset_path") or "", quote=True)
    alt = escape(layer.get("label") or layer.get("role") or "", quote=True)
    return f"<img class=\"layer\" data-layer=\"{ident}\" alt=\"{alt}\" src=\"{src}\" style=\"{style}\">"


def _css_pct(value, default):
    if value in (None, ""):
        if default is None:
            return None
        value = default
    return f"{float(value)}%"
