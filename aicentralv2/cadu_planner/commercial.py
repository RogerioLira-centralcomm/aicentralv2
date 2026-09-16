"""Internal commercial queue for client Planner quote requests.

The Planner owns its client plan and immutable request snapshot.  This module
only connects that request to a CentralComm CRM quotation; it never imports or
changes the legacy SmartPlanner sessions.
"""
from __future__ import annotations

from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from ..db import get_db


VALID_STATUSES = {
    'requested', 'in_review', 'needs_information', 'proposal_available',
    'approved', 'closed',
}


def _available():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.cadu_planner_quote_requests') AS table_name")
        return bool(cur.fetchone()['table_name'])


def _require_available():
    if not _available():
        raise BadRequest('Aplique a migration comercial do Planner antes de abrir solicitações.')


def _row(request_id, *, lock=False):
    _require_available()
    suffix = ' FOR UPDATE' if lock else ''
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f'''SELECT q.id, q.plan_id, q.plan_version_id, q.client_id, q.requested_by,
                               q.scope, q.message, q.status, q.assigned_executive_id, q.crm_quote_id,
                               q.created_at, q.accepted_at, q.closed_at,
                               cli.nome_fantasia AS client_name,
                               requester.nome_completo AS requester_name,
                               assigned.nome_completo AS assigned_executive_name,
                               v.snapshot
                          FROM cadu_planner_quote_requests q
                     LEFT JOIN tbl_cliente cli ON cli.id_cliente = q.client_id
                     LEFT JOIN tbl_contato_cliente requester ON requester.id_contato_cliente = q.requested_by
                     LEFT JOIN tbl_contato_cliente assigned ON assigned.id_contato_cliente = q.assigned_executive_id
                     LEFT JOIN cadu_planner_plan_versions v ON v.id = q.plan_version_id
                         WHERE q.id = %s{suffix}''', (str(request_id),))
        row = cur.fetchone()
    if not row:
        raise NotFound('Solicitação do Planner não encontrada.')
    return dict(row)


def _can_manage(row, actor_id, is_admin):
    if is_admin:
        return
    if row.get('assigned_executive_id') and int(row['assigned_executive_id']) == int(actor_id):
        return
    raise Forbidden('Esta solicitação pertence a outro executivo comercial.')


def list_requests(actor_id, is_admin=False):
    _require_available()
    where = '' if is_admin else 'WHERE q.assigned_executive_id = %s'
    params = () if is_admin else (actor_id,)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f'''SELECT q.id, q.plan_id, q.client_id, q.scope, q.message, q.status,
                               q.assigned_executive_id, q.crm_quote_id, q.created_at, q.accepted_at,
                               cli.nome_fantasia AS client_name,
                               requester.nome_completo AS requester_name,
                               assigned.nome_completo AS assigned_executive_name,
                               v.snapshot
                          FROM cadu_planner_quote_requests q
                     LEFT JOIN tbl_cliente cli ON cli.id_cliente = q.client_id
                     LEFT JOIN tbl_contato_cliente requester ON requester.id_contato_cliente = q.requested_by
                     LEFT JOIN tbl_contato_cliente assigned ON assigned.id_contato_cliente = q.assigned_executive_id
                     LEFT JOIN cadu_planner_plan_versions v ON v.id = q.plan_version_id
                     {where}
                      ORDER BY CASE q.status WHEN 'requested' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END,
                               q.created_at DESC''', params)
        return [dict(row) for row in cur.fetchall()]


def accept_request(request_id, actor_id, is_admin=False):
    _require_available()
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT id, assigned_executive_id, status
                         FROM cadu_planner_quote_requests WHERE id = %s FOR UPDATE''', (str(request_id),))
        row = cur.fetchone()
        if not row:
            raise NotFound('Solicitação do Planner não encontrada.')
        row = dict(row)
        _can_manage(row, actor_id, is_admin) if row.get('assigned_executive_id') else None
        assigned_id = row.get('assigned_executive_id') or actor_id
        cur.execute('''UPDATE cadu_planner_quote_requests
                          SET assigned_executive_id = %s,
                              status = CASE WHEN status = 'requested' THEN 'in_review' ELSE status END,
                              accepted_at = COALESCE(accepted_at, NOW())
                        WHERE id = %s''', (assigned_id, str(request_id)))
    return _row(request_id)


def link_crm_quote(request_id, actor_id, crm_quote_id, is_admin=False):
    try:
        crm_quote_id = int(crm_quote_id)
    except (TypeError, ValueError):
        raise BadRequest('Informe uma cotação do CRM válida.')
    _require_available()
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT id, client_id, assigned_executive_id
                         FROM cadu_planner_quote_requests WHERE id = %s FOR UPDATE''', (str(request_id),))
        row = cur.fetchone()
        if not row:
            raise NotFound('Solicitação do Planner não encontrada.')
        row = dict(row)
        _can_manage(row, actor_id, is_admin) if row.get('assigned_executive_id') else None
        cur.execute('''SELECT id FROM cadu_cotacoes
                         WHERE id = %s AND client_id = %s AND deleted_at IS NULL''', (crm_quote_id, row['client_id']))
        if not cur.fetchone():
            raise BadRequest('A cotação deve existir no CRM e pertencer ao mesmo cliente.')
        cur.execute('''UPDATE cadu_planner_quote_requests
                          SET assigned_executive_id = COALESCE(assigned_executive_id, %s),
                              crm_quote_id = %s, status = 'proposal_available',
                              accepted_at = COALESCE(accepted_at, NOW())
                        WHERE id = %s''', (actor_id, crm_quote_id, str(request_id)))
    return _row(request_id)


def update_status(request_id, actor_id, status, is_admin=False):
    status = str(status or '').strip()
    if status not in VALID_STATUSES:
        raise BadRequest('Status comercial inválido.')
    _require_available()
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT id, assigned_executive_id, crm_quote_id
                         FROM cadu_planner_quote_requests WHERE id = %s FOR UPDATE''', (str(request_id),))
        row = cur.fetchone()
        if not row:
            raise NotFound('Solicitação do Planner não encontrada.')
        row = dict(row)
        _can_manage(row, actor_id, is_admin) if row.get('assigned_executive_id') else None
        if status == 'proposal_available' and not row.get('crm_quote_id'):
            raise BadRequest('Vincule a cotação do CRM antes de disponibilizar a proposta.')
        cur.execute('''UPDATE cadu_planner_quote_requests
                          SET assigned_executive_id = COALESCE(assigned_executive_id, %s), status = %s,
                              accepted_at = CASE WHEN %s = 'requested' THEN accepted_at ELSE COALESCE(accepted_at, NOW()) END,
                              closed_at = CASE WHEN %s IN ('approved', 'closed') THEN COALESCE(closed_at, NOW()) ELSE NULL END
                        WHERE id = %s''', (actor_id, status, status, status, str(request_id)))
    return _row(request_id)
