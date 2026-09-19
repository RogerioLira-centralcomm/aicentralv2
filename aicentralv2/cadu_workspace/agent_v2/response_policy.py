"""Server-owned output limits; these do not rely on prompt obedience."""

from .contracts import ExecutionBudget, IntentRoute


def budget_for(route: IntentRoute) -> ExecutionBudget:
    if route.complexity == "high":
        return ExecutionBudget(max_llm_calls=2, max_tool_calls=8, max_context_chars=28000, max_output_tokens=2200)
    return ExecutionBudget()


def policy_for(route: IntentRoute) -> dict:
    policies = {
        "direct": {"max_questions": 1, "max_next_steps": 2, "artifact_in_chat": False},
        "analysis": {"max_questions": 1, "max_next_steps": 3, "artifact_in_chat": False},
        "decision": {"max_questions": 1, "max_next_steps": 3, "artifact_in_chat": False},
        "artifact_first": {"max_questions": 2, "max_next_steps": 2, "artifact_in_chat": False},
        "clarification": {"max_questions": 2, "max_next_steps": 0, "artifact_in_chat": False},
    }
    return {"mode": route.response_mode, **policies[route.response_mode]}
