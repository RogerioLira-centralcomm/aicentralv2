"""Trilhas visuais do Advertising OS: produto, KV, lifestyle, campo de tinta."""

from __future__ import annotations

TRACKS = (
    {
        "id": "packshot",
        "label": "Produto",
        "aspect": "1:1",
        "role": "product",
        "hint": "Packshot recortável, fundo limpo, produto reconhecível.",
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
        "hint": "Cena humana na tinta da marca, sem chrome de site.",
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
    tokens = getattr(system, "tokens", None) or (system or {}).get("tokens") or {}
    dna = getattr(system, "dna", None) or (system or {}).get("dna") or {}
    copy = getattr(system, "ad_copy", None) or (system or {}).get("ad_copy") or {}
    name = dna.get("name") or getattr(system, "name", None) or "a marca"
    ink = tokens.get("ink") or "#1E4D4F"
    paper = tokens.get("paper") or "#FFFFFF"
    highlight = tokens.get("highlight") or "#F3B71B"
    personality = ", ".join(dna.get("personality") or ["reconhecível"])
    must = "; ".join(dna.get("must") or ["logo e produto reconhecíveis"])
    avoid = "; ".join(dna.get("avoid") or ["card SaaS", "resize", "copy longa"])
    stored = ""
    for item in getattr(system, "tracks", None) or (system or {}).get("tracks") or []:
        if isinstance(item, dict) and item.get("id") == track_id and item.get("prompt"):
            stored = str(item["prompt"]).strip()
            break
    brief = stored or spec["hint"]
    extra = str(extra or "").strip()
    return (
        f"Advertising still for {name}. {brief} "
        f"Brand ink {ink}, paper {paper}, highlight {highlight}. "
        f"Personality: {personality}. Must: {must}. Avoid: {avoid}. "
        f"Headline space for: {copy.get('headline') or 'short line'}. "
        f"No website UI, no app chrome, no cream terracotta SaaS kit, no watermarks. "
        f"{extra}"
    ).strip()
