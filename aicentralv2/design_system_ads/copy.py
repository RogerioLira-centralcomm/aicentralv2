"""Linha de anúncio da marca — nunca copy sobre o laboratório."""

from __future__ import annotations

import re

COPY_KEYS = ("headline", "support", "cta", "legal")
META_COPY = re.compile(
    r"design system|tinta certa|herda o tema|tailwind|ver o sistema",
    re.I,
)
STOCK_COPY = re.compile(
    r"no primeiro olhar|o que .+ promete, no tamanho do anúncio|saiba mais",
    re.I,
)


def is_centralcomm_name(name):
    return str(name or "").strip().lower() in {
        "centralcomm",
        "central comm",
        "centralcomm ads",
        "central comm ads",
    }


def is_meta_copy(copy):
    blob = " ".join(str((copy or {}).get(key) or "") for key in COPY_KEYS)
    return bool(META_COPY.search(blob))


def is_stock_copy(copy):
    if is_centralcomm_name((copy or {}).get("legal")):
        return False
    blob = " ".join(str((copy or {}).get(key) or "") for key in COPY_KEYS)
    return bool(STOCK_COPY.search(blob) or META_COPY.search(blob))


def dna_is_generic(dna):
    from .materialize import GENERIC_TRAITS

    payload = dna if isinstance(dna, dict) else {}
    personality = [
        item
        for item in (payload.get("personality") or [])
        if str(item).strip() and str(item).strip().lower() not in GENERIC_TRAITS
    ]
    must = [item for item in (payload.get("must") or []) if str(item).strip()]
    return not personality or not must


def brand_ad_copy(name="", *, centralcomm=False):
    short = str(name or "").replace(" Ads", "").strip() or "A marca"
    if META_COPY.search(short):
        short = "A marca"
    if centralcomm or is_centralcomm_name(short) or is_centralcomm_name(name):
        return {
            "headline": "A campanha chega inteira",
            "support": "Do cliente à tela, sem perder cor nem prazo.",
            "cta": "Começar agora",
            "legal": "CentralComm",
        }
    return {
        "headline": short,
        "support": "",
        "cta": "Ver mais",
        "legal": short,
    }


COPY_LIMITS = {
    "compact": {"headline": 32, "support": 0, "cta": 14, "legal": 22},
    "standard": {"headline": 42, "support": 56, "cta": 16, "legal": 36},
    "rich": {"headline": 56, "support": 80, "cta": 18, "legal": 48},
}


def is_house_copy_system(system):
    source = getattr(system, "source", "") if not isinstance(system, dict) else system.get("source") or ""
    name = getattr(system, "name", "") if not isinstance(system, dict) else system.get("name") or ""
    dna = getattr(system, "dna", None) if not isinstance(system, dict) else system.get("dna")
    dna_name = (dna or {}).get("name") if isinstance(dna, dict) else ""
    return str(source or "") == "tailwind-centralcomm" or is_centralcomm_name(name) or is_centralcomm_name(dna_name)


def has_product(system):
    tracks = getattr(system, "tracks", None) if not isinstance(system, dict) else system.get("tracks")
    for item in tracks or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "") == "packshot" and str(item.get("url") or "").strip():
            return True
    evidence = getattr(system, "evidence", None) if not isinstance(system, dict) else system.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    for asset in evidence.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        role = str(asset.get("role") or "").strip().lower()
        url = str(asset.get("url") or asset.get("asset_url") or "").strip()
        if url and role in {"product", "packshot", "pack", "produto", "sku"}:
            return True
    return False


def compute_needs_input(system):
    """O que falta para o loop seguir. Casa/CentralComm não pede."""
    if is_house_copy_system(system):
        return []
    missing = []
    dna = getattr(system, "dna", None) if not isinstance(system, dict) else system.get("dna")
    if dna_is_generic(dna):
        missing.append("dna")
    if not has_product(system):
        missing.append("produto")
    copy = getattr(system, "ad_copy", None) if not isinstance(system, dict) else system.get("ad_copy")
    copy = copy if isinstance(copy, dict) else {}
    from .runtime_policy import legal_is_required

    if legal_is_required(system) and not str(copy.get("legal") or "").strip():
        missing.append("legal")
    return missing


def needs_input_label(items):
    labels = {"dna": "DNA", "produto": "produto", "legal": "legal"}
    names = [labels.get(str(item), str(item)) for item in (items or []) if item]
    if not names:
        return "Falta dado da marca."
    if len(names) == 1:
        return f"Falta {names[0]}."
    return f"Falta {', '.join(names[:-1])} e {names[-1]}."


def prune_format_copy(default, variants):
    """Só o que muda em relação ao default da marca."""
    base = clean_ad_copy(default)
    pruned = {}
    incoming = variants if isinstance(variants, dict) else {}
    for format_key, payload in incoming.items():
        key = str(format_key or "").strip()
        if not key or not isinstance(payload, dict):
            continue
        diff = {}
        for field in COPY_KEYS:
            value = str(payload.get(field) or "").strip()
            if value and value != str(base.get(field) or ""):
                diff[field] = value[:180]
        if diff:
            pruned[key] = diff
    return pruned


def merge_format_copy(current, incoming, default):
    merged = dict(current) if isinstance(current, dict) else {}
    extra = incoming if isinstance(incoming, dict) else {}
    for key, payload in extra.items():
        if not isinstance(payload, dict):
            continue
        slot = dict(merged.get(str(key)) or {})
        for field in COPY_KEYS:
            if payload.get(field) in (None, ""):
                continue
            slot[field] = str(payload.get(field) or "").strip()[:180]
        merged[str(key)] = slot
    return prune_format_copy(default, merged)


def resolve_ad_copy(system, format_key, density="rich"):
    """Default da marca + override do formato, depois o corte da densidade."""
    if isinstance(system, dict):
        name = system.get("name") or ""
        base = dict(system.get("ad_copy") or {})
        variants = system.get("ad_copy_by_format") or {}
    else:
        name = getattr(system, "name", "") or ""
        base = dict(getattr(system, "ad_copy", None) or {})
        variants = getattr(system, "ad_copy_by_format", None) or {}
    override = variants.get(str(format_key or "")) if isinstance(variants, dict) else None
    if isinstance(override, dict):
        for key in COPY_KEYS:
            if str(override.get(key) or "").strip():
                base[key] = override[key]
    return fit_ad_copy(base, density, name)


def fit_ad_copy(copy, density="rich", name=""):
    """Corta a linha no tamanho do IAB. Compacto não leva apoio."""
    cleaned = clean_ad_copy(copy, name)
    limits = COPY_LIMITS.get(str(density or "rich"), COPY_LIMITS["rich"])
    fitted = {}
    for key in COPY_KEYS:
        limit = int(limits.get(key) or 0)
        if limit <= 0:
            fitted[key] = ""
            continue
        fitted[key] = str(cleaned.get(key) or "")[:limit]
    return fitted


def clean_ad_copy(copy, name="", *, centralcomm=False):
    fallback = brand_ad_copy(name, centralcomm=centralcomm)
    if not isinstance(copy, dict) or is_meta_copy(copy):
        return dict(fallback)
    cleaned = dict(fallback)
    for key in COPY_KEYS:
        value = str(copy.get(key) or "").strip()
        if value and not META_COPY.search(value) and not STOCK_COPY.search(value):
            cleaned[key] = value[:180]
    return cleaned
