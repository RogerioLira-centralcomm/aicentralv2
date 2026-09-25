from aicentralv2.cadu_workspace.agent_v2 import memory_checkpoint


def test_memory_worker_reclaims_abandoned_claims(monkeypatch):
    statements = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, params=()): statements.append((sql, params))
        def fetchone(self): return None

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass

    monkeypatch.setattr(memory_checkpoint.repository, "get_db", lambda: Connection())

    assert memory_checkpoint.claim() is None
    assert "claimed_at < NOW()-INTERVAL '10 minutes'" in statements[0][0]
    assert "FOR UPDATE SKIP LOCKED" in statements[0][0]
