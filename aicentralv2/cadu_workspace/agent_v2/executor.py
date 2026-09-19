"""Compose a V2 run without coupling orchestration to Flask routes or Dify."""

from dataclasses import asdict

from .context_resolver import resolve_context
from .prompt_assembler import build_payload
from .response_policy import budget_for, policy_for
from .router import route_request
from .task_planner import build_task_plan
from ..mcp.registry import load_builtin_tools


def prepare_execution(message, request, history=""):
    route = route_request(message, request.surface, bool(request.project_ref))
    budget, policy = budget_for(route), policy_for(route)
    resolved = resolve_context(route, request, message, load_builtin_tools())
    payload = build_payload(message=message, request=request, route=route,
                            resolved=resolved.values, policy=policy,
                            user_label="user-" + str(request.user_id), history=history)
    return {
        "route": route.to_dict(), "budget": asdict(budget), "policy": policy,
        "plan": build_task_plan(route, budget), "resolved_context": resolved,
        "provider_payload": payload,
    }
