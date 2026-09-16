from unittest import TestCase

from flask import Flask, abort

from aicentralv2.error_pages import register_error_pages


def _app():
    app = Flask(__name__, template_folder="../aicentralv2/templates", static_folder="../aicentralv2/static")
    app.config.update(TESTING=False)
    register_error_pages(app)

    @app.get('/private')
    def private():
        abort(403)

    @app.get('/broken')
    def broken():
        raise RuntimeError('internal-only detail')

    return app


class ErrorPagesTest(TestCase):
    def test_html_error_screen_has_no_application_navigation(self):
        response = _app().test_client().get('/private')

        self.assertEqual(response.status_code, 403)
        html = response.get_data(as_text=True)
        self.assertIn('ACCESS_DENIED', html)
        self.assertIn('Código de suporte', html)
        self.assertNotIn('CentralX', html)
        self.assertNotIn('<nav', html)


    def test_unexpected_error_is_classified_without_exposing_exception_text(self):
        response = _app().test_client().get('/broken')

        self.assertEqual(response.status_code, 500)
        html = response.get_data(as_text=True)
        self.assertIn('INTERNAL_ERROR', html)
        self.assertNotIn('internal-only detail', html)


    def test_api_errors_are_machine_readable(self):
        app = _app()

        @app.get('/api/missing')
        def missing():
            abort(404)

        response = app.test_client().get('/api/missing')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error_class'], 'RESOURCE_NOT_FOUND')
