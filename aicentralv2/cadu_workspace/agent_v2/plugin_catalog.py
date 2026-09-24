"""Database access for the versioned Cadu chat plugin catalog."""

import json

from ...cadu_family import repository


def list_entries(kind: str = "plugin") -> list[dict]:
    if kind not in {"plugin", "integration"}:
        raise ValueError("Tipo de catálogo inválido.")
    entries = repository.rows(
        """SELECT p.id, p.kind, p.name, p.category, p.logo, p.sort_order, p.selectable,
                  v.version, v.maturity, v.description, v.manifest, v.changelog
             FROM cadu_chat_plugins p
             JOIN cadu_chat_plugin_versions v ON v.plugin_id = p.id AND v.is_current
            WHERE p.kind = %s AND p.enabled
            ORDER BY p.sort_order, LOWER(p.name), p.id""",
        (kind,),
    )
    return [_public(entry) for entry in entries]


def get_plugin(plugin_id: str) -> dict | None:
    entries = repository.rows(
        """SELECT p.id, p.kind, p.name, p.category, p.logo, p.sort_order, p.selectable,
                  v.version, v.maturity, v.description, v.manifest, v.changelog
             FROM cadu_chat_plugins p
             JOIN cadu_chat_plugin_versions v ON v.plugin_id = p.id AND v.is_current
            WHERE p.id = %s AND p.kind = 'plugin' AND p.enabled AND p.selectable
            LIMIT 1""",
        (plugin_id,),
    )
    return _public(entries[0]) if entries else None


def _public(entry: dict) -> dict:
    item = dict(entry)
    manifest = item.pop("manifest", {})
    if isinstance(manifest, str):
        manifest = json.loads(manifest or "{}")
    elif manifest is None:
        manifest = {}
    item["manifest"] = manifest
    for key in ("triggers", "internal_tools", "context", "external_connectors", "known_gaps", "inputs", "outputs"):
        item[key] = list(manifest.get(key) or [])
    item["logo"] = item.get("logo") or manifest.get("logo")
    return item
