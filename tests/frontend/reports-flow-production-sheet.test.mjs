import test from 'node:test';
import assert from 'node:assert/strict';
import {buildProductionSheet, productionSheetCsv, productionSheetHtml} from '../../frontend/reports-v1/flowProductionSheet.js';
import {FLOW_STRATEGIES, buildStrategyConfig} from '../../frontend/reports-v1/flowStrategies.js';

const config = {nodes: [
  {id: 'meta', type: 'source', kind: 'traffic.meta', title: 'Meta Ads'},
  {id: 'lp', type: 'page', title: 'Landing', status: 'planned', spec: {goal: 'Converter', owner: 'Ana', due_date: '2026-10-20', suggested_path: '/oferta'}},
  {id: 'home', type: 'page', title: 'Home', path: '/'},
  {id: 'lead', type: 'conversion', title: 'Lead', status: 'in_production', spec: {headline: '=HYPERLINK("http://mal")'}},
  {id: 'nota', type: 'note', title: 'Combinar com o cliente', checklist: [{text: 'Aprovar oferta', done: true}, {text: 'Revisar LGPD', done: false}]},
], edges: []};

test('a folha agrupa por seção e mede o progresso só pelos passos medidos', () => {
  const sheet = buildProductionSheet(config);
  assert.deepEqual(sheet.sections.map(section => section.id), ['page', 'tracking', 'source', 'note']);
  assert.deepEqual(sheet.progress, {done: 1, total: 3});
  assert.equal(sheet.openChecklist, 1);
  const landing = sheet.sections[0].items.find(item => item.id === 'lp');
  assert.deepEqual(landing.missing, ['Endereço final']);
  const lead = sheet.sections[1].items[0];
  assert.deepEqual(lead.missing, ['Endereço final', 'Objetivo', 'Responsável', 'Prazo']);
  assert.equal(sheet.sections[2].items[0].missing.length, 0);
});

test('o CSV não deixa a planilha executar fórmulas e separa por ponto e vírgula', () => {
  const csv = productionSheetCsv(buildProductionSheet(config));
  assert(csv.startsWith('﻿Seção;Passo;'));
  assert.match(csv, /"'=HYPERLINK\(""http:\/\/mal""\)"/);
  assert.match(csv, /\[x\] Aprovar oferta\n\[ \] Revisar LGPD/);
});

test('o documento para impressão escapa o conteúdo e não tem script', () => {
  const html = productionSheetHtml(buildProductionSheet({nodes: [{id: 'x', type: 'page', title: '<img src=x onerror=alert(1)>', status: 'planned'}]}), {name: 'Plano <b>', host: 'site.com'});
  assert.doesNotMatch(html, /<img|<script|<b>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /0 de 1 passos prontos/);
});

test('toda estratégia gera uma folha com todas as páginas pendentes de endereço', () => {
  for (const strategy of FLOW_STRATEGIES) {
    const sheet = buildProductionSheet(buildStrategyConfig(strategy));
    assert.equal(sheet.progress.done, 0, strategy.id);
    assert(sheet.progress.total > 0, strategy.id);
  }
});
