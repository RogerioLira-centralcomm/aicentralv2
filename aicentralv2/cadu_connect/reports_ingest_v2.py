"""Google Ads engine v2 ingestion for Reports.

One authenticated endpoint receives typed *datasets* from the Google Ads Script engine:

* daily metrics (campaign, ad group, keyword, search term, device) are upserted by natural key;
* snapshots (campaign settings, negative keywords) are upserted and, on the final chunk, anything
  the snapshot no longer contains is stamped ``removed_at`` so the change history survives;
* ``run_summary`` is the heartbeat: it arrives even when every dataset is empty, so the monitor can
  tell "connected but nothing to send" apart from "never connected".

Every chunk is idempotent through ``cadu_reports_source_runs`` so the script can retry safely.
"""
import hashlib
import json
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import abort, jsonify, request

from ..db import get_db
from .reports_page_identity import split_url
from .reports_ingest import MAX_BODY_BYTES, MAX_RECORDS, _google_id, _record, _text
from .reports_v1 import _rows


SCHEMA_VERSION = 2
CHUNK_SOURCE_KIND = 'google_ads_engine_v2_chunk'
SUMMARY_SOURCE_KIND = 'google_ads_engine_v2'
MAX_SUMMARY_BYTES = 20_000
MATCH_TYPES = ('EXACT', 'PHRASE', 'BROAD')
DEVICES = ('MOBILE', 'DESKTOP', 'TABLET', 'CONNECTED_TV', 'OTHER', 'UNKNOWN', 'UNSPECIFIED')
SUMMARY_STATUSES = ('ok', 'error', 'skipped', 'truncated', 'empty')


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

def _enum_text(value, name, default='UNKNOWN', limit=40):
    raw = str(value if value not in (None, '') else default).upper()
    if not re.fullmatch(r'[A-Z_]{1,%d}' % limit, raw):
        abort(400, description=f'{name} inválido.')
    return raw


def _count(value, name):
    if isinstance(value, bool):
        abort(400, description=f'{name} inválido.')
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        abort(400, description=f'{name} inválido.')
    if number < 0 or number > 9_000_000_000_000_000:
        abort(400, description=f'{name} fora do limite.')
    return number


def _decimal(value, name):
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        abort(400, description=f'{name} inválido.')
    if not number.is_finite() or number < 0 or number >= Decimal('100000000000000'):
        abort(400, description=f'{name} fora do limite.')
    return number.quantize(Decimal('0.0001'))


def _metric_date(value):
    try:
        parsed = date.fromisoformat(str(value or ''))
    except ValueError:
        abort(400, description='Data de métrica inválida.')
    today = date.today()
    # One day of tolerance: the account time zone can be ahead of the server clock.
    if parsed > today + timedelta(days=1) or parsed < today - timedelta(days=400):
        abort(400, description='Data fora da janela permitida.')
    return parsed


def _metrics(value):
    return {
        'impressions': _count(value.get('impressions'), 'Impressões'),
        'clicks': _count(value.get('clicks'), 'Cliques'),
        'cost_micros': _count(value.get('cost_micros'), 'Custo'),
        'conversions': _decimal(value.get('conversions'), 'Conversões'),
        'conversion_value_micros': _count(value.get('conversion_value_micros'), 'Valor de conversão'),
    }


def _entity(value, prefix):
    return {
        f'{prefix}_external_id': _google_id(value.get(f'{prefix}_id'), f'ID de {prefix}'),
        f'{prefix}_name': _text(value.get(f'{prefix}_name'), f'Nome de {prefix}'),
    }


def _optional_entity(value, prefix):
    if not value.get(f'{prefix}_id'):
        return {f'{prefix}_external_id': None, f'{prefix}_name': None}
    return _entity(value, prefix)


def _require_dict(value):
    if not isinstance(value, dict):
        abort(400, description='Registro inválido.')
    return value


# ---------------------------------------------------------------------------
# Dataset normalizers: raw JSON -> validated row. Each returns (natural_key, row).
# ---------------------------------------------------------------------------

def _norm_ad_group_metrics(value):
    value = _require_dict(value)
    row = {**_entity(value, 'campaign'), **_entity(value, 'ad_group'),
           'ad_group_status': _enum_text(value.get('ad_group_status'), 'Estado do grupo'),
           'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['ad_group_external_id'], row['metric_date']), row


def _norm_keyword_metrics(value):
    value = _require_dict(value)
    quality = value.get('quality_score')
    if quality is not None:
        quality = _count(quality, 'Índice de Qualidade')
        quality = quality if 1 <= quality <= 10 else None
    match_type = _enum_text(value.get('match_type'), 'Tipo de correspondência', 'BROAD', 16)
    if match_type not in MATCH_TYPES:
        abort(400, description='Tipo de correspondência inválido.')
    row = {**_entity(value, 'campaign'), **_entity(value, 'ad_group'),
           'criterion_external_id': _google_id(value.get('criterion_id'), 'ID da palavra-chave'),
           'keyword_text': _text(value.get('keyword_text'), 'Palavra-chave'),
           'match_type': match_type,
           'keyword_status': _enum_text(value.get('keyword_status'), 'Estado da palavra-chave'),
           'quality_score': quality, 'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['ad_group_external_id'], row['criterion_external_id'], row['metric_date']), row


def _norm_search_term_metrics(value):
    value = _require_dict(value)
    term = _text(value.get('search_term'), 'Termo de pesquisa', 800)
    row = {**_entity(value, 'campaign'), **_entity(value, 'ad_group'),
           'search_term': term, 'term_hash': hashlib.md5(term.lower().encode()).hexdigest(),
           'term_status': _enum_text(value.get('term_status'), 'Estado do termo', 'NONE'),
           'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['ad_group_external_id'], row['term_hash'], row['metric_date']), row


def _norm_device_metrics(value):
    value = _require_dict(value)
    device = _enum_text(value.get('device'), 'Dispositivo', 'UNKNOWN', 24)
    if device not in DEVICES:
        device = 'OTHER'
    row = {**_entity(value, 'campaign'), 'device': device,
           'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['campaign_external_id'], device, row['metric_date']), row


def _norm_landing_page_metrics(value):
    value = _require_dict(value)
    raw = str(value.get('final_url') or '').strip()
    page = split_url(raw) if len(raw) <= 2000 else None
    if not page or len(page[0]) > 253:
        abort(400, description='URL de destino inválida.')
    host, path = page
    row = {**_entity(value, 'campaign'), 'final_url': raw, 'url_hash': hashlib.md5(raw.encode()).hexdigest(),
           'page_host': host, 'page_path': path[:500], 'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['campaign_external_id'], row['url_hash'], row['metric_date']), row


def _norm_campaign_settings(value):
    value = _require_dict(value)
    budget = value.get('budget_micros')
    shared = value.get('budget_shared')
    row = {**_entity(value, 'campaign'),
           'status': _enum_text(value.get('status'), 'Estado da campanha'),
           'serving_status': _enum_text(value.get('serving_status'), 'Status de veiculação') if value.get('serving_status') else None,
           'channel_type': _enum_text(value.get('channel_type'), 'Tipo de campanha', limit=64) if value.get('channel_type') else None,
           'bidding_strategy_type': (_enum_text(value.get('bidding_strategy_type'), 'Estratégia de lances', limit=64)
                                     if value.get('bidding_strategy_type') else None),
           'budget_micros': None if budget is None else _count(budget, 'Orçamento'),
           'budget_shared': shared if isinstance(shared, bool) else None}
    return (row['campaign_external_id'],), row


def _norm_negative_keyword(value):
    value = _require_dict(value)
    level = value.get('level')
    if level not in ('campaign', 'ad_group', 'shared_list'):
        abort(400, description='Nível da palavra negativa inválido.')
    match_type = _enum_text(value.get('match_type'), 'Tipo de correspondência', 'BROAD', 16)
    if match_type not in MATCH_TYPES:
        abort(400, description='Tipo de correspondência inválido.')
    campaign = _entity(value, 'campaign') if level != 'shared_list' else _optional_entity(value, 'campaign')
    ad_group = _entity(value, 'ad_group') if level == 'ad_group' else {'ad_group_external_id': None, 'ad_group_name': None}
    shared = _entity(value, 'shared_set') if level == 'shared_list' else {'shared_set_external_id': None, 'shared_set_name': None}
    attached = value.get('attached_campaign_ids') or []
    if not isinstance(attached, list) or len(attached) > 500:
        abort(400, description='Campanhas vinculadas inválidas.')
    attached = sorted({_google_id(item, 'ID da campanha vinculada') for item in attached})
    text = _text(value.get('keyword_text'), 'Palavra negativa')
    fingerprint = hashlib.sha1('|'.join([
        level, campaign['campaign_external_id'] or '', ad_group['ad_group_external_id'] or '',
        shared['shared_set_external_id'] or '', text.lower(), match_type]).encode()).hexdigest()
    row = {'level': level, 'fingerprint': fingerprint, **campaign, **ad_group, **shared,
           'attached_campaign_ids': attached, 'keyword_text': text, 'match_type': match_type}
    return (fingerprint,), row


# ---------------------------------------------------------------------------
# Writers. Each upserts one validated row and is safe to replay.
# ---------------------------------------------------------------------------

_METRIC_COLUMNS = ('impressions', 'clicks', 'cost_micros', 'conversions', 'conversion_value_micros')
_METRIC_UPDATE = ',\n'.join(f'{name}=EXCLUDED.{name}' for name in _METRIC_COLUMNS) + ',\nlast_run_id=EXCLUDED.last_run_id,updated_at=NOW()'


def _write_daily(table, columns, conflict, row, ctx):
    names = ('client_id', 'account_id', *columns, *_METRIC_COLUMNS, 'last_run_id')
    values = (ctx['client_id'], ctx['account_pk'], *(row[column] for column in columns),
              *(row[column] for column in _METRIC_COLUMNS), ctx['run_id'])
    descriptive = [column for column in columns if column not in conflict]
    update = ',\n'.join([f'{name}=EXCLUDED.{name}' for name in descriptive] + [_METRIC_UPDATE]) if descriptive else _METRIC_UPDATE
    _rows(f'''INSERT INTO {table} ({','.join(names)}) VALUES ({','.join(['%s'] * len(names))})
        ON CONFLICT ({','.join(('account_id', *conflict))}) DO UPDATE SET {update} RETURNING account_id''', values)


def _write_ad_group(row, ctx):
    _write_daily('cadu_reports_gads_ad_group_daily',
                 ('campaign_external_id', 'campaign_name', 'ad_group_external_id', 'ad_group_name', 'ad_group_status', 'metric_date'),
                 ('ad_group_external_id', 'metric_date'), row, ctx)


def _write_keyword(row, ctx):
    _write_daily('cadu_reports_gads_keyword_daily',
                 ('campaign_external_id', 'campaign_name', 'ad_group_external_id', 'ad_group_name', 'criterion_external_id',
                  'keyword_text', 'match_type', 'keyword_status', 'quality_score', 'metric_date'),
                 ('ad_group_external_id', 'criterion_external_id', 'metric_date'), row, ctx)


def _write_search_term(row, ctx):
    _write_daily('cadu_reports_gads_search_term_daily',
                 ('campaign_external_id', 'campaign_name', 'ad_group_external_id', 'ad_group_name', 'search_term',
                  'term_hash', 'term_status', 'metric_date'),
                 ('ad_group_external_id', 'term_hash', 'metric_date'), row, ctx)


def _write_landing_page(row, ctx):
    _write_daily('cadu_reports_gads_landing_page_daily',
                 ('campaign_external_id', 'campaign_name', 'final_url', 'url_hash', 'page_host', 'page_path', 'metric_date'),
                 ('campaign_external_id', 'url_hash', 'metric_date'), row, ctx)


def _write_device(row, ctx):
    _write_daily('cadu_reports_gads_device_daily',
                 ('campaign_external_id', 'campaign_name', 'device', 'metric_date'),
                 ('campaign_external_id', 'device', 'metric_date'), row, ctx)


def _write_campaign_settings(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_campaign_settings
            (client_id,account_id,campaign_external_id,campaign_name,status,serving_status,channel_type,
             bidding_strategy_type,budget_micros,budget_shared,snapshot_id,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,campaign_external_id) DO UPDATE SET
            campaign_name=EXCLUDED.campaign_name,status=EXCLUDED.status,serving_status=EXCLUDED.serving_status,
            channel_type=EXCLUDED.channel_type,bidding_strategy_type=EXCLUDED.bidding_strategy_type,
            budget_micros=EXCLUDED.budget_micros,budget_shared=EXCLUDED.budget_shared,
            snapshot_id=EXCLUDED.snapshot_id,last_run_id=EXCLUDED.last_run_id,removed_at=NULL,updated_at=NOW()
        RETURNING account_id''',
          (ctx['client_id'], ctx['account_pk'], row['campaign_external_id'], row['campaign_name'], row['status'],
           row['serving_status'], row['channel_type'], row['bidding_strategy_type'], row['budget_micros'],
           row['budget_shared'], ctx['snapshot_id'], ctx['run_id']))


def _write_negative(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_negative_keywords
            (client_id,account_id,level,fingerprint,campaign_external_id,campaign_name,ad_group_external_id,
             ad_group_name,shared_set_external_id,shared_set_name,attached_campaign_ids,keyword_text,match_type,
             snapshot_id,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,fingerprint) DO UPDATE SET
            campaign_name=EXCLUDED.campaign_name,ad_group_name=EXCLUDED.ad_group_name,
            shared_set_name=EXCLUDED.shared_set_name,attached_campaign_ids=EXCLUDED.attached_campaign_ids,
            snapshot_id=EXCLUDED.snapshot_id,last_run_id=EXCLUDED.last_run_id,last_seen_at=NOW(),removed_at=NULL
        RETURNING id''',
          (ctx['client_id'], ctx['account_pk'], row['level'], row['fingerprint'], row['campaign_external_id'],
           row['campaign_name'], row['ad_group_external_id'], row['ad_group_name'], row['shared_set_external_id'],
           row['shared_set_name'], row['attached_campaign_ids'], row['keyword_text'], row['match_type'],
           ctx['snapshot_id'], ctx['run_id']))


def _finalize_settings(ctx):
    _rows('''UPDATE cadu_reports_gads_campaign_settings SET removed_at=NOW()
        WHERE account_id=%s AND removed_at IS NULL AND snapshot_id <> %s RETURNING account_id''',
          (ctx['account_pk'], ctx['snapshot_id']))


def _finalize_negatives(ctx):
    _rows('''UPDATE cadu_reports_gads_negative_keywords SET removed_at=NOW()
        WHERE account_id=%s AND removed_at IS NULL AND snapshot_id <> %s RETURNING id''',
          (ctx['account_pk'], ctx['snapshot_id']))


def _write_campaign_metrics(row, ctx):
    campaign = _rows('''INSERT INTO cadu_reports_campaigns (client_id,account_id,external_id,name,status,channel_type)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,external_id) DO UPDATE SET name=EXCLUDED.name,status=EXCLUDED.status,
            channel_type=COALESCE(EXCLUDED.channel_type,cadu_reports_campaigns.channel_type),updated_at=NOW()
        RETURNING id''', (ctx['client_id'], ctx['account_pk'], row['campaign_id'], row['campaign_name'],
                          row['campaign_status'], row['channel_type']))
    _rows('''INSERT INTO cadu_reports_campaign_daily_metrics
            (client_id,campaign_id,metric_date,source_kind,impressions,clicks,cost_micros,conversions,
             conversion_value_micros,last_run_id)
        VALUES (%s,%s,%s,'google_ads_script',%s,%s,%s,%s,%s,%s)
        ON CONFLICT (campaign_id,metric_date,source_kind) DO UPDATE SET impressions=EXCLUDED.impressions,
            clicks=EXCLUDED.clicks,cost_micros=EXCLUDED.cost_micros,conversions=EXCLUDED.conversions,
            conversion_value_micros=EXCLUDED.conversion_value_micros,last_run_id=EXCLUDED.last_run_id,updated_at=NOW()
        RETURNING campaign_id''',
          (ctx['client_id'], campaign[0]['id'], row['date'], row['impressions'], row['clicks'], row['cost_micros'],
           row['conversions'], row['conversion_value_micros'], ctx['run_id']))


def _norm_campaign_metrics(value):
    value = _require_dict(value)
    row = _record(value)
    return (row['campaign_id'], row['date']), row


# name -> (normalizer, writer, snapshot finalizer or None)
DATASETS = {
    'campaign_metrics': (_norm_campaign_metrics, _write_campaign_metrics, None),
    'ad_group_metrics': (_norm_ad_group_metrics, _write_ad_group, None),
    'keyword_metrics': (_norm_keyword_metrics, _write_keyword, None),
    'search_term_metrics': (_norm_search_term_metrics, _write_search_term, None),
    'device_metrics': (_norm_device_metrics, _write_device, None),
    'landing_page_metrics': (_norm_landing_page_metrics, _write_landing_page, None),
    'campaign_settings': (_norm_campaign_settings, _write_campaign_settings, _finalize_settings),
    'negative_keywords': (_norm_negative_keyword, _write_negative, _finalize_negatives),
}
SNAPSHOT_DATASETS = {name for name, spec in DATASETS.items() if spec[2]}


# ---------------------------------------------------------------------------
# Envelope: authentication, account scope and run bookkeeping
# ---------------------------------------------------------------------------

def _authenticate():
    if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
        abort(413)
    raw = request.get_data(cache=True)
    if len(raw) > MAX_BODY_BYTES:
        abort(413)
    bearer = request.headers.get('Authorization', '')
    token = bearer[7:].strip() if bearer.startswith('Bearer ') else ''
    if not token or len(token) > 128:
        abort(401)
    keys = _rows('''SELECT id,client_id,allowed_account_ids,bound_account_id,manager_external_id
            FROM cadu_reports_ingest_keys
            WHERE token_hash=%s AND source_kind='google_ads_script' AND revoked_at IS NULL FOR UPDATE''',
                 (hashlib.sha256(token.encode()).hexdigest(),))
    if not keys:
        abort(401)
    return keys[0]


def _authorize_scope(key, manager_id, account_id):
    """Same trust rules as engine v1: the key's MCC, allowlist and account linkage must all agree."""
    if manager_id != key['manager_external_id']:
        abort(403, description='A MCC deste lote não corresponde à chave gerada para este cliente.')
    allowed = set(key['allowed_account_ids'] or [])
    if allowed and account_id not in allowed:
        abort(403, description='A conta do lote está fora da lista autorizada.')
    if manager_id:
        linked = _rows('''SELECT a.external_id FROM cadu_reports_accounts a
            JOIN cadu_reports_accounts m ON m.id=a.parent_account_id
            WHERE a.client_id=%s AND a.platform='google_ads' AND a.account_kind='advertiser'
                AND a.status <> 'disabled' AND m.external_id=%s AND a.external_id=%s''',
                       (key['client_id'], manager_id, account_id))
        if not linked:
            abort(403, description='A conta do lote não está vinculada a esta MCC no Reports.')
        return
    if key['bound_account_id'] and key['bound_account_id'] != account_id:
        abort(403, description='Esta chave já está vinculada a outra conta.')
    if not allowed and not key['bound_account_id']:
        _rows('UPDATE cadu_reports_ingest_keys SET bound_account_id=%s WHERE id=%s RETURNING id', (account_id, key['id']))


def _upsert_account(client_id, manager_id, account):
    manager_pk = None
    if manager_id:
        manager = _rows('''INSERT INTO cadu_reports_accounts (client_id,platform,external_id,name,account_kind)
            VALUES (%s,'google_ads',%s,%s,'manager')
            ON CONFLICT (client_id,platform,external_id) DO UPDATE SET updated_at=NOW() RETURNING id''',
                        (client_id, manager_id, f'MCC {manager_id}'))
        manager_pk = manager[0]['id']
    currency = str(account.get('currency') or '').upper()
    if currency and not re.fullmatch(r'[A-Z]{3}', currency):
        abort(400, description='Moeda inválida.')
    zone = account.get('time_zone')
    zone = str(zone).strip()[:100] if zone else None
    row = _rows('''INSERT INTO cadu_reports_accounts
            (client_id,platform,external_id,name,parent_account_id,account_kind,currency,time_zone)
        VALUES (%s,'google_ads',%s,%s,%s,'advertiser',%s,%s)
        ON CONFLICT (client_id,platform,external_id) DO UPDATE SET name=EXCLUDED.name,
            currency=COALESCE(EXCLUDED.currency,cadu_reports_accounts.currency),
            time_zone=COALESCE(EXCLUDED.time_zone,cadu_reports_accounts.time_zone),
            parent_account_id=COALESCE(EXCLUDED.parent_account_id,cadu_reports_accounts.parent_account_id),
            updated_at=NOW() RETURNING id''',
                (client_id, account['id'], account['name'], manager_pk, currency or None, zone))
    return row[0]['id']


def _envelope(payload):
    if not isinstance(payload, dict):
        abort(400, description='Envie um objeto JSON.')
    if payload.get('schema_version') != SCHEMA_VERSION:
        abort(400, description='Versão do esquema não suportada. Gere o script novamente no Reports.')
    dataset = payload.get('dataset')
    if dataset != 'run_summary' and dataset not in DATASETS:
        abort(400, description='Conjunto de dados desconhecido.')
    raw_account = payload.get('account')
    if not isinstance(raw_account, dict):
        abort(400, description='Informe a conta Google Ads.')
    account = {'id': _google_id(raw_account.get('id'), 'ID da conta', account=True),
               'name': _text(raw_account.get('name'), 'Nome da conta'),
               'currency': raw_account.get('currency'), 'time_zone': raw_account.get('time_zone')}
    manager = payload.get('manager_account_id')
    chunk = payload.get('chunk') if isinstance(payload.get('chunk'), dict) else {}
    snapshot = payload.get('snapshot') if isinstance(payload.get('snapshot'), dict) else {}
    index = _count(chunk.get('index', 0), 'Índice do lote')
    return {
        'run_key': _text(payload.get('run_key'), 'Identificador da execução', 120),
        'engine_version': _text(str(payload.get('engine_version') or 'unknown'), 'Versão do motor', 20),
        'dataset': dataset, 'account': account,
        'manager_id': _google_id(manager, 'ID da MCC', account=True) if manager else None,
        'chunk_index': index,
        'snapshot_id': _text(str(snapshot.get('id') or ''), 'Identificador do snapshot', 200) if snapshot.get('id') else '',
        'snapshot_final': snapshot.get('final') is True,
    }


def _summary(payload):
    """Whitelist the heartbeat so only bounded, non-secret diagnostics are stored."""
    raw = payload.get('summary')
    if not isinstance(raw, dict) or len(json.dumps(raw)) > MAX_SUMMARY_BYTES:
        abort(400, description='Resumo da execução inválido.')
    datasets = raw.get('datasets') if isinstance(raw.get('datasets'), list) else []
    clean = []
    for item in datasets[:20]:
        if not isinstance(item, dict):
            continue
        status = item.get('status')
        clean.append({'name': str(item.get('name') or '')[:40],
                      'status': status if status in SUMMARY_STATUSES else 'error',
                      'rows': _count(item.get('rows'), 'Linhas'),
                      'error': str(item['error'])[:300] if item.get('error') else None})
    window = raw.get('window') if isinstance(raw.get('window'), dict) else {}

    def _day(value):
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None
    return {'datasets': clean, 'duration_ms': _count(raw.get('duration_ms'), 'Duração'),
            'window_start': _day(window.get('since')), 'window_end': _day(window.get('until')),
            'timed_out': raw.get('timed_out') is True}


def register(bp):
    @bp.post('/api/v1/reports/ingest/google-ads/v2')
    def reports_ingest_google_ads_v2():
        key = _authenticate()
        payload = request.get_json(silent=True)
        env = _envelope(payload)
        _authorize_scope(key, env['manager_id'], env['account']['id'])
        client_id = key['client_id']
        dataset = env['dataset']
        is_summary = dataset == 'run_summary'

        rows = []
        summary = None
        if is_summary:
            summary = _summary(payload)
        else:
            values = payload.get('records')
            if not isinstance(values, list) or len(values) > MAX_RECORDS:
                abort(400, description='Envie até 500 registros por lote.')
            if not values and dataset not in SNAPSHOT_DATASETS:
                abort(400, description='Envie de 1 a 500 registros.')
            if dataset in SNAPSHOT_DATASETS and not env['snapshot_id']:
                abort(400, description='Conjuntos de configuração exigem um snapshot.')
            normalize = DATASETS[dataset][0]
            # Last one wins on a repeated natural key instead of failing the whole chunk.
            deduped = {}
            for value in values:
                if dataset == 'campaign_metrics':
                    value = {**value, 'account_id': env['account']['id'], 'account_name': env['account']['name'],
                             'currency': env['account']['currency']} if isinstance(value, dict) else value
                key_tuple, row = normalize(value)
                deduped[key_tuple] = row
            rows = list(deduped.values())

        run_key = f"{env['run_key']}:{env['account']['id']}:{dataset}:{env['chunk_index']}"
        run_id = str(uuid.uuid4())
        source_kind = SUMMARY_SOURCE_KIND if is_summary else CHUNK_SOURCE_KIND
        dates = [item.get('metric_date') or item.get('date') for item in rows if item.get('metric_date') or item.get('date')]
        record_count = sum(item['rows'] for item in summary['datasets']) if is_summary else len(rows)
        has_error = bool(is_summary and any(item['status'] == 'error' for item in summary['datasets']))
        metadata = {'engine_version': env['engine_version'], 'dataset': dataset, 'account_id': env['account']['id']}
        if is_summary:
            metadata.update(datasets=summary['datasets'], duration_ms=summary['duration_ms'], timed_out=summary['timed_out'])
        inserted = _rows('''INSERT INTO cadu_reports_source_runs
                (id,client_id,source_kind,external_run_key,period_start,period_end,status,record_count,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,'processing',%s,%s::jsonb)
            ON CONFLICT (client_id,source_kind,external_run_key) DO NOTHING RETURNING id''',
                         (run_id, client_id, source_kind, run_key,
                          summary['window_start'] if is_summary else (min(dates) if dates else None),
                          summary['window_end'] if is_summary else (max(dates) if dates else None),
                          record_count, json.dumps(metadata)))
        if not inserted:
            get_db().rollback()
            return jsonify(accepted=True, duplicate=True, records=0)

        account_pk = _upsert_account(client_id, env['manager_id'], env['account'])
        ctx = {'client_id': client_id, 'account_pk': account_pk, 'run_id': run_id, 'snapshot_id': env['snapshot_id']}
        if not is_summary:
            _, writer, finalizer = DATASETS[dataset]
            for row in rows:
                writer(row, ctx)
            if finalizer and env['snapshot_final']:
                finalizer(ctx)
        status = 'partial' if has_error else 'completed'
        _rows("UPDATE cadu_reports_source_runs SET status=%s,finished_at=NOW() WHERE id=%s RETURNING id", (status, run_id))
        _rows('UPDATE cadu_reports_ingest_keys SET last_used_at=NOW() WHERE id=%s RETURNING id', (key['id'],))
        get_db().commit()
        return jsonify(accepted=True, duplicate=False, dataset=dataset, records=len(rows), client_id=client_id)


CHUNK_RETENTION_DAYS = 30
_RUN_REFERENCES = ('cadu_reports_campaign_daily_metrics', 'cadu_reports_gads_ad_group_daily', 'cadu_reports_gads_keyword_daily',
                   'cadu_reports_gads_search_term_daily', 'cadu_reports_gads_device_daily', 'cadu_reports_gads_campaign_settings',
                   'cadu_reports_gads_negative_keywords', 'cadu_reports_gads_landing_page_daily')


def prune_chunk_runs(days=CHUNK_RETENTION_DAYS):
    """Delete old per-batch idempotency rows that no data row still points to (``last_run_id``). Summaries are kept."""
    unreferenced = ' AND '.join(f'NOT EXISTS (SELECT 1 FROM {table} t WHERE t.last_run_id=r.id)' for table in _RUN_REFERENCES)
    cursor = get_db().cursor()
    cursor.execute(
        f"DELETE FROM cadu_reports_source_runs r WHERE r.source_kind=%s AND r.created_at < NOW() - make_interval(days => %s) AND {unreferenced}",
        (CHUNK_SOURCE_KIND, int(days)))
    removed = cursor.rowcount
    get_db().commit()
    return removed
