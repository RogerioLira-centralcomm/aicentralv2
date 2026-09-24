"""Versioned chat plugin workflows composed from the shared MCP registry.

Plugins are user-facing workflows. They do not implement data access: internal
MCP tools remain the authorized execution layer, while future external MCP
servers can be declared as connectors on the same manifest.
"""

from __future__ import annotations

import re

from .contracts import IntentRoute, RequestContext
from .plugin_catalog import get_plugin, list_entries

_CAMPAIGN_SEARCH = re.compile(
    r"\b(?:busc\w*|pesquis\w*|procur\w*|encontr\w*|localiz\w*|mostr\w*)\b.{0,55}"
    r"\b(?:campanhas?|cases?)\b|\b(?:campanhas?|cases?)\b.{0,55}"
    r"\b(?:busc\w*|pesquis\w*|procur\w*|encontr\w*|localiz\w*)\b", re.I,
)
_PLANNING = re.compile(r"\b(?:planej\w*|mont\w*|cri\w*|elabor\w*|estrutur\w*)\b.{0,70}\b(?:plano|planejamento)\b", re.I)
_INSIGHTS = re.compile(r"\b(?:insights?|aprendizados?|achados?)\b", re.I)
_MARKET = re.compile(r"\b(?:pesquisa de mercado|mercado|tend[eê]ncias?|benchmark|concorr[eê]ncia|setor)\b", re.I)
_EXPLICIT_ACTIVITIES = re.compile(
    r"\b(?:plugin\s+(?:de\s+)?)?(?:atividades?\s+do\s+projeto|"
    r"(?:consult\w*|list\w*|mostr\w*|ver\w*|organiz\w*|planej\w*)\b"
    r".{0,45}\b(?:atividades?|tarefas?)\b|"
    r"\b(?:atividades?|tarefas?)\b.{0,45}"
    r"\b(?:do\s+projeto|no\s+projeto|organiz\w*|planej\w*)\b)", re.I,
)
_EXPLICIT_PROJECT_SEARCH = re.compile(r"\b(?:plugin\s+(?:de\s+)?)?(?:busca\s+no\s+projeto|pesquisa\s+no\s+projeto)\b", re.I)
_GOOGLE_CONNECT = re.compile(r"\b(?:conect\w*|autoriza\w*|vincul\w*|configur\w*|status|estado|conta)\b.{0,65}\bgoogle\b|\bgoogle\b.{0,65}\b(?:conect\w*|autoriza\w*|vincul\w*|configur\w*|status|estado|conta)\b", re.I)
_GOOGLE_DRIVE = re.compile(r"\b(?:google\s+drive|drive|google\s+docs|google\s+sheets|pasta\s+(?:do|no)\s+google)\b", re.I)
_GOOGLE_CALENDAR = re.compile(r"\b(?:google\s+calendar|agenda\s+google|calend[aá]rio\s+google)\b", re.I)
_GOOGLE_MEET = re.compile(r"\b(?:google\s+meet|reuni[aã]o\s+(?:do|no)\s+meet|transcri[cç][aã]o\s+(?:do|no)\s+meet)\b", re.I)


def catalog() -> list[dict]:
    """Public metadata for the Plugins storefront and capability discovery."""
    return list_entries("plugin")


def integrations() -> list[dict]:
    """External providers shown in the planned integrations shelf."""
    return list_entries("integration")


def _execution_tools(plugin_id: str) -> tuple[str, ...]:
    """Allowlisted internal tools; database manifests never grant tool access."""
    return {
        "campaign-search": ("brands.get_context", "workspace.search_project_content"),
        "project-search": ("workspace.search_project_content", "workspace.get_project_context",
                           "projects.search_knowledge", "projects.list_resources", "resources.search",
                           "projects.get_source_chunks",
                           "artifacts.list"),
        "project-activities": ("workspace.get_project_context", "projects.list_tasks", "projects.list_resources",
                               "projects.create_initial_task_list", "projects.create_task", "projects.create_tasks",
                               "projects.update_task",
                               "artifacts.create_draft", "artifacts.update_draft"),
        "insights": ("insights.research_market",),
        "planner": ("planner.research_plan_inputs", "planner.search_catalog", "planner.get_media_plan",
                    "artifacts.create_draft", "artifacts.update_draft"),
        "reports": ("reports.list_project_reports", "reports.get_report_metrics", "reports.compare_report_to_plan"),
        "studio": ("media.creation_capabilities", "media.generate_image", "media.edit_image"),
        "google-connect": ("google.get_connector_status",),
        "google-drive": ("google.get_connector_status", "google.search_drive_resources",
                         "google.list_project_resources", "google.link_resource_to_project"),
        "google-calendar": ("google.get_connector_status", "google.list_calendar_events",
                            "google.create_project_meeting"),
        "google-meet": ("google.get_connector_status", "google.list_meet_records",
                        "google.list_meet_artifacts"),
    }.get(plugin_id, ())


def select(route: IntentRoute, message: str, context: RequestContext) -> tuple[dict | None, tuple[str, ...], list[str]]:
    """Select one workflow and its minimal MCP chain for this turn."""
    text = str(message or "")
    plugin_id = None
    tool_chain: tuple[str, ...] = ()
    missing: list[str] = []

    if route.action == "schedule_project_meeting":
        plugin_id = "google-calendar"
    elif route.action == "list_calendar_events":
        plugin_id = "google-calendar"
        tool_chain = ("google.get_connector_status", "google.list_calendar_events")
    elif _GOOGLE_CONNECT.search(text):
        plugin_id = "google-connect"
        tool_chain = ("google.get_connector_status",)
    elif _GOOGLE_DRIVE.search(text):
        plugin_id = "google-drive"
        tool_chain = ("google.get_connector_status", "google.search_drive_resources")
    elif _GOOGLE_CALENDAR.search(text):
        plugin_id = "google-calendar"
        tool_chain = ("google.get_connector_status", "google.list_calendar_events")
    elif _GOOGLE_MEET.search(text):
        plugin_id = "google-meet"
        tool_chain = ("google.get_connector_status", "google.list_meet_artifacts")
    elif _EXPLICIT_ACTIVITIES.search(text):
        plugin_id = "project-activities"
        if context.project_ref:
            tool_chain = ("workspace.get_project_context", "projects.list_tasks", "projects.list_resources")
        else:
            missing.append("projeto para consultar ou planejar as atividades")
    elif _EXPLICIT_PROJECT_SEARCH.search(text):
        plugin_id = "project-search"
        if context.project_ref:
            tool_chain = ("workspace.search_project_content", "projects.list_resources")
        else:
            missing.append("projeto que deseja consultar")
    elif _CAMPAIGN_SEARCH.search(text) and not _PLANNING.search(text) and not _INSIGHTS.search(text):
        plugin_id = "campaign-search"
        if context.brand_ref:
            tool_chain = ("brands.get_context",)
        elif context.project_ref:
            tool_chain = ("workspace.search_project_content",)
        else:
            missing.append("marca ou projeto onde procurar")
    elif _INSIGHTS.search(text):
        plugin_id = "insights"
        if _MARKET.search(text) or route.action == "search_insights":
            tool_chain = ("insights.research_market",)
        else:
            missing.append("tema de mercado dos insights")
    elif route.action == "compare_report_to_plan":
        plugin_id = "reports"
        if not context.project_ref:
            missing.append("projeto que contenha o relatório e o plano")
    elif route.domain == "reports" or route.action == "analyze_report":
        plugin_id = "reports"
        if context.active_object and context.active_object.type in {"report", "report_workspace"}:
            tool_chain = ("reports.get_report_metrics",)
        elif context.project_ref:
            tool_chain = ("reports.list_project_reports",)
        else:
            missing.append("relatório ou projeto com relatórios revisados")
    elif route.action == "plan_campaign" or route.domain == "planner":
        plugin_id = "planner"
        if route.action == "plan_campaign":
            tool_chain = ("planner.research_plan_inputs",)
    elif route.domain == "workspace" and route.action in {"list_project_tasks", "plan_project_tasks"}:
        plugin_id = "project-activities"
        if context.project_ref:
            if route.action == "list_project_tasks":
                tool_chain = ("projects.list_tasks",)
            else:
                tool_chain = ("workspace.get_project_context", "projects.list_tasks", "projects.list_resources")
        else:
            missing.append("projeto para consultar ou planejar as atividades")
    elif route.domain == "workspace" and route.action in {
        "search_project", "project_readout", "describe_project", "search_campaigns",
        "organize_project_resources", "describe_project_for_rename",
    }:
        plugin_id = "project-search"
        if context.project_ref:
            tool_chain = tuple(route.needs_tools) or ("workspace.search_project_content",)
        else:
            missing.append("projeto que deseja consultar")
    elif route.domain == "studio" or re.search(r"\b(?:ger\w*|cri\w*|edit\w*)\b.{0,45}\b(?:imagem|criativo|visual)\b", text, re.I):
        plugin_id = "studio"
    if plugin_id is None:
        return None, (), []
    selected = get_plugin(plugin_id)
    if not selected:
        # A removed or disabled catalog entry must never dispatch a workflow.
        return None, (), []
    # Runtime execution capabilities are code allowlisted. The database manifest
    # documents them but cannot expand what an automatic selection may invoke.
    selected["internal_tools"] = list(_execution_tools(plugin_id))
    selected["required_context_missing"] = missing
    selected["selected_automatically"] = True
    return selected, tool_chain, missing
