const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '../..');
const assetRoot = path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react');
const bootstrap = {
  user: {name: 'Teste'}, brands: [], projects: [], dock: {items: []},
  urls: {home: '/workspace', newConversation: '/chat', projects: '/projects', profile: '/profile'},
  endpoints: {context: '/api/context', history: '/api/history', artifacts: '/api/artifacts', studioLibrary: '/api/library', runs: '/api/runs', dockShortcuts: '/api/shortcuts'},
};
const shell = `<!doctype html><html lang="pt-BR" data-cadu-theme="dark" data-cadu-skin="conversations"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/app.css"></head><body class="portal portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root"></div><script id="cadu-conversations-v2-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/app.js"></script></main></body></html>`;

(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage({viewport: {width: 1366, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://cadu.test/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/chat') return route.fulfill({status: 200, contentType: 'text/html', body: shell});
    if (url.pathname === '/static/css/tailwind/artifact.css') {
      return route.fulfill({status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(root, 'aicentralv2/static/css/tailwind/artifact.css'))});
    }
    if (url.pathname.startsWith('/static/')) {
      const file = path.join(assetRoot, url.pathname.slice('/static/'.length));
      if (!fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
      return route.fulfill({status: 200, contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(file)});
    }
    const payload = url.pathname === '/api/artifacts/html1'
      ? {artifact: {id: 'html1', type: 'html', title: 'Dashboard COPASA', current_version: 1, content: {html: '<main id="dashboard" class="grid p-6"><h1>Dashboard COPASA</h1><strong>150.119 cliques</strong></main>'}}}
      : url.pathname === '/api/artifacts/html-empty'
        ? {artifact: {id: 'html-empty', type: 'html', title: 'Dashboard vazio', current_version: 1, content: {html: ''}}}
        : url.pathname === '/api/context' ? {context: {}, entities: []}
          : url.pathname === '/api/history' ? {conversations: []}
            : {items: [], resources: [], brand_assets: [], personal_assets: [], run: null};
    return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(payload)});
  });

  try {
    await page.goto('http://cadu.test/chat?surface=artifact&artifact_id=html1');
    const frame = page.frameLocator('iframe[title="Dashboard COPASA"]');
    await frame.getByRole('heading', {name: 'Dashboard COPASA'}).waitFor();
    assert.equal(await frame.locator('#dashboard').evaluate(element => getComputedStyle(element).display), 'grid');
    assert.match(await frame.locator('body').innerText(), /150\.119 cliques/);

    await page.goto('http://cadu.test/chat?surface=artifact&artifact_id=html-empty');
    await page.getByText('Esta página não possui conteúdo').waitFor();
    assert.equal(await page.locator('iframe[title="Dashboard vazio"]').count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: HTML visual renderiza no iframe e versões vazias não produzem tela branca.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
