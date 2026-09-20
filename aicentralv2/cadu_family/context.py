"""Revalidate identity and grants on every request; never trust selected IDs."""
from flask import abort, g, session
from . import repository


def identity():
    if not session.get('user_id'):
        abort(401)
    if not hasattr(g, 'family_actor'):
        g.family_actor = repository.actor(session['user_id'])
    if not g.family_actor or not g.family_actor.get('organization_id'):
        abort(403)
    return g.family_actor


def authorized_clients():
    if not hasattr(g, 'family_clients'):
        g.family_clients = repository.clients(identity())
    return g.family_clients


def resolve(client_id=None):
    user = identity()
    # The active client may be the agency's own tenant or an explicitly
    # authorized client selected in the Workspace session. Never trust the
    # value blindly: it must be present in the access projection below.
    tenant_id = user['organization_id']
    if client_id is None:
        client_id = session.get('cliente_id') or tenant_id
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        abort(400, description='Cliente inválido.')
    client = next((c for c in authorized_clients() if int(c['id']) == client_id), None)
    if client is None:
        abort(403, description='Este login não tem acesso a este cliente.')
    return {'organization_id': user['organization_id'], 'client_id': client_id,
            'client_name': client['name'], 'role': client['role']}


def inventory(client_id):
    context = resolve(client_id)
    items = repository.entities(context['client_id'])
    links = {row['ref']: row['canonical_ref'] for row in repository.entity_links(context['client_id'])}
    known = {item['ref'] for item in items}
    for item in items:
        item['canonical_ref'] = links.get(item['ref'], item['ref'])
        item['needs_review'] = item['source'] != 'ci' and item['ref'] not in links
        if item['canonical_ref'] not in known:
            item['canonical_ref'] = item['ref']
            item['needs_review'] = True
        item['related_refs'] = []
        item['related_names'] = []
    by_ref = {item['ref']: item for item in items}
    for link in repository.project_brand_links(context['client_id']):
        project, brand = by_ref.get(link['project_ref']), by_ref.get(link['brand_ref'])
        # Never expose a stale relationship to an entity the selected client cannot see.
        if project and brand and project['kind'] == 'project' and brand['kind'] == 'brand':
            project['related_refs'].append(brand['ref'])
            project['related_names'].append(brand['name'])
            brand['related_refs'].append(project['ref'])
            brand['related_names'].append(project['name'])
    return items


def select(payload):
    if not isinstance(payload, dict):
        abort(400, description='Contexto inválido.')
    if isinstance(payload.get('client_id'), bool) or isinstance(payload.get('client_id'), (list, dict, float)):
        abort(400, description='Cliente inválido.')
    context = resolve(payload.get('client_id'))
    items = {row['ref']: row for row in inventory(context['client_id'])}
    for field, kind in (('project_ref', 'project'), ('brand_ref', 'brand')):
        ref = payload.get(field) or None
        if ref is not None and not isinstance(ref, str):
            abort(400, description='Referência inválida.')
        if ref and (ref not in items or items[ref]['kind'] != kind):
            abort(403, description='A seleção não pertence ao cliente.')
        context[field] = ref
    # Replace the complete selection: old brand/project IDs cannot leak across clients.
    session['family_context'] = context
    return context


def require_admin():
    user = identity()
    if repository.account_role(user) != 'admin':
        abort(403, description='A administração da conta requer um administrador da organização.')
    return user
