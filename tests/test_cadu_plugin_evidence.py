"""Focused checks for the shared evidence boundary in Cadu plugins."""

from datetime import date, datetime, timezone

from aicentralv2.cadu_workspace.agent_v2.evidence import grounded_claims, read_status, supporting_refs
from aicentralv2.cadu_workspace.insights_research import (
    InsightsEvidenceUnavailable, _safe_sources, _read_source_contents, research_market,
)
from aicentralv2.cadu_workspace.agent_v2.long_jobs import LongJobSpec, default_units
from aicentralv2.cadu_workspace.agent_v2.campaign_metrics import supplied_metrics
from aicentralv2.cadu_workspace.agent_v2.investment_scenarios import simulate
from aicentralv2.cadu_workspace.agent_v2.media_plan_review import review_media_plan
from aicentralv2.cadu_workspace.agent_v2.performance_review import review_supplied_metrics
from aicentralv2.cadu_workspace.agent_v2.market_radar import requested_recency, relevant_read_sources
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
            "published_at": datetime.now(timezone.utc).date().isoformat(),
            "published_at_source": "page", "read_status": "read",
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


def test_insights_expand_search_when_initial_sources_are_unreadable(monkeypatch):
    from types import SimpleNamespace
    import json

    searches = []

    def fake_search(_context, arguments):
        searches.append(arguments["query"])
        if len(searches) == 1:
            return {"query": arguments["query"], "sources": [{
                "url": "https://example.com/search", "title": "Busca", "excerpt": "Só metadados",
            }], "sources_read": 0}
        return {"sources": [{
            "url": "https://example.com/report", "title": "Relatório", "content": "O CTR foi de 2,4% em julho no Brasil.",
            "published_at": datetime.now(timezone.utc).date().isoformat(), "read_status": "read",
        }], "sources_read": 1}

    def fake_model(*, stage, **_kwargs):
        if stage == "perplexity-research":
            return {"message": {"content": "Pesquisa preliminar."}}
        payload = {
            "headline": "CTR de 2,4%", "headline_source_ids": ["mkt-2"],
            "headline_support_quote": "O CTR foi de 2,4% em julho no Brasil",
            "insight": "O CTR foi de 2,4% em julho no Brasil.", "insight_source_ids": ["mkt-2"],
            "insight_support_quote": "O CTR foi de 2,4% em julho no Brasil",
            "metrics": [], "news": [],
        }
        return {"message": {"content": json.dumps(payload)}}

    monkeypatch.setattr("aicentralv2.cadu_workspace.insights_research.web_search.search", fake_search)
    monkeypatch.setattr("aicentralv2.cadu_workspace.insights_research._model_call", fake_model)
    context = SimpleNamespace(client_id=1, user_id=1, conversation_id=None)
    result = research_market(context, "mercado de café", "test-expansion")

    assert len(searches) == 2
    assert result["sources"][0]["url"] == "https://example.com/report"


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


def test_campaign_metric_review_calculates_conditional_ratios_without_period_claims():
    result = review_supplied_metrics("Impressões: 50.000; cliques: 1.250; investimento: R$ 2.500; receita: R$ 5.000")

    assert {item["name"]: item["value"] for item in result["derived_metrics"]} == {
        "CTR calculado": "2.50", "CPC calculado": "2.00",
        "CPM calculado": "50.00", "ROAS calculado": "2.00",
    }
    assert result["period_verified"] is False
    assert all("mesmo período" in item["condition"] for item in result["derived_metrics"])


def test_campaign_metric_review_does_not_mix_repeated_values():
    result = review_supplied_metrics("cliques: 100 em julho; cliques: 200 em agosto; impressões: 1.000")
    assert result["status"] == "ambiguous"
    assert result["repeated_metrics"] == ["cliques"]
    assert result["derived_metrics"] == []


def test_campaign_tracker_routes_text_metrics_to_deterministic_review(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools

    monkeypatch.setattr("aicentralv2.cadu_workspace.agent_v2.plugins.get_plugin",
                        lambda plugin_id: {"id": plugin_id, "name": "Acompanhamento", "internal_tools": []})
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             capabilities=("reports",))
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")
    message = "/campaign-tracker Analise impressões: 50.000 e cliques: 1.250"

    plugin, tools, missing = select(route, message, request)
    assert plugin["id"] == "campaign-tracker"
    assert tools == ("campaign.review_supplied_metrics",)
    assert not missing
    assert _arguments(tools[0], request, message) == {"query": message}
    registry = load_builtin_tools()
    assert any(item["name"] == tools[0] for item in registry.list(request))
    reviewed = registry.execute(tools[0], _arguments(tools[0], request, message), request)
    assert {item["name"] for item in reviewed["derived_metrics"]} == {"CTR calculado"}


def test_market_radar_uses_requested_time_window():
    assert requested_recency("Veja movimentos de hoje") == "day"
    assert requested_recency("Radar dos últimos 7 dias") == "week"
    assert requested_recency("Radar do último mês") == "month"
    assert requested_recency("Radar da marca") == "year"


def test_market_radar_filters_unread_and_generic_search_hits():
    brand = {"name": "Café Aurora", "market": {"competitors": [{"name": "Café Horizonte"}]}}
    result = {"sources": [
        {"url": "https://example.com/a", "title": "Café Aurora lança campanha", "excerpt": "Resultado de busca"},
        {"url": "https://example.com/b", "title": "Como fazer benchmarking", "content": "Guia genérico de marketing."},
        {"url": "https://example.com/c", "title": "Notícia setorial", "content": "Café Horizonte lançou nova linha."},
    ]}

    assert [item["url"] for item in relevant_read_sources(brand, result)] == ["https://example.com/c"]


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
    assert simulate("Distribua R$ 1.000,50")["budget_brl"] == "1000.50"
    assert simulate("Distribua R$ 1,5 milhão")["budget_brl"] == "1500000.0"


def test_media_plan_review_checks_budget_weights_and_channel_scope():
    plan = {
        "briefing": {"budget": "R$ 100.000"},
        "items": [{"kind": "canais", "resource_id": "social"}],
        "allocations": [
            {"resource_id": "social", "weight": "60", "investment": "50000"},
            {"resource_id": "search", "weight": "30", "investment": "40000"},
        ],
    }

    review = review_media_plan(plan)

    assert review["status"] == "issues"
    assert review["total_weight_percent"] == "90"
    assert review["total_investment_brl"] == "90000"
    assert {item["code"] for item in review["findings"]} == {
        "weight_total", "budget_total", "unselected_channel",
    }


def test_media_plan_review_keeps_unknown_budget_unknown():
    review = review_media_plan({
        "briefing": {"budget": "A definir"},
        "items": [{"kind": "canais", "resource_id": "social"}],
        "allocations": [{"resource_id": "social", "weight": "100", "investment": "500"}],
    })

    assert review["status"] == "clear_within_checked_fields"
    assert review["budget_brl"] is None
    assert review["findings"] == []


def test_media_plan_review_flags_missing_selection_and_duplicate_channel():
    review = review_media_plan({
        "items": [],
        "allocations": [
            {"resource_id": "social", "weight": "50", "investment": "500"},
            {"resource_id": "social", "weight": "50", "investment": "500"},
        ],
    })
    assert {item["code"] for item in review["findings"]} == {"no_selected_channels", "duplicate_channel"}


def test_planner_read_includes_calculation_review(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.tools import planner

    monkeypatch.setattr(planner.plans, "get_plan", lambda *_args: {
        "id": "plan-1", "title": "Plano", "briefing": {"budget": "R$ 1.000"},
        "items": [{"kind": "canais", "resource_id": "social"}],
        "allocations": [{"resource_id": "social", "weight": "100", "investment": "800"}],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="planner")

    result = planner.get_media_plan(request, {"plan_id": "plan-1"})

    assert result["calculation_review"]["budget_brl"] == "1000"
    assert [item["code"] for item in result["calculation_review"]["findings"]] == ["budget_total"]


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
