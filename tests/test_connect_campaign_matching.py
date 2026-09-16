from unittest import TestCase
from aicentralv2.cadu_connect.campaign_matching import recommendation


REPORTS = [
    {'id': 1, 'campaign_name': 'Inverno 2026', 'document': {'platform': 'Meta Ads', 'external_campaign_id': '123'}},
    {'id': 2, 'campaign_name': 'Inverno 2026', 'document': {'platform': 'Google Ads', 'external_campaign_id': '456'}},
]


class CampaignMatchingTests(TestCase):
    def test_external_id_is_safe_automatic_update_candidate(self):
        result = recommendation({'platform': 'Meta Ads', 'external_campaign_id': '123'}, REPORTS)
        self.assertEqual(result['action'], 'update_existing')
        self.assertEqual(result['candidate']['report_id'], 1)

    def test_same_name_across_platforms_requires_confirmation(self):
        result = recommendation({'campaign_name': 'Inverno 2026'}, REPORTS)
        self.assertEqual(result['action'], 'confirm_match')
        self.assertIsNone(result['candidate'])

    def test_unknown_import_can_be_created_or_held(self):
        self.assertEqual(recommendation({'campaign_name': 'Nova'}, REPORTS)['action'], 'create_or_hold')
