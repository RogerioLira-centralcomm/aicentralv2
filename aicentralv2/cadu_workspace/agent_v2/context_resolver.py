"""Resolve only the context explicitly requested by an IntentRoute."""

from dataclasses import dataclass, field
from typing import Any
from time import perf_counter

from .contracts import IntentRoute, RequestContext
from ..mcp.registry import ToolError, ToolNotFound, ToolRegistry


@dataclass
class ResolvedContext:
    values: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _arguments(tool_name: str, request: RequestContext, message: str) -> dict[str, Any]:
    if tool_name == "artifacts.get" and request.active_object and request.active_object.type.startswith("artifact:"):
        return {"artifact_id": request.active_object.id}
    if tool_name == "workspace.search_project_content":
        return {"query": message[:400]}
    if tool_name == "workspace.get_project_context":
        return {"query": message[:400]}
    if tool_name in {"planner.get_brief", "planner.get_media_plan", "reports.get_report_metrics"}:
        if request.active_object:
            key = "plan_id" if tool_name.startswith("planner.") else "report_id"
            return {key: request.active_object.id}
    if tool_name == "reports.compare_report_to_plan" and request.active_object:
        key = "report_id" if request.active_object.type in {"report", "report_workspace"} else "plan_id"
        return {key: request.active_object.id}
    return {}


def resolve_context(route: IntentRoute, request: RequestContext, message: str,
                    registry: ToolRegistry) -> ResolvedContext:
    result = ResolvedContext(values={"current_context": request.to_dict()})
    for tool_name in route.needs_tools:
        arguments = _arguments(tool_name, request, message)
        started = perf_counter()
        try:
            value = registry.execute(tool_name, arguments, request)
            result.values[tool_name] = value
            result.tool_calls.append({"name": tool_name, "status": "completed",
                                      "duration_ms": round((perf_counter() - started) * 1000)})
        except (ToolError, ValueError) as exc:
            # Missing context is data for the response policy, never a provider
            # diagnostic to expose to the customer.
            result.missing.append(tool_name)
            result.tool_calls.append({"name": tool_name, "status": "unavailable", "code": getattr(exc, "code", "invalid"),
                                      "duration_ms": round((perf_counter() - started) * 1000)})
    return result
