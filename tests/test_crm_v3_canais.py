import json
import unittest
from pathlib import Path

from flask import Flask

from aicentralv2.crm_v3_canais import (
    ficha_canal_texto,
    inferir_canal,
    listar_canais,
    resolver_canal,
)
from aicentralv2.crm_v3_routes import bp


ROOT = Path(__file__).resolve().parents[1]


class CrmV3CanaisCatalogTest(unittest.TestCase):
    def test_catalogo_tem_interativos_e_serasa(self):
        nomes = [item["nome"] for item in listar_canais()]
        self.assertIn("Interativos", nomes)
        self.assertTrue(any("Serasa" in nome or "Experian" in nome for nome in nomes) or "Serasa" in nomes)
        serasa = resolver_canal("Serasa")
        self.assertIsNotNone(serasa)
        self.assertTrue(serasa["arquivos"])
        self.assertIn("100M", ficha_canal_texto("Serasa", "imóveis"))

    def test_infere_interativos_pelo_titulo(self):
        self.assertEqual(inferir_canal("Apresentar formatos interativos"), "Interativos")
        self.assertEqual(inferir_canal("Apresentar Netflix", ""), "Netflix")
        self.assertEqual(inferir_canal("Qualquer coisa", "Serasa"), "Serasa")

    def test_ficha_imobiliario_prioriza_hot_spots(self):
        texto = ficha_canal_texto("Interativos", "lançamentos imobiliários e métricas de atenção")
        self.assertIn("Hot Spots", texto)
        self.assertIn("3-6%", texto)

    def test_modelo_da_atividade_e_gpt4o(self):
        source = (ROOT / "aicentralv2/crm_v3_routes.py").read_text()
        self.assertIn(
            'CRM_V3_ACTIVITY_MODEL = os.getenv("CRM_V3_ACTIVITY_MODEL", "openai/gpt-4o")',
            source,
        )

    def test_catalogo_vem_em_ordem_alfabetica(self):
        nomes = [item["nome"] for item in listar_canais()]
        self.assertEqual(nomes, sorted(nomes, key=str.casefold))
        self.assertLess(nomes.index("Amazon Music"), nomes.index("Netflix"))
        self.assertLess(nomes.index("Deezer"), nomes.index("Spotify"))

    def test_sidebar_ordena_canais_alfabeticamente(self):
        js = (ROOT / "aicentralv2/static/js/crm_v3_drawers.js").read_text()
        self.assertIn("function sortCanaisAlfabetico", js)
        self.assertIn("localeCompare", js)
        self.assertIn("canais = sortCanaisAlfabetico(canais)", js)

    def test_sidebar_canais_esta_no_crm(self):
        page = (ROOT / "aicentralv2/templates/crm_v3.html").read_text()
        drawer = (ROOT / "aicentralv2/templates/crm_v3/_drawer_canais.html").read_text()
        css = (ROOT / "aicentralv2/static/css/tailwind/enterprise-system.css").read_text()
        self.assertIn("crm-v3-btn-canais", page)
        self.assertIn("_drawer_canais.html", page)
        self.assertIn("cx-canais-desk", drawer)
        self.assertIn("cx-canais-rail", css)
        self.assertIn("grid-template-columns: 248px minmax(0, 1fr)", css)
        self.assertIn("--cx-surface", css)
        self.assertNotIn("#142c2e", css)

    def test_catalogo_traz_base_e_logo_local(self):
        canais = listar_canais()
        slugs = {item["slug"] for item in canais}
        self.assertGreaterEqual(len(canais), 33)
        self.assertIn("netflix", slugs)
        self.assertIn("interativos", slugs)
        netflix = resolver_canal("Netflix")
        self.assertIsNotNone(netflix)
        self.assertEqual(netflix["logo"], "/static/images/creative-viewers/netflix.png")
        self.assertTrue(netflix.get("descricao"))
        static_root = ROOT / "aicentralv2"
        for canal in canais:
            if canal["slug"] == "interativos":
                continue
            logo = canal.get("logo") or ""
            self.assertTrue(logo.startswith("/static/"), canal["slug"])
            rel = logo[len("/static/"):]
            self.assertTrue((static_root / "static" / rel).is_file(), canal["slug"] + " " + logo)

    def test_canal_publico_tem_formatos_segmentacao_e_assistente(self):
        from aicentralv2.crm_v3_canais import canal_publico
        for item in listar_canais():
            canal = canal_publico(item)
            self.assertTrue(canal["formatos"], canal["slug"])
            self.assertTrue(canal["segmentacoes"], canal["slug"])
            self.assertGreaterEqual(len((canal.get("assistente") or {}).get("passos") or []), 1, canal["slug"])
            self.assertTrue(canal["formatos"][0].get("chave"), canal["slug"])
            self.assertTrue(canal["formatos"][0].get("label"), canal["slug"])

    def test_catalogo_inclui_ifood_uber_99_logan(self):
        slugs = {item["slug"] for item in listar_canais()}
        for slug, nome in (("ifood", "iFood"), ("uber", "Uber"), ("99", "99"), ("logan", "Logan")):
            self.assertIn(slug, slugs)
            canal = resolver_canal(nome)
            self.assertIsNotNone(canal)
            self.assertEqual(canal["slug"], slug)
            self.assertTrue((canal.get("logo") or "").startswith("/static/"), slug)
            self.assertTrue(canal.get("formatos"), slug)
        self.assertEqual(inferir_canal("Apresentar iFood"), "iFood")
        self.assertEqual(inferir_canal("Campanha Uber e recibo"), "Uber")
        self.assertEqual(inferir_canal("Mídia Logan no trajeto"), "Logan")

    def test_ficha_traz_formato_e_segmentacao(self):
        netflix = ficha_canal_texto("Netflix")
        self.assertIn("Formatos:", netflix)
        self.assertIn("Segmentações:", netflix)
        self.assertIn("Quando indicar:", netflix)
        instagram = ficha_canal_texto("Instagram")
        self.assertIn("Stories", instagram)
        self.assertIn("9:16", instagram)
        serasa = ficha_canal_texto("Serasa", "imóveis")
        self.assertIn("100M", serasa)
        self.assertIn("Imóveis", serasa)

    def test_sidebar_tem_sessao_playbook_e_thumbs(self):
        drawer = (ROOT / "aicentralv2/templates/crm_v3/_drawer_canais.html").read_text()
        js = (ROOT / "aicentralv2/static/js/crm_v3_drawers.js").read_text()
        css = (ROOT / "aicentralv2/static/css/tailwind/enterprise-system.css").read_text()
        self.assertIn("data-canais-sessao", drawer)
        self.assertIn("data-canais-cats", drawer)
        self.assertIn("data-canais-playbook", js)
        self.assertIn("data-canais-gerar", js)
        self.assertIn("cx-canais-thumb", js)
        self.assertIn("falar_sobre_canal", js)
        self.assertIn("is-detail", css)
        self.assertIn("is-sessao", css)
        self.assertIn("flex-wrap: nowrap", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("aspect-ratio: 1 / 1", css)
        self.assertIn("aspect-ratio: 9 / 16", css)
        self.assertIn("aspect-ratio: 300 / 250", css)
        self.assertIn("#crm-v3-btn-canais", (ROOT / "aicentralv2/static/css/crm_v3.css").read_text())

    def test_api_canais_devolve_contrato_enriquecido(self):
        app = Flask(
            __name__,
            template_folder=str(ROOT / "aicentralv2/templates"),
            static_folder=str(ROOT / "aicentralv2/static"),
        )
        app.config.update(SECRET_KEY="test-canais", TESTING=True)
        app.register_blueprint(bp)
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Executivo Teste"
            sess["user_email"] = "teste@centralx.com"
            sess["user_type"] = "admin"
        res = client.get("/crm-v3/api/canais")
        self.assertEqual(res.status_code, 200)
        payload = json.loads(res.data)
        canais = payload.get("canais") or (payload.get("data") if isinstance(payload.get("data"), list) else [])
        self.assertGreaterEqual(len(canais), 33)
        netflix = next(item for item in canais if item.get("slug") == "netflix")
        instagram = next(item for item in canais if item.get("slug") == "instagram")
        serasa = next(item for item in canais if "serasa" in (item.get("nome") or "").casefold())
        for canal in (netflix, instagram, serasa):
            self.assertTrue(canal.get("formatos"))
            self.assertTrue(canal.get("segmentacoes"))
            self.assertGreaterEqual(len((canal.get("assistente") or {}).get("passos") or []), 1)
        detalhe = client.get("/crm-v3/api/canais/netflix")
        self.assertEqual(detalhe.status_code, 200)
        body = json.loads(detalhe.data)
        canal = body.get("canal") or body.get("data") or {}
        self.assertEqual(canal.get("slug"), "netflix")
        self.assertTrue(canal.get("formatos"))
