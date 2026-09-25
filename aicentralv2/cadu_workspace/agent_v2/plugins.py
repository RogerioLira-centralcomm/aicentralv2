"""Versioned chat plugin workflows composed from the shared MCP registry.

Plugins are user-facing workflows. They do not implement data access: internal
MCP tools remain the authorized execution layer, while future external MCP
servers can be declared as connectors on the same manifest.
"""

from __future__ import annotations

import re

from .contracts import IntentRoute, RequestContext
from .plugin_catalog import get_plugin, list_entries
from .daily_workflows import WORKFLOWS

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
_SUPPLIED_DATA = re.compile(r"\b(?:impress[oõ]es|cliques?|ctr|cpc|cpm|convers[oõ]es|roas|investimento|or[cç]amento|resultado|meta)\b", re.I)


def catalog() -> list[dict]:
    """Public metadata for the Plugins storefront and capability discovery."""
    return list_entries("plugin")


def integrations() -> list[dict]:
    """External providers shown in the planned integrations shelf."""
    return list_entries("integration")


def _execution_tools(plugin_id: str) -> tuple[str, ...]:
    """Allowlisted internal tools; database manifests never grant tool access."""
    if plugin_id in WORKFLOWS:
        return WORKFLOWS[plugin_id][3]
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
        "insights": ("workspace.get_project_context", "brands.get_context", "insights.research_market"),
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


def select(route: IntentRoute, message: str, context: RequestContext, *, has_report_attachment: bool = False) -> tuple[dict | None, tuple[str, ...], list[str]]:
    """Select one workflow and its minimal MCP chain for this turn."""
    # A newsletter request needs a wider, explicitly requested set of news
    # sources than the compact market-insights workflow returns.
    if route.action == "create_newsletter" and not re.match(r"^/([a-z][a-z-]+)(?:\s|$)", str(message or "").strip()):
        return None, (), []
    text = str(message or "")
    plugin_id = None
    tool_chain: tuple[str, ...] = ()
    missing: list[str] = []

    explicit = re.match(r"^/([a-z][a-z-]+)(?:\s|$)", text.strip())
    if explicit and explicit.group(1) in WORKFLOWS:
        plugin_id = explicit.group(1)
        tool_chain = _execution_tools(plugin_id)
        has_material = len(text.split()) >= 30 or text.count("\n") >= 3
        if not text.strip()[explicit.end():].strip():
            missing.append("objetivo do pedido")
        if re.search(r"\bdescreva (?:seu objetivo|sua tarefa)\b", text, re.I):
            missing.append("objetivo do pedido")
        refers_to_unselected_context = bool(re.search(
            r"\b(?:d?este projeto|desta campanha|desta marca)\b", text, re.I
        )) and not (context.project_ref or context.brand_ref)
        if (plugin_id in {"market-radar", "audience-map", "creative-concept", "channel-copy"}
                and refers_to_unselected_context and not has_material):
            missing.append("marca, setor ou campanha a considerar")
        if (plugin_id in {"investment-simulator", "meeting-copilot"}
                and refers_to_unselected_context and not has_material):
            missing.append("projeto ou objetivo a considerar")
        if plugin_id == "media-plan-audit":
            tool_chain = (("planner.get_media_plan",) if context.active_object and context.active_object.type in {"plan", "media_plan"}
                          else ("planner.list_plans",) if context.project_ref and not has_material else ())
        if plugin_id == "campaign-tracker":
            # Campaign reporting is still being built. This plugin currently
            # analyzes the supplied file and does not couple to Reports tools.
            tool_chain = ()
        if plugin_id == "campaign-tracker" and not context.project_ref and not context.active_object and not has_report_attachment:
            tool_chain = ()
            if not (_SUPPLIED_DATA.search(text) and re.search(r"\d", text)):
                missing.append("relatório revisado, métricas ou projeto da campanha")
        if plugin_id == "media-plan-audit" and not context.project_ref and not context.active_object and not has_material:
            missing.append("plano de mídia ou projeto com um plano")
        if plugin_id == "page-review" and not re.search(r"https://\S+", text):
            tool_chain = ()
            if not has_material:
                missing.append("URL ou conteúdo da página")
        if plugin_id == "client-delivery" and not context.project_ref:
            tool_chain = ()
            if not has_material:
                missing.append("projeto ou informações de status para o cliente")
        if plugin_id == "meeting-copilot" and not re.search(r"\b(?:meet|google|transcri[cç][aã]o|grava[cç][aã]o)\b", text, re.I):
            tool_chain = ()
        if plugin_id in {"market-radar", "audience-map", "investment-simulator", "creative-concept", "channel-copy", "page-review", "meeting-copilot", "client-delivery"}:
            context_tools = []
            if context.project_ref and plugin_id != "market-radar":
                context_tools.append("workspace.get_project_context")
            if context.brand_ref or context.project_ref:
                context_tools.append("brands.get_context")
            tool_chain = tuple(dict.fromkeys((*context_tools, *tool_chain)))
    elif route.action == "schedule_project_meeting":
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
            context_tools = ["workspace.get_project_context"] if context.project_ref else []
            if context.brand_ref or context.project_ref:
                context_tools.append("brands.get_context")
            tool_chain = tuple([*context_tools, "insights.research_market"])
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
        # Preserve an explicit slash request as an honest unavailable state;
        # never dispatch its tools while the catalog disables the workflow.
        if explicit and explicit.group(1) in WORKFLOWS:
            return {"id": plugin_id, "name": WORKFLOWS[plugin_id][0],
                    "unavailable": True, "internal_tools": []}, (), []
        return None, (), []
    # Runtime execution capabilities are code allowlisted. The database manifest
    # documents them but cannot expand what an automatic selection may invoke.
    selected["internal_tools"] = list(_execution_tools(plugin_id))
    selected["required_context_missing"] = missing
    selected["selected_automatically"] = not bool(explicit and explicit.group(1) in WORKFLOWS)
    return selected, tool_chain, missing
