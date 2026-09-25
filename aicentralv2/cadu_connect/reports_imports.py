"""Client-scoped import inbox for platform exports and screenshots."""
import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from flask import abort, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from ..auth import login_required_api
from ..db import get_db
from .report_sources import prepare_image
from .reports_import_parser import MAX_FILE_BYTES, normalized_platform, parse_record, read_export
from .reports_v1 import _rows, _selection, _write_guard

MAX_REQUEST_BYTES = 11 * 1024 * 1024
METRIC_KEYS = frozenset(('impressions', 'clicks', 'cost', 'conversions', 'conversion_value'))


def _ready():
    return _rows("SELECT to_regclass('public.cadu_reports_import_files') IS NOT NULL "
                 "AND to_regclass('public.cadu_reports_import_decisions') IS NOT NULL "
                 "AND to_regclass('public.cadu_reports_import_visual_runs') IS NOT NULL "
                 "AND to_regclass('public.cadu_reports_import_projection_decisions') IS NOT NULL "
                 "AND to_regclass('public.cadu_reports_import_metric_projection') IS NOT NULL AS ready")[0]['ready']


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
    @bp.get('/api/v1/reports/import-conflicts')
    @login_required_api
    def reports_import_conflicts():
        selected = _selection()
        if not _ready():
            return jsonify(ready=False, conflicts=[])
        scope = (selected['organization_id'], selected['client_id'])
        conflicts = _rows('''SELECT p.campaign_id,p.metric_date,p.metric_key,p.observation_count,
            p.version_count,c.name AS campaign_name,a.name AS account_name,a.platform
            FROM cadu_reports_import_metric_projection p
            JOIN cadu_reports_campaigns c ON c.id=p.campaign_id
                AND c.organization_id=p.organization_id AND c.client_id=p.client_id
            JOIN cadu_reports_accounts a ON a.id=c.account_id
                AND a.organization_id=c.organization_id AND a.client_id=c.client_id
            WHERE p.organization_id=%s AND p.client_id=%s
                AND p.version_count>1 AND p.value_numeric IS NULL
            ORDER BY p.metric_date DESC,p.campaign_id,p.metric_key LIMIT 50''', scope)
        for conflict in conflicts:
            conflict['metric_date'] = conflict['metric_date'].isoformat()
            conflict['candidates'] = _rows('''SELECT o.id,o.value_numeric,o.currency,f.original_name,
                f.created_at,f.id AS import_id
                FROM cadu_reports_import_observations o
                JOIN cadu_reports_import_rows r ON r.id=o.import_row_id
                    AND r.organization_id=o.organization_id AND r.client_id=o.client_id
                JOIN cadu_reports_import_files f ON f.id=r.import_id
                    AND f.organization_id=r.organization_id AND f.client_id=r.client_id
                WHERE o.organization_id=%s AND o.client_id=%s AND o.campaign_id=%s
                    AND o.metric_date=%s AND o.metric_key=%s
                ORDER BY o.id DESC LIMIT 20''',
                (*scope, conflict['campaign_id'], conflict['metric_date'], conflict['metric_key']))
        return jsonify(ready=True, conflicts=conflicts)

    @bp.post('/api/v1/reports/import-conflicts/<int:campaign_id>/<metric_date>/<metric_key>/resolve')
    @login_required_api
    def reports_import_conflict_resolve(campaign_id, metric_date, metric_key):
        selected = _selection()
        _write_guard(selected)
        if not _ready():
            abort(503, description='Instale as migrações de importações do Reports.')
        if metric_key not in METRIC_KEYS:
            abort(400, description='Métrica inválida.')
        try:
            parsed_date = date.fromisoformat(metric_date)
        except ValueError:
            abort(400, description='Data inválida.')
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {'observation_id', 'note'}:
            abort(400, description='Escolha uma observação e informe a justificativa.')
        try:
            observation_id = int(payload['observation_id'])
        except (ValueError, TypeError):
            abort(400, description='Observação inválida.')
        if observation_id < 1:
            abort(400, description='Observação inválida.')
        note = payload['note']
        if not isinstance(note, str) or not note.strip() or len(note.strip()) > 1000:
            abort(400, description='Justificativa obrigatória, com até 1.000 caracteres.')
        scope = (selected['organization_id'], selected['client_id'])
        key = (*scope, campaign_id, parsed_date, metric_key)
        conn = get_db()
        try:
            projection = _rows('''SELECT version_count,value_numeric
                FROM cadu_reports_import_metric_projection
                WHERE organization_id=%s AND client_id=%s AND campaign_id=%s
                    AND metric_date=%s AND metric_key=%s''', key)
            if not projection or projection[0]['version_count'] < 2 or projection[0]['value_numeric'] is not None:
                abort(409, description='O conflito já foi resolvido ou não existe neste cliente.')
            candidates = _rows('''SELECT id FROM cadu_reports_import_observations
                WHERE organization_id=%s AND client_id=%s AND campaign_id=%s
                    AND metric_date=%s AND metric_key=%s ORDER BY id DESC''', key)
            if observation_id not in {item['id'] for item in candidates}:
                abort(400, description='A observação não pertence a este conflito.')
            _rows('''INSERT INTO cadu_reports_import_projection_decisions
                (organization_id,client_id,campaign_id,metric_date,metric_key,
                 selected_observation_id,seen_observation_id,note,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (*key, observation_id, candidates[0]['id'], note.strip(), session['user_id']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return jsonify(resolved=True)

    @bp.get('/api/v1/reports/import-metrics')
    @login_required_api
    def reports_import_metrics():
        selected = _selection()
        if not _ready() or not _rows("SELECT to_regclass('public.cadu_reports_import_metric_projection') IS NOT NULL AS ready")[0]['ready']:
            return jsonify(ready=False, days=[], by_platform=[], totals={}, conflicts=0)
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        filters = ''
        params = [selected['organization_id'], selected['client_id'], date.today() - timedelta(days=days - 1)]
        platform = request.args.get('platform', '').strip()
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', platform):
                abort(400, description='Plataforma inválida.')
            filters += ' AND a.platform=%s'
            params.append(platform)
        for field, column in (('account_id', 'a.id'), ('campaign_id', 'c.id')):
            supplied = request.args.get(field, '').strip()
            if supplied:
                try:
                    number = int(supplied)
                except ValueError:
                    abort(400, description=f'{field} inválido.')
                if number < 1:
                    abort(400, description=f'{field} inválido.')
                filters += f' AND {column}=%s'
                params.append(number)
        rows = _rows('''SELECT p.metric_date,p.metric_key,p.currency,a.platform,
            SUM(p.value_numeric) AS value_numeric,
            COUNT(*) FILTER (WHERE p.version_count>1 AND p.value_numeric IS NULL)::bigint AS conflicts
            FROM cadu_reports_import_metric_projection p
            JOIN cadu_reports_campaigns c ON c.id=p.campaign_id
                AND c.organization_id=p.organization_id AND c.client_id=p.client_id
            JOIN cadu_reports_accounts a ON a.id=c.account_id
                AND a.organization_id=c.organization_id AND a.client_id=c.client_id
            WHERE p.organization_id=%s AND p.client_id=%s AND p.metric_date >= %s'''
            + filters + ''' GROUP BY p.metric_date,p.metric_key,p.currency,a.platform
            ORDER BY p.metric_date,a.platform,p.metric_key''', tuple(params))
        by_day = {}
        by_platform = {}
        grand = {'impressions': Decimal(0), 'clicks': Decimal(0), 'conversions': Decimal(0)}
        grand_cost = {}
        conflicts = 0
        for row in rows:
            day_key = row['metric_date'].isoformat()
            day = by_day.setdefault(day_key, {'date': day_key, 'impressions': Decimal(0),
                                              'clicks': Decimal(0), 'conversions': Decimal(0), 'costs': {}})
            source = by_platform.setdefault(row['platform'], {'platform': row['platform'],
                'impressions': Decimal(0), 'clicks': Decimal(0), 'conversions': Decimal(0), 'costs': {}})
            conflicts += int(row['conflicts'] or 0)
            value = row['value_numeric']
            if value is None:
                continue
            if row['metric_key'] == 'cost':
                currency = row['currency']
                for target in (day['costs'], source['costs'], grand_cost):
                    target[currency] = target.get(currency, Decimal(0)) + value
            elif row['metric_key'] in grand:
                key = row['metric_key']
                day[key] += value
                source[key] += value
                grand[key] += value
        def serialize(item, *, currency=None):
            currencies = item.pop('costs')
            effective = currency if currency is not None else (next(iter(currencies)) if len(currencies) == 1 else None)
            return {**item, 'impressions': str(item['impressions']), 'clicks': str(item['clicks']),
                    'conversions': str(item['conversions']),
                    'cost': str(currencies[effective]) if effective and effective in currencies else None,
                    'currency': effective}
        shared_currency = next(iter(grand_cost)) if len(grand_cost) == 1 else None
        return jsonify(ready=True, period_days=days, source='export', conflicts=conflicts,
            days=[serialize(day, currency=shared_currency) for day in by_day.values()],
            by_platform=[serialize(item) for item in by_platform.values()],
            totals={**{key: str(value) for key, value in grand.items()},
                    'cost': str(grand_cost[shared_currency]) if shared_currency else None},
            currency=shared_currency)

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
        if not _ready():
            abort(503, description='Instale as migrações de importações do Reports.')
        scope = (selected['organization_id'], selected['client_id'])
        batch = _rows('''SELECT id,original_name,file_kind,status,platform_hint,row_count,
            applied_count,created_at FROM cadu_reports_import_files
            WHERE id=%s AND organization_id=%s AND client_id=%s''', (str(import_id), *scope))
        if not batch:
            abort(404)
        rows = _rows('''SELECT r.id,r.source_row,r.sheet_name,r.parsed,r.status,r.reason,
            r.account_id,r.campaign_id,r.metric_date,d.note AS decision_note,d.created_at AS decided_at
            FROM cadu_reports_import_rows r LEFT JOIN cadu_reports_import_decisions d
                ON d.import_row_id=r.id AND d.organization_id=r.organization_id AND d.client_id=r.client_id
            WHERE r.import_id=%s AND r.organization_id=%s AND r.client_id=%s
            ORDER BY (r.status='needs_review') DESC,r.id LIMIT 100''', (str(import_id), *scope))
        visual = _rows('''SELECT result,model,created_at FROM cadu_reports_import_visual_runs
            WHERE import_id=%s AND organization_id=%s AND client_id=%s''', (str(import_id), *scope))
        return jsonify(import_file=batch[0], rows=rows, visual=visual[0] if visual else None)

    @bp.post('/api/v1/reports/imports/<uuid:import_id>/extract')
    @login_required_api
    def reports_import_extract(import_id):
        selected = _selection()
        _write_guard(selected)
        if not _ready():
            abort(503, description='Instale as migrações de importações do Reports.')
        scope = (selected['organization_id'], selected['client_id'])
        conn = get_db()
        try:
            batch = _rows('''SELECT id,raw_bytes FROM cadu_reports_import_files
                WHERE id=%s AND organization_id=%s AND client_id=%s AND file_kind='image'
                FOR UPDATE''', (str(import_id), *scope))
            if not batch:
                abort(404)
            existing = _rows('''SELECT result,model,created_at FROM cadu_reports_import_visual_runs
                WHERE import_id=%s AND organization_id=%s AND client_id=%s''', (str(import_id), *scope))
            if existing:
                conn.rollback()
                return jsonify(visual=existing[0], duplicate=True)
            from ..cadu_credit_connector import CaduCreditConnector, CreditActor
            from ..cadu_tool_billing import InsufficientToolCredits
            from ..services.openrouter_service import chat_completion
            from .reports_import_vision import MAX_TOKENS, extract_visual_result
            actor = CreditActor.from_values(selected['client_id'], session['user_id'])
            credits = CaduCreditConnector()
            try:
                credits.authorize(actor, MAX_TOKENS * 12)
                result, usage, model = extract_visual_result(
                    batch[0]['raw_bytes'], str(import_id), complete=chat_completion)
                run_id = str(uuid.uuid4())
                credits.charge_provider(
                    actor=actor, idempotency_key=f'reports:import-visual:{run_id}',
                    app='Cadu Reports', stage='extract_import_visual',
                    provider_result={'usage': usage, 'model': model},
                    metadata={'import_id': str(import_id), 'operation': 'visual_import_extraction'},
                    margin_multiplier=1)
            except InsufficientToolCredits as exc:
                conn.rollback()
                return jsonify(error=str(exc)), 409
            except (ValueError, json.JSONDecodeError) as exc:
                conn.rollback()
                return jsonify(error=str(exc)), 422
            except Exception:
                conn.rollback()
                return jsonify(error='Não foi possível ler o print agora. Tente novamente.'), 502
            visual = _rows('''INSERT INTO cadu_reports_import_visual_runs
                (id,import_id,organization_id,client_id,result,model,usage,created_by)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s)
                RETURNING result,model,created_at''',
                (run_id, str(import_id), *scope, json.dumps(result), model,
                 json.dumps(usage), session['user_id']))[0]
            _rows('''UPDATE cadu_reports_import_files SET status='needs_review'
                WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING id''',
                (str(import_id), *scope))
            conn.commit()
            return jsonify(visual=visual, duplicate=False)
        except Exception:
            conn.rollback()
            raise

    @bp.post('/api/v1/reports/imports/<uuid:import_id>/rows/<int:row_id>/resolve')
    @login_required_api
    def reports_import_resolve(import_id, row_id):
        selected = _selection()
        _write_guard(selected)
        if not _ready():
            abort(503, description='Instale as migrações de importações do Reports.')
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description='Envie os dados corrigidos da linha.')
        allowed = {'platform', 'external_account_id', 'account_name',
                   'external_campaign_id', 'campaign_name', 'metric_date', 'currency',
                   'impressions', 'clicks', 'cost', 'conversions', 'conversion_value', 'note'}
        if set(payload) - allowed:
            abort(400, description='Campo não permitido na revisão.')
        note = str(payload.get('note') or '').strip()
        if not note or len(note) > 1000:
            abort(400, description='Registre a justificativa da revisão (até 1.000 caracteres).')
        values = {}
        fields = {'platform': 'Platform', 'external_account_id': 'Account ID',
                  'account_name': 'Account Name', 'external_campaign_id': 'Campaign ID',
                  'campaign_name': 'Campaign Name', 'metric_date': 'Date', 'currency': 'Currency',
                  'impressions': 'Impressions', 'clicks': 'Clicks', 'cost': 'Cost',
                  'conversions': 'Conversions', 'conversion_value': 'Conversion Value'}
        for key, header in fields.items():
            value = payload.get(key, '')
            if not isinstance(value, str) or len(value) > 1000:
                abort(400, description=f'{key} inválido.')
            values[header] = value
        parsed = parse_record({'raw': values}, date_order='auto')
        if parsed['issues']:
            abort(400, description='Revise: ' + '; '.join(parsed['issues']))
        scope = (selected['organization_id'], selected['client_id'])
        conn = get_db()
        try:
            found = _rows('''SELECT r.id,r.parsed,r.status FROM cadu_reports_import_rows r
                JOIN cadu_reports_import_files f ON f.id=r.import_id
                    AND f.organization_id=r.organization_id AND f.client_id=r.client_id
                WHERE r.id=%s AND r.import_id=%s AND r.organization_id=%s AND r.client_id=%s
                    AND f.file_kind IN ('csv','xlsx') FOR UPDATE OF r''',
                (row_id, str(import_id), *scope))
            if not found:
                abort(404)
            if found[0]['status'] != 'needs_review':
                abort(409, description='Esta linha já foi confirmada.')
            account_id, campaign_id = _upsert_identity(selected, parsed)
            if parsed['issues'] or not campaign_id:
                abort(409, description='A conta ou campanha entrou em conflito; revise a identidade.')
            collisions = _rows('''SELECT id FROM cadu_reports_import_rows
                WHERE import_id=%s AND organization_id=%s AND client_id=%s
                    AND campaign_id=%s AND metric_date=%s AND status='applied' AND id<>%s LIMIT 1''',
                (str(import_id), *scope, campaign_id, parsed['metric_date'], row_id))
            if collisions:
                abort(409, description='Já existe uma linha confirmada da campanha nesta data e arquivo.')
            _rows('''INSERT INTO cadu_reports_import_decisions
                (import_row_id,organization_id,client_id,before_parsed,after_parsed,note,created_by)
                VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING id''',
                (row_id, *scope, json.dumps(found[0]['parsed']), json.dumps(parsed), note, session['user_id']))
            _rows('''UPDATE cadu_reports_import_rows SET parsed=%s::jsonb,status='applied',reason=NULL,
                account_id=%s,campaign_id=%s,metric_date=%s WHERE id=%s RETURNING id''',
                (json.dumps(parsed), account_id, campaign_id, parsed['metric_date'], row_id))
            for key, value in parsed['metrics'].items():
                monetary = key in ('cost', 'conversion_value')
                _rows('''INSERT INTO cadu_reports_import_observations
                    (import_row_id,organization_id,client_id,campaign_id,metric_date,
                     metric_key,value_numeric,unit,currency)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                    (row_id, *scope, campaign_id, parsed['metric_date'], key,
                     Decimal(value), 'currency' if monetary else 'count',
                     parsed['currency'] if monetary else None))
            _rows('''UPDATE cadu_reports_import_files SET applied_count=applied_count+1,
                status=CASE WHEN applied_count+1=row_count THEN 'parsed' ELSE 'needs_review' END
                WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING id''',
                (str(import_id), *scope))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return jsonify(resolved=True, row_id=row_id)

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
