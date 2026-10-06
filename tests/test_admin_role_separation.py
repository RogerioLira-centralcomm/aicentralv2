"""Admin de conta cliente != admin interno do CentralX.

``user_type='admin'`` também é o papel de administrador da conta do cliente no
Workspace (Agência, equipe). Rotas internas do CentralX exigem a equipe
CentralComm (``session['is_centralcomm']``). Roda sem banco: DB_HOST=127.0.0.1 DB_PORT=1.
"""
import os

os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")

import pytest
from flask import Flask, session

from aicentralv2 import auth
from tests.shared_app import get_app

CLIENT_ADMIN = {"user_id": 501, "cliente_id": 900, "user_type": "admin", "is_centralcomm": False,
                "user_name": "Ana", "user_email": "ana@cliente.test"}
CC_ADMIN = {"user_id": 7, "cliente_id": 1, "user_type": "admin", "is_centralcomm": True,
            "user_name": "Equipe", "user_email": "equipe@centralcomm.media"}
CC_SUPER = dict(CC_ADMIN, user_type="superadmin")


@pytest.fixture()
def app(monkeypatch):
    application = get_app()
    application.config["TESTING"] = True
    from aicentralv2 import db

    # login_required do CentralX revalida o cliente no banco: simula o cadastro.
    def contato(user_id):
        return {"id_contato_cliente": user_id, "pk_id_tbl_cliente": 1 if user_id == 7 else 900}

    def cliente(cliente_id):
        name = "CENTRALCOMM" if cliente_id == 1 else "Agência Cliente"
        return {"id_cliente": cliente_id, "nome_fantasia": name, "status": True}

    monkeypatch.setattr(db, "obter_contato_por_id", contato)
    monkeypatch.setattr(db, "obter_cliente_por_id", cliente)
    from aicentralv2.cadu_connect import reports_access
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    return application


def _client(app, data):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.update(data)
    return client


# Amostra das rotas internas: ERP/planos/créditos (login_required do CentralX),
# APIs com admin_required_api (integrações, monitor, Camadas, Studio interno)
# e o financeiro.
INTERNAL_PAGES = ["/cadu/creditos", "/cadu/creditos/1", "/clientes", "/contratos/novo",
                  "/parametros/integracoes", "/parametros/monitoramento", "/financeiro/gestao"]
INTERNAL_APIS = ["/parametros/api/integrations", "/parametros/api/server-monitor",
                 "/parametros/api/camadas/v2/jobs/x", "/studio/api/camadas/v2/jobs/x",
                 "/parametros/api/campaign-clients", "/financeiro/api/admin/summaries"]


@pytest.mark.parametrize("path", INTERNAL_PAGES)
def test_admin_de_conta_cliente_nao_entra_em_paginas_internas(app, path):
    response = _client(app, CLIENT_ADMIN).get(path)
    assert response.status_code in {302, 303, 403}, path
    location = response.headers.get("Location", "")
    assert path not in location or "login" in location


@pytest.mark.parametrize("path", INTERNAL_APIS)
def test_admin_de_conta_cliente_recebe_403_nas_apis_internas(app, path):
    response = _client(app, CLIENT_ADMIN).get(path)
    assert response.status_code == 403, (path, response.status_code)


@pytest.mark.parametrize("path", INTERNAL_APIS[:4])
@pytest.mark.parametrize("who", [CC_ADMIN, CC_SUPER])
def test_equipe_centralcomm_passa_pelo_guard_das_apis_internas(app, path, who):
    # Sem banco a view pode falhar depois do guard; o que importa é não ser barrada.
    response = _client(app, who).get(path)
    assert response.status_code not in {401, 403}, (path, response.status_code)


def _guarded_app():
    test_app = Flask(__name__)
    test_app.secret_key = "t"
    test_app.add_url_rule("/", "index", lambda: "home")
    test_app.add_url_rule("/login", "login", lambda: "login")

    @test_app.get("/interno")
    @auth.admin_required
    def interno():
        return "ok"

    @test_app.get("/api/interno")
    @auth.admin_required_api
    def interno_api():
        return "ok"

    @test_app.get("/conta")
    @auth.account_admin_required
    def conta():
        return "ok"

    @test_app.get("/api/conta")
    @auth.account_admin_required_api
    def conta_api():
        return "ok"

    @test_app.get("/super")
    @auth.superadmin_required_api
    def super_api():
        return "ok"
    return test_app


@pytest.mark.parametrize("who,interno,conta,superadmin", [
    (CLIENT_ADMIN, False, True, False),
    (dict(CLIENT_ADMIN, user_type="superadmin"), False, True, False),
    (dict(CLIENT_ADMIN, user_type="client"), False, False, False),
    (dict(CC_ADMIN, user_type="client"), False, False, False),
    (CC_ADMIN, True, True, False),
    (CC_SUPER, True, True, True),
])
def test_decoradores_separam_admin_de_conta_e_admin_interno(who, interno, conta, superadmin):
    client = _guarded_app().test_client()
    with client.session_transaction() as sess:
        sess.update(who)
    assert (client.get("/interno").status_code == 200) is interno
    assert (client.get("/api/interno").status_code == 200) is interno
    assert (client.get("/conta").status_code == 200) is conta
    assert (client.get("/api/conta").status_code == 200) is conta
    assert (client.get("/super").status_code == 200) is superadmin


def test_helpers_de_papel():
    app = Flask(__name__)
    app.secret_key = "t"
    with app.test_request_context():
        session.update(CLIENT_ADMIN)
        assert auth.is_account_admin() and not auth.is_admin() and not auth.is_internal_admin()
        assert not auth.is_finance_admin()
        session.update(is_finance_admin=True)
        assert not auth.is_finance_admin()
        session.update(CC_ADMIN)
        assert auth.is_admin() and auth.is_finance_admin()


@pytest.mark.parametrize("name", ["CENTRALCOMM", "CentralComm", " central comm ", "Central-Comm.", "céntralcomm"])
def test_nome_reservado_da_centralcomm(name):
    assert auth.is_reserved_org_name(name)


@pytest.mark.parametrize("name", ["", None, "Central", "CentralComm Media", "Agência Cliente"])
def test_nomes_comuns_nao_sao_reservados(name):
    assert not auth.is_reserved_org_name(name)


def test_cadastro_publico_recusa_nome_centralcomm(monkeypatch):
    from aicentralv2 import db
    from aicentralv2.services import onboarding_comercial
    monkeypatch.setattr(db, "obter_contato_por_email", lambda email: None)
    with pytest.raises(ValueError):
        onboarding_comercial.provisionar_conta_publica(nome="Central Comm", email="x@y.test", senha="12345678")


def test_workspace_admin_de_conta_gerencia_equipe_mas_nao_vira_centralcomm(app, monkeypatch):
    from werkzeug.exceptions import BadRequest, Forbidden
    from aicentralv2.cadu_workspace import routes
    with app.test_request_context("/workspace/app/organizacao", method="POST"):
        session.update(CLIENT_ADMIN)
        routes._workspace_team_admin()  # admin de conta continua gerenciando a equipe
        session.update(user_type="client")
        with pytest.raises(Forbidden):
            routes._workspace_team_admin()

    view = getattr(routes.update_organization, "__wrapped__", routes.update_organization)
    with app.test_request_context("/workspace/app/organizacao", method="POST",
                                  data={"trade_name": "Central Comm"}):
        session.update(CLIENT_ADMIN)
        monkeypatch.setattr(routes, "_workspace_api_csrf", lambda: True)
        with pytest.raises(BadRequest):
            view()


def test_checkout_de_plano_recusa_nome_centralcomm(monkeypatch):
    from aicentralv2 import cadu_plan_checkout as checkout
    from aicentralv2.cadu_family import repository
    monkeypatch.setattr(repository, "actor", lambda user_id: {"organization_id": 900, "user_type": "admin"})
    data = {field: "x" for field in checkout.BILLING_FIELDS}
    data["nome_fantasia"] = "CENTRALCOMM"
    with pytest.raises(checkout.CheckoutError):
        checkout.request_plan_change(user_id=501, client_id=900, data=data)
