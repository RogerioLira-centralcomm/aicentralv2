import pytest

from aicentralv2.cadu_planner import benchmarks
from aicentralv2.cadu_planner.benchmarks import Benchmark, Range


def test_impressions_and_reach_math():
    assert benchmarks.impressions(50_000, 25) == 2_000_000
    assert round(benchmarks.reach(2_000_000, 3)) == 666_667
    with pytest.raises(ValueError):
        benchmarks.impressions(1000, 0)


def test_reach_estimate_is_a_range_that_contains_the_middle():
    estimate = benchmarks.reach_estimate(50_000, Range(19, 23, 27), Range(2.5, 3, 3.5))
    imp, people = estimate['impressions'], estimate['reach']
    assert imp['low'] < imp['mid'] < imp['high']
    assert people['low'] < people['mid'] < people['high']
    assert imp['mid'] == int(50_000 / 23 * 1000)
    assert 'não promessas' in estimate['note']


def test_scenarios_scale_with_budget():
    rows = benchmarks.scenarios(45_000, Range(18, 23, 31), Range(3, 3.5, 4))
    assert [row['id'] for row in rows] == ['teste', 'recomendado', 'amplificacao']
    assert rows[0]['budget'] < rows[1]['budget'] < rows[2]['budget']
    assert rows[1]['budget'] == 45_000
    assert benchmarks.scenarios(0, Range(1, 2, 3), Range(1, 2, 3)) == []


def test_split_budget_keeps_every_cent():
    split = benchmarks.split_budget(120_000, {'meta': 30, 'youtube': 25, 'search': 20, 'prog': 15, 'dooh': 10})
    assert split == {'meta': 36_000, 'youtube': 30_000, 'search': 24_000, 'prog': 18_000, 'dooh': 12_000}
    odd = benchmarks.split_budget(100, {'a': 1, 'b': 1, 'c': 1})
    assert round(sum(odd.values()), 2) == 100
    assert benchmarks.split_budget(100, {'a': 0}) == {'a': 0.0}


def test_benchmark_requires_ordered_percentiles_and_known_source():
    assert Benchmark('meta', 'cpm', 18, 23, 31, 'history').range.mid == 23
    with pytest.raises(ValueError):
        Benchmark('meta', 'cpm', 31, 23, 18, 'history')
    with pytest.raises(ValueError):
        Benchmark('meta', 'cpm', 18, 23, 31, 'achismo')


def test_channel_roles_match_whole_words():
    from aicentralv2.cadu_planner.catalog import channel_roles
    roles = [item['role'] for item in channel_roles({'name': 'Spotify', 'slug': 'spotify', 'categoria': 'Streaming de áudio'})]
    assert roles == ['Frequência em contexto']
    assert [item['role'] for item in channel_roles({'name': 'Globoplay', 'categoria': 'CTV'})] == ['Construir alcance']
    assert channel_roles({'name': 'Desconhecido'}) == []
