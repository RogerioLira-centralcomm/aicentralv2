"""Provider-neutral connector registry for Cadu integrations.

The registry is intentionally metadata-first. Provider adapters own tokens and
API details; product surfaces consume one manifest to describe capabilities,
authentication and rollout state consistently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorManifest:
    key: str
    name: str
    status: str
    auth_modes: tuple[str, ...]
    resource_types: tuple[str, ...]
    capabilities: tuple[str, ...]
    surfaces: tuple[str, ...] = ("workspace", "project", "mcp")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "auth_modes": list(self.auth_modes),
            "resource_types": list(self.resource_types),
            "capabilities": list(self.capabilities),
            "surfaces": list(self.surfaces),
        }


class ConnectorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ConnectorManifest] = {}

    def register(self, manifest: ConnectorManifest) -> None:
        if manifest.key in self._items:
            raise ValueError(f"Conector duplicado: {manifest.key}")
        self._items[manifest.key] = manifest

    def get(self, key: str) -> ConnectorManifest | None:
        return self._items.get(str(key or "").strip().lower())

    def list(self, *, status: str | None = None) -> list[dict]:
        values = self._items.values()
        if status:
            values = (item for item in values if item.status == status)
        return [item.to_dict() for item in sorted(values, key=lambda item: item.name)]


registry = ConnectorRegistry()
registry.register(ConnectorManifest(
    key="google_workspace", name="Google Workspace", status="active",
    auth_modes=("oauth2",),
    resource_types=("drive_file", "calendar_event", "meet_space", "ads_account"),
    capabilities=("read", "search", "link", "sync", "index"),
))
registry.register(ConnectorManifest(
    key="slack", name="Slack", status="planned",
    auth_modes=("oauth2",), resource_types=("message", "thread", "file"),
    capabilities=("read", "search", "events", "notify", "link"),
))
registry.register(ConnectorManifest(
    key="clickup", name="ClickUp", status="planned",
    auth_modes=("oauth2", "api_key"), resource_types=("task", "list", "document"),
    capabilities=("read", "search", "write", "link", "events"),
))
registry.register(ConnectorManifest(
    key="trello", name="Trello", status="planned",
    auth_modes=("oauth2",), resource_types=("board", "card", "checklist"),
    capabilities=("read", "search", "write", "link", "events"),
))
registry.register(ConnectorManifest(
    key="canva", name="Canva", status="planned",
    auth_modes=("oauth2",), resource_types=("design", "folder", "comment"),
    capabilities=("read", "search", "preview", "link", "comments"),
))
