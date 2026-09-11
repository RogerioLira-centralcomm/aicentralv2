"""Pacing operacional de mídia do PI."""

import unittest
from datetime import date

from aicentralv2.campanha_pi_metrics import (
    calcular_pacing_midia,
    campanha_esta_encerrada,
)


class CampanhaPiPacingTest(unittest.TestCase):
    def test_pacing_ativo_usa_saldo_e_gasto_diario(self):
        pacing = calcular_pacing_midia(
            3000,
            1000,
            date(2026, 5, 1),
            date(2026, 5, 31),
            encerrada=False,
            hoje=date(2026, 5, 11),
        )
        self.assertEqual(pacing["modo"], "pacing")
        self.assertEqual(pacing["periodo_dias_decorridos"], 10)
        self.assertEqual(pacing["periodo_dias_restantes"], 20)
        self.assertEqual(pacing["pacing_atual_dia"], 100.0)
        self.assertEqual(pacing["pacing_previsto_dia"], 100.0)
        self.assertEqual(pacing["pct_gasto"], 33)
        self.assertEqual(pacing["resultado"], "abaixo")

    def test_campanha_encerrada_nao_mostra_ritmo(self):
        pacing = calcular_pacing_midia(
            2000,
            2300,
            date(2026, 4, 1),
            date(2026, 4, 30),
            encerrada=True,
            hoje=date(2026, 5, 10),
        )
        self.assertEqual(pacing["modo"], "resultado")
        self.assertEqual(pacing["resultado"], "acima")
        self.assertEqual(pacing["excedente"], 300.0)
        self.assertIsNone(pacing["pacing_atual_dia"])
        self.assertIsNone(pacing["pacing_previsto_dia"])

    def test_periodo_esgotado_vira_resultado_mesmo_sem_flag(self):
        pacing = calcular_pacing_midia(
            1000,
            1000,
            date(2026, 1, 1),
            date(2026, 1, 31),
            encerrada=False,
            hoje=date(2026, 2, 1),
        )
        self.assertEqual(pacing["modo"], "resultado")
        self.assertEqual(pacing["resultado"], "dentro")

    def test_campanha_encerrada_por_status_ou_substatus(self):
        self.assertTrue(campanha_esta_encerrada("Finalizada"))
        self.assertTrue(campanha_esta_encerrada("Ativa", pi_sub_status=4))
        self.assertTrue(
            campanha_esta_encerrada("Ativa", periodo_fim=date(2026, 4, 1), hoje=date(2026, 5, 1))
        )
        self.assertFalse(
            campanha_esta_encerrada("Ativa", periodo_fim=date(2026, 6, 1), hoje=date(2026, 5, 1))
        )


if __name__ == "__main__":
    unittest.main()
