"""Reports entitlements independent of Workspace projects and brands."""

import re
import unicodedata
from flask import abort, g, jsonify, request, session

from ..auth import login_required_api
from ..cadu_family import context
from ..db import get_db


def reports_only():
    if not session.get('user_id'):
        return False
    if not hasattr(g, 'reports_only'):
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_reports_user_access') IS NOT NULL AS ready")
            ready = bool(cursor.fetchone()['ready'])
            if not ready:
                g.reports_only = False
            else:
                cursor.execute('''SELECT COALESCE(reports_only,FALSE) AS reports_only
                    FROM tbl_contato_cliente WHERE id_contato_cliente=%s AND status=TRUE''',
                    (session['user_id'],))
                row = cursor.fetchone()
                g.reports_only = bool(row and row['reports_only'])
    return g.reports_only


def authorized_clients():
    actor = context.identity()
    legacy = [] if reports_only() else context.authorized_clients()
    with get_db().cursor() as cursor:
        if reports_only():
            cursor.execute('''SELECT c.id_cliente AS id,c.nome_fantasia AS name,a.role,
                    'centralcomm' AS kind
                FROM cadu_reports_user_access a JOIN tbl_cliente c ON c.id_cliente=a.client_id
                WHERE a.organization_id=%s AND a.user_id=%s AND a.revoked_at IS NULL
                    AND c.status=TRUE ORDER BY c.nome_fantasia,c.id_cliente''',
                (actor['organization_id'], actor['id']))
            legacy = [dict(row) for row in cursor.fetchall()]
        cursor.execute('''SELECT c.id,c.name,a.role,'reports' AS kind
            FROM cadu_reports_user_access a JOIN cadu_reports_clients c
                ON c.id=a.client_id AND c.organization_id=a.organization_id
            WHERE a.organization_id=%s AND a.user_id=%s AND a.revoked_at IS NULL
                AND c.status='active' ORDER BY c.name,c.id''',
            (actor['organization_id'], actor['id']))
        native = [dict(row) for row in cursor.fetchall()]
    normalized = [dict(item, kind=item.get('kind', 'centralcomm')) for item in legacy]
    known = {int(item['id']) for item in normalized}
    return normalized + [item for item in native if int(item['id']) not in known]


def resolve(client_id=None):
    actor = context.identity()
    clients = authorized_clients()
    if client_id is None:
        preferred = session.get('cliente_id') or actor['organization_id']
        try:
            preferred_id = int(preferred)
        except (TypeError, ValueError):
            preferred_id = None
        client_id = preferred_id if any(int(item['id']) == preferred_id for item in clients) else \
            (clients[0]['id'] if clients else None)
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        abort(400, description='Cliente inválido.')
    client = next((item for item in clients if int(item['id']) == client_id), None)
    if not client:
        abort(403, description='Este login não tem acesso ao cliente no Reports.')
    if client.get('kind') == 'reports' or reports_only():
        return {'organization_id': actor['organization_id'], 'client_id': client_id,
                'client_name': client['name'], 'role': client['role'],
                'client_kind': client.get('kind', 'centralcomm')}
    selected = context.resolve(client_id)
    selected['client_kind'] = 'centralcomm'
    return selected


def inventory(client_id):
    if reports_only():
        return []
    with get_db().cursor() as cursor:
        cursor.execute('SELECT 1 FROM cadu_reports_clients WHERE id=%s', (client_id,))
        if cursor.fetchone():
            return []
    return context.inventory(client_id)


def register(bp):
    def admin_scope(payload=None):
        from .reports_v1 import _selection, _write_guard
        selected = _selection(payload)
        if selected['role'] != 'admin' or reports_only():
            abort(403, description='A gestão de acesso requer um administrador da organização.')
        context.require_admin()
        if request.method != 'GET':
            _write_guard(selected)
        return selected

    @bp.post('/api/v1/reports/clients')
    @login_required_api
    def reports_client_create():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        from .reports_v1 import _selection, _write_guard
        selected = _selection(payload)
        if selected['role'] != 'admin':
            abort(403, description='A criação de clientes exige perfil administrador no Reports.')
        _write_guard(selected)
        name = payload.get('name')
        if not isinstance(name, str):
            abort(400, description='Informe o nome do cliente Reports.')
        name = ' '.join(name.strip().split())
        if not name or len(name) > 200:
            abort(400, description='O nome deve ter entre 1 e 200 caracteres.')
        slug = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')[:160]
        if not slug:
            abort(400, description='O nome precisa conter letras ou números.')
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO cadu_reports_clients
                (organization_id,name,slug,created_by)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (organization_id,slug) DO NOTHING
                RETURNING id,name,slug,status''',
                (selected['organization_id'], name, slug, session['user_id']))
            row = cursor.fetchone()
            if not row:
                abort(409, description='Já existe um cliente Reports com esse nome.')
            client = dict(row)
            cursor.execute('''INSERT INTO cadu_reports_user_access
                (organization_id,user_id,client_id,role,granted_by)
                VALUES (%s,%s,%s,'admin',%s)''',
                (selected['organization_id'], session['user_id'], client['id'], session['user_id']))
        conn.commit()
        return jsonify(client=client), 201

    @bp.get('/api/v1/reports/access')
    @login_required_api
    def reports_access_list():
        selected = admin_scope()
        with get_db().cursor() as cursor:
            cursor.execute('''SELECT u.id_contato_cliente AS id,u.nome_completo AS name,
                    u.email,u.reports_only,a.role,a.revoked_at
                FROM tbl_contato_cliente u
                LEFT JOIN cadu_reports_user_access a
                    ON a.user_id=u.id_contato_cliente AND a.organization_id=%s AND a.client_id=%s
                WHERE u.pk_id_tbl_cliente=%s AND u.status=TRUE
                ORDER BY lower(u.nome_completo),u.id_contato_cliente''',
                (selected['organization_id'], selected['client_id'], selected['organization_id']))
            users = [dict(row) for row in cursor.fetchall()]
        return jsonify(users=users)

    @bp.post('/api/v1/reports/access')
    @login_required_api
    def reports_access_grant():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = admin_scope(payload)
        try:
            user_id = int(payload.get('user_id'))
        except (TypeError, ValueError):
            abort(400, description='Usuário inválido.')
        role = payload.get('role')
        if role not in {'viewer', 'member', 'admin'} or not isinstance(payload.get('exclusive'), bool):
            abort(400, description='Informe o papel e se o acesso será exclusivo ao Reports.')
        with get_db().cursor() as cursor:
            cursor.execute('''SELECT id_contato_cliente,user_type FROM tbl_contato_cliente
                WHERE id_contato_cliente=%s AND pk_id_tbl_cliente=%s AND status=TRUE FOR UPDATE''',
                (user_id, selected['organization_id']))
            user = cursor.fetchone()
            if not user:
                abort(404, description='Usuário fora desta organização.')
            if payload['exclusive'] and (user_id == session['user_id'] or user['user_type'] in ('admin', 'superadmin')):
                abort(400, description='Não é possível tornar esta conta administrativa exclusiva do Reports.')
            cursor.execute('''INSERT INTO cadu_reports_user_access
                (organization_id,user_id,client_id,role,granted_by)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (organization_id,user_id,client_id)
                DO UPDATE SET role=EXCLUDED.role,granted_by=EXCLUDED.granted_by,
                    granted_at=NOW(),revoked_at=NULL''',
                (selected['organization_id'], user_id, selected['client_id'], role, session['user_id']))
            cursor.execute('''UPDATE tbl_contato_cliente SET reports_only=%s
                WHERE id_contato_cliente=%s''', (payload['exclusive'], user_id))
        get_db().commit()
        return jsonify(granted=True)

    @bp.post('/api/v1/reports/access/<int:user_id>/revoke')
    @login_required_api
    def reports_access_revoke(user_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = admin_scope(payload)
        with get_db().cursor() as cursor:
            cursor.execute('''UPDATE cadu_reports_user_access SET revoked_at=NOW()
                WHERE organization_id=%s AND user_id=%s AND client_id=%s AND revoked_at IS NULL
                RETURNING user_id''',
                (selected['organization_id'], user_id, selected['client_id']))
            revoked = cursor.fetchone()
        if not revoked:
            abort(404)
        get_db().commit()
        return jsonify(revoked=True)
