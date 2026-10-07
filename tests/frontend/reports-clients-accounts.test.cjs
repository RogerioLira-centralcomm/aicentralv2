// Clientes e contas: the client comes from the sidebar; Workspace brands, media accounts, campaigns and sites that always belong to a client.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const shots = process.env.WIZARD_SHOTS || '';
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/reports_clients_accounts.json'), 'utf8'));
const html = '<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"><link rel="stylesheet" href="/static/cadu_connect/react/untitled.css"></head><body class="portal portal--connect"><div id="cadu-reports-v1-root"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>';
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://x').pathname;
  if (pathname.startsWith('/static/cadu_connect/react/')) {
    const file = path.join(root, 'aicentralv2', pathname);
    if (!fs.existsSync(file)) {res.statusCode = 404; return res.end();}
    res.setHeader('content-type', file.endsWith('.css') ? 'text/css' : 'text/javascript');
    return fs.createReadStream(file).pipe(res);
  }
  res.setHeader('content-type', 'text/html'); res.end(html);
});
const boot = role => ({ready: true, features: {}, csrf: 't', reports: [], link_tests: [], workspace_projects: [],
  clients: [{client_id: 1, client_name: 'Cliente Teste'}], ...fixture.bootstrap, client: {client_id: 1, role, client_name: 'Cliente Teste'},
  can_manage_clients: role === 'admin'});

async function open(browser, role, url) {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.setDefaultTimeout(8000);
  const calls = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/connect/api/**', route => {
    const request = route.request(), pathname = new URL(request.url()).pathname.replace('/connect/api/v2/reports', '');
    if (request.method() !== 'GET') {
      calls.push({method: request.method(), path: pathname, body: request.postDataJSON()});
      return route.fulfill({status: 201, json: {saved: true, customer: {id: 13}, campaign: {id: 300}, account: {id: 50}, project_ref: 'ci:new'}});
    }
    if (pathname === '/bootstrap') return route.fulfill({json: boot(role)});
    if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
    if (pathname === '/supertag/sites') return route.fulfill({json: {sites: [
      {id: 's1', allowed_host: 'lojaverao.com.br', label: 'lojaverao.com.br', customer_id: 10, enabled: true, events_30d: 40, last_event_at: '2026-10-06T12:00:00Z'},
      {id: 's2', allowed_host: 'solto.com.br', label: 'solto.com.br', customer_id: null, enabled: true, events_30d: 0},
    ]}});
    return route.fulfill({json: {}});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}${url}`);
  await page.getByRole('heading', {name: 'Contas e campanhas'}).waitFor();
  return {page, calls, errors};
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const {page, calls, errors} = await open(browser, 'admin', '/connect/app/settings/accounts?customer=10');
    assert.equal(await page.getByRole('heading', {name: 'Loja Verão', level: 2}).count(), 1, 'o cliente escolhido abre no cabeçalho');
    assert.equal(await page.getByRole('complementary', {name: 'Clientes'}).count(), 0, 'a página não tem lista de clientes própria: usa a barra lateral');
    assert.ok(await page.getByRole('button', {name: 'Novo cliente'}).isVisible(), 'Novo cliente fica no cabeçalho da página');
    // Sites: o site do cliente aberto, o solto pode ser ligado a ele e o novo nasce no cliente.
    const sites = page.getByRole('region', {name: 'Sites'});
    assert.ok(await sites.getByText('lojaverao.com.br').isVisible());
    assert.ok(await sites.getByText('1 site sem cliente').isVisible());
    assert.ok(await sites.getByRole('button', {name: 'Site', exact: true}).isVisible());
    if (shots) await page.screenshot({path: path.join(shots, 'clients-customer.png'), fullPage: true});
    await sites.getByRole('button', {name: 'Ligar a Loja Verão'}).click();
    await page.waitForTimeout(200);
    assert.ok(await page.getByText('Gerente (MCC) · 2 contas').isVisible(), 'MCC agrupa as contas que gerencia');

    await page.getByRole('button', {name: 'Associar projeto'}).first().click();
    assert.ok(await page.getByText('Da marca deste cliente').isVisible(), 'projetos da marca do cliente vêm primeiro');
    await page.getByRole('option', {name: 'Black Friday 2026'}).click();
    await page.getByRole('button', {name: /Criar projeto “Search \| Genérico/}).click();
    // Todos os clientes: sem "+ Site" (o site precisa de cliente), o solto escolhe o cliente e as marcas livres viram clientes.
    await page.goto(page.url().replace(/\?customer=\d+/, ''));
    await page.getByRole('heading', {name: 'Todos os clientes', level: 2}).waitFor();
    assert.equal(await sites.getByRole('button', {name: 'Site', exact: true}).count(), 0);
    assert.ok(await sites.getByText('escolha o cliente na barra lateral').isVisible());
    await sites.getByLabel('Cliente de solto.com.br').selectOption('11');
    await page.waitForTimeout(200);
    const brands = page.getByRole('region', {name: 'Marcas do Workspace sem cliente'});
    assert.equal(await brands.getByRole('listitem').count(), 2, 'Café Aurora e Moda Sul ainda não são clientes');
    if (shots) await page.screenshot({path: path.join(shots, 'clients-all.png'), fullPage: true});
    await brands.getByRole('button', {name: 'Criar cliente Café Aurora'}).click();
    await page.waitForTimeout(300);

    await page.waitForURL(/customer=13/);
    await page.goto(page.url().replace(/customer=\d+/, 'customer=10'));
    await page.getByRole('button', {name: 'Conta de mídia'}).click();
    await page.getByLabel('Nome da conta').fill('Conta Shopping');
    await page.getByLabel('ID da conta').fill('987-654-3210');
    await page.getByRole('button', {name: 'Adicionar conta', exact: true}).click();
    await page.waitForTimeout(300);

    await page.getByRole('button', {name: 'Campanha', exact: true}).click();
    await page.getByLabel('Nome da campanha').fill('Shopping | Verão');
    await page.getByLabel('Projeto do Workspace').selectOption('new');
    await page.getByRole('button', {name: 'Adicionar campanha', exact: true}).click();
    await page.waitForTimeout(400);

    await page.getByLabel('Buscar conta ou campanha').fill('remarketing');
    assert.equal(await page.locator('[role=row]').count(), 3, 'a busca mantém a conta acima da campanha encontrada');

    const sent = calls.map(call => `${call.method} ${call.path}`);
    assert.deepEqual(sent, [
      'PATCH /supertag/sites/s2',
      'POST /workspace/campaign/101', 'POST /workspace/campaign/101/create-project',
      'PATCH /supertag/sites/s2',
      'POST /customers', 'POST /customers/13/brands',
      'POST /accounts',
      'POST /campaigns', 'POST /workspace/campaign/300/create-project',
    ]);
    assert.equal(calls[0].body.customer_id, 10, 'o site solto é ligado ao cliente aberto');
    assert.equal(calls[1].body.project_ref, 'ci:p1');
    assert.equal(calls[2].body.name, 'Search | Genérico | Tênis corrida', 'o projeto novo leva o nome da campanha');
    assert.equal(calls[3].body.customer_id, 11, 'em Todos os clientes o site solto escolhe o cliente');
    assert.equal(calls[5].body.brand_ref, 'ci:b3', 'o cliente criado já nasce vinculado à marca');
    assert.equal(calls[6].body.customer_id, '10', 'a conta nasce no cliente aberto');
    assert.equal(calls[7].body.customer_id, '10');
    assert.equal(calls[8].body.name, 'Shopping | Verão');
    assert.deepEqual(errors, []);
    await page.close();

    const viewer = await open(browser, 'viewer', '/connect/app/settings/clients?customer=10');
    assert.equal(await viewer.page.getByRole('button', {name: 'Campanha', exact: true}).count(), 0, 'leitura não cadastra');
    assert.equal(await viewer.page.getByRole('button', {name: 'Associar projeto'}).count(), 0, 'leitura não altera vínculos');
    assert.equal(await viewer.page.getByRole('button', {name: 'Novo cliente'}).count(), 0);
    assert.equal(await viewer.page.getByRole('region', {name: 'Sites'}).getByRole('button', {name: 'Site', exact: true}).count(), 0, 'leitura não cria site');
    assert.ok(await viewer.page.getByText('Coleção Verão').isVisible(), 'leitura ainda vê os projetos associados');
    console.log('Clientes e contas: hierarquia, marcas, projetos, cadastros e leitura aprovados');
  } finally {
    await browser.close(); server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
