"""Evidence-bounded summary of native project tasks for client status drafts."""

from __future__ import annotations


STATUSES = ("done", "in_progress", "blocked", "todo")


def summarize_tasks(result: dict) -> dict:
    """Count only canonical tasks, without equating task state to delivery."""
    if not isinstance(result, dict) or result.get("available") is not True:
        return {"status": "unavailable", "counts": {}, "items": [],
                "scope_note": "A lista de tarefas nativas não está disponível; não conclua status de entrega."}
    tasks = result.get("tasks") if isinstance(result.get("tasks"), list) else []
    counts = {status: 0 for status in STATUSES}
    items = []
    unknown = 0
    for task in tasks:
        if not isinstance(task, dict):
            unknown += 1
            continue
        state = str(task.get("status") or "")
        if state not in counts:
            unknown += 1
            continue
        counts[state] += 1
        if len(items) < 20:
            items.append({key: task.get(key) for key in (
                "id", "title", "status", "assignee_name", "due_at", "updated_at"
            )})
    return {"status": "available", "counts": counts, "unknown_status_count": unknown,
            "total_tasks": len(tasks), "items": items,
            "scope_note": "Resumo de tarefas nativas no estado atual. Não comprova entrega, aceite do cliente ou mudanças desde o último status."}
