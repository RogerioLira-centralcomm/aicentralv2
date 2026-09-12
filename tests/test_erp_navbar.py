import unittest
from pathlib import Path

from flask import Flask, render_template, request, session, url_for as flask_url_for
from werkzeug.routing import BuildError, Rule

from aicentralv2 import is_erp_nav_item_active


class ErpNavbarTestCase(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        templates = root / "aicentralv2" / "templates"
        self.base_template = (templates / "base_erp.html").read_text()
        self.enterprise_css = (
            root / "aicentralv2" / "static" / "css" / "tailwind" / "enterprise-system.css"
        ).read_text()
        self.app = Flask(__name__, template_folder=str(templates))
        self.app.config.update(TESTING=True, SECRET_KEY="erp-navbar-test")

        def safe_url_for(endpoint, **values):
            try:
                return flask_url_for(endpoint, **values)
            except BuildError:
                query = "&".join(f"{key}={value}" for key, value in values.items())
                return f"/{endpoint}" + (f"?{query}" if query else "")

        self.app.jinja_env.globals["url_for"] = safe_url_for

    def _context(self, endpoint, query="", user_type="admin", finance_admin=False):
        context = self.app.test_request_context("/test" + (f"?{query}" if query else ""))
        context.push()
        self.addCleanup(context.pop)
        request.url_rule = Rule("/test", endpoint=endpoint)
        session.update(
            user_id=1,
            user_name="Teste",
            user_email="teste@centralx.local",
            user_type=user_type,
            is_finance_admin=finance_admin,
        )

    def _render_base(self, endpoint="index", user_type="admin", finance_admin=False):
        self._context(endpoint, user_type=user_type, finance_admin=finance_admin)
        return render_template(
            "base_erp.html",
            is_centralcomm_user=False,
            perfil_contato=None,
            is_erp_nav_item_active=is_erp_nav_item_active,
            cx_page_context={
                "module": "erp",
                "screen": endpoint,
                "entity_type": "",
                "entity_id": "",
                "entity_label": "",
            },
        )

    def test_item_ativo_respeita_query_string(self):
        self._context(
            "cadu_pi_lista",
            "id_sub_status_pi=4&origem=faturamento",
        )
        financeiro = {
            "endpoint": "cadu_pi_lista",
            "match_args": {"id_sub_status_pi": 4, "origem": "faturamento"},
        }
        operacao = {
            "endpoint": "cadu_pi_lista",
            "match_args": {"id_sub_status_pi": 4, "origem": "operacao"},
        }
        self.assertTrue(is_erp_nav_item_active(financeiro))
        self.assertFalse(is_erp_nav_item_active(operacao))

    def test_item_ativo_respeita_prefixo_lista_e_exclusao(self):
        self._context("crm.objetivos_consolidadas")
        self.assertTrue(
            is_erp_nav_item_active(
                {"endpoint": "crm.index", "match_prefix": "crm."}
            )
        )

        self._context("campanhas_pi_lista", "view=diarios")
        self.assertFalse(
            is_erp_nav_item_active(
                {
                    "endpoint": "campanhas_pi_lista",
                    "exclude_args": ["view"],
                }
            )
        )

    def test_menu_respeita_permissoes_especiais(self):
        admin_html = self._render_base(user_type="admin", finance_admin=False)
        self.assertNotIn("Migrations do banco", admin_html)
        self.assertNotIn("Gestão de reembolsos", admin_html)
        self.assertIn(
            'aria-label="Navegação principal" aria-hidden="true" inert',
            admin_html,
        )

        super_html = self._render_base(
            user_type="superadmin",
            finance_admin=True,
        )
        self.assertIn("Migrations do banco", super_html)
        self.assertIn("Gestão de reembolsos", super_html)

    def test_agente_usa_novo_icone_compacto_na_navbar_mobile(self):
        self.assertIn('class="cx-agent-trigger-icon"', self.base_template)
        self.assertIn("filename='images/agent-centralx.png', v=2", self.base_template)
        self.assertIn('aria-label="Abrir Agente CentralX"', self.base_template)
        self.assertIn("@media (max-width: 1279px)", self.enterprise_css)
        self.assertIn(".erp-topbar .cx-agent-trigger-icon", self.enterprise_css)
        self.assertIn("width: 1.125rem", self.enterprise_css)
        self.assertIn("height: 1.125rem", self.enterprise_css)
        self.assertIn("flex: 0 0 2.25rem", self.enterprise_css)

    def test_places_fica_no_comercial_junto_do_smart_planner(self):
        html = self._render_base()
        comercial = html.split("Comercial", 1)[1]
        planner = comercial.find("Smart Planner")
        places = comercial.find("Places")
        self.assertGreater(planner, -1)
        self.assertGreater(places, planner)
        self.assertIn('href="/places.index"', html)
        self.assertIn("fa-location-dot", html)

    def test_navbar_nao_tem_campo_pesquisar(self):
        self.assertNotIn("nav-busca-pi-input", self.base_template)
        self.assertNotIn("class=\"erp-search", self.base_template)
        self.assertNotIn("erp-mobile-search", self.base_template)
        html = self._render_base()
        self.assertNotIn("Buscar PI por código ou título", html)

    def test_horizontal_nav_aparece_em_768_sem_overflow_auto(self):
        css = self.base_template
        start_768 = css.find("@media (min-width: 768px) {")
        self.assertGreater(start_768, -1)
        block_768 = css[start_768:css.find("}", css.find(".erp-page-context", start_768)) + 1]
        self.assertIn(".erp-horizontal-nav { display: flex; }", block_768)
        self.assertIn(".erp-menu-toggle { display: none; }", block_768)
        self.assertIn(".erp-page-context { display: none; }", block_768)

        nav_start = css.find(".erp-horizontal-nav {")
        self.assertGreater(nav_start, -1)
        nav_block = css[nav_start:css.find("}", nav_start) + 1]
        declarations = "\n".join(
            line for line in nav_block.splitlines() if "/*" not in line
        )
        self.assertIn("overflow: visible", declarations)
        self.assertNotIn("overflow-x: auto", declarations)
        self.assertNotRegex(css, r"\.erp-horizontal-nav\s*\{[^}/]*overflow-x:\s*auto")

        menu_start = css.find(".erp-nav-menu {")
        menu_block = css[menu_start:css.find("}", menu_start)]
        self.assertIn("position: fixed", menu_block)
        self.assertIn("placeFixedMenu", css)
        self.assertIn("anyNavMenuOpen", css)
        self.assertIn("setTopNavGroupOpen(group, !open)", css)
        self.assertNotIn("ev.detail > 0", css)
        self.assertNotIn(".erp-icon-button", css)
        self.assertNotIn(".erp-nav-group::after", css)

    def test_toast_popover_fechado_nao_forca_display_flex(self):
        css = self.base_template
        start = css.find("#toast-container {")
        self.assertGreater(start, -1)
        block = css[start:css.find("#toast-container:popover-open", start)]
        self.assertIn("display: none !important", block)
        self.assertIn("background: transparent !important", block)
        self.assertNotIn("display: flex !important", block)
        self.assertIn("#toast-container[popover]:not(:popover-open)", css)
        self.assertIn("popover=\"manual\"", css)


if __name__ == "__main__":
    unittest.main()
