"""Scoped, idempotent Google Ads Script ingestion for Reports."""
import hashlib
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from flask import abort, jsonify, request, session

from ..auth import login_required_api
from ..cadu_family import context
from ..db import get_db
from .reports_v1 import _ready, _rows, _selection, _write_guard


MAX_BODY_BYTES = 1_000_000
MAX_RECORDS = 500


def _google_id(value, name, *, account=False):
    raw = str(value or '').strip()
    if not re.fullmatch(r'[0-9-]+', raw):
        abort(400, description=f'{name} inválido.')
    normalized = raw.replace('-', '')
    if not normalized.isdigit() or len(normalized) > 20 or (account and len(normalized) != 10):
        abort(400, description=f'{name} inválido.')
    return normalized


def _text(value, name, limit=240):
    if not isinstance(value, str):
        abort(400, description=f'{name} inválido.')
    value = ' '.join(value.strip().split())
    if not value or len(value) > limit:
        abort(400, description=f'{name} inválido.')
    return value


def _integer(value, name):
    if isinstance(value, bool):
        abort(400, description=f'{name} inválido.')
    try:
        number = int(value)
    except (TypeError, ValueError):
        abort(400, description=f'{name} inválido.')
    if number < 0 or number > 9_000_000_000_000_000:
        abort(400, description=f'{name} fora do limite.')
    return number


def _conversions(value):
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        abort(400, description='Conversões inválidas.')
    if not number.is_finite() or number < 0 or number >= Decimal('100000000000000'):
        abort(400, description='Conversões fora do limite.')
    return number.quantize(Decimal('0.0001'))


def _record(value):
    if not isinstance(value, dict):
        abort(400, description='Registro de campanha inválido.')
    try:
        metric_date = date.fromisoformat(str(value.get('date') or ''))
    except ValueError:
        abort(400, description='Data de métrica inválida.')
    if metric_date > date.today() or metric_date < date.today() - timedelta(days=400):
        abort(400, description='Data fora da janela permitida.')
    account_id = _google_id(value.get('account_id'), 'ID da conta', account=True)
    campaign_id = _google_id(value.get('campaign_id'), 'ID da campanha')
    currency = str(value.get('currency') or '').upper()
    if currency and not re.fullmatch(r'[A-Z]{3}', currency):
        abort(400, description='Moeda inválida.')
    return {
        'account_id': account_id,
        'account_name': _text(value.get('account_name'), 'Nome da conta'),
        'campaign_id': campaign_id,
        'campaign_name': _text(value.get('campaign_name'), 'Nome da campanha'),
        'date': metric_date,
        'currency': currency or None,
        'impressions': _integer(value.get('impressions', 0), 'Impressões'),
        'clicks': _integer(value.get('clicks', 0), 'Cliques'),
        'cost_micros': _integer(value.get('cost_micros', 0), 'Custo'),
        'conversions': _conversions(value.get('conversions', 0)),
        'conversion_value_micros': _integer(value.get('conversion_value_micros', 0), 'Valor de conversão'),
    }


def _webhook_event(value):
    allowed = {'external_event_id', 'visitor_id', 'campaign_id', 'kind', 'occurred_at',
               'value_micros', 'currency'}
    if not isinstance(value, dict) or set(value) - allowed:
        abort(400, description='Evento inválido. Envie apenas os campos documentados, sem dados pessoais.')
    external_id = _text(value.get('external_event_id'), 'ID externo do evento', 160)
    if '@' in external_id:
        abort(400, description='Use um ID opaco para o evento, sem email.')
    kind = value.get('kind')
    if kind not in ('lead', 'qualified_lead', 'sale'):
        abort(400, description='Tipo de conversão inválido.')
    visitor_id = value.get('visitor_id') or None
    if visitor_id:
        try:
            visitor_id = str(uuid.UUID(str(visitor_id)))
        except (ValueError, TypeError, AttributeError):
            abort(400, description='ID do visitante inválido.')
    campaign_id = value.get('campaign_id') or None
    if campaign_id:
        try:
            campaign_id = int(campaign_id)
        except (ValueError, TypeError):
            abort(400, description='Campanha inválida.')
        if campaign_id < 1:
            abort(400, description='Campanha inválida.')
    if not visitor_id and not campaign_id:
        abort(400, description='Informe visitor_id ou campaign_id para atribuir a conversão.')
    raw_time = value.get('occurred_at')
    if raw_time is not None and not isinstance(raw_time, str):
        abort(400, description='Data da conversão inválida.')
    try:
        occurred_at = (datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                       if isinstance(raw_time, str) else datetime.now(timezone.utc))
    except ValueError:
        abort(400, description='Data da conversão inválida.')
    if occurred_at.tzinfo is None:
        abort(400, description='A data da conversão precisa incluir fuso horário.')
    now = datetime.now(timezone.utc)
    if occurred_at > now + timedelta(minutes=5) or occurred_at < now - timedelta(days=400):
        abort(400, description='Data da conversão fora da janela permitida.')
    value_micros = None if value.get('value_micros') is None else _integer(value['value_micros'], 'Valor da conversão')
    currency = value.get('currency') or None
    if currency:
        currency = str(currency).upper()
        if not re.fullmatch(r'[A-Z]{3}', currency):
            abort(400, description='Moeda inválida.')
    if value_micros is not None and not currency:
        abort(400, description='Informe a moeda do valor da conversão.')
    return {'external_event_id': external_id, 'visitor_id': visitor_id, 'campaign_id': campaign_id,
            'kind': kind, 'occurred_at': occurred_at, 'value_micros': value_micros, 'currency': currency}


def register(bp):
    @bp.get('/api/v1/reports/ingest-keys')
    @login_required_api
    def reports_ingest_keys():
        selected = _selection()
        if not _ready():
            return jsonify(keys=[])
        keys = _rows('''SELECT id,label,source_kind,created_at,last_used_at,revoked_at
                FROM cadu_reports_ingest_keys WHERE organization_id=%s AND client_id=%s
                ORDER BY created_at DESC''', (selected['organization_id'], selected['client_id']))
        runs = _rows('''SELECT id,source_kind,status,record_count,period_start,period_end,
                created_at,finished_at FROM cadu_reports_source_runs
                WHERE organization_id=%s AND client_id=%s
                ORDER BY created_at DESC LIMIT 20''',
                (selected['organization_id'], selected['client_id']))
        return jsonify(keys=keys, runs=runs)

    @bp.post('/api/v1/reports/ingest-keys')
    @login_required_api
    def reports_create_ingest_key():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _ready():
            abort(503)
        label = _text(payload.get('label'), 'Nome da chave', 120)
        source_kind = payload.get('source_kind', 'google_ads_script')
        if source_kind not in ('google_ads_script', 'conversion_webhook'):
            abort(400, description='Tipo de integração inválido.')
        token = secrets.token_urlsafe(32)
        key_id = str(uuid.uuid4())
        _rows('''INSERT INTO cadu_reports_ingest_keys
                (id,organization_id,client_id,label,token_hash,source_kind,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (key_id, selected['organization_id'], selected['client_id'], label,
                 hashlib.sha256(token.encode()).hexdigest(), source_kind, session['user_id']))
        get_db().commit()
        return jsonify(id=key_id, token=token, label=label, source_kind=source_kind), 201

    @bp.post('/api/v1/reports/ingest-keys/<key_id>/revoke')
    @login_required_api
    def reports_revoke_ingest_key(key_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        updated = _rows('''UPDATE cadu_reports_ingest_keys SET revoked_at=NOW()
                WHERE id::text=%s AND organization_id=%s AND client_id=%s AND revoked_at IS NULL
                RETURNING id''', (key_id, selected['organization_id'], selected['client_id']))
        get_db().commit()
        if not updated:
            abort(404)
        return jsonify(revoked=True)

    @bp.post('/api/v1/reports/ingest/google-ads')
    def reports_ingest_google_ads():
        if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
            abort(413)
        raw = request.get_data(cache=True)
        if len(raw) > MAX_BODY_BYTES:
            abort(413)
        bearer = request.headers.get('Authorization', '')
        token = bearer[7:].strip() if bearer.startswith('Bearer ') else ''
        if not token or len(token) > 128:
            abort(401)
        key = _rows('''SELECT id,organization_id,client_id FROM cadu_reports_ingest_keys
                WHERE token_hash=%s AND source_kind='google_ads_script' AND revoked_at IS NULL''',
                (hashlib.sha256(token.encode()).hexdigest(),))
        if not key:
            abort(401)
        key = key[0]
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description='Envie um objeto JSON.')
        run_key = _text(payload.get('run_key'), 'Identificador do lote', 200)
        manager_id = payload.get('manager_account_id')
        manager_id = _google_id(manager_id, 'ID da MCC', account=True) if manager_id else None
        values = payload.get('records')
        if not isinstance(values, list) or not values or len(values) > MAX_RECORDS:
            abort(400, description='Envie de 1 a 500 registros.')
        records = [_record(value) for value in values]
        unique = {(item['account_id'], item['campaign_id'], item['date']) for item in records}
        if len(unique) != len(records):
            abort(400, description='O lote contém campanha e data duplicadas.')
        org, client = key['organization_id'], key['client_id']
        run_id = str(uuid.uuid4())
        inserted = _rows('''INSERT INTO cadu_reports_source_runs
                (id,organization_id,client_id,source_kind,external_run_key,period_start,period_end,status,record_count)
                VALUES (%s,%s,%s,'google_ads_script',%s,%s,%s,'processing',%s)
                ON CONFLICT (organization_id,client_id,source_kind,external_run_key) DO NOTHING RETURNING id''',
                (run_id, org, client, run_key, min(item['date'] for item in records),
                 max(item['date'] for item in records), len(records)))
        if not inserted:
            get_db().rollback()
            return jsonify(accepted=True, duplicate=True, records=0)
        manager_pk = None
        if manager_id:
            manager = _rows('''INSERT INTO cadu_reports_accounts
                    (organization_id,client_id,platform,external_id,name,account_kind)
                    VALUES (%s,%s,'google_ads',%s,%s,'manager')
                    ON CONFLICT (organization_id,client_id,platform,external_id)
                    DO UPDATE SET updated_at=NOW() RETURNING id''',
                    (org, client, manager_id, f'MCC {manager_id}'))
            manager_pk = manager[0]['id']
        account_cache = {}
        campaign_cache = {}
        for item in records:
            account_pk = account_cache.get(item['account_id'])
            if not account_pk:
                account = _rows('''INSERT INTO cadu_reports_accounts
                        (organization_id,client_id,platform,external_id,name,parent_account_id,account_kind,currency)
                        VALUES (%s,%s,'google_ads',%s,%s,%s,'advertiser',%s)
                        ON CONFLICT (organization_id,client_id,platform,external_id)
                        DO UPDATE SET name=EXCLUDED.name,
                          currency=COALESCE(EXCLUDED.currency,cadu_reports_accounts.currency),
                          parent_account_id=COALESCE(EXCLUDED.parent_account_id,cadu_reports_accounts.parent_account_id),
                          updated_at=NOW()
                        RETURNING id''', (org, client, item['account_id'], item['account_name'], manager_pk, item['currency']))
                account_pk = account_cache[item['account_id']] = account[0]['id']
            campaign_key = (account_pk, item['campaign_id'])
            campaign_pk = campaign_cache.get(campaign_key)
            if not campaign_pk:
                campaign = _rows('''INSERT INTO cadu_reports_campaigns
                        (organization_id,client_id,account_id,external_id,name)
                        VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (account_id,external_id)
                        DO UPDATE SET name=EXCLUDED.name,updated_at=NOW() RETURNING id''',
                        (org, client, account_pk, item['campaign_id'], item['campaign_name']))
                campaign_pk = campaign_cache[campaign_key] = campaign[0]['id']
            _rows('''INSERT INTO cadu_reports_campaign_daily_metrics
                    (organization_id,client_id,campaign_id,metric_date,source_kind,impressions,clicks,
                     cost_micros,conversions,conversion_value_micros,last_run_id)
                    VALUES (%s,%s,%s,%s,'google_ads_script',%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (campaign_id,metric_date,source_kind)
                    DO UPDATE SET impressions=EXCLUDED.impressions,clicks=EXCLUDED.clicks,
                      cost_micros=EXCLUDED.cost_micros,conversions=EXCLUDED.conversions,
                      conversion_value_micros=EXCLUDED.conversion_value_micros,
                      last_run_id=EXCLUDED.last_run_id,updated_at=NOW() RETURNING campaign_id''',
                    (org, client, campaign_pk, item['date'], item['impressions'], item['clicks'],
                     item['cost_micros'], item['conversions'], item['conversion_value_micros'], run_id))
        _rows("UPDATE cadu_reports_source_runs SET status='completed',finished_at=NOW() WHERE id=%s RETURNING id", (run_id,))
        _rows('UPDATE cadu_reports_ingest_keys SET last_used_at=NOW() WHERE id=%s RETURNING id', (key['id'],))
        get_db().commit()
        return jsonify(accepted=True, duplicate=False, records=len(records), client_id=client)

    @bp.post('/api/v1/reports/ingest/conversions')
    def reports_ingest_conversions():
        if request.content_length is not None and request.content_length > 100_000:
            abort(413)
        raw = request.get_data(cache=True)
        if len(raw) > 100_000:
            abort(413)
        bearer = request.headers.get('Authorization', '')
        token = bearer[7:].strip() if bearer.startswith('Bearer ') else ''
        if not token or len(token) > 128:
            abort(401)
        keys = _rows('''SELECT id,organization_id,client_id FROM cadu_reports_ingest_keys
            WHERE token_hash=%s AND source_kind='conversion_webhook' AND revoked_at IS NULL''',
            (hashlib.sha256(token.encode()).hexdigest(),))
        if not keys:
            abort(401)
        key = keys[0]
        payload = request.get_json(silent=True)
        values = payload.get('events') if isinstance(payload, dict) else None
        if not isinstance(values, list) or not 1 <= len(values) <= 100:
            abort(400, description='Envie de 1 a 100 eventos.')
        events = [_webhook_event(value) for value in values]
        if len({event['external_event_id'] for event in events}) != len(events):
            abort(400, description='O lote contém IDs de evento duplicados.')
        params = (key['organization_id'], key['client_id'])
        accepted = 0
        for event in events:
            campaign_id = event['campaign_id']
            method = 'explicit_campaign' if campaign_id else None
            if campaign_id and not _rows('''SELECT id FROM cadu_reports_campaigns
                    WHERE organization_id=%s AND client_id=%s AND id=%s''', (*params, campaign_id)):
                abort(404, description='Campanha fora deste cliente.')
            if not campaign_id and event['visitor_id']:
                candidates = _rows('''SELECT DISTINCT campaign_id FROM cadu_reports_flow_events
                    WHERE organization_id=%s AND client_id=%s AND visitor_id=%s
                        AND campaign_id IS NOT NULL AND occurred_at <= %s
                        AND occurred_at >= %s - INTERVAL '90 days' LIMIT 2''',
                    (*params, event['visitor_id'], event['occurred_at'], event['occurred_at']))
                if len(candidates) == 1:
                    campaign_id, method = candidates[0]['campaign_id'], 'visitor'
            inserted = _rows('''INSERT INTO cadu_reports_external_conversions
                (organization_id,client_id,external_event_id,visitor_id,campaign_id,attribution_method,
                 conversion_kind,occurred_at,value_micros,currency)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (organization_id,client_id,source_kind,external_event_id)
                DO NOTHING RETURNING id''',
                (*params, event['external_event_id'], event['visitor_id'], campaign_id, method,
                 event['kind'], event['occurred_at'], event['value_micros'], event['currency']))
            accepted += bool(inserted)
        _rows('UPDATE cadu_reports_ingest_keys SET last_used_at=NOW() WHERE id=%s RETURNING id', (key['id'],))
        get_db().commit()
        return jsonify(accepted=accepted, duplicates=len(events) - accepted)

    @bp.get('/api/v1/reports/metrics')
    @login_required_api
    def reports_metrics():
        selected = _selection()
        if not _ready():
            return jsonify(days=[], totals={}, by_platform=[])
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            abort(400)
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        cutoff = date.today() - timedelta(days=days - 1)
        filters = ''
        params = [selected['organization_id'], selected['client_id'], cutoff]
        platform = request.args.get('platform', '').strip()
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', platform):
                abort(400, description='Plataforma inválida.')
            filters += ' AND a.platform=%s'
            params.append(platform)
        for field, column in (('account_id', 'a.id'), ('campaign_id', 'c.id')):
            supplied = request.args.get(field, '').strip()
            if supplied:
                try:
                    value = int(supplied)
                except ValueError:
                    abort(400, description=f'{field} inválido.')
                if value < 1:
                    abort(400, description=f'{field} inválido.')
                filters += f' AND {column}=%s'
                params.append(value)
        joins = '''JOIN cadu_reports_campaigns c ON c.id=m.campaign_id
                JOIN cadu_reports_accounts a ON a.id=c.account_id'''
        daily = _rows('''SELECT m.metric_date AS date,SUM(m.impressions)::bigint AS impressions,
                SUM(m.clicks)::bigint AS clicks,SUM(m.cost_micros)::bigint AS cost_micros,
                SUM(m.conversions)::numeric AS conversions
                FROM cadu_reports_campaign_daily_metrics m ''' + joins + '''
                WHERE m.organization_id=%s AND m.client_id=%s AND m.metric_date >= %s
                ''' + filters + ''' GROUP BY m.metric_date ORDER BY m.metric_date''', tuple(params))
        platforms = _rows('''SELECT a.platform,SUM(m.impressions)::bigint AS impressions,
                SUM(m.clicks)::bigint AS clicks,SUM(m.cost_micros)::bigint AS cost_micros,
                SUM(m.conversions)::numeric AS conversions
                FROM cadu_reports_campaign_daily_metrics m ''' + joins + '''
                WHERE m.organization_id=%s AND m.client_id=%s AND m.metric_date >= %s
                ''' + filters + ''' GROUP BY a.platform ORDER BY cost_micros DESC''', tuple(params))
        currencies = _rows('''SELECT DISTINCT COALESCE(a.currency,'') AS currency
                FROM cadu_reports_campaign_daily_metrics m ''' + joins + '''
                WHERE m.organization_id=%s AND m.client_id=%s AND m.metric_date >= %s
                ''' + filters, tuple(params))
        currency = currencies[0]['currency'] if len(currencies) == 1 and currencies[0]['currency'] else None
        if not currency:
            for row in daily + platforms:
                row['cost_micros'] = None
        totals = {field: sum(row[field] or 0 for row in daily) for field in
                  ('impressions', 'clicks', 'cost_micros', 'conversions')}
        if not currency:
            totals['cost_micros'] = None
        observed = _rows('''SELECT COUNT(DISTINCT e.visitor_id)::bigint AS total
                FROM cadu_reports_flow_events e
                LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
                LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE e.organization_id=%s AND e.client_id=%s AND e.occurred_at >= %s
                    AND e.event_kind='conversion' ''' + filters, tuple(params))[0]['total']
        confirmed = _rows('''SELECT COUNT(*)::bigint AS total
                FROM cadu_reports_external_conversions x
                LEFT JOIN cadu_reports_campaigns c ON c.id=x.campaign_id
                LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
                WHERE x.organization_id=%s AND x.client_id=%s AND x.occurred_at >= %s
                ''' + filters, tuple(params))[0]['total']
        return jsonify(days=daily, totals=totals, by_platform=platforms, period_days=days,
                       currency=currency, source='google_ads_script',
                       observed_conversions=observed, confirmed_conversions=confirmed)
