"""Resolve only the context explicitly requested by an IntentRoute."""

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any
from time import perf_counter

from .contracts import IntentRoute, RequestContext
from ..project_query import is_overview_query
from ..mcp.registry import ToolError, ToolNotFound, ToolRegistry


@dataclass
class ResolvedContext:
    values: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


_PUBLIC_SIGNAL = re.compile(
    r"\b(?:mercado|benchmarks?|tend[eê]ncias?|concorr[eê]ncias?|concorrentes?|pre[cç]os?|cota[cç][aã]o|"
    r"estat[ií]sticas?|not[ií]cias?|legisla[cç][aã]o|regras?|atuais?|recentes?|hoje|202[5-9]|"
    r"cpc|cpm|cac|ctr|google ads|meta ads|tiktok|instagram|campanha|campanhas|an[uú]ncios?|criativos?|"
    r"bebida|bebidas|cerveja|alimento|alimentos|"
    r"moda|beleza|automotivo|automotiva|turismo|esporte|entretenimento|streaming|jogos|games|"
    r"agroneg[oó]cio|energia|imobili[aá]rio|supermercado|restaurante|delivery|farm[aá]cia|"
    r"fintech|banc[aá]rio|banco|consumo|consumidor|consumidores|roupa|roupas|vestu[aá]rio|luxo)\b", re.IGNORECASE,
)
_PRIVATE_SCOPE = re.compile(
    r"\b(?:para|no|na|do|da|sobre|em)\s+(?:(?:o|a|os|as|um|uma)\s+)?"
    r"(?:(?:nosso|nossa|meu|minha|deste|desse)\s+)?"
    r"(?:projeto|cliente|campanha|marca|briefing|arquivo|documento)\b.*$", re.IGNORECASE,
)
_PUBLIC_TERMS = frozenset({
    "atual", "atuais", "recente", "recentes", "hoje", "mercado", "setor", "benchmark", "benchmarks",
    "tendencia", "tendencias", "concorrencia", "concorrentes", "preco", "precos",
    "cotacao", "estatistica", "estatisticas", "noticia", "noticias", "regra", "regras",
    "legislacao", "marketing", "midia", "digital", "publicidade", "campanha", "campanhas",
    "anuncios", "criativos", "funil", "email", "leads", "conversao", "conversoes",
    "audiencia", "alcance", "engajamento", "varejo", "ecommerce", "comercio",
    "construcao", "imoveis", "saude", "educacao", "financas", "tecnologia",
    "bebida", "bebidas", "cerveja", "alimento", "alimentos", "moda", "beleza",
    "automotivo", "automotiva", "turismo", "esporte", "entretenimento", "streaming",
    "jogos", "games", "agronegocio", "energia", "imobiliario", "supermercado",
    "restaurante", "delivery", "farmacia", "fintech", "bancario", "banco", "consumo",
    "consumidor", "consumidores", "roupa", "roupas", "vestuario", "luxo",
    "google", "ads", "meta", "facebook", "instagram", "tiktok", "youtube", "linkedin",
    "openai", "chatgpt", "claude", "cursor", "codex", "brasil", "brasileiro",
    "dolar", "euro", "cpc", "cpm", "cac", "ctr", "cpa", "roas", "roi", "kpi",
})


def public_web_query(message: str, *, project_selected: bool = False, min_terms: int = 2) -> str:
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
    return " ".join(safe[:16]) if len(safe) >= max(1, int(min_terms)) else ""


def _arguments(tool_name: str, request: RequestContext, message: str, execution_mode: str = "analysis",
               route_action: str = "") -> dict[str, Any]:
    if tool_name == "insights.research_market":
        public_message = re.sub(
            r"\b(?:for|about|on|in|from|inside)\s+(?:(?:my|our|the|this)\s+)?"
            r"(?:project|client|campaign|brand|brief|file|document)\b.*$",
            " ", message, flags=re.IGNORECASE,
        )
        arguments = {"query": public_web_query(public_message, project_selected=True, min_terms=1)}
        if request.request_id:
            arguments["request_id"] = request.request_id
        return arguments
    if tool_name == "planner.research_plan_inputs":
        # The composite catalog tool searches only Cadu's read-only catalog;
        # the private brief stays inside the authorized chat context.
        query = re.sub(r"\b(?:crie|criar|monte|montar|planeje|planejar|fa[cç]a|elabore)\b", " ", message, flags=re.I)
        city_match = re.search(r"\b(?:em|para)\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ -]{1,50}?)(?=\s+(?:com|para|usando|considerando)\b|[,.;!?]|$)", message)
        arguments = {"query": " ".join(query.split())[:100]}
        if city_match:
            arguments["city"] = city_match.group(1).strip()[:80]
        return arguments
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
        return {"query": message[:400], "mode": "overview" if route_action == "project_readout" or is_overview_query(message) else "search"}
    if tool_name == "workspace.get_project_context":
        return {"query": message[:400]}
    if tool_name == "brands.get_context" and request.brand_ref:
        match = re.fullmatch(r"studio:(\d+)", request.brand_ref)
        if match:
            return {"brand_id": int(match.group(1))}
    if tool_name == "workspace.list_projects":
        return {"limit": 20}
    if tool_name == "google.list_calendar_events":
        return {"limit": 50}
    if tool_name == "google.search_drive_resources":
        quoted = re.search(r'[“"]([^”"]{2,120})[”"]', message)
        if quoted:
            return {"query": quoted.group(1).strip(), "limit": 40}
        # A broad request lists recent discovered items; a named target uses
        # only the noun phrase, not the entire conversational instruction.
        target = re.search(r"\b(?:arquivo|pasta|documento|planilha)\s+(?:chamad[ao]\s+|sobre\s+|de\s+)?([^?.!,]{2,100})", message, re.I)
        return {"query": target.group(1).strip() if target else "", "limit": 40}
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
        arguments = _arguments(tool_name, request, message, execution_mode, route.action)
        started = perf_counter()
        try:
            value = registry.execute(tool_name, arguments, request)
            result.values[tool_name] = value
            call = {"name": tool_name, "status": "completed",
                    "duration_ms": round((perf_counter() - started) * 1000)}
            if tool_name in {"workspace.search_project_content", "workspace.get_project_context"} and isinstance(value, dict):
                call["project_evidence"] = {
                    "project_bound": bool(request.project_ref),
                    "context_status": value.get("context_status") or "unknown",
                    "source_retrieval_status": value.get("source_retrieval_status") or value.get("retrieval_status") or "unknown",
                    "result_count": len(value.get("results") or []),
                    "indexed_source_count": len(value.get("source_results") or value.get("fontes_verificadas") or []),
                    "source_inventory": value.get("source_inventory") or {},
                    "unavailable_scopes": list(value.get("unavailable_scopes") or []),
                }
            result.tool_calls.append(call)
        except (ToolError, ValueError) as exc:
            # Missing context is data for the response policy, never a provider
            # diagnostic to expose to the customer.
            result.missing.append(tool_name)
            if tool_name == "insights.research_market" and isinstance(exc, ToolError):
                result.values[tool_name] = {"status": "unavailable", "message": str(exc)[:400]}
            result.tool_calls.append({"name": tool_name, "status": "unavailable", "code": getattr(exc, "code", "invalid"),
                                      "duration_ms": round((perf_counter() - started) * 1000)})
    if result.missing:
        result.values["tool_status"] = {
            "unavailable": list(result.missing),
            "message": "A evidência externa solicitada não ficou disponível nesta resposta.",
        }
    return result
