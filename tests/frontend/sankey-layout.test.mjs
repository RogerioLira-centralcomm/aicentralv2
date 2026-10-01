import assert from 'node:assert/strict';
import test from 'node:test';
import {sankeyLayout} from '../../frontend/reports-v1/sankeyLayout.js';

const graph = {
  nodes: [{id: 'o:a', column: 0}, {id: 'o:b', column: 0}, {id: 'page', column: 1}, {id: 'n:x', column: 2}, {id: 'n:y', column: 2}, {id: 'r', column: 3}],
  links: [{source: 'o:a', target: 'page', value: 30}, {source: 'o:b', target: 'page', value: 10},
    {source: 'page', target: 'n:x', value: 25}, {source: 'page', target: 'n:y', value: 15},
    {source: 'n:x', target: 'r', value: 25}, {source: 'n:y', target: 'r', value: 15}],
};

test('every column stacks inside the drawing height and keeps one shared scale', () => {
  const out = sankeyLayout(graph, {height: 300, gap: 10});
  for (const column of [0, 1, 2, 3]) {
    const list = out.nodes.filter(node => node.column === column);
    const last = list.reduce((a, b) => (a.y > b.y ? a : b));
    assert.ok(last.y + last.h <= 300 + 1e-6, `coluna ${column} cabe na altura`);
  }
  const page = out.nodes.find(node => node.id === 'page');
  assert.equal(page.h, 40 * out.scale);
});

test('a node is as tall as the sessions that pass through it and nodes are sorted by size', () => {
  const out = sankeyLayout(graph);
  assert.equal(out.nodes.find(node => node.id === 'o:a').h, 30 * out.scale);
  assert.ok(out.nodes.find(node => node.id === 'o:a').y < out.nodes.find(node => node.id === 'o:b').y);
});

test('ribbons keep their width end to end and never overlap on the same node', () => {
  const out = sankeyLayout(graph);
  const intoPage = out.links.filter(link => link.target === 'page');
  assert.equal(intoPage.reduce((sum, link) => sum + link.width, 0).toFixed(6), out.nodes.find(node => node.id === 'page').h.toFixed(6));
  for (const link of out.links) assert.equal(link.width, link.value * out.scale);
  assert.ok(out.links.every(link => /^M[\d.]+,[\d.]+ C/.test(link.path)));
});

test('an empty graph lays out without NaN', () => {
  const out = sankeyLayout({nodes: [], links: []});
  assert.deepEqual(out.nodes, []);
  const single = sankeyLayout({nodes: [{id: 'a', column: 0}], links: []});
  assert.equal(single.nodes[0].h, 0);
});
