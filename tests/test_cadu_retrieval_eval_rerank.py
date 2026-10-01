"""Evaluation metrics and the optional reranker."""
import json

import pytest

from aicentralv2.cadu_workspace import retrieval_eval as ev
from aicentralv2.cadu_workspace.agent_v2 import rerank


ROWS = [{"title": "Plano", "trecho": "Canais do lançamento"},
        {"title": "Briefing", "trecho": "A verba de mídia é de R$ 50 mil"},
        {"title": "Ata", "trecho": "Público B2B"}]


def test_first_hit_rank_ignores_accents_and_case():
    assert ev.first_hit_rank(ROWS, ["VERBA DE MIDIA"]) == 2
    assert ev.first_hit_rank(ROWS, ["publico b2b"]) == 3
    assert ev.first_hit_rank(ROWS, ["orçamento"]) is None


def test_summary_reports_recall_and_mrr():
    summary = ev.summarize([1, 3, None, 6], [100, 200, 300, 400])
    assert summary["recall@3"] == 0.5 and summary["recall@5"] == 0.5 and summary["recall@8"] == 0.75
    assert summary["mrr"] == round((1 + 1 / 3 + 1 / 6) / 4, 3)
    assert summary["not_found"] == 1 and summary["latency_ms_p50"] == 250


def test_cases_file_skips_comments_and_validates(tmp_path):
    good = tmp_path / "cases.jsonl"
    good.write_text('# nota\n{"question":"q","expect_any":["x"],"project_ref":"ci:1"}\n', encoding="utf-8")
    assert ev.load_cases(str(good))[0]["id"] == "case-2"
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"question":"q"}\n', encoding="utf-8")
    with pytest.raises(Exception):
        ev.load_cases(str(bad))


def test_example_cases_file_is_valid():
    assert len(ev.load_cases("docs/cadu-eval/retrieval-cases.example.jsonl")) == 5


def test_rerank_moves_picks_first_and_keeps_omitted_rows():
    assert [r["title"] for r in rerank.apply_order(ROWS, ["2", "0"])] == ["Ata", "Plano", "Briefing"]
    assert [r["title"] for r in rerank.apply_order(ROWS, ["9", "1", "1", "x"])] == ["Briefing", "Plano", "Ata"]
    assert rerank.apply_order(ROWS, "invalid") == ROWS


def test_rerank_is_off_unless_enabled(monkeypatch):
    monkeypatch.delenv("CADU_RERANK", raising=False)
    monkeypatch.setattr(rerank, "_ask", lambda *_: pytest.fail("model must not be called"))
    assert rerank.rerank("q", ROWS) == (ROWS, False)
    assert rerank.rerank("q", ROWS, setting=False) == (ROWS, False)


def test_rerank_follows_env_and_explicit_setting(monkeypatch):
    monkeypatch.setattr(rerank, "_ask", lambda *_: ["1"])
    assert rerank.rerank("q", ROWS, setting=True)[0][0]["title"] == "Briefing"
    monkeypatch.setenv("CADU_RERANK", "1")
    assert rerank.rerank("q", ROWS)[1] is True
    assert rerank.rerank("q", ROWS, setting=False)[1] is False


def test_rerank_failure_keeps_original_order(monkeypatch):
    def fail(*_):
        raise TimeoutError
    monkeypatch.setattr(rerank, "_ask", fail)
    assert rerank.rerank("q", ROWS, setting=True) == (ROWS, False)


def test_rerank_skips_tiny_lists(monkeypatch):
    monkeypatch.setattr(rerank, "_ask", lambda *_: pytest.fail("not needed"))
    assert rerank.rerank("q", ROWS[:2], setting=True) == (ROWS[:2], False)
