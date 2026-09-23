"""Resolve only the context explicitly requested by an IntentRoute."""

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any
from time import perf_counter

from .contracts import IntentRoute, RequestContext
from ..mcp.registry import ToolError, ToolNotFound, ToolRegistry


@dataclass
class ResolvedContext:
    values: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


_PUBLIC_SIGNAL = re.compile(
    r"\b(?:mercado|benchmark|tend[eê]ncia|concorr[eê]ncia|concorrentes?|pre[cç]o|cota[cç][aã]o|"
    r"estat[ií]stica|not[ií]cias?|legisla[cç][aã]o|regra|atual|recente|hoje|202[5-9]|"
    r"cpc|cpm|cac|ctr|google ads|meta ads|tiktok|instagram)\b", re.IGNORECASE,
)
_PRIVATE_SCOPE = re.compile(
    r"\b(?:para|no|na|do|da|sobre|em)\s+(?:(?:o|a|os|as|um|uma)\s+)?"
    r"(?:(?:nosso|nossa|meu|minha|deste|desse)\s+)?"
    r"(?:projeto|cliente|campanha|marca|briefing|arquivo|documento)\b.*$", re.IGNORECASE,
)
_PUBLIC_TERMS = frozenset({
    "atual", "atuais", "recente", "recentes", "hoje", "mercado", "setor", "benchmark",
    "tendencia", "tendencias", "concorrencia", "concorrentes", "preco", "precos",
    "cotacao", "estatistica", "estatisticas", "noticia", "noticias", "regra", "regras",
    "legislacao", "marketing", "midia", "digital", "publicidade", "campanha", "campanhas",
    "anuncios", "criativos", "funil", "email", "leads", "conversao", "conversoes",
    "audiencia", "alcance", "engajamento", "varejo", "ecommerce", "comercio",
    "construcao", "imoveis", "saude", "educacao", "financas", "tecnologia",
    "google", "ads", "meta", "facebook", "instagram", "tiktok", "youtube", "linkedin",
    "openai", "chatgpt", "claude", "cursor", "codex", "brasil", "brasileiro",
    "dolar", "euro", "cpc", "cpm", "cac", "ctr", "cpa", "roas", "roi", "kpi",
})


def public_web_query(message: str, *, project_selected: bool = False) -> str:
    """Use only an independently meaningful public topic in external search."""
    text = " ".join(str(message or "").split())[:400]
    if not project_selected:
        return text
    text = re.sub(r"https?://\S+|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[\"“][^\"”]{1,160}[\"”]", " ", text)
    text = re.sub(r"\b(?:no|na|do|da)\s+(?:(?:nosso|nossa|meu|minha)\s+)?projeto\s+(?=sobre\b)",
                  " ", text, flags=re.IGNORECASE)
    text = _PRIVATE_SCOPE.sub("", text)
    if re.search(r"\b(?:nosso|nossa|meu|minha|projeto|cliente|briefing|anexo|arquivo)\b", text, re.IGNORECASE):
        return ""
    text = " ".join(text.strip(" ,.;:?!").split())
    if not _PUBLIC_SIGNAL.search(text):
        return ""
    terms = re.findall(r"[\wÀ-ÿ]{3,}", text)
    safe = [term for term in terms if (
        unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode("ascii").lower()
        in _PUBLIC_TERMS or re.fullmatch(r"20\d{2}", term)
    )]
    return " ".join(safe[:16]) if len(safe) >= 2 else ""


def _arguments(tool_name: str, request: RequestContext, message: str, execution_mode: str = "analysis") -> dict[str, Any]:
    if tool_name == "web.search":
        depth = {"fast": "fast", "analysis": "analysis", "agentic": "agentic"}.get(execution_mode, "analysis")
        private_reference = bool(re.search(r"\b(?:nosso|nossa|meu|minha)\s+(?:cliente|projeto|campanha|marca|briefing)\b",
                                           message, re.IGNORECASE))
        arguments = {"query": public_web_query(message, project_selected=bool(request.project_ref) or private_reference),
                     "depth": depth, "include_content": True}
        if not re.search(r"\b(?:pesquis\w*|busqu\w*|investig\w*|aprofunde|pesquisa)\b", message, re.IGNORECASE):
            arguments["limit"] = 4
        if request.request_id:
            arguments["request_id"] = request.request_id
        return arguments
    if tool_name == "web.read":
        match = re.search(r"https://[^\s<>{}\[\]\\\"']+", message, re.IGNORECASE)
        arguments = {"url": (match.group(0).rstrip(".,;:)") if match else "")}
        if request.request_id:
            arguments["request_id"] = request.request_id
        return arguments
    if tool_name == "brands.inspect_site":
        matches = re.findall(r"https?://[^\s<>{}\[\]\\\"']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>{}\[\]\\\"']*)?", message, re.IGNORECASE)
        values = [item.rstrip(".,;:)") for item in matches]
        arguments = {"website_url": values[0] if values else ""}
        if len(values) > 1 and re.search(r"\blogo\b", message, re.IGNORECASE):
            arguments["logo_url"] = values[1]
        return arguments
    if tool_name == "artifacts.get" and request.active_object and request.active_object.type.startswith("artifact:"):
        return {"artifact_id": request.active_object.id}
    if tool_name == "workspace.search_project_content":
        return {"query": message[:400]}
    if tool_name == "workspace.get_project_context":
        return {"query": message[:400]}
    if tool_name == "workspace.list_projects":
        return {"limit": 20}
    if tool_name == "google.list_calendar_events":
        return {"limit": 50}
    if tool_name in {"planner.get_brief", "planner.get_media_plan", "reports.get_report_metrics"}:
        if request.active_object:
            key = "plan_id" if tool_name.startswith("planner.") else "report_id"
            return {key: request.active_object.id}
    if tool_name == "reports.compare_report_to_plan" and request.active_object:
        key = "report_id" if request.active_object.type in {"report", "report_workspace"} else "plan_id"
        return {key: request.active_object.id}
    return {}


def resolve_context(route: IntentRoute, request: RequestContext, message: str,
                    registry: ToolRegistry, execution_mode: str = "analysis") -> ResolvedContext:
    result = ResolvedContext(values={"current_context": request.to_dict()})
    for tool_name in route.needs_tools:
        arguments = _arguments(tool_name, request, message, execution_mode)
        started = perf_counter()
        try:
            value = registry.execute(tool_name, arguments, request)
            result.values[tool_name] = value
            result.tool_calls.append({"name": tool_name, "status": "completed",
                                      "duration_ms": round((perf_counter() - started) * 1000)})
        except (ToolError, ValueError) as exc:
            # Missing context is data for the response policy, never a provider
            # diagnostic to expose to the customer.
            result.missing.append(tool_name)
            result.tool_calls.append({"name": tool_name, "status": "unavailable", "code": getattr(exc, "code", "invalid"),
                                      "duration_ms": round((perf_counter() - started) * 1000)})
    if result.missing:
        result.values["tool_status"] = {
            "unavailable": list(result.missing),
            "message": "A evidência externa solicitada não ficou disponível nesta resposta.",
        }
    return result
