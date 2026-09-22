const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const moduleUrl = pathToFileURL(path.resolve(__dirname, '../../frontend/conversations-v2/lib/executionQueue.mjs')).href;

test('conversation queue is capped, editable and reorderable', async () => {
  const queue = await import(moduleUrl);
  let items = [];
  for (let index = 0; index < 7; index += 1) {
    items = queue.enqueue(items, {id: String(index), prompt: `Pedido ${index}`});
  }
  assert.equal(items.length, 5);
  items = queue.updateQueued(items, '1', 'Pedido revisado');
  assert.equal(items[1].prompt, 'Pedido revisado');
  items = queue.moveQueued(items, '1', -1);
  assert.equal(items[0].id, '1');
});

test('conversation queues persist independently', async () => {
  const queue = await import(moduleUrl);
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  queue.writeQueue('conversation-a', [{id: 'a', prompt: 'Primeiro'}], storage);
  queue.writeQueue('conversation-b', [{id: 'b', prompt: 'Segundo'}], storage);
  assert.equal(queue.readQueue('conversation-a', storage)[0].prompt, 'Primeiro');
  assert.equal(queue.readQueue('conversation-b', storage)[0].prompt, 'Segundo');
});
