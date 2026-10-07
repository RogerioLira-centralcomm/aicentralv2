// Novo cliente e conta: three steps, scene per step, creates the client then its first media account.
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
    res.setHeader('content-type', types[path.extname(file)] || 'application/octet-stream');
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
    const calls = [], errors = [];
    let failAccount = true;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const request = route.request(), pathname = new URL(request.url()).pathname.replace('/connect/api/v2/reports', '');
      if (request.method() !== 'GET') {
        calls.push({path: pathname, body: request.postDataJSON()});
        if (pathname === '/accounts' && failAccount) {failAccount = false; return route.fulfill({status: 400, json: {error: 'ID da conta inválido.'}});}
        return route.fulfill({status: 201, json: {customer: {id: 13}, account: {id: 50}}});
      }
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
      return route.fulfill({json: {}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/settings/accounts?customer=10`);
    await page.getByRole('heading', {name: 'Contas e campanhas'}).waitFor();
    await page.getByRole('button', {name: 'Novo cliente'}).click();
    const dialog = page.getByRole('dialog', {name: 'Novo cliente e conta'});
    await dialog.waitFor();
    assert.ok(await dialog.getByRole('heading', {name: 'Quem é o cliente?'}).isVisible());
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled(), 'sem nome não avança');
    await dialog.getByLabel('Nome do cliente ou anunciante').fill('Padaria Sol');
    if (shots) await page.screenshot({path: path.join(shots, 'wizard-1440.png')});
    await dialog.getByRole('button', {name: 'Continuar'}).click();
    await dialog.getByRole('heading', {name: 'Em que plataforma ele anuncia?'}).waitFor();
    await dialog.getByRole('radio', {name: 'Google Ads'}).click();
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled(), 'conta escolhida exige nome e ID');
    await dialog.getByLabel('Nome da conta').fill('Padaria Sol | Ads');
    await dialog.getByLabel('ID da conta').fill('123-456-7890');
    await dialog.getByRole('button', {name: 'Continuar'}).click();
    await dialog.getByRole('heading', {name: 'Tudo certo?'}).waitFor();
    assert.ok(await dialog.getByText('Padaria Sol | Ads · Google Ads').isVisible());
    if (shots) {
      for (const [name, width, height] of [['tablet', 820, 1100], ['phone', 390, 844]]) {
        await page.setViewportSize({width, height}); await page.waitForTimeout(150);
        await page.screenshot({path: path.join(shots, `wizard-${name}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `sem rolagem horizontal em ${width}px`);
      }
      await page.setViewportSize({width: 1440, height: 900});
    }
    // A failed account must not make the retry create the client twice.
    await dialog.getByRole('button', {name: 'Criar cliente'}).click();
    await dialog.getByRole('alert').waitFor();
    await dialog.getByRole('button', {name: 'Criar cliente'}).click();
    await dialog.waitFor({state: 'detached'});
    assert.deepEqual(calls.map(call => call.path), ['/customers', '/accounts', '/accounts']);
    assert.equal(calls[0].body.name, 'Padaria Sol');
    assert.deepEqual({platform: calls[1].body.platform, customer_id: calls[1].body.customer_id, external_id: calls[1].body.external_id}, {platform: 'google_ads', customer_id: 13, external_id: '123-456-7890'});

    // Escape leaves without creating anything.
    calls.length = 0;
    await page.getByRole('button', {name: 'Novo cliente'}).click();
    await page.getByRole('dialog', {name: 'Novo cliente e conta'}).waitFor();
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', {name: 'Novo cliente e conta'}).waitFor({state: 'detached'});
    assert.equal(calls.length, 0);
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
