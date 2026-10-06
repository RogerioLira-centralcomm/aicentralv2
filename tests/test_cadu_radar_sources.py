from aicentralv2.cadu_radar import prompts, sources


def test_government_and_brand_site_are_primary():
    assert sources.lookup('https://www.gov.br/aneel/x')['tier'] == 'A'
    assert sources.lookup('https://dadosabertos.aneel.gov.br/d')['primary'] is True
    assert sources.lookup('https://www.cemig.com.br/noticia', 'https://cemig.com.br')['group'] == 'oficial'


def test_unknown_and_social_domains_are_tier_c():
    assert sources.lookup('https://blog.qualquer.com.br/post')['tier'] == 'C'
    assert sources.lookup('https://www.reddit.com/r/x')['tier'] == 'C'


def test_subdomain_inherits_catalogued_domain():
    assert sources.lookup('https://economia.estadao.com.br/a')['tier'] == 'A'


def test_confidence_needs_independent_groups():
    # g1 e O Globo são do mesmo grupo: valem uma fonte só.
    assert sources.confidence(['https://g1.globo.com/a', 'https://oglobo.globo.com/b']) == 'media'
    assert sources.confidence(['https://g1.globo.com/a', 'https://www.estadao.com.br/b']) == 'alta'
    assert sources.confidence(['https://www.gov.br/aneel/a']) == 'alta'
    assert sources.confidence(['https://blog.x.com/a', 'https://reddit.com/b']) == 'baixa'


def test_place_ufs_and_regional_press():
    assert sources.place_ufs('Mato Grosso do Sul, Belo Horizonte, SP') == {'MS', 'MG', 'SP'}
    domains = sources.press_domains('Minas Gerais')
    assert domains[0] in {'estadodeminas.com.br', 'otempo.com.br', 'itatiaia.com.br'}
    assert 'gauchazh.clicrbs.com.br' not in domains


def test_every_prompt_formats():
    values = dict(topic='t', places='BH', lenses='l', recency_days=30, brand_facts='f', sector='s', domains='d',
                  max_opportunities=5, payload='{}', today='2026-10-06', claims='c')
    for name in prompts.V1_0:
        system, user = (item['content'] for item in prompts.messages(name, **values))
        assert system and user


def test_angles_prompt_tells_the_model_not_to_leak_internal_ids():
    system = prompts.messages('angles', '1.5', today='2026-10-06', payload='{}')[0]['content']
    assert 'Hoje é 2026-10-06' in system and 'NUNCA cite os ids' in system
