import unittest

from aicentralv2.email_area_cc import (
    CC_FINANCEIRO,
    CC_OPERACAO,
    EMAIL_APOLO,
    EMAIL_LUIZ,
    cc_comercial,
    extrair_cc_emails_solicitados,
    normalizar_cc,
    resolver_cc_envio,
)


class EmailAreaCcTest(unittest.TestCase):
    def test_cc_operacao_lista_fixa(self):
        self.assertEqual(len(CC_OPERACAO), 4)
        self.assertIn("pedro@centralcomm.media", CC_OPERACAO)

    def test_cc_financeiro_lista_fixa(self):
        self.assertEqual(
            CC_FINANCEIRO,
            [
                "financeiro@centralcomm.media",
                "pedro@centralcomm.media",
                "max@centralcomm.media",
            ],
        )

    def test_cc_comercial_inclui_executivo_apolo_luiz(self):
        lista = cc_comercial("vendedor@cliente.com")
        self.assertEqual(
            lista,
            ["vendedor@cliente.com", EMAIL_APOLO, EMAIL_LUIZ],
        )

    def test_cc_comercial_sem_executivo(self):
        lista = cc_comercial(None)
        self.assertEqual(lista, [EMAIL_APOLO, EMAIL_LUIZ])

    def test_normalizar_cc_exclui_to_e_cc(self):
        lista = normalizar_cc(
            cc_comercial("vendedor@cliente.com"),
            excluir_to="vendedor@cliente.com",
        )
        self.assertEqual(lista, [EMAIL_APOLO, EMAIL_LUIZ])

        lista_interno = normalizar_cc(
            cc_comercial("vendedor@cliente.com"),
            excluir_to="apolo@centralcomm.media",
            excluir_cc="luiz@centralcomm.media",
        )
        self.assertEqual(lista_interno, ["vendedor@cliente.com"])

    def test_resolver_cc_envio_usa_padrao_quando_ausente(self):
        self.assertEqual(
            resolver_cc_envio(CC_OPERACAO, None, excluir_to="cliente@x.com"),
            CC_OPERACAO,
        )

    def test_resolver_cc_envio_respeita_lista_vazia(self):
        self.assertEqual(
            resolver_cc_envio(CC_OPERACAO, [], excluir_to="cliente@x.com"),
            [],
        )

    def test_extrair_cc_emails_solicitados(self):
        self.assertIsNone(extrair_cc_emails_solicitados({}))
        self.assertEqual(
            extrair_cc_emails_solicitados({"cc_emails": ["A@X.COM"]}),
            ["a@x.com"],
        )


if __name__ == "__main__":
    unittest.main()
