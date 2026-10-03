"""Rule-based suggestions for one page, each one backed by the numbers that triggered it.

The rules are deliberately plain: fixed thresholds, no model, nothing hidden. The system only suggests; it never
changes anything in Google Ads. A rule that cannot be evaluated honestly (data not collected yet) is reported in
``skipped`` instead of being silently dropped or guessed.
"""

# Thresholds, shown to the user in "Como decidimos".
MIN_TERM_CLICKS = 10
MIN_CAMPAIGN_CLICKS = 30
MIN_TRACKING_GAP_CLICKS = 50
TRACKING_GAP_RATIO = 0.5
HIGH_EXIT_RATE = 70.0
LOW_SCROLL_50 = 30.0
LOW_QUALITY_SCORE = 4
CONVERSION_DROP_PERCENT = 30.0
SLOW_RESPONSE_MS = 1500
MAX_PER_RULE = 5

RULES = [
    {'rule': 'paid_page_down', 'severity': 'high', 'title': 'Página fora do ar com anúncio gastando',
     'when': 'A última verificação HTTP da página falhou e há campanhas do Google Ads com custo apontando para ela no período.'},
    {'rule': 'negative_candidate', 'severity': 'medium', 'title': 'Termo de pesquisa para considerar como negativa',
     'when': f'Termo de campanhas que apontam para a página com ao menos {MIN_TERM_CLICKS} cliques, nenhuma conversão e ainda não coberto por palavra negativa.'},
    {'rule': 'campaign_without_conversion', 'severity': 'medium', 'title': 'Campanha com cliques e sem conversão',
     'when': f'Campanha com ao menos {MIN_CAMPAIGN_CLICKS} cliques e custo, sem nenhuma conversão registrada no Google Ads.'},
    {'rule': 'weak_engagement', 'severity': 'medium', 'title': 'Muito clique pago e pouca interação na página',
     'when': f'Taxa de saída de {HIGH_EXIT_RATE:.0f}% ou mais e menos de {LOW_SCROLL_50:.0f}% das sessões passando de 50% da página, com ao menos {MIN_CAMPAIGN_CLICKS} sessões e campanhas pagas ativas.'},
    {'rule': 'tracking_gap', 'severity': 'medium', 'title': 'Cliques do Google Ads muito acima das sessões medidas',
     'when': f'Ao menos {MIN_TRACKING_GAP_CLICKS} cliques no Google Ads e menos de {int(TRACKING_GAP_RATIO * 100)}% disso em sessões vindas do Google na Super Tag.'},
    {'rule': 'low_quality_unstable_page', 'severity': 'medium', 'title': 'Índice de Qualidade baixo e página instável',
     'when': f'Palavra-chave com Índice de Qualidade até {LOW_QUALITY_SCORE} e ao menos {MIN_TERM_CLICKS} cliques, com falha ou resposta acima de {SLOW_RESPONSE_MS} ms nas verificações recentes.'},
    {'rule': 'conversion_drop', 'severity': 'low', 'title': 'Queda na conversão da sessão',
     'when': f'Queda relativa de {CONVERSION_DROP_PERCENT:.0f}% ou mais frente ao período anterior, com amostra confiável nos dois períodos.'},
]
_RULE = {item['rule']: item for item in RULES}
_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def _tokens(text):
    return str(text or '').lower().split()


def negative_covers(term, text, match_type):
    """Whether a negative keyword (by match type) already blocks this search term."""
    words, target = _tokens(text), _tokens(term)
    if not words or not target:
        return False
    if match_type == 'EXACT':
        return words == target
    if match_type == 'PHRASE':
        return any(target[i:i + len(words)] == words for i in range(len(target) - len(words) + 1))
    return all(word in target for word in words)


def term_is_covered(term, negatives):
    """A term row carries account/campaign/ad group; a negative applies by its own level."""
    for negative in negatives:
        if negative['account_id'] != term['account_id']:
            continue
        level = negative['level']
        applies = (level == 'campaign' and negative['campaign_external_id'] == term['campaign_external_id']) or \
                  (level == 'ad_group' and negative['ad_group_external_id'] == term['ad_group_external_id']) or \
                  (level == 'shared_list' and term['campaign_external_id'] in (negative['attached_campaign_ids'] or []))
        if applies and negative_covers(term['search_term'], negative['keyword_text'], negative['match_type']):
            return True
    return False


def _item(rule, key, summary, evidence, action, **extra):
    meta = _RULE[rule]
    return {'id': f'{rule}:{key}', 'rule': rule, 'severity': meta['severity'], 'title': meta['title'],
            'summary': summary, 'evidence': evidence, 'action': action, **extra}


def _money(label, micros, currency):
    return {'label': label, 'value': micros, 'unit': 'money', 'currency': currency}


def _count(label, value):
    return {'label': label, 'value': value, 'unit': 'count'}


def _percent(label, value):
    return {'label': label, 'value': value, 'unit': 'percent'}


def build_suggestions(ctx):
    """ctx: metrics, previous, paid (paid_origin dict), health, google_sessions, candidate_terms, negatives,
    accounts_with_negatives (set of account ids whose negative snapshot was received)."""
    items, skipped = [], []
    metrics, previous = ctx['metrics'], ctx.get('previous')
    paid = ctx.get('paid') or {}
    campaigns = paid.get('campaigns') or [] if paid.get('available') else []
    latest = (ctx.get('health') or {}).get('latest')
    timeline = (ctx.get('health') or {}).get('timeline') or []
    currency = campaigns[0]['currency'] if campaigns else None
    paid_cost = sum(c['cost_micros'] or 0 for c in campaigns)
    paid_clicks = sum(c['clicks'] or 0 for c in campaigns)

    if not paid.get('available'):
        skipped.append('Dados de páginas de destino do Google Ads ainda não foram recebidos: as regras de origem paga não foram avaliadas.')

    if latest and latest.get('status') in ('offline', 'degraded') and paid_cost > 0:
        items.append(_item('paid_page_down', 'page',
            'A verificação mais recente mostra a página com problema enquanto campanhas pagas apontam para ela.',
            [{'label': 'Estado', 'value': 'Indisponível' if latest['status'] == 'offline' else 'Degradada', 'unit': 'text'},
             _count('Código HTTP', latest.get('http_status')), _money('Custo no período', paid_cost, currency), _count('Cliques pagos', paid_clicks)],
            'Confirme se a página abre e, se estiver fora do ar, pause as campanhas ou corrija a página antes de continuar gastando.',
            anchor='saude'))

    # Negative candidates: only for accounts whose negative-keyword snapshot was actually received.
    covered_accounts = ctx.get('accounts_with_negatives') or set()
    pending_accounts = {c['account_id'] for c in campaigns} - covered_accounts
    if pending_accounts and campaigns:
        skipped.append('A coleta de palavras negativas ainda não chegou para todas as contas: não dá para dizer se um termo já está bloqueado.')
    negatives = ctx.get('negatives') or []
    found = []
    for term in ctx.get('candidate_terms') or []:
        if term['account_id'] not in covered_accounts or term['clicks'] < MIN_TERM_CLICKS or (term['conversions'] or 0) > 0:
            continue
        if term_is_covered(term, negatives):
            continue
        found.append(term)
    for term in sorted(found, key=lambda t: -t['cost_micros'])[:MAX_PER_RULE]:
        items.append(_item('negative_candidate', f"{term['campaign_external_id']}:{term['term_hash']}",
            f"“{term['search_term']}” gerou cliques e custo sem nenhuma conversão e não está bloqueado por palavra negativa.",
            [{'label': 'Termo', 'value': term['search_term'], 'unit': 'text'}, _count('Cliques', term['clicks']),
             _money('Custo', term['cost_micros'], term['currency']), _count('Conversões', 0),
             {'label': 'Campanha', 'value': term['campaign_name'], 'unit': 'text'}],
            'Avalie se o termo é irrelevante para a oferta. Se for, adicione como palavra negativa no Google Ads; esta tela não altera a conta.',
            anchor='origem-paga'))

    for campaign in sorted(campaigns, key=lambda c: -(c['cost_micros'] or 0)):
        if (campaign['clicks'] or 0) >= MIN_CAMPAIGN_CLICKS and (campaign['cost_micros'] or 0) > 0 and not (campaign['conversions'] or 0):
            items.append(_item('campaign_without_conversion', campaign['campaign_external_id'],
                f"{campaign['campaign_name']} trouxe cliques para esta página sem registrar conversão no Google Ads.",
                [_count('Cliques', campaign['clicks']), _money('Custo', campaign['cost_micros'], campaign['currency']), _count('Conversões (Ads)', 0)],
                'Verifique se a conversão está configurada e disparando; se estiver, revise a oferta, a página e a segmentação da campanha.',
                anchor='origem-paga'))
            if sum(1 for i in items if i['rule'] == 'campaign_without_conversion') >= MAX_PER_RULE:
                break

    if (metrics['reliable'] and paid_clicks >= MIN_CAMPAIGN_CLICKS and (metrics.get('exit_rate') or 0) >= HIGH_EXIT_RATE
            and metrics.get('scroll_50') is not None and metrics['scroll_50'] < LOW_SCROLL_50):
        items.append(_item('weak_engagement', 'page',
            'A maior parte das visitas sai sem rolar a página, mesmo com campanhas pagas enviando tráfego.',
            [_percent('Taxa de saída', metrics['exit_rate']), _percent('Rolaram 50%', metrics['scroll_50']),
             _count('Sessões', metrics['sessions']), _count('Cliques pagos', paid_clicks), _money('Custo no período', paid_cost, currency)],
            'Compare a mensagem do anúncio com o topo da página, o tempo de carregamento e o que aparece antes da primeira rolagem.',
            anchor='comportamento'))

    google_sessions = ctx.get('google_sessions') or 0
    if paid_clicks >= MIN_TRACKING_GAP_CLICKS and google_sessions < paid_clicks * TRACKING_GAP_RATIO:
        items.append(_item('tracking_gap', 'page',
            'Há muito mais cliques no Google Ads do que sessões vindas do Google na Super Tag.',
            [_count('Cliques no Google Ads', paid_clicks), _count('Sessões do Google na Super Tag', google_sessions),
             _percent('Sessões ÷ cliques', round(100 * google_sessions / paid_clicks, 1))],
            'Cliques e sessões não são a mesma coisa, mas uma diferença grande costuma indicar UTM ausente, redirecionamento que perde parâmetros, '
            'página lenta, bloqueadores de script ou a Super Tag ausente na página de destino.',
            anchor='origem-paga'))

    unstable = bool(latest) and (any(item.get('status') != 'online' for item in timeline[:10])
                                 or (latest.get('duration_ms') or 0) >= SLOW_RESPONSE_MS)
    if unstable:
        for keyword in paid.get('keywords') or []:
            score = keyword.get('quality_score')
            if score is not None and score <= LOW_QUALITY_SCORE and (keyword['clicks'] or 0) >= MIN_TERM_CLICKS:
                items.append(_item('low_quality_unstable_page', keyword['keyword_text'],
                    f"“{keyword['keyword_text']}” tem Índice de Qualidade baixo e a página apresentou falhas ou lentidão nas verificações recentes.",
                    [{'label': 'Palavra-chave', 'value': keyword['keyword_text'], 'unit': 'text'}, _count('Índice de Qualidade', score),
                     _count('Cliques', keyword['clicks']), {'label': 'Última resposta (ms)', 'value': latest.get('duration_ms'), 'unit': 'count'}],
                    'A experiência da página é um dos componentes do Índice de Qualidade: estabilize e acelere a página e acompanhe o índice depois.',
                    anchor='saude'))
                if sum(1 for i in items if i['rule'] == 'low_quality_unstable_page') >= MAX_PER_RULE:
                    break

    now, before = metrics.get('session_conversion_rate'), (previous or {}).get('session_conversion_rate')
    if (previous and metrics['reliable'] and previous.get('reliable') and now is not None and before
            and 100 * (before - now) / before >= CONVERSION_DROP_PERCENT):
        items.append(_item('conversion_drop', 'page',
            'A taxa de conversão da sessão caiu bastante em relação ao período anterior equivalente.',
            [_percent('Período atual', now), _percent('Período anterior', before), _percent('Variação relativa', round(100 * (now - before) / before, 1)),
             _count('Sessões atuais', metrics['sessions'])],
            'Veja o que mudou na página, na oferta, nas campanhas e na coleta nesse intervalo; a queda por si só não indica a causa.',
            anchor='numeros'))

    items.sort(key=lambda item: (_ORDER[item['severity']], item['rule'], item['id']))
    return {'suggestions': items, 'skipped': skipped, 'rules': RULES}
