"""Deterministic first-pass router for common Cadu work.

Routing here costs no model call.  An ambiguity classifier may be introduced
later, but only for messages that fall through these product-level intents.
"""

import re
from urllib.parse import urlparse

from .contracts import IntentRoute


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


def route_request(message: str, surface: str = "conversations", has_project: bool = False,
                  active_object_type: str = "", has_brand: bool = False) -> IntentRoute:
    text = " ".join(str(message or "").split())[:20000]

    if (_has(text, r"\b(test|teste|testar|verifi|diagn[oó]stico|audit).{0,30}\b(link|url|destino|utm|tracking)\b")
            or _has(text, r"\b(link|url)\b.{0,30}\b(test|teste|testar|verifi|diagn[oó]stico|audit)")):
        return IntentRoute("planner", "link_test", "medium", "decision", (), (), None, True)
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
    if _has(text, r"\b(inicie|iniciar|fa[çc]a|rodar|rode|refa[çc]a|reprocess).{0,35}\bauditoria\b.{0,25}\bmarca\b|\bauditoria\b.{0,25}\bmarca\b"):
        return IntentRoute("workspace", "start_brand_audit", "high", "decision",
                           ("brand",), (), None, True)
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
    if _has(text, r"\b(adicion\w*|salv\w*|registre\w*|anex\w*).{0,45}\b(link|url|refer[eê]ncia)\b"):
        url_match = re.search(r"https?://[^\s<>\]\[\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>\]\[\"']*)?", text, re.IGNORECASE)
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
    if _has(text, r"\b(cri|fa[çc]|ger|transform|monte|montar)\w*\b.{0,45}\b(rascunho|documento|texto)\b") or _has(
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
    if _has(text, r"\b(ajust|alter|mude|troque|revis|atualiz).{0,45}\b(html|landing page|p[aá]gina|site|interface)\b"):
        return IntentRoute("workspace", "update_html", "high", "artifact_first",
                           ("current_object",), ("artifacts.get",), "html")
    if (_has(text, r"\b(cri(e|ar)|mont(e|ar)|gere|gerar|prototip).{0,40}\b(html|landing page|p[aá]gina|site|interface)\b")
            or _has(text, r"\b(html|landing page|p[aá]gina|site)\b.{0,35}\b(cri|mont|ger|prototip)")):
        return IntentRoute("workspace", "create_html", "high", "artifact_first",
                           ("project", "brand") if has_project else (),
                           ("workspace.get_project_context",) if has_project else (), "html")
    if _has(text, r"\b(pesquis|busqu|procur|encontr|localiz).{0,30}\b(projeto|arquivo|documento|nota|conte[uú]do)|\bo que (temos|existe|foi definido)\b"):
        return IntentRoute("workspace", "search_project", "medium", "analysis",
                           ("project",), ("workspace.search_project_content",))
    if _has(text, r"\b(cri(e|ar)|novo).{0,20}\bprojeto\b"):
        return IntentRoute("workspace", "create_project", "medium", "decision", (), (), None, True)
    if _has(text, r"\b(salv(e|ar)|adicione|enviar|envie|vincul).{0,35}\b(projeto|documento|arquivo|nota)\b"):
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
    return IntentRoute(
        surface if surface != "conversations" else "workspace", "answer",
        "high" if substantial else "low", "analysis" if substantial else "direct",
    )
