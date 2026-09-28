const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const clientId = 1000000000;
const newClientId = 1000000010;
const importId = 'f35a1b3e-3a5d-4c4f-b818-6f63456b2a35';
const organizationId = 23;
let canManageAccess = false;
const state = {
  clients: [{id: clientId, name: 'Cliente de interface', kind: 'reports'}],
  accounts: [],
  campaigns: [],
  flows: [],
  supertagSites: [],
  reports: [{id: 5, campaign_name: 'Relatório de teste', project_ref: '', revision: 2,
    updated_at: '2026-09-28T12:00:00Z'}],
  discoveryPage: {id: 'page-ui-1', path_prefix: '/landing', page_host: 'example.test', title: 'Landing',
    selected_kind: 'page', selected_as_entry: true, suggested_role: 'entry', campaign_id: null, form_count: 0, evidence: {signals: []}},
  suggestion: {result: {prompt_version: 'reports-import-column-choice-v2', suggestions: [
    {header: 'Coluna de gasto não reconhecida', field: 'cost', confidence: 0.9,
      probabilities: {cost: 0.9}},
  ], omitted_count: 0}},
  calls: [],
};

function response(res, body, status = 200, type = 'application/json; charset=utf-8') {
  res.writeHead(status, {'Content-Type': type});
  res.end(type.startsWith('application/json') ? JSON.stringify(body) : body);
}

const html = `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"></head><body class="portal--workspace"><div id="cadu-reports-v1-root" data-workspace-url="#" data-planner-url="#" data-studio-url="#" data-skills-url="#" data-credits-url="/workspace/app/creditos" data-profile-url="/workspace/app/conta?section=perfil" data-user-name="Teste Reports"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>`;
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname.startsWith('/static/cadu_connect/react/')) {
    const file = path.join(root, 'aicentralv2', 'static', 'cadu_connect', url.pathname.slice('/static/cadu_connect/'.length));
    if (!file.startsWith(path.join(root, 'aicentralv2', 'static', 'cadu_connect', 'react'))) return response(res, 'Not found', 404, 'text/plain');
    return response(res, fs.readFileSync(file), 200, file.endsWith('.css') ? 'text/css' : 'text/javascript');
  }
  return response(res, html, 200, 'text/html; charset=utf-8');
});

function makeFlow() {
  return {
    id: 'flow-ui-1', flow_code: 'CF_UI001', name: 'Fluxo de teste', status: 'draft',
    config: {nodes: [], edges: []}, tag_id: 'tag-ui-1', tag_label: 'Fluxo de teste',
    allowed_host: 'example.test', campaign_names: state.campaigns[0]?.name || '',
    monitor_enabled: false, monitor_interval_minutes: 15, monitor_status: 'unknown',
  };
}

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  const page = await browser.newPage();
  page.setDefaultTimeout(10000);
  const errors = [];
  const publicTagCalls = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/workspace/api/creditos/resumo', route => route.fulfill({json: {monthly_usage_percentage: 88.3}}));
  await page.route('**/static/cadu_connect/google-ads-monitor.js', route => route.fulfill({body: 'var CADU={endpoint:"__CADU_INGEST_URL__",apiKey:"__CADU_API_KEY__",accountIds:__CADU_ACCOUNT_IDS__};', contentType: 'text/javascript'}));
  await page.route('**/connect/api/v1/reports/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname.replace('/connect/api/v1/reports', '');
    const method = request.method();
    let body = {};
    try { body = request.postDataJSON() || {}; } catch (_) { /* GET or non-JSON request */ }
    state.calls.push({path: pathName, method, client_id: body.client_id || url.searchParams.get('client_id') || null, body});

    if (pathName === '/bootstrap' && method === 'GET') {
      const id = Number(url.searchParams.get('client_id')) || clientId;
      const client = id === newClientId
        ? {client_id: newClientId, organization_id: organizationId, client_name: 'Cliente criado na interface', role: 'admin', client_kind: 'reports'}
        : {client_id: clientId, organization_id: organizationId, client_name: 'Cliente de interface', role: 'admin', client_kind: 'reports'};
      return route.fulfill({json: {
        ready: true, client, csrf: 'csrf-ui', clients: state.clients,
        can_manage_access: canManageAccess, can_manage_clients: true,
        accounts: state.accounts, campaigns: state.campaigns, reports: state.reports, link_tests: [], workspace_projects: [],
      }});
    }
    if (pathName === '/workspaces/5' && method === 'GET') return route.fulfill({json: {
      report: {id: 5, campaign_name: 'Relatório de teste', revision: 2,
        updated_at: '2026-09-28T12:00:00Z', document: {objective: 'Gerar leads', goals: '100 leads', management_notes: ''}},
      versions: [], sources: [{id: 9, original_name: 'meta-setembro.png', supplier: 'Meta Ads', status: 'pending'}],
      public_link: null,
    }});
    if (pathName === '/workspaces/5/plan' && method === 'POST') return route.fulfill({json: {plan: {
      action: 'collect_evidence', title: 'Reunir evidência suficiente',
      steps: ['Adicionar fonte e período aos dados pendentes.'],
    }, report_id: 5, revision: 2}});
    if (pathName === '/metrics' || pathName === '/import-metrics') return route.fulfill({json: {totals: {}, days: [], by_platform: [], conflicts: 0}});
    if (pathName === '/ai/status') return route.fulfill({json: {configured: false}});
    if (pathName === '/access') return route.fulfill({json: {users: []}});
    if (pathName === '/ingest-keys' && method === 'GET') return route.fulfill({json: {keys: [], runs: []}});
    if (pathName === '/ingest-keys' && method === 'POST') {
      assert.deepEqual(body.account_ids, ['1234567890'], 'a conta Google Ads segue normalizada no cadastro da integração');
      return route.fulfill({status: 201, json: {id: 'key-ui-1', token: 'token-ui-1', label: body.label,
        source_kind: body.source_kind, allowed_account_ids: body.account_ids, manager_account_id: null}});
    }
    if (pathName === '/imports' && method === 'GET') return route.fulfill({json: {ready: true, imports: [
      {id: importId, original_name: 'export.csv', status: 'needs_review', applied_count: 0,
        row_count: 1, created_at: '2026-09-28T12:00:00Z', file_kind: 'csv'},
    ], custom_metrics: []}});
    if (pathName === `/imports/${importId}` && method === 'GET') return route.fulfill({json: {
      import_file: {id: importId, original_name: 'export.csv', file_kind: 'csv', status: 'needs_review',
        applied_count: 0, row_count: 1, platform_hint: 'Meta Ads'},
      headers: ['Coluna de gasto não reconhecida'], rows: [], column_maps: [], column_suggestions: null,
      custom_values: [], range_snapshots: [],
    }});
    if (pathName === `/imports/${importId}/suggest-columns` && method === 'POST') return route.fulfill({json: {suggestion: state.suggestion}});
    if (pathName === `/imports/${importId}/map-columns` && method === 'POST') {
      assert.equal(body.mapping.cost, 'Coluna de gasto não reconhecida');
      assert.equal(body.note, 'Cabeçalho revisado pelo operador');
      return route.fulfill({json: {mapping: body.mapping}});
    }
    if (pathName === '/import-conflicts') return route.fulfill({json: {conflicts: []}});
    if (pathName === '/import-ranges') return route.fulfill({json: {snapshots: [], custom_metrics: []}});
    if (pathName === '/supertag/sites' && method === 'GET') return route.fulfill({json: {sites: state.supertagSites}});
    if (pathName === '/supertag/sites' && method === 'POST') {
      assert.deepEqual(body, {label: 'Site de teste', allowed_host: 'example.test'},
        'o cadastro da Super Tag envia somente o contrato aceito pela API');
      const site = {id: 'site-ui-1', public_id: 'public-ui-1', label: body.label,
        allowed_host: body.allowed_host, enabled: true, config: {consent_mode: 'auto', audience_days: 90, retention_days: 90},
        snippet: '<script data-cadu-site="public-ui-1"></script>'};
      state.supertagSites.push(site);
      return route.fulfill({status: 201, json: {site}});
    }
    if (pathName === '/supertag/sites/site-ui-1/events' && method === 'GET') return route.fulfill({json: {
      site: {id: 'site-ui-1', events_30d: 0}, summary: [], pages: [], heatmap: [],
    }});
    if (pathName === '/supertag/sites/site-ui-1' && method === 'PATCH') {
      state.supertagSites[0].config = {...state.supertagSites[0].config, ...body};
      return route.fulfill({json: {site: state.supertagSites[0]}});
    }
    if (pathName === '/link-tests' && method === 'POST') {
      assert.equal(body.client_id, newClientId, 'a análise de link mantém o client_id Reports selecionado');
      assert.equal(body.url, 'https://example.test/landing?utm_source=google');
      assert.equal(body.mode, 'destination');
      return route.fulfill({json: {result: {kind: 'destination', score: 95,
        status_label: 'Pronto', summary: 'O clique chega ao destino.',
        final_url: 'https://example.test/landing?utm_source=google', alerts: []}}});
    }
    if (pathName === '/clients' && method === 'POST') {
      assert.equal(body.client_id, clientId, 'cliente Reports atual acompanha a criação');
      assert.equal(body.name, 'Cliente criado na interface');
      state.clients.push({id: newClientId, name: body.name, kind: 'reports'});
      return route.fulfill({status: 201, json: {client: {id: newClientId, name: body.name}}});
    }
    if (pathName === '/accounts' && method === 'POST') {
      assert.equal(body.client_id, newClientId, 'a conta usa o cliente Reports recém-criado');
      const account = {id: 41, platform: body.platform, external_id: body.platform === 'google_ads' ? body.external_id.replaceAll('-', '') : body.external_id, name: body.name,
        parent_account_id: null, account_kind: body.account_kind, status: 'active'};
      state.accounts.push(account);
      state.accounts.push({id: 42, platform: 'google_ads', external_id: '1', name: 'Conta antiga desativada',
        parent_account_id: null, account_kind: 'advertiser', status: 'disabled'});
      return route.fulfill({status: 201, json: {account}});
    }
    if (pathName === '/campaigns' && method === 'POST') {
      assert.equal(body.client_id, newClientId, 'a campanha usa o mesmo cliente Reports');
      assert.equal(Number(body.account_id), 41, 'a campanha aponta para a conta do cliente');
      const campaign = {id: 77, account_id: 41, external_id: body.external_id, name: body.name,
        status: 'ENABLED', account_name: 'Conta de teste', platform: 'google_ads', channel_type: body.channel_type || ''};
      state.campaigns.push(campaign);
      return route.fulfill({status: 201, json: {campaign}});
    }
    if (pathName === '/flow' && method === 'GET') {
      if (!state.flows.length) state.flows.push(makeFlow());
      return route.fulfill({json: {tags: [], steps: [], flows: state.flows, tests: [], tag_urls: {},
        activity: [], online: 0, conversions: 0, confirmed: [], events: [], event_summary: {},
        event_group_count: 0, site_pages: [], page_transitions: [],
        canvas_nodes: [{id: 'node-page', type: 'page', title: 'Landing', path: '/landing', x: 20, y: 30, reached: 3, progressed: 1},
          {id: 'node-conversion', type: 'conversion', title: 'Obrigado', path: '/obrigado', x: 250, y: 30, reached: 1, progressed: 0}],
        canvas_edges: [{from: 'node-page', to: 'node-conversion'}], monitor_checks: []}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/discoveries` && method === 'GET') {
      return route.fulfill({json: {run: null, pages: [state.discoveryPage]}});
    }
    if (pathName === '/flow/flows' && method === 'POST') {
      assert.equal(body.client_id, newClientId, 'o fluxo usa o mesmo cliente Reports');
      const flow = makeFlow();
      flow.name = body.name;
      flow.allowed_host = body.allowed_host;
      state.flows = [flow];
      return route.fulfill({status: 201, json: {flow, tag: {id: flow.tag_id}, tag_urls: {}}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/discoveries/page-ui-1/select` && method === 'POST') {
      assert.equal(body.client_id, newClientId);
      assert.equal(Number(body.campaign_id), 77, 'etapa do fluxo associa campanha do mesmo cliente');
      state.discoveryPage.campaign_id = 77;
      state.discoveryPage.selected_kind = body.selection === 'conversion' ? 'conversion' : 'page';
      return route.fulfill({json: {page_id: 'page-ui-1', campaign_id: 77, selection: body.selection}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/publish` && method === 'POST') {
      state.flows[0].status = 'published';
      return route.fulfill({json: {flow: state.flows[0]}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/monitor` && method === 'PATCH') {
      assert.equal(body.client_id, newClientId);
      state.flows[0].monitor_enabled = body.enabled;
      return route.fulfill({json: {flow: state.flows[0]}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/monitor/check` && method === 'POST') {
      assert.equal(body.client_id, newClientId);
      await new Promise(resolve => setTimeout(resolve, 350));
      return route.fulfill({json: {check: {status: 'online', pages: []}}});
    }
    if (pathName.startsWith('/flow/flows/') && pathName.endsWith('/discoveries') && method === 'GET') return route.fulfill({json: {run: null, pages: []}});
    if (pathName.startsWith('/flow/flows/') && method === 'PATCH') return route.fulfill({json: {flow: state.flows[0]}});
    if (pathName.startsWith('/flow/flows/') && method === 'POST') return route.fulfill({json: {flow: state.flows[0], events: []}});
    return route.fulfill({status: 404, json: {error: `Rota de teste sem resposta: ${method} ${pathName}`}});
  });

  await page.route('**/connect/relatorios/**', async route => {
    const url = new URL(route.request().url());
    const pathName = url.pathname.replace('/connect/relatorios', '');
    if (pathName === '/5/fontes/9/revisar' && route.request().method() === 'GET') {
      return route.fulfill({json: {metrics: [{name: 'Leads', raw: '12', unit: 'count',
        definition: 'Cadastros recebidos', scope: 'Meta Ads · setembro', evidence: 'Leads: 12'}], history: []}});
    }
    if (pathName === '/5/fontes/9/revisar-typesafe' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      assert.equal(body.metrics[0].name, 'Leads');
      return route.fulfill({json: {review: {judgments: [{index: 0, name: 'Leads', raw: '12', unit: 'count',
        judgment: 'supported', confidence: 0.9}], omitted_count: 0}}});
    }
    if (pathName === '/5/fontes/9/revisar' && route.request().method() === 'POST') {
      throw new Error('A revisão TypeSafe não deve salvar os indicadores automaticamente');
    }
    return route.fulfill({status: 404, json: {error: `Rota de teste sem resposta: ${route.request().method()} ${pathName}`}});
  });

  const publicTagBase = 'https://reports.example.test/connect/public/supertag/v1/public-ui';
  const corsHeaders = {'Access-Control-Allow-Origin': 'https://example.test',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400', 'Vary': 'Origin'};
  await page.route('https://example.test/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/static/cadu_connect/cadu-supertag-v1.js') {
      return route.fulfill({status: 200, contentType: 'text/javascript',
        body: fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_connect/cadu-supertag-v1.js'), 'utf8')});
    }
    return route.fulfill({status: 200, contentType: 'text/html', body: `<!doctype html><html><head><meta charset="utf-8"></head><body>
      <script async src="https://example.test/static/cadu_connect/cadu-supertag-v1.js"
        data-cadu-site="public-ui" data-cadu-config="${publicTagBase}/config.json" data-cadu-consent="manual"></script>
      </body></html>`});
  });
  await page.route(`${publicTagBase}/config.json`, route => {
    publicTagCalls.push({url: route.request().url(), method: route.request().method(), headers: route.request().headers()});
    return route.fulfill({status: 200, headers: corsHeaders,
      json: {site_id: 'public-ui', config_version: 2, consent_required: true, consent_mode: 'auto',
        visibility_enabled: true, audience_days: 90}});
  });
  await page.route(`${publicTagBase}/consent`, async route => {
    publicTagCalls.push({url: route.request().url(), method: route.request().method(), headers: route.request().headers(), body: route.request().postData()});
    return route.fulfill({status: route.request().method() === 'OPTIONS' ? 204 : 200,
      headers: corsHeaders, ...(route.request().method() === 'POST' ? {json: {analytics: true}} : {})});
  });
  await page.route(`${publicTagBase}/collect`, async route => {
    publicTagCalls.push({url: route.request().url(), method: route.request().method(), headers: route.request().headers(), body: route.request().postData()});
    return route.fulfill({status: 204, headers: corsHeaders});
  });

  try {
    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#accounts`);
    await page.getByRole('heading', {name: 'Novo cliente'}).waitFor();
    assert.equal(await page.getByRole('button', {name: 'Criar cliente'}).isEnabled(), false, 'cadastro exige nome');
    await page.getByLabel('Nome do cliente').fill('Cliente criado na interface');
    await page.getByRole('button', {name: 'Criar cliente'}).click();
    await page.waitForURL(`**/connect/app?client_id=${newClientId}#accounts`);
    await page.getByLabel('ID da conta').fill('123-456-7890');
    await page.getByPlaceholder('Nome exibido na plataforma').fill('Conta de teste');
    await page.getByRole('button', {name: 'Salvar conta'}).click();
    await page.waitForFunction(() => document.querySelector('input[aria-label^="Nome da conta"]')?.value === 'Conta de teste');

    await page.getByRole('link', {name: 'Dados de mídia'}).click();
    await page.getByRole('heading', {name: 'Dados de mídia', level: 1}).waitFor();
    await page.locator('select').filter({has: page.locator('option[value="1234567890"]')}).selectOption('1234567890');
    await page.getByRole('button', {name: 'Gerar integração'}).click();
    await page.getByRole('heading', {name: 'Script gerado'}).waitFor();
    assert.equal(await page.locator('.reports-integration-hint').count(), 0,
      'contas inválidas desativadas não bloqueiam nem confundem uma integração válida');

    await page.getByRole('link', {name: 'Campanhas'}).click();
    await page.getByRole('heading', {name: 'Campanhas', level: 1}).waitFor();
    await page.locator('.reports-panel').filter({hasText: 'Adicionar campanha'}).locator('form select').selectOption('41');
    await page.getByLabel('Nome', {exact: true}).fill('Campanha de teste');
    await page.getByLabel('ID da campanha').fill('campaign-001');
    await page.getByRole('button', {name: 'Salvar campanha'}).click();
    await page.getByRole('button', {name: /Campanha de teste/}).waitFor();

    await page.getByRole('link', {name: 'Tags e tracking'}).click();
    await page.getByRole('button', {name: 'Nova instalação'}).click();
    await page.getByLabel('Nome do site').fill('Site de teste');
    await page.getByLabel('Domínio permitido').fill('example.test');
    await page.getByRole('button', {name: 'Criar instalação'}).click();
    await page.getByText('public-ui-1', {exact: false}).waitFor();
    const supertagCreateCall = state.calls.find(item => item.path === '/supertag/sites' && item.method === 'POST');
    assert.equal(Number(supertagCreateCall?.client_id), newClientId,
      'a instalação Super Tag é criada no client_id selecionado');
    const supertagUpdate = page.waitForResponse(response => response.url().includes('/supertag/sites/site-ui-1') && response.request().method() === 'PATCH');
    await page.getByLabel('Duração do identificador').selectOption('60');
    await supertagUpdate;
    assert.equal(state.supertagSites[0].config.audience_days, 60,
      'as configurações da instalação são persistidas para o cliente Reports selecionado');

    await page.getByRole('link', {name: 'Link Tester'}).click();
    await page.getByLabel('URL').fill('https://example.test/landing?utm_source=google');
    await page.getByRole('button', {name: 'Analisar link'}).click();
    await page.getByText('O clique chega ao destino.').waitFor();

    await page.getByRole('link', {name: 'Fluxos'}).click();
    await page.getByLabel('Nome do fluxo').fill('Fluxo de teste');
    await page.getByLabel('Domínio do site').fill('example.test');
    await page.getByRole('button', {name: 'Criar fluxo e abrir editor'}).click();
    await page.getByLabel('Campanha para /landing').selectOption('77');
    await page.getByRole('button', {name: 'Salvar'}).click();
    await page.getByRole('button', {name: 'Página / URL'}).click();
    assert.equal(await page.locator('.reports-flow-block').count(), 1, 'clique na paleta adiciona um único bloco');
    const flowCanvas = page.locator('.reports-flow-canvas');
    const pagePaletteItem = page.getByRole('button', {name: 'Página / URL'});
    await pagePaletteItem.dragTo(flowCanvas, {targetPosition: {x: 330, y: 190}});
    await page.waitForFunction(() => document.querySelectorAll('.reports-flow-block').length === 2);
    assert.equal(await page.locator('.reports-flow-block').count(), 2, 'arrastar um bloco não aciona também o clique da paleta');
    const draggedBlock = page.locator('.reports-flow-block').first();
    const dragStart = await draggedBlock.boundingBox();
    const originalLeft = await draggedBlock.evaluate(element => Number.parseFloat(element.style.left));
    await page.mouse.move(dragStart.x + 40, dragStart.y + 45);
    await page.mouse.down();
    await page.mouse.move(dragStart.x + 130, dragStart.y + 75, {steps: 5});
    await page.mouse.up();
    await page.waitForFunction(left => Number.parseFloat(document.querySelector('.reports-flow-block')?.style.left) !== left, originalLeft);
    assert.notEqual(await draggedBlock.evaluate(element => Number.parseFloat(element.style.left)), originalLeft, 'arrastar um bloco no canvas atualiza sua posição');
    const moveRight = page.getByRole('button', {name: 'Mover para direita'}).first();
    for (let index = 0; index < 15; index++) await moveRight.evaluate(button => button.click());
    assert.ok(await flowCanvas.evaluate(element => element.scrollWidth > element.clientWidth), 'canvas expande a área rolável ao mover blocos para a direita');
    await page.getByRole('button', {name: 'Publicar'}).click();
    await page.getByRole('tab', {name: /^Criar/}).click();
    await page.getByText('Campanhas: Campanha de teste').waitFor();
    await page.getByRole('button', {name: 'Monitorar'}).click();
    await page.getByRole('button', {name: 'Ativar monitoramento'}).click();
    const monitorCheckResponse = page.waitForResponse(response => response.url().includes('/monitor/check'));
    await page.getByRole('button', {name: 'Verificar agora'}).click();
    await page.getByRole('button', {name: 'Verificando…'}).waitFor();
    assert.equal(await page.locator('.reports-page-monitor.is-monitor-checking').count(), 1, 'o painel sinaliza visualmente a checagem em andamento');
    assert.equal(await page.locator('.reports-flow-monitor-node.is-checking').count(), 2, 'os blocos do monitoramento recebem estado animado durante a checagem');
    await monitorCheckResponse;
    await page.getByRole('button', {name: 'Verificar agora'}).waitFor();

    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${newClientId}#conversions`);
    await page.getByRole('heading', {name: 'Eventos', level: 1}).waitFor();
    assert.match(await page.getByRole('button', {name: 'Conversões'}).getAttribute('class'), /is-active/, 'rota antiga de conversões abre o filtro dentro de Eventos');
    assert.equal(await page.locator('a[href="#conversions"]').count(), 0, 'Conversões não duplica a página na navegação');
    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${newClientId}#data-library`);
    await page.getByRole('heading', {name: 'Importações', level: 1}).waitFor();
    await page.locator('#reports-data-library').waitFor();
    assert.equal(await page.getByRole('link', {name: 'Biblioteca de dados'}).count(), 0, 'Biblioteca de dados fica dentro de Importações');
    await page.getByRole('button', {name: 'Abrir'}).click();
    await page.getByRole('heading', {name: 'Mapear colunas do arquivo'}).waitFor();
    await page.getByRole('button', {name: 'Corrigir mapeamento com TypeSafe'}).click();
    await page.getByText('Concentração das alternativas, não uma garantia de acerto.').waitFor();
    assert.equal(state.calls.some(item => item.path === `/imports/${importId}/map-columns`), false,
      'a sugestão TypeSafe não é aplicada automaticamente');
    await page.getByRole('button', {name: 'Usar no formulário'}).click();
    await page.getByLabel('Custo').selectOption('Coluna de gasto não reconhecida');
    await page.getByLabel('Justificativa').fill('Cabeçalho revisado pelo operador');
    await page.getByRole('button', {name: 'Aplicar às linhas pendentes'}).click();
    assert.ok(state.calls.some(item => item.path === `/imports/${importId}/map-columns`),
      'a aplicação só é enviada após a confirmação no formulário');

    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${newClientId}#reports`);
    await page.getByRole('heading', {name: 'Relatórios', level: 1}).waitFor();
    const profile = page.locator('.cadu-solution-sidebar__account');
    const usage = page.locator('.cadu-solution-sidebar__usage');
    assert.match(await profile.getAttribute('href'), /conta\?section=perfil/);
    assert.match(await usage.getAttribute('href'), /creditos/);
    await page.getByText('88,3%', {exact: true}).waitFor();
    const [profileBox, usageBox] = await Promise.all([profile.boundingBox(), usage.boundingBox()]);
    assert.ok(Math.abs(profileBox.y + profileBox.height / 2 - usageBox.y - usageBox.height / 2) < 3,
      'perfil e uso ficam alinhados na mesma faixa como na sidebar do Workspace');
    await page.getByRole('link', {name: /Relatório de teste/}).click();
    await page.getByRole('button', {name: 'Planejar próximo passo com TypeSafe'}).click();
    await page.locator('.reports-suggestion strong').filter({hasText: 'Plano sugerido · Reunir evidência suficiente'}).waitFor();
    await page.getByRole('button', {name: 'Incorporar às notas do relatório'}).click();
    assert.match(await page.getByLabel('Notas de gestão').inputValue(), /Reunir evidência suficiente/,
      'o operador incorpora o plano ao rascunho antes de salvar');
    await page.getByRole('button', {name: 'Revisar ↗'}).click();
    await page.getByRole('button', {name: 'Revisar evidências com TypeSafe'}).click();
    await page.getByText('evidência direta · concentração 90%').waitFor();
    assert.equal(state.calls.some(item => item.path === '/workspaces/5/document'), false,
      'planejar e revisar não gravam o relatório sem confirmação');

    for (const [section, title] of [
      ['overview', 'Visão geral'], ['accounts', 'Contas'], ['campaigns', 'Campanhas'], ['reports', 'Relatórios'],
      ['imports', 'Importações'], ['monitor', 'Dados de mídia'], ['supertag', 'Tags e tracking'],
      ['flow', 'Fluxos'], ['events', 'Eventos'], ['links', 'Link Tester'],
    ]) {
      await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${newClientId}#${section}`);
      await page.getByRole('heading', {name: title, level: 1}).waitFor();
      assert.equal(await page.locator('.reports-content .reports-error').count(), 0, `${title} abre sem erro da API`);
    }
    canManageAccess = true;
    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${newClientId}#access`);
    await page.getByRole('heading', {name: 'Acessos', level: 1}).waitFor();
    assert.equal(await page.locator('.reports-content .reports-error').count(), 0, 'Acessos abre para perfil autorizado');

    const testedClientIds = state.calls.filter(item => item.path === '/accounts' || item.path === '/campaigns' || item.path.startsWith('/flow/flows')).map(item => Number(item.client_id));
    assert.ok(testedClientIds.length >= 6, 'cadastros, associações e monitoramento foram executados pela interface');
    assert.ok(testedClientIds.every(id => id === newClientId), 'conta, campanha e fluxo mantêm o mesmo client_id');

    await page.goto('https://example.test/');
    const collectResponse = page.waitForResponse(response => response.url() === `${publicTagBase}/collect`);
    await page.getByRole('button', {name: 'Aceitar analytics'}).click();
    await page.evaluate(() => window.CaduSuperTag.trackConversion('test_conversion'));
    await collectResponse;
    const consentCall = publicTagCalls.find(item => item.method === 'POST' && item.body?.includes('analytics'));
    assert.ok(consentCall, 'a escolha de consentimento é confirmada no endpoint público');
    const collectedEvents = JSON.parse(publicTagCalls.find(item => item.body?.includes('events'))?.body || '{"events":[]}').events;
    assert.ok(collectedEvents.some(item => item.kind === 'page_view'), `a tag envia visualização após consentimento: ${JSON.stringify(publicTagCalls)}`);
    assert.ok(collectedEvents.some(item => item.kind === 'conversion' && item.event_name === 'test_conversion'),
      'a tag envia conversões próprias');

    assert.deepEqual(errors, [], `erros JavaScript de interface: ${errors.join('; ')}`);
    process.stdout.write('Reports UI e Super Tag: cadastros, links, fluxos, monitoramento, consentimento CORS e coleta de conversão passaram.\n');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { process.stderr.write(`${error.stack || error}\n`); process.exitCode = 1; });
