import test from 'node:test';
import assert from 'node:assert/strict';
import {flowGoal, isEngagementFlow} from '../../frontend/reports-v1/flowGoals.js';
import {wireNewNodes, entryPageOf} from '../../frontend/reports-v1/flowOrigins.js';
import {flowValidation} from '../../frontend/reports-v1/flowValidation.js';

const page = {id: 'p', type: 'page', path: '/', x: 400, y: 300};
const source = (id, y = 0) => ({id, type: 'source', source: id, y});

test('a saved goal wins; institutional sites default to navigation', () => {
  assert.equal(flowGoal({}), 'conversion');
  assert.equal(flowGoal({site_kind: 'institucional'}), 'navigation');
  assert.equal(flowGoal({site_kind: 'institucional', goal: 'conversion'}), 'conversion');
  assert.equal(isEngagementFlow({goal: 'time'}), true);
});

test('only the conversion goal requires a conversion node to publish', () => {
  const codes = goal => flowValidation({goal, nodes: [page], edges: []}).map(issue => issue.code);
  assert.ok(codes('conversion').includes('no_conversion'));
  for (const goal of ['time', 'reach', 'navigation']) assert.ok(!codes(goal).includes('no_conversion'));
});

test('loose origins join the entry page once and sit in one column', () => {
  const config = {nodes: [page, source('a'), source('b', 40)], edges: []};
  const {config: wired, wired: count} = wireNewNodes(config, new Set(['a', 'b']));
  assert.equal(count, 2);
  assert.deepEqual(wired.edges.map(edge => edge.to), ['p', 'p']);
  assert.deepEqual(wired.nodes.filter(n => n.type === 'source').map(n => n.y), [240, 360]);
  // Nothing new was added, or the person already wired it: leave the map alone.
  assert.equal(wireNewNodes(wired, new Set(wired.nodes.map(n => n.id))).wired, 0);
});

test('an edge the person removed is not redrawn, and an ambiguous entry is not guessed', () => {
  const two = {nodes: [{...page, path: '/a', id: 'a'}, {...page, path: '/b', id: 'b'}, source('s')], edges: []};
  assert.equal(entryPageOf(two), null);
  assert.equal(wireNewNodes(two, new Set(['a', 'b'])).wired, 0);
});
