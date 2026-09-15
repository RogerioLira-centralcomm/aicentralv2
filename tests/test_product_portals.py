from pathlib import Path
from unittest import TestCase

from flask import Flask

from aicentralv2.cadu_connect.routes import bp as connect_bp
from aicentralv2.cadu_identity.routes import bp as identity_bp
from aicentralv2.product_domains import product_url, register_product_host_routing, safe_product_target


ROOT = Path(__file__).resolve().parents[1]


def _app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / "aicentralv2" / "templates"),
        static_folder=str(ROOT / "aicentralv2" / "static"),
    )
    app.config.update(
        SECRET_KEY="test",
        CENTRALX_URL="https://ai.centralcomm.media",
        CADU_URL="https://cadu.centralcomm.media",
        STUDIO_URL="https://studio.centralcomm.media",
        SKILLS_URL="https://skills.centralcomm.media",
        PLANNER_URL="https://planner.centralcomm.media",
        CONNECT_URL="https://connect.centralcomm.media",
        AUTH_URL="https://auth.centralcomm.media",
        CADU_GOOGLE_LOGIN_URL="https://cadu.centralcomm.media/google-login.php",
        SESSION_COOKIE_DOMAIN="centralcomm.media",
    )
    app.add_url_rule("/login", "login", lambda: "login")
    app.add_url_rule("/logout", "logout", lambda: "logout")
    app.add_url_rule("/", "index", lambda: "centralx")
    app.add_url_rule("/studio", "parametros.modelagem_criativos", lambda: "studio")
    app.add_url_rule("/skills/", "cadu_skills.marketplace", lambda: "skills")
    app.add_url_rule("/smart-planner/", "smart_planner.index", lambda: "planner")
    app.register_blueprint(connect_bp)
    app.register_blueprint(identity_bp)
    app.context_processor(lambda: {"product_url": product_url})
    register_product_host_routing(app)
    return app


class ProductPortalsTest(TestCase):
    def test_each_product_domain_has_a_root_entry(self):
        client = _app().test_client()
        expected = {
            "auth.centralcomm.media": "/auth/",
            "connect.centralcomm.media": "/connect/",
            "studio.centralcomm.media": "/studio",
            "skills.centralcomm.media": "/skills/",
            "planner.centralcomm.media": "/smart-planner/",
        }
        for host, path in expected.items():
            with self.subTest(host=host):
                response = client.get("/", headers={"Host": host})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], path)

    def test_login_get_is_canonical_on_the_auth_domain(self):
        client = _app().test_client()
        response = client.get(
            "/login?next=https%3A%2F%2Fplanner.centralcomm.media%2F",
            headers={"Host": "ai.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://auth.centralcomm.media/login?next=https%3A%2F%2Fplanner.centralcomm.media%2F",
        )

    def test_connect_requires_login_and_renders_for_a_session(self):
        app = _app()
        client = app.test_client()
        response = client.get("/connect/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("https://auth.centralcomm.media/login?"))
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_name="Apolo", user_email="apolo@centralcomm.media")
        response = client.get("/connect/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cadu Connect", response.get_data(as_text=True))

    def test_identity_has_no_dashboard_and_redirects_to_product(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_name="Apolo", user_email="apolo@centralcomm.media", is_centralcomm=True)
        response = client.get("/auth/", headers={"Host": "auth.centralcomm.media"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://ai.centralcomm.media/")

    def test_cadu_google_access_uses_existing_php_flow(self):
        client = _app().test_client()
        response = client.get(
            "/auth/google?next=https%3A%2F%2Fplanner.centralcomm.media%2F",
            headers={"Host": "auth.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 302)
        target = response.headers["Location"]
        self.assertTrue(target.startswith("https://cadu.centralcomm.media/google-login.php?"))
        self.assertIn("v3=1", target)
        self.assertIn("return_to=https%3A%2F%2Fplanner.centralcomm.media%2F", target)

    def test_redirect_targets_are_limited_to_product_hosts(self):
        app = _app()
        with app.test_request_context("/"):
            self.assertEqual(
                safe_product_target("https://planner.centralcomm.media/plano/1"),
                "https://planner.centralcomm.media/plano/1",
            )
            self.assertEqual(safe_product_target("https://evil.example/x", "/"), "/")
            self.assertEqual(safe_product_target("//evil.example/x", "/"), "/")

    def test_sso_migration_never_persists_the_raw_ticket(self):
        sql = (ROOT / "migrations" / "add_cadu_sso_tickets.sql").read_text()
        self.assertIn("token_hash CHAR(64)", sql)
        self.assertNotIn("raw_token", sql)
        self.assertIn("consumed_at", sql)
