import json
import re
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from aicentralv2 import leads_v3_routes as routes

ROOT = Path(__file__).resolve().parents[1]
BASE = "{% block styles %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"


def _app():
    app = Flask(__name__)
    app.secret_key = "t"
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base_erp.html": BASE}),
        FileSystemLoader(str(ROOT / "aicentralv2" / "templates")),
    ])
    app.register_blueprint(routes.bp)
    app.add_url_rule("/", "index", lambda: "home")
    return app


def _client(centralcomm=True):
    client = _app().test_client()
    with client.session_transaction() as s:
        s.update(user_id=7, user_name="Exec", user_type="admin", is_centralcomm=centralcomm)
    return client


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return [{"id": i} for i in self.conn.updated]


class FakeConn:
    def __init__(self, updated):
        self.updated = updated
        self.calls = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class LeadsV3PageTest(TestCase):
    def test_pagina_monta_o_react_com_o_bootstrap(self):
        with patch.object(routes.db, "obter_vendedores_centralcomm", return_value=[{"id_contato_cliente": 7, "nome_completo": "Exec"}]):
            resp = _client().get("/leads-v3")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="leads-v3-root"', html)
        self.assertIn("leads_v3/app.js", html)
        boot = json.loads(re.search(r'id="leads-v3-bootstrap">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(boot["filtroExecutivoInicial"], "7")
        self.assertEqual([s["value"] for s in boot["status"]], ["inbox", "tentativa_contato", "reuniao_agendada", "nutricao"])

    def test_quem_nao_e_executivo_comeca_no_inbox(self):
        with patch.object(routes.db, "obter_vendedores_centralcomm", return_value=[]):
            html = _client().get("/leads-v3").get_data(as_text=True)
        self.assertIn('"filtroExecutivoInicial": "sem"', html)

    def test_pagina_exige_login_e_equipe_centralcomm(self):
        self.assertEqual(_app().test_client().get("/leads-v3").status_code, 302)
        self.assertEqual(_client(centralcomm=False).post("/leads-v3/api/leads/lote", json={}).status_code, 403)


class LeadsV3ListTest(TestCase):
    def test_filtros_viram_parametros_do_dashboard(self):
        with patch.object(routes.db, "obter_leads_dashboard", return_value=[{"id": 1, "valor_estimado": None}]) as fn:
            resp = _client().get("/leads-v3/api/leads?executivo=sem&status=inbox&q=vale")
        self.assertEqual(resp.get_json()["data"]["total"], 1)
        kwargs = fn.call_args.kwargs
        self.assertTrue(kwargs["sem_responsavel"])
        self.assertEqual((kwargs["status"], kwargs["search"]), ("inbox", "vale"))

    def test_executivo_numerico_filtra_pelo_id(self):
        with patch.object(routes.db, "obter_leads_dashboard", return_value=[]) as fn:
            _client().get("/leads-v3/api/leads?executivo=12")
        self.assertEqual(fn.call_args.kwargs["id_executivo"], 12)
        self.assertNotIn("sem_responsavel", fn.call_args.kwargs)


class LeadsV3BulkTest(TestCase):
    def _post(self, body, updated=(1, 2)):
        conn = FakeConn(list(updated))
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().post("/leads-v3/api/leads/lote", json=body)
        return resp, conn

    def test_mudar_etapa_atualiza_e_registra_atividade(self):
        resp, conn = self._post({"acao": "status", "valor": "nutricao", "ids": [2, 1, 2, "x"]}, updated=[1])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["data"], {"alterados": [1], "ignorados": 1})
        update_sql, update_params = conn.calls[0]
        self.assertIn("SET status = %s", update_sql)
        self.assertIn("l.status IS DISTINCT FROM %s", update_sql)
        self.assertEqual(update_params, ["nutricao", [1, 2], "nutricao"])
        insert_sql, insert_params = conn.calls[1]
        self.assertIn("INSERT INTO cadu_lead_atividades", insert_sql)
        self.assertEqual(insert_params[0], [1])
        self.assertIn("Nutrição", insert_params[1])
        self.assertTrue(conn.committed)

    def test_desqualificar_exige_motivo(self):
        resp, conn = self._post({"acao": "desqualificar", "ids": [1]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(conn.calls, [])

    def test_desqualificar_grava_motivo(self):
        resp, conn = self._post({"acao": "desqualificar", "ids": [1, 2], "motivo": "Spam / teste"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status = 'nao_qualificado', motivo_desqualificacao = %s", conn.calls[0][0])
        self.assertEqual(conn.calls[0][1][0], "Spam / teste")

    def test_responsavel_sem_tira_o_executivo_sem_atividade(self):
        resp, conn = self._post({"acao": "responsavel", "valor": "sem", "ids": [1]})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("id_executivo = NULL", conn.calls[0][0])
        self.assertEqual(len(conn.calls), 1)

    def test_rejeita_etapa_fora_da_lista_e_lote_vazio_ou_grande(self):
        self.assertEqual(self._post({"acao": "status", "valor": "fechado_ganho", "ids": [1]})[0].status_code, 400)
        self.assertEqual(self._post({"acao": "status", "valor": "inbox", "ids": []})[0].status_code, 400)
        big = list(range(1, routes.MAX_LOTE + 2))
        self.assertEqual(self._post({"acao": "status", "valor": "inbox", "ids": big})[0].status_code, 400)
        self.assertEqual(self._post({"acao": "apagar", "ids": [1]})[0].status_code, 400)

    def test_erro_no_banco_desfaz_tudo(self):
        conn = FakeConn([1])
        conn.cursor = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().post("/leads-v3/api/leads/lote", json={"acao": "potencial", "valor": "alto", "ids": [1]})
        self.assertEqual(resp.status_code, 500)
        self.assertTrue(conn.rolled_back)


class LeadsV3OrigemTest(TestCase):
    def test_filtro_de_origem_separa_site_dos_adicionados(self):
        rows = [{"id": 1, "fonte": "site"}, {"id": 2, "fonte": "import"}, {"id": 3, "fonte": "manual"}]
        with patch.object(routes.db, "obter_leads_dashboard", return_value=rows), \
                patch.object(routes, "_golden_por_lead", return_value={}):
            site = _client().get("/leads-v3/api/leads?origem=site").get_json()["data"]["leads"]
            adicionados = _client().get("/leads-v3/api/leads?origem=adicionados").get_json()["data"]["leads"]
        self.assertEqual([l["id"] for l in site], [1])
        self.assertEqual([l["id"] for l in adicionados], [2, 3])
