from unittest.mock import MagicMock, patch

import pytest

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import ToolInputError, load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools.operations import get_operation
from aicentralv2.cadu_workspace.mcp.tools.artifacts import describe_types, move_project, restore_artifact_version


def _context():
    return RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id=None,
        surface="workspace", project_ref=None, capabilities=("workspace",),
    )


def test_operation_receipt_is_registered_for_external_agents():
    names = {item["name"] for item in load_builtin_tools().list(_context(), "customer_agent")}
    assert "operations.get" in names


def test_operation_receipt_query_is_tenant_and_user_scoped():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "tool_name": "projects.create_note", "status": "completed",
        "result": {"source_id": 91}, "error_code": None,
        "started_at": None, "finished_at": None, "updated_at": None,
    }]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_workspace.mcp.tools.operations.get_db", return_value=connection):
        result = get_operation(_context(), {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
            "tool_name": "projects.create_note",
        })
    assert result["status"] == "completed"
    assert result["receipts"][0]["result"] == {"source_id": 91}
    assert cursor.execute.call_args.args[1] == (
        "be777b36-a973-419c-802a-886bf1d125b0", 12, 7, "projects.create_note",
    )


def test_operation_receipt_does_not_disclose_missing_or_foreign_operations():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_workspace.mcp.tools.operations.get_db", return_value=connection), \
         pytest.raises(ToolInputError, match="não encontrada"):
        get_operation(_context(), {"request_id": "be777b36-a973-419c-802a-886bf1d125b0"})


def test_customer_agents_receive_the_canonical_persisted_artifact_catalog():
    result = describe_types(_context(), {})
    types = {item["type"]: item for item in result["types"]}

    assert "document" in types
    assert types["html"]["publishable"] is True
    assert types["link_reader"]["agent_editable"] is False
    assert "image" not in types
    assert "resource" not in types


def test_restore_version_creates_a_new_version_without_mutating_the_snapshot():
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "artifact_id": "artifact-1",
        "version": 2,
        "expected_version": 5,
    }
    restored = {"id": "artifact-1", "current_version": 6, "content": {"summary": "Versão aprovada"}}

    with patch(
        "aicentralv2.cadu_workspace.mcp.tools.artifacts.service.restore_version",
        return_value=restored,
    ) as restore_version, patch(
        "aicentralv2.cadu_workspace.mcp.tools.artifacts.operations.execute",
        side_effect=lambda _request_id, _context, _name, _payload, callback: callback(),
    ):
        result = restore_artifact_version(_context(), arguments)

    assert result == restored
    restore_version.assert_called_once_with(_context(), "artifact-1", 2, expected_version=5)


def test_mcp_move_checks_both_projects_and_updates_the_artifact():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:source", capabilities=("workspace", "artifacts"))
    arguments = {"request_id": "be777b36-a973-419c-802a-886bf1d125b0", "confirmed": True,
                 "artifact_id": "artifact-1", "destination_project_ref": "ci:target"}
    with patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.service.get_artifact",
               return_value={"id": "artifact-1", "project_ref": "ci:source"}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.repository.actor",
               return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.repository.account_role",
               return_value="editor"), \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.repository.project_user_can_view",
               return_value=True) as can_view, \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.repository.project_access",
               return_value=[{"user_id": 7, "role": "editor"}]) as access, \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.service.attach_to_project",
               return_value={"id": "artifact-1", "project_ref": "ci:target"}) as attach, \
         patch("aicentralv2.cadu_workspace.mcp.tools.artifacts.operations.execute",
               side_effect=lambda _id, _context, _name, _payload, callback: callback()):
        result = move_project(context, arguments)
    assert result["project_ref"] == "ci:target"
    assert {call.args[1] for call in can_view.call_args_list} == {"ci:source", "ci:target"}
    assert {call.args[1] for call in access.call_args_list} == {"ci:source", "ci:target"}
    attach.assert_called_once_with(context, "artifact-1", "ci:target")
