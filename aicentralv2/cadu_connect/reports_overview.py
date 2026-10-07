"""Visão geral → comparativos: the selected period against the previous one of the same length, and the rolling
"7 dias × 30 dias" windows, in one call.

Media comes from the Google Ads script table (falling back to imported files when the script sent nothing in the
range, like the overview does); the site comes from Super Tag events. Rolling windows end yesterday (São Paulo) so a
partial day never makes the latest window look worse than the one before it. Costs are returned in currency units;
when the accounts in scope mix currencies the cost is null.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_page_metrics import RETENTION_DAYS
from .reports_pages import EVENT_TABLE
from .reports_v1 import _customer_scope, _ready, _rows, _selection

ZONE = ZoneInfo('America/Sao_Paulo')
MEDIA_FIELDS = ('impressions', 'clicks', 'cost', 'conversions')
SITE_FIELDS = ('sessions', 'visitors', 'conversions')
WINDOW_KEYS = ('period', 'period_previous', 'last7', 'previous7', 'last30', 'previous30')

_JOINS = '''JOIN cadu_reports_campaigns c ON c.id=m.campaign_id
    JOIN cadu_reports_accounts a ON a.id=c.account_id'''

_MEDIA_SQL = '''SELECT m.metric_date AS date,SUM(m.impressions)::bigint AS impressions,SUM(m.clicks)::bigint AS clicks,
        SUM(m.cost_micros)::bigint AS cost_micros,SUM(m.conversions)::numeric AS conversions,
        ARRAY_AGG(DISTINCT COALESCE(a.currency,'')) AS currencies
    FROM cadu_reports_campaign_daily_metrics m ''' + _JOINS + '''
    WHERE m.client_id=%(client)s AND m.metric_date>=%(lo)s AND m.metric_date<=%(hi)s{filters}
    GROUP BY m.metric_date'''

_IMPORT_SQL = '''SELECT m.metric_date AS date,m.metric_key,COALESCE(m.currency,'') AS currency,SUM(m.value_numeric) AS value
    FROM cadu_reports_import_metric_projection m
    JOIN cadu_reports_campaigns c ON c.id=m.campaign_id AND c.client_id=m.client_id
    JOIN cadu_reports_accounts a ON a.id=c.account_id AND a.client_id=c.client_id
    WHERE m.client_id=%(client)s AND m.metric_date>=%(lo)s AND m.metric_date<=%(hi)s AND m.value_numeric IS NOT NULL{filters}
        AND m.metric_key IN ('impressions','clicks','cost','conversions')
    GROUP BY m.metric_date,m.metric_key,COALESCE(m.currency,'')'''


def _site_sql(windows, customer=None):
    """One pass over the events: distinct sessions/visitors and conversions per window, plus the previous period by day."""
    columns = []
    for key in windows:
        inside = f"e.occurred_at>=%({key}_since)s AND e.occurred_at<%({key}_until)s"
        columns.append(f"COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view' AND {inside})::bigint AS {key}_sessions")
        columns.append(f"COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind='page_view' AND {inside})::bigint AS {key}_visitors")
        columns.append(f"COUNT(*) FILTER (WHERE e.event_kind='conversion' AND {inside})::bigint AS {key}_conversions")
    return f'''SELECT {",".join(columns)}
        FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
        WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW(){' AND s.customer_id=%(customer)s' if customer else ''}
            AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s'''


_SITE_DAILY_SQL = f'''SELECT (e.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date AS date,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions
    FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW(){{customer_filter}}
        AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
    GROUP BY 1 ORDER BY 1'''


def windows_for(start, end, today):
    """{key: (first, last)} inclusive days: the period, the same length right before it, and the rolling windows."""
    length = (end - start).days + 1
    anchor = today - timedelta(days=1)
    return {
        'period': (start, end),
        'period_previous': (start - timedelta(days=length), start - timedelta(days=1)),
        'last7': (anchor - timedelta(days=6), anchor),
        'previous7': (anchor - timedelta(days=13), anchor - timedelta(days=7)),
        'last30': (anchor - timedelta(days=29), anchor),
        'previous30': (anchor - timedelta(days=59), anchor - timedelta(days=30)),
    }


def media_windows(daily, windows):
    """Sums the per-day media rows ({date, impressions, clicks, cost, conversions}) into each window."""
    out = {}
    for key, (first, last) in windows.items():
        rows = [row for row in daily if first <= row['date'] <= last]
        totals = {field: sum(float(row[field] or 0) for row in rows) for field in MEDIA_FIELDS}
        if any(row['cost'] is None for row in rows):
            totals['cost'] = None
        out[key] = totals
    return out


def fill_days(rows, days, fields, currency):
    """One entry per day of the window, zeros where nothing happened (cost stays null without a single currency)."""
    by_day = {row['date']: row for row in rows}
    out = []
    for day in days:
        row = by_day.get(day) or {}
        entry = {'date': day.isoformat()}
        for field in fields:
            value = row.get(field)
            entry[field] = None if field == 'cost' and not currency else float(value or 0)
        out.append(entry)
    return out


def _script_daily(params, filters):
    rows = _rows(_MEDIA_SQL.format(filters=filters), params)
    currencies = {code for row in rows for code in (row.pop('currencies') or [])}
    currency = next(iter(currencies)) if len(currencies) == 1 and '' not in currencies else None
    daily = [{'date': row['date'], 'impressions': row['impressions'], 'clicks': row['clicks'],
              'cost': float(row['cost_micros']) / 1e6 if currency and row['cost_micros'] is not None else None,
              'conversions': row['conversions']} for row in rows]
    return daily, currency


def _imported_daily(params, filters):
    if not _rows("SELECT to_regclass('public.cadu_reports_import_metric_projection') IS NOT NULL AS ready")[0]['ready']:
        return [], None
    rows = _rows(_IMPORT_SQL.format(filters=filters), params)
    currencies = {row['currency'] for row in rows if row['metric_key'] == 'cost'}
    currency = next(iter(currencies)) if len(currencies) == 1 and '' not in currencies else None
    days = {}
    for row in rows:
        day = days.setdefault(row['date'], {'date': row['date'], 'impressions': 0, 'clicks': 0, 'cost': 0 if currency else None, 'conversions': 0})
        if row['metric_key'] == 'cost':
            if currency:
                day['cost'] += float(row['value'])
        else:
            day[row['metric_key']] += float(row['value'])
    return sorted(days.values(), key=lambda item: item['date']), currency


def _scope_filters():
    filters, params = '', {}
    for field, column in (('account_id', 'a.id'), ('campaign_id', 'c.id')):
        supplied = request.args.get(field, '').strip()
        if not supplied:
            continue
        try:
            value = int(supplied)
        except ValueError:
            abort(400, description=f'{field} inválido.')
        if value < 1:
            abort(400, description=f'{field} inválido.')
        filters += f' AND {column}=%({field})s'
        params[field] = value
    return filters, params


def _period(today):
    start_raw, end_raw = request.args.get('start_date', '').strip(), request.args.get('end_date', '').strip()
    try:
        end = date.fromisoformat(end_raw) if end_raw else today
        start = date.fromisoformat(start_raw) if start_raw else end - timedelta(days=29)
    except ValueError:
        abort(400, description='Informe um intervalo de datas válido.')
    if start > end or (end - start).days > 365:
        abort(400, description='O período deve ser válido e ter no máximo 366 dias.')
    return start, end


def _bounds(first, last):
    return datetime.combine(first, time.min, ZONE), datetime.combine(last + timedelta(days=1), time.min, ZONE)


def register(bp):
    @bp.get('/api/v2/reports/overview/compare')
    @login_required_api
    def reports_overview_compare():
        selected = _selection()
        today = datetime.now(ZONE).date()
        start, end = _period(today)
        windows = windows_for(start, end, today)
        serial = {key: {'start': first.isoformat(), 'end': last.isoformat()} for key, (first, last) in windows.items()}
        filters, scope = _scope_filters()
        customer = _customer_scope(selected)
        if customer:
            filters += ' AND c.customer_id=%(customer)s'
            scope['customer'] = customer
        empty = {'currency': None, 'media_source': None, 'windows': serial, 'media': None, 'site': None,
                 'previous_daily': {'media': [], 'site': []}}
        if not _ready():
            return jsonify(empty)
        lo = min(first for first, _ in windows.values())
        hi = max(last for _, last in windows.values())
        params = {'client': selected['client_id'], 'lo': lo, 'hi': hi, **scope}
        daily, currency = _script_daily(params, filters)
        source = 'google_ads_script' if daily else None
        if not daily:
            daily, currency = _imported_daily(params, filters)
            source = 'export' if daily else None
        previous_first, previous_last = windows['period_previous']
        site = site_daily = None
        if _rows("SELECT to_regclass('public.cadu_reports_supertag_sites') IS NOT NULL AS ready")[0]['ready']:
            # Windows whose start already left the event retention are not compared: their totals would be partial.
            oldest = today - timedelta(days=RETENTION_DAYS - 1)
            live = {key: value for key, value in windows.items() if value[0] >= oldest}
            if live:
                site_params = {'client': selected['client_id'], **({'customer': customer} if customer else {})}
                for key, (first, last) in live.items():
                    site_params[f'{key}_since'], site_params[f'{key}_until'] = _bounds(first, last)
                site_params['since'] = min(site_params[f'{key}_since'] for key in live)
                site_params['until'] = max(site_params[f'{key}_until'] for key in live)
                row = (_rows(_site_sql(live, customer), site_params) or [{}])[0]
                site = {key: ({field: int(row.get(f'{key}_{field}') or 0) for field in SITE_FIELDS} if key in live else None)
                        for key in WINDOW_KEYS}
                if 'period_previous' in live:
                    since, until = _bounds(previous_first, previous_last)
                    site_daily = _rows(_SITE_DAILY_SQL.format(customer_filter=' AND s.customer_id=%(customer)s' if customer else ''),
                                       {'client': selected['client_id'], 'since': since, 'until': until, **({'customer': customer} if customer else {})})
        previous_days = [previous_first + timedelta(days=offset) for offset in range((previous_last - previous_first).days + 1)]
        return jsonify(
            currency=currency, media_source=source, windows=serial,
            media=media_windows(daily, windows) if daily else None, site=site,
            previous_daily={'media': fill_days(daily, previous_days, MEDIA_FIELDS, currency) if daily else [],
                            'site': fill_days(site_daily, previous_days, ('sessions', 'conversions'), True) if site_daily is not None else []})
