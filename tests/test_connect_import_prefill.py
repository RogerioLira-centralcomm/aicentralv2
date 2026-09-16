from datetime import date
from unittest import TestCase
from aicentralv2.cadu_connect.import_prefill import campaign_draft

class ImportPrefillTests(TestCase):
    def test_draft_keeps_unknown_business_fields_empty(self):
        draft=campaign_draft({'original_name':'google_ads_maio.png','supplier':'Google Ads','period_start':date(2026,5,1)})
        self.assertEqual(draft['platform'],'Google Ads')
        self.assertEqual(draft['start_date'],'2026-05-01')
        self.assertIn('objective',draft['requires_confirmation'])
