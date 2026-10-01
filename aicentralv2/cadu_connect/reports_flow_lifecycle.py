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


SEGMENT_KINDS = {'prospeccao', 'interesses', 'palavras_chave', 'semelhante', 'remarketing', 'base', 'outro'}
OBJECTIVES = {'leads', 'vendas', 'trafego', 'alcance', 'engajamento', 'video', 'mensagens', 'relacionamento'}
CREATIVE_FORMATS = {'imagem', 'video', 'carrossel', 'stories', 'texto', 'mensagem'}
CREATIVE_STATUSES = {'rascunho', 'em_aprovacao', 'aprovado'}
UTM_VALUE = re.compile(r'[A-Za-z0-9_.\-]{1,100}')


def _text(value, limit, message):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise BadRequest(message)
    return ' '.join(value.split())[:limit]


def _item_id(value):
    text = _text(value, 16, 'Identificador de item inválido.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,16}', text):
        raise BadRequest('Identificador de item inválido.')
    return text


def normalize_segment(segment):
    """Who a traffic origin reaches; one segment per origin node."""
    if segment is None:
        return None
    if not isinstance(segment, dict):
        raise BadRequest('A segmentação precisa ser um objeto.')
    name = _text(segment.get('name'), 80, 'Nome de público inválido.')
    kind = segment.get('kind') or 'outro'
    if kind not in SEGMENT_KINDS:
        raise BadRequest('Tipo de público inválido.')
    description = _text(segment.get('description'), 500, 'Descrição de público inválida.')
    if not name and not description:
        return None
    return {key: value for key, value in (('name', name), ('kind', kind), ('description', description)) if value}


def normalize_media(media):
    """Objective, creatives, platform setup checklist and UTM overrides of one origin."""
    if media is None:
        return None
    if not isinstance(media, dict):
        raise BadRequest('A mídia da origem precisa ser um objeto.')
    clean = {}
    objective = media.get('objective') or ''
    if objective:
        if objective not in OBJECTIVES:
            raise BadRequest('Objetivo de campanha inválido.')
        clean['objective'] = objective
    creatives = media.get('creatives') or []
    if not isinstance(creatives, list) or len(creatives) > 20:
        raise BadRequest('Use até 20 criativos por origem.')
    clean_creatives = []
    for creative in creatives:
        if not isinstance(creative, dict) or creative.get('format') not in CREATIVE_FORMATS \
                or creative.get('status', 'rascunho') not in CREATIVE_STATUSES:
            raise BadRequest('Criativo inválido.')
        item = {'id': _item_id(creative.get('id')), 'name': _text(creative.get('name'), 80, 'Criativo inválido.') or 'Criativo',
                'format': creative['format'], 'status': creative.get('status', 'rascunho')}
        message = _text(creative.get('message'), 500, 'Criativo inválido.')
        if message:
            item['message'] = message
        clean_creatives.append(item)
    if clean_creatives:
        clean['creatives'] = clean_creatives
    setup = media.get('setup') or []
    if not isinstance(setup, list) or len(setup) > 20:
        raise BadRequest('Use até 20 itens de setup por origem.')
    clean_setup = []
    for entry in setup:
        if not isinstance(entry, dict):
            raise BadRequest('Item de setup inválido.')
        text = _text(entry.get('text'), 200, 'Item de setup inválido.')
        if text:
            clean_setup.append({'id': _item_id(entry.get('id')), 'text': text, 'done': entry.get('done') is True})
    if clean_setup:
        clean['setup'] = clean_setup
    utm = media.get('utm') or {}
    if not isinstance(utm, dict):
        raise BadRequest('UTM inválida.')
    clean_utm = {}
    for field in ('source', 'medium', 'campaign', 'content'):
        value = utm.get(field)
        if value in (None, ''):
            continue
        if not isinstance(value, str) or not UTM_VALUE.fullmatch(value):
            raise BadRequest('Use letras, números, ponto, hífen ou sublinhado nos parâmetros UTM.')
        clean_utm[field] = value
    if clean_utm:
        clean['utm'] = clean_utm
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
