"""Compose a V2 run without coupling orchestration to Flask routes or Dify."""

import json
import re
from dataclasses import asdict, replace
from typing import Optional
from urllib.parse import urlsplit

from .context_resolver import public_web_query, resolve_context
from .prompt_assembler import build_payload
from .response_policy import budget_for, policy_for, requested_answer_chars, requested_output_tokens
from .router import route_request
from .task_planner import build_task_plan
from .contracts import execution_mode_for
from . import plugins
from .daily_workflows import recent_preferences
from ..mcp.registry import load_builtin_tools
from ...db import close_db


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


def _market_radar_query(brand: dict) -> str:
    """Build a public query from approved brand fields, never private project notes."""
    name = " ".join(str(brand.get("name") or "").split())[:100]
    sector = " ".join(str(brand.get("sector") or "").split())[:60]
    market = brand.get("market") if isinstance(brand.get("market"), dict) else {}
    competitors = market.get("competitors") or []
    if isinstance(competitors, str):
        competitors = re.split(r"[,;\n]+", competitors)
    competitor_names = []
    for competitor in competitors:
        value = competitor.get("name") if isinstance(competitor, dict) else competitor
        value = " ".join(str(value or "").split())[:45]
        if value and value.casefold() != name.casefold() and value not in competitor_names:
            competitor_names.append(value)
    if not name:
        return ""
    terms = [name]
    if sector:
        terms.append(sector)
    terms.extend(competitor_names[:3])
    terms.append("notícias recentes lançamentos campanhas movimentos concorrentes")
    return " ".join(terms)[:400]


def _market_radar_country(brand: dict) -> str | None:
    """Infer a search region only from an explicit country-code domain."""
    host = urlsplit(str(brand.get("website_url") or "")).hostname or ""
    suffix = host.lower().rsplit(".", 1)[-1]
    return {
        "br": "BR", "uk": "GB", "us": "US", "ca": "CA", "au": "AU", "nz": "NZ",
        "de": "DE", "fr": "FR", "es": "ES", "it": "IT", "pt": "PT", "jp": "JP",
        "in": "IN", "mx": "MX", "ar": "AR", "cl": "CL", "co": "CO", "cn": "CN",
        "kr": "KR", "nl": "NL", "za": "ZA", "ae": "AE",
    }.get(suffix)


def prepare_execution(message, request, history="", requested_mode="", conversation_state=None, routing_message=None,
                      defer_market_insights=False, has_report_attachment=False):
    routed_message = routing_message or message
    explicit_plugin = re.match(r"^/([a-z][a-z-]+)(?:\s|$)", str(message).strip())
    if explicit_plugin and explicit_plugin.group(1) in plugins.WORKFLOWS:
        routed_message = str(message).strip()[explicit_plugin.end():].strip() or "Ajude com esta tarefa."
    route = route_request(
        routed_message, request.surface, bool(request.project_ref),
        request.active_object.type if request.active_object else "", bool(request.brand_ref),
    )
    if (request.selected_context or {}).get("type") in {"artifact_ambiguity", "artifact_missing"}:
        route = replace(route, action="choose_artifact", complexity="low", response_mode="clarification",
                        needs_context=(), needs_tools=(), artifact_type=None, requires_confirmation=False)
    selected = getattr(request, "selected_context", None) or {}
    previous_text = str(selected.get("text") or "") if selected.get("type") == "assistant_response" else ""
    planning_terms = bool(re.search(
        r"\b(?:plano|planejamento|campanha)\b.{0,100}\b(?:campanha|m[ií]dia|funil|an[uú]ncios?|"
        r"or[cç]amento|verba|google|instagram|meta)\b|"
        r"\b(?:topo|meio|fundo)\s+(?:de\s+)?funil\b",
        message, re.IGNORECASE,
    ))
    planning_request = route.action == "plan_campaign" or (
        planning_terms and route.action in {
            "search_web", "analyze_plan", "answer", "create_substantial_delivery",
            "create_text_draft", "create_client_delivery",
        }
    )
    planning_followup = route.action == "reformat_previous_answer" and bool(re.search(
        r"\b(?:campanha|m[ií]dia|funil|planejamento|verba|an[uú]ncios?)\b",
        previous_text, re.IGNORECASE,
    ))
    if planning_request and route.action == "answer" and route.response_mode == "direct":
        route = replace(route, action="plan_campaign", complexity="high", response_mode="analysis")
    elif planning_request and route.action == "analyze_plan" and route.response_mode == "decision":
        route = replace(route, complexity="high", response_mode="analysis")
    elif (planning_request and route.action == "create_substantial_delivery"
          and not re.search(r"\b(?:documento|arquivo|artefato|edit[aá]vel)\b", message, re.IGNORECASE)):
        route = replace(route, action="plan_campaign", response_mode="analysis", artifact_type=None)
    plugin_message = message
    if has_report_attachment and re.search(r"\b(?:campanh\w*|relat[oó]ri\w*|resultad\w*)\b", message, re.I):
        plugin_message = "/campaign-tracker " + message
    selected_plugin, plugin_tools, plugin_missing = plugins.select(
        route, plugin_message, request, has_report_attachment=has_report_attachment,
    )
    if selected_plugin and selected_plugin.get("unavailable"):
        route = replace(route, action="plugin_unavailable", complexity="low", response_mode="direct",
                        needs_tools=(), artifact_type=None, requires_confirmation=False)
    elif plugin_missing:
        route = replace(route, action="clarify_plugin_context", response_mode="clarification",
                        needs_tools=(), artifact_type=None, requires_confirmation=False)
    elif plugin_tools:
        required_tools = (plugin_tools if selected_plugin and (selected_plugin.get("id") in plugins.WORKFLOWS or selected_plugin.get("id") in {"insights", "reports", "google-connect", "google-drive", "google-calendar", "google-meet"})
                          else tuple(dict.fromkeys((*route.needs_tools, *plugin_tools))))
        route = replace(route, needs_tools=required_tools)
    if selected_plugin and selected_plugin.get("id") in plugins.WORKFLOWS and not plugin_missing and not selected_plugin.get("unavailable"):
        route = replace(route, action="run_plugin", complexity="medium", response_mode="analysis", artifact_type=None,
                        requires_confirmation=False, needs_tools=plugin_tools)
    readiness = None
    if route.action == "create_brief":
        readiness = briefing_readiness(message, history)
        if readiness["complete"]:
            route = replace(route, response_mode="artifact_first", artifact_type="brief")
        else:
            route = replace(route, response_mode="clarification", artifact_type=None)
    if (route.action == "plan_campaign" and not requested_mode
            and re.search(r"\b(?:r[aá]pid[oa]|diret[oa]|resumid[oa]|enxut[oa]|simples)\b", message, re.I)):
        requested_mode = "fast"
    execution_mode = execution_mode_for(route, requested_mode)
    budget, policy = budget_for(route, execution_mode), policy_for(route)
    if (selected_plugin and selected_plugin.get("id") in plugins.WORKFLOWS
            and not plugin_missing and not selected_plugin.get("unavailable") and execution_mode != "fast"):
        budget = replace(budget, max_output_tokens=max(budget.max_output_tokens, 1800),
                         max_context_chars=max(budget.max_context_chars, 22000),
                         max_tool_calls=max(budget.max_tool_calls, 6))
    if route.action == "create_newsletter":
        news_count = re.search(r"\b(\d{1,2})\s+(?:not[ií]cias?|novidades?)\b", routed_message, re.I)
        policy["newsletter_news_count"] = min(8, max(1, int(news_count.group(1)))) if news_count else 4
    planning_delivery = (planning_request or planning_followup) and not (
        selected_plugin and selected_plugin.get("id") in plugins.WORKFLOWS
    )
    if planning_delivery:
        budget = replace(budget, max_output_tokens=max(budget.max_output_tokens, 4000),
                         max_context_chars=max(budget.max_context_chars, 28000))
        if route.artifact_type:
            policy["planning_artifact"] = True
        elif route.response_mode in {"analysis", "direct"}:
            policy["max_answer_chars"] = max(policy["max_answer_chars"], 18000)
            policy["planning_response"] = True
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
    if selected_plugin:
        if selected_plugin.get("unavailable"):
            policy["plugin_unavailable"] = selected_plugin["id"]
        else:
            policy["plugin"] = {**selected_plugin, "required_context_missing": plugin_missing}
        policy["plugin_instruction"] = (
            "Este plugin está ativo na conversa. Use apenas evidências e retornos MCP "
            "presentes neste turno; não afirme que uma busca, análise, geração ou gravação ocorreu sem retorno correspondente. "
            "Mantenha a resposta na conversa. Crie ou atualize artefato somente quando o usuário pedir, ou quando a rota "
            "já determinar uma entrega editável. Se faltar escopo, pergunte antes de consultar uma base privada."
        )
        if selected_plugin.get("unavailable"):
            policy["plugin_instruction"] = (
                f"O plugin {selected_plugin['name']} está temporariamente indisponível. "
                "Diga isso em uma frase, sem alegar que executou o plugin, e ofereça continuar a tarefa na conversa."
            )
            policy["max_questions"] = 0
        elif selected_plugin.get("id") in plugins.WORKFLOWS and not plugin_missing:
            policy["plugin_instruction"] += " " + plugins.WORKFLOWS[selected_plugin["id"]][4]
            policy["max_answer_chars"] = max(policy.get("max_answer_chars", 0), 7000)
            preferences = recent_preferences(request, selected_plugin["id"])
            if preferences:
                policy["plugin_instruction"] += (
                    " Preferências recorrentes desta pessoa neste projeto: " + ", ".join(preferences)
                    + ". Use-as apenas para ordenar sugestões; o pedido atual prevalece. "
                    "Se ajudar, ofereça uma única próxima ação personalizada ao final."
                )
    if plugin_missing:
        daily_next_step = None
        if selected_plugin and selected_plugin.get("id") in plugins.WORKFLOWS:
            daily_next_step = (
                "Peça em uma única pergunta o menor dado necessário para executar este plugin: "
                + ", ".join(dict.fromkeys(plugin_missing)) + "."
            )
        policy["action_preflight"] = {
            "ready": False, "missing": plugin_missing,
            "next_step": daily_next_step or (
                "Pergunte onde deve procurar: na marca ou em um projeto."
                if selected_plugin and selected_plugin.get("id") == "campaign-search"
                else "Pergunte qual tema de mercado deve orientar a busca."
                if selected_plugin and selected_plugin.get("id") == "insights"
                else "Peça para selecionar o projeto cujas informações devem ser pesquisadas."
                if selected_plugin and selected_plugin.get("id") == "project-search"
                else "Peça para selecionar o projeto cujas atividades devem ser consultadas ou organizadas."
                if selected_plugin and selected_plugin.get("id") == "project-activities"
                else "Peça para selecionar o relatório ou projeto com dados revisados."
            ),
        }
        policy["max_questions"] = 1
    if readiness:
        policy["briefing_readiness"] = readiness
    policy["artifact_fallback_title"] = {
        "project_readout": "Dossiê do projeto",
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
        "project_readout": "Organizei as informações do projeto em um dossiê com seções e fontes. Abra o material para ler ou editar.",
        "create_brief": "Estruturei o briefing em uma versão editável. Os poucos pontos em aberto continuam destacados.",
        "create_meeting_summary": "Organizei a reunião em uma ata editável. Revise decisões e pendências antes de salvar no projeto.",
        "create_meeting_agenda": "Preparei a pauta editável. Ajuste os temas e o resultado esperado de cada bloco.",
        "create_text_draft": "Organizei o conteúdo completo em um documento editável, com título e seções para facilitar a leitura. Revise antes de salvar no projeto.",
        "create_link_summary": "Preparei um resumo editável do conteúdo disponível.",
        "create_client_delivery": "Organizei o conteúdo em uma entrega privada e editável, pronta para sua revisão.",
        "create_substantial_delivery": "Organizei o conteúdo completo em um documento editável para facilitar a revisão.",
        "save_to_project": "Organizei o conteúdo referenciado em um documento editável dentro do projeto ativo.",
    }.get(route.action, "Atualizei o documento existente com as decisões desta conversa." if route.action.startswith("update_") and route.artifact_type else "Organizei o resultado em uma versão editável para você revisar.")
    policy["require_artifact_patch"] = bool(route.action.startswith("update_") and route.artifact_type)
    policy["artifact_scope"] = "session" if route.action in {
        "create_text_draft", "create_client_delivery", "create_substantial_delivery"
    } else "context"
    project_web = route.action == "search_web" and bool(request.project_ref)
    resolution_route = replace(route, needs_tools=("workspace.search_project_content",)) if project_web else route
    deferred_tools = ()
    if defer_market_insights and route.action == "search_insights" and "insights.research_market" in route.needs_tools:
        deferred_tools = ("insights.research_market",)
        resolution_route = replace(route, needs_tools=tuple(
            tool for tool in route.needs_tools if tool != "insights.research_market"
        ))
    registry = load_builtin_tools()
    market_radar = bool(selected_plugin and selected_plugin.get("id") == "market-radar"
                        and route.action == "run_plugin")
    if market_radar:
        # Resolve project and linked brand first. Do not fire the public search
        # until we can scope it to the selected brand.
        resolution_route = replace(resolution_route, needs_tools=tuple(
            tool for tool in resolution_route.needs_tools if tool != "web.search"
        ))
    resolved = resolve_context(resolution_route, request, routed_message, registry, execution_mode)
    if market_radar:
        brand = resolved.values.get("brands.get_context")
        if isinstance(brand, dict) and brand.get("name"):
            radar_query = _market_radar_query(brand)
            if radar_query:
                radar_route = replace(route, needs_tools=("web.search",))
                close_db()
                external = resolve_context(
                    radar_route, request, radar_query, registry, execution_mode,
                    tool_argument_overrides={"web.search": {
                        "query": radar_query, "recency": "year", "limit": 8,
                        "country": _market_radar_country(brand),
                    }},
                )
                resolved.values.update({key: value for key, value in external.values.items() if key != "current_context"})
                resolved.missing.extend(external.missing)
                resolved.tool_calls.extend(external.tool_calls)
                if external.missing:
                    resolved.values["tool_status"] = {
                        "unavailable": list(dict.fromkeys(resolved.missing)),
                        "message": "A busca pública focada na marca não ficou disponível nesta resposta.",
                    }
            else:
                resolved.values["brand_context_status"] = "missing_brand_name"
        else:
            resolved.values["brand_context_status"] = "unavailable_or_not_unique"
            route = replace(
                route, action="clarify_plugin_context", complexity="low",
                response_mode="clarification", needs_tools=(), artifact_type=None,
                requires_confirmation=False,
            )
            policy.update({
                "mode": "clarification", "max_questions": 1,
                "max_next_steps": 1, "max_answer_chars": 360,
                "artifact_type": None, "allow_artifact": False,
            })
            policy["action_preflight"] = {
                "ready": False,
                "reason": "Não foi possível resolver uma única marca vinculada ao projeto selecionado.",
                "missing": ["marca única vinculada ao projeto"],
                "next_step": "Peça para selecionar ou vincular a marca correta ao projeto e só então inicie a pesquisa.",
            }
            policy["plugin_instruction"] = (
                "O Radar de mercado não foi executado porque não foi possível resolver uma marca única para este projeto. "
                "Explique essa pendência sem dizer que o projeto não tem vínculo; peça para selecionar ou vincular a marca correta. "
                "Não apresente achados, links ou recomendações de mercado nesta etapa."
            )
    internal_search = resolved.values.get("workspace.search_project_content") or {}
    public_query = public_web_query(routed_message, project_selected=bool(request.project_ref))
    explicit_external = bool(re.search(
        r"\b(?:pesquis\w*|busqu\w*|investig\w*|consult\w*)\b.{0,80}"
        r"\b(?:internet|web|online|fontes? externas?)\b|"
        r"\b(?:internet|web|online|fontes? externas?)\b.{0,80}"
        r"\b(?:pesquis\w*|busqu\w*|investig\w*|consult\w*)\b",
        routed_message, re.IGNORECASE))
    needs_current_facts = bool(re.search(
        r"\b(?:hoje|atuais?|recentes?|202[5-9]|pre[cç]os?|cota[cç][aã]o|not[ií]cias?)\b",
        routed_message, re.IGNORECASE))
    internal_has_evidence = bool((internal_search.get("results") or []) if isinstance(internal_search, dict) else [])
    should_search_public = bool(public_query) and (
        (project_web and (explicit_external or needs_current_facts or not internal_has_evidence))
        or (route.action == "search_project" and not internal_has_evidence)
    )
    if project_web and not public_query:
        resolved.values["external_search_skipped"] = (
            "O pedido mistura contexto privado e tema público sem uma consulta externa segura. "
            "Use somente a evidência interna e não afirme ter pesquisado a internet."
        )
    if should_search_public:
        close_db()
        external = resolve_context(replace(route, needs_tools=("web.search",)), request,
                                   public_query, registry, execution_mode)
        resolved.values.update({key: value for key, value in external.values.items() if key != "current_context"})
        resolved.missing.extend(external.missing)
        resolved.tool_calls.extend(external.tool_calls)
        if external.missing:
            resolved.values["tool_status"] = {
                "unavailable": list(dict.fromkeys(resolved.missing)),
                "message": "A pesquisa pública complementar não ficou disponível nesta resposta.",
            }
    if route.action == "select_brand_for_audit":
        # Do not leave a provider enough latitude to turn an unbound request
        # into an unsupported brand analysis. The next safe action is a
        # registered, selected brand; evidence sent in chat can be attached
        # afterwards.
        policy["action_preflight"] = {
            "ready": False,
            "reason": "A análise só pode ser executada para uma marca cadastrada e selecionada.",
            "missing": ["marca cadastrada e selecionada"],
            "next_step": "Cadastre ou selecione a marca; para o cadastro, informe nome, segmento e site oficial.",
        }
        policy["max_answer_chars"] = min(policy.get("max_answer_chars", 260), 260)
        policy["max_questions"] = 1
        policy["max_next_steps"] = 1
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
            policy["action_preflight"]["next_step"] = (
                "Entendi: você quer criar uma nova marca, acima do projeto atual. "
                "Vou separar isso em uma conversa pessoal; para iniciar, informe nome, segmento e site oficial. "
                "Os anexos e referências desta conversa serão preservados como base."
            )
        plan = build_task_plan(route, budget, routed_message)
    payload = build_payload(message=message, request=request, route=route,
                            resolved=resolved.values, policy=policy,
                            user_label="user-" + str(request.user_id), history=history,
                            execution_mode=execution_mode, max_context_chars=budget.max_context_chars,
                            selected_context=getattr(request, "selected_context", None),
                            conversation_state=conversation_state)
    provider_evidence = json.loads(payload["inputs"]["evidence"])
    project_tools = ("workspace.search_project_content", "workspace.get_project_context")
    payload_diagnostics = {
        "project_bound": bool(request.project_ref),
        "project_ref_in_current_context": json.loads(payload["inputs"]["current_context"]).get("project_ref") == request.project_ref,
        "project_evidence_tools": [name for name in project_tools if name in provider_evidence],
        "evidence_truncated": bool(provider_evidence.get("truncated")),
        "evidence_chars": len(payload["inputs"]["evidence"]),
    }
    return {
        "route": route.to_dict(), "execution_mode": execution_mode,
        "budget": asdict(budget), "policy": policy,
        "plan": plan, "resolved_context": resolved,
        "deferred_tools": deferred_tools,
        "selected_context": getattr(request, "selected_context", None),
        "provider_payload": payload,
        "payload_diagnostics": payload_diagnostics,
    }
