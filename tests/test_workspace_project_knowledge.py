from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


class WorkspaceProjectKnowledgeTest(TestCase):
    def _client(self, token='known-token'):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf=token)
        return client

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    def test_query_requires_the_session_csrf_token(self, _project):
        response = self._client().post('/workspace/api/projetos/p-1/consultar', json={'query': 'marca'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['error'], 'Atualize a página e tente novamente.')

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_query_returns_only_citable_source_and_excerpt(self, get_db, _project):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{'titulo': 'Guia de marca', 'conteudo': 'Tom direto e seguro.', 'score': 0.9}]
        get_db.return_value = connection
        response = self._client().post(
            '/workspace/api/projetos/p-1/consultar',
            json={'query': 'tom de voz'}, headers={'X-CSRF-Token': 'known-token'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'query': 'tom de voz', 'result_count': 1,
            'results': [{'source': 'Guia de marca', 'excerpt': 'Tom direto e seguro.'}],
        })
        sql, params = cursor.execute.call_args.args
        self.assertIn('id_cliente = %s', sql)
        self.assertEqual(params[1:3], ('p-1', 12))
