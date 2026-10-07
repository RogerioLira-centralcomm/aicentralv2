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
INSIGHT_MIN_SESSIONS = 20       # sessions behind one (channel, page) or (campaign, page) reading
INSIGHT_OTHERS_MIN = 20         # sessions of the other channels on the same page, the yardstick for a channel reading
INSIGHT_BOUNCE_PERCENT = 60.0   # share of sessions that leave without a second page
INSIGHT_BOUNCE_GAP = 20.0       # points above the other channels on the same page
INSIGHT_MIN_CONVERTED = 5       # the site needs this many converted sessions before "below average" means anything
INSIGHT_BELOW_RATIO = 0.5       # conversion under this share of the site average
INSIGHT_PER_RULE = 10           # findings kept per insight rule, busiest first
RULES = {
    'page_down': {'channel': 'site', 'kind': 'incident', 'severity': 'high', 'title': 'Página indisponível',
                  'when': f'A página falhou em {CONSECUTIVE_FAILURES} verificações seguidas do monitor.'},
    'collection_absent': {'channel': 'site', 'kind': 'incident', 'severity': 'medium', 'title': 'Super Tag sem enviar eventos',
                          'when': f'Nenhum evento há {SILENT_AFTER_HOURS} horas ou mais em um site que enviou ao menos {MIN_BASELINE_EVENTS} eventos nos 7 dias anteriores.'},
    'conversion_drop': {'channel': 'site', 'kind': 'incident', 'severity': 'low', 'title': 'Queda na conversão da página',
                        'when': f'Queda relativa de {CONVERSION_DROP_PERCENT:.0f}% ou mais na taxa de conversão da sessão, '
                                f'7 dias contra os 7 anteriores, com ao menos {MIN_RELIABLE_SESSIONS} sessões nos dois.'},
    'channel_entry_exit': {'channel': 'journey', 'kind': 'opportunity', 'severity': 'low', 'title': 'Canal entra e sai sem ver outra página',
                           'when': f'Ao menos {INSIGHT_MIN_SESSIONS} sessões de um canal entram por uma página e {INSIGHT_BOUNCE_PERCENT:.0f}% ou mais saem sem ver outra, '
                                   f'{INSIGHT_BOUNCE_GAP:.0f} pontos acima dos demais canais na mesma página (que somam ao menos {INSIGHT_OTHERS_MIN} sessões), 7 dias.'},
    'device_conversion_low': {'channel': 'site', 'kind': 'opportunity', 'severity': 'low', 'title': 'Aparelho ou tela converte abaixo da média',
                              'when': f'Ao menos {MIN_RELIABLE_SESSIONS} sessões num tipo de aparelho ou tamanho de tela, com conversão abaixo de '
                                      f'{INSIGHT_BELOW_RATIO * 100:.0f}% da média do site, que tem ao menos {INSIGHT_MIN_CONVERTED} sessões convertidas, 7 dias.'},
    'campaign_weak_page': {'channel': 'journey', 'kind': 'opportunity', 'severity': 'low', 'title': 'Campanha leva a uma página fraca',
                           'when': f'Ao menos {INSIGHT_MIN_SESSIONS} sessões de uma campanha (utm_campaign) entram por uma página onde {INSIGHT_BOUNCE_PERCENT:.0f}% ou mais saem sem ver outra '
                                   f'e a conversão fica abaixo de {INSIGHT_BELOW_RATIO * 100:.0f}% da média do site, 7 dias.'},
}


def _finding(rule, subject_key, summary, evidence, page_path=None, impact=None):
    """impact: the one number the alerts table shows ({value, unit: percent|text|count, label}); None when there is no single figure."""
    meta = RULES[rule]
    return {'rule': rule, 'subject_key': subject_key, 'severity': meta['severity'], 'title': meta['title'],
            'summary': summary, 'evidence': evidence, 'page_path': page_path, 'channel': meta['channel'], 'kind': meta['kind'], 'impact': impact}


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
             {'label': 'Detalhe', 'value': latest.get('detail') or '—', 'unit': 'text'}], page_path=path,
            impact={'value': f"erro {latest['http_status']}" if latest.get('http_status') else 'sem resposta', 'unit': 'text', 'label': 'página fora do ar'}))
    return findings


def collection_absent_findings(site_label, events_last_7d_before, hours_since_last_event):
    """events_last_7d_before: events in the 7 days before the silence started; None hours = no event ever."""
    if hours_since_last_event is None or events_last_7d_before < MIN_BASELINE_EVENTS or hours_since_last_event < SILENT_AFTER_HOURS:
        return []
    return [_finding('collection_absent', '',
                     f'{site_label} não recebe eventos da Super Tag há {int(hours_since_last_event)} horas, mas costumava receber.',
                     [{'label': 'Horas sem eventos', 'value': int(hours_since_last_event), 'unit': 'count'},
                      {'label': 'Eventos nos 7 dias anteriores', 'value': events_last_7d_before, 'unit': 'count'}],
                     impact={'value': f'{int(hours_since_last_event)} h', 'unit': 'text', 'label': 'sem eventos'})]


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
             {'label': 'Sessões atuais', 'value': now['sessions'], 'unit': 'count'}], page_path=page['path'],
            impact={'value': round(100 * (a - b) / b, 1), 'unit': 'percent', 'label': 'taxa de conversão'}))
    return findings


def _subject(*parts):
    return '|'.join(str(part) for part in parts)[:520]


def _busiest(findings):
    return [item for _, item in sorted(findings, key=lambda pair: -pair[0])[:INSIGHT_PER_RULE]]


def channel_entry_findings(rows, labels):
    """rows: [{origin, path, sessions, single_page}] — sessions that entered each page, by origin group.

    A channel is flagged on a page when it bounces much more than the other channels do on that same page, so a page that
    is weak for everyone is not blamed on one channel."""
    by_path = {}
    for row in rows:
        if row['origin'] == 'unknown':     # the real landing was not captured, so it is neither a channel nor a fair yardstick
            continue
        by_path.setdefault(row['path'], []).append(row)
    found = []
    for path, lines in by_path.items():
        total = sum(int(line['sessions']) for line in lines)
        total_single = sum(int(line['single_page']) for line in lines)
        for line in lines:
            sessions, single = int(line['sessions']), int(line['single_page'])
            others, others_single = total - sessions, total_single - single
            if sessions < INSIGHT_MIN_SESSIONS or others < INSIGHT_OTHERS_MIN:
                continue
            bounce, baseline = 100 * single / sessions, 100 * others_single / others
            if bounce < INSIGHT_BOUNCE_PERCENT or bounce - baseline < INSIGHT_BOUNCE_GAP:
                continue
            label = labels.get(line['origin'], line['origin'])
            found.append((sessions, _finding(
                'channel_entry_exit', _subject(line['origin'], path),
                f'{label} entra por {path} e {bounce:.0f}% das sessões saem sem ver outra página; nos demais canais são {baseline:.0f}%.',
                [{'label': 'Canal', 'value': label, 'unit': 'text'}, {'label': 'Sessões do canal na página', 'value': sessions, 'unit': 'count'},
                 {'label': 'Saem sem ver outra página', 'value': round(bounce, 1), 'unit': 'percent'},
                 {'label': 'Demais canais', 'value': round(baseline, 1), 'unit': 'percent'}], page_path=path,
                impact={'value': round(bounce, 1), 'unit': 'percent', 'label': 'saem sem ver outra página'})))
    return _busiest(found)


def _site_rate(rows):
    overall = next((row for row in rows if row.get('kind') == 'overall'), None)
    if not overall or int(overall['converted']) < INSIGHT_MIN_CONVERTED or int(overall['sessions']) < MIN_RELIABLE_SESSIONS:
        return None
    return 100 * int(overall['converted']) / int(overall['sessions'])


def tech_conversion_findings(rows, labels):
    """rows: [{kind: device|resolution|overall, value, sessions, converted}]; labels maps device classes to names."""
    average = _site_rate(rows)
    if average is None:
        return []
    found = []
    for row in rows:
        if row.get('kind') not in ('device', 'resolution'):
            continue
        sessions, converted = int(row['sessions']), int(row['converted'])
        if sessions < MIN_RELIABLE_SESSIONS:
            continue
        rate = 100 * converted / sessions
        if rate >= average * INSIGHT_BELOW_RATIO:
            continue
        name = labels.get(row['value'], row['value']) if row['kind'] == 'device' else str(row['value']).replace('x', '×')
        what = 'O aparelho' if row['kind'] == 'device' else 'A tela'
        found.append((sessions, _finding(
            'device_conversion_low', _subject(row['kind'], row['value']),
            f'{what} {name} converte {rate:.1f}% das sessões, abaixo da metade da média do site ({average:.1f}%).',
            [{'label': 'Aparelho ou tela', 'value': name, 'unit': 'text'}, {'label': 'Sessões', 'value': sessions, 'unit': 'count'},
             {'label': 'Conversão', 'value': round(rate, 1), 'unit': 'percent'}, {'label': 'Média do site', 'value': round(average, 1), 'unit': 'percent'}],
            impact={'value': round(rate, 1), 'unit': 'percent', 'label': 'conversão'})))
    return _busiest(found)


def campaign_page_findings(rows, overall):
    """rows: [{campaign, path, sessions, single_page, converted}]; overall: the tech rows, only for the site conversion average."""
    average = _site_rate(overall)
    if average is None:
        return []
    found = []
    for row in rows:
        sessions, single, converted = int(row['sessions']), int(row['single_page']), int(row['converted'])
        if sessions < INSIGHT_MIN_SESSIONS:
            continue
        bounce, rate = 100 * single / sessions, 100 * converted / sessions
        if bounce < INSIGHT_BOUNCE_PERCENT or rate >= average * INSIGHT_BELOW_RATIO:
            continue
        found.append((sessions, _finding(
            'campaign_weak_page', _subject(row['campaign'], row['path']),
            f"A campanha {row['campaign']} leva {sessions} sessões a {row['path']}, onde {bounce:.0f}% saem sem ver outra página e {rate:.1f}% convertem.",
            [{'label': 'Campanha', 'value': row['campaign'], 'unit': 'text'}, {'label': 'Sessões na página', 'value': sessions, 'unit': 'count'},
             {'label': 'Saem sem ver outra página', 'value': round(bounce, 1), 'unit': 'percent'},
             {'label': 'Conversão', 'value': round(rate, 1), 'unit': 'percent'}, {'label': 'Média do site', 'value': round(average, 1), 'unit': 'percent'}],
            page_path=row['path'], impact={'value': round(bounce, 1), 'unit': 'percent', 'label': 'saem sem ver outra página'})))
    return _busiest(found)
