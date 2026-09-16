const {test} = require('node:test');
const assert = require('node:assert/strict');
require('../aicentralv2/static/cadu_workspace/conversations/stream.js');
const {queued} = globalThis.CaduConversationStream;
const run = {run_id:'run', conversation_id:'thread'};
const event = (id, kind, extra = {}) => ({id, event:{event:kind, ...extra}});
async function collect(fetchPage, overrides = {}) {
  const result = [];
  for await (const data of queued(run, {signal:new AbortController().signal, fetchPage,
    sleep:async () => {}, ...overrides})) result.push(data);
  return result;
}
test('network retry retains cursor and ignores replayed IDs', async () => {
  const cursors = [], retries = []; let calls = 0;
  const result = await collect(async cursor => {
    cursors.push(cursor);
    if (++calls === 1) return {status:'running', events:[event(1,'start'), event(2,'message',{text:'Olá'})]};
    if (calls === 2) throw new TypeError('network');
    return {status:'completed', events:[event(2,'message',{text:'Olá'}), event(3,'message',{text:' mundo'}), event(4,'done',{status:'completed'})]};
  }, {onRetry:attempt => retries.push(attempt)});
  assert.deepEqual(cursors, [0,2,2]);
  assert.deepEqual(retries, [1]);
  assert.equal(result.filter(x => x.event === 'message').map(x => x.text).join(''), 'Olá mundo');
  assert.equal(result.filter(x => x.event === 'start').length, 1);
});
test('fresh page rebuilds from zero and terminal status can close a missing done event', async () => {
  let seen;
  const result = await collect(async cursor => {
    seen = cursor;
    return {status:'completed', events:[event(20,'message',{text:'Texto salvo'})]};
  });
  assert.equal(seen, 0);
  assert.deepEqual(result.at(-1), {event:'done', status:'completed'});
});
test('terminal state drains a full page before ending', async () => {
  const cursors = [];
  const result = await collect(async cursor => {
    cursors.push(cursor);
    return {status:'completed', events: cursor === 0 ? Array.from({length:100}, (_, i) => event(i+1,'message',{text:'a'})) : [event(101,'message',{text:'b'})]};
  });
  assert.deepEqual(cursors, [0,100]);
  assert.equal(result.filter(x => x.event === 'message').length, 101);
});
test('authorization and missing runs fail immediately without retries', async () => {
  for (const status of [401,403,404]) {
    let calls = 0;
    await assert.rejects(collect(async () => { calls++; throw Object.assign(new Error('denied'), {status}); }), /denied/);
    assert.equal(calls, 1);
  }
});
test('transient failures have bounded exponential retry, never call send', async () => {
  const delays = []; let calls = 0;
  await assert.rejects(collect(async () => { calls++; throw Object.assign(new Error('unavailable'), {status:503}); },
    {sleep:async ms => delays.push(ms)}), /unavailable/);
  assert.equal(calls, 4);
  assert.deepEqual(delays, [1000,2000,4000]);
});
test('aborting does not replay further events or make another request', async () => {
  const controller = new AbortController(); let calls = 0;
  await assert.rejects(collect(async () => {
    calls++; controller.abort(); return {status:'running', events:[]};
  }, {signal:controller.signal}), {name:'AbortError'});
  assert.equal(calls, 1);
});
test('invalid events and unknown statuses fail closed', async () => {
  for (const page of [{status:'mystery', events:[]}, {status:'running', events:[{id:'x', event:{event:'message'}}]}]) {
    await assert.rejects(collect(async () => page), /inválido/);
  }
});
test('five-minute deadline stops observation, not the worker', async () => {
  let calls = 0, time = 0;
  await assert.rejects(collect(async () => { calls++; return {status:'running', events:[]}; },
    {now:() => time, sleep:async () => {time = 300001;}}), /processamento continua/);
  assert.equal(calls, 1);
});
