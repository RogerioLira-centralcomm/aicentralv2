// Custom report metrics: same grammar as aicentralv2/cadu_connect/report_metrics.py (numbers, variables, + - * / and parentheses).
export const VARIABLES = {
  custo: 'Investimento', impressoes: 'Impressões', cliques: 'Cliques', conversoes: 'Conversões (mídia)',
  valor: 'Valor de conversão', entradas_fluxo: 'Entradas no fluxo', conversoes_fluxo: 'Conversões do fluxo',
};
export const UNITS = [['count', 'Número'], ['BRL', 'R$'], ['USD', 'US$'], ['percent', '% (fórmula × 100)'], ['ratio', 'Razão (2 casas)']];

const tokenize = formula => {
  const tokens = [];
  const pattern = /\s*(?:(\d+(?:[.,]\d+)?)|([a-z_]+)|(.))/gy;
  let match;
  while (pattern.lastIndex < formula.length && (match = pattern.exec(formula))) {
    const [, number, name, symbol] = match;
    if (number) tokens.push(['num', Number(number.replace(',', '.'))]);
    else if (name) { if (!(name in VARIABLES)) throw new Error(`Variável desconhecida: ${name}.`); tokens.push(['var', name]); }
    else if (symbol && symbol.trim()) { if (!'+-*/()'.includes(symbol)) throw new Error(`Símbolo não permitido: ${symbol}.`); tokens.push(['op', symbol]); }
  }
  return tokens;
};

const run = (tokens, values) => {
  let at = 0;
  const peek = () => tokens[at] || [null, null];
  const is = (kind, value) => peek()[0] === kind && peek()[1] === value;
  const factor = () => {
    const [kind, value] = peek();
    if (is('op', '-')) { at += 1; const inner = factor(); return inner == null ? null : -inner; }
    if (is('op', '(')) { at += 1; const inner = expr(); if (!is('op', ')')) throw new Error('Parêntese sem fechamento.'); at += 1; return inner; }
    if (kind === 'num') { at += 1; return value; }
    if (kind === 'var') { at += 1; const found = values[value]; return found == null ? null : Number(found); }
    throw new Error('Fórmula incompleta.');
  };
  const term = () => {
    let left = factor();
    while (is('op', '*') || is('op', '/')) {
      const op = tokens[at][1]; at += 1; const right = factor();
      left = left == null || right == null ? null : op === '*' ? left * right : right === 0 ? null : left / right;
    }
    return left;
  };
  const expr = () => {
    let left = term();
    while (is('op', '+') || is('op', '-')) {
      const op = tokens[at][1]; at += 1; const right = term();
      left = left == null || right == null ? null : op === '+' ? left + right : left - right;
    }
    return left;
  };
  const result = expr();
  if (at !== tokens.length) throw new Error('Fórmula inválida.');
  return result;
};

/** '' when the formula is valid, else the reason. */
export const formulaError = formula => {
  if (!formula?.trim()) return 'Informe a fórmula.';
  if (formula.length > 200) return 'Até 200 caracteres.';
  try { run(tokenize(formula.trim().toLowerCase()), Object.fromEntries(Object.keys(VARIABLES).map(key => [key, 1]))); return ''; }
  catch (error) { return error.message; }
};

export const baseValues = (totals, journey) => ({
  custo: totals?.cost, impressoes: totals?.impressions, cliques: totals?.clicks, conversoes: totals?.conversions,
  valor: totals?.conversion_value, entradas_fluxo: journey?.funnel?.entries ?? journey?.entries, conversoes_fluxo: journey?.funnel?.conversions ?? journey?.conversions,
});

/** Value of one metric now (null when data is missing or a division by zero). */
export const metricResult = (metric, values) => {
  if (metric.kind !== 'formula') return metric.value === '' || metric.value == null ? null : Number(String(metric.value).replace(',', '.'));
  try {
    const result = run(tokenize(String(metric.formula || '').trim().toLowerCase()), values);
    return result == null ? null : metric.unit === 'percent' ? result * 100 : result;
  } catch { return null; }
};

export const formatMetric = (value, unit) => {
  if (value == null || !Number.isFinite(value)) return '—';
  if (unit === 'BRL' || unit === 'USD') return new Intl.NumberFormat('pt-BR', {style: 'currency', currency: unit}).format(value);
  if (unit === 'percent') return `${value.toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
  return value.toLocaleString('pt-BR', {maximumFractionDigits: 2});
};
