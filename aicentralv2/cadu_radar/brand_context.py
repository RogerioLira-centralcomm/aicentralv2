"""O que o Radar sabe de uma marca, no formato que a página da marca no Workspace consome.

Leitura apenas: oportunidades abertas, notícias recentes, execuções e alertas ligados a ``studio:<id>``.
Falhas ou tabelas ausentes nunca derrubam a página da marca; o resultado vira "indisponível".
"""
from __future__ import annotations

import logging

from ..cadu_family import repository as family
from . import repository, watches

LOGGER = logging.getLogger(__name__)
OPEN_STATUSES = ('nova', 'salva')


def brand_ref(brand_id) -> str:
    return f'studio:{int(brand_id)}'


def _iso(value):
    return value.isoformat() if hasattr(value, 'isoformat') else (str(value) if value else None)


def _opportunity(row):
    breakdown = row.get('score_breakdown') or {}
    sources = [{'title': entry.get('assunto') or '', 'outlet': entry.get('veiculo') or '', 'date': entry.get('data') or '',
                'url': entry.get('url') or ''} for entry in (breakdown.get('buzz') or [])[:2] if entry.get('url')]
    return {'id': str(row['id']), 'runId': str(row['run_id']) if row.get('run_id') else None, 'title': row['title'],
            'thesis': row.get('thesis') or '', 'quadrant': row.get('quadrant') or 'ignorar', 'status': row.get('status'),
            'editorialScore': row.get('editorial_score'), 'paidScore': row.get('paid_score'),
            'window': breakdown.get('window') or '', 'whyNow': breakdown.get('why_now') or '', 'sources': sources,
            'createdAt': _iso(row.get('created_at'))}


def _signal(row):
    return {'id': str(row['id']), 'title': row['headline'], 'source': row.get('source') or 'Fonte', 'url': row.get('url') or '',
            'publishedAt': _iso(row.get('published_at') or row.get('detected_at')), 'radar': row.get('focus') or ''}


def _watch(row):
    return {'id': str(row['id']), 'name': row.get('name') or row.get('focus') or '', 'status': row.get('status'),
            'frequency': row.get('frequency'), 'lastRunAt': _iso(row.get('last_run_at')), 'nextRunAt': _iso(row.get('next_run_at'))}


def empty(enabled=False, ref=''):
    return {'enabled': bool(enabled), 'available': False, 'brandRef': ref, 'opportunities': [], 'signals': [], 'runs': [], 'watches': []}


def brand_radar(client_id, brand_id, *, enabled, opportunity_limit=6, signal_limit=8):
    ref = brand_ref(brand_id)
    result = empty(enabled, ref)
    if not enabled:
        return result
    try:
        if not repository.available():
            return result
        result['available'] = True
        client_id = int(client_id)
        result['opportunities'] = [_opportunity(row) for row in family.rows(
            '''SELECT id, run_id, title, thesis, quadrant, status, editorial_score, paid_score, score_breakdown, created_at
                 FROM cadu_radar_opportunities
                WHERE client_id = %s AND brand_ref = %s AND status = ANY(%s) AND COALESCE(quadrant, '') <> 'ignorar'
             ORDER BY GREATEST(COALESCE(editorial_score, 0), COALESCE(paid_score, 0)) DESC, created_at DESC LIMIT %s''',
            (client_id, ref, list(OPEN_STATUSES), int(opportunity_limit)))]
        result['signals'] = [_signal(row) for row in family.rows(
            '''SELECT s.id, s.headline, s.source, s.url, s.published_at, s.detected_at, r.focus
                 FROM cadu_radar_signals s JOIN cadu_radar_runs r ON r.id = s.run_id
                WHERE s.client_id = %s AND r.brand_ref = %s AND COALESCE(s.published_at, s.detected_at) >= NOW() - INTERVAL '30 days'
             ORDER BY COALESCE(s.published_at, s.detected_at) DESC LIMIT %s''', (client_id, ref, int(signal_limit)))]
        result['runs'] = [{'id': str(row['id']), 'status': row['status'], 'focus': row.get('focus') or '',
                           'createdAt': _iso(row.get('created_at')), 'finishedAt': _iso(row.get('finished_at')),
                           'trigger': row.get('trigger') or 'manual'} for row in family.rows(
            '''SELECT id, status, focus, trigger, created_at, finished_at FROM cadu_radar_runs
                WHERE client_id = %s AND brand_ref = %s ORDER BY created_at DESC LIMIT 5''', (client_id, ref))]
        if repository.watches_available():
            result['watches'] = [_watch(row) for row in watches.list_watches(client_id) if row.get('brand_ref') == ref]
    except Exception:  # noqa: BLE001 - a página da marca não pode depender do Radar
        LOGGER.warning('Radar da marca indisponível', exc_info=True)
        return empty(enabled, ref)
    return result
