"""Evidence-led market insight workflow for the Cadu Insights chat plugin."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from ..services.cadu_ai_connector import CaduAIConnector
from ..services.openrouter_service import message_text
from . import web_search


RESEARCH_MODEL = os.getenv("CADU_INSIGHTS_RESEARCH_MODEL", "perplexity/sonar")
SYNTHESIS_MODEL = os.getenv("CADU_INSIGHTS_SYNTHESIS_MODEL", "openai/gpt-5.4-mini")
REVIEW_MODEL = os.getenv("CADU_INSIGHTS_REVIEW_MODEL", "openai/gpt-5.4-mini")
class InsightsEvidenceUnavailable(RuntimeError):
    """The configured recency/source rules produced no usable market evidence."""


def _source_refs(value: Any, eligible_ids: set[str]) -> list[str]:
    values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return list(dict.fromkeys(str(item) for item in values if str(item) in eligible_ids))


def _parse_json(value: Any) -> dict:
    text = message_text(value) if isinstance(value, dict) else str(value or "")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except (TypeError, ValueError):
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _date_value(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    iso = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso[:32]).date()
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(raw[:40], pattern).date()
        except ValueError:
            continue
    match = re.fullmatch(r"(20\d{2})", raw)
    return date(int(match.group(1)), 1, 1) if match else None


def _freshness(published_at: Any, today: date) -> str:
    published = _date_value(published_at)
    if not published:
        return "date_unverified"
    if published > today:
        return "future_date"
    if published >= today - timedelta(days=183):
        return "last_6_months"
    if published.year == today.year:
        return "current_year"
    return "out_of_window"


def _safe_sources(web_result: dict, perplexity_message: dict, today: date) -> list[dict]:
    rows: list[dict] = []
    for item in web_result.get("sources") or []:
        if isinstance(item, dict):
            rows.append({**item, "published_at": item.get("published_at") or item.get("date") or item.get("publishedDate") or "",
                         "research_stream": "internet"})
    citations = perplexity_message.get("_cadu_citations") or []
    if isinstance(citations, dict):
        citations = citations.get("search_results") or citations.get("citations") or []
    for item in citations if isinstance(citations, list) else []:
        if isinstance(item, str):
            item = {"url": item, "title": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("link") or "").strip()
        try:
            parsed_url = urlsplit(url)
        except ValueError:
            continue
        if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
            continue
        rows.append({
            "title": item.get("title") or item.get("name") or "Resultado Perplexity",
            "url": url,
            "excerpt": item.get("snippet") or item.get("text") or item.get("description") or "",
            "published_at": item.get("date") or item.get("published_at") or item.get("publishedDate") or "",
            "research_stream": "perplexity",
        })
    unique = {}
    for item in rows:
        url = str(item.get("url") or "").strip()
        title = " ".join(str(item.get("title") or "").split())[:220]
        try:
            parsed_url = urlsplit(url)
        except ValueError:
            continue
        if (parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username
                or parsed_url.password or not title):
            continue
        freshness = _freshness(item.get("published_at"), today)
        key = url.split("#", 1)[0].rstrip("/").casefold()
        current = unique.get(key)
        normalized = {
            "title": title, "url": url[:2000],
            "published_at": str(item.get("published_at") or "")[:80],
            "freshness": freshness,
            "excerpt": " ".join(str(item.get("content_excerpt") or item.get("excerpt") or "").split())[:1000],
            "research_stream": item.get("research_stream") or "internet",
        }
        if current is None or (current["freshness"] == "date_unverified" and freshness != "date_unverified"):
            unique[key] = normalized
    # Assign IDs after deduplication so duplicate URLs cannot cause two
    # different sources to share an evidence ID in the model/reviewer packet.
    return [{**item, "id": f"mkt-{index}"}
            for index, item in enumerate(list(unique.values())[:12], 1)]


def _model_call(*, context, run_id: str, stage: str, model: str, messages: list[dict],
                estimated_tokens: int, max_tokens: int, timeout: int, json_mode: bool = False,
                provider: str | None = None) -> dict:
    connector = CaduAIConnector()
    options = {"max_tokens": max_tokens, "timeout": timeout, "temperature": 0.1}
    if json_mode:
        options["response_format"] = {"type": "json_object"}
    if provider:
        options["provider"] = provider
    return connector.complete(
        messages, client_id=context.client_id, user_id=context.user_id,
        idempotency_key=f"cadu-insights:{run_id}:{stage}", app="Cadu Chat",
        stage=f"insights:{stage}", estimated_tokens=estimated_tokens,
        model=model, metadata={"conversation_id": context.conversation_id,
                               "plugin": "insights", "plugin_version": "0.3.0"}, **options,
    )


def research_market(context, query: str, request_id: str | None = None,
                    personalization: dict | None = None) -> dict:
    """Search current market evidence, synthesize one insight, and review it."""
    query = " ".join(str(query or "").split())[:400]
    if len(query) < 4:
        raise ValueError("Diga o tema de mercado para buscar insights.")
    today = datetime.now(timezone.utc).date()
    period_start = date(today.year, 1, 1)
    period_start_6m = today - timedelta(days=183)
    run_id = str(request_id or uuid4())[:90]
    market_query = (
        f"{query} marketing comunicação mídia Brasil tendências dados métricas notícias "
        f"{today.year} after:{period_start.isoformat()}"
    )[:400]

    web_result = web_search.search(context, {
        "query": market_query, "depth": "fast", "limit": 4,
        "recency": "year", "include_content": True,
        "request_id": f"{run_id}:internet",
    })
    perplexity_result = _model_call(
        context=context, run_id=run_id, stage="perplexity-research", model=RESEARCH_MODEL,
        provider="openrouter", estimated_tokens=3500, max_tokens=1800, timeout=45,
        messages=[
            {"role": "system", "content": (
                "Pesquise na web, em português, dados reais de mercado relacionados a marketing, comunicação e mídia. "
                f"Priorize publicações dos últimos seis meses; aceite também dados publicados em {today.year}. "
                "Traga notícias, métricas, investimento, comportamento, alcance ou mudanças de canais apenas se houver "
                "evidência explícita. Para cada número, identifique valor, período, geografia e URL de sustentação. "
                "Não invente números nem use projeções como resultado observado. Responda com síntese curta e citações/URLs; "
                "não faça uma lista genérica de links."
            )},
            {"role": "user", "content": f"Tema solicitado: {query}\nConsulta de mercado: {market_query}"},
        ],
    )
    pplx_message = perplexity_result.get("message") if isinstance(perplexity_result.get("message"), dict) else {}
    pplx_text = message_text(pplx_message)
    sources = _safe_sources(web_result, pplx_message, today)
    eligible_sources = [item for item in sources if item["freshness"] in {"last_6_months", "current_year"}]
    if not eligible_sources:
        raise InsightsEvidenceUnavailable(
            "Não encontrei fontes com data verificável nos últimos seis meses ou neste ano para sustentar o insight. "
            "Tente outro recorte de mercado ou um tema mais específico."
        )
    research_packet = {
        "topic": query, "market_period": {"from": period_start.isoformat(), "to": today.isoformat(),
                                           "priority": "prefer last 183 days; current-year evidence is fallback"},
        "verified_recent_sources": eligible_sources,
        "other_sources": [item for item in sources if item["freshness"] not in {"last_6_months", "current_year"}],
        "internet_search": {"query": web_result.get("query"), "sources_read": web_result.get("sources_read")},
        "perplexity_research": pplx_text[:14000],
    }
    personalization = personalization if isinstance(personalization, dict) else {}
    # This private workspace context is added only after public search has
    # finished. It can guide relevance and recommendations, never evidence.
    personalization = {
        "project": personalization.get("project"),
        "brand": personalization.get("brand"),
        "recent_insights_requests": personalization.get("recent_insights_requests", [])[:4],
    }
    research_packet["workspace_personalization"] = personalization
    synthesis = _model_call(
        context=context, run_id=run_id, stage="market-synthesis", model=SYNTHESIS_MODEL,
        estimated_tokens=7500, max_tokens=3000, timeout=45, json_mode=True,
        messages=[
            {"role": "system", "content": (
                "Você transforma evidências de pesquisa em um insight de mercado útil para decisão de marketing, comunicação e mídia. "
                "Escreva em português claro. A primeira frase deve ser o insight principal, específico e surpreendente quando os dados sustentarem. "
                "Depois explique o que os dados mostram, por que isso importa para marketing/mídia e o que fazer. "
                "Dê destaque a números, período e geografia; não abra com metodologia ou bibliografia. "
                "Só use métricas sustentadas pelo conteúdo pesquisado e por fontes elegíveis do ano atual ou dos últimos seis meses. "
                "Se uma métrica não estiver sustentada, omita-a. Separe fato de interpretação. Não complete lacunas com conhecimento paramétrico. "
                "Retorne JSON com headline, headline_source_ids (array de strings), insight, insight_source_ids (array de strings), "
                "metrics[{name,value,period,geography,meaning,source_ids}], "
                "news[{title,date,summary,marketing_relevance,source_ids}], implications[string], actions[string], "
                "application_to_project[string], personalized_suggestions[string], confidence[high|medium|low]. "
                "Use workspace_personalization somente para priorizar relevância e adaptar aplicações e sugestões; "
                "ela não é evidência de mercado e nunca sustenta fatos, métricas ou notícias. Se houver histórico recente de pedidos, "
                "identifique padrões de formato/tema e ofereça até duas próximas ações úteis, sem afirmar preferências como certeza. "
                "Só preencha application_to_project quando houver projeto ou marca no contexto; sem esse contexto, retorne lista vazia. "
                "Inclua até quatro métricas, quatro notícias, quatro implicações e quatro ações."
            )},
            {"role": "user", "content": json.dumps(research_packet, ensure_ascii=False)},
        ],
    )
    draft = _parse_json((synthesis.get("message") or {}).get("content"))
    if not draft.get("headline") or not draft.get("insight"):
        raise RuntimeError("A síntese de mercado não retornou um insight utilizável.")
    review = _model_call(
        context=context, run_id=run_id, stage="insight-review", model=REVIEW_MODEL,
        estimated_tokens=5000, max_tokens=2600, timeout=35, json_mode=True,
        messages=[
            {"role": "system", "content": (
                "Você é o revisor factual e editorial do Cadu Insights. Faça auditoria de cada número, período, geografia, notícia e inferência "
                "contra as evidências fornecidas. Remova afirmações sem sustentação ou fora da janela de atualidade; nunca tente preencher "
                "a lacuna com conhecimento próprio. Mantenha o insight como primeira frase e preserve o foco em dados e implicações para "
                "marketing, comunicação e mídia, não em listar fontes. Preserve application_to_project e personalized_suggestions como recomendações, "
                "sem convertê-las em fatos; verifique se cada source_id citado existe entre as fontes elegíveis. "
                "Retorne o mesmo JSON do rascunho, corrigido; headline e insight precisam de source_ids elegíveis. "
                "Se não houver fonte elegível para sustentar o insight principal, retorne headline e insight vazios. Sem comentários fora do JSON."
            )},
            {"role": "user", "content": json.dumps({"draft": draft, "evidence": research_packet}, ensure_ascii=False)},
        ],
    )
    final = _parse_json((review.get("message") or {}).get("content"))
    if not isinstance(final.get("headline"), str) or not final.get("headline") or not isinstance(final.get("insight"), str) or not final.get("insight"):
        raise RuntimeError("A revisão final não retornou um insight utilizável.")
    final["headline"] = " ".join(str(final["headline"]).split())[:220]
    final["insight"] = " ".join(str(final["insight"]).split())[:1800]
    eligible_ids = {item["id"] for item in eligible_sources}
    for key in ("headline_source_ids", "insight_source_ids"):
        final[key] = _source_refs(final.get(key), eligible_ids)
    for key in ("metrics", "news"):
        cleaned = []
        for item in final.get(key) if isinstance(final.get(key), list) else []:
            if not isinstance(item, dict):
                continue
            refs = _source_refs(item.get("source_ids"), eligible_ids)
            if not refs:
                continue
            cleaned.append({**item, "source_ids": refs})
        final[key] = cleaned[:4]
    if not final["insight_source_ids"]:
        final["insight_source_ids"] = list(dict.fromkeys(
            source_id for group in (final["metrics"] + final["news"])
            for source_id in group.get("source_ids", [])
        ))
    if not final["headline_source_ids"]:
        final["headline_source_ids"] = list(final["insight_source_ids"])
    if not final["insight_source_ids"]:
        raise InsightsEvidenceUnavailable(
            "As fontes recentes encontradas não sustentaram uma conclusão confiável para este tema. Tente outro recorte."
        )
    implications = final.get("implications") if isinstance(final.get("implications"), list) else []
    actions = final.get("actions") if isinstance(final.get("actions"), list) else []
    final["implications"] = [str(item).strip()[:500] for item in implications if str(item).strip()][:4]
    final["actions"] = [str(item).strip()[:500] for item in actions if str(item).strip()][:4]
    def _string_items(value, limit, count):
        values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        return [str(item).strip()[:limit] for item in values if str(item).strip()][:count]
    final["application_to_project"] = _string_items(final.get("application_to_project"), 500, 3)
    final["personalized_suggestions"] = _string_items(final.get("personalized_suggestions"), 300, 2)
    final["confidence"] = final.get("confidence") if final.get("confidence") in {"high", "medium", "low"} else "medium"
    cited_ids = set(final["headline_source_ids"] + final["insight_source_ids"])
    cited_ids.update(source_id for group in (final["metrics"] + final["news"])
                     for source_id in group.get("source_ids", []))
    cited_sources = [item for item in eligible_sources if item["id"] in cited_ids]
    return {
        "type": "market_insight", "title": final["headline"], "summary": final["insight"],
        "insight": final, "sources": cited_sources,
        "personalization": {"project_used": bool(personalization.get("project")),
                            "brand_used": bool(personalization.get("brand")),
                            "history_used": bool(personalization.get("recent_insights_requests"))},
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "period": {"from": period_start.isoformat(), "last_six_months_from": period_start_6m.isoformat(),
                   "to": today.isoformat()},
        "review": {"status": "reviewed", "model": review.get("model") or REVIEW_MODEL},
        "models": {"research": perplexity_result.get("model") or RESEARCH_MODEL,
                   "synthesis": synthesis.get("model") or SYNTHESIS_MODEL,
                   "review": review.get("model") or REVIEW_MODEL},
        "source_counts": {"internet": web_result.get("source_count") or 0,
                          "recent_cited": len(cited_sources)},
    }
