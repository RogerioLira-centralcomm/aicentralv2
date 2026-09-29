from unittest import TestCase
from aicentralv2.cadu_connect.reports_flow import _assemble_discovered_flow, _discovery_flow_groups


class AutomaticFlowTests(TestCase):
    def page(self, path, role='intermediate', links=()):
        return dict(id=path, page_host='example.com', path_prefix=path, title=path,
                    suggested_role=role, evidence={'links': list(links)}, form_fields=[])

    def test_groups_and_real_links_are_idempotent(self):
        pages = [self.page('/', 'entry', ['https://example.com/products/a']),
                 self.page('/products/a'), self.page('/contact', 'form'),
                 self.page('/thanks', 'conversion')]
        config, omitted = _assemble_discovered_flow({}, pages, 'example.com')
        self.assertEqual(omitted, 0)
        self.assertEqual([n['type'] for n in config['nodes']], ['page', 'page', 'page', 'page'])
        self.assertEqual(config['nodes'][1]['pageGroup'], 'example.com · products')
        self.assertEqual(len(config['edges']), 1)
        again, _ = _assemble_discovered_flow(config, pages, 'example.com')
        self.assertEqual(config, again)

    def test_preserves_authored_nodes_and_respects_limit(self):
        original = {'nodes': [dict(id=str(i), type='page', path=f'/{i}', title='Authored') for i in range(100)], 'edges': []}
        config, omitted = _assemble_discovered_flow(original, [self.page('/new')], 'example.com')
        self.assertEqual(config, original)
        self.assertEqual(omitted, 1)

    def test_primary_pages_exclude_landing_pages_and_other_sections(self):
        pages = [self.page('/', 'entry'), self.page('/contact', 'form'),
                 self.page('/lp/summer', 'form'), self.page('/lp/winter', 'form'),
                 self.page('/blog/article')]
        primary, groups = _discovery_flow_groups(pages)
        self.assertEqual([page['path_prefix'] for page in primary], ['/', '/contact'])
        self.assertEqual(len(groups), 3)
        self.assertEqual([group['kind'] for group in groups], ['landing', 'landing', 'section'])

    def test_large_groups_and_many_groups_never_overlap(self):
        for pages in ([self.page(f'/blog/{i}') for i in range(100)],
                      [self.page(f'/section{i}/page') for i in range(100)]):
            config, omitted = _assemble_discovered_flow({}, pages, 'example.com')
            self.assertEqual(omitted, 0)
            self.assertEqual(len({(n['x'], n['y']) for n in config['nodes']}), 100)
            self.assertTrue(all(0 <= n['x'] <= 10000 and 0 <= n['y'] <= 10000 for n in config['nodes']))

    def test_inferred_conversion_stays_a_page_until_review(self):
        config, _ = _assemble_discovered_flow({}, [self.page('/thanks', 'conversion')], 'example.com')
        self.assertEqual(config['nodes'][0]['type'], 'page')
        self.assertEqual(config['nodes'][0]['suggestedRole'], 'conversion')

    def test_authored_position_is_reserved(self):
        original = {'nodes': [dict(id='manual', type='page', path='/manual', x=80, y=100)]}
        config, _ = _assemble_discovered_flow(original, [self.page('/new')], 'example.com')
        self.assertNotEqual((config['nodes'][1]['x'], config['nodes'][1]['y']), (80,100))
