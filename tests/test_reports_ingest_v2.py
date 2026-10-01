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
