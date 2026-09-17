"""Bounded, review-only visual extraction for report sources."""
import base64
import json
import os

from .report_prompts import PROMPTS, PROMPT_VERSION
from .report_review import UNITS

MODEL = os.getenv('CONNECT_REPORT_EXTRACT_MODEL', 'openai/gpt-5-nano')
MAX_SUGGESTED_METRICS = 60
MAX_EXTRACTION_TOKENS = 3200


def extraction_messages(source, document):
    image = base64.b64encode(bytes(source['image_bytes'])).decode('ascii')
    context = {key: document.get(key, '') for key in ('campaign_name', 'platform', 'external_account_id', 'external_campaign_id', 'start_date', 'end_date', 'objective', 'goals')}
    instruction = '''Retorne JSON: {"source_id":number,"observations":[],"metrics":[{"name":"","raw":"","unit":"count|BRL|USD|percent|seconds","definition":"","scope":"","evidence":"","confidence":"high|medium|low"}],"questions":[]}. Métricas exigem evidência textual visível; máximo 60.'''
    return [
        {'role': 'system', 'content': PROMPTS['extract'] + '\n' + instruction},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': f'prompt_version={PROMPT_VERSION}; contexto autorizado={json.dumps(context, ensure_ascii=False)}; source_id={source["id"]}'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + image}},
        ]},
    ]


def normalize_suggestion(payload, source_id):
    if not isinstance(payload, dict) or payload.get('source_id') != source_id:
        raise ValueError('A sugestão não corresponde à fonte solicitada.')
    metrics = payload.get('metrics', [])
    if not isinstance(metrics, list) or len(metrics) > MAX_SUGGESTED_METRICS:
        raise ValueError('A sugestão excede o limite de indicadores.')
    clean = []
    for metric in metrics:
        if not isinstance(metric, dict) or metric.get('unit') not in UNITS:
            raise ValueError('A sugestão contém unidade inválida.')
        row = {key: str(metric.get(key, '')).strip()[:1000] for key in ('name', 'raw', 'definition', 'scope', 'evidence')}
        if not all(row[key] for key in ('name', 'definition', 'scope', 'evidence')):
            raise ValueError('A sugestão não preservou evidência suficiente.')
        row['unit'] = metric['unit']
        row['confidence'] = metric.get('confidence') if metric.get('confidence') in ('high', 'medium', 'low') else 'low'
        clean.append(row)
    return {'source_id': source_id, 'metrics': clean,
            'observations': [str(item)[:1000] for item in payload.get('observations', []) if isinstance(item, str)][:30],
            'questions': [str(item)[:1000] for item in payload.get('questions', []) if isinstance(item, str)][:20]}


def extract_suggestion(source, document, *, complete):
    """Calls a supplied model client; caller owns credits, persistence and review."""
    result = complete(extraction_messages(source, document), model=MODEL, max_tokens=MAX_EXTRACTION_TOKENS,
                      temperature=0, response_format={'type': 'json_object'})
    message = result.get('message', {}) if isinstance(result, dict) else {}
    content = message.get('content', message) if isinstance(message, dict) else message
    if not isinstance(content, str):
        raise ValueError('O modelo não retornou uma sugestão legível.')
    suggestion = normalize_suggestion(json.loads(content), source['id'])
    suggestion['_usage'] = result.get('usage') or {}
    suggestion['_model'] = result.get('model') or MODEL
    return suggestion
