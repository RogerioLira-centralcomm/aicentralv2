"""Deterministic first-pass router for common Cadu work.

Routing here costs no model call.  An ambiguity classifier may be introduced
later, but only for messages that fall through these product-level intents.
"""

import re

from .contracts import IntentRoute


def _has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def route_request(message: str, surface: str = "conversations", has_project: bool = False) -> IntentRoute:
    text = " ".join(str(message or "").split())[:20000]

    if (_has(text, r"\b(test|teste|testar|verifi|diagn[oó]stico|audit).{0,30}\b(link|url|destino|utm|tracking)\b")
            or _has(text, r"\b(link|url)\b.{0,30}\b(test|teste|testar|verifi|diagn[oó]stico|audit)")):
        return IntentRoute("planner", "link_test", "medium", "decision", (), (), None, True)
    if _has(text, r"\b(cri(e|ar)|mont(e|ar)|estrutur(e|ar)|transform(e|ar)).{0,30}\bbriefing\b|\bbriefing\b.{0,20}\b(cri|mont|estrutur)"):
        return IntentRoute("planner", "create_brief", "medium", "artifact_first",
                           ("project", "brand") if has_project else (),
                           ("planner.get_brief",), "brief")
    if _has(text, r"\b(revis(e|ar)|melhor(e|ar)|atualiz(e|ar)|corrig).{0,30}\bbriefing\b"):
        return IntentRoute("planner", "update_brief", "medium", "artifact_first",
                           ("project", "brief"), ("planner.get_brief",), "brief")
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
    if _has(text, r"\b(pesquis|busqu|procur|encontr|localiz).{0,30}\b(projeto|arquivo|documento|nota|conte[uú]do)|\bo que (temos|existe|foi definido)\b"):
        return IntentRoute("workspace", "search_project", "medium", "analysis",
                           ("project",), ("workspace.search_project_content",))
    if _has(text, r"\b(cri(e|ar)|novo).{0,20}\bprojeto\b"):
        return IntentRoute("workspace", "create_project", "medium", "artifact_first", (), (), "project", True)
    if _has(text, r"\b(salv(e|ar)|adicione|enviar|envie|vincul).{0,35}\b(projeto|documento|arquivo|nota)\b"):
        return IntentRoute("workspace", "save_to_project", "medium", "artifact_first",
                           ("project",), (), "document", True)
    if _has(text, r"\b(compare|comparar|qual (?:é|e) melhor|recomenda|decid)\b"):
        return IntentRoute(surface if surface in {"planner", "studio", "reports"} else "workspace",
                           "recommend", "medium", "decision", ("current_object",) if has_project else ())
    if _has(text, r"\b(analise|avali(e|ar)|diagn[oó]stico|riscos?|oportunidades?)\b"):
        return IntentRoute(surface if surface != "conversations" else "workspace", "analyze", "medium", "analysis",
                           ("current_object",) if has_project else ())
    return IntentRoute(surface if surface != "conversations" else "workspace", "answer", "low", "direct")
