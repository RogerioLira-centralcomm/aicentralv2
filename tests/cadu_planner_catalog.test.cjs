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
