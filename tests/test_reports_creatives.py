from unittest import TestCase, mock

from aicentralv2.cadu_connect import reports_creatives as creatives

CAMPAIGN = {'id': 11, 'name': 'Luz para Todos', 'platform': 'google_ads', 'objective': 'Leads', 'customer_id': 7,
            'project_ref': 'ci:abc'}
ITEMS = [
    {'ref': 'studio:5', 'kind': 'brand', 'name': 'Cemig', 'logo_url': '/l.png', 'related_refs': ['ci:abc']},
    {'ref': 'studio:9', 'kind': 'brand', 'name': 'Outra', 'related_refs': []},
    {'ref': 'ci:marca', 'kind': 'brand', 'name': 'Marca do Workspace', 'related_refs': []},
    {'ref': 'ci:abc', 'kind': 'project', 'name': 'Campanha 2026', 'related_refs': ['studio:5']},
]


class ReportsCreativesTest(TestCase):
    def test_prompt_uses_converting_intent_landing_page_format_and_angle(self):
        signals = {'terms': ['tarifa social cemig', 'como pedir tarifa'], 'keywords': [], 'landing_page': 'www.cemig.com.br/luz',
                   'metrics': {'impressions': 1000, 'clicks': 50, 'conversions': 4}}
        prompt = creatives.build_prompt(CAMPAIGN, signals, 'stories', 'urgency', 'Evitar fotos de banco')
        for expected in ('"Luz para Todos"', 'Google Ads', 'Objetivo da campanha: Leads', '"tarifa social cemig"',
                         'www.cemig.com.br/luz', 'CTR de 5,0%', '4 conversões', 'Oferta e urgência', 'Stories e Reels 9:16',
                         'identidade da marca', 'Evitar fotos de banco'):
            self.assertIn(expected, prompt)
        self.assertLessEqual(len(prompt), 3900)

    def test_prompt_falls_back_to_keywords_and_unknown_options(self):
        prompt = creatives.build_prompt({**CAMPAIGN, 'objective': None}, {'terms': [], 'keywords': ['energia solar'], 'landing_page': None, 'metrics': None}, 'nope', 'nope')
        self.assertIn('Temas com mais cliques: energia solar', prompt)
        self.assertIn('Feed 4:5', prompt)
        self.assertIn('Benefício direto', prompt)
        self.assertNotIn('Objetivo', prompt)

    def test_context_takes_the_studio_brand_linked_to_the_campaign_project(self):
        with mock.patch.object(creatives, 'workspace_items', return_value=ITEMS):
            context = creatives._context({'client_id': 1}, CAMPAIGN)
        self.assertEqual('ci:abc', context['project_ref'])
        self.assertEqual('studio:5', context['brand_ref'])
        # Workspace-only brands cannot carry visual identity into the Studio.
        self.assertEqual({'studio:5', 'studio:9'}, {item['ref'] for item in context['brands']})

    def test_context_falls_back_to_the_customer_brand(self):
        items = [item for item in ITEMS if item['kind'] == 'brand']
        with mock.patch.object(creatives, 'workspace_items', return_value=items), \
             mock.patch.object(creatives, '_exists', return_value=True), \
             mock.patch.object(creatives, '_rows', return_value=[{'brand_ref': 'studio:9'}]):
            context = creatives._context({'client_id': 1}, CAMPAIGN)
        self.assertIsNone(context['project_ref'])
        self.assertEqual('studio:9', context['brand_ref'])

    def test_context_leaves_brand_open_when_ambiguous(self):
        items = [item for item in ITEMS if item['kind'] == 'brand']
        with mock.patch.object(creatives, 'workspace_items', return_value=items), \
             mock.patch.object(creatives, '_exists', return_value=False):
            context = creatives._context({'client_id': 1}, {**CAMPAIGN, 'project_ref': None})
        self.assertIsNone(context['brand_ref'])
