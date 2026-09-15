const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

test('catalog client never inserts catalog strings as HTML', () => {
  const source = fs.readFileSync('aicentralv2/static/cadu_planner/catalog.js', 'utf8');
  assert.match(source, /\.textContent = value/);
  assert.match(source, /\.textContent = data\.record\.name/);
  assert.doesNotMatch(source, /innerHTML/);
});

test('catalog modal uses a server-controlled path and encodes route segments', () => {
  const source = fs.readFileSync('aicentralv2/static/cadu_planner/catalog.js', 'utf8');
  assert.match(source, /\/familia\/api\/planner\/catalog\//);
  assert.match(source, /encodeURIComponent\(button\.dataset\.catalogKind\)/);
  assert.match(source, /credentials: 'same-origin'/);
});

test('conversation cards render result text without innerHTML', () => {
  const source = fs.readFileSync('aicentralv2/static/cadu_workspace/conversations/chat.js', 'utf8');
  const card = source.slice(source.indexOf('function addCatalogCard'), source.indexOf("opener.addEventListener"));
  assert.match(card, /record\.name/);
  assert.match(card, /data\.catalog_kind/);
  assert.match(card, /textContent/);
  assert.doesNotMatch(card, /innerHTML/);
});

test('document preview uses an authenticated endpoint and textContent', () => {
  const source = fs.readFileSync('aicentralv2/static/cadu_planner/docs.js', 'utf8');
  assert.match(source, /\/familia\/api\/planner\/documents\//);
  assert.match(source, /credentials: 'same-origin'/);
  assert.match(source, /preview\.textContent = data\.preview/);
  assert.doesNotMatch(source, /innerHTML/);
});
