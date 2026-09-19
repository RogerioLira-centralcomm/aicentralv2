"""Bounded deterministic task plans; simple turns never invoke a planner LLM."""

from .contracts import ExecutionBudget, IntentRoute


def build_task_plan(route: IntentRoute, budget: ExecutionBudget) -> list[dict]:
    steps = [{"kind": "tool", "name": name} for name in route.needs_tools[:budget.max_tool_calls]]
    if route.artifact_type:
        steps.append({"kind": "artifact", "action": route.action, "type": route.artifact_type})
    steps.append({"kind": "generate", "response_mode": route.response_mode})
    return steps
