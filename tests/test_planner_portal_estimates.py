from aicentralv2.cadu_planner import portal_estimates as pe


def test_registrable_keeps_three_labels_for_br_second_level():
    assert pe.registrable('g1.globo.com') == 'globo.com'
    assert pe.registrable('www.exemplo.com.br') == 'exemplo.com.br'
    assert pe.registrable('uol.com.br') == 'uol.com.br'


def test_popularity_prefers_exact_domain_then_parent():
    ranks = {'globo.com': 396, 'ge.globo.com': 900}
    assert pe.popularity('ge.globo.com', ranks) == (900, 'tranco')
    assert pe.popularity('g1.globo.com', ranks) == (396, 'tranco_parent')
    assert pe.popularity('desconhecido.com.br', ranks) == (None, None)


def test_tier_inherited_from_small_parent_drops_one_level_but_not_for_giants():
    assert pe.traffic_tier(396, 'tranco_parent') == 'grande'
    assert pe.traffic_tier(8_000, 'tranco_parent') == 'medio'
    assert pe.traffic_tier(8_000, 'tranco') == 'grande'
    assert pe.traffic_tier(None, None) == 'nicho'


def test_demographics_are_labelled_as_estimates():
    result = pe.demographics('Esportes')
    assert result['genero'] == 'masculino' and result['estimado'] is True and result['confianca'] == 'baixa'
    assert pe.demographics('Jornalismo online · Nordeste')['regiao'] == 'Nordeste'
