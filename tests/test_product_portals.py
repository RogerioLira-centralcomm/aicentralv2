from pathlib import Path
from unittest import TestCase, mock

from flask import Blueprint, Flask
from jinja2 import TemplateNotFound

from aicentralv2.cadu_connect.routes import bp as connect_bp
from aicentralv2.cadu_connect import routes as connect_routes
from aicentralv2.cadu_identity.routes import bp as identity_bp
from aicentralv2.cadu_workspace.routes import bp as workspace_bp
from aicentralv2.cadu_workspace import routes as workspace_routes
from aicentralv2.product_domains import ProductSessionInterface, product_url, register_product_host_routing, safe_product_target


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
        # O fixture usa um único cliente entre hosts para injetar sessões de
        # teste; a configuração de produção compartilha o cookie Cadu.
        CADU_SESSION_COOKIE_DOMAIN=".centralcomm.media",
        CENTRALX_SESSION_COOKIE_NAME="centralx_session",
        CADU_SESSION_COOKIE_NAME="cadu_sso_session",
    )
    app.session_interface = ProductSessionInterface()
    app.add_url_rule("/login", "login", lambda: "login")
    app.add_url_rule("/logout", "logout", lambda: "logout")
    app.add_url_rule("/", "index", lambda: "centralx")
    app.add_url_rule("/studio", "parametros.modelagem_criativos", lambda: "studio")
    app.add_url_rule("/skills/", "cadu_skills.marketplace", lambda: "skills")
    app.add_url_rule("/skills/agentes", "cadu_skills.agents", lambda: "agents")
    app.add_url_rule("/smart-planner/", "smart_planner.index", lambda: "planner")
    studio_product_bp = Blueprint("studio_product", __name__)
    studio_product_bp.add_url_rule("/", "studio_home", lambda: "studio portal")
    app.register_blueprint(studio_product_bp)
    app.register_blueprint(connect_bp)
    app.register_blueprint(identity_bp)
    app.register_blueprint(workspace_bp)
    app.context_processor(lambda: {"product_url": product_url, "cadu_nav_credit": {"available": 84, "monthly": 100, "configured": True}})
    register_product_host_routing(app)
    return app


class ProductPortalsTest(TestCase):
    def test_each_product_domain_has_a_root_entry(self):
        client = _app().test_client()
        expected = {
            "auth.centralcomm.media": (302, "/auth/"),
            "connect.centralcomm.media": (200, None),
            "studio.centralcomm.media": (200, None),
            "skills.centralcomm.media": (302, "/skills/"),
            "planner.centralcomm.media": (302, "/familia/planner/"),
            "workspace.centralcomm.media": (302, "/workspace/"),
        }
        for host, (status, path) in expected.items():
            with self.subTest(host=host):
                response = client.get("/", headers={"Host": host})
                self.assertEqual(response.status_code, status)
                if host == "studio.centralcomm.media":
                    self.assertEqual(response.get_data(as_text=True), "studio portal")
                elif path is not None:
                    self.assertEqual(response.headers["Location"], path)

    def test_connect_legacy_family_entry_reaches_the_connect_product(self):
        client = _app().test_client()
        response = client.get(
            "/familia/connect/?project_id=12",
            headers={"Host": "connect.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://connect.centralcomm.media/?project_id=12",
        )

    def test_studio_legacy_family_entry_reaches_media_studio(self):
        client = _app().test_client()
        response = client.get(
            "/familia/studio/?client=174",
            headers={"Host": "studio.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://studio.centralcomm.media/studio/modelagem-criativos?client=174",
        )

    def test_workspace_and_skills_legacy_family_entries_reach_their_products(self):
        client = _app().test_client()
        cases = (
            ("workspace.centralcomm.media", "/familia/workspace/", "https://workspace.centralcomm.media/workspace/app"),
            ("workspace.centralcomm.media", "/familia/workspace/projetos", "https://workspace.centralcomm.media/workspace/app/projetos"),
            ("workspace.centralcomm.media", "/familia/workspace/consumo", "https://workspace.centralcomm.media/workspace/app/creditos"),
            ("workspace.centralcomm.media", "/familia/workspace/marcas/sistema?creative_client_id=31", "https://workspace.centralcomm.media/workspace/app/marcas/31?creative_client_id=31"),
            ("skills.centralcomm.media", "/familia/skills/minhas-skills", "https://skills.centralcomm.media/skills/"),
        )
        for host, path, location in cases:
            with self.subTest(host=host, path=path):
                response = client.get(path, headers={"Host": host})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], location)

    def test_login_stays_on_the_product_domain(self):
        client = _app().test_client()
        response = client.get(
            "/login?next=https%3A%2F%2Fplanner.centralcomm.media%2F",
            headers={"Host": "ai.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "login")

    def test_connect_has_a_public_entry_and_renders_the_workspace_for_a_session(self):
        app = _app()
        client = app.test_client()
        with mock.patch("aicentralv2.cadu_connect.routes.customization_targets") as targets:
            response = client.get("/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        public_html = response.get_data(as_text=True)
        self.assertIn("Tudo o que comprova o trabalho, no contexto certo.", public_html)
        self.assertIn("Entrar no Reports", public_html)
        self.assertIn("Criar conta", public_html)
        self.assertNotIn('class="connect-entry-sidebar"', public_html)
        targets.assert_not_called()
        with client.session_transaction(headers={"Host": "connect.centralcomm.media"}) as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo", user_email="apolo@centralcomm.media")
        with mock.patch("aicentralv2.cadu_connect.routes.campaigns_for_client", return_value=[]), \
             mock.patch("aicentralv2.cadu_connect.routes.customization_targets", return_value={"clients": [], "projects": []}):
            response = client.get("/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Reports", html)
        self.assertIn("O que precisa de decisão agora.", html)
        self.assertIn("Clientes e projetos", html)
        self.assertIn("relatórios de mídia por cliente", html)
        self.assertIn('reports-home.css?v=3', html)
        self.assertNotIn("Carteira de clientes", html)

    def test_workspace_session_is_reused_by_connect(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction(headers={"Host": "connect.centralcomm.media"}) as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo", user_email="apolo@centralcomm.media")

        with mock.patch("aicentralv2.cadu_connect.routes.campaigns_for_client", return_value=[]), \
             mock.patch("aicentralv2.cadu_connect.routes.customization_targets", return_value={"clients": [], "projects": []}):
            response = client.get("/", headers={"Host": "connect.centralcomm.media"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Reports", response.get_data(as_text=True))

    def test_connect_falls_back_to_the_operational_screen_when_entry_cannot_render(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction(headers={"Host": "connect.centralcomm.media"}) as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo")

        original_render = connect_routes.render_template

        def render_with_missing_entry(template, **context):
            if template == "cadu_connect/reports_home.html":
                raise TemplateNotFound(template)
            return original_render(template, **context)

        with mock.patch("aicentralv2.cadu_connect.routes.campaigns_for_client", return_value=[]), \
             mock.patch("aicentralv2.cadu_connect.routes.customization_targets", return_value={"clients": [], "projects": []}), \
             mock.patch("aicentralv2.cadu_connect.routes.render_template", side_effect=render_with_missing_entry):
            response = client.get("/", headers={"Host": "connect.centralcomm.media"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Estamos preparando sua operação.", response.get_data(as_text=True))

    @mock.patch("aicentralv2.cadu_workspace.routes.credit_position", return_value={
        "configured": True, "available": 75, "monthly": 110,
    })
    @mock.patch("aicentralv2.db.obter_planos_clientes", return_value=[{
        "plan_status": "active", "plan_definition_name": "Equipe",
        "pd_tokens_monthly_limit": 500, "pd_limit_image_generation": 100,
    }])
    @mock.patch("aicentralv2.db.obter_contatos_por_cliente", return_value=[{
        "nome_completo": "Apolo", "email": "apolo@centralcomm.media", "status": True,
        "cargo": "Administrador", "invite_status": None,
    }])
    def test_workspace_imports_php_account_data_for_team_plan_and_credits(self, _people, _plans, _credits):
        client = _app().test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo")

        team = client.get("/workspace/app/equipe", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(team.status_code, 200)
        self.assertIn("Apolo", team.get_data(as_text=True))
        self.assertIn("Administrador", team.get_data(as_text=True))

        plan = client.get("/workspace/app/planos", headers={"Host": "workspace.centralcomm.media"})
        self.assertIn("Equipe", plan.get_data(as_text=True))
        self.assertIn("500", plan.get_data(as_text=True))

        credits = client.get("/workspace/app/creditos", headers={"Host": "workspace.centralcomm.media"})
        self.assertIn("75", credits.get_data(as_text=True))

    def test_workspace_public_pages_do_not_render_authenticated_chrome(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction(headers={"Host": "workspace.centralcomm.media"}) as sess:
            sess.update(user_id=7, user_name="Apolo Lira", user_email="apolo@centralcomm.media")

        response = client.get("/workspace/contato", headers={"Host": "workspace.centralcomm.media"})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count('aria-label="Navegação principal"'), 1)
        self.assertNotIn("Apolo Lira", html)
        self.assertNotIn("apolo@centralcomm.media", html)
        self.assertNotIn("84 disponíveis", html)
        self.assertNotIn('cadu-product-switch', html)

    @mock.patch("aicentralv2.email_service.send_email", return_value=True)
    @mock.patch("aicentralv2.db.criar_lead", return_value=91)
    def test_workspace_public_contact_validates_and_redirects_to_thanks(self, create_lead, send_email):
        client = _app().test_client()
        invalid = client.post("/workspace/contato", data={"name": "A"}, headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("Revise as informações", invalid.get_data(as_text=True))

        response = client.post("/workspace/contato", data={
            "name": "Ana Souza", "email": "ana@empresa.com", "company": "Empresa",
            "profile": "marketing", "team_size": "6-20", "contact_preference": "email",
            "challenge": "Precisamos conectar planejamento, criação e resultados da equipe.",
        }, headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["Location"].endswith("/workspace/contato/obrigado"))
        self.assertTrue(create_lead.called)
        self.assertTrue(send_email.called)

        thanks = client.get(response.headers["Location"], headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(thanks.status_code, 200)
        self.assertIn("Recebemos seu contexto.", thanks.get_data(as_text=True))

    def test_workspace_exposes_unlisted_current_design_system_reference(self):
        client = _app().test_client()
        for path in ("/design-system", "/workspace/design-system"):
            with self.subTest(path=path):
                response = client.get(path, headers={"Host": "workspace.centralcomm.media"})
                html = response.get_data(as_text=True)

                self.assertEqual(response.status_code, 200)
                self.assertIn("Uma linguagem para organizar o trabalho.", html)
                self.assertIn("Projeto informa. Marca diferencia.", html)
                self.assertIn("A mesma mesa de trabalho, em modo contínuo.", html)
                self.assertIn('name="robots" content="noindex,nofollow"', html)
                self.assertIn('cadu-workspace-design-system.css?v=2', html)

    def test_workspace_has_public_site_and_private_app_reusing_cadu_php(self):
        app = _app()
        client = app.test_client()
        response = client.get("/workspace/", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Seu time não deveria reconstruir o briefing a cada entrega.", html)
        self.assertIn('data-public-nav', html)
        self.assertIn('data-carousel', html)
        self.assertIn('data-cadu-theme="light"', html)
        self.assertIn('rel="canonical" href="https://workspace.centralcomm.media/"', html)
        self.assertIn('>Criar conta</a>', html)
        self.assertIn('href="https://auth.centralcomm.media/login"', html)
        self.assertIn('class="studio-showcase"', html)
        self.assertIn('aria-label="Navegação principal"', html)
        self.assertIn('href="#como-funciona"', html)
        self.assertIn('id="seguranca"', html)
        self.assertNotIn('aria-label="Produtos Cadu"', html)
        self.assertEqual(client.get("/workspace/app", headers={"Host": "workspace.centralcomm.media"}).status_code, 302)
        for page in ("como-funciona", "planos", "ajuda", "contato"):
            with self.subTest(page=page):
                public = client.get(f"/workspace/{page}", headers={"Host": "workspace.centralcomm.media"})
                self.assertEqual(public.status_code, 200)
                self.assertIn('name="description"', public.get_data(as_text=True))
        with client.session_transaction() as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo")
        conversations = client.get("/workspace/app/conversas", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(conversations.status_code, 308)
        self.assertTrue(conversations.headers["Location"].endswith("/workspace/conversas-v2-lab"))
        sidebar_projects = [{"id": str(index), "nome": f"Projeto {index}"} for index in range(1, 7)]
        with mock.patch("aicentralv2.cadu_workspace.routes._workspace_sidebar_projects", return_value=sidebar_projects):
            response = client.get("/app", headers={"Host": "workspace.centralcomm.media"})
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Bom ter você de volta, Apolo.", html)
            self.assertIn('workspace-app-shell workspace-app-shell--home', html)
            self.assertIn('class="workspace-nav-icon"', html)
            self.assertIn('fa-solid fa-house', html)
            self.assertIn('fa-solid fa-comment-dots', html)
            self.assertIn('fa-solid fa-folder-open', html)
            self.assertIn('fa-solid fa-wand-magic-sparkles', html)
            self.assertNotIn('class="workspace-nav-abbr"', html)
            self.assertNotIn('title="Marcas"', html)
            self.assertIn('class="workspace-recent-projects"', html)
            self.assertLess(html.index('>Projeto 1</a>'), html.index('>Projeto 5</a>'))
            self.assertIn('data-cadu-sidebar-mobile-toggle', html)
            for label in ("Equipe", "Planos", "Uso", "Conta"):
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

    def test_workspace_sidebar_prioritizes_last_opened_projects_and_limits_six(self):
        app = _app()
        cursor = mock.MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchall.return_value = [
            {"id": str(index), "nome": f"Projeto {index}"} for index in range(1, 8)
        ]
        connection = mock.MagicMock()
        connection.cursor.return_value = cursor

        with app.test_request_context("/workspace/app", headers={"Host": "workspace.centralcomm.media"}):
            from flask import session
            session.update(user_id=7, cliente_id=12, workspace_recent_project_ids=["4", "2"])
            with mock.patch("aicentralv2.cadu_workspace.routes.get_db", return_value=connection):
                projects = workspace_routes._workspace_sidebar_projects(12)
            self.assertEqual([item["id"] for item in projects], ["4", "2", "1", "3", "5", "6"])
            workspace_routes._remember_workspace_project("5")
            self.assertEqual(session["workspace_recent_project_ids"], ["5", "4", "2"])

    def test_product_menu_keeps_the_public_cadu_entry_on_workspace(self):
        client = _app().test_client()
        response = client.get("/entrada/cadu", headers={"Host": "workspace.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('href="https://workspace.centralcomm.media/entrada/cadu"', html)
        self.assertNotIn('href="https://cadu.centralcomm.media/entrada/cadu"', html)
        self.assertIn('rel="canonical" href="https://workspace.centralcomm.media/entrada/cadu"', html)

    def test_public_home_explains_the_five_products_in_workflow_order(self):
        client = _app().test_client()
        html = client.get("/workspace/", headers={"Host": "workspace.centralcomm.media"}).get_data(as_text=True)
        labels = ("Workspace", "Planner", "Studio", "Reports", "Skills")
        for label in labels:
            self.assertIn(label, html)
        for icon in ("workspace-192.png", "planner-192.png", "studio-192.png", "connect-192.png", "skills-192.png"):
            self.assertIn(f"images/cadu/brand-icons/{icon}", html)

    @mock.patch("aicentralv2.cadu_connect.routes.link_campaign_project", return_value=True)
    def test_agents_links_campaign_to_project_inside_client_context(self, link):
        client = _app().test_client()
        with client.session_transaction(headers={"Host": "connect.centralcomm.media"}) as sess:
            sess.update(user_id=7, cliente_id=12)
        response = client.post(
            "/connect/api/campaigns/31/project", json={"project_id": 5},
            headers={"Host": "connect.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 200)
        link.assert_called_once_with(31, client_id=12, project_id=5, user_id=7)

    def test_connect_applies_a_verified_workspace_project_filter(self):
        app = _app()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7, cliente_id=12, user_name="Apolo",
                        family_context={"client_id": 12, "project_ref": "projects:5"})
        targets = {"clients": [], "projects": [{"id": 5, "client_id": 12, "name": "Lançamento"}]}
        with mock.patch("aicentralv2.cadu_connect.routes.campaigns_for_client", return_value=[]) as campaigns, \
             mock.patch("aicentralv2.cadu_connect.routes.customization_targets", return_value=targets):
            response = client.get("/", headers={"Host": "connect.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        campaigns.assert_called_once_with(12, project_id=5)
        self.assertIn("Lançamento", response.get_data(as_text=True))

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
