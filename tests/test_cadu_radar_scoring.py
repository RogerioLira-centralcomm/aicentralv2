import pytest

from aicentralv2.cadu_radar import scoring
from aicentralv2.cadu_radar.contracts import GeoScore, Opportunity, Signal


def test_weights_sum_to_one_hundred():
    assert sum(scoring.EDITORIAL_WEIGHTS.values()) == 100
    assert sum(scoring.PAID_WEIGHTS.values()) == 100
    assert sum(scoring.GEO_WEIGHTS.values()) == 100


def test_paid_score_is_weighted_average():
    criteria = {key: 80 for key in scoring.PAID_WEIGHTS}
    assert scoring.paid_score(criteria).score == 80
    criteria['icp'] = 30  # peso 20: derruba 10 pontos
    assert scoring.paid_score(criteria).score == 70


def test_missing_criteria_count_as_zero():
    result = scoring.editorial_score({'icp': 100})
    assert result.score == 20
    assert result.criteria['timing'] == 0


def test_penalties_are_capped_and_floor_at_zero():
    criteria = {key: 90 for key in scoring.PAID_WEIGHTS}
    result = scoring.paid_score(criteria, {'risco_reputacional': 500, 'baixa_confianca': 5})
    assert result.penalties == {'risco_reputacional': 30, 'baixa_confianca': 5}
    assert result.score == 55
    assert scoring.paid_score({}, {'restricao_marca': 30}).score == 0


def test_unknown_criteria_and_penalties_are_rejected():
    with pytest.raises(ValueError):
        scoring.paid_score({'viralidade': 90})
    with pytest.raises(ValueError):
        scoring.paid_score({}, {'achismo': 10})


@pytest.mark.parametrize('editorial,paid,expected', [
    (94, 89, 'integrada'), (92, 42, 'conteudo'), (54, 91, 'midia'), (40, 30, 'ignorar'), (70, 70, 'integrada'),
])
def test_quadrant(editorial, paid, expected):
    assert scoring.quadrant(editorial, paid) == expected


def test_geo_ranking_does_not_follow_audience_alone():
    sao_paulo = GeoScore('São Paulo', interest=60, audience=98, owned_base=40, media_history=50,
                         competition=30, coverage=40, context=50, business_goal=50)
    belo_horizonte = GeoScore('Belo Horizonte', interest=85, audience=70, owned_base=94, media_history=80,
                              competition=83, coverage=70, context=80, business_goal=80)
    ranked = scoring.rank_places([sao_paulo, belo_horizonte])
    assert [place.place for place in ranked] == ['Belo Horizonte', 'São Paulo']
    assert ranked[0].score > ranked[1].score


def test_contracts_validate_enums():
    with pytest.raises(ValueError):
        Signal(headline='x', source='y', source_type='boato')
    with pytest.raises(ValueError):
        Signal(headline='x', source='y', confidence=2)
    with pytest.raises(ValueError):
        Opportunity(title='x', thesis='y', quadrant='talvez')
