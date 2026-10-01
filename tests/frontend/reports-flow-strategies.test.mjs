import test from 'node:test';
import assert from 'node:assert/strict';
import {FLOW_STRATEGIES, buildStrategyConfig, defaultStrategyChannels} from '../../frontend/reports-v1/flowStrategies.js';
import {flowValidation, MAX_FLOW_PAGES, isPlanned} from '../../frontend/reports-v1/flowValidation.js';

const measured = new Set(['page', 'form', 'event', 'conversion', 'whatsapp', 'error']);
const pageTypes = new Set(['page', 'form', 'conversion', 'error']);

for (const strategy of FLOW_STRATEGIES) {
  test(`estratégia ${strategy.id} gera um plano válido com os canais padrão`, () => {
    const config = buildStrategyConfig(strategy);
    const ids = new Set(config.nodes.map(node => node.id));
    assert.equal(ids.size, config.nodes.length);
    assert(config.edges.every(edge => ids.has(edge.from) && ids.has(edge.to) && edge.from !== edge.to));
    assert(config.nodes.filter(node => measured.has(node.type)).every(isPlanned), 'passos medidos nascem planejados');
    assert(config.nodes.filter(node => node.type === 'source').length >= 1);
    assert(config.nodes.filter(node => pageTypes.has(node.type)).length <= MAX_FLOW_PAGES);
    const connected = new Set(config.edges.flatMap(edge => [edge.from, edge.to]));
    assert(config.nodes.every(node => connected.has(node.id)), 'nenhum passo solto');
    const issues = flowValidation(config);
    assert.deepEqual(issues.filter(issue => issue.severity === 'error').map(issue => issue.code), []);
    assert.deepEqual(issues.filter(issue => issue.severity === 'warning').map(issue => issue.code), [], 'plano novo sem pendências');
  });
}

test('canais desmarcados saem do plano junto com as conexões', () => {
  const strategy = FLOW_STRATEGIES.find(item => item.id === 'leads-landing');
  const config = buildStrategyConfig(strategy, ['traffic.meta']);
  assert.deepEqual(config.nodes.filter(node => node.type === 'source').map(node => node.kind), ['traffic.meta']);
  const ids = new Set(config.nodes.map(node => node.id));
  assert(config.edges.every(edge => ids.has(edge.from) && ids.has(edge.to)));
});

test('cada estratégia tem canais padrão e passos com etapa', () => {
  for (const strategy of FLOW_STRATEGIES) {
    assert(defaultStrategyChannels(strategy).length > 0, strategy.id);
    assert(strategy.steps.every(step => step.stage), strategy.id);
  }
});

test('modelo do time vira um plano novo com identificadores próprios', async () => {
  const {instantiateTemplate} = await import('../../frontend/reports-v1/flowStrategies.js');
  const template = {schema_version: 3, nodes: [{id: 'a', type: 'source', title: 'Meta'}, {id: 'b', type: 'page', title: 'Oferta', status: 'planned'}],
    edges: [{id: 'e', from: 'a', to: 'b'}, {id: 'solta', from: 'a', to: 'x'}], groups: [{id: 'g', name: 'Grupo', memberIds: ['b', 'x'], bounds: {x: 0, y: 0, width: 200, height: 200}}]};
  const plan = instantiateTemplate(template);
  const ids = new Set(plan.nodes.map(node => node.id));
  assert(!ids.has('a') && !ids.has('b') && ids.size === 2);
  assert.equal(plan.edges.length, 1);
  assert(ids.has(plan.edges[0].from) && ids.has(plan.edges[0].to) && plan.edges[0].id !== 'e');
  assert.deepEqual(plan.groups[0].memberIds, [plan.nodes[1].id]);
  assert(plan.nodes.every(node => node.origin === 'template'));
  assert.equal(template.nodes[0].id, 'a');
});

test('todo plano nasce alinhado à grade e com as colunas centradas na mesma linha', async () => {
  const {FLOW_GRID, alignConfigToGrid} = await import('../../frontend/reports-v1/flowStages.js');
  for (const strategy of FLOW_STRATEGIES) {
    const plan = buildStrategyConfig(strategy);
    assert(plan.nodes.every(node => node.x % FLOW_GRID === 0 && node.y % FLOW_GRID === 0), strategy.id);
    const columns = new Map();
    for (const node of plan.nodes) columns.set(node.x, [...(columns.get(node.x) || []), node.y]);
    const middles = [...columns.values()].map(ys => (Math.min(...ys) + Math.max(...ys)) / 2);
    assert(Math.max(...middles) - Math.min(...middles) <= FLOW_GRID, `${strategy.id}: colunas na mesma linha do meio`);
  }
  const off = {nodes: [{id: 'a', x: 83, y: 247}, {id: 'b', x: 410, y: 331}], groups: [{id: 'g', memberIds: ['a'], bounds: {x: 11, y: 29, width: 301, height: 95}}]};
  const aligned = alignConfigToGrid(off);
  assert.deepEqual(aligned.nodes.map(node => [node.x, node.y]), [[80, 240], [420, 340]]);
  assert.deepEqual(aligned.groups[0].bounds, {x: 20, y: 20, width: 300, height: 100});
  assert.equal(alignConfigToGrid(aligned), aligned);
});
