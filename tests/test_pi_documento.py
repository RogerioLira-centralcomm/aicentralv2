"""PDFs de fechamento gerados a partir do snapshot."""

import unittest
from unittest.mock import MagicMock

from aicentralv2.pi_documento_service import (
    REPORTLAB_AVAILABLE,
    DocumentoIndisponivelError,
    PiDocumentoService,
)


def _snapshot(**overrides):
    data = {
        "persistido": True,
        "id_pi": 10,
        "codigo_pi": "PI-10",
        "cliente_nome": "Cliente Teste",
        "agencia_nome": "Agência Norte",
        "gasto_midia_realizado": 80,
        "gasto_midia_previsto": 100,
        "pct_gasto_midia": 80,
        "pct_objetivo": 90,
        "valor_bruto": 1200,
        "valor_liquido": 1000,
        "margem_cc": 200,
        "tech_fee": 50,
        "com_vendas": 40,
        "pl_incentivos": 120,
        "impostos": 80,
        "margem_liquida_calculada": 920,
        "zona_lucratividade": 2,
        "zona_label": "Lucrativa",
        "saude_pi": "saudavel",
        "saude_label": "Saudável",
        "status_financeiro_label": "Aguardando comprovação",
        "observacoes_operacao": "Fechamento ok",
        "drive": {"principal": "https://drive.example/pi"},
        "pendencias": [],
        "campanhas": [
            {
                "id_campanha": 30,
                "nome_campanha": "Display",
                "plataforma": "Meta",
                "gasto_realizado": 80,
                "pct_gasto": 80,
                "pct_objetivo": 90,
                "periodo_inicio": "2026-09-01",
                "periodo_fim": "2026-09-30",
            }
        ],
    }
    data.update(overrides)
    return data


class FakeFechamento:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def resultado(self, id_pi):
        return dict(self._snapshot)


class PiDocumentoServiceTest(unittest.TestCase):
    def _service(self, snapshot=None):
        return PiDocumentoService(fechamento=FakeFechamento(snapshot or _snapshot()))

    @unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab não instalado")
    def test_gera_os_quatro_tipos_com_cabecalho_pdf(self):
        service = self._service()
        for tipo, variante in (
            ("fechamento", "cliente"),
            ("fechamento", "agencia"),
            ("comprovacao", "cliente"),
            ("bonificacao", "agencia"),
            ("passagem", "interno"),
        ):
            pdf, nome = service.gerar(10, tipo, variante=variante)
            self.assertTrue(pdf.startswith(b"%PDF"), tipo)
            self.assertIn(tipo, nome)
            self.assertTrue(nome.endswith(".pdf"))

    @unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab não instalado")
    def test_nao_usa_campanhas_fora_do_snapshot(self):
        snapshot = _snapshot(
            campanhas=[{"id_campanha": 99, "nome_campanha": "Snapshot Only", "plataforma": "DV360", "gasto_realizado": 10, "pct_gasto": 10, "pct_objetivo": 5}]
        )
        live = MagicMock()
        live.listar_campanhas.return_value = [{"nome_campanha": "Campanha ao vivo"}]
        service = self._service(snapshot)
        pdf, _ = service.gerar(10, "comprovacao")
        self.assertTrue(pdf.startswith(b"%PDF"))
        live.listar_campanhas.assert_not_called()

    def test_bonificacao_exige_incentivo_ou_agencia(self):
        service = self._service(_snapshot(agencia_nome="", pl_incentivos=0))
        with self.assertRaises(DocumentoIndisponivelError):
            service.gerar(10, "bonificacao", variante="agencia")

    def test_fechamento_exige_snapshot_persistido(self):
        service = self._service(_snapshot(persistido=False))
        with self.assertRaises(DocumentoIndisponivelError):
            service.gerar(10, "fechamento", variante="cliente")

    @unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab não instalado")
    def test_passagem_pode_usar_preview(self):
        service = self._service(_snapshot(persistido=False))
        pdf, nome = service.gerar(10, "passagem", variante="interno")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("passagem", nome)

    def test_listar_esconde_bonificacao_sem_incentivo_e_snapshot(self):
        docs = self._service(_snapshot(persistido=False, pl_incentivos=0, agencia_nome="")).listar(
            _snapshot(persistido=False, pl_incentivos=0, agencia_nome="")
        )
        self.assertEqual([item["tipo"] for item in docs], ["passagem"])
        docs_pos = self._service().listar(_snapshot())
        tipos = {item["tipo"] for item in docs_pos}
        self.assertIn("fechamento", tipos)
        self.assertIn("bonificacao", tipos)


if __name__ == "__main__":
    unittest.main()
