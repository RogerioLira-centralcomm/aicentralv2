"""Lifecycle of a flow node: a step can exist in the plan long before its page does."""
import re

from werkzeug.exceptions import BadRequest

from .reports_flow_validation import NODE_STATUSES, has_real_path, is_measured, node_status  # noqa: F401

SPEC_LIMITS = {
    'goal': 500, 'suggested_path': 500, 'headline': 200, 'content': 2000, 'cta': 200,
    'notes': 2000, 'owner': 120, 'due_date': 10, 'references': 2000,
}
DUE_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


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
        if field == 'suggested_path' and not value.startswith('/'):
            raise BadRequest('O endereço sugerido precisa começar com /.')
        clean[field] = value
    return clean or None
