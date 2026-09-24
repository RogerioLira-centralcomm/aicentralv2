"""Public Cadu MCP tool modules used to keep default client catalogs focused."""

from __future__ import annotations


TOOL_MODULES = {
    "marketing": "Marketing",
    "projects": "Projetos",
    "library": "Biblioteca",
    "media": "Mídia",
    "brands": "Marcas",
    "google": "Google",
    "artifacts": "Documentos",
    "account": "Conta e créditos",
    "reports": "Relatórios",
}
DEFAULT_MODULES = ("marketing",)
ALL_MODULES = tuple(TOOL_MODULES)

_MARKETING_TOOLS = frozenset({
    "intent.interpret", "intent.execute", "context.open", "context.get",
    "context.update", "context.close", "operations.get",
    "projects.list_sources", "projects.search_knowledge", "projects.get_source_chunks",
    "projects.inspect_link", "projects.ingestion_status", "projects.list_resources",
    "projects.inspect_file_support", "projects.classify_intake",
    "workspace.get_project_context", "workspace.search_project_content",
    "brands.list", "brands.get_context", "brands.inspect_site", "brands.list_assets",
    "artifacts.list", "artifacts.describe_types", "artifacts.get", "artifacts.create_draft",
    "artifacts.update_draft", "artifacts.finalize_to_project",
    "planner.list_plans", "planner.search_catalog", "planner.list_link_tests",
    "planner.get_link_test", "planner.get_brief", "planner.get_media_plan",
    "web.search", "web.read", "media.creation_capabilities", "media.plan_video",
    "resources.search", "resources.inspect_input", "resources.get", "resources.capabilities",
})


def module_for_tool(name: str) -> str:
    """Return the single user-facing module that owns a public tool."""
    if name in _MARKETING_TOOLS:
        return "marketing"
    prefix = name.partition(".")[0]
    if prefix == "resources" or name in {"projects.prepare_source_upload", "projects.reindex_source"}:
        return "library"
    if prefix == "media":
        return "media"
    if prefix == "brands":
        return "brands"
    if prefix == "google":
        return "google"
    if prefix == "artifacts":
        return "artifacts"
    if prefix in {"account", "credits"}:
        return "account"
    if prefix == "reports":
        return "reports"
    if prefix in {"intent", "context", "operations", "planner", "web"}:
        return "marketing"
    return "projects"


def normalize_modules(value, *, default=DEFAULT_MODULES) -> tuple[str, ...]:
    if value is None:
        return tuple(default)
    if isinstance(value, str):
        value = value.split()
    modules = {str(item).strip().lower() for item in (value or ()) if str(item).strip()}
    invalid = modules - set(TOOL_MODULES)
    if invalid:
        raise ValueError("Módulo MCP inválido.")
    return tuple(name for name in TOOL_MODULES if name in modules)
