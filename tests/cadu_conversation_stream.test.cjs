const {test} = require('node:test');
const assert = require('node:assert/strict');
require('../aicentralv2/static/cadu_workspace/conversations/stream.js');

function body(text, step = 1) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({start(controller) {
    for (let i = 0; i < bytes.length; i += step) controller.enqueue(bytes.slice(i, i + step));
    controller.close();
  }});
}
async function read(text, step) {
  const result = [];
  for await (const event of CaduConversationStream.events(body(text, step))) result.push(event);
  return result;
}
test('fragmented UTF-8, CRLF and heartbeat comments', async () => {
  assert.deepEqual(await read(':ping\r\ndata: {"event":"message","text":"Olá 👋"}\r\n\r\n'),
    [{event:'message',text:'Olá 👋'}]);
});
test('multiple events and final frame without blank line', async () => {
  assert.deepEqual(await read('data: {"event":"start"}\n\ndata: {"event":"done"}', 256),
    [{event:'start'},{event:'done'}]);
});
test('multiline data and end marker', async () => {
  assert.deepEqual(await read('data: {"event":\ndata: "done"}\n\ndata: [DONE]\n\n'), [{event:'done'}]);
});
test('malformed and non-object payloads fail closed', async () => {
  await assert.rejects(read('data: not-json\n\n'));
  await assert.rejects(read('data: []\n\n'));
});
test('oversized unfinished frame is rejected', async () => {
  await assert.rejects(read('data: '+ 'x'.repeat(1024 * 1024 + 1), 8192), /muito grande/);
});
