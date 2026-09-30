from aicentralv2.cadu_connect import reports_flow
from aicentralv2.cadu_connect.reports_flow_catalog import build_catalog, catalog_groups


def page(index, path, **extra):
    return {'id': index, 'url': f'https://exemplo.com{path}', 'path_prefix': path, 'title': f'Página {index}',
            'page_status': 'valida', 'evidence': extra.pop('evidence', {}), 'form_count': 0, 'form_fields': [], **extra}


def test_discovery_budget_is_bounded_per_call_and_per_mapping():
    total = reports_flow.MAX_DISCOVERY_TOTAL_PAGES
    assert total == 100
    assert reports_flow._discovery_budget(0) == reports_flow.MAX_DISCOVERY_PAGES
    assert reports_flow._discovery_budget(60) == 40
    assert reports_flow._discovery_budget(total) == 0
    assert reports_flow._discovery_budget(total + 10) == 0
    assert reports_flow._discovery_budget(0, 20) == 20
    assert reports_flow._discovery_budget(90, 50) == 10
    assert reports_flow._discovery_budget(0, 'abc') == reports_flow.MAX_DISCOVERY_PAGES
    assert reports_flow._discovery_budget(0, 9999) == reports_flow.MAX_DISCOVERY_PAGES


def test_pages_are_grouped_by_url_folder_and_labelled_as_such():
    pages = [page(i, f'/blog/post-{i}') for i in range(1, 6)] + [page(10, '/'), page(11, '/contato'), page(12, '/sobre/equipe')]
    catalog = build_catalog(pages, 'exemplo.com')
    blog = [item for item in catalog if item['path_prefix'].startswith('/blog/')]
    assert len(blog) == 5
    assert all(item['template_id'] is None for item in blog)
    assert {item['section_pattern'] for item in blog} == {'/blog/*'}
    assert len({item['section_id'] for item in blog}) == 1
    assert all(not item.get('section_id') for item in catalog if not item['path_prefix'].startswith('/blog/'))


def test_html_signature_keeps_the_template_kind_and_groups_summarize_counts():
    signed = [page(i, f'/produtos/item-{i}', evidence={'structure_signature': 'abc'}) for i in range(1, 5)]
    folder = [page(20 + i, f'/blog/post-{i}') for i in range(1, 4)]
    groups = catalog_groups(build_catalog(signed + folder, 'exemplo.com'))
    by_kind = {group['kind']: group for group in groups}
    assert by_kind['template']['count'] == 4 and by_kind['template']['pattern'] == '/produtos/*'
    assert by_kind['path']['count'] == 3 and by_kind['path']['pattern'] == '/blog/*'
    assert groups[0]['count'] >= groups[-1]['count']
    assert by_kind['path']['locales'] and isinstance(by_kind['path']['roles'], dict)


def test_two_pages_in_a_folder_are_not_a_group():
    catalog = build_catalog([page(1, '/blog/a'), page(2, '/blog/b')], 'exemplo.com')
    assert all(not item.get('template_id') and not item.get('section_id') for item in catalog)
    assert catalog_groups(catalog) == []
