// Forecast layer: plan numbers flow from origins through connection rates to conversions.
export const FORECAST_SCENARIOS = Object.freeze([
  {id: 'pessimistic', label: 'Pessimista', factor: 0.75},
  {id: 'likely', label: 'Provável', factor: 1},
  {id: 'optimistic', label: 'Otimista', factor: 1.25},
]);

const number = value => {const parsed = Number(value); return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;};
export const forecastRate = edge => {const rate = number(edge?.forecast?.rate); return rate == null ? null : Math.min(100, rate);};

/** Edges that close a cycle are returns: they never feed the forecast, or traffic would loop forever. */
function acyclicOrder(nodes, edges) {
  const outgoing = new Map(nodes.map(node => [node.id, []]));
  for (const edge of edges) if (outgoing.has(edge.from) && outgoing.has(edge.to)) outgoing.get(edge.from).push(edge);
  const state = new Map(), order = [], back = new Set();
  const visit = id => {
    state.set(id, 'open');
    for (const edge of outgoing.get(id)) {
      if (state.get(edge.to) === 'open') back.add(edge.id);
      else if (!state.has(edge.to)) visit(edge.to);
    }
    state.set(id, 'done');
    order.push(id);
  };
  const roots = nodes.filter(node => node.type === 'source').map(node => node.id);
  for (const id of [...roots, ...nodes.map(node => node.id)]) if (!state.has(id)) visit(id);
  return {order: order.reverse(), back};
}

/** Sessions per node and per connection for one scenario, plus campaign totals. */
export function computeForecast(config, factor = 1) {
  const nodes = (config.nodes || []).filter(node => node.type !== 'note');
  const ids = new Set(nodes.map(node => node.id));
  const edges = (config.edges || []).filter(edge => ids.has(edge.from) && ids.has(edge.to));
  const {order, back} = acyclicOrder(nodes, edges);
  const byId = new Map(nodes.map(node => [node.id, node]));
  const sessions = new Map(nodes.map(node => [node.id, node.type === 'source' ? number(node.forecast?.visits) ?? 0 : 0]));
  const flows = {};
  const missingRates = [];
  const overAllocated = [];
  for (const id of order) {
    const out = edges.filter(edge => edge.from === id && !back.has(edge.id));
    const rates = out.map(edge => forecastRate(edge));
    const total = rates.reduce((sum, rate) => sum + (rate ?? 0), 0);
    if (total > 100.0001) overAllocated.push(id);
    out.forEach((edge, index) => {
      const rate = rates[index];
      if (rate == null) {missingRates.push(edge.id); flows[edge.id] = {rate: null, sessions: 0}; return;}
      // Origins send their visits as planned; later steps scale with the scenario, never above 100%.
      const applied = byId.get(id).type === 'source' ? rate : Math.min(100, rate * factor);
      const value = sessions.get(id) * applied / 100;
      flows[edge.id] = {rate: applied, sessions: value};
      sessions.set(edge.to, sessions.get(edge.to) + value);
    });
  }
  const sources = nodes.filter(node => node.type === 'source');
  const conversions = nodes.filter(node => node.type === 'conversion');
  const visits = sources.reduce((sum, node) => sum + sessions.get(node.id), 0);
  const cost = sources.reduce((sum, node) => sum + (number(node.forecast?.cost) ?? 0), 0);
  const results = conversions.reduce((sum, node) => sum + sessions.get(node.id), 0);
  const revenue = conversions.reduce((sum, node) => sum + sessions.get(node.id) * (number(node.forecast?.value) ?? 0), 0);
  return {
    nodes: Object.fromEntries([...sessions].map(([id, value]) => [id, value])), edges: flows,
    totals: {visits, cost, results, revenue, conversionRate: visits ? results / visits * 100 : null,
      costPerResult: results ? cost / results : null, roas: cost ? revenue / cost : null},
    missingRates, overAllocated, returns: [...back],
  };
}

export const forecastScenarios = config => Object.fromEntries(FORECAST_SCENARIOS.map(scenario => [scenario.id, computeForecast(config, scenario.factor)]));

export const hasForecastInput = config => (config.nodes || []).some(node => node.forecast && Object.keys(node.forecast).length)
  || (config.edges || []).some(edge => forecastRate(edge) != null);
