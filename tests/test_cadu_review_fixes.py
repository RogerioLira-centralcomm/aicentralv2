from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_family import repository
from aicentralv2 import db
from aicentralv2.cadu_family.chat import lock_organization_generation
from werkzeug.exceptions import Conflict


class SchemaCompatibilityTest(TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_missing_grants_table_only_returns_own_organization(self):
        with self.app.test_request_context('/'), mock.patch.object(repository, 'rows', side_effect=[
            [{'available': False}], [{'id': 12, 'name': 'Own', 'role': 'member'}],
        ]) as rows:
            result = repository.clients({'organization_id': 12, 'id': 7, 'user_type': 'client'})
            self.assertEqual(result[0]['id'], 12)
            sql, params = rows.call_args.args
            self.assertNotIn('cadu_family_client_access', sql)
            self.assertIn('id_cliente = %s', sql)
            self.assertEqual(params, ('member', 12))

    def test_missing_mapping_does_not_invent_correspondences(self):
        with self.app.test_request_context('/'), mock.patch.object(repository, 'rows', return_value=[{'available': False}]) as rows:
            self.assertEqual(repository.entity_links(12), [])
            rows.assert_called_once()

    def test_missing_sidecar_history_still_checks_user_and_client(self):
        with self.app.test_request_context('/'), mock.patch.object(repository, 'rows', side_effect=[
            [{'available': False}], [],
        ]) as rows:
            repository.conversation_history({'id': 7, 'organization_id': 12}, 24)
            sql, params = rows.call_args.args
            self.assertNotIn('JOIN', sql)
            self.assertEqual(params[:2], (7, 24))
            self.assertIn('titulo ILIKE %s', sql)
            self.assertIn('status = ANY(%s)', sql)

    def test_schema_failure_does_not_fallback_to_a_grant(self):
        with self.app.test_request_context('/'), mock.patch.object(repository, 'rows', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                repository.clients({'organization_id': 12, 'id': 7})

    def test_schema_detection_is_cached_for_one_request_only(self):
        with mock.patch.object(repository, 'rows', return_value=[{'available': True}]) as rows:
            with self.app.test_request_context('/'):
                self.assertTrue(repository.family_table_available('cadu_family_client_access'))
                self.assertTrue(repository.family_table_available('cadu_family_client_access'))
                self.assertEqual(rows.call_count, 1)
            with self.app.test_request_context('/'):
                repository.family_table_available('cadu_family_client_access')
                self.assertEqual(rows.call_count, 2)

    def test_reset_update_reports_whether_token_was_written(self):
        for count in (0, 1):
            connection = mock.MagicMock()
            connection.cursor.return_value.__enter__.return_value.rowcount = count
            with mock.patch.object(db, 'get_db', return_value=connection):
                self.assertEqual(db.atualizar_reset_token('user@example.test', 'token', 'date'), bool(count))
            connection.commit.assert_called_once()

    def test_generation_admission_locks_organization_before_checking_runs(self):
        cursor = mock.MagicMock()
        cursor.fetchone.return_value = {'id': 'running'}
        with self.assertRaises(Conflict):
            lock_organization_generation(cursor, 12)
        calls = cursor.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[0].args[0])
        self.assertIn('c.organization_id = %s', calls[1].args[0])
        self.assertEqual(calls[1].args[1], (12,))

    def test_generation_admission_allows_idle_organization(self):
        cursor = mock.MagicMock()
        cursor.fetchone.return_value = None
        lock_organization_generation(cursor, 12)

    def test_limits_count_every_source_without_name_based_merging(self):
        refs = ['ci:1', 'projects:1', 'studio:1']
        self.assertEqual(repository.count_distinct_entities(refs, []), 3)
        links = [{'ref': 'projects:1', 'canonical_ref': 'ci:1'},
                 {'ref': 'studio:1', 'canonical_ref': 'projects:1'}]
        self.assertEqual(repository.count_distinct_entities(refs, links), 1)
        links.append({'ref': 'ci:1', 'canonical_ref': 'studio:1'})
        self.assertEqual(repository.count_distinct_entities(refs, links), 1)

    def test_limit_query_scopes_each_source_to_selected_client(self):
        with mock.patch.object(repository, 'rows', return_value=[{'ref': 'ci:1'}, {'ref': 'studio:1'}]) as rows, \
             mock.patch.object(repository, 'entity_links', return_value=[]):
            self.assertEqual(repository.active_entity_count(12), 2)
            self.assertEqual(rows.call_args.args[1], (12, 12, 12))
            for source in ('cadu_ci_projetos', 'cadu_projetos', 'cx_clients'):
                self.assertIn(source, rows.call_args.args[0])
