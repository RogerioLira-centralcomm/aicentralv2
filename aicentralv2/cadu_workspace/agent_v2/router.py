"""Deterministic first-pass router for common Cadu work.

Routing here costs no model call.  An ambiguity classifier may be introduced
later, but only for messages that fall through these product-level intents.
"""

import re
from urllib.parse import urlparse

from .contracts import IntentRoute
from ..conversations.guardrails import normalize_colloquial
from ..intent_engine import interpret as interpret_canonical_intent


def _has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def _usable_public_url(value: str) -> bool:
    """Accept only complete public HTTP(S) URLs before planning extraction."""
    candidate = str(value or '').strip().rstrip('.,;:)')
    if not re.match(r'^[a-z][a-z0-9+.-]*://', candidate, re.IGNORECASE):
        candidate = f'https://{candidate}'
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return False
    host = (parsed.hostname or '').lower().rstrip('.')
    return (
        parsed.scheme in {'http', 'https'}
        and bool(host)
        and '.' in host
        and ' ' not in host
        and not parsed.username
        and not parsed.password
    )


def _explicit_artifact_creation_refusal(text: str) -> bool:
    """Detect a refusal to create/open an artifact, independently of persistence."""
    return _has(
        text,
        r"\b(?:n[aã]o|ainda\s+n[aã]o|sem)\b.{0,55}"
        r"\b(?:cri\w*|ger\w*|abr\w*|mont\w*|transform\w*)\b.{0,55}"
        r"\b(?:artefato|documento|rascunho)\b",
    ) or _has(
        text,
        r"\b(?:sem|n[aã]o)\s+(?:artefato|documento|rascunho)\b",
    )


def _project_persistence_refusal(text: str) -> bool:
    """Keep a session artifact possible when only project persistence is forbidden."""
    return _has(
        text,
        r"\b(?:n[aã]o|ainda\s+n[aã]o|sem)\b.{0,45}"
        r"\b(?:salv\w*|adicion\w*|envi\w*|vincul\w*)\b.{0,45}\bprojeto\b",
    )


def _web_requires_confirmation(text: str) -> bool:
    return _has(
        text,
        r"\b(?:pesquis\w*|busqu\w*|consult\w*)\b.{0,90}"
        r"\b(?:se|quando|ap[oó]s|mediante|com)\b.{0,25}"
        r"\b(?:eu\s+)?(?:autoriz\w*|der\s+permiss[aã]o|permit\w*)\b",
    ) or _has(
        text,
        r"\bantes\s+de\s+(?:pesquis\w*|busqu\w*|consult\w*)\b.{0,70}"
        r"\b(?:pergunt\w*|confirm\w*|autoriz\w*)\b",
    )


def _destructive_request_is_negated(text: str) -> bool:
    return _has(
        text,
        r"\b(?:n[aã]o|nunca|jamais|sem)\b.{0,35}\b(?:apag|exclu|delet|remov|mescl|fund)\w*\b",
    )


def route_request(message: str, surface: str = "conversations", has_project: bool = False,
                  active_object_type: str = "", has_brand: bool = False) -> IntentRoute:
    text = normalize_colloquial(message)[:20000]
    forbid_project_persistence = _project_persistence_refusal(text)

    if not _destructive_request_is_negated(text):
        if _has(text, r"\b(?:mescl|fund)\w*\b.{0,45}\bprojetos?\b|\bprojetos?\b.{0,45}\b(?:mescl|fund)\w*\b"):
            return IntentRoute("workspace", "open_project_merge" if has_project else "select_project_for_merge",
                               "low", "direct" if has_project else "clarification", ("project",) if has_project else ())
        if _has(text, r"\b(?:apag|exclu|delet|remov)\w*\b.{0,45}\bmarca\b|\bmarca\b.{0,45}\b(?:apag|exclu|delet|remov)\w*\b"):
            return IntentRoute("workspace", "open_brand_delete" if has_brand else "select_brand_for_delete",
                               "low", "direct" if has_brand else "clarification", ("brand",) if has_brand else ())
        if _has(text, r"\b(?:apag|exclu|delet|remov)\w*\b.{0,45}\bprojeto\b|\bprojeto\b.{0,45}\b(?:apag|exclu|delet|remov)\w*\b"):
            return IntentRoute("workspace", "open_project_delete" if has_project else "select_project_for_delete",
                               "low", "direct" if has_project else "clarification", ("project",) if has_project else ())

    # Negative constraints are requirements, not weak hints. Resolve them
    # before rules such as "salve ... projeto" can match the same sentence.
    if _web_requires_confirmation(text):
        return IntentRoute("research", "confirm_web_research", "low", "clarification",
                           ("project", "brand") if has_project else (), (), None, False)
    if _explicit_artifact_creation_refusal(text):
        web_requested = _has(text, r"\b(?:pesquis\w*|busqu\w*|consult\w*)\b") and _has(
            text, r"\b(?:internet|web|online|fontes?\s+externas?|dados?\s+atuais?)\b",
        )
        return IntentRoute(
            "research" if web_requested else (surface if surface != "conversations" else "workspace"),
            "search_web" if web_requested else "answer",
            "high", "analysis",
            ("project", "brand") if has_project else (),
            ("web.search",) if web_requested else (), None, False,
        )

    meeting_write = _has(text, r"\b(?:agend|marqu)\w*\b.{0,55}\b(?:reuni[aã]o|convite|meet)\b") or _has(
        text, r"\b(?:crie|criar|mande|envi)\w*\b.{0,55}\b(?:convite|meet)\b",
    )
    if meeting_write and not _has(text, r"\b(?:resumo|ata|s[ií]ntese|pauta)\b"):
        if not has_project:
            return IntentRoute("workspace", "select_project_for_meeting", "low", "clarification")
        return IntentRoute("workspace", "schedule_project_meeting", "medium", "decision",
                           ("project",), ("google.get_connector_status", "workspace.list_project_shares"), None, True)

    if _has(text, r"\b(?:minha|meu|meus|eu)\b.{0,35}\b(?:agenda|reuni[oõ]es?|compromissos?)\b") or _has(
        text, r"\b(?:agenda|reuni[oõ]es?|compromissos?)\b.{0,35}\b(?:hoje|amanh[aã]|semana|m[eê]s)\b",
    ):
        return IntentRoute("workspace", "list_calendar_events", "low", "analysis", (),
                           ("google.list_calendar_events",))

    if has_brand and _has(text, r"\b(?:qual|quais|mostre|traga|consulte|como)\b.{0,55}\b(?:marca|identidade|tom(?: de voz)?|posicionamento|p[uú]blico|cores?|dire[cç][aã]o criativa)\b"):
        return IntentRoute("workspace", "get_brand_context", "low", "analysis",
                           ("brand",), ("brands.get_context",))

    project_overview = _has(
        text,
        r"\b(?:sobre\s+o\s+que\s+[ée]|do\s+que\s+(?:se\s+)?trata)\s+(?:esse|este|o)\s+projeto\b",
    ) or _has(
        text,
        r"\b(?:qual|explique|resuma|conte)\b.{0,45}"
        r"\b(?:objetivo|contexto|escopo|descri[cç][aã]o|projeto)\b",
    )
    if has_project and project_overview:
        return IntentRoute("workspace", "describe_project", "low", "analysis",
                           ("project",), ("workspace.get_project_context",))

    if has_project and _has(text, r"\b(?:listar|liste|mostrar|mostre|ver|quais)\w*\b.{0,45}\btarefas?\b"):
        return IntentRoute("workspace", "list_project_tasks", "low", "analysis",
                           ("project",), ("projects.list_tasks",))

    project_task_list = _has(
        text,
        r"\b(?:cri\w*|proponh\w*|mont\w*|organiz\w*)\b.{0,55}\b(?:lista\s+de\s+)?tarefas?\b|"
        r"\b(?:primeira\s+)?lista\s+de\s+tarefas\b|\b(?:tarefas?|pr[oó]ximos?\s+passos?)\b.{0,55}"
        r"\b(?:projeto|contexto|fontes?|conversas?)\b|\b(?:projeto|contexto|fontes?|conversas?)\b.{0,55}"
        r"\b(?:tarefas?|pr[oó]ximos?\s+passos?)\b",
    )
    if has_project and project_task_list:
        return IntentRoute(
            "workspace", "plan_project_tasks", "high", "analysis", ("project",),
            ("workspace.get_project_context", "projects.list_tasks", "projects.list_resources"), None, True,
        )

    if _has(text, r"\b(?:list|liste|mostrar|mostre|quais|buscar|busque)\w*\b(?:\s+(?:os|meus|todos\s+os))?\s+projetos\b"):
        return IntentRoute("workspace", "list_projects", "low", "analysis", (),
                           ("workspace.list_projects",))

    if (_has(text, r"\b(test|teste|testar|verifi|diagn[oó]stico|audit).{0,30}\b(link|url|destino|utm|tracking)\b")
            or _has(text, r"\b(link|url)\b.{0,30}\b(test|teste|testar|verifi|diagn[oó]stico|audit)")):
        return IntentRoute("planner", "link_test", "medium", "decision", (), (), None, True)
    # A linked brand is usually present in project context. An implicit name
    # change still targets the active project unless the user names the brand
    # as the object of the change.
    project_rename = (
        _has(text, r"\b(?:mud|alter|troc|renome)\w*\b.{0,25}\bnome\b.{0,120}\bpara\b")
        or _has(text, r"\brenome\w*\b.{0,120}\bpara\b")
    )
    rename_subject = re.split(r"\bpara\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    if has_project and project_rename and (not _has(rename_subject, r"\bmarca\b") or _has(rename_subject, r"\bprojeto\b")):
        return IntentRoute("workspace", "rename_project", "medium", "decision",
                           ("project",), (), None, True)
    active_artifact_type = active_object_type.split(":", 1)[1] if active_object_type.startswith("artifact:") else ""
    if active_artifact_type in {
        "brief", "document", "note", "executive_summary", "media_plan", "scenario", "research", "project_map", "html", "meeting_summary", "meeting_agenda",
    } and _has(text, r"\b(ajust|alter|mud|troqu|revis|atualiz|corrig|edit|refin|melhore\b|melhorar\b)"):
        return IntentRoute("workspace", f"update_{active_artifact_type}", "high", "artifact_first",
                           ("current_object",), ("artifacts.get",), active_artifact_type)
    if _has(text, r"\b(resumo|ata|s[ií]ntese).{0,35}\b(reuni[aã]o|call|alinhamento)\b|\b(reuni[aã]o|call|alinhamento).{0,35}\b(resumo|ata|s[ií]ntese)\b"):
        return IntentRoute("workspace", "create_meeting_summary", "medium", "artifact_first",
                           ("project",) if has_project else (), (), "meeting_summary")
    if _has(text, r"\b(cri(e|ar)|cadastre|cadastrar|nova)\b.{0,35}\bmarca\b"):
        return IntentRoute("workspace", "create_brand", "medium", "decision", (), (), None, True)
    if has_brand and (_has(text, r"\b(envi|substitu|troc|troqu|alter|atualiz)\w*\b.{0,35}\blogo\b")
                      or _has(text, r"\blogo\b.{0,35}\b(envi|substitu|troc|troqu|alter|atualiz)\w*\b")):
        return IntentRoute("workspace", "prepare_brand_logo_upload", "low", "decision",
                           ("brand",), (), None, False)
    if has_brand and _has(text, r"\b(ajust|alter|mud|troqu|atualiz|corrig|edit)\w*\b") and _has(
            text, r"\b(marca|identidade|nome|setor|site|cor|p[uú]blico|posicionamento|tom(?: de voz)?|ess[eê]ncia|descri[cç][aã]o|oferta|diferencia|prova|dire[cç][aã]o criativa)\b"):
        return IntentRoute("workspace", "update_brand_identity", "medium", "decision",
                           ("brand",), (), None, True)
    if _has(text, r"\b(inicie|iniciar|fa[çc]a|rodar|rode|refa[çc]a|reprocess).{0,35}\bauditoria\b.{0,25}\bmarca\b|\bauditoria\b.{0,25}\bmarca\b"):
        return IntentRoute("workspace", "start_brand_audit", "high", "decision",
                           ("brand",), (), None, True)
    # Project creation may include URLs, notes and upload requests. It must win
    # over the generic bare-link route so the sources bootstrap the new project
    # instead of being treated as an orphan reference.
    if _has(text, r"\b(?:crie|criar|novo)\s+(?:(?:um|o)\s+)?projeto\b"):
        return IntentRoute("workspace", "create_project", "medium", "decision", (), (), None, True)
    if _has(text, r"\b(pauta|agenda).{0,35}\b(reuni[aã]o|call|alinhamento)\b|\b(reuni[aã]o|call|alinhamento).{0,35}\b(pauta|agenda)\b"):
        return IntentRoute("workspace", "create_meeting_agenda", "medium", "artifact_first",
                           ("project",) if has_project else (), (), "meeting_agenda")
    if _has(text, r"\b(cri(e|ar)|mont(e|ar)|estrutur(e|ar)|transform(e|ar)).{0,30}\bbriefing\b|\bbriefing\b.{0,20}\b(cri|mont|estrutur)"):
        # A request to structure a briefing begins a short discovery, not an
        # empty document. The executor promotes it to an artifact only after
        # enough concrete campaign data has been gathered.
        return IntentRoute("planner", "create_brief", "medium", "clarification",
                           ("project", "brand") if has_project else (),
                           ("planner.get_brief",), None)
    if _has(text, r"\b(revis(e|ar)|melhor(e|ar)|atualiz(e|ar)|corrig).{0,30}\bbriefing\b"):
        return IntentRoute("planner", "update_brief", "medium", "artifact_first",
                           ("project", "brief"), ("planner.get_brief",), "brief")
    if (_has(text, r"\b(leitura de partida|leitura inicial|diagn[oó]stico inicial|raio[- ]x).{0,45}\bprojeto\b")
            or (_has(text, r"\bprojeto\b")
                and _has(text, r"\bobjetivo\b")
                and _has(text, r"\b(entregas?|riscos?|decis(?:[aã]o|[oõ]es))\b"))):
        if not has_project:
            return IntentRoute("workspace", "select_project_for_readout", "low", "clarification")
        return IntentRoute(
            "workspace", "project_readout", "high", "artifact_first",
            ("project",), ("workspace.search_project_content",),
            "executive_summary",
        )
    # Cross-domain comparisons must win over the generic media-plan route.
    if (_has(text, r"\b(relat[oó]rio|m[eé]trica|resultado|performance|agosto|campanha)\b")
            and _has(text, r"\bplano(?: de m[ií]dia)?\b")):
        return IntentRoute("reports", "compare_report_to_plan", "high", "analysis",
                           ("project", "reports", "media_plan"), ("reports.compare_report_to_plan",))
    if _has(text, r"\b(plano de m[ií]dia|mix de m[ií]dia|cen[aá]rio de m[ií]dia)\b"):
        action = "compare_plan" if _has(text, r"\b(compar|versus|vs\.?|cen[aá]rios?)\b") else "analyze_plan"
        return IntentRoute("planner", action, "high" if action == "compare_plan" else "medium", "decision",
                           ("project", "media_plan"), ("planner.get_media_plan",))
    if _has(text, r"\b(relat[oó]rio|m[eé]trica|resultado|performance|agosto|campanha)\b") and (
            surface == "reports" or _has(text, r"\b(compare|comparar|resultado|performance|m[eé]trica)\b")):
        cross = _has(text, r"\bplano\b")
        return IntentRoute("reports", "compare_report_to_plan" if cross else "analyze_report", "high" if cross else "medium",
                           "analysis", ("project", "reports") + (("media_plan",) if cross else ()),
                           ("reports.compare_report_to_plan",) if cross else ("reports.get_report_metrics",))
    if has_project and _has(text, r"\b(list|liste|mostrar|mostre|ver|quais).{0,45}\b(fontes?|arquivos?|documentos?|links?|recursos?)\b"):
        needs_tool = "projects.list_sources" if _has(text, r"\b(fontes?|base de conhecimento|indexad[oa])\b") else "projects.list_resources"
        return IntentRoute("workspace", "list_project_resources", "low", "analysis",
                           ("project",), (needs_tool,))
    inline_project_url = re.search(
        r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?",
        text,
        re.IGNORECASE,
    )
    project_link_signal = has_project and (
        _has(text, r"\b(link|url|refer[eê]ncia|pasta)\b.{0,70}\bprojeto\b")
        or _has(text, r"\bprojeto\b.{0,70}\b(link|url|refer[eê]ncia|pasta)\b")
        or (
            inline_project_url
            and _has(text, r"\b(adicion\w*|salv\w*|registre\w*|anex\w*|import\w*)\b.{0,45}\bprojeto\b")
        )
    )
    meeting_invite_signal = bool(
        has_project and inline_project_url
        and _has(text, r"\b(?:google meet|microsoft teams|zoom|como participar|join meeting|fuso hor[aá]rio|time zone)\b")
        and _has(text, r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b")
    )
    if (_has(text, r"\b(adicion\w*|salv\w*|registre\w*|anex\w*|import\w*).{0,45}\b(link|url|refer[eê]ncia|pasta)\b")
            or project_link_signal or meeting_invite_signal):
        url_match = inline_project_url
        has_url = bool(url_match and _usable_public_url(url_match.group(0)))
        if not has_project:
            return IntentRoute("workspace", "select_project_for_link" if has_url else "clarify_project_link",
                               "low", "clarification", ("project",) if has_url else (), (), None, False)
        return IntentRoute("workspace", "create_project_link" if has_url else "clarify_project_link",
                           "low", "decision" if has_url else "clarification", ("project",), (), None, has_url)
    if has_project and re.search(r"https://[^\s<>{}\[\]\\\"']+", text, re.IGNORECASE) and _has(text, r"\b(resumo|resumir|s[ií]ntese).{0,45}\b(texto|edit[aá]vel|site|conte[uú]do)\b"):
        return IntentRoute("research", "create_link_summary", "high", "artifact_first",
                           ("project",), ("web.read",), "document")
    if has_project and _has(
            text,
            r"\b(arquivar|arquive|desativar|desative|reativar|reative|restaurar|restaure)\b.{0,30}\bprojeto\b",
    ):
        return IntentRoute("workspace", "set_project_status", "medium", "decision",
                           ("project",), (), None, True)
    if has_project and _has(text, r"\b(vincul|associ|conect).{0,35}\bmarca\b"):
        return IntentRoute("workspace", "link_project_brand" if has_brand else "select_brand_for_project",
                           "medium", "decision" if has_brand else "clarification",
                           ("project", "brand") if has_brand else ("project",), (), None, has_brand)
    reindex_requested = (
        _has(text, r"\b(reprocess|reindex)\w*.{0,35}\b(fonte|arquivo|documento)\b")
        or _has(text, r"\batualiz\w*.{0,35}\b([íi]ndice|indexa[çc][ãa]o)\b.{0,35}\b(fonte|arquivo|documento)\b")
    )
    if has_project and reindex_requested:
        has_source_id = bool(re.search(r"\b(?:fonte|arquivo|documento)\s*#?\s*\d+\b", text, re.IGNORECASE))
        return IntentRoute("workspace", "reindex_project_source" if has_source_id else "select_project_source",
                           "high", "decision" if has_source_id else "clarification",
                           ("project",), ("projects.list_sources",), None, has_source_id)
    if has_project and _has(text, r"\b(adicion|crie|registre).{0,35}\b(nota|fonte textual)\b"):
        has_note_payload = bool(re.search(
            r"\b(?:nota|fonte textual)\s*[\"“][^\"”]{2,180}[\"”]\s*:\s*.{20,50000}$",
            text, re.IGNORECASE | re.DOTALL,
        ))
        return IntentRoute("workspace", "create_project_note" if has_note_payload else "clarify_project_note",
                           "medium", "decision" if has_note_payload else "clarification",
                           ("project",), (), None, has_note_payload)
    direct_url = re.search(r"https?://[^\s<>{}\[\]\\\"']+", text, re.IGNORECASE)
    if direct_url and not _usable_public_url(direct_url.group(0)):
        direct_url = None
    explicit_read = _has(text, r"\b(abri|abra|leia|ler|entend\w*|resum\w*|extraia|extra\w*|analise|analis\w*)\b")
    if direct_url and explicit_read:
        return IntentRoute("research", "read_web_page", "high", "analysis",
                           ("project", "brand") if has_project else (), ("web.read",))
    if direct_url:
        return IntentRoute("workspace", "register_link_reference", "low", "clarification",
                           ("project",) if has_project else (), (), None, False)
    if _has(text, r"\b(cri|fa[çc]|ger|transform|monte|montar|organiz)\w*\b.{0,45}\b(rascunho|documento|texto)\b") or _has(
        text,
        r"\b(?:resumo|s[ií]ntese)\s+(?:edit[aá]vel|para editar)\b|"
        r"\b(?:transforme?|converta?|coloque?)\b.{0,55}\b(?:texto|resposta|conte[uú]do)\b.{0,35}\bedit[aá]vel\b",
    ):
        return IntentRoute("workspace", "create_text_draft", "high", "artifact_first",
                           ("project", "brand") if has_project else (), (), "document")
    web_request = _has(text, r"\b(pesquis|busqu|procure|encontre|verifi)\w*\b")
    web_signal = _has(text, r"\b(internet|web|online|fontes? externas?|fontes? online|not[ií]cias?|recente|recentes|atual|atualizado|mercado|concorrentes?)\b")
    live_signal = _has(text, r"\bhoje\b") and _has(
        text, r"\b(cota[cç][aã]o|pre[cç]o|clima|tempo|placar|resultado|tr[aâ]nsito|not[ií]cia|agenda p[uú]blica)\b",
    )
    history_signal = _has(text, r"\b(hist[oó]ria|trajet[oó]ria|legado|evolu[cç][aã]o|origem)\b") and _has(text, r"\b(marca|campanha|empresa|artista|pessoa|obra|case)\b")
    project_only = (
        _has(text, r"\b(no|na|nos|nas|dentro do|dentro da)\b.{0,60}\b(projeto|arquivo|documento|nota|base)\b")
        or _has(text, r"\b(as|os)\s+(fontes?|arquivos?|documentos?)\s+(do|da|dos|das)\s+projeto\b")
    )
    freshness_request = _has(text, r"\b(atualiz|acompanhe)\w*\b") and web_signal
    web_question = (web_signal or live_signal) and _has(text, r"\b(qual|quais|como|o que|traga|mostre|resuma|compare|quanto|quem)\b")
    if (web_request or freshness_request or web_question or history_signal) and not project_only:
        return IntentRoute("research", "search_web", "high", "analysis",
                           ("project", "brand") if has_project else (), ("web.search",))
    # Resource organization is intentionally evaluated after explicit web
    # research. Phrases such as "pesquise na internet e organize as fontes"
    # describe the shape of a research answer, not a project-map request.
    if has_project and (
            _has(text, r"\b(mapa|mapeie|organiz|agrupe|agrupar|visualiz).{0,45}\b(arquivo|documento|recurso|fonte|projeto)s?\b")
            or _has(text, r"\b(arquivo|documento|recurso|fonte)s?\b.{0,45}\b(mapa|organiz|agrupe|agrupar|visualiz)")):
        return IntentRoute("workspace", "organize_project_resources", "high", "artifact_first",
                           ("project",), ("projects.list_resources",), "project_map")
    if _has(text, r"\b(ajust|alter|mude|troque|revis|atualiz|refa[cç]|remont).{0,45}\b(html|landing page|p[aá]gina|site|interface|dashboard|painel)\b"):
        return IntentRoute("workspace", "update_html", "high", "artifact_first",
                           ("current_object",), ("artifacts.get",), "html")
    if (_has(text, r"\b(cri(e|ar)|mont(e|ar)|gere|gerar|prototip).{0,55}\b(html|landing page|p[aá]gina|site|interface|dashboard interativo|painel interativo)\b")
            or _has(text, r"\b(html|landing page|p[aá]gina|site|dashboard interativo|painel interativo)\b.{0,35}\b(cri|mont|ger|prototip)")):
        return IntentRoute("workspace", "create_html", "high", "artifact_first",
                           ("project", "brand") if has_project else (),
                           ("workspace.get_project_context",) if has_project else (), "html")
    if _has(text, r"\b(pesquis|busqu|procur|encontr|localiz).{0,30}\b(projeto|arquivo|documento|nota|conte[uú]do)|\bo que (temos|existe|foi definido)\b"):
        return IntentRoute("workspace", "search_project", "medium", "analysis",
                           ("project",), ("workspace.search_project_content",))
    if _has(text, r"\b(?:crie|criar|novo)\s+(?:(?:um|o)\s+)?projeto\b"):
        return IntentRoute("workspace", "create_project", "medium", "decision", (), (), None, True)
    canonical = interpret_canonical_intent(text, has_project=has_project, surface="chat")
    if canonical.intent == "persist_content":
        if not has_project:
            return IntentRoute("workspace", "select_project_for_artifact", "low", "clarification",
                               ("project",), (), None, False)
        return IntentRoute("workspace", "save_to_project", "medium", "artifact_first",
                           ("project",), (), canonical.format if canonical.format == "note" else "document", False)
    if canonical.intent == "create_artifact":
        return IntentRoute("workspace", "create_text_draft", "high", "artifact_first",
                           ("project", "brand") if has_project else (), (), "document")
    if canonical.intent == "research_entity":
        return IntentRoute("research", "search_web", "high", "analysis",
                           ("project", "brand") if has_project else (), ("web.search",))
    # Product language comes after specialized and canonical intents. It turns
    # a generic request for something ready to use into an editable delivery
    # without shadowing persistence, meeting, HTML or project operations.
    if _has(
        text,
        r"\b(?:organiz|consolid|estrutur|prepar|deix|mont|transform)\w*\b.{0,90}"
        r"\b(?:pronto|final|entrega|material|cliente|apresentar|compartilhar|reuni[aã]o)\b|"
        r"\b(?:vers[aã]o final|material para (?:o )?cliente|pronto para apresentar|"
        r"pronto para enviar|entrega final)\b",
    ):
        return IntentRoute("workspace", "create_client_delivery", "high", "artifact_first",
                           ("project", "brand") if has_project else (), (), "document")
    if (not forbid_project_persistence
            and _has(text, r"\b(salv(e|ar)|adicione|enviar|envie|vincul).{0,35}\b(projeto|documento|arquivo|nota)\b")):
        return IntentRoute("workspace", "save_to_project", "medium", "artifact_first",
                           ("project",), (), "document", True)
    if _has(text, r"\b(compare|comparar|qual (?:é|e) (?:a |o )?melhor|recomenda|decid)\b"):
        return IntentRoute(surface if surface in {"planner", "studio", "reports"} else "workspace",
                           "recommend", "medium", "decision", ("current_object",) if has_project else ())
    if _has(text, r"\b(analise|avali(e|ar)|diagn[oó]stico|riscos?|oportunidades?)\b"):
        return IntentRoute(surface if surface != "conversations" else "workspace", "analyze", "medium", "analysis",
                           ("current_object",) if has_project else ())
    explicit_length = re.search(r"\b(\d{1,5}(?:\.\d{3})?)\s*palavras?\b", text, re.IGNORECASE)
    requested_words = int(explicit_length.group(1).replace(".", "")) if explicit_length else 0
    substantial = requested_words >= 500 or _has(
        text,
        r"\b(guia|relat[oó]rio|an[aá]lise|planejamento|documento)\b.{0,45}\b(completo|detalhado|aprofundado|extenso)\b|"
        r"\b(completo|detalhado|aprofundado|extenso)\b.{0,45}\b(guia|relat[oó]rio|an[aá]lise|planejamento|documento)\b",
    )
    if substantial:
        return IntentRoute(surface if surface != "conversations" else "workspace",
                           "create_substantial_delivery", "high", "artifact_first",
                           ("project", "brand") if has_project else (), (), "document")
    return IntentRoute(surface if surface != "conversations" else "workspace", "answer", "low", "direct")
