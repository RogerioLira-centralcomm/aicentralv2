import test from 'node:test';
import assert from 'node:assert/strict';
import {pageUrl, parsePageUrl, suggestedHost} from '../../frontend/reports-v1/flowPageUrl.js';

test('a URL completa vira host e caminho, sem consulta nem âncora', () => {
  assert.deepEqual(parsePageUrl('https://www.Cliente.com.br/oferta/black-friday?utm_source=x#topo'), {host: 'www.cliente.com.br', path: '/oferta/black-friday'});
  assert.deepEqual(parsePageUrl('cliente.com.br'), {host: 'cliente.com.br', path: '/'});
  assert.deepEqual(parsePageUrl('http://cliente.com.br:8080/a'), {host: 'cliente.com.br', path: '/a'});
});

test('caminho relativo continua aceito e entradas ruins explicam o erro', () => {
  assert.deepEqual(parsePageUrl('/oferta?x=1'), {host: '', path: '/oferta'});
  assert.deepEqual(parsePageUrl('  '), {empty: true});
  assert.match(parsePageUrl('//evil.com/x').error, /URL completa/);
  assert.match(parsePageUrl('isso não é url').error, /URL/);
  assert.match(parsePageUrl('ftp://cliente.com.br/x').error, /URL com domínio/);
  assert.match(parsePageUrl('semponto').error, /domínio/);
});

test('exibição usa a URL completa quando há domínio', () => {
  assert.equal(pageUrl({host: 'a.com', path: '/oferta'}), 'https://a.com/oferta');
  assert.equal(pageUrl({host: 'a.com', path: '/'}), 'https://a.com');
  assert.equal(pageUrl({path: '/oferta'}), '/oferta');
  assert.equal(pageUrl({}), '');
  assert.equal(suggestedHost({nodes: [{path: '/x'}, {host: 'b.com', path: '/'}]}), 'b.com');
});
