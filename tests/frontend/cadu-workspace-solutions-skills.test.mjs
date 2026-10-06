import test from 'node:test';
import assert from 'node:assert/strict';
import {workspaceSolutionItems, workspaceMobileSolutionItems} from '../../frontend/cadu-design-system/workspaceSolutions.js';

const base = {workspace: '/w', planner: '/p', studio: '/s', connect: '/r'};

test('Skills some do seletor quando o servidor não publica a URL (CADU_SKILLS_ENABLED desligada)', () => {
  const ids = workspaceSolutionItems({urls: {solutions: base}}).map(item => item.id);
  assert.deepEqual(ids, ['workspace', 'planner', 'studio', 'connect']);
  assert.ok(!workspaceMobileSolutionItems({solutions: base}).some(item => item.id === 'skills'));
  assert.ok(!workspaceSolutionItems({urls: {solutions: {...base, skills: ''}}}).some(item => item.id === 'skills'));
});

test('Skills volta quando a URL está no bootstrap (CADU_SKILLS_ENABLED=true)', () => {
  const urls = {...base, skills: '/k'};
  assert.ok(workspaceSolutionItems({urls: {solutions: urls}}).some(item => item.id === 'skills' && item.href === '/k'));
  assert.ok(workspaceMobileSolutionItems({solutions: urls}).some(item => item.id === 'skills'));
});

test('soluções sem URL continuam listadas (só Skills depende da chave)', () => {
  const ids = workspaceSolutionItems({}).map(item => item.id);
  assert.deepEqual(ids, ['workspace', 'planner', 'studio', 'connect']);
});
