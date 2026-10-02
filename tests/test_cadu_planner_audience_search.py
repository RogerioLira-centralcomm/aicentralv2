from aicentralv2.cadu_family import repository


def run(monkeypatch, **kwargs):
    calls = []

    def fake_rows(sql, params=()):
        calls.append((sql, params))
        if 'COUNT(*) OVER ()' in sql:
            return [{'id': 1, 'name': 'A', 'total_count': 933}, {'id': 2, 'name': 'B', 'total_count': 933}]
        return [{'value': 'Netflix', 'n': 60}]

    monkeypatch.setattr(repository, 'rows', fake_rows)
    return repository.audience_search(**kwargs), calls


def test_page_total_and_facets(monkeypatch):
    result, calls = run(monkeypatch)
    assert result['total'] == 933
    assert [record.get('total_count') for record in result['records']] == [None, None]
    assert result['facets']['platforms'] == [{'value': 'Netflix', 'count': 60, 'logo': '/static/images/creative-viewers/netflix.png'}]
    # Subcategories only appear once a category is chosen.
    assert result['facets']['subcategories'] == []
    assert len(calls) == 3


def test_limit_is_clamped_and_sort_whitelisted(monkeypatch):
    result, calls = run(monkeypatch, limit=10_000, offset=-5, sort='DROP TABLE')
    assert result['limit'] == repository.AUDIENCE_PAGE_MAX
    assert result['offset'] == 0
    assert repository.AUDIENCE_SORTS['relevant'] in calls[0][0]
    assert 'DROP' not in calls[0][0]


def test_each_facet_ignores_its_own_filter(monkeypatch):
    _result, calls = run(monkeypatch, platform='Netflix', category='Mobilidade', subcategory='Carro')
    facet_sql = {sql.split(' AS value')[0].split('SELECT ')[1]: sql for sql, _params in calls[1:]}
    assert "p.nome = %(platform)s" not in facet_sql['p.nome']
    assert "c.nome = %(category)s" not in facet_sql['c.nome'] and "s.nome = %(subcategory)s" not in facet_sql['c.nome']
    assert "s.nome = %(subcategory)s" not in facet_sql['s.nome'] and "c.nome = %(category)s" in facet_sql['s.nome']
    assert calls[0][1]['platform'] == 'Netflix'


def test_empty_search_skips_the_text_filter(monkeypatch):
    _result, calls = run(monkeypatch)
    sql, params = calls[0]
    assert "%(query)s = ''" in sql and params['query'] == '' and params['q'] == '%%'
    _result, calls = run(monkeypatch, query='viagem')
    assert calls[0][1]['query'] == 'viagem' and calls[0][1]['q'] == '%viagem%'


def test_platform_logos_resolve_to_files_that_exist():
    from pathlib import Path
    static = Path(repository.__file__).resolve().parents[1]
    for name in repository.AUDIENCE_PLATFORM_LOGOS:
        logo = repository.platform_logo_by_name(name)
        assert logo and (static / logo.lstrip('/')).is_file(), name
    assert repository.platform_logo_by_name('Plataforma desconhecida') == ''


def test_format_platforms_link_to_channels_with_logos():
    from pathlib import Path
    from aicentralv2.crm_v3_canais import _resolver_logo
    static = Path(repository.__file__).resolve().parents[1]
    for platform, slugs in repository.FORMAT_PLATFORM_CHANNELS.items():
        assert slugs, platform
        for slug in slugs:
            logo = _resolver_logo(slug, '')
            assert logo and (static / logo.lstrip('/')).is_file(), (platform, slug)
    for platform in repository.FORMAT_PLATFORM_LOGOS:
        logo = repository.platform_logo_by_slug(platform, '')
        assert logo and (static / logo.lstrip('/')).is_file(), platform
