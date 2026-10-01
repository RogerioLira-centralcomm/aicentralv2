"""Customers see an audience's description and estimates, never internal costs or pipeline data."""
from unittest import TestCase

from aicentralv2.cadu_planner.catalog import client_projection


class AudienceClientProjectionTest(TestCase):
    def test_audience_projection_drops_costs_ids_and_pipeline(self):
        record = {
            'id': 7, 'name': 'Executivos', 'description': 'Gestores', 'audience': '992K', 'category': 'B2B',
            'cpm_custo': 12, 'cpm_venda': 30, 'slug': 'executivos', 'id_audiencia_plataforma': 'x1',
            'pipeline_tracking': {'step': 3}, 'versao_pipeline': 'v9', 'perfil_consumo': 'Premium',
            'demografia_homens': 54, 'ctr_medio_estimado': 1.2, 'taxonomy': {'role': 'contexto'},
        }
        projected = client_projection('audiencias', record)
        self.assertEqual({key for key in projected if key != 'data_groups'}, {'id', 'name', 'description', 'audience', 'category'})
        variables = {field['variable'] for group in projected['data_groups'] for field in group['fields']}
        self.assertIn('perfil_consumo', variables)
        self.assertIn('demografia_homens', variables)
        self.assertIn('ctr_medio_estimado', variables)
        for internal in ('cpm_custo', 'cpm_venda', 'slug', 'id_audiencia_plataforma', 'pipeline_tracking', 'versao_pipeline', 'taxonomy', 'id'):
            self.assertNotIn(internal, variables)
        self.assertIn('Indicadores estimados', [group['title'] for group in projected['data_groups']])

    def test_other_kinds_are_unchanged(self):
        record = {'id': 1, 'name': 'Canal'}
        self.assertIs(client_projection('canais', record), record)
