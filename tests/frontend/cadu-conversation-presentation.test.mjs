import test from 'node:test';
import assert from 'node:assert/strict';
import {conversationContextLabel, conversationDisplayTitle} from '../../frontend/conversations-v2/lib/conversationPresentation.mjs';

test('conversation titles turn pasted links into useful labels', () => {
  assert.equal(conversationDisplayTitle('https://docs.google.com/document/d/abc/edit'), 'Documento compartilhado');
  assert.equal(conversationDisplayTitle('https://docs.google.com/document/d/abc/edit\n\nadicionar no projeto'), 'Adicionar no projeto');
  assert.equal(conversationDisplayTitle('  revisar o planejamento de mídia  '), 'Revisar o planejamento de mídia');
});

test('conversation context exposes the selected entity name without leaking its ref', () => {
  const projects = [{id:'42', projectRef:'ci:42', name:'Mídia Paga'}];
  const brands = [{id:'7', name:'Centralcomm'}];
  assert.deepEqual(conversationContextLabel({project_ref:'ci:42'}, projects, brands), {kind:'project', label:'Mídia Paga'});
  assert.deepEqual(conversationContextLabel({brand_ref:'studio:7'}, projects, brands), {kind:'brand', label:'Centralcomm'});
  assert.deepEqual(conversationContextLabel({}, projects, brands), {kind:'free', label:'Conversa livre'});
});
