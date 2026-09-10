"""Testes do gate, snapshot e handoff financeiro do PI."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aicentralv2.pi_fechamento_service import (
    HandoffBloqueadoError,
    PiFechamentoService,
    classificar_zona,
    calcular_zonas,
)


class FakeFechamentoRepo:
    def __init__(self):
        self.status = {}
        self.resultados = []
        self.campanhas = []
        self.finalizado = False

    def obter_status(self, id_pi):
        codigo = self.status.get(id_pi)
        return {"id_pi": id_pi, "status_financeiro": codigo} if codigo else None

    def listar_status(self, ids_pi):
        return {key: self.status[key] for key in ids_pi if key in self.status}

    def upsert_status(self, id_pi, status, autor_id=None):
        self.status[id_pi] = status

    def proxima_versao(self, id_pi):
        return 1

    def obter_resultado(self, id_pi, versao=None):
        return None

    def listar_resultados_lote(self, ids_pi):
        return {}

    def listar_campanhas(self, id_pi, versao):
        return []

    def gravar_resultado(self, payload):
        self.resultados.append(payload)
        return 1

    def gravar_campanhas(self, rows):
        self.campanhas.extend(rows)

    def finalizar_handoff(self, id_pi):
        self.finalizado = True
        return 2


class FakeOperacao:
    def __init__(self, checklist_ok=True, drive=True, campanhas_ativas=False):
        self.repository = MagicMock()
        self.pi = {
            "id_pi": 10,
            "id_sub_status_pi": 3,
            "codigo_pi_cc": "PI-10",
            "cliente_nome": "Cliente",
            "valor_liquido": 1000,
            "valor_bruto": 1200,
            "val_margem_cc": 200,
            "googled_pi_princ": "https://drive.example/pi" if drive else "",
            "observacoes_operacao": "Fechamento ok",
            "objetivo_contratado_pi": 1000,
            "custo_base_unitario": 10,
            "desvio_aceitavel_pct": 5,
            "resp_comercial_email": "exec@example.com",
            "resp_comercial_nome": "Ana",
        }
        self.campanhas = [
            {
                "id_campanha": 30,
                "nome_campanha": "Display",
                "plataforma_nome": "Meta",
                "totalizador_gasto": "R$ 80,00",
                "custo_midia_orcado": "R$ 100,00",
                "obj_contratados": "1000",
                "totalizador_atingido": "900",
                "status_descricao": "Ativa" if campanhas_ativas else "Finalizada",
            }
        ]
        self.checklist = [
            {
                "codigo": "enviar_relatorios_faturamento",
                "concluido": checklist_ok,
                "fase": "fechamento",
            }
        ]

    def estado_completo(self, id_pi):
        return {
            "pi": dict(self.pi),
            "campanhas": [dict(item) for item in self.campanhas],
            "checklist": [dict(item) for item in self.checklist],
            "checklist_operacional": {"itens_pi": [dict(item) for item in self.checklist]},
            "saude": {"status": "saudavel"},
        }


class FechamentoServiceTest(unittest.TestCase):
    def test_classifica_zonas_pelo_gasto(self):
        zonas = {"limite_inf": 80, "orcado": 100, "limite_sup": 110, "ruptura": 150}
        self.assertEqual(classificar_zona(70, zonas), 1)
        self.assertEqual(classificar_zona(90, zonas), 2)
        self.assertEqual(classificar_zona(105, zonas), 3)
        self.assertEqual(classificar_zona(140, zonas), 4)
        self.assertEqual(classificar_zona(200, zonas), 5)

    def test_calcular_zonas_respeita_desvio(self):
        calc = calcular_zonas(
            {"objetivo_contratado_pi": 1000, "custo_base_unitario": 10, "meta_baseada_em_cpm": False},
            10,
            ruptura_mult=5,
        )
        self.assertEqual(calc["midia_orcado"], 10000.0)
        self.assertEqual(calc["zonas"]["limite_inf"], 9000.0)
        self.assertEqual(calc["zonas"]["limite_sup"], 11000.0)

    def test_preview_bloqueia_sem_relatorios(self):
        service = PiFechamentoService(
            repository=FakeFechamentoRepo(),
            operacao=FakeOperacao(checklist_ok=False),
        )
        preview = service.preview(10)
        self.assertFalse(preview["gate_ok"])
        self.assertEqual(preview["pendencias"][0]["codigo"], "enviar_relatorios_faturamento")

    def test_enviar_financeiro_grava_snapshot_e_status(self):
        repo = FakeFechamentoRepo()
        operacao = FakeOperacao()
        service = PiFechamentoService(
            repository=repo,
            operacao=operacao,
            brevo_service=MagicMock(),
            renderer=lambda *args, **kwargs: "<html></html>",
        )
        service.notificar_financeiro_interno = MagicMock(return_value={"success": True, "enviados": []})
        with patch("aicentralv2.pi_operacao_service.sincronizar_operacao_pi"):
            result = service.enviar_financeiro(10, autor_id=99)
        self.assertTrue(result["success"])
        self.assertTrue(repo.finalizado)
        self.assertEqual(repo.status[10], "aguardando_comprovacao")
        self.assertEqual(repo.resultados[0]["id_pi"], 10)
        self.assertEqual(len(repo.campanhas), 1)
        self.assertEqual(repo.campanhas[0]["nome_campanha"], "Display")

    def test_validar_handoff_levanta_pendencias(self):
        service = PiFechamentoService(
            repository=FakeFechamentoRepo(),
            operacao=FakeOperacao(drive=False),
        )
        with self.assertRaises(HandoffBloqueadoError) as ctx:
            service.validar_handoff(10)
        self.assertTrue(any(item["codigo"] == "pasta_drive" for item in ctx.exception.pendencias))


class FechamentoUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.templates = root / "aicentralv2/templates"
        cls.routes = (root / "aicentralv2/pi_financeiro_routes.py").read_text()
        cls.init = (root / "aicentralv2/__init__.py").read_text()

    def test_shell_reuses_pi_op_layout_and_sidebar(self):
        shell = (self.templates / "pi_operacao/_fechamento_shell.html").read_text()
        self.assertIn("pi-op-header", shell)
        self.assertIn("pi-op-layout", shell)
        self.assertIn("pi_operacao/_sidebar.html", shell)
        self.assertIn("pi-op-btn--accent", shell)
        self.assertIn("Enviar ao Financeiro", shell)

    def test_pages_and_blueprint_are_wired(self):
        self.assertTrue((self.templates / "cadu_pi_fechamento.html").exists())
        self.assertTrue((self.templates / "cadu_pi_financeiro.html").exists())
        self.assertTrue((self.templates / "emails/internos/pi_operacao/handoff_financeiro.html").exists())
        self.assertIn('Blueprint("pi_financeiro"', self.routes)
        self.assertIn("/cadu_pi/<int:id_pi>/fechamento", self.routes)
        self.assertIn("/cadu_pi/<int:id_pi>/financeiro", self.routes)
        self.assertIn("/cadu_pi/<int:id_pi>/financeiro/documento/<tipo>.pdf", self.routes)
        self.assertIn("pi_financeiro_bp", self.init)
        main = (self.templates / "pi_operacao/_fechamento_main.html").read_text()
        self.assertIn("documento_pdf", main)
        self.assertIn("Gerar PDFs", main)


if __name__ == "__main__":
    unittest.main()
