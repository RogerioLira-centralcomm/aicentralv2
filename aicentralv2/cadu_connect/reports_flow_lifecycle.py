"""Lifecycle of a flow node: a step can exist in the plan long before its page does."""
import math
import re

from werkzeug.exceptions import BadRequest

from .reports_flow_validation import NODE_STATUSES, has_real_path, is_measured, node_status  # noqa: F401

SPEC_LIMITS = {
    'goal': 500, 'suggested_path': 500, 'headline': 200, 'content': 2000, 'cta': 200,
    'notes': 2000, 'owner': 120, 'due_date': 10, 'references': 2000,
}
DUE_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


FORECAST_LIMITS = {'visits': 1e9, 'cost': 1e12, 'value': 1e9, 'rate': 100}


def normalize_forecast(forecast, fields):
    """Plan numbers for the forecast layer; blank values are dropped, invalid ones rejected."""
    if forecast is None:
        return None
    if not isinstance(forecast, dict):
        raise BadRequest('A previsão precisa ser um objeto.')
    clean = {}
    for field in fields:
        value = forecast.get(field)
        if value is None or value == '':
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not 0 <= value <= FORECAST_LIMITS[field]:
            raise BadRequest('Use números positivos na previsão; taxas vão de 0 a 100.')
        clean[field] = round(float(value), 4)
    return clean or None


def measured_nodes(nodes):
    return [node for node in nodes or [] if is_measured(node)]


def normalize_spec(spec):
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise BadRequest('A especificação do nó precisa ser um objeto.')
    clean = {}
    for field, limit in SPEC_LIMITS.items():
        value = spec.get(field)
        if value is None or value == '':
            continue
        if not isinstance(value, str) or len(value) > limit:
            raise BadRequest('Especificação de nó inválida.')
        if field == 'due_date' and not DUE_DATE.fullmatch(value):
            raise BadRequest('Use o prazo no formato AAAA-MM-DD.')
        if field == 'suggested_path':
            value = '/' + value.strip().lstrip('/')
        clean[field] = value
    return clean or None
