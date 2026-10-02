"""Google Ads · Ações: changes approved in the Reports and applied by the "Ações" script installed in the account.

The Reports validates and queues each change; the script claims the queue on its hourly run, applies what its own
closed list and limits allow, and reports back. Every command carries the state it expects (status, budget, CPC), so a
decision taken on data that has since changed is skipped instead of applied. The read script (engine v2) never writes.
"""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import abort, jsonify, request

from ..auth import login_required_api
from ..db import get_db
from .reports_ingest import _google_id
from .reports_ingest_v2 import _authenticate, _authorize_scope
from .reports_v1 import _rows, _selection, _write_guard

SOURCE_KIND = 'google_ads_actions'
ENGINE_VERSION = '1.0.0'
SCHEDULE_MINUTES = 60
EXPIRES_HOURS = 24
LEASE_MINUTES = 90
MAX_BATCH = 200
MAX_CLAIM = 100
DEFAULT_LIMITS = {'max_budget_change_pct': 30, 'max_cpc_change_pct': 30}
MATCH_TYPES = ('EXACT', 'PHRASE', 'BROAD')
OPEN = ('approved', 'sent')
FINAL = ('applied', 'failed', 'skipped', 'expired', 'cancelled')
_ID = re.compile(r'\d{1,20}')

# Target ids each operation needs; negatives also need the level and the id of that level.
OPS = {
    'campaign.pause': ('campaign_id',), 'campaign.enable': ('campaign_id',),
    'ad_group.pause': ('ad_group_id',), 'ad_group.enable': ('ad_group_id',),
    'keyword.pause': ('ad_group_id', 'keyword_id'), 'keyword.enable': ('ad_group_id', 'keyword_id'),
    'keyword.add': ('ad_group_id',), 'keyword.set_cpc': ('ad_group_id', 'keyword_id'),
    'negative.add': (), 'negative.remove': (),
    'campaign.set_budget': ('campaign_id',),
}
NEGATIVE_LEVEL_ID = {'campaign': 'campaign_id', 'ad_group': 'ad_group_id', 'shared_list': 'shared_set_id'}
TOGGLES = {'campaign.pause': 'campaign.enable', 'campaign.enable': 'campaign.pause', 'ad_group.pause': 'ad_group.enable',
           'ad_group.enable': 'ad_group.pause', 'keyword.pause': 'keyword.enable', 'keyword.enable': 'keyword.pause'}
VERBS = {'campaign.pause': 'Pausar campanha', 'campaign.enable': 'Ativar campanha', 'ad_group.pause': 'Pausar grupo',
         'ad_group.enable': 'Ativar grupo', 'keyword.pause': 'Pausar palavra-chave', 'keyword.enable': 'Ativar palavra-chave',
         'keyword.add': 'Adicionar palavra-chave', 'keyword.set_cpc': 'Ajustar lance', 'negative.add': 'Negativar',
         'negative.remove': 'Remover negativa', 'campaign.set_budget': 'Ajustar orçamento'}


# ---------------------------------------------------------------------------
# Pure rules: validation, limits and the inverse of an applied change
# ---------------------------------------------------------------------------

def _bad(message):
    abort(400, description=message)


def _id(value, name):
    text = str(value if value is not None else '').strip()
    if not _ID.fullmatch(text):
        _bad(f'{name} inválido.')
    return text


def _text(value):
    text = ' '.join(str(value or '').split())
    if not text or len(text) > 80 or len(text.split()) > 10 or any(ch in text for ch in '[]"!@%^*={};~`<>?\\|'):
        _bad('Texto de palavra-chave inválido: até 80 caracteres e 10 palavras, sem símbolos especiais.')
    return text.lower()


def _micros(value, name):
    try:
        amount = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        _bad(f'{name} inválido.')
    if not 0 < amount <= 1e7:
        _bad(f'{name} fora do limite.')
    return int(round(amount * 100)) * 10000  # centavos: o Google Ads recusa frações menores


def _expected_micros(expect, key, name):
    try:
        value = int(expect.get(key))
    except (TypeError, ValueError):
        _bad(f'Informe o {name} atual para conferir antes de aplicar.')
    if value <= 0:
        _bad(f'{name.capitalize()} atual inválido.')
    return value


def clamp(current, wanted, pct):
    """Wanted value limited to ±pct of the current one, in whole cents. Returns (value, clamped)."""
    low, high = current * (1 - pct / 100), current * (1 + pct / 100)
    value = min(max(wanted, low), high)
    value = int(round(value / 10000)) * 10000
    return value, value != wanted


def normalize(op, target, params, expect, limits=None):
    """Validated (target, params, expect, note) for one command, or a 400 that says what is wrong."""
    if op not in OPS:
        _bad('Operação não permitida.')
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    target, params, expect = target or {}, params or {}, expect or {}
    if not all(isinstance(item, dict) for item in (target, params, expect)):
        _bad('Comando inválido.')
    clean_target = {key: _id(target.get(key), key) for key in OPS[op]}
    # Context ids are optional and only help the screen; they are never trusted by the script.
    for key in ('campaign_id', 'ad_group_id'):
        if key not in clean_target and target.get(key) not in (None, ''):
            clean_target[key] = _id(target[key], key)
    clean_params, clean_expect, note = {}, {}, None
    if op.startswith('negative.'):
        level = target.get('level')
        if level not in NEGATIVE_LEVEL_ID:
            _bad('Nível da negativa inválido.')
        clean_target['level'] = level
        clean_target[NEGATIVE_LEVEL_ID[level]] = _id(target.get(NEGATIVE_LEVEL_ID[level]), NEGATIVE_LEVEL_ID[level])
    if op in ('negative.add', 'negative.remove', 'keyword.add'):
        if params.get('match_type') not in MATCH_TYPES:
            _bad('Correspondência inválida.')
        clean_params = {'text': _text(params.get('text')), 'match_type': params['match_type']}
    if op in TOGGLES and expect.get('status') in ('ENABLED', 'PAUSED'):
        clean_expect['status'] = expect['status']
    if op == 'campaign.set_budget':
        current = _expected_micros(expect, 'budget_micros', 'orçamento')
        value, clamped = clamp(current, _micros(params.get('amount'), 'Orçamento'), float(limits['max_budget_change_pct']))
        clean_params, clean_expect = {'amount_micros': value}, {'budget_micros': current}
        note = f"Limitado a {limits['max_budget_change_pct']:g}% do orçamento atual." if clamped else None
    if op == 'keyword.set_cpc':
        current = _expected_micros(expect, 'cpc_micros', 'lance')
        value, clamped = clamp(current, _micros(params.get('cpc'), 'Lance'), float(limits['max_cpc_change_pct']))
        clean_params, clean_expect = {'cpc_micros': value}, {'cpc_micros': current}
        note = f"Limitado a {limits['max_cpc_change_pct']:g}% do lance atual." if clamped else None
    if op in ('campaign.set_budget', 'keyword.set_cpc') and clean_params[next(iter(clean_params))] == next(iter(clean_expect.values())):
        _bad('O valor pedido é igual ao atual.')
    return clean_target, clean_params, clean_expect, note


def inverse(action):
    """(op, target, params, expect) that undoes an applied action, or None when it cannot be undone safely."""
    op, target, params = action['op'], dict(action['target'] or {}), dict(action['params'] or {})
    observed = ((action.get('result') or {}).get('observed')) or {}
    if op in TOGGLES:
        return TOGGLES[op], target, {}, {'status': 'PAUSED' if op.endswith('.pause') else 'ENABLED'}
    if op == 'negative.add':
        return 'negative.remove', target, params, {}
    if op == 'negative.remove':
        return 'negative.add', target, params, {}
    if op == 'keyword.add' and observed.get('keyword_id'):
        return 'keyword.pause', {**target, 'keyword_id': str(observed['keyword_id'])}, {}, {'status': 'ENABLED'}
    if op == 'campaign.set_budget':
        previous = observed.get('previous_budget_micros') or (action.get('expect') or {}).get('budget_micros')
        if previous:
            return op, target, {'amount': previous / 1e6}, {'budget_micros': params['amount_micros']}
    if op == 'keyword.set_cpc':
        previous = observed.get('previous_cpc_micros') or (action.get('expect') or {}).get('cpc_micros')
        if previous:
            return op, target, {'cpc': previous / 1e6}, {'cpc_micros': params['cpc_micros']}
    return None


def next_run(last_poll, previous_poll, now=None):
    """When the hourly script is expected to call again; the observed interval wins over the nominal hour."""
    if not last_poll:
        return None
    interval = timedelta(minutes=SCHEDULE_MINUTES)
    if previous_poll and timedelta(minutes=50) <= last_poll - previous_poll <= timedelta(hours=24):
        interval = last_poll - previous_poll
    expected = last_poll + interval
    now = now or datetime.now(timezone.utc)
    # A missed run: Google Ads runs scripts on the hour it was scheduled, so the next slot is the next interval.
    while expected < now - timedelta(minutes=10) and interval.total_seconds() > 0:
        expected += interval
        if expected - last_poll > timedelta(days=2):
            return None
    return expected


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def tables_ready():
    return bool(_rows("SELECT to_regclass('public.cadu_reports_gads_actions') IS NOT NULL AS ready")[0]['ready'])


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _public(row):
    row = dict(row)
    for key in ('approved_at', 'sent_at', 'finished_at', 'expires_at', 'created_at'):
        row[key] = _iso(row.get(key))
    row['id'] = str(row['id'])
    row['undo_of'] = str(row['undo_of']) if row.get('undo_of') else None
    row['can_undo'] = row['status'] == 'applied' and not row.get('undone') and inverse(row) is not None
    row['can_cancel'] = row['status'] == 'approved'
    return row


def _expire(client_id, account_external_id=None):
    _rows('''UPDATE cadu_reports_gads_actions SET status='expired',finished_at=NOW(),
            result=COALESCE(result,'{}'::jsonb) || '{"message":"Aprovação vencida antes de o script rodar."}'::jsonb
        WHERE client_id=%s AND status IN ('approved','sent') AND expires_at < NOW()
            AND (%s::text IS NULL OR account_external_id=%s) RETURNING id''',
          (client_id, account_external_id, account_external_id))


def _limits_for(client_id, account_external_id):
    rows = _rows('''SELECT limits FROM cadu_reports_ingest_keys WHERE client_id=%s AND source_kind=%s AND revoked_at IS NULL
            AND (%s=ANY(allowed_account_ids) OR bound_account_id=%s) ORDER BY created_at DESC LIMIT 1''',
                 (client_id, SOURCE_KIND, account_external_id, account_external_id))
    stored = (rows[0]['limits'] if rows else None) or {}
    return {key: float(stored.get(key, value)) for key, value in DEFAULT_LIMITS.items()}


def recommendation_actions(client_id, ids):
    """Latest action per recommendation id (last 7 days), for the status shown next to each recommendation."""
    if not ids or not tables_ready():
        return {}
    rows = _rows('''SELECT DISTINCT ON (recommendation_id) id,recommendation_id,op,status,label,created_at,finished_at,expires_at,
            target,params,expect,result,approved_at,sent_at,undo_of,origin,account_external_id,
            EXISTS (SELECT 1 FROM cadu_reports_gads_actions u WHERE u.undo_of=a.id AND u.status NOT IN ('cancelled','expired','failed')) AS undone
        FROM cadu_reports_gads_actions a
        WHERE client_id=%s AND recommendation_id=ANY(%s) AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY recommendation_id, created_at DESC''', (client_id, list(ids)))
    return {row['recommendation_id']: _public(row) for row in rows}


_LIST_SQL = '''SELECT a.id,a.account_id,a.account_external_id,acc.name AS account_name,a.op,a.target,a.params,a.expect,a.label,
        a.status,a.origin,a.recommendation_id,a.undo_of,a.created_by,a.approved_at,a.sent_at,a.attempts,a.finished_at,a.result,
        a.expires_at,a.created_at,
        EXISTS (SELECT 1 FROM cadu_reports_gads_actions u WHERE u.undo_of=a.id AND u.status NOT IN ('cancelled','expired','failed')) AS undone
    FROM cadu_reports_gads_actions a JOIN cadu_reports_accounts acc ON acc.id=a.account_id
    WHERE a.client_id=%s ORDER BY a.created_at DESC LIMIT 300'''

_ACCOUNTS_SQL = '''SELECT acc.id,acc.name,acc.external_id,
        ag.last_poll_at,ag.previous_poll_at,ag.engine_version,ag.allow_writes,ag.preview,ag.limits AS agent_limits,
        EXISTS (SELECT 1 FROM cadu_reports_ingest_keys k WHERE k.client_id=acc.client_id AND k.source_kind=%(kind)s
            AND k.revoked_at IS NULL AND (acc.external_id=ANY(k.allowed_account_ids) OR k.bound_account_id=acc.external_id)) AS has_key
    FROM cadu_reports_accounts acc
    LEFT JOIN cadu_reports_gads_action_agents ag ON ag.client_id=acc.client_id
        AND ag.account_external_id=regexp_replace(acc.external_id,'\\D','','g')
    WHERE acc.client_id=%(client)s AND acc.platform='google_ads' AND acc.account_kind='advertiser' AND acc.status<>'disabled'
    ORDER BY acc.name'''


def _account(client_id, account_id):
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        _bad('Conta inválida.')
    rows = _rows('''SELECT id,external_id,name FROM cadu_reports_accounts WHERE id=%s AND client_id=%s AND platform='google_ads'
            AND account_kind='advertiser' AND status<>'disabled' ''', (account_id, client_id))
    if not rows:
        abort(404, description='Conta Google Ads não encontrada neste cliente.')
    external = re.sub(r'\D', '', rows[0]['external_id'] or '')
    if len(external) != 10:
        _bad('A conta precisa de um ID Google Ads de 10 dígitos.')
    return rows[0], external


def _queue(selected, account, external, op, target, params, expect, label, origin, recommendation_id, undo_of=None):
    target, params, expect, note = normalize(op, target, params, expect, _limits_for(selected['client_id'], external))
    duplicate = _rows('''SELECT id,status FROM cadu_reports_gads_actions WHERE client_id=%s AND account_external_id=%s AND op=%s
            AND target=%s::jsonb AND params=%s::jsonb AND status IN ('approved','sent') LIMIT 1''',
                      (selected['client_id'], external, op, _json(target), _json(params)))
    if duplicate:
        return {'id': str(duplicate[0]['id']), 'status': duplicate[0]['status'], 'duplicate': True}
    label = ' '.join(str(label or '').split())[:300] or f"{VERBS[op]} · {account['name']}"
    if note:
        label = f'{label} ({note.rstrip(".").lower()})'[:300]
    action_id = str(uuid.uuid4())
    _rows('''INSERT INTO cadu_reports_gads_actions (id,client_id,account_id,account_external_id,op,target,params,expect,label,status,
            origin,recommendation_id,undo_of,created_by,approved_by,approved_at,expires_at)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,'approved',%s,%s,%s,%s,%s,NOW(),NOW() + %s * INTERVAL '1 hour')
        RETURNING id''',
          (action_id, selected['client_id'], account['id'], external, op, _json(target), _json(params), _json(expect), label,
           origin, recommendation_id, undo_of, selected['user_id'], selected['user_id'], EXPIRES_HOURS))
    return {'id': action_id, 'status': 'approved', 'duplicate': False, 'note': note}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _version(text):
    return tuple(int(part) for part in re.findall(r'\d+', str(text or ''))[:3])


def _script_scope():
    key = _authenticate(SOURCE_KIND)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        _bad('Corpo inválido.')
    account = _google_id(payload.get('account_id'), 'ID da conta', account=True)
    manager = payload.get('manager_account_id')
    manager_id = _google_id(manager, 'ID da MCC', account=True) if manager else None
    _authorize_scope(key, manager_id, account)
    return key, payload, account


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def register(bp):
    # ---- Script side (Bearer key of kind google_ads_actions) -------------------------------------------------------
    @bp.post('/api/gads/actions/next')
    def reports_gads_actions_next():
        """Approved commands for one account. Claiming leases them; an unanswered lease is offered again later."""
        key, payload, account = _script_scope()
        if not tables_ready():
            abort(503, description='Ações do Google Ads ainda não habilitadas no Reports.')
        limits = payload.get('limits') if isinstance(payload.get('limits'), dict) else {}
        _rows('''INSERT INTO cadu_reports_gads_action_agents (client_id,account_external_id,key_id,engine_version,allow_writes,preview,limits)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (client_id,account_external_id) DO UPDATE SET key_id=EXCLUDED.key_id,engine_version=EXCLUDED.engine_version,
                allow_writes=EXCLUDED.allow_writes,preview=EXCLUDED.preview,limits=EXCLUDED.limits,
                previous_poll_at=CASE WHEN cadu_reports_gads_action_agents.preview THEN cadu_reports_gads_action_agents.previous_poll_at
                    ELSE cadu_reports_gads_action_agents.last_poll_at END,
                last_poll_at=NOW() RETURNING client_id''',
              (key['client_id'], account, key['id'], str(payload.get('engine_version') or '')[:20], payload.get('allow_writes') is not False,
               payload.get('preview') is True, _json({k: limits[k] for k in list(limits)[:5] if isinstance(limits[k], (int, float))})))
        _expire(key['client_id'], account)
        commands = _rows(f'''UPDATE cadu_reports_gads_actions SET status='sent',sent_at=NOW(),attempts=attempts+1
            WHERE id IN (SELECT id FROM cadu_reports_gads_actions
                WHERE client_id=%s AND account_external_id=%s AND expires_at > NOW()
                    AND (status='approved' OR (status='sent' AND sent_at < NOW() - INTERVAL '{LEASE_MINUTES} minutes'))
                ORDER BY created_at LIMIT {MAX_CLAIM} FOR UPDATE SKIP LOCKED)
            RETURNING id,op,target,params,expect,label,expires_at,created_at''', (key['client_id'], account))
        _rows('UPDATE cadu_reports_ingest_keys SET last_used_at=NOW() WHERE id=%s RETURNING id', (key['id'],))
        get_db().commit()
        commands.sort(key=lambda row: row['created_at'])
        return jsonify(commands=[{'id': str(row['id']), 'op': row['op'], 'target': row['target'], 'params': row['params'],
                                  'expect': row['expect'], 'label': row['label'], 'expires_at': _iso(row['expires_at'])} for row in commands],
                       schedule_minutes=SCHEDULE_MINUTES, latest_version=ENGINE_VERSION)

    @bp.post('/api/gads/actions/result')
    def reports_gads_actions_result():
        """What the script did with each claimed command. Simulations and deferred ones go back to the queue."""
        key, payload, account = _script_scope()
        results = payload.get('results')
        if not isinstance(results, list) or len(results) > MAX_CLAIM:
            _bad(f'Envie até {MAX_CLAIM} resultados.')
        done = 0
        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                action_id = str(uuid.UUID(str(item.get('id'))))
            except ValueError:
                continue
            state = item.get('status')
            if state not in ('applied', 'failed', 'skipped', 'requeue'):
                continue
            message = ' '.join(str(item.get('message') or '').split())[:300]
            observed = item.get('observed') if isinstance(item.get('observed'), dict) else {}
            observed = {k: v for k, v in list(observed.items())[:8] if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 40}
            result = _json({'message': message, 'observed': observed, 'simulated': bool(item.get('simulated')),
                            'engine_version': str(payload.get('engine_version') or '')[:20]})
            if state == 'requeue' or item.get('simulated'):
                updated = _rows('''UPDATE cadu_reports_gads_actions SET status='approved',sent_at=NULL,result=%s::jsonb
                    WHERE id=%s AND client_id=%s AND account_external_id=%s AND status='sent' RETURNING id''',
                                (result, action_id, key['client_id'], account))
            else:
                updated = _rows('''UPDATE cadu_reports_gads_actions SET status=%s,finished_at=NOW(),result=%s::jsonb
                    WHERE id=%s AND client_id=%s AND account_external_id=%s AND status='sent' RETURNING id''',
                                (state, result, action_id, key['client_id'], account))
            done += len(updated)
        get_db().commit()
        return jsonify(recorded=done)

    # ---- Reports side (session) --------------------------------------------------------------------------------------
    @bp.get('/api/v2/reports/google-ads/actions')
    @login_required_api
    def reports_google_ads_actions():
        """The queue and the history, plus each account's Ações script: installed, last contact and next expected run."""
        selected = _selection()
        if not tables_ready():
            return jsonify(ready=False, actions=[], accounts=[], schedule_minutes=SCHEDULE_MINUTES, latest_version=ENGINE_VERSION,
                           limits=DEFAULT_LIMITS, server_time=datetime.now(timezone.utc).isoformat())
        _expire(selected['client_id'])
        get_db().commit()
        now = datetime.now(timezone.utc)
        accounts = []
        for row in _rows(_ACCOUNTS_SQL, {'client': selected['client_id'], 'kind': SOURCE_KIND}):
            expected = next_run(row['last_poll_at'], row['previous_poll_at'], now)
            accounts.append({'account_id': row['id'], 'name': row['name'], 'external_id': row['external_id'], 'has_key': row['has_key'],
                             'last_poll_at': _iso(row['last_poll_at']), 'next_run_at': _iso(expected),
                             'engine_version': row['engine_version'], 'outdated': bool(row['engine_version']) and _version(row['engine_version']) < _version(ENGINE_VERSION),
                             'allow_writes': row['allow_writes'] if row['last_poll_at'] else None, 'preview': row['preview'],
                             'limits': _limits_for(selected['client_id'], re.sub(r'\D', '', row['external_id'] or ''))})
        return jsonify(ready=True, actions=[_public(row) for row in _rows(_LIST_SQL, (selected['client_id'],))], accounts=accounts,
                       schedule_minutes=SCHEDULE_MINUTES, latest_version=ENGINE_VERSION, limits=DEFAULT_LIMITS, server_time=now.isoformat())

    @bp.post('/api/v2/reports/google-ads/actions')
    @login_required_api
    def reports_google_ads_actions_create():
        """Approve one or more changes. Anyone who can edit the client approves; the next hourly run applies them."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            _bad('Corpo inválido.')
        selected = _selection(payload)
        _write_guard(selected)
        if not tables_ready():
            abort(503, description='Aplique a migração add_reports_google_ads_actions.sql para usar as ações.')
        items = payload.get('items')
        if not isinstance(items, list) or not 0 < len(items) <= MAX_BATCH:
            _bad(f'Envie de 1 a {MAX_BATCH} ações.')
        created, accounts = [], {}
        for item in items:
            if not isinstance(item, dict):
                _bad('Ação inválida.')
            account_key = item.get('account_id')
            if account_key not in accounts:
                accounts[account_key] = _account(selected['client_id'], account_key)
            account, external = accounts[account_key]
            recommendation = str(item.get('recommendation_id') or '')[:200] or None
            origin = f'rule:{recommendation.split(":", 1)[0]}' if recommendation else 'manual'
            created.append(_queue(selected, account, external, item.get('op'), item.get('target'), item.get('params'), item.get('expect'),
                                  item.get('label'), origin[:80], recommendation))
        get_db().commit()
        return jsonify(created=created, expires_hours=EXPIRES_HOURS), 201

    @bp.post('/api/v2/reports/google-ads/actions/<action_id>/cancel')
    @login_required_api
    def reports_google_ads_action_cancel(action_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        row = _rows("SELECT status FROM cadu_reports_gads_actions WHERE id::text=%s AND client_id=%s", (action_id, selected['client_id']))
        if not row:
            abort(404)
        if row[0]['status'] == 'sent':
            abort(409, description='O script já recebeu esta ação nesta execução. Aguarde o resultado e desfaça se precisar.')
        updated = _rows('''UPDATE cadu_reports_gads_actions SET status='cancelled',finished_at=NOW()
            WHERE id::text=%s AND client_id=%s AND status='approved' RETURNING id''', (action_id, selected['client_id']))
        get_db().commit()
        if not updated:
            abort(409, description='Esta ação não está mais na fila.')
        return jsonify(cancelled=True)

    @bp.post('/api/v2/reports/google-ads/actions/<action_id>/undo')
    @login_required_api
    def reports_google_ads_action_undo(action_id):
        """Queue the opposite change of an applied one (pause ↔ enable, negative ↔ removal, previous budget or bid)."""
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        rows = _rows('''SELECT a.*,EXISTS (SELECT 1 FROM cadu_reports_gads_actions u WHERE u.undo_of=a.id
                AND u.status NOT IN ('cancelled','expired','failed')) AS undone
            FROM cadu_reports_gads_actions a WHERE a.id::text=%s AND a.client_id=%s''', (action_id, selected['client_id']))
        if not rows:
            abort(404)
        action = rows[0]
        if action['status'] != 'applied':
            abort(409, description='Só é possível desfazer uma ação aplicada.')
        if action['undone']:
            abort(409, description='Esta ação já tem um desfazer na fila ou aplicado.')
        opposite = inverse(action)
        if not opposite:
            abort(409, description='Esta ação não pode ser desfeita automaticamente.')
        op, target, params, expect = opposite
        account, external = _account(selected['client_id'], action['account_id'])
        label = f"Desfazer: {action['label']}"
        created = _queue(selected, account, external, op, target, params, expect, label, 'undo', action['recommendation_id'],
                         undo_of=str(action['id']))
        get_db().commit()
        return jsonify(created=created), 201
