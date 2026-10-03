// Super Tag site panel (built React app, API mocked): tabs with their own address (?site_tab=), the snippet only in
// Instalação with the "Direto no site" | "Google Tag Manager" switch, creating conversion rules of every type (the body
// sent is the one the API accepts) and the server's message shown instead of "Falha HTTP 400".
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const SITE = '6f1c2a8e-1b2c-4d3e-8f90-123456789abc';
const shots = process.env.SUPERTAG_SHOTS || '';
const site = {id: SITE, public_id: 'pubpanel', label: 'Loja Centro', allowed_host: 'loja.example.test', enabled: true, events_30d: 0, conversions_30d: 0,
  config: {audience_days: 365, retention_days: 365}, config_version: 1,
  snippet: '<!-- Cadu Super Tag · Loja Centro (loja.example.test) -->\n<script async src="https://reports.example.test/v1/supertag.js" data-cadu-site="pubpanel"></script>\n<!-- End Cadu Super Tag -->',
  snippet_gtm: "<!-- Cadu Super Tag · Loja Centro (loja.example.test) -->\n<script>\n(function (d) {\n  var s = d.createElement('script');\n  s.async = true;\n  s.src = 'https://reports.example.test/v1/supertag.js?id=pubpanel';\n  s.setAttribute('data-cadu-site', 'pubpanel');\n  (d.head || d.getElementsByTagName('head')[0]).appendChild(s);\n})(document);\n</script>\n<!-- End Cadu Super Tag -->"};
const patches = [];

const html = `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"></head><body class="portal--workspace"><div id="cadu-reports-v1-root" data-workspace-url="#" data-planner-url="#" data-studio-url="#" data-skills-url="#" data-credits-url="/workspace/app/creditos" data-profile-url="/workspace/app/conta?section=perfil" data-user-name="Teste Reports"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>`;
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname.startsWith('/static/cadu_connect/react/')) {
    const file = path.join(root, 'aicentralv2', 'static', 'cadu_connect', url.pathname.slice('/static/cadu_connect/'.length));
    if (!file.startsWith(path.join(root, 'aicentralv2', 'static', 'cadu_connect', 'react')) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, {'Content-Type': file.endsWith('.css') ? 'text/css' : 'text/javascript'});
    return res.end(fs.readFileSync(file));
  }
  res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
  return res.end(html);
});

/** Mirrors the server enough for the panel: the same normalization of rules, and a JSON 400 with a readable message. */
function serverRules(rules) {
  for (const rule of rules) {
    if (rule.type === 'event_name' && !/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(rule.value)) return 'Nome do evento: o mesmo usado em CaduSuperTag.event().';
  }
  return null;
}

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/workspace/api/creditos/resumo', route => route.fulfill({json: {monthly_usage_percentage: 10}}));
  await page.route('https://loja.example.test/**', route => route.fulfill({status: 404, body: ''}));
  await page.route('**/connect/api/v2/reports/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname.replace('/connect/api/v2/reports', '');
    const method = request.method();
    let body = {};
    try { body = request.postDataJSON() || {}; } catch (_) { /* GET */ }
    if (pathName === '/bootstrap') return route.fulfill({json: {ready: true, csrf: 'csrf-ui', clients: [{id: 1, name: 'Cliente', kind: 'reports'}],
      client: {client_id: 1, organization_id: 2, client_name: 'Cliente', role: 'admin', client_kind: 'reports'},
      can_manage_access: false, can_manage_clients: false, accounts: [], campaigns: [], reports: [], link_tests: [], workspace_projects: []}});
    if (pathName === '/supertag/sites') return route.fulfill({json: {sites: [site]}});
    if (pathName === `/supertag/sites/${SITE}/events`) return route.fulfill({json: {site: {id: SITE, events_30d: 0}, summary: [], pages: [], heatmap: [], sessions: []}});
    if (pathName === `/supertag/sites/${SITE}/conversion-rules`) return route.fulfill({json: {rules: site.config.conversion_rules || [],
      conversion_defaults: true, suggestions: [], form_capture: {enabled: true, fields: [], confirm: 'conversion'}}});
    if (pathName === `/supertag/sites/${SITE}` && method === 'PATCH') {
      assert.equal(request.headers()['x-csrf-token'], 'csrf-ui', 'PATCH leva o token CSRF');
      patches.push(body);
      const problem = body.conversion_rules && serverRules(body.conversion_rules);
      if (problem) return route.fulfill({status: 400, json: {error: problem, message: problem, code: 'http_400'}});
      site.config = {...site.config, ...body};
      site.config_version += 1;
      return route.fulfill({json: {site}});
    }
    return route.fulfill({json: {}});
  });

  try {
    await page.goto(`${origin}/connect/app/supertag/sites/${SITE}?site_tab=conversions`);
    const tabs = page.getByRole('tablist', {name: 'Áreas do site'});
    await tabs.waitFor();
    const labels = await tabs.getByRole('tab').allInnerTexts();
    assert.deepEqual(labels.map(item => item.replace(/\d+$/, '').trim()),
      ['Visão geral', 'Medição', 'Conversões', 'Identificação', 'Instalação', 'Fluxos', 'Configurações'], 'abas do painel (Atividade só com eventos)');
    assert.match(await tabs.locator('[data-cadu-tab="conversions"]').getAttribute('class'), /is-active/, 'deep link ?site_tab=conversions abre Conversões');
    await page.getByText('Página de obrigado automática', {exact: true}).waitFor();
    assert.ok(await page.getByText(/alguma parte do endereço começa com obrigad, thank, sucesso ou confirmac/).isVisible(), 'texto da regra automática corrigido');
    if (shots) await page.screenshot({path: path.join(shots, 'supertag-conversoes.png'), fullPage: true});

    const add = async (kind, field, value, name = '') => {
      await page.getByLabel('Tipo de regra').selectOption({label: kind});
      await page.getByLabel(field, {exact: true}).fill(value);
      await page.getByLabel('Nome da conversão (opcional)').fill(name);
      const before = patches.length;
      await page.getByRole('button', {name: 'Adicionar regra'}).click();
      for (let i = 0; i < 50 && patches.length === before; i++) await page.waitForTimeout(50);
      await page.waitForTimeout(200);
      assert.equal(await page.getByLabel(field, {exact: true}).inputValue(), '', `${kind}: campo limpo depois de salvar`);
      return patches[patches.length - 1];
    };
    let sent = await add('Página exata', 'Endereço da página', 'https://loja.example.test/obrigado?pedido=9', 'Lead do Site');
    assert.deepEqual(sent.conversion_rules, [{type: 'path', match: 'exact', value: '/obrigado', name: 'lead_do_site'}], 'página exata: URL colada vira caminho e nome vira slug');
    sent = await add('Página que começa com', 'Começo do endereço', 'checkout/fim');
    assert.deepEqual(sent.conversion_rules.at(-1), {type: 'path', match: 'prefix', value: '/checkout/fim'}, 'prefixo ganha a barra inicial');
    sent = await add('Parte do endereço que começa com', 'Trecho', '/sucesso/');
    assert.deepEqual(sent.conversion_rules.at(-1), {type: 'path', match: 'segment', value: 'sucesso'}, 'trecho sem barras');
    sent = await add('Formulário válido', 'Formulário (opcional)', '');
    assert.deepEqual(sent.conversion_rules.at(-1), {type: 'valid_form'}, 'formulário válido sem id');
    sent = await add('Evento próprio do site', 'Nome do evento', 'lead_enviado');
    assert.deepEqual(sent.conversion_rules.at(-1), {type: 'event_name', value: 'lead_enviado'}, 'evento próprio');
    assert.equal(sent.conversion_rules.length, 5, 'cada regra nova mantém as anteriores');

    // Local check: an invalid event name never reaches the server and explains what to fix.
    const before = patches.length;
    await page.getByLabel('Tipo de regra').selectOption({label: 'Evento próprio do site'});
    await page.getByLabel('Nome do evento', {exact: true}).fill('lead-enviado');
    await page.getByRole('button', {name: 'Adicionar regra'}).click();
    await page.getByText(/Nome do evento: letras sem acento/).waitFor();
    assert.equal(patches.length, before, 'nome de evento inválido é barrado no navegador');
    assert.equal(await page.getByText('Falha HTTP 400').count(), 0);

    // Measurement: switches only, no snippet; the snippet lives in Instalação.
    await tabs.getByRole('tab', {name: 'Medição'}).click();
    assert.match(page.url(), /site_tab=measurement/, 'a aba muda o endereço');
    await page.getByText('Medição aprimorada', {exact: true}).waitFor();
    assert.equal(await page.locator('code', {hasText: 'data-cadu-site'}).count() + await page.locator('pre', {hasText: 'data-cadu-site'}).count(), 0, 'Medição não repete o código');
    if (shots) await page.screenshot({path: path.join(shots, 'supertag-medicao.png'), fullPage: true});

    await tabs.getByRole('tab', {name: 'Instalação'}).click();
    const pre = page.locator('pre').first();
    assert.match(await pre.innerText(), /^<!-- Cadu Super Tag · Loja Centro \(loja\.example\.test\) -->/, 'snippet com comentário nomeado');
    assert.match(await pre.innerText(), /data-cadu-site="pubpanel"/);
    await page.getByRole('button', {name: 'Google Tag Manager'}).click();
    assert.match(await pre.innerText(), /createElement\('script'\)/, 'GTM mostra o carregador para HTML personalizado');
    await page.getByText(/não lê o dataLayer|não lê o/).first().waitFor();
    assert.ok(await page.getByText(/History Change/).isVisible(), 'passo a passo do GTM');
    if (shots) await page.screenshot({path: path.join(shots, 'supertag-instalacao-gtm.png'), fullPage: true});

    await tabs.getByRole('tab', {name: 'Identificação'}).click();
    await page.getByText('Associar visita a um usuário', {exact: true}).waitFor();
    await tabs.getByRole('tab', {name: 'Configurações'}).click();
    await page.getByLabel('Nome da instalação').waitFor();
    if (shots) await page.screenshot({path: path.join(shots, 'supertag-configuracoes.png'), fullPage: true});

    // A refusal from the server shows its message, not "Falha HTTP 400" (an old rule the server no longer accepts).
    site.config.conversion_rules = [{type: 'event_name', value: 'lead-antigo'}, {type: 'path', match: 'exact', value: '/fim'}];
    await page.goto(`${origin}/connect/app/supertag/sites/${SITE}?site_tab=conversions`);
    await page.getByRole('button', {name: 'Remover Página /fim'}).click();
    await page.getByRole('alert').filter({hasText: 'Nome do evento: o mesmo usado em CaduSuperTag.event().'}).waitFor();
    assert.equal(await page.getByText('Falha HTTP 400').count(), 0, 'mensagem do servidor no lugar de Falha HTTP 400');
    assert.deepEqual(errors, [], 'sem erros de JavaScript');
  } finally {
    await browser.close();
    server.close();
  }
  process.stdout.write('supertag-panel: ok\n');
}

main().catch(error => { console.error(error); process.exit(1); });
