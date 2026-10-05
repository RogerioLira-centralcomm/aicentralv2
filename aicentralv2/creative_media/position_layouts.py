"""Layouts by position (Lab v5): an ad as elements placed in relation to each other, not a grid of boxes.

The masks in ``ad_masks`` describe a piece as filled rectangles (photo box, headline box, panel box). Models copy
that grid literally and the pieces come out square and artificial. Real banners (MaxMilhas, TIM, Sebrae, BDMG — see
docs/creative-lab/01-anatomia-criativos-reais.md) are built from *positions and relations*: a cut-out person that
bleeds off an edge, a brand shape behind it, the offer set beside the face, a signature corner.

A position layout says, per element, where it sits and how it relates to the others. The image model receives the
positions in words and a sketch made of shapes (circle, diagonal, silhouette) instead of grey boxes, and draws the
scene with the brand shapes in it. The Studio sets the copy, the button and the logo in the copy positions by code.
Coordinates are fractions of the canvas (x, y, w, h); the copy positions stay inside the 8% safe frame.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw

SKETCH_URL_PREFIX = "/static/images/cadu/studio/references/positions/"

LAYOUTS = {
    "pessoa-circulo": {
        "label": "Pessoa recortada sobre círculo da marca",
        "learned_from": "TIM Pré (recorte com brilho atrás), Sebrae · Planeje-se (recorte + forma da marca)",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "Flat solid background in the brand's ground color, edge to edge, no texture, no scenery.",
            "A large solid circle in the brand accent color, centred at about 74% across and 58% down, its diameter "
            "about 80% of the canvas height, partly cut by the right and bottom edges.",
            "The person, photographed as a clean studio cut-out, stands in front of the circle on the right half "
            "(from 52% to 100% across, never left of 50%), cropped by the bottom edge at the waist, head at about 12–45% down, facing the "
            "camera; shoulders overlap the circle edge. A worn product from the references (necklace, watch, glasses) is "
            "large, sharp and well lit on the person: it is part of the offer.",
            "The left half (8% to 50% across) is plain background with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.067, 0.10, 0.38, 0.50), "cta": (0.067, 0.66, 0.30, 0.10), "logo": (0.067, 0.84, 0.18, 0.08),
                  "subject": (0.52, 0.10, 0.48, 0.90)},
        "logo": "bottom-left", "cta": True,
        "sketch": {"background": "ground", "circle": (0.74, 0.58, 0.40), "silhouette": (0.77, 0.12, 0.24, 0.88)},
    },
    "produto-diagonal": {
        "label": "Produto herói cruzando uma diagonal",
        "learned_from": "BDMG 300×600 (divisão diagonal foto/produto)",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "The background is split by one bold straight diagonal running from 62% across at the top to 38% across at "
            "the bottom: left of it a flat solid field in the brand's ground color, right of it a soft, out-of-focus "
            "photographic setting.",
            "The product is the hero: large, sharp, in three-quarter view, sitting on the right side and crossing the "
            "diagonal, about 55% of the canvas width, its lowest point at about 85% down.",
            "The upper-left area (8% to 52% across, 8% to 62% down) is plain flat color with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.067, 0.09, 0.44, 0.46), "cta": (0.067, 0.64, 0.28, 0.10), "logo": (0.773, 0.85, 0.16, 0.07),
                  "subject": (0.40, 0.20, 0.56, 0.68)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "diagonal": (0.62, 0.38), "product": (0.68, 0.55, 0.28, 0.20)},
    },
    "faixa-foto-bloco": {
        "label": "Foto em faixa com corte seco + bloco de cor",
        "learned_from": "MaxMilhas 300×250",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "The top 46% of the canvas is a lifestyle photograph with a hard straight bottom edge; the subject's face "
            "or the product sits in the right half of that band, never cut by its bottom edge.",
            "Frame a person from the chest up with the whole head inside the band and clear space above the hair (never "
            "cut by the top edge); a worn product (necklace, watch, glasses) stays visible inside the band.",
            "The bottom 54% is a flat solid field in the brand's ground color, edge to edge, with nothing drawn on it: "
            "the copy, the button and the logo go there.",
        ],
        # The block is painted by the Studio when the model lets the photo run past the cut (measured: it went to ~55%
        # and the headline sat on the photo).
        "zones": {"headline": (0.067, 0.50, 0.62, 0.28), "cta": (0.067, 0.81, 0.30, 0.09), "logo": (0.773, 0.85, 0.16, 0.07),
                  "subject": (0.0, 0.0, 1.0, 0.46), "panel": (0.0, 0.46, 1.0, 0.54)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "band": 0.46, "silhouette": (0.70, 0.04, 0.16, 0.42)},
    },
    "tipografico-selo": {
        "label": "Tipográfico com selo da oferta",
        "learned_from": "Governo de Minas · Carnaval (tipográfico), BDMG (selo circular)",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One small solid tab in a secondary brand color at the top-left corner, about 12% wide.",
            "The right third (61% to 95% across) holds one round seal: a flat solid circle in the brand accent color, "
            "about 40% of the height, centred at 78% across and 42% down, with nothing inside it (the Studio sets the "
            "highlight in it).",
            "Everything else is plain: the copy is set by the Studio.",
        ],
        "zones": {"headline": (0.067, 0.16, 0.52, 0.52), "cta": (0.067, 0.74, 0.30, 0.10), "logo": (0.773, 0.85, 0.16, 0.07),
                  "seal": (0.613, 0.22, 0.333, 0.40)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "tab": True, "seal": (0.78, 0.42, 0.20)},
    },
}


# Half page (300×600): the same four ideas stacked for a tall canvas — copy on top, the subject below it, the signature
# at the foot. Safe frame 8% across, 4% down (ad_masks._safe_rect).
LAYOUTS.update({
    "pessoa-circulo-300x600": {
        "label": "Pessoa recortada sobre círculo da marca (vertical)",
        "learned_from": "TIM Pré e Sebrae em meia página: chamada em cima, recorte embaixo",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "Flat solid background in the brand's ground color, edge to edge, no texture, no scenery.",
            "A large solid circle in the brand accent color, centred at 50% across and 76% down, its diameter about "
            "95% of the canvas width, partly cut by the bottom edge.",
            "The person, photographed as a clean studio cut-out, stands in front of the circle in the lower half (head "
            "at about 48–62% down, centred across), cropped by the bottom edge at the waist, facing the camera. A worn "
            "product from the references (necklace, watch, glasses) is large, sharp and well lit on the person.",
            "The top 45% of the canvas is plain background with nothing on it: the copy and the button go there.",
        ],
        "zones": {"logo": (0.08, 0.05, 0.30, 0.045), "headline": (0.08, 0.12, 0.84, 0.24), "cta": (0.08, 0.38, 0.50, 0.055),
                  "subject": (0.0, 0.45, 1.0, 0.55)},
        "logo": "top-left", "cta": True,
        "sketch": {"background": "ground", "circle": (0.50, 0.76, 0.24), "silhouette": (0.50, 0.46, 0.22, 0.54)},
    },
    "produto-diagonal-300x600": {
        "label": "Produto herói cruzando uma diagonal (vertical)",
        "learned_from": "BDMG 300×600 (divisão diagonal foto/produto)",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "The background is split by one bold straight diagonal running from 44% down at the left edge to 60% down "
            "at the right edge: above it a flat solid field in the brand's ground color, below it a soft, out-of-focus "
            "photographic setting.",
            "The product is the hero: large, sharp, in three-quarter view, centred across in the lower half and "
            "crossing the diagonal, about 85% of the canvas width, its lowest point at about 88% down.",
            "The top area (4% to 44% down) is plain flat color with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.08, 0.06, 0.84, 0.25), "cta": (0.08, 0.33, 0.50, 0.055), "logo": (0.70, 0.905, 0.22, 0.045),
                  "subject": (0.04, 0.46, 0.92, 0.44)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "diagonal_h": (0.44, 0.60), "product": (0.50, 0.68, 0.42, 0.13)},
    },
    "faixa-foto-bloco-300x600": {
        "label": "Foto em faixa com corte seco + bloco de cor (vertical)",
        "learned_from": "MaxMilhas meia página",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "The top 56% of the canvas is a lifestyle photograph with a hard straight bottom edge; the subject sits "
            "centred in it, never cut by its bottom edge.",
            "Frame a person from the waist up with the whole head inside the band and clear space above the hair (never "
            "cut by the top edge); a worn product (necklace, watch, glasses) stays visible inside the band.",
            "The bottom 44% is a flat solid field in the brand's ground color, edge to edge, with nothing drawn on it: "
            "the copy, the button and the logo go there.",
        ],
        "zones": {"headline": (0.08, 0.60, 0.84, 0.21), "cta": (0.08, 0.84, 0.50, 0.055), "logo": (0.70, 0.905, 0.22, 0.045),
                  "subject": (0.0, 0.0, 1.0, 0.56), "panel": (0.0, 0.56, 1.0, 0.44)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "band": 0.56, "silhouette": (0.50, 0.08, 0.20, 0.48)},
    },
    "tipografico-selo-300x600": {
        "label": "Tipográfico com selo da oferta (vertical)",
        "learned_from": "Governo de Minas · Carnaval (tipográfico), BDMG (selo circular)",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One small solid tab in a secondary brand color at the top-left corner, about 18% wide.",
            "One round seal: a flat solid circle in the brand accent color, its diameter about 60% of the canvas width, "
            "centred at 50% across and 63% down, with nothing inside it (the Studio sets the highlight in it).",
            "Everything else is plain: the copy is set by the Studio.",
        ],
        "zones": {"headline": (0.08, 0.10, 0.84, 0.36), "seal": (0.20, 0.48, 0.60, 0.30), "cta": (0.08, 0.83, 0.50, 0.055),
                  "logo": (0.70, 0.905, 0.22, 0.045)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "tab": True, "seal": (0.50, 0.63, 0.15)},
    },
})


# Institutional pieces: a statement, no button (and sometimes no logo — a teaser, a manifesto, a campaign signed
# elsewhere). The copy is a single thought set large; the signature, when there is one, closes the piece.
LAYOUTS.update({
    "manifesto-foto-plena": {
        "label": "Manifesto sobre foto plena",
        "learned_from": "Campanhas institucionais de energia e varejo: uma frase sobre a imagem, assinatura no canto",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "One full-bleed photograph edge to edge, cinematic and calm, with a single clear subject in the upper "
            "right two thirds.",
            "The lower-left area (8% to 70% across, 55% to 92% down) is the quietest part of the photo: soft shadow, "
            "sky, wall or out-of-focus ground, darker than the rest, with nothing on it: the statement goes there.",
        ],
        "zones": {"headline": (0.067, 0.56, 0.62, 0.32), "logo": (0.773, 0.85, 0.16, 0.07),
                  "subject": (0.30, 0.0, 0.70, 0.60)},
        "logo": "bottom-right", "cta": False,
        "sketch": {"background": "photo", "silhouette": (0.68, 0.08, 0.17, 0.50)},
    },
    "assinatura-centro": {
        "label": "Frase centralizada com assinatura",
        "learned_from": "Peças tipográficas institucionais (Governo de Minas, campanhas de marca)",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One thin straight line in the brand accent color, centred across at about 74% down, about 20% wide.",
            "Everything else is plain: the statement and the signature are set by the Studio.",
        ],
        "zones": {"headline": (0.10, 0.16, 0.80, 0.52), "logo": (0.38, 0.80, 0.24, 0.10)},
        "logo": "bottom-center", "cta": False, "align": "center",
        "sketch": {"background": "ground", "rule": (0.50, 0.74, 0.10)},
    },
    "retrato-dividido": {
        "label": "Retrato dividido: foto e frase lado a lado",
        "learned_from": "Campanhas de moda e joalheria em meio-a-meio",
        "format": "iab-300x250", "width": 300, "height": 250,
        "scene": [
            "The canvas is split by one hard vertical edge at 52% across.",
            "The left part (0% to 52%) is a portrait photograph: the person framed from the chest up, the whole head "
            "inside with space above the hair, looking at the camera; a worn product from the references (necklace, "
            "watch, glasses) is large, sharp and well lit.",
            "The right part (52% to 100%) is a flat solid field in the brand's ground color with nothing drawn on it: "
            "the statement goes there.",
        ],
        "zones": {"headline": (0.58, 0.14, 0.353, 0.56), "logo": (0.58, 0.82, 0.30, 0.08),
                  "subject": (0.0, 0.0, 0.52, 1.0), "panel": (0.52, 0.0, 0.48, 1.0)},
        "logo": "bottom-left", "cta": False,
        "sketch": {"background": "ground", "split_v": 0.52, "silhouette": (0.26, 0.10, 0.17, 0.90)},
    },
    "manifesto-foto-plena-300x600": {
        "label": "Manifesto sobre foto plena (vertical)",
        "learned_from": "Campanhas institucionais em meia página",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "One full-bleed photograph edge to edge, cinematic and calm, with a single clear subject in the upper half.",
            "The lower part (58% to 96% down) is the quietest part of the photo: soft shadow, ground or out-of-focus "
            "surface, darker than the rest, with nothing on it: the statement goes there.",
        ],
        "zones": {"headline": (0.08, 0.60, 0.84, 0.26), "logo": (0.70, 0.905, 0.22, 0.045),
                  "subject": (0.0, 0.0, 1.0, 0.56)},
        "logo": "bottom-right", "cta": False,
        "sketch": {"background": "photo", "silhouette": (0.50, 0.08, 0.22, 0.46)},
    },
    "assinatura-centro-300x600": {
        "label": "Frase centralizada com assinatura (vertical)",
        "learned_from": "Peças tipográficas institucionais em meia página",
        "format": "iab-300x600", "width": 300, "height": 600,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One thin straight line in the brand accent color, centred across at about 80% down, about 24% wide.",
            "Everything else is plain: the statement and the signature are set by the Studio.",
        ],
        "zones": {"headline": (0.10, 0.22, 0.80, 0.50), "logo": (0.35, 0.86, 0.30, 0.06)},
        "logo": "bottom-center", "cta": False, "align": "center",
        "sketch": {"background": "ground", "rule": (0.50, 0.80, 0.12)},
    },
})


def for_format(layout_id: str, format_key: str) -> str:
    """The layout's version for a format ('pessoa-circulo' in a 300×600 -> 'pessoa-circulo-300x600')."""
    from . import ad_masks
    fmt = ad_masks.FORMATS.get(format_key)
    sized = f"{layout_id}-{fmt[1]}x{fmt[2]}" if fmt else ""
    return sized if sized in LAYOUTS else layout_id


def get(layout_id: str | None) -> dict | None:
    return LAYOUTS.get(str(layout_id or ""))


def spec(layout_id: str) -> dict | None:
    """The layout in the shape the composer and the reviewer use (same keys as an ``ad_masks`` spec)."""
    item = get(layout_id)
    if not item:
        return None
    from . import ad_masks
    left, top, right, bottom = ad_masks._safe_rect(item["width"], item["height"])
    safe = (round(left, 4), round(top, 4), round(right - left, 4), round(bottom - top, 4))
    return {"id": f"pos:{layout_id}", "format": item["format"], "format_label": ad_masks.FORMATS[item["format"]][0],
            "group": "iab", "width": item["width"], "height": item["height"],
            "class": ad_masks.layout_class(item["width"], item["height"]), "family": f"pos-{layout_id}",
            "family_label": item["label"], "logo": item["logo"], "cta": item["cta"], "safe": safe,
            **({"align": item["align"]} if item.get("align") else {}),
            "zones": dict(item["zones"]), "positions": True}


def brand_colors(palette) -> dict:
    """The colors a position layout names: a deep brand ground (high contrast for white copy) and the accent shape."""
    from .banner_compose import accent_color, ground_color
    ground = ground_color(palette)
    accent = accent_color(palette)
    return {"ground": "#%02X%02X%02X" % ground, "accent": "#%02X%02X%02X" % accent}


def words(layout_id: str, text_free: bool = True, palette=None) -> list[str]:
    """The layout for the image model: positions and relations, in plain words (binding), with the brand colors named
    (left to itself the model picks the safest pale tone and the brand disappears)."""
    item = get(layout_id)
    if not item:
        return []
    colors = brand_colors(palette or [])
    # The model drifts to black when it reads "deep" (measured: Reserva's brown ground came out black): name the tone.
    scene = [line.replace("the brand's ground color", f"the brand's deep ground color {colors['ground']} (that exact "
                          "colored tone, not black, not grey)")
             .replace("the brand accent color", f"the brand accent color {colors['accent']}") for line in item["scene"]]
    return [
        f"LAYOUT BY POSITION (binding, {item['label']}): the attached sketch shows where each element goes, as shapes; "
        "it is a placement guide, not artwork to copy (no grey, no outlines, no hatching in the final image).",
        *scene,
        "Leave the copy area completely empty: the Studio sets the copy" + (", the button" if item["cta"] else "")
        + " and the signature there afterwards. No button, badge or logo drawn in the picture."
        if text_free else "Set the copy inside the empty copy area.",
    ]


def sketch_path(layout_id: str) -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "images" / "cadu" / "studio" / "references" / "positions" / f"{layout_id}.png"


def sketch_url(layout_id: str) -> str:
    return SKETCH_URL_PREFIX + f"{layout_id}.png"


def render_sketch(layout_id: str, longest_side: int = 1200) -> bytes:
    """The placement sketch: soft tones and real shapes (circle, diagonal, silhouette), never a grid of boxes."""
    item = get(layout_id)
    w, h = item["width"], item["height"]
    scale = longest_side / max(w, h)
    size = (round(w * scale), round(h * scale))
    canvas = Image.new("RGB", size, (214, 214, 210))
    draw = ImageDraw.Draw(canvas)
    sketch = item["sketch"]
    W, H = size
    shape_tone, subject_tone, line = (150, 150, 146), (92, 92, 90), max(2, round(longest_side / 300))
    if "band" in sketch:
        draw.rectangle((0, 0, W, round(H * sketch["band"])), fill=(176, 176, 172))
    if sketch.get("background") == "photo":
        draw.rectangle((0, 0, W, H), fill=(176, 176, 172))
    if "split_v" in sketch:
        draw.rectangle((0, 0, round(W * sketch["split_v"]), H), fill=(176, 176, 172))
    if "rule" in sketch:
        cx, cy, half = sketch["rule"]
        draw.rectangle((W * (cx - half), H * cy - line, W * (cx + half), H * cy + line), fill=shape_tone)
    if "diagonal_h" in sketch:
        left_y, right_y = sketch["diagonal_h"]
        draw.polygon([(0, round(H * left_y)), (W, round(H * right_y)), (W, H), (0, H)], fill=(176, 176, 172))
    if "diagonal" in sketch:
        top, bottom = sketch["diagonal"]
        draw.polygon([(round(W * top), 0), (W, 0), (W, H), (round(W * bottom), H)], fill=(176, 176, 172))
    if "circle" in sketch:
        cx, cy, r = sketch["circle"]
        radius = r * H
        draw.ellipse((W * cx - radius, H * cy - radius, W * cx + radius, H * cy + radius), fill=shape_tone)
    if "seal" in sketch:
        cx, cy, r = sketch["seal"]
        radius = r * H
        draw.ellipse((W * cx - radius, H * cy - radius, W * cx + radius, H * cy + radius), fill=(236, 236, 232))
    if sketch.get("tab"):
        draw.rectangle((0, 0, round(W * 0.12), round(H * 0.05)), fill=shape_tone)
    if "silhouette" in sketch:
        cx, top, half_w, height = sketch["silhouette"]
        head_r = half_w * W * 0.42
        head_cy = H * top + head_r * 1.1
        draw.ellipse((W * cx - head_r, head_cy - head_r, W * cx + head_r, head_cy + head_r), fill=subject_tone)
        shoulders = head_cy + head_r * 1.2
        draw.rounded_rectangle((W * (cx - half_w), shoulders, W * (cx + half_w), H * (top + height)),
                               radius=round(half_w * W * 0.5), fill=subject_tone)
    if "product" in sketch:
        cx, cy, rw, rh = sketch["product"]
        draw.ellipse((W * (cx - rw), H * (cy - rh), W * (cx + rw), H * (cy + rh)), fill=subject_tone)
    # Copy positions as soft text lines and a pill, the logo as a small mark: positions, not panels.
    zones = item["zones"]
    hx, hy, hw, hh = zones["headline"]
    for index, share in enumerate((0.55, 0.95, 0.80)):
        bar_h = H * hh * (0.12 if index == 0 else 0.22)
        top = H * hy + sum(H * hh * (0.12 if i == 0 else 0.22) * 1.35 for i in range(index))
        left = W * (hx + (hw - hw * share) / 2) if item.get("align") == "center" else W * hx
        draw.rounded_rectangle((left, top, left + W * hw * share, top + bar_h), radius=round(bar_h / 3), fill=(120, 120, 116))
    if "cta" in zones:
        cx, cy, cw, ch = zones["cta"]
        draw.rounded_rectangle((W * cx, H * cy, W * (cx + cw), H * (cy + ch)), radius=round(H * ch / 2), outline=(90, 90, 88), width=line)
    if "logo" in zones:
        lx, ly, lw, lh = zones["logo"]
        r = H * lh * 0.35
        draw.ellipse((W * lx, H * ly + H * lh / 2 - r, W * lx + 2 * r, H * ly + H * lh / 2 + r), outline=(90, 90, 88), width=line)
        draw.line((W * lx + 2.6 * r, H * ly + H * lh / 2, W * (lx + lw), H * ly + H * lh / 2), fill=(90, 90, 88), width=line)
    out = io.BytesIO()
    canvas.save(out, "PNG", optimize=True)
    return out.getvalue()


def write_sketches() -> list[Path]:
    paths = []
    for layout_id in LAYOUTS:
        path = sketch_path(layout_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_sketch(layout_id))
        paths.append(path)
    return paths


def sketch_data_url(layout_id: str) -> str:
    """The sketch embedded in the request (never depends on the file being deployed or publicly reachable)."""
    path = sketch_path(layout_id)
    content = path.read_bytes() if path.is_file() else render_sketch(layout_id)
    return "data:image/png;base64," + base64.b64encode(content).decode("ascii")
