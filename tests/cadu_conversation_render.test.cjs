const {test} = require('node:test');
const assert = require('node:assert/strict');
require('../aicentralv2/static/cadu_workspace/conversations/render.js');
const {html, visible} = globalThis.CaduConversationRenderer;
test('formats headings, lists, emphasis and code without executing model markup', () => {
  const output = html('# Plano\n- **Meta**\n- *Canal*\n```html\n<img src=x onerror=alert(1)>\n```');
  assert.match(output, /<h4>Plano<\/h4>/);
  assert.match(output, /<strong>Meta<\/strong>/);
  assert.match(output, /<em>Canal<\/em>/);
  assert.match(output, /&lt;img/);
  assert.doesNotMatch(output, /<img/);
});
test('only HTTP links become anchors, attributes are escaped', () => {
  assert.doesNotMatch(html('[x](javascript:alert) [x](data:text/html)'), /<a /);
  assert.match(html('[Fonte](https://example.com)'), /rel="noopener noreferrer"/);
  assert.doesNotMatch(html('[x](https://example.com/"onclick="evil)'), /href="[^"]*"onclick=/);
  assert.doesNotMatch(html('<script>alert(1)</script>'), /<script>/);
});
test('tables have accessible scrolling and bounded column count', () => {
  const output = html('| Canal | Valor |\n| --- | ---: |\n| Busca | 10 | extra |');
  assert.match(output, /role="region"/);
  assert.match(output, /scope="col"/);
  assert.equal((output.match(/<td>/g) || []).length, 2);
});
test('thinking is hidden even before its closing chunk arrives', () => {
  assert.equal(visible('Olá<think>privado'), 'Olá');
  assert.equal(visible('<analysis>privado</analysis>Resposta'), 'Resposta');
});
test('incomplete code fences remain escaped', () => {
  assert.match(html('```js\n<script>'), /&lt;script&gt;/);
});
