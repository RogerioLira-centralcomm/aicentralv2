"""Compose a V2 run without coupling orchestration to Flask routes or Dify."""

from dataclasses import asdict

from .context_resolver import resolve_context
from .prompt_assembler import build_payload
from .response_policy import budget_for, policy_for
from .router import route_request
from .task_planner import build_task_plan
from .contracts import execution_mode_for
from ..mcp.registry import load_builtin_tools


def prepare_execution(message, request, history="", requested_mode=""):
    route = route_request(
        message, request.surface, bool(request.project_ref),
        request.active_object.type if request.active_object else "",
    )
    execution_mode = execution_mode_for(route, requested_mode)
    budget, policy = budget_for(route, execution_mode), policy_for(route)
    policy["execution_mode"] = execution_mode
    policy["max_output_tokens"] = budget.max_output_tokens
    policy["max_duration_ms"] = budget.max_duration_ms
    policy["artifact_type"] = route.artifact_type
    policy["artifact_fallback_title"] = {
        "project_readout": "Leitura inicial do projeto",
        "create_brief": "Briefing do projeto",
    }.get(route.action, "Resultado do trabalho")
    policy["artifact_chat_message"] = {
        "project_readout": "Concluí a leitura inicial. Organizei objetivos, entregas, riscos e decisões no artefato ao lado.",
        "create_brief": "Estruturei o briefing no artefato ao lado. Os pontos em aberto continuam editáveis.",
    }.get(route.action, "Organizei o resultado no artefato ao lado para você revisar e editar.")
    resolved = resolve_context(route, request, message, load_builtin_tools())
    payload = build_payload(message=message, request=request, route=route,
                            resolved=resolved.values, policy=policy,
                            user_label="user-" + str(request.user_id), history=history,
                            execution_mode=execution_mode, max_context_chars=budget.max_context_chars,
                            selected_context=getattr(request, "selected_context", None))
    return {
        "route": route.to_dict(), "execution_mode": execution_mode,
        "budget": asdict(budget), "policy": policy,
        "plan": build_task_plan(route, budget, message), "resolved_context": resolved,
        "selected_context": getattr(request, "selected_context", None),
        "provider_payload": payload,
    }
