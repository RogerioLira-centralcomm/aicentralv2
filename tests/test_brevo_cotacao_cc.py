import unittest
from unittest.mock import MagicMock, patch

from aicentralv2.services import brevo_service


class BrevoCotacaoCcTest(unittest.TestCase):
    @patch.object(brevo_service, "get_brevo_service")
    def test_enviar_cotacao_cliente_repassa_cc_comercial(self, get_service):
        service = MagicMock()
        get_service.return_value = service
        service.enviar_email_com_template.return_value = {"success": True}

        brevo_service.enviar_email_cotacao_enviada_cliente(
            to_email="cliente@empresa.com",
            to_name="Cliente",
            numero_cotacao="COT-1",
            nome_campanha="Campanha",
            valor_total="R$ 1.000,00",
            executivo_email="exec@centralcomm.media",
        )

        kwargs = service.enviar_email_com_template.call_args.kwargs
        self.assertEqual(
            kwargs["cc_email"],
            [
                "exec@centralcomm.media",
                "apolo@centralcomm.media",
                "luiz@centralcomm.media",
            ],
        )

    @patch.object(brevo_service, "get_brevo_service")
    def test_override_cc_emails(self, get_service):
        service = MagicMock()
        get_service.return_value = service
        service.enviar_email_com_template.return_value = {"success": True}

        brevo_service.enviar_email_cotacao_enviada_cliente(
            to_email="cliente@empresa.com",
            to_name="Cliente",
            numero_cotacao="COT-1",
            nome_campanha="Campanha",
            valor_total="R$ 1.000,00",
            executivo_email="exec@centralcomm.media",
            cc_emails=["luiz@centralcomm.media"],
        )

        kwargs = service.enviar_email_com_template.call_args.kwargs
        self.assertEqual(kwargs["cc_email"], ["luiz@centralcomm.media"])


if __name__ == "__main__":
    unittest.main()
