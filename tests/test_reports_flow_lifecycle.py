import unittest

from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config
from aicentralv2.cadu_connect.reports_flow_lifecycle import measured_nodes, normalize_spec
from aicentralv2.cadu_connect.reports_flow_matching import match_flow_node
from aicentralv2.cadu_connect.reports_flow_validation import is_measured, node_status, validate_flow_config

HOST = 'exemplo.com.br'


def page(node_id='landing', **extra):
    return {'id': node_id, 'type': 'page', 'title': 'Landing', 'x': 80, 'y': 80, **extra}


def conversion(**extra):
    return {'id': 'lead', 'type': 'conversion', 'title': 'Lead', 'path': '/obrigado', 'x': 300, 'y': 80, **extra}


def codes(issues, severity):
    return {issue['code'] for issue in issues if issue['severity'] == severity}


class NodeStatusTests(unittest.TestCase):
    def test_status_is_explicit_and_legacy_nodes_keep_their_meaning(self):
        self.assertEqual(node_status(page(path='/landing')), 'live')
        self.assertEqual(node_status(page()), 'ready')
        self.assertEqual(node_status(page(status='planned')), 'planned')
        self.assertEqual(node_status({'id': 's', 'type': 'source', 'title': 'Meta'}), 'live')

    def test_only_ready_or_live_steps_with_a_real_address_are_measured(self):
        self.assertTrue(is_measured(page(path='/landing')))
        self.assertTrue(is_measured(page(path='/landing', status='ready')))
        self.assertFalse(is_measured(page(path='/landing', status='planned')))
        self.assertFalse(is_measured(page(path='/landing', status='in_production')))
        self.assertFalse(is_measured(page(status='ready')))
        self.assertFalse(is_measured({'id': 's', 'type': 'source', 'title': 'Meta'}))
        self.assertEqual([node['id'] for node in measured_nodes([page(path='/a'), page('b', status='planned')])], ['landing'])


class PlannedValidationTests(unittest.TestCase):
    def test_planned_step_without_page_does_not_block_publication(self):
        config = {'nodes': [page(status='planned'), conversion()], 'edges': [{'from': 'landing', 'to': 'lead'}]}
        issues = validate_flow_config(config, HOST)
        self.assertEqual(codes(issues, 'error'), set())
        self.assertEqual(codes(issues, 'info'), {'planned_step'})

    def test_ready_step_without_page_still_blocks_and_points_to_planning(self):
        config = {'nodes': [page(status='ready'), conversion()], 'edges': [{'from': 'landing', 'to': 'lead'}]}
        issue = next(item for item in validate_flow_config(config, HOST) if item['code'] == 'unmapped_page')
        self.assertEqual(issue['severity'], 'error')
        self.assertIn('Planejado', issue['message'])

    def test_planned_event_without_name_is_not_an_error(self):
        event = {'id': 'cta', 'type': 'event', 'title': 'Clique no CTA', 'status': 'planned', 'x': 0, 'y': 0}
        config = {'nodes': [event, conversion()], 'edges': [{'from': 'cta', 'to': 'lead'}]}
        self.assertNotIn('unmapped_event', codes(validate_flow_config(config, HOST), 'error'))

    def test_planned_pages_do_not_count_as_duplicate_addresses(self):
        config = {'nodes': [page(path='/a'), page('copy', path='/a', status='planned'), conversion()],
                  'edges': [{'from': 'landing', 'to': 'lead'}, {'from': 'copy', 'to': 'lead'}]}
        self.assertNotIn('duplicate_page', codes(validate_flow_config(config, HOST), 'error'))


class PlannedConversionTests(unittest.TestCase):
    def test_measurement_with_only_planned_conversions_warns_without_blocking(self):
        config = {'nodes': [page(path='/'), conversion(status='planned')], 'edges': [{'from': 'landing', 'to': 'lead'}]}
        issues = validate_flow_config(config, HOST)
        self.assertEqual(codes(issues, 'error'), set())
        self.assertIn('planned_conversion', codes(issues, 'warning'))

    def test_a_flow_that_is_only_a_plan_does_not_warn(self):
        config = {'nodes': [page(status='planned'), conversion(status='planned')], 'edges': [{'from': 'landing', 'to': 'lead'}]}
        self.assertNotIn('planned_conversion', codes(validate_flow_config(config, HOST), 'warning'))

    def test_a_live_conversion_removes_the_warning(self):
        config = {'nodes': [page(path='/'), conversion(), conversion(id='lead2', status='planned', path='/obrigado-2')],
                  'edges': [{'from': 'landing', 'to': 'lead'}, {'from': 'landing', 'to': 'lead2'}]}
        self.assertNotIn('planned_conversion', codes(validate_flow_config(config, HOST), 'warning'))


class PlannedNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.context = Flask(__name__).test_request_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_flow_with_only_planned_steps_is_saved_and_has_no_measured_steps(self):
        spec = {'goal': 'Captar leads da campanha', 'suggested_path': '/oferta', 'due_date': '2026-10-15', 'owner': ''}
        config, measured = _normalize_flow_config(
            {'nodes': [page(status='planned', spec=spec), conversion(status='planned')], 'edges': []}, HOST)
        self.assertFalse(measured)
        self.assertEqual(config['nodes'][0]['status'], 'planned')
        self.assertEqual(config['nodes'][0]['spec'], {'goal': 'Captar leads da campanha', 'suggested_path': '/oferta',
                                                      'due_date': '2026-10-15'})
        self.assertNotIn('path', config['nodes'][0])

    def test_a_live_step_makes_the_flow_measurable(self):
        _, measured = _normalize_flow_config({'nodes': [page(path='/landing'), conversion(status='planned')], 'edges': []}, HOST)
        self.assertTrue(measured)

    def test_two_planned_steps_on_the_same_event_are_not_a_conflict(self):
        nodes = [conversion(status='planned', event_name='lead'), conversion(id='lead2', status='planned', event_name='lead')]
        _normalize_flow_config({'nodes': nodes, 'edges': []}, HOST)

    def test_notes_keep_text_and_a_clean_checklist_and_are_never_measured(self):
        note = {'id': 'nota', 'type': 'note', 'title': 'Combinados', 'description': 'Aprovar com o cliente', 'x': 500, 'y': 40,
                'checklist': [{'text': '  Aprovar   oferta ', 'done': True}, {'text': '   '}, {'text': 'Revisar LGPD', 'done': 'sim'}]}
        config, measured = _normalize_flow_config({'nodes': [note], 'edges': []}, HOST)
        self.assertFalse(measured)
        saved = config['nodes'][0]
        self.assertEqual(saved['checklist'], [{'text': 'Aprovar oferta', 'done': True}, {'text': 'Revisar LGPD', 'done': False}])
        self.assertEqual((saved['x'], saved['y'], saved['description']), (500, 40, 'Aprovar com o cliente'))
        self.assertNotIn('stage', saved)
        for invalid in ('item', [{'text': 3}], [{'text': 'x'}] * 31):
            with self.assertRaises(BadRequest):
                _normalize_flow_config({'nodes': [{**note, 'checklist': invalid}], 'edges': []}, HOST)

    def test_notes_survive_the_v2_document(self):
        note = {'id': 'nota', 'type': 'note', 'kind': 'annotation.note', 'title': 'Combinados', 'x': 0, 'y': 0, 'data': {'label': 'Combinados', 'url': ''},
                'checklist': [{'text': 'Aprovar', 'done': False}]}
        config, _ = _normalize_flow_config({'schema_version': 2, 'nodes': [note], 'edges': []}, HOST)
        self.assertEqual((config['nodes'][0]['type'], config['nodes'][0]['kind']), ('note', 'annotation.note'))
        self.assertEqual(config['nodes'][0]['checklist'], [{'text': 'Aprovar', 'done': False}])

    def test_forecast_numbers_are_kept_per_node_type_and_on_connections(self):
        nodes = [{'id': 'meta', 'type': 'source', 'title': 'Meta', 'x': 0, 'y': 0, 'forecast': {'visits': 10000, 'cost': 5000.5, 'value': 9}},
                 page(status='planned', forecast={'visits': 3}),
                 conversion(status='planned', forecast={'value': 120, 'cost': ''})]
        edges = [{'id': 'e1', 'from': 'meta', 'to': 'landing', 'forecast': {'rate': 100}}, {'id': 'e2', 'from': 'landing', 'to': 'lead', 'forecast': {'rate': ''}}]
        config, _ = _normalize_flow_config({'nodes': nodes, 'edges': edges}, HOST)
        by_id = {node['id']: node for node in config['nodes']}
        self.assertEqual(by_id['meta']['forecast'], {'visits': 10000.0, 'cost': 5000.5})
        self.assertNotIn('forecast', by_id['landing'])
        self.assertEqual(by_id['lead']['forecast'], {'value': 120.0})
        self.assertEqual(config['edges'][0]['forecast'], {'rate': 100.0})
        self.assertNotIn('forecast', config['edges'][1])
        for invalid in ({'rate': 120}, {'rate': -1}, {'rate': True}, {'rate': float('inf')}, 'alto'):
            with self.assertRaises(BadRequest):
                _normalize_flow_config({'nodes': nodes, 'edges': [{**edges[0], 'forecast': invalid}]}, HOST)

    def test_origins_keep_segment_and_media_with_closed_vocabularies(self):
        source = {'id': 'meta', 'type': 'source', 'title': 'Meta', 'x': 0, 'y': 0,
                  'segment': {'name': '  Remarketing   30 dias ', 'kind': 'remarketing', 'description': ''},
                  'media': {'objective': 'leads', 'utm': {'source': 'facebook', 'campaign': ''},
                            'creatives': [{'id': 'c1', 'name': 'Vídeo depoimento', 'format': 'video', 'status': 'aprovado', 'message': 'Oi'}],
                            'setup': [{'id': 's1', 'text': 'Pixel instalado', 'done': True}, {'id': 's2', 'text': '  '}]}}
        config, _ = _normalize_flow_config({'nodes': [source, page(status='planned', segment={'name': 'x'}, media={'objective': 'leads'})], 'edges': []}, HOST)
        meta, landing = config['nodes']
        self.assertEqual(meta['segment'], {'name': 'Remarketing 30 dias', 'kind': 'remarketing'})
        self.assertEqual(meta['media'], {'objective': 'leads', 'creatives': [{'id': 'c1', 'name': 'Vídeo depoimento', 'format': 'video', 'status': 'aprovado', 'message': 'Oi'}],
                                         'setup': [{'id': 's1', 'text': 'Pixel instalado', 'done': True}], 'utm': {'source': 'facebook'}})
        self.assertNotIn('segment', landing)
        self.assertNotIn('media', landing)
        for invalid in ({'objective': 'viral'}, {'creatives': [{'id': 'c', 'format': 'holograma'}]}, {'creatives': [{'id': 'c', 'format': 'video', 'status': 'publicado'}]},
                        {'utm': {'source': 'face book'}}, {'setup': ['texto']}, {'creatives': [{'id': 'c d', 'format': 'video'}]}):
            with self.assertRaises(BadRequest):
                _normalize_flow_config({'nodes': [{**source, 'media': invalid}], 'edges': []}, HOST)
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [{**source, 'segment': {'name': 'x', 'kind': 'vip'}}], 'edges': []}, HOST)

    def test_pages_may_live_on_other_domains_with_or_without_a_site(self):
        pages = [page(path='/a', host='cliente.com.br'), page('b', path='/b', host='outro.com')]
        for allowed in ('', 'cliente.com.br'):
            config, _ = _normalize_flow_config({'nodes': pages, 'edges': []}, allowed)
            self.assertEqual([node['host'] for node in config['nodes']], ['cliente.com.br', 'outro.com'])

    def test_pages_can_be_saved_by_full_url(self):
        config, measured = _normalize_flow_config({'nodes': [page(url='https://cliente.com.br/oferta?x=1')], 'edges': []}, '')
        node = config['nodes'][0]
        self.assertEqual((node['host'], node['path']), ('cliente.com.br', '/oferta'))
        self.assertNotIn('url', node)
        self.assertTrue(measured)

    def test_tags_are_trimmed_deduplicated_and_limited(self):
        config, _ = _normalize_flow_config({'nodes': [], 'edges': [], 'tags': ['  Black  Friday ', 'black friday', 'Leads', 'x' * 60]}, HOST)
        self.assertEqual(config['tags'], ['Black Friday', 'Leads', 'x' * 40])
        for invalid in ('Leads', ['ok', 3], ['t'] * 13):
            with self.assertRaises(BadRequest):
                _normalize_flow_config({'nodes': [], 'edges': [], 'tags': invalid}, HOST)
        self.assertNotIn('tags', _normalize_flow_config({'nodes': [], 'edges': []}, HOST)[0])

    def test_invalid_status_and_spec_are_rejected(self):
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [page(status='archived')], 'edges': []}, HOST)
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [page(status='planned', spec={'due_date': 'amanhã'})], 'edges': []}, HOST)
        with self.assertRaises(BadRequest):
            _normalize_flow_config({'nodes': [page(status='planned', path='sem-barra')], 'edges': []}, HOST)


class SpecTests(unittest.TestCase):
    def test_spec_keeps_known_fields_within_limits(self):
        self.assertIsNone(normalize_spec(None))
        self.assertIsNone(normalize_spec({'goal': ''}))
        self.assertEqual(normalize_spec({'cta': 'Quero uma proposta', 'unknown': 'x'}), {'cta': 'Quero uma proposta'})
        self.assertEqual(normalize_spec({'suggested_path': 'oferta'}), {'suggested_path': '/oferta'})
        for invalid in ({'cta': 'x' * 201}, {'due_date': '15/10/2026'}, {'goal': 3}, []):
            with self.assertRaises(BadRequest):
                normalize_spec(invalid)


class PlannedMatchingTests(unittest.TestCase):
    def test_events_never_match_a_planned_step_even_with_an_address(self):
        planned = page(path='/landing', status='planned')
        self.assertIsNone(match_flow_node([planned], '/landing', HOST, 'page_view'))
        live = page('live', path='/landing')
        self.assertEqual(match_flow_node([planned, live], '/landing', HOST, 'page_view')['id'], 'live')


if __name__ == '__main__':
    unittest.main()
