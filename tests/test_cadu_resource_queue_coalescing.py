from aicentralv2.cadu_workspace import project_resource_service


def test_project_resource_queue_coalesces_pending_events(monkeypatch):
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params=()):
            statements.append((sql, params))

        def fetchone(self):
            return {"id": "existing-job"}

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(project_resource_service, "get_db", lambda: Connection())
    monkeypatch.setattr(project_resource_service, "_relation", lambda *_: True)

    project_resource_service.notify_change(174, "ci:project", "updated", source_id="file-1")

    sql = [statement for statement, _ in statements]
    assert any("pg_advisory_xact_lock" in statement for statement in sql)
    assert any("status='queued'" in statement and "FOR UPDATE" in statement for statement in sql)
    assert any("UPDATE cadu_project_resource_jobs" in statement for statement in sql)
    assert not any("INSERT INTO cadu_project_resource_jobs" in statement for statement in sql)
