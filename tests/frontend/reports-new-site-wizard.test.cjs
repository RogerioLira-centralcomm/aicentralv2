// Site, fluxo e Super Tag: site criado ao sair do 1º passo, código para instalar, fluxo e regra de conversão no fim.
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
const SITE = {id: '11111111-1111-4111-8111-111111111111', label: 'Padaria Sol', allowed_host: 'padaria.test', enabled: true, config: {}, config_version: 1, customer_id: 10,
  snippet: '<script src="https://x.test/v1/supertag.js" data-site="pub_123" async></script>', snippet_gtm: '<script>/* gtm */</script>'};

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    page.setDefaultTimeout(8000);
    const calls = [], errors = [];
    let sites = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const request = route.request(), pathname = new URL(request.url()).pathname.replace('/connect/api/v2/reports', '');
      if (request.method() !== 'GET') {
        calls.push({method: request.method(), path: pathname, body: request.postDataJSON()});
        if (pathname === '/supertag/sites') {sites = [SITE]; return route.fulfill({status: 201, json: {site: SITE}});}
        if (pathname === '/flow/flows') return route.fulfill({status: 201, json: {flow: {id: 'flow-9'}}});
        return route.fulfill({json: {ok: true}});
      }
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
      if (pathname === '/supertag/site-check') return route.fulfill({json: {host: 'padaria.test', title: 'Padaria Sol', status: 200}});
      if (pathname === '/supertag/sites') return route.fulfill({json: {sites}});
      if (pathname.endsWith('/verify-install')) return route.fulfill({json: {host: 'padaria.test', reachable: true, status: 200, tag_in_html: true, gtm_detected: false}});
      return route.fulfill({json: {}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/supertag`);
    await page.getByRole('button', {name: /Assistente: site, fluxo e Super Tag/}).click();
    const dialog = page.getByRole('dialog', {name: 'Site, fluxo e Super Tag'});
    await dialog.waitFor();

    // 1 · site: só avança com o domínio verificado; o site é criado ao sair do passo.
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled());
    await dialog.getByLabel('Endereço do site').fill('padaria.test');
    await dialog.getByRole('button', {name: 'Verificar'}).click();
    await dialog.getByText('Respondeu').waitFor();
    assert.equal(await dialog.getByLabel('Nome desta instalação').inputValue(), 'Padaria Sol');
    if (shots) await page.screenshot({path: path.join(shots, 'site-1440.png')});
    assert.equal(calls.length, 0, 'nada é criado antes de continuar');
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled(), 'todo site pertence a um cliente');
    await dialog.getByLabel('Cliente / anunciante').selectOption('10');
    await dialog.getByRole('button', {name: 'Continuar'}).click();
    await dialog.getByRole('heading', {name: 'Instale a Super Tag'}).waitFor();
    assert.deepEqual(calls.map(call => call.path), ['/supertag/sites']);
    assert.equal(calls[0].body.allowed_host, 'padaria.test');
    assert.equal(calls[0].body.customer_id, '10', 'o site nasce no cliente escolhido');

    // 2 · Super Tag: código e verificação.
    await dialog.getByLabel('Código da Super Tag').getByText(/supertag\.js/).waitFor();
    await dialog.getByRole('button', {name: 'Verificar instalação'}).click();
    await dialog.getByText('Super Tag encontrada no site').waitFor();
    await dialog.getByRole('radio', {name: 'Google Tag Manager'}).click();
    assert.ok((await dialog.getByLabel('Código da Super Tag').textContent()).includes('gtm'));
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 3 · fluxo · voltar e avançar não cria o site de novo.
    await dialog.getByRole('heading', {name: 'Monte o caminho do visitante'}).waitFor();
    await dialog.getByRole('button', {name: 'Voltar'}).click();
    await dialog.getByRole('button', {name: 'Continuar'}).click();
    assert.equal(calls.filter(call => call.path === '/supertag/sites').length, 1);
    await dialog.getByLabel('Nome do fluxo').fill('Jornada Padaria');
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 4 · conversão: página específica exige endereço válido.
    await dialog.getByRole('heading', {name: 'O que conta como resultado?'}).waitFor();
    await dialog.getByRole('radio', {name: /Uma página específica/}).click();
    assert.ok(await dialog.getByRole('button', {name: 'Continuar'}).isDisabled());
    await dialog.getByLabel('Endereço da página').fill('/obrigado');
    await dialog.getByRole('button', {name: 'Continuar'}).click();

    // 5 · revisão
    await dialog.getByRole('heading', {name: 'Publicar e começar a medir'}).waitFor();
    assert.ok(await dialog.getByText('Jornada Padaria').isVisible());
    if (shots) {
      for (const [name, width, height] of [['tablet', 820, 1100], ['phone', 390, 844]]) {
        await page.setViewportSize({width, height}); await page.waitForTimeout(150);
        await page.screenshot({path: path.join(shots, `site-${name}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `sem rolagem horizontal em ${width}px`);
      }
      await page.setViewportSize({width: 1440, height: 900});
    }
    await dialog.getByRole('button', {name: 'Criar fluxo e abrir o editor'}).click();
    await page.waitForURL(url => url.pathname.includes('/flows/flow-9'));
    const patch = calls.find(call => call.method === 'PATCH');
    assert.deepEqual(patch.body.conversion_rules, [{type: 'path', match: 'exact', value: '/obrigado'}]);
    const flow = calls.find(call => call.path === '/flow/flows');
    assert.deepEqual({name: flow.body.name, host: flow.body.allowed_host}, {name: 'Jornada Padaria', host: 'padaria.test'});
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
