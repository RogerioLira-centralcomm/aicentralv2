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


TONE_RANK = {'bad': 0, 'warn': 1}
TONE_COLORS = {'ok': '#12b76a', 'warn': '#f79009', 'bad': '#f04438', 'info': '#3974bd', 'skip': '#98a2b3', 'muted': '#98a2b3'}


def top_issues(report, limit=6):
    """The most serious items across the report, each with its section and the fix when there is one."""
    found = []
    for order, section in enumerate(report.get('sections') or []):
        for block in section['blocks']:
            for item in block.get('items') or []:
                tone = item.get('status') if block['type'] == 'checks' else item.get('tone') if block['type'] == 'list' else None
                if tone in TONE_RANK:
                    found.append({'tone': tone, 'section': section['title'], 'title': item.get('title') or item.get('text'),
                                  'fix': item.get('fix'), 'rank': (TONE_RANK[tone], order)})
    found.sort(key=lambda item: item['rank'])
    seen, unique = set(), []
    for item in found:
        if item['title'] and item['title'] not in seen:
            seen.add(item['title'])
            unique.append(item)
    return unique[:limit], len(found)


def render(run, base_url, note=''):
    """(subject, html) for a run of either source (``reports_link_history.detail``), from the same report as the app."""
    from .reports_link_report import build
    report = build(run)
    header = report['header']
    kind = header['kind'] if header['kind'] in KINDS else 'media'
    template, label, accent, soft, subject = KINDS[kind]
    label = header.get('type_label') or label
    base_url = base_url.rstrip('/')
    token = run.get('public_token')
    report_url = f'{base_url}/connect/public/link-tests/{token}' if token else None
    shots = report['screenshots']
    screenshots = {device: f'{report_url}/screenshot?device={device}' if token and shots.get(device) else None for device in ('desktop', 'mobile')}
    issues, issue_total = top_issues(report)
    created = header.get('created_at')
    score = int(header.get('score') or 0)
    host = urlparse(header.get('url') or '').hostname or ''
    html = render_template(f'emails/externos/{template}', kind=kind, kind_label=label, accent=accent, accent_soft=soft, base_url=base_url,
                           headline=QUESTIONS[kind], summary=header.get('summary') or '', score=score, status_label=header.get('status_label') or label,
                           url=header.get('url'), highlights=header.get('highlights') or [], indicators=report['indicators'][:6], modules=report['modules'][:6],
                           overview=report.get('overview') or {}, issues=issues, issue_total=issue_total, tone_colors=TONE_COLORS,
                           screenshot=screenshots['desktop'], screenshot_mobile=screenshots['mobile'], report_url=report_url,
                           author=header.get('author'), legacy=header.get('source') == 'cadu_php',
                           preheader=f'{label}: {score}/100 · {host}' + (f' · {issue_total} ponto(s) a corrigir' if issue_total else ''),
                           created_at=created.strftime('%d/%m/%Y %H:%M') if hasattr(created, 'strftime') else str(created or ''),
                           note=str(note or '').strip()[:500])
    return f'{subject} · {score}/100 · {host}', html
