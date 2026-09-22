const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '../..');
const css = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react/app.css'), 'utf8');
const fixes = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react/chat-layout-fixes.css'), 'utf8');

function documentFor(surface) {
  return `<!doctype html><html data-cadu-theme="dark" data-cadu-skin="conversations"><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>${css}\n${fixes}</style></head><body class="portal portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root"><div class="cadu-ds-home-shell cv-conversations-shell" data-surface="${surface}" data-artifact-side="right"><main class="cadu-ds-home-main"><div class="cadu-ds-home-workarea cv-conversations-workarea"><aside class="cadu-ds-dock">Dock</aside><aside class="cv-recent-sidebar is-closing">Histórico</aside><div class="cv-conversation-stage cv-relative cv-flex cv-min-w-0 cv-flex-1"><section class="cv-conversation-shell cv-relative cv-flex cv-min-w-0 cv-flex-1 cv-flex-col cv-bg-ink"><header class="cv-conversation-header">Chat</header><div class="cv-thread-scroll cv-min-h-0 cv-flex-1 cv-overflow-y-auto">Mensagens</div><div class="cv-composer-stage"><form class="cv-composer-shell"><textarea class="cv-composer-input">Mensagem</textarea></form></div></section>${surface === 'library' ? '<section class="cv-library-view"><header class="cv-library-view__header">Biblioteca</header><div class="cv-library-view__scroll">Itens</div></section>' : ''}${surface === 'artifact' ? '<div class="cv-artifact-resizer"></div><aside class="cv-artifact-panel cv-artifact-overlay">Artefato</aside>' : ''}</div></div></main></div></div></main></body></html>`;
}

(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  try {
    for (const {width, height, surface} of [
      {width: 390, height: 844, surface: 'library'},
      {width: 820, height: 1180, surface: 'artifact'},
      {width: 1024, height: 768, surface: 'artifact'},
      {width: 1366, height: 1024, surface: 'artifact'},
    ]) {
      const page = await browser.newPage({viewport: {width, height}});
      await page.setContent(documentFor(surface));
      const result = await page.evaluate(() => {
        const stage = document.querySelector('.cv-conversation-stage').getBoundingClientRect();
        const chat = document.querySelector('.cv-conversation-shell').getBoundingClientRect();
        const panel = document.querySelector('.cv-library-view,.cv-artifact-panel').getBoundingClientRect();
        const composer = document.querySelector('.cv-composer-stage').getBoundingClientRect();
        return {stage, chat, panel, composer, scrollWidth: document.documentElement.scrollWidth, viewportWidth: document.documentElement.clientWidth};
      });
      assert.equal(result.scrollWidth, result.viewportWidth, `${width}: sem overflow horizontal`);
      assert.ok(result.composer.bottom <= height + 3, `${width}: composer dentro da viewport (${JSON.stringify({stage: result.stage, chat: result.chat, composer: result.composer})})`);
      if (width < 768) {
        assert.ok(result.panel.width >= width - 1, 'telefone: painel ocupa toda a largura');
        assert.ok(Math.abs(result.panel.left) <= 1, 'telefone: painel começa na borda');
      } else if (width === 820) {
        assert.ok(result.panel.width <= width * .85 + 1, 'tablet portrait: painel secundário');
      } else {
        assert.ok(result.panel.width < result.stage.width, `${width}: painel compartilha a largura`);
        assert.ok(result.chat.width >= 350, `${width}: conversa continua legível`);
      }
      await page.close();
    }
    const keyboardPage = await browser.newPage({viewport: {width: 390, height: 844}});
    await keyboardPage.setContent(documentFor('conversation'));
    await keyboardPage.locator('.cv-conversations-shell').evaluate(element => {
      element.dataset.keyboardOpen = 'true';
      document.documentElement.style.setProperty('--cv-visual-height', '500px');
    });
    const keyboard = await keyboardPage.evaluate(() => ({
      shellHeight: document.querySelector('.cv-conversations-shell').getBoundingClientRect().height,
      composerBottom: document.querySelector('.cv-composer-stage').getBoundingClientRect().bottom,
    }));
    assert.equal(keyboard.shellHeight, 500, 'telefone: shell acompanha viewport visual reduzida');
    assert.ok(keyboard.composerBottom <= 503, 'telefone: composer permanece acima do teclado simulado');
    await keyboardPage.close();
    console.log('PASS: superfícies do Cadu Chat em telefone, tablet e desktop.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
