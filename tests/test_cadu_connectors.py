from aicentralv2.services.cadu_connectors import registry


def test_connector_registry_has_google_as_active_foundation_and_slack_as_next_adapter():
    assert registry.get("google_workspace").status == "active"
    assert registry.get("google_workspace").auth_modes == ("oauth2",)
    assert registry.get("slack").status == "planned"
    assert "events" in registry.get("slack").capabilities


def test_connector_registry_is_safe_for_integration_catalogs():
    items = registry.list()
    assert [item["key"] for item in items] == ["canva", "clickup", "google_workspace", "slack", "trello"]
    assert all("client_secret" not in str(item) and "token" not in str(item) for item in items)
