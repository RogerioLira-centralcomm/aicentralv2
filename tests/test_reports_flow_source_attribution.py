import unittest

from aicentralv2.cadu_connect.reports_flow_live import build_live_snapshot
from aicentralv2.cadu_connect.reports_flow_metrics import apply_session_bounds, origin_platform, origin_summary
from aicentralv2.cadu_connect.reports_flow_metrics import search_engine_for_host


def _bounds(*rows):
    return [{'first_node': 'home', 'last_node': 'home', 'origin': origin, 'sessions': sessions} for origin, sessions in rows]


class SourceAttributionTests(unittest.TestCase):
    def run_bounds(self, sources, bounds):
        config = {'nodes': [*sources, {'id': 'home', 'type': 'page'}],
                  'edges': [{'id': f"e-{node['id']}", 'from': node['id'], 'to': 'home'} for node in sources]}
        nodes = [{'id': node['id'], 'sessions': None} for node in config['nodes']]
        edges = [dict(edge, sessions=None) for edge in config['edges']]
        unattributed = apply_session_bounds(config, nodes, edges, bounds, {'home'})
        return {node['id']: node for node in nodes}, {edge['from']: edge for edge in edges}, unattributed

    def test_two_instagram_origins_split_by_utm_campaign(self):
        sources = [{'id': 'ig1', 'type': 'source', 'source': 'instagram', 'media': {'utm': {'campaign': 'lancamento'}}},
                   {'id': 'ig2', 'type': 'source', 'source': 'instagram', 'media': {'utm': {'campaign': 'remarketing'}}}]
        by_id, edges, unattributed = self.run_bounds(sources, _bounds(('utm:instagram|lancamento', 7), ('utm:instagram|remarketing', 3), ('utm:instagram|', 2)))
        self.assertEqual((by_id['ig1']['sessions'], by_id['ig2']['sessions']), (7, 3))
        self.assertEqual((edges['ig1']['sessions'], edges['ig2']['sessions']), (7, 3))
        self.assertEqual(unattributed[0]['platform'], 'meta')
        self.assertEqual(unattributed[0]['sessions'], 2)

    def test_identical_origins_are_not_double_counted(self):
        sources = [{'id': 'ig1', 'type': 'source', 'source': 'instagram'}, {'id': 'ig2', 'type': 'source', 'source': 'instagram'}]
        by_id, _, unattributed = self.run_bounds(sources, _bounds(('utm:instagram|x', 5)))
        self.assertEqual((by_id['ig1']['sessions'], by_id['ig2']['sessions']), (0, 0))
        self.assertEqual(unattributed[0]['sessions'], 5)

    def test_single_origin_keeps_legacy_rows(self):
        by_id, _, unattributed = self.run_bounds([{'id': 'g', 'type': 'source', 'source': 'google'}], _bounds(('utm:google', 4)))
        self.assertEqual(by_id['g']['sessions'], 4)
        self.assertEqual(unattributed, [])

    def test_search_origins_split_by_engine(self):
        sources = [{'id': 'g', 'type': 'source', 'kind': 'traffic.organic_search', 'search_engines': ['google']},
                   {'id': 'b', 'type': 'source', 'kind': 'traffic.organic_search', 'search_engines': ['bing', 'duckduckgo']}]
        by_id, _, unattributed = self.run_bounds(sources, _bounds(('ref:www.google.com.br', 6), ('ref:www.bing.com', 2), ('ref:duckduckgo.com', 1), ('ref:search.yahoo.com', 4)))
        self.assertEqual((by_id['g']['sessions'], by_id['b']['sessions']), (6, 3))
        self.assertEqual([item['engine'] for item in by_id['b']['search_engines']], ['bing', 'duckduckgo'])
        self.assertEqual(unattributed[0]['search_engines'][0]['engine'], 'yahoo')

    def test_engine_hosts(self):
        self.assertEqual(search_engine_for_host('www.google.com.br'), 'google')
        self.assertIsNone(search_engine_for_host('mail.google.com'))
        self.assertIsNone(search_engine_for_host('bing.example.org'))
        self.assertEqual(origin_platform('ref:mail.google.com'), 'referral')
        self.assertEqual(origin_platform('utm:instagram|campanha'), 'meta')
        summary = origin_summary(_bounds(('ref:www.google.com', 3), ('ref:www.bing.com', 1)))
        self.assertEqual([item['engine'] for item in summary[0]['search_engines']], ['google', 'bing'])

    def test_live_lights_only_the_claiming_origin(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        nodes = [{'id': 'ig1', 'type': 'source', 'source': 'instagram', 'media': {'utm': {'campaign': 'a'}}},
                 {'id': 'ig2', 'type': 'source', 'source': 'instagram', 'media': {'utm': {'campaign': 'b'}}},
                 {'id': 'home', 'type': 'page', 'path': '/'}]
        edges = [{'id': 'e1', 'from': 'ig1', 'to': 'home'}, {'id': 'e2', 'from': 'ig2', 'to': 'home'}]
        events = [{'id': 1, 'session_id': 's', 'page_host': 'site.com', 'page_path': '/', 'event_kind': 'page_view', 'event_name': None,
                   'occurred_at': now, 'utm_source': 'instagram', 'utm_campaign': 'b', 'referrer_host': None}]
        snapshot = build_live_snapshot(events, nodes, edges, now)
        self.assertEqual(list(snapshot['transitions']), ['e2'])


if __name__ == '__main__':
    unittest.main()
