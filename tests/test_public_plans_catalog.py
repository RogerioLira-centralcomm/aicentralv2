import unittest
from pathlib import Path

from aicentralv2.cadu_workspace import routes
from aicentralv2.cadu_billing_catalog import PLAN_CATALOG

ROOT = Path(__file__).resolve().parents[1]


class PublicPlansFormattingTests(unittest.TestCase):
    def test_formata_preco_em_reais_com_ponto_de_milhar(self):
        self.assertEqual(routes._brl_label(297.0), "R$ 297")
        self.assertEqual(routes._brl_label(1497.0), "R$ 1.497")
        self.assertEqual(routes._brl_label(49.5), "R$ 49,50")

    def test_sem_valor_mostra_consulte(self):
        self.assertEqual(routes._brl_label(None), "Consulte")
        self.assertEqual(routes._tokens_short(None), "Consulte")
        self.assertEqual(routes._storage_label(None), "Consulte")

    def test_tokens_e_espaco_abreviados(self):
        self.assertEqual(routes._tokens_short(100_000), "100 mil")
        self.assertEqual(routes._tokens_short(1_000_000), "1 mi")
        self.assertEqual(routes._tokens_short(350_000), "350 mil")
        self.assertEqual(routes._storage_label(10.0), "10 GB")


class PublicPlanCardTests(unittest.TestCase):
    def test_free_leva_ao_cadastro_e_pagos_ao_contato(self):
        urls = {"signup_url": "/signup", "contact_url": "/contato"}
        free = routes._public_plan_card(routes.PUBLIC_FREE_PLAN, **urls)
        self.assertEqual(free["price_main"], "Grátis")
        self.assertEqual(free["href"], "/signup")
        paid = routes._public_plan_card({**PLAN_CATALOG[0], "tokens_monthly": None, "storage_gb": None}, **urls)
        self.assertEqual(paid["href"], "/contato")
        self.assertEqual(paid["cta_label"], "Falar com a equipe")
        self.assertEqual(paid["tokens_text"], "Consulte")
        self.assertEqual(paid["price_unit"], "/mês")

    def test_plano_sem_preco_nao_mostra_unidade(self):
        card = routes._public_plan_card({**PLAN_CATALOG[0], "price_monthly": None}, signup_url="/signup", contact_url="/contato")
        self.assertEqual(card["price_main"], "Consulte")
        self.assertEqual(card["price_unit"], "")


class PublicPlansTemplateTests(unittest.TestCase):
    def test_pagina_publica_nao_tem_preco_fixo(self):
        html = (ROOT / "aicentralv2" / "templates" / "cadu_workspace" / "public_page.html").read_text(encoding="utf-8")
        partial = (ROOT / "aicentralv2" / "templates" / "cadu_workspace" / "_public_plans.html").read_text(encoding="utf-8")
        for fixed in ("R$ 149", "R$ 549", "R$ 1.490", "'149'", "'549'", "'1490'"):
            self.assertNotIn(fixed, html)
            self.assertNotIn(fixed, partial)
        self.assertIn("_public_plans.html", html)


if __name__ == "__main__":
    unittest.main()
