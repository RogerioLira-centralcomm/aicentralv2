import test from 'node:test';
import assert from 'node:assert/strict';
import {defaultMedia, entryPageFor, isPaidPlatform, mediaProgress, utmLink} from '../../frontend/reports-v1/flowMedia.js';
import {FLOW_STRATEGIES, buildStrategyConfig} from '../../frontend/reports-v1/flowStrategies.js';
import {buildProductionSheet} from '../../frontend/reports-v1/flowProductionSheet.js';

test('cada plataforma recebe criativos e checklist de setup adequados', () => {
  const meta = defaultMedia('meta', 'leads');
  assert.equal(meta.objective, 'leads');
  assert.deepEqual(meta.creatives.map(item => item.format), ['imagem', 'video']);
  assert(meta.setup.some(item => item.text.includes('Pixel')));
  assert.deepEqual(defaultMedia('email').creatives.map(item => item.format), ['mensagem']);
  assert.equal(defaultMedia('organic').creatives.length, 0);
  assert.equal(defaultMedia('organic').setup.length, 1);
});

test('o link com UTM usa a página de entrada e o público da origem', () => {
  const config = {nodes: [
    {id: 'meta', type: 'source', source: 'meta', title: 'Meta Ads', segment: {name: 'Remarketing 30 dias'}},
    {id: 'split', type: 'condition', title: 'A/B'},
    {id: 'lp', type: 'page', title: 'Oferta', path: '/oferta'},
  ], edges: [{id: 'a', from: 'meta', to: 'split'}, {id: 'b', from: 'split', to: 'lp'}]};
  assert.equal(entryPageFor(config, 'meta').id, 'lp');
  const link = utmLink(config.nodes[0], {platform: 'meta', host: 'www.cliente.com.br', entryPath: '/oferta', flowName: 'Black Friday 2026'});
  assert.equal(link.url, 'https://www.cliente.com.br/oferta?utm_source=facebook&utm_medium=paid_social&utm_campaign=black-friday-2026&utm_content=remarketing-30-dias');
  assert.equal(utmLink(config.nodes[0], {platform: 'meta', host: '', entryPath: '/oferta', flowName: 'X'}).url, '');
  const custom = utmLink({...config.nodes[0], media: {utm: {source: 'fb', campaign: 'bf26'}}}, {platform: 'meta', host: 'a.com', entryPath: '/', flowName: 'X'});
  assert.equal(custom.params.utm_source, 'fb');
  assert.equal(custom.params.utm_campaign, 'bf26');
});

test('o progresso conta criativos aprovados e setup concluído', () => {
  const progress = mediaProgress({media: {creatives: [{status: 'aprovado'}, {status: 'rascunho'}], setup: [{text: 'Pixel', done: true}, {text: 'Públicos', done: false}]}});
  assert.deepEqual(progress.creatives, {done: 1, total: 2});
  assert.deepEqual(progress.setup, {done: 1, total: 2});
  assert.deepEqual(progress.missing, ['Públicos', '1 criativo(s) sem aprovação']);
});

test('estratégias nascem com público, objetivo e mídia em cada canal pago, e a folha lista o que falta', () => {
  const plan = buildStrategyConfig(FLOW_STRATEGIES.find(item => item.id === 'leads-landing'));
  // Só canais pagos recebem público e objetivo; orgânico/direto entram sem mídia (aa82ad140).
  const sources = plan.nodes.filter(node => node.type === 'source' && isPaidPlatform(node.source));
  assert(sources.length >= 3);
  assert(sources.every(node => node.segment?.name && node.media?.objective === 'leads' && node.media.setup.length));
  assert.equal(sources.find(node => node.kind === 'traffic.retargeting').segment.kind, 'remarketing');
  const section = buildProductionSheet(plan).sections.find(item => item.id === 'source');
  const paidItems = section.items.filter(item => item.objective);
  assert(paidItems.length >= sources.length);
  assert(paidItems.every(item => !item.done && item.missing.length && item.segment));
});

test('o CSV da revisão protege fórmulas e separa por ponto e vírgula', async () => {
  const {sheetCell} = await import('../../frontend/reports-v1/flowProductionSheet.js');
  assert.equal(sheetCell('=SOMA(A1)'), "'=SOMA(A1)");
  assert.equal(sheetCell('a;b'), '"a;b"');
  assert.equal(sheetCell('linha 1\nlinha 2'), '"linha 1\nlinha 2"');
  assert.equal(sheetCell('ok'), 'ok');
});
