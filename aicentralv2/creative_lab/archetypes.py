"""Layout archetypes learned from real Brazilian ads (docs/creative-lab/01-anatomia-criativos-reais.md).

An archetype is how a piece is *diagrammed*: where the hero, the copy levels, the people and the
signature band go, per format. The Director turns it into explicit zones so the model lays out an ad
instead of painting an atmosphere.
"""

from __future__ import annotations

# Target formats of the Lab. ``ratio`` is what we ask for; ``size`` is the delivered piece.
FORMATS = {
    "feed-1x1": {"label": "Feed 1:1", "ratio": "1:1", "size": [1080, 1080], "family": "square"},
    "feed-4x5": {"label": "Feed 4:5", "ratio": "4:5", "size": [1080, 1350], "family": "portrait"},
    "story-9x16": {"label": "Story 9:16", "ratio": "9:16", "size": [1080, 1920], "family": "tall"},
    "wide-16x9": {"label": "Horizontal 16:9", "ratio": "16:9", "size": [1920, 1080], "family": "wide"},
    "iab-300x250": {"label": "IAB 300×250", "ratio": "6:5", "size": [600, 500], "family": "square"},
    "iab-300x600": {"label": "IAB 300×600", "ratio": "1:2", "size": [600, 1200], "family": "tall"},
    "linkedin-1200x627": {"label": "LinkedIn 1.91:1", "ratio": "16:9", "size": [1200, 627], "family": "wide"},
    "display-300x300": {"label": "Display 300×300", "ratio": "1:1", "size": [600, 600], "family": "square"},
}

# Zones per format family. Percentages of the canvas, top-to-bottom reading order.
_ZONES = {
    "square": "kicker+headline top 0–40%, hero element 40–65%, support+CTA 65–82%, signature band 82–100%",
    "portrait": "kicker+headline top 0–35%, hero element 35–68%, support+CTA 68–85%, signature band 85–100%",
    "tall": "brand+kicker 6–14% (keep 0–6% clear for app UI), headline 14–32%, hero 32–70%, CTA 72–84%, signature 86–96% (keep 96–100% clear)",
    "wide": "copy column on the left 0–48% (kicker, headline, hero, CTA stacked), visual on the right 52–100%, logo bottom-right",
}

ARCHETYPES = {
    "oferta-heroi": {
        "label": "Oferta com número herói",
        "learned_from": "MaxMilhas 300×250, TIM Pré story, BDMG 300×600",
        "when": "varejo, telecom, financeiro: preço, desconto, franquia ou taxa",
        "layout": "Solid brand-color field. The offer number is the hero, 2–4× the headline size, in the accent color, "
                  "with its qualifier set small right next to it. A photo enters as a cut-out person or as a clean photo block, never as the background behind text.",
        "devices": "optional urgency seal (circle) or a badge whose shape echoes the brand; solid rectangular CTA button",
        "copy_levels": ["kicker", "headline", "highlight", "support", "cta", "legal"],
    },
    "foto-faixa-bloco": {
        "label": "Foto em faixa + bloco de cor",
        "learned_from": "MaxMilhas 300×250",
        "when": "desejo/lifestyle com oferta; display pequeno",
        "layout": "A lifestyle photo occupies the top 35–40% as a band with a hard straight edge; below it a flat brand-color block "
                  "holds headline, highlighted offer, one support line, CTA button bottom-left and logo bottom-right.",
        "devices": "hard horizontal cut between photo and color block; CTA button in a contrasting brand color",
        "copy_levels": ["headline", "highlight", "support", "cta"],
    },
    "tipografico-faixa": {
        "label": "Tipográfico puro + faixa de assinatura",
        "learned_from": "Governo de Minas · Carnaval, Uhuru",
        "when": "institucional, conceito, campanha de posicionamento",
        "layout": "No photo. Flat brand-color field with subtle grain. Very large heavy uppercase sans headline left-aligned over 3–5 lines; "
                  "one key word in the accent color. A light signature band at the bottom 25% holds the logo(s) and tagline.",
        "devices": "small solid tab/corner accent in a secondary brand color; optional rhythm (anaphora) with alternating line colors",
        "copy_levels": ["headline", "highlight", "tagline"],
    },
    "colagem-recortes": {
        "label": "Colagem de recortes + ícone 3D",
        "learned_from": "Sebrae · Calendário de Vendas",
        "when": "serviço para um público plural (MPE, cidadãos, alunos)",
        "layout": "Flat brand-color background. Heavy italic uppercase headline top-left, a ribbon/tag below it with the edition/date. "
                  "A group of 3–5 cut-out people who ARE the audience (different ages, races, professions, each holding a tool of the trade), "
                  "overlapping in the lower-left two thirds; support sentence on the right; one glossy 3D icon top-right.",
        "devices": "angled ribbon tag in the secondary color; 3D clay-style icon; bottom band in the secondary color with the logo",
        "copy_levels": ["headline", "tag", "support", "signature"],
    },
    "recorte-chamada": {
        "label": "Recorte + chamada + barras",
        "learned_from": "Sebrae · Planeje-se, TIM Pré",
        "when": "chamada direta com uma pessoa porta-voz",
        "layout": "Flat brand background. One cut-out person on the right third looking at the camera with an inviting gesture or using the product; "
                  "huge headline on the left two thirds; thick horizontal bars of the secondary color as graphic rhythm; small 3D icon as accent.",
        "devices": "horizontal color bars; soft glow behind the person; bottom band with logo",
        "copy_levels": ["headline", "support", "cta", "signature"],
    },
    "quebra-silabica": {
        "label": "Institucional com quebra silábica",
        "learned_from": "ALMG · Educação",
        "when": "institucional público com tema (educação, saúde, cultura)",
        "layout": "Saturated flat background. Small kicker above a theme word broken into stacked syllables, huge, white. "
                  "Two cut-out people of different generations in the center looking at the camera; hand-drawn doodle icons of the theme around them; "
                  "white signature band at the bottom with tagline, logo and social icons.",
        "devices": "hand-drawn doodles; syllable break; white bottom band",
        "copy_levels": ["kicker", "headline", "support", "tagline"],
    },
    "split-financeiro": {
        "label": "Split foto/produto financeiro",
        "learned_from": "BDMG 300×600",
        "when": "crédito, taxa, produto financeiro de governo",
        "layout": "Presenter line on top; the canvas split diagonally between a customer photo (entrepreneur using a tablet) and a darkened product photo; "
                  "the rate is the hero in the accent color with its qualifier; a circular urgency seal; the ombudsman/legal line at the very bottom.",
        "devices": "diagonal split, circular seal, institutional stripe",
        "copy_levels": ["kicker", "headline", "highlight", "support", "seal", "legal"],
    },
    "ritmo-tipografico": {
        "label": "Ritmo tipográfico sobre foto escurecida",
        "learned_from": "Uhuru",
        "when": "agência, conceito, manifesto",
        "layout": "Full-bleed photo darkened and desaturated to near monochrome in the brand's dark color; a stack of short condensed uppercase lines "
                  "alternating two brand colors, ending in a turn line; signature sentence and small symbol at the bottom.",
        "devices": "alternating line colors; heavy darkening of the photo",
        "copy_levels": ["headline", "tagline"],
    },
}


def archetype(key: str | None) -> dict | None:
    return ARCHETYPES.get(key or "")


def format_info(key: str | None) -> dict | None:
    return FORMATS.get(key or "")


def zones_for_ratio(ratio: str) -> str:
    try:
        width, height = (float(part) for part in ratio.split(":"))
    except ValueError:
        return _ZONES["square"]
    value = width / height
    family = "wide" if value >= 1.5 else "square" if value >= 0.95 else "portrait" if value >= 0.7 else "tall"
    return _ZONES[family]


def catalog_view() -> dict:
    return {"archetypes": [{"key": key, **item} for key, item in ARCHETYPES.items()],
            "formats": [{"key": key, **item} for key, item in FORMATS.items()]}
