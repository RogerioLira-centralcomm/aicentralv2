from datetime import datetime, timezone

import pytest
from werkzeug.exceptions import BadRequest, Conflict

from aicentralv2.cadu_workspace import project_task_service
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext


def _context():
    return RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id=None,
        surface="workspace", project_ref="ci:42",
    )


class _Connection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        connection = self

        class Cursor:
            rowcount = 1

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params=None):
                connection.executions.append((query, params))

            def fetchone(self):
                return next(connection.rows)

            def fetchall(self):
                return next(connection.rows)

        return Cursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_create_completed_task_records_completion_and_tenant_scope(monkeypatch):
    connection = _Connection([{"available": True}])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)
    monkeypatch.setattr(project_task_service, "list_tasks", lambda _context: {
        "available": True, "tasks": [{"id": connection.executions[-1][1][0], "status": "done"}],
    })

    task = project_task_service.create_task(_context(), {"title": "Publicar campanha", "status": "done"})

    insert, params = connection.executions[-1]
    assert "CASE WHEN %s='done' THEN NOW()" in insert
    assert params[-1] == "done"
    assert task["status"] == "done"
    assert connection.committed is True


def test_partial_date_update_cannot_invalidate_existing_task(monkeypatch):
    connection = _Connection([
        {"available": True},
        {
            "starts_at": datetime(2026, 9, 23, 14, tzinfo=timezone.utc),
            "due_at": datetime(2026, 9, 24, 14, tzinfo=timezone.utc),
        },
    ])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    with pytest.raises(BadRequest, match="prazo não pode ser anterior"):
        project_task_service.update_task(
            _context(), "f2f8d99a-14f8-4f35-9f83-e5e61bfc11c9",
            {"due_at": "2026-09-22T14:00:00Z"},
        )

    assert connection.rolled_back is True
    assert not any("UPDATE cadu_project_tasks" in query for query, _ in connection.executions)


def test_list_tasks_uses_organization_and_client_boundaries(monkeypatch):
    connection = _Connection([{"available": True}])
    cursor = connection.cursor()
    cursor.fetchall = lambda: []
    monkeypatch.setattr(connection, "cursor", lambda: cursor)
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    assert project_task_service.list_tasks(_context()) == {"available": True, "tasks": []}
    query, params = connection.executions[-1]
    assert "task.organization_id=%s AND task.client_id=%s" in query
    assert params == (12, 12, "ci:42")


def test_create_tasks_inserts_batch_in_one_transaction(monkeypatch):
    connection = _Connection([{"available": True}])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    def listed(_context):
        ids = [params[0] for query, params in connection.executions
               if "INSERT INTO cadu_project_tasks" in query]
        return {"available": True, "tasks": [{"id": item, "status": "todo"} for item in ids]}

    monkeypatch.setattr(project_task_service, "list_tasks", listed)
    result = project_task_service.create_tasks(_context(), [
        {"title": "Preparar briefing"},
        {"title": "Revisar campanha", "priority": "high"},
    ])

    inserts = [query for query, _ in connection.executions if "INSERT INTO cadu_project_tasks" in query]
    assert len(inserts) == 2
    assert result["created"] == 2
    assert result["initial_list"] is False
    assert connection.committed is True
    assert connection.rolled_back is False


def test_initial_task_list_is_created_only_for_empty_project(monkeypatch):
    connection = _Connection([{"available": True}, None])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    def listed(_context):
        task_id = next(params[0] for query, params in connection.executions
                       if "INSERT INTO cadu_project_tasks" in query)
        return {"available": True, "tasks": [{"id": task_id, "status": "todo"}]}

    monkeypatch.setattr(project_task_service, "list_tasks", listed)
    result = project_task_service.create_tasks(
        _context(), [{"title": "Primeiro próximo passo"}], require_empty=True,
    )

    assert any("pg_advisory_xact_lock" in query for query, _ in connection.executions)
    assert result == {"created": 1, "tasks": result["tasks"], "initial_list": True}
    assert connection.committed is True


def test_initial_task_list_rejects_project_that_already_has_tasks(monkeypatch):
    connection = _Connection([{"available": True}, {"exists": 1}])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    with pytest.raises(Conflict, match="já possui uma lista"):
        project_task_service.create_tasks(
            _context(), [{"title": "Não deve duplicar"}], require_empty=True,
        )

    assert connection.rolled_back is True
    assert not any("INSERT INTO cadu_project_tasks" in query for query, _ in connection.executions)


def test_task_update_contract_accepts_clearing_dates_and_assignee(monkeypatch):
    connection = _Connection([
        {"available": True},
        {"starts_at": datetime(2026, 9, 23, tzinfo=timezone.utc),
         "due_at": datetime(2026, 9, 24, tzinfo=timezone.utc)},
    ])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)
    monkeypatch.setattr(project_task_service, "list_tasks", lambda _context: {
        "available": True,
        "tasks": [{"id": "f2f8d99a-14f8-4f35-9f83-e5e61bfc11c9", "assignee_id": None}],
    })

    task = project_task_service.update_task(
        _context(), "f2f8d99a-14f8-4f35-9f83-e5e61bfc11c9",
        {"starts_at": None, "due_at": None, "assignee_id": None},
    )

    update, params = next((query, params) for query, params in connection.executions
                          if "UPDATE cadu_project_tasks" in query)
    assert "starts_at=%s" in update and "due_at=%s" in update and "assignee_id=%s" in update
    assert params[:3] == (None, None, None)
    assert task["assignee_id"] is None
    assert connection.committed is True


def test_batch_validates_and_persists_project_resource_provenance(monkeypatch):
    resource_id = "f2f8d99a-14f8-4f35-9f83-e5e61bfc11c9"
    connection = _Connection([{"available": True}, [{"id": resource_id}]])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)

    result = project_task_service.create_tasks(
        _context(), [{"title": "Revisar achados", "resource_refs": [resource_id],
                      "evidence": "O relatório aponta uma decisão pendente."}],
        user_instruction="Priorize o que depende de validação humana.",
        context_summary="Relatório e briefing foram organizados antes da proposta.",
    )

    assert result["tasks"][0]["metadata"]["resource_refs"] == [resource_id]
    assert result["tasks"][0]["metadata"]["user_instruction"].startswith("Priorize")
    insert_params = next(params for query, params in connection.executions
                         if "INSERT INTO cadu_project_tasks" in query)
    assert insert_params[-2].obj["evidence"].startswith("O relatório")


def test_update_task_can_replace_resource_provenance(monkeypatch):
    resource_id = "f2f8d99a-14f8-4f35-9f83-e5e61bfc11c9"
    connection = _Connection([
        {"available": True},
        {"starts_at": None, "due_at": None, "metadata": {"origin": "mcp"}},
        [{"id": resource_id}],
    ])
    monkeypatch.setattr(project_task_service, "get_db", lambda: connection)
    monkeypatch.setattr(project_task_service, "list_tasks", lambda _context: {
        "available": True, "tasks": [{"id": resource_id, "metadata": {"resource_refs": [resource_id]}}],
    })

    result = project_task_service.update_task(
        _context(), resource_id,
        {"resource_refs": [resource_id], "evidence": "O PDF sustenta esta revisão.",
         "user_instruction": "Manter a validação humana."},
    )

    update_params = next(params for query, params in connection.executions
                         if "UPDATE cadu_project_tasks" in query)
    assert update_params[0].obj["resource_refs"] == [resource_id]
    assert update_params[0].obj["evidence"].startswith("O PDF")
    assert result["metadata"]["resource_refs"] == [resource_id]
