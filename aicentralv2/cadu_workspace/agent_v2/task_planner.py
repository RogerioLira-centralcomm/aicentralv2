"""Bounded deterministic task plans; simple turns never invoke a planner LLM."""

import re
from uuid import uuid4

from .contracts import ExecutionBudget, IntentRoute


def _link_test_step(message: str):
    match = re.search(r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?",
                      str(message or ""), re.IGNORECASE)
    if not match:
        return None
    mode = "agentic" if re.search(r"\b(ia|ai|llms?\.txt|rob[oô]s?|ag[eê]ntic)", message, re.IGNORECASE) else (
        "media" if re.search(r"\b(m[ií]dia|utm|pixel|tag|tracking|convers[aã]o)", message, re.IGNORECASE)
        else "destination"
    )
    return {
        "kind": "action", "name": "planner.link_test", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"url": match.group(0).rstrip(".,;:)"), "mode": mode},
        "effect": "write", "summary": "Testar o link informado e salvar o diagnóstico no Planner.",
    }


def _create_project_step(message: str):
    """Create only when the user supplied a usable name; never infer one from a task."""
    match = re.search(r"\b(?:crie|criar|novo)\s+(?:(?:um|o)\s+)?projeto\s*(?:chamado|nomeado|:)?\s*[\"“]?([^\"”\n.]{2,150})",
                      str(message or ""), re.IGNORECASE)
    if not match:
        return None
    name = " ".join(match.group(1).split()).strip(' -:;,."')
    if len(name) < 2:
        return None
    return {
        "kind": "action", "name": "workspace.create_project", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"name": name[:150]}, "effect": "write",
        "summary": f"Criar o projeto “{name[:150]}” no Workspace.",
    }


def build_task_plan(route: IntentRoute, budget: ExecutionBudget, message: str = "") -> list[dict]:
    steps = [{"kind": "tool", "name": name} for name in route.needs_tools[:budget.max_tool_calls]]
    if route.action == "link_test":
        action = _link_test_step(message)
        if action:
            steps.append(action)
    if route.action == "create_project":
        action = _create_project_step(message)
        if action:
            steps.append(action)
    if route.artifact_type:
        steps.append({"kind": "artifact", "action": route.action, "type": route.artifact_type,
                      "requires_confirmation": route.requires_confirmation})
    steps.append({"kind": "generate", "response_mode": route.response_mode})
    return steps
