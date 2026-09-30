import json
from pathlib import Path

from aicentralv2.cadu_connect.reports_flow_validation import validate_flow_config


def test_shared_validation_cases():
    cases = json.loads((Path(__file__).parent / 'fixtures' / 'reports_flow_validation.json').read_text())
    for item in cases:
        issues = validate_flow_config(item['config'])
        for severity, expected in [('error', item['expected_errors']), ('warning', item['expected_warnings'])]:
            actual = [issue['code'] + (':' + issue['node_id'] if issue.get('node_id') else '')
                      for issue in issues if issue['severity'] == severity]
            assert actual == expected, item['name']
        assert all(issue.get('action') and issue.get('consequence') for issue in issues), item['name']
        assert all(issue.get('edge_id') == 'volta' for issue in issues if issue['code'] == 'cycle_without_condition')
