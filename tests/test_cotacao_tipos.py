import unittest

from aicentralv2.cotacao_tipos import (
    destino_tipo_comercial,
    normalizar_tipo_comercial,
    rotulo_tipo_comercial,
    validar_status_tipo_comercial,
)


class CotacaoTiposTest(unittest.TestCase):
    def test_dados_legados_sao_midia(self):
        self.assertEqual("midia", normalizar_tipo_comercial(None))
        self.assertEqual("Mídia", rotulo_tipo_comercial(""))

    def test_tipos_validos_sao_canonicos(self):
        self.assertEqual(
            "formatos_interativos",
            normalizar_tipo_comercial("formatos-interativos"),
        )
        self.assertEqual("parceiros", normalizar_tipo_comercial(" Parceiros "))

    def test_tipo_desconhecido_e_rejeitado(self):
        with self.assertRaisesRegex(ValueError, "Tipo de cotação inválido"):
            normalizar_tipo_comercial("outro")

    def test_novos_tipos_ficam_em_rascunho(self):
        self.assertEqual(
            "dados", validar_status_tipo_comercial("dados", "Rascunho")
        )
        with self.assertRaisesRegex(ValueError, "deve permanecer como rascunho"):
            validar_status_tipo_comercial("dados", "Aprovada")

    def test_midia_preserva_fluxo_atual(self):
        self.assertEqual(
            "midia", validar_status_tipo_comercial("midia", "Aprovada")
        )

    def test_destino_da_continuidade_depende_do_tipo(self):
        self.assertEqual(
            ("cotacoes.cotacao_detalhes", "detalhes"),
            destino_tipo_comercial("midia"),
        )
        for tipo in ("parceiros", "formatos_interativos", "dados"):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    ("cotacoes.cotacao_editar", "editar"),
                    destino_tipo_comercial(tipo),
                )


if __name__ == "__main__":
    unittest.main()
