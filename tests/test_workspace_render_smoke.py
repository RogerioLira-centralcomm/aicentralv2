"""Every Workspace account page renders without a database and sends only public fields."""
import json
import re
from contextlib import ExitStack
from unittest import TestCase, mock

from tests.test_product_portals import _app

R = 'aicentralv2.cadu_workspace.routes.'
ACCOUNT = {
    'current_user': {'id_contato_cliente': 7, 'nome_completo': 'Apolo Lira', 'email': 'apolo@example.com',
                     'telefone': 'None', 'wasender_api_key_mask': 'sk-***', 'id_centralx': 'x-1'},
    'organization': {'nome_fantasia': 'Agência Teste', 'razao_social': 'Agência Teste LTDA', 'cnpj': '00.000.000/0001-00',
                     'margem_cc': '12', 'fee': 3, 'nota_executivo_vendas': 'interno', 'observacoes_comerciais_adicionais': 'interno'},
    'people': [{'id_contato_cliente': 7, 'nome_completo': 'Apolo Lira', 'email': 'apolo@example.com', 'status': True,
                'user_type': 'admin', 'wasender_api_key_mask': 'sk-***'}],
    'states': [{'sigla': 'MG', 'descricao': 'Minas Gerais', 'id_centralx': 'x-2'}],
    'invites': [], 'plan': {'plan_definition_name': 'Free'}, 'credit': {}, 'position': {'usage_percentage': 12},
    'movements': [], 'credit_additions': [], 'purchases': [], 'space': {}, 'insights': {},
}


class WorkspaceAccountRenderTest(TestCase):
    def render(self, path):
        with ExitStack() as stack:
            stack.enter_context(mock.patch(R + '_php_account_data', side_effect=lambda _client, *_args, **_kw: json.loads(json.dumps(ACCOUNT))))
            stack.enter_context(mock.patch(R + '_workspace_settings_data', return_value={}))
            stack.enter_context(mock.patch(R + '_workspace_projects', return_value=[]))
            stack.enter_context(mock.patch(R + '_workspace_brands', return_value=[]))
            stack.enter_context(mock.patch(R + '_workspace_common_dock_items', return_value=[]))
            stack.enter_context(mock.patch(R + '_workspace_billing_data', return_value={'summary': {}, 'invoices': []}))
            stack.enter_context(mock.patch(R + '_workspace_integration_data', return_value={'accounts': [], 'connected_count': 0}))
            stack.enter_context(mock.patch(R + '_workspace_sidebar_payload', return_value={'agency': {}, 'brands': [], 'projects': []}))
            stack.enter_context(mock.patch('aicentralv2.db.obter_plan_definitions', return_value=[]))
            client = _app().test_client()
            with client.session_transaction() as session:
                session.update(user_id=7, cliente_id=12, organization_id=44, user_name='Apolo')
            return client.get(path, headers={'Host': 'workspace.centralcomm.media'})

    def test_every_account_section_renders_with_public_fields_only(self):
        for path, section in (('/perfil', 'perfil'), ('/agencia', 'agencia'), ('/equipe', 'equipe'), ('/plano', 'planos'),
                              ('/uso', 'uso'), ('/creditos', 'creditos'), ('/faturas', 'faturamento'), ('/integracoes', 'integracoes')):
            with self.subTest(path=path):
                response = self.render(path)
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'"section": "{section}"', html)
                boot = json.loads(re.search(r'<script id="cadu-conversations-v2-bootstrap" type="application/json">(.*?)</script>', html, re.S).group(1))
                account = boot['account']
                for secret in ('wasender_api_key_mask', 'margem_cc', 'fee', 'nota_executivo_vendas', 'observacoes_comerciais_adicionais', 'id_centralx'):
                    self.assertNotIn(secret, json.dumps(account), f'{secret} em {path}')
                self.assertEqual(account['current_user']['telefone'], '')
                self.assertEqual(account['organization']['nome_fantasia'], 'Agência Teste')
                self.assertEqual(account['states'], [{'sigla': 'MG', 'descricao': 'Minas Gerais'}])

    def test_retired_dashboard_redirects_home(self):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name='Apolo')
        response = client.get('/workspace/app/visao-geral', headers={'Host': 'workspace.centralcomm.media'})
        self.assertEqual(response.status_code, 308)
        self.assertTrue(response.headers['Location'].endswith('/app'))
