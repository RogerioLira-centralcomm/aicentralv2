"""Reports ownership and memberships. Workspace is an optional integration."""
import re
import unicodedata
from flask import abort, g, jsonify, request, session
from ..auth import login_required_api
from ..db import get_db


def reports_only():
    if not session.get('user_id'):
        return False
    if not hasattr(g, 'reports_only'):
        with get_db().cursor() as cursor:
            cursor.execute('SELECT COALESCE(reports_only,FALSE) AS reports_only FROM tbl_contato_cliente WHERE id_contato_cliente=%s AND status=TRUE', (session['user_id'],))
            row = cursor.fetchone()
            g.reports_only = bool(row and row['reports_only'])
    return g.reports_only


def authorized_clients():
    if not session.get('user_id'):
        abort(401)
    with get_db().cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.cadu_reports_client_memberships') IS NOT NULL AS ready")
        if not cursor.fetchone()['ready']:
            abort(503, description='Reports requer a migração de contas v2 antes de iniciar.')
        cursor.execute('''SELECT c.id_cliente AS id,c.nome_fantasia AS name,m.role,m.access_scope
            FROM cadu_reports_client_memberships m JOIN tbl_cliente c ON c.id_cliente=m.client_id
            JOIN tbl_contato_cliente u ON u.id_contato_cliente=m.user_id
            WHERE m.user_id=%s AND m.revoked_at IS NULL AND c.status=TRUE AND u.status=TRUE
            ORDER BY c.nome_fantasia,c.id_cliente''', (session['user_id'],))
        return [dict(row) for row in cursor.fetchall()]


def resolve(client_id=None):
    clients = authorized_clients()
    if client_id is None:
        preferred = session.get('reports_client_id')
        client_id = next((c['id'] for c in clients if str(c['id']) == str(preferred)), clients[0]['id'] if clients else None)
    if isinstance(client_id, (bool, float, list, dict)):
        abort(400, description='Conta principal inválida.')
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        abort(403, description='Nenhuma conta Reports autorizada.')
    client = next((c for c in clients if int(c['id']) == client_id), None)
    if not client:
        abort(403, description='Sem acesso a esta conta Reports.')
    selected = dict(user_id=session['user_id'],client_id=client_id,client_name=client['name'],role=client['role'],access_scope=client['access_scope'])
    if selected['access_scope'] == 'shared':
        # Resource guests use the restricted viewer endpoints only. Never expose aggregate APIs.
        if not request.path.startswith('/connect/app') and not request.path.endswith('/bootstrap') and not request.path.endswith('/shared/resources'):
            match=re.fullmatch(r'/connect/api/v2/reports/flow/flows/([0-9a-fA-F-]{36})/(journey|live|previews(?:/[^/]+/image)?)',request.path)
            allowed=False
            if match and request.method=='GET':
                with get_db().cursor() as cursor:
                    cursor.execute('''SELECT f.id FROM cadu_reports_flow_registry f WHERE f.id=%s AND f.client_id=%s AND
                        (EXISTS(SELECT 1 FROM cadu_reports_flow_grants g WHERE g.flow_id=f.id AND g.client_id=f.client_id AND g.user_id=%s)
                         OR EXISTS(SELECT 1 FROM cadu_reports_site_grants g WHERE g.site_id=f.site_id AND g.client_id=f.client_id AND g.user_id=%s))''',(match[1],client_id,selected['user_id'],selected['user_id']))
                    allowed=bool(cursor.fetchone())
            if not allowed: abort(403, description='Este acesso está limitado aos recursos compartilhados.')
    return selected


def inventory(client_id):
    # Called only by an explicit Workspace integration; Reports core does not depend on it.
    if reports_only():
        return []
    from ..cadu_family import context
    return context.inventory(client_id)


def can_read_all(client_id,user_id=None):
    """Cross-product readers must independently check Reports permissions."""
    from flask import has_request_context
    if user_id is None and has_request_context(): user_id=session.get('user_id')
    if not user_id:return False
    with get_db().cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.cadu_reports_client_memberships') IS NOT NULL AS ready")
        if not cursor.fetchone()['ready']:return False
        cursor.execute('''SELECT 1 FROM cadu_reports_client_memberships m
            JOIN tbl_contato_cliente u ON u.id_contato_cliente=m.user_id AND u.status=TRUE
            JOIN tbl_cliente c ON c.id_cliente=m.client_id AND c.status=TRUE
            WHERE m.client_id=%s AND m.user_id=%s AND m.revoked_at IS NULL AND m.access_scope='all' ''',(client_id,user_id))
        return bool(cursor.fetchone())


def register(bp):
    def admin_scope(payload=None):
        from .reports_v1 import _selection, _write_guard
        selected = _selection(payload)
        if selected['role'] != 'admin' or selected['access_scope'] != 'all':
            abort(403, description='A gestão requer administrador desta conta Reports.')
        if request.method != 'GET':
            _write_guard(selected)
        return selected

    @bp.get('/api/v2/reports/customers')
    @login_required_api
    def reports_customers_list():
        from .reports_v1 import _selection, _rows
        selected = _selection()
        return jsonify(customers=_rows('SELECT id,name,slug,status FROM cadu_reports_customers WHERE client_id=%s ORDER BY name', (selected['client_id'],)))

    @bp.post('/api/v2/reports/customers')
    @login_required_api
    def reports_customer_create():
        from .reports_v1 import _required_text, _rows
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict): abort(400)
        selected = admin_scope(payload)
        name = _required_text(payload,'name',200)
        slug = re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower()).strip('-')[:160]
        if not slug: abort(400,description='Informe um nome com letras ou números.')
        rows = _rows('''INSERT INTO cadu_reports_customers(client_id,name,slug,created_by) VALUES(%s,%s,%s,%s)
            ON CONFLICT(client_id,slug) DO NOTHING RETURNING id,name,slug,status''', (selected['client_id'],name,slug,session['user_id']))
        if not rows: abort(409,description='Já existe um cliente com esse nome.')
        get_db().commit()
        return jsonify(customer=rows[0]),201

    @bp.patch('/api/v2/reports/customers/<int:customer_id>')
    @login_required_api
    def reports_customer_update(customer_id):
        from .reports_v1 import _required_text,_rows
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict): abort(400)
        selected=admin_scope(payload)
        name=_required_text(payload,'name',200)
        status=payload.get('status','active')
        if status not in ('active','archived'): abort(400)
        rows=_rows('UPDATE cadu_reports_customers SET name=%s,status=%s,updated_at=NOW() WHERE id=%s AND client_id=%s RETURNING id,name,status',(name,status,customer_id,selected['client_id']))
        if not rows: abort(404)
        get_db().commit()
        return jsonify(customer=rows[0])

    @bp.get('/api/v2/reports/access')
    @login_required_api
    def reports_access_list():
        from .reports_v1 import _rows
        selected=admin_scope()
        users=_rows('''SELECT u.id_contato_cliente AS id,u.nome_completo AS name,u.email,
            FALSE AS reports_only,m.role,m.access_scope,m.revoked_at
            FROM tbl_contato_cliente u LEFT JOIN cadu_reports_client_memberships m
                ON m.user_id=u.id_contato_cliente AND m.client_id=%s
            WHERE u.status=TRUE AND (u.pk_id_tbl_cliente=%s OR m.user_id IS NOT NULL)
            ORDER BY lower(u.nome_completo)''',(selected['client_id'],selected['client_id']))
        return jsonify(users=users)

    @bp.post('/api/v2/reports/access')
    @login_required_api
    def reports_access_grant():
        from .reports_v1 import _optional_positive_id,_rows
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict): abort(400)
        selected=admin_scope(payload)
        user_id=_optional_positive_id(payload.get('user_id'),'Usuário')
        role=payload.get('role')
        if role not in ('admin','member','viewer'): abort(400)
        conn=get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT client_id FROM cadu_reports_client_memberships WHERE client_id=%s AND role=\'admin\' AND revoked_at IS NULL FOR UPDATE',(selected['client_id'],))
            cursor.fetchall()
            if user_id==session['user_id'] and role!='admin': abort(400,description='Peça a outro administrador para alterar seu acesso.')
            cursor.execute('SELECT id_contato_cliente FROM tbl_contato_cliente u WHERE id_contato_cliente=%s AND (pk_id_tbl_cliente=%s OR EXISTS(SELECT 1 FROM cadu_reports_client_memberships m WHERE m.user_id=u.id_contato_cliente AND m.client_id=%s)) AND status=TRUE',(user_id,selected['client_id'],selected['client_id']))
            if not cursor.fetchone(): abort(404,description='Usuário não encontrado nesta conta.')
            cursor.execute('''INSERT INTO cadu_reports_client_memberships(client_id,user_id,role,granted_by)
                VALUES(%s,%s,%s,%s) ON CONFLICT(client_id,user_id) DO UPDATE SET role=EXCLUDED.role,
                access_scope='all',granted_by=EXCLUDED.granted_by,revoked_at=NULL''',(selected['client_id'],user_id,role,session['user_id']))
        conn.commit()
        return jsonify(granted=True)

    @bp.post('/api/v2/reports/access/<int:user_id>/revoke')
    @login_required_api
    def reports_access_revoke(user_id):
        from .reports_v1 import _rows
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict): abort(400)
        selected=admin_scope(payload)
        admins=_rows("SELECT user_id FROM cadu_reports_client_memberships WHERE client_id=%s AND role='admin' AND revoked_at IS NULL FOR UPDATE",(selected['client_id'],))
        if user_id==session['user_id'] or (len(admins)==1 and admins[0]['user_id']==user_id): abort(400,description='Mantenha pelo menos um administrador ativo.')
        rows=_rows('UPDATE cadu_reports_client_memberships SET revoked_at=NOW() WHERE client_id=%s AND user_id=%s AND revoked_at IS NULL RETURNING user_id',(selected['client_id'],user_id))
        if not rows: abort(404)
        # Revocation ends all resource grants, including grants created before full access.
        for table in ('cadu_reports_site_grants', 'cadu_reports_flow_grants'):
            _rows(f'DELETE FROM {table} WHERE client_id=%s AND user_id=%s RETURNING user_id',
                  (selected['client_id'], user_id))
        get_db().commit()
        return jsonify(revoked=True)
