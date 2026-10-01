"""The LLM memory extractor only keeps validated, user-sourced, non-duplicate items."""
import json

import pytest

from aicentralv2.cadu_workspace.conversations import memory_extractor as extractor

USER = "11111111-1111-1111-1111-111111111111"
ASSISTANT = "22222222-2222-2222-2222-222222222222"
ALLOWED = {USER: "user", ASSISTANT: "assistant"}


def raw(*items):
    return json.dumps({"items": list(items)})


def item(**overrides):
    base = {"kind": "decision", "summary": "A verba de mídia ficou em R$ 50 mil para o lançamento.",
            "confidence": 0.95, "source_message_id": USER}
    base.update(overrides)
    return base


def test_valid_user_decision_is_kept():
    assert extractor.parse_items(raw(item()), ALLOWED)[0]["kind"] == "decision"


@pytest.mark.parametrize("bad", [
    item(source_message_id=ASSISTANT),
    item(source_message_id="99999999-9999-9999-9999-999999999999"),
    item(kind="opinion"),
    item(summary="curto"),
    item(confidence="alta"),
])
def test_invalid_items_are_dropped(bad):
    assert extractor.parse_items(raw(bad), ALLOWED) == []


def test_malformed_output_yields_nothing():
    assert extractor.parse_items("não é json", ALLOWED) == []
    assert extractor.parse_items(json.dumps({"items": "x"}), ALLOWED) == []


def test_near_duplicate_items_in_one_pass_are_merged():
    result = extractor.parse_items(raw(
        item(), item(summary="A verba de mídia ficou em R$ 50 mil para o lançamento!")), ALLOWED)
    assert len(result) == 1


def test_only_clear_decisions_and_constraints_are_auto_confirmed():
    assert extractor.should_auto_confirm({"kind": "decision", "confidence": 0.9})
    assert extractor.should_auto_confirm({"kind": "constraint", "confidence": 0.85})
    assert not extractor.should_auto_confirm({"kind": "decision", "confidence": 0.8})
    assert not extractor.should_auto_confirm({"kind": "risk", "confidence": 0.99})
    assert not extractor.should_auto_confirm({"kind": "next_step", "confidence": 0.99})


class _Cursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.log.append((sql, params))


class _Connection:
    def __init__(self):
        self.log, self.committed = [], False

    def cursor(self):
        return _Cursor(self.log)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_store_skips_known_memories_and_marks_auto_confirmation(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(extractor.repository, "get_db", lambda: connection)
    monkeypatch.setattr(extractor.repository, "rows", lambda *_: [
        {"summary": "Lançamento marcado para o dia 15/10 com foco em leads."}])
    items = [
        {"kind": "decision", "summary": "Lançamento marcado para o dia 15/10 com foco em leads.",
         "confidence": 0.95, "source_message_id": USER},
        {"kind": "decision", "summary": "Verba fechada em R$ 50 mil para mídia paga.",
         "confidence": 0.95, "source_message_id": USER},
        {"kind": "risk", "summary": "Depende da liberação do estoque pelo cliente.",
         "confidence": 0.7, "source_message_id": USER},
    ]

    assert extractor._store(12, "ci:p1", "conversation-1", 7, items) == 2

    inserts = [params for sql, params in connection.log if "INSERT INTO cadu_working_memories" in sql]
    assert [(params[4], params[7]) for params in inserts] == [("decision", "confirmed"), ("risk", "proposed")]
    assert all(params[3] == "ci:p1" and params[8] == "conversation-1" for params in inserts)
    events = [params for sql, params in connection.log if "working_memory_events" in sql]
    assert json.loads(events[0][2])["auto_confirmed"] is True
    assert json.loads(events[1][2])["auto_confirmed"] is False
    assert connection.committed


def test_extraction_is_skipped_for_conversations_without_new_user_messages(monkeypatch):
    monkeypatch.setattr(extractor, "enabled", lambda: True)
    calls = []

    def rows(sql, params):
        calls.append(sql)
        if "FROM cadu_family_conversation_context" in sql:
            return [{"client_id": 12, "project_ref": "ci:p1", "author_id": 7, "author_name": "Ana Souza"}]
        if "last_sequence FROM cadu_working_memory_extraction" in sql:
            return [{"last_sequence": 4}]
        return [{"id": ASSISTANT, "role": "assistant", "content": "resposta", "conversation_sequence": 5}]

    monkeypatch.setattr(extractor.repository, "rows", rows)
    monkeypatch.setattr(extractor, "_call_model", lambda *_: pytest.fail("model must not be called"))

    assert extractor.extract_conversation("conversation-1") == 0


def test_extraction_stores_items_and_advances_the_watermark(monkeypatch):
    monkeypatch.setattr(extractor, "enabled", lambda: True)
    connection = _Connection()
    monkeypatch.setattr(extractor.repository, "get_db", lambda: connection)

    def rows(sql, params):
        if "FROM cadu_family_conversation_context" in sql:
            return [{"client_id": 12, "project_ref": "ci:p1", "author_id": 7, "author_name": "Ana Souza"}]
        if "last_sequence FROM cadu_working_memory_extraction" in sql:
            return []
        if "FROM cadu_working_memories" in sql:
            return []
        return [{"id": USER, "role": "user", "content": "Fechamos a verba em R$ 50 mil.", "conversation_sequence": 1},
                {"id": ASSISTANT, "role": "assistant", "content": "Registrado.", "conversation_sequence": 2}]

    monkeypatch.setattr(extractor.repository, "rows", rows)
    seen = {}
    monkeypatch.setattr(extractor, "_call_model", lambda window: seen.update(window=window) or raw(
        item(summary="Verba de mídia fechada em R$ 50 mil.")))

    assert extractor.extract_conversation("conversation-1") == 1

    assert seen["window"][0]["author"] == "Ana"
    watermark = [params for sql, params in connection.log if "working_memory_extraction" in sql][0]
    assert watermark[1] == 2
