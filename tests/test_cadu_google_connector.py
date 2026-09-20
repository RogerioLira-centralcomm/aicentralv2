from unittest.mock import patch

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools
from aicentralv2.services.cadu_google_connector import connector


def context(**overrides):
    values = {
        "organization_id": 12,
        "client_id": 12,
        "user_id": 7,
        "conversation_id": "conversation-1",
        "surface": "conversations",
        "project_ref": "ci:project-1",
        "brand_ref": None,
        "capabilities": ("workspace",),
    }
    values.update(overrides)
    return RequestContext(**values)


def test_global_connector_exposes_user_project_and_google_status_without_secrets():
    matrix = {
        "services": [{"key": "drive", "status": "enabled"}],
        "summary": {"enabled_count": 1, "total_count": 1, "pending_count": 0},
        "configuration": {
            "configured": True,
            "missing": [],
            "redirect_uri": "https://auth.centralcomm.media/auth/google/workspace/callback",
        },
    }
    connection = {
        "status": "connected",
        "google_email": "workspace@example.com",
        "google_domain": "example.com",
        "granted_scopes": "scope-a scope-b",
        "last_sync_at": None,
        "encrypted_refresh_token": "must-not-leak",
    }
    with patch("aicentralv2.services.cadu_google_connector.google_workspace.service_matrix", return_value=matrix), \
         patch("aicentralv2.services.cadu_google_connector.google_workspace.get_connection", return_value=connection):
        result = connector.status(context())

    assert result["connector"] == "cadu_google"
    assert result["context"]["user_id"] == 7
    assert result["context"]["project_ref"] == "ci:project-1"
    assert result["permissions"]["user_can_link_project_resources"] is True
    assert result["connection"]["account"]["email"] == "workspace@example.com"
    assert "encrypted_refresh_token" not in str(result)


def test_global_connector_exposes_calendar_and_meet_without_provider_tokens():
    with patch("aicentralv2.services.cadu_google_connector.google_workspace.list_calendar_events", return_value=[{"id": "event-1"}]), \
         patch("aicentralv2.services.cadu_google_connector.google_workspace.list_meet_conference_records", return_value=[{"name": "conferenceRecords/1"}]):
        events = connector.list_calendar_events(context(), limit=5)
        records = connector.list_meet_records(context(), limit=5)

    assert events["events"] == [{"id": "event-1"}]
    assert records["conference_records"] == [{"name": "conferenceRecords/1"}]
    assert "encrypted_refresh_token" not in str(events)
    assert "encrypted_refresh_token" not in str(records)


def test_global_connector_lists_only_resources_linked_to_current_project():
    with patch("aicentralv2.services.cadu_google_connector.repository.rows", return_value=[{"id": "project-1"}]), \
         patch("aicentralv2.services.cadu_google_connector.google_workspace.list_resources", return_value=[{"id": "resource-1"}]) as list_resources:
        result = connector.list_project_resources(context(), limit=10)

    list_resources.assert_called_once_with(12, project_ref="ci:project-1", limit=10)
    assert result == {
        "connector": "cadu_google",
        "project_ref": "ci:project-1",
        "user_id": 7,
        "resources": [{"id": "resource-1"}],
        "total": 1,
    }


def test_google_tools_are_available_through_the_cadu_mcp_registry():
    names = {
        item["name"] for item in load_builtin_tools().list(context(), "customer_agent")
    }
    assert {
        "google.get_connector_status",
        "google.list_project_resources",
        "google.link_resource_to_project",
    } <= names
    assert "google.sync_workspace" not in names
    assert "google.sync_workspace" in {
        item["name"] for item in load_builtin_tools().list(context(), "internal")
    }
