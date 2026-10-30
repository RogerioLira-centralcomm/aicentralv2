import unittest

from aicentralv2.contrato_tipos import (
    filtrar_plataformas_por_tipo_contrato,
    normalizar_tipo_de_contrato,
    plataforma_permitida_para_tipo_contrato,
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

    def test_filtro_plataformas_por_tipo_contrato(self):
        plataformas = [
            {"descricao": "Meta", "categoria": "Social"},
            {"descricao": "Serasa", "categoria": "Dados"},
            {"descricao": "Outro", "categoria": "Sem categoria"},
        ]
        op = filtrar_plataformas_por_tipo_contrato(plataformas, "operacao_propria")
        self.assertEqual(["Meta", "Outro"], [p["descricao"] for p in op])
        rep = filtrar_plataformas_por_tipo_contrato(plataformas, "representacao_comercial")
        self.assertEqual(["Serasa"], [p["descricao"] for p in rep])
        self.assertTrue(plataforma_permitida_para_tipo_contrato("Dados", "representacao_comercial"))
        self.assertFalse(plataforma_permitida_para_tipo_contrato("Dados", "operacao_propria"))


if __name__ == "__main__":
    unittest.main()
