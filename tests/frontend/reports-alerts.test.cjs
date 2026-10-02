// Alert center against simulated APIs. Run after building Reports:
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

const alert = (id, overrides = {}) => ({id, rule: 'page_down', severity: 'high', status: 'open', resolution: null, title: 'Página indisponível',
  summary: 'exemplo.com.br/lp falhou em 3 verificações seguidas.', evidence: [{label: 'Falhas seguidas', value: 3, unit: 'count'}, {label: 'Código HTTP', value: 503, unit: 'count'}],
  page_path: '/lp', occurrences: 3, assigned_to: null, assigned_name: null, acknowledged_at: null, silenced_until: null, first_seen_at: '2026-10-01T10:00:00Z',
  last_seen_at: '2026-10-01T12:00:00Z', resolved_at: null, site_id: 'site-1', site_label: 'Site principal', allowed_host: 'exemplo.com.br', ...overrides});

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.setDefaultTimeout(10000);
  const errors = [], posts = [];
  let current = alert('a1');
  const resolved = alert('a2', {status: 'resolved', resolution: 'auto', resolved_at: '2026-10-01T11:00:00Z', title: 'Super Tag sem enviar eventos', severity: 'medium', page_path: null});
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/workspace/api/creditos/resumo', route => route.fulfill({json: {monthly_usage_percentage: 10}}));
  await page.route('**/connect/api/v2/reports/**', route => {
    const request = route.request();
    const url = new URL(request.url());
    const name = url.pathname.replace('/connect/api/v2/reports', '');
    if (name === '/bootstrap') return route.fulfill({json: {ready: true, client: {client_id: clientId, client_name: 'Cliente', role: 'admin'}, csrf: 'csrf-alertas',
      clients: [{id: clientId, name: 'Cliente'}], accounts: [], campaigns: [], reports: [], link_tests: [], workspace_projects: [], features: {}}});
    if (name === '/alerts' && request.method() === 'GET') return route.fulfill({json: {user_id: 42, emails_enabled: false, silence_choices: [1, 24, 168],
      rules: [{rule: 'page_down', title: 'Página indisponível', when: 'Falhou em 2 verificações seguidas.'}],
      alerts: url.searchParams.get('status') === 'resolved' ? [resolved] : [current]}});
    if (name === '/alerts/a1/events') return route.fulfill({json: {events: [{kind: 'notification_skipped', detail: {reason: 'disabled'}, created_at: '2026-10-01T10:00:00Z'}, {kind: 'opened', detail: {}, created_at: '2026-10-01T10:00:00Z'}]}});
    const match = name.match(/^\/alerts\/a1\/(acknowledge|assign|silence|unsilence)$/);
    if (match && request.method() === 'POST') {
      posts.push({action: match[1], csrf: request.headers()['x-csrf-token'], body: request.postDataJSON()});
      if (match[1] === 'acknowledge') current = {...current, status: 'acknowledged', acknowledged_at: '2026-10-01T12:05:00Z'};
      if (match[1] === 'assign') current = {...current, assigned_to: 42, assigned_name: 'Ana'};
      if (match[1] === 'silence') current = {...current, status: 'silenced', silenced_until: '2026-10-02T12:00:00Z'};
      return route.fulfill({json: {ok: true}});
    }
    return route.fulfill({json: {}});
  });

  await page.goto(`${base}/connect/app/alerts`);
  await page.getByRole('heading', {name: 'Página indisponível'}).first().waitFor();
  const text = await page.locator('.alerts-center').innerText();
  for (const expected of ['Prioridade alta', 'falhou em 3 verificações', 'Falhas seguidas', '503', 'sem responsável', 'E-mail desativado neste ambiente', 'Quando um alerta abre']) assert.ok(text.includes(expected), `a central deve mostrar "${expected}"`);
  assert.ok((await page.getByRole('link', {name: 'Ver página'}).getAttribute('href')).includes('site_id=site-1'), 'liga ao detalhe da página');
  assert.ok((await page.getByRole('link', {name: 'Ver coleta do site'}).getAttribute('href')).includes('/supertag/sites/site-1'), 'liga à coleta do site');

  await page.getByRole('button', {name: 'Reconhecer'}).click();
  await page.getByText('Reconhecido em').waitFor();
  assert.equal(posts[0].csrf, 'csrf-alertas', 'ações enviam o token CSRF');
  assert.equal(posts[0].body.client_id, clientId);
  await page.getByRole('button', {name: 'Assumir'}).click();
  await page.getByText('responsável: Ana').waitFor();
  assert.equal(posts[1].body.assign, true);
  await page.getByLabel('Duração do silêncio').selectOption('168');
  await page.getByRole('button', {name: 'Silenciar'}).click();
  await page.getByText('Silenciado até').waitFor();
  assert.equal(posts[2].body.hours, 168, 'silêncio de 7 dias');
  await page.getByRole('button', {name: 'Remover silêncio'}).waitFor();
  assert.equal(await page.getByRole('button', {name: 'Reconhecer'}).count(), 0, 'alerta silenciado não oferece reconhecer');

  await page.getByRole('button', {name: 'Histórico'}).click();
  await page.getByText('Alerta aberto').waitFor();
  assert.ok((await page.locator('.alerts-history').innerText()).includes('envio de e-mail desativado'), 'o histórico explica por que não houve e-mail');

  await page.getByRole('tab', {name: 'Resolvidos'}).click();
  await page.getByText('Resolvido automaticamente em').waitFor();
  assert.equal(await page.getByRole('button', {name: 'Reconhecer'}).count(), 0, 'resolvidos não têm ações');
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(300);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'sem rolagem horizontal no celular');
  assert.deepEqual(errors, [], 'sem erros de JavaScript');
  await browser.close();
  server.close();
  console.log('reports-alerts: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
