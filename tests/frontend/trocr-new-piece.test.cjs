const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('aicentralv2/static/js/mc-trocar.js', 'utf8');
const start = source.slice(source.indexOf('  async function startNewRun()'), source.indexOf('  async function resetHistory()'));
test('failed new-run request preserves the current editor', async () => {
  let cleared = false;
  const context = vm.createContext({ resetHistory: async () => { throw new Error('offline'); }, startFresh: async () => { cleared = true; } });
  vm.runInContext(start, context);
  await assert.rejects(context.startNewRun(), /offline/);
  assert.equal(cleared, false);
});
test('new-run request completes before clearing the current editor', async () => {
  const calls = [];
  const context = vm.createContext({ resetHistory: async () => calls.push('saved'), startFresh: async () => calls.push('cleared') });
  vm.runInContext(start, context);
  await context.startNewRun();
  assert.deepEqual(calls, ['saved', 'cleared']);
});
