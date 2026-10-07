"""Link Tester history inside the tool: Reports runs and the analyses made by the PHP Cadu, side by side.

The PHP analyses (``cadu_link_tests``) are read only. Their ``analise_completa`` JSON is kept as evidence, but its
screenshot URLs carry the ScreenshotOne access key, so they never leave the server: the first time a print is asked
for, the server downloads it once and serves our own copy afterwards.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

LEGACY_PREFIX = 'php-'
KIND_FROM_PHP = {'campanha': 'media', 'completo': 'media', 'agentic': 'agentic'}
PHP_LABELS = {'campanha': 'Análise de campanha (Cadu anterior)', 'completo': 'Análise completa (Cadu anterior)',
              'agentic': 'Site agêntico (Cadu anterior)'}


def _rows(sql, params=()):
    from ..cadu_family import repository
    return repository.rows(sql, params)


def _ready(table):
    try:
        return bool(_rows('SELECT to_regclass(%s) IS NOT NULL AS ready', (f'public.{table}',))[0]['ready'])
    except Exception:
        return False


def _status(score):
    score = int(score or 0)
    return 'Pronto' if score >= 85 else 'Atenção' if score >= 55 else 'Bloqueado'


def _domain(url):
    return (urlparse(str(url or '')).hostname or '').lower().removeprefix('www.')


def history(client_id, *, query='', limit=60, offset=0):
    """Both sources, newest first, with who ran each test. ``query`` filters by URL or domain."""
    like = f"%{query.strip().lower()}%" if query and query.strip() else None
    runs = []
    if _ready('cadu_reports_link_test_runs'):
        runs += _rows(f'''SELECT r.id::text AS id, 'reports' AS source, r.mode, r.original_url, r.final_url, r.score, r.status_label,
                r.public_token, r.created_at, r.media_campaign_id, r.report_workspace_id, c.name AS campaign_name,
                u.nome_completo AS author, (r.result->'evidence'->>'screenshot') IS NOT NULL AS has_screenshot
            FROM cadu_reports_link_test_runs r
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = r.created_by
            LEFT JOIN cadu_reports_campaigns c ON c.id = r.media_campaign_id AND c.client_id = r.client_id
            WHERE r.client_id = %s {"AND LOWER(r.final_url || ' ' || r.original_url) LIKE %s" if like else ''}
            ORDER BY r.created_at DESC LIMIT %s''', (client_id, *([like] if like else []), limit + offset))
    if _ready('cadu_link_tests'):
        legacy = _rows(f'''SELECT t.id, t.tipo_analise, t.url_testada, t.url_final, t.score_total, t.created_at, u.nome_completo AS author
            FROM cadu_link_tests t LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = t.user_id
            WHERE t.client_id = %s {"AND LOWER(COALESCE(t.url_final, t.url_testada)) LIKE %s" if like else ''}
            ORDER BY t.created_at DESC LIMIT %s''', (client_id, *([like] if like else []), limit + offset))
        runs += [{'id': f'{LEGACY_PREFIX}{row["id"]}', 'source': 'cadu_php', 'mode': KIND_FROM_PHP.get(row['tipo_analise'] or 'campanha', 'media'),
                  'php_type': row['tipo_analise'] or 'campanha', 'original_url': row['url_testada'], 'final_url': row['url_final'] or row['url_testada'],
                  'score': row['score_total'], 'status_label': _status(row['score_total']), 'public_token': None, 'created_at': row['created_at'],
                  'media_campaign_id': None, 'report_workspace_id': None, 'campaign_name': None, 'author': row['author'],
                  'has_screenshot': True} for row in legacy]
    runs.sort(key=lambda item: item['created_at'], reverse=True)
    for item in runs:
        item['domain'] = _domain(item['final_url'] or item['original_url'])
    return runs[offset:offset + limit]


def _reports_detail(client_id, run_id):
    rows = _rows('''SELECT r.id::text AS id, r.mode, r.original_url, r.final_url, r.score, r.status_label, r.result, r.public_token,
            r.created_at, r.media_campaign_id, r.report_workspace_id, r.account_id, c.name AS campaign_name, u.nome_completo AS author
        FROM cadu_reports_link_test_runs r
        LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = r.created_by
        LEFT JOIN cadu_reports_campaigns c ON c.id = r.media_campaign_id AND c.client_id = r.client_id
        WHERE r.id = %s AND r.client_id = %s''', (run_id, client_id))
    if not rows:
        return None
    row = rows[0]
    result = row.pop('result') or {}
    return {**row, 'source': 'reports', 'kind': result.get('kind') or row['mode'], 'result': result}


def _strip_provider_urls(value):
    """Drop any URL that carries a provider key (ScreenshotOne access_key) from evidence shown to people."""
    if isinstance(value, dict):
        return {key: _strip_provider_urls(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strip_provider_urls(item) for item in value]
    if isinstance(value, str) and re.search(r'access_key=|api\.screenshotone\.com', value):
        return None
    return value


def legacy_row(client_id, legacy_id):
    rows = _rows('''SELECT t.id, t.uuid::text AS uuid, t.tipo_analise, t.url_testada, t.url_final, t.dominio, t.score_total,
            t.ssl_valido, t.ssl_expira_em, t.ssl_emissor, t.tempo_resposta_ms, t.redirects_count, t.screenshot_url,
            t.analise_completa, t.created_at, u.nome_completo AS author
        FROM cadu_link_tests t LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = t.user_id
        WHERE t.id = %s AND t.client_id = %s''', (legacy_id, client_id))
    return rows[0] if rows else None


def _legacy_detail(client_id, legacy_id):
    row = legacy_row(client_id, legacy_id)
    if not row:
        return None
    data = row['analise_completa'] if isinstance(row['analise_completa'], dict) else {}
    shots = data.get('screenshot') if isinstance(data.get('screenshot'), dict) else {}
    devices = {device: bool((shots.get(device) or {}).get('url')) for device in ('desktop', 'mobile')}
    if not any(devices.values()) and row.get('screenshot_url'):
        devices['desktop'] = True
    base = f'/connect/api/v2/reports/link-tests/{LEGACY_PREFIX}{row["id"]}/screenshot'
    php_type = row['tipo_analise'] or 'campanha'
    return {
        'id': f'{LEGACY_PREFIX}{row["id"]}', 'source': 'cadu_php', 'php_type': php_type, 'kind': KIND_FROM_PHP.get(php_type, 'media'),
        'type_label': PHP_LABELS.get(php_type, 'Cadu anterior'), 'original_url': row['url_testada'], 'final_url': row['url_final'] or row['url_testada'],
        'score': row['score_total'], 'status_label': data.get('readiness_label') or data.get('score_label') or _status(row['score_total']),
        'created_at': row['created_at'], 'author': row['author'], 'public_token': None,
        'screenshots': {device: f'{base}?device={device}' if present else None for device, present in devices.items()},
        'analysis': _strip_provider_urls(data),
    }


def detail(client_id, run_id):
    """One run from either source, or None. Reports ids are UUIDs; PHP ids are ``php-<n>``."""
    value = str(run_id or '')
    if value.startswith(LEGACY_PREFIX):
        number = value.removeprefix(LEGACY_PREFIX)
        return _legacy_detail(client_id, int(number)) if number.isdigit() and _ready('cadu_link_tests') else None
    try:
        return _reports_detail(client_id, str(uuid.UUID(value)))
    except ValueError:
        return None


def domain_runs(client_id, domain, exclude_id=None, limit=12):
    """Other analyses of the same domain (both sources), for the evolution strip of the detail page."""
    if not domain:
        return []
    items = [item for item in history(client_id, query=domain, limit=80) if item['domain'] == domain and item['id'] != exclude_id]
    return [{key: item[key] for key in ('id', 'source', 'mode', 'score', 'status_label', 'created_at', 'author', 'final_url')} for item in items[:limit]]


def legacy_screenshot(client_id, legacy_id, device):
    """Path of our own copy of a PHP print, downloading it once from the stored provider URL. None when unavailable."""
    from flask import current_app
    device = 'mobile' if device == 'mobile' else 'desktop'
    # Ownership first: the cached file is shared by id, so it must never answer for another client.
    row = legacy_row(client_id, legacy_id)
    if not row:
        return None
    target = Path(current_app.instance_path) / 'reports-link-tests' / 'legacy' / f'{int(legacy_id)}-{device}.webp'
    if target.is_file():
        return target
    data = row['analise_completa'] if isinstance(row['analise_completa'], dict) else {}
    shots = data.get('screenshot') if isinstance(data.get('screenshot'), dict) else {}
    url = (shots.get(device) or {}).get('url') or (row.get('screenshot_url') if device == 'desktop' else None)
    if not url or urlparse(url).hostname != 'api.screenshotone.com' or urlparse(url).scheme != 'https':
        return None  # only the provider that made the PHP prints; never an arbitrary stored URL
    try:
        from .reports_link_screenshots import _download
        from .reports_page_captures import process_image
        encoded, _, _ = process_image(_download(url), device)
    except Exception:
        current_app.logger.info('Print antigo do Link Tester indisponível (%s, %s).', legacy_id, device, exc_info=True)
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    return target
