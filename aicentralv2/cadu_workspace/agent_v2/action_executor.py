"""Execute server-authored, user-approved action steps through the MCP registry."""

from ..mcp.registry import ToolError, ToolInputError, load_builtin_tools

ALLOWED_ACTION_TOOLS = frozenset({
    "planner.link_test", "workspace.create_project", "workspace.set_project_status",
    "workspace.link_current_brand",
    "projects.reindex_source",
    "projects.create_note",
    "projects.create_link_reference",
})


def _completion(step_name: str, result: dict) -> dict:
    """Give the UI a small, semantic receipt instead of a generic success string."""
    if step_name == "workspace.create_project":
        name = result.get("name") or "Projeto"
        return {"answer": f"Projeto “{name}” criado.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Projeto criado", "detail": name},
        ], "refresh_context": True}
    if step_name == "workspace.set_project_status":
        status = result.get("status") or "atualizado"
        return {"answer": f"Projeto {status}.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Status do projeto atualizado", "detail": status},
        ], "refresh_context": True}
    if step_name == "workspace.link_current_brand":
        linked = bool(result.get("linked"))
        brand = result.get("brand_name") or "Marca"
        return {"answer": f"{brand} {'vinculada ao' if linked else 'desvinculada do'} projeto.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Vínculo de marca atualizado", "detail": brand},
        ], "refresh_context": True}
    if step_name == "projects.create_note":
        name = result.get("name") or "Nota"
        sync = result.get("registry_sync")
        detail = "Fonte indexada e disponível no projeto." if sync != "pending" else "Fonte indexada; a organização do projeto será concluída em seguida."
        return {"answer": f"“{name}” foi adicionada como fonte do projeto.", "blocks": [
            {"type": "sources", "title": "Fonte adicionada", "items": [{"id": result.get("source_id"), "title": name}]},
            {"type": "activity", "state": "completed", "label": detail},
        ], "refresh_context": True}
    if step_name == "projects.reindex_source":
        source_id = result.get("source_id")
        status = result.get("status") or "concluído"
        return {"answer": f"Fonte {source_id} reprocessada.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Reprocessamento concluído", "detail": status},
        ], "refresh_context": True}
    if step_name == "projects.create_link_reference":
        title = result.get("title") or "Link"
        detail = "Referência salva sem indexação automática."
        return {"answer": f"“{title}” foi adicionado às referências do projeto.", "blocks": [
            {"type": "activity", "state": "completed", "label": detail},
        ], "refresh_context": True}
    return {"answer": "Ação concluída.", "blocks": [{"type": "activity", "state": "completed", "label": "Ação concluída"}]}


def execute(step: dict, context) -> dict:
    if step.get("kind") != "action" or step.get("status") != "running":
        raise ToolInputError("A etapa não está pronta para execução.")
    snapshot = step.get("input_snapshot") or {}
    if not isinstance(snapshot, dict) or snapshot.get("name") != step.get("name"):
        raise ToolInputError("A proposta de ação não corresponde à etapa aprovada.")
    if step.get("name") not in ALLOWED_ACTION_TOOLS:
        raise ToolInputError("Esta ação ainda não pode ser executada automaticamente.")
    arguments = snapshot.get("arguments")
    request_id = snapshot.get("request_id")
    if not isinstance(arguments, dict) or not request_id:
        raise ToolInputError("A proposta aprovada está incompleta.")
    sealed = {**arguments, "request_id": request_id, "confirmed": True}
    result = load_builtin_tools().execute(step["name"], sealed, context, "internal")
    if not isinstance(result, dict):
        raise ToolError("A ação não devolveu um receipt válido.")
    return {"tool": step["name"], "request_id": request_id, "result": result,
            "completion": _completion(step["name"], result)}
