import pytest
from flask import Flask

from aicentralv2.cadu_workspace.agent_v2.context_builder import ConversationContextBuilder
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.conversation_runtime import RuntimeRollout, TurnIdentity
from aicentralv2.cadu_workspace.agent_v2 import memory_checkpoint
from aicentralv2.cadu_workspace.conversations import conversation_memory


RUN_ID = "be777b36-a973-419c-802a-886bf1d125b0"
CONVERSATION_ID = "11111111-1111-4111-8111-111111111111"


def request_context():
    return RequestContext(organization_id=12, client_id=12, user_id=7,
                          conversation_id=CONVERSATION_ID, surface="conversations")


def test_runtime_keeps_conversation_and_run_id_distinct():
    app = Flask(__name__)
    with app.test_request_context():
        identity = TurnIdentity.from_payload({"request_id": RUN_ID, "conversation_id": CONVERSATION_ID})
        assert identity.run_id == RUN_ID
        assert identity.conversation_id == CONVERSATION_ID
        assert identity.conversation_supplied is True
        with pytest.raises(Exception) as error:
            TurnIdentity.from_payload({"request_id": RUN_ID, "conversation_id": RUN_ID})
        assert getattr(error.value, "code", None) == 400


def test_runtime_rollout_flags_are_independent():
    app = Flask(__name__)
    app.config.update(CADU_CONVERSATION_RUNTIME_V2=True,
                      CADU_CONVERSATION_MEMORY_V2=False,
                      CADU_CHAT_SHELL_V2="off")
    with app.app_context():
        rollout = RuntimeRollout.current()
        assert rollout.runtime_v2 is True
        assert rollout.memory_v2 is False
        assert rollout.shell_v2 is False


def test_runtime_rollout_supports_internal_and_client_stages():
    app = Flask(__name__)
    app.config.update(
        CADU_CONVERSATION_RUNTIME_V2="staged",
        CADU_CONVERSATION_MEMORY_V2="allowlist",
        CADU_CHAT_SHELL_V2="internal",
        CADU_CONVERSATION_ROLLOUT_CLIENTS="12, 44",
    )
    with app.app_context():
        customer = RuntimeRollout.current(client_id=12, user_id=7)
        assert customer.runtime_v2 is True
        assert customer.memory_v2 is True
        assert customer.shell_v2 is False
        internal = RuntimeRollout.current(client_id=99, user_id=8, is_internal=True)
        assert internal.runtime_v2 is True
        assert internal.memory_v2 is False
        assert internal.shell_v2 is True
        outside = RuntimeRollout.current(client_id=99, user_id=8)
        assert outside.public_metadata() == {
            "runtime_v2": False, "memory_v2": False, "shell_v2": False,
        }


def test_context_builder_preserves_recent_bob_marley_turn_after_reload(monkeypatch):
    monkeypatch.setattr(
        "aicentralv2.cadu_workspace.agent_v2.context_builder.conversation_memory.packet",
        lambda **_: {"versao": 3, "estado": {"goal": "Falar sobre Bob Marley"}},
    )
    messages = [
        {"id": "1", "role": "user", "content": "Bob Marley foi um músico jamaicano."},
        {"id": "2", "role": "assistant", "content": "Sim, foi um dos principais nomes do reggae."},
    ]
    built = ConversationContextBuilder().build(
        message="De quem eu estava falando?", messages=messages,
        request_context=request_context(), conversation_id=CONVERSATION_ID,
    )
    assert "Bob Marley" in built.history
    assert built.diagnostics["history_message_count"] == 2
    assert built.diagnostics["memory_present"] is True
    assert built.routing_message == "De quem eu estava falando?"


def test_memory_checkpoint_is_scheduled_outside_the_response(monkeypatch):
    statements = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, sql, params): statements.append((sql, params))

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): statements.append(("commit", ()))
        def rollback(self): statements.append(("rollback", ()))

    app = Flask(__name__)
    monkeypatch.setattr(memory_checkpoint.repository, "get_db", lambda: Connection())
    with app.app_context():
        result = memory_checkpoint.schedule(
            conversation_id=CONVERSATION_ID, organization_id=12, client_id=12, user_id=7,
        )

    assert result is True
    assert "cadu_conversation_memory_jobs" in statements[0][0]
    assert statements[0][1] == (CONVERSATION_ID, 12, 12, 7)
    assert statements[-1][0] == "commit"


def test_memory_rebuild_command_fails_cleanly_before_migration(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(conversation_memory, "available", lambda: False)
    result = app.test_cli_runner().invoke(
        conversation_memory.rebuild_command,
        ["--conversation-id", CONVERSATION_ID],
    )
    assert result.exit_code == 1
    assert "add_cadu_conversation_memory.sql" in result.output
