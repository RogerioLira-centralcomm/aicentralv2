from aicentralv2.cadu_workspace.agent_v2 import observability


def test_run_detail_exposes_technical_context_without_message_content(monkeypatch):
    run = {
        "id": "run-1", "conversation_id": "conversation-1", "user_id": 7,
        "status": "completed", "execution_mode": "analysis", "runtime_id": "model-1",
        "provider_config_version": "v3", "terminal_error_code": None,
        "request_context": {"selected_context": {"text": "segredo"}},
    }
    events = [
        {
            "sequence": 1, "event_type": "run.admitted", "item_type": "activity",
            "payload": {
                "context_diagnostics": {"history_message_count": 8, "retrieved_message_count": 2},
                "rollout": {"runtime_v2": True},
                "message": "pedido sensível", "response": {"answer": "resposta sensível"},
            },
            "duration_ms": None,
        },
        {
            "sequence": 2, "event_type": "run.completed", "item_type": "activity",
            "payload": {"status": "completed", "message_id": "message-2", "answer": "segredo"},
            "duration_ms": 40,
        },
    ]

    def rows(sql, params=()):
        if "FROM cadu_family_chat_runs" in sql:
            return [run]
        if "FROM cadu_agent_turn_events" in sql:
            return events
        if "FROM cadu_agent_run_steps" in sql:
            return [{"position": 1, "name": "context", "status": "completed",
                     "output_snapshot": {"answer": "segredo"}}]
        if "FROM cadu_agent_tool_calls" in sql:
            return [{"tool_name": "projects.read", "status": "completed", "duration_ms": 12}]
        if "FROM cadu_conversation_messages" in sql:
            assert params == ("conversation-1", 12)
            return [{"message_count": 9, "sequence_start": 1, "sequence_end": 9}]
        raise AssertionError(sql)

    monkeypatch.setattr(observability.repository, "rows", rows)
    detail = observability.run_detail(12, "run-1")

    assert detail["diagnostics"]["retrieved_message_count"] == 2
    assert detail["transcript"]["sequence_end"] == 9
    assert detail["tools"][0]["tool_name"] == "projects.read"
    assert detail["events"][0]["payload"] == {
        "context_diagnostics": {"history_message_count": 8, "retrieved_message_count": 2},
        "rollout": {"runtime_v2": True},
    }
    assert detail["events"][1]["payload"] == {
        "status": "completed", "message_id": "message-2",
    }
    assert "request_context" not in detail["run"]
    assert "output_snapshot" not in detail["steps"][0]
