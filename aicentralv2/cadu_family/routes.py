"""Pilot surface with explicit availability and a fail-closed context boundary."""
import secrets
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, session, stream_with_context
from werkzeug.exceptions import HTTPException

from ..auth import login_url
from ..product_domains import product_url
from . import context, repository
from .catalog import ADMIN_MODULES, PRODUCTS, PROFILES

bp = Blueprint('cadu_family', __name__, url_prefix='/familia')


@bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.before_request
def protect():
    if not current_app.config.get('CADU_FAMILY_ENABLED'):
        abort(404)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not session.get('user_id'):
            abort(401)
        token = session.get('family_csrf')
        if not token or not secrets.compare_digest(token, request.headers.get('X-CSRF-Token', '')):
            abort(403, description='Atualize a página e tente novamente.')
        # Fail closed for new mutation routes too. Context changes only the
        # session; Copy Ads validation only reads the catalog.
        read_only_posts = {'cadu_family.set_context', 'cadu_family.copy_validate',
                           'cadu_family.conversation_send'}
        if (not current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)
                and request.endpoint not in read_only_posts):
            abort(403, description='Migração em modo de consulta. Gravações não estão habilitadas.')


@bp.errorhandler(Exception)
def error(exc):
    if isinstance(exc, HTTPException):
        code, message = exc.code, exc.description
    else:
        current_app.logger.exception('Falha no serviço da família Cadu')
        code, message = 503, 'Não foi possível carregar os dados. Tente novamente.'
        try:
            repository.get_db().rollback()
        except Exception:
            pass
    if '/api/' in request.path:
        return jsonify(error=message), code
    return render_template('cadu_family/error.html', message=message), code


@bp.get('/api/context')
def get_context():
    selected = context.resolve()
    entities = context.inventory(selected['client_id'])
    # Revalidate persisted references too, including deleted records and revoked grants.
    saved = session.get('family_context') or {}
    for key, kind in (('project_ref', 'project'), ('brand_ref', 'brand')):
        ref = saved.get(key)
        selected[key] = ref if any(row['ref'] == ref and row['kind'] == kind for row in entities) else None
    return jsonify(context=selected, clients=context.authorized_clients(), entities=entities)


@bp.post('/api/context')
def set_context():
    return jsonify(context=context.select(request.get_json(silent=True) or {}))


def writable_context():
    selected = context.resolve()
    if selected['role'] not in ('admin', 'member'):
        abort(403)
    return selected


@bp.post('/api/actions/link-report-project')
def propose_report_link():
    from .actions import prepare
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    try:
        campaign_id = int(data.get('campaign_id'))
    except (TypeError, ValueError):
        abort(400)
    return jsonify(prepare(campaign_id, data.get('project_ref'), selected)), 201


@bp.post('/api/actions/<uuid:action_id>/confirm')
def confirm_action(action_id):
    from .actions import confirm
    return jsonify(confirm(str(action_id), writable_context()))


def entity_payload():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    if not 2 <= len(name) <= 150 or data.get('kind') not in ('project', 'brand'):
        abort(400, description='Informe um nome de 2 a 150 caracteres e um tipo válido.')
    result = {'name': name, 'kind': data['kind']}
    for key, maximum in (('description', 10000), ('instructions', 20000)):
        if key in data:
            result[key] = str(data[key] or '')[:maximum]
    return result


@bp.post('/api/entities')
def create_entity():
    selected = writable_context()
    try:
        ref = repository.create_entity(selected['client_id'], context.identity()['id'], entity_payload())
    except ValueError as exc:
        abort(409, description=str(exc))
    return jsonify(ref=ref), 201


@bp.patch('/api/entities/<ref>')
def edit_entity(ref):
    selected = writable_context()
    if not any(item['ref'] == ref for item in context.inventory(selected['client_id'])):
        abort(404)
    repository.update_entity(selected['client_id'], ref, entity_payload())
    return jsonify(success=True)


@bp.patch('/api/profile')
def edit_profile():
    user = context.identity()
    data = request.get_json(silent=True) or {}
    name, phone = str(data.get('name') or '').strip(), str(data.get('phone') or '').strip()
    if not 2 <= len(name) <= 150 or len(phone) > 40:
        abort(400, description='Confira o nome e o telefone.')
    repository.profile_update(user['id'], name, phone)
    session['user_name'] = name
    return jsonify(success=True)


@bp.get('/api/conversations')
def conversation_history():
    user = context.identity()
    selected = context.resolve()
    return jsonify(conversations=repository.conversation_history(user, selected['client_id']))


@bp.get('/api/studio/copy-ads/formats')
def copy_formats():
    from . import copy_ads
    context.resolve()
    return jsonify(formats=copy_ads.formats())


@bp.post('/api/studio/copy-ads/validate')
def copy_validate():
    from . import copy_ads
    context.resolve()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    spec = next((row for row in copy_ads.formats() if str(row['id']) == str(data.get('format_id'))), None)
    if spec is None:
        abort(404, description='Formato indisponível. Atualize o catálogo.')
    return jsonify(copy_ads.validate_copy(spec, data.get('values')))


@bp.post('/api/conversations/send')
def conversation_send():
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or data.get('profile') not in PROFILES:
        abort(400, description='Esta solução não utiliza o agente compartilhado.')
    # Enable only after the provider, schema and full client have passed pilot validation.
    if (not current_app.config.get('CADU_FAMILY_CHAT_ENABLED', False)
            or not current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)):
        abort(503, description='O envio integrado está em preparação. Seu histórico foi preservado.')
    from . import chat
    run = chat.prepare(data, selected)
    return Response(stream_with_context(chat.stream(run)), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no'})


@bp.get('/api/conversations/modes')
def conversation_modes():
    from .chat import modes
    user = context.identity()
    context.resolve()
    return jsonify(modes=modes(user['id']))


@bp.post('/api/conversations/runs/<uuid:run_id>/stop')
def conversation_stop(run_id):
    from . import dify
    selected = writable_context()
    user = context.identity()
    runs = repository.rows('''SELECT task_id, status FROM cadu_family_chat_runs
                              WHERE id = %s AND user_id = %s AND client_id = %s''',
                           (str(run_id), user['id'], selected['client_id']))
    if not runs:
        abort(404)
    if runs[0]['status'] != 'running':
        return jsonify(stopped=True)
    if not runs[0]['task_id']:
        abort(409, description='A geração ainda está iniciando. Tente novamente.')
    dify.stop(runs[0]['task_id'], 'user-' + str(user['id']))
    return jsonify(stopped=True)


@bp.get('/api/conversations/<conversation_id>/messages')
def messages(conversation_id):
    user = context.identity()
    selected = context.resolve()
    result = repository.conversation_messages(user['id'], selected['client_id'], conversation_id)
    if result is None:
        abort(404)
    return jsonify(messages=result)


@bp.get('/<product>/')
@bp.get('/<product>/<module>')
def page(product, module=None):
    if product not in PRODUCTS:
        abort(404)
    spec = PRODUCTS[product]
    module = module or next(iter(spec['modules']))
    if module not in spec['modules']:
        abort(404)
    title, legacy = spec['modules'][module]
    user, selected, clients, entities, records = None, None, [], [], []
    if session.get('user_id'):
        user = context.identity()
        selected = context.resolve()
        clients = context.authorized_clients()
        entities = context.inventory(selected['client_id'])
        if product == 'workspace' and module in ADMIN_MODULES:
            context.require_admin()
        if product == 'workspace':
            if module == 'equipe': records = repository.team(user['organization_id'])
            if module == 'planos': records = [repository.plan(user['organization_id'])]
            if module == 'consumo': records = repository.consumption(user['organization_id'])
            if module == 'faturamento': records = repository.invoices(user['organization_id'])
            if module == 'integracoes': records = repository.integrations(user['organization_id'])
        if product == 'planner' and module == 'cotacoes':
            records = repository.quotes(selected['client_id'])
        if product == 'planner' and module in ('audiencias', 'canais', 'formatos', 'interativos'):
            records = repository.catalog(module, request.args.get('q', ''))
        if product == 'connect':
            from ..cadu_connect.repository import campaigns_for_client
            records = campaigns_for_client(selected['client_id'])
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    # PHP currently knows the actor's organization, not an agency's selected client.
    # Never hand off to the wrong tenant while the adapter is pending.
    legacy_url = None
    if user and legacy and selected['client_id'] == user['organization_id']:
        legacy_url = product_url('auth', '/auth/sso/to-cadu') + '?' + urlencode({'next': product_url('cadu', legacy)})
    return render_template('cadu_family/page.html', product=product, spec=spec, module=module,
        title=title, products=PRODUCTS, user=user, selected=selected, clients=clients,
        entities=entities, records=records, profile=PROFILES.get(product), csrf=token,
        legacy_url=legacy_url, login_url=login_url(), product_url=product_url)
