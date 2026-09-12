"""Trilhas visuais do Advertising OS: produto, KV, lifestyle, campo de tinta."""

from __future__ import annotations

TRACKS = (
    {
        "id": "packshot",
        "label": "Produto",
        "aspect": "1:1",
        "role": "product",
        "hint": "Packshot recortável, fundo limpo, produto da marca.",
    },
    {
        "id": "kv",
        "label": "KV digital",
        "aspect": "16:9",
        "role": "ground",
        "hint": "Master 16:9 com espaço para headline e CTA.",
    },
    {
        "id": "lifestyle",
        "label": "Lifestyle",
        "aspect": "16:9",
        "role": "visual",
        "hint": "Cena humana no mundo desta marca, sem chrome de site.",
    },
    {
        "id": "wash",
        "label": "Campo de tinta",
        "aspect": "16:9",
        "role": "ground",
        "hint": "Campo da cor da marca, sem foto, para lavagem IAB.",
    },
)


def default_tracks():
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "aspect": item["aspect"],
            "role": item["role"],
            "hint": item["hint"],
            "url": "",
            "prompt": "",
        }
        for item in TRACKS
    ]


def merge_tracks(existing, incoming=None):
    by_id = {item["id"]: dict(item) for item in default_tracks()}
    for item in existing or []:
        if isinstance(item, dict) and item.get("id") in by_id:
            by_id[item["id"]].update({key: item[key] for key in item if key in by_id[item["id"]] or key in {"url", "prompt"}})
    for item in incoming or []:
        if not isinstance(item, dict) or item.get("id") not in by_id:
            continue
        current = by_id[item["id"]]
        if item.get("prompt"):
            current["prompt"] = str(item["prompt"]).strip()[:600]
        if item.get("url"):
            current["url"] = str(item["url"]).strip()[:500]
    return [by_id[item["id"]] for item in TRACKS]


def track_spec(track_id):
    for item in TRACKS:
        if item["id"] == track_id:
            return dict(item)
    raise ValueError("Trilha inválida. Use produto, KV, lifestyle ou campo.")


def prompt_for_track(system, track_id, extra=""):
    spec = track_spec(track_id)
    payload = system if isinstance(system, dict) else {}
    tokens = getattr(system, "tokens", None) or payload.get("tokens") or {}
    dna = getattr(system, "dna", None) or payload.get("dna") or {}
    copy = getattr(system, "ad_copy", None) or payload.get("ad_copy") or {}
    evidence = getattr(system, "evidence", None)
    if not isinstance(evidence, dict):
        evidence = payload.get("evidence") or {}
    tracks = getattr(system, "tracks", None)
    if tracks is None:
        tracks = payload.get("tracks") or []
    name = dna.get("name") or getattr(system, "name", None) or "the brand"
    ink = tokens.get("ink") or "#111111"
    paper = tokens.get("paper") or "#FFFFFF"
    highlight = tokens.get("highlight") or ink
    products = [str(item).strip() for item in (evidence.get("products") or []) if str(item).strip()]
    product = products[0] if products else name
    sector = str(evidence.get("sector") or "").strip()
    tone = str(evidence.get("tone") or "").strip()
    personality = ", ".join(
        item for item in (dna.get("personality") or []) if str(item).strip()
    ) or f"{name}, {sector}".strip(", ")
    must = "; ".join(dna.get("must") or ["logo and product of this brand"])
    avoid = "; ".join(
        dna.get("avoid")
        or ["SaaS cards", "resize", "stock handshake", "cream terracotta", "acid green"]
    )
    stored = ""
    for item in tracks or []:
        if isinstance(item, dict) and item.get("id") == track_id and item.get("prompt"):
            stored = str(item["prompt"]).strip()
            break
    brief = stored or spec["hint"]
    extra = str(extra or "").strip()
    world = f"{name} in {sector}" if sector else name
    if track_id == "packshot":
        direction = (
            f"Studio packshot of the real {product} from {name}, clipped on {paper}, "
            f"brand ink {ink} in the label or shadow, hard but soft-edged key light, "
            f"recognizable silhouette of THIS product, 28 percent of frame, "
            f"room on the right for type. Not a generic bottle."
        )
    elif track_id == "kv":
        direction = (
            f"16:9 master key visual for {world}. Negative space for a 2-line headline and CTA. "
            f"Brand ink {ink} as the signal, paper {paper} as the field, highlight {highlight} only once. "
            f"{tone + ' tone. ' if tone else ''}Art directed, not a website hero."
        )
    elif track_id == "lifestyle":
        direction = (
            f"Lived scene of someone using {product} in the world of {world}, "
            f"ink {ink} in wardrobe or light, {tone or 'brand'} atmosphere, "
            f"no stock handshake, no office glass, no navbar."
        )
    else:
        direction = (
            f"Abstract wash of {name} ink {ink} on {paper}, pigment and paper grain, "
            f"no photography, no logo, no UI. This is the brand's stain, not a gradient."
        )
    return (
        f"{direction} {brief} Personality: {personality}. Must: {must}. Avoid: {avoid}. "
        f"Headline space for: {copy.get('headline') or name}. "
        f"No website UI, no app chrome, no cream terracotta SaaS kit, no watermarks, "
        f"no generic stock. {extra}"
    ).strip()
