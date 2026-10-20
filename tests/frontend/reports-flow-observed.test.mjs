import test from 'node:test';
import assert from 'node:assert/strict';
import {undrawnOrigins, addObservedOrigins, observedPageDetail, observedPassageDetail, addObservedChain, addObservedPassage, reachesGoal} from '../../frontend/reports-v1/flowObserved.js';

const n = (id, type, extra = {}) => ({id, type, title: id, x: 0, y: 0, ...extra});
const config = {nodes: [n('meta', 'source', {source: 'meta'}), n('home', 'page', {path: '/'}), n('contato', 'page', {path: '/Contato/'}),
  n('ok', 'conversion', {path: '/obrigado'})], edges: [{id: 'e1', from: 'meta', to: 'home'}, {id: 'e2', from: 'contato', to: 'ok'}]};
const step = (path, extra = {}) => ({kind: 'page', path, title: path, ...extra});

test('origins without a node are summed per platform with the drawn pages they land on', () => {
  const journey = {origin_landings: [
    {platform: 'direct', label: 'Acesso direto', node_id: 'home', sessions: 60, drawn: false},
    {platform: 'direct', label: 'Acesso direto', node_id: 'contato', sessions: 7, drawn: false},
    {platform: 'direct', label: 'Acesso direto', node_id: 'removido', sessions: 3, drawn: false},
    {platform: 'meta', label: 'Meta Ads · sem origem identificada', node_id: 'home', sessions: 2, drawn: false},
    {platform: 'organic', label: 'Busca orgânica', node_id: 'home', sessions: 6, drawn: false},
    {platform: 'meta', label: 'Meta Ads', node_id: 'home', sessions: 4, drawn: true}]};
  const origins = undrawnOrigins(journey, config);
  assert.deepEqual(origins.map(item => [item.platform, item.sessions]), [['direct', 70], ['organic', 6]]);
  assert.deepEqual(origins[0].landings.map(item => item.node_id), ['home', 'contato']);
  const {config: next, added} = addObservedOrigins(config, origins);
  assert.equal(added.length, 2);
  const direct = next.nodes.find(node => node.id === added[0]);
  assert.equal(direct.kind, 'traffic.direct');
  assert.equal(direct.source, 'direct');
  assert.deepEqual(next.edges.filter(edge => edge.from === added[0]).map(edge => edge.to), ['home', 'contato']);
  assert.deepEqual(undrawnOrigins(journey, next), [], 'once drawn, an origin is no longer listed');
});

test('an off-flow page detail finds the drawn steps around it and the most common way', () => {
  const journeys = [
    {steps: [step('/'), step('/solucoes/ctv'), step('/cases'), step('/contato'), step('/obrigado', {goal: true})]},
    {steps: [step('/'), step('/solucoes/ctv'), step('/cases'), step('/contato'), step('/obrigado', {goal: true})]},
    {steps: [step('/blog'), step('/solucoes/ctv'), step('/obrigado', {goal: true})]},
    {steps: [step('/'), step('/contato'), step('/obrigado', {goal: true})]}];
  const detail = observedPageDetail(journeys, '/Solucoes/CTV/', config);
  assert.equal(detail.conversions, 3);
  assert.deepEqual(detail.best, {before: 'home', after: 'contato', conversions: 2,
    pages: [{path: '/solucoes/ctv', title: '/solucoes/ctv'}, {path: '/cases', title: '/cases'}]});
  assert.deepEqual(detail.ways[1].before, null);
  const {config: next, created} = addObservedChain(config, detail.best);
  assert.equal(created.length, 2);
  const [ctv, cases] = created;
  assert.deepEqual(next.edges.slice(2).map(edge => [edge.from, edge.to]), [['home', ctv], [ctv, cases], [cases, 'contato']]);
  assert.ok(reachesGoal(next, ctv));
  // Creating it again reuses the pages already drawn and adds nothing.
  const again = addObservedChain(next, detail.best);
  assert.equal(again.created.length, 0);
  assert.equal(again.config.edges.length, next.edges.length);
});

test('a way that ends at the goal without a drawn step after it is chained to the goal', () => {
  const draft = {nodes: config.nodes.filter(node => node.id !== 'ok'), edges: []};
  const {config: next, created} = addObservedChain({...draft, nodes: [...draft.nodes, n('meta2', 'conversion', {path: '/fim'})]},
    {before: 'home', pages: [{path: '/x', title: 'X'}], after: null, goalId: 'meta2'});
  assert.deepEqual(next.edges.map(edge => [edge.from, edge.to]), [['home', created[0]], [created[0], 'meta2']]);
});

test('a passage between drawn steps counts conversions and links to the goal only when it leads nowhere', () => {
  const journeys = [{steps: [step('/'), step('/contato'), step('/obrigado', {goal: true})]}, {steps: [step('/'), step('/blog')]}];
  assert.deepEqual(observedPassageDetail(journeys, 'home', 'contato', config), {conversions: 1, reaches_goal: true});
  const linked = addObservedPassage(config, {from: 'home', to: 'contato', goalId: 'ok'});
  assert.deepEqual(linked.edges.slice(2).map(edge => [edge.from, edge.to]), [['home', 'contato']]);
  const loose = {...config, edges: [config.edges[0]]};
  const wired = addObservedPassage(loose, {from: 'home', to: 'contato', goalId: 'ok'});
  assert.deepEqual(wired.edges.slice(1).map(edge => [edge.from, edge.to]), [['home', 'contato'], ['contato', 'ok']]);
});
