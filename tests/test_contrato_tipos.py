import unittest

from aicentralv2.contrato_tipos import (
    normalizar_tipo_de_contrato,
    rotulo_tipo_de_contrato,
)


class ContratoTiposTest(unittest.TestCase):
    def test_padrao_e_operacao_propria(self):
        self.assertEqual("operacao_propria", normalizar_tipo_de_contrato(None))
        self.assertEqual("Operação própria", rotulo_tipo_de_contrato(""))

    def test_slugs_canonicos(self):
        self.assertEqual(
            "representacao_comercial",
            normalizar_tipo_de_contrato(" Representação comercial "),
        )
        self.assertEqual(
            "operacao_propria",
            normalizar_tipo_de_contrato("operacao-propria"),
        )

    def test_tipo_desconhecido_e_rejeitado(self):
        with self.assertRaisesRegex(ValueError, "Tipo de contrato inválido"):
            normalizar_tipo_de_contrato("outro")


if __name__ == "__main__":
    unittest.main()
