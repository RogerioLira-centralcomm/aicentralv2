"""Testes da regra responsavel_setor (1 ativo = True; 2+ = False)."""

import unittest
from unittest import mock

from aicentralv2 import db


class ResponsavelSetorSyncTest(unittest.TestCase):
    def _mock_conn(self, fetch_sequences, commit_side=None):
        conn = mock.MagicMock()
        cursor = mock.MagicMock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cursor)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)
        cursor.fetchall.side_effect = fetch_sequences
        return conn, cursor

    @mock.patch('aicentralv2.db.get_db')
    def test_um_contato_ativo_marca_true(self, get_db_mock):
        conn, cursor = self._mock_conn([[{'id_contato_cliente': 7}]])
        get_db_mock.return_value = conn

        db.sincronizar_responsavel_setor_padrao(100)

        updates = [c.args for c in cursor.execute.call_args_list]
        self.assertTrue(any('id_contato_cliente = %s' in str(u) for u in updates))
        conn.commit.assert_called_once()

    @mock.patch('aicentralv2.db.get_db')
    def test_dois_contatos_ativos_marca_false(self, get_db_mock):
        conn, cursor = self._mock_conn([[{'id_contato_cliente': 1}, {'id_contato_cliente': 2}]])
        get_db_mock.return_value = conn

        db.sincronizar_responsavel_setor_padrao(100)

        sql_calls = ' '.join(str(c.args[0]) for c in cursor.execute.call_args_list)
        self.assertIn('responsavel_setor = FALSE', sql_calls)
        conn.commit.assert_called_once()

    @mock.patch('aicentralv2.db.get_db')
    def test_sem_contatos_nao_atualiza(self, get_db_mock):
        conn, cursor = self._mock_conn([[]])
        get_db_mock.return_value = conn

        db.sincronizar_responsavel_setor_padrao(100)

        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()


class ResolverContatoResponsavelSetorTest(unittest.TestCase):
    @mock.patch('aicentralv2.db.obter_contatos_para_operacao')
    def test_retorna_id_quando_responsavel_marcado(self, obter_mock):
        obter_mock.return_value = [
            {
                'id_contato_cliente': 10,
                'setor': 'Operações',
                'responsavel_setor': True,
            },
        ]
        self.assertEqual(
            db.resolver_contato_responsavel_setor(1, 'Operações', somente_responsavel_setor=True),
            10,
        )

    @mock.patch('aicentralv2.db.obter_contatos_para_operacao')
    def test_somente_responsavel_sem_flag_retorna_none(self, obter_mock):
        obter_mock.return_value = [
            {
                'id_contato_cliente': 11,
                'setor': 'Operações',
                'responsavel_setor': False,
            },
        ]
        self.assertIsNone(
            db.resolver_contato_responsavel_setor(1, 'Operações', somente_responsavel_setor=True)
        )

    @mock.patch('aicentralv2.db.obter_contatos_para_operacao')
    def test_fallback_unico_contato_sem_flag_quando_nao_estrito(self, obter_mock):
        obter_mock.return_value = [
            {
                'id_contato_cliente': 12,
                'setor': 'Financeiro',
                'responsavel_setor': False,
            },
        ]
        self.assertEqual(db.resolver_contato_responsavel_setor(1, 'Financeiro'), 12)


if __name__ == '__main__':
    unittest.main()
