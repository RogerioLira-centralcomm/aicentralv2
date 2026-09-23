"""Server-owned output limits; these do not rely on prompt obedience."""

import re

from .contracts import ExecutionBudget, IntentRoute


def budget_for(route: IntentRoute, execution_mode: str = "analysis") -> ExecutionBudget:
    if execution_mode == "fast":
        return ExecutionBudget(max_llm_calls=1, max_tool_calls=1, max_context_chars=6000,
                               max_output_tokens=900, max_duration_ms=30000)
    if execution_mode == "agentic":
        return ExecutionBudget(max_llm_calls=3, max_tool_calls=12, max_context_chars=36000,
                               max_output_tokens=2600, max_duration_ms=240000)
    if route.complexity == "high":
        return ExecutionBudget(max_llm_calls=2, max_tool_calls=8, max_context_chars=28000,
                               max_output_tokens=2200, max_duration_ms=120000)
    return ExecutionBudget()


def policy_for(route: IntentRoute) -> dict:
    policies = {
        "direct": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 900, "artifact_in_chat": False},
        # Intermediate/analysis is the normal working mode. It must have room
        # for a useful answer even when the user did not request an artifact.
        "analysis": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 6000, "artifact_in_chat": False},
        "decision": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 320, "artifact_in_chat": False},
        "artifact_first": {"max_questions": 1, "max_next_steps": 2, "max_answer_chars": 240, "artifact_in_chat": False},
        "clarification": {"max_questions": 1, "max_next_steps": 1, "max_answer_chars": 360, "artifact_in_chat": False},
    }
    policy = {"mode": route.response_mode, **policies[route.response_mode]}
    if route.action == "describe_project":
        policy.update({"max_questions": 0, "max_next_steps": 0})
    return policy


def requested_answer_chars(message: str) -> int:
    """Translate an explicit user length into a safe character allowance.

    Portuguese prose commonly needs more than six characters per word once
    spaces and punctuation are included. Eight gives the provider enough room
    to honor the request without turning the number into an exact quota.
    """
    text = " ".join(str(message or "").split())
    match = re.search(r"\b(?:cerca de|aproximadamente|aprox\.?|at[eé])?\s*(\d{1,5}(?:\.\d{3})?)\s*palavras?\b", text, re.IGNORECASE)
    if not match:
        return 0
    words = min(5000, max(50, int(match.group(1).replace(".", ""))))
    return min(40000, words * 8)


def requested_output_tokens(message: str) -> int:
    """Return provider output room for an explicit requested length."""
    chars = requested_answer_chars(message)
    return min(12000, max(1200, (chars + 3) // 4)) if chars else 0
