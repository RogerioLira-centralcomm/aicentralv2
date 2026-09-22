from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceIntegrationsLayoutTests(TestCase):
    def test_pagina_prioriza_decisao_do_usuario_e_esconde_arquitetura(self):
        template = (ROOT / 'aicentralv2' / 'templates' / 'cadu_workspace' / 'integrations.html').read_text(encoding='utf-8')

        self.assertIn('Conecte suas ferramentas ao trabalho', template)
        self.assertIn('workspace-integration-primary', template)
        self.assertIn('workspace-integration-imports', template)
        self.assertIn('workspace-integration-agents', template)
        self.assertNotIn('workspace-integration-advanced', template)
        self.assertNotIn('workspace-integration-overview', template)
        self.assertNotIn('workspace-integration-boundary', template)
        self.assertIn('Conectar agente', template)
        self.assertNotIn('developer token', template.lower())

    def test_integracoes_compartilha_sidebar_de_conta_aberta(self):
        sidebar = (ROOT / 'aicentralv2' / 'templates' / 'cadu_workspace' / '_app_sidebar.html').read_text(encoding='utf-8')
        legacy = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceLegacyChrome.jsx').read_text(encoding='utf-8')
        context = (ROOT / 'frontend' / 'cadu-design-system' / 'components' / 'WorkspaceContextSidebar.jsx').read_text(encoding='utf-8')

        self.assertIn("'accountSurface': legacy_active == 'integracoes'", sidebar)
        self.assertIn('mode="account"', legacy)
        self.assertIn("mode === 'account' ? false : readCollapsed(mode)", context)


if __name__ == '__main__':
    import unittest
    unittest.main()
