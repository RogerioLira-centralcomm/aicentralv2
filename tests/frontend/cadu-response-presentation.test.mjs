import test from 'node:test';
import assert from 'node:assert/strict';
import {formatResponseParagraphs} from '../../frontend/conversations-v2/lib/responsePresentation.mjs';

test('long prose is grouped into readable paragraphs at sentence boundaries', () => {
  const source = 'Primeira frase explica o contexto com clareza. Segunda frase desenvolve o mesmo argumento de maneira objetiva. Terceira frase adiciona um exemplo importante. Quarta frase apresenta uma consequência prática. Quinta frase abre uma nova consideração para a resposta.';
  const formatted = formatResponseParagraphs(source, 130);
  assert.ok(formatted.includes('\n\n'));
  assert.equal(formatted.replace(/\n\n/g, ' '), source);
});

test('markdown lists and short paragraphs keep their original structure', () => {
  const source = 'Uma introdução curta.\n\n- Primeiro item\n- Segundo item';
  assert.equal(formatResponseParagraphs(source, 80), source);
});

test('fenced code does not disable formatting for prose that follows it', () => {
  const source = 'Introdução curta.\n\n```js\nconst answer = 42;\n```\n\nPrimeira frase longa depois do código. Segunda frase desenvolve a explicação. Terceira frase acrescenta contexto. Quarta frase encerra o raciocínio.';
  const formatted = formatResponseParagraphs(source, 75);
  assert.match(formatted, /```js\nconst answer = 42;\n```/);
  assert.match(formatted, /código\.\n\nSegunda frase/);
});
