"""Bounded deterministic task plans; simple turns never invoke a planner LLM."""

import json
import re
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from .contracts import ExecutionBudget, IntentRoute
from ..meeting_reference import parse_meeting_invite
from ..reference_context import clean_user_message


def _project_meeting_step(message: str, now=None):
    """Plan a meeting only when date and time are explicit enough to seal."""
    text = str(message or "")
    current = now or datetime.now(ZoneInfo("America/Sao_Paulo"))
    time_match = re.search(r"\b(?:[àa]s?\s*)?(\d{1,2})(?::|h)(\d{2})?\b", text, re.IGNORECASE)
    date_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if not time_match:
        return None
    hour, minute = int(time_match.group(1)), int(time_match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        year = int(date_match.group(3) or current.year)
        year += 2000 if year < 100 else 0
        try:
            meeting_date = current.date().replace(year=year, month=month, day=day)
        except ValueError:
            return None
    elif re.search(r"\bamanh[aã]\b", text, re.IGNORECASE):
        meeting_date = current.date() + timedelta(days=1)
    elif re.search(r"\b(?:hoje|hj)\b", text, re.IGNORECASE):
        meeting_date = current.date()
    else:
        return None
    starts = datetime.combine(meeting_date, datetime.min.time(), current.tzinfo).replace(hour=hour, minute=minute)
    if starts <= current:
        return None
    duration_match = re.search(r"\b(?:por|dura(?:[cç][aã]o)?\s*(?:de)?)\s*(\d{1,3})\s*(min(?:utos?)?|h(?:oras?)?)\b", text, re.IGNORECASE)
    duration = 60
    if duration_match:
        duration = int(duration_match.group(1)) * (60 if duration_match.group(2).lower().startswith("h") else 1)
    duration = min(max(duration, 15), 480)
    title_match = re.search(r"\b(?:reuni[aã]o|meet)\s+(?:sobre|para|de)\s+([^,.;\n]{2,120})", text, re.IGNORECASE)
    title = "Reunião do projeto" if not title_match else "Reunião: " + title_match.group(1).strip()
    ends = starts + timedelta(minutes=duration)
    return {
        "kind": "action", "name": "google.create_project_meeting", "requires_confirmation": True,
        "request_id": str(uuid4()), "effect": "write",
        "arguments": {"title": title[:300], "starts_at": starts.isoformat(), "ends_at": ends.isoformat(),
                      "timezone": "America/Sao_Paulo"},
        "summary": f"Criar Meet em {starts.strftime('%d/%m/%Y às %H:%M')} ({duration} min) e convidar a equipe ativa do projeto.",
    }


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
    name = re.split(
        r"\s+(?:com\s+(?:links?|fontes?|arquivos?|documentos?|acesso|visibilidade)|privado|compartilhado|aberto\s+para)\b",
        " ".join(match.group(1).split()), maxsplit=1, flags=re.IGNORECASE,
    )[0].strip(' -:;,."')
    if len(name) < 2:
        return None
    text = str(message or "")
    urls = []
    for value in re.findall(r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?", text, re.IGNORECASE):
        url = value.rstrip(".,;:)")
        if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE):
            url = "https://" + url
        urls.append({"url": url})
    visibility = "team" if re.search(r"\b(?:toda\s+a\s+equipe|equipe\s+inteira|aberto\s+para\s+(?:a\s+)?equipe)\b", text, re.IGNORECASE) else "private"
    arguments = {"name": name[:150]}
    if visibility != "private":
        arguments["visibility"] = visibility
    if urls:
        arguments["links"] = urls[:20]
    if re.search(r"\b(?:anex|envi|adicion)\w*.{0,30}\b(?:arquivos?|documentos?|fontes?)\b", text, re.IGNORECASE):
        arguments["file_uploads"] = [{"use_as_knowledge": True}]
    return {
        "kind": "action", "name": "workspace.create_project", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": arguments, "effect": "write",
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


def _project_rename_step(message: str):
    """Extract only the requested new name; the UI will confirm the mutation."""
    text = " ".join(str(message or "").split())
    match = re.search(
        r"\b(?:mud|alter|troc|renome)\w*\b(?:\s+o)?(?:\s+nome)?(?:\s+(?:do|deste)\s+projeto)?"
        r"(?:\s+de\s+.+?)?\s+para\s+[\"“]?(.+?)[\"”]?(?:[.!?]|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    name = match.group(1).strip(' -:;,."“”')
    if len(name) < 2:
        return None
    name = name[:150]
    return {
        "kind": "action", "name": "workspace.update_project_context",
        "requires_confirmation": True, "request_id": str(uuid4()),
        "arguments": {"name": name}, "effect": "write",
        "summary": f"Renomear o projeto atual para “{name}”.",
    }


def _section(text: str, labels: str) -> str:
    match = re.search(
        rf"(?:^|\n)\s*(?:#+\s*)?(?:{labels})\s*:?[ \t]*\n(.+?)(?=\n\s*(?:#+\s*)?[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n]{{1,80}}\s*:?[ \t]*\n|\Z)",
        text, re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _project_context_step(message: str):
    """Build a bounded patch from explicit project data, including variable fields."""
    text = str(message or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            selected = json.loads(text)
            if isinstance(selected, dict) and selected.get("type") == "conversation_turn":
                prior = str(selected.get("latest_assistant_answer") or "")
                turns = "\n\n".join(str(item.get("content") or "") for item in selected.get("recent_turns") or []
                                     if isinstance(item, dict))
                text = "\n\n".join(value for value in (prior, turns) if value)
        except (TypeError, ValueError):
            pass
    payload = {}
    name_match = re.search(
        r"(?:^|\n)\s*(?:#+\s*)?(?:nome do projeto|projeto)\s*:\s*\*{0,2}([^\n*]{2,150})",
        text, re.IGNORECASE,
    )
    if name_match:
        payload["name"] = " ".join(name_match.group(1).strip(" .—-*\"").split())[:150]
    description = _section(text, r"descri[cç][aã]o|foco do projeto")
    if description:
        payload["description"] = description[:4000]
    instructions = _section(text, r"diretrizes? operacionais?|regras? de opera[cç][aã]o|dire[cç][aã]o estrat[eé]gica")
    if instructions:
        payload["instructions"] = instructions[:12000]
    custom = []
    sections = (
        ("objetivo", "Objetivo", r"objetivo(?: principal| central)?"),
        ("canais", "Canais", r"canais?(?: de m[ií]dia)?(?: inclu[ií]dos)?"),
        ("estrutura_de_funil", "Estrutura de funil", r"estrutura(?: estrat[eé]gica| de funil)|etapas? do funil"),
        ("orcamento_mensal", "Orçamento mensal", r"or[cç]amento(?: mensal)?|diretriz de or[cç]amento"),
        ("restricoes", "Restrições", r"restri[cç][oõ]es?(?: do projeto)?"),
        ("indicadores", "Indicadores", r"indicadores?(?: principais)?|crit[eé]rios? de acompanhamento|kpis?"),
    )
    for key, label, aliases in sections:
        value = _section(text, aliases)
        if value:
            custom.append({"key": key, "label": label, "value": value[:12000]})
    budget = re.search(r"(?:R\$\s*)?[\d.]+(?:,\d{1,2})?\s*(?:por\s+m[eê]s|/\s*m[eê]s|mensais?)", text, re.IGNORECASE)
    if budget and not any(item["key"] == "orcamento_mensal" for item in custom):
        custom.append({"key": "orcamento_mensal", "label": "Orçamento mensal", "value": budget.group(0)})
    channels = [name for name in ("Google Ads", "Instagram Ads", "Facebook Ads", "LinkedIn Ads", "TikTok Ads")
                if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)]
    if channels and not any(item["key"] == "canais" for item in custom):
        custom.append({"key": "canais", "label": "Canais", "value": channels})
    generic_pattern = re.compile(
        r"\b(?:adicion|inclu|cri|atualiz|alter|mud)\w*\b\s+(?:o\s+)?(?:campo|item|dado)\s+[\"“]?"
        r"([^\"”:\n]{1,120})[\"”]?\s*(?:para|como|com|:)\s*(.+?)"
        r"(?=(?:[.;!?]\s*|,\s*|\s+e\s+)(?:adicion|inclu|cri|atualiz|alter|mud)\w*\b\s+(?:o\s+)?(?:campo|item|dado)\b|[.!?]?$)",
        re.IGNORECASE,
    )
    for generic in generic_pattern.finditer(text):
        label = " ".join(generic.group(1).strip(" -:;,.").split())[:120]
        value = re.split(r"\s+(?:na|no|da|do)\s+(?:dire[cç][aã]o|contexto|projeto)\b",
                         generic.group(2), maxsplit=1, flags=re.IGNORECASE)[0].strip(" \n-:;,. ")[:12000]
        if label and value:
            custom.append({"key": label, "label": label, "value": value})
    removal = re.search(
        r"\b(?:remov|exclu|apag)\w*\b\s+(?:o\s+)?(?:campo|item|dado)\s+[\"“]?"
        r"([^\"”.,;:\n]{1,120})",
        text, re.IGNORECASE,
    )
    if removal:
        payload["remove_custom_fields"] = [removal.group(1).strip()]
    if custom:
        payload["custom_fields"] = custom
    replace_context = bool(re.search(r"\b(?:completamente|do zero|substitu\w*|novo contexto|deixar de ser)\b", text, re.IGNORECASE))
    if replace_context:
        payload["replace_custom_fields"] = True
    if not payload:
        return None
    return {
        "kind": "action", "name": "workspace.update_project_context", "requires_confirmation": True,
        "request_id": str(uuid4()), "arguments": payload, "effect": "write",
        "summary": "Atualizar os dados do projeto atual" + (" e substituir seu contexto anterior." if replace_context else "."),
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


def _project_link_step(message: str):
    meeting = parse_meeting_invite(message)
    match = re.search(r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?",
                      str(message or ""), re.IGNORECASE)
    if not match:
        return None
    url = match.group(0).rstrip(".,;:)")
    if not re.match(r'^[a-z][a-z0-9+.-]*://', url, re.IGNORECASE):
        url = f'https://{url}'
    approve_for_me = bool(re.search(
        r"\b(?:aprovar?\s+por\s+mim|pode\s+aprovar|sem\s+(?:pedir\s+)?confirma[cç][aã]o)\b",
        str(message or ""), re.IGNORECASE,
    ))
    arguments = {"url": meeting["url"] if meeting else url, "user_message": clean_user_message(message)[:5000]}
    if meeting:
        arguments.update({
            "title": meeting["title"], "resource_kind": "meeting",
            "platform": meeting["platform"], "external_id": meeting["external_id"],
            "meeting": {key: meeting[key] for key in (
                "starts_at", "ends_at", "timezone", "year_inferred", "dial_in", "pin", "related_urls"
            )},
            "tags": ["reunião", meeting["platform"]],
        })
    return {
        "kind": "action", "name": "projects.create_link_reference", "requires_confirmation": not approve_for_me,
        "request_id": str(uuid4()), "arguments": arguments, "effect": "write",
        "summary": (f"Salvar a reunião “{meeting['title']}” como fonte estruturada do projeto."
                    if meeting else "Salvar o link no projeto e deixar o indexador classificar e organizar seus metadados."),
    }


def _brand_create_step(message: str):
    text = str(message or "")
    url_match = re.search(r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?", text, re.IGNORECASE)
    name_match = re.search(r"\bmarca\s*(?:chamada|nomeada|:)?\s*[\"“]?([^\"”\n,;]{2,150})", text, re.IGNORECASE)
    if not url_match or not name_match:
        return None
    url = url_match.group(0).rstrip(".,;:)")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE):
        url = "https://" + url
    name = re.split(r"\s+(?:com|site|website)\s+", name_match.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip(" .:-")
    if len(name) < 2:
        return None
    return {"kind": "action", "name": "brands.create", "requires_confirmation": True,
            "request_id": str(uuid4()), "arguments": {"name": name[:150], "website_url": url},
            "effect": "write", "summary": f"Criar a marca “{name[:150]}” neste cliente e vincular seu projeto."}


def _brand_audit_step(message: str):
    mode = "deep" if re.search(r"\b(profunda|profundo|deep)\b", str(message or ""), re.IGNORECASE) else "complete"
    return {"kind": "action", "name": "brands.start_audit", "requires_confirmation": True,
            "request_id": str(uuid4()), "arguments": {"analysis_mode": mode, "confirmed_cost": True},
            "effect": "write", "summary": f"Iniciar auditoria {'profunda' if mode == 'deep' else 'completa'} da marca ativa, com uso de créditos."}


def _brand_identity_step(message: str):
    """Extract one explicit field/value pair; ambiguous edits stay conversational."""
    text = " ".join(str(message or "").split())
    aliases = (
        (r"nome(?: da marca)?", "name", False), (r"setor", "sector", False),
        (r"site(?: oficial)?|website", "website_url", False),
        (r"cor principal", "primary_color", False), (r"cor secund[aá]ria", "secondary_color", False),
        (r"ess[eê]ncia|resumo(?: da marca)?|descri[cç][aã]o(?: da marca)?", "brand_summary", False),
        (r"posicionamento", "positioning", False), (r"p[uú]blico(?:-alvo)?|p[uú]blico e contexto", "target_audience", False),
        (r"tom(?: de voz)?|tom e linguagem", "tone_of_voice", False),
        (r"dire[cç][aã]o criativa", "creative_guidelines", False),
        (r"produtos? e servi[cç]os?|oferta(?: priorit[aá]ria)?", "products_services", True),
        (r"diferenciais?", "differentiators", True), (r"provas? e sinais?", "proof_points", True),
    )
    for label, field, is_list in aliases:
        match = re.search(rf"\b(?:{label})\b\s*(?:para|por|como|:|=)\s*[\"“]?(.+?)[\"”]?(?:\s*$)", text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip(" .\"“”")
        if not value:
            return None
        if is_list:
            value = [item.strip() for item in re.split(r"\s*(?:,|;|\be\b)\s*", value, flags=re.IGNORECASE) if item.strip()]
        return {"kind": "action", "name": "brands.update_identity", "requires_confirmation": True,
                "request_id": str(uuid4()), "arguments": {"changes": {field: value}}, "effect": "write",
                "summary": f"Alterar somente {field} na identidade da marca ativa."}
    return None


def build_task_plan(route: IntentRoute, budget: ExecutionBudget, message: str = "") -> list[dict]:
    # The plan is user-facing. It must remain understandable in the chat.
    # Reserve the fourth slot for the response itself. The user should never
    # see preparation without the outcome that preparation produces.
    steps = [{"kind": "tool", "name": name} for name in route.needs_tools[:2]]
    if route.action == "link_test":
        action = _link_test_step(message)
        if action:
            steps.append(action)
    if route.action == "schedule_project_meeting":
        action = _project_meeting_step(message)
        if action:
            steps.append(action)
    if route.action == "create_project":
        action = _create_project_step(message)
        if action:
            steps.append(action)
    if route.action == "set_project_status":
        steps.append(_project_status_step(message))
    if route.action == "rename_project":
        action = _project_rename_step(message)
        if action:
            steps.append(action)
    if route.action == "update_project_context":
        action = _project_context_step(message)
        if action:
            steps.append(action)
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
    if route.action == "create_project_link":
        action = _project_link_step(message)
        if action:
            steps.append(action)
    if route.action == "create_brand":
        action = _brand_create_step(message)
        if action:
            steps.append(action)
    if route.action == "update_brand_identity":
        action = _brand_identity_step(message)
        if action:
            steps.append(action)
    if route.action == "prepare_brand_logo_upload":
        steps.append({"kind": "action", "name": "brands.prepare_logo_upload",
                      "requires_confirmation": False, "request_id": str(uuid4()),
                      "arguments": {}, "effect": "draft",
                      "summary": "Preparar o envio ou a substituição do logo principal da marca ativa."})
    if route.action == "start_brand_audit":
        steps.append(_brand_audit_step(message))
    if route.artifact_type and len(steps) < 3:
        steps.append({"kind": "artifact", "action": route.action, "type": route.artifact_type,
                      "requires_confirmation": route.requires_confirmation})
    return steps[:3] + [{"kind": "generate", "response_mode": route.response_mode}]
