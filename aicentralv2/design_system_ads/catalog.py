"""Catálogo do Advertising OS: DNA, tokens, componentes, IAB, arquétipos, fluxo."""

from __future__ import annotations

from .adapt import compose_family_of, list_iab_formats
from .components import (
    ARCHETYPE_FORMAT,
    ARCHETYPES,
    DENSITY,
    TRACK_FOR_ARCHETYPE,
    component_of,
    density_for,
)
from .layouts import recipe_for
from .learn import curriculum, training_catalog
from .schema import parse_system

FLOW = (
    ("dna", "DNA"),
    ("tokens", "Tokens"),
    ("components", "Componentes"),
    ("adapter", "Adapter IAB"),
    ("templates", "Templates"),
    ("rules", "Regras da IA"),
)

TOKEN_ROLES = (
    ("colors", "Cores", ("paper", "ink", "accent", "highlight")),
    ("type", "Tipo", ("font-display", "weight-display", "tracking", "type-headline")),
    ("cta", "CTA", ("accent", "cta_ink", "cta-pad", "cta-radius")),
    ("legal", "Legal", ("muted", "type-legal")),
    ("density", "Densidade", ("safe", "type-support")),
)

TOKEN_NAMES = {
    "paper": "Papel",
    "ink": "Tinta",
    "accent": "CTA",
    "highlight": "Acento",
    "muted": "Apoio",
}

CATALOG_COMPONENTS = (
    ("logo", "Logo"),
    ("product", "Produto"),
    ("headline", "Headline"),
    ("support", "Apoio"),
    ("cta", "CTA"),
    ("legal", "Legal"),
    ("chip", "Selo"),
)

def catalog_for(system, *, client_id=None):
    parsed = parse_system(system)
    tokens = parsed.tokens or {}
    copy = parsed.ad_copy or {}
    dna = parsed.dna or {}
    slug = client_id or parsed.client_id or "centralcomm"
    loop = inspect_loop(parsed)
    return {
        "tagline": _tagline(parsed),
        "dna": {
            "name": dna.get("name") or parsed.name,
            "personality": list(dna.get("personality") or []),
            "must": list(dna.get("must") or []),
            "avoid": list(dna.get("avoid") or []),
            "logo_url": parsed.logo_url or tokens.get("logo") or "",
            "product_url": _track_url(parsed, "packshot"),
        },
        "token_roles": _token_roles(tokens, copy),
        "components": _components(parsed, copy, tokens),
        "iab_formats": _formats(),
        "archetypes": _archetypes(parsed, slug),
        "backgrounds": _backgrounds(parsed),
        "effects": {
            "wash-strength": tokens.get("wash-strength") or "16%",
            "grain": tokens.get("grain") or "0",
            "overlay": tokens.get("overlay") or "transparent",
            "hairline": tokens.get("hairline") or "",
            "cta-shadow": tokens.get("cta-shadow") or "none",
        },
        "creative_line": parsed.creative_line or "",
        "scope": parsed.scope,
        "rules": parsed.rules or {},
        "flow": [
            {
                "id": key,
                "label": label,
                "current": key == loop["step"],
                "done": _flow_done(key, loop),
            }
            for key, label in FLOW
        ],
        "loop": loop,
        "curriculum": curriculum(),
        "training": training_catalog(),
    }


def inspect_loop(system):
    parsed = parse_system(system)
    dna = parsed.dna or {}
    from .copy import is_stock_copy
    from .fidelity import missing_required_tracks, needs_fidelity_review
    from .materialize import GENERIC_TRAITS

    personality = [
        item
        for item in (dna.get("personality") or [])
        if str(item).strip() and str(item).strip().lower() not in GENERIC_TRAITS
    ]
    must = [item for item in (dna.get("must") or []) if str(item).strip()]
    missing = missing_required_tracks(parsed)
    contrast_ok = bool((parsed.contrast or {}).get("passed"))
    if not personality or not must or is_stock_copy(parsed.ad_copy):
        action, step = "compose", "dna"
    elif not contrast_ok:
        action, step = "contrast", "tokens"
    elif needs_fidelity_review(parsed):
        action, step = "review", "tokens"
    elif missing:
        action, step = "track", "components"
    elif not (parsed.rules or {}).get("must"):
        action, step = "rules", "rules"
    else:
        action, step = "ready", "templates"
    return {
        "step": step,
        "action": action,
        "track_id": missing[0] if action == "track" else "",
        "missing_tracks": missing,
        "ready": action == "ready",
        "label": _loop_label(action, missing[0] if missing else ""),
    }


def _loop_label(action, track_id):
    return {
        "compose": "Montar o DNA e a copy.",
        "contrast": "Fechar o contraste a 4.5:1.",
        "review": "Revisar fidelidade da tinta e da copy.",
        "track": f"Gerar a trilha {track_id}." if track_id else "Gerar as trilhas.",
        "rules": "Assentar as regras da IA.",
        "ready": "Sistema pronto para a peça.",
    }.get(action, "Seguir o loop.")


def _flow_done(key, loop):
    order = [item[0] for item in FLOW]
    current = order.index(loop["step"]) if loop["step"] in order else 0
    return order.index(key) < current or loop.get("ready")


def _tagline(parsed):
    if parsed.scope == "campaign" and parsed.creative_line:
        return parsed.creative_line
    dna = parsed.dna or {}
    traits = ", ".join((dna.get("personality") or [])[:3])
    if traits:
        return f"{dna.get('name') or parsed.name}. {traits}."
    return f"{parsed.name}."


def _backgrounds(parsed):
    tokens = parsed.tokens or {}
    active = tokens.get("ground-kind") or "paper"
    rows = []
    for item in parsed.backgrounds or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") or item.get("id") or "paper"
        rows.append(
            {
                **item,
                "active": kind == active or item.get("id") == active,
                "preview": item.get("fill") or tokens.get("paper") or "#FFFFFF",
                "image": tokens.get("ground") if kind == "image" else "",
            }
        )
    return rows


def _token_roles(tokens, copy):
    rows = []
    for key, label, ids in TOKEN_ROLES:
        rows.append(
            {
                "id": key,
                "label": label,
                "items": [
                    {
                        "id": token_id,
                        "label": TOKEN_NAMES.get(token_id, token_id),
                        "value": tokens.get(token_id, ""),
                    }
                    for token_id in ids
                ],
                "preview": {
                    "headline": copy.get("headline") or "",
                    "cta": copy.get("cta") or "",
                    "legal": copy.get("legal") or "",
                    "font": tokens.get("font-display") or "Inter",
                    "weight": tokens.get("weight-display") or "700",
                    "tracking": tokens.get("tracking") or "0",
                    "paper": tokens.get("paper") or "#FFFFFF",
                    "ink": tokens.get("ink") or "#1E4D4F",
                    "accent": tokens.get("accent") or "#1E4D4F",
                    "cta_ink": tokens.get("cta_ink") or "#FFFFFF",
                },
            }
        )
    return rows


def _components(parsed, copy, tokens):
    rows = []
    for key, label in CATALOG_COMPONENTS:
        spec = component_of(key)
        parked = []
        for density, data in DENSITY.items():
            if int(spec.get("priority") or 3) >= int(data["park_from"]) and key not in {
                "logo",
                "headline",
                "product",
                "cta",
            }:
                parked.append(density)
        text = {
            "headline": copy.get("headline") or "",
            "support": copy.get("support") or "",
            "cta": copy.get("cta") or "",
            "legal": copy.get("legal") or "",
        }.get(key, "")
        image = ""
        if key == "logo":
            image = parsed.logo_url or tokens.get("logo") or ""
        elif key == "product":
            image = _track_url(parsed, "packshot")
        rows.append(
            {
                "id": key,
                "label": label,
                "priority": spec.get("priority", 3),
                "text": text,
                "image": image,
                "parked_in": parked,
            }
        )
    return rows


def _formats():
    rows = []
    for item in list_iab_formats():
        density = density_for(item.get("key"))
        recipe = recipe_for(item.get("key"), compose_family_of(item))
        parked = set(recipe.get("park") or ())
        visible = [
            role
            for role in ("logo", "headline", "product", "cta", "support", "legal")
            if role not in parked
        ]
        rows.append(
            {
                **item,
                "density": density,
                "ready": True,
                "visible": visible,
            }
        )
    return rows


def _archetypes(parsed, slug):
    rows = []
    for key, spec in ARCHETYPES.items():
        fmt = ARCHETYPE_FORMAT.get(key) or "iab-billboard"
        rows.append(
            {
                "id": key,
                "label": spec["label"],
                "ground": spec["ground"],
                "lead": spec["lead"],
                "format": fmt,
                "active": parsed.archetype == key,
                "headline": (parsed.ad_copy or {}).get("headline") or "",
                "cta": (parsed.ad_copy or {}).get("cta") or "",
                "image": _track_url(parsed, TRACK_FOR_ARCHETYPE.get(key) or "kv"),
                "specimen_url": f"/lab/design-system/marca/{slug}?format={fmt}&layers=6",
            }
        )
    return rows


def _track_url(parsed, track_id):
    for item in parsed.tracks or []:
        if isinstance(item, dict) and item.get("id") == track_id:
            return item.get("url") or ""
    return ""
