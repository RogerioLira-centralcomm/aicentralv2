"""Quanto tempo o plano poupou: estimativa simples e explicável.

Cada atividade tem o tempo que um planejador costuma gastar fazendo à mão
(pesquisar o canal, montar o mix numa planilha, revisar o briefing). O plano
soma só o que o Cadu de fato fez nele. Os números são referência interna e
aparecem como estimativa, com a conta aberta para quem quiser ver.
"""
from __future__ import annotations

# Minutos de trabalho manual por atividade.
MANUAL_MINUTES = {
    'canais': (20, 'Pesquisar canal, especificações e mínimo de compra'),
    'audiencias': (15, 'Encontrar e dimensionar audiência'),
    'formatos': (10, 'Levantar formato e especificação'),
    'interativos': (12, 'Levantar formato interativo'),
    'portais': (10, 'Avaliar portal e audiência'),
    'places': (10, 'Levantar ponto e entorno'),
    'briefing_review': (45, 'Revisar e estruturar o briefing'),
    'balance': (90, 'Montar o mix e dividir a verba na planilha'),
    'calendar': (30, 'Distribuir a verba mês a mês'),
    'radar': (180, 'Pesquisar o contexto e qualificar a oportunidade'),
}


def estimate(plan: dict) -> dict:
    """Minutos poupados com a conta por atividade. Não grava nada."""
    lines = []

    def add(key, count=1):
        minutes, label = MANUAL_MINUTES[key]
        if count > 0:
            lines.append({'key': key, 'label': label, 'count': count, 'minutes': minutes * count})

    kinds = {}
    for item in plan.get('items') or []:
        kinds[item.get('kind')] = kinds.get(item.get('kind'), 0) + 1
    for kind in ('canais', 'audiencias', 'formatos', 'interativos', 'portais', 'places'):
        add(kind, kinds.get(kind, 0))
    add('briefing_review', min(len(plan.get('review_history') or []), 1))
    balance = ((plan.get('workbench') or {}).get('balance') or {})
    if balance.get('method'):
        add('balance')
        if balance.get('progressive'):
            add('calendar')
    if plan.get('source') == 'radar':
        add('radar')
    total = sum(line['minutes'] for line in lines)
    return {'minutes': total, 'label': label(total), 'lines': lines,
            'note': 'Estimativa com tempos de referência do trabalho manual de planejamento.'}


def label(minutes: int) -> str:
    if minutes <= 0:
        return ''
    if minutes < 60:
        return f'{minutes} min'
    hours, rest = divmod(minutes, 60)
    if rest < 15:
        return f'{hours} h'
    if rest >= 45:
        return f'{hours + 1} h'
    return f'{hours} h {rest} min' if hours < 3 else f'{hours},5 h'
