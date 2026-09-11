import unittest
from datetime import timedelta
from unittest.mock import patch

from flask import Flask, session

from aicentralv2.auth import (
    LOGIN_EMAIL_DOMAIN,
    compose_login_email,
    login_email_local_part,
    persist_login_session,
)
from aicentralv2.config import Config, ProductionConfig, TestingConfig
from aicentralv2.routes import login_required


class ComposeLoginEmailTests(unittest.TestCase):
    def test_monta_dominio_fixo_a_partir_da_parte_local(self):
        self.assertEqual(compose_login_email("Apolo.Lira"), "apolo.lira@centralcomm.media")
        self.assertEqual(LOGIN_EMAIL_DOMAIN, "centralcomm.media")

    def test_aceita_email_completo_do_dominio(self):
        self.assertEqual(
            compose_login_email("marina@centralcomm.media"),
            "marina@centralcomm.media",
        )

    def test_rejeita_outro_dominio_e_local_invalido(self):
        self.assertIsNone(compose_login_email("marina@gmail.com"))
        self.assertIsNone(compose_login_email("nome@empresa.com"))
        self.assertIsNone(compose_login_email(""))
        self.assertIsNone(compose_login_email("apo lo"))
        self.assertIsNone(compose_login_email(".apolo"))

    def test_extrai_parte_local(self):
        self.assertEqual(login_email_local_part("Apolo@centralcomm.media"), "apolo")
        self.assertEqual(login_email_local_part("marina"), "marina")


class SessionPersistenceConfigTests(unittest.TestCase):
    def test_sessao_permanente_renova_a_cada_request(self):
        self.assertGreaterEqual(Config.SESSION_LIFETIME_DAYS, 365)
        self.assertEqual(Config.PERMANENT_SESSION_LIFETIME, timedelta(days=Config.SESSION_LIFETIME_DAYS))
        self.assertTrue(Config.SESSION_REFRESH_EACH_REQUEST)
        self.assertTrue(Config.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(Config.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(ProductionConfig.SESSION_COOKIE_SECURE)
        self.assertFalse(TestingConfig.SESSION_COOKIE_SECURE)

    def test_persist_login_session_marca_cookie_permanente(self):
        app = Flask(__name__)
        app.secret_key = "auth-login-test"
        with app.test_request_context("/login"):
            persist_login_session()
            self.assertTrue(session.permanent)


class LoginRequiredPersistenceTests(unittest.TestCase):
    def test_falha_transitoria_nao_limpa_sessao(self):
        app = Flask(__name__)
        app.secret_key = "auth-login-test"

        @login_required
        def protected():
            return "ok"

        with app.test_request_context("/"):
            session["user_id"] = 17
            with patch("aicentralv2.routes.db.obter_contato_por_id", side_effect=RuntimeError("db down")):
                response = protected()

            self.assertEqual(session.get("user_id"), 17)
            self.assertEqual(response[1], 503)


if __name__ == "__main__":
    unittest.main()
