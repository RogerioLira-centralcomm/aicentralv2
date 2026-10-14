from aicentralv2.cadu_planner import balance


def test_channel_indicators_follow_plan_kpis():
    kpis = balance.plan_kpis('Visitas qualificadas, CTR; views completas (VTR) e visitas a pontos de venda, Viewability')
    assert kpis == ['Visitas qualificadas', 'CTR', 'views completas (VTR)', 'visitas a pontos de venda', 'Viewability']
    assert balance._channel_kpis('places', kpis) == (['visitas a pontos de venda'], True)
    assert balance._channel_kpis('ctv', kpis) == (['views completas (VTR)', 'Viewability'], True)
    # Nenhum KPI do plano serve ao áudio: volta aos indicadores típicos do grupo.
    assert balance._channel_kpis('audio', kpis)[1] is False
