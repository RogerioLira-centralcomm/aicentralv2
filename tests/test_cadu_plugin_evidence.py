"""Focused checks for the shared evidence boundary in Cadu plugins."""

from datetime import date

from aicentralv2.cadu_workspace.agent_v2.evidence import grounded_claims, read_status, supporting_refs
from aicentralv2.cadu_workspace.insights_research import (
    InsightsEvidenceUnavailable, _safe_sources, _read_source_contents, research_market,
)
from aicentralv2.cadu_workspace.agent_v2.long_jobs import LongJobSpec, default_units
from aicentralv2.cadu_workspace.agent_v2.campaign_metrics import supplied_metrics
from aicentralv2.cadu_workspace.agent_v2.investment_scenarios import simulate
from aicentralv2.cadu_workspace.agent_v2.context_resolver import _arguments
from aicentralv2.cadu_workspace.agent_v2.contracts import IntentRoute, RequestContext
from aicentralv2.cadu_workspace.agent_v2.plugins import select
from aicentralv2.cadu_workspace.agent_v2.action_executor import _validate_action_result
from aicentralv2.cadu_workspace.mcp.registry import ToolError
import pytest


def test_extracted_claim_requires_a_literal_quote_in_its_source():
    sources = {"source-1": "A campanha alcançou 12 mil pessoas em Curitiba no mês de julho."}
    claims = [
        {"source_id": "source-1", "claim": "Alcance de 12 mil pessoas", "quote": "alcançou 12 mil pessoas em Curitiba"},
        {"source_id": "source-1", "claim": "Vendas subiram", "quote": "vendas subiram 20%"},
        {"source_id": "source-2", "claim": "Outro número", "quote": "alcançou 12 mil pessoas em Curitiba"},
    ]

    accepted, rejected = grounded_claims(claims, sources)

    assert accepted == claims[:1]
    assert [item["reason"] for item in rejected] == ["quote_not_found", "source_not_read"]


def test_discovered_citation_does_not_become_a_read_source():
    result = {"sources": [{"url": "https://example.com/story", "title": "Notícia",
                           "excerpt": "Trecho da busca", "published_at": "2026-09-20"}]}
    citations = [{"url": "https://example.com/story", "title": "Notícia", "date": "2026-09-20"}]

    sources = _safe_sources(result, {"_cadu_citations": citations}, date(2026, 9, 25))

    assert len(sources) == 1
    assert sources[0]["read_status"] == "discovered"
    assert read_status(result["sources"][0]) == "discovered"


def test_read_source_wins_duplicate_search_hit_without_borrowing_provider_date():
    result = {"sources": [
        {"url": "https://example.com/story", "title": "Busca", "published_at": "2026-09-20"},
        {"url": "https://example.com/story", "title": "Página", "content": "Corpo lido da página.",
         "content_excerpt": "Corpo lido da página.", "source_type": "direct_url"},
    ]}

    sources = _safe_sources(result, {}, date(2026, 9, 25))

    assert len(sources) == 1
    assert sources[0]["read_status"] == "read"
    assert sources[0]["freshness"] == "date_unverified"


def test_insight_support_requires_a_quote_in_the_read_body():
    result = {"sources": [
        {"url": "https://example.com/story", "title": "Busca", "excerpt": "O CTR subiu 30%"},
        {"url": "https://example.com/story", "title": "Página", "content": "O CTR foi de 2,4% no mês de julho.",
         "source_type": "direct_url", "published_at": "2026-09-20"},
    ]}
    sources = _safe_sources(result, {}, date(2026, 9, 25))
    contents = _read_source_contents(result, sources)

    assert supporting_refs("O CTR foi de 2,4% no mês de julho", [sources[0]["id"]], contents) == [sources[0]["id"]]
    assert supporting_refs("O CTR subiu 30%", [sources[0]["id"]], contents) == []
    assert supporting_refs("O CTR foi de 2,4% no mês de julho", ["outro-id"], contents) == []


def test_insights_block_reviewed_claim_without_literal_support(monkeypatch):
    from types import SimpleNamespace
    import json

    page = "O CTR foi de 2,4% no mês de julho em campanhas de café no Brasil."
    monkeypatch.setattr("aicentralv2.cadu_workspace.insights_research.web_search.search", lambda *_args, **_kwargs: {
        "query": "café", "sources_read": 1, "sources": [{
            "url": "https://example.com/coffee", "title": "Relatório público", "content": page,
            "published_at": "2026-09-20", "published_at_source": "page", "read_status": "read",
        }],
    })

    def fake_model(*, stage, **_kwargs):
        if stage == "perplexity-research":
            return {"message": {"content": "Pesquisa preliminar."}}
        payload = {
            "headline": "CTR de 2,4% em julho", "headline_source_ids": ["mkt-1"],
            "headline_support_quote": "O CTR foi de 2,4% no mês de julho",
            "insight": "O CTR foi de 2,4% no mês de julho.", "insight_source_ids": ["mkt-1"],
            "insight_support_quote": "O CTR foi de 2,4% no mês de julho",
            "metrics": [], "news": [],
        }
        if stage == "insight-review":
            payload["insight_support_quote"] = "O CTR cresceu 30% no mês de julho"
        return {"message": {"content": json.dumps(payload)}}

    monkeypatch.setattr("aicentralv2.cadu_workspace.insights_research._model_call", fake_model)
    context = SimpleNamespace(client_id=1, user_id=1, conversation_id=None)
    with pytest.raises(InsightsEvidenceUnavailable):
        research_market(context, "mercado de café", "test-quote-gate")


def test_quick_market_scan_includes_independent_review_before_render():
    spec = LongJobSpec(kind="market_intelligence", mode="quick", title="Quick Scan",
                       objective="Movimentos do café no Brasil", source_target=15,
                       max_agent_calls=8, max_extractor_calls=5, token_budget=24_000)

    assert [item["kind"] for item in default_units(spec)] == [
        "discover", "extract", "analyze", "review", "render",
    ]


def test_campaign_tracker_requires_an_actual_metric_value():
    assert supplied_metrics("Analise o CTR da campanha em 2026.") == []
    assert supplied_metrics("CTR: 2,4% e cliques: 1.250") == [
        {"name": "ctr", "value": "2,4", "unit": "%"},
        {"name": "cliques", "value": "1.250", "unit": ""},
    ]


def test_investment_scenarios_have_exact_totals_and_keep_missing_budget_unknown():
    with_budget = simulate("Compare cenários para R$ 100 mil")
    assert with_budget["budget_brl"] == "100000"
    for scenario in with_budget["scenarios"]:
        assert scenario["total_percent"] == 100
        assert sum(float(item["amount_brl"]) for item in scenario["allocations"]) == 100000

    without_budget = simulate("Compare cenários por percentual")
    assert without_budget["budget_brl"] is None
    assert all(item["amount_brl"] is None for scenario in without_budget["scenarios"]
               for item in scenario["allocations"])

    restricted = simulate("Distribua R$ 50 mil apenas entre Google Ads e LinkedIn")
    assert restricted["channels"] == ["Google Ads", "LinkedIn"]
    assert all([item["channel"] for item in scenario["allocations"]] == restricted["channels"]
               for scenario in restricted["scenarios"])


def test_page_review_reads_http_url_and_accepts_pasted_content(monkeypatch):
    monkeypatch.setattr("aicentralv2.cadu_workspace.agent_v2.plugins.get_plugin",
                        lambda plugin_id: {"id": plugin_id, "name": "Revisor de página", "internal_tools": []})
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")

    url = "/page-review Revise http://example.com/landing"
    plugin, tools, missing = select(route, url, request)
    assert plugin["id"] == "page-review"
    assert "web.read" in tools
    assert not missing
    assert _arguments("web.read", request, url)["url"] == "http://example.com/landing"

    pasted = "/page-review Revise esta página:\n" + ("Título: Café para sua rotina. CTA: Conheça nossos produtos.\n" * 4)
    plugin, tools, missing = select(route, pasted, request)
    assert plugin["id"] == "page-review"
    assert "web.read" not in tools
    assert not missing


def test_project_operations_require_task_ids_in_write_receipt():
    _validate_action_result("projects.create_tasks", {"created": 1, "tasks": [{"id": "task-1"}]})
    for invalid in ({"created": 0, "tasks": []},
                    {"created": 1, "tasks": [{}]},
                    {"created": 2, "tasks": [{"id": "task-1"}]}):
        with pytest.raises(ToolError):
            _validate_action_result("projects.create_tasks", invalid)
