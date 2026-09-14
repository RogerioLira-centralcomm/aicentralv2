"""Testes da fórmula unificada Fee_ag / FeePR."""

import unittest
from unittest.mock import patch

from aicentralv2 import db


class TestPrecoUnitarioFee(unittest.TestCase):
    @patch('aicentralv2.db.obter_tech_fee_fracao_por_nome_plataforma', return_value=(0.1, 'Plat', 'descricao_exata'))
    @patch('aicentralv2.db.obter_margem_cc_fracao_e_bruto', return_value=(0.2, '20'))
    @patch('aicentralv2.db.obter_com_vendas_fracao_e_bruto', return_value=(0.05, '5'))
    @patch('aicentralv2.db._cotacao_tem_agencia_para_inc', return_value=False)
    @patch('aicentralv2.db._cotacao_tem_parceiro_para_parc', return_value=False)
    def test_sem_agencia_sem_parceiro(self, *_mocks):
        out = db.calcular_preco_unitario_teste_calculo(
            valor_unitario_tabela=100,
            nome_plataforma='Test',
            cliente_id=1,
            id_resp_comercial=1,
            volume_contratado=1000,
            imposto_percentual_externo=17,
        )
        self.assertTrue(out['success'])
        opex = 100 / 0.9
        expected = opex / (1 - 0.2 - 0.05 - 0.17)
        self.assertAlmostEqual(out['preco_unit'], round(expected, 6))
        self.assertEqual(out['fee_ag'], 0.0)
        self.assertEqual(out['fee_pr'], 0.0)

    @patch('aicentralv2.db.obter_tech_fee_fracao_por_nome_plataforma', return_value=(0.0, 'Plat', 'descricao_exata'))
    @patch('aicentralv2.db.obter_margem_cc_fracao_e_bruto', return_value=(0.1, '10'))
    @patch('aicentralv2.db.obter_com_vendas_fracao_e_bruto', return_value=(0.0, '0'))
    @patch('aicentralv2.db._cotacao_tem_agencia_para_inc', return_value=True)
    @patch('aicentralv2.db.cliente_possui_incentivo', return_value=False)
    @patch('aicentralv2.db.obter_incentivo_fracao_por_cliente_volume', return_value=0.0)
    @patch('aicentralv2.db._cotacao_tem_parceiro_para_parc', return_value=True)
    def test_com_fee_ag_e_fee_pr(self, *_mocks):
        out = db.calcular_preco_unitario_teste_calculo(
            valor_unitario_tabela=100,
            nome_plataforma='Test',
            cliente_id=1,
            id_resp_comercial=1,
            volume_contratado=1000,
            imposto_percentual_externo=10,
            agencia_id=10,
            parceiro_id=20,
            fee_ag_percentual=15,
            fee_pr_percentual=10,
        )
        self.assertTrue(out['success'])
        opex = 100.0
        soma = 0.1 + 0.0 + 0.0 + 0.1 + 0.10  # mcc + com + inc + imp + fee_pr
        preco_base = opex / (1 - soma)
        expected = preco_base / 0.85
        self.assertAlmostEqual(out['preco_unit'], round(expected, 6))
        self.assertAlmostEqual(out['fee_ag'], 0.15, places=4)
        self.assertAlmostEqual(out['fee_pr'], 0.10, places=4)

    def test_derivar_investimento_de_preco(self):
        inv = db.derivar_investimento_de_preco(10, 11.764706, 0.15, 0.10)
        self.assertAlmostEqual(inv['investimento_bruto'], 117.65, places=2)
        self.assertAlmostEqual(inv['investimento_liquido'], 100.0, places=2)
        self.assertAlmostEqual(inv['comissao_agencia'], 17.65, places=2)

    def test_soma_margens_invalida(self):
        with patch('aicentralv2.db.obter_tech_fee_fracao_por_nome_plataforma', return_value=(0.0, 'P', 'x')):
            with patch('aicentralv2.db.obter_margem_cc_fracao_e_bruto', return_value=(0.5, '50')):
                with patch('aicentralv2.db.obter_com_vendas_fracao_e_bruto', return_value=(0.5, '50')):
                    with patch('aicentralv2.db._cotacao_tem_agencia_para_inc', return_value=False):
                        with patch('aicentralv2.db._cotacao_tem_parceiro_para_parc', return_value=False):
                            out = db.calcular_preco_unitario_teste_calculo(
                                valor_unitario_tabela=100,
                                nome_plataforma='Test',
                                cliente_id=1,
                                id_resp_comercial=1,
                                volume_contratado=0,
                                imposto_percentual_externo=10,
                            )
        self.assertFalse(out['success'])


if __name__ == '__main__':
    unittest.main()
