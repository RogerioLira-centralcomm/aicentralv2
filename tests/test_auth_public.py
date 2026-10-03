import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates"
STATIC = ROOT / "aicentralv2" / "static"
AUTH = ROOT / "frontend" / "cadu-design-system" / "auth"


def auth_source():
    """The access screens are split in modules: every text assertion reads them all."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(AUTH.glob("*.js*")))


class AuthPublicLayoutTests(unittest.TestCase):
    def test_shell_trava_viewport_e_teclado(self):
        base = (TEMPLATES / "base_auth_react.html").read_text(encoding="utf-8")
        css = (AUTH / "styles.css").read_text(encoding="utf-8")
        app = auth_source()

        # The keyboard resizes the layout (Chrome) or is measured through visualViewport (iOS): never "overlays-content".
        self.assertIn("interactive-widget=resizes-content", base)
        self.assertNotIn("overlays-content", base)
        self.assertIn("workspace-kit.css", base + (TEMPLATES / "cadu_workspace" / "_untitled_styles.html").read_text(encoding="utf-8"))
        self.assertIn("cadu-auth-root", base)
        self.assertIn("cadu_auth/app.css", base)
        self.assertIn("cadu_auth/app.js", base)
        self.assertIn("100svh", css)
        self.assertIn("--auth-kb", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn(".cadu-auth-visual, .cadu-auth-signup-rail { display: none; }", css)
        self.assertIn("inputMode: 'email'", app)
        self.assertIn("cadu-auth-mobile-tools", app)
        self.assertIn("cadu-auth-noscript", base)
        self.assertIn("cadu-auth-transition", app)
        self.assertNotIn(".cadu-auth-flashes { position: fixed", css)

    def test_login_e_recuperacao_sem_autofocus(self):
        login = (TEMPLATES / "login_tailwind.html").read_text(encoding="utf-8")
        forgot = (TEMPLATES / "forgot_password_tailwind.html").read_text(encoding="utf-8")
        reset = (TEMPLATES / "reset_password_tailwind.html").read_text(encoding="utf-8")

        self.assertNotIn("autofocus", login)
        self.assertNotIn("autofocus", forgot)
        self.assertNotIn("autofocus", reset)
        self.assertIn("base_auth_react.html", login)
        self.assertIn("'page': 'login'", login)
        self.assertIn("'signupUrl'", login)
        self.assertIn("'forgotUrl'", login)
        self.assertIn("'caduLogoUrl'", login)
        self.assertIn("base_auth_react.html", forgot)
        self.assertIn("'requestSent': request_sent|default(false)", forgot)
        self.assertIn('Verifique seu email', auth_source())
        self.assertIn("base_auth_react.html", reset)

    def test_dominio_corporativo_apenas_no_login_interno(self):
        login = (TEMPLATES / "login_tailwind.html").read_text(encoding="utf-8")
        forgot = (TEMPLATES / "forgot_password_tailwind.html").read_text(encoding="utf-8")
        app = auth_source()

        self.assertIn("'isCorporate': is_centralx_access", login)
        self.assertIn("email_local", app)
        self.assertIn("Use seu acesso CentralComm.", app)
        self.assertNotIn("'isCorporate': is_centralx_access", forgot)

    def test_convite_usa_shell_publico(self):
        invite = (TEMPLATES / "aceitar_convite.html").read_text(encoding="utf-8")
        self.assertIn("{% extends \"base_auth_public.html\" %}", invite)
        self.assertNotIn("base_auth.html", invite)
        self.assertNotIn("btn-primary", invite)
        self.assertNotIn("form-control", invite)
        self.assertIn('name="senha"', invite)
        self.assertIn('name="confirmar_senha"', invite)
        self.assertIn("{% block page_name %}invite{% endblock %}", invite)

    def test_cadastro_publico_usa_google_e_mostra_ferramentas(self):
        signup = (TEMPLATES / "signup_tailwind.html").read_text(encoding="utf-8")
        app = auth_source()

        self.assertIn("base_auth_react.html", signup)
        self.assertIn("'page': 'signup'", signup)
        self.assertIn("Criar conta com Google", app)
        self.assertIn("cadu_identity.google_signup", signup)
        self.assertIn("'formAction'", signup)
        self.assertIn('id="confirm_password"', app)
        self.assertIn('Nome completo', app)
        self.assertIn("Ferramentas incluídas no Cadu", app)
        for tool in ("Workspace", "Planner", "Studio", "Reports", "Skills"):
            self.assertIn(tool, app)


class AuthKeyboardAndTouchTests(unittest.TestCase):
    """Mobile and tablet keyboards were the main source of access errors: keep the fixes from regressing."""

    def test_campos_de_16px_e_alvo_de_toque(self):
        css = (AUTH / "styles.css").read_text(encoding="utf-8")
        self.assertIn("font-size: 16px", css)  # smaller text makes iOS zoom the page on focus
        self.assertIn("min-height: 48px", css)
        self.assertIn("env(safe-area-inset-bottom", css)

    def test_animacao_nao_deixa_transform_em_volta_dos_campos(self):
        import re
        motion = re.sub(r"/\*.*?\*/", "", (STATIC / "css" / "cadu-auth-motion.css").read_text(encoding="utf-8"), flags=re.S)
        self.assertNotIn("transform", motion)
        self.assertNotIn(" both", motion)

    def test_teclado_e_cache_do_navegador(self):
        hook = (AUTH / "useAuthViewport.js").read_text(encoding="utf-8")
        form = (AUTH / "useAuthForm.js").read_text(encoding="utf-8")
        self.assertIn("visualViewport", hook)
        self.assertIn("pageshow", hook)  # back/forward cache must not leave the button spinning
        self.assertIn("persisted", hook)
        self.assertIn("onRestore", form)

    def test_campos_nao_corrompem_email_e_senha(self):
        fields = (AUTH / "AuthFields.jsx").read_text(encoding="utf-8")
        for hint in ("autoCapitalize: 'none'", "autoCorrect: 'off'", "spellCheck: false", "enterKeyHint"):
            self.assertIn(hint, fields)
        self.assertIn("onMouseDown={event => event.preventDefault()}", fields)  # show/hide never closes the keyboard

    def test_formularios_validam_sem_bolhas_do_navegador(self):
        pages = (AUTH / "AuthPages.jsx").read_text(encoding="utf-8")
        self.assertGreaterEqual(pages.count("noValidate"), 4)
        for name in ("autoComplete=\"new-password\"", "autoComplete=\"current-password\""):
            self.assertIn(name, pages)


class CentralxAccessScreensTests(unittest.TestCase):
    """ai.centralcomm.media is the internal CentralX access: it never says Cadu."""

    def test_copy_do_centralx_nao_cita_cadu(self):
        copy = (AUTH / "brandCopy.js").read_text(encoding="utf-8")
        centralx = copy[copy.index("centralx: {"):copy.index("export const copyFor")]
        self.assertNotIn("Cadu", centralx)
        self.assertIn("Acesse o CentralX", centralx)

    def test_telas_de_senha_recebem_o_produto_do_servidor(self):
        for name in ("login_tailwind.html", "forgot_password_tailwind.html", "reset_password_tailwind.html"):
            template = (TEMPLATES / name).read_text(encoding="utf-8")
            self.assertIn("'product': 'centralx' if is_centralx_host else 'cadu'", template, name)
            self.assertIn("images/cc_logo.png", template, name)

    def test_link_de_redefinicao_so_vai_para_o_centralx_com_email_corporativo(self):
        routes = (ROOT / "aicentralv2" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("internal = is_centralx_request() and email.endswith('@' + LOGIN_EMAIL_DOMAIN)", routes)
        self.assertIn("product_url('centralx' if internal else 'auth'", routes)

    def test_servidor_renderiza_centralx_no_dominio_interno(self):
        from urllib.parse import urlparse
        from tests.shared_app import get_app
        app = get_app()
        host = urlparse(str(app.config.get("CENTRALX_URL") or "")).hostname
        if not host:
            self.skipTest("CENTRALX_URL não configurada")
        client = app.test_client()
        for path in ("/login", "/forgot-password"):
            html = client.get(path, headers={"Host": host}).get_data(as_text=True)
            self.assertIn('"product": "centralx"', html, path)
            self.assertIn("CentralX", html, path)
            self.assertNotIn("Cadu Workspace", html, path)


if __name__ == "__main__":
    unittest.main()
