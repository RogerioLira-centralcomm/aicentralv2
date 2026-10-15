from pathlib import Path
from unittest import TestCase

from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from aicentralv2 import crm_v3_routes as routes

ROOT = Path(__file__).resolve().parents[1]
BASE = "{% block content %}{% endblock %}{% block styles %}{% endblock %}"
JS = ROOT / "aicentralv2/static/js/crm_v3_agencias.js"


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


class CrmV3AgenciasPageTest(TestCase):
    def test_pagina_de_agencias_renderiza_para_usuario_logado(self):
        client = _app().test_client()
        with client.session_transaction() as s:
            s.update(user_id=1, user_type="admin", is_centralcomm=True)
        resp = client.get("/crm-v3/agencias")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="crm-ag-tree"', html)
        self.assertIn("js/crm_v3_agencias.js", html)

    def test_pagina_exige_login(self):
        resp = _app().test_client().get("/crm-v3/agencias")
        self.assertEqual(resp.status_code, 302)

    def test_js_usa_os_endpoints_de_vinculo_existentes(self):
        js = JS.read_text()
        self.assertIn("'/clientes'", js)
        self.assertIn("'/agencias/' + encodeURIComponent(agenciaId) + '/clientes/'", js)
        self.assertIn("method: ativo ? 'POST' : 'DELETE'", js)

    def test_js_escapa_nomes_antes_de_inserir_html(self):
        js = JS.read_text()
        self.assertIn("function esc(valor)", js)
        self.assertNotIn("innerHTML = c.nome", js)
