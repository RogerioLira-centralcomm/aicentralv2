"""Full-page reference captures that give the interaction heatmap a real picture to sit on.

One capture per client, canonical page and device class (mobile, tablet, desktop), because the layouts differ. Captures
are taken only when a person asks (they cost provider credits), never automatically, and are served through an
authenticated route; the files are private.

Storage sits behind ``CaptureStore``. Today it is the server's disk (like the flow previews); moving to an external
service later means adding another implementation and pointing ``get_store`` at it, nothing else changes.
"""
import fcntl
import hashlib
import io
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlencode, urlparse

import requests
from flask import abort, current_app, jsonify, request, send_file
from PIL import Image

from ..auth import login_required_api
from . import reports_ai
from .reports_flow import _safe_path
from .reports_page_identity import canonical_page
from .reports_v1 import _rows, _selection, _write_guard

DEVICES = {'mobile': (390, 844), 'tablet': (820, 1180), 'desktop': (1440, 900)}
MAX_DOWNLOAD_BYTES = 12_000_000
MAX_SOURCE_PIXELS = 60_000_000
OUTPUT_WIDTH = 720
OUTPUT_MAX_HEIGHT = 16000          # WebP's hard limit is 16383
CAPTURING_STALE_SECONDS = 240
REGENERATE_AFTER_SECONDS = 30
RETENTION_DAYS = 120

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='reports-page-capture')
_slots = BoundedSemaphore(2)


# ------------------------------------------------------------------------------------------------ storage

class CaptureStore:
    """What the rest of the module needs from storage. Implement this to move captures to another service."""

    def read_state(self, key):
        raise NotImplementedError

    def write_state(self, key, state):
        raise NotImplementedError

    def save_image(self, key, data):
        raise NotImplementedError

    def image_file(self, key):
        """Path (or file-like) for send_file, or None when there is no image."""
        raise NotImplementedError

    def try_lock(self, key):
        """Cross-process lock for one capture. Returns a handle with release(), or None if already held."""
        raise NotImplementedError

    def prune(self, max_age_days):
        raise NotImplementedError


class _FileLock:
    def __init__(self, handle):
        self.handle = handle

    def release(self):
        try:
            self.handle.close()
        except OSError:
            pass


class FilesystemCaptureStore(CaptureStore):
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def read_state(self, key):
        try:
            return json.loads((self.root / f'{key}.json').read_text())
        except (OSError, ValueError):
            return {'status': 'missing'}

    def write_state(self, key, state):
        temporary = self.root / f'{key}.json.tmp'
        temporary.write_text(json.dumps(state))
        temporary.replace(self.root / f'{key}.json')

    def save_image(self, key, data):
        temporary = self.root / f'{key}.webp.tmp'
        temporary.write_bytes(data)
        temporary.replace(self.root / f'{key}.webp')

    def image_file(self, key):
        path = self.root / f'{key}.webp'
        try:
            return path if path.stat().st_size > 0 else None
        except OSError:
            return None

    def try_lock(self, key):
        handle = open(self.root / f'{key}.lock', 'a')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        return _FileLock(handle)

    def prune(self, max_age_days):
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for path in self.root.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed


def get_store():
    root = current_app.config.get('REPORTS_PAGE_CAPTURE_DIR') or Path(current_app.instance_path) / 'reports-page-captures'
    return FilesystemCaptureStore(root)


# --------------------------------------------------------------------------------------------- capture logic

def capture_key(client_id, host, path, device):
    host, path = canonical_page(host, path)
    return hashlib.sha256(f'v1:{client_id}:{host}:{path}:{device}'.encode()).hexdigest()


def current_state(store, key):
    state = store.read_state(key)
    if state.get('status') == 'capturing' and time.time() - state.get('updated', 0) > CAPTURING_STALE_SECONDS:
        state = {**state, 'status': 'missing'}
    if state.get('status') == 'ready' and store.image_file(key) is None:
        state = {**state, 'status': 'missing'}
    return state


def process_image(content, device):
    """Validate, bound and re-encode a downloaded screenshot as WebP."""
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width < 1 or image.height < 1 or image.width * image.height > MAX_SOURCE_PIXELS:
                raise ValueError('Dimensões inválidas.')
            source = image.convert('RGB')
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError('Imagem inválida.') from error
    source.thumbnail((OUTPUT_WIDTH, OUTPUT_MAX_HEIGHT))
    output = io.BytesIO()
    source.save(output, format='WEBP', quality=80)
    return output.getvalue(), source.width, source.height


def _download(image_url):
    from .reports_link_tester import _public_host, _url
    parsed = _url(image_url or '')
    if parsed.scheme != 'https':
        raise ValueError('Captura inválida.')
    _public_host(parsed)
    with requests.get(parsed.geturl(), timeout=(5, 25), stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError('Captura indisponível.')
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > MAX_DOWNLOAD_BYTES:
                raise ValueError('Captura excedeu o limite.')
    return bytes(content)


# The capture opens the page as a visitor from Brazil with a Portuguese browser, so sites that pick the language from
# the visitor's country or Accept-Language show the same version the client's audience sees (not the English one).
CAPTURE_LOCATION = {'country': 'BR', 'languages': ['pt-BR', 'pt']}

def _run_capture(app, store, key, url, allowed_host, device, lock, actor=None):
    previous = current_state(store, key)
    try:
        with app.app_context():
            from ..crm_v3_web_scout import _firecrawl_scrape
            from .reports_flow_monitor import _check_page
            parsed = urlparse(url)
            checked = _check_page({'host': parsed.hostname, 'path': parsed.path}, allowed_host)
            if checked['status'] != 'online':
                raise ValueError('Página indisponível para captura.')
            width, height = DEVICES[device]
            data = reports_ai.firecrawl_scrape('page_capture', checked['checked_url'], call=_firecrawl_scrape, actor=actor, formats=[{'type': 'screenshot', 'fullPage': True, 'viewport': {'width': width, 'height': height}}],
                                     timeout_s=60, max_age_ms=0, location=CAPTURE_LOCATION)
            image_url = data.get('screenshot')
            if isinstance(image_url, dict):
                image_url = image_url.get('url') or image_url.get('imageUrl')
            encoded, out_width, out_height = process_image(_download(image_url), device)
            store.save_image(key, encoded)
            store.write_state(key, {'status': 'ready', 'updated': time.time(), 'captured_at': time.time(), 'device': device,
                                    'width': out_width, 'height': out_height})
    except Exception:
        app.logger.warning('Captura de página falhou: %s', url, exc_info=True)
        store.write_state(key, {'status': 'failed', 'updated': time.time(), 'captured_at': previous.get('captured_at'), 'device': device,
                                'width': previous.get('width'), 'height': previous.get('height'),
                                'message': 'Não foi possível capturar a página. Tente de novo em instantes.'})
    finally:
        lock.release()
        _slots.release()


def capture_cost_tokens(client_id):
    """Cadu tokens one capture (one Firecrawl scrape) costs this client, or None when it cannot be priced.

    Shown next to the capture button; a client without a token price (or any pricing failure) must never break the screen.
    """
    try:
        from ..cadu_credit_connector import CaduCreditConnector
        return int(CaduCreditConnector().estimate_firecrawl_tokens('scrape', client_id=int(client_id), pages=1)) or None
    except Exception:
        current_app.logger.info('Custo da captura indisponível para o cliente %s', client_id, exc_info=True)
        return None


def ensure_balance(actor):
    """Refuse up front (409) when the client cannot pay for one capture, instead of failing a minute later in the background.

    Any other pricing problem is left to the capture itself, exactly as before.
    """
    from ..cadu_credit_connector import CaduCreditConnector
    from ..cadu_tool_billing import InsufficientToolCredits
    try:
        CaduCreditConnector().authorize_firecrawl(actor, 'scrape', pages=1)
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc) or 'Saldo de tokens insuficiente para capturar.')
    except Exception:
        current_app.logger.info('Verificação de saldo da captura indisponível', exc_info=True)


def schedule(store, key, url, allowed_host, device, actor=None):
    """Start a capture in the background. Returns 'started', 'busy' (already running or too soon) or 'full'."""
    if not _slots.acquire(blocking=False):
        return 'full'
    lock = store.try_lock(key)
    if lock is None:
        _slots.release()
        return 'busy'
    try:
        state = current_state(store, key)
        if state['status'] == 'capturing' or time.time() - state.get('updated', 0) < REGENERATE_AFTER_SECONDS:
            lock.release()
            _slots.release()
            return 'busy'
        store.prune(RETENTION_DAYS)
        store.write_state(key, {**state, 'status': 'capturing', 'updated': time.time(), 'device': device})
        _pool.submit(_run_capture, current_app._get_current_object(), store, key, url, allowed_host, device, lock, actor)
        return 'started'
    except Exception:
        lock.release()
        _slots.release()
        raise


# ----------------------------------------------------------------------------------------------------- routes

def _params(source):
    """site_id, path and device from the query string (GET) or the JSON body (POST), validated."""
    try:
        site_id = str(uuid.UUID(str(source.get('site_id', ''))))
    except ValueError:
        abort(400, description='Informe site_id.')
    raw_path = str(source.get('path', ''))
    if not raw_path.startswith('/') or len(raw_path) > 500 or any(char.isspace() for char in raw_path):
        abort(400, description='Informe o caminho da página começando por /.')
    device = source.get('device')
    if device not in DEVICES:
        abort(400, description='Escolha celular, tablet ou computador.')
    return site_id, raw_path.split('?')[0].split('#')[0], device


def _target(selected, site_id, raw_path, device):
    sites = _rows('SELECT id,allowed_host FROM cadu_reports_supertag_sites WHERE id=%s AND client_id=%s AND revoked_at IS NULL', (site_id, selected['client_id']))
    if not sites:
        abort(404)
    host = sites[0]['allowed_host']
    safe = _safe_path(raw_path)
    return host, safe, f'https://{host}{safe}', capture_key(selected['client_id'], host, safe, device)


def _describe(store, key, site_id, raw_path, device, client_id, available):
    state = current_state(store, key)
    image = None
    if state['status'] in ('ready', 'failed') and store.image_file(key) is not None:
        image = '/connect/api/v2/reports/pages/capture/image?' + urlencode(
            {'client_id': client_id, 'site_id': site_id, 'path': raw_path, 'device': device, 'v': int(state.get('captured_at') or 0)})
    return {'status': state['status'], 'device': device, 'captured_at': state.get('captured_at'), 'width': state.get('width'),
            'height': state.get('height'), 'message': state.get('message'), 'image_url': image, 'available': available}


def register(bp):
    @bp.get('/api/v2/reports/pages/capture')
    @login_required_api
    def reports_page_capture_state():
        selected = _selection()
        site_id, raw_path, device = _params(request.args)
        _host, safe, _url, key = _target(selected, site_id, raw_path, device)
        from ..services.integration_credentials import resolve_firecrawl_api_key
        return jsonify(_describe(get_store(), key, site_id, safe, device, selected['client_id'], bool(resolve_firecrawl_api_key())))

    @bp.post('/api/v2/reports/pages/capture')
    @login_required_api
    def reports_page_capture_start():
        payload = request.get_json(silent=True)
        payload = payload if isinstance(payload, dict) else {}
        selected = _selection(payload)
        _write_guard(selected)
        site_id, raw_path, device = _params(payload)
        host, safe, url, key = _target(selected, site_id, raw_path, device)
        from ..services.integration_credentials import resolve_firecrawl_api_key
        if not resolve_firecrawl_api_key():
            abort(503, description='A captura de páginas depende da integração Firecrawl, que não está configurada.')
        actor = reports_ai.actor_for(selected)
        ensure_balance(actor)
        store = get_store()
        outcome = schedule(store, key, url, host, device, actor=actor)
        if outcome == 'full':
            abort(429, description='Há capturas em andamento. Tente de novo em instantes.')
        body = _describe(store, key, site_id, safe, device, selected['client_id'], True)
        body['started'] = outcome == 'started'
        return jsonify(body), 202 if outcome == 'started' else 200

    @bp.get('/api/v2/reports/pages/capture/image')
    @login_required_api
    def reports_page_capture_image():
        selected = _selection()
        site_id, raw_path, device = _params(request.args)
        _host, _safe, _url, key = _target(selected, site_id, raw_path, device)
        path = get_store().image_file(key)
        if path is None:
            abort(404)
        response = send_file(path, mimetype='image/webp', conditional=True, max_age=0)
        response.headers['Cache-Control'] = 'private, no-cache'
        return response
