// Conectar o Google Ads: conta/MCC → scripts com chave → campanha → primeiro envio.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const shots = process.env.WIZARD_SHOTS || '';
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/reports_clients_accounts.json'), 'utf8'));
const html = '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"><link rel="stylesheet" href="/static/cadu_connect/react/untitled.css"></head><body class="portal portal--connect"><div id="cadu-reports-v1-root"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>';
const types = {'.css': 'text/css', '.js': 'text/javascript', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml'};
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://x').pathname;
  if (pathname.startsWith('/static/')) {
    const file = path.join(root, 'aicentralv2', pathname);
    if (!file.startsWith(path.join(root, 'aicentralv2', 'static')) || !fs.existsSync(file)) {res.statusCode = 404; return res.end();}
    res.setHeader('content-type', types[path.extname(file)] || 'text/javascript');
    return fs.createReadStream(file).pipe(res);
  }
  res.setHeader('content-type', 'text/html'); res.end(html);
});
const boot = {ready: true, features: {}, csrf: 't', reports: [], link_tests: [], workspace_projects: [], clients: [{client_id: 1, client_name: 'Cliente Teste'}],
  ...fixture.bootstrap, client: {client_id: 1, role: 'admin', client_name: 'Cliente Teste'}, can_manage_clients: true};

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    page.setDefaultTimeout(8000);
    const posts = [], errors = [];
    let keys = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const request = route.request(), pathname = new URL(request.url()).pathname.replace('/connect/api/v2/reports', '');
      if (request.method() !== 'GET') {
        posts.push({path: pathname, body: request.postDataJSON()});
        if (pathname === '/ingest-keys') {
          const body = request.postDataJSON(), id = `key-${posts.length}`;
          keys.push({id, label: body.label, source_kind: body.source_kind, last_used_at: null});
          return route.fulfill({status: 201, json: {id, token: 'tok_secreto', allowed_account_ids: body.account_ids, limits: {max_budget_change_pct: 30, max_cpc_change_pct: 30}}});
        }
        return route.fulfill({status: 201, json: {campaign: {id: 900}}});
      }
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
      if (pathname === '/ingest-keys') return route.fulfill({json: {keys, runs: []}});
      if (pathname === '/google-ads/unlinked-campaigns') return route.fulfill({json: {campaigns: [{account_id: 2, account_name: 'Loja Verão — Search', campaign_external_id: '555', campaign_name: 'PMax | Verão', channel_type: 'PERFORMANCE_MAX', status: 'ENABLED'}]}});
      return route.fulfill({json: {}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/data-sources/connect`);
    await page.getByRole('button', {name: /Conectar o Google Ads|Assistente do Google Ads/}).first().click();
    const dialog = page.getByRole('dialog', {name: 'Conectar o Google Ads'});
    await dialog.waitFor();

    // 1 · fonte: a MCC com contas já vem escolhida; falta marcar a conta.
    assert.ok(await dialog.getByRole('heading', {name: 'De onde vêm os dados?'}).isVisible());
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled(), 'sem conta não avança');
    await dialog.getByRole('checkbox', {name: /Loja Verão — Search/}).check();
    if (shots) await page.screenshot({path: path.join(shots, 'gads-1440.png')});
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 2 · script: gera Leitura + Ações; só avança depois de gerar.
    await dialog.getByRole('heading', {name: 'Cole o script no Google Ads'}).waitFor();
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled(), 'precisa gerar antes de continuar');
    await dialog.getByRole('button', {name: 'Gerar os 2 scripts'}).click();
    await dialog.getByRole('heading', {name: /Script de Leitura/}).waitFor();
    assert.ok(await dialog.getByRole('heading', {name: /Script de Ações/}).isVisible());
    assert.deepEqual(posts.filter(item => item.path === '/ingest-keys').map(item => item.body.source_kind), ['google_ads_script', 'google_ads_actions']);
    assert.equal(posts[0].body.manager_account_id, '111-222-3333');
    assert.deepEqual(posts[0].body.account_ids, ['123-456-7890']);
    assert.ok((await dialog.getByLabel('Código do script de Leitura').textContent()).includes('tok_secreto'), 'a chave entra no código');
    if (shots) await page.screenshot({path: path.join(shots, 'gads-script-1440.png')});
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 3 · campanha: cadastra a que o script já mandou e uma pelo ID.
    await dialog.getByRole('heading', {name: 'Qual campanha acompanhar?'}).waitFor();
    await dialog.getByRole('button', {name: 'Cadastrar', exact: true}).click();
    await dialog.getByText('PMax | Verão').last().waitFor();
    await dialog.getByLabel('Nome da campanha').fill('Search | Marca');
    await dialog.getByLabel('ID da campanha').fill('2093840001');
    await dialog.getByRole('button', {name: 'Cadastrar campanha'}).click();
    await dialog.getByText('Search | Marca').waitFor();
    const campaigns = posts.filter(item => item.path === '/campaigns');
    assert.equal(campaigns.length, 2);
    assert.deepEqual({account: campaigns[1].body.account_id, id: campaigns[1].body.external_id}, {account: 2, id: '2093840001'});
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 4 · espera: quando a chave recebe o primeiro envio, o estado muda.
    await dialog.getByRole('heading', {name: 'Conectado. Esperando os dados'}).waitFor();
    await dialog.getByText('Aguardando primeiro envio').first().waitFor();
    keys = keys.map(item => ({...item, last_used_at: new Date().toISOString()}));
    await dialog.getByText('Dados recebidos').waitFor({timeout: 9000});
    if (shots) {
      for (const [name, width, height] of [['tablet', 820, 1100], ['phone', 390, 844]]) {
        await page.setViewportSize({width, height}); await page.waitForTimeout(150);
        await page.screenshot({path: path.join(shots, `gads-${name}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `sem rolagem horizontal em ${width}px`);
      }
    }
    await dialog.getByRole('button', {name: 'Concluir'}).click();
    await dialog.waitFor({state: 'detached'});
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
