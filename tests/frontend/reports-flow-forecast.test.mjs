import test from 'node:test';
import assert from 'node:assert/strict';
import {computeForecast, forecastScenarios, hasForecastInput} from '../../frontend/reports-v1/flowForecast.js';
import {FLOW_STRATEGIES, buildStrategyConfig} from '../../frontend/reports-v1/flowStrategies.js';

const config = {nodes: [
  {id: 'meta', type: 'source', forecast: {visits: 10000, cost: 5000}},
  {id: 'google', type: 'source', forecast: {visits: 2000, cost: 3000}},
  {id: 'lp', type: 'page'}, {id: 'form', type: 'form'},
  {id: 'lead', type: 'conversion', forecast: {value: 50}},
  {id: 'nota', type: 'note'},
], edges: [
  {id: 'a', from: 'meta', to: 'lp', forecast: {rate: 100}}, {id: 'b', from: 'google', to: 'lp', forecast: {rate: 100}},
  {id: 'c', from: 'lp', to: 'form', forecast: {rate: 30}}, {id: 'd', from: 'form', to: 'lead', forecast: {rate: 50}},
  {id: 'volta', from: 'form', to: 'lp', forecast: {rate: 20}},
]};

test('as visitas descem pelas taxas até a conversão e os totais fecham', () => {
  const result = computeForecast(config);
  assert.equal(result.nodes.lp, 12000);
  assert.equal(result.nodes.form, 3600);
  assert.equal(result.nodes.lead, 1800);
  assert.deepEqual(result.returns, ['volta']);
  assert.equal(result.totals.visits, 12000);
  assert.equal(result.totals.cost, 8000);
  assert.equal(result.totals.revenue, 90000);
  assert.equal(result.totals.conversionRate, 15);
  assert.equal(Math.round(result.totals.costPerResult * 100) / 100, 4.44);
  assert.equal(result.totals.roas, 11.25);
});

test('os cenários mudam as taxas do meio do funil, não as visitas compradas', () => {
  const {pessimistic, likely, optimistic} = forecastScenarios(config);
  assert.equal(pessimistic.totals.visits, likely.totals.visits);
  assert(pessimistic.totals.results < likely.totals.results && likely.totals.results < optimistic.totals.results);
  assert.equal(Math.round(optimistic.nodes.form), 4500);
});

test('taxa ausente vira aviso e uma saída acima de 100% é sinalizada', () => {
  const result = computeForecast({nodes: [{id: 's', type: 'source', forecast: {visits: 100}}, {id: 'x', type: 'page'}, {id: 'y', type: 'page'}, {id: 'z', type: 'page'}],
    edges: [{id: 'sx', from: 's', to: 'x'}, {id: 'xy', from: 'x', to: 'y', forecast: {rate: 80}}, {id: 'xz', from: 'x', to: 'z', forecast: {rate: 40}}]});
  assert.deepEqual(result.missingRates, ['sx']);
  assert.equal(result.totals.results, 0);
  assert.equal(result.totals.costPerResult, null);
  const over = computeForecast({nodes: [{id: 's', type: 'source', forecast: {visits: 100}}, {id: 'x', type: 'page'}, {id: 'y', type: 'page'}, {id: 'z', type: 'page'}],
    edges: [{id: 'sx', from: 's', to: 'x', forecast: {rate: 100}}, {id: 'xy', from: 'x', to: 'y', forecast: {rate: 80}}, {id: 'xz', from: 'x', to: 'z', forecast: {rate: 40}}]});
  assert.deepEqual(over.overAllocated, ['x']);
});

test('estratégias já trazem taxas de referência em todas as conexões', () => {
  for (const strategy of FLOW_STRATEGIES) {
    const plan = buildStrategyConfig(strategy);
    assert(plan.edges.every(edge => edge.forecast?.rate != null), strategy.id);
    assert(hasForecastInput(plan), strategy.id);
    const visits = {...plan, nodes: plan.nodes.map(node => node.type === 'source' ? {...node, forecast: {visits: 1000}} : node)};
    const result = computeForecast(visits);
    assert.deepEqual(result.missingRates, [], strategy.id);
    assert.deepEqual(result.overAllocated, [], strategy.id);
    assert(result.totals.results > 0, strategy.id);
  }
});
