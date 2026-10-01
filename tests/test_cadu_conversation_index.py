"""Conversation excerpts are rebuilt incrementally and searched across the project team."""
import pytest

from aicentralv2.cadu_workspace import conversation_index, project_knowledge


def message(sequence, role, content):
    return {"id": f"m{sequence}", "role": role, "content": content,
            "conversation_sequence": sequence, "created_at": f"2026-09-{sequence:02d}",
            "author_name": "Ana"}


def test_segments_use_fixed_windows_and_label_authors():
    messages = [message(index, "user" if index % 2 else "assistant", f"texto {index}") for index in range(1, 9)]
    result = conversation_index.segments(messages)
    assert [item["segment_index"] for item in result] == [0, 1]
    assert result[0]["first_sequence"] == 1 and result[0]["last_sequence"] == 6
    assert result[0]["content"].startswith("Usuário (Ana): texto 1\nAssistente: texto 2")
    assert result[1]["message_ids"] == ["m7", "m8"]


def test_segments_strip_reasoning_and_bound_assistant_text():
    long_answer = "<think>privado</think>" + "resposta " * 400
    result = conversation_index.segments([message(1, "user", "pergunta"), message(2, "assistant", long_answer)])
    assert "privado" not in result[0]["content"]
    assert len(result[0]["content"].split("\n")[1]) <= len("Assistente: ") + conversation_index.ASSISTANT_CHARS + 1


class _Cursor:
    def __init__(self, executed):
        self.executed = executed

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.executed.append(params)


class _Connection:
    def __init__(self):
        self.executed = []
        self.committed = False

    def cursor(self):
        return _Cursor(self.executed)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_index_conversation_embeds_only_changed_segments(monkeypatch):
    transcript = [message(index, "user" if index % 2 else "assistant", f"texto {index}") for index in range(1, 9)]
    unchanged_hash = conversation_index.segments(transcript)[0]["content_hash"]

    def rows(sql, params):
        if "FROM cadu_conversations conversation" in sql:
            return [{"client_id": 12, "author_name": "Ana Souza"}]
        if "FROM cadu_conversation_messages" in sql:
            return [dict(item) for item in transcript]
        return [{"segment_index": 0, "content_hash": unchanged_hash}]

    embedded = []
    def embed(texts):
        embedded.extend(texts)
        return [[0.0] * project_knowledge.EMBEDDING_DIMENSIONS for _ in texts], 1, "test-model"

    connection = _Connection()
    monkeypatch.setattr(conversation_index.repository, "rows", rows)
    monkeypatch.setattr(conversation_index.repository, "get_db", lambda: connection)
    monkeypatch.setattr(conversation_index.project_knowledge, "_embed", embed)

    assert conversation_index.index_conversation("conversation-1") == 1
    assert embedded == [conversation_index.segments(transcript)[1]["content"]]
    assert connection.committed
    assert connection.executed[0][1] == 12


def test_project_search_is_scoped_to_client_and_project_not_author(monkeypatch):
    captured = {}
    def rows(sql, params):
        captured["sql"], captured["params"] = sql, params
        return [{"chunk_id": 9, "conversation_id": "c1", "content": "Usuário (Ana): verba de 50 mil",
                 "message_ids": ["m1", "m2"], "last_message_at": "2026-09-20",
                 "conversation_title": "Planejamento", "score": 0.03}]

    monkeypatch.setattr(conversation_index.repository, "rows", rows)
    monkeypatch.setattr(conversation_index.project_knowledge, "query_embedding",
                        lambda _query: [0.0] * project_knowledge.EMBEDDING_DIMENSIONS)

    results = conversation_index.search_project(client_id=12, project_ref="ci:p1",
                                                query="qual a verba do Google Ads?",
                                                exclude_conversation_id="current")

    assert "binding.project_ref=%s" in captured["sql"]
    assert "user_id" not in captured["sql"] and "id_contato_cliente" not in captured["sql"]
    assert captured["params"][1:5] == (12, 12, "ci:p1", "current")
    assert results[0]["evidence_level"] == "conversation_excerpt"
    assert results[0]["message_id"] == "m1"


def test_project_search_falls_back_to_lexical_without_embeddings(monkeypatch):
    captured = {}
    monkeypatch.setattr(conversation_index.repository, "rows",
                        lambda sql, params: captured.update(sql=sql) or [])
    def unavailable(_query):
        raise project_knowledge.KnowledgeIndexError("offline")
    monkeypatch.setattr(conversation_index.project_knowledge, "query_embedding", unavailable)

    assert conversation_index.search_project(client_id=12, project_ref="ci:p1", query="verba",
                                             exclude_conversation_id=None) == []
    assert "AND FALSE" in captured["sql"]
