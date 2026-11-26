"""Período da campanha deve herdar do PI quando não informado (cotação ou formulário)."""

import unittest
from datetime import date
from unittest.mock import patch

from aicentralv2.db import (
    _montar_dados_campanha_pi_de_item_cotacao,
    preencher_periodo_campanha_de_pi,
)


class PreencherPeriodoCampanhaDePiTest(unittest.TestCase):
    def test_preenche_inicio_e_fim_do_pi(self):
        data = {"nome_campanha": "Teste"}
        pi = {"periodo_inicio": date(2026, 11, 1), "periodo_fim": date(2026, 11, 30)}
        preencher_periodo_campanha_de_pi(data, pi)
        self.assertEqual(data["periodo_inicio"], date(2026, 11, 1))
        self.assertEqual(data["periodo_fim"], date(2026, 11, 30))
        self.assertEqual(data["mes_ref"], date(2026, 11, 1))
        self.assertTrue(data.get("mes_ref_comp"))

    def test_nao_sobrescreve_datas_informadas(self):
        data = {"periodo_inicio": "2026-12-01", "periodo_fim": "2026-12-15"}
        pi = {"periodo_inicio": date(2026, 11, 1), "periodo_fim": date(2026, 11, 30)}
        preencher_periodo_campanha_de_pi(data, pi)
        self.assertEqual(data["periodo_inicio"], "2026-12-01")
        self.assertEqual(data["periodo_fim"], "2026-12-15")


class MontarCampanhaDeCotacaoPeriodoTest(unittest.TestCase):
    @patch("aicentralv2.db.obter_id_plataforma_por_nome", return_value=1)
    @patch("aicentralv2.db.obter_id_objetivo_campanha_por_kpi", return_value=None)
    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    @patch("aicentralv2.db.consolidar_composicao_financeira_campanha")
    def test_sem_datas_na_linha_usa_periodo_do_pi(
        self, _consolidar, obter_pi, _kpi, _plat
    ):
        obter_pi.return_value = {
            "periodo_inicio": date(2026, 6, 1),
            "periodo_fim": date(2026, 6, 30),
        }
        cotacao = {
            "id": 10,
            "client_id": 1,
            "nome_campanha": "Camp",
            "periodo_inicio": date(2026, 3, 1),
            "periodo_fim": date(2026, 3, 31),
        }
        linha = {
            "id": 1,
            "plataforma": "Meta Ads",
            "investimento_liquido": "1000",
            "volume_contratado": 100,
        }
        dados = _montar_dados_campanha_pi_de_item_cotacao(
            linha,
            99,
            cotacao,
            plataforma_key="plataforma",
            kpi_key="objetivo_kpi",
            nome_fallback="Camp",
        )
        self.assertIsNotNone(dados)
        self.assertEqual(dados["periodo_inicio"], date(2026, 6, 1))
        self.assertEqual(dados["periodo_fim"], date(2026, 6, 30))

    @patch("aicentralv2.db.obter_id_plataforma_por_nome", return_value=1)
    @patch("aicentralv2.db.obter_id_objetivo_campanha_por_kpi", return_value=None)
    @patch("aicentralv2.db.obter_cadu_pi_por_id", return_value=None)
    @patch("aicentralv2.db.consolidar_composicao_financeira_campanha")
    def test_linha_com_datas_proprias_preserva(
        self, _consolidar, _obter_pi, _kpi, _plat
    ):
        cotacao = {"id": 10, "client_id": 1, "nome_campanha": "Camp"}
        linha = {
            "id": 1,
            "plataforma": "Meta Ads",
            "investimento_liquido": "1000",
            "volume_contratado": 100,
            "data_inicio": "2026-08-01",
            "data_fim": "2026-08-20",
        }
        dados = _montar_dados_campanha_pi_de_item_cotacao(
            linha,
            99,
            cotacao,
            plataforma_key="plataforma",
            kpi_key="objetivo_kpi",
            nome_fallback="Camp",
        )
        self.assertEqual(dados["periodo_inicio"], date(2026, 8, 1))
        self.assertEqual(dados["periodo_fim"], date(2026, 8, 20))


if __name__ == "__main__":
    unittest.main()