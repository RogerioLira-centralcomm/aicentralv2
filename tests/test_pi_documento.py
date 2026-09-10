"""PDFs de fechamento gerados a partir do snapshot."""

import unittest
from unittest.mock import MagicMock

from aicentralv2.pi_documento_service import (
    REPORTLAB_AVAILABLE,
    DocumentoIndisponivelError,
    PiDocumentoService,
    mensagem_padrao,
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
        "objetivo_contratado": 1000,
        "objetivo_atingido": 900,
        "contato_agencia": {
            "id": 7,
            "nome": "Maria Souza",
            "email": "maria@agencia.com",
        },
        "cartas": {},
        "campanhas": [
            {
                "id_campanha": 30,
                "nome_campanha": "Display",
                "plataforma": "Meta",
                "gasto_realizado": 80,
                "pct_gasto": 80,
                "obj_contratado": 1000,
                "obj_atingido": 900,
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
        self.brevo = MagicMock()
        self.brevo.enviar_email.return_value = {"success": True, "messageId": "msg-1"}
        self.repository = MagicMock()
        self.operacao = MagicMock()
        self.registrados = []

    def resultado(self, id_pi):
        return dict(self._snapshot)

    def registrar_documento(self, id_pi, tipo, dados, autor_id=None):
        self.registrados.append((tipo, dados, autor_id))
        return {tipo: dados}


class PiDocumentoServiceTest(unittest.TestCase):
    def _service(self, snapshot=None):
        return PiDocumentoService(fechamento=FakeFechamento(snapshot or _snapshot()))

    @unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab não instalado")
    def test_gera_os_quatro_tipos_com_cabecalho_pdf(self):
        service = self._service()
        for tipo, variante in (
            ("fechamento", "cliente"),
            ("fechamento", "agencia"),
            ("comprovacao", "agencia"),
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

    def test_listar_esconde_bonificacao_sem_incentivo(self):
        docs = self._service().listar(_snapshot(pl_incentivos=0, agencia_nome=""))
        self.assertEqual([item["tipo"] for item in docs], ["comprovacao"])
        docs_pos = self._service().listar(_snapshot())
        tipos = {item["tipo"] for item in docs_pos}
        self.assertEqual(tipos, {"comprovacao", "bonificacao"})

    def test_listar_endereca_agencia_e_preenche_mensagem(self):
        docs = self._service().listar(_snapshot())
        comprovacao = next(item for item in docs if item["tipo"] == "comprovacao")
        self.assertEqual(comprovacao["variante"], "agencia")
        self.assertEqual(comprovacao["destinatario"]["email"], "maria@agencia.com")
        self.assertIn("Maria", comprovacao["mensagem"])
        self.assertIn("900", comprovacao["mensagem"])
        self.assertIn("1.000", comprovacao["mensagem"])
        self.assertTrue(comprovacao["pode_enviar"])

    def test_mensagem_padrao_cita_contratado_e_entregue(self):
        texto = mensagem_padrao("comprovacao", _snapshot())
        self.assertIn("Aos cuidados de Maria Souza", texto)
        self.assertIn("entregaram 900 de 1.000 contratados", texto)

    def test_enviar_assinatura_anexa_pdf_ao_contato(self):
        fechamento = FakeFechamento(_snapshot())
        service = PiDocumentoService(fechamento=fechamento)
        if REPORTLAB_AVAILABLE:
            result = service.enviar_para_assinatura(10, "comprovacao", autor_id=99)
            self.assertTrue(result["enviado"])
            self.assertEqual(result["destinatario"]["email"], "maria@agencia.com")
            kwargs = fechamento.brevo.enviar_email.call_args.kwargs
            self.assertEqual(kwargs["to_email"], "maria@agencia.com")
            self.assertTrue(kwargs["attachments"])
            self.assertIn("assinatura", kwargs["subject"].lower())
            self.assertEqual(fechamento.registrados[0][0], "comprovacao")
            fechamento.repository.upsert_status.assert_called_once()
        else:
            with self.assertRaises(DocumentoIndisponivelError):
                service.enviar_para_assinatura(10, "comprovacao", autor_id=99)

    def test_enviar_assinatura_exige_contato(self):
        service = self._service(_snapshot(contato_agencia={}))
        with self.assertRaises(DocumentoIndisponivelError):
            service.enviar_para_assinatura(10, "comprovacao")


if __name__ == "__main__":
    unittest.main()
