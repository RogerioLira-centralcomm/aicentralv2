import unittest
from unittest import mock

from aicentralv2.cotacao_tipos import campos_item_tipo_comercial
from aicentralv2.contrato_tipos import categoria_plataforma_eh_dados
from aicentralv2.representacao_comercial.parceiros import (
    TRILHA_LOGAN,
    TRILHA_SERASA,
    resolver_trilha_parceiro,
    validar_plataforma_cotacao_dados,
    validar_plataforma_dados_valor,
)


class WorkspaceDadosPlataformaTest(unittest.TestCase):
    def test_campos_item_dados_plataforma_e_vigencia(self):
        permitidos = set(campos_item_tipo_comercial("dados"))
        self.assertEqual(
            permitidos,
            {"plataforma_campanha", "data_inicio", "data_fim"},
        )
        self.assertNotIn("fonte", permitidos)
        self.assertNotIn("periodo_uso", permitidos)

    def test_resolver_trilha_pelo_nome_da_plataforma(self):
        self.assertEqual(TRILHA_SERASA, resolver_trilha_parceiro(None, "Serasa"))
        self.assertEqual(TRILHA_LOGAN, resolver_trilha_parceiro(None, "Logan DOOH"))

    @mock.patch("aicentralv2.db.listar_plataformas_dados_ativas")
    def test_validar_plataforma_cotacao_dados(self, mock_listar):
        mock_listar.return_value = [
            {"descricao": "Serasa", "categoria": "Dados"},
            {"descricao": "Logan", "categoria": "Dados"},
        ]
        validar_plataforma_cotacao_dados("dados", None, exigir=False)
        validar_plataforma_cotacao_dados("midia", None)
        validar_plataforma_dados_valor("Serasa")
        with self.assertRaises(ValueError):
            validar_plataforma_dados_valor(None)
        with self.assertRaises(ValueError):
            validar_plataforma_cotacao_dados("dados", "Meta", exigir=True)

    def test_categoria_dados_canonica(self):
        self.assertTrue(categoria_plataforma_eh_dados("Dados"))
        self.assertFalse(categoria_plataforma_eh_dados("Social"))


class WorkspaceDadosItemMetadataTest(unittest.TestCase):
    def test_salvar_item_dados_exige_plataforma_e_datas(self):
        from aicentralv2 import db

        with mock.patch.object(db, "get_db") as mock_get_db:
            mock_conn = mock.MagicMock()
            mock_cur = mock.MagicMock()
            mock_get_db.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.side_effect = [
                {"tipo_comercial": "dados"},
            ]
            with self.assertRaises(ValueError):
                db.salvar_item_especifico_cotacao(
                    1,
                    {
                        "titulo": "Pacote teste",
                        "quantidade": 1,
                        "valor_unitario": 10,
                        "metadata": {},
                    },
                )


if __name__ == "__main__":
    unittest.main()