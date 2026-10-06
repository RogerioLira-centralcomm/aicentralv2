from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace import routes as workspace_routes


class RequestMemoTest(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test', TESTING=True)

    def _counted(self, calls, value):
        def read(client_id, *args, **kwargs):
            calls.append(client_id)
            return value
        read.__name__ = 'probe'
        return read

    def test_get_request_reads_once_and_hands_out_independent_copies(self):
        calls = []
        wrapped = workspace_routes._request_memo(self._counted(calls, [{'id': 1, 'tags': ['a']}]))
        with self.app.test_request_context('/x'):
            first = wrapped(12)
            first[0]['tags'].append('mutated')
            second = wrapped(12)
            other_client = wrapped(13)
        self.assertEqual(calls, [12, 13])
        self.assertEqual(second, [{'id': 1, 'tags': ['a']}])
        self.assertEqual(other_client, second)

    def test_writes_are_never_served_from_the_cache(self):
        calls = []
        wrapped = workspace_routes._request_memo(self._counted(calls, []))
        with self.app.test_request_context('/x', method='POST'):
            wrapped(12)
            wrapped(12)
        self.assertEqual(calls, [12, 12])

    def test_injected_identity_data_bypasses_the_cache(self):
        calls = []
        wrapped = workspace_routes._request_memo(self._counted(calls, []))
        with self.app.test_request_context('/x'):
            wrapped(12, identity_brands=[{'id': 1}])
            wrapped(12, identity_brands=[{'id': 2}])
        self.assertEqual(calls, [12, 12])

    def test_outside_a_request_nothing_is_cached(self):
        calls = []
        wrapped = workspace_routes._request_memo(self._counted(calls, []))
        wrapped(12)
        wrapped(12)
        self.assertEqual(calls, [12, 12])

    def test_project_brand_links_are_read_once_per_get(self):
        with self.app.test_request_context('/x'), \
                mock.patch.object(workspace_routes.family_repository, 'project_brand_links', return_value=[{'project_ref': 'ci:1'}]) as read:
            workspace_routes._project_brand_links(12)
            workspace_routes._project_brand_links(12)
        read.assert_called_once_with(12)
