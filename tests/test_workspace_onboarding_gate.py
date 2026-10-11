from unittest import TestCase, mock

from flask import session

from tests.test_product_portals import _app

R = 'aicentralv2.cadu_workspace.routes.'


def _gate(path='/app', accept='text/html', table=True, record=None, org=False, **sess):
    from aicentralv2.cadu_workspace.routes import require_workspace_onboarding
    with _app().test_request_context(path, headers={'Accept': accept}), \
         mock.patch(R + '_workspace_onboarding_table_available', return_value=table), \
         mock.patch(R + '_workspace_onboarding_record', return_value=record), \
         mock.patch(R + '_workspace_org_onboarded', return_value=org):
        session.update(user_id=7, cliente_id=174, **sess)
        response = require_workspace_onboarding()
        return response, session.get('workspace_onboarded')


class WorkspaceOnboardingGateTests(TestCase):
    def test_conta_antiga_sem_registro_vai_para_o_onboarding(self):
        for path in ('/app', '/workspace/app/projetos', '/projetos', '/marcas', '/equipe'):
            response, flag = _gate(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.headers['Location'].endswith('/workspace/onboarding'))
            self.assertIsNone(flag)

    def test_nao_barra_quem_ja_concluiu_nem_membros_de_conta_ja_configurada(self):
        for kwargs in ({'record': {'id': 1}}, {'org': True}):
            response, flag = _gate(**kwargs)
            self.assertIsNone(response)
            self.assertEqual(flag, 174)

    def test_equipe_centralcomm_apis_paginas_publicas_e_tabela_ausente_ficam_livres(self):
        cases = ({'is_centralcomm': True}, {'accept': 'application/json'},
                 {'path': '/workspace/api/creditos/resumo'}, {'path': '/workspace/onboarding'},
                 {'path': '/termos'}, {'path': '/workspace/app/projetos/1/fontes/2/download', 'accept': 'application/pdf'},
                 {'table': False})
        for case in cases:
            response, _ = _gate(**case)
            self.assertIsNone(response, case)

    def test_falha_ao_ler_o_banco_nunca_tranca_o_acesso(self):
        from aicentralv2.cadu_workspace.routes import require_workspace_onboarding
        with _app().test_request_context('/app', headers={'Accept': 'text/html'}), \
             mock.patch(R + '_workspace_onboarding_table_available', side_effect=RuntimeError('db down')):
            session.update(user_id=7, cliente_id=174)
            self.assertIsNone(require_workspace_onboarding())
