"""Resolver de assets: criativo → variante → marca → mock → demo → placeholder."""

from __future__ import annotations

from .creative_format_placeholder import render_placeholder
from .creative_format_registry import PUBLIC_LABELS, entry, public_label_for


SOURCE_ORDER = (
    "client_creative",
    "client_assets_recomposed",
    "generated_mock",
    "internal_demo",
    "smart_placeholder",
)


def resolve_assets(payload):
    payload = payload if isinstance(payload, dict) else {}
    format_key = payload.get("format_key") or payload.get("slug")
    item = entry(format_key)
    if not item:
        return {
            "status": "blocked",
            "code": "PLACEMENT_NOT_DEFINED",
            "format_key": str(format_key or ""),
            "source_type": "smart_placeholder",
            "public_label": public_label_for("smart_placeholder"),
            "placeholder": render_placeholder(format_key),
        }
    approved = payload.get("approved_creative")
    if _usable(approved, item):
        return _pack("client_creative", approved, item, payload)
    variant = payload.get("campaign_variant")
    if _usable(variant, item):
        return _pack("client_assets_recomposed", variant, item, payload)
    client_assets = payload.get("client_assets") if isinstance(payload.get("client_assets"), dict) else {}
    if client_assets.get("logo") or client_assets.get("product") or client_assets.get("image"):
        return _pack("client_assets_recomposed", client_assets, item, payload)
    mock = payload.get("generated_mock")
    if _usable(mock, item):
        return _pack("generated_mock", mock, item, payload)
    demo = payload.get("internal_demo")
    if _usable(demo, item):
        return _pack("internal_demo", demo, item, payload)
    brand_label = "LOGO DO CLIENTE" if client_assets.get("logo") else "MARCA DEMONSTRATIVA"
    placeholder = render_placeholder(item["format_key"], brand_label=brand_label)
    return {
        "status": "ok",
        "format_key": item["format_key"],
        "source_type": "smart_placeholder",
        "public_label": public_label_for("smart_placeholder"),
        "asset": None,
        "placeholder": placeholder,
        "synthetic": False,
    }


def _usable(asset, item):
    if not isinstance(asset, dict):
        return False
    if asset.get("url") or asset.get("html") or asset.get("asset_url"):
        width = int(asset.get("width") or 0)
        height = int(asset.get("height") or 0)
        if width and height and (width, height) != (item["width"], item["height"]):
            return False
        return True
    return False


def _pack(source_type, asset, item, payload):
    return {
        "status": "ok",
        "format_key": item["format_key"],
        "source_type": source_type,
        "public_label": PUBLIC_LABELS[source_type],
        "asset": asset,
        "placeholder": None,
        "synthetic": source_type == "generated_mock" or bool(payload.get("synthetic")),
        "brand_invented": False,
    }
