const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createStore } = require('../../aicentralv2/static/js/mc-studio-library.js');
function fixture() {
  const calls = [];
  const store = createStore((url, options) => new Promise((resolve, reject) => calls.push({ url, options, resolve, reject })), () => {});
  return { calls, store };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
test('marca B prevalece quando respostas de A chegam por último; contexto repetido não duplica carga', async () => {
  const { calls, store } = fixture();
  store.context('A'); store.context('A'); assert.equal(calls.length, 2);
  store.context('B'); assert.equal(calls.length, 4); assert.equal(calls[0].options.signal.aborted, true);
  calls[2].resolve({ items: [{ name: 'B' }] }); calls[3].resolve({ items: [] }); await tick();
  calls[0].resolve({ items: [{ name: 'A' }] }); calls[1].resolve({ items: [] }); await tick();
  assert.equal(store.state.clientId, 'B'); assert.equal(store.view().items[0].name, 'B');
});
test('biblioteca completa pesquisável, mostrar mais e troca de filtro', async () => {
  const { calls, store } = fixture(); store.context('A');
  calls[0].resolve({ items: Array.from({length: 30}, (_, i) => ({ name: `Peça ${i}`, headline: i === 29 ? 'Promoção especial' : '', created_at: String(i).padStart(2, '0') })) });
  calls[1].resolve({ items: [{ name: 'Clipe' }] }); await tick();
  assert.equal(store.view().total, 31); assert.equal(store.view().items.length, 12);
  store.more(); assert.equal(store.view().items.length, 24);
  store.search('promocao'); assert.equal(store.view().total, 1); assert.equal(store.view().items[0].name, 'Peça 29');
  store.search(''); store.filter('video'); assert.equal(store.view().total, 1);
});
test('falha parcial preserva a outra mídia; retry não apaga resultados saudáveis', async () => {
  const { calls, store } = fixture(); store.context('A');
  assert.equal(store.view().loading, true);
  calls[0].resolve({ items: [{ name: 'Imagem' }] }); calls[1].reject(new Error('offline')); await tick();
  assert.deepEqual(store.view().errors, ['video']); assert.equal(store.view().total, 1);
  store.retry('video'); calls[2].resolve({ items: [{ name: 'Clipe' }] }); await tick();
  assert.equal(store.view().total, 2); assert.deepEqual(store.view().errors, []);
});
test('sem marca ou erro de contexto limpa dados e cancela respostas pendentes', async () => {
  const { calls, store } = fixture(); store.context('A'); store.context('', 'empty');
  calls[0].resolve({ items: [{ name: 'A' }] }); calls[1].resolve({ items: [] }); await tick();
  assert.equal(store.view().total, 0); assert.equal(store.state.context, 'empty');
  store.retry(); assert.equal(calls.length, 2);
});
test('resposta inválida é erro recuperável, não biblioteca vazia', async () => {
  const { calls, store } = fixture(); store.context('A'); calls[0].resolve({}); calls[1].resolve({ items: [] }); await tick();
  assert.deepEqual(store.view().errors, ['still']);
});
