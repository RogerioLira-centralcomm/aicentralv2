import unittest

from aicentralv2.cadu_connect.reports_management import workspace_map

ITEMS = [
    {'ref': 'ci:b1', 'kind': 'brand', 'name': 'Loja Verão', 'logo_url': '/logo.png', 'related_refs': ['ci:p1']},
    {'ref': 'ci:p1', 'kind': 'project', 'name': 'Black Friday', 'related_refs': ['ci:b1']},
    {'ref': 'projects:9', 'kind': 'project', 'name': 'Institucional'},
]


class WorkspaceMapTests(unittest.TestCase):
    def test_groups_links_by_customer_and_campaign(self):
        result = workspace_map(ITEMS, [{'customer_id': 10, 'brand_ref': 'ci:b1'}],
                               [{'campaign_id': 100, 'project_ref': 'ci:p1'}, {'campaign_id': 100, 'project_ref': 'projects:9'}])
        self.assertTrue(result['available'])
        self.assertEqual(result['customer_brands']['10'], [{'ref': 'ci:b1', 'name': 'Loja Verão', 'accessible': True}])
        self.assertEqual([p['name'] for p in result['campaign_projects']['100']], ['Black Friday', 'Institucional'])
        self.assertEqual(result['brands'], [{'ref': 'ci:b1', 'name': 'Loja Verão', 'logo_url': '/logo.png'}])
        self.assertEqual(result['projects'][0], {'ref': 'ci:p1', 'name': 'Black Friday', 'brand_refs': ['ci:b1']})
        self.assertEqual(result['projects'][1]['brand_refs'], [])

    def test_hidden_or_wrong_kind_links_stay_removable(self):
        result = workspace_map(ITEMS, [{'customer_id': 10, 'brand_ref': 'ci:p1'}], [{'campaign_id': 7, 'project_ref': 'ci:gone'}])
        self.assertFalse(result['customer_brands']['10'][0]['accessible'])
        self.assertEqual(result['campaign_projects']['7'], [{'ref': 'ci:gone', 'name': 'Indisponível no Workspace', 'accessible': False}])


if __name__ == '__main__':
    unittest.main()
