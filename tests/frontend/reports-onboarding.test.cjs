// Conhecer o Reports: entrada na barra lateral, capítulos, estado do ambiente e ações que abrem os assistentes.
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
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const pathname = new URL(route.request().url()).pathname.replace('/connect/api/v2/reports', '');
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (pathname === '/workspace/map') return route.fulfill({json: fixture['/workspace/map']});
      if (pathname === '/supertag/sites') return route.fulfill({json: {sites: []}});
      if (pathname === '/ingest-keys') return route.fulfill({json: {keys: [], runs: []}});
      return route.fulfill({json: {}});
    });
    // One scene is missing on purpose: its chapter keeps a brand block instead of a broken image.
    await page.route('**/onb-3-midia.webp', route => route.fulfill({status: 404}));
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/overview`);
    // A tela fica logo abaixo de Visão geral, na barra lateral.
    const links = await page.getByRole('navigation', {name: /Seções do Reports/}).getByRole('link').allTextContents();
    assert.deepEqual(links.slice(0, 2).map(text => text.trim()), ['Visão geral', 'Conhecer o Reports']);
    await page.getByRole('link', {name: 'Conhecer o Reports'}).click();
    await page.waitForURL('**/connect/app/onboarding**');
    await page.getByRole('heading', {name: 'Bem-vindo ao Reports', level: 2}).waitFor();
    await page.waitForFunction(() => document.querySelector('.ob-scene img')?.naturalWidth > 0);
    assert.equal(await page.locator('.ob-scene--empty').count(), 0, 'com a imagem, não há bloco de marca');
    if (shots) await page.screenshot({path: path.join(shots, 'onboarding-1440.png')});

    // Capítulos: botão Começar, passos clicáveis e setas do teclado.
    await page.getByRole('button', {name: 'Começar'}).click();
    await page.getByRole('heading', {name: 'Clientes e contas', level: 2}).waitFor();
    assert.ok(await page.getByText('Feito').first().isVisible(), 'o fixture já tem cliente e conta');
    await page.keyboard.press('ArrowRight');
    await page.getByRole('heading', {name: 'Mídia', level: 2}).waitFor();
    await page.locator('.ob-scene--empty').waitFor();
    await page.keyboard.press('ArrowLeft');
    await page.getByRole('heading', {name: 'Clientes e contas', level: 2}).waitFor();

    // A ação do capítulo abre o assistente certo, sem sair da tela.
    await page.getByRole('button', {name: 'Adicionar outro cliente'}).click();
    await page.getByRole('dialog', {name: 'Novo cliente e conta'}).waitFor();
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', {name: 'Novo cliente e conta'}).waitFor({state: 'detached'});
    await page.getByRole('button', {name: 'Site & Jornada'}).click();
    await page.getByRole('button', {name: 'Adicionar site, fluxo e Super Tag'}).click();
    await page.getByRole('dialog', {name: 'Site, fluxo e Super Tag'}).waitFor();
    await page.keyboard.press('Escape');
    await page.getByRole('button', {name: 'Fontes de dados'}).click();
    await page.getByRole('button', {name: 'Conectar o Google Ads'}).click();
    await page.getByRole('dialog', {name: 'Conectar o Google Ads'}).waitFor();
    await page.keyboard.press('Escape');

    // Último capítulo: o estado do ambiente, com atalho para o que falta.
    await page.getByRole('button', {name: 'Pronto'}).click();
    await page.getByRole('heading', {name: 'Seu ambiente', level: 2}).waitFor();
    assert.ok(await page.getByText('3 de 5 etapas prontas').isVisible());
    assert.equal(await page.getByRole('button', {name: 'Resolver'}).count(), 2, 'fonte do Google Ads e site ainda faltam');
    if (shots) {
      await page.waitForTimeout(600);
      await page.screenshot({path: path.join(shots, 'onboarding-final-1440.png')});
      for (const [name, width, height] of [['tablet', 820, 1100], ['phone', 390, 844]]) {
        await page.setViewportSize({width, height}); await page.waitForTimeout(150);
        await page.screenshot({path: path.join(shots, `onboarding-${name}.png`)});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `sem rolagem horizontal em ${width}px`);
      }
    }

    // O passeio lembra onde parou.
    await page.setViewportSize({width: 1440, height: 900});
    await page.reload();
    await page.getByRole('heading', {name: 'Seu ambiente', level: 2}).waitFor();
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
