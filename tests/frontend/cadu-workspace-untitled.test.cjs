const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '../..');
const assets = path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react');
const kitCss = path.join(root, 'aicentralv2/static/cadu_workspace/untitled/workspace-kit.css');
const templates = path.join(root, 'aicentralv2/templates/cadu_workspace');

for (const name of ['workspace_home_chat', 'brands_react', 'projects_react', 'brand_detail_react', 'project_detail_react', 'account_react']) {
  assert.match(fs.readFileSync(path.join(templates, `${name}.html`), 'utf8'), /_untitled_styles\.html/, `${name} loads the isolated kit`);
}
assert.doesNotMatch(fs.readFileSync(path.join(templates, 'conversations_v2_lab.html'), 'utf8'), /_untitled_styles\.html/, 'Conversations does not load the Workspace kit');

const bootstrap = (mode, section = '') => ({
  [mode]: true, section, admin: true, csrf: 'test', caduMark: '/mark.svg', user: {name: 'Teste', email: 'teste@example.com'}, brands: [], projects: [], dock: {items: []},
  account: {organization: {nome_fantasia: 'Agência de teste'}, agency_context: {projects: [], brands: []}, current_user: {nome_completo: 'Pessoa de teste', email: 'teste@example.com'}, people: []},
  endpoints: {updateOrganization: '/account/save-agency', updateProfile: '/account/save-profile'},
  urls: {home: '/workspace', brands: '/brands', projects: '/projects', newConversation: '/chat', createBrand: '/brands/new', createProject: '/projects/new', profile: '/account/perfil', usage: '/usage', plans: '/plans', team: '/team', agency: '/account/agencia', agencia: '/account/agencia', perfil: '/account/perfil', logout: '/logout', solutions: {}},
});
const pageHtml = (mode, section) => `<!doctype html><html lang="pt-BR" data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/app.css"><link rel="stylesheet" href="/static/kit.css"></head><body class="portal portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root" class="cv-home-root"></div><script id="cadu-conversations-v2-bootstrap" type="application/json">${JSON.stringify(bootstrap(mode, section))}</script><script type="module" src="/static/app.js"></script></main></body></html>`;

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://workspace.test/**', route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/brands/new' && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Marca criada</title>'});
      if (pathname === '/projects/new' && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({project: {id: 'p1', href: '/projects/p1'}})});
      if (pathname.startsWith('/account/save-') && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Salvo</title>'});
      if (pathname === '/brands' || pathname === '/projects') return route.fulfill({status: 200, contentType: 'text/html', body: pageHtml(pathname === '/brands' ? 'brandsMode' : 'projectsMode')});
      if (pathname === '/account/agencia' || pathname === '/account/perfil') return route.fulfill({status: 200, contentType: 'text/html', body: pageHtml('accountMode', pathname.split('/').pop())});
      if (pathname === '/mark.svg') return route.fulfill({status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"/>'});
      if (pathname === '/static/kit.css') return route.fulfill({status: 200, contentType: 'text/css', body: fs.readFileSync(kitCss)});
      if (pathname.startsWith('/static/')) {
        const file = path.join(assets, pathname.slice('/static/'.length));
        return route.fulfill(fs.existsSync(file) ? {status: 200, contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(file)} : {status: 404, body: ''});
      }
      return route.fulfill({status: 200, contentType: 'application/json', body: '{}'});
    });
    for (const {pathname, label} of [{pathname: '/brands', label: 'Nova marca'}, {pathname: '/projects', label: 'Novo projeto'}]) {
      for (const width of [1440, 820, 390]) {
        await page.setViewportSize({width, height: 900});
        await page.goto(`http://workspace.test${pathname}`);
        const action = page.getByRole('button', {name: label});
        await action.waitFor();
        assert.equal(await action.getAttribute('data-cadu-untitled-button'), '', `${pathname} ${width}: official Button mounted`);
        const state = await action.evaluate(element => ({background: getComputedStyle(element).backgroundColor, width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth}));
        assert.equal(state.background, 'rgb(8, 119, 101)', `${pathname} ${width}: CADU Workspace brand color`);
        assert.ok(state.width <= state.viewport + 1, `${pathname} ${width}: no horizontal overflow`);
        if (pathname === '/brands' && width === 820 && process.env.CADU_UNTITLED_SCREENSHOT) await page.screenshot({path: process.env.CADU_UNTITLED_SCREENSHOT});
        if (width === 390) {
          await action.focus();
          await page.keyboard.press('Enter');
        } else await action.click();
        const dialog = page.getByRole('dialog');
        await dialog.waitFor();
        const submit = dialog.getByRole('button', {name: pathname === '/brands' ? 'Criar marca' : 'Criar projeto'});
        assert.equal(await submit.getAttribute('data-cadu-untitled-button'), '', `${pathname} ${width}: official submit Button mounted`);
        assert.equal(await submit.evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(8, 119, 101)', `${pathname} ${width}: submit keeps Workspace skin`);
        if (width === 1440) {
          await dialog.locator('input[name="name"]').fill(pathname === '/brands' ? 'Marca de teste' : 'Projeto de teste');
          if (pathname === '/projects') await dialog.locator('textarea[name="description"]').fill('Contexto do projeto de teste.');
          const requestPromise = page.waitForRequest(request => request.url().endsWith(pathname === '/brands' ? '/brands/new' : '/projects/new') && request.method() === 'POST');
          await submit.click();
          const request = await requestPromise;
          assert.ok(request.postData()?.includes(pathname === '/brands' ? 'Marca de teste' : 'Projeto de teste'), `${pathname}: form submission reaches the API`);
        }
      }
    }
    for (const {pathname, label, endpoint} of [{pathname: '/account/agencia', label: 'Salvar dados da agência', endpoint: '/account/save-agency'}, {pathname: '/account/perfil', label: 'Salvar perfil', endpoint: '/account/save-profile'}]) {
      for (const width of [1440, 390]) {
        await page.setViewportSize({width, height: 900});
        await page.goto(`http://workspace.test${pathname}`);
        const action = page.getByRole('button', {name: label});
        await action.waitFor();
        assert.equal(await action.getAttribute('data-cadu-untitled-button'), '', `${pathname} ${width}: official account Button mounted`);
        assert.equal(await action.evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(8, 119, 101)', `${pathname} ${width}: account action keeps Workspace skin`);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        assert.ok(overflow <= 1, `${pathname} ${width}: no horizontal overflow`);
        if (width === 1440) {
          const requestPromise = page.waitForRequest(request => request.url().endsWith(endpoint) && request.method() === 'POST');
          await action.click();
          await requestPromise;
        }
      }
    }
    assert.deepEqual(errors, []);
    console.log('PASS: Untitled UI Button, CADU skin, catalog and account actions at desktop, tablet and phone widths.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
