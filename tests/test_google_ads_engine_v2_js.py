import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / 'js' / 'google_ads_engine_v2_harness.cjs'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node não instalado')


def run(scenario):
    done = subprocess.run(['node', str(HARNESS), scenario], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def by_dataset(result):
    grouped = {}
    for call in result['calls']:
        grouped.setdefault(call['dataset'], []).append(call)
    return grouped


def test_every_dataset_is_sent_and_a_summary_closes_the_run():
    result = run('happy')
    grouped = by_dataset(result)
    assert result['thrown'] is None
    assert set(grouped) == {'campaign_metrics', 'campaign_settings', 'device_metrics', 'landing_page_metrics', 'search_term_metrics',
                            'negative_keywords', 'run_summary'}
    assert result['calls'][-1]['dataset'] == 'run_summary'
    assert all(call['schema_version'] == 2 and call['run_key'] == 'uuid-1' for call in result['calls'])
    summary = {item['name']: item for item in grouped['run_summary'][0]['summary']['datasets']}
    assert summary['keyword_metrics']['status'] == 'empty' and summary['campaign_metrics']['rows'] == 1


def test_negative_keywords_cover_ad_group_and_shared_lists_with_attachments():
    records = by_dataset(run('happy'))['negative_keywords'][0]['records']
    assert {item['level'] for item in records} == {'ad_group', 'shared_list'}
    shared = next(item for item in records if item['level'] == 'shared_list')
    assert shared['attached_campaign_ids'] == ['1'] and shared['shared_set_id'] == '9'
    snapshot = by_dataset(run('happy'))['negative_keywords'][0]['snapshot']
    assert snapshot == {'id': 'uuid-1:negative_keywords', 'final': True}


def test_empty_snapshots_are_still_sent_but_empty_metrics_are_not():
    grouped = by_dataset(run('happy'))
    assert 'keyword_metrics' not in grouped and 'ad_group_metrics' not in grouped
    assert grouped['negative_keywords'][0]['snapshot']['final'] is True


def test_large_datasets_are_chunked_under_the_server_limit():
    chunks = by_dataset(run('chunking'))['search_term_metrics']
    assert [len(chunk['records']) for chunk in chunks] == [300, 300, 50]
    assert [chunk['chunk']['index'] for chunk in chunks] == [0, 1, 2]
    assert max(len(chunk['records']) for chunk in chunks) <= 500


def test_a_failing_dataset_does_not_stop_the_others_and_is_reported():
    result = run('dataset_error')
    grouped = by_dataset(result)
    assert 'search_term_metrics' in grouped and 'negative_keywords' in grouped
    summary = {item['name']: item for item in grouped['run_summary'][0]['summary']['datasets']}
    assert summary['keyword_metrics']['status'] == 'error' and 'Field not valid' in summary['keyword_metrics']['error']
    assert 'keyword_metrics' in result['thrown']


def test_rejected_key_aborts_immediately():
    result = run('unauthorized')
    assert len(result['calls']) == 1
    assert 'recusou' in result['thrown']


def test_dry_run_sends_nothing():
    result = run('dry_run')
    assert result['calls'] == [] and result['thrown'] is None
    assert any('simulação' in line for line in result['logs'])


def test_landing_pages_carry_the_final_url_per_campaign_and_day():
    record = by_dataset(run('happy'))['landing_page_metrics'][0]['records'][0]
    assert record['final_url'].startswith('https://exemplo.com.br/lp/verao/') and record['campaign_id'] == '1'
    assert record['date'] == '2026-10-01' and record['cost_micros'] == 2000000
