from aicentralv2.cadu_connect.reports_page_paths import normalize_page_path, translation_key
from aicentralv2.cadu_connect.reports_flow_catalog import build_catalog, catalog_summary
from aicentralv2.cadu_connect.reports_flow import _SitePageParser


def test_normalized_paths_and_locale_boundaries():
    examples = [
        ('https://centralcomm.media/', 'pt', '/'),
        ('https://centralcomm.media/en/', 'en', '/'),
        ('/en/cases/abc/', 'en', '/cases/abc'),
        ('/Cases/ABC?utm=x', 'pt', '/cases/abc'),
        ('/english-page', 'pt', '/english-page'),
        ('//media-hacks//leituras/x/', 'pt', '/media-hacks/leituras/x'),
        ('/en/index.html', 'en', '/'),
    ]
    for value, locale, path in examples:
        assert normalize_page_path(value) == {'locale': locale, 'path': path}


def test_translation_key_needs_evidence_for_different_slugs():
    paths = {'/contato': {'pt'}, '/contact': {'en'}}
    contact = {'path_prefix': '/en/contact', 'evidence': {'hreflang': {'pt': 'https://example.com/contato'}}}
    assert translation_key(contact, paths) == '/contato'
    assert translation_key({'path_prefix': '/en/contact'}, paths) == '/contact:en'
    assert translation_key({'path_prefix': '/en/cases/x'}, {'/cases/x': {'pt', 'en'}}) == '/cases/x'


def test_catalog_merges_language_group_and_keeps_counts_consistent():
    paths = ['/cases/a', '/cases/b', '/cases/c', '/en/cases/a', '/en/cases/b', '/en/cases/c']
    pages = [{'id': path, 'url': 'https://example.com' + path, 'path_prefix': path,
              'title': path, 'evidence': {'structure_signature': 'main|article'}} for path in paths]
    pages.append({**pages[0], 'id': 'alias'})
    catalog = build_catalog(pages, 'example.com')
    summary = catalog_summary(pages, catalog)
    assert len(catalog) == 6
    assert len({page['template_id'] for page in catalog}) == 1
    assert {page['template_pattern'] for page in catalog} == {'/cases/*'}
    assert {page['locale'] for page in catalog} == {'pt', 'en'}
    assert summary['descobertas'] == summary['validas'] + sum(summary['excluidas'].values())
    assert summary['validas'] == summary['classificadas'] + summary['sem_tipo']
    pages.append({**pages[0], 'id': 'noindex', 'page_status': 'noindex'})
    summary=catalog_summary(pages, build_catalog(pages,'example.com'))
    assert summary['excluidas']['noindex']==1
    assert summary['descobertas']==summary['validas']+sum(summary['excluidas'].values())


def test_hreflang_is_collected_and_duplicate_case_urls_are_one_page():
    parser = _SitePageParser()
    parser.feed('<link rel="alternate" hreflang="pt" href="/contato"><link rel="alternate" hreflang="en" href="/en/contact"><meta name="robots" content="noindex,follow">')
    assert parser.hreflang == {'pt': '/contato', 'en': '/en/contact'}
    assert parser.noindex is True
    pages = [
        {'id': 'pt', 'url': 'https://example.com/Cases/ABC/', 'path_prefix': '/Cases/ABC/', 'title': 'Case'},
        {'id': 'alias', 'url': 'https://example.com/cases/abc', 'path_prefix': '/cases/abc', 'title': 'Case'},
    ]
    assert len(build_catalog(pages, 'example.com')) == 1
