import unittest
from unittest.mock import patch

from aicentralv2 import db
from aicentralv2.representacao_comercial.precificacao import calcular_breakdown_representacao_linha


def _deps():
    return {
        "parse_valor": db.parse_valor_monetario_para_float,
        "derivar_investimento_de_liquido_informado": db.derivar_investimento_de_liquido_informado,
        "derivar_investimento_de_preco": db.derivar_investimento_de_preco,
        "derivar_investimento_liquido_de_bruto": db.derivar_investimento_liquido_de_bruto,
        "obter_com_vendas_fracao": lambda _rid: 0.0,
    }


class PrecificacaoRepresentacaoTest(unittest.TestCase):
    def test_breakdown_so_valor_unitario_sem_tabela(self):
        cotacao = {
            "tipo_de_contrato": "representacao_comercial",
            "fee_ag": 20,
            "agencia_percentual": 20,
            "parceiro_percentual": 15,
        }
        data = {
            "plataforma": "Serasa",
            "objetivo_kpi": "CPM",
            "valor_unitario": 27,
            "investimento_liquido": 6400,
        }
        out = calcular_breakdown_representacao_linha(cotacao, data, **_deps())
        self.assertTrue(out["representacao_comercial"])
        self.assertEqual(out["valor_unitario"], 27)
        self.assertGreater(out["investimento_bruto"], out["investimento_liquido"])
        self.assertGreater(out["comissao_parceiro"], 0)

    @patch("aicentralv2.db.obter_descricao_objetivo_campanha", return_value="CPM")
    def test_kpi_resolvido_por_id_no_db(self, _mock_desc):
        cotacao = {
            "tipo_de_contrato": "representacao_comercial",
            "fee_ag": 0,
            "parceiro_percentual": 10,
        }
        data = {
            "plataforma": "Serasa",
            "id_objetivo_kpi": 99,
            "valor_unitario_negociado": 30,
            "volume_contratado": 100000,
        }
        out = db.calcular_breakdown_linha_cotacao(cotacao, data)
        self.assertEqual(out["representacao_comercial"], True)
        self.assertEqual(out["volume_contratado"], 100000)


if __name__ == "__main__":
    unittest.main()