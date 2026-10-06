from unittest import TestCase, mock

from flask import Flask, render_template_string

from aicentralv2.cadu_workspace import routes as workspace_routes


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(workspace_routes.bp)
    return app


class WorkspaceShellLazyTest(TestCase):
    """The dock and credit meter cost a dozen queries: pay only when a template reads them."""

    def _render(self, template):
        app = _app()
        with app.test_request_context('/workspace/app/projetos'):
            from flask import session
            session.update(user_id=7, cliente_id=12)
            with mock.patch.object(workspace_routes, '_workspace_common_dock_items', return_value=[{'id': 'a'}]) as dock, \
                    mock.patch.object(workspace_routes, 'credit_position', return_value={'monthly_usage_percentage': 42.26}) as credit:
                html = render_template_string(template)
            return html, dock, credit

    def test_pages_that_do_not_read_the_shell_run_no_dock_or_credit_queries(self):
        _html, dock, credit = self._render('<p>pagina react</p>')
        dock.assert_not_called()
        credit.assert_not_called()

    def test_templates_that_read_the_shell_compute_it_once(self):
        template = ('{{ workspace_usage_percent() if workspace_usage_percent is callable else workspace_usage_percent|default(none) }}|'
                    '{{ (workspace_dock_items() if workspace_dock_items is callable else workspace_dock_items|default([]))|length }}|'
                    '{{ workspace_usage_percent() }}')
        html, dock, credit = self._render(template)
        self.assertEqual(html, '42.3|1|42.3')
        dock.assert_called_once()
        credit.assert_called_once()
