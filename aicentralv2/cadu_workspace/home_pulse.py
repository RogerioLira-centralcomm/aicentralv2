"""Resumo de "Seu dia no Cadu": um fato real por solução, para a Home da conta com trabalho em andamento.

Cada cartão é independente: se uma consulta falha ou a solução não tem dado, o cartão simplesmente não existe.
Somente leitura; nunca cria tabelas nem escreve.
"""
from __future__ import annotations

import logging

from flask import current_app

from ..cadu_family import repository
from ..product_domains import product_url

log = logging.getLogger(__name__)


def _iso(value):
    return value.isoformat() if hasattr(value, 'isoformat') else None


def _table_exists(name: str) -> bool:
    found = repository.rows('SELECT to_regclass(%s) IS NOT NULL AS ok', (f'public.{name}',))
    return bool(found and found[0]['ok'])


def _plans(client_id, user_id):
    from ..cadu_planner import plans
    drafts = [plan for plan in plans.list_plans(client_id, user_id) if plan.get('status') == 'draft']
    if not drafts:
        return None
    latest = drafts[0]
    return {'id': 'plans', 'solution': 'planner', 'title': 'Planos', 'count': len(drafts),
            'noun': 'plano' if len(drafts) == 1 else 'planos', 'caption': 'em andamento',
            'detail': {'title': latest.get('title') or 'Plano sem nome', 'items': int(latest.get('item_count') or 0), 'updatedAt': _iso(latest.get('updated_at'))},
            'cta': 'Retomar plano', 'href': product_url('planner', f"/planos/{latest['id']}")}


def _radar(client_id, user_id):
    from ..cadu_radar import radars
    items = radars.list_radars(client_id, user_id)
    if not items:
        return None
    news = sum(int((item.get('changes') or {}).get('signals') or 0) for item in items)
    top = [{'title': item.get('title') or 'Radar', 'changes': int((item.get('changes') or {}).get('signals') or 0), 'at': _iso(item.get('activity_at'))} for item in items[:2]]
    return {'id': 'radar', 'solution': 'planner', 'title': 'Radar', 'count': news,
            'noun': 'novidade' if news == 1 else 'novidades', 'caption': 'desde sua última visita',
            'detail': {'radars': top}, 'cta': 'Ver resultados', 'href': product_url('planner', '/radares')}


def _studio(client_id, user_id):
    if not _table_exists('cx_studio_assets'):
        return None
    rows = repository.rows('''SELECT title, asset_url, kind, updated_at FROM cx_studio_assets
                               WHERE client_id = %s AND owner_user_id = %s AND status = 'working'
                                 AND kind IN ('image', 'video') AND deleted_at IS NULL AND asset_url <> ''
                            ORDER BY updated_at DESC LIMIT 50''', (client_id, user_id))
    if not rows:
        return None
    return {'id': 'studio', 'solution': 'studio', 'title': 'Studio', 'count': len(rows),
            'noun': 'criativo' if len(rows) == 1 else 'criativos', 'caption': 'em edição',
            'detail': {'thumbs': [row['asset_url'] for row in rows[:3] if row['kind'] == 'image'][:3], 'more': max(0, len(rows) - 3), 'updatedAt': _iso(rows[0]['updated_at'])},
            'cta': 'Continuar edição', 'href': product_url('studio', '/')}


def _reports(client_id, user_id):
    if not _table_exists('cadu_connect_report_workspaces'):
        return None
    rows = repository.rows('''SELECT campaign_name, updated_at FROM cadu_connect_report_workspaces
                               WHERE client_id = %s ORDER BY updated_at DESC LIMIT 200''', (client_id,))
    if not rows:
        return None
    return {'id': 'reports', 'solution': 'connect', 'title': 'Reports', 'count': len(rows),
            'noun': 'relatório' if len(rows) == 1 else 'relatórios', 'caption': 'no Workspace',
            'detail': {'title': rows[0].get('campaign_name') or 'Relatório', 'updatedAt': _iso(rows[0]['updated_at'])},
            'cta': 'Ver relatório', 'href': product_url('connect', '/')}


def build_home_pulse(client_id, user_id) -> list[dict]:
    cards = []
    for builder in (_reports, _studio, _plans, _radar):
        try:
            card = builder(client_id, user_id)
        except Exception:
            current_app.logger.warning('Resumo da Home: %s indisponível', builder.__name__, exc_info=True)
            continue
        if card:
            cards.append(card)
    return cards
