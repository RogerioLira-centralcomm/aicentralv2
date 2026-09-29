"""Client-scoped draft persistence; config remains the active collector snapshot."""
import json

from flask import abort

from .reports_v1 import _rows


def expected_revision(payload):
    value = payload.get('expected_revision')
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        abort(400, description='Informe a revisão do rascunho antes de salvar ou publicar.')
    return value


def lock_flow(flow_id, selected, revision):
    rows = _rows('''SELECT id,name,draft_config,draft_revision,published_revision,status,tag_id
        FROM cadu_reports_flow_registry WHERE id=%s AND organization_id=%s AND client_id=%s
        FOR UPDATE''', (flow_id, selected['organization_id'], selected['client_id']))
    if not rows:
        abort(404, description='Fluxo não encontrado neste cliente.')
    if rows[0]['draft_revision'] != revision:
        abort(409, description='Este fluxo foi alterado em outra aba. Reabra o rascunho antes de continuar.')
    return rows[0]


def save_draft(flow_id, selected, revision, name, config):
    rows = _rows('''UPDATE cadu_reports_flow_registry
        SET name=%s,draft_config=%s::jsonb,draft_revision=draft_revision+1,updated_at=NOW()
        WHERE id=%s AND organization_id=%s AND client_id=%s AND draft_revision=%s
        RETURNING id,flow_code,name,status,draft_config AS config,draft_revision,
            published_revision,tag_id,created_at,updated_at,published_at''',
        (name, json.dumps(config, allow_nan=False), flow_id,
         selected['organization_id'], selected['client_id'], revision))
    if not rows:
        abort(409, description='Este fluxo foi alterado em outra aba. Seu rascunho local foi preservado.')
    return rows[0]


def sync_published_steps(flow, selected):
    """Update URL mappings only at activation, under the registry row lock.

    Each publication gets immutable node mappings; prior IDs and event references survive.
    A Flow owns its own tag, while a Super Tag can fan out to many Flow tags.
    """
    nodes = (flow['draft_config'] or {}).get('nodes', [])
    active_ids = []
    for index, node in enumerate(nodes):
        kind = node.get('type')
        if kind not in {'page','form','event','conversion','whatsapp','error'}:
            continue
        step = _rows("""INSERT INTO cadu_reports_flow_steps
            (organization_id,client_id,tag_id,node_id,flow_revision,name,path_prefix,page_host,
             step_kind,is_entry,position,campaign_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(tag_id,flow_revision,node_id) DO UPDATE
                SET is_active=TRUE,archived_at=NULL
            RETURNING id""",
            (selected['organization_id'],selected['client_id'],flow['tag_id'],node['id'],
             flow['draft_revision'],node.get('title',kind),node['path'],node.get('host'),
             kind,bool(node.get('isEntry')),index,node.get('campaign_id')))[0]
        active_ids.append(step['id'])
    _rows("""UPDATE cadu_reports_flow_steps SET is_active=FALSE,is_entry=FALSE,archived_at=NOW()
        WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
            AND NOT (id=ANY(%s::bigint[])) RETURNING id""",
        (flow['tag_id'],selected['organization_id'],selected['client_id'],active_ids))


def publish_draft(flow_id, selected, revision, actor_id):
    flow = lock_flow(flow_id, selected, revision)
    sync_published_steps(flow, selected)
    # Repeated requests for an unchanged revision do not create duplicate history.
    _rows('''INSERT INTO cadu_reports_flow_versions
        (flow_id,organization_id,client_id,revision,name,config,created_by)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
        ON CONFLICT(flow_id,revision) DO NOTHING RETURNING revision''',
        (flow_id, selected['organization_id'], selected['client_id'], revision,
         flow['name'], json.dumps(flow['draft_config'], allow_nan=False), actor_id))
    return _rows('''UPDATE cadu_reports_flow_registry SET config=draft_config,
        published_revision=draft_revision,status='published',published_at=NOW(),updated_at=NOW()
        WHERE id=%s AND organization_id=%s AND client_id=%s
        RETURNING id,flow_code,name,status,published_revision,draft_revision,published_at''',
        (flow_id, selected['organization_id'], selected['client_id']))[0]


def session_snapshot(flow, session_id):
    """Pin a session to one immutable publication, including concurrent first events."""
    scope = (flow['id'],flow['organization_id'],flow['client_id'])
    current = _rows("""SELECT published_revision FROM cadu_reports_flow_registry
        WHERE id=%s AND organization_id=%s AND client_id=%s AND status='published'
        FOR SHARE""", scope)
    if not current or current[0]['published_revision'] is None:
        abort(409, description='Fluxo sem versão publicada.')
    pinned = _rows("""INSERT INTO cadu_reports_flow_sessions
        (flow_id,organization_id,client_id,session_id,revision) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT(flow_id,session_id) DO UPDATE SET session_id=EXCLUDED.session_id
        RETURNING revision""", (*scope,session_id,current[0]['published_revision']))[0]['revision']
    version = _rows("""SELECT config FROM cadu_reports_flow_versions
        WHERE flow_id=%s AND organization_id=%s AND client_id=%s AND revision=%s""",
        (*scope,pinned))[0]
    return {**flow,'config':version['config'],'published_revision':pinned}


def match_version_step(flow, path, host, kind, event_name=None):
    expected = {'form_submit':'form','custom_event':'event','whatsapp_click':'whatsapp',
                'conversion':'conversion','error_view':'error'}.get(kind)
    nodes = [node for node in (flow.get('config') or {}).get('nodes', [])
             if node.get('path') == path and (not node.get('host') or node['host'] == host)
             and (node.get('type') == expected if expected else
                  node.get('type') in ('page','conversion','error'))
             and (node.get('type') != 'event' or node.get('event_name') == event_name)
             and (node.get('type') != 'conversion' or
                  (kind == 'page_view' and not node.get('event_name')) or
                  (kind == 'conversion' and (not node.get('event_name') or node.get('event_name') == event_name)))]
    if not nodes:
        return None
    # Conversion/error page rules outrank a generic page at the same URL.
    node = sorted(nodes, key=lambda n: (
        n.get('type') == 'page',
        kind == 'conversion' and n.get('type') == 'conversion' and not n.get('event_name')))[0]
    steps = _rows("""SELECT id,campaign_id,step_kind FROM cadu_reports_flow_steps
        WHERE tag_id=%s AND organization_id=%s AND client_id=%s
            AND flow_revision=%s AND node_id=%s""",
        (flow['tag_id'],flow['organization_id'],flow['client_id'],flow['published_revision'],node['id']))
    return steps[0] if steps else {'id':None,'campaign_id':node.get('campaign_id'),'step_kind':node['type']}
