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


def _project_status_step(message: str):
    text = str(message or "")
    status = "ativo" if re.search(r"\b(reativ|restaur)\w*", text, re.IGNORECASE) else "arquivado"
    label = "Reativar" if status == "ativo" else "Arquivar"
    return {
        "kind": "action", "name": "workspace.set_project_status", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"status": status}, "effect": "write",
        "summary": f"{label} o projeto atual.",
    }


def _project_brand_step(message: str):
    linked = not bool(re.search(r"\b(desvincul|remov|desassoci)\w*", str(message or ""), re.IGNORECASE))
    return {
        "kind": "action", "name": "workspace.link_current_brand", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"linked": linked}, "effect": "write",
        "summary": "Vincular a marca selecionada ao projeto atual." if linked else "Desvincular a marca selecionada do projeto atual.",
    }


def _reindex_source_step(message: str):
    match = re.search(r"\b(?:fonte|arquivo|documento)\s*#?\s*(\d+)\b", str(message or ""), re.IGNORECASE)
    if not match:
        return None
    source_id = int(match.group(1))
    return {
        "kind": "action", "name": "projects.reindex_source", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"source_id": source_id}, "effect": "write",
        "summary": f"Reprocessar a fonte {source_id} do projeto atual.",
    }


def _project_note_step(message: str):
    match = re.search(r"\b(?:nota|fonte textual)\s*[\"“]([^\"”]{2,180})[\"”]\s*:\s*(.{20,50000})$",
                      str(message or ""), re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = " ".join(match.group(1).split())
    content = match.group(2).strip()
    return {
        "kind": "action", "name": "projects.create_note", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": {"title": title, "content": content}, "effect": "write",
        "summary": f"Adicionar “{title}” como fonte de conhecimento do projeto.",
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
    if route.action == "set_project_status":
        steps.append(_project_status_step(message))
    if route.action == "link_project_brand":
        steps.append(_project_brand_step(message))
    if route.action == "reindex_project_source":
        action = _reindex_source_step(message)
        if action:
            steps.append(action)
    if route.action == "create_project_note":
        action = _project_note_step(message)
        if action:
            steps.append(action)
    if route.artifact_type:
        steps.append({"kind": "artifact", "action": route.action, "type": route.artifact_type,
                      "requires_confirmation": route.requires_confirmation})
    steps.append({"kind": "generate", "response_mode": route.response_mode})
    return steps
