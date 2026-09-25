"""Execute server-authored, user-approved action steps through the MCP registry."""

import unicodedata
from dataclasses import replace

from ..mcp.registry import ToolError, ToolInputError, load_builtin_tools

ALLOWED_ACTION_TOOLS = frozenset({
    "planner.link_test", "workspace.create_project", "workspace.update_project_context",
    "workspace.set_project_status",
    "workspace.link_current_brand",
    "projects.reindex_source",
    "projects.create_note",
    "projects.create_link_reference",
    "projects.create_tasks", "projects.create_initial_task_list",
    "brands.create", "brands.prepare_logo_upload", "brands.prepare_asset_upload",
    "brands.update_identity", "brands.start_audit",
    "google.create_project_meeting",
    "media.generate_image", "media.edit_image", "media.plan_video",
})


def _normalized(value) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore")
                    .decode("ascii").lower().split())


def _validate_action_result(step_name: str, result: dict) -> None:
    """Do not present a task write as completed without task identities."""
    if step_name in {"projects.create_tasks", "projects.create_initial_task_list"}:
        tasks = result.get("tasks")
        created = result.get("created")
        if (not isinstance(tasks, list) or not tasks or type(created) is not int
                or created != len(tasks)
                or any(not isinstance(task, dict) or not task.get("id") for task in tasks)):
            raise ToolError("A ação não devolveu os IDs das tarefas criadas.")


def _resolve_audit_brand(sealed: dict, context, registry) -> None:
    """Resolve an explicitly named brand without changing project/conversation context."""
    query = str(sealed.pop("_brand_query", "") or "").strip()
    if not query or "brand_id" in sealed:
        return
    response = registry.execute("brands.list", {"query": query, "limit": 20}, context, "internal")
    brands = list((response or {}).get("brands") or [])
    normalized = _normalized(query)
    exact = [item for item in brands if _normalized(item.get("name")) == normalized]
    matches = exact or (brands if len(brands) == 1 else [])
    if len(matches) != 1:
        raise ToolInputError("Não encontrei uma única marca com esse nome. Informe o nome exato ou o ID da marca.")
    sealed["brand_id"] = int(matches[0]["brand_id"])


def _completion(step_name: str, result: dict) -> dict:
    """Give the UI a small, semantic receipt instead of a generic success string."""
    if step_name in {"media.generate_image", "media.edit_image"}:
        image_url = result.get("image_url")
        studio_url = result.get("studio_url")
        indexed = bool(result.get("indexed"))
        links = [item for item in (
            {"title": "Ver imagem", "url": image_url},
            {"title": "Abrir no Cadu Studio", "url": studio_url},
        ) if item.get("url")]
        label = "Imagem editada" if step_name == "media.edit_image" else "Imagem criada"
        detail = f"{int(result.get('charged_credits') or 0):,}".replace(",", ".") + " créditos utilizados"
        if indexed:
            detail += " · salva no projeto"
        elif result.get("project_link_status") == "pending_reconciliation":
            detail += " · imagem criada; indexação pendente"
        return {"answer": f"{label} no Cadu Studio.", "blocks": [
            {"type": "activity", "state": "completed", "label": label, "detail": detail},
            {"type": "links", "title": "Resultado", "items": links},
        ], "refresh_context": indexed}
    if step_name == "media.plan_video":
        session_url = result.get("studio_url") or result.get("session_url")
        links = [{"title": "Revisar no Cadu Studio", "url": session_url}] if session_url else []
        return {"answer": "O plano de vídeo foi preparado no Cadu Studio para revisão. A geração do vídeo ainda não foi iniciada.",
                "blocks": [{"type": "activity", "state": "completed",
                            "label": "Plano de vídeo preparado", "detail": "Aguardando revisão no Studio."},
                           {"type": "links", "title": "Studio", "items": links}],
                "refresh_context": False}
    if step_name == "workspace.create_project":
        name = result.get("name") or "Projeto"
        resources = result.get("resources") or {}
        links = len(resources.get("links") or [])
        notes = len(resources.get("notes") or [])
        uploads = resources.get("uploads") or []
        visibility = result.get("visibility") or "private"
        visibility_label = {"private": "Privado", "team": "Equipe", "restricted": "Acesso definido"}.get(visibility, visibility)
        details = [visibility_label]
        if links:
            details.append(f"{links} {'link' if links == 1 else 'links'}")
        if notes:
            details.append(f"{notes} {'fonte textual' if notes == 1 else 'fontes textuais'}")
        detail = " · ".join(details)
        completion = {"answer": f"Projeto “{name}” criado e preparado para receber o contexto solicitado.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Projeto criado", "detail": detail},
        ], "refresh_context": True, "open_surface": {
            "type": "project_profile", "project_ref": result.get("project_ref"),
        }, "activate_context": {"project_ref": result.get("project_ref"), "brand_ref": None}}
        if uploads:
            completion["uploads"] = uploads
            completion["blocks"].append({"type": "activity", "state": "running",
                                          "label": "Arquivos aguardando envio",
                                          "detail": f"{len(uploads)} autorização(ões) disponível(is)."})
        if resources.get("errors"):
            completion["blocks"].append({"type": "activity", "state": "needs_attention",
                                          "label": "Algumas fontes precisam ser repetidas",
                                          "detail": f"{len(resources['errors'])} item(ns) não concluído(s)."})
        return completion
    if step_name == "workspace.update_project_context":
        name = result.get("name") or "Projeto"
        fields = result.get("updated_fields") or []
        renamed_only = fields == ["name"] or not fields
        return {"answer": (f"Projeto renomeado para “{name}” com sucesso." if renamed_only else
                            f"Os dados do projeto “{name}” foram atualizados com sucesso."), "blocks": [
            {"type": "activity", "state": "completed", "label": ("Nome do projeto atualizado" if renamed_only else "Contexto do projeto atualizado"),
             "detail": name if renamed_only else " · ".join(fields)},
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
                  "O link e seus metadados foram classificados e organizados pelo indexador do projeto. O conteúdo protegido não foi lido.")
        blocks = [{"type": "activity", "state": "completed", "label": detail}]
        if is_meeting:
            blocks.append({"type": "questions", "title": "Usar este link", "items": [{
                "id": "prepare-meeting", "title": "Preparar pauta da reunião",
                "prompt": f"Prepare uma pauta para a reunião deste projeto: {result.get('url', '')}",
            }]})
        return {"answer": f"“{title}” foi adicionado às referências do projeto.", "blocks": [
            *blocks,
        ], "refresh_context": True}
    if step_name in {"projects.create_tasks", "projects.create_initial_task_list"}:
        count = int(result.get("created") or len(result.get("tasks") or []))
        return {"answer": f"{count} tarefa(s) criada(s) com as fontes do projeto preservadas.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Próximos passos organizados",
             "detail": f"{count} tarefa(s) criada(s) após confirmação."},
        ], "refresh_context": True}
    if step_name == "brands.create":
        name = result.get("name") or "Marca"
        blocks = [
            {"type": "activity", "state": "completed", "label": "Marca criada", "detail": name},
            {"type": "links", "title": "Marca", "items": [
                {"title": "Abrir detalhes da marca", "url": result.get("detail_url")},
            ]},
            {"type": "questions", "title": "Completar a nova marca", "items": [
                {"id": "logo-brand", "title": "Enviar logo principal",
                 "prompt": f"Quero enviar o logo principal da marca {result.get('brand_id')}."},
                {"id": "reference-brand", "title": "Adicionar referências",
                 "prompt": f"Quero adicionar referências visuais à marca {result.get('brand_id')}."},
                {"id": "audit-brand", "title": "Auditoria completa",
                 "prompt": f"Inicie a auditoria completa da marca {result.get('brand_id')}."},
                {"id": "deep-audit-brand", "title": "Auditoria profunda",
                 "prompt": f"Inicie a auditoria profunda da marca {result.get('brand_id')}."},
            ]},
        ]
        blocks[1]["items"] = [item for item in blocks[1]["items"] if item.get("url")]
        return {"answer": f"A marca “{name}” foi criada acima dos projetos. Vou continuar em uma conversa pessoal para você completar identidade, referências e auditoria sem perder o trabalho atual.", "blocks": blocks,
        "refresh_context": True, "open_surface": {
            "type": "personal_conversation", "brand_ref": result.get("brand_ref"),
            "seed_prompt": (f"Continue o trabalho sobre a marca {name}. Preserve o pedido original, os anexos e as referências da conversa anterior. "
                            "Organize os próximos passos para completar nome, segmento, site, identidade visual e auditoria, sem vincular a marca a um projeto automaticamente."),
        }, "artifact": result.get("artifact"),
        "activate_context": {"project_ref": None, "brand_ref": None}}
    if step_name in {"brands.prepare_logo_upload", "brands.prepare_asset_upload"}:
        replacing = result.get("purpose") == "replace_primary_logo"
        is_reference = result.get("role") == "reference"
        return {"answer": ("O envio da referência visual está autorizado por 10 minutos." if is_reference else
                            "O envio do novo logo principal está autorizado por 10 minutos."), "blocks": [
            {"type": "activity", "state": "running",
             "label": "Enviar referência visual" if is_reference else "Substituir logo principal" if replacing else "Enviar logo principal",
             "detail": "PNG, JPG ou WebP, até 5 MB."},
        ], "refresh_context": False, "upload": {
            "url": result.get("upload_url"), "token": result.get("upload_token"),
            "field": result.get("field"), "accepted": result.get("accepted"),
            "max_bytes": result.get("max_bytes"),
        }}
    if step_name == "brands.start_audit":
        mode = result.get("analysis_mode") or "complete"
        brand_name = result.get("brand_name") or f"Marca {result.get('brand_id')}"
        return {"answer": f"A auditoria de “{brand_name}” entrou na fila.", "blocks": [
            {"type": "activity", "state": "running", "label": "Auditoria da marca iniciada", "detail": mode},
        ], "refresh_context": False}
    if step_name == "brands.update_identity":
        fields = result.get("updated_fields") or []
        return {"answer": "A identidade da marca foi atualizada nos campos solicitados.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Identidade da marca atualizada",
             "detail": " · ".join(fields)},
        ], "refresh_context": True}
    if step_name == "google.create_project_meeting":
        title = result.get("title") or "Reunião do projeto"
        return {"answer": f"“{title}” foi criada e os convites foram enviados para a equipe do projeto.", "blocks": [
            {"type": "activity", "state": "completed", "label": "Reunião criada no Google Calendar",
             "detail": f"{result.get('invites_sent', 0)} convite(s) enviado(s)"},
            {"type": "links", "title": "Acessos", "items": [item for item in [
                {"title": "Entrar no Google Meet", "url": result.get("meet_url")},
                {"title": "Abrir no Google Calendar", "url": result.get("calendar_url")},
            ] if item.get("url")]},
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
    sealed = {**arguments, "request_id": request_id}
    if step["name"] in {"media.generate_image", "media.edit_image", "media.plan_video"}:
        estimate = snapshot.get("cost_estimate") or {}
        estimate_key = "video_plan_cost_estimate" if step["name"] == "media.plan_video" else "image_cost_estimate"
        if (snapshot.get("requires_confirmation") is not True
                or estimate.get("unit") != "credits"
                or not isinstance(estimate.get("estimated_total"), int)
                or estimate["estimated_total"] <= 0
                or estimate.get("kind") != estimate_key):
            raise ToolInputError("A geração do Studio não tem uma estimativa aprovada válida.")
        # These flags are stamped only after the journal has transitioned the
        # step from waiting_confirmation to running through the decision API.
        sealed["confirmed_cost"] = True
        if step["name"] != "media.plan_video":
            sealed["confirmed"] = True
        target = snapshot.get("execution_context") or {}
        if not isinstance(target, dict):
            raise ToolInputError("O contexto de destino da ação do Studio é inválido.")
        context = replace(context, project_ref=target.get("project_ref"), brand_ref=None)
    if step["name"] not in {"brands.prepare_logo_upload", "brands.prepare_asset_upload",
                             "media.generate_image", "media.edit_image", "media.plan_video"}:
        sealed["confirmed"] = True
    registry = load_builtin_tools()
    if step["name"] == "brands.start_audit":
        _resolve_audit_brand(sealed, context, registry)
    if step["name"] in {"brands.prepare_logo_upload", "brands.prepare_asset_upload", "brands.start_audit", "brands.update_identity"} and "brand_id" not in sealed:
        brand_ref = str(getattr(context, "brand_ref", "") or "")
        if not brand_ref.startswith("studio:") or not brand_ref[7:].isdigit():
            raise ToolInputError("Selecione uma marca antes de iniciar a auditoria.")
        sealed["brand_id"] = int(brand_ref[7:])
    result = registry.execute(step["name"], sealed, context, "internal")
    if not isinstance(result, dict):
        raise ToolError("A ação não devolveu um receipt válido.")
    _validate_action_result(step["name"], result)
    return {"tool": step["name"], "request_id": request_id, "result": result,
            "completion": _completion(step["name"], result)}
