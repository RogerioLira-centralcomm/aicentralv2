"""Make desligado + pastas locais no fluxo de produção do PI."""

import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from aicentralv2.services.pi_local_storage import use_local_pastas
from aicentralv2.services.pi_make_webhooks import (
    disparar_webhooks_producao_pi,
    gerar_pastas_drive_pi,
    make_configuracao_enabled,
    make_invites_enabled,
)


class TestMakeWebhooksLocal(unittest.TestCase):
    def test_flags_desligados_por_padrao(self):
        app = Flask(__name__)
        app.config["PI_MAKE_INVITES_ENABLED"] = False
        app.config["PI_MAKE_CONFIGURACAO_ENABLED"] = False
        with app.app_context():
            self.assertFalse(make_invites_enabled())
            self.assertFalse(make_configuracao_enabled())

    def test_use_local_com_backend_local(self):
        app = Flask(__name__)
        app.config["PI_PASTAS_BACKEND"] = "local"
        with app.app_context():
            self.assertTrue(use_local_pastas())

    @patch("aicentralv2.services.pi_make_webhooks.requests.get")
    @patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True)
    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    def test_disparar_sem_make_quando_flags_off(self, mock_obter, _mock_gdrive, mock_get):
        app = Flask(__name__)
        app.config["PI_MAKE_INVITES_ENABLED"] = False
        app.config["PI_MAKE_CONFIGURACAO_ENABLED"] = False
        mock_obter.return_value = {
            "id_pi": 5,
            "codigo_pi_cc": "PI000005",
            "googled_pi_princ": "http://localhost/cadu_pi/5/arquivos/principal",
            "periodo_inicio": "2026-01-01",
            "periodo_fim": "2026-01-31",
        }
        pi = mock_obter.return_value
        with app.app_context():
            with patch.dict(
                "os.environ",
                {
                    "MAKE_WEBHOOK_PI_CONFIGURACAO": "https://hook.example/config",
                    "MAKE_WEBHOOK_PI_INVITES": "https://hook.example/invites",
                },
            ):
                with patch("aicentralv2.services.pi_make_webhooks._atualizar_status_pi_producao"):
                    erros = disparar_webhooks_producao_pi(pi, strict=False)
        self.assertEqual(erros, [])
        mock_get.assert_not_called()

    @patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True)
    def test_gerar_pastas_usa_local_sem_chamar_make(self, _mock_save):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.config["PI_PASTAS_BACKEND"] = "local"
            app.config["PI_UPLOAD_ROOT"] = tmp
            app.config["PI_FILES_SERVER_ONLY"] = False
            pi = {"id_pi": 99, "codigo_pi_cc": "PI000099"}
            with app.app_context():
                with patch.dict("os.environ", {"MAKE_WEBHOOK_GDRIVE": "https://hook.example/gdrive"}):
                    with patch(
                        "aicentralv2.db.obter_link_publico_pi",
                        return_value={"link_publico_token": "test-token", "link_publico_ativo": True},
                    ):
                        with patch("aicentralv2.services.pi_make_webhooks.requests.get") as mock_get:
                            out = gerar_pastas_drive_pi(pi, strict=True)
            self.assertIn("/arquivos/principal", out["googled_pi_princ"])
            mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()