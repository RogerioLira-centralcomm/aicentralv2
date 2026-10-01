"""Pure alert rules: look at observations, return findings. No database, no side effects.

An alert is a *confirmed* condition, not a single bad reading: availability needs consecutive failures, a silent tag
needs a baseline that proves it used to send events, and a conversion drop needs a reliable sample in both periods.
"""
from .reports_page_identity import canonical_page
from .reports_page_metrics import MIN_RELIABLE_SESSIONS

CONSECUTIVE_FAILURES = 2
SILENT_AFTER_HOURS = 6
MIN_BASELINE_EVENTS = 50
CONVERSION_DROP_PERCENT = 30.0
RULES = {
    'page_down': {'severity': 'high', 'title': 'Página indisponível',
                  'when': f'A página falhou em {CONSECUTIVE_FAILURES} verificações seguidas do monitor.'},
    'collection_absent': {'severity': 'medium', 'title': 'Super Tag sem enviar eventos',
                          'when': f'Nenhum evento há {SILENT_AFTER_HOURS} horas ou mais em um site que enviou ao menos {MIN_BASELINE_EVENTS} eventos nos 7 dias anteriores.'},
    'conversion_drop': {'severity': 'low', 'title': 'Queda na conversão da página',
                        'when': f'Queda relativa de {CONVERSION_DROP_PERCENT:.0f}% ou mais na taxa de conversão da sessão, '
                                f'7 dias contra os 7 anteriores, com ao menos {MIN_RELIABLE_SESSIONS} sessões nos dois.'},
}


def _finding(rule, subject_key, summary, evidence, page_path=None):
    meta = RULES[rule]
    return {'rule': rule, 'subject_key': subject_key, 'severity': meta['severity'], 'title': meta['title'],
            'summary': summary, 'evidence': evidence, 'page_path': page_path}


def page_down_findings(checks):
    """checks: newest first, each {checked_at, pages:[{host,path,status,http_status,detail}]}.

    A page alerts when its most recent CONSECUTIVE_FAILURES readings are all not-online. A reading is skipped for
    pages that a check did not include, so a flow edit never fabricates an outage.
    """
    history = {}
    for check in checks:
        for page in check.get('pages') or []:
            key = canonical_page(page.get('host'), page.get('path'))
            history.setdefault(key, []).append({**page, 'checked_at': check['checked_at']})
    findings = []
    for (host, path), readings in history.items():
        recent = readings[:CONSECUTIVE_FAILURES]
        if len(recent) < CONSECUTIVE_FAILURES or any(item.get('status') == 'online' for item in recent):
            continue
        failing = 0
        for item in readings:
            if item.get('status') == 'online':
                break
            failing += 1
        latest = recent[0]
        findings.append(_finding(
            'page_down', path,
            f'{host}{path} falhou em {failing} verificações seguidas.',
            [{'label': 'Estado', 'value': 'Indisponível' if latest.get('status') == 'offline' else 'Degradada', 'unit': 'text'},
             {'label': 'Falhas seguidas', 'value': failing, 'unit': 'count'},
             {'label': 'Código HTTP', 'value': latest.get('http_status'), 'unit': 'count'},
             {'label': 'Detalhe', 'value': latest.get('detail') or '—', 'unit': 'text'}], page_path=path))
    return findings


def collection_absent_findings(site_label, events_last_7d_before, hours_since_last_event):
    """events_last_7d_before: events in the 7 days before the silence started; None hours = no event ever."""
    if hours_since_last_event is None or events_last_7d_before < MIN_BASELINE_EVENTS or hours_since_last_event < SILENT_AFTER_HOURS:
        return []
    return [_finding('collection_absent', '',
                     f'{site_label} não recebe eventos da Super Tag há {int(hours_since_last_event)} horas, mas costumava receber.',
                     [{'label': 'Horas sem eventos', 'value': int(hours_since_last_event), 'unit': 'count'},
                      {'label': 'Eventos nos 7 dias anteriores', 'value': events_last_7d_before, 'unit': 'count'}])]


def conversion_drop_findings(pages):
    """pages: [{path, current:{sessions,session_conversion_rate}, previous:{...}}]."""
    findings = []
    for page in pages:
        now, before = page['current'], page['previous']
        if min(now['sessions'], before['sessions']) < MIN_RELIABLE_SESSIONS:
            continue
        a, b = now.get('session_conversion_rate'), before.get('session_conversion_rate')
        if a is None or not b or 100 * (b - a) / b < CONVERSION_DROP_PERCENT:
            continue
        findings.append(_finding(
            'conversion_drop', page['path'], f"A conversão de {page['path']} caiu em relação à semana anterior.",
            [{'label': 'Últimos 7 dias', 'value': a, 'unit': 'percent'}, {'label': '7 dias anteriores', 'value': b, 'unit': 'percent'},
             {'label': 'Variação relativa', 'value': round(100 * (a - b) / b, 1), 'unit': 'percent'},
             {'label': 'Sessões atuais', 'value': now['sessions'], 'unit': 'count'}], page_path=page['path']))
    return findings
