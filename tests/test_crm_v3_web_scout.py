"""Testes isolados do Web Scout, sem rede ou PostgreSQL reais."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from flask import Flask

from aicentralv2 import crm_v3_routes
from aicentralv2 import crm_v3_web_scout as scout


class _Response:
    def __init__(self, status_code=200, body=None, headers=None, chunks=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}
        self._chunks = chunks or []

    def json(self):
        return self._body

    def iter_content(self, chunk_size=8192):
        del chunk_size
        return iter(self._chunks)


class WebScoutFirecrawlTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "FIRECRAWL_API_KEY": "fc-test",
                "FIRECRAWL_TIMEOUT_S": "10",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @patch.object(scout.requests, "post")
    def test_scrape_v2_usa_branding_e_links(self, post):
        post.return_value = _Response(
            body={"success": True, "data": {"branding": {"logo": "/logo.svg"}}}
        )

        data = scout._firecrawl_scrape("https://cliente.com.br")

        self.assertEqual(data["branding"]["logo"], "/logo.svg")
        kwargs = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "https://api.firecrawl.dev/v2/scrape")
        self.assertEqual(kwargs["json"]["formats"], ["branding", "links"])
        self.assertNotIn("markdown", kwargs["json"]["formats"])

    @patch.object(scout.requests, "post")
    def test_timeout_tenta_novamente_e_recupera(self, post):
        post.side_effect = [
            requests.Timeout("lento"),
            _Response(body={"success": True, "data": {"links": []}}),
        ]

        self.assertEqual(scout._firecrawl_scrape("https://cliente.com.br"), {"links": []})
        self.assertEqual(post.call_count, 2)

    @patch.object(scout.requests, "post")
    def test_timeout_definitivo_retorna_mensagem_acionavel(self, post):
        post.side_effect = requests.Timeout("lento")

        with self.assertRaisesRegex(RuntimeError, "demorou mais de 10s"):
            scout._firecrawl_scrape("https://cliente.com.br")
        self.assertEqual(post.call_count, 2)

    @patch.object(scout.requests, "post")
    def test_erro_de_autenticacao_nao_e_repetido(self, post):
        post.return_value = _Response(
            status_code=401,
            body={"success": False, "error": "Unauthorized"},
        )

        with self.assertRaisesRegex(RuntimeError, "credencial inválida"):
            scout._firecrawl_scrape("https://cliente.com.br")
        self.assertEqual(post.call_count, 1)

    def test_branding_tem_prioridade_e_normaliza_url_relativa(self):
        result = scout._montar_registro(
            "cliente.com.br",
            {
                "branding": {
                    "logo": "/assets/logo.svg",
                    "images": {"ogImage": "/social.jpg", "favicon": "/favicon.ico"},
                },
                "metadata": {
                    "title": "Cliente",
                    "description": "Descrição",
                    "ogImage": "/metadata.jpg",
                },
                "links": ["https://cliente.com.br/sobre"],
            },
        )

        self.assertEqual(result["logo_url"], "https://cliente.com.br/assets/logo.svg")
        self.assertEqual(result["favicon_url"], "https://cliente.com.br/favicon.ico")
        self.assertEqual(result["titulo"], "Cliente")
        self.assertEqual(result["menu_links"][0]["label"], "Sobre")

    def test_metadata_e_fallback_quando_branding_nao_tem_logo(self):
        result = scout._montar_registro(
            "cliente.com.br",
            {"metadata": {"ogImage": "/social.png", "favicon": "/icon.png"}},
        )

        self.assertEqual(result["logo_url"], "https://cliente.com.br/social.png")
        self.assertEqual(result["favicon_url"], "https://cliente.com.br/icon.png")

    @patch.object(scout.requests, "get")
    def test_download_rejeita_resposta_que_nao_e_imagem(self, get):
        get.return_value = _Response(
            headers={"Content-Type": "text/html"},
            chunks=[b"<html>nao e logo</html>"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(scout, "_LOGO_DIR", Path(tmp)):
                self.assertIsNone(
                    scout._persistir_logo_cliente(7, "https://cliente.com.br/logo")
                )
                self.assertEqual(list(Path(tmp).iterdir()), [])

    @patch.object(scout, "_upsert_erro")
    @patch.object(scout, "_firecrawl_scrape")
    def test_refresh_preserva_dados_anteriores_no_registro_de_erro(
        self, firecrawl, upsert_erro
    ):
        firecrawl.side_effect = RuntimeError("timeout")
        upsert_erro.return_value = {
            "status": "erro",
            "erro_mensagem": "timeout",
            "logo_url": "/static/uploads/clientes/anterior.png",
            "titulo": "Leitura anterior",
        }

        result = scout.refresh_web_info(7, "cliente.com.br")

        self.assertEqual(result["logo_url"], "/static/uploads/clientes/anterior.png")
        self.assertEqual(result["titulo"], "Leitura anterior")
        upsert_erro.assert_called_once_with(7, "cliente.com.br", "timeout")


class WebScoutRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test", TESTING=True)
        app.register_blueprint(crm_v3_routes.bp)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_name"] = "Teste"
            session["user_type"] = "admin"

    @patch.object(scout, "obter_web_info")
    def test_get_retorna_cache_sem_disparar_novo_scrape(self, obter):
        obter.return_value = {
            "status": "ok",
            "dominio": "cliente.com.br",
            "logo_url": "/static/uploads/clientes/logo.png",
        }

        response = self.client.get("/crm-v3/api/clientes/7/web-info")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["web_info"]["status"], "ok")
        obter.assert_called_once_with("7")

    @patch.object(scout, "refresh_web_info")
    @patch.object(scout, "obter_web_info")
    @patch.object(crm_v3_routes.store, "get_cliente")
    def test_refresh_expoe_timeout_com_status_http_200(
        self, get_cliente, obter, refresh
    ):
        get_cliente.return_value = {"id": 7, "site_url": "cliente.com.br"}
        obter.return_value = None
        refresh.return_value = {
            "status": "erro",
            "dominio": "cliente.com.br",
            "erro_mensagem": "O site demorou mais de 45s para responder.",
        }

        response = self.client.post("/crm-v3/api/clientes/7/web-info/refresh", json={})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["web_info"]["status"], "erro")
        self.assertIn("demorou", payload["web_info"]["erro_mensagem"])


if __name__ == "__main__":
    unittest.main()
