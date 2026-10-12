import unittest
from unittest import mock

from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_site_pages
from aicentralv2.cadu_connect.reports_flow import FLOW_COORD_LIMIT, _normalize_flow_config


def node(**extra):
    return {'id': 'n1', 'type': 'page', 'title': 'Home', 'path': '/', 'x': 80, 'y': 80, **extra}


class InfiniteBoardTests(unittest.TestCase):
    def setUp(self):
        self.context = Flask(__name__).test_request_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_cards_may_sit_left_of_and_above_the_origin(self):
        config, _ = _normalize_flow_config({'nodes': [node(x=-640, y=-120)], 'edges': []}, 'exemplo.com.br')
        self.assertEqual((config['nodes'][0]['x'], config['nodes'][0]['y']), (-640, -120))

    def test_positions_beyond_the_sanity_limit_are_refused(self):
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [node(x=FLOW_COORD_LIMIT + 1)], 'edges': []}, 'exemplo.com.br')

    def test_frames_follow_the_same_board(self):
        config, _ = _normalize_flow_config({'nodes': [node(x=-600, y=-300, groupId='g')], 'edges': [],
                                            'groups': [{'id': 'g', 'name': 'Grupo', 'memberIds': ['n1'], 'bounds': {'x': -640, 'y': -360, 'width': 300, 'height': 260}}]},
                                           'exemplo.com.br')
        self.assertEqual(config['groups'][0]['bounds']['x'], -640)

    def test_a_suggested_address_is_remembered(self):
        config, _ = _normalize_flow_config({'nodes': [node(pathSource='suggested')], 'edges': []}, 'exemplo.com.br')
        self.assertEqual(config['nodes'][0]['pathSource'], 'suggested')


class NextPageSuggestionTests(unittest.TestCase):
    def rank(self, kind, observed, catalog_rows, after='/'):
        def rows(sql, params=()):
            if 'path=ANY' in sql:
                return [row for row in catalog_rows if row['path'] in params[2]]
            if '~*' in sql:
                return [row for row in catalog_rows if reports_site_pages.NEXT_PAGE_HINTS[kind].search(row['path'])]
            return [row for row in catalog_rows if row['path'] != '/']
        with mock.patch.object(reports_site_pages, '_rows', side_effect=rows):
            return reports_site_pages.suggest_next_pages(1, 'exemplo.com.br', after, kind, ['/ja-no-fluxo'], observed)

    def test_observed_navigation_comes_first_with_its_share(self):
        catalog = [{'path': '/servicos', 'name': 'Serviços', 'title': None}, {'path': '/sobre', 'name': 'Sobre', 'title': None}]
        ranked = self.rank('page', [{'path': '/servicos', 'passes': 30}, {'path': '/sobre', 'passes': 10}], catalog)
        self.assertEqual([page['path'] for page in ranked[:2]], ['/servicos', '/sobre'])
        self.assertEqual(ranked[0]['reason'], 'observed')
        self.assertEqual(ranked[0]['confidence'], 0.75)

    def test_a_form_step_looks_for_contact_pages_and_skips_pages_already_in_the_flow(self):
        catalog = [{'path': '/ja-no-fluxo', 'name': 'x', 'title': None}, {'path': '/contato', 'name': 'Contato', 'title': None}, {'path': '/blog', 'name': 'Blog', 'title': None}]
        ranked = self.rank('form', [{'path': '/blog', 'passes': 50}], catalog, after='/servicos')
        self.assertEqual([page['path'] for page in ranked], ['/contato'])
        self.assertEqual(ranked[0]['reason'], 'pattern')


if __name__ == '__main__':
    unittest.main()
