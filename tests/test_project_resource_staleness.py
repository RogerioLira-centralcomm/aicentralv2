import pytest

from aicentralv2.cadu_workspace import project_resource_service as service


class _Cursor:
    def __init__(self, fresh, pending, statements):
        self.fresh, self.pending, self.statements, self._last = fresh, pending, statements, ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.statements.append(sql)
        self._last = sql

    def fetchone(self):
        if "MAX(last_seen_at)" in self._last:
            return {"fresh": self.fresh}
        if "EXISTS" in self._last:
            return {"pending": self.pending}
        return {"available": True}


def _wire(monkeypatch, *, fresh, pending):
    statements, calls = [], []

    class Connection:
        def cursor(self):
            return _Cursor(fresh, pending, statements)

    monkeypatch.setattr(service, "get_db", lambda: Connection())
    monkeypatch.setattr(service, "_relation", lambda *_: True)

    def fake_list(client_id, project_ref, *, reconcile_first=True, **_):
        calls.append(reconcile_first)
        return {"resources": [{"id": "r1"}], "summary": {}}

    monkeypatch.setattr(service, "list_resources", fake_list)
    return statements, calls


def test_fresh_registry_is_read_without_reconciling(monkeypatch):
    _statements, calls = _wire(monkeypatch, fresh=True, pending=False)
    result = service.reconcile_if_stale(12, "ci:p")
    assert calls == [False]
    assert result["available"] is True and result["resources"] == [{"id": "r1"}]


@pytest.mark.parametrize("fresh,pending", [(False, False), (True, True), (None, False)])
def test_stale_empty_or_pending_registry_reconciles(monkeypatch, fresh, pending):
    _statements, calls = _wire(monkeypatch, fresh=fresh, pending=pending)
    service.reconcile_if_stale(12, "ci:p")
    assert calls == [True]


def test_reconcile_completes_the_events_queued_before_it_started(monkeypatch):
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params=()):
            statements.append(sql)

        def fetchone(self):
            return {"id": "p", "available": True, "started_at": "t0"}

        def fetchall(self):
            return []

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(service, "get_db", lambda: Connection())
    monkeypatch.setattr(service, "_relation", lambda *_: True)
    monkeypatch.setattr(service, "_collect", lambda *_: [])
    monkeypatch.setattr(service, "_columns", lambda *_: set())
    monkeypatch.setattr(service, "_rebuild_relations", lambda *_: None)
    monkeypatch.setattr(service, "list_resources", lambda *a, **k: {"resources": []})

    service.reconcile(12, "ci:00000000-0000-0000-0000-000000000001")

    completed = [sql for sql in statements if "UPDATE cadu_project_resource_jobs" in sql]
    assert len(completed) == 1
    assert "status='queued'" in completed[0] and "created_at <=" in completed[0]
