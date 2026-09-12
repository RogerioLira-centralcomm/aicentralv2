#!/usr/bin/env node
'use strict';

const assert = require('assert');
const path = require('path');
const queue = require(path.join(
  __dirname,
  '../../aicentralv2/static/js/mc-dsa-write-queue.js'
));

function testMergeTwoFastEdits() {
  let pending = queue.emptyPatch();
  pending = queue.mergePatch(pending, { tokens: { ink: '#111111' } });
  pending = queue.mergePatch(pending, { tokens: { 'cta-radius': '0.2rem' } });
  assert.deepStrictEqual(pending.tokens, {
    ink: '#111111',
    'cta-radius': '0.2rem',
  });
  assert.strictEqual(queue.patchIsEmpty(pending), false);
}

async function testTwoQueuedWritesSecondDiscarded() {
  const sent = [];
  const results = await queue.runQueuedWrites(
    [
      { extra: { tokens: { ink: '#111111' } }, revision: 1, epoch: 0 },
      { extra: { tokens: { ink: '#222222' } }, revision: 1, epoch: 0 },
    ],
    { revision: 1, epoch: 0 },
    async (body) => {
      sent.push(body);
    }
  );
  assert.strictEqual(results[0].ok, true);
  assert.strictEqual(results[0].sentRevision, 1);
  assert.strictEqual(results[0].body.expected_revision, 1);
  assert.strictEqual(results[1].discarded, 'stale_after_local');
  assert.strictEqual(results[1].message, queue.DISCARDED_STALE_LOCAL);
  assert.strictEqual(results[1].revision, 1);
  assert.strictEqual(sent.length, 1);
  assert.notStrictEqual(results[1].revision, 2);
}

function testDoesNotRelabel() {
  assert.throws(
    () => queue.relabelJob({ extra: { tokens: { ink: '#111' } }, revision: 1 }, 2),
    /Não reetiquete/
  );
}

function testConflictMessage() {
  const reason = queue.queuedWriteReason(1, 1, 0, 1, false);
  assert.strictEqual(reason, 'conflict');
  assert.strictEqual(queue.messageFor(reason), queue.DISCARDED_EDIT);
  assert.strictEqual(queue.BRAND_CONFLICT, 'A marca mudou. Recarregue.');
}

(async () => {
  testMergeTwoFastEdits();
  await testTwoQueuedWritesSecondDiscarded();
  testDoesNotRelabel();
  testConflictMessage();
  console.log('mc_dsa_write_queue_test ok');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
