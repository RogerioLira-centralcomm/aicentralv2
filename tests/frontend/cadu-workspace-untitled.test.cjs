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
const conversationsTemplate = fs.readFileSync(path.join(templates, 'conversations_v2_lab.html'), 'utf8');
assert.doesNotMatch(conversationsTemplate, /_untitled_styles\.html|untitled\/workspace-kit\.css/, 'Conversations does not load the Workspace kit');
assert.match(conversationsTemplate, /untitled\/chat-kit\.css/, 'Conversations loads its own dark Untitled kit');

const bootstrap = (mode, section = '') => ({
  [mode]: true, section, admin: true, csrf: 'test', caduMark: '/mark.svg', user: {name: 'Teste', email: 'teste@example.com'}, brands: [], projects: [], dock: {items: []},
  account: {organization: {nome_fantasia: 'Agência de teste'}, agency_context: {projects: [], brands: []}, current_user: {nome_completo: 'Pessoa de teste', email: 'teste@example.com'}, people: []},
  endpoints: {updateOrganization: '/account/save-agency', updateProfile: '/account/save-profile', creditRequest:'/account/credit-request'},
  urls: {home: '/workspace', brands: '/brands', projects: '/projects', newConversation: '/chat', createBrand: '/brands/new', inspectBrandSite:'/brands/inspect', createProject: '/projects/new', profile: '/account/perfil', usage: '/usage', plans: '/plans', team: '/team', agency: '/account/agencia', agencia: '/account/agencia', perfil: '/account/perfil', logout: '/logout', solutions: {}},
});
const pageHtml = (mode, section, extra = {}) => `<!doctype html><html lang="pt-BR" data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/app.css"><link rel="stylesheet" href="/static/kit.css"></head><body class="portal portal--workspace"><main id="content" class="portal-content--workspace-react"><div id="cadu-conversations-v2-root" class="cv-home-root"></div><script id="cadu-conversations-v2-bootstrap" type="application/json">${JSON.stringify({...bootstrap(mode, section), ...extra})}</script><script type="module" src="/static/app.js"></script></main></body></html>`;

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://workspace.test/**', route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/brands/new' && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Marca criada</title>'});
      if (pathname === '/brands/inspect' && route.request().method() === 'POST') return route.fulfill({status:200, contentType:'application/json', body:JSON.stringify({ok:true, inspection_token:'token', inspection:{ready_for_analysis:true, suggested_name:'Marca sugerida', suggested_sector:'Varejo', final_url:'https://exemplo.com.br', logo_candidates:[]}})});
      if (pathname === '/projects/new' && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({project: {id: 'p1', href: '/projects/p1'}})});
      if (pathname.startsWith('/account/save-') && route.request().method() === 'POST') return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Salvo</title>'});
      if (pathname === '/account/credit-request' && route.request().method() === 'POST') return route.fulfill({status:200, contentType:'application/json', body:JSON.stringify({success:false, message:'Solicitação registrada'})});
      if (pathname === '/brands' || pathname === '/projects') return route.fulfill({status: 200, contentType: 'text/html', body: pageHtml(pathname === '/brands' ? 'brandsMode' : 'projectsMode')});
      if (pathname === '/workspace') return route.fulfill({status:200, contentType:'text/html', body:pageHtml('homeMode', '', {home:{}, credit:{available:0}})});
      if (pathname === '/brand-detail') return route.fulfill({status:200, contentType:'text/html', body:pageHtml('brandMode', '', {canManageBrand:true, brand:{id:'b1', name:'Marca teste', profile:{}, linkedProjects:[], assets:[], reviewPack:{status:'not_started'}}, brandLinks:{deleteBrand:'/brand/delete', updateIdentity:'/brand/identity'}})});
      if (pathname === '/project-detail' || pathname === '/project-library') return route.fulfill({status:200, contentType:'text/html', body:pageHtml('projectMode', '', {project:{id:'p1', name:'Projeto teste', status:'ativo', health:{missing:[]}, links:[], files:[], deliveries:[], memory:[]}, projectLinks:{deleteProject:'/project/delete'}, projectView:pathname === '/project-library' ? 'library' : 'overview'})});
      if (pathname.startsWith('/account/')) return route.fulfill({status: 200, contentType: 'text/html', body: pageHtml('accountMode', pathname.split('/').pop())});
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
        assert.equal(await dialog.getAttribute('data-rac'), '', `${pathname} ${width}: Untitled UI React Aria modal mounted`);
        const dialogBounds = await dialog.boundingBox();
        assert.ok(dialogBounds && dialogBounds.x >= 15 && dialogBounds.x + dialogBounds.width <= width - 15, `${pathname} ${width}: modal fits viewport with gutters`);
        assert.doesNotMatch(await dialog.evaluate(element => getComputedStyle(element).fontFamily), /Times New Roman/i, `${pathname} ${width}: modal inherits CADU typography`);
        if (pathname === '/brands' && width === 820 && process.env.CADU_UNTITLED_MODAL_SCREENSHOT) await page.screenshot({path: process.env.CADU_UNTITLED_MODAL_SCREENSHOT});
        if (width === 820) {
          await page.keyboard.press('Escape');
          await dialog.waitFor({state: 'hidden'});
          await action.click();
          await dialog.waitFor();
          if (pathname === '/brands') {
            await dialog.locator('input[name="website_url"]').fill('exemplo.com.br');
            await dialog.getByRole('button', {name:'Buscar'}).click();
            await dialog.locator('input[name="name"]').waitFor();
            await page.waitForFunction(() => document.querySelector('input[name="name"]')?.value === 'Marca sugerida');
            assert.equal(await dialog.locator('input[name="sector"]').inputValue(), 'Varejo', 'Brand inspection fills the controlled Untitled UI fields');
          }
        }
        const submit = dialog.getByRole('button', {name: pathname === '/brands' ? 'Criar marca' : 'Criar projeto'});
        if (pathname === '/projects') assert.equal(await dialog.locator('select[data-cadu-untitled-select][name="brand_id"]').count(), 1, `Project ${width}: Untitled UI native select mounted`);
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
      for (const width of [1440, 820, 390]) {
        await page.setViewportSize({width, height: 900});
        await page.goto(`http://workspace.test${pathname}`);
        const action = page.getByRole('button', {name: label});
        await action.waitFor();
        assert.equal(await action.getAttribute('data-cadu-untitled-button'), '', `${pathname} ${width}: official account Button mounted`);
        const nameField = page.locator('input[data-cadu-untitled-input][name="' + (pathname.endsWith('agencia') ? 'trade_name' : 'name') + '"]');
        assert.equal(await nameField.count(), 1, `${pathname} ${width}: Untitled UI text field mounted`);
        if (pathname.endsWith('agencia')) assert.equal(await page.locator('select[data-cadu-untitled-select][name="state"]').count(), 1, `Agency ${width}: Untitled UI native select mounted`);
        if (pathname === '/account/agencia' && width === 820 && process.env.CADU_UNTITLED_ACCOUNT_SCREENSHOT) await page.screenshot({path:process.env.CADU_UNTITLED_ACCOUNT_SCREENSHOT, fullPage:true});
        assert.equal(await action.evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(8, 119, 101)', `${pathname} ${width}: account action keeps Workspace skin`);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        assert.ok(overflow <= 1, `${pathname} ${width}: no horizontal overflow`);
        if (width === 1440) {
          await nameField.fill('Nome atualizado');
          const requestPromise = page.waitForRequest(request => request.url().endsWith(endpoint) && request.method() === 'POST');
          await action.click();
          const request = await requestPromise;
          assert.ok(request.postData()?.includes('Nome+atualizado'), `${pathname}: field value reaches the form endpoint`);
        }
      }
    }
    for (const section of ['equipe', 'planos', 'uso', 'creditos', 'faturamento', 'integracoes']) {
      for (const width of [1440, 820, 390]) {
        await page.setViewportSize({width, height: 900});
        await page.goto(`http://workspace.test/account/${section}`);
        await page.locator('.cadu-ds-account-content').waitFor();
        assert.ok((await page.locator('h1').first().textContent())?.trim(), `${section} ${width}: page title is present`);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        assert.ok(overflow <= 1, `${section} ${width}: no horizontal overflow`);
      }
    }
    for (const width of [1440, 820, 390]) {
      await page.setViewportSize({width, height:900});
      await page.goto('http://workspace.test/account/creditos');
      await page.evaluate(() => window.dispatchEvent(new CustomEvent('cadu-open-purchase', {detail:{name:'Pacote de teste', price:50, tokens:1000, kind:'package'}})));
      const dialog = page.getByRole('dialog', {name:'Confirmar pacote'});
      await dialog.waitFor();
      assert.equal(await dialog.getAttribute('data-rac'), '', `Credits ${width}: Untitled UI purchase modal`);
      const bounds = await dialog.boundingBox();
      assert.ok(bounds && bounds.x >= 15 && bounds.x + bounds.width <= width - 15, `Credits ${width}: purchase modal fits viewport`);
      assert.doesNotMatch(await dialog.evaluate(element => getComputedStyle(element).fontFamily), /Times New Roman/i, `Credits ${width}: purchase modal uses CADU typography`);
      if (width === 390 && process.env.CADU_UNTITLED_PURCHASE_SCREENSHOT) await page.screenshot({path:process.env.CADU_UNTITLED_PURCHASE_SCREENSHOT});
      if (width === 1440) {
        await dialog.locator('select[data-cadu-untitled-select]').selectOption('postpaid');
        await dialog.locator('textarea[data-cadu-untitled-textarea]').fill('Pedido do time');
        const requestPromise = page.waitForRequest(request => request.url().endsWith('/account/credit-request') && request.method() === 'POST');
        await dialog.getByRole('button', {name:'Confirmar compra'}).click();
        const request = await requestPromise;
        assert.ok(request.postData()?.includes('Pacote de teste'), 'Credits: purchase payload reaches API');
        assert.ok(request.postData()?.includes('Pedido do time'), 'Credits: textarea value reaches API');
        assert.ok(request.postData()?.includes('postpaid'), 'Credits: billing selection reaches API');
      }
      await page.keyboard.press('Escape');
      await dialog.waitFor({state:'hidden'});
    }
    for (const pathname of ['/brand-detail?acao=apagar', '/project-detail?acao=excluir']) {
      for (const width of [1440, 820, 390]) {
        await page.setViewportSize({width, height:900});
        await page.goto(`http://workspace.test${pathname}`);
        const dialog = page.getByRole('dialog');
        await dialog.waitFor({timeout:5000});
        assert.equal(await dialog.getAttribute('data-rac'), '', `${pathname} ${width}: detail uses Untitled UI modal`);
        const bounds = await dialog.boundingBox();
        assert.ok(bounds && bounds.x >= 15 && bounds.x + bounds.width <= width - 15, `${pathname} ${width}: detail modal fits viewport`);
        await page.keyboard.press('Escape');
        await dialog.waitFor({state:'hidden'});
        const visiblePrimaryColors = await page.locator('button[data-cadu-untitled-button]:visible').evaluateAll(elements => elements.map(element => ({label:element.textContent.trim(), background:getComputedStyle(element).backgroundColor, text:getComputedStyle(element.querySelector('[data-text]') || element).color})));
        for (const button of visiblePrimaryColors) {
          assert.equal(button.background, 'rgb(8, 119, 101)', `${pathname} ${width}: ${button.label} keeps Workspace skin`);
          assert.equal(button.text, 'rgb(255, 255, 255)', `${pathname} ${width}: ${button.label} text has contrast`);
        }
      }
    }
    for (const width of [1440, 820, 390]) {
      await page.setViewportSize({width, height:900});
      await page.goto('http://workspace.test/project-library');
      const tabs = page.getByRole('tablist', {name:'Visualização do projeto'});
      await tabs.waitFor();
      if (width === 820 && process.env.CADU_UNTITLED_LIBRARY_SCREENSHOT) await page.screenshot({path:process.env.CADU_UNTITLED_LIBRARY_SCREENSHOT, fullPage:true});
      const addSource = page.getByRole('button', {name:'Adicionar fonte'});
      assert.equal(await addSource.getAttribute('data-cadu-untitled-button'), '', `Library ${width}: primary action uses Untitled UI Button`);
      assert.equal(await addSource.evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(8, 119, 101)', `Library ${width}: primary action keeps Workspace skin`);
      assert.equal(await addSource.evaluate(element => getComputedStyle(element).color), 'rgb(255, 255, 255)', `Library ${width}: primary action text has contrast`);
      assert.equal(await addSource.locator('[data-text]').evaluate(element => getComputedStyle(element).color), 'rgb(255, 255, 255)', `Library ${width}: nested button label has contrast`);
      assert.equal(await tabs.getByRole('tab').count(), 3, `Library ${width}: three Untitled UI view tabs`);
      const visual = tabs.getByRole('tab', {name:'Visual'});
      await visual.focus();
      await page.keyboard.press('ArrowRight');
      await page.getByRole('tab', {name:'Lista'}).waitFor();
      assert.equal(await page.getByRole('tab', {name:'Lista'}).getAttribute('aria-selected'), 'true', `Library ${width}: arrow key changes view`);
      assert.equal(await page.getByRole('tabpanel').count(), 1, `Library ${width}: selected view has an associated panel`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 1, `Library ${width}: no horizontal overflow`);
    }
    for (const width of [1440, 820, 390]) {
      await page.setViewportSize({width, height:900});
      await page.goto('http://workspace.test/workspace');
      await page.locator('.cadu-ds-home-shell').waitFor();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 1, `Home ${width}: no horizontal overflow`);
      await page.goto('http://workspace.test/workspace#atalhos');
      await page.reload();
      const shortcutDialog = page.getByRole('dialog', {name:'Configurar dock'});
      await shortcutDialog.waitFor();
      assert.equal(await shortcutDialog.getAttribute('data-rac'), '', `Home ${width}: Untitled UI shortcut modal`);
      const shortcutBounds = await shortcutDialog.boundingBox();
      assert.ok(shortcutBounds && shortcutBounds.x >= 15 && shortcutBounds.x + shortcutBounds.width <= width - 15, `Home ${width}: shortcut modal fits viewport`);
      await page.keyboard.press('Escape');
      await shortcutDialog.waitFor({state:'hidden'});
      if (width > 760) {
        const accountTrigger = page.getByRole('button', {name:'Abrir conta de Teste'});
        await accountTrigger.click();
        const menu = page.getByRole('menu', {name:'Conta e gestão'});
        await menu.waitFor();
        const menuBounds = await menu.boundingBox();
        assert.ok(menuBounds && menuBounds.x >= 0 && menuBounds.x + menuBounds.width <= width, `Home ${width}: account menu fits viewport`);
        const firstItem = menu.getByRole('menuitem').first();
        await firstItem.waitFor();
        await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitem');
        assert.equal(await firstItem.evaluate(element => element === document.activeElement), true, `Home ${width}: account menu focuses first link`);
        await page.keyboard.press('ArrowDown');
        await page.waitForFunction(() => document.querySelectorAll('.cadu-ds-account-menu [role="menuitem"]')[1] === document.activeElement);
        await page.keyboard.press('Escape');
        await menu.waitFor({state:'hidden'});
        assert.equal(await accountTrigger.evaluate(element => element === document.activeElement), true, `Home ${width}: account focus returns to trigger`);
      }
    }
    assert.deepEqual(errors, []);
    console.log('PASS: Workspace kit controls, dialogs, account navigation and page widths at desktop, tablet and phone sizes.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
