"""Testes do payload da página pública de acompanhamento da campanha."""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from aicentralv2.campanha_acompanhamento_publico import montar_payload_acompanhamento_campanha


class FakeOperacaoService:
    def estado_campanha(self, id_pi, id_campanha):
        hoje = date.today()
        return {
            "pi": {
                "id_pi": id_pi,
                "codigo_pi_cc": "PI036826",
                "cliente_nome": "Cliente Teste",
                "id_resp_comercial": 99,
                "responsavel_comercial_nome": "Ana Comercial",
                "periodo_inicio": hoje - timedelta(days=5),
                "periodo_fim": hoje + timedelta(days=10),
                "googled_pi_princ": "https://drive.example/pi",
                "cotacao_id": None,
            },
            "campanha": {
                "id_campanha": id_campanha,
                "nome_campanha": "Display Principal",
                "link_dash": "https://lookerstudio.google.com/embed/reporting/x",
                "periodo_inicio": hoje - timedelta(days=5),
                "periodo_fim": hoje + timedelta(days=10),
                "objetivo_nome": "Alcance",
                "obj_contratados": "1000000",
                "plataforma_nome": "Google Ads",
                "updated_at": hoje,
            },
            "campanhas_relacionadas": [
                {
                    "id_campanha": id_campanha,
                    "nome": "Display Principal",
                    "plataforma": "Google Ads",
                    "atual": True,
                }
            ],
            "destinatarios": [
                {
                    "nome_completo": "Contato Cliente",
                    "email": "cliente@example.com",
                    "papel": "cliente_final",
                }
            ],
            "timeline": [
                {"etapa": "dados_validados", "concluida": True, "concluida_em": hoje - timedelta(days=4)},
                {"etapa": "campanha_iniciada", "concluida": True, "concluida_em": hoje - timedelta(days=1)},
            ],
            "resumo": {"ultima_atualizacao": hoje},
        }


class CampanhaAcompanhamentoPublicoTest(unittest.TestCase):
    @patch("aicentralv2.db.obter_campanha_pi_por_id")
    @patch("aicentralv2.db.obter_contato_por_id")
    def test_montar_payload_estrutura_template(self, contato_mock, campanha_mock):
        campanha_mock.return_value = {
            "id_campanha": 30,
            "id_pi": 10,
            "nome_campanha": "Display Principal",
        }
        contato_mock.return_value = {
            "nome_completo": "Ana Comercial",
            "email": "ana@centralcomm.media",
        }

        payload = montar_payload_acompanhamento_campanha(
            30,
            service=FakeOperacaoService(),
        )

        self.assertFalse(payload["demo"])
        self.assertEqual(payload["campanha"], "Display Principal")
        self.assertEqual(payload["pi"], "PI036826")
        self.assertIn("marcos", payload)
        self.assertEqual(len(payload["marcos"]), 8)
        self.assertIn("modulos", payload)
        self.assertEqual(
            payload["modulos"]["dashboard"]["url_embed"],
            "https://lookerstudio.google.com/embed/reporting/x",
        )
        pi_marco = next(m for m in payload["marcos"] if m["id"] == "pi")
        self.assertTrue(pi_marco["realizado"])
        self.assertEqual(payload["modulos"]["contatos"]["cliente"][0]["email"], "cliente@example.com")


if __name__ == "__main__":
    unittest.main()
