import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


contrato = _load_module("contrato_tipos_test", "aicentralv2/contrato_tipos.py")
domain = _load_module(
    "rep_domain_test",
    "aicentralv2/representacao_comercial/domain.py",
)
parceiros = _load_module(
    "rep_parceiros_test",
    "aicentralv2/representacao_comercial/parceiros.py",
)

class RepresentacaoDomainTest(unittest.TestCase):
    def test_eh_representacao(self):
        self.assertTrue(
            domain.eh_representacao_comercial({"tipo_de_contrato": "representacao_comercial"})
        )
        self.assertFalse(
            domain.eh_representacao_comercial({"tipo_de_contrato": "operacao_propria"})
        )


class RepresentacaoParceirosTest(unittest.TestCase):
    def test_trilha_por_nome(self):
        self.assertEqual(parceiros.TRILHA_LOGAN, parceiros.resolver_trilha_parceiro(None, "Logan DOOH"))
        self.assertEqual(parceiros.TRILHA_SERASA, parceiros.resolver_trilha_parceiro(None, "Serasa Ads"))

    def test_metadados_logan_planilha(self):
        meta = parceiros.metadados_trilha(parceiros.TRILHA_LOGAN)
        self.assertEqual(meta["fluxo_proposta"], parceiros.FLUXO_PLANILHA)
        self.assertEqual(meta["vencimento_nf"], parceiros.VENCIMENTO_D_PLUS_2)


if __name__ == "__main__":
    unittest.main()
