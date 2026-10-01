import unittest

from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config


def node(**extra):
    return {'id': 'n1', 'type': 'page', 'title': 'Home', 'path': '/', 'x': 80, 'y': 80, **extra}


class FlowContractTests(unittest.TestCase):
    def setUp(self):
        self.context = Flask(__name__).test_request_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_kind_survives_v1_normalization(self):
        source = {'id': 's1', 'type': 'source', 'title': 'Meta', 'kind': 'traffic.meta', 'source': 'meta', 'x': 0, 'y': 0}
        config, _ = _normalize_flow_config({'nodes': [source, node()], 'edges': []}, 'exemplo.com.br')
        self.assertEqual(config['nodes'][0]['kind'], 'traffic.meta')
        self.assertEqual(config['nodes'][0]['source'], 'meta')

    def test_invalid_kind_falls_back_to_the_default_kind_of_its_type(self):
        config, _ = _normalize_flow_config({'nodes': [node(kind='<script>')], 'edges': []}, 'exemplo.com.br')
        self.assertEqual(config['nodes'][0]['kind'], 'page.generic')
        self.assertEqual(config['schema_version'], 3)

    def test_site_kind(self):
        config, _ = _normalize_flow_config({'nodes': [node()], 'edges': [], 'site_kind': 'landing'}, 'exemplo.com.br')
        self.assertEqual(config['site_kind'], 'landing')
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [node()], 'edges': [], 'site_kind': 'blog'}, 'exemplo.com.br')


if __name__ == '__main__':
    unittest.main()
