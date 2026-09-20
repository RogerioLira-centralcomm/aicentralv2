"""Server-owned output limits; these do not rely on prompt obedience."""

from .contracts import ExecutionBudget, IntentRoute


def budget_for(route: IntentRoute, execution_mode: str = "analysis") -> ExecutionBudget:
    if execution_mode == "fast":
        return ExecutionBudget(max_llm_calls=1, max_tool_calls=1, max_context_chars=6000,
                               max_output_tokens=700, max_duration_ms=30000)
    if execution_mode == "agentic":
        return ExecutionBudget(max_llm_calls=3, max_tool_calls=12, max_context_chars=36000,
                               max_output_tokens=2600, max_duration_ms=240000)
    if route.complexity == "high":
        return ExecutionBudget(max_llm_calls=2, max_tool_calls=8, max_context_chars=28000,
                               max_output_tokens=2200, max_duration_ms=120000)
    return ExecutionBudget()


def policy_for(route: IntentRoute) -> dict:
    policies = {
        "direct": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 600, "artifact_in_chat": False, "single_sentence": True},
        "analysis": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 420, "artifact_in_chat": False, "single_sentence": True},
        "decision": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 320, "artifact_in_chat": False, "single_sentence": True},
        "artifact_first": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 240, "artifact_in_chat": False, "single_sentence": True},
        "clarification": {"max_questions": 1, "max_next_steps": 1, "max_answer_chars": 360, "artifact_in_chat": False},
    }
    return {"mode": route.response_mode, **policies[route.response_mode]}
