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
import re
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
            "The person, photographed as a clean studio cut-out, stands in front of the circle on the right half, "
            "occupying only from 56% to 94% across: the whole head and both shoulders inside the canvas with at least 6% "
            "of free space to the right edge, head at about 16–46% down, cropped by the bottom edge at the waist, facing "
            "the camera; shoulders overlap the circle edge. Anything the person holds or wears (a bottle, a necklace, a "
            "watch, glasses) stays inside that same 56%–94% column, large, sharp and well lit: it is part of the offer.",
            "The left half (8% to 50% across) is plain background with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.067, 0.10, 0.38, 0.50), "cta": (0.067, 0.66, 0.30, 0.10), "logo": (0.067, 0.84, 0.18, 0.08),
                  "subject": (0.56, 0.12, 0.38, 0.88)},
        "logo": "bottom-left", "cta": True,
        "sketch": {"background": "ground", "circle": (0.74, 0.58, 0.40), "silhouette": (0.75, 0.16, 0.19, 0.84)},
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


# Leaderboard (728×90), billboard (970×250) and skyscraper (160×600): the same ideas fitted to the shape. A banner
# 90 px high is one line of reading — logo, statement, button, picture at the end —, the billboard is the 300×250 piece
# stretched sideways (copy left, picture right), the skyscraper is the half page narrowed (copy on top, picture below).
LAYOUTS.update({
    # ---- 970×250 -----------------------------------------------------------------------------------------------
    "produto-diagonal-970x250": {
        "label": "Produto herói cruzando uma diagonal (billboard)",
        "learned_from": "BDMG 300×600 (divisão diagonal foto/produto) em formato largo",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "The background is split by one bold straight diagonal running from 60% across at the top to 48% across "
            "at the bottom: left of it a flat solid field in the brand's ground color, right of it a soft, "
            "out-of-focus photographic setting.",
            "The product is the hero: large, sharp, in three-quarter view, on the right side and crossing the diagonal, "
            "about 30% of the canvas width and 75% of its height, its lowest point at about 88% down.",
            "The left 45% (3.5% to 46% across) is plain flat color with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.035, 0.12, 0.42, 0.50), "cta": (0.035, 0.68, 0.15, 0.14), "logo": (0.84, 0.82, 0.125, 0.10),
                  "subject": (0.50, 0.10, 0.36, 0.78)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "diagonal": (0.60, 0.48), "product": (0.72, 0.52, 0.12, 0.30)},
    },
    "faixa-foto-bloco-970x250": {
        "label": "Foto em faixa lateral com corte seco + bloco de cor (billboard)",
        "learned_from": "MaxMilhas 300×250 virado de lado",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "The right 38% of the canvas is a lifestyle photograph with a hard straight vertical left edge; the "
            "subject's face or the product sits in the middle of that band, never cut by its left edge.",
            "Frame a person from the chest up with the whole head inside the band and clear space above the hair; a "
            "worn product (necklace, watch, glasses) stays visible inside the band.",
            "The left 62% is a flat solid field in the brand's ground color, edge to edge, with nothing drawn on it: "
            "the copy, the button and the logo go there.",
        ],
        "zones": {"logo": (0.035, 0.08, 0.12, 0.10), "headline": (0.035, 0.24, 0.54, 0.42), "cta": (0.035, 0.70, 0.15, 0.14),
                  "subject": (0.62, 0.0, 0.38, 1.0), "panel": (0.0, 0.0, 0.62, 1.0)},
        "logo": "top-left", "cta": True,
        "sketch": {"background": "ground", "photo_right": 0.38, "silhouette": (0.81, 0.10, 0.07, 0.90)},
    },
    "tipografico-selo-970x250": {
        "label": "Tipográfico com selo da oferta (billboard)",
        "learned_from": "Governo de Minas · Carnaval (tipográfico), BDMG (selo circular)",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One small solid tab in a secondary brand color at the top-left corner, about 4% wide.",
            "The right side holds one round seal: a flat solid circle in the brand accent color, about 60% of the "
            "height, centred at 82% across and 50% down, with nothing inside it (the Studio sets the highlight in it).",
            "Everything else is plain: the copy is set by the Studio.",
        ],
        "zones": {"headline": (0.035, 0.16, 0.62, 0.46), "cta": (0.035, 0.70, 0.14, 0.14), "logo": (0.84, 0.83, 0.125, 0.09),
                  "seal": (0.743, 0.20, 0.155, 0.60)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "tab": True, "seal": (0.82, 0.50, 0.30)},
    },
    "manifesto-foto-plena-970x250": {
        "label": "Manifesto sobre foto plena (billboard)",
        "learned_from": "Campanhas institucionais de energia e varejo: uma frase sobre a imagem, assinatura no canto",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "One full-bleed photograph edge to edge, cinematic and calm, with a single clear subject in the right half.",
            "The lower-left area (3.5% to 58% across, 48% to 92% down) is the quietest part of the photo: soft shadow, "
            "sky, wall or out-of-focus ground, darker than the rest, with nothing on it: the statement goes there.",
        ],
        "zones": {"headline": (0.035, 0.50, 0.55, 0.38), "logo": (0.84, 0.80, 0.125, 0.12),
                  "subject": (0.50, 0.0, 0.50, 0.70)},
        "logo": "bottom-right", "cta": False,
        "sketch": {"background": "photo", "silhouette": (0.76, 0.08, 0.06, 0.62)},
    },
    "assinatura-centro-970x250": {
        "label": "Frase centralizada com assinatura (billboard)",
        "learned_from": "Peças tipográficas institucionais (Governo de Minas, campanhas de marca)",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One thin straight line in the brand accent color, centred across at about 70% down, about 8% wide.",
            "Everything else is plain: the statement and the signature are set by the Studio.",
        ],
        "zones": {"headline": (0.12, 0.14, 0.76, 0.50), "logo": (0.43, 0.76, 0.14, 0.14)},
        "logo": "bottom-center", "cta": False, "align": "center",
        "sketch": {"background": "ground", "rule": (0.50, 0.70, 0.04)},
    },
    "retrato-dividido-970x250": {
        "label": "Retrato dividido: foto e frase lado a lado (billboard)",
        "learned_from": "Campanhas de moda e joalheria em meio-a-meio",
        "format": "iab-970x250", "width": 970, "height": 250,
        "scene": [
            "The canvas is split by one hard vertical edge at 34% across.",
            "The left part (0% to 34%) is a portrait photograph: the person framed from the chest up, the whole head "
            "inside with space above the hair, looking at the camera; a worn product from the references (necklace, "
            "watch, glasses) is large, sharp and well lit.",
            "The right part (34% to 100%) is a flat solid field in the brand's ground color with nothing drawn on it: "
            "the statement goes there.",
        ],
        "zones": {"headline": (0.40, 0.14, 0.52, 0.52), "logo": (0.40, 0.76, 0.14, 0.14),
                  "subject": (0.0, 0.0, 0.34, 1.0), "panel": (0.34, 0.0, 0.66, 1.0)},
        "logo": "bottom-left", "cta": False,
        "sketch": {"background": "ground", "split_v": 0.34, "silhouette": (0.17, 0.10, 0.07, 0.90)},
    },
    # ---- 728×90 ------------------------------------------------------------------------------------------------
    "faixa-foto-bloco-728x90": {
        "label": "Foto na ponta com corte seco + bloco de cor (leaderboard)",
        "learned_from": "MaxMilhas 300×250 em faixa",
        "format": "iab-728x90", "width": 728, "height": 90,
        "scene": [
            "The right 24% of the canvas is a lifestyle photograph with a hard straight vertical left edge; a face or "
            "the product sits in the middle of it, never cut by its left edge.",
            "Frame only a face (head and shoulders) or the product, large and sharp, with space around it.",
            "The left 76% is a flat solid field in the brand's ground color, edge to edge, with nothing drawn on it: "
            "the logo, the copy and the button go there, in one line.",
        ],
        "zones": {"logo": (0.035, 0.12, 0.10, 0.76), "headline": (0.155, 0.12, 0.40, 0.76), "cta": (0.58, 0.28, 0.16, 0.44),
                  "subject": (0.76, 0.0, 0.24, 1.0), "panel": (0.0, 0.0, 0.76, 1.0)},
        "logo": "left", "cta": True,
        "sketch": {"background": "ground", "photo_right": 0.24, "silhouette": (0.88, 0.06, 0.05, 0.94)},
    },
    "tipografico-selo-728x90": {
        "label": "Tipográfico com selo da oferta (leaderboard)",
        "learned_from": "Governo de Minas · Carnaval (tipográfico), BDMG (selo circular)",
        "format": "iab-728x90", "width": 728, "height": 90,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "At the right end one round seal: a flat solid circle in the brand accent color, about 84% of the height, "
            "centred at 90% across and 50% down, with nothing inside it (the Studio sets the highlight in it).",
            "Everything else is plain: the copy is set by the Studio.",
        ],
        "zones": {"logo": (0.035, 0.12, 0.10, 0.76), "headline": (0.155, 0.12, 0.42, 0.76), "cta": (0.60, 0.28, 0.15, 0.44),
                  "seal": (0.848, 0.08, 0.104, 0.84)},
        "logo": "left", "cta": True,
        "sketch": {"background": "ground", "seal": (0.90, 0.50, 0.42)},
    },
    "manifesto-foto-plena-728x90": {
        "label": "Manifesto sobre foto plena (leaderboard)",
        "learned_from": "Campanhas institucionais: uma frase sobre a imagem, assinatura na ponta",
        "format": "iab-728x90", "width": 728, "height": 90,
        "scene": [
            "One full-bleed photograph edge to edge, calm and wide, with the interest on the right third.",
            "The left 65% is the quietest part of the photo: soft shadow, sky or out-of-focus ground, darker than the "
            "rest, with nothing on it: the statement goes there, in one or two lines.",
        ],
        "zones": {"headline": (0.035, 0.14, 0.62, 0.72), "logo": (0.84, 0.18, 0.125, 0.64),
                  "subject": (0.66, 0.0, 0.34, 1.0)},
        "logo": "right", "cta": False,
        "sketch": {"background": "photo", "silhouette": (0.74, 0.08, 0.05, 0.92)},
    },
    "assinatura-centro-728x90": {
        "label": "Frase centralizada com assinatura (leaderboard)",
        "learned_from": "Peças tipográficas institucionais (Governo de Minas, campanhas de marca)",
        "format": "iab-728x90", "width": 728, "height": 90,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "Everything is plain: the statement and the signature are set by the Studio.",
        ],
        "zones": {"logo": (0.035, 0.18, 0.12, 0.64), "headline": (0.22, 0.14, 0.56, 0.72)},
        "logo": "left", "cta": False, "align": "center",
        "sketch": {"background": "ground"},
    },
    # ---- 160×600 -----------------------------------------------------------------------------------------------
    "pessoa-circulo-160x600": {
        "label": "Pessoa recortada sobre círculo da marca (arranha-céu)",
        "learned_from": "TIM Pré e Sebrae em arranha-céu: chamada em cima, recorte embaixo",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "Flat solid background in the brand's ground color, edge to edge, no texture, no scenery.",
            "A solid circle in the brand accent color, centred at 50% across and 78% down, its diameter about 100% of "
            "the canvas width, cut by the bottom edge.",
            "The person, photographed as a clean studio cut-out, stands in front of the circle in the lower half (head "
            "at about 52–64% down, centred across), cropped by the bottom edge at the chest, facing the camera.",
            "The top 46% of the canvas is plain background with nothing on it: the logo, the copy and the button go there.",
        ],
        "zones": {"logo": (0.08, 0.035, 0.55, 0.04), "headline": (0.08, 0.10, 0.84, 0.26), "cta": (0.08, 0.38, 0.84, 0.05),
                  "subject": (0.0, 0.48, 1.0, 0.52)},
        "logo": "top-left", "cta": True,
        "sketch": {"background": "ground", "circle": (0.50, 0.78, 0.1333), "silhouette": (0.50, 0.50, 0.32, 0.50)},
    },
    "produto-diagonal-160x600": {
        "label": "Produto herói cruzando uma diagonal (arranha-céu)",
        "learned_from": "BDMG 300×600 (divisão diagonal foto/produto)",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "The background is split by one bold straight diagonal running from 46% down at the left edge to 58% down "
            "at the right edge: above it a flat solid field in the brand's ground color, below it a soft, "
            "out-of-focus photographic setting.",
            "The product is the hero: sharp, in three-quarter view, centred across in the lower half and crossing the "
            "diagonal, about 85% of the canvas width, its lowest point at about 88% down.",
            "The top area (2% to 46% down) is plain flat color with nothing on it: the copy goes there.",
        ],
        "zones": {"headline": (0.08, 0.05, 0.84, 0.28), "cta": (0.08, 0.36, 0.84, 0.05), "logo": (0.45, 0.925, 0.47, 0.04),
                  "subject": (0.04, 0.48, 0.92, 0.42)},
        "logo": "bottom-right", "cta": True,
        "sketch": {"background": "ground", "diagonal_h": (0.46, 0.58), "product": (0.50, 0.70, 0.42, 0.09)},
    },
    "faixa-foto-bloco-160x600": {
        "label": "Foto em faixa com corte seco + bloco de cor (arranha-céu)",
        "learned_from": "MaxMilhas meia página",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "The top 54% of the canvas is a lifestyle photograph with a hard straight bottom edge; the subject sits "
            "centred in it, never cut by its bottom edge.",
            "Frame a person from the chest up with the whole head inside the band and clear space above the hair; a "
            "worn product (necklace, watch, glasses) stays visible inside the band.",
            "The bottom 46% is a flat solid field in the brand's ground color, edge to edge, with nothing drawn on it: "
            "the copy, the button and the logo go there.",
        ],
        "zones": {"headline": (0.08, 0.575, 0.84, 0.22), "cta": (0.08, 0.82, 0.84, 0.05), "logo": (0.08, 0.915, 0.55, 0.045),
                  "subject": (0.0, 0.0, 1.0, 0.54), "panel": (0.0, 0.54, 1.0, 0.46)},
        "logo": "bottom-left", "cta": True,
        "sketch": {"background": "ground", "band": 0.54, "silhouette": (0.50, 0.06, 0.30, 0.48)},
    },
    "tipografico-selo-160x600": {
        "label": "Tipográfico com selo da oferta (arranha-céu)",
        "learned_from": "Governo de Minas · Carnaval (tipográfico), BDMG (selo circular)",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One round seal: a flat solid circle in the brand accent color, its diameter about 84% of the canvas "
            "width, centred at 50% across and 60% down, with nothing inside it (the Studio sets the highlight in it).",
            "Everything else is plain: the copy is set by the Studio.",
        ],
        "zones": {"headline": (0.08, 0.06, 0.84, 0.40), "seal": (0.08, 0.488, 0.84, 0.224), "cta": (0.08, 0.82, 0.84, 0.05),
                  "logo": (0.08, 0.90, 0.55, 0.045)},
        "logo": "bottom-left", "cta": True,
        "sketch": {"background": "ground", "seal": (0.50, 0.60, 0.112)},
    },
    "manifesto-foto-plena-160x600": {
        "label": "Manifesto sobre foto plena (arranha-céu)",
        "learned_from": "Campanhas institucionais em meia página",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "One full-bleed photograph edge to edge, cinematic and calm, with a single clear subject in the upper half.",
            "The lower part (60% to 96% down) is the quietest part of the photo: soft shadow, ground or out-of-focus "
            "surface, darker than the rest, with nothing on it: the statement goes there.",
        ],
        "zones": {"headline": (0.08, 0.62, 0.84, 0.26), "logo": (0.08, 0.915, 0.55, 0.045),
                  "subject": (0.0, 0.0, 1.0, 0.58)},
        "logo": "bottom-left", "cta": False,
        "sketch": {"background": "photo", "silhouette": (0.50, 0.08, 0.30, 0.48)},
    },
    "assinatura-centro-160x600": {
        "label": "Frase centralizada com assinatura (arranha-céu)",
        "learned_from": "Peças tipográficas institucionais em meia página",
        "format": "iab-160x600", "width": 160, "height": 600,
        "scene": [
            "No photograph. A flat solid background in the brand's ground color with a subtle grain, edge to edge.",
            "One thin straight line in the brand accent color, centred across at about 79% down, about 30% wide.",
            "Everything else is plain: the statement and the signature are set by the Studio.",
        ],
        "zones": {"headline": (0.08, 0.22, 0.84, 0.46), "logo": (0.18, 0.84, 0.64, 0.06)},
        "logo": "bottom-center", "cta": False, "align": "center",
        "sketch": {"background": "ground", "rule": (0.50, 0.79, 0.15)},
    },
})


def for_format(layout_id: str, format_key: str) -> str:
    """The layout's version for a format ('pessoa-circulo' in a 300×600 -> 'pessoa-circulo-300x600').

    "" when the layout has no version for that format (measured and dropped: a cut-out person or a product in a
    970×250 or 728×90 band scored 35–65 over several rounds)."""
    from . import ad_masks
    fmt = ad_masks.FORMATS.get(format_key)
    sized = f"{layout_id}-{fmt[1]}x{fmt[2]}" if fmt else ""
    if sized in LAYOUTS:
        return sized
    base = LAYOUTS.get(layout_id)
    # A layout drawn for another size does not fit this one: no layout here (the Studio's standard composition runs).
    return "" if fmt and base and base["format"] != format_key else layout_id


_PERSON = re.compile(r"\b(pessoa|mulher|homem|modelo|crian[çc]a|retrato|casal|fam[íi]lia|atleta|m[ée]dic[oa]|jovem|"
                     r"person|woman|man|people|portrait)\b", re.I)
_PRODUCT = re.compile(r"(produto|smartphone|celular|aparelho|t[êe]nis|garrafa|embalag|notebook|carro|product|phone|"
                      r"bottle|package)", re.I)
_OFFER_LINE = re.compile(r"^(?:Título|Destaque):.*(?:\d|%|\$)", re.I | re.M)


def choose(format_key: str, briefing: str) -> str:
    """The layout for a briefing in a format, or "" (the Studio's standard composition runs).

    Without a button the piece is institutional (a statement over a photo); with one, an offer without person or
    product is typographic with the offer in a seal, a product crosses a diagonal, a person sits on the brand's
    circle, anything else is a photo band over a color block. A format without that layout falls back to the photo
    band, then the seal."""
    from .banner_compose import extract_copy
    headline, cta = extract_copy(briefing)
    if not headline:
        return ""
    if not cta:
        candidates = ["manifesto-foto-plena", "assinatura-centro"]
    else:
        person, product = bool(_PERSON.search(briefing)), bool(_PRODUCT.search(briefing))
        offer = bool(_OFFER_LINE.search(briefing))
        first = ("tipografico-selo" if offer and not person and not product else "produto-diagonal" if product
                 else "pessoa-circulo" if person else "faixa-foto-bloco")
        candidates = [first, "faixa-foto-bloco", "tipografico-selo"]
    return next((sized for sized in (for_format(item, format_key) for item in candidates) if sized), "")


def director_note(layout_id: str, room: int) -> str:
    """What the director reads about a layout (label and scene), cut to ``room`` characters — never the copy."""
    item = get(layout_id)
    if not item or room <= 0:
        return ""
    note = "Layout da peça (já definido, não reposicione nada): " + item["label"] + ". " + " ".join(item["scene"])
    return note if len(note) <= room else note[:room].rsplit(" ", 1)[0]


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
    if "photo_right" in sketch:
        draw.rectangle((round(W * (1 - sketch["photo_right"])), 0, W, H), fill=(176, 176, 172))
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
