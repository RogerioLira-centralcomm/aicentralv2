"""Planning workspaces backed by canonical catalog snapshots."""
from __future__ import annotations

from uuid import uuid4
from decimal import Decimal, InvalidOperation

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from ..db import get_db
from . import catalog, places

VALID_OBJECTIVES = {'awareness', 'consideracao', 'leads', 'vendas', 'trafego', 'outro'}
VALID_KINDS = {'audiencias', 'canais', 'formatos', 'interativos', 'places'}


def _available():
    result = repository.rows("SELECT to_regclass('public.cadu_planner_plans') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def _require_available():
    if not _available():
        raise BadRequest('Aplique a migration do Planner antes de criar planos.')


def _allocations_available():
    result = repository.rows("SELECT to_regclass('public.cadu_planner_channel_allocations') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def list_plans(client_id, actor_id):
    if not _available():
        return []
    return repository.rows('''SELECT p.id, p.title, p.objective, p.status, p.project_ref, p.brand_ref,
                                     p.updated_at, COUNT(i.id) AS item_count
                                FROM cadu_planner_plans p
                           LEFT JOIN cadu_planner_plan_items i ON i.plan_id = p.id
                               WHERE p.client_id = %s AND p.archived_at IS NULL
                                 AND p.created_by = %s
                            GROUP BY p.id ORDER BY p.updated_at DESC LIMIT 100''', (client_id, actor_id))


def create_plan(client_id, actor_id, payload, context):
    _require_available()
    title = ' '.join(str(payload.get('title') or '').split())[:180]
    if len(title) < 2:
        raise BadRequest('Informe um nome para o plano.')
    objective = str(payload.get('objective') or '').strip()
    if objective and objective not in VALID_OBJECTIVES:
        raise BadRequest('Objetivo inválido.')
    plan_id = str(uuid4())
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cadu_planner_plans
             (id, client_id, created_by, project_ref, brand_ref, title, objective, briefing)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (plan_id, client_id, actor_id, context.get('project_ref'), context.get('brand_ref'),
             title, objective or None, Json({})))
    return get_plan(client_id, actor_id, plan_id)


def get_plan(client_id, actor_id, plan_id):
    _require_available()
    rows = repository.rows('''SELECT id, title, objective, status, project_ref, brand_ref, briefing,
                                      created_at, updated_at FROM cadu_planner_plans
                                WHERE id = %s AND client_id = %s AND created_by = %s AND archived_at IS NULL''',
                           (str(plan_id), client_id, actor_id))
    if not rows:
        raise NotFound('Plano indisponível.')
    plan = rows[0]
    plan['items'] = repository.rows('''SELECT kind, resource_id, snapshot, created_at
                                         FROM cadu_planner_plan_items WHERE plan_id = %s
                                      ORDER BY kind, created_at''', (str(plan_id),))
    plan['allocations'] = repository.rows('''SELECT resource_id, investment, weight, flight, notes
                                                FROM cadu_planner_channel_allocations WHERE plan_id = %s
                                             ORDER BY resource_id''', (str(plan_id),)) if _allocations_available() else []
    plan['allocation_by_channel'] = {row['resource_id']: row for row in plan['allocations']}
    plan['readiness'] = readiness(plan)
    return plan


def readiness(plan):
    """Explain whether a plan can leave drafting without inventing performance scores."""
    briefing = plan.get('briefing') or {}
    kinds = {item['kind'] for item in plan.get('items') or []}
    checks = [
        {'label': 'Objetivo definido', 'complete': bool(plan.get('objective'))},
        {'label': 'Período definido', 'complete': bool(briefing.get('period'))},
        {'label': 'KPI prioritário definido', 'complete': bool(briefing.get('kpis'))},
        {'label': 'Ao menos uma audiência selecionada', 'complete': 'audiencias' in kinds},
        {'label': 'Ao menos um canal selecionado', 'complete': 'canais' in kinds},
        {'label': 'Ao menos um formato selecionado', 'complete': 'formatos' in kinds},
    ]
    channels = [item for item in plan.get('items') or [] if item['kind'] == 'canais']
    if channels:
        allocated = {str(row['resource_id']) for row in plan.get('allocations') or []}
        checks.append({'label': 'Distribuição registrada para os canais',
                       'complete': all(str(item['resource_id']) in allocated for item in channels)})
    return {'ready': all(item['complete'] for item in checks), 'checks': checks}


def update_briefing(client_id, actor_id, plan_id, payload):
    """Store the small, decision-facing brief that guides a media plan."""
    plan = get_plan(client_id, actor_id, plan_id)
    raw_briefing = payload.get('briefing')
    if not isinstance(raw_briefing, dict):
        raise BadRequest('Briefing inválido.')
    limits = {'budget': 80, 'period': 120, 'geography': 120, 'kpis': 180, 'notes': 2000}
    briefing = {}
    for key, limit in limits.items():
        value = raw_briefing.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            briefing[key] = value[:limit]
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE cadu_planner_plans
                          SET briefing = %s, updated_at = NOW()
                        WHERE id = %s''', (Json(briefing), str(plan['id'])))
    return get_plan(client_id, actor_id, plan_id)


def save_allocations(client_id, actor_id, plan_id, payload):
    """Replace the channel allocation grid after checking plan ownership and selection."""
    plan = get_plan(client_id, actor_id, plan_id)
    if not _allocations_available():
        raise BadRequest('Aplique a migration de distribuição de mídia antes de salvar.')
    rows = payload.get('allocations')
    if not isinstance(rows, list) or len(rows) > 100:
        raise BadRequest('Distribuição inválida.')
    allowed = {str(item['resource_id']) for item in plan['items'] if item['kind'] == 'canais'}
    cleaned = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BadRequest('Distribuição inválida.')
        resource_id = str(row.get('resource_id') or '')
        if resource_id not in allowed or resource_id in seen:
            raise BadRequest('Escolha canais que já estejam na mesa de mídia.')
        seen.add(resource_id)
        try:
            investment = Decimal(str(row.get('investment') or '0'))
            weight = Decimal(str(row.get('weight') or '0'))
        except (InvalidOperation, ValueError):
            raise BadRequest('Use valores numéricos para investimento e participação.')
        if investment < 0 or investment > Decimal('999999999.99') or weight < 0 or weight > 100:
            raise BadRequest('Os valores da distribuição estão fora do limite permitido.')
        flight = str(row.get('flight') or '').strip()[:120]
        notes = str(row.get('notes') or '').strip()[:500]
        if investment or weight or flight or notes:
            cleaned.append((resource_id, investment, weight, flight or None, notes or None))
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM cadu_planner_channel_allocations WHERE plan_id = %s', (str(plan['id']),))
        for resource_id, investment, weight, flight, notes in cleaned:
            cur.execute('''INSERT INTO cadu_planner_channel_allocations
                           (plan_id, resource_id, investment, weight, flight, notes)
                           VALUES (%s, %s, %s, %s, %s, %s)''',
                        (str(plan['id']), resource_id, investment, weight, flight, notes))
        cur.execute('UPDATE cadu_planner_plans SET updated_at = NOW() WHERE id = %s', (str(plan['id']),))
    return get_plan(client_id, actor_id, plan_id)


def update_status(client_id, actor_id, plan_id, payload):
    plan = get_plan(client_id, actor_id, plan_id)
    status = str(payload.get('status') or '').strip()
    if status not in {'draft', 'ready'}:
        raise BadRequest('Status inválido.')
    if status == 'ready' and not plan['readiness']['ready']:
        pending = [item['label'] for item in plan['readiness']['checks'] if not item['complete']]
        raise BadRequest('Complete antes de marcar como pronto: ' + '; '.join(pending) + '.')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('UPDATE cadu_planner_plans SET status = %s, updated_at = NOW() WHERE id = %s',
                    (status, str(plan['id'])))
    return get_plan(client_id, actor_id, plan_id)


def toggle_item(client_id, actor_id, plan_id, payload):
    plan = get_plan(client_id, actor_id, plan_id)
    kind, resource_id = str(payload.get('kind') or ''), str(payload.get('resource_id') or '')
    if kind not in VALID_KINDS or not resource_id:
        raise BadRequest('Escolha um item válido do catálogo.')
    record = places.detail(resource_id) if kind == 'places' else catalog.detail(kind, resource_id)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''DELETE FROM cadu_planner_plan_items
                         WHERE plan_id = %s AND kind = %s AND resource_id = %s RETURNING id''',
                    (str(plan['id']), kind, resource_id))
        removed = cur.fetchone()
        if removed:
            selected = False
        else:
            cur.execute('''INSERT INTO cadu_planner_plan_items (plan_id, kind, resource_id, snapshot)
                           VALUES (%s, %s, %s, %s)''',
                        (str(plan['id']), kind, resource_id, Json(record)))
            selected = True
        cur.execute('UPDATE cadu_planner_plans SET updated_at = NOW() WHERE id = %s', (str(plan['id']),))
    return {'selected': selected, 'record': record}
