"""Confirmation binds an immutable proposal to its actor, tenant and targets."""
import json
from uuid import uuid4

from flask import abort

from . import context, repository


def validate(campaign_id, project_ref, selected):
    matches = repository.rows('''SELECT id_campanha, nome_campanha AS name
                                 FROM cadu_pi_campanha
                                WHERE id_campanha = %s AND id_cliente = %s''',
                             (campaign_id, selected['client_id']))
    project = next((item for item in context.inventory(selected['client_id'])
                    if item['ref'] == project_ref and item['kind'] == 'project'), None)
    if not matches or not project:
        abort(404, description='Relatório ou projeto não encontrado neste cliente.')
    return matches[0], project


def prepare(campaign_id, project_ref, selected):
    user = context.identity()
    campaign, project = validate(campaign_id, project_ref, selected)
    action_id = str(uuid4())
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_family_action_previews
                (id, user_id, organization_id, client_id, action, payload)
                VALUES (%s, %s, %s, %s, 'link_report_project', %s::jsonb)''',
                (action_id, user['id'], user['organization_id'], selected['client_id'],
                 json.dumps({'campaign_id': campaign_id, 'project_ref': project_ref})))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {'id': action_id, 'summary': f'Vincular “{campaign["name"]}” ao projeto “{project["name"]}”.'}


def confirm(action_id, selected):
    user = context.identity()
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT payload, status, expires_at > NOW() AS valid
                             FROM cadu_family_action_previews
                            WHERE id = %s AND user_id = %s AND organization_id = %s
                              AND client_id = %s FOR UPDATE''',
                        (action_id, user['id'], user['organization_id'], selected['client_id']))
            action = cur.fetchone()
            if not action:
                abort(404)
            if action['status'] == 'confirmed':
                conn.rollback()
                return {'success': True, 'already_confirmed': True}
            if not action['valid']:
                abort(409, description='A prévia expirou. Prepare o vínculo novamente.')
            payload = action['payload']
            validate(payload['campaign_id'], payload['project_ref'], selected)
            cur.execute('''INSERT INTO cadu_family_report_projects
                    (campaign_id, client_id, project_ref, updated_by)
                    SELECT id_campanha, id_cliente, %s, %s FROM cadu_pi_campanha
                     WHERE id_campanha = %s AND id_cliente = %s
                    ON CONFLICT (campaign_id) DO UPDATE
                    SET project_ref = EXCLUDED.project_ref, updated_by = EXCLUDED.updated_by,
                        client_id = EXCLUDED.client_id, updated_at = NOW() RETURNING campaign_id''',
                        (payload['project_ref'], user['id'], payload['campaign_id'], selected['client_id']))
            if not cur.fetchone():
                abort(409, description='O relatório mudou. Prepare o vínculo novamente.')
            cur.execute("UPDATE cadu_family_action_previews SET status = 'confirmed', confirmed_at = NOW() WHERE id = %s", (action_id,))
        conn.commit()
        return {'success': True}
    except Exception:
        conn.rollback()
        raise
