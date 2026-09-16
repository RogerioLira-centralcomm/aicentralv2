from unittest import TestCase
from aicentralv2.cadu_connect.campaign_health import assess

class CampaignHealthTests(TestCase):
    def test_uses_coverage_before_claiming_health(self):
        self.assertEqual(assess(elapsed_pct=70,delivered_pct=90,coverage_pct=50,days_remaining=3)['state'],'Sem leitura')
    def test_flags_pacing_risk(self):
        result=assess(elapsed_pct=70,delivered_pct=50,coverage_pct=100,days_remaining=8)
        self.assertEqual(result['state'],'Risco')
        self.assertEqual(result['estimated_goal_pct'],'71.42857142857142857142857143')
