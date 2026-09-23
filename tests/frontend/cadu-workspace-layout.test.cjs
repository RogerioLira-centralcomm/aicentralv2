const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const {chromium} = require(playwrightModule);

const root = path.resolve(__dirname, '../..');
const tokens = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/tokens.css'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
const conversationStyles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
const workspaceBundleStyles = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react/app.css'), 'utf8');
const workspaceHomeStyles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceHome.css'), 'utf8');
const dockStyles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/CaduDock.css'), 'utf8');
const workspaceChromeStyles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/workspace-chrome.css'), 'utf8');
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

function brandDocument(processing = false) {
  return `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><style>html,body{margin:0}\n${workspaceBundleStyles}</style></head>
    <body class="portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root" class="cv-home-root">
      <div class="cadu-ds-home-shell cadu-ds-brand-shell ${processing ? 'is-audit_processing' : 'is-approved'}"><main class="cadu-ds-home-main"><div class="cadu-ds-home-workarea cadu-ds-brand-workarea">
        <aside class="cadu-ds-dock"><button class="cadu-ds-dock-home">Início</button><button class="cadu-ds-dock-brand"><span class="cadu-ds-visual-identity cadu-ds-visual-identity--brand"><img alt="Marca" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20'%3E%3Crect width='20' height='20' fill='%23007766'/%3E%3C/svg%3E"></span></button></aside>
        <div class="cadu-ds-entity-portal cadu-ds-entity-portal--brand">${processing ? '' : '<aside class="cadu-ds-entity-nav"><nav><a class="is-active">Visão geral</a></nav></aside>'}
          <section class="cadu-ds-brand-content"><header class="cadu-ds-brand-hero"><div class="cadu-ds-brand-hero__identity"></div><div><h1>Marca</h1></div></header>
            ${processing ? '<section class="cadu-ds-brand-state cadu-ds-brand-state--processing"><div class="cadu-ds-brand-state__visual"><i class="cadu-ds-brand-orbit cadu-ds-brand-orbit--one"></i><div class="cadu-ds-brand-audit-mark"><img alt="" src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'120\' height=\'40\'%3E%3C/svg%3E"></div></div><div class="cadu-ds-brand-state__copy"><h2>Processando</h2><div class="cadu-ds-brand-audit-progress"><div class="is-active"><i></i><span>Fontes oficiais</span></div><div><i></i><span>Identidade visual</span></div></div></div></section>' : '<section class="cadu-ds-brand-review"><div>Base aprovada</div></section><header class="cadu-ds-brand-data-viewer__header"><h2>Informações organizadas</h2></header><div class="cadu-ds-brand-data-viewer"><section class="cadu-ds-brand-library"><div class="cadu-ds-brand-library__stage"><img alt="Ativo"></div><aside><button class="is-active"><img alt=""><span><b>Logo</b></span></button></aside></section></div>'}
          </section>${processing ? '' : '<aside class="cadu-ds-entity-rail">Gestão<button class="cadu-ds-entity-rail__action">Criar ou vincular projeto</button><button class="cadu-ds-entity-rail__danger">Apagar marca</button></aside>'}</div>
      </div></main></div></div></main></body></html>`;
}

function projectDocument() {
  const logo = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='40'%3E%3Crect width='120' height='40' fill='%23fff'/%3E%3Cpath d='M8 29h104' stroke='%23b21f2d' stroke-width='12'/%3E%3C/svg%3E";
  return `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><style>html,body{margin:0}\n${workspaceBundleStyles}</style></head>
    <body class="portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root" class="cv-home-root">
      <div class="cadu-ds-home-shell cadu-ds-project-shell is-editorial"><main class="cadu-ds-home-main"><div class="cadu-ds-home-workarea cadu-ds-project-workarea">
        <aside class="cadu-ds-dock">Dock</aside><div class="cadu-ds-entity-portal cadu-ds-entity-portal--project">
          <aside class="cadu-ds-entity-nav"><div class="cadu-ds-entity-nav__identity"><span><small>Projeto</small><b>BDMG Orienta 2026 – Portal da Micro e Pequena Empresa Mineira</b></span></div><nav><a class="is-active">Visão geral</a><a>Direção</a><a>Documentos e fontes</a><a>Atividade</a><a>Indexação</a></nav><div class="cadu-ds-entity-nav__actions"><button>Conversar no projeto</button><button>Editar contexto</button></div></aside>
          <section class="cadu-ds-project-content"><header class="cadu-ds-project-hero"><div><p>Projeto em andamento</p><h1>BDMG Orienta 2026 – Portal da Micro e Pequena Empresa Mineira</h1></div></header><section class="cadu-ds-project-editorial" style="min-height:1600px"><h2>Direção do projeto</h2><p>Conteúdo do projeto</p></section></section>
          <aside class="cadu-ds-entity-rail"><header class="cadu-ds-entity-rail__header"><span>Projeto agora</span></header><section class="cadu-ds-project-brand-feature"><div class="cadu-ds-project-brand-feature__body"><a class="cadu-ds-project-brand-feature__identity"><span class="cadu-ds-visual-identity has-rendered-image"><img src="${logo}" alt="BDMG"></span><span><b>BDMG</b></span></a></div></section><div style="min-height:900px">Contexto</div></aside>
        </div></div></main></div></div></main></body></html>`;
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
    assert.match(workspaceHomeStyles, /#cadu-conversations-v2-root[^\{]+\.cadu-ds-prompt-suggestions\.is-workspace-home button/, 'Home: CTA vence a regra escura do root');
    assert.match(workspaceHomeStyles, /\.cadu-ds-context-sidebar__project-tree[^\{]+\{[^}]*border-left:\s*1px\s+solid/, 'Home: projetos organizados por uma linha de árvore');
    assert.match(workspaceChromeStyles, /\.cadu-ds-dock :is\(\.cadu-ds-dock-brand,\.cadu-ds-dock-resource\)[^\{]+\{[^}]*transform:none/, 'Dock: atalhos usam o eixo canônico sem compensação lateral');
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
      assert.equal(mobile.mobileChrome.display, 'grid', `${contentClass}: chrome móvel visível`);
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
    assert.equal(conversationDesktop.recent.width, 272, 'Conversas: recentes desktop');
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

    await page.setViewportSize({width: 1440, height: 1000});
    await page.setContent(brandDocument(false));
    const brand = await page.evaluate(() => {
      const portal = document.querySelector('.cadu-ds-entity-portal');
      const hero = document.querySelector('.cadu-ds-brand-hero');
      const review = document.querySelector('.cadu-ds-brand-review');
      const logo = document.querySelector('.cadu-ds-dock-brand img');
      const stage = document.querySelector('.cadu-ds-brand-library__stage');
      const stageImage = stage.querySelector('img');
      const railAction = document.querySelector('.cadu-ds-entity-rail__action');
      const railDanger = document.querySelector('.cadu-ds-entity-rail__danger');
      const dock = document.querySelector('.cadu-ds-dock').getBoundingClientRect();
      const home = document.querySelector('.cadu-ds-dock-home').getBoundingClientRect();
      const brandShortcut = document.querySelector('.cadu-ds-dock-brand').getBoundingClientRect();
      const activeLink = document.querySelector('.cadu-ds-entity-nav a.is-active');
      const assetRow = document.querySelector('.cadu-ds-brand-library > aside button');
      return {
        portalColumns: getComputedStyle(portal).gridTemplateColumns,
        heroDisplay: getComputedStyle(hero).display,
        reviewBackground: getComputedStyle(review).backgroundColor,
        logoFit: getComputedStyle(logo).objectFit,
        dockCenter: dock.left + dock.width / 2,
        homeCenter: home.left + home.width / 2,
        brandCenter: brandShortcut.left + brandShortcut.width / 2,
        activeBackground: getComputedStyle(activeLink).backgroundColor,
        activeShadow: getComputedStyle(activeLink).boxShadow,
        stageBackground: getComputedStyle(stage).backgroundColor,
        assetBackground: getComputedStyle(assetRow).backgroundColor,
        assetRadius: getComputedStyle(assetRow).borderRadius,
        stageHeight: stageImage.getBoundingClientRect().height,
        railActionDisplay: getComputedStyle(railAction).display,
        railDangerDisplay: getComputedStyle(railDanger).display,
        railDangerTop: railDanger.getBoundingClientRect().top,
        railActionBottom: railAction.getBoundingClientRect().bottom,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    assert.match(brand.portalColumns, /239px/, 'Marca: navegação contextual preservada');
    assert.equal(brand.heroDisplay, 'flex', 'Marca: hero sem coluna de ações redundante');
    assert.equal(brand.reviewBackground, 'rgba(0, 0, 0, 0)', 'Marca: estado da base sem card decorativo');
    assert.equal(brand.logoFit, 'contain', 'Marca: logo da Dock usa toda a área sem recorte');
    assert.ok(Math.abs(brand.homeCenter - brand.dockCenter) < 1, 'Marca: acesso centralizado na Dock');
    assert.ok(Math.abs(brand.brandCenter - brand.dockCenter) < 1, 'Marca: atalho de marca centralizado na Dock');
    assert.equal(brand.activeBackground, 'rgba(0, 0, 0, 0)', 'Marca: link ativo da sidebar sem card');
    assert.equal(brand.activeShadow, 'none', 'Marca: link ativo da sidebar sem barra lateral');
    assert.equal(brand.stageBackground, 'rgba(0, 0, 0, 0)', 'Marca: visualizador de ativos integrado ao canvas');
    assert.equal(brand.assetBackground, 'rgba(0, 0, 0, 0)', 'Marca: lista de ativos sem cards');
    assert.equal(brand.assetRadius, '0px', 'Marca: lista de ativos sem cantos de card');
    assert.ok(brand.stageHeight <= 320, 'Marca: ativo não domina a página');
    assert.equal(brand.railActionDisplay, 'block', 'Marca: ação principal do rail ocupa linha própria');
    assert.equal(brand.railDangerDisplay, 'block', 'Marca: ação destrutiva do rail ocupa linha própria');
    assert.ok(brand.railDangerTop > brand.railActionBottom, 'Marca: ações do rail não colidem');
    assert.equal(brand.overflow, 0, 'Marca: sem overflow desktop');

    await page.setViewportSize({width: 1440, height: 800});
    await page.setContent(projectDocument());
    const projectBeforeScroll = await page.evaluate(() => {
      const nav = document.querySelector('.cadu-ds-entity-nav');
      const rail = document.querySelector('.cadu-ds-entity-rail');
      const title = document.querySelector('.cadu-ds-project-hero h1');
      const logo = document.querySelector('.cadu-ds-project-brand-feature__identity img');
      return {
        navTop:nav.getBoundingClientRect().top,
        navPosition:getComputedStyle(nav).position,
        navOverflow:getComputedStyle(nav).overflowY,
        railOverflow:getComputedStyle(rail).overflowY,
        titleSize:parseFloat(getComputedStyle(title).fontSize),
        horizontalOverflow:document.documentElement.scrollWidth - document.documentElement.clientWidth,
        pageScrollHeight:document.scrollingElement.scrollHeight,
        logoFit:getComputedStyle(logo).objectFit,
      };
    });
    await page.evaluate(() => window.scrollTo(0, 520));
    const projectNavTopAfterScroll = await page.$eval('.cadu-ds-entity-nav', node => node.getBoundingClientRect().top);
    assert.equal(projectBeforeScroll.navPosition, 'fixed', 'Projeto: sidebar 1 realmente fixa');
    assert.equal(projectBeforeScroll.navTop, 0, 'Projeto: sidebar 1 começa no topo');
    assert.equal(projectNavTopAfterScroll, 0, 'Projeto: sidebar 1 permanece fixa ao rolar');
    assert.equal(projectBeforeScroll.navOverflow, 'hidden', 'Projeto: sidebar 1 não cria scroll concorrente');
    assert.equal(projectBeforeScroll.railOverflow, 'visible', 'Projeto: sidebar 2 usa o scroll do documento');
    assert.ok(projectBeforeScroll.titleSize <= 48, 'Projeto: título longo respeita a escala máxima');
    assert.equal(projectBeforeScroll.horizontalOverflow, 0, 'Projeto: nome longo não rompe a largura');
    assert.ok(projectBeforeScroll.pageScrollHeight > 800, 'Projeto: navegador controla o scroll vertical');
    assert.equal(projectBeforeScroll.logoFit, 'contain', 'Projeto: logo da sidebar 2 aparece sem recorte');

    await page.setContent(brandDocument(true));
    const processingBrand = await page.evaluate(() => ({
      display: getComputedStyle(document.querySelector('.cadu-ds-entity-portal')).display,
      nav: document.querySelector('.cadu-ds-entity-nav'),
      rail: document.querySelector('.cadu-ds-entity-rail'),
      stateHeight: document.querySelector('.cadu-ds-brand-state').getBoundingClientRect().height,
      progressColor: getComputedStyle(document.querySelector('.cadu-ds-brand-audit-progress .is-active i')).borderColor,
    }));
    assert.equal(processingBrand.display, 'block', 'Marca em análise: conteúdo em coluna única');
    assert.equal(processingBrand.nav, null, 'Marca em análise: navegação contextual não é exibida');
    assert.equal(processingBrand.rail, null, 'Marca em análise: rail de ações não é exibido');
    assert.ok(processingBrand.stateHeight >= 360, 'Marca em análise: andamento permanece dominante');
    assert.equal(processingBrand.progressColor, 'rgb(8, 119, 101)', 'Marca em análise: progresso usa o teal do Workspace');
    assert.deepEqual(errors, []);
    console.log('PASS: Workspace full-width, Dock and overflow at 1440px and 390px.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
