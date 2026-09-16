"""Pilot surface with explicit availability and a fail-closed context boundary."""
import secrets
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, current_app, jsonify, make_response, redirect, render_template, request, session, stream_with_context
from werkzeug.exceptions import HTTPException
from urllib.parse import urlparse

from ..auth import login_url
from ..product_domains import canonical_workspace_legacy_path, product_url
from . import context, repository
from .catalog import ADMIN_MODULES, LANDINGS, PRODUCTS, PROFILES
from . import product_pages

bp = Blueprint('cadu_family', __name__, url_prefix='/familia')
from ..cadu_workspace.conversations.jobs import worker_command
bp.cli.add_command(worker_command)


def planner_url(path='', **query):
    """Build clean, product-owned Planner URLs for templates and shares."""
    target = product_url('planner', '/' + str(path or '').lstrip('/'))
    values = {key: value for key, value in query.items() if value not in (None, '')}
    return f"{target}?{urlencode(values)}" if values else target


@bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.before_request
def protect():
    planner_host = (urlparse(str(current_app.config.get('PLANNER_URL') or '')).hostname or '').lower()
    request_host = (request.host.split(':', 1)[0] or '').lower()
    planner_surface = request_host == planner_host and (
        request.path.startswith('/familia/planner/')
        or request.path == '/familia/api/context'
        or request.path.startswith('/familia/api/planner/')
    )
    # Planner is a released Cadu product. It must not depend on the broader
    # family rollout flag, otherwise planner.centralcomm.media lands on the
    # CentralX 404 shell instead of its own product experience.
    if not current_app.config.get('CADU_FAMILY_ENABLED') and not planner_surface:
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
                           'cadu_family.conversation_send', 'cadu_family.conversation_preflight',
                           'cadu_family.planner_link_test'}
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


@bp.put('/api/project-brand-links')
def set_project_brand_link():
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    project_ref, brand_ref, linked = data.get('project_ref'), data.get('brand_ref'), data.get('linked')
    if not isinstance(project_ref, str) or not isinstance(brand_ref, str) or not isinstance(linked, bool):
        abort(400, description='Informe projeto, marca e o estado do vínculo.')
    items = {item['ref']: item for item in context.inventory(selected['client_id'])}
    if (items.get(project_ref) or {}).get('kind') != 'project' or (items.get(brand_ref) or {}).get('kind') != 'brand':
        abort(403, description='Projeto ou marca não pertencem ao cliente selecionado.')
    repository.set_project_brand_link(selected['client_id'], context.identity()['id'], project_ref, brand_ref, linked)
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
    try:
        offset = int(request.args.get('offset', '0'))
    except ValueError:
        abort(400, description='Página inválida.')
    if offset < 0 or offset > 100000:
        abort(400, description='Página inválida.')
    query = request.args.get('q', '').strip()
    if len(query) > 150:
        abort(400, description='Use até 150 caracteres na busca.')
    archived = request.args.get('archived', '0')
    if archived not in ('0', '1'):
        abort(400, description='Filtro inválido.')
    records = repository.conversation_history(user, selected['client_id'], limit=21, offset=offset, query=query, archived=archived == '1')
    return jsonify(conversations=records[:20], next_offset=offset + 20 if len(records) > 20 else None,
                   can_manage=bool(current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)
                                   and selected.get('role') in ('admin', 'member')))


@bp.patch('/api/conversations/<conversation_id>')
def conversation_update(conversation_id):
    selected = writable_context()
    user = context.identity()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data or set(data) - {'title', 'archived'}:
        abort(400, description='Informe um título ou estado de arquivamento.')
    title = data.get('title')
    if 'title' in data:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 150 or '\x00' in title:
            abort(400, description='Use um título de 1 a 150 caracteres.')
        title = title.strip()
    if 'archived' in data and not isinstance(data['archived'], bool):
        abort(400, description='Estado de arquivamento inválido.')
    result = repository.update_conversation(user['id'], selected['client_id'], conversation_id, title, data.get('archived'))
    if not result:
        abort(404)
    return jsonify(conversation=result)


@bp.get('/api/studio/copy-ads/formats')
def copy_formats():
    from . import copy_ads
    context.resolve()
    return jsonify(formats=copy_ads.formats())


@bp.get('/api/planner/catalog/<kind>')
def planner_catalog(kind):
    """Read-only catalog for SmartPlanner and future approved chat cards."""
    from ..cadu_planner import catalog
    context.identity()
    context.resolve()
    return jsonify(kind=kind, records=catalog.query(kind, request.args.get('q', ''), request.args.get('limit', 20)))


@bp.get('/api/planner/catalog/<kind>/<item_id>')
def planner_catalog_detail(kind, item_id):
    from ..cadu_planner import catalog
    context.identity()
    context.resolve()
    return jsonify(kind=kind, record=catalog.detail(kind, item_id))


@bp.get('/api/planner/documents')
def planner_documents():
    """Read-only SmartPlanner document index in the selected authorized client."""
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(documents=docs.list_documents(selected['client_id'], user['id']))


@bp.get('/api/planner/documents/<int:document_id>')
def planner_document_preview(document_id):
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    document, preview = docs.document_preview(selected['client_id'], user['id'], document_id)
    return jsonify(document=document, preview=preview)


@bp.get('/api/planner/places')
def planner_places():
    from ..cadu_planner import places
    context.identity()
    context.resolve()
    return jsonify(records=places.catalog(request.args.get('q', '')))


@bp.get('/api/planner/places/<slug>')
def planner_place_detail(slug):
    from ..cadu_planner import places
    context.identity()
    context.resolve()
    return jsonify(record=places.detail(slug))


@bp.get('/api/planner/selections')
def planner_selections():
    from ..cadu_planner import selections
    user, selected = context.identity(), context.resolve()
    return jsonify(selections=selections.list_selected(selected['client_id'], user['id']))


@bp.get('/api/planner/plans')
def planner_plans():
    from ..cadu_planner import plans
    user, selected = context.identity(), context.resolve()
    return jsonify(plans=plans.list_plans(selected['client_id'], user['id']))


@bp.post('/api/planner/plans')
def planner_plan_create():
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.create_plan(selected['client_id'], user['id'], request.get_json(silent=True) or {}, selected)), 201


@bp.get('/api/planner/plans/<plan_id>')
def planner_plan_detail(plan_id):
    from ..cadu_planner import plans
    user, selected = context.identity(), context.resolve()
    return jsonify(plan=plans.get_plan(selected['client_id'], user['id'], plan_id))


@bp.put('/api/planner/plans/<plan_id>')
def planner_plan_update(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.update_briefing(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.put('/api/planner/plans/<plan_id>/allocations')
def planner_plan_allocations(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.save_allocations(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.put('/api/planner/plans/<plan_id>/status')
def planner_plan_status(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.update_status(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/items/toggle')
def planner_plan_item_toggle(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plans.toggle_item(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/quote-requests')
def planner_plan_quote_request(plan_id):
    """Freeze the customer plan for commercial review; pricing remains in CRM."""
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.request_quote(selected['client_id'], user['id'], plan_id,
                                             request.get_json(silent=True) or {})), 201


@bp.post('/api/planner/selections/toggle')
def planner_selection_toggle():
    from ..cadu_planner import selections
    selected = writable_context()
    user = context.identity()
    return jsonify(selections.toggle(selected['client_id'], user['id'], request.get_json(silent=True) or {}))


@bp.post('/api/planner/link-tester')
def planner_link_test():
    from ..cadu_planner import link_tester
    context.identity()
    context.resolve()
    return jsonify(result=link_tester.test(request.get_json(silent=True) or {}))


@bp.get('/api/planner/docs')
def planner_docs():
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(documents=docs.list_documents(selected['client_id'], user['id']), templates=docs.templates(selected['client_id']))


@bp.post('/api/planner/docs')
def planner_docs_create():
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.create_document(selected['client_id'], user['id'], request.get_json(silent=True) or {})), 201


@bp.get('/api/planner/docs/<int:doc_id>')
def planner_doc_detail(doc_id):
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(document=docs.get_document(selected['client_id'], user['id'], doc_id))


@bp.put('/api/planner/docs/<int:doc_id>')
def planner_doc_save(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.save_document(selected['client_id'], user['id'], doc_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/docs/<int:doc_id>/duplicate')
def planner_doc_duplicate(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.duplicate_document(selected['client_id'], user['id'], doc_id)), 201


@bp.post('/api/planner/docs/<int:doc_id>/share')
def planner_doc_share(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    data = request.get_json(silent=True) or {}
    return jsonify(document=docs.share_document(selected['client_id'], user['id'], doc_id, data.get('enabled', True)))


@bp.get('/planner/docs/public/<token>')
def planner_doc_public(token):
    from ..cadu_planner import docs
    # Documents originate in a legacy HTML editor. The sanitizer removes active
    # content and this sandbox is a second boundary for every public share.
    response = make_response(render_template('cadu_planner/public_doc.html', document=docs.public_document(token)))
    response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; font-src https: data:"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.get('/planner/audiencias/<int:audience_id>')
def planner_audience_detail(audience_id):
    """Customer-facing decision page; the catalog modal remains a quick preview."""
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    from ..cadu_planner import catalog
    user = context.identity()
    selected = context.resolve()
    audience = catalog.detail('audiencias', audience_id)
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    return render_template('cadu_planner/family/audience_detail_page.html',
        product='planner', spec=PRODUCTS['planner'], module='audiencias', title=audience['name'],
        products=PRODUCTS, landing=LANDINGS['planner'], user=user, selected=selected,
        clients=context.authorized_clients(), entities=[], records=[],
        audience=audience, profile=PROFILES['planner'], csrf=token, legacy_url=None, planner_view='audience-detail',
        login_url=login_url(), product_url=product_url, planner_url=planner_url)


@bp.get('/planner/planos/<plan_id>')
def planner_plan_media_desk(plan_id):
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    from ..cadu_planner import plans
    user = context.identity()
    selected = context.resolve()
    plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    return render_template('cadu_planner/family/plan_detail_page.html',
        product='planner', spec=PRODUCTS['planner'], module='planos', title=plan['title'],
        products=PRODUCTS, landing=LANDINGS['planner'], user=user, selected=selected,
        clients=context.authorized_clients(), entities=[], records=[],
        plan=plan, profile=PROFILES['planner'], csrf=token, planner_view='plan-detail',
        legacy_url=None,
        login_url=login_url(), product_url=product_url, planner_url=planner_url)


@bp.get('/planner/<kind>/<int:item_id>')
def planner_catalog_detail_page(kind, item_id):
    if kind not in {'canais', 'formatos', 'interativos'}:
        abort(404)
    if not session.get('user_id'):
        return redirect(login_url(request.full_path))
    from ..cadu_planner import catalog
    user = context.identity()
    selected = context.resolve()
    record = catalog.detail(kind, item_id)
    labels = {'canais': 'Canal', 'formatos': 'Formato', 'interativos': 'Formato interativo'}
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    return render_template('cadu_planner/family/catalog_detail_page.html',
        product='planner', spec=PRODUCTS['planner'], module=kind, title=record['name'],
        products=PRODUCTS, landing=LANDINGS['planner'], user=user, selected=selected,
        clients=context.authorized_clients(), entities=[], records=[],
        record=record, kind_label=labels[kind], profile=PROFILES['planner'], csrf=token, planner_view='catalog-detail',
        legacy_url=None, login_url=login_url(), product_url=product_url, planner_url=planner_url)


@bp.post('/api/planner/docs/<int:doc_id>/export')
def planner_doc_export(doc_id):
    from io import BytesIO
    from flask import send_file
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    document = docs.get_document(selected['client_id'], user['id'], doc_id)
    return send_file(BytesIO(docs.export_pdf(document)), mimetype='application/pdf', as_attachment=True,
                     download_name='documento-%s.pdf' % doc_id)


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
    if run.get('queued'):
        return jsonify(accepted=True, run_id=run['run_id'], conversation_id=run['conversation_id']), 202
    if run.get('recovered'):
        response = jsonify(run)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return Response(stream_with_context(chat.stream(run)), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store'})


@bp.get('/api/conversations/runs/<uuid:run_id>')
def conversation_run_state(run_id):
    from ..cadu_workspace.conversations import recovery
    user = context.identity()
    selected = context.resolve()
    result = recovery.state(str(run_id), user, selected['client_id'])
    if result is None:
        abort(404)
    result = {**result, 'replay': bool(current_app.config.get('CADU_CHAT_WORKER_ENABLED', False)
        and repository.rows('SELECT run_id FROM cadu_family_chat_jobs WHERE run_id = %s', (str(run_id),)))}
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/api/conversations/runs/<uuid:run_id>/events')
def conversation_run_events(run_id):
    from ..cadu_workspace.conversations import recovery, jobs
    user = context.identity()
    selected = context.resolve()
    result = recovery.state(str(run_id), user, selected['client_id'])
    if result is None:
        abort(404)
    if not current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
        abort(503, description='Retomada de eventos ainda não habilitada.')
    try:
        after = int(request.args.get('after', '0'))
        if after < 0 or after > 9223372036854775807:
            raise ValueError()
    except ValueError:
        abort(400)
    return jsonify(**jobs.page(str(run_id), after), status=result['status'])


@bp.get('/api/conversations/capabilities')
def conversation_capabilities():
    from ..cadu_workspace.conversations.attachments import ACCEPT, MAX_BYTES
    context.identity()
    selected = context.resolve()
    enabled = bool(current_app.config.get('CADU_FAMILY_CHAT_ENABLED', False)
                   and current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)
                   and selected['role'] in ('admin', 'member'))
    return jsonify(send=enabled, attachments=enabled, replay=bool(current_app.config.get('CADU_CHAT_WORKER_ENABLED', False)), max_files=3, max_bytes=MAX_BYTES,
                   accept=ACCEPT, external_tools=False)


@bp.post('/api/conversations/preflight')
def conversation_preflight():
    from ..cadu_workspace.conversations.guardrails import validate_message, require_available_intent
    writable_context()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    message = validate_message(data.get('message'))
    return jsonify(intent=require_available_intent(message))


@bp.post('/api/conversations/uploads')
def conversation_upload():
    from ..cadu_workspace.conversations import attachments
    selected = writable_context()
    user = context.identity()
    if not current_app.config.get('CADU_FAMILY_CHAT_ENABLED', False):
        abort(503, description='Anexos ainda não foram habilitados nesta instalação.')
    # Bound multipart parsing as well as the individual file read.
    request.max_content_length = attachments.MAX_BYTES + 65536
    files = request.files.getlist('file')
    if len(files) != 1 or len(request.files) != 1:
        abort(400, description='Envie um arquivo de cada vez.')
    return jsonify(file=attachments.upload(files[0], user, selected)), 201


@bp.get('/api/conversations/modes')
def conversation_modes():
    from .chat import modes
    user = context.identity()
    context.resolve()
    return jsonify(modes=modes(user['id']))


@bp.post('/api/conversations/modes/active')
def conversation_mode_active():
    from .chat import set_active_mode
    writable_context()
    data = request.get_json(silent=True) or {}
    return jsonify(modes=set_active_mode(context.identity()['id'], data.get('mode')))


@bp.put('/api/conversations/modes/<slug>')
def conversation_mode_update(slug):
    from .chat import update_mode_prompt
    writable_context()
    data = request.get_json(silent=True) or {}
    if set(data) != {'prompt'}:
        abort(400, description='Informe somente as instruções do modo.')
    return jsonify(modes=update_mode_prompt(context.identity()['id'], slug, data['prompt']))


@bp.delete('/api/conversations/modes/<slug>')
def conversation_mode_reset(slug):
    from .chat import reset_mode_prompt
    writable_context()
    return jsonify(modes=reset_mode_prompt(context.identity()['id'], slug))


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
    if current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
        from ..cadu_workspace.conversations.jobs import cancel_pending
        if cancel_pending(str(run_id)):
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
    return jsonify(messages=result, context=repository.conversation_context(user, selected['client_id'], conversation_id))


@bp.get('/workspace/marcas/sistema')
def workspace_brand_system():
    """Keep shared links alive without maintaining a second brand interface."""
    brand_id = (request.args.get('creative_client_id') or request.args.get('brand_id')
                or request.args.get('crm_client_id') or request.args.get('client_id'))
    target = product_url('workspace', canonical_workspace_legacy_path('marcas/sistema', brand_id))
    if request.query_string:
        target = f"{target}?{request.query_string.decode('utf-8')}"
    return redirect(target, code=302)


@bp.get('/<product>/')
@bp.get('/<product>/<module>')
def page(product, module=None):
    if product not in PRODUCTS:
        abort(404)
    if product == 'workspace':
        target = product_url('workspace', canonical_workspace_legacy_path(module or ''))
        if request.query_string:
            target = f"{target}?{request.query_string.decode('utf-8')}"
        return redirect(target, code=302)
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
        # Planner no longer works with a selectable project/brand context.
        # Avoid loading those legacy records on every Planner request.
        if product != 'planner':
            entities = context.inventory(selected['client_id'])
        if product == 'workspace' and module in ADMIN_MODULES:
            context.require_admin()
        records = product_pages.load_records(product, module, user, selected, request.args.get('q', ''))
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    # PHP currently knows the actor's organization, not an agency's selected client.
    # Never hand off to the wrong tenant while the adapter is pending.
    legacy_url = None
    if user and legacy and selected['client_id'] == user['organization_id']:
        legacy_url = product_url('auth', '/auth/sso/to-cadu') + '?' + urlencode({'next': product_url('cadu', legacy)})
    template = product_pages.page_template(product)
    return render_template(template, product=product, spec=spec, module=module,
        title=title, products=PRODUCTS, landing=LANDINGS[product], user=user, selected=selected, clients=clients,
        entities=entities, records=records, profile=PROFILES.get(product), csrf=token,
        legacy_url=legacy_url, login_url=login_url(), product_url=product_url, planner_url=planner_url,
        planner_view='page')
