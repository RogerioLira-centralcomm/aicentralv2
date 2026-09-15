"""Isolated HTTP contract test: actual route function and actual auth decorator.

No database, production app initialization or credentials are loaded.
"""
import ast
from pathlib import Path
import runpy
import unittest
from flask import Flask, Blueprint, current_app, send_from_directory, session

ROOT = Path(__file__).resolve().parents[1]


class CaduPrototypeRoutesTest(unittest.TestCase):
    def setUp(self):
        auth = runpy.run_path(str(ROOT / 'aicentralv2/auth.py'))
        source = ast.parse((ROOT / 'aicentralv2/integration_settings_routes.py').read_text())
        registrar = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'register_integration_settings_routes')
        scope = dict(Path=Path, current_app=current_app, send_from_directory=send_from_directory,
                     session=session, admin_required=auth['admin_required'],
                     admin_required_api=auth['admin_required_api'], render_template=lambda name, **kwargs: name)
        exec(compile(ast.Module(body=[registrar], type_ignores=[]), '<route-contract>', 'exec'), scope)
        app = Flask('cadu-route-test', root_path=str(ROOT / 'aicentralv2'))
        app.secret_key = 'local-test-only'
        app.add_url_rule('/login', 'login', lambda: 'login')
        app.add_url_rule('/', 'index', lambda: 'index')
        bp = Blueprint('parametros', __name__, url_prefix='/parametros')
        scope['register_integration_settings_routes'](bp)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def login(self, role):
        with self.client.session_transaction() as s:
            s['user_id'] = 1
            s['user_type'] = role

    def test_unauthenticated_and_non_admin_are_blocked(self):
        path = '/parametros/prototipos-cadu/cadu-finance.js'
        self.assertEqual(self.client.get(path).status_code, 302)
        self.login('client')
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_admin_pages_and_assets(self):
        self.login('admin')
        self.assertEqual(self.client.get('/parametros/prototipos-cadu').status_code, 200)
        for filename in ['cadu-platform.html', 'cadu-commercial-model.html', 'cadu-ui.css',
                         'cadu-finance.js', 'cadu-app.js', 'cadu-commercial.js',
                         'cadu-components-v2.html', 'brand-assets/studio/app-icon-192.png']:
            with self.subTest(filename=filename):
                with self.client.get('/parametros/prototipos-cadu/' + filename) as response:
                    self.assertEqual(response.status_code, 200)

    def test_missing_and_traversal_assets(self):
        self.login('admin')
        self.assertEqual(self.client.get('/parametros/prototipos-cadu/not-found.html').status_code, 404)
        self.assertEqual(self.client.get('/parametros/prototipos-cadu/../../aicentralv2/config.py').status_code, 404)

    def test_parameter_menu_links_to_existing_artifacts(self):
        template = (ROOT / 'aicentralv2/templates/parametros/prototipos_cadu.html').read_text()
        import re
        files = re.findall(r"filename='([^']+)'\)", template)
        self.assertGreaterEqual(len(files), 6)
        for name in files:
            self.assertTrue((ROOT / 'output/mockups' / name).is_file(), name)
        self.assertIn('parametros.prototipos_cadu', (ROOT / 'aicentralv2/templates/base_erp.html').read_text())

    def test_catalog_renders_all_products_identities_and_archived_htmls(self):
        from jinja2 import Environment, ChoiceLoader, DictLoader, FileSystemLoader
        env = Environment(loader=ChoiceLoader([
            DictLoader({'base_erp.html': '{% block content %}{% endblock %}'}),
            FileSystemLoader(str(ROOT / 'aicentralv2/templates')),
        ]), autoescape=True)
        env.globals['url_for'] = lambda endpoint, filename: '/parametros/prototipos-cadu/' + filename
        files = sorted(p.name for p in (ROOT / 'output/mockups').glob('*.html'))
        html = env.get_template('parametros/prototipos_cadu.html').render(prototype_files=files)
        for product in ['workspace', 'studio', 'connect', 'skills', 'planner']:
            self.assertIn('cadu-platform.html#' + product, html)
            self.assertIn('cadu-family-design-system.html#' + product, html)
        for filename in files:
            self.assertIn('/parametros/prototipos-cadu/' + filename, html)


if __name__ == '__main__':
    unittest.main()
