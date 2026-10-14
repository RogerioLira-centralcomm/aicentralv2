from aicentralv2.cadu_planner import balance


def test_channel_indicators_follow_plan_kpis():
    kpis = balance.plan_kpis('Visitas qualificadas, CTR; views completas (VTR) e visitas a pontos de venda, Viewability')
    assert kpis == ['Visitas qualificadas', 'CTR', 'views completas (VTR)', 'visitas a pontos de venda', 'Viewability']
    assert balance._channel_kpis('places', kpis) == (['visitas a pontos de venda'], True)
    assert balance._channel_kpis('ctv', kpis) == (['views completas (VTR)', 'Viewability'], True)
    # Nenhum KPI do plano serve ao áudio: volta aos indicadores típicos do grupo.
    assert balance._channel_kpis('audio', kpis)[1] is False


def test_kpi_cut_from_the_column_is_not_reported_as_unmeasured():
    plan = {'briefing': {'kpis': 'Alcance, CTR, VTR, lembrança de marca, Vendas'}, 'items': []}
    rows = [{'group': 'social'}]
    present = {row['group'] for row in rows}
    kpis = balance.plan_kpis(plan['briefing']['kpis'])
    assert len(balance._channel_kpis('social', kpis)[0]) == 4
    assert [kpi for kpi in kpis if balance.kpi_groups(kpi) and not balance.kpi_groups(kpi) & present] == []
