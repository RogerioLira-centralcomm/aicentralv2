"""Google Ads recommendations: plain rules over the data the engine v2 script sends, in the order they should be done.

Every item names the object it is about (account, campaign, ad group, keyword, search term, negative), the numbers
that triggered it and one concrete action. Nothing is changed in Google Ads; the person executes, usually through
Google Ads Editor with the CSV this area exports. Rules that cannot be evaluated honestly (no negative snapshot, stale
data) are reported instead of guessed.
"""
from datetime import datetime, timezone

from .reports_page_suggestions import negative_covers, term_is_covered

STALE_HOURS = 48
NEGATIVE_SNAPSHOT_DAYS = 7
MIN_TERM_CLICKS = 10
MIN_KEYWORD_CLICKS = 30
MIN_CAMPAIGN_CLICKS = 30
OPPORTUNITY_CONVERSIONS = 2
LOW_QUALITY_SCORE = 4
BUDGET_USAGE = 0.95
DEVICE_CPA_RATIO = 2.0
MIN_DEVICE_CLICKS = 30
MAX_PER_RULE = 10
PACING_OVER = 1.03
PACING_UNDER = 0.85
CPA_TOLERANCE = 1.2
ROAS_TOLERANCE = 0.8
CONVERSION_GOAL_RISK = 0.9
TARGET_MISMATCH = 0.2
MIN_GOAL_CONVERSIONS = 5

RULES = [
    {'rule': 'cap_reached', 'severity': 'high', 'title': 'Teto de orçamento atingido',
     'when': 'O gasto do mês (ou do período da campanha) já alcançou o teto definido na meta.'},
    {'rule': 'flight_ended', 'severity': 'high', 'title': 'Campanha gastando depois do fim previsto',
     'when': 'A data final da meta já passou e houve gasto nos últimos 3 dias.'},
    {'rule': 'pacing_over', 'severity': 'medium', 'title': 'Ritmo vai estourar o teto do mês',
     'when': f'Projeção do mês (gasto até hoje + média dos últimos 7 dias × dias restantes) {int((PACING_OVER - 1) * 100)}% acima do teto mensal.'},
    {'rule': 'cpa_above_target', 'severity': 'medium', 'title': 'Custo por conversão acima da meta',
     'when': f'CPA do período {int((CPA_TOLERANCE - 1) * 100)}% acima da meta, com ao menos {MIN_GOAL_CONVERSIONS} conversões (ou gasto de 3 metas sem conversão).'},
    {'rule': 'roas_below_target', 'severity': 'medium', 'title': 'ROAS abaixo da meta',
     'when': f'ROAS do período abaixo de {int(ROAS_TOLERANCE * 100)}% da meta.'},
    {'rule': 'conversion_goal_risk', 'severity': 'medium', 'title': 'Meta de conversões do mês em risco',
     'when': f'Projeção de conversões do mês abaixo de {int(CONVERSION_GOAL_RISK * 100)}% da meta mensal.'},
    {'rule': 'pacing_under', 'severity': 'low', 'title': 'Orçamento sobrando no mês',
     'when': f'Projeção abaixo de {int(PACING_UNDER * 100)}% do teto mensal, com conversões dentro da meta de CPA.'},
    {'rule': 'target_mismatch', 'severity': 'low', 'title': 'Meta do Google Ads diferente da meta da equipe',
     'when': f'CPA desejado configurado no Google Ads difere mais de {int(TARGET_MISMATCH * 100)}% da meta registrada no Reports.'},
    {'rule': 'script_stale', 'severity': 'high', 'title': 'Script do Google Ads sem enviar dados',
     'when': f'Nenhuma execução do script recebida há mais de {STALE_HOURS} horas.'},
    {'rule': 'negative_conflict', 'severity': 'high', 'title': 'Negativa bloqueando palavra-chave ativa',
     'when': 'Uma palavra negativa da mesma campanha, grupo ou lista compartilhada cobre o texto de uma palavra-chave que recebeu impressões no período.'},
    {'rule': 'data_incomplete', 'severity': 'medium', 'title': 'Última coleta incompleta',
     'when': 'A execução mais recente terminou por tempo ou teve conjuntos truncados ou com erro.'},
    {'rule': 'negative_candidate', 'severity': 'medium', 'title': 'Termo para negativar',
     'when': f'Termo de pesquisa ainda não adicionado nem excluído, com ao menos {MIN_TERM_CLICKS} cliques, nenhuma conversão e não coberto por negativa.'},
    {'rule': 'keyword_waste', 'severity': 'medium', 'title': 'Palavra-chave com gasto e sem conversão',
     'when': f'Palavra-chave com ao menos {MIN_KEYWORD_CLICKS} cliques e nenhuma conversão no período.'},
    {'rule': 'campaign_without_conversion', 'severity': 'medium', 'title': 'Campanha com cliques e sem conversão',
     'when': f'Campanha com ao menos {MIN_CAMPAIGN_CLICKS} cliques e nenhuma conversão registrada no Google Ads.'},
    {'rule': 'budget_limited', 'severity': 'medium', 'title': 'Campanha que converte limitada pelo orçamento',
     'when': f'Gasto médio diário de {int(BUDGET_USAGE * 100)}% ou mais do orçamento, com custo por conversão igual ou menor que o da conta.'},
    {'rule': 'add_keyword', 'severity': 'low', 'title': 'Termo que converte para virar palavra-chave',
     'when': f'Termo de pesquisa ainda não adicionado, com {OPPORTUNITY_CONVERSIONS} ou mais conversões.'},
    {'rule': 'low_quality_score', 'severity': 'low', 'title': 'Índice de Qualidade baixo',
     'when': f'Palavra-chave com Índice de Qualidade até {LOW_QUALITY_SCORE} e ao menos {MIN_TERM_CLICKS} cliques.'},
    {'rule': 'device_cpa', 'severity': 'low', 'title': 'Dispositivo com custo por conversão alto',
     'when': f'Dispositivo com ao menos {MIN_DEVICE_CLICKS} cliques e custo por conversão {DEVICE_CPA_RATIO:.0f}× o da conta, ou sem conversões.'},
    {'rule': 'negatives_unknown', 'severity': 'low', 'title': 'Lista de negativas desatualizada',
     'when': f'Sem leitura completa das palavras negativas nos últimos {NEGATIVE_SNAPSHOT_DAYS} dias; termos para negativar não são sugeridos sem ela.'},
]
_RULE = {item['rule']: item for item in RULES}
_ORDER = {'high': 0, 'medium': 1, 'low': 2}
DATASET_LABELS = {'campaign_metrics': 'campanhas', 'campaign_settings': 'configurações', 'ad_group_metrics': 'grupos',
                  'device_metrics': 'dispositivos', 'landing_page_metrics': 'páginas de destino', 'keyword_metrics': 'palavras-chave',
                  'search_term_metrics': 'termos de pesquisa', 'negative_keywords': 'negativas'}
DATASET_STATUS = {'truncated': 'cortado no limite de linhas', 'error': 'com erro', 'skipped': 'não rodou por falta de tempo'}
DEVICE_LABELS = {'MOBILE': 'Celular', 'DESKTOP': 'Computador', 'TABLET': 'Tablet', 'CONNECTED_TV': 'TV conectada', 'OTHER': 'Outro'}


def _num(value):
    return float(value or 0)


def _item(rule, key, obj, summary, action, impact_kind='cost', impact=0.0, evidence=(), link=None, proposal=None):
    meta = _RULE[rule]
    return {'id': f'{rule}:{key}', 'rule': rule, 'severity': meta['severity'], 'title': meta['title'], 'object': obj,
            'summary': summary, 'action': action, 'impact': {'kind': impact_kind, 'value': round(float(impact), 2)},
            'evidence': list(evidence), 'link': link, 'proposal': proposal}


def _proposal(op, account_id, target, label, params=None, expect=None):
    """The change the Ações script can apply for a recommendation; the Reports validates it again before queueing."""
    return {'op': op, 'account_id': account_id, 'target': {k: str(v) for k, v in target.items() if v not in (None, '')},
            'params': params or {}, 'expect': expect or {}, 'label': label}


def _campaign_pause(campaign, label):
    if campaign.get('status') != 'ENABLED':
        return None
    return _proposal('campaign.pause', campaign['account_id'], {'campaign_id': campaign['campaign_external_id']},
                     f"{label} “{campaign['campaign_name']}”", expect={'status': 'ENABLED'})


def _budget(campaign, amount):
    """New daily budget for a campaign with its own budget; shared budgets are changed in the shared library."""
    budget = campaign.get('budget')
    if not budget or campaign.get('budget_shared') or amount <= 0 or round(amount, 2) == round(float(budget), 2):
        return None
    return _proposal('campaign.set_budget', campaign['account_id'], {'campaign_id': campaign['campaign_external_id']},
                     f"Orçamento diário de “{campaign['campaign_name']}”: {_br(float(budget))} → {_br(amount)}",
                     params={'amount': round(amount, 2)}, expect={'budget_micros': int(round(float(budget) * 1e6))})


def _age_hours(value, now):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (now - value).total_seconds() / 3600


def term_action(term, negatives, negatives_known):
    """What to do with one search term row; the order of the checks is the order of the decision."""
    status = term.get('status') or 'NONE'
    if status == 'EXCLUDED':
        return 'excluded'
    if status in ('ADDED', 'ADDED_EXCLUDED'):
        return 'added'
    if negatives_known and term_is_covered(term, negatives):
        return 'covered'
    if _num(term.get('conversions')) >= OPPORTUNITY_CONVERSIONS:
        return 'add_keyword'
    if int(term.get('clicks') or 0) >= MIN_TERM_CLICKS and _num(term.get('conversions')) == 0:
        return 'negate' if negatives_known else 'review'
    return 'keep'


def keyword_conflicts(keywords, negatives):
    """Negatives that would block an active keyword's own text in the same scope."""
    found = []
    for keyword in keywords:
        probe = {'account_id': keyword['account_id'], 'campaign_external_id': keyword['campaign_external_id'],
                 'ad_group_external_id': keyword['ad_group_external_id'], 'search_term': keyword['keyword_text']}
        for negative in negatives:
            if negative['account_id'] != keyword['account_id']:
                continue
            level = negative['level']
            applies = (level == 'campaign' and negative['campaign_external_id'] == probe['campaign_external_id']) or \
                      (level == 'ad_group' and negative['ad_group_external_id'] == probe['ad_group_external_id']) or \
                      (level == 'shared_list' and probe['campaign_external_id'] in (negative['attached_campaign_ids'] or []))
            if applies and negative_covers(probe['search_term'], negative['keyword_text'], negative['match_type']):
                found.append({'keyword': keyword, 'negative': negative})
                break
    return found


def build_recommendations(*, accounts, campaigns, terms, keywords, devices, negatives, totals, now=None):
    """All recommendations for the period, highest priority and largest impact first."""
    now = now or datetime.now(timezone.utc)
    items = []
    for account in accounts:
        age = _age_hours(account.get('last_run_at'), now)
        if age is None or age > STALE_HOURS:
            items.append(_item('script_stale', account['id'], {'kind': 'account', 'label': account['name']},
                               'Nenhuma execução recebida.' if age is None else f'Última execução há {int(age // 24)} dias e {int(age % 24)} horas.',
                               'Abra o Google Ads → Ferramentas → Scripts, confira a autorização e a programação diária do script do Cadu.',
                               'none', 0, link={'tab': 'overview'}))
        problems = [d for d in (account.get('datasets') or []) if d.get('status') in ('truncated', 'error', 'skipped')]
        if account.get('timed_out') or problems:
            names = ', '.join(f"{DATASET_LABELS.get(d['name'], d['name'])} ({DATASET_STATUS[d['status']]})" for d in problems) or 'execução terminou por tempo'
            items.append(_item('data_incomplete', account['id'], {'kind': 'account', 'label': account['name']},
                               f'Conjuntos afetados: {names}.', 'Reduza a janela ou o volume no script, ou rode-o em horário de menor uso; os números desta área podem estar incompletos.',
                               'none', 0, link={'tab': 'overview'}))
    known_accounts = {account['id'] for account in accounts if (_age_hours(account.get('negatives_at'), now) or 1e9) <= NEGATIVE_SNAPSHOT_DAYS * 24}
    for account in accounts:
        if account['id'] not in known_accounts:
            items.append(_item('negatives_unknown', account['id'], {'kind': 'account', 'label': account['name']},
                               'As negativas não foram lidas por completo recentemente.', 'Deixe o script terminar uma execução completa (o conjunto de negativas é o último a rodar).',
                               'none', 0, link={'tab': 'negatives'}))
    account_cpa = _num(totals.get('cost')) / _num(totals['conversions']) if _num(totals.get('conversions')) else None

    for conflict in keyword_conflicts([k for k in keywords if int(k.get('impressions') or 0) > 0], negatives)[:MAX_PER_RULE]:
        keyword, negative = conflict['keyword'], conflict['negative']
        scope = negative.get('shared_set_name') or negative.get('ad_group_name') or negative.get('campaign_name')
        items.append(_item('negative_conflict', f"{keyword['account_id']}:{keyword['criterion_external_id']}",
                           {'kind': 'keyword', 'label': keyword['keyword_text'], 'campaign': keyword['campaign_name'], 'ad_group': keyword['ad_group_name']},
                           f"A negativa “{negative['keyword_text']}” ({negative['match_type'].lower()}, {scope}) cobre esta palavra-chave.",
                           'Remova ou restrinja a negativa, ou pause a palavra-chave se o bloqueio for intencional.',
                           'cost', _num(keyword.get('cost')), [('Negativa', negative['keyword_text']), ('Nível', negative['level'])], {'tab': 'negatives'},
                           _proposal('negative.remove', negative['account_id'],
                                     {'level': negative['level'], 'campaign_id': negative.get('campaign_external_id'),
                                      'ad_group_id': negative.get('ad_group_external_id'), 'shared_set_id': negative.get('shared_set_external_id')},
                                     f"Remover a negativa “{negative['keyword_text']}” de {scope}",
                                     params={'text': negative['keyword_text'], 'match_type': negative['match_type']})))

    candidates = []
    for term in terms:
        action = term_action(term, negatives, term['account_id'] in known_accounts)
        if action == 'negate':
            candidates.append(term)
        elif action == 'add_keyword':
            items.append(_item('add_keyword', f"{term['account_id']}:{term['ad_group_external_id']}:{term['term_hash']}",
                               {'kind': 'search_term', 'label': term['search_term'], 'campaign': term['campaign_name'], 'ad_group': term['ad_group_name']},
                               f"{_num(term['conversions']):.0f} conversões com {int(term['clicks'])} cliques, ainda sem palavra-chave própria.",
                               'Adicione como palavra-chave de correspondência exata neste grupo para controlar lance e anúncio.',
                               'conversions', _num(term['conversions']), link={'tab': 'search_terms', 'filter': 'add_keyword'},
                               proposal=_proposal('keyword.add', term['account_id'],
                                                  {'ad_group_id': term['ad_group_external_id'], 'campaign_id': term['campaign_external_id']},
                                                  f"Adicionar [{term['search_term']}] em “{term['ad_group_name']}”",
                                                  params={'text': term['search_term'], 'match_type': 'EXACT'})))
    for term in sorted(candidates, key=lambda row: -_num(row.get('cost')))[:MAX_PER_RULE]:
        items.append(_item('negative_candidate', f"{term['account_id']}:{term['ad_group_external_id']}:{term['term_hash']}",
                           {'kind': 'search_term', 'label': term['search_term'], 'campaign': term['campaign_name'], 'ad_group': term['ad_group_name']},
                           f"{int(term['clicks'])} cliques e nenhuma conversão.",
                           'Negative como correspondência exata na campanha (ou frase, se a intenção inteira não serve).',
                           'cost', _num(term.get('cost')), link={'tab': 'search_terms', 'filter': 'negate'},
                           proposal=_proposal('negative.add', term['account_id'], {'level': 'campaign', 'campaign_id': term['campaign_external_id']},
                                              f"Negativar [{term['search_term']}] em “{term['campaign_name']}”",
                                              params={'text': term['search_term'], 'match_type': 'EXACT'})))

    for keyword in sorted((k for k in keywords if int(k.get('clicks') or 0) >= MIN_KEYWORD_CLICKS and _num(k.get('conversions')) == 0),
                          key=lambda row: -_num(row.get('cost')))[:MAX_PER_RULE]:
        items.append(_item('keyword_waste', f"{keyword['account_id']}:{keyword['criterion_external_id']}",
                           {'kind': 'keyword', 'label': keyword['keyword_text'], 'campaign': keyword['campaign_name'], 'ad_group': keyword['ad_group_name']},
                           f"{int(keyword['clicks'])} cliques, nenhuma conversão.", 'Revise os termos que ela aciona; restrinja a correspondência ou pause.',
                           'cost', _num(keyword.get('cost')), link={'tab': 'keywords'},
                           proposal=_proposal('keyword.pause', keyword['account_id'],
                                              {'ad_group_id': keyword['ad_group_external_id'], 'keyword_id': keyword['criterion_external_id'],
                                               'campaign_id': keyword.get('campaign_external_id')},
                                              f"Pausar a palavra-chave “{keyword['keyword_text']}” em “{keyword['ad_group_name']}”",
                                              expect={'status': 'ENABLED'}) if keyword.get('status') == 'ENABLED' else None))
    for keyword in sorted((k for k in keywords if k.get('quality_score') and int(k['quality_score']) <= LOW_QUALITY_SCORE and int(k.get('clicks') or 0) >= MIN_TERM_CLICKS),
                          key=lambda row: -_num(row.get('cost')))[:MAX_PER_RULE]:
        items.append(_item('low_quality_score', f"{keyword['account_id']}:{keyword['criterion_external_id']}",
                           {'kind': 'keyword', 'label': keyword['keyword_text'], 'campaign': keyword['campaign_name'], 'ad_group': keyword['ad_group_name']},
                           f"Índice de Qualidade {keyword['quality_score']}/10.", 'Aproxime anúncio e página de destino da palavra-chave; considere um grupo próprio.',
                           'cost', _num(keyword.get('cost')), link={'tab': 'keywords'}))

    for campaign in campaigns:
        clicks, conversions, cost = int(campaign.get('clicks') or 0), _num(campaign.get('conversions')), _num(campaign.get('cost'))
        if clicks >= MIN_CAMPAIGN_CLICKS and conversions == 0 and cost > 0:
            items.append(_item('campaign_without_conversion', f"{campaign['account_id']}:{campaign['campaign_external_id']}",
                               {'kind': 'campaign', 'label': campaign['campaign_name']}, f'{clicks} cliques e nenhuma conversão.',
                               'Confira a ação de conversão e a página de destino antes de mexer em lances.', 'cost', cost, link={'tab': 'campaigns'}))
        budget = _num(campaign.get('budget')) if campaign.get('budget') is not None else None
        active_days = int(campaign.get('active_days') or 0)
        if budget and active_days and conversions > 0 and cost / active_days >= BUDGET_USAGE * budget and \
                (account_cpa is None or cost / conversions <= account_cpa):
            items.append(_item('budget_limited', f"{campaign['account_id']}:{campaign['campaign_external_id']}",
                               {'kind': 'campaign', 'label': campaign['campaign_name']},
                               f'Gasto médio de {cost / active_days:.2f} por dia para um orçamento de {budget:.2f}; custo por conversão {cost / conversions:.2f}.'.replace('.', ','),
                               'Aumente o orçamento diário ou redistribua de campanhas sem conversão.', 'conversions', conversions, link={'tab': 'campaigns'},
                               proposal=_budget(campaign, budget * 1.2)))

    for device in devices:
        clicks, conversions, cost = int(device.get('clicks') or 0), _num(device.get('conversions')), _num(device.get('cost'))
        if clicks < MIN_DEVICE_CLICKS or not account_cpa:
            continue
        if conversions == 0 or cost / conversions >= DEVICE_CPA_RATIO * account_cpa:
            label = DEVICE_LABELS.get(device['device'], device['device'])
            items.append(_item('device_cpa', device['device'], {'kind': 'device', 'label': label},
                               'Nenhuma conversão.' if conversions == 0 else f'Custo por conversão {cost / conversions / account_cpa:.1f}× o da conta.'.replace('.', ','),
                               f'Reduza o ajuste de lance para {label.lower()} ou revise a página nesse dispositivo.', 'cost', cost, link={'tab': 'details'}))

    items.extend(goal_recommendations(campaigns))
    items.sort(key=lambda item: (_ORDER[item['severity']], 0 if item['impact']['kind'] == 'none' else 1, -item['impact']['value']))
    return items


def _br(value):
    return f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def goal_recommendations(campaigns):
    """Next steps against what the team set for each campaign: budget ceilings, flight dates and objective targets."""
    items = []
    for campaign in campaigns:
        goal, pacing = campaign.get('goal') or {}, campaign.get('pacing') or {}
        if not goal:
            continue
        key = f"{campaign['account_id']}:{campaign['campaign_external_id']}"
        obj = {'kind': 'campaign', 'label': campaign['campaign_name']}
        cap = _num(goal.get('monthly_budget_cap')) or None
        mtd, days_left = _num(pacing.get('mtd_cost')), int(pacing.get('days_left') or 0)
        projected = _num(pacing.get('projected_cost'))
        daily_budget = campaign.get('budget')
        if goal.get('flight_ended') and _num(pacing.get('last3_cost')) > 0:
            items.append(_item('flight_ended', key, obj, f"A meta terminava em {goal['flight_end']} e a campanha gastou {_br(_num(pacing['last3_cost']))} nos últimos 3 dias.",
                               'Pause a campanha ou atualize a data final da meta.', 'cost', _num(pacing['last3_cost']), link={'tab': 'campaigns'},
                               proposal=_campaign_pause(campaign, 'Pausar')))
        total_cap = _num(goal.get('total_budget_cap')) or None
        if total_cap and _num(pacing.get('flight_cost')) >= total_cap:
            items.append(_item('cap_reached', f'{key}:total', obj, f"Gasto total {_br(_num(pacing['flight_cost']))} para um teto de {_br(total_cap)}.",
                               'Pause a campanha ou aprove um teto maior com o cliente.', 'cost', _num(pacing['flight_cost']) - total_cap, link={'tab': 'campaigns'},
                               proposal=_campaign_pause(campaign, 'Pausar')))
        if cap and mtd >= cap:
            items.append(_item('cap_reached', key, obj, f'Gasto do mês {_br(mtd)} para um teto de {_br(cap)}.',
                               'Pause a campanha ou reduza o orçamento diário até o próximo mês.', 'cost', mtd - cap, link={'tab': 'campaigns'},
                               proposal=_campaign_pause(campaign, 'Pausar')))
        elif cap and days_left and projected > cap * PACING_OVER:
            suggested = max(0.0, (cap - mtd) / days_left)
            items.append(_item('pacing_over', key, obj, f'Projeção de {_br(projected)} para um teto de {_br(cap)} ({_br(mtd)} gastos, {days_left} dias restantes).',
                               f"Reduza o orçamento diário{f' de {_br(daily_budget)}' if daily_budget else ''} para {_br(suggested)}.",
                               'cost', projected - cap, link={'tab': 'campaigns'}, proposal=_budget(campaign, suggested)))
        target_cpa = _num(goal.get('target_cpa')) or None
        cost, conversions = _num(campaign.get('cost')), _num(campaign.get('conversions'))
        cpa = cost / conversions if conversions else None
        if cap and days_left and projected < cap * PACING_UNDER and conversions > 0 and (target_cpa is None or (cpa or 0) <= target_cpa):
            suggested = (cap - mtd) / days_left
            items.append(_item('pacing_under', key, obj, f'Projeção de {_br(projected)} para um teto de {_br(cap)}; CPA de {_br(cpa)}.',
                               f'Pode subir o orçamento diário para até {_br(suggested)} e usar o teto do mês.', 'conversions', conversions, link={'tab': 'campaigns'},
                               proposal=_budget(campaign, suggested)))
        if target_cpa:
            if conversions >= MIN_GOAL_CONVERSIONS and cpa > target_cpa * CPA_TOLERANCE:
                items.append(_item('cpa_above_target', key, obj, f'CPA de {_br(cpa)} para uma meta de {_br(target_cpa)}.',
                                   'Negative os termos sem conversão desta campanha e revise as palavras-chave mais caras antes de mexer no lance.',
                                   'cost', cost - conversions * target_cpa, link={'tab': 'search_terms', 'filter': 'negate'}))
            elif conversions == 0 and cost >= 3 * target_cpa:
                items.append(_item('cpa_above_target', key, obj, f'{_br(cost)} gastos sem conversão; a meta é {_br(target_cpa)} por conversão.',
                                   'Confira a conversão e a página de destino; se estiverem certas, reduza o orçamento.', 'cost', cost, link={'tab': 'campaigns'}))
            google_cpa = campaign.get('target_cpa')
            if google_cpa and abs(google_cpa - target_cpa) / target_cpa > TARGET_MISMATCH:
                items.append(_item('target_mismatch', key, obj, f'CPA desejado no Google Ads: {_br(google_cpa)}; meta da equipe: {_br(target_cpa)}.',
                                   'Alinhe o CPA desejado da estratégia de lances à meta acordada.', 'none', 0, link={'tab': 'campaigns'}))
        target_roas = _num(goal.get('target_roas')) or None
        roas = _num(campaign.get('conversion_value')) / cost if cost and campaign.get('conversion_value') else None
        if target_roas and roas is not None and roas < target_roas * ROAS_TOLERANCE:
            items.append(_item('roas_below_target', key, obj, f'ROAS de {roas:.2f} para uma meta de {target_roas:.2f}.'.replace('.', ','),
                               'Concentre investimento nos grupos e termos com maior valor; reduza os de ROAS mais baixo.', 'cost', cost, link={'tab': 'details'}))
        goal_conversions = int(goal.get('target_conversions_month') or 0)
        projected_conversions = _num(pacing.get('projected_conversions'))
        if goal_conversions and days_left and projected_conversions < goal_conversions * CONVERSION_GOAL_RISK:
            items.append(_item('conversion_goal_risk', key, obj, f'Projeção de {projected_conversions:.0f} conversões para uma meta de {goal_conversions}.',
                               'Aumente o orçamento nas campanhas dentro da meta de CPA ou amplie palavras-chave que já convertem.',
                               'conversions', goal_conversions - projected_conversions, link={'tab': 'campaigns'}))
    return items
