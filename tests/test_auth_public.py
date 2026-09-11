import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates"
STATIC = ROOT / "aicentralv2" / "static"


class AuthPublicLayoutTests(unittest.TestCase):
    def test_shell_trava_viewport_e_teclado(self):
        base = (TEMPLATES / "base_auth_public.html").read_text(encoding="utf-8")
        css = (STATIC / "css" / "auth-public.css").read_text(encoding="utf-8")
        js = (STATIC / "js" / "auth-public.js").read_text(encoding="utf-8")

        self.assertIn("interactive-widget=overlays-content", base)
        self.assertIn('class="auth-root"', base)
        self.assertIn("auth-public.css", base)
        self.assertIn("?v=3", base)
        self.assertIn("visualViewport", js)
        self.assertIn("is-keyboard-open", js)
        self.assertIn("--vvh", css)
        self.assertIn("overflow: hidden", css)
        self.assertIn("font-size: 16px", css)
        self.assertIn("auth-scene-pan", css)

    def test_login_e_recuperacao_sem_autofocus(self):
        login = (TEMPLATES / "login_tailwind.html").read_text(encoding="utf-8")
        forgot = (TEMPLATES / "forgot_password_tailwind.html").read_text(encoding="utf-8")
        reset = (TEMPLATES / "reset_password_tailwind.html").read_text(encoding="utf-8")

        self.assertNotIn("autofocus", login)
        self.assertNotIn("autofocus", forgot)
        self.assertNotIn("autofocus", reset)
        self.assertIn('inputmode="email"', login)
        self.assertIn('name="email_local"', login)
        self.assertIn("@centralcomm.media", login)
        self.assertNotIn('name="remember"', login)
        self.assertNotIn("Manter acesso neste dispositivo", login)
        self.assertIn("{% extends \"base_auth_public.html\" %}", login)

    def test_login_e_recuperacao_usam_dominio_centralcomm(self):
        login = (TEMPLATES / "login_tailwind.html").read_text(encoding="utf-8")
        forgot = (TEMPLATES / "forgot_password_tailwind.html").read_text(encoding="utf-8")
        css = (STATIC / "css" / "auth-public.css").read_text(encoding="utf-8")
        js = (STATIC / "js" / "auth-public.js").read_text(encoding="utf-8")

        self.assertIn("auth-email-lock", login)
        self.assertIn("auth-email-lock", forgot)
        self.assertIn("auth-email-domain", css)
        self.assertIn("setupCorporateEmail", js)
        self.assertIn("centralcomm.media", js)

    def test_convite_usa_shell_publico(self):
        invite = (TEMPLATES / "aceitar_convite.html").read_text(encoding="utf-8")
        self.assertIn("{% extends \"base_auth_public.html\" %}", invite)
        self.assertNotIn("base_auth.html", invite)
        self.assertNotIn("btn-primary", invite)
        self.assertNotIn("form-control", invite)
        self.assertIn('name="senha"', invite)
        self.assertIn('name="confirmar_senha"', invite)
        self.assertIn("{% block page_name %}invite{% endblock %}", invite)


if __name__ == "__main__":
    unittest.main()
