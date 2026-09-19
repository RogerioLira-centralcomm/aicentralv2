"""Compose a V2 run without coupling orchestration to Flask routes or Dify."""

from dataclasses import asdict

from .context_resolver import resolve_context
from .prompt_assembler import build_payload
from .response_policy import budget_for, policy_for
from .router import route_request
from .task_planner import build_task_plan
from .contracts import execution_mode_for
from ..mcp.registry import load_builtin_tools


def prepare_execution(message, request, history="", requested_mode=""):
    route = route_request(message, request.surface, bool(request.project_ref))
    execution_mode = execution_mode_for(route, requested_mode)
    budget, policy = budget_for(route, execution_mode), policy_for(route)
    policy["execution_mode"] = execution_mode
    resolved = resolve_context(route, request, message, load_builtin_tools())
    payload = build_payload(message=message, request=request, route=route,
                            resolved=resolved.values, policy=policy,
                            user_label="user-" + str(request.user_id), history=history,
                            execution_mode=execution_mode)
    return {
        "route": route.to_dict(), "execution_mode": execution_mode,
        "budget": asdict(budget), "policy": policy,
        "plan": build_task_plan(route, budget, message), "resolved_context": resolved,
        "provider_payload": payload,
    }
