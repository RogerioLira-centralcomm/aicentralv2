"""Custom report metrics: a formula over base metrics or a reviewed manual value, with an optional target.

Formulas use only numbers, the base variables below, + - * / and parentheses. Parsed here, never eval'd.
The same grammar lives in frontend/reports-v1/reportMetrics.js for the live preview.
"""
import re

VARIABLES = {
    'custo': 'Investimento', 'impressoes': 'Impressões', 'cliques': 'Cliques', 'conversoes': 'Conversões (mídia)',
    'valor': 'Valor de conversão', 'entradas_fluxo': 'Entradas no fluxo', 'conversoes_fluxo': 'Conversões do fluxo',
}
UNITS = ('count', 'BRL', 'USD', 'percent', 'ratio')
MAX_METRICS = 20
_TOKEN = re.compile(r'\s*(?:(\d+(?:[.,]\d+)?)|([a-z_]+)|(.))')


def _tokens(formula):
    out = []
    for number, name, symbol in _TOKEN.findall(formula):
        if number:
            out.append(('num', float(number.replace(',', '.'))))
        elif name:
            if name not in VARIABLES:
                raise ValueError(f'Variável desconhecida: {name}.')
            out.append(('var', name))
        elif symbol.strip():
            if symbol not in '+-*/()':
                raise ValueError(f'Símbolo não permitido: {symbol}.')
            out.append(('op', symbol))
    return out


def parse(formula):
    """Validated token list (raises ValueError). Grammar: expr := term (('+'|'-') term)*; term := factor (('*'|'/') factor)*."""
    if not isinstance(formula, str) or not formula.strip() or len(formula) > 200:
        raise ValueError('Informe uma fórmula de até 200 caracteres.')
    tokens = _tokens(formula.strip().lower())
    evaluate_tokens(tokens, {name: 1.0 for name in VARIABLES})
    return tokens


def evaluate_tokens(tokens, values):
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else (None, None)

    def take():
        nonlocal position
        position += 1
        return tokens[position - 1]

    def factor():
        kind, value = peek()
        if kind == 'op' and value == '-':
            take(); inner = factor()
            return None if inner is None else -inner
        if kind == 'op' and value == '(':
            take(); inner = expr()
            if peek() != ('op', ')'):
                raise ValueError('Parêntese sem fechamento.')
            take()
            return inner
        if kind == 'num':
            take(); return value
        if kind == 'var':
            take(); found = values.get(value)
            return None if found is None else float(found)
        raise ValueError('Fórmula incompleta.')

    def term():
        left = factor()
        while peek() in (('op', '*'), ('op', '/')):
            _, op = take(); right = factor()
            if left is None or right is None:
                left = None
            elif op == '*':
                left = left * right
            else:
                left = None if right == 0 else left / right
        return left

    def expr():
        left = term()
        while peek() in (('op', '+'), ('op', '-')):
            _, op = take(); right = term()
            left = None if left is None or right is None else left + right if op == '+' else left - right
        return left

    result = expr()
    if position != len(tokens):
        raise ValueError('Fórmula inválida.')
    return result


def _number(value, label):
    if value is None or value == '':
        return None
    try:
        number = float(str(value).replace(',', '.'))
    except ValueError:
        raise ValueError(f'{label} inválido.')
    if abs(number) >= 1e15:
        raise ValueError(f'{label} fora do limite.')
    return number


def validate_metric(item):
    if not isinstance(item, dict):
        raise ValueError('Métrica inválida.')
    name = ' '.join(str(item.get('name') or '').split())[:80]
    if not name:
        raise ValueError('Dê um nome à métrica.')
    kind = item.get('kind')
    if kind not in ('formula', 'manual'):
        raise ValueError('Tipo de métrica inválido.')
    unit = item.get('unit') if item.get('unit') in UNITS else 'count'
    direction = item.get('direction') if item.get('direction') in ('higher', 'lower') else 'higher'
    metric = {'id': str(item.get('id') or '')[:40] or re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40] or 'metrica',
              'name': name, 'kind': kind, 'unit': unit, 'direction': direction,
              'definition': ' '.join(str(item.get('definition') or '').split())[:300],
              'target': _number(item.get('target'), 'Meta')}
    if kind == 'formula':
        formula = str(item.get('formula') or '').strip().lower()
        parse(formula)
        metric['formula'] = formula
    else:
        metric['value'] = _number(item.get('value'), 'Valor')
        if metric['value'] is None:
            raise ValueError(f'Informe o valor de “{name}”.')
        metric['evidence'] = ' '.join(str(item.get('evidence') or '').split())[:300]
    if not re.fullmatch(r'[a-z0-9-]{1,40}', metric['id']):
        raise ValueError('Identificador de métrica inválido.')
    return metric


def validate_metrics(value):
    if not isinstance(value, list) or len(value) > MAX_METRICS:
        raise ValueError(f'Use até {MAX_METRICS} métricas por relatório.')
    clean = [validate_metric(item) for item in value]
    if len({item['id'] for item in clean}) != len(clean):
        raise ValueError('Há métricas repetidas.')
    return clean


def base_values(totals, journey=None):
    totals = totals or {}
    journey = journey or {}
    return {'custo': totals.get('cost'), 'impressoes': totals.get('impressions'), 'cliques': totals.get('clicks'),
            'conversoes': totals.get('conversions'), 'valor': totals.get('conversion_value'),
            'entradas_fluxo': journey.get('entries'), 'conversoes_fluxo': journey.get('conversions')}


def compute(metrics, totals, journey=None):
    """Metrics with `result` (None when a variable is missing or there is a division by zero) and `status` vs target."""
    values = base_values(totals, journey)
    out = []
    for metric in metrics or []:
        if metric.get('kind') == 'formula':
            try:
                result = evaluate_tokens(_tokens(metric['formula']), values)
            except ValueError:
                result = None
        else:
            result = metric.get('value')
        if result is not None and metric.get('unit') == 'percent' and metric.get('kind') == 'formula':
            result = result * 100
        target = metric.get('target')
        status = None
        if result is not None and target is not None:
            status = 'met' if (result >= target if metric.get('direction') != 'lower' else result <= target) else 'missed'
        out.append({**metric, 'result': None if result is None else round(result, 4), 'status': status})
    return out
