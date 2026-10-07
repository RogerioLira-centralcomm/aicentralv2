// Central de alertas (ocorrências, monitores e oportunidades) against simulated APIs. Run after building Reports:
//   REPORTS_BUILD_DIR=<vite outDir> node tests/frontend/reports-alerts.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const buildDir = process.env.REPORTS_BUILD_DIR || path.resolve(__dirname, '../../aicentralv2/static/cadu_connect/react');
const clientId = 1000000000;
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

const alert = (id, overrides = {}) => ({id, rule: 'page_down', channel: 'site', kind: 'incident', severity: 'high', status: 'open', resolution: null, title: 'Página indisponível',
  summary: 'exemplo.com.br/lp falhou em 3 verificações seguidas.', evidence: [{label: 'Falhas seguidas', value: 3, unit: 'count'}, {label: 'Código HTTP', value: 503, unit: 'count'}],
  impact: {value: 'erro 503', unit: 'text', label: 'página fora do ar'}, page_path: '/lp', occurrences: 3, assigned_to: null, assigned_name: null, acknowledged_at: null, silenced_until: null,
  first_seen_at: '2026-10-01T10:00:00Z', last_seen_at: '2026-10-01T12:00:00Z', resolved_at: null, site_id: 'site-1', site_label: 'Site principal', allowed_host: 'exemplo.com.br',
  causes: [], recommendations: [], ...overrides});

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.setDefaultTimeout(10000);
  const errors = [], posts = [], lists = [], saved = [];
  const panelData = {metrics: [{label: 'Taxa de conversão', value: 0.8, unit: 'percent', previous: 1.1, change: -27.3}, {label: 'Visitas', value: 4582, unit: 'count', previous: 4085, change: 12.2}],
    series: {labels: ['2026-09-30', '2026-10-01', '2026-10-02'], current: [1.0, 0.9, 0.8], previous: [1.2, 1.1, null], unit: 'percent', current_label: 'Período atual', previous_label: 'Período anterior'},
    impacted_urls: [{path: '/lp', sessions: 4582, conversions: 37, rate: 0.8, change: -27.3}], causes: ['A URL ficou abaixo de 95% de disponibilidade em 2 dias dos últimos 7 (pior dia: 80%).']};
  let current = alert('a1', panelData);
  const resolved = alert('a2', {status: 'resolved', resolution: 'auto', resolved_at: '2026-10-01T11:00:00Z', title: 'Super Tag sem enviar eventos', severity: 'medium', page_path: null, impact: null});
  const opportunity = alert('a3', {kind: 'opportunity', rule: 'device_conversion_low', severity: 'low', title: 'Aparelho ou tela converte abaixo da média', page_path: null, impact: {value: 1.2, unit: 'percent', label: 'conversão'}});
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/workspace/api/creditos/resumo', route => route.fulfill({json: {monthly_usage_percentage: 10}}));
  await page.route('**/connect/api/v2/reports/**', route => {
    const request = route.request();
    const url = new URL(request.url());
    const name = url.pathname.replace('/connect/api/v2/reports', '');
    if (name === '/bootstrap') return route.fulfill({json: {ready: true, client: {client_id: clientId, client_name: 'Cliente', role: 'admin'}, csrf: 'csrf-alertas',
      clients: [{id: clientId, name: 'Cliente'}], accounts: [], campaigns: [], reports: [], link_tests: [], workspace_projects: [], features: {}}});
    if (name === '/alerts/summary') return route.fulfill({json: {tabs: {incidents: 1, monitors: 2, opportunities: 1}, active: 1, opened_delta: 1, investigating: 0, resolved_today: 2,
      resolved_today_change: 100, uptime: 99.2, uptime_change: -0.4, estimated_impact: null, conversion_value_set: false}});
    if (name === '/alerts/settings' && request.method() === 'GET') return route.fulfill({json: {can_edit: true, emails_enabled: false, conversion_value: null, rules: [
      {rule: 'page_down', channel: 'site', kind: 'incident', severity: 'high', title: 'Página indisponível', when: 'Falhou em 2 verificações seguidas.', enabled: true, notify: true,
        tunable: {label: 'Verificações seguidas com falha', unit: 'vezes', default: 2, min: 2, max: 10, step: 1, value: 2}},
      {rule: 'channel_entry_exit', channel: 'journey', kind: 'opportunity', severity: 'low', title: 'Canal entra e sai', when: 'Insight.', enabled: true, notify: true, tunable: null},
      {rule: 'gads_cap_reached', channel: 'google_ads', kind: 'incident', severity: 'high', title: 'Google Ads: teto atingido', when: 'Gasto no teto.', enabled: true, notify: true, tunable: null}]}});
    if (name === '/alerts/settings' && request.method() === 'PUT') { saved.push({csrf: request.headers()['x-csrf-token'], body: request.postDataJSON()}); return route.fulfill({json: {ok: true}}); }
    if (name === '/alerts/a1/analyze') { posts.push({action: 'analyze', csrf: request.headers()['x-csrf-token'], body: request.postDataJSON()}); return route.fulfill({json: {ok: true, text: '**O que aconteceu**\n\nA conversão caiu.\n\n**Hipóteses**\nA URL ficou fora do ar.'}}); }
    if (name === '/alerts/monitors') {
      const heat = Array.from({length: 90}, (_, index) => index < 10 ? null : index % 20 === 0 ? [80, 900] : [100, 400]);
      const url = (path, label, vital, extra = {}) => ({flow_id: 'f1', flow_name: 'Fluxo Verão', host: 'exemplo.com.br', path, label, state: vital === 'critical' ? 'offline' : 'online', vital,
        http_status: vital === 'critical' ? 503 : 200, duration_ms: 420, average_ms: 450, detail: 'Página respondendo', uptime: 99, readings: 30, streak: vital === 'critical' ? 2 : 0,
        down_since: vital === 'critical' ? '2026-10-01T11:00:00Z' : null, last_checked_at: '2026-10-01T12:00:00Z', uptime_90: 99.2, days_measured: 80,
        pulse: ['online', 'online', vital === 'critical' ? 'offline' : 'online'], heat, ...extra});
      return route.fulfill({json: {emails_enabled: false, rules: [{rule: 'page_down', title: 'Página indisponível', when: 'Falhou em 2 verificações seguidas.'}],
        summary: {critical: 1, attention: 0, stable: 1, total: 2}, urls: [url('/orcamento', 'Orçamento', 'critical'), url('/contato', 'Contato', 'stable')],
        monitors: [{kind: 'collection', id: 's1', name: 'Site principal', target: 'exemplo.com.br', health: 'ok', last_checked_at: '2026-10-01T11:59:00Z', events_24h: 120}]}});
    }
    if (name === '/alerts' && request.method() === 'GET') {
      lists.push(Object.fromEntries(url.searchParams));
      const kind = url.searchParams.get('kind'), status = url.searchParams.get('status');
      const alerts = kind === 'opportunity' ? [opportunity] : status === 'resolved' ? [resolved] : [current];
      return route.fulfill({json: {user_id: 42, emails_enabled: false, silence_choices: [1, 24, 168], page: 1, per_page: 10, page_sizes: [10, 25, 50], total: alerts.length, rules: [], alerts}});
    }
    if (name === '/alerts/a1/events') return route.fulfill({json: {events: [{kind: 'notification_skipped', detail: {reason: 'flow_monitor'}, created_at: '2026-10-01T10:00:00Z'}, {kind: 'opened', detail: {}, created_at: '2026-10-01T10:00:00Z'}]}});
    const match = name.match(/^\/alerts\/a1\/(acknowledge|assign|silence|unsilence|investigate|resolve)$/);
    if (match && request.method() === 'POST') {
      posts.push({action: match[1], csrf: request.headers()['x-csrf-token'], body: request.postDataJSON()});
      if (match[1] === 'assign') current = {...current, assigned_to: 42, assigned_name: 'Ana'};
      if (match[1] === 'silence') current = {...current, status: 'silenced', silenced_until: '2026-10-02T12:00:00Z'};
      if (match[1] === 'unsilence') current = {...current, status: 'open', silenced_until: null};
      if (match[1] === 'investigate') current = {...current, status: 'investigating'};
      if (match[1] === 'resolve') current = {...current, status: 'resolved', resolution: 'manual', resolved_at: '2026-10-01T12:30:00Z'};
      return route.fulfill({json: {ok: true}});
    }
    return route.fulfill({json: {}});
  });

  await page.goto(`${base}/connect/app/alerts`);
  const row = page.getByRole('row', {name: /Página indisponível/});
  await row.waitFor();
  const text = await page.locator('.alerts-center').innerText();
  for (const expected of ['Ocorrências ativas', 'Resolvidas hoje', 'Uptime dos sites', '99,2%', 'erro 503', 'Alta', 'Ativo']) assert.ok(text.includes(expected), `a central deve mostrar "${expected}"`);
  assert.ok(text.includes('Impacto estimado') && text.includes('Informar valor por conversão') && !text.includes('R$'), 'sem o valor por conversão não há número em R$, só o convite para informá-lo');
  assert.deepEqual([lists[0].kind, lists[0].status], ['incident', 'active']);

  await page.getByRole('button', {name: /Mais filtros/}).click();
  await page.getByLabel('Responsável').selectOption('me');
  await page.getByRole('button', {name: /Mais filtros \(1\)/}).waitFor();
  assert.equal(lists.at(-1).assigned, 'me', 'o filtro de responsável chega à API');
  await page.getByLabel('Última ocorrência').selectOption('7');
  assert.equal(lists.at(-1).seen, '7');
  await page.getByLabel('Responsável').selectOption('');
  await page.getByLabel('Última ocorrência').selectOption('');
  await row.click();
  const panel = page.getByRole('complementary', {name: /Detalhes: Página indisponível/});
  await panel.waitFor();
  const panelText = await panel.innerText();
  for (const expected of ['falhou em 3 verificações', 'Taxa de conversão', '4.582', 'no período anterior', 'Evolução', 'URLs impactadas', '/lp', 'sem responsável']) assert.ok(panelText.includes(expected), `o painel deve mostrar "${expected}"`);
  assert.ok((await panel.getByRole('link', {name: 'Ver em Site & Jornada'}).getAttribute('href')).includes('site_id=site-1'), 'liga ao detalhe da página');

  await panel.getByRole('group', {name: /Evolução/}).focus();
  await page.keyboard.press('ArrowLeft');
  assert.match(await panel.locator('.al-chart figcaption').innerText(), /01\/10 · Período atual: 0,9% · Período anterior: 1,1%/, 'o gráfico lê cada dia pelas setas');
  await panel.getByRole('tab', {name: 'Evidências'}).click();
  await panel.getByText('Falhas seguidas').waitFor();
  await panel.getByRole('button', {name: 'Investigar com IA'}).click();
  await panel.getByText('A URL ficou fora do ar.').waitFor();
  assert.equal(await panel.locator('.al-ai__text strong').first().innerText(), 'O que aconteceu', 'a resposta da IA mostra o negrito como texto, sem HTML');
  const analysis = posts.find(item => item.action === 'analyze');
  assert.equal(analysis.csrf, 'csrf-alertas', 'a IA também exige o token CSRF');
  posts.splice(posts.indexOf(analysis), 1);
  await panel.getByRole('tab', {name: 'Visão geral'}).click();
  await panel.getByRole('button', {name: 'Assumir'}).click();
  await panel.getByText('responsável: Ana').waitFor();
  assert.equal(posts[0].csrf, 'csrf-alertas', 'ações enviam o token CSRF');
  assert.equal(posts[0].body.client_id, undefined, 'o cliente vem da sessão, não do corpo');
  assert.equal(posts[0].body.assign, true);
  await panel.getByLabel('Duração do silêncio').selectOption('168');
  await panel.getByRole('button', {name: 'Silenciar'}).click();
  await panel.getByText('silenciado até').waitFor();
  assert.equal(posts[1].body.hours, 168, 'silêncio de 7 dias');
  assert.equal(await panel.getByRole('button', {name: 'Em investigação'}).count(), 0, 'alerta silenciado não entra em investigação');
  await panel.getByRole('button', {name: 'Remover silêncio'}).click();
  await panel.getByRole('button', {name: 'Em investigação'}).click();
  await page.getByRole('row').filter({hasText: 'Em investigação'}).waitFor();
  assert.equal(posts[3].action, 'investigate');
  await panel.getByRole('tab', {name: 'Histórico'}).click();
  await panel.getByText('Alerta aberto').waitFor();
  assert.ok((await panel.locator('.alerts-history').innerText()).includes('a queda já é avisada pelo monitor de páginas'), 'o histórico explica por que não houve e-mail');
  await panel.getByRole('tab', {name: 'Possíveis causas'}).click();
  await panel.getByText('A URL ficou abaixo de 95% de disponibilidade').waitFor();
  await panel.getByText('não provam a causa').waitFor();

  await panel.getByRole('button', {name: 'Marcar como resolvido'}).click();
  await panel.getByRole('tab', {name: 'Visão geral'}).click();
  await page.getByText('resolvido manualmente em').waitFor();
  assert.equal(posts[4].action, 'resolve');
  assert.equal(await panel.getByRole('button', {name: 'Marcar como resolvido'}).count(), 0, 'resolvidos não têm ações');

  await page.getByLabel('Status').selectOption('resolved');
  await page.getByRole('row', {name: /Super Tag sem enviar eventos/}).waitFor();
  assert.equal(lists.at(-1).status, 'resolved');

  await page.getByRole('tab', {name: /Oportunidades/}).click();
  await page.getByRole('row', {name: /Aparelho ou tela converte abaixo da média/}).waitFor();
  assert.equal(lists.at(-1).kind, 'opportunity');
  await page.getByRole('tab', {name: /Monitores/}).click();
  const card = page.getByRole('article').filter({hasText: 'Orçamento'});
  await card.waitFor();
  await page.getByText('Estável', {exact: true}).waitFor();   // cards are painted lazily (content-visibility), so read the text only once it is rendered
  await card.getByText('Crítico', {exact: true}).waitFor();
  const monitors = await page.locator('.alerts-center').innerText();
  for (const expected of ['Crítico', 'HTTP 503', 'Estável', 'Coleta da Super Tag', '120 eventos em 24 h', 'E-mail desativado neste ambiente', 'Quando um alerta abre']) assert.ok(monitors.includes(expected), `monitores devem mostrar "${expected}"`);
  assert.ok((await card.getByRole('link', {name: 'Abrir saúde'}).getAttribute('href')).endsWith('/flows/f1/monitor'), 'liga à saúde do fluxo');
  assert.equal(await card.locator('.uti-beat').evaluate(node => getComputedStyle(node).animationDuration), '3s', 'o bullet pulsa a cada 3 segundos');
  assert.equal(await card.locator('.uti-heat i[data-i]').count(), 90, 'o mapa de calor tem 90 dias');
  await card.locator('.uti-heat').focus();
  await page.keyboard.press('ArrowDown');
  assert.match(await card.locator('.uti-readout').innerText(), /% disponível|sem leitura/, 'as setas leem cada dia');
  await card.locator('.uti-heat i[data-i="20"]').hover();
  assert.match(await card.locator('.uti-readout').innerText(), /80% disponível · 900 ms/, 'o mouse lê o dia');
  await card.getByRole('button', {name: /Orçamento/}).click();
  await card.getByText('fora do ar desde').waitFor();
  await page.getByRole('button', {name: /Estáveis/}).click();
  assert.equal(await page.getByRole('article').filter({hasText: 'Orçamento'}).count(), 0, 'o filtro Estáveis esconde o crítico');
  await page.getByRole('button', {name: /Todas/}).click();
  await page.getByLabel('Buscar URL ou fluxo').fill('contato');
  assert.equal(await page.locator('.uti-card').count(), 1, 'a busca filtra as URLs');

  await page.getByRole('tab', {name: /Ocorrências/}).click();
  await page.getByRole('button', {name: 'Informar valor por conversão'}).click();
  const drawer = page.getByRole('dialog', {name: 'Configurar alertas'});
  await drawer.getByText('Página indisponível', {exact: true}).waitFor();
  assert.ok((await drawer.innerText()).includes('O envio de e-mail está desligado neste ambiente'), 'avisa que o e-mail está desligado');
  await drawer.getByLabel(/R\$ por conversão/).fill('120,50');
  await drawer.getByLabel(/Verificações seguidas com falha/).fill('4');
  await drawer.getByText('Avisar por e-mail').first().click();
  await drawer.getByText('Google Ads', {exact: false}).first().click();
  await drawer.getByText('Google Ads: teto atingido').waitFor();
  await drawer.getByRole('button', {name: 'Salvar configuração'}).click();
  await page.getByRole('dialog', {name: 'Configurar alertas'}).waitFor({state: 'detached'});
  assert.deepEqual(saved[0].body, {rules: {page_down: {notify: false, threshold: 4}}, conversion_value: 120.5}, 'só o que mudou é enviado');
  assert.equal(saved[0].csrf, 'csrf-alertas');
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(300);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'sem rolagem horizontal no celular');
  assert.deepEqual(errors, [], 'sem erros de JavaScript');
  await browser.close();
  server.close();
  console.log('reports-alerts: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
