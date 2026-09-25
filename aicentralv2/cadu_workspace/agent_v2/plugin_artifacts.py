"""Presentation capabilities of Cadu plugins, separate from tool permissions."""

from __future__ import annotations

from ..artifacts.catalog import ALLOWED_TYPES


# These are suggested semantic outputs, not permission grants. An explicit
# deliverable from the user remains authoritative, including HTML when asked.
PLUGIN_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "market-intelligence": ("research", "executive_summary", "document"),
    "market-radar": ("research", "executive_summary", "note"),
    "insights": ("research", "executive_summary", "note"),
    "campaign-search": ("research", "document"),
    "planner": ("media_plan", "brief", "scenario"),
    "audience-map": ("research", "brief", "document"),
    "investment-simulator": ("scenario", "media_plan"),
    "media-plan-audit": ("media_plan", "executive_summary", "document"),
    "creative-concept": ("brief", "document", "note"),
    "channel-copy": ("document", "note"),
    "page-review": ("document", "note", "research"),
    "studio": ("document", "brief"),
    "campaign-tracker": ("executive_summary", "document", "research"),
    "reports": ("executive_summary", "document"),
    "project-search": ("project_map", "executive_summary", "document", "note"),
    "project-activities": ("project_map", "note", "document"),
    "meeting-copilot": ("meeting_agenda", "meeting_summary"),
    "client-delivery": ("executive_summary", "document", "note"),
    "google-drive": ("project_map",),
    "google-calendar": ("meeting_agenda",),
    "google-meet": ("meeting_summary", "meeting_agenda"),
}


def delivery_metadata(plugin_id: str) -> dict:
    """Describe possible presentations without causing artifact creation."""
    suggested = PLUGIN_ARTIFACTS.get(plugin_id, ())
    assert set(suggested) <= ALLOWED_TYPES
    return {
        "default_channel": "chat",
        "suggested_artifact_types": list(suggested),
        "materialize_when": "deep_mode_or_explicit_request" if plugin_id == "market-intelligence" else "explicit_request",
    }
