from unittest import TestCase
from unittest.mock import MagicMock, patch

from aicentralv2 import leads_v3_clientes as cl
from aicentralv2.leads_v3_prospeccao import ProspeccaoError
from tests.test_leads_v3_routes import _client


class ClienteParaLeadTest(TestCase):
    def test_pi_em_andamento_bloqueia_antes_de_mexer_em_algo(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id_cliente": 1, "nome_fantasia": "Gerdau", "razao_social": "", "cnpj": "", "status": True, "vendas_central_comm": 7}
        cursor.fetchall.return_value = [{"id_pi": 9, "codigo_pi_cc": "PI-9", "titulo_pi": "X", "situacao": "Em andamento"}]
        with self.assertRaises(ProspeccaoError) as ctx:
            cl.cliente_para_lead(cursor, 1, usuario_id=1)
        self.assertIn("PI-9", str(ctx.exception))
        self.assertFalse(any(str(c.args[0]).strip().startswith(("UPDATE", "INSERT")) for c in cursor.execute.call_args_list))

    def test_cotacao_fechada_nao_expira(self):
        self.assertEqual({cl._slug_cotacao(s) for s in ("Aprovada", "Rejeitada", "Expirada", "perdida")}, cl.COTACAO_FECHADA)
        self.assertNotIn(cl._slug_cotacao("Em Acompanhamento"), cl.COTACAO_FECHADA)

    def test_reativar_exige_lead_vindo_de_cliente(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": 3, "cliente_origem_id": None, "convertido_cliente_id": None}
        with self.assertRaises(ProspeccaoError):
            cl.reativar_cliente(cursor, 3, usuario_id=1)

    def test_rotas_respondem_erro_de_negocio_como_400(self):
        from tests.test_leads_v3_routes import FakeConn
        from aicentralv2 import leads_v3_routes as routes

        with patch.object(routes.db, "get_db", return_value=FakeConn([])), \
                patch.object(routes.clientes, "cliente_para_lead", side_effect=ProspeccaoError("O cliente tem 1 PI em andamento")):
            resp = _client().post("/leads-v3/api/clientes/5/para-lead", json={"motivo": "x"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PI", resp.get_json()["error"])


class ListaCrmTest(TestCase):
    def test_cliente_inativo_que_voltou_para_lead_sai_da_lista(self):
        from aicentralv2 import crm_v3_repository as repo

        cur = MagicMock()
        cur.fetchall.return_value = [{"cliente_origem_id": 2}]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        fake_db = MagicMock()
        fake_db.get_db.return_value = conn
        rows = [{"id_cliente": 1, "status": True}, {"id_cliente": 2, "status": False}, {"id_cliente": 3, "status": False}]
        with patch.object(repo, "_db", return_value=fake_db):
            store = repo.CrmV3Repository.__new__(repo.CrmV3Repository)
            self.assertEqual([r["id_cliente"] for r in store._sem_clientes_que_voltaram_para_lead(rows)], [1, 3])
