"""Super Tag conversion rules and "who converted" (leads).

Conversion rules
    Each site may keep ``config.conversion_rules``: a list of rules that turn ordinary events into a derived
    ``conversion`` event at ingestion time (so every screen that reads ``event_kind='conversion'`` sees them):

    * ``{"type": "path", "match": "exact"|"prefix"|"segment", "value": "/obrigado", "name": "pagina_obrigado"}``
      matches a page view (``segment`` = any path segment starting with the value, e.g. ``obrigad``);
    * ``{"type": "valid_form", "form_id": "contato"?}`` matches a form submit that the browser considered valid;
    * ``{"type": "event_name", "value": "lead_enviado"}`` matches a custom event with that name.

    A site with no rule at all uses DEFAULT_CONVERSION_RULES (any path segment starting with obrigad, thank, sucesso
    or confirmac), unless ``config.conversion_defaults`` is ``false``. As soon as one rule is saved, only the saved
    rules apply. The derived event id is ``uuid5(site_id, source_event_id)``, so retries never double count; a
    thank-you page reloaded in the same session counts once.

Leads
    A valid form submit sends name/e-mail/phone (and the extra fields the site listed in ``config.form_capture``) to
    ``/lead``. Values are encrypted with Fernet (SUPERTAG_LEADS_KEY, or a key derived from SECRET_KEY with its own
    domain separator) and expire with the site's retention. A lead starts ``pending`` and is confirmed by a
    conversion of the same session within 30 minutes (rule, thank-you page or trackConversion), or directly when
    ``config.form_capture.confirm == 'valid_submit'``.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import abort, current_app, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_flow import _host_allowed, _safe_path
from .reports_v1 import _rows, _selection, _write_guard

LEADS_TABLE = 'cadu_reports_supertag_leads'
MAX_RULES = 20
MAX_CAPTURE_FIELDS = 20
MAX_LEAD_BYTES = 16 * 1024
FIELD_LIMIT = 200
TEXTAREA_LIMIT = 2000
CONFIRM_WINDOW = timedelta(minutes=30)
# A beacon for the lead and the batch with the thank-you page may arrive in any order.
CONFIRM_SKEW = timedelta(minutes=2)
SUGGESTION_PATTERN = r'(obrigad|thank|sucesso|confirmac)'
DEFAULT_CONVERSION_RULES = tuple(
    {'type': 'path', 'match': 'segment', 'value': stem, 'name': 'pagina_obrigado'}
    for stem in ('obrigad', 'thank', 'sucesso', 'confirmac'))
DEFAULT_RULE_NAMES = {'path': 'pagina_obrigado', 'valid_form': 'formulario_enviado'}
CONFIRMATIONS = ('pending', 'rule', 'conversion', 'valid_submit')
# Field names that are never captured, whatever the site configures.
SENSITIVE_NAME = re.compile(r'senha|pass|card|cartao|cartão|cvv|cvc|token|captcha|csrf|cpf|cnpj|(^|[^a-z])rg($|[^a-z])|secret|otp', re.I)
DOCUMENT_VALUE = re.compile(r'^\s*(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\s*$')
CARD_VALUE = re.compile(r'\d{13,19}')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')
PHONE = re.compile(r'\+?[0-9(). -]{7,40}')
NAME_RULE = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,79}')
FIELD_NAME = re.compile(r'[A-Za-z0-9_.\[\]-]{1,80}')

_ready_tables = set()


def leads_ready():
    """True once the leads migration exists; a positive answer is cached for the process."""
    if LEADS_TABLE in _ready_tables:
        return True
    if _rows(f"SELECT to_regclass('public.{LEADS_TABLE}') IS NOT NULL AS ready")[0]['ready']:
        _ready_tables.add(LEADS_TABLE)
        return True
    return False


# ---------------------------------------------------------------- conversion rules

def validate_conversion_rules(value):
    if not isinstance(value, list) or len(value) > MAX_RULES:
        abort(400, description=f'Informe até {MAX_RULES} regras de conversão.')
    clean = []
    for rule in value:
        if not isinstance(rule, dict) or rule.get('type') not in ('path', 'valid_form', 'event_name'):
            abort(400, description='Regra de conversão inválida.')
        kind = rule['type']
        allowed = {'path': {'type', 'match', 'value', 'name'}, 'valid_form': {'type', 'form_id', 'name'},
                   'event_name': {'type', 'value', 'name'}}[kind]
        if set(rule) - allowed:
            abort(400, description='Regra de conversão com campos desconhecidos.')
        name = rule.get('name') or None
        if name is not None and (not isinstance(name, str) or not NAME_RULE.fullmatch(name)):
            abort(400, description='Nome da conversão: letras, números e _ (começando por letra).')
        item = {'type': kind}
        if kind == 'path':
            match = rule.get('match') or 'prefix'
            raw = rule.get('value')
            if match not in ('exact', 'prefix', 'segment') or not isinstance(raw, str):
                abort(400, description='Informe o caminho e como ele deve ser comparado.')
            raw = raw.strip()
            if match == 'segment':
                if not re.fullmatch(r'[A-Za-z0-9_.-]{2,60}', raw):
                    abort(400, description='Trecho do caminho inválido.')
            elif not raw.startswith('/') or '?' in raw or '#' in raw or '@' in raw or len(raw) > 200:
                abort(400, description='O caminho começa com / e não leva ?, # nem e-mail.')
            item.update(match=match, value=raw)
        elif kind == 'valid_form':
            form_id = rule.get('form_id') or None
            if form_id is not None and (not isinstance(form_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', form_id)):
                abort(400, description='Identificador de formulário inválido.')
            if form_id:
                item['form_id'] = form_id
        else:
            raw = rule.get('value')
            if not isinstance(raw, str) or not NAME_RULE.fullmatch(raw):
                abort(400, description='Nome de evento inválido.')
            item['value'] = raw
        if name:
            item['name'] = name
        clean.append(item)
    return clean


def effective_rules(config):
    rules = (config or {}).get('conversion_rules') or []
    if rules:
        return list(rules)
    return list(DEFAULT_CONVERSION_RULES) if (config or {}).get('conversion_defaults', True) is not False else []


def _norm_path(path):
    value = str(path or '/').lower()
    return value.rstrip('/') or '/'


def rule_matches(rule, kind, event_name, path, data):
    rule_type = rule.get('type')
    if rule_type == 'path' and kind == 'page_view':
        current, wanted, match = _norm_path(path), str(rule.get('value') or ''), rule.get('match', 'prefix')
        if match == 'segment':
            stem = wanted.strip('/').lower()
            return bool(stem) and any(part.startswith(stem) for part in current.split('/') if part)
        wanted = _norm_path(wanted)
        return current == wanted if match == 'exact' else current.startswith(wanted)
    if rule_type == 'valid_form' and kind == 'form_submit':
        # Tags older than the `valid` flag only fire after the browser accepted the form.
        if (data or {}).get('valid') is False:
            return False
        return not rule.get('form_id') or (data or {}).get('form_id') == rule['form_id']
    if rule_type == 'event_name' and kind == 'custom_event':
        return event_name == rule.get('value')
    return False


def derived_event_id(site_id, source_event_id):
    return str(uuid.uuid5(uuid.UUID(str(site_id)) if _is_uuid(site_id) else uuid.NAMESPACE_URL,
                          f'supertag-conversion:{site_id}:{source_event_id}'))


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def derive_conversions(site, prepared, converted_pages=frozenset()):
    """Conversion events implied by the site rules. ``converted_pages`` holds (session, path) already converted."""
    rules = effective_rules(site.get('config'))
    if not rules:
        return []
    explicit = {(str(item[4]), item[7]) for item in prepared if item[5] == 'conversion'}
    seen = set(converted_pages)
    derived = []
    for item in prepared:
        (event_id, site_id, client_id, visitor_id, session_id, kind, event_name, path, referrer,
         attribution_json, data_json, width, height, occurred_at) = item
        if kind not in ('page_view', 'form_submit', 'custom_event'):
            continue
        data = json.loads(data_json or '{}')
        rule = next((candidate for candidate in rules if rule_matches(candidate, kind, event_name, path, data)), None)
        if not rule:
            continue
        page_key = (str(session_id), path)
        if kind == 'page_view':
            # A reloaded thank-you page or a site that also calls trackConversion there counts once.
            if page_key in seen or page_key in explicit:
                continue
            seen.add(page_key)
        name = rule.get('name') or DEFAULT_RULE_NAMES.get(rule['type']) or event_name or 'conversao'
        derived.append((derived_event_id(site_id, event_id), site_id, client_id, visitor_id, session_id,
                        'conversion', name[:80], path, referrer, attribution_json,
                        json.dumps({'derived_from': kind, 'rule': rule['type'], 'source_event_id': str(event_id)}),
                        width, height, occurred_at))
    return derived


def converted_pages(site_id, prepared):
    sessions = sorted({str(item[4]) for item in prepared if item[5] == 'page_view'})
    if not sessions:
        return set()
    rows = _rows('''SELECT session_id,page_path FROM cadu_reports_supertag_events
        WHERE site_id=%s AND session_id = ANY(%s::uuid[]) AND event_kind='conversion'
            AND event_data->>'derived_from'='page_view' AND occurred_at>=NOW()-INTERVAL '2 days' ''',
        (site_id, sessions))
    return {(str(row['session_id']), row['page_path']) for row in rows}


def confirm_leads(site_id, conversions):
    """Pending leads of the same session, submitted up to 30 min before a conversion, become confirmed."""
    if not conversions or not leads_ready():
        return
    for item in conversions:
        data = json.loads(item[10] or '{}')
        how = 'rule' if data.get('derived_from') else 'conversion'
        occurred_at = item[13]
        _rows(f'''UPDATE {LEADS_TABLE} SET confirmed_at=%s,confirmation=%s
            WHERE site_id=%s AND session_id=%s AND confirmed_at IS NULL
                AND submitted_at BETWEEN %s AND %s RETURNING id''',
              (occurred_at, how, site_id, str(item[4]), occurred_at - CONFIRM_WINDOW, occurred_at + CONFIRM_SKEW))


def conversion_suggestions(site):
    """Visited paths that look like a thank-you page and are not covered by the saved rules yet."""
    rows = _rows('''SELECT page_path,COUNT(*)::bigint AS views,MAX(occurred_at) AS last_at
        FROM cadu_reports_supertag_events
        WHERE site_id=%s AND event_kind='page_view' AND expires_at>NOW()
            AND occurred_at>=NOW()-INTERVAL '90 days' AND page_path ~* %s
        GROUP BY page_path ORDER BY views DESC LIMIT 20''', (site['id'], SUGGESTION_PATTERN))
    saved = (site.get('config') or {}).get('conversion_rules') or []
    out = []
    for row in rows:
        covered = any(rule_matches(rule, 'page_view', None, row['page_path'], {}) for rule in saved)
        if not covered:
            out.append({'path': row['page_path'], 'views': int(row['views']), 'last_at': row['last_at'],
                        'rule': {'type': 'path', 'match': 'exact', 'value': row['page_path'], 'name': 'pagina_obrigado'}})
    return out


# ---------------------------------------------------------------- form capture config

def validate_form_capture(value):
    if not isinstance(value, dict) or set(value) - {'enabled', 'fields', 'confirm'}:
        abort(400, description='Configuração de captura de formulário inválida.')
    clean = {}
    if 'enabled' in value:
        if not isinstance(value['enabled'], bool):
            abort(400, description='Informe se a captura de contatos está ativa.')
        clean['enabled'] = value['enabled']
    if 'confirm' in value:
        if value['confirm'] not in ('conversion', 'valid_submit'):
            abort(400, description='Escolha como o lead é confirmado.')
        clean['confirm'] = value['confirm']
    if 'fields' in value:
        fields = value['fields']
        if not isinstance(fields, list) or len(fields) > MAX_CAPTURE_FIELDS:
            abort(400, description=f'Informe até {MAX_CAPTURE_FIELDS} campos extras.')
        names = []
        for name in fields:
            if not isinstance(name, str) or not FIELD_NAME.fullmatch(name.strip()):
                abort(400, description='Use o atributo name (ou id) do campo: letras, números, _, -, . e [].')
            if SENSITIVE_NAME.search(name):
                abort(400, description=f'O campo "{name}" parece sensível (senha, cartão, documento ou token) e nunca é capturado.')
            if name.strip() not in names:
                names.append(name.strip())
        clean['fields'] = names
    return clean


def public_form_capture(config):
    capture = (config or {}).get('form_capture') or {}
    return {'enabled': capture.get('enabled', True) is not False, 'fields': list(capture.get('fields') or [])}


# ---------------------------------------------------------------- encryption

def _setting(name):
    try:
        return current_app.config.get(name) or os.getenv(name, '')
    except RuntimeError:
        return os.getenv(name, '')


def _fernet():
    key = _setting('SUPERTAG_LEADS_KEY')
    if key:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError):
            abort(503, description='SUPERTAG_LEADS_KEY não é uma chave Fernet válida.')
    app_secret = str(_setting('SECRET_KEY') or '').strip()
    if not app_secret:
        abort(503, description='Configure SECRET_KEY no servidor antes de guardar contatos.')
    # Own domain separator: never the same key as the integration credentials.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'centralx:supertag-leads:v1:' + app_secret.encode()).digest()))


def encrypt(value):
    if value in (None, '', {}):
        return None
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _fernet().encrypt(raw.encode()).decode()


def decrypt(token, as_json=False):
    if not token:
        return {} if as_json else ''
    try:
        raw = _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return None
    if as_json:
        try:
            return json.loads(raw)
        except ValueError:
            return None
    return raw


def contact_digest(site_id, kind, value):
    secret = _setting('SECRET_KEY')
    if not value or not secret:
        return None
    key = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(key, f'supertag-lead:v1:{site_id}:{kind}:{value}'.encode(), hashlib.sha256).hexdigest()


def mask_email(value):
    if not value or '@' not in value:
        return value or ''
    user, domain = value.split('@', 1)
    return f'{user[:2]}{"•" * max(1, min(len(user) - 2, 6))}@{domain}'


def mask_phone(value):
    digits = re.sub(r'\D', '', value or '')
    return f'••••{digits[-4:]}' if len(digits) >= 4 else ('••••' if digits else '')


def mask_name(value):
    parts = (value or '').split()
    if not parts:
        return ''
    return parts[0] + (f' {parts[-1][0]}.' if len(parts) > 1 else '')


# ---------------------------------------------------------------- lead payload

def _looks_sensitive(value):
    compact = re.sub(r'[\s.-]', '', value)
    return bool(DOCUMENT_VALUE.match(value) or CARD_VALUE.search(compact))


def clean_contact(name, email, phone):
    """Invalid pieces are dropped, never the whole lead (a rejected beacon is lost for good)."""
    name = ' '.join(name.split())[:FIELD_LIMIT] if isinstance(name, str) else ''
    if name and (_looks_sensitive(name) or '@' in name):
        name = ''
    email = email.strip()[:254] if isinstance(email, str) else ''
    if email and not EMAIL.fullmatch(email):
        email = ''
    phone = phone.strip()[:40] if isinstance(phone, str) else ''
    if phone and not PHONE.fullmatch(phone):
        phone = ''
    return name, email, phone


def clean_fields(fields, config):
    allowed = set(public_form_capture(config)['fields'])
    if not isinstance(fields, dict):
        return {}
    clean = {}
    for key, value in list(fields.items())[:MAX_CAPTURE_FIELDS]:
        if key not in allowed or SENSITIVE_NAME.search(str(key)) or not isinstance(value, str):
            continue
        value = value.strip()[:TEXTAREA_LIMIT]
        if value and not _looks_sensitive(value):
            clean[key] = value
    return clean


def _retention(site):
    from .reports_supertag import DEFAULT_RETENTION_DAYS, RETENTION_DAYS_CHOICES
    days = (site.get('config') or {}).get('retention_days', DEFAULT_RETENTION_DAYS)
    return DEFAULT_RETENTION_DAYS if isinstance(days, bool) or days not in RETENTION_DAYS_CHOICES else days


def store_lead(site, *, source, source_event_id, session_id, visitor_id, form_id, page_path, submitted_at,
               name, email, phone, fields):
    """Insert (idempotent per source event) and confirm it right away when the conversion already arrived."""
    if not leads_ready():
        return None
    capture = (site.get('config') or {}).get('form_capture') or {}
    confirmation, confirmed_at = 'pending', None
    if source == 'form' and capture.get('confirm') == 'valid_submit':
        confirmation, confirmed_at = 'valid_submit', submitted_at
    else:
        found = _rows('''SELECT occurred_at,event_data->>'derived_from' AS derived_from
            FROM cadu_reports_supertag_events WHERE site_id=%s AND session_id=%s AND event_kind='conversion'
                AND occurred_at BETWEEN %s AND %s ORDER BY occurred_at LIMIT 1''',
            (site['id'], session_id, submitted_at - CONFIRM_SKEW, submitted_at + CONFIRM_WINDOW))
        if found:
            confirmation = 'rule' if found[0]['derived_from'] else 'conversion'
            confirmed_at = found[0]['occurred_at']
    normalized_email = email.strip().casefold()
    normalized_phone = re.sub(r'[^0-9+]', '', phone)
    rows = _rows(f'''INSERT INTO {LEADS_TABLE}
            (id,site_id,client_id,session_id,visitor_id,source_event_id,source,form_id,page_path,submitted_at,
             confirmed_at,confirmation,display_name_enc,email_enc,phone_enc,fields_enc,email_digest,phone_digest,expires_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW() + (%s * INTERVAL '1 day'))
        ON CONFLICT (site_id,source_event_id) DO NOTHING RETURNING id''',
        (str(uuid.uuid4()), site['id'], site['client_id'], session_id, visitor_id, source_event_id, source,
         form_id, page_path, submitted_at, confirmed_at, confirmation, encrypt(name), encrypt(email),
         encrypt(phone), encrypt(fields) if fields else None,
         contact_digest(site['id'], 'email', normalized_email), contact_digest(site['id'], 'phone', normalized_phone),
         _retention(site)))
    return rows[0]['id'] if rows else None


def identify_source_event(site_id, session_id, digest):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'supertag-identify:{site_id}:{session_id}:{digest}'))


def _uuid(value, field, optional=False):
    if optional and value in (None, ''):
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        abort(400, description=f'{field} inválido.')


def _origin_guard(site):
    request._supertag_allowed_host = site['allowed_host']
    parsed = urlparse(request.headers.get('Origin') or '')
    if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
        abort(403)


def _lead_payload(site):
    if request.content_length is not None and request.content_length > MAX_LEAD_BYTES:
        abort(413)
    raw = request.stream.read(MAX_LEAD_BYTES + 1)
    if len(raw) > MAX_LEAD_BYTES:
        abort(413)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        abort(400, description='Contato inválido.')
    allowed = {'event_id', 'visitor_id', 'session_id', 'form_id', 'path', 'occurred_at', 'name', 'email', 'phone', 'fields'}
    if not isinstance(payload, dict) or set(payload) - allowed:
        abort(400, description='Contato fora do contrato da Super Tag.')
    path = payload.get('path') or '/'
    if not isinstance(path, str) or not path.startswith('/') or '?' in path or '#' in path or len(path) > 1000:
        abort(400, description='Caminho da página inválido.')
    form_id = payload.get('form_id') or None
    if form_id is not None and (not isinstance(form_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', form_id)):
        form_id = None
    try:
        submitted_at = datetime.fromisoformat(str(payload.get('occurred_at', '')).replace('Z', '+00:00'))
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        submitted_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    submitted_at = min(max(submitted_at.astimezone(timezone.utc), now - timedelta(days=1)), now + timedelta(minutes=5))
    name, email, phone = clean_contact(payload.get('name'), payload.get('email'), payload.get('phone'))
    fields = clean_fields(payload.get('fields') or {}, site.get('config'))
    return {
        'source_event_id': _uuid(payload.get('event_id'), 'Evento'),
        'session_id': _uuid(payload.get('session_id'), 'Sessão'),
        'visitor_id': _uuid(payload.get('visitor_id'), 'Visitante', optional=True),
        'form_id': form_id, 'page_path': _safe_path(path)[:500], 'submitted_at': submitted_at,
        'name': name, 'email': email, 'phone': phone, 'fields': fields,
    }


# ---------------------------------------------------------------- read side

_LEADS_SQL = f'''SELECT l.id,l.site_id,s.allowed_host AS host,l.session_id,l.source,l.form_id,l.page_path,
        l.submitted_at,l.confirmed_at,l.confirmation,l.display_name_enc,l.email_enc,l.phone_enc,l.fields_enc,
        o.utm_source,o.utm_medium,o.utm_campaign,o.utm_id,o.referrer_host,o.landing_path,j.journey
    FROM {LEADS_TABLE} l JOIN cadu_reports_supertag_sites s ON s.id=l.site_id
    LEFT JOIN LATERAL (
        SELECT e.attribution->>'utm_source' AS utm_source,e.attribution->>'utm_medium' AS utm_medium,
            e.attribution->>'utm_campaign' AS utm_campaign,e.attribution->>'utm_id' AS utm_id,
            e.referrer_host,e.page_path AS landing_path
        FROM cadu_reports_supertag_events e
        WHERE e.site_id=l.site_id AND e.session_id=l.session_id AND e.event_kind='page_view' AND e.expires_at>NOW()
        ORDER BY e.occurred_at,e.id LIMIT 1) o ON TRUE
    LEFT JOIN LATERAL (
        SELECT JSONB_AGG(JSONB_BUILD_OBJECT('kind',x.event_kind,'path',x.page_path,'at',x.occurred_at,'name',x.event_name)
            ORDER BY x.occurred_at,x.id) AS journey
        FROM (SELECT e.id,e.event_kind,e.page_path,e.occurred_at,e.event_name FROM cadu_reports_supertag_events e
            WHERE e.site_id=l.site_id AND e.session_id=l.session_id AND e.expires_at>NOW()
                AND e.event_kind IN ('page_view','form_submit','conversion')
            ORDER BY e.occurred_at,e.id LIMIT 40) x) j ON TRUE
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND l.expires_at>NOW()
        AND l.submitted_at>=%(since)s AND l.submitted_at<%(until)s {{site}}
    ORDER BY l.submitted_at DESC LIMIT 200'''


def lead_row(row, can_reveal):
    name = decrypt(row.pop('display_name_enc'))
    email = decrypt(row.pop('email_enc'))
    phone = decrypt(row.pop('phone_enc'))
    fields = decrypt(row.pop('fields_enc'), as_json=True)
    unreadable = name is None or email is None or phone is None or fields is None
    row.update(
        id=str(row['id']), site_id=str(row['site_id']), session_id=str(row['session_id']),
        name=(name or '') if can_reveal else mask_name(name),
        email=mask_email(email or ''), phone=mask_phone(phone or ''),
        fields=(fields or {}) if can_reveal else {key: '•••' for key in (fields or {})},
        status='confirmed' if row['confirmation'] != 'pending' else 'pending',
        campaign=row.get('utm_campaign') or row.get('utm_id') or '', unreadable=unreadable,
        journey=row.get('journey') or [])
    return row


def register(bp):
    @bp.route('/public/supertag/v1/<public_id>/lead', methods=['POST', 'OPTIONS'])
    def supertag_public_lead(public_id):
        from .reports_supertag import MAX_IP_EVENTS_PER_MINUTE, _ip_digest, _site_by_public_id, enhanced_settings
        site = _site_by_public_id(public_id)
        _origin_guard(site)
        if request.method == 'OPTIONS':
            return ('', 204)
        # The tag reads config.json with cache: 'force-cache', so a browser may keep an old "enabled" copy: the
        # server is what enforces a capture (or the form measurement it rides on) turned off.
        if not public_form_capture(site.get('config'))['enabled'] or not enhanced_settings(site.get('config'))['forms']:
            return jsonify(accepted=0), 202
        lead = _lead_payload(site)
        if not (lead['name'] or lead['email'] or lead['phone'] or lead['fields']):
            return jsonify(accepted=0), 202
        quota = _rows('''INSERT INTO cadu_reports_supertag_ip_rate_limits (site_id,ip_digest,bucket_start,event_count)
            VALUES (%s,%s,date_trunc('minute',NOW()),1)
            ON CONFLICT (site_id,ip_digest,bucket_start) DO UPDATE
                SET event_count=cadu_reports_supertag_ip_rate_limits.event_count+1
                WHERE cadu_reports_supertag_ip_rate_limits.event_count < %s
            RETURNING event_count''', (site['id'], _ip_digest(), MAX_IP_EVENTS_PER_MINUTE))
        if not quota:
            abort(429, description='Limite temporário de envio atingido para esta origem.')
        stored = store_lead(site, source='form', **lead)
        get_db().commit()
        return jsonify(accepted=1 if stored else 0), 202

    @bp.get('/api/v2/reports/supertag/leads')
    @login_required_api
    def supertag_leads():
        """Who converted in the period: contacts masked for viewers, origin of the session and its journey."""
        from .reports_pages import _window
        selected = _selection()
        since, until, days = _window()
        can_reveal = selected['role'] != 'viewer'
        window = {'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo'}
        if not leads_ready():
            return jsonify(ready=False, window=window, leads=[], totals={'leads': 0, 'confirmed': 0, 'pending': 0},
                           can_reveal=can_reveal)
        scope = {'client': selected['client_id'], 'since': since, 'until': until}
        site_filter = ''
        if request.args.get('site_id', '').strip():
            scope['site'] = _uuid(request.args['site_id'].strip(), 'Site')
            site_filter = 'AND l.site_id=%(site)s::uuid'
        leads = [lead_row(row, can_reveal) for row in _rows(_LEADS_SQL.replace('{site}', site_filter), scope)]
        confirmed = sum(1 for lead in leads if lead['status'] == 'confirmed')
        body = dict(ready=True, window=window, leads=leads, can_reveal=can_reveal,
                    totals={'leads': len(leads), 'confirmed': confirmed, 'pending': len(leads) - confirmed})
        if can_reveal:
            body['csrf'] = session.get('family_csrf', '')
        return jsonify(body)

    @bp.get('/api/v2/reports/supertag/leads/<uuid:lead_id>/contact')
    @login_required_api
    def supertag_lead_contact(lead_id):
        selected = _selection()
        if selected['role'] == 'viewer':
            abort(403)
        if not leads_ready():
            abort(404)
        found = _rows(f'''SELECT l.display_name_enc,l.email_enc,l.phone_enc,l.fields_enc FROM {LEADS_TABLE} l
            JOIN cadu_reports_supertag_sites s ON s.id=l.site_id
            WHERE l.id=%s AND s.client_id=%s AND s.revoked_at IS NULL AND l.expires_at>NOW()''', (str(lead_id), selected['client_id']))
        if not found:
            abort(404)
        row = found[0]
        response = jsonify(name=decrypt(row['display_name_enc']) or '', email=decrypt(row['email_enc']) or '',
                           phone=decrypt(row['phone_enc']) or '', fields=decrypt(row['fields_enc'], as_json=True) or {})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @bp.delete('/api/v2/reports/supertag/leads/<uuid:lead_id>')
    @login_required_api
    def supertag_lead_delete(lead_id):
        selected = _selection()
        _write_guard(selected)
        if not leads_ready():
            abort(404)
        deleted = _rows(f'''DELETE FROM {LEADS_TABLE} l USING cadu_reports_supertag_sites s
            WHERE l.id=%s AND s.id=l.site_id AND s.client_id=%s RETURNING l.id''', (str(lead_id), selected['client_id']))
        if not deleted:
            abort(404)
        get_db().commit()
        return jsonify(deleted=True)

    @bp.get('/api/v2/reports/supertag/sites/<uuid:site_id>/conversion-rules')
    @login_required_api
    def supertag_conversion_rules(site_id):
        selected = _selection()
        found = _rows('''SELECT id,config FROM cadu_reports_supertag_sites
            WHERE id=%s AND client_id=%s AND revoked_at IS NULL''', (str(site_id), selected['client_id']))
        if not found:
            abort(404)
        site = found[0]
        config = site.get('config') or {}
        saved = config.get('conversion_rules') or []
        return jsonify(rules=saved, defaults=list(DEFAULT_CONVERSION_RULES),
                       defaults_active=not saved and config.get('conversion_defaults', True) is not False,
                       conversion_defaults=config.get('conversion_defaults', True) is not False,
                       suggestions=conversion_suggestions(site),
                       form_capture={**public_form_capture(config), 'confirm': (config.get('form_capture') or {}).get('confirm', 'conversion')})
