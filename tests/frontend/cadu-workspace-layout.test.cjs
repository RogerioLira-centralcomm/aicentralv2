const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium} = require(playwrightModule);

const root = path.resolve(__dirname, '../..');
const tokens = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/tokens.css'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
const conversationStyles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
const chromePath = process.env.CHROME_PATH;

function documentFor(contentClass) {
  return `<!doctype html>
  <html data-cadu-theme="light" data-cadu-skin="workspace">
    <head><meta charset="utf-8"><style>html,body{margin:0}\n${tokens}\n${styles}</style></head>
    <body class="portal--workspace">
      <main id="content" class="portal-content--workspace-react">
        <div id="cadu-conversations-v2-root" class="cv-home-root">
          <div class="cadu-ds-home-shell">
            <main class="cadu-ds-home-main">
              <div class="cadu-ds-home-workarea">
                <header class="cadu-ds-mobile-chrome"><div><span>Workspace</span><strong>Centralcomm</strong></div><button>Menu</button></header>
                <aside class="cadu-ds-dock">Dock</aside>
                <section class="${contentClass}">Conteúdo</section>
              </div>
            </main>
          </div>
        </div>
      </main>
    </body>
  </html>`;
}

function conversationDocument() {
  return `<!doctype html><html data-cadu-theme="dark" data-cadu-skin="conversations"><head><meta charset="utf-8"><style>html,body{margin:0;height:100%}.cv-conversation-surface{min-width:0;flex:1}\n${tokens}\n${conversationStyles}\n${styles}</style></head><body><main id="content"><div id="cadu-conversations-v2-root"><div class="cadu-ds-home-shell cv-conversations-shell"><main class="cadu-ds-home-main"><header class="cadu-ds-home-navbar cv-conversations-navbar">Navegação</header><div class="cadu-ds-home-workarea cv-conversations-workarea"><aside class="cadu-ds-dock">Dock</aside><aside class="cv-recent-sidebar">Recentes</aside><section class="cv-conversation-surface">Conversa</section></div></main></div></div></main></body></html>`;
}

function conversationDocumentWithPersistedLightTheme() {
  return conversationDocument().replace('data-cadu-theme="dark"', 'data-cadu-theme="light"');
}

async function dimensions(page, contentClass) {
  return page.evaluate(selector => {
    const shell = document.querySelector('.cadu-ds-home-shell').getBoundingClientRect();
    const mobileChromeElement = document.querySelector('.cadu-ds-mobile-chrome');
    const mobileChrome = mobileChromeElement.getBoundingClientRect();
    const workarea = document.querySelector('.cadu-ds-home-workarea').getBoundingClientRect();
    const dockElement = document.querySelector('.cadu-ds-dock');
    const dock = dockElement.getBoundingClientRect();
    const content = document.querySelector(`.${selector}`).getBoundingClientRect();
    return {
      viewport: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      shell: {left: shell.left, right: shell.right, width: shell.width},
      mobileChrome: {display: getComputedStyle(mobileChromeElement).display, left: mobileChrome.left, right: mobileChrome.right, width: mobileChrome.width},
      workarea: {left: workarea.left, right: workarea.right, width: workarea.width},
      dock: {display: getComputedStyle(dockElement).display, left: dock.left, right: dock.right, width: dock.width},
      content: {left: content.left, right: content.right, width: content.width},
    };
  }, contentClass);
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(chromePath ? {executablePath: chromePath} : {channel: process.env.CADU_BROWSER_CHANNEL || 'chrome'}),
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  try {
    for (const contentClass of ['cadu-ds-home-content', 'cadu-ds-project-content', 'cadu-ds-brands-content']) {
      await page.setViewportSize({width: 1440, height: 1000});
      await page.setContent(documentFor(contentClass));
      const desktop = await dimensions(page, contentClass);
      assert.equal(desktop.shell.width, desktop.viewport, `${contentClass}: shell desktop`);
      assert.equal(desktop.mobileChrome.display, 'none', `${contentClass}: chrome móvel oculto no desktop`);
      assert.equal(desktop.workarea.width, desktop.viewport, `${contentClass}: workarea desktop`);
      assert.equal(desktop.dock.width, 64, `${contentClass}: dock desktop`);
      assert.ok(desktop.content.left >= desktop.dock.right, `${contentClass}: conteúdo após dock`);
      assert.equal(desktop.content.right, desktop.viewport, `${contentClass}: conteúdo até a borda`);
      assert.equal(desktop.scrollWidth, desktop.viewport, `${contentClass}: sem overflow desktop`);

      await page.setViewportSize({width: 390, height: 844});
      await page.setContent(documentFor(contentClass));
      const mobile = await dimensions(page, contentClass);
      assert.equal(mobile.dock.display, 'none', `${contentClass}: dock oculta no mobile`);
      assert.equal(mobile.mobileChrome.display, 'flex', `${contentClass}: chrome móvel visível`);
      assert.equal(mobile.mobileChrome.width, mobile.viewport, `${contentClass}: chrome móvel em largura total`);
      assert.equal(mobile.content.left, 0, `${contentClass}: conteúdo começa na borda mobile`);
      assert.equal(mobile.content.right, mobile.viewport, `${contentClass}: conteúdo em largura total mobile`);
      assert.equal(mobile.scrollWidth, mobile.viewport, `${contentClass}: sem overflow mobile`);
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.setContent(conversationDocument());
    const conversationDesktop = await page.evaluate(() => {
      const dock = document.querySelector('.cadu-ds-dock').getBoundingClientRect();
      const recent = document.querySelector('.cv-recent-sidebar').getBoundingClientRect();
      const conversation = document.querySelector('.cv-conversation-surface').getBoundingClientRect();
      return {dock, recent, conversation, viewport: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};
    });
    assert.equal(conversationDesktop.dock.width, 64, 'Conversas: Dock desktop');
    assert.equal(conversationDesktop.recent.width, 275, 'Conversas: recentes desktop');
    assert.equal(conversationDesktop.recent.left, conversationDesktop.dock.right, 'Conversas: recentes ao lado da Dock');
    assert.equal(conversationDesktop.conversation.left, conversationDesktop.recent.right, 'Conversas: conteúdo após recentes');
    assert.equal(conversationDesktop.conversation.right, conversationDesktop.viewport, 'Conversas: conteúdo até a borda');
    assert.equal(conversationDesktop.scrollWidth, conversationDesktop.viewport, 'Conversas: sem overflow desktop');

    await page.setViewportSize({width: 390, height: 844});
    await page.setContent(conversationDocument());
    const conversationMobile = await page.evaluate(() => ({
      dockDisplay: getComputedStyle(document.querySelector('.cadu-ds-dock')).display,
      recentPosition: getComputedStyle(document.querySelector('.cv-recent-sidebar')).position,
      scrollWidth: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }));
    assert.equal(conversationMobile.dockDisplay, 'none', 'Conversas: Dock oculta no mobile');
    assert.equal(conversationMobile.recentPosition, 'fixed', 'Conversas: recentes sobrepostos no mobile');
    assert.equal(conversationMobile.scrollWidth, conversationMobile.viewport, 'Conversas: sem overflow mobile');

    for (const viewport of [
      {width: 1024, height: 768, label: 'desktop compacto'},
      {width: 768, height: 1024, label: 'tablet'},
      {width: 320, height: 700, label: 'mobile estreito'},
    ]) {
      await page.setViewportSize(viewport);
      await page.setContent(conversationDocument());
      const responsive = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        viewport: document.documentElement.clientWidth,
        colorScheme: getComputedStyle(document.documentElement).colorScheme,
      }));
      assert.equal(responsive.scrollWidth, responsive.viewport, `Conversas: sem overflow em ${viewport.label}`);
      assert.equal(responsive.colorScheme, 'dark', `Conversas: tema escuro em ${viewport.label}`);
    }

    await page.setViewportSize({width: 390, height: 844});
    await page.setContent(conversationDocumentWithPersistedLightTheme());
    const protectedTheme = await page.evaluate(() => ({
      colorScheme: getComputedStyle(document.documentElement).colorScheme,
      canvas: getComputedStyle(document.documentElement).getPropertyValue('--cadu-canvas').trim(),
    }));
    assert.equal(protectedTheme.colorScheme, 'dark', 'Conversas: preferência clara não vaza para o chat');
    assert.equal(protectedTheme.canvas, '#071113', 'Conversas: canvas escuro permanece protegido');
    assert.deepEqual(errors, []);
    console.log('PASS: Workspace full-width, Dock and overflow at 1440px and 390px.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
