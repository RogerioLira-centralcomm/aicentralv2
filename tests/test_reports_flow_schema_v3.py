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


class FlowSchemaV3Tests(TestCase):
    def test_v1_document_becomes_canonical_and_keeps_collector_fields(self):
        original = {'nodes': [
            {'id': 'page', 'type': 'page', 'title': 'Inicial', 'path': '/', 'x': 20, 'y': 30},
            {'id': 'sale', 'type': 'conversion', 'title': 'Venda', 'path': '/obrigado', 'x': 240, 'y': 30},
        ], 'edges': [{'id': 'edge', 'from': 'page', 'to': 'sale', 'label': 'Próximo'}]}
        document = schema.to_v3(original)
        self.assertEqual(document['schema_version'], 3)
        self.assertEqual(document['nodes'][0], {'id': 'page', 'type': 'page', 'title': 'Inicial', 'path': '/', 'x': 20, 'y': 30, 'kind': 'page.generic'})
        self.assertEqual(document['edges'][0], {'id': 'edge', 'from': 'page', 'to': 'sale', 'label': 'Próximo', 'variant': 'direct'})
        self.assertEqual(schema.to_v3(document), document)
        self.assertIsNone(original['nodes'][0].get('kind'))

    def test_v2_mirrored_fields_are_folded_into_one_shape(self):
        config = {'schema_version': 2, 'viewport': {'x': 0, 'y': 0, 'zoom': 1}, 'nodes': [
            {'id': 'page', 'kind': 'page.generic', 'position': {'x': 20, 'y': 30},
             'data': {'label': 'Inicial', 'url': '/', 'tracking': {'event': ''}}},
            {'id': 'lead', 'type': 'conversion', 'kind': 'conversion.lead', 'title': 'Lead', 'x': 1, 'y': 2,
             'data': {'label': 'Lead', 'url': '', 'tracking': {'event': 'lead_enviado'}}},
        ], 'edges': [{'id': 'e', 'source': 'page', 'target': 'lead', 'source_handle': 'right-out', 'target_handle': 'left-in'},
                     {'id': 'link', 'from': 'page', 'to': 'lead', 'kind': 'site_link'}]}
        document = schema.to_v3(config)
        page, lead = document['nodes']
        self.assertEqual((page['type'], page['title'], page['x'], page['y'], page['path']), ('page', 'Inicial', 20, 30, '/'))
        self.assertEqual(lead['event_name'], 'lead_enviado')
        self.assertTrue(all('data' not in node and 'position' not in node for node in document['nodes']))
        self.assertEqual(document['edges'][0], {'id': 'e', 'from': 'page', 'to': 'lead', 'from_port': 'right-out', 'to_port': 'left-in', 'variant': 'direct'})
        self.assertEqual(document['edges'][1]['variant'], 'planned')
        self.assertEqual(document['viewport'], {'x': 0, 'y': 0, 'zoom': 1})

    def test_placeholder_paths_become_planned_steps(self):
        document = schema.to_v3({'nodes': [
            {'id': 'a', 'type': 'page', 'title': 'Landing', 'path': '/configurar-abcd'},
            {'id': 'b', 'type': 'page', 'title': 'Pronta', 'path': '/configurar-x', 'status': 'ready'},
            {'id': 'c', 'type': 'conversion', 'title': 'Compra', 'path': '/obrigado'},
        ], 'edges': [{'from': 'a', 'to': 'c'}, {'from': 'b', 'to': 'c'}]})
        a, b, _ = document['nodes']
        self.assertEqual((a.get('path'), a['status']), (None, 'planned'))
        self.assertEqual((b.get('path'), b['status']), (None, 'ready'))
        codes = {(issue['code'], issue.get('node_id')) for issue in validation.validate_flow_config(document)}
        self.assertIn(('planned_step', 'a'), codes)
        self.assertIn(('unmapped_page', 'b'), codes)

    def test_duplicate_page_path_is_blocked_at_publish(self):
        config = {'nodes': [
            {'id': 'first', 'type': 'page', 'title': 'Entrada', 'path': '/'},
            {'id': 'second', 'type': 'page', 'title': 'Entrada duplicada', 'host': 'site.example', 'path': '/'},
            {'id': 'lead', 'type': 'conversion', 'title': 'Lead', 'path': '/obrigado'},
        ], 'edges': [{'from': 'first', 'to': 'lead'}, {'from': 'second', 'to': 'lead'}]}
        issues = validation.validate_flow_config(config, 'site.example')
        self.assertIn('duplicate_page', {issue['code'] for issue in issues})
