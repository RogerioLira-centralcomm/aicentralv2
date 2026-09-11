import unittest
from pathlib import Path

from aicentralv2.crm_v3_canais import (
    ficha_canal_texto,
    inferir_canal,
    listar_canais,
    resolver_canal,
)


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
