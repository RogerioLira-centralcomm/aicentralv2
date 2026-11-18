import unittest
from unittest import mock

from aicentralv2.cotacoes_routes import _validar_precondicoes_aprovacao_cotacao


class CotacaoAprovacaoDadosTest(unittest.TestCase):
    @mock.patch('aicentralv2.cotacoes_routes.db.listar_itens_especificos_cotacao')
    @mock.patch('aicentralv2.cotacoes_routes.db.obter_linhas_cotacao')
    def test_dados_exige_segmento_e_valor(self, mock_linhas, mock_itens):
        mock_linhas.return_value = []
        mock_itens.return_value = []
        with self.assertRaises(ValueError) as ctx:
            _validar_precondicoes_aprovacao_cotacao(
                1, {'tipo_comercial': 'dados', 'valor_total_proposta': 100}
            )
        self.assertIn('segmento', str(ctx.exception).lower())

        mock_itens.return_value = [{'id': 1}]
        with self.assertRaises(ValueError) as ctx:
            _validar_precondicoes_aprovacao_cotacao(
                1, {'tipo_comercial': 'dados', 'valor_total_proposta': 0}
            )
        self.assertIn('valor', str(ctx.exception).lower())

        mock_itens.return_value = [{'id': 1}]
        _validar_precondicoes_aprovacao_cotacao(
            1, {'tipo_comercial': 'dados', 'valor_total_proposta': 20000}
        )
        mock_linhas.assert_not_called()

    @mock.patch('aicentralv2.cotacoes_routes.db.listar_itens_especificos_cotacao')
    @mock.patch('aicentralv2.cotacoes_routes.db.obter_linhas_cotacao')
    def test_midia_ainda_exige_linha_com_valor(self, mock_linhas, mock_itens):
        mock_linhas.return_value = []
        with self.assertRaises(ValueError) as ctx:
            _validar_precondicoes_aprovacao_cotacao(
                2, {'tipo_comercial': 'midia', 'valor_total_proposta': 1000}
            )
        self.assertIn('item de proposta', str(ctx.exception).lower())
        mock_itens.assert_not_called()

        mock_linhas.return_value = [
            {'investimento_bruto': 500, 'is_subtotal': False, 'is_header': False}
        ]
        _validar_precondicoes_aprovacao_cotacao(
            2, {'tipo_comercial': 'midia', 'valor_total_proposta': 1000}
        )


if __name__ == '__main__':
    unittest.main()