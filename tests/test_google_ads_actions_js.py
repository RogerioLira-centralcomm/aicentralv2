import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / 'js' / 'google_ads_actions_harness.cjs'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node não instalado')


def run(scenario):
    done = subprocess.run(['node', str(HARNESS), scenario], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def results(result):
    return {item['id']: item for item in result['calls'][-1]['body']['results']}


def test_each_command_is_applied_checked_or_refused_and_reported():
    result = run('happy')
    assert [call['path'] for call in result['calls']] == ['/actions/next', '/actions/result']
    assert result['calls'][0]['body']['engine_version'] == '1.0.0' and result['calls'][0]['body']['allow_writes'] is True
    by_id = results(result)
    assert by_id['a']['status'] == 'applied' and by_id['a']['observed'] == {'status': 'PAUSED', 'previous_status': 'ENABLED'}
    assert by_id['b']['status'] == 'skipped'                     # keyword was already paused
    assert by_id['c']['status'] == 'applied'
    assert by_id['d']['status'] == 'skipped'                     # negative already there
    assert by_id['e']['status'] == 'skipped' and '30%' in by_id['e']['message']   # +100% refused by the pasted limit
    assert by_id['f']['status'] == 'applied' and by_id['f']['observed']['previous_budget_micros'] == 100000000
    assert by_id['g']['status'] == 'applied' and by_id['g']['observed'] == {'keyword_id': '99'}
    assert by_id['h']['status'] == 'skipped' and 'não permitida' in by_id['h']['message']
    assert by_id['i']['status'] == 'skipped'
    assert by_id['j']['status'] == 'applied'
    assert ['campaign', 1, 'pause'] in result['changes'] and ['campaign', 1, 'add_negative', '"vagas"'] in result['changes']
    assert ['budget', 1, 120] in result['changes'] and ['ad_group', 2, 'add_keyword', '[tênis]'] in result['changes']
    assert not any(change[0] == 'budget' and change[2] == 200 for change in result['changes'])
    assert result['thrown'] is None


@pytest.mark.parametrize('scenario', ['preview', 'writes_off'])
def test_preview_and_disabled_writes_change_nothing(scenario):
    result = run(scenario)
    assert result['changes'] == []
    assert all(item['simulated'] for item in results(result).values())


def test_changes_beyond_the_run_limit_go_back_to_the_queue():
    by_id = results(run('limit'))
    assert by_id['n49']['status'] in ('applied', 'skipped') and by_id['n50']['status'] == 'requeue' and by_id['n51']['status'] == 'requeue'
