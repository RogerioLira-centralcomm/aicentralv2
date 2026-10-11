from pathlib import Path
from unittest import TestCase, mock

from flask import Blueprint, Flask

from aicentralv2.studio_interest import register_api_routes

ROOT = Path(__file__).resolve().parents[1]
HOST = {"Host": "studio.centralcomm.media"}


class StudioInterestTest(TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(ROOT / "aicentralv2" / "templates"))
        self.app.config.update(SECRET_KEY="test", TESTING=True, STUDIO_URL="https://studio.centralcomm.media")
        self.app.add_url_rule("/login", "login", lambda: "login")
        api = Blueprint("studio", __name__, url_prefix="/studio")
        register_api_routes(api)
        self.app.register_blueprint(api)
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction(headers=HOST) as session:
            session.update(user_id=7, cliente_id=174, user_name="Apolo", trocr_csrf_token="csrf")

    def post(self, product="audio", token="csrf"):
        return self.client.post(f"/studio/api/interesse/{product}", headers={**HOST, "X-Trocr-CSRF-Token": token})

    def test_requires_login(self):
        self.assertIn(self.client.get("/studio/api/interesse/audio", headers=HOST).status_code, (302, 401, 403))

    def test_register_stores_the_known_product_once(self):
        self.login()
        with mock.patch("aicentralv2.studio_interest.db") as db:
            db.criar_interesse_produto.return_value = 10
            first = self.post()
            db.criar_interesse_produto.return_value = None  # already on the list
            second = self.post()
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.get_json()["data"], {"registered": True, "launch": "2026-12"})
        args, kwargs = db.criar_interesse_produto.call_args
        self.assertEqual(args, (7, "cadu_studio_audio"))
        self.assertEqual(kwargs["dados_adicionais"]["lancamento"], "2026-12")

    def test_needs_the_csrf_token_and_a_known_product(self):
        self.login()
        with mock.patch("aicentralv2.studio_interest.db") as db:
            self.assertEqual(self.post(token="errado").status_code, 403)
            self.assertEqual(self.post(product="qualquer").status_code, 404)
            db.criar_interesse_produto.assert_not_called()

    def test_status_reports_registration(self):
        self.login()
        with mock.patch("aicentralv2.studio_interest.db") as db:
            db.obter_interesses_produto.return_value = [{"id_interesse": 1}]
            on = self.client.get("/studio/api/interesse/audio", headers=HOST)
            db.obter_interesses_produto.return_value = []
            off = self.client.get("/studio/api/interesse/audio", headers=HOST)
        self.assertTrue(on.get_json()["data"]["registered"])
        self.assertFalse(off.get_json()["data"]["registered"])

    def test_database_failure_is_a_clean_error_not_a_crash(self):
        self.login()
        with mock.patch("aicentralv2.studio_interest.db") as db:
            db.criar_interesse_produto.side_effect = RuntimeError("tabela ausente")
            db.obter_interesses_produto.side_effect = RuntimeError("tabela ausente")
            self.assertEqual(self.post().status_code, 503)
            status = self.client.get("/studio/api/interesse/audio", headers=HOST)
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["data"]["unknown"])
