"""Propostas do Cadu para seções do plano e a linha do tempo da co-construção.

O Cadu nunca grava direto no plano. Ele cria uma proposta (``pending``) com o
conteúdo da seção, a justificativa, as evidências e a revisão do plano em que
se baseou. O plano só muda quando o usuário decide, em uma transação que
confere a revisão e a incrementa.
"""
from __future__ import annotations

from uuid import uuid4

from flask import current_app
from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from ..db import get_db
from . import workbench
from .plans import BRIEFING_LIMITS, VALID_OBJECTIVES, _clean_briefing, get_plan

EVENT_ROLES = ('user', 'cadu', 'system')
MAX_EVENT_BODY = 4000


def available() -> bool:
    result = repository.rows("""SELECT to_regclass('public.cadu_planner_proposals') IS NOT NULL AS proposals,
                                       EXISTS (SELECT 1 FROM information_schema.columns
                                                WHERE table_schema = 'public' AND table_name = 'cadu_planner_plans'
                                                  AND column_name = 'workbench') AS workbench""")
    return bool(result and result[0]['proposals'] and result[0]['workbench'])


def cobuild_enabled() -> bool:
    return bool(current_app.config.get('CADU_PLANNER_COBUILD_ENABLED')) and available()


def pending_by_section(plan_id) -> dict:
    if not available():
        return {}
    rows = repository.rows('''SELECT DISTINCT ON (section) section, id
                                FROM cadu_planner_proposals
                               WHERE plan_id = %s AND status = 'pending'
                            ORDER BY section, created_at DESC''', (str(plan_id),))
    return {row['section']: str(row['id']) for row in rows}


def list_proposals(plan_id, limit=50):
    if not available():
        return []
    return repository.rows('''SELECT id, section, payload, rationale, evidence, questions, status,
                                     base_revision, model, created_at, decided_at
                                FROM cadu_planner_proposals WHERE plan_id = %s
                            ORDER BY created_at DESC LIMIT %s''', (str(plan_id), int(limit)))


def list_events(plan_id, limit=200):
    if not available():
        return []
    return repository.rows('''SELECT id, role, kind, body, proposal_id, created_at
                                FROM cadu_planner_plan_events WHERE plan_id = %s
                            ORDER BY created_at, id LIMIT %s''', (str(plan_id), int(limit)))


def record_event(cur, plan_id, role, kind, body=None, proposal_id=None, actor_id=None):
    if role not in EVENT_ROLES:
        raise ValueError('Papel de evento inválido.')
    text = body if isinstance(body, dict) else {'text': str(body or '')[:MAX_EVENT_BODY]}
    cur.execute('''INSERT INTO cadu_planner_plan_events (plan_id, role, kind, body, proposal_id, actor_id)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                (str(plan_id), role, str(kind)[:32], Json(text), proposal_id, actor_id))


def create_proposal(plan, section, payload, *, rationale='', evidence=None, questions=None, model=None, cost=None):
    """Grava uma proposta do Cadu. Uma proposta pendente anterior da seção é substituída."""
    if not workbench.can_propose(plan, section):
        raise BadRequest('A seção está travada pelo usuário.')
    proposal_id = str(uuid4())
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE cadu_planner_proposals SET status = 'superseded'
                        WHERE plan_id = %s AND section = %s AND status = 'pending' ''', (str(plan['id']), section))
        cur.execute('''INSERT INTO cadu_planner_proposals
                          (id, plan_id, section, payload, rationale, evidence, questions, base_revision, model, cost)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (proposal_id, str(plan['id']), section, Json(payload or {}), (rationale or '')[:4000],
                     Json(evidence or []), Json(questions or []), int(plan.get('revision') or 0),
                     model, Json(cost or {})))
        record_event(cur, plan['id'], 'cadu', 'proposal', {'section': section, 'text': (rationale or '')[:600]},
                     proposal_id=proposal_id)
    return proposal_id


def propose_section(client_id, actor_id, plan_id, section):
    """Ponto de entrada dos proposers por seção (Fase 2).

    Enquanto a flag ``CADU_PLANNER_COBUILD_ENABLED`` estiver desligada, ou os
    proposers ainda não existirem, responde de forma explícita em vez de
    inventar conteúdo.
    """
    if section not in workbench.SECTION_KEYS:
        raise BadRequest('Seção do plano desconhecida.')
    if not cobuild_enabled():
        raise BadRequest('A co-construção com o Cadu ainda não está habilitada neste ambiente.')
    raise NotImplementedError('Proposers por seção entram na Fase 2.')


def decide(client_id, actor_id, plan_id, proposal_id, payload):
    """Aplica a decisão do usuário (aceitar, aceitar em parte, recusar)."""
    if not available():
        raise BadRequest('Aplique a migration de co-construção do Planner.')
    plan = get_plan(client_id, actor_id, plan_id)
    rows = repository.rows('''SELECT id, section, payload, status, base_revision
                                FROM cadu_planner_proposals WHERE id = %s AND plan_id = %s''',
                           (str(proposal_id), str(plan['id'])))
    if not rows:
        raise NotFound('Proposta indisponível.')
    proposal = {**rows[0], 'id': str(rows[0]['id'])}
    decision = str(payload.get('decision') or '')
    new_workbench, changes = workbench.apply_proposal(
        plan, proposal, decision, payload.get('fields'), payload.get('expected_revision'))
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE cadu_planner_plans
                          SET workbench = %s, revision = revision + 1, updated_at = NOW()
                        WHERE id = %s AND revision = %s RETURNING revision''',
                    (Json(new_workbench), str(plan['id']), int(plan.get('revision') or 0)))
        if not cur.fetchone():
            from werkzeug.exceptions import Conflict
            raise Conflict('O plano mudou enquanto a decisão era registrada. Atualize e tente de novo.')
        for section, value in changes.items():
            _apply_section(cur, plan, section, value)
        cur.execute('''UPDATE cadu_planner_proposals SET status = %s, decided_by = %s, decided_at = NOW()
                        WHERE id = %s''', (decision, actor_id, proposal['id']))
        record_event(cur, plan['id'], 'user', 'decision', {'section': proposal['section'], 'decision': decision},
                     proposal_id=proposal['id'], actor_id=actor_id)
    return get_plan(client_id, actor_id, plan_id)


def _apply_section(cur, plan, section, value):
    """Traduz o conteúdo aceito de uma seção para as colunas e itens do plano."""
    if not isinstance(value, dict):
        raise BadRequest('Conteúdo da proposta inválido.')
    briefing = dict(plan.get('briefing') or {})
    if section in ('briefing', 'pracas', 'verba', 'objetivo'):
        updates = {key: value[key] for key in BRIEFING_LIMITS if key in value}
        if updates:
            briefing = {**briefing, **_clean_briefing(updates)}
            cur.execute('UPDATE cadu_planner_plans SET briefing = %s WHERE id = %s', (Json(briefing), str(plan['id'])))
        objective = value.get('objective')
        if section == 'objetivo' and objective:
            if objective not in VALID_OBJECTIVES:
                raise BadRequest('Objetivo inválido na proposta.')
            cur.execute('UPDATE cadu_planner_plans SET objective = %s WHERE id = %s', (objective, str(plan['id'])))
    if section in workbench.ITEM_SECTIONS:
        from . import catalog
        allowed = workbench.ITEM_SECTIONS[section]
        for item in value.get('add') or []:
            kind, resource_id = str(item.get('kind') or ''), str(item.get('resource_id') or '')
            if kind not in allowed or not resource_id:
                raise BadRequest('Item de catálogo inválido na proposta.')
            snapshot = catalog.client_detail(kind, resource_id)
            cur.execute('''INSERT INTO cadu_planner_plan_items (plan_id, kind, resource_id, snapshot)
                           VALUES (%s, %s, %s, %s) ON CONFLICT (plan_id, kind, resource_id) DO NOTHING''',
                        (str(plan['id']), kind, resource_id, Json(snapshot)))
    # Papéis de canal, cenários de verba e o sistema criativo vivem no workbench.
    extra = {key: val for key, val in value.items() if key not in BRIEFING_LIMITS and key not in ('add', 'objective')}
    if extra:
        cur.execute('''UPDATE cadu_planner_plans
                          SET workbench = jsonb_set(workbench, ARRAY['sections', %s, 'value'], %s, TRUE)
                        WHERE id = %s''', (section, Json(extra), str(plan['id'])))
