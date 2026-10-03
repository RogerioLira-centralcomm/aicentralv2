"""Model manifests (ours, one JSON per model) merged with the OpenRouter catalog (theirs, fetched at runtime).

Capabilities are never hardcoded: limits such as the reference count, ratios and quality values come
from GET /api/v1/images/models and /endpoints, cached on disk for CATALOG_TTL seconds. A model whose
catalog entry disappears is shown as ``unavailable`` instead of breaking the page.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests
from flask import current_app, has_app_context

log = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).with_name("models")
CATALOG_URL = "https://openrouter.ai/api/v1/images/models"
ENDPOINTS_URL = "https://openrouter.ai/api/v1/images/models/{id}/endpoints"
CATALOG_TTL = 12 * 3600


def manifests() -> dict[str, dict]:
    items = {}
    for path in sorted(MODELS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items[data["model_key"]] = data
    return items


def manifest(model_key: str) -> dict:
    items = manifests()
    if model_key not in items:
        raise KeyError(f"Modelo desconhecido: {model_key}")
    return items[model_key]


def _cache_path() -> Path:
    root = Path(current_app.instance_path) if has_app_context() else Path.cwd() / "instance"
    path = root / "creative_lab"
    path.mkdir(parents=True, exist_ok=True)
    return path / "openrouter_catalog.json"


def _fetch(catalog_ids) -> dict:
    response = requests.get(CATALOG_URL, timeout=20)
    response.raise_for_status()
    models = {item["id"]: item for item in response.json().get("data", []) if isinstance(item, dict) and item.get("id")}
    endpoints = {}
    for catalog_id in sorted(set(catalog_ids)):
        if catalog_id not in models:
            continue
        try:
            detail = requests.get(ENDPOINTS_URL.format(id=catalog_id), timeout=20)
            detail.raise_for_status()
            endpoints[catalog_id] = detail.json().get("endpoints") or []
        except requests.RequestException:
            log.warning("OpenRouter endpoints unavailable for %s", catalog_id)
    return {"fetched_at": int(time.time()), "models": models, "endpoints": endpoints}


def catalog(*, refresh: bool = False) -> dict:
    path = _cache_path()
    cached = None
    if path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            cached = None
    if cached and not refresh and time.time() - cached.get("fetched_at", 0) < CATALOG_TTL:
        return cached
    try:
        fresh = _fetch(item["catalog_id"] for item in manifests().values())
        path.write_text(json.dumps(fresh), encoding="utf-8")
        return fresh
    except (requests.RequestException, ValueError):
        log.warning("OpenRouter image catalog unavailable; using the cached copy", exc_info=True)
        return cached or {"fetched_at": 0, "models": {}, "endpoints": {}}


def _pricing(endpoints) -> list[dict]:
    for endpoint in endpoints or []:
        if endpoint.get("pricing"):
            return endpoint["pricing"]
    return []


def capabilities(model_key: str, data: dict | None = None) -> dict:
    """What the catalog says this model accepts, normalized for the adapter."""
    item = manifest(model_key)
    data = data or catalog()
    entry = data.get("models", {}).get(item["catalog_id"])
    if not entry:
        return {"available": False, "reason": "Modelo não está no catálogo do OpenRouter."}
    params = entry.get("supported_parameters") or {}
    endpoints = data.get("endpoints", {}).get(item["catalog_id"]) or []
    refs = params.get("input_references") or {}
    return {
        "available": True,
        "name": entry.get("name") or item["label"],
        "description": entry.get("description") or "",
        "max_references": int(refs.get("max", 0) or 0),
        "aspect_ratios": list((params.get("aspect_ratio") or {}).get("values") or []),
        "resolutions": list((params.get("resolution") or {}).get("values") or []),
        "qualities": list((params.get("quality") or {}).get("values") or []),
        "backgrounds": list((params.get("background") or {}).get("values") or []),
        "supports_seed": bool(params.get("seed")),
        "parameters": sorted(params),
        "passthrough": sorted({key for endpoint in endpoints for key in endpoint.get("allowed_passthrough_parameters") or []}),
        "providers": [endpoint.get("provider_slug") for endpoint in endpoints],
        "pricing": _pricing(endpoints),
        "fetched_at": data.get("fetched_at"),
    }


def models_view() -> list[dict]:
    data = catalog()
    view = []
    for key, item in manifests().items():
        caps = capabilities(key, data)
        view.append({
            "model_key": key, "label": item["label"], "group": item["group"], "provider": item["provider"],
            "provider_model_id": item["provider_model_id"], "adapter": item["adapter"],
            "profile_version": item["profile_version"], "notes": item.get("notes", []),
            "quality_map": item["quality_map"], "reference_policy": item["reference_policy"],
            "prompt_profile": item["prompt_profile"], "capabilities": caps,
            "status": "available" if caps.get("available") else "unavailable",
        })
    order = {"production": 0, "specialist": 1, "draft": 2}
    return sorted(view, key=lambda row: (order.get(row["group"], 9), row["label"]))
