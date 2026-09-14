"""Score em oito eixos. Defeito estrutural barra publicação."""

from ..creative_format_registry import entry


def run(payload):
    payload = payload if isinstance(payload, dict) else {}
    item = entry((payload.get("catalog") or {}).get("format_key") or payload.get("format_key"))
    placement = payload.get("placement") or {}
    anatomy = payload.get("anatomy") or {}
    assets = payload.get("assets") or {}
    blocking = []
    if placement.get("status") == "blocked":
        blocking.append(placement.get("message") or "Placement inválido.")
    if anatomy.get("missing_required") and payload.get("has_piece"):
        blocking.append("Faltam elementos obrigatórios da densidade.")
    if item and item["format_key"] in {"reels-9x16", "shorts-9x16"} and payload.get("static_only"):
        blocking.append("Estático em superfície audiovisual.")
    scores = {
        "format": 9 if item else 0,
        "anatomy": 8 if not anatomy.get("missing_required") else 4,
        "channel": 10 if placement.get("status") == "ok" else 2,
        "placement": 10 if placement.get("status") == "ok" else 0,
        "legibility": 8,
        "brand_consistency": 7 if assets.get("source_type") != "smart_placeholder" else 5,
        "context": 9,
        "technical": 10 if not blocking else 3,
    }
    return {
        "status": "blocked" if blocking else "ok",
        "scores": scores,
        "blocking_defects": blocking,
        "public_enabled": not blocking,
        "recommendations": _tips(item, anatomy),
    }


def _tips(item, anatomy):
    tips = []
    if item and item["density"] == "compact":
        tips.append("Reduzir a headline para duas linhas.")
    if "cta" in (anatomy.get("optional_missing") or []):
        tips.append("Aumentar o contraste do CTA.")
    if "logo" in (item or {}).get("required_elements", []):
        tips.append("Preservar mais respiro ao redor do logo.")
    return tips
