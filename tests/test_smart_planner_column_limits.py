"""Texto extraído de um PDF longo não pode derrubar o plano por estourar uma coluna varchar(100)."""

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
        if "information_schema" in sql and self.db.fail_schema:
            raise RuntimeError("sem permissão")

    def fetchall(self):
        return [{"column_name": "nome_campanha", "character_maximum_length": 100},
                {"column_name": "user_email", "character_maximum_length": 20}]

    def fetchone(self):
        return {"id": 1}


class _Db:
    def __init__(self, fail_schema=False):
        self.calls, self.fail_schema, self.rollbacks = [], fail_schema, 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        self.rollbacks += 1


def _setup(monkeypatch, db):
    repository._LIMITS["cols"] = None
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
    assert failing.rollbacks == 1  # a transação abortada não fica para o UPDATE seguinte
    assert repository._LIMITS["cols"] is None  # tenta de novo na próxima
