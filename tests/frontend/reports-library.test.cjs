// Relatórios: cards com situação, origem, resumo e versão; abas, busca, grade ou lista, paginação e menu de ações.
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
const campaign = fixture.bootstrap.campaigns[0];
// 14 relatórios: um fluxo, um independente e o resto por campanha; dois publicados, um fixado.
const reports = Array.from({length: 14}, (_, index) => ({
  id: index + 1, campaign_name: index === 0 ? 'Resultado de setembro' : `Relatório ${index + 1}`, revision: index === 0 ? 3 : 1,
  media_campaign_id: index === 1 || index === 2 ? null : campaign.id, flow_id: index === 1 ? 'f1' : null, flow_name: index === 1 ? 'Cadastro de leads' : null,
  summary: index === 0 ? 'Performance da campanha institucional com foco em geração de leads.' : null,
  pinned: index === 0, published: index < 2, published_revision: index === 0 ? 2 : index === 1 ? 1 : null,
  updated_at: new Date(Date.UTC(2026, 9, 3 - index, 15)).toISOString(),
}));
const boot = {ready: true, features: {}, csrf: 't', reports, link_tests: [], workspace_projects: [], clients: [{client_id: 1, client_name: 'Cliente Teste'}],
  ...fixture.bootstrap, client: {client_id: 1, role: 'admin', client_name: 'Cliente Teste'}, can_manage_clients: true};

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.setDefaultTimeout(8000);
    const errors = [];
    const pins = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/connect/api/**', route => {
      const pathname = new URL(route.request().url()).pathname.replace('/connect/api/v2/reports', '');
      if (pathname === '/bootstrap') return route.fulfill({json: boot});
      if (/\/workspaces\/\d+\/pin$/.test(pathname)) {pins.push([pathname, route.request().postDataJSON()]); return route.fulfill({json: {ok: true}});}
      return route.fulfill({json: {}});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/reports`);
    await page.getByRole('heading', {name: 'Resultado de setembro', level: 3}).waitFor();

    // Card: situação, origem (plataforma · cliente), resumo, versão com a publicada atrás e data longa.
    const first = page.locator('li').filter({has: page.getByRole('heading', {name: 'Resultado de setembro'})});
    const card = await first.innerText();
    for (const text of ['Publicado', 'Principal', 'Google Ads', 'geração de leads', 'v3', 'Atualizado em 03 de out. de 2026']) assert.ok(card.includes(text), `card sem "${text}": ${card}`);
    const flow = await page.locator('li').filter({has: page.getByRole('heading', {name: 'Relatório 2'})}).innerText();
    assert.ok(flow.includes('Fluxo · Cadastro de leads'));
    const loose = await page.locator('li').filter({has: page.getByRole('heading', {name: 'Relatório 3', exact: true})}).innerText();
    assert.ok(loose.includes('Rascunho') && loose.includes('Independente'));
    assert.ok(await page.getByText('Mostrando 12 de 14 relatórios').isVisible());
    assert.equal(await first.getByText('v3').getAttribute('title'), 'v3 · publicada v2');
    // Novo relatório fica no cabeçalho da página e abre o assistente de criação.
    await page.getByRole('button', {name: 'Novo relatório'}).click();
    await page.getByRole('dialog', {name: 'Criar relatório'}).waitFor();
    await page.keyboard.press('Escape');
    await page.getByRole('dialog', {name: 'Criar relatório'}).waitFor({state: 'detached'});
    if (shots) {await page.waitForTimeout(300); await page.screenshot({path: path.join(shots, 'reports-library-grid.png'), fullPage: true});}

    // Abas com contagem e paginação.
    assert.ok((await page.getByRole('button', {name: /Rascunhos/}).innerText()).includes('12'));
    await page.getByRole('button', {name: 'Próxima página'}).click();
    assert.ok(await page.getByText('Mostrando 2 de 14 relatórios').isVisible());
    await page.getByRole('button', {name: /Publicados/}).click();
    assert.ok(await page.getByText('Mostrando 2 de 2 relatórios').isVisible(), 'trocar a aba volta à primeira página');

    // Menu de ações: marca como principal sem abrir o relatório.
    await page.getByRole('button', {name: 'Ações de Relatório 2'}).click();
    await page.getByRole('menuitem', {name: 'Marcar como principal'}).click();
    await page.waitForResponse(response => response.url().endsWith('/workspaces/2/pin')).catch(() => {});
    assert.deepEqual(pins.at(-1), ['/workspaces/2/pin', {pinned: true}]);

    // Lista: mesma informação em tabela, e a escolha fica salva.
    await page.getByRole('button', {name: /^Todos \d/}).click();
    await page.getByRole('button', {name: 'Lista'}).click();
    await page.getByRole('table').waitFor();
    assert.equal(await page.locator('tbody tr').count(), 12);
    if (shots) await page.screenshot({path: path.join(shots, 'reports-library-list.png'), fullPage: true});
    await page.reload();
    await page.getByRole('table').waitFor();

    // Busca pelo resumo.
    await page.getByRole('searchbox', {name: 'Buscar relatórios'}).fill('institucional');
    assert.equal(await page.locator('tbody tr').count(), 1);

    if (shots) {
      await page.getByRole('button', {name: 'Grade'}).click();
      await page.getByRole('searchbox', {name: 'Buscar relatórios'}).fill('');
      await page.setViewportSize({width: 390, height: 844}); await page.waitForTimeout(150);
      await page.screenshot({path: path.join(shots, 'reports-library-phone.png')});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'sem rolagem horizontal no celular');
    }
    assert.deepEqual(errors, []);
    console.log('ok');
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error); process.exit(1);});
