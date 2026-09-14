"""Agente de viewer — escolhe o shell, não redesenha a peça."""

from ..creative_format_registry import DISCLAIMER, entry


VIEWER_BY_KIND = {
    "video": "ctv",
    "social": "social_feed",
    "banner": "portal",
    "native": "portal",
    "interactive": "portal",
}


def run(payload):
    payload = payload if isinstance(payload, dict) else {}
    item = entry((payload.get("catalog") or {}).get("format_key") or payload.get("format_key"))
    if not item:
        return {"status": "blocked", "code": "PLACEMENT_NOT_DEFINED"}
    requested = payload.get("viewer_slug")
    kind = item["kind"]
    viewer_type = (item["viewer_types"] or [VIEWER_BY_KIND.get(kind, "isolated")])[0]
    if kind == "social" and item["format_key"] == "linkedin-landscape":
        viewer_type = "linkedin"
    if item["format_key"] in {"story-9x16", "reels-9x16", "shorts-9x16"}:
        viewer_type = "social_vertical"
    if item["format_key"] == "youtube-infeed":
        viewer_type = "youtube_infeed"
    return {
        "status": "ok",
        "viewer_type": viewer_type,
        "viewer_slug": requested or _default_slug(viewer_type),
        "inject": "well" if viewer_type != "portal" else "zone",
        "disclaimer": DISCLAIMER,
        "isolate_html": True,
    }


def _default_slug(viewer_type):
    return {
        "portal": "g1",
        "ctv": "netflix",
        "social_feed": "instagram",
        "social_vertical": "instagram",
        "linkedin": "linkedin",
        "youtube_infeed": "youtube",
    }.get(viewer_type, "g1")
