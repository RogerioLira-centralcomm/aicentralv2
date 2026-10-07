// Cliente na barra lateral: o cabeçalho oferece só as campanhas e os sites dele, e cada cliente lembra a própria escolha.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
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
// Sites: o servidor devolve só os do cliente pedido.
const SITES = {10: [{id: '11111111-1111-4111-8111-111111111111', allowed_host: 'loja.test', label: 'Loja', customer_id: 10, enabled: true, events_30d: 5}],
  11: [{id: '22222222-2222-4222-8222-222222222222', allowed_host: 'farma.test', label: 'Farma', customer_id: 11, enabled: true, events_30d: 0},
    {id: '33333333-3333-4333-8333-333333333333', allowed_host: 'farma2.test', label: 'Farma 2', customer_id: 11, enabled: true, events_30d: 9}]};

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    page.setDefaultTimeout(8000);
    const siteCalls = [], errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const url = new URL(route.request().url()), pathname = url.pathname.replace('/connect/api/v2/reports', '');
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
      if (pathname === '/supertag/sites') {siteCalls.push(url.searchParams.get('customer_id')); return route.fulfill({json: {sites: SITES[url.searchParams.get('customer_id')] || []}});}
      if (pathname === '/journey/navigation') return route.fulfill({json: {pages: [], origin_groups: []}});
      return route.fulfill({json: {}});
    });
    const base = `http://127.0.0.1:${server.address().port}/connect/app`;
    const campaignOptions = () => page.getByLabel('Campanha', {exact: true}).locator('option').allTextContents();
    const pickClient = async name => {
      await page.getByRole('button', {name: /^Cliente:/}).click();
      await page.getByRole('option', {name: new RegExp(name)}).click();
    };

    // Mídia: só as campanhas do cliente escolhido.
    await page.goto(`${base}/media?customer=10`);
    await page.getByLabel('Campanha', {exact: true}).waitFor();
    let options = await campaignOptions();
    assert.ok(options.some(text => text.includes('Search | Marca | BR')));
    assert.ok(!options.some(text => text.includes('Bing | Marca')), 'campanha de outro cliente não aparece');
    await page.getByLabel('Campanha', {exact: true}).selectOption({label: 'Search | Marca | BR'});

    if (process.env.WIZARD_SHOTS) {await page.getByRole('button', {name: /^Cliente:/}).click(); await page.screenshot({path: path.join(process.env.WIZARD_SHOTS, 'sidebar-clientes.png')}); await page.keyboard.press('Escape');}
    // Trocar de cliente troca as listas e mantém a rota.
    await pickClient('Rede Farma');
    await page.waitForURL(url => url.searchParams.get('customer') === '11');
    await page.waitForFunction(() => [...document.querySelectorAll('select[aria-label="Campanha"] option')].some(option => option.textContent.includes('Bing | Marca')));
    options = await campaignOptions();
    assert.ok(!options.some(text => text.includes('Search | Marca | BR')), 'a campanha do outro cliente some');

    // Cada cliente lembra a própria escolha.
    await pickClient('Loja Verão');
    await page.waitForURL(url => url.searchParams.get('customer') === '10');
    await page.waitForFunction(() => document.querySelector('select[aria-label="Campanha"]')?.selectedOptions[0]?.textContent.includes('Search | Marca | BR'));

    // Site & Jornada: só os sites do cliente, sem "Todos os sites".
    await page.goto(`${base}/journey/pages?customer=11`);
    await page.getByLabel('Site', {exact: true}).waitFor();
    const sites = await page.getByLabel('Site', {exact: true}).locator('option').allTextContents();
    assert.deepEqual(sites.sort(), ['farma.test', 'farma2.test']);
    assert.equal(siteCalls.at(-1), '11', 'a lista de sites é pedida já filtrada pelo cliente');

    // Cliente sem site: orienta a conectar, não mostra dados de outro.
    await pickClient('Construtora Horizonte');
    await page.getByRole('heading', {name: 'Este cliente ainda não tem um site conectado'}).waitFor();
    await page.getByRole('button', {name: 'Adicionar site, fluxo e Super Tag'}).click();
    await page.getByRole('dialog', {name: 'Site, fluxo e Super Tag'}).waitFor();
    await page.keyboard.press('Escape');

    // Um fluxo aberto pelo próprio endereço (editor) não ganha ?customer= nem some atrás do aviso de "sem site".
    await page.goto(`${base}/flows/flow-1`);
    await page.waitForTimeout(800);
    assert.equal(new URL(page.url()).searchParams.get('customer'), null);
    assert.equal(await page.getByRole('heading', {name: 'Este cliente ainda não tem um site conectado'}).count(), 0);
    errors.length = 0;

    // Telas de análise nunca abrem em "todos": sem cliente na URL, volta ao último usado.
    await page.goto(`${base}/overview`);
    await page.waitForURL(url => url.searchParams.get('customer') !== null);
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
