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
AD_STRENGTHS = ('PENDING', 'NO_ADS', 'POOR', 'AVERAGE', 'GOOD', 'EXCELLENT', 'UNSPECIFIED', 'UNKNOWN')
RATINGS = ('BELOW_AVERAGE', 'AVERAGE', 'ABOVE_AVERAGE', 'UNSPECIFIED', 'UNKNOWN')
PERFORMANCE_LABELS = ('PENDING', 'LEARNING', 'LOW', 'GOOD', 'BEST', 'UNSPECIFIED', 'UNKNOWN')
MAX_ASSET_TEXTS = 30


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
           'quality_score': quality, 'metric_date': _metric_date(value.get('date')), **_metrics(value),
           # Engine 2.2: Quality Score components and bid; absent (None) on older scripts or when the API refuses them.
           'expected_ctr': _optional_enum(value.get('expected_ctr'), RATINGS, 'CTR esperado'),
           'ad_relevance': _optional_enum(value.get('ad_relevance'), RATINGS, 'Relevância do anúncio'),
           'landing_page_experience': _optional_enum(value.get('landing_page_experience'), RATINGS, 'Experiência na página'),
           'cpc_bid_micros': None if value.get('cpc_bid_micros') in (None, '') else _count(value.get('cpc_bid_micros'), 'Lance')}
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
           'budget_shared': shared if isinstance(shared, bool) else None,
           # Bidding targets (engine 2.1+): tCPA in micros and tROAS as a ratio; absent on older scripts.
           'target_cpa_micros': None if value.get('target_cpa_micros') in (None, '', 0) else _count(value.get('target_cpa_micros'), 'CPA desejado'),
           'target_roas': _ratio(value.get('target_roas'))}
    return (row['campaign_external_id'],), row


def _ratio(value):
    if value in (None, '', 0):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        abort(400, description='ROAS desejado inválido.')
    if parsed < 0 or parsed > 1000:
        abort(400, description='ROAS desejado inválido.')
    return parsed


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


def _optional_enum(value, allowed, name):
    """An enum the API may leave out: None when absent, 'UNKNOWN' when it is a value this version does not know."""
    if value in (None, ''):
        return None
    raw = _enum_text(value, name, limit=24)
    return raw if raw in allowed else 'UNKNOWN'


def _share(value, name):
    """A 0..1 ratio, or None when Google reports no value."""
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        abort(400, description=f'{name} inválido.')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        abort(400, description=f'{name} inválido.')
    if not number.is_finite() or number < 0 or number > 1:
        abort(400, description=f'{name} fora do limite.')
    return number.quantize(Decimal('0.000001'))


def _ad_texts(value, name):
    """Headlines/descriptions of a responsive ad: a bounded list of {text, pinned}."""
    if value in (None, ''):
        return []
    if not isinstance(value, list) or len(value) > MAX_ASSET_TEXTS:
        abort(400, description=f'{name} inválidos.')
    clean = []
    for item in value:
        item = _require_dict(item)
        clean.append({'text': _text(item.get('text'), name, 400), 'pinned': str(item.get('pinned') or '')[:24]})
    return clean


def _norm_ads(value):
    value = _require_dict(value)
    raw_url = str(value.get('final_url') or '').strip()
    row = {**_entity(value, 'campaign'), **_entity(value, 'ad_group'),
           'ad_external_id': _google_id(value.get('ad_id'), 'ID do anúncio'),
           'ad_type': _enum_text(value.get('ad_type'), 'Tipo de anúncio', limit=48),
           'status': _enum_text(value.get('status'), 'Estado do anúncio'),
           'ad_strength': _optional_enum(value.get('ad_strength'), AD_STRENGTHS, 'Força do anúncio'),
           'approval_status': _enum_text(value.get('approval_status'), 'Aprovação', limit=32) if value.get('approval_status') else None,
           'final_url': raw_url[:2000] if re.match(r'https?://', raw_url, re.I) else None,
           'headlines': _ad_texts(value.get('headlines'), 'Títulos'), 'descriptions': _ad_texts(value.get('descriptions'), 'Descrições'),
           'path1': str(value.get('path1') or '')[:30] or None, 'path2': str(value.get('path2') or '')[:30] or None}
    return (row['ad_external_id'],), row


def _norm_ad_metrics(value):
    value = _require_dict(value)
    row = {**_entity(value, 'campaign'), 'ad_group_external_id': _google_id(value.get('ad_group_id'), 'ID de grupo'),
           'ad_external_id': _google_id(value.get('ad_id'), 'ID do anúncio'),
           'metric_date': _metric_date(value.get('date')), **_metrics(value)}
    return (row['ad_external_id'], row['metric_date']), row


def _norm_asset_performance(value):
    value = _require_dict(value)
    field = _enum_text(value.get('field_type'), 'Tipo de ativo', limit=24)
    row = {'campaign_external_id': _google_id(value.get('campaign_id'), 'ID de campanha'),
           'ad_group_external_id': _google_id(value.get('ad_group_id'), 'ID de grupo'),
           'ad_external_id': _google_id(value.get('ad_id'), 'ID do anúncio'),
           'asset_external_id': _google_id(value.get('asset_id'), 'ID do ativo'), 'field_type': field,
           'asset_text': str(value.get('text') or '')[:400],
           'performance_label': _optional_enum(value.get('performance_label'), PERFORMANCE_LABELS, 'Desempenho do ativo'),
           'enabled': value.get('enabled') is not False}
    return (row['ad_external_id'], row['asset_external_id'], field), row


def _norm_impression_share(value):
    value = _require_dict(value)
    row = {**_entity(value, 'campaign'), 'metric_date': _metric_date(value.get('date')),
           'search_impression_share': _share(value.get('search_impression_share'), 'Parcela de impressões'),
           'budget_lost': _share(value.get('budget_lost'), 'Parcela perdida por orçamento'),
           'rank_lost': _share(value.get('rank_lost'), 'Parcela perdida por classificação'),
           'top_impression_share': _share(value.get('top_impression_share'), 'Parcela no topo'),
           'absolute_top_impression_share': _share(value.get('absolute_top_impression_share'), 'Parcela na primeira posição')}
    return (row['campaign_external_id'], row['metric_date']), row


def _norm_conversion_action(value):
    value = _require_dict(value)
    name = _text(value.get('action_name'), 'Ação de conversão', 240)
    row = {**_entity(value, 'campaign'), 'action_name': name, 'action_hash': hashlib.md5(name.lower().encode()).hexdigest(),
           'metric_date': _metric_date(value.get('date')), 'conversions': _decimal(value.get('conversions'), 'Conversões'),
           'conversion_value_micros': _count(value.get('conversion_value_micros'), 'Valor de conversão')}
    return (row['campaign_external_id'], row['action_hash'], row['metric_date']), row


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


def _keyword_components_ready():
    """The component columns arrive with add_reports_google_ads_engine_v22.sql; older databases keep working without them."""
    return bool(_rows("""SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cadu_reports_gads_keyword_daily'
        AND column_name='expected_ctr') AS ready""")[0]['ready'])


def _write_keyword(row, ctx):
    if 'keyword_components' not in ctx:
        ctx['keyword_components'] = _keyword_components_ready()
    extra = ('expected_ctr', 'ad_relevance', 'landing_page_experience', 'cpc_bid_micros') if ctx['keyword_components'] else ()
    _write_daily('cadu_reports_gads_keyword_daily',
                 ('campaign_external_id', 'campaign_name', 'ad_group_external_id', 'ad_group_name', 'criterion_external_id',
                  'keyword_text', 'match_type', 'keyword_status', 'quality_score', *extra, 'metric_date'),
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


def _settings_targets_ready():
    """The target columns arrive with add_reports_google_ads_history_goals.sql; older databases keep working without them."""
    return bool(_rows("""SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cadu_reports_gads_campaign_settings'
        AND column_name='target_cpa_micros') AND to_regclass('public.cadu_reports_gads_campaign_settings_history') IS NOT NULL AS ready""")[0]['ready'])


def _write_campaign_settings(row, ctx):
    if 'targets_ready' not in ctx:
        ctx['targets_ready'] = _settings_targets_ready()
    targets = ctx['targets_ready']
    if targets:
        # Keep a history row whenever something an operator would care about changed (or the campaign is new).
        _rows('''INSERT INTO cadu_reports_gads_campaign_settings_history
                (client_id,account_id,campaign_external_id,campaign_name,status,bidding_strategy_type,budget_micros,target_cpa_micros,target_roas)
            SELECT %(client)s::bigint,%(account)s::bigint,%(campaign)s::varchar,%(name)s::varchar,%(status)s::varchar,
                %(bidding)s::varchar,%(budget)s::bigint,%(tcpa)s::bigint,%(troas)s::numeric
            WHERE NOT EXISTS (SELECT 1 FROM cadu_reports_gads_campaign_settings s
                WHERE s.account_id=%(account)s::bigint AND s.campaign_external_id=%(campaign)s::varchar
                  AND s.status IS NOT DISTINCT FROM %(status)s::varchar AND s.bidding_strategy_type IS NOT DISTINCT FROM %(bidding)s::varchar
                  AND s.budget_micros IS NOT DISTINCT FROM %(budget)s::bigint AND s.target_cpa_micros IS NOT DISTINCT FROM %(tcpa)s::bigint
                  AND s.target_roas IS NOT DISTINCT FROM %(troas)s::numeric)
            RETURNING id''', {'client': ctx['client_id'], 'account': ctx['account_pk'], 'campaign': row['campaign_external_id'],
                                'name': row['campaign_name'], 'status': row['status'], 'bidding': row['bidding_strategy_type'],
                                'budget': row['budget_micros'], 'tcpa': row['target_cpa_micros'], 'troas': row['target_roas']})
    extra_cols = ',target_cpa_micros,target_roas' if targets else ''
    extra_vals = ',%s,%s' if targets else ''
    extra_set = ',target_cpa_micros=EXCLUDED.target_cpa_micros,target_roas=EXCLUDED.target_roas' if targets else ''
    params = [ctx['client_id'], ctx['account_pk'], row['campaign_external_id'], row['campaign_name'], row['status'],
              row['serving_status'], row['channel_type'], row['bidding_strategy_type'], row['budget_micros'],
              row['budget_shared'], ctx['snapshot_id'], ctx['run_id']] + ([row['target_cpa_micros'], row['target_roas']] if targets else [])
    _rows(f'''INSERT INTO cadu_reports_gads_campaign_settings
            (client_id,account_id,campaign_external_id,campaign_name,status,serving_status,channel_type,
             bidding_strategy_type,budget_micros,budget_shared,snapshot_id,last_run_id{extra_cols})
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s{extra_vals})
        ON CONFLICT (account_id,campaign_external_id) DO UPDATE SET
            campaign_name=EXCLUDED.campaign_name,status=EXCLUDED.status,serving_status=EXCLUDED.serving_status,
            channel_type=EXCLUDED.channel_type,bidding_strategy_type=EXCLUDED.bidding_strategy_type,
            budget_micros=EXCLUDED.budget_micros,budget_shared=EXCLUDED.budget_shared{extra_set},
            snapshot_id=EXCLUDED.snapshot_id,last_run_id=EXCLUDED.last_run_id,removed_at=NULL,updated_at=NOW()
        RETURNING account_id''', tuple(params))


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


def _write_ad(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_ads
            (client_id,account_id,ad_external_id,campaign_external_id,campaign_name,ad_group_external_id,ad_group_name,ad_type,
             status,ad_strength,approval_status,final_url,headlines,descriptions,path1,path2,snapshot_id,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
        ON CONFLICT (account_id,ad_external_id) DO UPDATE SET
            campaign_external_id=EXCLUDED.campaign_external_id,campaign_name=EXCLUDED.campaign_name,
            ad_group_external_id=EXCLUDED.ad_group_external_id,ad_group_name=EXCLUDED.ad_group_name,ad_type=EXCLUDED.ad_type,
            status=EXCLUDED.status,ad_strength=EXCLUDED.ad_strength,approval_status=EXCLUDED.approval_status,
            final_url=EXCLUDED.final_url,headlines=EXCLUDED.headlines,descriptions=EXCLUDED.descriptions,
            path1=EXCLUDED.path1,path2=EXCLUDED.path2,snapshot_id=EXCLUDED.snapshot_id,last_run_id=EXCLUDED.last_run_id,
            removed_at=NULL,updated_at=NOW()
        RETURNING account_id''',
          (ctx['client_id'], ctx['account_pk'], row['ad_external_id'], row['campaign_external_id'], row['campaign_name'],
           row['ad_group_external_id'], row['ad_group_name'], row['ad_type'], row['status'], row['ad_strength'],
           row['approval_status'], row['final_url'], json.dumps(row['headlines']), json.dumps(row['descriptions']),
           row['path1'], row['path2'], ctx['snapshot_id'], ctx['run_id']))


def _write_ad_metrics(row, ctx):
    _write_daily('cadu_reports_gads_ad_daily',
                 ('campaign_external_id', 'campaign_name', 'ad_group_external_id', 'ad_external_id', 'metric_date'),
                 ('ad_external_id', 'metric_date'), row, ctx)


def _write_asset_performance(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_asset_performance
            (client_id,account_id,ad_external_id,asset_external_id,field_type,campaign_external_id,ad_group_external_id,
             asset_text,performance_label,enabled,snapshot_id,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,ad_external_id,asset_external_id,field_type) DO UPDATE SET
            campaign_external_id=EXCLUDED.campaign_external_id,ad_group_external_id=EXCLUDED.ad_group_external_id,
            asset_text=EXCLUDED.asset_text,performance_label=EXCLUDED.performance_label,enabled=EXCLUDED.enabled,
            snapshot_id=EXCLUDED.snapshot_id,last_run_id=EXCLUDED.last_run_id,removed_at=NULL,updated_at=NOW()
        RETURNING account_id''',
          (ctx['client_id'], ctx['account_pk'], row['ad_external_id'], row['asset_external_id'], row['field_type'],
           row['campaign_external_id'], row['ad_group_external_id'], row['asset_text'], row['performance_label'],
           row['enabled'], ctx['snapshot_id'], ctx['run_id']))


def _write_impression_share(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_impression_share_daily
            (client_id,account_id,campaign_external_id,campaign_name,metric_date,search_impression_share,budget_lost,rank_lost,
             top_impression_share,absolute_top_impression_share,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,campaign_external_id,metric_date) DO UPDATE SET campaign_name=EXCLUDED.campaign_name,
            search_impression_share=EXCLUDED.search_impression_share,budget_lost=EXCLUDED.budget_lost,rank_lost=EXCLUDED.rank_lost,
            top_impression_share=EXCLUDED.top_impression_share,absolute_top_impression_share=EXCLUDED.absolute_top_impression_share,
            last_run_id=EXCLUDED.last_run_id,updated_at=NOW()
        RETURNING account_id''',
          (ctx['client_id'], ctx['account_pk'], row['campaign_external_id'], row['campaign_name'], row['metric_date'],
           row['search_impression_share'], row['budget_lost'], row['rank_lost'], row['top_impression_share'],
           row['absolute_top_impression_share'], ctx['run_id']))


def _write_conversion_action(row, ctx):
    _rows('''INSERT INTO cadu_reports_gads_conversion_action_daily
            (client_id,account_id,campaign_external_id,campaign_name,action_name,action_hash,metric_date,conversions,
             conversion_value_micros,last_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,campaign_external_id,action_hash,metric_date) DO UPDATE SET campaign_name=EXCLUDED.campaign_name,
            action_name=EXCLUDED.action_name,conversions=EXCLUDED.conversions,
            conversion_value_micros=EXCLUDED.conversion_value_micros,last_run_id=EXCLUDED.last_run_id,updated_at=NOW()
        RETURNING account_id''',
          (ctx['client_id'], ctx['account_pk'], row['campaign_external_id'], row['campaign_name'], row['action_name'],
           row['action_hash'], row['metric_date'], row['conversions'], row['conversion_value_micros'], ctx['run_id']))


def _finalize_ads(ctx):
    _rows('''UPDATE cadu_reports_gads_ads SET removed_at=NOW()
        WHERE account_id=%s AND removed_at IS NULL AND snapshot_id <> %s RETURNING account_id''',
          (ctx['account_pk'], ctx['snapshot_id']))


def _finalize_asset_performance(ctx):
    _rows('''UPDATE cadu_reports_gads_asset_performance SET removed_at=NOW()
        WHERE account_id=%s AND removed_at IS NULL AND snapshot_id <> %s RETURNING account_id''',
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
    # Engine 2.2
    'ads': (_norm_ads, _write_ad, _finalize_ads),
    'ad_metrics': (_norm_ad_metrics, _write_ad_metrics, None),
    'asset_performance': (_norm_asset_performance, _write_asset_performance, _finalize_asset_performance),
    'impression_share_metrics': (_norm_impression_share, _write_impression_share, None),
    'conversion_action_metrics': (_norm_conversion_action, _write_conversion_action, None),
}
SNAPSHOT_DATASETS = {name for name, spec in DATASETS.items() if spec[2]}


# ---------------------------------------------------------------------------
# Envelope: authentication, account scope and run bookkeeping
# ---------------------------------------------------------------------------

def _authenticate(source_kind='google_ads_script'):
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
            WHERE token_hash=%s AND source_kind=%s AND revoked_at IS NULL FOR UPDATE''',
                 (hashlib.sha256(token.encode()).hexdigest(), source_kind))
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


# History: every run re-reads the recent window (conversions arrive late) and backfills one older slice, until the
# account has HISTORY_DAYS of daily data. Rows are never deleted, so the history only grows.
RECENT_DAYS = 14
HISTORY_DAYS = 395
BACKFILL_STEP_DAYS = 45


def collection_plan(today, oldest):
    """Date ranges the script should read now: the recent window plus the next missing slice of history."""
    recent_start = today - timedelta(days=RECENT_DAYS - 1)
    ranges = [{'since': recent_start.isoformat(), 'until': today.isoformat(), 'kind': 'recent'}]
    floor = today - timedelta(days=HISTORY_DAYS - 1)
    edge = min(oldest, recent_start) if oldest else recent_start
    if edge > floor:
        start = max(floor, edge - timedelta(days=BACKFILL_STEP_DAYS))
        ranges.append({'since': start.isoformat(), 'until': (edge - timedelta(days=1)).isoformat(), 'kind': 'backfill'})
    return ranges


def register(bp):
    # /api/gads is the short address handed out in new scripts; the long one keeps installed scripts working.
    @bp.get('/api/gads/plan')
    @bp.get('/api/v1/reports/ingest/google-ads/v2/plan')
    def reports_ingest_v2_plan():
        """Tells the script which dates to read for one account (engine 2.1+). Same key and scope rules as the ingest."""
        key = _authenticate()
        account_id = _google_id(request.args.get('account_id'), 'ID da conta', account=True)
        manager = request.args.get('manager_account_id')
        _authorize_scope(key, _google_id(manager, 'ID da MCC', account=True) if manager else None, account_id)
        # Oldest day already covered: stored data or, when a slice came back empty, the window the script already read.
        found = _rows('''SELECT LEAST(
                (SELECT MIN(d.metric_date) FROM cadu_reports_gads_ad_group_daily d JOIN cadu_reports_accounts a ON a.id=d.account_id
                    WHERE a.client_id=%(client)s AND a.platform='google_ads'
                      AND regexp_replace(a.external_id,'\\D','','g')=regexp_replace(%(account)s,'\\D','','g')),
                (SELECT MIN(r.period_start) FROM cadu_reports_source_runs r
                    WHERE r.client_id=%(client)s AND r.source_kind=%(summary)s AND r.status IN ('completed','partial')
                      AND regexp_replace(r.metadata->>'account_id','\\D','','g')=regexp_replace(%(account)s,'\\D','','g'))) AS oldest''',
                      {'client': key['client_id'], 'account': account_id, 'summary': SUMMARY_SOURCE_KIND})
        get_db().commit()
        oldest = found[0]['oldest'] if found else None
        return jsonify(ranges=collection_plan(date.today(), oldest), history_days=HISTORY_DAYS, recent_days=RECENT_DAYS,
                       oldest=oldest.isoformat() if oldest else None)

    @bp.post('/api/gads')
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
                   'cadu_reports_gads_negative_keywords', 'cadu_reports_gads_landing_page_daily', 'cadu_reports_gads_ads',
                   'cadu_reports_gads_ad_daily', 'cadu_reports_gads_asset_performance',
                   'cadu_reports_gads_impression_share_daily', 'cadu_reports_gads_conversion_action_daily')


def prune_chunk_runs(days=CHUNK_RETENTION_DAYS):
    """Delete old per-batch idempotency rows that no data row still points to (``last_run_id``). Summaries are kept."""
    cursor = get_db().cursor()
    # Tables from newer migrations may not exist yet on an older database.
    cursor.execute("SELECT name FROM unnest(%s::text[]) AS name WHERE to_regclass('public.' || name) IS NOT NULL", (list(_RUN_REFERENCES),))
    present = [row['name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
    unreferenced = ' AND '.join(f'NOT EXISTS (SELECT 1 FROM {table} t WHERE t.last_run_id=r.id)' for table in present) or 'TRUE'
    cursor.execute(
        f"DELETE FROM cadu_reports_source_runs r WHERE r.source_kind=%s AND r.created_at < NOW() - make_interval(days => %s) AND {unreferenced}",
        (CHUNK_SOURCE_KIND, int(days)))
    removed = cursor.rowcount
    get_db().commit()
    return removed
