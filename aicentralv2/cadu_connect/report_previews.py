"""Relatórios → biblioteca: o que cada card mostra além do nome. Plataformas das campanhas do relatório, uma capa real
(o criativo mais recente feito no Studio para uma dessas campanhas) e a série diária dos últimos dias do período do relatório,
com o total e o período anterior de mesma duração. Só leitura e em poucas consultas para a lista inteira."""
from datetime import date, timedelta

from flask import jsonify

from ..auth import login_required_api
from .reports_v1 import _rows, _selection

SPARK_DAYS = 30
MAX_REPORTS = 60


def _table_ready(name):
    return bool(_rows('SELECT to_regclass(%s) IS NOT NULL AS ready', (f'public.{name}',))[0]['ready'])


def _campaign_ids(row):
    ids = [row.get('media_campaign_id')] if row.get('media_campaign_id') else \
        [item.get('id') for item in row.get('flow_campaigns') or [] if isinstance(item, dict)]
    return [int(value) for value in ids if str(value or '').isdigit()]


def _window(row, today):
    """Últimos dias do período do relatório (no máximo SPARK_DAYS) e a janela anterior de mesma duração."""
    try:
        end = date.fromisoformat(row['end_date']) if row.get('end_date') else today - timedelta(days=1)
        start = date.fromisoformat(row['start_date']) if row.get('start_date') else end - timedelta(days=SPARK_DAYS - 1)
    except ValueError:
        end, start = today - timedelta(days=1), today - timedelta(days=SPARK_DAYS)
    end = min(end, today)
    start = min(max(start, end - timedelta(days=SPARK_DAYS - 1)), end)
    days = (end - start).days + 1
    return start, end, start - timedelta(days=days), start - timedelta(days=1)


def build_previews(client_id, reports, today=None):
    """`reports`: linhas com id, media_campaign_id, flow_campaigns, start_date e end_date. Devolve um preview por relatório."""
    today = today or date.today()
    plans = {row['id']: {'ids': _campaign_ids(row), 'window': _window(row, today)} for row in reports}
    every = sorted({value for plan in plans.values() for value in plan['ids']})
    previews = {report_id: {'id': report_id, 'platforms': [], 'cover_url': None, 'metric': None, 'total': None, 'previous': None, 'series': []}
                for report_id in plans}

    platforms = {} if not every else {row['id']: row['platform'] for row in _rows('''SELECT c.id,a.platform FROM cadu_reports_campaigns c
        LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id WHERE c.client_id=%s AND c.id = ANY(%s)''', (client_id, every))}

    # Capa: a gerada para o próprio relatório vence; senão, o criativo mais recente de uma das campanhas.
    report_covers, campaign_covers = {}, {}
    if _table_ready('cx_studio_sessions') and _table_ready('cx_studio_assets'):
        for row in _rows('''SELECT s.metadata->>'reports_report_id' AS report_id,s.metadata->>'reports_campaign_id' AS campaign_id,
                COALESCE(s.metadata->>'reports_cover_url',a.asset_url) AS url
                FROM cx_studio_sessions s LEFT JOIN cx_studio_assets a ON a.id=s.active_asset_id AND a.deleted_at IS NULL
                WHERE s.metadata->>'origin'='cadu_reports' AND s.metadata->>'reports_client_id'=%s
                    AND (s.metadata->>'reports_report_id' = ANY(%s) OR s.metadata->>'reports_campaign_id' = ANY(%s))
                    AND COALESCE(s.metadata->>'reports_cover_url',a.asset_url) IS NOT NULL
                ORDER BY s.updated_at DESC LIMIT 500''', (str(client_id), [str(value) for value in plans], [str(value) for value in every])):
            if row['report_id'] and str(row['report_id']).isdigit():
                report_covers.setdefault(int(row['report_id']), row['url'])
            elif row['campaign_id'] and str(row['campaign_id']).isdigit():
                campaign_covers.setdefault(int(row['campaign_id']), row['url'])

    for report_id in plans:
        previews[report_id]['cover_url'] = report_covers.get(report_id)
    daily = {}
    if every and _table_ready('cadu_reports_campaign_daily_metrics'):
        first = min(plan['window'][2] for plan in plans.values() if plan['ids'])
        last = max(plan['window'][1] for plan in plans.values() if plan['ids'])
        for row in _rows('''SELECT campaign_id,metric_date,SUM(clicks)::bigint AS clicks,SUM(conversions)::numeric AS conversions
                FROM cadu_reports_campaign_daily_metrics WHERE client_id=%s AND campaign_id = ANY(%s) AND metric_date BETWEEN %s AND %s
                GROUP BY campaign_id,metric_date''', (client_id, every, first, last)):
            daily[(row['campaign_id'], row['metric_date'])] = (int(row['clicks'] or 0), float(row['conversions'] or 0))

    for report_id, plan in plans.items():
        if not plan['ids']:
            continue
        preview = previews[report_id]
        preview['platforms'] = sorted({platforms[value] for value in plan['ids'] if platforms.get(value)})
        preview['cover_url'] = preview['cover_url'] or next((campaign_covers[value] for value in plan['ids'] if value in campaign_covers), None)
        start, end, previous_start, previous_end = plan['window']

        def day_values(first_day, last_day):
            out = []
            for offset in range((last_day - first_day).days + 1):
                day = first_day + timedelta(days=offset)
                clicks = sum(daily.get((value, day), (0, 0))[0] for value in plan['ids'])
                conversions = sum(daily.get((value, day), (0, 0))[1] for value in plan['ids'])
                out.append((day, clicks, conversions))
            return out
        now, before = day_values(start, end), day_values(previous_start, previous_end)
        if not any(clicks or conversions for _, clicks, conversions in now + before):
            continue
        # Conversões quando houver; senão cliques, que toda plataforma reporta.
        column = 2 if any(conversions for _, _, conversions in now) else 1
        preview['metric'] = 'conversions' if column == 2 else 'clicks'
        preview['series'] = [{'date': item[0].isoformat(), 'value': round(item[column], 2)} for item in now]
        preview['total'] = round(sum(item[column] for item in now), 2)
        preview['previous'] = round(sum(item[column] for item in before), 2)
    return list(previews.values())


def register(bp):
    @bp.get('/api/v2/reports/workspaces/previews')
    @login_required_api
    def reports_workspace_previews():
        selected = _selection()
        if not _table_ready('cadu_connect_report_workspaces'):
            return jsonify(previews=[])
        reports = _rows('''SELECT id,media_campaign_id,document->'flow_campaigns' AS flow_campaigns,
                document->>'start_date' AS start_date,document->>'end_date' AS end_date
            FROM cadu_connect_report_workspaces WHERE client_id=%s ORDER BY updated_at DESC LIMIT %s''', (selected['client_id'], MAX_REPORTS))
        if not _table_ready('cadu_reports_campaigns'):
            return jsonify(previews=[{'id': row['id'], 'platforms': [], 'cover_url': None, 'metric': None, 'total': None, 'previous': None, 'series': []} for row in reports])
        return jsonify(previews=build_previews(selected['client_id'], reports))
