"""B1 (checkout de plano) e A1 (cadastro atômico) com banco simulado."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from aicentralv2 import cadu_plan_checkout as checkout
from aicentralv2.services import onboarding_comercial as onboarding


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.last = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        for needle, result in self.conn.script:
            if needle in sql:
                if isinstance(result, Exception):
                    raise result
                self.last = result(params) if callable(result) else result
                return
        self.last = None

    def fetchone(self):
        return self.last


class FakeConn:
    def __init__(self, script):
        self.script = script
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def ran(self, needle):
        return [p for s, p in self.executed if needle in s]


BILLING = {"cnpj": "00.000.000/0001-00", "razao_social": "ACME", "nome_fantasia": "Acme", "cep": "01000-000",
           "cidade": "SP", "estado": "SP", "endereco": "Rua A", "responsavel_nome": "Ana",
           "email_faturamento": "fin@acme.test", "telefone": "11999999999"}
ADMIN = {"organization_id": 7, "user_type": "admin", "name": "Ana", "email": "ana@acme.test"}
SELLABLE = '{"equipe": {"cta": "checkout"}}'


def run(conn, data, actor=ADMIN, definitions=(), env=SELLABLE, monkeypatch=None, sent=True):
    if env is not None:
        monkeypatch.setenv("CADU_PLAN_CATALOG_JSON", env)
    else:
        monkeypatch.delenv("CADU_PLAN_CATALOG_JSON", raising=False)
    with patch("aicentralv2.db.get_db", return_value=conn), \
         patch("aicentralv2.db.obter_plan_definitions", return_value=list(definitions)), \
         patch("aicentralv2.cadu_family.repository.actor", return_value=actor), \
         patch("aicentralv2.email_service.send_email", return_value=sent) as mail:
        result = checkout.request_plan_change(user_id=3, client_id=7, data=data)
    return result, mail


def base_script(existing=None):
    return [("FROM cadu_client_plans", None),
            ("pg_advisory_xact_lock", None),
            ("SELECT id_log FROM tbl_admin_audit_log", existing),
            ("UPDATE tbl_cliente", None),
            ("INSERT INTO tbl_admin_audit_log", {"id_log": 99})]


def test_preco_e_limites_do_cliente_sao_ignorados(monkeypatch):
    conn = FakeConn(base_script())
    data = {**BILLING, "plan_type": "equipe", "plan_price": 0, "max_users": 999, "tokens_monthly_limit": 10**9}
    result, mail = run(conn, data, monkeypatch=monkeypatch)
    assert result["request_id"] == 99 and result["duplicate"] is False
    novos = json.loads(conn.ran("INSERT INTO tbl_admin_audit_log")[0][-1])
    assert novos["price_monthly"] == 697.0 and novos["status"] == "pending_finance"
    assert "max_users" not in novos
    assert not conn.ran("cadu_client_plans (") and not conn.ran("invoice")
    assert conn.commits == 1
    assert set(mail.call_args.args[1]) >= {"financeiro@centralcomm.media"}


def test_nao_admin_recusado(monkeypatch):
    conn = FakeConn(base_script())
    with pytest.raises(checkout.CheckoutError) as err:
        run(conn, {**BILLING, "plan_type": "equipe"}, actor={**ADMIN, "user_type": "client"}, monkeypatch=monkeypatch)
    assert err.value.status == 403 and conn.executed == []


def test_admin_de_outra_organizacao_recusado(monkeypatch):
    conn = FakeConn(base_script())
    with pytest.raises(checkout.CheckoutError):
        run(conn, {**BILLING, "plan_type": "equipe"}, actor={**ADMIN, "organization_id": 8}, monkeypatch=monkeypatch)


def test_plano_inexistente_recusado(monkeypatch):
    conn = FakeConn(base_script())
    with pytest.raises(checkout.CheckoutError, match="desconhecido"):
        run(conn, {**BILLING, "plan_type": "enterprise", "plan_id": 42}, monkeypatch=monkeypatch)
    assert not conn.ran("INSERT") and conn.rollbacks == 1


def test_plano_de_contato_recusado_sem_alterar_nada(monkeypatch):
    conn = FakeConn(base_script())
    with pytest.raises(checkout.CheckoutError, match="Falar com a equipe"):
        run(conn, {**BILLING, "plan_type": "equipe"}, env=None, monkeypatch=monkeypatch)
    assert not conn.ran("UPDATE tbl_cliente") and not conn.ran("INSERT")


def test_plano_sem_preco_recusado(monkeypatch):
    conn = FakeConn(base_script())
    with pytest.raises(checkout.CheckoutError, match="preço"):
        run(conn, {**BILLING, "plan_type": "equipe"}, env='{"equipe": {"cta": "checkout", "price_monthly": null}}',
            monkeypatch=monkeypatch)


def test_resolve_pelo_id_da_definicao(monkeypatch):
    conn = FakeConn(base_script())
    result, _ = run(conn, {**BILLING, "plan_id": 5}, definitions=[{"id": 5, "plan_type": "equipe"}],
                    monkeypatch=monkeypatch)
    assert result["plan"]["slug"] == "equipe"


def test_rollback_quando_auditoria_falha(monkeypatch):
    script = base_script()
    script[-1] = ("INSERT INTO tbl_admin_audit_log", RuntimeError("db down"))
    conn = FakeConn(script)
    with pytest.raises(RuntimeError):
        run(conn, {**BILLING, "plan_type": "equipe"}, monkeypatch=monkeypatch)
    assert conn.commits == 0 and conn.rollbacks == 1


def test_pedido_repetido_nao_duplica(monkeypatch):
    conn = FakeConn(base_script(existing={"id_log": 55}))
    result, mail = run(conn, {**BILLING, "plan_type": "equipe"}, monkeypatch=monkeypatch)
    assert result == {**result, "request_id": 55, "duplicate": True}
    assert not conn.ran("INSERT") and not conn.ran("UPDATE tbl_cliente") and conn.commits == 0
    mail.assert_not_called()


def test_falha_de_email_nao_desfaz_solicitacao(monkeypatch):
    conn = FakeConn(base_script())
    result, _ = run(conn, {**BILLING, "plan_type": "equipe"}, monkeypatch=monkeypatch, sent=False)
    assert result["notification_sent"] is False and conn.commits == 1


# ------------------------------------------------------------------ A1

def provision(conn):
    with patch("aicentralv2.db.get_db", return_value=conn), \
         patch("aicentralv2.db.obter_contato_por_email", return_value=None), \
         patch("aicentralv2.db.obter_executivo_demetrius", return_value={"id_contato_cliente": 1}), \
         patch("aicentralv2.db.obter_tipos_cliente", return_value=[{"id_tipo_cliente": 2, "display": "Prospecção"}]), \
         patch("aicentralv2.db.obter_contato_por_id", return_value=None):
        return onboarding.provisionar_conta_publica(nome="Ana", email="ANA@x.test", senha="segredo123")


def signup_script(**over):
    script = {
        "pg_advisory_xact_lock": None,
        "SELECT 1 FROM tbl_contato_cliente": None,
        "INSERT INTO tbl_cliente": {"id_cliente": 10},
        "INSERT INTO tbl_contato_cliente": {"id_contato_cliente": 20},
        "to_regclass('cadu_credit_entitlements')": {"ok": True},
        "VALUES (%s, 'cadu_launch_100k'": None,
        "VALUES (%s, 'cadu_welcome'": {"id": 30},
        "information_schema.columns": {"ok": True},
        "INSERT INTO cadu_credits_extras": {"id": 40},
        "FROM cadu_plan_definitions": {"id": 1},
        "FROM cadu_client_plans": None,
        "INSERT INTO cadu_client_plans": None,
    }
    script.update(over)
    return FakeConn(list(script.items()))


def test_cadastro_atomico_cria_cliente_contato_plano_free_e_boas_vindas(monkeypatch):
    monkeypatch.delenv("CADU_WELCOME_TOKENS", raising=False)
    conn = signup_script()
    user, _ = provision(conn)
    assert user["id_contato_cliente"] == 20 and user["pk_id_tbl_cliente"] == 10
    # o primeiro contato administra a conta (edita Agência e convida pessoas)
    assert user["user_type"] == "admin"
    assert "'admin'" in [s for s, _ in conn.executed if "INSERT INTO tbl_contato_cliente" in s][0]
    assert conn.commits == 1 and conn.rollbacks == 0
    assert conn.ran("pg_advisory_xact_lock")[0] == ("cadu-signup:ana@x.test",)
    assert conn.ran("INSERT INTO cadu_credits_extras")[0] == (10, 50000)
    assert "'welcome'" in [s for s, _ in conn.executed if "INSERT INTO cadu_credits_extras" in s][0]
    assert conn.ran("INSERT INTO cadu_client_plans")[0] == (10, 1, 100000)
    # o direito de lançamento (100k do trigger) é neutralizado ANTES do plano ativo
    order = [s for s, _ in conn.executed]
    launch = next(i for i, s in enumerate(order) if "'cadu_launch_100k'" in s)
    plan = next(i for i, s in enumerate(order) if "INSERT INTO cadu_client_plans" in s)
    assert launch < plan


def test_boas_vindas_configuravel(monkeypatch):
    monkeypatch.setenv("CADU_WELCOME_TOKENS", "70000")
    conn = signup_script()
    provision(conn)
    assert conn.ran("INSERT INTO cadu_credits_extras")[0] == (10, 70000)


def test_boas_vindas_repetidas_nao_duplicam(monkeypatch):
    conn = signup_script(**{"VALUES (%s, 'cadu_welcome'": None, "FROM cadu_client_plans": {"?column?": 1}})
    provision(conn)
    assert not conn.ran("INSERT INTO cadu_credits_extras") and not conn.ran("INSERT INTO cadu_client_plans")
    assert conn.commits == 1


def test_sem_definicao_free_cadastra_sem_plano():
    conn = signup_script(**{"FROM cadu_plan_definitions": None})
    provision(conn)
    assert not conn.ran("INSERT INTO cadu_client_plans") and conn.commits == 1


def test_falha_no_lote_desfaz_cadastro_inteiro():
    conn = signup_script(**{"INSERT INTO cadu_credits_extras": RuntimeError("boom")})
    with pytest.raises(RuntimeError):
        provision(conn)
    assert conn.commits == 0 and conn.rollbacks == 1


def test_cadastro_desfaz_cliente_se_contato_falha():
    conn = signup_script(**{"INSERT INTO tbl_contato_cliente": RuntimeError("unique violation")})
    with pytest.raises(RuntimeError):
        provision(conn)
    assert conn.commits == 0 and conn.rollbacks == 1


def test_cadastro_corrida_email_detectada_dentro_do_lock():
    conn = signup_script(**{"SELECT 1 FROM tbl_contato_cliente": {"?column?": 1}})
    with pytest.raises(ValueError, match="já possui uma conta"):
        provision(conn)
    assert not conn.ran("INSERT") and conn.commits == 0 and conn.rollbacks == 1


def test_pagina_de_checkout_so_oferece_planos_solicitaveis(monkeypatch):
    monkeypatch.setenv("CADU_PLAN_CATALOG_JSON", SELLABLE)
    plans = {p["slug"]: p["requestable"] for p in checkout.checkout_plans([{"id": 9, "plan_type": "pro"}])}
    assert plans == {"essencial": False, "equipe": True, "agencia": False}
