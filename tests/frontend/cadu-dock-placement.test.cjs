const test = require('node:test');
const assert = require('node:assert/strict');

test('dock insertion is sensitive across the full icon height', async () => {
  const {insertionIndexFromCenters} = await import('../../frontend/cadu-design-system/dockPlacement.mjs');
  assert.equal(insertionIndexFromCenters([20, 67, 114], 0), 0);
  assert.equal(insertionIndexFromCenters([20, 67, 114], 43), 1);
  assert.equal(insertionIndexFromCenters([20, 67, 114], 90), 2);
  assert.equal(insertionIndexFromCenters([20, 67, 114], 150), 3);
});

test('dock reorder follows visible insertion slot in both directions', async () => {
  const {reorderAtInsertion} = await import('../../frontend/cadu-design-system/dockPlacement.mjs');
  const items = ['brand', 'project', 'link'];
  const identity = item => item;
  assert.deepEqual(reorderAtInsertion(items, 'brand', 3, identity), ['project', 'link', 'brand']);
  assert.deepEqual(reorderAtInsertion(items, 'link', 0, identity), ['link', 'brand', 'project']);
  assert.deepEqual(reorderAtInsertion(items, 'project', 2, identity), items);
  assert.deepEqual(reorderAtInsertion(items, 'missing', 0, identity), items);
});

test('dock order keeps saved shortcuts not visible in the current catalog', async () => {
  const {completeDockOrder} = await import('../../frontend/cadu-design-system/dockPlacement.mjs');
  assert.deepEqual(completeDockOrder(['new', 'brand'], ['brand', 'hidden', 'new']), ['new', 'brand', 'hidden']);
});
