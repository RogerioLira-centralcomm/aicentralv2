from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase


def load_pure_module(name):
    path = Path(__file__).resolve().parents[1] / 'aicentralv2' / 'cadu_connect' / f'{name}.py'
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = load_pure_module('reports_flow_schema')
validation = load_pure_module('reports_flow_validation')


class FlowSchemaV2Tests(TestCase):
    def test_v1_upgrade_preserves_collector_fields_and_is_idempotent(self):
        original = {'nodes': [
            {'id': 'page', 'type': 'page', 'title': 'Inicial', 'path': '/', 'x': 20, 'y': 30},
            {'id': 'sale', 'type': 'conversion', 'title': 'Venda', 'path': '/obrigado', 'x': 240, 'y': 30},
        ], 'edges': [{'id': 'edge', 'from': 'page', 'to': 'sale', 'label': 'Próximo'}]}
        upgraded = schema.migrate_v1_to_v2(original)
        self.assertEqual(upgraded['schema_version'], 2)
        self.assertEqual(upgraded['nodes'][0]['kind'], 'page.generic')
        self.assertEqual(upgraded['nodes'][0]['path'], '/')
        self.assertEqual(upgraded['edges'][0]['source'], 'page')
        self.assertEqual(schema.migrate_v1_to_v2(upgraded), upgraded)
        self.assertEqual(original['nodes'][0].get('kind'), None)

    def test_pure_v2_input_gets_safe_legacy_projection(self):
        config = {'schema_version': 2, 'nodes': [
            {'id': 'page', 'kind': 'page.generic', 'position': {'x': 20, 'y': 30},
             'data': {'label': 'Inicial', 'url': '/'}},
        ], 'edges': []}
        projected = schema.legacy_projection(config)
        self.assertEqual(projected['nodes'][0]['type'], 'page')
        self.assertEqual(projected['nodes'][0]['path'], '/')

    def test_publication_requires_real_mapping_and_conversion(self):
        config = {'nodes': [
            {'id': 'a', 'type': 'page', 'title': 'Landing', 'path': '/configurar-abcd'},
            {'id': 'b', 'type': 'conversion', 'title': 'Compra', 'path': '/obrigado'},
        ], 'edges': [{'from': 'a', 'to': 'b'}]}
        issues = validation.validate_flow_config(config)
        self.assertIn('unmapped_page', {issue['code'] for issue in issues})
        config['nodes'][0]['path'] = '/landing'
        self.assertEqual([issue for issue in validation.validate_flow_config(config) if issue['severity'] == 'error'], [])

    def test_duplicate_page_path_is_blocked_at_publish(self):
        config = {'nodes': [
            {'id': 'first', 'type': 'page', 'title': 'Entrada', 'path': '/'},
            {'id': 'second', 'type': 'page', 'title': 'Entrada duplicada', 'host': 'site.example', 'path': '/'},
            {'id': 'lead', 'type': 'conversion', 'title': 'Lead', 'path': '/obrigado'},
        ], 'edges': [{'from': 'first', 'to': 'lead'}, {'from': 'second', 'to': 'lead'}]}
        issues = validation.validate_flow_config(config, 'site.example')
        self.assertIn('duplicate_page', {issue['code'] for issue in issues})
