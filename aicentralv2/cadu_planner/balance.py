"""Balanceamento de mídia do Cadu Planner.

Usa o motor do SmartPlanner (``smart_planner.mix``: métodos, pesos por grupo e
objetivo, normalização para 100% e divisão em reais) sem depender das telas ou
das tabelas dele. O Planner guarda o resultado nas próprias alocações
(``cadu_planner_channel_allocations``) e no workbench do plano.

Nada aqui chama modelo de linguagem: a mesma verba, o mesmo método e os mesmos
canais sempre geram a mesma distribuição, e o usuário vê o porquê de cada fatia.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from werkzeug.exceptions import BadRequest

from ..smart_planner import mix as engine
from ..smart_planner.catalog import CHANNEL_CATALOG, CHANNEL_GROUPS, GROUP_KPIS

# Objetivos do Planner → objetivos das tabelas do motor.
OBJECTIVE_MAP = {'awareness': 'reconhecimento', 'consideracao': 'consideracao', 'leads': 'leads',
                 'vendas': 'vendas', 'trafego': 'trafego', 'outro': 'consideracao', '': 'consideracao'}
# Categoria do canal → grupo de mídia, quando o canal não está no catálogo do motor.
CATEGORY_GROUPS = {'streaming': 'ctv', 'portais': 'portais', 'sociais': 'social', 'programatica': 'programmatic',
                   'dooh': 'ooh', 'mobilidade': 'apps', 'dados': 'data', 'interativos': 'portais'}
# Papel que cada grupo cumpre no plano, em linguagem de planejamento.
GROUP_ROLES = {
    'ctv': 'Cobertura e lembrança na tela grande', 'video': 'Atenção com vídeo completo',
    'portais': 'Contexto editorial e credibilidade', 'social': 'Alcance com conversa e engajamento',
    'programmatic': 'Escala com controle de audiência', 'audio': 'Frequência em momentos sem tela',
    'performance': 'Captura da demanda e conversão', 'data': 'Precisão com dados de primeira mão',
    'apps': 'Presença no trajeto e no momento de uso', 'ooh': 'Impacto físico nas praças',
    'places': 'Presença no ponto de interesse',
}
METHOD_IDS = tuple(item['id'] for item in engine.METHODS)
CONCENTRATION_LIMIT = 60  # % de um só grupo a partir do qual o plano fica dependente dele
MAX_MONTHS = 12

_MONTHS = {'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6, 'jul': 7, 'ago': 8,
           'set': 9, 'out': 10, 'nov': 11, 'dez': 12}
_MONTH_LABELS = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')


def _fold(value):
    text = unicodedata.normalize('NFD', str(value or '')).encode('ascii', 'ignore').decode()
    return text.lower().strip()


def parse_budget(value):
    """'R$ 120.000', '120 mil', '1,2 mi', 'R$ 80k' → 120000 / 120000 / 1200000 / 80000. None se não der."""
    text = _fold(value).replace('r$', ' ').replace('brl', ' ')
    match = re.search(r'(\d[\d.,]*)\s*(milhoes|milhao|mi|mm|mil|k)?\b', text)
    if not match:
        return None
    number, unit = match.group(1), match.group(2) or ''
    if ',' in number and '.' in number:
        number = number.replace('.', '').replace(',', '.')
    elif ',' in number:
        whole, _, decimals = number.rpartition(',')
        number = f'{whole.replace(",", "")}.{decimals}' if len(decimals) <= 2 else number.replace(',', '')
    elif number.count('.') >= 1 and len(number.rpartition('.')[2]) == 3:
        number = number.replace('.', '')
    try:
        amount = float(number)
    except ValueError:
        return None
    amount *= {'mil': 1_000, 'k': 1_000, 'mi': 1_000_000, 'mm': 1_000_000,
               'milhao': 1_000_000, 'milhoes': 1_000_000}.get(unit, 1)
    return int(round(amount)) if amount > 0 else None


def parse_period(value, today=None):
    """Meses cobertos pelo período escrito no briefing.

    Entende 'mar a mai 2027', '01/03/2027 a 31/05/2027', '3 meses' e '8 semanas'.
    Sem período legível, o plano vale como um bloco único.
    """
    today = today or date.today()
    text = _fold(value)
    if not text:
        return {'months': [], 'label': '', 'parsed': False}
    dates = re.findall(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', text)
    if len(dates) >= 2:
        (_, m1, y1), (_, m2, y2) = dates[0], dates[-1]
        start, end = (_year(y1), int(m1)), (_year(y2), int(m2))
        return _span(start, end, value)
    names = [(m.start(), _MONTHS[m.group(1)]) for m in re.finditer(r'\b(' + '|'.join(_MONTHS) + r')[a-z]*\b', text)]
    years = [int(y) for y in re.findall(r'\b(20\d{2})\b', text)]
    if names:
        first, last = names[0][1], names[-1][1]
        year = years[0] if years else (today.year if first >= today.month else today.year + 1)
        end_year = years[-1] if len(years) > 1 else (year + 1 if last < first else year)
        return _span((year, first), (end_year, last), value)
    count = re.search(r'(\d{1,2})\s*(meses|mes|semanas|semana)', text)
    if count:
        size = int(count.group(1))
        months = max(1, round(size / 4.345)) if count.group(2).startswith('semana') else size
        start = (today.year, today.month)
        end = _shift(start, min(months, MAX_MONTHS) - 1)
        return _span(start, end, value)
    return {'months': [], 'label': str(value), 'parsed': False}


def _year(value):
    year = int(value)
    return year + 2000 if year < 100 else year


def _shift(month, offset):
    year, number = month
    index = year * 12 + (number - 1) + offset
    return index // 12, index % 12 + 1


def _span(start, end, raw):
    if not (1 <= start[1] <= 12 and 1 <= end[1] <= 12):
        return {'months': [], 'label': str(raw), 'parsed': False}
    total = (end[0] - start[0]) * 12 + end[1] - start[1] + 1
    if total < 1:
        return {'months': [], 'label': str(raw), 'parsed': False}
    total = min(total, MAX_MONTHS)
    months = []
    for offset in range(total):
        year, number = _shift(start, offset)
        months.append({'key': f'{year}-{number:02d}', 'label': f'{_MONTH_LABELS[number - 1]}/{str(year)[2:]}'})
    return {'months': months, 'label': str(raw), 'parsed': True}


def channel_group(channel):
    """Grupo de mídia de um canal do catálogo do Cadu (cadu_canais)."""
    for key in (channel.get('chave_sp'), channel.get('slug'), str(channel.get('slug') or '').replace('-', '_')):
        if key and key in CHANNEL_CATALOG:
            return CHANNEL_CATALOG[key].get('group') or 'performance'
    return CATEGORY_GROUPS.get(_fold(channel.get('categoria')).replace(' ', ''), 'performance')


def _channels(plan):
    """Canais do plano com o que o motor precisa (grupo) e o que o usuário vê (logo, mínimo)."""
    from ..cadu_family import repository
    from .channels import _channel_logo
    ids = [str(item['resource_id']) for item in plan.get('items') or [] if item.get('kind') == 'canais']
    if not ids:
        return []
    numeric = [int(value) for value in ids if value.isdigit()]
    rows = {str(row['id']): row for row in repository.rows(
        '''SELECT id, slug, nome, categoria, chave_sp, logo_path, cor, investimento_minimo_valor
             FROM cadu_canais WHERE id = ANY(%s)''', (numeric,))} if numeric else {}
    snapshots = {str(item['resource_id']): item.get('snapshot') or {} for item in plan.get('items') or []}
    channels = []
    for resource_id in ids:
        row = rows.get(resource_id) or {}
        snapshot = snapshots.get(resource_id) or {}
        group = channel_group(row) if row else CATEGORY_GROUPS.get(_fold(snapshot.get('category')), 'performance')
        minimum = row.get('investimento_minimo_valor')
        channels.append({
            'resource_id': resource_id, 'name': row.get('nome') or snapshot.get('name') or resource_id,
            'category': row.get('categoria') or snapshot.get('category') or '',
            'logo': _channel_logo(str(row.get('slug') or '').lower(), row.get('logo_path')) if row else '',
            'color': row.get('cor') or '', 'group': group,
            'minimum': int(minimum) if minimum else None,
        })
    return channels


def _weights_for(channels, method, objective, manual):
    keys = [channel['resource_id'] for channel in channels]
    if method == 'manual':
        raw = [(key, float(manual.get(key, 0) or 0)) for key in keys]
        if not any(weight > 0 for _, weight in raw):
            raw = [(key, 1.0) for key in keys]
        return engine.normalize_pcts(raw)
    groups = [channel['group'] for channel in channels]
    group_weights = engine.group_weights(method, objective, list(dict.fromkeys(groups)))
    counts = {group: groups.count(group) for group in groups}
    raw = [(channel['resource_id'], group_weights.get(channel['group'], 4) / max(counts[channel['group']], 1))
           for channel in channels]
    return engine.normalize_pcts(raw)


def _blend(early, late, keys, ratio):
    return engine.normalize_pcts([(key, (1 - ratio) * early.get(key, 0) + ratio * late.get(key, 0)) for key in keys])


def _money(value):
    return f"R$ {int(round(value or 0)):,}".replace(',', '.')


def compute(plan, method=None, manual=None, progress=True):
    """Proposta de balanceamento para o plano. Não grava nada."""
    channels = _channels(plan)
    briefing = plan.get('briefing') or {}
    objective = OBJECTIVE_MAP.get(str(plan.get('objective') or ''), 'consideracao')
    recommended = engine.recommend_methods(objective)
    method = method if method in METHOD_IDS else recommended[0]
    manual = {str(key): value for key, value in (manual or {}).items() if value not in (None, '')}
    if method == 'manual' and not manual:
        # Reabrir um balanceamento manual parte do que está salvo no plano, não de fatias iguais.
        manual = {str(key): row.get('weight') for key, row in (plan.get('allocation_by_channel') or {}).items()
                  if row.get('weight') is not None}
    budget = parse_budget(briefing.get('budget'))
    period = parse_period(briefing.get('period'))
    methods = [{**item, 'recommended': item['id'] in recommended, 'primary': item['id'] == recommended[0]}
               for item in engine.METHODS]
    base = {'method': method, 'methods': methods, 'objective': objective,
            'budget': {'value': budget, 'label': _money(budget) if budget else '', 'raw': briefing.get('budget') or ''},
            'period': period, 'channels': [], 'groups': [], 'calendar': None, 'warnings': [],
            'strategy': next(item for item in methods if item['id'] == method)}
    if not channels:
        base['warnings'].append({'level': 'info', 'text': 'Adicione canais ao plano para balancear a verba.'})
        return base

    pcts = _weights_for(channels, method, objective, manual)
    money = engine.shares_to_money([{'id': key, 'pct': pct} for key, pct in pcts.items()], budget or 0)
    saved = plan.get('allocation_by_channel') or {}
    rows = []
    for channel in channels:
        key = channel['resource_id']
        current = saved.get(key) or {}
        rows.append({**channel, 'group_label': CHANNEL_GROUPS.get(channel['group'], channel['group']),
                     'role': GROUP_ROLES.get(channel['group'], ''), 'kpis': list(GROUP_KPIS.get(channel['group'], ())),
                     'pct': pcts.get(key, 0), 'investment': money.get(key) if budget else None,
                     'current_pct': float(current['weight']) if current.get('weight') is not None else None,
                     'current_investment': float(current['investment']) if current.get('investment') is not None else None})
    base['channels'] = rows

    groups = {}
    for row in rows:
        entry = groups.setdefault(row['group'], {'group': row['group'], 'label': row['group_label'], 'pct': 0, 'count': 0})
        entry['pct'] += row['pct']
        entry['count'] += 1
    base['groups'] = sorted(groups.values(), key=lambda item: -item['pct'])

    months = period['months']
    if months and budget:
        keys = [row['resource_id'] for row in rows]
        moving = progress and method != 'manual' and len(months) >= 2
        early = _weights_for(channels, 'funil' if method == 'alcance' else method, 'reconhecimento', manual) if moving else pcts
        # Verba igual por mês; a sobra de centavos vai para os primeiros meses.
        month_budget = engine.shares_to_money([{'id': item['key'], 'pct': 100 / len(months)} for item in months], budget)
        cells = {key: [] for key in keys}
        for index, month in enumerate(months):
            ratio = index / (len(months) - 1) if moving else 1.0
            share = _blend(early, pcts, keys, ratio) if moving else pcts
            values = engine.shares_to_money([{'id': key, 'pct': share.get(key, 0)} for key in keys], month_budget[month['key']])
            for key in keys:
                cells[key].append({'month': month['key'], 'pct': share.get(key, 0), 'value': values.get(key, 0)})
        base['calendar'] = {'months': months, 'progressive': moving, 'cells': cells,
                            'totals': [{'month': item['key'], 'value': month_budget[item['key']]} for item in months]}

    base['warnings'] = _warnings(rows, base['groups'], budget, period)
    return base


def _warnings(rows, groups, budget, period):
    warnings = []
    if not budget:
        warnings.append({'level': 'info', 'text': 'Informe o investimento na direção da campanha para ver os valores em reais.'})
    if not period.get('parsed'):
        warnings.append({'level': 'info', 'text': 'Escreva o período como "mar a mai 2027" ou "3 meses" para ver a distribuição mês a mês.'})
    if groups and groups[0]['pct'] >= CONCENTRATION_LIMIT and len(groups) > 1:
        warnings.append({'level': 'attention', 'text': f"{groups[0]['label']} concentra {groups[0]['pct']}% da verba. Se esse grupo render menos que o previsto, o plano inteiro sente."})
    for row in rows:
        if budget and row['minimum'] and row['investment'] is not None and 0 < row['investment'] < row['minimum']:
            warnings.append({'level': 'attention', 'resource_id': row['resource_id'],
                             'text': f"{row['name']} recebe {_money(row['investment'])}, abaixo do mínimo de compra de {_money(row['minimum'])}. Aumente a fatia ou tire o canal."})
        if row['pct'] == 0:
            warnings.append({'level': 'attention', 'resource_id': row['resource_id'],
                             'text': f"{row['name']} ficou sem verba neste método."})
    return warnings


def apply(client_id, actor_id, plan_id, payload):
    """Grava o balanceamento escolhido como a distribuição do plano."""
    from ..db import get_db
    from . import plans, workbench
    from psycopg.types.json import Json
    plan = plans.get_plan(client_id, actor_id, plan_id)
    method = str(payload.get('method') or '')
    if method not in METHOD_IDS:
        raise BadRequest('Escolha um método de balanceamento.')
    manual = payload.get('weights') if isinstance(payload.get('weights'), dict) else {}
    result = compute(plan, method, manual, progress=bool(payload.get('progress', True)))
    if not result['channels']:
        raise BadRequest('Adicione canais ao plano antes de balancear.')
    flight = result['period']['label'][:120] if result['period'].get('parsed') else None
    allocations = [{'resource_id': row['resource_id'], 'weight': row['pct'],
                    'investment': row['investment'] or 0, 'flight': flight,
                    'notes': (row['role'] or '')[:500]} for row in result['channels']]
    plans.save_allocations(client_id, actor_id, plan_id, {'allocations': allocations})
    if plans._cobuild_available():
        state = plans.get_plan(client_id, actor_id, plan_id)
        board = workbench.mark_edited(state, 'verba')
        board.setdefault('balance', {}).update({
            'method': method, 'strategy': result['strategy']['label'], 'progressive': bool(result['calendar'] and result['calendar']['progressive']),
            'budget': result['budget']['value'], 'manual': method == 'manual'})
        from .proposals import available as events_available, record_event
        with get_db() as conn, conn.cursor() as cur:
            cur.execute('UPDATE cadu_planner_plans SET workbench = %s, revision = revision + 1 WHERE id = %s',
                        (Json(board), str(plan['id'])))
            if events_available():
                record_event(cur, plan['id'], 'user', 'balance_applied',
                             f"Balanceamento aplicado: {result['strategy']['label']}.", actor_id=actor_id)
    return plans.get_plan(client_id, actor_id, plan_id)
