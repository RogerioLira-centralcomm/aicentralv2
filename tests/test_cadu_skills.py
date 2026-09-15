from pathlib import Path
from unittest import TestCase

from flask import Flask

from aicentralv2.cadu_skills.catalog import CADU_MEDIA_PLANNING, DIRECTORY_SKILLS, get_public_skill
from aicentralv2.cadu_skills.consultations import consultation_state
from aicentralv2.cadu_skills.credits import balance_from_ledger
from aicentralv2.cadu_skills.routes import bp


ROOT = Path(__file__).resolve().parents[1]


def _app():
    app = Flask(__name__, template_folder=str(ROOT / "aicentralv2" / "templates"), static_folder=str(ROOT / "aicentralv2" / "static"))
    app.secret_key = "test"
    app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    app.register_blueprint(bp)
    return app


class CaduSkillsTest(TestCase):
    def test_public_marketplace_and_detail_do_not_require_login(self):
        client = _app().test_client()
        response = client.get("/skills/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Diretório público de skills", response.get_data(as_text=True))
        detail = client.get("/skills/cadu-media-planning")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("34 canais ativos", detail.get_data(as_text=True))
        self.assertEqual(len(DIRECTORY_SKILLS), 100)
        self.assertIn("Produção de vídeos curtos", response.get_data(as_text=True))
        self.assertIn("Navegação do Cadu Skills", response.get_data(as_text=True))
        self.assertNotIn("Instrument Serif", response.get_data(as_text=True))
        self.assertEqual(client.get("/skills/assets/skills-icon-64.png").status_code, 200)

    def test_premium_share_urls_are_not_enumerable(self):
        client = _app().test_client()
        self.assertEqual(client.get("/skills/s/curto").status_code, 404)
        self.assertEqual(client.get("/skills/s/" + "x" * 40).status_code, 404)

    def test_studio_requires_login_and_api_never_debits_before_ledger(self):
        app = _app()
        client = app.test_client()
        self.assertEqual(client.get("/skills/studio").status_code, 302)
        with client.session_transaction() as sess:
            sess["user_id"] = 7
        response = client.post("/skills/api/cadu-media-planning/runs", json={"prompt": "Planeje"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "CREDITS_NOT_ENABLED")

    def test_credit_balance_respects_reservations_and_releases(self):
        balance = balance_from_ledger([
            {"kind": "monthly_grant", "amount": 20},
            {"kind": "reserve", "amount": -5},
            {"kind": "release", "amount": 2},
            {"kind": "capture", "amount": -3},
        ])
        self.assertEqual(balance.available, 14)
        self.assertTrue(balance.can_reserve(CADU_MEDIA_PLANNING["credit_cost"]))
        self.assertIs(get_public_skill("cadu-media-planning"), CADU_MEDIA_PLANNING)

    def test_public_preview_invites_after_second_consultation_and_stops_at_three(self):
        client = _app().test_client()
        for expected in (1, 2, 3):
            response = client.post("/skills/api/public/cadu-media-planning/preview", json={"prompt": "Planeje uma campanha regional de varejo"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["state"]["count"], expected)
        self.assertTrue(response.get_json()["state"]["show_ecosystem_invite"])
        self.assertEqual(client.post("/skills/api/public/cadu-media-planning/preview", json={"prompt": "Planeje uma campanha regional de varejo"}).status_code, 429)
        self.assertFalse(consultation_state(3, is_client=True)["show_ecosystem_invite"])
