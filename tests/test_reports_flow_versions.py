from unittest import TestCase
from unittest.mock import patch

from flask import Flask
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from aicentralv2.cadu_connect import reports_flow, reports_flow_versions as versions


class FlowVersionTests(TestCase):
    def setUp(self):
        self.context = Flask(__name__).app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.scope = {'organization_id': 10, 'client_id': 20}

    def test_revision_is_required_and_not_boolean(self):
        for value in [None, True, '2', 0, -1]:
            with self.assertRaises(BadRequest):
                versions.expected_revision({'expected_revision': value})
        self.assertEqual(versions.expected_revision({'expected_revision': 2}), 2)

    @patch.object(versions, '_rows')
    def test_draft_save_never_updates_active_config_and_compares_revision(self, rows):
        rows.return_value = [{'draft_revision': 4}]
        result = versions.save_draft('flow', self.scope, 3, 'Edited', {'nodes': []})
        sql, params = rows.call_args.args
        self.assertIn('draft_config=%s::jsonb', sql)
        self.assertNotIn('SET config=', sql)
        self.assertNotIn("status <> 'published'", sql)
        self.assertIn('AND draft_revision=%s', sql)
        self.assertEqual(params[-3:], (10, 20, 3))
        self.assertEqual(result['draft_revision'], 4)

    @patch.object(versions, '_rows', return_value=[])
    def test_concurrent_write_is_conflict(self, rows):
        with self.assertRaises(Conflict):
            versions.save_draft('flow', self.scope, 3, 'Edited', {})

    @patch.object(versions, 'sync_published_steps')
    @patch.object(versions, '_rows')
    def test_publish_locks_exact_client_revision_and_preserves_snapshot(self, rows, sync):
        rows.side_effect = [
            [{'draft_revision': 4, 'draft_config': {'nodes': []}, 'name': 'Flow'}],
            [{'revision': 4}], [{'published_revision': 4}],
        ]
        self.assertEqual(versions.publish_draft('flow', self.scope, 4, 7)['published_revision'], 4)
        lock_sql, lock_params = rows.call_args_list[0].args
        self.assertIn('FOR UPDATE', lock_sql)
        self.assertEqual(lock_params, ('flow', 10, 20))
        snapshot_sql, snapshot_params = rows.call_args_list[1].args
        self.assertIn('ON CONFLICT(flow_id,revision) DO NOTHING', snapshot_sql)
        self.assertEqual(snapshot_params[:4], ('flow', 10, 20, 4))
        self.assertIn('SET config=draft_config', rows.call_args_list[2].args[0])

    @patch.object(versions, '_rows')
    def test_stale_or_other_client_cannot_publish(self, rows):
        rows.return_value = [{'draft_revision': 5}]
        with self.assertRaises(Conflict):
            versions.publish_draft('flow', self.scope, 4, 7)
        self.assertEqual(rows.call_count, 1)
        rows.reset_mock()
        rows.return_value = []
        with self.assertRaises(NotFound):
            versions.publish_draft('flow', self.scope, 4, 7)
        self.assertEqual(rows.call_count, 1)

    def test_visual_fields_and_integer_step_survive_roundtrip(self):
        config = {'schema_version': 1, 'nodes': [
            {'id': 'a', 'type': 'page', 'path': '/', 'stepId': 3,
             'campaign_id': 5, 'appearance': {'color': '#ffffff'},
             'description': 'Landing', 'width': 172, 'height': 116},
            {'id': 'b', 'type': 'conversion', 'path': '/thanks'},
        ], 'edges': [{'id': 'e', 'from': 'a', 'to': 'b', 'from_port': 'out', 'kind': 'normal'}]}
        normalized, measured = reports_flow._normalize_flow_config(config, 'example.com')
        self.assertTrue(measured)
        self.assertEqual(normalized['nodes'][0]['stepId'], 3)
        self.assertEqual(normalized['nodes'][0]['appearance'], {'color': '#ffffff'})
        self.assertEqual(normalized['edges'][0]['from_port'], 'out')
        self.assertEqual(reports_flow._normalize_flow_config(normalized, 'example.com')[0], normalized)

    def test_duplicate_edges_and_nonfinite_metadata_are_rejected(self):
        nodes = [{'id':'a','type':'source'}, {'id':'b','type':'source'}]
        with self.assertRaises(BadRequest):
            reports_flow._normalize_flow_config({'nodes':nodes,'edges':[
                {'id':'e','from':'a','to':'b'},{'id':'e','from':'b','to':'a'}]}, 'example.com')
        with self.assertRaises(BadRequest):
            reports_flow._normalize_flow_config({'nodes':nodes,'viewport':{'zoom':float('nan')}}, 'example.com')
