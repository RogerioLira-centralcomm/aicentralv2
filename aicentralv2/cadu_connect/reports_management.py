"""Optional Workspace links and explicit, read-only resource sharing."""
import hashlib
import json
from flask import abort,jsonify,request,session
from ..auth import login_required_api
from ..db import get_db
from .reports_v1 import _rows,_selection,_write_guard,_required_text

RESOURCES={'site':('cadu_reports_supertag_sites','site_id'),'flow':('cadu_reports_flow_registry','flow_id'),'campaign':('cadu_reports_campaigns','campaign_id')}


def resource(selected,kind,resource_id):
    if kind not in RESOURCES: abort(404)
    table,column=RESOURCES[kind]
    rows=_rows(f'SELECT id FROM {table} WHERE id::text=%s AND client_id=%s',(str(resource_id),selected['client_id']))
    if not rows: abort(404)
    return column


def workspace_items(selected):
    from .reports_access import inventory
    from ..cadu_family import repository
    items=inventory(selected['client_id'])
    return [i for i in items if str(i.get('status') or '').lower() not in ('arquivado','archived','deletado') and (i['kind']=='brand' or (i['kind']=='project' and repository.project_user_can_view(selected['client_id'],i['ref'],selected['user_id'])))]


def register(bp):
    @bp.get('/api/v2/reports/workspace/catalog')
    @login_required_api
    def reports_workspace_catalog():
        return jsonify(items=workspace_items(_selection()))

    @bp.route('/api/v2/reports/workspace/<kind>/<resource_id>',methods=['GET','POST','DELETE'])
    @login_required_api
    def reports_workspace_link(kind,resource_id):
        payload=request.get_json(silent=True) if request.method!='GET' else None
        if request.method!='GET' and not isinstance(payload,dict): abort(400)
        selected=_selection(payload)
        column=resource(selected,kind,resource_id)
        items=workspace_items(selected)
        visible={i['ref']:i for i in items if i['kind']=='project'}
        if request.method=='GET':
            links=_rows(f'SELECT project_ref FROM cadu_reports_workspace_links WHERE {column}::text=%s AND client_id=%s',(resource_id,selected['client_id']))
            return jsonify(links=[visible[l['project_ref']] for l in links if l['project_ref'] in visible])
        _write_guard(selected)
        ref=payload.get('project_ref')
        if ref not in visible: abort(403,description='Projeto não acessível no Workspace.')
        if request.method=='DELETE':
            _rows(f'DELETE FROM cadu_reports_workspace_links WHERE client_id=%s AND {column}::text=%s AND project_ref=%s RETURNING project_ref',(selected['client_id'],resource_id,ref))
        else:
            _rows(f'INSERT INTO cadu_reports_workspace_links(client_id,{column},project_ref,created_by) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING project_ref',(selected['client_id'],resource_id,ref,selected['user_id']))
        get_db().commit()
        return jsonify(saved=True)

    @bp.post('/api/v2/reports/workspace/<kind>/<resource_id>/create-project')
    @login_required_api
    def reports_workspace_create(kind,resource_id):
        from ..cadu_family import context,repository
        from .reports_access import reports_only
        if reports_only(): abort(403,description='Esta conta não tem acesso ao Workspace.')
        payload=request.get_json(silent=True)
        if not isinstance(payload,dict): abort(400)
        selected=_selection(payload);_write_guard(selected)
        column=resource(selected,kind,resource_id)
        workspace=context.resolve(selected['client_id'])
        if workspace['role']=='viewer': abort(403)
        name=_required_text(payload,'name',150)
        key=_required_text(payload,'idempotency_key',120)
        digest=hashlib.sha256(json.dumps([kind,resource_id,name,selected['user_id']],ensure_ascii=True).encode()).hexdigest()
        _rows('INSERT INTO cadu_reports_workspace_operations(client_id,operation_key,payload_hash) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING operation_key',(selected['client_id'],key,digest))
        operation=_rows('SELECT * FROM cadu_reports_workspace_operations WHERE client_id=%s AND operation_key=%s FOR UPDATE',(selected['client_id'],key))[0]
        if operation['payload_hash']!=digest: abort(409,description='Esta operação já foi usada com outros dados.')
        if operation['completed']:
            if not repository.project_user_can_view(selected['client_id'],operation['project_ref'],selected['user_id']): abort(403)
            _rows(f'INSERT INTO cadu_reports_workspace_links(client_id,{column},project_ref,created_by) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING project_ref',
                  (selected['client_id'],resource_id,operation['project_ref'],selected['user_id']))
            get_db().commit()
            return jsonify(project_ref=operation['project_ref'])
        try:
            ref=repository.create_entity(selected['client_id'],selected['user_id'],{'kind':'project','name':name,'idempotency_key':f'reports:{key}'},commit=False)
        except ValueError as error: abort(400,description=str(error))
        _rows(f'INSERT INTO cadu_reports_workspace_links(client_id,{column},project_ref,created_by) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING project_ref',(selected['client_id'],resource_id,ref,selected['user_id']))
        _rows('UPDATE cadu_reports_workspace_operations SET project_ref=%s,completed=TRUE WHERE client_id=%s AND operation_key=%s RETURNING operation_key',(ref,selected['client_id'],key))
        get_db().commit()
        return jsonify(project_ref=ref),201

    @bp.route('/api/v2/reports/customers/<int:customer_id>/brands',methods=['GET','POST','DELETE'])
    @login_required_api
    def reports_customer_brands(customer_id):
        payload=request.get_json(silent=True) if request.method!='GET' else None
        if request.method!='GET' and not isinstance(payload,dict): abort(400)
        selected=_selection(payload)
        if not _rows('SELECT id FROM cadu_reports_customers WHERE id=%s AND client_id=%s',(customer_id,selected['client_id'])): abort(404)
        brands={i['ref']:i for i in workspace_items(selected) if i['kind']=='brand'}
        if request.method=='GET':
            links=_rows('SELECT brand_ref FROM cadu_reports_customer_workspace_brand_links WHERE customer_id=%s AND client_id=%s',(customer_id,selected['client_id']))
            return jsonify(brands=[brands[l['brand_ref']] for l in links if l['brand_ref'] in brands])
        _write_guard(selected)
        ref=payload.get('brand_ref')
        if ref not in brands: abort(403)
        if request.method=='POST':
            _rows('INSERT INTO cadu_reports_customer_workspace_brand_links(client_id,customer_id,brand_ref) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING brand_ref',(selected['client_id'],customer_id,ref))
        else:
            _rows('DELETE FROM cadu_reports_customer_workspace_brand_links WHERE client_id=%s AND customer_id=%s AND brand_ref=%s RETURNING brand_ref',(selected['client_id'],customer_id,ref))
        get_db().commit();return jsonify(saved=True)

    @bp.route('/api/v2/reports/<kind>/<resource_id>/grants',methods=['GET','POST','DELETE'])
    @login_required_api
    def reports_resource_grants(kind,resource_id):
        if kind not in ('site','flow'): abort(404)
        payload=request.get_json(silent=True) if request.method!='GET' else None
        if request.method!='GET' and not isinstance(payload,dict): abort(400)
        selected=_selection(payload)
        if selected['role']!='admin': abort(403)
        column=resource(selected,kind,resource_id)
        table=f'cadu_reports_{kind}_grants'
        if request.method=='GET':
            return jsonify(grants=_rows(f'SELECT g.user_id,u.nome_completo AS name,u.email FROM {table} g JOIN tbl_contato_cliente u ON u.id_contato_cliente=g.user_id WHERE g.client_id=%s AND g.{column}::text=%s',(selected['client_id'],resource_id)))
        _write_guard(selected)
        email=_required_text(payload,'email',254)
        users=_rows('SELECT id_contato_cliente AS id FROM tbl_contato_cliente WHERE lower(email)=lower(%s) AND status=TRUE',(email,))
        if len(users)!=1: abort(404,description='Use o e-mail de um usuário ativo da plataforma.')
        user_id=users[0]['id']
        if request.method=='DELETE':
            _rows(f'DELETE FROM {table} WHERE client_id=%s AND {column}::text=%s AND user_id=%s RETURNING user_id',(selected['client_id'],resource_id,user_id))
        else:
            previous=_rows('SELECT revoked_at FROM cadu_reports_client_memberships WHERE client_id=%s AND user_id=%s FOR UPDATE', (selected['client_id'],user_id))
            if previous and previous[0]['revoked_at'] is not None:
                for grant_table in ('cadu_reports_site_grants','cadu_reports_flow_grants'):
                    _rows(f'DELETE FROM {grant_table} WHERE client_id=%s AND user_id=%s RETURNING user_id', (selected['client_id'],user_id))
            _rows("""INSERT INTO cadu_reports_client_memberships(client_id,user_id,role,access_scope,granted_by)
                VALUES(%s,%s,'viewer','shared',%s) ON CONFLICT(client_id,user_id) DO UPDATE
                SET revoked_at=NULL,role=CASE WHEN cadu_reports_client_memberships.revoked_at IS NOT NULL THEN 'viewer' ELSE cadu_reports_client_memberships.role END,
                access_scope=CASE WHEN cadu_reports_client_memberships.revoked_at IS NOT NULL THEN 'shared' ELSE cadu_reports_client_memberships.access_scope END RETURNING user_id""",(selected['client_id'],user_id,selected['user_id']))
            _rows(f'INSERT INTO {table}(client_id,{column},user_id,granted_by) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING user_id',(selected['client_id'],resource_id,user_id,selected['user_id']))
        get_db().commit();return jsonify(saved=True)

    @bp.get('/api/v2/reports/shared/resources')
    @login_required_api
    def reports_shared_resources():
        selected=_selection()
        sites=_rows('''SELECT s.id,s.label,s.allowed_host,s.enabled,s.revoked_at,COUNT(e.id) AS events_30d
            FROM cadu_reports_supertag_sites s JOIN cadu_reports_site_grants g ON g.site_id=s.id AND g.client_id=s.client_id
            LEFT JOIN cadu_reports_supertag_events e ON e.site_id=s.id AND e.expires_at>NOW() AND e.occurred_at>NOW()-INTERVAL '30 days'
            WHERE s.client_id=%s AND g.user_id=%s GROUP BY s.id ORDER BY s.label''',(selected['client_id'],selected['user_id']))
        return jsonify(sites=sites,flows=_rows('''SELECT f.id,f.name,f.status,f.config,f.published_revision
            FROM cadu_reports_flow_registry f WHERE f.client_id=%s AND
            (EXISTS(SELECT 1 FROM cadu_reports_flow_grants g WHERE g.flow_id=f.id AND g.client_id=f.client_id AND g.user_id=%s)
             OR EXISTS(SELECT 1 FROM cadu_reports_site_grants g WHERE g.site_id=f.site_id AND g.client_id=f.client_id AND g.user_id=%s))
            ORDER BY f.name''',(selected['client_id'],selected['user_id'],selected['user_id'])))

    @bp.route('/api/v2/reports/<kind>/<resource_id>/customer',methods=['GET','PATCH'])
    @login_required_api
    def reports_resource_customer(kind,resource_id):
        from .reports_v1 import _customer_id
        if kind not in ('site','campaign','account'):abort(404)
        payload=request.get_json(silent=True) if request.method=='PATCH' else None
        if request.method=='PATCH' and not isinstance(payload,dict):abort(400)
        selected=_selection(payload)
        table={'site':'cadu_reports_supertag_sites','campaign':'cadu_reports_campaigns','account':'cadu_reports_accounts'}[kind]
        found=_rows(f'SELECT id,customer_id FROM {table} WHERE id::text=%s AND client_id=%s FOR UPDATE',(resource_id,selected['client_id']))
        if not found:abort(404)
        if request.method=='GET':return jsonify(customer_id=found[0]['customer_id'])
        _write_guard(selected)
        customer_id=_customer_id(selected,payload.get('customer_id'))
        if kind=='account' and customer_id!=found[0]['customer_id'] and _rows('SELECT id FROM cadu_reports_campaigns WHERE account_id=%s AND client_id=%s LIMIT 1',(resource_id,selected['client_id'])):
            abort(409,description='Esta conta já tem campanhas. Preserve o anunciante para manter a consistência do histórico.')
        if kind=='campaign':
            account=_rows('SELECT a.customer_id FROM cadu_reports_campaigns c JOIN cadu_reports_accounts a ON a.id=c.account_id AND a.client_id=c.client_id WHERE c.id::text=%s AND c.client_id=%s',(resource_id,selected['client_id']))
            if account and account[0]['customer_id']!=customer_id:abort(409,description='O anunciante deve ser o mesmo da conta de mídia.')
        _rows(f'UPDATE {table} SET customer_id=%s WHERE id::text=%s AND client_id=%s RETURNING id',(customer_id,resource_id,selected['client_id']))
        get_db().commit();return jsonify(customer_id=customer_id)
