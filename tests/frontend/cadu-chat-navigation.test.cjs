const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '../..');
const assetRoot = path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react');
const bootstrap = {
  user: {name: 'Teste'}, brands: [], projects: [], dock: {items: []},
  urls: {home: '/workspace', newConversation: '/chat', docs: '/docs', projects: '/projects', profile: '/profile'},
  endpoints: {context: '/api/context', history: '/api/history', artifacts: '/api/artifacts', studioLibrary: '/api/library', runs: '/api/runs', dockShortcuts: '/api/shortcuts'},
};
const html = `<!doctype html><html lang="pt-BR" data-cadu-theme="dark" data-cadu-skin="conversations"><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="stylesheet" href="/static/app.css"></head><body class="portal portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root"></div><script id="cadu-conversations-v2-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/app.js"></script></main></body></html>`;

(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://cadu.test/**', route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/chat') return route.fulfill({status: 200, contentType: 'text/html', body: html});
      if (url.pathname.startsWith('/static/')) {
        const file = path.join(assetRoot, url.pathname.slice('/static/'.length));
        if (!fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
        return route.fulfill({status: 200, contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(file)});
      }
      if (url.pathname === '/api/artifacts/a1' && route.request().method() === 'PATCH') {
        const edit = route.request().postDataJSON();
        return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({artifact: {id: 'a1', type: 'document', title: edit.title, content: edit.content, current_version: 2}})});
      }
      const body = url.pathname === '/api/context' ? {context: {}, entities: []}
        : url.pathname === '/api/history' ? {conversations: [{id: 'c1', title: 'Conversa de teste', section: 'recent'}]}
        : url.pathname === '/api/history/c1/messages' ? {messages: Array.from({length: 40}, (_, index) => ({role: index % 2 ? 'assistant' : 'user', content: `Mensagem de teste ${index + 1}: ${'conteúdo '.repeat(20)}`}))}
        : url.pathname === '/api/library' ? {project_ref: 'ci:1', brand_assets: [], personal_assets: [], resources: [
          {id: 'r1', title: 'Documento de referência', url: '/docs/test', type: 'file'},
          {id: 'r2', source_system: 'project_files', source_id: 'f2', title: 'Arquivo do registro', locator: '/docs/registry.pdf', resource_type: 'file'},
          {id: 'r3', source_system: 'planner_docs', source_id: 'a3', title: 'Artefato indexado', resource_type: 'artifact'},
        ]}
        : {artifact: {id: 'a1', type: 'document', title: 'Documento de teste', content: {title: 'Documento de teste'}}, items: [], run: null};
      return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await page.goto('http://cadu.test/chat');
    await page.locator('.cv-composer-input').waitFor();
    await page.locator('.cv-composer-input').fill('Rascunho preservado');
    await page.getByRole('button', {name: 'Abrir conversas recentes'}).click();
    assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'navigation');
    await page.locator('.cv-mobile-navigation').getByRole('button', {name: 'Biblioteca'}).click();
    await page.locator('.cv-library-view').waitFor();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'library');
    assert.equal(await page.locator('.cv-conversation-shell').getAttribute('inert'), '');
    await page.goBack();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'navigation');
    await page.locator('.cv-mobile-navigation').getByRole('button', {name: 'Biblioteca'}).click();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'library');
    await page.locator('.cv-library-view').getByRole('button', {name: 'Voltar à conversa'}).click();
    assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'conversation');
    assert.equal(await page.locator('.cv-composer-input').inputValue(), 'Rascunho preservado');
    await page.getByRole('button', {name: 'Biblioteca'}).click();
    await page.goBack();
    assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'conversation');
    await page.getByRole('button', {name: 'Abrir conversas recentes'}).click();
    await page.locator('.cv-mobile-navigation .cv-conversation-card').first().click();
    await page.waitForFunction(() => document.querySelector('.cv-thread-scroll')?.scrollHeight > document.querySelector('.cv-thread-scroll')?.clientHeight * 2);
    await page.locator('.cv-thread-scroll').evaluate(element => { element.scrollTop = 220; });
    const scrollBefore = await page.locator('.cv-thread-scroll').evaluate(element => element.scrollTop);
    await page.getByRole('button', {name: 'Biblioteca'}).click();
    await page.locator('.cv-library-view').getByRole('button', {name: 'Voltar à conversa'}).click();
    const scrollAfter = await page.locator('.cv-thread-scroll').evaluate(element => element.scrollTop);
    assert.ok(Math.abs(scrollAfter - scrollBefore) < 2, `posição da conversa preservada (${scrollBefore} → ${scrollAfter})`);
    await page.getByRole('button', {name: 'Biblioteca'}).click();
    await page.locator('.cv-library-view').getByRole('button', {name: 'Documento de referência'}).click();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'artifact');
    const resourceUrl = page.url();
    assert.match(resourceUrl, /resource_ref=resource%3Ar1/, 'recurso tem URL estável');
    assert.match(resourceUrl, /resource_project_ref=ci%3A1/, 'link conserva o projeto necessário para reabrir o recurso');
    assert.ok(await page.locator('.cv-artifact-panel').isVisible(), 'recurso aberto como artefato');
    await page.locator('.cv-artifact-return.is-mobile').click();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'conversation');
    const scrollAfterArtifact = await page.locator('.cv-thread-scroll').evaluate(element => element.scrollTop);
    assert.ok(Math.abs(scrollAfterArtifact - scrollBefore) < 2, `posição preservada após artefato (${scrollBefore} → ${scrollAfterArtifact})`);
    await page.goto(resourceUrl);
    await page.locator('.cv-artifact-panel').getByText('Documento de referência').first().waitFor();
    await page.locator('.cv-artifact-panel').getByRole('link', {name: 'Abrir arquivo'}).waitFor();
    await page.locator('.cv-artifact-return.is-mobile').click();
    await page.getByRole('button', {name: 'Biblioteca'}).click();
    await page.locator('.cv-library-view').getByRole('button', {name: 'Arquivo do registro'}).click();
    await page.locator('.cv-artifact-panel').getByRole('link', {name: 'Abrir arquivo'}).waitFor();
    await page.locator('.cv-artifact-return.is-mobile').click();
    await page.getByRole('button', {name: 'Biblioteca'}).click();
    await page.locator('.cv-library-view').getByRole('button', {name: 'Artefato indexado'}).click();
    await page.locator('.cv-artifact-panel').getByRole('link', {name: 'Abrir projetos'}).waitFor();
    assert.deepEqual(errors, []);
    const keyboardPage = await browser.newPage({viewport: {width: 390, height: 844}});
    await keyboardPage.addInitScript(() => {
      const viewport = new EventTarget();
      viewport.height = 844;
      viewport.width = 390;
      viewport.offsetTop = 0;
      Object.defineProperty(window, 'visualViewport', {configurable: true, value: viewport});
      window.setTestVisualHeight = height => {
        viewport.height = height;
        viewport.dispatchEvent(new Event('resize'));
      };
    });
    await keyboardPage.route('http://cadu.test/**', route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/chat') return route.fulfill({status: 200, contentType: 'text/html', body: html});
      if (url.pathname.startsWith('/static/')) {
        const file = path.join(assetRoot, url.pathname.slice('/static/'.length));
        if (!fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
        return route.fulfill({status: 200, contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(file)});
      }
      return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({context: {}, entities: [], conversations: [], brand_assets: [], personal_assets: [], resources: []})});
    });
    await keyboardPage.goto('http://cadu.test/chat');
    await keyboardPage.locator('.cv-composer-input').focus();
    await keyboardPage.evaluate(() => window.setTestVisualHeight(500));
    await keyboardPage.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.keyboardOpen === 'true');
    const keyboardGeometry = await keyboardPage.evaluate(() => ({
      shellHeight: document.querySelector('.cv-conversations-shell').getBoundingClientRect().height,
      composerBottom: document.querySelector('.cv-composer-stage').getBoundingClientRect().bottom,
    }));
    assert.equal(keyboardGeometry.shellHeight, 500, 'teclado: shell acompanha viewport visual');
    assert.ok(keyboardGeometry.composerBottom <= 503, 'teclado: composer permanece visível');
    await keyboardPage.locator('.cv-composer-input').blur();
    await keyboardPage.evaluate(() => window.setTestVisualHeight(844));
    await keyboardPage.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.keyboardOpen === 'false');
    await keyboardPage.setViewportSize({width: 1024, height: 768});
    await keyboardPage.evaluate(() => { window.visualViewport.width = 1024; window.setTestVisualHeight(768); });
    await keyboardPage.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.layout === 'tablet');
    assert.ok(await keyboardPage.locator('.cv-conversations-workarea > .cadu-ds-dock').isVisible(), 'tablet landscape: dock visível sem teclado');
    await keyboardPage.locator('.cv-composer-input').focus();
    await keyboardPage.evaluate(() => window.setTestVisualHeight(430));
    await keyboardPage.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.keyboardOpen === 'true');
    assert.equal(await keyboardPage.locator('.cv-conversations-workarea > .cadu-ds-dock').isVisible(), false, 'tablet landscape: dock oculta com teclado');
    await keyboardPage.close();
    for (const {width, height} of [{width: 820, height: 1180}, {width: 1024, height: 768}]) {
      await page.setViewportSize({width, height});
      await page.goto('http://cadu.test/chat?surface=artifact&artifact_id=a1');
      await page.locator('.cv-artifact-panel').waitFor();
      assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-layout'), 'tablet');
      const dimensions = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        stageLeft: document.querySelector('.cv-conversation-stage').getBoundingClientRect().left,
        artifactWidth: document.querySelector('.cv-artifact-panel').getBoundingClientRect().width,
      }));
      assert.equal(dimensions.scrollWidth, dimensions.viewportWidth, `${width}: sem overflow horizontal`);
      assert.ok(dimensions.artifactWidth > 0 && dimensions.artifactWidth < width, `${width}: artefato visível no tablet`);
      assert.equal(dimensions.stageLeft, width === 820 ? 0 : 56, `${width}: conversa alinhada à dock visível`);
      assert.equal(await page.locator('.cv-tablet-dock').isVisible(), width === 820, `${width}: dock compacta só no retrato`);
      if (width === 820) {
        await page.locator('.cv-rich-document__canvas').fill('Edição pendente');
        await page.locator('.cv-tablet-dock').getByRole('button', {name: 'Novo chat'}).click();
        await page.getByRole('dialog', {name: 'Descartar alterações?'}).waitFor();
        await page.getByRole('button', {name: 'Continuar editando'}).click();
        assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'artifact');
        assert.match(await page.locator('.cv-rich-document__canvas').innerText(), /Edição pendente/);
        await page.locator('.cv-rich-document__canvas').fill('Nova edição pendente');
        await page.locator('.cv-tablet-dock').getByRole('link', {name: 'Início'}).click();
        await page.getByRole('dialog', {name: 'Descartar alterações?'}).waitFor();
        await page.getByRole('button', {name: 'Continuar editando'}).click();
        assert.equal(new URL(page.url()).pathname, '/chat', 'cancelar saída mantém a conversa');
        await page.locator('.cv-tablet-dock').getByRole('button', {name: 'Conversa'}).click();
        await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'conversation');
        if (process.env.CADU_TABLET_SCREENSHOT) await page.screenshot({path: process.env.CADU_TABLET_SCREENSHOT});
        await page.locator('.cv-tablet-dock').getByRole('button', {name: 'Biblioteca'}).click();
        await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'library');
      }
    }
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.layout === 'phone');
    assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'artifact');
    await page.locator('.cv-artifact-return.is-mobile').click();
    await page.waitForFunction(() => document.querySelector('.cv-conversations-shell')?.dataset.surface === 'conversation');
    await page.setViewportSize({width: 1366, height: 1024});
    await page.goto('http://cadu.test/chat?surface=artifact&artifact_id=a1');
    await page.locator('.cv-artifact-panel').waitFor();
    assert.equal(await page.locator('.cv-conversations-shell').getAttribute('data-surface'), 'artifact');
    const before = await page.locator('.cv-artifact-panel').evaluate(element => element.getBoundingClientRect().width);
    await page.locator('.cv-artifact-resizer').focus();
    await page.keyboard.press('ArrowLeft');
    await page.waitForFunction(width => document.querySelector('.cv-artifact-panel')?.getBoundingClientRect().width > width, before);
    const after = await page.locator('.cv-artifact-panel').evaluate(element => element.getBoundingClientRect().width);
    assert.ok(after > before, 'desktop: divisor amplia o artefato');
    assert.deepEqual(errors, []);
    console.log('PASS: navegação mobile, histórico, rascunho, scroll, artefato e breakpoints.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
