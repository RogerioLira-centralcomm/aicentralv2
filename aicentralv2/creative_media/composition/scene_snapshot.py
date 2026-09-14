"""Cópia imutável da cena Camadas. O job nunca lê a cena live."""

from __future__ import annotations

import hashlib
import json

from ...camadas.schemas import TEXT_ROLES

PROTECT_ROLES = set(TEXT_ROLES) | {
    "logo",
    "badge",
    "logo_text",
    "qr",
    "code",
    "barcode",
}
ANIMATE_ROLES = {
    "background",
    "person",
    "product",
    "graphic",
    "illustration",
    "decoration",
    "foreground",
    "shadow",
}
INTENTS = ("protect", "animate", "hide")


def default_intent(element):
    item = element if isinstance(element, dict) else {}
    role = str(item.get("role") or "")
    layer_type = str(item.get("type") or item.get("layer_type") or "")
    label = str(item.get("label") or "").lower()
    if role in PROTECT_ROLES or layer_type == "text":
        return "protect"
    if "qr" in label or "código" in label or "codigo" in label:
        return "protect"
    if role in ANIMATE_ROLES:
        return "animate"
    return "unplaced"


def classify_layers(elements, overrides=None):
    mapping = overrides if isinstance(overrides, dict) else {}
    rows = []
    for item in elements or []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or item.get("public_id") or "")
        intent = str(mapping.get(ident) or item.get("intent") or default_intent(item))
        if intent not in INTENTS:
            intent = default_intent(item)
            if intent not in INTENTS:
                intent = "unplaced"
        row = {
            "id": ident,
            "role": item.get("role") or "",
            "label": item.get("label") or "",
            "type": item.get("type") or item.get("layer_type") or "image",
            "bbox": item.get("bbox") if isinstance(item.get("bbox"), dict) else {},
            "z_index": int(item.get("z_index") or 0),
            "visible": item.get("visible") is not False,
            "png_path": item.get("png_path") or "",
            "text": item.get("text") or item.get("text_content") or "",
            "intent": intent,
        }
        rows.append(row)
    rows.sort(key=lambda item: item.get("z_index") or 0)
    return rows


def snapshot_scene(payload, *, source_version_id="", overrides=None):
    data = payload if isinstance(payload, dict) else {}
    creative = data.get("creative") if isinstance(data.get("creative"), dict) else {}
    creative_id = str(
        data.get("creative_id")
        or creative.get("id")
        or creative.get("public_id")
        or ""
    )
    elements = classify_layers(data.get("elements") or [], overrides)
    document = data.get("scene") if isinstance(data.get("scene"), dict) else data.get("document")
    if not isinstance(document, dict):
        document = {}
    snapshot = {
        "creative_id": creative_id,
        "scene_version": int(data.get("scene_version") or 1),
        "document": document,
        "elements": elements,
        "protected_layer_ids": [item["id"] for item in elements if item["intent"] == "protect"],
        "animate_layer_ids": [item["id"] for item in elements if item["intent"] == "animate"],
        "hide_layer_ids": [item["id"] for item in elements if item["intent"] == "hide"],
        "unplaced_layer_ids": [item["id"] for item in elements if item["intent"] == "unplaced"],
        "source_version_id": str(source_version_id or data.get("source_version_id") or ""),
    }
    snapshot["fingerprint"] = snapshot_fingerprint(snapshot)
    return snapshot


def validate_snapshot(snapshot):
    data = snapshot if isinstance(snapshot, dict) else {}
    if not data.get("creative_id"):
        raise ValueError("A composição protegida exige o criativo do Camadas (crt_).")
    elements = [item for item in (data.get("elements") or []) if isinstance(item, dict)]
    if not elements:
        raise ValueError("A cena não tem camadas. Mapeie a peça no Camadas antes de animar.")
    return data


def snapshot_fingerprint(snapshot):
    data = snapshot if isinstance(snapshot, dict) else {}
    payload = {
        "scene_version": data.get("scene_version"),
        "protected": list(data.get("protected_layer_ids") or []),
        "animate": list(data.get("animate_layer_ids") or []),
        "hide": list(data.get("hide_layer_ids") or []),
        "boxes": [
            {
                "id": item.get("id"),
                "bbox": item.get("bbox") or {},
                "intent": item.get("intent"),
                "text": item.get("text") or "",
            }
            for item in (data.get("elements") or [])
            if isinstance(item, dict)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
