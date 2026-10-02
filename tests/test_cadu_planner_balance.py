"""Balanceamento de mídia do Planner: leitura do briefing, motor e alertas."""
from datetime import date

import pytest

from aicentralv2.cadu_planner import balance, time_saved


@pytest.mark.parametrize('raw, expected', [
    ('R$ 120.000', 120_000), ('120 mil', 120_000), ('1,2 mi', 1_200_000), ('R$ 80k', 80_000),
    ('100.000,00', 100_000), ('R$ 1.500.000', 1_500_000), ('2.5 milhões', 2_500_000), ('a definir', None), ('', None),
])
def test_parse_budget(raw, expected):
    assert balance.parse_budget(raw) == expected


@pytest.mark.parametrize('raw, labels', [
    ('mar a mai 2027', ['mar/27', 'abr/27', 'mai/27']),
    ('01/03/2027 a 31/05/2027', ['mar/27', 'abr/27', 'mai/27']),
    ('3 meses', ['out/26', 'nov/26', 'dez/26']),
    ('novembro a fevereiro', ['nov/26', 'dez/26', 'jan/27', 'fev/27']),
    ('Black Friday', []),
])
def test_parse_period(raw, labels):
    result = balance.parse_period(raw, today=date(2026, 10, 2))
    assert [month['label'] for month in result['months']] == labels
    assert result['parsed'] is bool(labels)


def test_channel_group_uses_smartplanner_key_then_slug_then_category():
    assert balance.channel_group({'chave_sp': 'meta_ads', 'slug': 'instagram', 'categoria': 'Sociais'}) == 'social'
    assert balance.channel_group({'slug': 'spotify', 'categoria': 'Streaming'}) == 'audio'
    assert balance.channel_group({'slug': 'novo-canal', 'categoria': 'Streaming'}) == 'ctv'
    assert balance.channel_group({'slug': 'x', 'categoria': 'Desconhecida'}) == 'performance'


CHANNELS = [
    {'resource_id': '1', 'name': 'Netflix', 'category': 'Streaming', 'logo': '', 'color': '', 'group': 'ctv', 'minimum': 50_000},
    {'resource_id': '2', 'name': 'Instagram', 'category': 'Sociais', 'logo': '', 'color': '', 'group': 'social', 'minimum': 3_000},
    {'resource_id': '3', 'name': 'Google DV360', 'category': 'Programática', 'logo': '', 'color': '', 'group': 'programmatic', 'minimum': 10_000},
]


@pytest.fixture
def channels(monkeypatch):
    monkeypatch.setattr(balance, '_channels', lambda plan: [dict(item) for item in CHANNELS])


def plan(**briefing):
    return {'objective': 'vendas', 'briefing': briefing, 'items': [], 'allocation_by_channel': {'1': {'weight': 50, 'investment': 50_000}}}


def test_compute_closes_100_percent_and_the_budget(channels):
    result = balance.compute(plan(budget='R$ 100 mil', period='mar a mai 2027'), 'eficiencia')
    assert sum(row['pct'] for row in result['channels']) == 100
    assert sum(row['investment'] for row in result['channels']) == 100_000
    assert result['strategy']['id'] == 'eficiencia'
    assert result['channels'][0]['current_pct'] == 50
    assert result['methods'][0]['id'] == 'funil' and any(item['primary'] for item in result['methods'])


def test_recommended_method_is_used_when_none_is_given(channels):
    assert balance.compute(plan(budget='100 mil'))['method'] == 'funil'


def test_calendar_moves_from_awareness_to_objective(channels):
    result = balance.compute(plan(budget='R$ 300 mil', period='mar a mai 2027'), 'funil')
    calendar = result['calendar']
    assert calendar['progressive'] is True
    assert sum(item['value'] for item in calendar['totals']) == 300_000
    netflix = [cell['pct'] for cell in calendar['cells']['1']]
    assert netflix[0] > netflix[-1]  # CTV pesa mais no começo (lembrança) que no fim (vendas)
    for index in range(3):
        assert sum(calendar['cells'][key][index]['value'] for key in calendar['cells']) == calendar['totals'][index]['value']


def test_manual_weights_are_normalized(channels):
    result = balance.compute(plan(budget='100 mil'), 'manual', {'1': 60, '2': 30, '3': 30})
    assert [row['pct'] for row in result['channels']] == [50, 25, 25]
    assert result['calendar'] is None  # sem período legível não há mês a mês


def test_warns_when_a_channel_falls_below_its_buying_minimum(channels):
    result = balance.compute(plan(budget='R$ 60 mil', period='3 meses'), 'eficiencia')
    texts = ' '.join(item['text'] for item in result['warnings'])
    assert 'Netflix' in texts and 'mínimo de compra' in texts


def test_without_budget_or_period_asks_for_them(channels):
    texts = ' '.join(item['text'] for item in balance.compute(plan(), 'funil')['warnings'])
    assert 'investimento' in texts and 'período' in texts


def test_time_saved_counts_only_what_the_plan_used():
    estimate = time_saved.estimate({
        'items': [{'kind': 'canais'}] * 3 + [{'kind': 'audiencias'}],
        'review_history': [{'id': 'r1'}, {'id': 'r2'}],
        'workbench': {'balance': {'method': 'funil', 'progressive': True}}, 'source': 'radar'})
    keys = {line['key']: line['minutes'] for line in estimate['lines']}
    assert keys == {'canais': 60, 'audiencias': 15, 'briefing_review': 45, 'balance': 90, 'calendar': 30, 'radar': 180}
    assert estimate['minutes'] == 420 and estimate['label'] == '7 h'
    assert time_saved.estimate({'items': []})['minutes'] == 0


def test_reopening_a_manual_balance_starts_from_the_saved_allocation(channels):
    saved = plan(budget='100 mil')
    saved['allocation_by_channel'] = {'1': {'weight': 70}, '2': {'weight': 20}, '3': {'weight': 10}}
    assert [row['pct'] for row in balance.compute(saved, 'manual')['channels']] == [70, 20, 10]
