import unittest

from aicentralv2.cadu_connect.reports_flow_pages import MIN_SCORE_SESSIONS, flow_page_rows, grade, usage_score


class UsageScoreTests(unittest.TestCase):
    def test_small_sample_has_no_score(self):
        self.assertEqual(usage_score(MIN_SCORE_SESSIONS - 1, 60, 80, 60, 50, 10), (None, {}))

    def test_full_marks_and_renormalised_weights(self):
        score, parts = usage_score(100, 90, 100, 100, 60, 0)
        self.assertEqual(score, 100)
        self.assertEqual(set(parts), {'time', 'scroll', 'advance', 'exit'})
        # Without a next step or scroll events, only time and exit count, each by its own weight.
        score, parts = usage_score(100, median_active_seconds=45, exit_rate=100)
        self.assertEqual(set(parts), {'time', 'exit'})
        self.assertEqual(score, round((100 * 25 + 0 * 20) / 45))

    def test_grades(self):
        self.assertEqual([grade(None), grade(85), grade(55), grade(12)], [None, 'good', 'attention', 'critical'])


class FlowPageRowsTests(unittest.TestCase):
    config = {'nodes': [
        {'id': 'home', 'type': 'page', 'title': 'Home', 'path': '/'},
        {'id': 'blog', 'type': 'page', 'title': 'Blog', 'path': '/Blog/'},
        {'id': 'contato', 'type': 'form', 'title': 'Contato', 'path': '/contato'},
        {'id': 'fim', 'type': 'conversion', 'title': 'Obrigado', 'path': '/obrigado'},
        {'id': 'fora', 'type': 'page', 'title': 'Parceiro', 'path': '/x', 'host': 'outro.com'},
        {'id': 'meta', 'type': 'source', 'title': 'Meta'},
    ], 'edges': [{'from': 'home', 'to': 'contato'}, {'from': 'home', 'to': 'blog'}, {'from': 'contato', 'to': 'fim'}]}

    def rows(self):
        pages = {'/': {'views': 200, 'sessions': 150, 'entries': 140, 'exits': 60, 'single_page': 40},
                 '/contato': {'views': 50, 'sessions': 40, 'entries': 2, 'exits': 10, 'single_page': 1},
                 '/obrigado': {'views': 25, 'sessions': 25, 'entries': 0, 'exits': 25, 'single_page': 0}}
        engagement = {'/': {'median_active_ms': 30000, 'scrolled': 120, 'scroll_50': 90, 'scroll_75': 45},
                      '/obrigado': {'median_active_ms': 4000, 'scrolled': 0}}
        transitions = {('/', '/contato'): 30, ('/', '/blog'): 0, ('/contato', '/obrigado'): 25}
        return {row['node_id']: row for row in flow_page_rows(self.config, 'site.com', pages, engagement, transitions)}

    def test_measured_page_reads_every_signal(self):
        home = self.rows()['home']
        self.assertEqual((home['sessions'], home['advance_rate'], home['exit_rate'], home['scroll_50']), (150, 20.0, 30.0, 60.0))
        self.assertEqual(home['median_active_seconds'], 30.0)
        self.assertEqual(home['next_steps'], ['Contato', 'Blog'])
        self.assertIsNotNone(home['score'])

    def test_idle_external_and_conversion_pages(self):
        rows = self.rows()
        self.assertEqual(rows['blog']['status'], 'idle')
        self.assertIsNone(rows['blog']['score'])
        self.assertEqual(rows['fora']['status'], 'external')
        self.assertNotIn('meta', rows)
        # The thank-you page ends the visit by design: it has numbers but no usage score.
        self.assertEqual((rows['fim']['sessions'], rows['fim']['score']), (25, None))


if __name__ == '__main__':
    unittest.main()
