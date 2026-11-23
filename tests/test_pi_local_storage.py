"""Testes das pastas locais do PI (sem PostgreSQL)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.services.pi_local_storage import (
    diagnosticar_pastas_pi,
    exigir_pastas_pi_acessiveis,
    gerar_pastas_local_pi,
    is_local_arquivos_url,
    is_portal_arquivos_url,
    pi_storage_dir,
    resolve_arquivo,
    salvar_upload,
    sincronizar_urls_pastas_equipe,
    url_arquivos_para_cliente,
)
from aicentralv2.services.pi_make_webhooks import make_invites_enabled


class TestPiLocalStorage(unittest.TestCase):
    def test_is_local_arquivos_url(self):
        self.assertTrue(is_local_arquivos_url("http://localhost:5000/cadu_pi/9/arquivos/principal"))
        self.assertTrue(
            is_local_arquivos_url(
                "https://ai.centralcomm.media/campanha/p/cliente-pi-abc/arquivos/principal"
            )
        )
        self.assertFalse(is_local_arquivos_url("https://drive.google.com/drive/folders/abc"))

    def test_gerar_pastas_cria_subpastas(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.config["PI_UPLOAD_ROOT"] = tmp
            app.config["PI_FILES_SERVER_ONLY"] = False
            pi = {"id_pi": 42, "codigo_pi_cc": "PI999001"}

            with app.app_context():
                with patch("aicentralv2.db.atualizar_cadu_pi_gdrive") as mock_save:
                    mock_save.return_value = True
                    result = gerar_pastas_local_pi(pi, strict=True)
                base = pi_storage_dir(pi)
                self.assertTrue((base / "principal").is_dir())
            self.assertTrue((base / "financeiro").is_dir())
            self.assertIn("googled_pi_princ", result)
            self.assertIn("/arquivos/principal", result["googled_pi_princ"])
            self.assertIn("/cadu_pi/", result["googled_pi_princ"])
            mock_save.assert_called_once()

    def test_upload_e_download_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.config["PI_UPLOAD_ROOT"] = tmp
            app.config["PI_FILES_SERVER_ONLY"] = False
            pi = {"id_pi": 7, "codigo_pi_cc": "PI000007"}

            class FakeFile:
                filename = "briefing.pdf"

                def save(self, dest):
                    Path(dest).write_bytes(b"%PDF-test")

            with app.app_context():
                with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                    pi = {**pi, **gerar_pastas_local_pi(pi, strict=True)}
                saved = salvar_upload(pi, "principal", FakeFile())
                path = resolve_arquivo(pi, "principal", saved["name"])
            self.assertTrue(path.is_file())


    def test_windows_server_only_bloqueia_disco(self):
        app = Flask(__name__)
        app.config["PI_FILES_SERVER_ONLY"] = True
        pi = {"id_pi": 1, "codigo_pi_cc": "PI1"}
        with app.app_context():
            with patch("aicentralv2.services.pi_local_storage.platform.system", return_value="Windows"):
                with self.assertRaises(Exception) as ctx:
                    gerar_pastas_local_pi(pi, strict=True)
                self.assertIn("servidor Linux", str(ctx.exception))

    def test_exigir_falha_sem_pasta(self):
        app = Flask(__name__)
        with app.app_context():
            with self.assertRaises(Exception):
                exigir_pastas_pi_acessiveis(
                    {"id_pi": 1, "codigo_pi_cc": "PI1", "googled_pi_princ": "http://x/cadu_pi/1/arquivos/principal"}
                )

    def test_diagnostico_ok_apos_gerar(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.config["PI_UPLOAD_ROOT"] = tmp
            app.config["PI_FILES_SERVER_ONLY"] = False
            pi = {"id_pi": 5, "codigo_pi_cc": "PI00005"}
            with app.app_context():
                with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True):
                    with patch(
                        "aicentralv2.db.obter_link_publico_pi",
                        return_value={"link_publico_token": "test-token", "link_publico_ativo": True},
                    ):
                        gerar_pastas_local_pi(pi, strict=True)
                d = diagnosticar_pastas_pi(
                    {**pi, "googled_pi_princ": f"http://localhost/cadu_pi/5/arquivos/principal"}
                )
            self.assertTrue(d["ok"])


    def test_sincronizar_urls_pastas_equipe_campanha_para_portal(self):
        app = Flask(__name__)
        app.config["PI_PASTAS_BACKEND"] = "local"
        pi = {
            "id_pi": 182,
            "codigo_pi_cc": "PI teste",
            "googled_pi_princ": "https://ai.centralcomm.media/campanha/p/token-x/arquivos/principal",
            "googled_pi_financ": "https://ai.centralcomm.media/campanha/p/token-x/arquivos/financeiro",
            "googled_pi_pecas": "https://ai.centralcomm.media/campanha/p/token-x/arquivos/pecas",
            "googled_pi_arq_ass": "https://ai.centralcomm.media/campanha/p/token-x/arquivos/assinados",
        }
        with app.app_context():
            with patch("aicentralv2.services.pi_local_storage.use_local_pastas", return_value=True):
                with patch("aicentralv2.db.atualizar_cadu_pi_gdrive", return_value=True) as mock_save:
                    urls = sincronizar_urls_pastas_equipe(pi)
            self.assertIsNotNone(urls)
            self.assertIn("/cadu_pi/182/arquivos/principal", urls["googled_pi_princ"])
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            self.assertTrue(is_portal_arquivos_url(args[1]))

    def test_sincronizar_nao_altera_portal_ou_drive(self):
        app = Flask(__name__)
        app.config["PI_PASTAS_BACKEND"] = "local"
        pi_portal = {
            "id_pi": 1,
            "googled_pi_princ": "https://ai.centralcomm.media/cadu_pi/1/arquivos/principal",
        }
        pi_drive = {"id_pi": 2, "googled_pi_princ": "https://drive.google.com/drive/folders/abc"}
        with app.app_context():
            with patch("aicentralv2.services.pi_local_storage.use_local_pastas", return_value=True):
                self.assertIsNone(sincronizar_urls_pastas_equipe(pi_portal))
                self.assertIsNone(sincronizar_urls_pastas_equipe(pi_drive))

    def test_url_arquivos_para_cliente_usa_token(self):
        app = Flask(__name__)
        pi = {"id_pi": 9, "codigo_pi_cc": "PI9"}
        portal = "https://ai.centralcomm.media/cadu_pi/9/arquivos/principal"
        with app.app_context():
            with patch(
                "aicentralv2.services.pi_local_storage.arquivos_url_publica_pi",
                return_value="https://ai.centralcomm.media/campanha/p/tok/arquivos/principal",
            ):
                url = url_arquivos_para_cliente(pi, "principal", portal)
            self.assertIn("/campanha/p/", url)


class TestMakeFlags(unittest.TestCase):
    def test_invites_desligado_por_padrao(self):
        app = Flask(__name__)
        with app.app_context():
            self.assertFalse(make_invites_enabled())


if __name__ == "__main__":
    unittest.main()