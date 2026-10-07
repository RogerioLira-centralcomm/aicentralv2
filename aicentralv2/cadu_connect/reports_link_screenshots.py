"""Desktop and mobile screenshots for the Link Tester through ScreenshotOne signed requests.

The keys live in the integrations vault (``screenshotone``: access key + secret key). Every request is signed with
HMAC-SHA256 of its query string, so a leaked URL cannot be reused for other pages once "require signed requests" is on
in the ScreenshotOne dashboard. Downloads run in worker threads while the analysis runs; files are stored by the caller.
"""
from __future__ import annotations

import hashlib
import hmac
from concurrent.futures import Future, ThreadPoolExecutor
from urllib.parse import urlencode

import requests

API = 'https://api.screenshotone.com/take'
DEVICES = {
    'desktop': (('viewport_width', '1440'), ('viewport_height', '900'), ('device_scale_factor', '1')),
    'mobile': (('viewport_width', '390'), ('viewport_height', '844'), ('device_scale_factor', '2'), ('viewport_mobile', 'true'),
               ('viewport_has_touch', 'true')),
}
MAX_BYTES = 12_000_000
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='link-tester-shot')


def keys():
    """(access_key, secret_key) or None. Needs an app context (vault)."""
    try:
        from ..services.integration_credentials import resolve_screenshotone
        access, secret = resolve_screenshotone()
    except Exception:
        return None
    return (access, secret) if access and secret else None


def signed_url(page_url, device, credentials):
    access, secret = credentials
    # Cookie banners stay visible on purpose: the print documents what a visitor really sees (consent is analysed too).
    params = [('access_key', access), ('url', page_url), ('format', 'webp'), ('image_quality', '80'), ('block_ads', 'false'),
              ('delay', '2'), ('timeout', '40'), ('cache', 'true'), ('cache_ttl', '14400'), *DEVICES[device]]
    query = urlencode(params)
    signature = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return f'{API}?{query}&signature={signature}'


def _download(url):
    with requests.get(url, timeout=(5, 60), stream=True, allow_redirects=False) as response:
        if response.status_code != 200 or 'image' not in response.headers.get('Content-Type', ''):
            raise ValueError(f'ScreenshotOne respondeu {response.status_code}.')
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise ValueError('Captura excedeu o limite.')
    return bytes(content)


def start(page_url, credentials):
    """Start desktop and mobile downloads; returns {device: Future[bytes]} (empty without credentials)."""
    if not credentials:
        return {}
    return {device: _pool.submit(_download, signed_url(page_url, device, credentials)) for device in DEVICES}


def result(future: Future, timeout=30):
    """Downloads start before the analysis, so this usually returns at once; it never holds the response long."""
    try:
        return future.result(timeout=timeout)
    except Exception:
        return None
