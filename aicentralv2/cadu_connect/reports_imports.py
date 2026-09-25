"""Client-scoped import inbox for platform exports and screenshots."""
import hashlib
import json
import re
import uuid
from collections import Counter
from decimal import Decimal

from flask import abort, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from ..auth import login_required_api
from ..db import get_db
from .report_sources import prepare_image
from .reports_import_parser import MAX_FILE_BYTES, normalized_platform, parse_record, read_export
from .reports_v1 import _rows, _selection, _write_guard

MAX_REQUEST_BYTES = 11 * 1024 * 1024


def _ready():
    return _rows("SELECT to_regclass('public.cadu_reports_import_files') IS NOT NULL AS ready")[0]['ready']


def _bounded_body():
    if request.content_length is not None and request.content_length > MAX_REQUEST_BYTES:
        raise RequestEntityTooLarge('O arquivo excede o limite de upload.')
    body = request.stream.read(MAX_REQUEST_BYTES + 1)
    if len(body) > MAX_REQUEST_BYTES:
        raise RequestEntityTooLarge('O arquivo excede o limite de upload.')
    request._cached_data = body


def _upsert_identity(selected, parsed):
    if not all(parsed.get(key) for key in ('platform', 'external_account_id', 'account_name',
                                           'external_campaign_id', 'campaign_name')):
        return None, None
    if parsed['issues'] and any('ausente ou longo demais' in issue or 'plataforma' in issue
                                for issue in parsed['issues']):
        return None, None
    scope = (selected['organization_id'], selected['client_id'])
    account = _rows('''INSERT INTO cadu_reports_accounts
        (organization_id,client_id,platform,external_id,name,account_kind,currency)
        VALUES (%s,%s,%s,%s,%s,'advertiser',%s)
        ON CONFLICT (organization_id,client_id,platform,external_id)
        DO UPDATE SET updated_at=NOW()
        RETURNING id,account_kind,currency''', (*scope, parsed['platform'], parsed['external_account_id'],
                         parsed['account_name'], parsed['currency'] or None))[0]
    if account['account_kind'] != 'advertiser':
        parsed['issues'].append('ID da conta pertence a uma conta gerente')
        return account['id'], None
    if account['currency'] and parsed['currency'] and account['currency'] != parsed['currency']:
        parsed['issues'].append('moeda difere da conta cadastrada')
        return account['id'], None
    campaign = _rows('''INSERT INTO cadu_reports_campaigns
        (organization_id,client_id,account_id,external_id,name)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (account_id,external_id)
        DO UPDATE SET updated_at=NOW()
        RETURNING id''', (*scope, account['id'], parsed['external_campaign_id'], parsed['campaign_name']))[0]['id']
    return account['id'], campaign


def register(bp):
    @bp.get('/api/v1/reports/imports')
    @login_required_api
    def reports_import_list():
        selected = _selection()
        if not _ready():
            return jsonify(ready=False, imports=[])
        batches = _rows('''SELECT id,original_name,file_kind,status,platform_hint,row_count,applied_count,
            created_at FROM cadu_reports_import_files
            WHERE organization_id=%s AND client_id=%s ORDER BY created_at DESC LIMIT 60''',
            (selected['organization_id'], selected['client_id']))
        return jsonify(ready=True, imports=batches)

    @bp.get('/api/v1/reports/imports/<uuid:import_id>')
    @login_required_api
    def reports_import_detail(import_id):
        selected = _selection()
        scope = (selected['organization_id'], selected['client_id'])
        batch = _rows('''SELECT id,original_name,file_kind,status,platform_hint,row_count,
            applied_count,created_at FROM cadu_reports_import_files
            WHERE id=%s AND organization_id=%s AND client_id=%s''', (str(import_id), *scope))
        if not batch:
            abort(404)
        rows = _rows('''SELECT source_row,sheet_name,parsed,status,reason,account_id,campaign_id,
            metric_date FROM cadu_reports_import_rows
            WHERE import_id=%s AND organization_id=%s AND client_id=%s
            ORDER BY id LIMIT 100''', (str(import_id), *scope))
        return jsonify(import_file=batch[0], rows=rows)

    @bp.post('/api/v1/reports/imports')
    @login_required_api
    def reports_import_upload():
        selected = _selection()
        _write_guard(selected)
        if not _ready():
            abort(503, description='Instale a migração de importações do Reports.')
        _bounded_body()
        uploads = request.files.getlist('file')
        if len(uploads) != 1 or not uploads[0].filename:
            abort(400, description='Envie um arquivo CSV, XLSX ou imagem.')
        upload = uploads[0]
        filename = upload.filename.rsplit('/', 1)[-1].rsplit('\\', 1)[-1][:200]
        lower = filename.lower()
        platform_hint = normalized_platform(request.form.get('platform_hint', ''))
        currency_hint = request.form.get('currency_hint', '').strip().upper()
        date_order = request.form.get('date_order', 'auto')
        if request.form.get('platform_hint') and not platform_hint:
            abort(400, description='Plataforma inválida.')
        if currency_hint and not re.fullmatch(r'[A-Z]{3}', currency_hint):
            abort(400, description='Moeda inválida.')
        if date_order not in ('auto', 'dmy', 'mdy'):
            abort(400, description='Formato de data inválido.')
        try:
            if lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                image = prepare_image(upload)
                kind, raw, sha256, records = 'image', image['image_bytes'], image['sha256'], []
                mime_type = 'image/png'
            elif lower.endswith(('.csv', '.xlsx')):
                raw = upload.stream.read(MAX_FILE_BYTES + 1)
                kind, records = read_export(raw, filename)
                sha256 = hashlib.sha256(raw).hexdigest()
                mime_type = 'text/csv' if kind == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                abort(400, description='Formato não aceito. Use CSV, XLSX, PNG, JPEG ou WebP.')
        except ValueError as exc:
            abort(400, description=str(exc))
        parsed_rows = [(record, parse_record(record, platform_hint=platform_hint,
                        currency_hint=currency_hint, date_order=date_order)) for record in records]
        identities = Counter((item['platform'], item['external_account_id'],
                              item['external_campaign_id'], item['metric_date'])
                             for _, item in parsed_rows if all(item.get(key) for key in
                             ('platform', 'external_account_id', 'external_campaign_id', 'metric_date')))
        scope = (selected['organization_id'], selected['client_id'])
        existing = _rows('''SELECT id FROM cadu_reports_import_files
            WHERE organization_id=%s AND client_id=%s AND sha256=%s''', (*scope, sha256))
        if existing:
            return jsonify(import_id=existing[0]['id'], duplicate=True), 200
        import_id = str(uuid.uuid4())
        conn = get_db()
        try:
            _rows('''INSERT INTO cadu_reports_import_files
                (id,organization_id,client_id,original_name,sha256,mime_type,file_kind,raw_bytes,
                 status,platform_hint,row_count,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (import_id, *scope, filename, sha256, mime_type, kind, raw,
                 'awaiting_extraction' if kind == 'image' else 'received',
                 platform_hint or None, len(records), session['user_id']))
            applied = 0
            for record, parsed in parsed_rows:
                identity = (parsed['platform'], parsed['external_account_id'],
                            parsed['external_campaign_id'], parsed['metric_date'])
                if identities[identity] > 1:
                    parsed['issues'].append('campanha e data repetidas no arquivo; confirme os segmentos')
                account_id, campaign_id = _upsert_identity(selected, parsed)
                status = 'applied' if not parsed['issues'] and campaign_id else 'needs_review'
                row_id = _rows('''INSERT INTO cadu_reports_import_rows
                    (import_id,organization_id,client_id,sheet_name,source_row,raw,parsed,status,
                     reason,account_id,campaign_id,metric_date)
                    VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s) RETURNING id''',
                    (import_id, *scope, record['sheet'], record['row'], json.dumps(record['raw']),
                     json.dumps(parsed), status, '; '.join(parsed['issues']) or None,
                     account_id, campaign_id, parsed['metric_date']))[0]['id']
                if status == 'applied':
                    applied += 1
                    for key, value in parsed['metrics'].items():
                        monetary = key in ('cost', 'conversion_value')
                        _rows('''INSERT INTO cadu_reports_import_observations
                            (import_row_id,organization_id,client_id,campaign_id,metric_date,
                             metric_key,value_numeric,unit,currency)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                            (row_id, *scope, campaign_id, parsed['metric_date'], key,
                             Decimal(value), 'currency' if monetary else 'count',
                             parsed['currency'] if monetary else None))
            status = 'awaiting_extraction' if kind == 'image' else ('parsed' if applied == len(records) else 'needs_review')
            _rows('''UPDATE cadu_reports_import_files SET status=%s,applied_count=%s WHERE id=%s
                RETURNING id''', (status, applied, import_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return jsonify(import_id=import_id, duplicate=False, status=status,
                       row_count=len(records), applied_count=applied), 201
