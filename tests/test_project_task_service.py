from datetime import datetime, timezone

import pytest
from werkzeug.exceptions import BadRequest

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
