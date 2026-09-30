"""Private per-client page captures; bounded background work and cross-process locks."""
import fcntl
import hashlib
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlparse, urlencode

import requests
from PIL import Image
from flask import abort, current_app, jsonify, request, send_file
from ..auth import login_required_api
from .reports_v1 import _selection, _write_guard, _rows
from .reports_flow import _flow_row, _host_allowed, _safe_path

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='reports-preview')
_slots = BoundedSemaphore(2)


def _root():
    root = Path(current_app.config.get('REPORTS_FLOW_PREVIEW_DIR') or Path(current_app.instance_path) / 'reports-flow-previews')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _key(selected, url):
    return hashlib.sha256(f"v2:{selected['client_id']}:{selected.get('site_id','')}:{url}".encode()).hexdigest()


def _state(root, key):
    try:
        state = json.loads((root / f'{key}.json').read_text())
    except (OSError, ValueError):
        state = {'status': 'missing'}
    if state.get('status') == 'capturing' and time.time() - state.get('updated', 0) > 180:
        state['status'] = 'missing'
    if state.get('status') == 'ready':
        image = root / f'{key}.webp'
        try:
            if image.stat().st_size == 0:
                state['status'] = 'missing'
        except OSError:
            state['status'] = 'missing'
    return state


def _write(root, key, state):
    temporary = root / f'{key}.tmp'
    temporary.write_text(json.dumps(state))
    temporary.replace(root / f'{key}.json')


def _capture(app, root, key, url, allowed_host, lock):
    previous = _state(root, key)
    try:
        with app.app_context():
            # Reuse the bounded redirect/public-domain checker before hosted rendering.
            from .reports_flow_monitor import _check_page
            from ..crm_v3_web_scout import _firecrawl_scrape
            from .reports_link_tester import _public_host, _url
            parsed = urlparse(url)
            checked = _check_page({'host': parsed.hostname, 'path': parsed.path}, allowed_host)
            if checked['status'] != 'online':
                raise ValueError('Página indisponível para captura.')
            data = _firecrawl_scrape(checked['checked_url'], formats=[{'type':'screenshot','fullPage':False,'viewport':{'width':1440,'height':900}}], timeout_s=35, max_age_ms=0)
            image_url = data.get('screenshot')
            if isinstance(image_url, dict):
                image_url = image_url.get('url') or image_url.get('imageUrl')
            parsed_image = _url(image_url or '')
            if parsed_image.scheme != 'https':
                raise ValueError('Captura inválida.')
            _public_host(parsed_image)
            with requests.get(parsed_image.geturl(), timeout=(5,20), stream=True, allow_redirects=False) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError('Captura indisponível.')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 8_000_000:
                        raise ValueError('Captura excedeu o limite.')
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 16_000_000:
                    raise ValueError('Dimensões inválidas.')
                image.thumbnail((720,450))
                temporary = root / f'{key}.webp.tmp'
                image.convert('RGB').save(temporary, format='WEBP', quality=82)
                temporary.replace(root / f'{key}.webp')
            _write(root,key,{'status':'ready','updated':time.time(),'captured_at':time.time()})
    except Exception:
        _write(root,key,{'status':'failed','updated':time.time(),'captured_at':previous.get('captured_at'),'message':'Não foi possível capturar. Tente regenerar a imagem.'})
    finally:
        lock.close()
        _slots.release()


def _schedule(root, key, url, host, force=False):
    if not _slots.acquire(blocking=False):
        return False
    lock = open(root / f'{key}.lock','a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = _state(root,key)
        if state['status']=='capturing' or (state['status']!='missing' and not force) or (force and time.time()-state.get('updated',0)<30):
            lock.close();_slots.release();return state['status']=='capturing'
        _write(root,key,{**state,'status':'capturing','updated':time.time()})
        _pool.submit(_capture,current_app._get_current_object(),root,key,url,host,lock)
        return True
    except BlockingIOError:
        lock.close();_slots.release()
        return False
    except Exception:
        lock.close();_slots.release();raise


def register(bp):
    def context(flow_id):
        selected = _selection()
        flow = _flow_row(flow_id,selected)
        selected = dict(selected,site_id=flow['site_id'])
        config = (flow['active_config'] if selected.get('access_scope')=='shared' else flow['config']) or {}
        revision = request.args.get('revision')
        if revision:
            if not revision.isdigit(): abort(400)
            versions = _rows('SELECT config FROM cadu_reports_flow_versions WHERE flow_id=%s AND client_id=%s AND revision=%s', (flow_id,selected['client_id'],int(revision)))
            if not versions: abort(404)
            config = versions[0]['config']
        targets = {}
        for node in config.get('nodes',[]):
            if node.get('type')!='page': continue
            host = node.get('host') or flow['allowed_host']
            path = node.get('path') or ''
            if not _host_allowed(host,flow['allowed_host']) or not path.startswith('/') or path.startswith('//') or path.startswith('/configurar-'): continue
            targets[node['id']] = f'https://{host}{_safe_path(path)}'
        return selected,flow,targets

    @bp.route('/api/v2/reports/flow/flows/<flow_id>/previews',methods=['GET','POST'])
    @login_required_api
    def previews(flow_id):
        selected,flow,targets = context(flow_id)
        root = _root()
        available = True
        if request.method=='POST':
            _write_guard(selected)
            from ..services.integration_credentials import resolve_firecrawl_api_key
            available = bool(resolve_firecrawl_api_key())
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload,dict): abort(400)
            node_id = payload.get('node_id')
            if node_id and node_id not in targets: abort(404)
            if available and not flow.get('revoked_at'):
                for id,url in targets.items():
                    if node_id and id!=node_id: continue
                    scheduled = _schedule(root,_key(selected,url),url,flow['allowed_host'],force=bool(node_id))
                    if node_id and not scheduled:
                        abort(429,description='Aguarde as capturas em andamento e tente regenerar novamente em 30 segundos.')
        items = {}
        for id,url in targets.items():
            key = _key(selected,url)
            state = _state(root,key)
            params = {'client_id':selected['client_id'],'v':state.get('captured_at',0)}
            if request.args.get('revision'): params['revision']=request.args['revision']
            items[id] = {**state,'url':f'/connect/api/v2/reports/flow/flows/{flow_id}/previews/{id}/image?{urlencode(params)}' if (root / f'{key}.webp').exists() else None}
            items[id]['canvas_url']=(items[id]['url']+'&size=240') if items[id]['url'] else None
        return jsonify(items=items,available=available)

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/previews/<node_id>/image')
    @login_required_api
    def preview_image(flow_id,node_id):
        selected,_,targets = context(flow_id)
        if node_id not in targets: abort(404)
        path = _root() / f'{_key(selected,targets[node_id])}.webp'
        if not path.exists(): abort(404)
        if request.args.get('size')=='240':
            with Image.open(path) as image:
                image.thumbnail((240,150));buffer=io.BytesIO();image.convert('RGB').save(buffer,format='WEBP',quality=78);buffer.seek(0)
            response=send_file(buffer,mimetype='image/webp',max_age=0)
        else:
            response = send_file(path,mimetype='image/webp',conditional=True,max_age=0)
        response.headers['Cache-Control']='private, no-cache'
        return response
