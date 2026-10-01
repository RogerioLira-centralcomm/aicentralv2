"""Team templates: a finished plan reused as the starting point of new flows of the same client."""
import json
import uuid

from flask import abort, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_flow_schema import to_v3
from .reports_v1 import _rows, _selection, _write_guard

MEASURED = {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}
# Campaign-specific facts never travel with a template.
NODE_DROP = ('path', 'host', 'discoveryPageId', 'stepId', 'campaign_id', 'evidence', 'role_source',
             'pageTypeStatus', 'suggestedRole', 'manuallyEdited', 'thumbnail_asset_id', 'isEntry')
DOCUMENT_DROP = ('blueprintGoalConfirmed', 'dismissedSuggestions', 'viewport')


def template_config(config):
    """Strip addresses, owners, deadlines, budget and approvals; keep the plan, rates and briefs."""
    document = {key: value for key, value in config.items() if key not in DOCUMENT_DROP}
    if isinstance(document.get('settings'), dict):
        document['settings'] = {key: value for key, value in document['settings'].items() if key != 'publication_note'}
    nodes = []
    for node in config.get('nodes', []) if isinstance(config.get('nodes'), list) else []:
        if not isinstance(node, dict):
            nodes.append(node)
            continue
        item = {key: value for key, value in node.items() if key not in NODE_DROP}
        if item.get('type') in MEASURED:
            item['status'] = 'planned'
        if isinstance(item.get('spec'), dict):
            item['spec'] = {key: value for key, value in item['spec'].items() if key not in ('owner', 'due_date')} or None
            if not item['spec']:
                del item['spec']
        if item.get('type') == 'source':
            item.pop('forecast', None)
        if isinstance(item.get('media'), dict):
            media = dict(item['media'])
            media['creatives'] = [{**creative, 'status': 'rascunho'} for creative in media.get('creatives', [])]
            media['setup'] = [{**entry, 'done': False} for entry in media.get('setup', [])]
            item['media'] = {key: value for key, value in media.items() if value}
        if item.get('type') == 'note':
            item['checklist'] = [{**entry, 'done': False} for entry in item.get('checklist', [])]
        nodes.append(item)
    document['nodes'] = nodes
    return document


def _templates_ready():
    return _rows("SELECT to_regclass('public.cadu_reports_flow_templates') IS NOT NULL AS ready")[0]['ready']


def register(bp):
    from .reports_flow import _normalize_flow_config

    @bp.get('/api/v2/reports/flow/templates')
    @login_required_api
    def reports_flow_templates():
        selected = _selection()
        if not _templates_ready():
            return jsonify(templates=[], ready=False)
        templates = _rows('''SELECT id,name,description,sector,config,created_by,created_at
            FROM cadu_reports_flow_templates WHERE client_id=%s ORDER BY created_at DESC LIMIT 100''',
            (selected['client_id'],))
        return jsonify(templates=templates, ready=True)

    @bp.post('/api/v2/reports/flow/templates')
    @login_required_api
    def reports_flow_create_template():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _templates_ready():
            abort(503, description='Modelos do time indisponíveis: aplique add_reports_flow_templates_v1.sql.')
        name = ' '.join(str(payload.get('name') or '').split())[:120]
        if not name:
            abort(400, description='Dê um nome ao modelo.')
        description = ' '.join(str(payload.get('description') or '').split())[:500]
        sector = ' '.join(str(payload.get('sector') or '').split())[:40]
        # Addresses are removed before validation: a template never belongs to a site.
        source = to_v3(payload.get('config') if isinstance(payload.get('config'), dict) else {})
        template, _ = _normalize_flow_config(template_config(source), '')
        if not template['nodes']:
            abort(422, description='Um modelo precisa de ao menos um passo.')
        created = _rows('''INSERT INTO cadu_reports_flow_templates
            (id,client_id,name,description,sector,config,created_by) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING id,name,description,sector,config,created_by,created_at''',
            (str(uuid.uuid4()), selected['client_id'], name, description, sector,
             json.dumps(template, allow_nan=False), session['user_id']))[0]
        get_db().commit()
        return jsonify(template=created), 201

    @bp.delete('/api/v2/reports/flow/templates/<template_id>')
    @login_required_api
    def reports_flow_delete_template(template_id):
        selected = _selection()
        _write_guard(selected)
        try:
            template_id = str(uuid.UUID(template_id))
        except ValueError:
            abort(404)
        if not _templates_ready():
            abort(404)
        removed = _rows('DELETE FROM cadu_reports_flow_templates WHERE id=%s AND client_id=%s RETURNING id',
                        (template_id, selected['client_id']))
        if not removed:
            abort(404, description='Modelo não encontrado neste cliente.')
        get_db().commit()
        return jsonify(ok=True)
