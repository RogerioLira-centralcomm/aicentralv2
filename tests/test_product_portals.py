from pathlib import Path
from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_connect.routes import bp as connect_bp
from aicentralv2.cadu_identity.routes import bp as identity_bp
from aicentralv2.cadu_workspace.routes import bp as workspace_bp
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
        WORKSPACE_URL="https://workspace.centralcomm.media",
        AUTH_URL="https://auth.centralcomm.media",
        CADU_GOOGLE_LOGIN_URL="https://cadu.centralcomm.media/google-login.php",
        SESSION_COOKIE_DOMAIN="centralcomm.media",
    )
    app.add_url_rule("/login", "login", lambda: "login")
    app.add_url_rule("/logout", "logout", lambda: "logout")
    app.add_url_rule("/", "index", lambda: "centralx")
    app.add_url_rule("/studio", "parametros.modelagem_criativos", lambda: "studio")
    app.add_url_rule("/skills/", "cadu_skills.marketplace", lambda: "skills")
    app.add_url_rule("/skills/agentes", "cadu_skills.agents", lambda: "agents")
    app.add_url_rule("/smart-planner/", "smart_planner.index", lambda: "planner")
    app.register_blueprint(connect_bp)
    app.register_blueprint(identity_bp)
    app.register_blueprint(workspace_bp)
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
            "workspace.centralcomm.media": "/workspace/",
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
            sess.update(user_id=7, cliente_id=12, user_name="Apolo", user_email="apolo@centralcomm.media")
        with mock.patch("aicentralv2.cadu_connect.routes.campaigns_for_client", return_value=[]), \
             mock.patch("aicentralv2.cadu_connect.routes.customization_targets", return_value={"clients": [], "projects": []}):
            response = client.get("/connect/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cadu Agentes", response.get_data(as_text=True))

    def test_workspace_has_public_site_and_private_app_reusing_cadu_php(self):
        app = _app()
        client = app.test_client()
        response = client.get("/workspace/", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("O contexto certo", html)
        self.assertIn('rel="canonical" href="https://workspace.centralcomm.media/"', html)
        self.assertEqual(client.get("/workspace/app", headers={"Host": "workspace.centralcomm.media"}).status_code, 302)
        for page in ("como-funciona", "planos", "ajuda", "contato"):
            with self.subTest(page=page):
                public = client.get(f"/workspace/{page}", headers={"Host": "workspace.centralcomm.media"})
                self.assertEqual(public.status_code, 200)
                self.assertIn('name="description"', public.get_data(as_text=True))
        with client.session_transaction() as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo")
        with mock.patch("aicentralv2.cadu_workspace.routes.customization_targets", return_value={"clients": [], "projects": []}), \
             mock.patch("aicentralv2.cadu_workspace.routes.list_customizations", return_value=[]), \
             mock.patch("aicentralv2.cadu_workspace.routes.credit_position", return_value={"available": 20, "monthly": 20, "configured": True}):
            response = client.get("/workspace/app", headers={"Host": "workspace.centralcomm.media"})
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Administração da conta", html)
            for label in ("Usuários", "Planos", "Créditos", "Financeiro", "Integrações"):
                self.assertIn(label, html)
        self.assertEqual(client.get("/workspace/agentes", headers={"Host": "workspace.centralcomm.media"}).headers["Location"], "/skills/agentes")
        robots = client.get("/robots.txt", headers={"Host": "workspace.centralcomm.media"}).get_data(as_text=True)
        self.assertIn("Allow: /workspace/", robots)
        self.assertIn("Disallow: /workspace/app", robots)
        llms = client.get("/llms.txt", headers={"Host": "workspace.centralcomm.media"}).get_data(as_text=True)
        self.assertIn("Páginas públicas", llms)
        sitemap = client.get("/sitemap.xml", headers={"Host": "workspace.centralcomm.media"}).get_data(as_text=True)
        self.assertIn("https://workspace.centralcomm.media/planos", sitemap)
        self.assertNotIn("/workspace/app", sitemap)
        self.assertEqual(client.get("/workspace/assets/workspace-icon-64.png").status_code, 200)

    def test_product_menu_keeps_the_public_cadu_entry_on_workspace(self):
        client = _app().test_client()
        response = client.get("/entrada/cadu", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="https://workspace.centralcomm.media/entrada/cadu"', html)
        self.assertNotIn('href="https://cadu.centralcomm.media/entrada/cadu"', html)
        self.assertIn('rel="canonical" href="https://workspace.centralcomm.media/entrada/cadu"', html)

    @mock.patch("aicentralv2.cadu_connect.routes.link_campaign_project", return_value=True)
    def test_agents_links_campaign_to_project_inside_client_context(self, link):
        client = _app().test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, cliente_id=12)
        response = client.post(
            "/connect/api/campaigns/31/project", json={"project_id": 5},
            headers={"Host": "connect.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 200)
        link.assert_called_once_with(31, client_id=12, project_id=5, user_id=7)

    def test_deploy_creates_agents_campaign_project_context(self):
        deploy = (ROOT / "deploy.sh").read_text()
        sql = (ROOT / "migrations" / "add_cadu_agent_campaign_projects.sql").read_text()
        self.assertIn("run_add_cadu_agent_campaign_projects.py", deploy)
        self.assertIn("campaign_id INTEGER PRIMARY KEY", sql)
        self.assertIn("client_id INTEGER NOT NULL", sql)

    def test_identity_has_no_dashboard_and_redirects_to_product(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_name="Apolo", user_email="apolo@centralcomm.media", is_centralcomm=True)
        response = client.get("/auth/", headers={"Host": "auth.centralcomm.media"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://ai.centralcomm.media/")

    def test_identity_enters_php_cadu_through_the_sso_handoff(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, user_name="Cliente", is_centralcomm=False)
        response = client.get("/auth/", headers={"Host": "auth.centralcomm.media"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "/auth/sso/to-cadu?next=https://cadu.centralcomm.media/",
        )

    def test_cadu_google_access_starts_from_central_auth(self):
        app = _app()
        app.config["CADU_GOOGLE_NATIVE_ENABLED"] = True
        client = app.test_client()
        with mock.patch("aicentralv2.cadu_identity.routes.google_authorization_url", return_value="https://accounts.google.com/o/oauth2/v2/auth") as authorize:
            response = client.get(
                "/auth/google?next=https%3A%2F%2Fplanner.centralcomm.media%2F",
                headers={"Host": "auth.centralcomm.media"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://accounts.google.com/o/oauth2/v2/auth")
        authorize.assert_called_once_with("cadu")

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
