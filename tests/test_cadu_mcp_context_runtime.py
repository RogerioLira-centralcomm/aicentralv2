from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp import context_runtime
from aicentralv2.cadu_workspace.mcp.registry import ToolInputError, load_builtin_tools


def _context(**changes):
    values = dict(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                  surface="workspace", project_ref=None, brand_ref=None,
                  capabilities=("workspace", "artifacts"))
    values.update(changes)
    return RequestContext(**values)


@dataclass
class _Principal:
    context: RequestContext
    credential_type: str = "oauth"
    key_id: str = "access-token-id"
    grant_id: str = "grant-id"
    client_type: str = "codex"


def test_context_tools_are_public_and_every_regular_tool_advertises_handle():
    tools = load_builtin_tools().list(_context(), "customer_agent")
    schemas = {item["name"]: item["inputSchema"] for item in tools}
    assert {"context.open", "context.get", "context.update", "context.close"} <= set(schemas)
    assert "context_handle" in schemas["operations.get"]["properties"]
    assert schemas["context.get"]["required"] == ["context_handle"]


def test_oauth_context_identity_is_bound_to_grant_not_rotating_access_token():
    identity = context_runtime._identity(_Principal(_context()), "customer_agent")
    assert identity["credential_id"] == "grant-id"
    assert identity["credential_type"] == "oauth"


def test_runtime_restores_context_and_hides_handle_from_tool_schema():
    principal = _Principal(_context())
    row = {"id": "context-id", "conversation_id": None, "surface": "workspace",
           "project_ref": "ci:91", "brand_ref": "studio:4", "active_object": None}
    registry = MagicMock()
    registry.execute.return_value = {"items": []}
    with patch.object(context_runtime, "_row", return_value=row), \
         patch.object(context_runtime, "_record") as record:
        result = context_runtime.execute(principal, "workspace.list_projects",
                                         {"context_handle": "cadu_ctx_valid"},
                                         "customer_agent", registry)
    called = registry.execute.call_args.args
    assert called[1] == {}
    assert called[2].project_ref == "ci:91"
    assert called[2].brand_ref == "studio:4"
    assert result["_context"]["context_handle"] == "cadu_ctx_valid"
    record.assert_called_once()


def test_context_handle_cannot_cross_credentials():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = {
        "status": "active", "expires_at": object(), "credential_id": "another-grant",
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch.object(context_runtime, "get_db", return_value=connection), \
         pytest.raises(ToolInputError, match="outra conexão"):
        context_runtime._row("cadu_ctx_abcdefghijklmnopqrstuvwxyz", _Principal(_context()), "customer_agent")


def test_context_tools_use_registry_validation_before_dispatch():
    principal = _Principal(_context())
    with patch.object(context_runtime, "available", return_value=True), \
         pytest.raises(ToolInputError, match="Campo não permitido"):
        context_runtime.execute(principal, "context.open", {"unexpected": True},
                                "customer_agent", load_builtin_tools())


def test_projection_failure_does_not_turn_successful_tool_into_failure():
    principal = _Principal(_context())
    row = {"id": "context-id", "conversation_id": None, "surface": "workspace",
           "project_ref": None, "brand_ref": None, "active_object": None,
           "exposure": "customer_agent"}
    registry = MagicMock()
    registry.execute.return_value = {"updated": True}
    with patch.object(context_runtime, "_row", return_value=row), \
         patch.object(context_runtime, "_record", side_effect=RuntimeError("database unavailable")), \
         patch.object(context_runtime, "_link_operation"):
        result = context_runtime.execute(principal, "workspace.list_projects",
                                         {"context_handle": "cadu_ctx_valid"},
                                         "customer_agent", registry)
    assert result["updated"] is True
    assert result["_context"]["context_handle"] == "cadu_ctx_valid"
