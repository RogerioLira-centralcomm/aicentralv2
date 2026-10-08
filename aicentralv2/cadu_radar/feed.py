"""Tela de resultados do Radar: os sinais achados pelas buscas, em ordem de relevância ou de data.

Os sinais já vêm verificados pelo pipeline (data recente, link que abre). Cada um carrega o radar (tema da busca)
que o achou e os ângulos que sustenta; aqui também se guardam os salvos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..cadu_family import repository

TIER_WEIGHT = {'A': 3, 'B': 2, 'C': 1}


def available():
    result = repository.rows("SELECT to_regclass('public.cadu_radar_signals') IS NOT NULL AS ok, "
                             "EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cadu_radar_signals' "
                             "AND column_name = 'saved_at') AS saved")
    return bool(result and result[0]['ok']), bool(result and result[0]['saved'])


def _score(item, now):
    age_days = max(0.0, (now - (item['published_at'] or item['detected_at'])).total_seconds() / 86400)
    return (item['angle_count'] * 4 + TIER_WEIGHT.get(item['tier'], 0) * 2 + max(0.0, 8 - age_days) / 2
            + (3 if item['saved'] else 0))


def list_feed(client_id, *, days=30, limit=120):
    exists, has_saved = available()
    if not exists:
        return {'items': []}
    days = max(1, min(int(days), 365))
    now = datetime.now(timezone.utc)
    saved_col = 's.saved_at' if has_saved else 'NULL::timestamptz'
    rows = repository.rows(f'''SELECT s.id, s.headline, s.description, s.source, s.url, s.published_at, s.detected_at, s.verification,
                                      {saved_col} AS saved_at, s.run_id, r.focus, r.brand_ref, r.project_ref, r.watch_id
                                 FROM cadu_radar_signals s LEFT JOIN cadu_radar_runs r ON r.id = s.run_id
                                WHERE s.client_id = %s AND COALESCE(s.published_at, s.detected_at) >= %s
                             ORDER BY COALESCE(s.published_at, s.detected_at) DESC LIMIT %s''',
                              (int(client_id), now - timedelta(days=days), max(1, min(int(limit), 300))))
    run_ids = sorted({str(row['run_id']) for row in rows if row['run_id']})
    angles = {}
    if run_ids:
        for opp in repository.rows('''SELECT id, title, status, signal_ids FROM cadu_radar_opportunities
                                       WHERE client_id = %s AND run_id = ANY(%s::uuid[])''', (int(client_id), run_ids)):
            for signal_id in opp.get('signal_ids') or []:
                angles.setdefault(str(signal_id), []).append({'id': str(opp['id']), 'title': opp['title'], 'status': opp['status']})
    from . import repository as radar
    plan_of = {}
    for plan in radar.plans_for(client_id, signal_ids=[row['id'] for row in rows]):
        if plan.get('signal_id'):
            plan_of.setdefault(str(plan['signal_id']), {'id': str(plan['id']), 'title': plan['title']})
    items = []
    for row in rows:
        verification = row.get('verification') or {}
        item = {'id': str(row['id']), 'title': row['headline'], 'summary': row['description'] or '', 'source': row['source'] or 'Fonte',
                'url': row['url'], 'published_at': row['published_at'], 'detected_at': row['detected_at'],
                'tier': verification.get('tier'),
                'angles': angles.get(str(row['id']), []), 'plan': plan_of.get(str(row['id'])), 'saved': bool(row['saved_at']), 'radar': row['focus'] or '',
                'brand_ref': row['brand_ref'], 'project_ref': row['project_ref'], 'scheduled': bool(row['watch_id']),
                'run_id': str(row['run_id']) if row['run_id'] else None}
        item['angle_count'] = len(item['angles'])
        item['score'] = round(_score(item, now), 2)
        items.append(item)
    return {'items': items}


def set_saved(client_id, signal_id, saved):
    from werkzeug.exceptions import NotFound
    from .db import transaction
    _exists, has_saved = available()
    if not has_saved:
        raise NotFound('Recurso indisponível.')
    with transaction() as cur:
        cur.execute('UPDATE cadu_radar_signals SET saved_at = CASE WHEN %s THEN NOW() ELSE NULL END '
                    'WHERE id = %s AND client_id = %s RETURNING id', (bool(saved), str(signal_id), int(client_id)))
        if not cur.fetchone():
            raise NotFound('Notícia indisponível.')
    return bool(saved)
