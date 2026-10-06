// Renders the Página 360 route against simulated APIs. Run after building Reports:
//   REPORTS_BUILD_DIR=<vite outDir> node tests/frontend/reports-page-detail.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const buildDir = process.env.REPORTS_BUILD_DIR || path.join(root, 'aicentralv2/static/cadu_connect/react');
const clientId = 1000000000;
const siteId = '8f1f2c3a-0000-4000-8000-000000000001';
const html = `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"></head><body class="portal--workspace"><div id="cadu-reports-v1-root" data-user-name="Teste"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>`;
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname.startsWith('/static/cadu_connect/react/')) {
    const file = path.join(buildDir, url.pathname.slice('/static/cadu_connect/react/'.length));
    res.writeHead(200, {'Content-Type': file.endsWith('.css') ? 'text/css' : 'text/javascript'});
    return res.end(fs.readFileSync(file));
  }
  res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
  res.end(html);
});

let captureState = {status: 'missing', device: 'mobile', captured_at: null, width: null, height: null, image_url: null, available: true};
const captureCalls = [];
const metrics = {sessions: 124, visitors: 98, views: 140, entrances: 100, exits: 60, exit_rate: 48.4, single_page_rate: 35,
  avg_active_seconds: 83, median_active_seconds: 45, scroll_25: 80, scroll_50: 55, scroll_75: 30, scroll_100: 12, clicks: 70,
  clicks_per_session: 0.56, form_submits: 9, conversions_on_page: 4, converted_sessions: 11, session_conversion_rate: 8.9,
  measured_visits: 90, reliable: true};
const overview = {
  page: {site_id: siteId, site_label: 'Site principal', host: 'exemplo.com.br', path: '/lp/verao'},
  window: {days: 30, since: '2026-09-01T00:00:00Z', until: '2026-10-01T00:00:00Z', timezone: 'America/Sao_Paulo', rolling: true},
  has_data: true, metrics, previous: {...metrics, sessions: 100},
  previous_unavailable: null, change: {sessions: {absolute: 24, relative: 24}, session_conversion_rate: {absolute: -1.2, relative: -12}},
  sources: [{platform: 'google', label: 'Google Ads', sessions: 80, converted_sessions: 9}, {platform: 'direct', label: 'Acesso direto', sessions: 44, converted_sessions: 2}],
  devices: [{device: 'mobile', label: 'Celular', sessions: 90, converted_sessions: 8}, {device: 'desktop', label: 'Computador', sessions: 34, converted_sessions: 3}],
  paid: {available: true, note: 'Nota de teste.', campaigns: [{campaign_external_id: '111', campaign_name: 'Verão Search', currency: 'BRL', clicks: 100, cost_micros: 50000000, conversions: 5, cost_per_conversion_micros: 10000000}],
    observed_campaigns: [{utm_campaign: 'verao', sessions: 70, converted_sessions: 9, matched_campaign_id: null}],
    search_terms: [{search_term: 'tênis de verão', clicks: 40, cost_micros: 20000000, conversions: 2}],
    keywords: [{keyword_text: 'tênis', match_type: 'PHRASE', quality_score: 7, clicks: 40, cost_micros: 20000000}]},
  health: {monitored: true, latest: {status: 'online', http_status: 200, duration_ms: 180, checked_at: '2026-10-01T12:00:00Z', detail: 'Página respondendo'},
    timeline: [{status: 'online', checked_at: '2026-10-01T12:00:00Z'}, {status: 'offline', checked_at: '2026-10-01T11:00:00Z'}]},
  dictionary: [{key: 'sessions', label: 'Sessões', source: 'Super Tag', definition: 'Sessões distintas.'}],
};

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.setDefaultTimeout(10000);
  const errors = [], calls = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('PAGEERROR', error.message); }); page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  await page.route('**/workspace/api/creditos/resumo', route => route.fulfill({json: {monthly_usage_percentage: 10}}));
  await page.route('**/connect/api/v2/reports/**', route => {
    const url = new URL(route.request().url());
    const name = url.pathname.replace('/connect/api/v2/reports', '');
    calls.push(name + url.search);
    if (name === '/bootstrap') return route.fulfill({json: {ready: true, client: {client_id: clientId, client_name: 'Cliente', role: 'admin'}, csrf: 'x',
      clients: [{id: clientId, name: 'Cliente'}], accounts: [], campaigns: [], reports: [], link_tests: [], workspace_projects: [], features: {}}});
    if (name === '/pages/overview') return route.fulfill({json: overview});
    if (name === '/pages/capture' && route.request().method() === 'GET') return route.fulfill({json: captureState});
    if (name === '/pages/capture' && route.request().method() === 'POST') {
      captureCalls.push({csrf: route.request().headers()['x-csrf-token'], body: route.request().postDataJSON()});
      captureState = {status: 'ready', device: 'mobile', captured_at: 1790000000, width: 390, height: 1560, message: null, available: true,
        image_url: `/connect/api/v2/reports/pages/capture/image?site_id=${siteId}&path=%2Flp%2Fverao&device=mobile&v=1`};
      return route.fulfill({status: 202, json: {...captureState, started: true}});
    }
    if (name === '/pages/capture/image') return route.fulfill({contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')});
    if (name === '/pages/suggestions') return route.fulfill({json: {skipped: ['A coleta de palavras negativas ainda não chegou para todas as contas: não dá para dizer se um termo já está bloqueado.'],
      rules: [{rule: 'negative_candidate', title: 'Termo de pesquisa para considerar como negativa', when: 'Regra de teste.'}],
      suggestions: [{id: 'paid_page_down:page', rule: 'paid_page_down', severity: 'high', title: 'Página fora do ar com anúncio gastando', summary: 'A verificação mais recente mostra a página com problema.',
        evidence: [{label: 'Estado', value: 'Indisponível', unit: 'text'}, {label: 'Custo no período', value: 50000000, unit: 'money', currency: 'BRL'}, {label: 'Cliques pagos', value: 100, unit: 'count'}],
        action: 'Confirme se a página abre.', anchor: 'saude'},
        {id: 'negative_candidate:1', rule: 'negative_candidate', severity: 'medium', title: 'Termo de pesquisa para considerar como negativa', summary: '“tênis grátis” gerou cliques sem conversão.',
          evidence: [{label: 'Termo', value: 'tênis grátis', unit: 'text'}, {label: 'Conversões', value: 0, unit: 'count'}], action: 'Avalie adicionar como negativa.', anchor: 'origem-paga'}]}});
    if (name === '/pages/conversion-map') return route.fulfill({json: {has_data: true, reliable: true, total: 100,
      nodes: [{id: 'o:google', column: 0, label: 'Google Ads'}, {id: 'o:direct', column: 0, label: 'Acesso direto'}, {id: 'page', column: 1, label: 'Esta página'},
        {id: 'n:page:/contato', column: 2, label: '/contato'}, {id: 'n:exit', column: 2, label: 'Saiu do site'}, {id: 'r:yes', column: 3, label: 'Converteu no site'}, {id: 'r:no', column: 3, label: 'Não converteu'}],
      links: [{source: 'o:google', target: 'page', value: 70}, {source: 'o:direct', target: 'page', value: 30}, {source: 'page', target: 'n:page:/contato', value: 40},
        {source: 'page', target: 'n:exit', value: 60}, {source: 'n:page:/contato', target: 'r:yes', value: 25}, {source: 'n:page:/contato', target: 'r:no', value: 15}, {source: 'n:exit', target: 'r:no', value: 60}],
      crm: {available: true, stages: [{key: 'lead', label: 'Lead', sessions: 12, rate: 12}, {key: 'qualified', label: 'Lead qualificado', sessions: 5, rate: 5}, {key: 'sale', label: 'Venda', sessions: 2, rate: 2}]},
      crm_coverage: {events: 20, with_visitor: 18}, notes: ['Nota A.', 'Nota B.']}});
    if (name === '/pages/interactions') return route.fulfill({json: {device: url.searchParams.get('device'), has_data: true, reliable: true, mixed_layouts: url.searchParams.get('device') === 'all',
      clicks: 60, unidentified_clicks: 20, sessions: 100, marked_elements: true, visibility_tracked: true,
      elements: [{element_id: 'cta-principal', clicks: 40, click_sessions: 30, share_of_sessions: 30, seen_sessions: 50, click_rate_of_seen: 60}],
      grid: {size: 10, peak: 40, total: 60, cells: Array.from({length: 10}, (_, y) => Array.from({length: 10}, (_, x) => x === 4 && y === 2 ? 40 : 0))},
      document: {columns: 10, rows: 20, peak: 30, total: 30, coverage: 50, median_height: 5400, cells: Array.from({length: 20}, (_, y) => Array.from({length: 10}, (_, x) => x === 3 && y === 7 ? 30 : 0))},
      notes: ['Nota 1.', 'Nota 2.', 'Nota 3.']}});
    if (name === '/journey/navigation') return route.fulfill({json: {totals: {sessions: 100, views: 140, single_page_sessions: 20}, paths: [], origins: [],
      pages: [{site_id: siteId, host: 'exemplo.com.br', path: '/lp/verao', views: 140, visitors: 90, entries: 80, exits: 50, single_page: 20, conversions: 4, avg_active_seconds: 42, exit_rate: 35.7}]}});
    if (name === '/supertag/sites') return route.fulfill({json: {sites: [{id: siteId, label: 'Site principal', allowed_host: 'exemplo.com.br'}]}});
    if (name === `/supertag/sites/${siteId}/events`) return route.fulfill({json: {pages: [{page_path: '/lp/verao', views: 140, conversions: 4}]}});
    return route.fulfill({json: {}});
  });

  await page.goto(`${base}/connect/app/pages?site_id=${siteId}&path=%2Flp%2Fverao&days=30`);
  await page.getByRole('heading', {name: '/lp/verao'}).waitFor();
  const text = await page.locator('.page-detail').innerText();
  for (const expected of ['124', '8,9%', '1 min 23 s', 'Google Ads', 'Celular', 'Verão Search', 'R$', 'tênis de verão', 'Sem correspondência', 'Disponível', 'Como lemos esses números']) {
    assert.ok(text.includes(expected), `a página deve mostrar "${expected}"`);
  }
  assert.ok(text.includes('▲ 24 % vs. período anterior') || text.includes('▲ 24% vs. período anterior'), 'mostra a variação de sessões');
  assert.ok(calls.some(call => call.includes('/pages/overview') && call.includes('days=30') && call.includes('path=%2Flp%2Fverao')), 'consulta o endpoint com período e caminho');
  await page.screenshot({path: process.env.SCREENSHOT_DIR ? path.join(process.env.SCREENSHOT_DIR, 'page-detail-desktop.png') : undefined, fullPage: true});

  await page.getByRole('heading', {name: 'Ações sugeridas'}).waitFor();
  await page.getByText('Prioridade alta').waitFor();
  const suggestionText = await page.locator('#acoes').innerText();
  for (const expected of ['Página fora do ar com anúncio gastando', 'R$', '50,00', 'tênis grátis', 'O que verificar', 'não dá para dizer', 'Como decidimos']) assert.ok(suggestionText.includes(expected), `as ações devem mostrar "${expected}"`);
  assert.equal(await page.locator('.page-suggestion').count(), 2, 'uma ação por sugestão');
  assert.ok((await page.locator('.page-suggestion a').first().getAttribute('href')) === '#saude', 'a ação aponta para o dado de origem');
  assert.ok(await page.locator('#saude').count() === 1 && await page.locator('#origem-paga').count() === 1, 'as âncoras existem');
  await page.getByRole('heading', {name: 'Mapa de conversão'}).waitFor();
  await page.locator('.page-detail-sankey').waitFor();
  const mapText = await page.locator('.page-detail-sankey').textContent();
  for (const expected of ['Google Ads', 'Esta página', '/contato', 'Saiu do site', 'Converteu no site', '70 · 70%']) assert.ok(mapText.includes(expected), `o mapa de conversão deve mostrar "${expected}"`);
  assert.equal(await page.locator('.page-detail-sankey-links path').count(), 7, 'uma faixa por conexão');
  const crmText = await page.locator('.page-detail-crm').innerText();
  assert.ok(crmText.includes('Lead qualificado') && crmText.includes('12'), 'mostra as etapas do CRM');
  await page.getByText('Mapa de interação').waitFor();
  const interactionText = await page.locator('.page-detail-interactions').innerText();
  for (const expected of ['cta-principal', '60%', '60 cliques em 100 sessões', '20 sem identificação']) assert.ok(interactionText.includes(expected), `o mapa deve mostrar "${expected}"`);
  assert.ok(await page.getByText('escolha um dispositivo').isVisible(), 'avisa sobre layouts misturados');
  assert.equal(await page.locator('.page-detail-heat i').count(), 100, 'a grade tem 10x10 células');
  await page.getByRole('tab', {name: 'Página inteira'}).click();
  await page.getByText('Onde clicam · página inteira').waitFor();
  assert.equal(await page.locator('.page-detail-heat--page i').count(), 200, 'a página inteira tem 10x20 faixas');
  assert.ok((await page.locator('.page-detail-interactions').innerText()).includes('50% dos cliques têm posição na página inteira'), 'informa a cobertura');
  await page.getByRole('tab', {name: 'Primeira tela'}).click();
  await page.getByLabel('Dispositivo do mapa de interação').selectOption('mobile');
  await page.getByRole('tab', {name: 'Sobre a captura'}).click();
  await page.getByText('Ainda não há captura desta página neste dispositivo.').waitFor();
  assert.ok((await page.locator('.page-detail-capture').innerText()).includes('usa tokens do provedor'), 'avisa sobre o custo da captura');
  await page.getByRole('button', {name: 'Capturar a página'}).click();
  await page.locator('.page-detail-capture-stage img').waitFor();
  assert.equal(captureCalls[0].csrf, 'x', 'a captura envia o token CSRF');
  assert.deepEqual([captureCalls[0].body.device, captureCalls[0].body.path], ['mobile', '/lp/verao']);
  assert.equal(await page.locator('.page-detail-overlay i').count(), 200, 'o calor de cliques sobre a captura tem 10x20 faixas');
  if (process.env.SCREENSHOT_DIR) await page.locator('.page-detail-interactions').screenshot({path: path.join(process.env.SCREENSHOT_DIR, 'capture-heat.png')});
  await page.getByRole('tab', {name: 'Rolagem'}).click();
  assert.equal(await page.locator('.page-detail-overlay--bands i').count(), 4, 'a rolagem tem 4 faixas');
  assert.ok((await page.locator('.page-detail-overlay--bands').textContent()).includes('80%'), 'mostra a % que chegou ao fim da faixa');
  await page.getByRole('tab', {name: 'Cliques'}).click();
  await page.getByRole('tab', {name: 'Primeira tela'}).click();
  await page.waitForFunction(() => !document.body.innerText.includes('escolha um dispositivo'));
  assert.ok(calls.some(call => call.includes('/pages/interactions') && call.includes('device=mobile')), 'filtra por dispositivo');
  await page.getByLabel('Período').selectOption('7');
  await page.waitForFunction(() => location.search.includes('days=7'));
  assert.ok(calls.some(call => call.includes('days=7')), 'troca de período refaz a consulta');

  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(300);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'sem rolagem horizontal no celular');

  // The old address lands on Site & Jornada → Páginas, a table of every page that opens the page view.
  await page.goto(`${base}/connect/app/pages`);
  await page.getByRole('heading', {name: 'Páginas'}).waitFor();
  assert.match(page.url(), /\/connect\/app\/journey\/pages/, 'endereço antigo redireciona');
  await page.getByRole('link', {name: '/lp/verao'}).waitFor();
  const href = await page.getByRole('link', {name: '/lp/verao'}).getAttribute('href');
  assert.ok(href.includes('site_id=' + siteId) && href.startsWith('/connect/app/journey/pages'), 'a lista liga à página escolhida');
  assert.equal(await page.locator('h1').count(), 1, 'um único título na página');
  assert.deepEqual(errors, [], 'sem erros de JavaScript');
  await browser.close();
  server.close();
  console.log('reports-page-detail: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
