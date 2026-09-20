import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates"
STATIC = ROOT / "aicentralv2" / "static"


class AuthPublicLayoutTests(unittest.TestCase):
    def test_shell_trava_viewport_e_teclado(self):
        base = (TEMPLATES / "base_auth_react.html").read_text(encoding="utf-8")
        css = (ROOT / "frontend" / "cadu-design-system" / "auth" / "styles.css").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "cadu-design-system" / "auth" / "AuthApp.jsx").read_text(encoding="utf-8")

        self.assertIn("interactive-widget=overlays-content", base)
        self.assertIn("cadu-auth-root", base)
        self.assertIn("cadu_auth/app.css", base)
        self.assertIn("cadu_auth/app.js", base)
        self.assertIn("100dvh", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("cadu-auth-visual { display: none; }", css)
        self.assertIn("inputMode=\"email\"", app)
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
        self.assertIn("base_auth_react.html", reset)

    def test_dominio_corporativo_apenas_no_login_interno(self):
        login = (TEMPLATES / "login_tailwind.html").read_text(encoding="utf-8")
        forgot = (TEMPLATES / "forgot_password_tailwind.html").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "cadu-design-system" / "auth" / "AuthApp.jsx").read_text(encoding="utf-8")

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
        app = (ROOT / "frontend" / "cadu-design-system" / "auth" / "AuthApp.jsx").read_text(encoding="utf-8")

        self.assertIn("base_auth_react.html", signup)
        self.assertIn("'page': 'signup'", signup)
        self.assertIn("Criar conta com Google", app)
        self.assertIn("cadu_identity.google_signup", signup)
        self.assertIn("'formAction'", signup)
        self.assertIn('name="confirm_password"', app)
        self.assertIn('Nome completo', app)
        self.assertIn("Ferramentas incluídas no Cadu", app)
        for tool in ("Workspace", "Planner", "Studio", "Reports", "Skills"):
            self.assertIn(tool, app)


if __name__ == "__main__":
    unittest.main()
