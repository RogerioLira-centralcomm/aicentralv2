from aicentralv2.cadu_workspace.agent_v2 import observability


def test_run_detail_exposes_technical_context_without_message_content(monkeypatch):
    run = {
        "id": "run-1", "conversation_id": "conversation-1", "user_id": 7,
        "status": "completed", "execution_mode": "analysis", "runtime_id": "model-1",
        "provider_config_version": "v3", "terminal_error_code": None,
        "request_context": {"client_id": 12, "project_ref": "ci:project-1",
                            "selected_context": {"text": "segredo"}},
    }
    events = [
        {
            "sequence": 1, "event_type": "run.admitted", "item_type": "activity",
            "payload": {
                "context_diagnostics": {"history_message_count": 8, "retrieved_message_count": 2},
                "payload_diagnostics": {"project_evidence_tools": ["workspace.search_project_content"],
                                        "evidence_truncated": True, "evidence_chars": 4200,
                                        "prompt": "segredo"},
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
            return [{"tool_name": "workspace.search_project_content", "status": "completed", "duration_ms": 12,
                     "output_summary": {"project_evidence": {"result_count": 3,
                                     "indexed_source_count": 1, "source_inventory": {"needs_index": 2},
                                     "secret": "segredo"}}}]
        if "FROM cadu_conversation_messages" in sql:
            assert params == ("conversation-1", 12)
            return [{"message_count": 9, "sequence_start": 1, "sequence_end": 9}]
        raise AssertionError(sql)

    monkeypatch.setattr(observability.repository, "rows", rows)
    detail = observability.run_detail(12, "run-1")

    assert detail["diagnostics"]["retrieved_message_count"] == 2
    assert detail["payload_diagnostics"]["project_evidence_tools"] == ["workspace.search_project_content"]
    assert detail["transcript"]["sequence_end"] == 9
    assert detail["tools"][0]["tool_name"] == "workspace.search_project_content"
    assert detail["scope"] == {"client_id": 12, "project_ref": "ci:project-1", "brand_ref": None}
    assert detail["tools"][0]["project_evidence"]["result_count"] == 3
    assert "secret" not in detail["tools"][0]["project_evidence"]
    assert detail["events"][0]["payload"] == {
        "context_diagnostics": {"history_message_count": 8, "retrieved_message_count": 2},
        "payload_diagnostics": {"project_evidence_tools": ["workspace.search_project_content"],
                                "evidence_truncated": True, "evidence_chars": 4200},
        "rollout": {"runtime_v2": True},
    }
    assert detail["events"][1]["payload"] == {
        "status": "completed", "message_id": "message-2",
    }
    assert "request_context" not in detail["run"]
    assert "output_snapshot" not in detail["steps"][0]


def test_dashboard_flags_project_route_without_completed_retrieval(monkeypatch):
    responses = iter([
        [{"turns": 1, "failed": 0, "avg_first_token_ms": 1000}],
        [], [],
        [{"project_questions": 1, "without_project_evidence": 1}],
        [],
        [{"queued": 0, "queued_old": 0, "failed": 0, "stalled": 0}],
        [{"pending": 0, "pending_old": 0}],
    ])
    monkeypatch.setattr(observability.repository, "rows", lambda *_: next(responses))

    result = observability.dashboard(12)

    assert result["available"] is True
    assert result["project_retrieval"]["without_project_evidence"] == 1
    assert any(alert["code"] == "project_answers_without_evidence" for alert in result["alerts"])
