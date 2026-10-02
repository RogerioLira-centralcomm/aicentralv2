import datetime
from unittest import mock

import pytest
from flask import Blueprint, Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_google_ads_actions as actions
from aicentralv2.cadu_connect import reports_ingest_v2 as v2
from aicentralv2.cadu_connect.reports_google_ads_rules import build_recommendations

UTC = datetime.timezone.utc


def test_budget_change_is_limited_to_the_ceiling_and_says_so():
    target, params, expect, note = actions.normalize('campaign.set_budget', {'campaign_id': '12'}, {'amount': '200'},
                                                     {'budget_micros': 100_000_000})
    assert target == {'campaign_id': '12'} and expect == {'budget_micros': 100_000_000}
    assert params == {'amount_micros': 130_000_000} and '30%' in note
    _, params, _, note = actions.normalize('campaign.set_budget', {'campaign_id': '12'}, {'amount': '110,50'},
                                           {'budget_micros': 100_000_000})
    assert params == {'amount_micros': 110_500_000} and note is None


def test_user_ceiling_replaces_the_default():
    _, params, _, _ = actions.normalize('keyword.set_cpc', {'ad_group_id': '1', 'keyword_id': '2'}, {'cpc': 10},
                                        {'cpc_micros': 1_000_000}, {'max_cpc_change_pct': 50})
    assert params == {'cpc_micros': 1_500_000}


@pytest.mark.parametrize('op,target,params,expect', [
    ('campaign.delete', {'campaign_id': '1'}, {}, {}),
    ('campaign.pause', {'campaign_id': 'abc'}, {}, {}),
    ('negative.add', {'level': 'campaign'}, {'text': 'x', 'match_type': 'EXACT'}, {}),
    ('negative.add', {'level': 'account', 'campaign_id': '1'}, {'text': 'x', 'match_type': 'EXACT'}, {}),
    ('negative.add', {'level': 'campaign', 'campaign_id': '1'}, {'text': 'x', 'match_type': 'WILD'}, {}),
    ('keyword.add', {'ad_group_id': '1'}, {'text': 'a [b]', 'match_type': 'EXACT'}, {}),
    ('campaign.set_budget', {'campaign_id': '1'}, {'amount': 10}, {}),
    ('campaign.set_budget', {'campaign_id': '1'}, {'amount': 100}, {'budget_micros': 100_000_000}),
])
def test_invalid_commands_are_refused(op, target, params, expect):
    with Flask(__name__).test_request_context(), pytest.raises(BadRequest):
        actions.normalize(op, target, params, expect)


def test_negative_keeps_only_the_id_of_its_level_and_normalizes_text():
    target, params, _, _ = actions.normalize('negative.add', {'level': 'shared_list', 'shared_set_id': 9, 'campaign_id': 3},
                                             {'text': '  Tênis   GRÁTIS ', 'match_type': 'PHRASE'}, {})
    assert target == {'level': 'shared_list', 'shared_set_id': '9', 'campaign_id': '3'}
    assert params == {'text': 'tênis grátis', 'match_type': 'PHRASE'}


def test_every_applied_change_has_its_opposite():
    pause = {'op': 'campaign.pause', 'target': {'campaign_id': '1'}, 'params': {}, 'expect': {'status': 'ENABLED'}}
    assert actions.inverse(pause) == ('campaign.enable', {'campaign_id': '1'}, {}, {'status': 'PAUSED'})
    negative = {'op': 'negative.add', 'target': {'level': 'campaign', 'campaign_id': '1'}, 'params': {'text': 'x', 'match_type': 'EXACT'}}
    assert actions.inverse(negative)[0] == 'negative.remove'
    added = {'op': 'keyword.add', 'target': {'ad_group_id': '5'}, 'params': {'text': 'x', 'match_type': 'EXACT'},
             'result': {'observed': {'keyword_id': '77'}}}
    assert actions.inverse(added) == ('keyword.pause', {'ad_group_id': '5', 'keyword_id': '77'}, {}, {'status': 'ENABLED'})
    assert actions.inverse({**added, 'result': {}}) is None
    budget = {'op': 'campaign.set_budget', 'target': {'campaign_id': '1'}, 'params': {'amount_micros': 130_000_000},
              'expect': {'budget_micros': 100_000_000}, 'result': {'observed': {'previous_budget_micros': 100_000_000}}}
    assert actions.inverse(budget) == ('campaign.set_budget', {'campaign_id': '1'}, {'amount': 100.0}, {'budget_micros': 130_000_000})


def test_next_run_follows_the_observed_interval_and_skips_missed_slots():
    last = datetime.datetime(2026, 10, 2, 14, 2, tzinfo=UTC)
    assert actions.next_run(last, None, last) == last + datetime.timedelta(hours=1)
    assert actions.next_run(last, last - datetime.timedelta(hours=2), last) == last + datetime.timedelta(hours=2)
    later = last + datetime.timedelta(hours=3, minutes=30)
    assert actions.next_run(last, None, later) == last + datetime.timedelta(hours=4)
    assert actions.next_run(last, None, last + datetime.timedelta(days=3)) is None
    assert actions.next_run(None, None) is None


def test_recommendations_carry_a_change_the_script_can_apply():
    now = datetime.datetime.now(UTC)
    accounts = [{'id': 1, 'name': 'Conta', 'last_run_at': now, 'negatives_at': now, 'datasets': []}]
    term = {'account_id': 1, 'campaign_external_id': '10', 'ad_group_external_id': '20', 'term_hash': 'h', 'search_term': 'grátis',
            'campaign_name': 'C', 'ad_group_name': 'G', 'clicks': 40, 'cost': 80.0, 'conversions': 0, 'status': 'NONE'}
    keyword = {'account_id': 1, 'campaign_external_id': '10', 'ad_group_external_id': '20', 'criterion_external_id': '30',
               'keyword_text': 'tênis', 'campaign_name': 'C', 'ad_group_name': 'G', 'clicks': 50, 'cost': 90.0, 'conversions': 0,
               'impressions': 900, 'status': 'ENABLED', 'quality_score': 7}
    items = build_recommendations(accounts=accounts, campaigns=[], terms=[term], keywords=[keyword], devices=[], negatives=[],
                                  totals={'cost': 170.0, 'conversions': 0})
    by_rule = {item['rule']: item for item in items}
    negate = by_rule['negative_candidate']['proposal']
    assert negate['op'] == 'negative.add' and negate['target'] == {'level': 'campaign', 'campaign_id': '10'}
    assert negate['params'] == {'text': 'grátis', 'match_type': 'EXACT'}
    pause = by_rule['keyword_waste']['proposal']
    assert pause['op'] == 'keyword.pause' and pause['target']['keyword_id'] == '30' and pause['expect'] == {'status': 'ENABLED'}
    for item in items:
        if item['proposal']:
            with Flask(__name__).test_request_context():
                actions.normalize(item['proposal']['op'], item['proposal']['target'], item['proposal']['params'], item['proposal']['expect'])


# ---------------------------------------------------------------------------- script routes

@pytest.fixture
def client():
    app = Flask(__name__)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    actions.register(bp)
    app.register_blueprint(bp)
    return app.test_client()


class FakeDb:
    def __init__(self, commands=()):
        self.key = {'id': 'k', 'client_id': 7, 'allowed_account_ids': ['6550012913'], 'bound_account_id': None, 'manager_external_id': None}
        self.commands, self.statements = list(commands), []

    def rows(self, sql, params=()):
        flat = ' '.join(sql.split())
        self.statements.append((flat, params))
        if 'FROM cadu_reports_ingest_keys' in flat and 'token_hash' in flat:
            return [self.key] if self.key and params[1] == 'google_ads_actions' else []
        if 'to_regclass' in flat:
            return [{'ready': True}]
        if flat.startswith("UPDATE cadu_reports_gads_actions SET status='sent'"):
            return self.commands
        if flat.startswith('UPDATE cadu_reports_gads_actions SET status'):
            return [{'id': params[-3] if len(params) > 3 else params[1]}]
        return [{'id': 1}]


def call(client, db, path, body):
    with mock.patch.object(v2, '_rows', db.rows), mock.patch.object(actions, '_rows', db.rows), \
            mock.patch.object(actions, 'get_db', return_value=mock.Mock()):
        return client.post(path, json=body, headers={'Authorization': 'Bearer tok'})


def test_read_key_cannot_claim_actions(client):
    db = FakeDb()
    db.key = None
    response = call(client, db, '/connect/api/gads/actions/next', {'account_id': '655-001-2913'})
    assert response.status_code == 401


def test_claim_records_the_agent_and_returns_commands_in_order(client):
    first = {'id': '00000000-0000-0000-0000-000000000001', 'op': 'campaign.pause', 'target': {'campaign_id': '1'}, 'params': {},
             'expect': {'status': 'ENABLED'}, 'label': 'Pausar', 'expires_at': datetime.datetime(2026, 10, 3, tzinfo=UTC),
             'created_at': datetime.datetime(2026, 10, 2, 10, tzinfo=UTC)}
    second = {**first, 'id': '00000000-0000-0000-0000-000000000002', 'created_at': datetime.datetime(2026, 10, 2, 9, tzinfo=UTC)}
    db = FakeDb([first, second])
    response = call(client, db, '/connect/api/gads/actions/next',
                    {'account_id': '655-001-2913', 'engine_version': '1.0.0', 'allow_writes': True, 'preview': False,
                     'limits': {'maxChangesPerRun': 50}})
    assert response.status_code == 200
    assert [item['id'] for item in response.get_json()['commands']] == [second['id'], first['id']]
    agent = next(params for sql, params in db.statements if 'INSERT INTO cadu_reports_gads_action_agents' in sql)
    assert agent[:3] == (7, '6550012913', 'k')


def test_results_finish_real_runs_and_requeue_simulations(client):
    db = FakeDb()
    response = call(client, db, '/connect/api/gads/actions/result', {'account_id': '6550012913', 'results': [
        {'id': '00000000-0000-0000-0000-000000000001', 'status': 'applied', 'message': 'Pausada.', 'observed': {'status': 'PAUSED'}},
        {'id': '00000000-0000-0000-0000-000000000002', 'status': 'applied', 'simulated': True, 'message': 'Seria pausada.'},
        {'id': '00000000-0000-0000-0000-000000000003', 'status': 'requeue', 'message': 'Limite.'},
        {'id': 'not-a-uuid', 'status': 'applied'},
        {'id': '00000000-0000-0000-0000-000000000004', 'status': 'deleted'},
    ]})
    assert response.status_code == 200
    updates = [(sql, params) for sql, params in db.statements if sql.startswith('UPDATE cadu_reports_gads_actions')]
    assert len(updates) == 3
    assert "finished_at=NOW()" in updates[0][0] and updates[0][1][0] == 'applied'
    assert all("status='approved',sent_at=NULL" in sql for sql, _ in updates[1:])
