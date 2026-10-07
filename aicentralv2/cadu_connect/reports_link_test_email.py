"""E-mail of a Link Tester result: one template per analysis, always with the screenshot and the public report link."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from flask import render_template
from werkzeug.exceptions import BadRequest

QUESTIONS = {'destination': 'O clique do anúncio chega ao site?', 'media': 'A conversão desta página será medida?',
             'agentic': 'Agentes de IA conseguem ler este site?'}
KINDS = {  # kind → (template, label, accent, soft background, subject)
    'destination': ('link-test-destination.html', 'Destino e redirecionamentos', '#3974bd', '#edf5ff', 'Diagnóstico do destino do link'),
    'media': ('link-test-media.html', 'Medição de mídia', '#0e9384', '#e8f7f5', 'Diagnóstico de medição da página'),
    'agentic': ('link-test-agentic.html', 'Presença para agentes de IA', '#7a5af8', '#f1edff', 'Diagnóstico de presença para agentes de IA'),
}
EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$')


def valid_recipient(value):
    value = str(value or '').strip()
    if not EMAIL.match(value) or len(value) > 254:
        raise BadRequest('Informe um e-mail válido.')
    return value


def render(run, base_url, note=''):
    """(subject, html) for a saved run row (``reports_link_tester.detail``)."""
    result = run['result'] or {}
    kind = run['mode'] if run['mode'] in KINDS else 'destination'
    template, label, accent, soft, subject = KINDS[kind]
    base_url = base_url.rstrip('/')
    token = run['public_token']
    screenshot = (result.get('evidence') or {}).get('screenshot')
    created = run['created_at']
    html = render_template(f'emails/externos/{template}', kind=kind, kind_label=label, accent=accent, accent_soft=soft, base_url=base_url,
                           headline=QUESTIONS[kind], summary=result.get('summary') or '', score=int(run['score'] or 0),
                           status_label=result.get('status_label') or label, url=run['final_url'], highlights=result.get('highlights') or [],
                           screenshot=f'{base_url}{screenshot}' if screenshot else None, report_url=f'{base_url}/connect/public/link-tests/{token}',
                           preheader=f'{label}: {int(run["score"] or 0)}/100 · {urlparse(run["final_url"]).hostname}',
                           created_at=created.strftime('%d/%m/%Y %H:%M') if hasattr(created, 'strftime') else str(created),
                           note=str(note or '').strip()[:500])
    return f'{subject} · {int(run["score"] or 0)}/100', html
