"""Per-client settings of the alert center: which rules run, which e-mail, and the few thresholds that are worth tuning.

Defaults live in the rules themselves (reports_alert_rules); a missing row means "default", so a new client needs no setup. The
client-wide value of one conversion (what makes "estimated impact" an honest number) is stored under the reserved rule `_client`.
"""
from .reports_alert_rules import ANOMALY_CHANGE_PERCENT, CONSECUTIVE_FAILURES, CONVERSION_DROP_PERCENT, SILENT_AFTER_HOURS

CLIENT_RULE = '_client'
MAX_CONVERSION_VALUE = 10_000_000

# The only thresholds exposed: each one maps to a keyword of the pure rule. Anything else stays a product decision.
TUNABLE = {
    'page_down': {'label': 'Verificações seguidas com falha', 'unit': 'vezes', 'default': CONSECUTIVE_FAILURES, 'min': 2, 'max': 10, 'step': 1},
    'collection_absent': {'label': 'Horas sem eventos da Super Tag', 'unit': 'horas', 'default': SILENT_AFTER_HOURS, 'min': 1, 'max': 72, 'step': 1},
    'conversion_drop': {'label': 'Queda mínima da conversão da página', 'unit': '%', 'default': CONVERSION_DROP_PERCENT, 'min': 10, 'max': 90, 'step': 5},
    'traffic_anomaly': {'label': 'Variação mínima das sessões', 'unit': '%', 'default': ANOMALY_CHANGE_PERCENT, 'min': 10, 'max': 90, 'step': 5},
    'conversion_anomaly': {'label': 'Variação mínima das conversões', 'unit': '%', 'default': ANOMALY_CHANGE_PERCENT, 'min': 10, 'max': 90, 'step': 5},
}


def load(rows_fn, client_id):
    """{rule: {enabled, notify, params}} for the client; rules without a row are absent (= defaults)."""
    return {row['rule']: {'enabled': row['enabled'], 'notify': row['notify'], 'params': row['params'] or {}}
            for row in rows_fn('SELECT rule,enabled,notify,params FROM cadu_reports_alert_settings WHERE client_id=%s', (client_id,))}


def is_enabled(settings, rule):
    return settings.get(rule, {}).get('enabled', True)


def threshold(settings, rule):
    """The client's threshold for the rule, or its default; None for rules without a tunable threshold."""
    meta = TUNABLE.get(rule)
    if not meta:
        return None
    value = settings.get(rule, {}).get('params', {}).get('threshold')
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and meta['min'] <= value <= meta['max'] else meta['default']


def conversion_value(settings):
    value = settings.get(CLIENT_RULE, {}).get('params', {}).get('conversion_value')
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def disabled_rules(settings):
    return frozenset(rule for rule, row in settings.items() if rule != CLIENT_RULE and not row['enabled'])


def describe(catalog, settings):
    """The catalog the screen edits: every rule with its current switches and its tunable threshold."""
    items = []
    for rule in catalog:
        key = rule['rule']
        meta = TUNABLE.get(key)
        items.append({**rule, 'enabled': is_enabled(settings, key), 'notify': settings.get(key, {}).get('notify', True),
                      'tunable': {**meta, 'value': threshold(settings, key)} if meta else None})
    return items


def parse(payload, known_rules):
    """Validated changes from a request body: {rule: {enabled?, notify?, threshold?}} and the optional conversion value. Raises ValueError."""
    changes = {}
    for rule, change in (payload.get('rules') or {}).items():
        if rule not in known_rules or not isinstance(change, dict):
            raise ValueError('Regra desconhecida.')
        clean = {}
        for key in ('enabled', 'notify'):
            if key in change:
                if not isinstance(change[key], bool):
                    raise ValueError('Ligado e e-mail aceitam só verdadeiro ou falso.')
                clean[key] = change[key]
        if 'threshold' in change:
            meta, value = TUNABLE.get(rule), change['threshold']
            if not meta or isinstance(value, bool) or not isinstance(value, (int, float)) or not meta['min'] <= value <= meta['max']:
                raise ValueError(f"Limite fora do intervalo de {meta['min']} a {meta['max']}." if meta else 'Esta regra não tem limite ajustável.')
            clean['threshold'] = value
        changes[rule] = clean
    value = payload.get('conversion_value', ...)
    if value is not ...:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= MAX_CONVERSION_VALUE):
            raise ValueError('O valor por conversão deve ser maior que zero.')
    return changes, value


_SAVE_RULE_SQL = '''
    INSERT INTO cadu_reports_alert_settings (client_id,rule,enabled,notify,params,updated_by)
    VALUES (%(client)s,%(rule)s,COALESCE(%(enabled)s,TRUE),COALESCE(%(notify)s,TRUE),
        CASE WHEN %(threshold)s::numeric IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('threshold',%(threshold)s::numeric) END,%(user)s)
    ON CONFLICT (client_id,rule) DO UPDATE SET enabled=COALESCE(%(enabled)s,cadu_reports_alert_settings.enabled),
        notify=COALESCE(%(notify)s,cadu_reports_alert_settings.notify),
        params=CASE WHEN %(threshold)s::numeric IS NULL THEN cadu_reports_alert_settings.params
                    ELSE cadu_reports_alert_settings.params || jsonb_build_object('threshold',%(threshold)s::numeric) END,
        updated_by=%(user)s,updated_at=NOW() RETURNING rule'''
_SAVE_VALUE_SQL = '''
    INSERT INTO cadu_reports_alert_settings (client_id,rule,params,updated_by) VALUES (%(client)s,%(rule)s,jsonb_build_object('conversion_value',%(value)s::numeric),%(user)s)
    ON CONFLICT (client_id,rule) DO UPDATE SET params=jsonb_build_object('conversion_value',%(value)s::numeric),updated_by=%(user)s,updated_at=NOW() RETURNING rule'''


def save(rows_fn, client_id, user_id, changes, conversion_value_change=...):
    for rule, change in changes.items():
        rows_fn(_SAVE_RULE_SQL, {'client': client_id, 'rule': rule, 'enabled': change.get('enabled'), 'notify': change.get('notify'),
                                 'threshold': change.get('threshold'), 'user': user_id})
    if conversion_value_change is None:
        rows_fn('DELETE FROM cadu_reports_alert_settings WHERE client_id=%s AND rule=%s RETURNING rule', (client_id, CLIENT_RULE))
    elif conversion_value_change is not ...:
        rows_fn(_SAVE_VALUE_SQL, {'client': client_id, 'rule': CLIENT_RULE, 'value': conversion_value_change, 'user': user_id})
