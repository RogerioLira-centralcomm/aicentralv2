import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from aicentralv2.creative_media.studio_projects import save, read, listing, RevisionConflict


class ProjectRevisionsTest(unittest.TestCase):
    def test_immutable_revisions_and_brand_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = save(root / 'a', {'name': 'Campanha', 'clips': []})
            second = save(root / 'a', {'name': 'Versão final', 'clips': ['one']}, first['id'], 1)
            self.assertEqual(second['revision'], 2)
            self.assertEqual(read(root / 'a', first['id'], 1)['document']['clips'], [])
            self.assertEqual(read(root / 'a', first['id'])['document']['clips'], ['one'])
            self.assertEqual(len(listing(root / 'a')), 1)
            with self.assertRaises(ValueError):
                read(root / 'b', first['id'])

    def test_concurrent_edit_never_silently_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = save(root, {'name': 'Campanha'})
            def update(name):
                try:
                    return save(root, {'name': name}, first['id'], 1)['revision']
                except RevisionConflict:
                    return 'conflict'
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(update, ['A', 'B']))
            self.assertCountEqual(results, [2, 'conflict'])
            self.assertEqual(read(root, first['id'])['latest_revision'], 2)

class ProjectRoutesTest(unittest.TestCase):
    def test_routes_auth_csrf_revision_and_conflict(self):
        from flask import Flask, Blueprint, request, jsonify
        from unittest.mock import patch
        from aicentralv2.creative_media.studio import register_studio_routes
        with tempfile.TemporaryDirectory() as directory:
            app = Flask(__name__, instance_path=directory)
            app.secret_key = 'test-only'
            bp = Blueprint('projects_test', __name__)
            register_studio_routes(bp)
            app.register_blueprint(bp)
            client = app.test_client()
            url = '/api/format-lab/studio/projects'
            self.assertEqual(client.get(url).status_code, 401)
            with client.session_transaction() as sess:
                sess.update(user_id=7, user_type='admin', trocr_csrf_token='test-token')
            self.assertEqual(client.post(url).status_code, 403)
            def execute(fn):
                try:
                    return fn()
                except ValueError as error:
                    return jsonify(success=False, error=str(error)), 400
            http = (execute, lambda: request.get_json(), lambda data: jsonify(success=True, data=data), None)
            headers = {'X-Trocr-CSRF-Token': 'test-token'}
            with patch('aicentralv2.creative_format_lab.swap_routes._http', return_value=http):
                first = client.post(url, json={'client_id': 10, 'document': {'name': 'Campanha'}}, headers=headers)
                self.assertEqual(first.status_code, 200, first.json)
                ident = first.json['data']['id']
                edit = {'client_id': 10, 'document': {'name': 'Final'}, 'expected_revision': 1}
                self.assertEqual(client.post(f'{url}/{ident}', json=edit, headers=headers).status_code, 200)
                self.assertEqual(client.post(f'{url}/{ident}', json=edit, headers=headers).status_code, 409)
                self.assertEqual(client.get(f'{url}/{ident}?client_id=10&revision=1').json['data']['document']['name'], 'Campanha')
                self.assertEqual(client.get(f'{url}/{ident}?client_id=11').status_code, 400)
