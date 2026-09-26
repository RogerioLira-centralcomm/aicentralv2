from aicentralv2.cadu_workspace.agent_v2 import plugins
from aicentralv2.cadu_workspace.agent_v2.contracts import IntentRoute, RequestContext


def test_plugin_capability_catalog_reports_allowlist_drift(monkeypatch):
    monkeypatch.setattr(plugins, "list_entries", lambda _kind: [{
        "id": "audience-map",
        "internal_tools": ["web.search", "planner.research_plan_inputs"],
        "manifest": {},
    }])

    [entry] = plugins.catalog()

    assert entry["manifest_tools_unavailable"] == []
    assert entry["runtime_tools_not_documented"] == [
        "brands.get_context", "workspace.get_project_context",
    ]
    assert entry["tool_contract_matches_manifest"] is False
    assert entry["provider_dependencies"] == ["firecrawl"]


def test_optional_context_tools_are_allowlisted_but_not_called_without_context(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": "Mapa de audiência", "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")
    message = "/audience-map " + "Mapeie segmentos possíveis no canal indicado, explicando necessidades e sinais verificáveis. " * 2

    selected, called_tools, missing = plugins.select(route, message, request)

    assert selected["runtime_tools"] == [
        "web.search", "planner.research_plan_inputs",
        "workspace.get_project_context", "brands.get_context",
    ]
    assert called_tools == ("web.search", "planner.research_plan_inputs")
    assert not missing


def test_optional_context_tools_are_called_only_for_selected_context(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": "Mapa de audiência", "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             project_ref="ci:42", brand_ref="brand:7")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")

    selected, called_tools, missing = plugins.select(route, "/audience-map Mapear audiência para social.", request)

    assert called_tools == (
        "workspace.get_project_context", "brands.get_context",
        "web.search", "planner.research_plan_inputs",
    )
    assert set(called_tools) <= set(selected["runtime_tools"])
    assert not missing


def test_campaign_search_keeps_project_search_chain_minimal(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": "Buscar campanhas", "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             project_ref="ci:42")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")

    selected, called_tools, missing = plugins.select(route, "Busque campanhas de café.", request)

    assert selected["id"] == "campaign-search"
    assert called_tools == ("workspace.search_project_content",)
    assert set(called_tools) <= set(selected["runtime_tools"])
    assert not missing


def test_clear_natural_language_selects_specialist_modes(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": plugin_id, "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             project_ref="ci:42", brand_ref="brand:7")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")
    cases = [
        ("Audite o plano de mídia e aponte incoerências.", "media-plan-audit"),
        ("Simule cenários de investimento para a campanha.", "investment-simulator"),
        ("Mapeie a audiência e os segmentos para a campanha.", "audience-map"),
        ("Proponha um conceito criativo para a marca.", "creative-concept"),
        ("Escreva variações de texto para Instagram.", "channel-copy"),
        ("Organize o status das entregas e pendências para o cliente.", "client-delivery"),
        ("Prepare a pauta da reunião semanal.", "meeting-copilot"),
        ("Veja os movimentos recentes dos concorrentes da marca.", "market-radar"),
    ]

    for message, expected_plugin in cases:
        selected, called_tools, missing = plugins.select(route, message, request)
        assert selected["id"] == expected_plugin, message
        assert set(called_tools) <= set(selected["runtime_tools"]), message
        assert not missing, message


def test_specialist_selection_does_not_override_confirmation_routes(monkeypatch):
    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": plugin_id, "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             project_ref="ci:42")
    route = IntentRoute(domain="workspace", action="schedule_project_meeting", complexity="medium",
                        response_mode="decision", requires_confirmation=True)

    selected, called_tools, missing = plugins.select(route, "Agende uma reunião e prepare a pauta.", request)

    assert selected["id"] == "google-calendar"
    assert called_tools == ()
    assert missing == []


def test_every_plugin_tool_contract_resolves_to_a_registered_internal_tool():
    from aicentralv2.cadu_workspace.agent_v2.plugins import PLUGIN_FLOW, _execution_tools, WORKFLOWS
    from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools

    plugin_ids = set(PLUGIN_FLOW) | set(WORKFLOWS) | {
        "google-connect", "google-drive", "google-calendar", "google-meet",
    }
    registry = load_builtin_tools()
    registered = set(registry._tools)

    assert plugin_ids
    for plugin_id in plugin_ids:
        assert set(_execution_tools(plugin_id)) <= registered, plugin_id


def test_explicit_specialist_workflows_dispatch_only_registered_tools(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools

    monkeypatch.setattr(plugins, "get_plugin", lambda plugin_id: {
        "id": plugin_id, "name": plugin_id, "internal_tools": [],
    })
    request = RequestContext(client_id=1, user_id=1, conversation_id=None, surface="conversations",
                             project_ref="ci:42", brand_ref="brand:7")
    route = IntentRoute(domain="general", action="answer", complexity="medium", response_mode="analysis")
    cases = [
        ("/market-intelligence Pesquise tendências recentes do setor de café.", "market-intelligence", False),
        ("/market-radar Pesquise movimentos recentes da marca selecionada.", "market-radar", False),
        ("/audience-map Mapeie a audiência do Instagram para esta campanha.", "audience-map", False),
        ("/investment-simulator Simule cenários de investimento para esta campanha.", "investment-simulator", False),
        ("/media-plan-audit Revise o plano de mídia deste projeto.", "media-plan-audit", False),
        ("/campaign-tracker Analise o relatório da campanha anexado.", "campaign-tracker", True),
        ("/creative-concept Crie um conceito criativo para esta campanha.", "creative-concept", False),
        ("/channel-copy Escreva copy para Instagram para esta campanha.", "channel-copy", False),
        ("/page-review https://example.com Revise a página informada.", "page-review", False),
        ("/meeting-copilot Prepare a pauta para a reunião do Google Meet.", "meeting-copilot", False),
        ("/client-delivery Organize as entregas e pendências deste projeto.", "client-delivery", False),
    ]
    registered = set(load_builtin_tools()._tools)

    for message, expected_plugin, has_attachment in cases:
        selected, called_tools, missing = plugins.select(
            route, message, request, has_report_attachment=has_attachment,
        )
        assert selected["id"] == expected_plugin, message
        assert not missing, message
        assert set(called_tools) <= registered, message
        assert set(called_tools) <= set(selected["runtime_tools"]), message


def test_plugin_success_badge_requires_the_selected_tool_chain_to_complete():
    from aicentralv2.cadu_workspace.agent_v2.service import _plugin_execution_succeeded

    plugin = {"id": "market-radar", "completion_tools": ["web.search"]}
    route = {"action": "run_plugin"}

    assert not _plugin_execution_succeeded(plugin, route, [
        {"name": "brands.get_context", "status": "completed"},
        {"name": "web.search", "status": "failed"},
    ])
    assert not _plugin_execution_succeeded(plugin, route, [
        {"name": "brands.get_context", "status": "completed"},
    ])
    assert _plugin_execution_succeeded(plugin, route, [
        {"name": "brands.get_context", "status": "completed"},
        {"name": "web.search", "status": "completed"},
    ])
    assert not _plugin_execution_succeeded(
        {"id": "market-radar", "completion_tools": []}, route, [],
    )
    assert _plugin_execution_succeeded(
        {"id": "creative-concept", "completion_tools": []}, route, [],
    )
    assert _plugin_execution_succeeded(
        {"id": "meeting-copilot", "completion_tools": []}, route, [],
    )
