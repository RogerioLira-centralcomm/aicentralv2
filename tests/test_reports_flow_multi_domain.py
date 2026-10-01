import unittest
from unittest.mock import patch

from aicentralv2.cadu_connect import reports_flow, reports_supertag

SITE_B = {'id': 'site-b', 'allowed_host': 'loja.outro.com'}


def flow(site_id='site-a', host='cliente.com.br', nodes=()):
    return {'site_id': site_id, 'allowed_host': host, 'config': {'nodes': list(nodes)}}


class FanoutTests(unittest.TestCase):
    def test_a_flow_listens_to_its_own_site(self):
        self.assertTrue(reports_supertag._flow_listens_to(flow(), {'id': 'site-a', 'allowed_host': 'cliente.com.br'}, [], 'www.cliente.com.br'))

    def test_a_flow_ignores_other_sites_without_a_step_on_that_domain(self):
        self.assertFalse(reports_supertag._flow_listens_to(flow(), SITE_B, [], 'loja.outro.com'))

    def test_a_step_on_another_domain_makes_the_flow_listen_to_that_installation(self):
        nodes = [{'type': 'conversion', 'host': 'loja.outro.com', 'path': '/obrigado'}]
        self.assertTrue(reports_supertag._flow_listens_to(flow(nodes=nodes), SITE_B, nodes, 'loja.outro.com'))

    def test_events_from_a_domain_the_installation_does_not_own_are_ignored(self):
        nodes = [{'type': 'page', 'host': 'outro.com', 'path': '/x'}]
        self.assertFalse(reports_supertag._flow_listens_to(flow(nodes=nodes), {'id': 'site-c', 'allowed_host': 'terceiro.com'}, nodes, 'outro.com'))


class ExternalHostIssueTests(unittest.TestCase):
    config = {'nodes': [
        {'id': 'a', 'type': 'page', 'title': 'Home', 'host': 'cliente.com.br', 'path': '/', 'status': 'ready'},
        {'id': 'b', 'type': 'conversion', 'title': 'Obrigado', 'host': 'loja.outro.com', 'path': '/obrigado', 'status': 'ready'},
        {'id': 'c', 'type': 'page', 'title': 'Planejada', 'host': 'planejada.com', 'status': 'planned'}]}

    def issues(self, installed):
        with patch.object(reports_flow, '_rows', return_value=[{'allowed_host': host} for host in installed]):
            return reports_flow._external_host_issues(self.config, 'cliente.com.br', 'client')

    def test_warns_only_for_measured_steps_without_an_installation(self):
        result = self.issues(['cliente.com.br'])
        self.assertEqual([(item['code'], item['node_id'], item['severity']) for item in result], [('external_host_without_tag', 'b', 'warning')])

    def test_silent_once_the_super_tag_is_installed_on_that_domain(self):
        self.assertEqual(self.issues(['cliente.com.br', 'outro.com']), [])


if __name__ == '__main__':
    unittest.main()
