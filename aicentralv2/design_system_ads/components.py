"""Componentes de anúncio, densidade, arquétipo e fundos — não UI de site."""

from __future__ import annotations

COMPONENTS = {
    "logo": {"priority": 0, "safe": True, "bleed": False, "drop": False, "label": "logo"},
    "headline": {"priority": 0, "safe": True, "max_lines": 2, "drop": False, "label": "headline"},
    "product": {"priority": 0, "safe": False, "bleed": True, "min_share": 0.28, "label": "produto"},
    "cta": {"priority": 1, "safe": True, "drop": False, "label": "cta"},
    "visual": {"priority": 1, "safe": False, "bleed": True, "label": "lifestyle"},
    "ground": {"priority": 1, "safe": False, "bleed": True, "label": "fundo"},
    "support": {"priority": 2, "safe": True, "max_lines": 2, "label": "apoio"},
    "legal": {"priority": 3, "safe": True, "max_lines": 1, "label": "legal"},
    "chip": {"priority": 3, "safe": True, "label": "selo"},
    "icon": {"priority": 3, "safe": True, "label": "ícone"},
}

DENSITY = {
    "compact": {"max_visible": 3, "park_from": 2, "formats": ("iab-leaderboard", "iab-mobile")},
    "standard": {"max_visible": 5, "park_from": 3, "formats": ("iab-medium", "iab-skyscraper")},
    "rich": {"max_visible": 7, "park_from": 4, "formats": ("iab-billboard", "iab-halfpage")},
}

ARCHETYPES = {
    "brand": {"ground": "wash", "lead": "headline", "label": "Marca"},
    "product-hero": {"ground": "paper", "lead": "product", "label": "Produto"},
    "lifestyle": {"ground": "image", "lead": "visual", "label": "Lifestyle"},
    "promotion": {"ground": "wash", "lead": "cta", "label": "Promoção"},
}

GROUND_KINDS = ("paper", "wash", "image")


def component_of(role):
    key = str(role or "").split("-")[0]
    if key == "ornament":
        return {"priority": 3, "safe": False, "bleed": True, "label": "recorte"}
    return dict(COMPONENTS.get(role) or COMPONENTS.get(key) or {"priority": 3, "label": role})


def density_for(format_key, recipe_density=None):
    key = str(format_key or "")
    if recipe_density == "thin" or key in DENSITY["compact"]["formats"]:
        return "compact"
    if key in DENSITY["rich"]["formats"]:
        return "rich"
    return "standard"


def should_park(role, density):
    spec = DENSITY.get(density) or DENSITY["standard"]
    return int(component_of(role).get("priority") or 3) >= int(spec["park_from"])


def default_backgrounds(tokens):
    tokens = tokens if isinstance(tokens, dict) else {}
    paper = tokens.get("paper") or "#FFFFFF"
    ink = tokens.get("ink") or "#1E4D4F"
    ground = str(tokens.get("ground") or "").strip()
    return [
        {"id": "paper", "kind": "solid", "label": "Papel", "fill": paper},
        {"id": "wash", "kind": "wash", "label": "Lavagem", "fill": ink},
        {"id": "image", "kind": "image", "label": "Imagem", "fill": ground},
    ]


def apply_background(tokens, background_id, *, image_url=None):
    """Papel, lavagem da marca ou imagem. Overlay protege o texto."""
    tokens = dict(tokens or {})
    kind = str(background_id or "paper").strip().lower()
    if kind not in GROUND_KINDS:
        kind = "paper"
    image = str(image_url or tokens.get("ground") or "").strip()
    if kind == "image" and image:
        tokens["ground"] = image
        tokens["ground-fit"] = tokens.get("ground-fit") or "cover"
        tokens["overlay"] = tokens.get("overlay") or "color-mix(in srgb, var(--dsa-ink) 34%, transparent)"
    elif kind == "wash":
        tokens["ground"] = ""
        tokens["overlay"] = f"color-mix(in srgb, {tokens.get('ink') or '#1E4D4F'} 16%, transparent)"
    else:
        tokens["ground"] = ""
        tokens["overlay"] = "transparent"
    tokens["ground-kind"] = kind
    return tokens


def compile_rules(dna=None, archetype="brand"):
    dna = dna if isinstance(dna, dict) else {}
    arch = ARCHETYPES.get(str(archetype or "brand"), ARCHETYPES["brand"])
    must = list(dna.get("must") or ["logo reconhecível", "headline curta", "produto ou marca visível", "CTA com 4.5:1"])
    avoid = list(dna.get("avoid") or ["resize cego", "copy longa", "card SaaS", "pílula de site", "produto minúsculo"])
    return {
        "archetype": arch,
        "mandatory": ["logo", "headline"],
        "preferred": [arch["lead"], "cta"],
        "park_first": ["legal", "chip", "icon", "support"],
        "must": must[:8],
        "avoid": avoid[:8],
    }
