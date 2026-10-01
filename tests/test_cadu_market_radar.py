"""Market radar: brand-scoped search, read-source filter, fallback, and evidence that survives the prompt budget."""
import json

import pytest

from aicentralv2.cadu_workspace.agent_v2 import executor, plugins
from aicentralv2.cadu_workspace.agent_v2.context_resolver import ResolvedContext
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import _bounded_json

BRAND = {"name": "Acme", "sector": "tecnologia", "website_url": "https://acme.com.br",
         "market": {"competitors": [{"name": "Beta Corp"}, {"name": "Gama SA"}]}}


def page(index, text, **extra):
    return {"id": f"w{index}", "title": f"Fonte {index}", "url": f"https://site{index}.com/n",
            "published_at": "2026-09-25", "content": text, "content_blocks": [{"text": text}],
            "content_excerpt": text[:200], "quality_gate": "passed", **extra}


@pytest.fixture(autouse=True)
def radar_environment(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda pid: {"id": pid, "name": pid, "maturity": "active",
                        "internal_tools": [], "manifest": {}, "selectable": True, "version": "1"})
    monkeypatch.setattr(executor, "recent_preferences", lambda *a, **k: [])
    monkeypatch.setattr(executor, "close_db", lambda: None)


def request(project=True):
    return RequestContext(client_id=1, user_id=7, conversation_id="c", surface="conversations",
                          project_ref="ci:t" if project else None, capabilities=("workspace",))


def install(monkeypatch, searches, brand=BRAND):
    calls = []

    def resolve(route, req, message, registry, mode, **kwargs):
        calls.append({"tools": route.needs_tools, "overrides": kwargs.get("tool_argument_overrides") or {}})
        values = {"current_context": req.to_dict()}
        for tool in route.needs_tools:
            if tool == "brands.get_context":
                if brand:
                    values[tool] = dict(brand)
            elif tool == "web.search":
                issued = (kwargs.get("tool_argument_overrides") or {}).get("web.search", {}).get("query")
                values[tool] = {"query": issued, **(searches.pop(0) if searches else {"sources": []})}
            else:
                values[tool] = {"status": "ok"}
        return ResolvedContext(values=values, tool_calls=[])

    monkeypatch.setattr(executor, "resolve_context", resolve)
    return calls


def run(message="/market-radar Movimentos recentes da marca e dos concorrentes", project=True):
    return executor.prepare_execution(message, request(project))


def test_radar_searches_by_brand_and_competitors_never_by_project_name(monkeypatch):
    calls = install(monkeypatch, [{"sources": [page(1, "A Acme e a Beta Corp lançaram novas campanhas de verão. " * 10)]}])
    execution = run()
    searches = [c for c in calls if "web.search" in c["tools"]]
    query = searches[0]["overrides"]["web.search"]["query"]
    assert "Acme" in query and "Beta Corp" in query and "Lançamento" not in query
    assert execution["route"]["action"] == "run_plugin"
    assert execution["route"]["response_mode"] == "analysis"


def test_only_read_pages_naming_the_brand_or_a_competitor_reach_the_model(monkeypatch):
    sources = [page(1, "A Acme anunciou uma nova campanha de mídia. " * 8),
               page(2, "Cinco dicas para analisar concorrentes no seu negócio. " * 8),
               {"id": "d", "title": "Acme descoberta", "url": "https://x.com", "snippet": "só resumo"}]
    install(monkeypatch, [{"sources": sources, "source_count": 3, "sources_read": 2}])
    evidence = json.loads(run()["provider_payload"]["inputs"]["evidence"])["web.search"]
    assert [s["id"] for s in evidence["sources"]] == ["w1"]
    assert evidence["radar_evidence_filter"].startswith("read pages naming the brand")


def test_search_is_broadened_once_when_nothing_relevant_was_read(monkeypatch):
    irrelevant = {"sources": [page(1, "Guia genérico de análise competitiva. " * 10)]}
    relevant = {"sources": [page(2, "A Gama SA abriu uma nova loja e a Acme respondeu com promoção. " * 6)]}
    calls = install(monkeypatch, [irrelevant, relevant])
    execution = run()
    queries = [c["overrides"]["web.search"]["query"] for c in calls if "web.search" in c["tools"]]
    assert len(queries) == 2 and queries[0] != queries[1] and "notícia" in queries[1]
    evidence = json.loads(execution["provider_payload"]["inputs"]["evidence"])["web.search"]
    assert evidence["search_expanded"] is True and [s["id"] for s in evidence["sources"]] == ["w2"]


def test_no_relevant_read_page_becomes_an_honest_gap_not_generic_findings(monkeypatch):
    install(monkeypatch, [{"sources": [page(1, "Guia genérico. " * 20)]}, {"sources": []}])
    execution = run()
    assert execution["route"]["action"] == "clarify_plugin_evidence"
    assert execution["policy"]["action_preflight"]["ready"] is False
    assert "Não apresente movimentos" in execution["policy"]["plugin_instruction"]


def test_without_a_resolvable_brand_the_radar_does_not_search(monkeypatch):
    calls = install(monkeypatch, [], brand=None)
    execution = run()
    assert execution["route"]["action"] == "clarify_plugin_context"
    assert not any("web.search" in c["tools"] for c in calls)
    assert execution["policy"]["action_preflight"]["missing"] == ["marca única vinculada ao projeto"]


def test_large_web_evidence_is_shrunk_not_dropped():
    sources = [page(i, ("A Acme lançou novidades no mercado. " * 180)[:6000]) for i in range(8)]
    value = {"current_context": {"client_id": 1}, "brands.get_context": BRAND,
             "web.search": {"query": "Acme", "sources": sources, "source_count": 8, "sources_read": 8}}
    for budget in (36000, 22000, 12000):
        out = json.loads(_bounded_json(value, budget))
        web = out["web.search"]
        assert len(web["sources"]) == 8, budget
        assert all(s["url"] and s["read_status"] == "read" and "content_blocks" not in s for s in web["sources"])
        assert len(json.dumps(out, separators=(",", ":"), ensure_ascii=False)) <= budget


def test_read_sources_are_kept_before_discovered_ones_when_space_runs_out():
    sources = [{"id": "d", "title": "Descoberta", "url": "https://d.com", "snippet": "x" * 300}] + \
              [page(i, "A Acme anunciou. " * 400) for i in range(1, 6)]
    value = {"current_context": {}, "web.search": {"sources": sources}}
    out = json.loads(_bounded_json(value, 1900))
    ids = [s["id"] for s in out["web.search"]["sources"]]
    assert ids[0] == "w1" and "d" not in ids[:3]
    assert out["web.search"].get("content_truncated") is True


from aicentralv2.cadu_workspace.agent_v2.plugins import _MARKET_RADAR


@pytest.mark.parametrize("message", [
    "Quais os movimentos recentes dos concorrentes da marca?",
    "O que a concorrência lançou esta semana?",
    "Acompanhe os lançamentos dos concorrentes",
    "Me traga novidades dos concorrentes",
    "Radar da marca",
    "Monitore os concorrentes do setor",
])
def test_radar_is_selected_by_natural_requests(message):
    assert _MARKET_RADAR.search(message)


@pytest.mark.parametrize("message", [
    "Crie um plano de lançamento para o mercado brasileiro",
    "Monte a campanha de lançamento da marca",
    "Qual a verba do lançamento?",
    "Liste as novidades do produto no site",
])
def test_radar_does_not_hijack_ordinary_marketing_requests(message):
    assert not _MARKET_RADAR.search(message)
