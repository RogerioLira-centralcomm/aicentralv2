"""Execute server-authored, user-approved action steps through the MCP registry."""

from ..mcp.registry import ToolError, ToolInputError, load_builtin_tools

ALLOWED_ACTION_TOOLS = frozenset({
    "planner.link_test", "workspace.create_project", "workspace.set_project_status",
    "workspace.link_current_brand",
    "projects.reindex_source",
    "projects.create_note",
    "projects.create_link_reference",
    "brands.create", "brands.start_audit",
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
        is_meeting = result.get("resource_kind") == "meeting"
        detail = ("O link foi classificado como reunião com acesso controlado e organizado no projeto."
                  if is_meeting else
                  "O link foi organizado como referência. O conteúdo não foi aberto, lido ou indexado.")
        blocks = [{"type": "activity", "state": "completed", "label": detail}]
        if is_meeting:
            blocks.append({"type": "questions", "title": "Usar este link", "items": [{
                "id": "prepare-meeting", "title": "Preparar pauta da reunião",
                "prompt": f"Prepare uma pauta para a reunião deste projeto: {result.get('url', '')}",
            }]})
        if result.get("provider") in {"generic", "google_drive"}:
            blocks.append({"type": "questions", "title": "Próximo passo opcional", "items": [{
                "id": "summarize-link", "title": "Criar resumo editável deste link",
                "prompt": f"Crie um resumo em texto editável do conteúdo disponível neste link para o projeto: {result.get('url', '')}",
            }]})
        return {"answer": f"“{title}” foi adicionado às referências do projeto.", "blocks": [
            *blocks,
        ], "refresh_context": True}
    if step_name == "brands.create":
        name = result.get("name") or "Marca"
        return {"answer": f"A marca “{name}” foi criada neste cliente com o site informado.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Marca criada", "detail": name},
            {"type": "questions", "title": "Completar a marca", "items": [{
                "id": "audit-brand", "title": "Iniciar auditoria completa",
                "prompt": f"Inicie a auditoria completa da marca {result.get('brand_id')}.",
            }]},
        ], "refresh_context": True}
    if step_name == "brands.start_audit":
        mode = result.get("analysis_mode") or "complete"
        return {"answer": "A auditoria da marca entrou na fila.", "blocks": [
            {"type": "activity", "state": "running", "label": "Auditoria da marca iniciada", "detail": mode},
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
    if step["name"] == "brands.start_audit" and "brand_id" not in sealed:
        brand_ref = str(getattr(context, "brand_ref", "") or "")
        if not brand_ref.startswith("studio:") or not brand_ref[7:].isdigit():
            raise ToolInputError("Selecione uma marca antes de iniciar a auditoria.")
        sealed["brand_id"] = int(brand_ref[7:])
    result = load_builtin_tools().execute(step["name"], sealed, context, "internal")
    if not isinstance(result, dict):
        raise ToolError("A ação não devolveu um receipt válido.")
    return {"tool": step["name"], "request_id": request_id, "result": result,
            "completion": _completion(step["name"], result)}
