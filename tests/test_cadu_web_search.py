import pytest

from aicentralv2.cadu_workspace import web_search
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools


def context(**overrides):
    values = {
        "organization_id": 12,
        "client_id": 12,
        "user_id": 7,
        "conversation_id": "conversation",
        "request_id": "request-1",
        "surface": "conversations",
        "capabilities": ("research",),
    }
    values.update(overrides)
    return RequestContext(**values)


def test_web_search_uses_firecrawl_v2_and_reads_selected_sources(monkeypatch):
    payloads = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"web": [{
                "title": "Fonte oficial",
                "description": "Resumo atual da fonte.",
                "url": "https://example.com/report",
                "date": "2026-09-20",
            }]}}

    monkeypatch.setattr(web_search, "resolve_firecrawl_api_key", lambda: "secret")
    monkeypatch.setattr(web_search.requests, "post", lambda endpoint, **kwargs: (
        payloads.append((endpoint, kwargs["json"])) or Response()
    ))
    monkeypatch.setattr(web_search, "_read_source", lambda url: "Conteúdo principal limpo e selecionado.")
    monkeypatch.setattr(web_search.CaduCreditConnector, "authorize_firecrawl", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_search.CaduCreditConnector, "charge_firecrawl", lambda *args, **kwargs: None)

    result = web_search.search(context(), {
        "query": "mercado de tênis esportivos",
        "limit": 6,
        "recency": "week",
        "include_content": True,
    })

    assert payloads[0][0].endswith("/v2/search")
    assert payloads[0][1]["query"] == "mercado de tênis esportivos"
    assert payloads[0][1]["country"] == "BR"
    assert payloads[0][1]["tbs"] == "qdr:w"
    assert result["source_count"] == 1
    assert result["sources_read"] == 1
    assert result["sources"][0]["content"].startswith("Conteúdo principal")


def test_web_search_rejects_conflicting_domain_filters():
    with pytest.raises(ValueError, match="incluir ou excluir"):
        web_search.search(context(), {
            "query": "tendências",
            "include_domains": ["example.com"],
            "exclude_domains": ["bad.example"],
        })


def test_router_distinguishes_web_research_from_project_search():
    web_route = route_request("Pesquise na internet fontes recentes sobre Nike", has_project=True)
    project_route = route_request("Pesquise no projeto os arquivos sobre Nike", has_project=True)
    project_sources_route = route_request("Pesquise as fontes do projeto sobre Nike", has_project=True)
    current_route = route_request("Quais são os concorrentes atuais da Nike?", has_project=True)
    simple_route = route_request("Resuma a identidade da Nike", has_project=True)

    assert web_route.action == "search_web"
    assert web_route.needs_tools == ("web.search",)
    assert project_route.action == "search_project"
    assert project_route.needs_tools == ("workspace.search_project_content",)
    assert project_sources_route.action == "search_project"
    assert current_route.action == "search_web"
    assert simple_route.needs_tools == ()


def test_web_tool_is_available_only_with_research_capability():
    registry = load_builtin_tools()
    assert any(item["name"] == "web.search" for item in registry.list(context(), "customer_agent"))
    assert not any(item["name"] == "web.search" for item in registry.list(
        context(capabilities=("workspace",)), "customer_agent"
    ))
