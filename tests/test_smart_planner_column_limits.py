"""Texto extraído de um PDF longo não pode derrubar o plano por estourar uma coluna varchar(100)."""

from psycopg.errors import StringDataRightTruncation

from aicentralv2.smart_planner import repository


class _Cursor:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.db.calls.append((sql, params))
        if "pg_attribute" in sql and self.db.fail_schema:
            raise RuntimeError("sem permissão")
        if sql.startswith("UPDATE") and self.db.limit:
            if any(isinstance(p, str) and len(p) > self.db.limit for p in params or ()):
                raise StringDataRightTruncation(f"value too long for type character varying({self.db.limit})")

    def fetchall(self):
        if self.db.no_limits:
            return []
        return [{"column_name": "nome_campanha", "character_maximum_length": 100},
                {"column_name": "user_email", "character_maximum_length": 20}]

    def fetchone(self):
        return {"id": 1}


class _Savepoint:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *exc):
        if exc_type:
            self.db.savepoint_rollbacks += 1
        return False


class _Db:
    def __init__(self, fail_schema=False, no_limits=False, limit=None):
        self.calls, self.fail_schema, self.rollbacks, self.savepoint_rollbacks = [], fail_schema, 0, 0
        self.no_limits, self.limit = no_limits, limit

    def cursor(self):
        return _Cursor(self)

    def transaction(self):
        return _Savepoint(self)

    def commit(self):
        pass

    def rollback(self):
        self.rollbacks += 1


def _setup(monkeypatch, db):
    repository._LIMITS.update(cols=None, retry_at=0.0)
    monkeypatch.setattr(repository, "get_db", lambda: db)
    monkeypatch.setattr(repository, "get_by_token", lambda token: {"id": 7})


def test_long_campaign_name_is_cut_to_fit_the_column(monkeypatch):
    db = _Db()
    _setup(monkeypatch, db)
    long_name = "PropostaCentralcomm_-CZG-SALA_Simmons-BestFriday2026 " * 4
    repository.update_session("tok", {"nome_campanha": long_name, "objetivo": "vendas"})
    sql, params = db.calls[-1]
    assert sql.startswith("UPDATE")
    assert len(params[0]) == 100 and params[0].endswith("…")
    assert params[1] == "vendas"
    repository._LIMITS["cols"] = None


def test_email_is_never_cut_and_a_failed_schema_read_cuts_nothing(monkeypatch):
    db = _Db()
    _setup(monkeypatch, db)
    assert repository.fit_column("user_email", "pessoa.com.nome.longo@centralcomm.media") == "pessoa.com.nome.longo@centralcomm.media"
    failing = _Db(fail_schema=True)
    _setup(monkeypatch, failing)
    assert repository.fit_column("nome_campanha", "x" * 300) == "x" * 300
    # Só o savepoint volta: o que a requisição já escreveu não se perde.
    assert failing.savepoint_rollbacks == 1 and failing.rollbacks == 0
    assert "to_regclass" in failing.calls[-1][0]
    assert repository._LIMITS["cols"] is None  # tenta de novo na próxima


def test_empty_schema_read_is_not_cached(monkeypatch):
    # Tabela fora do esquema esperado devolvia zero linhas, e o vazio ficava em cache: nunca mais cortava.
    db = _Db(no_limits=True)
    _setup(monkeypatch, db)
    assert repository.fit_column("nome_campanha", "x" * 300) == "x" * 300
    assert repository._LIMITS["cols"] is None
    reads = sum("pg_attribute" in sql for sql, _ in db.calls)
    repository.fit_column("prazo", "y" * 300)
    assert sum("pg_attribute" in sql for sql, _ in db.calls) == reads  # sem repetir a consulta por coluna
    repository._LIMITS["retry_at"] = 0.0


def test_update_cuts_by_the_database_error_when_limits_are_unknown(monkeypatch):
    db = _Db(no_limits=True, limit=100)
    _setup(monkeypatch, db)
    repository.update_session("tok", {"prazo": "p" * 250, "objetivo": "vendas", "user_email": "a@b.c"})
    updates = [(sql, params) for sql, params in db.calls if sql.startswith("UPDATE")]
    cut = [params for sql, params in updates if "SET prazo" in sql][-1]
    assert len(cut[0]) == 100 and cut[0].endswith("…")
    assert any("SET objetivo" in sql and params[0] == "vendas" for sql, params in updates)
    assert db.calls[-1][0].startswith("SELECT * FROM cadu_smart_planner_sessions")
