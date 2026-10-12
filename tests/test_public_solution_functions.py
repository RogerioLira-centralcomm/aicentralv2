import unittest
from pathlib import Path

from aicentralv2.cadu_workspace import routes
from aicentralv2.cadu_workspace.public_solution_functions import SOLUTION_FUNCTIONS

ROOT = Path(__file__).resolve().parents[1]

# Funções fora do lançamento: não podem aparecer nas páginas públicas.
NOT_RELEASED = ("mesa infinita", "portais e veículos", "site & jornada", "sites e funis", "creative analyzer",
                "copy ads", "smart docs", "docs")


class PublicSolutionFunctionsTests(unittest.TestCase):
    def test_toda_solucao_publicada_tem_funcoes(self):
        for slug in routes.PUBLIC_SOLUTIONS:
            with self.subTest(solution=slug):
                groups = SOLUTION_FUNCTIONS.get(slug)
                self.assertTrue(groups, slug)
                for group in groups:
                    self.assertTrue(group["title"])
                    self.assertTrue(group["items"], group["title"])

    def test_nomes_unicos_e_descricao_preenchida(self):
        for slug, groups in SOLUTION_FUNCTIONS.items():
            names = [item["name"] for group in groups for item in group["items"]]
            with self.subTest(solution=slug):
                self.assertEqual(len(names), len(set(names)))
                for group in groups:
                    for item in group["items"]:
                        self.assertTrue(item["description"].strip(), item["name"])

    def test_descricoes_sem_preco_ou_promessa_de_performance(self):
        for slug, groups in SOLUTION_FUNCTIONS.items():
            for group in groups:
                for item in group["items"]:
                    text = f"{item['name']} {item['description']}".lower()
                    self.assertNotIn("r$", text, item["name"])
                    self.assertNotIn("garant", text, item["name"])

    def test_funcoes_nao_lancadas_ficam_de_fora(self):
        for slug, groups in SOLUTION_FUNCTIONS.items():
            for group in groups:
                for item in group["items"]:
                    text = item["name"].lower()
                    for banned in NOT_RELEASED:
                        self.assertNotIn(banned, text, f"{slug}: {item['name']}")

    def test_template_renderiza_todas_as_funcoes(self):
        html = (ROOT / "aicentralv2" / "templates" / "cadu_workspace" / "public_solution.html").read_text(encoding="utf-8")
        self.assertIn("function_groups", html)
        self.assertIn("solution-functions", html)


if __name__ == "__main__":
    unittest.main()
