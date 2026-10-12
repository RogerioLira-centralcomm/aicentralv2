import unittest

from tests.shared_app import get_app


class RemovedProductsTests(unittest.TestCase):
    """Copy Ads e a rota Docs do Planner saíram do produto; não podem voltar pelo mapa de URLs."""

    def setUp(self):
        self.app = get_app()
        self.rules = list(self.app.url_map.iter_rules())

    def test_copy_ads_sem_rotas(self):
        self.assertEqual([rule.rule for rule in self.rules if "copy-ads" in rule.rule], [])
        endpoints = {rule.endpoint for rule in self.rules}
        self.assertNotIn("cadu_family.copy_formats", endpoints)
        self.assertNotIn("cadu_family.copy_validate", endpoints)

    def test_docs_do_planner_sem_rota_de_host(self):
        endpoints = {rule.endpoint for rule in self.rules}
        self.assertNotIn("planner_host_docs", endpoints)


if __name__ == "__main__":
    unittest.main()
