const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium} = require(playwrightModule);

const root = path.resolve(__dirname, '../..');
const tokens = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/tokens.css'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
const chromePath = process.env.CHROME_PATH;

function documentFor(contentClass) {
  return `<!doctype html>
  <html data-cadu-theme="light" data-cadu-skin="workspace">
    <head><meta charset="utf-8"><style>html,body{margin:0}\n${tokens}\n${styles}</style></head>
    <body class="portal--workspace">
      <main id="content">
        <div id="cadu-conversations-v2-root" class="cv-home-root">
          <div class="cadu-ds-home-shell">
            <main class="cadu-ds-home-main">
              <header class="cadu-ds-home-navbar">Navegação</header>
              <div class="cadu-ds-home-workarea">
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

async function dimensions(page, contentClass) {
  return page.evaluate(selector => {
    const shell = document.querySelector('.cadu-ds-home-shell').getBoundingClientRect();
    const navbar = document.querySelector('.cadu-ds-home-navbar').getBoundingClientRect();
    const workarea = document.querySelector('.cadu-ds-home-workarea').getBoundingClientRect();
    const dockElement = document.querySelector('.cadu-ds-dock');
    const dock = dockElement.getBoundingClientRect();
    const content = document.querySelector(`.${selector}`).getBoundingClientRect();
    return {
      viewport: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      shell: {left: shell.left, right: shell.right, width: shell.width},
      navbar: {left: navbar.left, right: navbar.right, width: navbar.width},
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
      assert.equal(desktop.navbar.width, desktop.viewport, `${contentClass}: navbar desktop`);
      assert.equal(desktop.workarea.width, desktop.viewport, `${contentClass}: workarea desktop`);
      assert.equal(desktop.dock.width, 64, `${contentClass}: dock desktop`);
      assert.equal(desktop.content.left, desktop.dock.right, `${contentClass}: conteúdo após dock`);
      assert.equal(desktop.content.right, desktop.viewport, `${contentClass}: conteúdo até a borda`);
      assert.equal(desktop.scrollWidth, desktop.viewport, `${contentClass}: sem overflow desktop`);

      await page.setViewportSize({width: 390, height: 844});
      await page.setContent(documentFor(contentClass));
      const mobile = await dimensions(page, contentClass);
      assert.equal(mobile.dock.display, 'none', `${contentClass}: dock oculta no mobile`);
      assert.equal(mobile.content.left, 0, `${contentClass}: conteúdo começa na borda mobile`);
      assert.equal(mobile.content.right, mobile.viewport, `${contentClass}: conteúdo em largura total mobile`);
      assert.equal(mobile.scrollWidth, mobile.viewport, `${contentClass}: sem overflow mobile`);
    }
    assert.deepEqual(errors, []);
    console.log('PASS: Workspace full-width, Dock and overflow at 1440px and 390px.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
