import json
import shutil
import subprocess
import unittest
from pathlib import Path

from flask import Flask

from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config
from aicentralv2.cadu_connect.reports_flow_validation import is_measured, validate_flow_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = """
import {FLOW_STRATEGIES, buildStrategyConfig} from './frontend/reports-v1/flowStrategies.js';
console.log(JSON.stringify(FLOW_STRATEGIES.map(item => ({id: item.id, config: buildStrategyConfig(item)}))));
"""


@unittest.skipUnless(shutil.which('node'), 'Node.js indisponível')
class StrategyBackendTests(unittest.TestCase):
    """Strategies are built in the browser; the server must accept them unchanged."""

    @classmethod
    def setUpClass(cls):
        output = subprocess.run(['node', '--input-type=module', '-e', SCRIPT], cwd=ROOT,
                                check=True, capture_output=True, text=True).stdout
        cls.strategies = json.loads(output)

    def setUp(self):
        self.context = Flask(__name__).test_request_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_every_strategy_is_saved_as_a_plan_without_measured_steps(self):
        self.assertGreaterEqual(len(self.strategies), 7)
        for item in self.strategies:
            with self.subTest(strategy=item['id']):
                config, measured = _normalize_flow_config(item['config'], 'exemplo.com.br')
                self.assertFalse(measured)
                self.assertEqual(len(config['nodes']), len(item['config']['nodes']))
                self.assertEqual(len(config['edges']), len(item['config']['edges']))
                self.assertFalse(any(is_measured(node) for node in config['nodes']))
                self.assertTrue(all(node.get('spec') or node['type'] not in ('page', 'form') for node in config['nodes']))
                self.assertEqual(config.get('strategy_id'), item['id'])

    def test_server_validation_finds_no_blocking_issue(self):
        for item in self.strategies:
            with self.subTest(strategy=item['id']):
                config, _ = _normalize_flow_config(item['config'], 'exemplo.com.br')
                errors = [issue['code'] for issue in validate_flow_config(config, 'exemplo.com.br') if issue['severity'] == 'error']
                self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
