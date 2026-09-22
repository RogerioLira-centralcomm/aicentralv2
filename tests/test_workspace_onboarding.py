from pathlib import Path
from unittest import TestCase, mock

from tests.test_product_portals import _app


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceEnterpriseOnboardingTests(TestCase):
    def test_migration_registra_onboarding_sem_criar_novo_cliente(self):
        migration = (ROOT / 'migrations' / 'add_cadu_workspace_enterprise_onboarding.sql').read_text(encoding='utf-8')

        self.assertIn('cadu_workspace_onboarding', migration)
        self.assertIn('id_cliente BIGINT NOT NULL', migration)
        self.assertIn('UNIQUE (contato_id, id_cliente)', migration)
        self.assertIn('REFERENCES cx_clients(id)', migration)
        self.assertIn('REFERENCES cadu_ci_projetos(id)', migration)
        self.assertNotIn('CREATE TABLE IF NOT EXISTS tbl_cliente', migration)
        self.assertNotIn('INSERT INTO tbl_cliente', migration)

    def test_agencia_exibe_que_o_client_id_atual_continua_canonico(self):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=174, user_name='Apolo', family_csrf='test-csrf')

        with mock.patch('aicentralv2.cadu_workspace.routes._workspace_onboarding_table_available', return_value=True), \
             mock.patch('aicentralv2.cadu_workspace.routes._workspace_onboarding_record', return_value=None), \
             mock.patch('aicentralv2.db.obter_cliente_por_id', return_value={
                 'id_cliente': 174,
                 'nome_fantasia': 'Agência Horizonte',
                 'agencia_key': True,
                 'agencia_display': 'Sim',
             }):
            response = client.get('/workspace/onboarding', headers={'Host': 'workspace.centralcomm.media'})

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('O <strong>client_id atual da sua agência</strong> continua sendo a conta principal.', html)
        self.assertIn('Criar meu Workspace', html)
        self.assertIn('data-step="4"', html)
        self.assertIn('data-onboarding-mobile-story', html)
        for product in ('Workspace', 'Planner', 'Skills', 'Studio', 'Reports'):
            self.assertIn(f'data-story-name="{product}"', html)

    def test_fluxo_usa_o_client_id_da_sessao_como_limite_de_marca_e_projeto(self):
        source = (ROOT / 'aicentralv2' / 'cadu_workspace' / 'routes.py').read_text(encoding='utf-8')

        self.assertIn("client_id = int(session.get('cliente_id') or 0)", source)
        self.assertIn("crm_client_id=%s", source)
        self.assertIn("id_cliente=%s", source)
        self.assertIn("'agency_client_id': client_id if form['operation_type'] == 'agency' else None", source)
        self.assertIn("tbl_cliente_agencia", (ROOT / 'migrations' / 'create_tbl_cliente_agencia.py').read_text(encoding='utf-8'))

    def test_email_de_onboarding_usa_a_ilustracao_publicada_e_contexto_do_usuario(self):
        template = (ROOT / 'aicentralv2' / 'templates' / 'emails' / 'externos' / 'workspace-onboarding-concluido.html').read_text(encoding='utf-8')
        service = (ROOT / 'aicentralv2' / 'services' / 'onboarding_comercial.py').read_text(encoding='utf-8')

        self.assertIn('welcome.png', service)
        self.assertNotIn('workspace-context.png', service)
        for value in ('{{ empresa }}', '{{ marca }}', '{{ projeto }}', '{{ primeiro_nome }}', 'Conversas', 'Planner', 'Studio', 'Skills', 'Reports'):
            self.assertIn(value, template)

if __name__ == '__main__':
    import unittest
    unittest.main()
