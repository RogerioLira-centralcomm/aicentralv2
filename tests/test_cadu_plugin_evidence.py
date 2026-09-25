"""Focused checks for the shared evidence boundary in Cadu plugins."""

from datetime import date

from aicentralv2.cadu_workspace.agent_v2.evidence import grounded_claims, read_status
from aicentralv2.cadu_workspace.insights_research import _safe_sources


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
