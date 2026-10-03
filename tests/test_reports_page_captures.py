import io
import os
import time
import uuid
from unittest import mock

import pytest
from flask import Blueprint, Flask
from PIL import Image

from aicentralv2.cadu_connect import reports_page_captures as captures
from aicentralv2.cadu_connect.reports_page_captures import FilesystemCaptureStore, capture_key, current_state, process_image, schedule

SITE = str(uuid.uuid4())


def png(width, height, color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buffer, format='PNG')
    return buffer.getvalue()


def test_key_is_canonical_per_client_page_and_device():
    base = capture_key(7, 'www.Exemplo.com.br', '/LP/Verao/', 'mobile')
    assert base == capture_key(7, 'exemplo.com.br', '/lp/verao', 'mobile')
    assert base != capture_key(7, 'exemplo.com.br', '/lp/verao', 'desktop')
    assert base != capture_key(8, 'exemplo.com.br', '/lp/verao', 'mobile')
    assert base != capture_key(7, 'exemplo.com.br', '/outra', 'mobile')


def test_images_are_bounded_reencoded_and_oversized_sources_rejected():
    data, width, height = process_image(png(1440, 5000), 'desktop')
    assert width == 720 and height == 2500
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == 'WEBP' and image.size == (720, 2500)
    tall, w, h = process_image(png(400, 40000), 'mobile')
    assert h <= 16000 and w < 400                       # shrunk to fit WebP's height limit
    small, w, h = process_image(png(390, 800), 'mobile')
    assert (w, h) == (390, 800)                           # never upscaled
    with pytest.raises(ValueError):
        process_image(b'not an image', 'mobile')
    with mock.patch.object(captures, 'MAX_SOURCE_PIXELS', 1000), pytest.raises(ValueError):
        process_image(png(100, 100), 'mobile')


def test_filesystem_store_round_trip_lock_and_prune(tmp_path):
    store = FilesystemCaptureStore(tmp_path)
    assert store.read_state('k') == {'status': 'missing'} and store.image_file('k') is None
    store.write_state('k', {'status': 'ready', 'width': 1})
    store.save_image('k', b'data')
    assert store.read_state('k')['width'] == 1 and store.image_file('k').read_bytes() == b'data'
    first = store.try_lock('k')
    assert first is not None and store.try_lock('k') is None
    first.release()
    assert store.try_lock('k') is not None
    old = tmp_path / 'k.webp'
    os.utime(old, (time.time() - 200 * 86400,) * 2)
    assert store.prune(120) == 1 and store.image_file('k') is None and (tmp_path / 'k.json').exists()


def test_a_ready_state_without_its_image_is_reported_missing_and_stale_capturing_expires(tmp_path):
    store = FilesystemCaptureStore(tmp_path)
    store.write_state('a', {'status': 'ready'})
    assert current_state(store, 'a')['status'] == 'missing'
    store.write_state('b', {'status': 'capturing', 'updated': time.time() - 1000})
    assert current_state(store, 'b')['status'] == 'missing'
    store.write_state('c', {'status': 'capturing', 'updated': time.time()})
    assert current_state(store, 'c')['status'] == 'capturing'


# ---- end to end through schedule() with the provider simulated -------------------------------------------------------
@pytest.fixture
def app(tmp_path):
    flask_app = Flask(__name__)
    flask_app.secret_key = 'test'
    flask_app.config['REPORTS_PAGE_CAPTURE_DIR'] = str(tmp_path)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    captures.register(bp)
    flask_app.register_blueprint(bp)
    return flask_app


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]


class Inline:
    """Runs the background capture right away so the test can look at the result."""
    def submit(self, fn, *args):
        fn(*args)


def run_capture(app, store, key='k1', device='desktop', scrape=None, image=None, status='online', host_ok=True):
    scrape = {'screenshot': 'https://cdn.example.test/shot.png'} if scrape is None else scrape
    with app.app_context(), mock.patch.object(captures, '_pool', Inline()), \
         mock.patch('aicentralv2.crm_v3_web_scout._firecrawl_scrape', return_value=scrape) as scraper, \
         mock.patch('aicentralv2.cadu_connect.reports_flow_monitor._check_page', return_value={'status': status, 'checked_url': 'https://exemplo.com.br/lp'}), \
         mock.patch('aicentralv2.cadu_connect.reports_link_tester._public_host', side_effect=None if host_ok else Exception('privado')), \
         mock.patch.object(captures.requests, 'get', return_value=image if image is not None else Response(png(1440, 4000))):
        outcome = schedule(store, key, 'https://exemplo.com.br/lp', 'exemplo.com.br', device)
    return outcome, scraper


def test_a_successful_capture_is_stored_and_asks_the_provider_for_the_full_page_at_the_device_width(app, tmp_path):
    store = FilesystemCaptureStore(tmp_path)
    outcome, scraper = run_capture(app, store, device='mobile')
    assert outcome == 'started'
    state = current_state(store, 'k1')
    assert state['status'] == 'ready' and state['device'] == 'mobile' and state['width'] == 720 and store.image_file('k1') is not None
    options = scraper.call_args.kwargs['formats'][0]
    assert options['fullPage'] is True and options['viewport']['width'] == 390 and scraper.call_args.kwargs['max_age_ms'] == 0
    assert scraper.call_args.kwargs['location'] == {'country': 'BR', 'languages': ['pt-BR', 'pt']}


@pytest.mark.parametrize('kwargs', [
    {'status': 'offline'},
    {'scrape': {'screenshot': 'http://cdn.example.test/shot.png'}},       # not https
    {'scrape': {}},                                                       # no image returned
    {'host_ok': False},                                                   # image host is not public
    {'image': Response(b'x', status=302)},                                # redirects are never followed
    {'image': Response(b'x' * 100)},                                      # not an image
])
def test_failures_never_store_an_image_and_keep_the_previous_one(app, tmp_path, kwargs):
    store = FilesystemCaptureStore(tmp_path)
    store.save_image('k1', b'previous')
    store.write_state('k1', {'status': 'ready', 'updated': time.time() - 100, 'captured_at': 123.0, 'width': 720, 'height': 100})
    outcome, _ = run_capture(app, store, **kwargs)
    state = store.read_state('k1')
    assert outcome == 'started' and state['status'] == 'failed' and state['captured_at'] == 123.0 and 'Não foi possível' in state['message']
    assert store.image_file('k1').read_bytes() == b'previous'


def test_download_size_limit_is_enforced(app, tmp_path):
    store = FilesystemCaptureStore(tmp_path)
    with mock.patch.object(captures, 'MAX_DOWNLOAD_BYTES', 1000):
        run_capture(app, store, image=Response(b'x' * 5000))
    assert store.read_state('k1')['status'] == 'failed'


def test_schedule_is_rate_limited_and_never_runs_two_captures_of_the_same_key(app, tmp_path):
    store = FilesystemCaptureStore(tmp_path)
    assert run_capture(app, store)[0] == 'started'
    assert run_capture(app, store)[0] == 'busy'                      # asked again within 30 s
    store.write_state('k1', {'status': 'ready', 'updated': time.time() - 60})
    store.save_image('k1', b'x')
    assert run_capture(app, store)[0] == 'started'
    held = store.try_lock('k2')
    assert run_capture(app, store, key='k2')[0] == 'busy'
    held.release()


def test_schedule_gives_up_when_every_slot_is_busy(app, tmp_path):
    slots = [captures._slots.acquire(blocking=False) for _ in range(2)]
    try:
        assert run_capture(app, FilesystemCaptureStore(tmp_path))[0] == 'full'
    finally:
        for taken in slots:
            if taken:
                captures._slots.release()


# ---- routes ----------------------------------------------------------------------------------------------------------
def routes(app, role='admin', firecrawl='key', site=True, balance=None):
    def rows(sql, params=()):
        return [{'id': SITE, 'allowed_host': 'exemplo.com.br'}] if site else []
    return mock.patch.object(captures, '_rows', rows), \
        mock.patch.object(captures, 'ensure_balance', side_effect=balance), \
        mock.patch.object(captures, '_selection', return_value={'client_id': 7, 'role': role, 'user_id': 1}), \
        mock.patch('aicentralv2.services.integration_credentials.resolve_firecrawl_api_key', return_value=firecrawl), \
        mock.patch.object(captures, '_write_guard', side_effect=lambda s: (_ for _ in ()).throw(__import__('werkzeug').exceptions.Forbidden()) if s['role'] == 'viewer' else None)


def call(app, method, body=None, query='', **kwargs):
    client = app.test_client()
    with client.session_transaction() as s:
        s['user_id'] = 1
    patches = routes(app, **kwargs)
    for patch in patches:
        patch.start()
    try:
        if method == 'GET':
            return client.get('/connect/api/v2/reports/pages/capture' + query)
        return client.post('/connect/api/v2/reports/pages/capture', json=body)
    finally:
        for patch in patches:
            patch.stop()


def test_state_route_reports_missing_then_the_image_url_after_a_capture(app, tmp_path):
    query = f'?site_id={SITE}&path=/LP/Verao/&device=desktop'
    first = call(app, 'GET', query=query).get_json()
    assert first['status'] == 'missing' and first['image_url'] is None and first['available'] is True
    key = capture_key(7, 'exemplo.com.br', '/LP/Verao/', 'desktop')
    store = FilesystemCaptureStore(tmp_path)
    store.write_state(key, {'status': 'ready', 'updated': time.time(), 'captured_at': 1700000000, 'width': 720, 'height': 2500})
    store.save_image(key, b'webp')
    ready = call(app, 'GET', query=query).get_json()
    assert ready['status'] == 'ready' and ready['width'] == 720 and 'capture/image' in ready['image_url'] and 'v=1700000000' in ready['image_url']
    assert call(app, 'GET', query=query, firecrawl='').get_json()['available'] is False


def test_start_route_requires_edit_permission_provider_and_valid_input(app):
    body = {'site_id': SITE, 'path': '/lp', 'device': 'tablet'}
    assert call(app, 'POST', {**body}, role='viewer').status_code == 403
    assert call(app, 'POST', body, firecrawl='').status_code == 503
    assert call(app, 'POST', {**body, 'device': 'tv'}).status_code == 400
    assert call(app, 'POST', {**body, 'path': 'lp'}).status_code == 400
    assert call(app, 'POST', {**body, 'site_id': 'x'}).status_code == 400
    assert call(app, 'POST', body, site=False).status_code == 404


def test_start_route_schedules_and_reports_busy(app):
    body = {'site_id': SITE, 'path': '/lp', 'device': 'desktop'}
    with mock.patch.object(captures, 'schedule', return_value='started'):
        response = call(app, 'POST', body)
    assert response.status_code == 202 and response.get_json()['started'] is True
    with mock.patch.object(captures, 'schedule', return_value='busy'):
        assert call(app, 'POST', body).status_code == 200
    with mock.patch.object(captures, 'schedule', return_value='full'):
        assert call(app, 'POST', body).status_code == 429


def test_start_route_refuses_up_front_when_credits_are_short(app):
    from werkzeug.exceptions import Conflict
    body = {'site_id': SITE, 'path': '/lp', 'device': 'desktop'}
    with mock.patch.object(captures, 'schedule') as scheduled:
        response = call(app, 'POST', body, balance=Conflict('Saldo insuficiente.'))
    assert response.status_code == 409 and not scheduled.called


def test_image_route_is_private_and_404_without_a_capture(app, tmp_path):
    query = f'?site_id={SITE}&path=/lp&device=desktop'
    client = app.test_client()
    assert client.get('/connect/api/v2/reports/pages/capture/image' + query).status_code == 401
    assert call(app, 'GET', query=query).status_code == 200
    key = capture_key(7, 'exemplo.com.br', '/lp', 'desktop')
    path = '/connect/api/v2/reports/pages/capture/image'
    client = app.test_client()
    with client.session_transaction() as s:
        s['user_id'] = 1
    patches = routes(app)
    for patch in patches:
        patch.start()
    try:
        assert client.get(path + query).status_code == 404
        FilesystemCaptureStore(tmp_path).save_image(key, png(10, 10))
        response = client.get(path + query)
        assert response.status_code == 200 and response.mimetype == 'image/webp' and 'private' in response.headers['Cache-Control']
    finally:
        for patch in patches:
            patch.stop()
