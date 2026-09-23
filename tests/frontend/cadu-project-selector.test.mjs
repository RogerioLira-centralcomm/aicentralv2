import test from 'node:test';
import assert from 'node:assert/strict';
import {markProjectUsed, PROJECT_RECENCY_KEY, readProjectRecency, recentProjectOptions} from '../../frontend/cadu-design-system/projectOptions.mjs';

test('project selector keeps the selected project and the ten most recently updated options', () => {
  const projects = Array.from({length:12}, (_, index) => ({
    id:`ci:${index + 1}`,
    name:`Projeto ${index + 1}`,
    updatedAt:new Date(Date.UTC(2026, 0, index + 1)).toISOString(),
  }));
  const options = recentProjectOptions(projects, 'ci:1');
  assert.equal(options.length, 10);
  assert.equal(options[0].id, 'ci:1');
  assert.deepEqual(options.slice(1).map(item => item.id), ['ci:12','ci:11','ci:10','ci:9','ci:8','ci:7','ci:6','ci:5','ci:4']);
});

test('project selector prefers actual recent use and persists it safely', () => {
  const values = new Map();
  const storage = {
    getItem:key => values.get(key) || null,
    setItem:(key, value) => values.set(key, value),
  };
  markProjectUsed('ci:2', storage, 200);
  markProjectUsed('ci:1', storage, 100);
  assert.deepEqual(readProjectRecency(storage), {'ci:2':200, 'ci:1':100});
  assert.equal(values.has(PROJECT_RECENCY_KEY), true);

  const projects = [
    {id:'ci:1', name:'Atualizado hoje', updatedAt:'2026-09-23T12:00:00Z'},
    {id:'ci:2', name:'Usado agora', updatedAt:'2026-01-01T12:00:00Z'},
  ];
  assert.equal(recentProjectOptions(projects, '', 10, readProjectRecency(storage))[0].id, 'ci:2');
});
