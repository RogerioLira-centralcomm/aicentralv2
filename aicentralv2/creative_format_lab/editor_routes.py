"""Authenticated HTTP boundary for the Trocr workspace."""
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import current_app, jsonify, request, send_file, session

from .studio_auth import studio_or_admin_required_api
from ..creative_media.storage import media_root
from .editor_workspace import Conflict, MAX_FILE, Workspace
from .swap_csrf import trocr_csrf_required

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='trocr-edit')


def workspace():
    client = request.args.get('client_id')
    if not str(client or '').isdigit() or int(client) <= 0:
        raise ValueError('Escolha uma marca.')
    key = hashlib.sha256(f'client:{int(client)}'.encode()).hexdigest()[:32]
    return Workspace(media_root() / 'trocr-editor' / key)


def register_editor_routes(blueprint):
    prefix = '/api/format-lab/swap/editor'
    blueprint.add_url_rule(prefix + '/<collection>', view_func=collection, methods=['GET', 'POST'])
    blueprint.add_url_rule(prefix + '/<collection>/<ident>', view_func=record, methods=['GET', 'POST'])
    blueprint.add_url_rule(prefix + '/assets/<ident>/content', view_func=asset_content)
    blueprint.add_url_rule(prefix + '/jobs/<ident>/retry', view_func=retry_job, methods=['POST'])
    blueprint.add_url_rule(prefix + '/jobs/<ident>/cancel', view_func=cancel_job, methods=['POST'])


def respond(work):
    try:
        return jsonify({'success': True, 'data': work()})
    except Conflict as exc:
        return jsonify({'success': False, 'error': str(exc)}), 409
    except (ValueError, TypeError) as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@studio_or_admin_required_api
@trocr_csrf_required
def collection(collection):
    def action():
        store = workspace()
        if collection == 'assets' and request.method == 'POST':
            file = request.files.get('file')
            if not file:
                raise ValueError('Selecione uma imagem.')
            return store.upload(file.stream.read(MAX_FILE + 1), file.filename)
        if collection in {'documents', 'campaigns'}:
            if request.method == 'GET':
                return store.listing(collection)
            body = request.get_json() or {}
            return store.save(collection, body.get('id') or uuid.uuid4().hex, body, body.get('revision', 0))
        if collection == 'selection' and request.method == 'POST':
            from .editor_selection import suggest
            return suggest(store, request.get_json() or {})
        if collection == 'render' and request.method == 'POST':
            from .editor_layers import render
            body = request.get_json() or {}
            return store.upload(render(store, body.get('base_asset'), body.get('layers') or []), 'Composição.png')
        if collection == 'jobs' and request.method == 'POST':
            job = store.enqueue(request.get_json() or {})
            if job['status'] == 'queued':
                launch(store, job['id'])
            return job
        raise ValueError('Recurso inválido.')
    return respond(action)


def launch(store, ident):
    app = current_app._get_current_object()
    def run():
        with app.app_context():
            from .swap_routes import _http
            def generate(prompt, **kwargs):
                service = _http()[3]()._format_lab()
                provider = service._image_callable({'generate': True, 'image_quality': 'medium'})
                if not callable(provider):
                    raise ValueError('Gerador de imagem indisponível.')
                return provider(prompt, **kwargs)
            store.run(ident, generate)
    _POOL.submit(run)


@studio_or_admin_required_api
@trocr_csrf_required
def record(collection, ident):
    def action():
        store = workspace()
        if collection == 'revisions' and request.method == 'GET':
            return store.revisions(ident)
        if collection not in {'documents', 'campaigns', 'jobs'}:
            raise ValueError('Recurso inválido.')
        if request.method == 'POST':
            body = request.get_json() or {}
            return store.save(collection, ident, body, body.get('revision', 0))
        data = store.get(collection, ident)
        if collection == 'jobs' and data and data['status'] == 'queued':
            launch(store, ident)
        return data
    return respond(action)


@studio_or_admin_required_api
def asset_content(ident):
    try:
        store = workspace()
        store.asset(ident)
        suffix = '-thumb.png' if request.args.get('thumbnail') == '1' else '.png'
        response = send_file(store.root / (ident + suffix), mimetype='image/png', conditional=True)
        response.headers['Cache-Control'] = 'private, max-age=3600'
        return response
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404


@studio_or_admin_required_api
@trocr_csrf_required
def cancel_job(ident):
    return respond(lambda: workspace().cancel(ident))


@studio_or_admin_required_api
@trocr_csrf_required
def retry_job(ident):
    def action():
        store = workspace()
        job = store.retry(ident)
        launch(store, ident)
        return job
    return respond(action)
