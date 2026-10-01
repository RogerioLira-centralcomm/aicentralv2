"""Project suggestions are conservative, owner-scoped and never bind a conversation."""
import numpy as np
import pytest

from aicentralv2.cadu_workspace import conversation_project_suggestions as sg


def test_clear_winner_is_suggested():
    result = sg.decide([("ci:a", 0.62), ("ci:b", 0.41)], False)
    assert result["project_ref"] == "ci:a" and result["runner_up_ref"] == "ci:b"


@pytest.mark.parametrize("ranked", [
    [("ci:a", 0.55), ("ci:b", 0.54)],
    [("ci:a", 0.30), ("ci:b", 0.10)],
    [],
])
def test_ambiguous_or_weak_matches_are_not_suggested(ranked):
    assert sg.decide(ranked, False) is None


def test_name_mention_lowers_the_bar_but_not_to_zero():
    assert sg.decide([("ci:a", 0.33), ("ci:b", 0.32)], True)["name_mentioned"] is True
    assert sg.decide([("ci:a", 0.20), ("ci:b", 0.05)], True) is None


def test_single_project_needs_the_minimum_score():
    assert sg.decide([("ci:a", 0.45)], False)["runner_up_ref"] is None
    assert sg.decide([("ci:a", 0.35)], False) is None


def test_rank_projects_orders_by_cosine_and_handles_zero_vectors():
    profiles = {"ci:a": np.array([1.0, 0.0]), "ci:b": np.array([0.0, 1.0])}
    ranked = sg.rank_projects(np.array([0.9, 0.1]), profiles)
    assert [ref for ref, _ in ranked] == ["ci:a", "ci:b"]
    assert sg.rank_projects(np.zeros(2), profiles) == []


def test_generate_only_offers_projects_the_owner_can_open(monkeypatch):
    profiles = {"ci:private": np.array([1.0, 0.0]), "ci:team": np.array([0.8, 0.6])}
    monkeypatch.setattr(sg, "project_profiles", lambda _client: (profiles, {"ci:private": "Sigilo", "ci:team": "Equipe"}))
    monkeypatch.setattr(sg, "_unbound_conversations", lambda *_: [{"id": "c1", "owner_id": 7}])
    monkeypatch.setattr(sg, "_conversation_vector", lambda _id: np.array([1.0, 0.0]))
    monkeypatch.setattr(sg, "_name_mentioned", lambda *_: False)
    monkeypatch.setattr(sg.repository, "project_user_can_view", lambda client, ref, user: ref == "ci:team")
    saved = []
    monkeypatch.setattr(sg, "_save", lambda client, conversation, decision: saved.append((conversation, decision)))

    stats = sg.generate(12, min_score=0.5, margin=0.0)

    assert stats["suggested"] == 1 and saved[0][1]["project_ref"] == "ci:team"
    assert all(item[1]["project_ref"] != "ci:private" for item in saved)


def test_dry_run_saves_nothing_and_reports_scores(monkeypatch):
    monkeypatch.setattr(sg, "project_profiles", lambda _c: ({"ci:a": np.array([1.0, 0.0])}, {"ci:a": "Alfa"}))
    monkeypatch.setattr(sg, "_unbound_conversations", lambda *_: [{"id": "c1", "owner_id": 7}])
    monkeypatch.setattr(sg, "_conversation_vector", lambda _id: np.array([1.0, 0.0]))
    monkeypatch.setattr(sg, "_name_mentioned", lambda *_: False)
    monkeypatch.setattr(sg.repository, "project_user_can_view", lambda *_: True)
    monkeypatch.setattr(sg, "_save", lambda *_: pytest.fail("dry run must not write"))
    stats = sg.generate(12, dry_run=True)
    assert stats["suggested"] == 1 and stats["scores"] == [pytest.approx(1.0)]


def test_pending_suggestion_is_hidden_when_the_project_is_no_longer_viewable(monkeypatch):
    monkeypatch.setattr(sg.repository, "rows", lambda *_: [{"project_ref": "ci:a", "score": 0.6, "project_name": "Alfa"}])
    monkeypatch.setattr(sg.repository, "project_user_can_view", lambda *_: False)
    assert sg.pending_for_owner(7, 12, "c1") is None
    monkeypatch.setattr(sg.repository, "project_user_can_view", lambda *_: True)
    assert sg.pending_for_owner(7, 12, "c1")["project_name"] == "Alfa"


def test_pending_query_is_scoped_to_the_owner_and_unbound_conversations(monkeypatch):
    captured = {}
    monkeypatch.setattr(sg.repository, "rows", lambda sql, params: captured.update(sql=sql, params=params) or [])
    assert sg.pending_for_owner(7, 12, "c1") is None
    assert "conversation.id_contato_cliente=%s" in captured["sql"]
    assert "binding.project_ref IS NULL" in captured["sql"]
    assert captured["params"] == ("c1", 12, 7, 12)


def test_suggestions_never_write_the_conversation_binding():
    import inspect
    source = inspect.getsource(sg)
    assert "cadu_family_conversation_context SET" not in source
    assert "INSERT INTO cadu_family_conversation_context" not in source
    assert "move_conversation_project" not in source
