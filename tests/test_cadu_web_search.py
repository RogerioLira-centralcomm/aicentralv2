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
    monkeypatch.setattr(web_search, "_read_source", lambda url: {
        "content": "Conteúdo principal limpo e selecionado.",
        "content_excerpt": "Conteúdo principal limpo e selecionado.",
        "content_blocks": [{"kind": "paragraph", "text": "Conteúdo principal limpo e selecionado."}],
        "favicon": "https://example.com/favicon.ico",
        "cleaning": "test",
    })
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
    assert result["sources"][0]["favicon"].endswith("favicon.ico")


def test_web_search_rejects_conflicting_domain_filters():
    with pytest.raises(ValueError, match="incluir ou excluir"):
        web_search.search(context(), {
            "query": "tendências",
            "include_domains": ["example.com"],
            "exclude_domains": ["bad.example"],
        })


def test_research_depth_controls_site_count_and_page_reading(monkeypatch):
    searched_limits = []
    read_urls = []

    monkeypatch.setattr(web_search.CaduCreditConnector, "authorize_firecrawl", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_search.CaduCreditConnector, "charge_firecrawl", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_search, "_search", lambda query, **kwargs: (
        searched_limits.append(kwargs["limit"])
        or [{"id": f"web-{index}", "title": f"Fonte {index}", "url": f"https://example.com/{index}", "excerpt": "Resumo"}
            for index in range(1, kwargs["limit"] + 1)]
    ))
    monkeypatch.setattr(web_search, "_read_source", lambda url: (
        read_urls.append(url)
        or {"content": "Texto principal suficientemente longo para ser evidência.", "content_excerpt": "Texto principal"}
    ))

    web_search.search(context(), {"query": "tema", "depth": "fast"})
    web_search.search(context(), {"query": "tema", "depth": "agentic"})

    assert searched_limits == [4, 10]
    assert len(read_urls) == 6


def test_html_cleanup_keeps_main_blocks_and_drops_page_chrome(monkeypatch):
    monkeypatch.setattr("aicentralv2.crm_v3_web_scout._firecrawl_scrape", lambda *args, **kwargs: {
        "html": "<nav>Menu</nav><main><h1>Título principal</h1><p>Conteúdo útil da página para a decisão, com contexto suficiente para orientar uma recomendação personalizada.</p></main><footer>Publicidade e rodapé</footer>",
        "metadata": {"title": "Título principal"},
    })

    result = web_search._read_source("https://example.com/article")

    assert "Conteúdo útil" in result["content"]
    assert "Menu" not in result["content"]
    assert "Publicidade" not in result["content"]
    assert result["content_blocks"][0]["kind"] == "heading"


def test_direct_link_uses_the_same_clean_source_contract(monkeypatch):
    monkeypatch.setattr(web_search, "_read_source", lambda url: {
        "content": "Texto principal da página, sem menu ou publicidade.",
        "content_excerpt": "Texto principal da página, sem menu ou publicidade.",
        "content_blocks": [{"kind": "paragraph", "text": "Texto principal da página, sem menu ou publicidade."}],
        "page_title": "Página analisada",
        "favicon": "https://example.com/favicon.ico",
    })
    monkeypatch.setattr(web_search.CaduCreditConnector, "authorize_firecrawl", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_search.CaduCreditConnector, "charge_firecrawl", lambda *args, **kwargs: None)
    result = web_search.read(context(), {"url": "https://example.com/article"})
    assert result["result_type"] == "direct_read"
    assert result["sources"][0]["title"] == "Página analisada"
    assert result["sources"][0]["content_blocks"][0]["text"].startswith("Texto principal")


def test_router_distinguishes_web_research_from_project_search():
    web_route = route_request("Pesquise na internet fontes recentes sobre Nike", has_project=True)
    project_route = route_request("Pesquise no projeto os arquivos sobre Nike", has_project=True)
    project_sources_route = route_request("Pesquise as fontes do projeto sobre Nike", has_project=True)
    direct_route = route_request("Entenda este link: https://example.com/article", has_project=True)
    current_route = route_request("Quais são os concorrentes atuais da Nike?", has_project=True)
    simple_route = route_request("Resuma a identidade da Nike", has_project=True)

    assert web_route.action == "search_web"
    assert web_route.needs_tools == ("web.search",)
    assert project_route.action == "search_project"
    assert project_route.needs_tools == ("workspace.search_project_content",)
    assert project_sources_route.action == "search_project"
    assert direct_route.action == "read_web_page"
    assert direct_route.needs_tools == ("web.read",)
    assert current_route.action == "search_web"
    assert simple_route.needs_tools == ()


def test_web_tool_is_available_only_with_research_capability():
    registry = load_builtin_tools()
    assert any(item["name"] == "web.search" for item in registry.list(context(), "customer_agent"))
    assert not any(item["name"] == "web.search" for item in registry.list(
        context(capabilities=("workspace",)), "customer_agent"
    ))
