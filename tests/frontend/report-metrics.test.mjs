import test from 'node:test';
import assert from 'node:assert/strict';
import {baseValues, formulaError, metricResult} from '../../frontend/reports-v1/reportMetrics.js';

const values = baseValues({cost: 1000, impressions: 20000, clicks: 400, conversions: 10, conversion_value: 5000}, {funnel: {entries: 300, conversions: 25}});

test('mesma gramática do backend', () => {
  assert.equal(metricResult({kind: 'formula', formula: '(custo + 200) / -(-conversoes_fluxo) * 2'}, values), 96);
  assert.equal(metricResult({kind: 'formula', formula: 'custo / (cliques - cliques)'}, values), null);
  assert.ok(Math.abs(metricResult({kind: 'formula', formula: 'conversoes_fluxo / entradas_fluxo', unit: 'percent'}, values) - 8.333) < 0.01);
  assert.equal(metricResult({kind: 'manual', value: '12,5'}, values), 12.5);
});

test('rejeita o que o backend rejeita', () => {
  for (const bad of ['custo ** 2', 'custo; 1', 'desconhecida / 2', 'custo /', '(custo', '', 'custo 2']) assert.notEqual(formulaError(bad), '', bad);
  assert.equal(formulaError('custo / conversoes_fluxo'), '');
});
