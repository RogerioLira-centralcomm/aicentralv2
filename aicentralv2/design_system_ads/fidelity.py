"""Dossiê de fidelidade: evidência da marca trava a tinta e preenche as trilhas."""

from __future__ import annotations

from .copy import is_stock_copy
from .schema import dump_system, parse_system, relative_luminance
from .tracks import merge_tracks

ASSET_TO_TRACK = (
    ("packshot", ("product", "packshot", "pack", "produto", "sku")),
    ("lifestyle", ("lifestyle", "scene", "cena", "ambiente")),
    ("kv", ("kv", "key", "hero", "ground", "fundo", "banner")),
    ("wash", ("wash", "tinta", "campo")),
)
REQUIRED_TRACKS = ("packshot", "kv", "lifestyle")
OPTIONAL_TRACKS = ("wash",)


def compile_fidelity(system, client=None):
    parsed = parse_system(system)
    client = client if isinstance(client, dict) else {}
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    evidence = dict(parsed.evidence or {})
    tokens = parsed.tokens or {}
    assets = _asset_rows(client, evidence)
    locked = {
        "paper": tokens.get("paper"),
        "ink": tokens.get("ink"),
        "accent": tokens.get("accent"),
        "highlight": tokens.get("highlight"),
    }
    return {
        "name": (parsed.dna or {}).get("name") or parsed.name or client.get("name"),
        "locked_tokens": locked,
        "source": parsed.source,
        "extract_url": evidence.get("url") or client.get("website_url") or "",
        "sector": client.get("sector") or evidence.get("sector") or "",
        "tone": client.get("tone_of_voice") or evidence.get("tone") or "",
        "summary": str(profile.get("brand_summary") or evidence.get("summary") or "")[:400],
        "products": list(profile.get("products_services") or evidence.get("products") or [])[:6],
        "forbidden": list(profile.get("forbidden_elements") or [])[:6],
        "must": list(profile.get("mandatory_elements") or (parsed.dna or {}).get("must") or [])[:6],
        "logo_url": parsed.logo_url or tokens.get("logo") or "",
        "assets": assets,
        "stock_copy": is_stock_copy(parsed.ad_copy),
        "reviewed": bool(evidence.get("reviewed")),
        "palette": list(evidence.get("palette") or [])[:8],
        "voice": evidence.get("voice") if isinstance(evidence.get("voice"), dict) else {},
    }


def attach_client_evidence(system, client=None):
    parsed = parse_system(system)
    client = client if isinstance(client, dict) else {}
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    provenance = evidence.get("provenance")
    if client.get("sector"):
        evidence["sector"] = client.get("sector")
    if client.get("tone_of_voice"):
        evidence["tone"] = client.get("tone_of_voice")
    if profile.get("brand_summary"):
        evidence["summary"] = str(profile.get("brand_summary"))[:400]
    if profile.get("products_services"):
        evidence["products"] = list(profile.get("products_services"))[:6]
    assets = _asset_rows(client, evidence)
    if assets:
        evidence["assets"] = assets
    if parsed.source == "tailwind-centralcomm":
        evidence["reviewed"] = True
    if isinstance(provenance, dict):
        evidence["provenance"] = provenance
    data["evidence"] = evidence
    data["tracks"] = bind_evidence_tracks(data.get("tracks"), assets)
    return parse_system(data)


def bind_evidence_tracks(tracks, assets):
    incoming = []
    used = set()
    for track_id, words in ASSET_TO_TRACK:
        url = _first_asset(assets, words, used)
        if url:
            incoming.append({"id": track_id, "url": url})
            used.add(url)
    leftovers = [item.get("url") for item in (assets or []) if item.get("url") and item.get("url") not in used]
    claimed = {item["id"] for item in incoming}
    for track_id, url in zip(REQUIRED_TRACKS, leftovers):
        if track_id in claimed:
            continue
        incoming.append({"id": track_id, "url": url})
        claimed.add(track_id)
    return merge_tracks(tracks, incoming)


def track_reference_urls(system, track_id, client=None):
    """Até duas imagens reais: produto/cena da marca e o logo. Lavagem não usa foto."""
    if str(track_id or "") == "wash":
        return []
    parsed = parse_system(system)
    client = client if isinstance(client, dict) else {}
    assets = _asset_rows(client, parsed.evidence or {})
    tracks = {
        item.get("id"): item.get("url")
        for item in (parsed.tracks or [])
        if isinstance(item, dict) and item.get("id")
    }
    logo = (
        parsed.logo_url
        or (parsed.tokens or {}).get("logo")
        or client.get("logo_upload_path")
        or client.get("logo_url")
        or ""
    )
    product = tracks.get("packshot") or _first_asset(
        assets, ("product", "packshot", "pack", "produto", "sku"), set()
    )
    scene = tracks.get("lifestyle") or _first_asset(
        assets, ("lifestyle", "scene", "cena", "ambiente"), set()
    )
    kv = tracks.get("kv") or _first_asset(
        assets, ("kv", "key", "hero", "ground", "fundo", "banner"), set()
    )
    if track_id == "packshot":
        ordered = [product, logo]
    elif track_id == "lifestyle":
        ordered = [scene or product, logo]
    else:
        ordered = [kv or product, logo]
    seen = set()
    urls = []
    for url in ordered:
        text = str(url or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        urls.append(text)
        if len(urls) >= 2:
            break
    return urls


def missing_required_tracks(system):
    parsed = parse_system(system)
    return [
        item["id"]
        for item in (parsed.tracks or [])
        if isinstance(item, dict)
        and item.get("id") in REQUIRED_TRACKS
        and not item.get("url")
    ]


def mark_reviewed(system, score=0.0, notes=None, kind="local"):
    from .provenance import set_review

    parsed = parse_system(system)
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    review_kind = str(kind or "local").strip().lower()
    if review_kind not in {"local", "model"}:
        review_kind = "local"
    evidence["reviewed"] = True
    evidence["fidelity"] = {
        "score": float(score or 0),
        "notes": [str(item)[:200] for item in (notes or [])][:6],
        "kind": review_kind,
    }
    data["evidence"] = evidence
    return set_review(parse_system(data), review_kind, score=score, notes=notes)


def needs_fidelity_review(system):
    parsed = parse_system(system)
    if parsed.source == "tailwind-centralcomm":
        return False
    evidence = parsed.evidence if isinstance(parsed.evidence, dict) else {}
    if evidence.get("reviewed"):
        return False
    from .provenance import get_provenance

    kind = (get_provenance(parsed).get("review") or {}).get("kind")
    return kind not in {"local", "model"}


def lock_token_patches(system, patches):
    """Descarta patch que troca a tinta extraída por outra família de cor."""
    parsed = parse_system(system)
    locked = {
        key: str((parsed.tokens or {}).get(key) or "").upper()
        for key in ("paper", "ink", "accent", "highlight")
    }
    kept = []
    for item in patches or []:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("id") or "").strip()
        css = str(item.get("css") or item.get("value") or "").strip()
        current = locked.get(token_id)
        if current and css.upper().startswith("#") and current.startswith("#"):
            if not _same_family(current, css):
                continue
        kept.append(item)
    return kept


def _same_family(first, second):
    def channels(hex_color):
        raw = hex_color.lstrip("#")
        if len(raw) != 6:
            return (0, 0, 0)
        return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))

    left = channels(first)
    right = channels(second)
    if max(abs(a - b) for a, b in zip(left, right)) <= 56:
        return True
    if relative_luminance(first) > 0.72 and relative_luminance(second) > 0.72:
        return True
    hue_left = _hue(left)
    hue_right = _hue(right)
    if hue_left is None or hue_right is None:
        return True
    delta = abs(hue_left - hue_right)
    return min(delta, 360 - delta) <= 35


def _hue(channels):
    red, green, blue = [value / 255 for value in channels]
    high, low = max(red, green, blue), min(red, green, blue)
    delta = high - low
    if delta < 0.04:
        return None
    if high == red:
        hue = ((green - blue) / delta) % 6
    elif high == green:
        hue = (blue - red) / delta + 2
    else:
        hue = (red - green) / delta + 4
    return hue * 60


def _asset_rows(client, evidence):
    rows = []
    seen = set()
    incoming = list(client.get("brand_assets") or [])
    incoming.extend(evidence.get("assets") or [])
    for item in incoming:
        if isinstance(item, str):
            item = {"asset_url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("asset_url") or item.get("url") or item.get("stored_url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "url": url[:500],
                "role": str(item.get("role") or item.get("kind") or item.get("slot") or "").lower(),
                "label": str(item.get("label") or item.get("name") or ""),
            }
        )
    return rows[:8]


def _first_asset(assets, words, used):
    for item in assets or []:
        url = item.get("url")
        if not url or url in used:
            continue
        blob = f"{item.get('role')} {item.get('label')} {url}".lower()
        if any(word in blob for word in words):
            return url
    return ""
