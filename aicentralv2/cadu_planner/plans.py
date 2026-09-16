"""Planning workspaces backed by canonical catalog snapshots."""
from __future__ import annotations

from uuid import uuid4
from decimal import Decimal, InvalidOperation
from datetime import date

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from ..db import get_db
from . import catalog, places

VALID_OBJECTIVES = {'awareness', 'consideracao', 'leads', 'vendas', 'trafego', 'outro'}
VALID_KINDS = {'audiencias', 'canais', 'formatos', 'interativos', 'places'}
BRIEFING_LIMITS = {'budget': 80, 'period': 120, 'geography': 120, 'kpis': 180, 'notes': 2000}
QUOTE_SCOPES = {'full_operation', 'media_inventory', 'specific_channels'}


def _available():
    result = repository.rows("""SELECT to_regclass('public.cadu_planner_plans') IS NOT NULL AS available,
                                      COUNT(*) FILTER (WHERE column_name IN ('advertiser_name', 'campaign_name')) = 2 AS client_flow
                                 FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = 'cadu_planner_plans'""")
    return bool(result and result[0]['available'] and result[0]['client_flow'])


def _require_available():
    if not _available():
        raise BadRequest('Aplique a migration do Planner antes de criar planos.')


def _allocations_available():
    result = repository.rows("SELECT to_regclass('public.cadu_planner_channel_allocations') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def _commercial_available():
    result = repository.rows("SELECT to_regclass('public.cadu_planner_quote_requests') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def _user_notifications_available():
    result = repository.rows("SELECT to_regclass('public.cadu_planner_user_notifications') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def list_plans(client_id, actor_id):
    if not _available():
        return []
    return repository.rows('''SELECT p.id, p.title, p.objective, p.status, p.advertiser_name, p.campaign_name,
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
    briefing = _clean_briefing(payload.get('briefing') or {})
    first_planner_use = False
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cadu_planner_plans
             (id, client_id, created_by, title, objective, advertiser_name, campaign_name, briefing)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (plan_id, client_id, actor_id, title, objective or None,
             _clean_label(payload.get('advertiser_name')), _clean_label(payload.get('campaign_name')), Json(briefing)))
        if _user_notifications_available():
            cur.execute('''INSERT INTO cadu_planner_user_notifications (client_id, user_id)
                           VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING user_id''', (client_id, actor_id))
            first_planner_use = bool(cur.fetchone())
    if first_planner_use:
        try:
            from ..services.cadu_planner_emails import notify_new_planner_user
            actor = repository.rows('SELECT nome_completo AS name, email FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (actor_id,))
            user = actor[0] if actor else {}
            notify_new_planner_user(user_name=user.get('name') or 'Novo usuário', user_email=user.get('email') or '',
                                    client_name=context.get('name') or 'Cliente Cadu')
        except Exception:
            pass
    return get_plan(client_id, actor_id, plan_id)


def get_plan(client_id, actor_id, plan_id):
    _require_available()
    rows = repository.rows('''SELECT id, title, objective, status, advertiser_name, campaign_name, briefing,
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
    plan['quote_requests'] = repository.rows('''SELECT id, scope, status, assigned_executive_id, crm_quote_id,
                                                        created_at, accepted_at, closed_at
                                                   FROM cadu_planner_quote_requests
                                                  WHERE plan_id = %s ORDER BY created_at DESC''', (str(plan_id),)) if _commercial_available() else []
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


def _clean_briefing(raw_briefing):
    if not isinstance(raw_briefing, dict):
        raise BadRequest('Briefing inválido.')
    briefing = {}
    for key, limit in BRIEFING_LIMITS.items():
        value = raw_briefing.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            briefing[key] = value[:limit]
    return briefing


def _clean_label(value):
    return ' '.join(str(value or '').split())[:180] or None


def update_briefing(client_id, actor_id, plan_id, payload):
    """Store the small, decision-facing brief that guides a media plan."""
    plan = get_plan(client_id, actor_id, plan_id)
    briefing = _clean_briefing(payload.get('briefing'))
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE cadu_planner_plans
                          SET briefing = %s, advertiser_name = %s, campaign_name = %s, updated_at = NOW()
                        WHERE id = %s''', (Json(briefing), _clean_label(payload.get('advertiser_name')),
                                           _clean_label(payload.get('campaign_name')), str(plan['id'])))
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


def request_quote(client_id, actor_id, plan_id, payload):
    """Freeze a client plan for the commercial team; never create prices here."""
    plan = get_plan(client_id, actor_id, plan_id)
    if not _commercial_available():
        raise BadRequest('Aplique a migration comercial do Planner antes de solicitar cotação.')
    if not plan['readiness']['ready']:
        raise BadRequest('Complete o checklist do plano antes de solicitar uma cotação.')
    scope = str(payload.get('scope') or '').strip()
    if scope not in QUOTE_SCOPES:
        raise BadRequest('Escolha o escopo da cotação.')
    message = str(payload.get('message') or '').strip()[:2000] or None
    snapshot = {
        'title': plan['title'], 'objective': plan.get('objective'),
        'advertiser_name': plan.get('advertiser_name'), 'campaign_name': plan.get('campaign_name'),
        'briefing': plan.get('briefing') or {},
        'items': [{'kind': item['kind'], 'resource_id': item['resource_id'],
                   'snapshot': item.get('snapshot') or {}} for item in plan.get('items') or []],
        'allocations': [{**row, 'investment': str(row.get('investment') or 0),
                         'weight': str(row.get('weight') or 0)} for row in plan.get('allocations') or []],
    }
    owner = repository.rows('''SELECT cli.nome_fantasia AS client_name, cli.vendas_central_comm AS executive_id,
                                      exec.nome_completo AS executive_name, exec.email AS executive_email
                                 FROM tbl_cliente cli
                            LEFT JOIN tbl_contato_cliente exec ON exec.id_contato_cliente = cli.vendas_central_comm
                                WHERE cli.id_cliente = %s AND cli.status = TRUE LIMIT 1''', (client_id,))
    owner = owner[0] if owner else {}
    executive_id = owner.get('executive_id')
    version_id, request_id = str(uuid4()), str(uuid4())
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT COALESCE(MAX(version_number), 0) + 1 AS next FROM cadu_planner_plan_versions WHERE plan_id = %s', (str(plan['id']),))
        version_number = cur.fetchone()['next']
        cur.execute('''INSERT INTO cadu_planner_plan_versions
                          (id, plan_id, version_number, snapshot, created_by)
                       VALUES (%s, %s, %s, %s, %s)''',
                    (version_id, str(plan['id']), version_number, Json(snapshot), actor_id))
        cur.execute('''INSERT INTO cadu_planner_quote_requests
                          (id, plan_id, plan_version_id, client_id, requested_by, scope, message, assigned_executive_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                    (request_id, str(plan['id']), version_id, client_id, actor_id, scope, message, executive_id))
    if executive_id:
        # The existing CRM activity is the commercial inbox. A request remains valid
        # even if that optional notification cannot be recorded on an older schema.
        try:
            from .. import db
            db.criar_atividade_cliente(
                client_id, executive_id,
                'Solicitação do Planner: %s%s' % (plan['title'], (' — ' + message) if message else ''),
                date.today(), contato_id=actor_id, tipo='cotacao',
                titulo='Nova solicitação de cotação pelo Planner')
        except Exception:
            pass
    try:
        from ..services.cadu_planner_emails import notify_quote_request
        requester = repository.rows('SELECT nome_completo AS name FROM tbl_contato_cliente WHERE id_contato_cliente = %s', (actor_id,))
        notify_quote_request(executive_email=owner.get('executive_email') or '',
                             executive_name=owner.get('executive_name') or '',
                             client_name=owner.get('client_name') or 'Cliente Cadu',
                             requester_name=(requester[0].get('name') if requester else '') or 'Usuário do Planner',
                             plan_title=plan['title'], scope=scope, message=message or '')
    except Exception:
        pass
    return get_plan(client_id, actor_id, plan_id)
