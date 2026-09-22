import json
from unittest.mock import patch

import pytest

from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS, _public_catalog
from aicentralv2.cadu_public_mcp.auth import PublicMcpPrincipal
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import ToolError, ToolInputError
from aicentralv2.cadu_workspace.mcp.tools.projects import get_source_chunks, search_knowledge


CONTEXT = RequestContext(organization_id=12, client_id=12, user_id=7,
                         conversation_id=None, surface="workspace", project_ref="ci:project-1",
                         capabilities=("workspace",))


class Cursor:
    def __init__(self):
        self.calls = []
        self.one = iter([{"id": 9, "name": "Briefing", "indexing_status": "completed"}, {"total": 2}])

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params): self.calls.append((sql, params))
    def fetchone(self): return next(self.one)
    def fetchall(self): return [{"chunk_id": 31, "position": 0, "content": "Trecho A"}]


def test_public_catalog_advertises_project_rag_tools_and_project_selector():
    principal = PublicMcpPrincipal("key", 12, 7, "codex", "Teste", ("projects:read",), CONTEXT)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.can_purchase_credits", return_value=False):
        tools = {item["name"]: item for item in _public_catalog(principal)}
    for name in ("projects.search_knowledge", "projects.get_source_chunks"):
        assert name in tools and name in PUBLIC_TOOLS
        assert "project_ref" in tools[name]["inputSchema"]["properties"]


def test_search_knowledge_returns_citable_evidence():
    packet = {"projeto": {"nome": "Projeto"}, "fontes_verificadas": [
        {"source_id": 9, "chunk_id": 31, "trecho": "Trecho A"}]}
    with patch("aicentralv2.cadu_workspace.mcp.tools.projects.project_knowledge_context",
               return_value=json.dumps(packet)) as search:
        result = search_knowledge(CONTEXT, {"query": "  plano   de mídia "})
    assert search.call_args.args[0:3] == ("ci:project-1", None, 12)
    assert search.call_args.kwargs["result_limit"] == 8
    assert search.call_args.kwargs["strict_retrieval"] is True
    assert result["results"][0]["chunk_id"] == 31


def test_search_knowledge_reports_retrieval_failure():
    with patch("aicentralv2.cadu_workspace.mcp.tools.projects.project_knowledge_context",
               side_effect=RuntimeError("database unavailable")):
        with pytest.raises(ToolError, match="indisponível"):
            search_knowledge(CONTEXT, {"query": "plano de mídia"})


def test_source_chunks_are_tenant_and_project_scoped_and_paginated():
    cursor = Cursor()
    class DB:
        def cursor(self): return cursor
    with patch("aicentralv2.cadu_workspace.mcp.tools.projects.get_db", return_value=DB()):
        result = get_source_chunks(CONTEXT, {"source_id": 9, "limit": 1})
    assert cursor.calls[0][1] == (9, "project-1", 12)
    assert cursor.calls[1][1] == (9, "project-1", 12)
    assert cursor.calls[2][1] == (9, "project-1", 12, 1, 0)
    assert result["next_offset"] == 1
    assert result["chunks"][0]["content"] == "Trecho A"


def test_source_chunks_does_not_read_another_projects_source():
    cursor = Cursor()
    cursor.one = iter([None])
    class DB:
        def cursor(self): return cursor
    with patch("aicentralv2.cadu_workspace.mcp.tools.projects.get_db", return_value=DB()):
        with pytest.raises(ToolInputError):
            get_source_chunks(CONTEXT, {"source_id": 9})
    assert len(cursor.calls) == 1
