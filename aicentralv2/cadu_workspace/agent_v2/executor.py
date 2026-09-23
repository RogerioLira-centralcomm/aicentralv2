"""Compose a V2 run without coupling orchestration to Flask routes or Dify."""

import json
import re
from dataclasses import asdict, replace
from typing import Optional

from .context_resolver import resolve_context
from .prompt_assembler import build_payload
from .response_policy import budget_for, policy_for, requested_answer_chars, requested_output_tokens
from .router import route_request
from .task_planner import build_task_plan
from .contracts import execution_mode_for
from ..mcp.registry import load_builtin_tools


_BRIEFING_FIELDS = (
    ("objective", "objetivo", r"\b(objetivo|resultado|vendas?|leads?|convers[ãa]o|awareness|lan[çc]amento|reten[çc][ãa]o)\b"),
    ("audience", "público", r"\b(p[uú]blico|audi[êe]ncia|clientes?|b2b|b2c|segmento|idade|faixa et[áa]ria)\b"),
    ("offer", "oferta", r"\b(oferta|produto|servi[çc]o|marca|cta|pre[çc]o|benef[ií]cio|diferencial)\b"),
    ("distribution", "canais e entregas", r"\b(canais?|instagram|google|meta|youtube|linkedin|tiktok|m[ií]dia|pe[çc]as?|formatos?)\b"),
    ("constraints", "prazo ou investimento", r"\b(prazo|data|m[eê]s|semana|or[çc]amento|verba|r\$|restri[çc][õo]es?)\b"),
)


def briefing_readiness(message: str, history: str = "", context: Optional[dict] = None) -> dict:
    """Measure campaign facts conservatively before opening an editable brief."""
    evidence = " ".join((str(message or ""), str(history or ""), str(context or "")))
    completed = [key for key, _label, pattern in _BRIEFING_FIELDS if re.search(pattern, evidence, re.IGNORECASE)]
    missing = [label for key, label, _pattern in _BRIEFING_FIELDS if key not in completed]
    total = len(_BRIEFING_FIELDS)
    percent = round((len(completed) / total) * 100) if total else 0
    return {"percent": percent, "complete": percent >= 80, "completed": completed, "missing": missing}


def prepare_execution(message, request, history="", requested_mode="", conversation_state=None, routing_message=None):
    routed_message = routing_message or message
    route = route_request(
        routed_message, request.surface, bool(request.project_ref),
        request.active_object.type if request.active_object else "", bool(request.brand_ref),
    )
    readiness = None
    if route.action == "create_brief":
        readiness = briefing_readiness(message, history)
        if readiness["complete"]:
            route = replace(route, response_mode="artifact_first", artifact_type="brief")
        else:
            route = replace(route, response_mode="clarification", artifact_type=None)
    execution_mode = execution_mode_for(route, requested_mode)
    budget, policy = budget_for(route, execution_mode), policy_for(route)
    explicit_answer_chars = requested_answer_chars(message)
    if explicit_answer_chars and route.response_mode in {"direct", "analysis"}:
        policy["max_answer_chars"] = max(policy["max_answer_chars"], explicit_answer_chars)
        # A requested length is a delivery requirement, not a formatting hint.
        # Give the provider enough output room instead of increasing only the
        # post-processing character limit and then truncating the generation.
        output_tokens = requested_output_tokens(message)
        budget = replace(budget, max_output_tokens=max(budget.max_output_tokens, output_tokens))
    policy["execution_mode"] = execution_mode
    policy["max_output_tokens"] = budget.max_output_tokens
    policy["max_duration_ms"] = budget.max_duration_ms
    policy["artifact_type"] = route.artifact_type
    policy["allow_artifact"] = route.artifact_type is not None
    policy["allow_task_proposal"] = route.action == "plan_project_tasks"
    if readiness:
        policy["briefing_readiness"] = readiness
    policy["artifact_fallback_title"] = {
        "project_readout": "Leitura inicial do projeto",
        "create_brief": "Briefing do projeto",
        "create_meeting_summary": "Resumo da reunião",
        "create_meeting_agenda": "Pauta da reunião",
        "create_text_draft": "Documento editável",
        "create_link_summary": "Resumo do site",
        "create_client_delivery": "Entrega para revisão",
        "create_substantial_delivery": "Documento completo",
        "save_to_project": "Documento do projeto",
    }.get(route.action, "Resultado do trabalho")
    policy["artifact_chat_message"] = {
        "project_readout": "Concluí a leitura inicial. Organizei objetivos, entregas, riscos e decisões em um resumo editável.",
        "create_brief": "Estruturei o briefing em uma versão editável. Os poucos pontos em aberto continuam destacados.",
        "create_meeting_summary": "Organizei a reunião em uma ata editável. Revise decisões e pendências antes de salvar no projeto.",
        "create_meeting_agenda": "Preparei a pauta editável. Ajuste os temas e o resultado esperado de cada bloco.",
        "create_text_draft": "Organizei o conteúdo completo em um documento editável, com título e seções para facilitar a leitura. Revise antes de salvar no projeto.",
        "create_link_summary": "Preparei um resumo editável do conteúdo disponível.",
        "create_client_delivery": "Organizei o conteúdo em uma entrega privada e editável, pronta para sua revisão.",
        "create_substantial_delivery": "Organizei o conteúdo completo em um documento editável para facilitar a revisão.",
        "save_to_project": "Organizei o conteúdo referenciado em um documento editável dentro do projeto ativo.",
    }.get(route.action, "Organizei o resultado em uma versão editável para você revisar.")
    policy["artifact_scope"] = "session" if route.action in {
        "create_text_draft", "create_client_delivery", "create_substantial_delivery"
    } else "context"
    resolved = resolve_context(route, request, routed_message, load_builtin_tools(), execution_mode)
    if route.action == "schedule_project_meeting":
        google_status = resolved.values.get("google.get_connector_status") or {}
        shares = resolved.values.get("workspace.list_project_shares") or {}
        connector_ready = google_status.get("next_step") == "ready"
        active_members = [item for item in shares.get("members") or []
                          if item.get("status") == "active" and item.get("email")]
        policy["action_preflight"] = {
            "ready": connector_ready and bool(active_members),
            "connector_ready": connector_ready,
            "active_recipient_count": len(active_members),
            "external_effect": "Envia convites do Calendar para a equipe do projeto.",
        }
        if not connector_ready or not active_members:
            route = replace(route, action=("connect_google_for_meeting" if not connector_ready
                                           else "complete_project_team_for_meeting"),
                            response_mode="clarification", requires_confirmation=False, needs_tools=())
            policy["allow_artifact"] = False
            policy["artifact_type"] = None
    # A failed or incomplete link must stop before artifact fallback. The
    # provider may still explain the issue, but it must not manufacture a
    # document from an unavailable page.
    if route.action == "create_link_summary":
        reads = [call for call in resolved.tool_calls if call.get("name") == "web.read"]
        if not reads or any(call.get("status") != "completed" for call in reads):
            route = replace(route, action="clarify_link", response_mode="clarification", artifact_type=None, needs_tools=())
            policy = policy_for(route)
            policy["execution_mode"] = execution_mode
            policy["max_output_tokens"] = budget.max_output_tokens
            policy["max_duration_ms"] = budget.max_duration_ms
            policy["artifact_type"] = None
            policy["allow_artifact"] = False
    planning_message = routed_message
    selected = getattr(request, "selected_context", None)
    if route.action in {"update_project_context", "create_project"} and selected:
        selected_text = str(selected.get("text") or "")
        if selected.get("type") == "conversation_turn":
            try:
                selected_turn = json.loads(selected_text)
                previous_request = str(selected_turn.get("latest_user_request") or "").strip()
                if previous_request:
                    selected_text = previous_request
            except (TypeError, ValueError):
                pass
        # Keep the explicit current command as well as the referenced payload.
        # The planner can therefore understand "criar projeto com esses dados"
        # without relying on a provider session or silently dropping the turn.
        planning_message = f"{selected_text}\n{routed_message}".strip()
    plan = build_task_plan(route, budget, planning_message)
    has_action = any(step.get("kind") == "action" for step in plan)
    if route.action == "schedule_project_meeting" and not has_action:
        policy["action_preflight"] = {
            **(policy.get("action_preflight") or {}), "ready": False,
            "missing": ["data e horário futuros"],
        }
    if route.requires_confirmation and not has_action and not route.artifact_type:
        original_action = route.action
        route = replace(route, action=f"clarify_{original_action}", response_mode="clarification",
                        requires_confirmation=False, needs_tools=())
        execution_mode = execution_mode_for(route, requested_mode)
        budget = budget_for(route, execution_mode)
        policy = policy_for(route)
        policy["execution_mode"] = execution_mode
        policy["max_output_tokens"] = budget.max_output_tokens
        policy["max_duration_ms"] = budget.max_duration_ms
        policy["action_preflight"] = {
            "ready": False,
            "reason": "A operação precisa de dados suficientes para gerar uma ação confirmável.",
            "original_action": original_action,
        }
        if original_action == "create_brand":
            missing = []
            if not re.search(r"\bmarca(?:\s+nova)?\s*(?:chamada|nomeada|:)?\s*[\"“]?[^\"”\n,;]{2,150}", planning_message, re.IGNORECASE):
                missing.append("nome da marca")
            if not re.search(r"\b(?:site|website|endere[cç]o)\s*(?:oficial)?\s*(?::|=)?\s*(?:https?://|www\.)", planning_message, re.IGNORECASE):
                missing.append("site oficial")
            if not re.search(r"\b(?:setor|segmento|ramo)\s*(?:de|da|do|:|=)?\s*\S+", planning_message, re.IGNORECASE):
                missing.append("segmento")
            policy["action_preflight"]["missing"] = missing
        plan = build_task_plan(route, budget, routed_message)
    payload = build_payload(message=message, request=request, route=route,
                            resolved=resolved.values, policy=policy,
                            user_label="user-" + str(request.user_id), history=history,
                            execution_mode=execution_mode, max_context_chars=budget.max_context_chars,
                            selected_context=getattr(request, "selected_context", None),
                            conversation_state=conversation_state)
    return {
        "route": route.to_dict(), "execution_mode": execution_mode,
        "budget": asdict(budget), "policy": policy,
        "plan": plan, "resolved_context": resolved,
        "selected_context": getattr(request, "selected_context", None),
        "provider_payload": payload,
    }
