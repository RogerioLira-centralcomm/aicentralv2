import unittest

from aicentralv2.cadu_connect.reports_flow_metrics import apply_session_bounds, origin_platform, origin_summary


class SessionBoundsTests(unittest.TestCase):
    def test_origin_platform(self):
        self.assertEqual(origin_platform(None), 'direct')
        self.assertEqual(origin_platform('utm:google'), 'google')
        self.assertEqual(origin_platform('utm:instagram'), 'meta')
        self.assertEqual(origin_platform('utm:parceiro'), 'campaign')
        self.assertEqual(origin_platform('ref:www.google.com.br'), 'organic')
        self.assertEqual(origin_platform('ref:l.facebook.com'), 'social')
        self.assertEqual(origin_platform('ref:portal.example.org'), 'referral')

    def test_entrances_exits_and_sources(self):
        config = {'nodes': [{'id': 's1', 'type': 'source', 'source': 'google'}, {'id': 's2', 'type': 'source', 'kind': 'traffic.organic_search'},
                            {'id': 'home', 'type': 'page'}, {'id': 'lead', 'type': 'conversion'}],
                  'edges': [{'id': 'a', 'from': 's1', 'to': 'home'}, {'id': 'b', 'from': 's2', 'to': 'home'}]}
        nodes = [{'id': 's1', 'sessions': None}, {'id': 's2', 'sessions': None}, {'id': 'home', 'sessions': 10}, {'id': 'lead', 'sessions': 3}]
        edges = [{'id': 'a', 'from': 's1', 'to': 'home', 'sessions': None}, {'id': 'b', 'from': 's2', 'to': 'home', 'sessions': None}]
        bounds = [{'first_node': 'home', 'last_node': 'home', 'origin': 'utm:google', 'sessions': 4},
                  {'first_node': 'home', 'last_node': 'lead', 'origin': 'utm:google', 'sessions': 3},
                  {'first_node': 'home', 'last_node': 'home', 'origin': 'ref:www.google.com', 'sessions': 3}]
        apply_session_bounds(config, nodes, edges, bounds, {'home', 'lead'})
        by_id = {node['id']: node for node in nodes}
        self.assertEqual((by_id['home']['entrances'], by_id['home']['exits']), (10, 7))
        self.assertEqual(by_id['lead']['exits'], 3)
        self.assertEqual(by_id['s1']['sessions'], 7)
        self.assertEqual(by_id['s2']['sessions'], 3)
        self.assertEqual((edges[0]['sessions'], edges[0]['rate']), (7, 100.0))
        self.assertEqual(origin_summary(bounds)[0], {'platform': 'google', 'label': 'Google Ads', 'sessions': 7})


if __name__ == '__main__':
    unittest.main()
