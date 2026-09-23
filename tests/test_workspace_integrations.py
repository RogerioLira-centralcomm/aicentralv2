from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceIntegrationsLayoutTests(TestCase):
    def test_pagina_usa_a_superficie_react_da_conta(self):
        template = (ROOT / 'aicentralv2' / 'templates' / 'cadu_workspace' / 'account_react.html').read_text(encoding='utf-8')
        component = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceAccount.jsx').read_text(encoding='utf-8')
        routes = (ROOT / 'aicentralv2' / 'cadu_workspace' / 'routes.py').read_text(encoding='utf-8')

        self.assertIn("'googleSync'", template)
        self.assertIn("'googleResourceBase'", template)
        self.assertIn("'googleMeetArtifactBase'", template)
        self.assertIn('function Integrations', component)
        self.assertIn('Conectar agentes e MCPs publicáveis', component)
        self.assertIn('Contas autorizadas', component)
        self.assertIn('Reuniões encontradas', component)
        self.assertIn('Preparar para revisão', component)
        self.assertIn('Vincular ao projeto', component)
        self.assertIn('Ver todas no Connect', component)
        self.assertIn("section === 'integracoes' ? <Integrations", component)
        self.assertIn("'cadu_workspace/account_react.html', section='integracoes'", routes)
        self.assertNotIn('developer token', component.lower())

    def test_integracoes_e_agencia_compartilham_sidebar_de_conta(self):
        context = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceContextSidebar.jsx').read_text(encoding='utf-8')

        self.assertIn("{id: 'agencia', label: 'Agência'", context)
        self.assertIn("{id: 'integracoes', label: 'Integrações'", context)
        self.assertIn("mode === 'account' ? false : readCollapsed(mode)", context)


if __name__ == '__main__':
    import unittest
    unittest.main()
