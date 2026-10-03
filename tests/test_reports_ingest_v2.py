import datetime
from unittest import mock

import pytest
from flask import Blueprint, Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_ingest_v2 as v2

TODAY = datetime.date.today().isoformat()
METRICS = {'impressions': 10, 'clicks': 2, 'cost_micros': 1500000, 'conversions': 1.5, 'conversion_value_micros': 9000000}
ACCOUNT = {'id': '655-001-2913', 'name': 'Conta', 'currency': 'BRL', 'time_zone': 'America/Sao_Paulo'}


def test_ad_group_row_is_validated_and_keyed_by_group_and_date():
    key, row = v2._norm_ad_group_metrics({
        'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '22', 'ad_group_name': 'G',
        'ad_group_status': 'enabled', 'date': TODAY, **METRICS})
    assert key == ('22', datetime.date.today())
    assert row['ad_group_status'] == 'ENABLED' and row['cost_micros'] == 1500000


def test_search_term_hash_ignores_case_and_spacing():
    base = {'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'date': TODAY, **METRICS}
    first = v2._norm_search_term_metrics({**base, 'search_term': 'Tênis  Corrida'})[1]
    second = v2._norm_search_term_metrics({**base, 'search_term': 'tênis corrida'})[1]
    assert first['term_hash'] == second['term_hash']


def test_negative_keyword_levels_require_their_own_scope():
    campaign = {'level': 'campaign', 'campaign_id': '1', 'campaign_name': 'C', 'keyword_text': 'grátis', 'match_type': 'PHRASE'}
    assert v2._norm_negative_keyword(campaign)[1]['ad_group_external_id'] is None
    with pytest.raises(BadRequest):
        v2._norm_negative_keyword({**campaign, 'level': 'ad_group'})
    shared = {'level': 'shared_list', 'shared_set_id': '9', 'shared_set_name': 'Lista', 'keyword_text': 'x',
              'match_type': 'EXACT', 'attached_campaign_ids': ['2', '1', '2']}
    assert v2._norm_negative_keyword(shared)[1]['attached_campaign_ids'] == ['1', '2']
    with pytest.raises(BadRequest):
        v2._norm_negative_keyword({**campaign, 'match_type': 'WILD'})


def test_negative_fingerprint_is_stable_across_names_and_case():
    base = {'level': 'campaign', 'campaign_id': '1', 'keyword_text': 'Grátis', 'match_type': 'BROAD'}
    one = v2._norm_negative_keyword({**base, 'campaign_name': 'Antigo'})[0]
    two = v2._norm_negative_keyword({**base, 'campaign_name': 'Novo', 'keyword_text': 'grátis'})[0]
    assert one == two


def test_metric_values_reject_negative_and_future_dates():
    with pytest.raises(BadRequest):
        v2._norm_device_metrics({'campaign_id': '1', 'campaign_name': 'C', 'device': 'MOBILE', 'date': TODAY, **METRICS, 'clicks': -1})
    far = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    with pytest.raises(BadRequest):
        v2._metric_date(far)


def test_landing_page_url_yields_host_and_path_join_keys():
    base = {'campaign_id': '1', 'campaign_name': 'C', 'date': TODAY, **METRICS}
    key, row = v2._norm_landing_page_metrics({**base, 'final_url': 'https://www.Exemplo.com.br/LP/Verao/?utm_source=google'})
    assert row['page_host'] == 'exemplo.com.br' and row['page_path'] == '/lp/verao'  # lower-case, no trailing slash
    assert row['final_url'].endswith('utm_source=google')
    other = v2._norm_landing_page_metrics({**base, 'final_url': 'https://exemplo.com.br/lp/verao/?utm_source=bing'})[1]
    assert other['page_path'] == row['page_path'] and other['url_hash'] != row['url_hash']
    assert v2._norm_landing_page_metrics({**base, 'final_url': 'https://exemplo.com.br'})[1]['page_path'] == '/'
    for bad in ('', 'javascript:alert(1)', 'ftp://x.com/a', '{lpurl}'):
        with pytest.raises(BadRequest):
            v2._norm_landing_page_metrics({**base, 'final_url': bad})


def test_unknown_device_is_bucketed_instead_of_rejected():
    row = v2._norm_device_metrics({'campaign_id': '1', 'campaign_name': 'C', 'device': 'HOLOGRAM', 'date': TODAY, **METRICS})[1]
    assert row['device'] == 'OTHER'


def test_summary_is_whitelisted_and_bounded():
    app = Flask(__name__)
    with app.test_request_context():
        summary = v2._summary({'summary': {
            'duration_ms': 1200, 'window': {'since': '2026-09-24', 'until': TODAY}, 'timed_out': False,
            'datasets': [{'name': 'x' * 100, 'status': 'weird', 'rows': 3, 'error': 'e' * 999, 'secret': 'no'}]}})
    item = summary['datasets'][0]
    assert len(item['name']) == 40 and item['status'] == 'error' and len(item['error']) == 300 and 'secret' not in item
    with app.test_request_context(), pytest.raises(BadRequest):
        v2._summary({'summary': 'oops'})


@pytest.fixture
def client():
    app = Flask(__name__)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    v2.register(bp)
    app.register_blueprint(bp)
    return app.test_client()


class FakeDb:
    def __init__(self, key=None, linked=True, duplicate=False):
        self.key = key or {'id': 'k', 'client_id': 7, 'allowed_account_ids': ['6550012913'], 'bound_account_id': None,
                           'manager_external_id': None}
        self.linked, self.duplicate, self.statements = linked, duplicate, []

    def rows(self, sql, params=()):
        self.statements.append((' '.join(sql.split()), params))
        if 'FROM cadu_reports_ingest_keys' in sql:
            return [self.key] if self.key else []
        if 'INSERT INTO cadu_reports_source_runs' in sql:
            return [] if self.duplicate else [{'id': 'run'}]
        if 'INSERT INTO cadu_reports_accounts' in sql:
            return [{'id': 55}]
        return [{'id': 1}]


def post(client, db, body, token='tok'):
    db_obj = mock.Mock()
    with mock.patch.object(v2, '_rows', db.rows), mock.patch.object(v2, 'get_db', return_value=db_obj):
        response = client.post('/connect/api/v1/reports/ingest/google-ads/v2', json=body,
                               headers={'Authorization': f'Bearer {token}'})
    return response, db_obj


def envelope(dataset, **extra):
    return {'schema_version': 2, 'engine_version': '2.0.0', 'run_key': 'run-1', 'manager_account_id': None,
            'account': ACCOUNT, 'dataset': dataset, 'chunk': {'index': 0, 'total': 1}, **extra}


def test_requires_bearer_token(client):
    response = client.post('/connect/api/v1/reports/ingest/google-ads/v2', json=envelope('device_metrics', records=[]))
    assert response.status_code == 401


def test_rejects_old_schema_and_unknown_dataset(client):
    db = FakeDb()
    assert post(client, db, {**envelope('device_metrics', records=[{}]), 'schema_version': 1})[0].status_code == 400
    assert post(client, db, envelope('drop_tables', records=[{}]))[0].status_code == 400


def test_account_outside_allowlist_is_forbidden(client):
    db = FakeDb(key={'id': 'k', 'client_id': 7, 'allowed_account_ids': ['1111111111'], 'bound_account_id': None, 'manager_external_id': None})
    response, _ = post(client, db, envelope('device_metrics', records=[{}]))
    assert response.status_code == 403


def test_manager_mismatch_is_forbidden(client):
    response, _ = post(client, FakeDb(), {**envelope('device_metrics', records=[{}]), 'manager_account_id': '999-999-9999'})
    assert response.status_code == 403


def test_empty_metrics_chunk_is_rejected_but_empty_final_snapshot_is_accepted(client):
    assert post(client, FakeDb(), envelope('device_metrics', records=[]))[0].status_code == 400
    assert post(client, FakeDb(), envelope('negative_keywords', records=[]))[0].status_code == 400
    ok, db_obj = post(client, FakeDb(), envelope('negative_keywords', records=[], snapshot={'id': 's1', 'final': True}))
    assert ok.status_code == 200 and ok.get_json()['records'] == 0
    db_obj.commit.assert_called_once()


def test_snapshot_removal_only_runs_on_the_final_chunk(client):
    record = {'level': 'campaign', 'campaign_id': '1', 'campaign_name': 'C', 'keyword_text': 'x', 'match_type': 'BROAD'}
    partial = FakeDb()
    post(client, partial, envelope('negative_keywords', records=[record], snapshot={'id': 's1', 'final': False}))
    assert not any('SET removed_at=NOW()' in sql for sql, _ in partial.statements)
    final = FakeDb()
    post(client, final, envelope('negative_keywords', records=[record], snapshot={'id': 's1', 'final': True}))
    assert any('SET removed_at=NOW()' in sql for sql, _ in final.statements)


def test_duplicate_chunk_is_acknowledged_without_writing(client):
    db = FakeDb(duplicate=True)
    response, db_obj = post(client, db, envelope('device_metrics', records=[
        {'campaign_id': '1', 'campaign_name': 'C', 'device': 'MOBILE', 'date': TODAY, **METRICS}]))
    assert response.get_json()['duplicate'] is True
    db_obj.rollback.assert_called_once()
    assert not any('cadu_reports_gads_device_daily' in sql for sql, _ in db.statements)


def test_run_summary_is_a_heartbeat_that_marks_partial_on_error(client):
    db = FakeDb()
    summary = {'duration_ms': 10, 'window': {'since': TODAY, 'until': TODAY},
               'datasets': [{'name': 'campaign_metrics', 'status': 'empty', 'rows': 0},
                            {'name': 'keyword_metrics', 'status': 'error', 'rows': 0, 'error': 'campo inválido'}]}
    response, _ = post(client, db, envelope('run_summary', summary=summary))
    assert response.status_code == 200
    updates = [params for sql, params in db.statements if sql.startswith('UPDATE cadu_reports_source_runs')]
    assert updates and updates[0][0] == 'partial'
    assert any('SET last_used_at=NOW()' in sql for sql, _ in db.statements)


def test_campaign_metrics_reuse_the_v1_record_contract(client):
    db = FakeDb()
    record = {'campaign_id': '12', 'campaign_name': 'C', 'campaign_status': 'ENABLED', 'channel_type': 'SEARCH',
              'date': TODAY, **METRICS}
    response, _ = post(client, db, envelope('campaign_metrics', records=[record, record]))
    assert response.status_code == 200 and response.get_json()['records'] == 1
    assert any('cadu_reports_campaign_daily_metrics' in sql for sql, _ in db.statements)


def test_chunk_retention_only_removes_unreferenced_old_batches():
    db = mock.Mock()
    cursor = db.cursor.return_value
    cursor.rowcount = 3
    cursor.fetchall.return_value = [{'name': table} for table in v2._RUN_REFERENCES]
    with mock.patch.object(v2, 'get_db', return_value=db):
        assert v2.prune_chunk_runs(30) == 3
    sql, params = cursor.execute.call_args[0]
    assert params == (v2.CHUNK_SOURCE_KIND, 30)
    for table in v2._RUN_REFERENCES:
        assert f'FROM {table} t WHERE t.last_run_id=r.id' in sql
    assert 'NOT EXISTS' in sql and 'summary' not in sql
    db.commit.assert_called_once()


def test_chunk_retention_skips_tables_a_database_has_not_migrated_yet():
    db = mock.Mock()
    cursor = db.cursor.return_value
    cursor.rowcount = 0
    cursor.fetchall.return_value = [{'name': 'cadu_reports_gads_keyword_daily'}]
    with mock.patch.object(v2, 'get_db', return_value=db):
        v2.prune_chunk_runs(30)
    sql = cursor.execute.call_args[0][0]
    assert 'cadu_reports_gads_keyword_daily t' in sql and 'cadu_reports_gads_ads t' not in sql


def test_ad_keeps_text_strength_and_approval_and_is_keyed_by_ad():
    key, row = v2._norm_ads({
        'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'ad_id': '77',
        'ad_type': 'responsive_search_ad', 'status': 'enabled', 'ad_strength': 'poor', 'approval_status': 'approved',
        'final_url': 'https://exemplo.com.br/', 'headlines': [{'text': 'Título', 'pinned': 'HEADLINE_1'}],
        'descriptions': [{'text': 'Descrição'}], 'path1': 'loja'})
    assert key == ('77',) and row['ad_strength'] == 'POOR' and row['approval_status'] == 'APPROVED'
    assert row['headlines'] == [{'text': 'Título', 'pinned': 'HEADLINE_1'}] and row['descriptions'] == [{'text': 'Descrição', 'pinned': ''}]
    assert v2._norm_ads({'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'ad_id': '78',
                         'final_url': 'javascript:alert(1)'})[1]['final_url'] is None
    with pytest.raises(BadRequest):
        v2._norm_ads({'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'ad_id': '79',
                      'headlines': [{'text': 'x'}] * 31})


def test_unknown_ad_strength_is_bucketed_not_rejected():
    row = v2._norm_ads({'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'ad_id': '7',
                        'ad_strength': 'SUPERB'})[1]
    assert row['ad_strength'] == 'UNKNOWN'


def test_ad_metrics_and_asset_performance_keys():
    key, row = v2._norm_ad_metrics({'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_id': '7', 'date': TODAY, **METRICS})
    assert key == ('7', datetime.date.today()) and row['clicks'] == 2
    key, row = v2._norm_asset_performance({'campaign_id': '1', 'ad_group_id': '2', 'ad_id': '7', 'asset_id': '11', 'text': 'Compre agora',
                                           'field_type': 'headline', 'performance_label': 'low', 'enabled': True})
    assert key == ('7', '11', 'HEADLINE') and row['performance_label'] == 'LOW'


def test_impression_share_accepts_missing_values_and_rejects_out_of_range():
    base = {'campaign_id': '1', 'campaign_name': 'C', 'date': TODAY}
    row = v2._norm_impression_share({**base, 'search_impression_share': 0.42, 'budget_lost': None})[1]
    assert str(row['search_impression_share']) == '0.420000' and row['budget_lost'] is None and row['rank_lost'] is None
    with pytest.raises(BadRequest):
        v2._norm_impression_share({**base, 'search_impression_share': 1.4})


def test_conversion_action_hash_ignores_case():
    base = {'campaign_id': '1', 'campaign_name': 'C', 'date': TODAY, 'conversions': 2, 'conversion_value_micros': 5}
    one = v2._norm_conversion_action({**base, 'action_name': 'Lead Site'})
    two = v2._norm_conversion_action({**base, 'action_name': 'lead site'})
    assert one[0] == two[0] and one[1]['conversions'] == 2


def test_keyword_quality_components_are_optional_for_older_scripts():
    base = {'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'criterion_id': '5',
            'keyword_text': 'sapato', 'match_type': 'EXACT', 'keyword_status': 'ENABLED', 'quality_score': 4, 'date': TODAY, **METRICS}
    old = v2._norm_keyword_metrics(base)[1]
    assert old['expected_ctr'] is None and old['cpc_bid_micros'] is None
    new = v2._norm_keyword_metrics({**base, 'expected_ctr': 'below_average', 'ad_relevance': 'AVERAGE',
                                    'landing_page_experience': 'ABOVE_AVERAGE', 'cpc_bid_micros': 1200000})[1]
    assert new['expected_ctr'] == 'BELOW_AVERAGE' and new['cpc_bid_micros'] == 1200000


def test_new_datasets_are_accepted_by_the_endpoint(client):
    db = FakeDb()
    ad = {'campaign_id': '1', 'campaign_name': 'C', 'ad_group_id': '2', 'ad_group_name': 'G', 'ad_id': '7', 'ad_type': 'RESPONSIVE_SEARCH_AD',
          'status': 'ENABLED', 'headlines': [{'text': 'A'}], 'descriptions': []}
    response, _ = post(client, db, envelope('ads', records=[ad], snapshot={'id': 's', 'final': True}))
    assert response.status_code == 200 and response.get_json()['records'] == 1
    assert any('cadu_reports_gads_ads' in sql for sql, _ in db.statements)
    assert any('SET removed_at=NOW()' in sql and 'cadu_reports_gads_ads' in sql for sql, _ in db.statements)


def test_short_address_reaches_the_same_ingest(client):
    assert client.post('/connect/api/gads', json=envelope('device_metrics', records=[])).status_code == 401
    db = FakeDb()
    with mock.patch.object(v2, '_rows', db.rows), mock.patch.object(v2, 'get_db', return_value=mock.Mock()):
        response = client.post('/connect/api/gads', json=envelope('campaign_settings', records=[], snapshot={'id': 's', 'final': True}),
                               headers={'Authorization': 'Bearer tok'})
    assert response.status_code != 404


@pytest.mark.parametrize('path', ['/connect/api/gads/plan', '/connect/api/v1/reports/ingest/google-ads/v2/plan'])
def test_plan_answers_on_both_addresses(client, path):
    db = FakeDb()
    oldest = datetime.date.today() - datetime.timedelta(days=13)
    rows = lambda sql, params=(): [{'oldest': oldest}] if 'LEAST' in sql else db.rows(sql, params)
    with mock.patch.object(v2, '_rows', rows), mock.patch.object(v2, 'get_db', return_value=mock.Mock()):
        response = client.get(path + '?account_id=655-001-2913', headers={'Authorization': 'Bearer tok'})
    assert response.status_code == 200
    assert [item['kind'] for item in response.get_json()['ranges']] == ['recent', 'backfill']
