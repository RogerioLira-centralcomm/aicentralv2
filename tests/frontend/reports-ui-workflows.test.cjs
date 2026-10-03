const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const clientId = 1000000000;
const customerId = 31;
const flowId = '0b8e2f4a-5c6d-4e7f-8a9b-1c2d3e4f5a6b';
const siteId = '6c0f3f0e-7a4b-4e55-9d1e-2f6b8a1c9d10';
const importId = 'f35a1b3e-3a5d-4c4f-b818-6f63456b2a35';
const organizationId = 23;
let canManageAccess = false;
const state = {
  clients: [{id: clientId, name: 'Cliente de interface', kind: 'reports'}],
  customers: [],
  accounts: [],
  campaigns: [],
  flows: [],
  supertagSites: [],
  reports: [{id: 5, campaign_name: 'Relatório de teste', project_ref: '', revision: 2,
    updated_at: '2026-09-28T12:00:00Z'}],
  discoveryPage: {id: 'page-ui-1', path_prefix: '/landing', page_host: 'example.test', title: 'Landing',
    selected_kind: 'page', selected_as_entry: true, suggested_role: 'entry', campaign_id: null, form_count: 0, evidence: {signals: []}},
  suggestion: {result: {prompt_version: 'reports-import-column-choice-v2', evidence_fingerprint: 'evidence-ui-1', suggestions: [
    {header: 'Coluna de gasto não reconhecida', field: 'cost', confidence: 0.9,
      probabilities: {cost: 0.9}},
  ], omitted_count: 0}},
  calls: [],
  // Mirrors the server: the bootstrap call with ?client_id= picks the client; every other call reads it from the session.
  sessionClient: clientId,
};

function response(res, body, status = 200, type = 'application/json; charset=utf-8') {
  res.writeHead(status, {'Content-Type': type});
  res.end(type.startsWith('application/json') ? JSON.stringify(body) : body);
}

const html = `<!doctype html><html data-cadu-theme="light" data-cadu-skin="workspace"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"><link rel="stylesheet" href="/static/cadu_connect/react/untitled.css"></head><body class="portal--workspace"><div id="cadu-reports-v1-root" data-workspace-url="#" data-planner-url="#" data-studio-url="#" data-skills-url="#" data-credits-url="/workspace/app/creditos" data-profile-url="/workspace/app/conta?section=perfil" data-user-name="Teste Reports"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>`;
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
    id: flowId, flow_code: 'CF_UI001', name: 'Fluxo de teste', status: 'draft',
    config: {nodes: [], edges: []}, tag_id: 'tag-ui-1', tag_label: 'Fluxo de teste',
    allowed_host: 'example.test', campaign_names: state.campaigns[0]?.name || '',
    monitor_enabled: false, monitor_interval_minutes: 15, monitor_status: 'unknown',
    draft_revision: 1, published_revision: null,
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
  await page.route('**/static/cadu_connect/google-ads-engine-v2.js', route => route.fulfill({body: 'var CADU={endpoint:"__CADU_INGEST_URL__",apiKey:"__CADU_API_KEY__",accountIds:__CADU_ACCOUNT_IDS__};', contentType: 'text/javascript'}));
  await page.route('**/connect/api/v2/reports/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname.replace('/connect/api/v2/reports', '');
    const method = request.method();
    let body = {};
    try { body = request.postDataJSON() || {}; } catch (_) { /* GET or non-JSON request */ }
    if (pathName === '/bootstrap' && url.searchParams.get('client_id')) state.sessionClient = Number(url.searchParams.get('client_id'));
    if (pathName !== '/bootstrap') {
      assert.equal(body.client_id ?? url.searchParams.get('client_id'), null, `${method} ${pathName} não envia client_id; o cliente vem da sessão`);
    }
    const sessionClient = state.sessionClient;
    state.calls.push({path: pathName, method, client_id: sessionClient, body});

    if (pathName === '/bootstrap' && method === 'GET') {
      const client = {client_id: clientId, organization_id: organizationId, client_name: 'Cliente de interface', role: 'admin', client_kind: 'reports'};
      return route.fulfill({json: {
        ready: true, client, csrf: 'csrf-ui', clients: state.clients,
        can_manage_access: canManageAccess, can_manage_clients: true,
        customers: state.customers, accounts: state.accounts, campaigns: state.campaigns, reports: state.reports, link_tests: [], workspace_projects: [],
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
      column_evidence_fingerprint: 'evidence-ui-1',
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
    if (pathName === '/supertag/site-check' && method === 'GET') {
      assert.equal(url.searchParams.get('url'), 'https://example.test');
      return route.fulfill({json: {host: 'example.test', title: 'Site de teste', status: 200}});
    }
    if (pathName === '/supertag/sites' && method === 'GET') return route.fulfill({json: {sites: state.supertagSites}});
    if (pathName === '/supertag/sites' && method === 'POST') {
      assert.deepEqual(body, {label: 'Site de teste', allowed_host: 'example.test'},
        'o cadastro da Super Tag envia somente o contrato aceito pela API');
      const site = {id: siteId, public_id: 'public-ui-1', label: body.label,
        allowed_host: body.allowed_host, enabled: true, config: {audience_days: 90, retention_days: 90},
        snippet: '<script data-cadu-site="public-ui-1"></script>'};
      state.supertagSites.push(site);
      return route.fulfill({status: 201, json: {site}});
    }
    if (pathName === `/supertag/sites/${siteId}/events` && method === 'GET') return route.fulfill({json: {
      site: {id: siteId, events_30d: 0}, summary: [], pages: [], heatmap: [],
    }});
    if (pathName === `/supertag/sites/${siteId}` && method === 'PATCH') {
      state.supertagSites[0].config = {...state.supertagSites[0].config, ...body};
      return route.fulfill({json: {site: state.supertagSites[0]}});
    }
    if (pathName === '/link-tests' && method === 'POST') {
      assert.equal(sessionClient, clientId, 'a análise de link mantém o client_id Reports selecionado');
      assert.equal(body.url, 'https://example.test/landing?utm_source=google');
      assert.equal(body.mode, 'destination');
      return route.fulfill({json: {result: {kind: 'destination', score: 95,
        status_label: 'Pronto', summary: 'O clique chega ao destino.',
        final_url: 'https://example.test/landing?utm_source=google', alerts: []}}});
    }
    if (pathName === '/workspace/map' && method === 'GET') return route.fulfill({json: {available: false}});
    if (pathName === '/customers' && method === 'POST') {
      assert.equal(body.name, 'Cliente criado na interface');
      state.customers.push({id: customerId, name: body.name, status: 'active'});
      return route.fulfill({status: 201, json: {customer: {id: customerId, name: body.name}}});
    }
    if (pathName === '/accounts' && method === 'POST') {
      assert.equal(sessionClient, clientId, 'a conta fica no cliente Reports aberto');
      assert.equal(String(body.customer_id), String(customerId), 'a conta nasce no cliente recém-criado');
      const account = {id: 41, platform: body.platform, external_id: body.platform === 'google_ads' ? body.external_id.replaceAll('-', '') : body.external_id, name: body.name,
        parent_account_id: null, account_kind: body.account_kind, status: 'active', customer_id: body.customer_id ? Number(body.customer_id) : null};
      state.accounts.push(account);
      state.accounts.push({id: 42, platform: 'google_ads', external_id: '1', name: 'Conta antiga desativada',
        parent_account_id: null, account_kind: 'advertiser', status: 'disabled'});
      return route.fulfill({status: 201, json: {account}});
    }
    if (pathName === '/campaigns' && method === 'POST') {
      assert.equal(sessionClient, clientId, 'a campanha usa o mesmo cliente Reports');
      assert.equal(String(body.customer_id), String(customerId), 'a campanha nasce no cliente recém-criado');
      assert.equal(Number(body.account_id), 41, 'a campanha aponta para a conta do cliente');
      const campaign = {id: 77, account_id: 41, external_id: body.external_id, name: body.name,
        status: 'ENABLED', account_name: 'Conta de teste', platform: 'google_ads', channel_type: body.channel_type || '',
        customer_id: body.customer_id ? Number(body.customer_id) : null};
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
      assert.equal(sessionClient, clientId, 'o fluxo usa o mesmo cliente Reports');
      assert.equal(body.allowed_host, 'example.test');
      assert.equal(String(body.customer_id), String(customerId), 'o fluxo nasce associado ao cliente criado');
      assert.equal(Number(body.campaign_id), 77, 'o fluxo associa a campanha do mesmo cliente');
      const flow = makeFlow();
      flow.name = body.name;
      flow.allowed_host = body.allowed_host;
      state.flows = [flow];
      return route.fulfill({status: 201, json: {flow, tag: {id: flow.tag_id}, tag_urls: {}}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/discoveries/page-ui-1/select` && method === 'POST') {
      assert.equal(sessionClient, clientId);
      assert.equal(Number(body.campaign_id), 77, 'etapa do fluxo associa campanha do mesmo cliente');
      state.discoveryPage.campaign_id = 77;
      state.discoveryPage.selected_kind = body.selection === 'conversion' ? 'conversion' : 'page';
      return route.fulfill({json: {page_id: 'page-ui-1', campaign_id: 77, selection: body.selection}});
    }
    if (pathName === `/flow/flows/${flowId}/plan-versions` && method === 'POST') {
      assert.equal(body.expected_revision, state.flows[0].draft_revision);
      return route.fulfill({status: 201, json: {version: {revision: 1}}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/publish` && method === 'POST') {
      state.flows[0].status = 'published';
      state.flows[0].published_revision = state.flows[0].draft_revision;
      return route.fulfill({json: {flow: state.flows[0]}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/monitor` && method === 'PATCH') {
      assert.equal(sessionClient, clientId);
      state.flows[0].monitor_enabled = body.enabled;
      return route.fulfill({json: {flow: state.flows[0]}});
    }
    if (pathName === `/flow/flows/${state.flows[0]?.id}/monitor/check` && method === 'POST') {
      assert.equal(sessionClient, clientId);
      await new Promise(resolve => setTimeout(resolve, 350));
      return route.fulfill({json: {check: {status: 'online', pages: []}}});
    }
    if (pathName.startsWith('/flow/flows/') && pathName.endsWith('/discoveries') && method === 'GET') return route.fulfill({json: {run: null, pages: []}});
    if (pathName === `/flow/flows/${flowId}` && method === 'PATCH') {
      assert.equal(body.expected_revision, state.flows[0].draft_revision, 'o rascunho salva sobre a revisão atual');
      Object.assign(state.flows[0], {name: body.name, config: body.config, draft_revision: state.flows[0].draft_revision + 1});
      return route.fulfill({json: {flow: state.flows[0]}});
    }
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
        data-cadu-site="public-ui" data-cadu-config="${publicTagBase}/config.json"></script>
      </body></html>`});
  });
  await page.route(`${publicTagBase}/config.json`, route => {
    publicTagCalls.push({url: route.request().url(), method: route.request().method(), headers: route.request().headers()});
    return route.fulfill({status: 200, headers: corsHeaders,
      json: {site_id: 'public-ui', config_version: 2,
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
    await page.waitForURL('**/connect/app/settings/accounts');
    await page.getByRole('heading', {name: 'Contas e campanhas'}).waitFor();
    await page.getByRole('button', {name: 'Novo cliente'}).click();
    await page.getByRole('heading', {name: 'Novo cliente'}).waitFor();
    // "Criar cliente" stays enabled; the required name field is what stops an empty submit (browser validation).
    const customerName = page.getByLabel('Nome do cliente ou anunciante');
    await page.getByRole('button', {name: 'Criar cliente'}).click();
    assert.equal(await customerName.evaluate(input => input.validity.valueMissing), true, 'cadastro exige nome');
    assert.equal(state.calls.some(item => item.path === '/customers' && item.method === 'POST'), false,
      'sem nome, nenhum cliente é enviado à API');
    await customerName.fill('Cliente criado na interface');
    await page.getByRole('button', {name: 'Criar cliente'}).click();
    await page.waitForURL(`**/connect/app/settings/accounts?customer=${customerId}`);
    await page.getByRole('heading', {name: 'Cliente criado na interface', level: 2}).waitFor();
    await page.getByRole('button', {name: 'Conta de mídia'}).click();
    await page.getByLabel('Nome da conta').fill('Conta de teste');
    await page.getByLabel('ID da conta').fill('123-456-7890');
    await page.getByRole('button', {name: 'Adicionar conta', exact: true}).click();
    await page.getByText('Conta de teste', {exact: true}).waitFor();

    await page.getByRole('button', {name: 'Campanha', exact: true}).click();
    await page.getByLabel('Conta de mídia').selectOption('41');
    await page.getByLabel('Nome da campanha').fill('Campanha de teste');
    await page.getByLabel('ID da campanha').fill('campaign-001');
    await page.getByRole('button', {name: 'Adicionar campanha', exact: true}).click();
    await page.getByRole('link', {name: 'Campanha de teste'}).waitFor();

    await page.getByRole('link', {name: 'Fontes de dados'}).click();
    await page.getByRole('link', {name: 'Conexões e chaves'}).click();
    await page.getByRole('heading', {name: 'Conectar fonte'}).waitFor();
    await page.getByRole('radio', {name: /Conta de teste/}).check();
    await page.getByRole('checkbox', {name: /Também gerar o script de Ações/}).uncheck();
    await page.getByRole('button', {name: 'Gerar script de Leitura'}).click();
    await page.getByText(/^Script de Leitura · v/).waitFor();
    assert.equal(await page.getByText(/sem ID de 10 dígitos/).count(), 0,
      'contas inválidas desativadas não bloqueiam nem confundem uma integração válida');

    await page.getByRole('link', {name: 'Super Tag'}).click();
    await page.getByRole('button', {name: 'Conectar site'}).first().click();
    await page.getByLabel('Endereço do site').fill('https://example.test');
    await page.getByRole('button', {name: 'Verificar'}).click();
    await page.getByText('Respondeu').waitFor();
    assert.equal(await page.getByLabel('Nome desta instalação').inputValue(), 'Site de teste', 'o título do site vira o nome da instalação');
    await page.getByRole('button', {name: 'Criar instalação'}).click();
    // The new installation opens selected (by path or by the header site picker).
    await page.waitForURL(url => url.pathname === `/connect/app/supertag/sites/${siteId}` || url.searchParams.get('scope_site') === siteId);
    await page.getByRole('tab', {name: 'Instalação'}).click();
    await page.getByText('public-ui-1', {exact: false}).first().waitFor();
    const supertagCreateCall = state.calls.find(item => item.path === '/supertag/sites' && item.method === 'POST');
    assert.equal(Number(supertagCreateCall?.client_id), clientId,
      'a instalação Super Tag é criada no client_id selecionado');
    await page.getByRole('tab', {name: 'Configurações'}).click();
    const supertagUpdate = page.waitForResponse(response => response.url().includes(`/supertag/sites/${siteId}`) && response.request().method() === 'PATCH');
    await page.getByLabel('Duração do identificador').selectOption('60');
    await supertagUpdate;
    assert.equal(state.supertagSites[0].config.audience_days, 60,
      'as configurações da instalação são persistidas para o cliente Reports selecionado');

    await page.getByRole('link', {name: 'Link Tester'}).click();
    await page.getByLabel('URL').fill('https://example.test/landing?utm_source=google');
    await page.getByRole('button', {name: 'Analisar link'}).click();
    await page.getByText('O clique chega ao destino.').waitFor();

    await page.getByRole('link', {name: 'Site & Jornada'}).click();
    await page.getByRole('link', {name: 'Fluxos'}).click();
    await page.getByRole('button', {name: 'Novo fluxo'}).click();
    await page.getByRole('radio', {name: /Testar a página inicial/}).check();
    await page.getByPlaceholder('https://www.exemplo.com.br').fill('https://example.test');
    await page.getByRole('button', {name: 'Validar domínio'}).click();
    await page.getByText('example.test · HTTP 200').waitFor();
    await page.getByLabel('Nome do fluxo').fill('Fluxo de teste');
    await page.getByText('Associações').click();
    await page.getByLabel('Cliente / anunciante').selectOption(String(customerId));
    await page.locator('.reports-flow-new__optional label').filter({hasText: /^Campanha/}).locator('select').selectOption('77');
    await page.getByRole('button', {name: 'Criar fluxo', exact: true}).click();
    await page.waitForURL(`**/connect/app/flows/${flowId}**`);
    await page.getByRole('button', {name: 'Adicionar ao mapa'}).click();
    const flowNodes = page.locator('.reports-flow-canvas .react-flow__node:not([data-id="__exit"])');
    await page.getByRole('button', {name: 'Página / URL'}).click();
    await flowNodes.first().waitFor();
    assert.equal(await flowNodes.count(), 1, 'clique na paleta adiciona um único bloco');
    await page.getByRole('button', {name: 'Adicionar ao mapa'}).click();
    await page.getByRole('button', {name: 'Página / URL'}).dragTo(page.locator('.reports-flow-canvas .react-flow__pane'), {targetPosition: {x: 420, y: 260}});
    await page.waitForFunction(() => document.querySelectorAll('.reports-flow-canvas .react-flow__node:not([data-id="__exit"])').length >= 2);
    await page.waitForTimeout(150);
    assert.equal(await flowNodes.count(), 2, 'arrastar um bloco não aciona também o clique da paleta');
    await page.getByRole('button', {name: 'Publicar', exact: true}).click();
    const publication = page.getByRole('dialog', {name: 'Publicar'});
    await publication.getByRole('radio', {name: /Publicar plano/}).check();
    await publication.getByRole('button', {name: 'Publicar plano', exact: true}).click();
    await page.getByText('Plano v1 publicado para aprovação', {exact: false}).waitFor();
    assert.equal(state.calls.filter(item => item.path === `/flow/flows/${flowId}/plan-versions`).length, 1,
      'publicar o plano congela uma versão sem ligar a medição');
    // Turning measurement on needs real pages and a connected conversion (covered by reports-flow-m1-browser); here the
    // flow is treated as already measured to exercise the availability monitor.
    Object.assign(state.flows[0], {status: 'published', published_revision: state.flows[0].draft_revision});

    await page.goto(`http://127.0.0.1:${address.port}/connect/app/flows/${flowId}/monitor`);
    await page.getByRole('heading', {name: 'Disponibilidade das páginas'}).waitFor();
    await page.getByRole('button', {name: 'Ativar monitoramento'}).click();
    await page.getByRole('button', {name: 'Desativar monitoramento'}).waitFor();
    const monitorCheckResponse = page.waitForResponse(response => response.url().includes('/monitor/check'));
    await page.getByRole('button', {name: 'Verificar agora'}).click();
    await page.getByRole('button', {name: 'Verificando…'}).waitFor();
    assert.equal(await page.locator('.reports-page-monitor.is-monitor-checking').count(), 1, 'o painel sinaliza visualmente a checagem em andamento');
    assert.equal(await page.locator('.reports-monitor-status.is-checking i').evaluate(element => getComputedStyle(element).animationName), 'reports-pulse', 'o status de disponibilidade anima durante a checagem');
    assert.equal(await page.locator('.reports-flow-monitor-node.is-checking').count(), 0, 'a checagem HTTP não anima o gráfico independente de sessões');
    await monitorCheckResponse;
    await page.getByRole('button', {name: 'Verificar agora'}).waitFor();

    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#conversions`);
    await page.waitForURL('**/connect/app/journey/conversions**');
    await page.getByRole('heading', {name: 'Site & Jornada', level: 1}).waitFor();
    assert.equal(await page.locator('.rs-tabs a[aria-current="page"]').innerText(), 'Conversões',
      'rota antiga de conversões abre a aba Conversões de Site & Jornada');
    assert.equal(await page.locator('a[href="#conversions"]').count(), 0, 'Conversões não duplica a página na navegação');
    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#data-library`);
    // The old #data-library hash lands on Importações (files view); only /connect/app/data-library keeps ?view=library.
    await page.waitForURL('**/connect/app/imports');
    await page.getByRole('heading', {name: 'Fontes de dados', level: 1}).waitFor();
    assert.equal(await page.locator('.rs-tabs a[aria-current="page"]').innerText(), 'Importações',
      'Biblioteca de dados abre dentro de Importações');
    assert.equal(await page.getByRole('link', {name: 'Biblioteca de dados'}).count(), 0, 'Biblioteca de dados fica dentro de Importações');
    await page.getByRole('button', {name: 'Revisar', exact: true}).click();
    await page.getByRole('button', {name: 'Mapear colunas'}).click();
    await page.getByRole('heading', {name: 'Mapear colunas'}).waitFor();
    await page.getByRole('button', {name: 'Sugerir'}).click();
    await page.getByText('Concentração entre alternativas, não garantia de acerto.', {exact: false}).waitFor();
    assert.equal(state.calls.some(item => item.path === `/imports/${importId}/map-columns`), false,
      'a sugestão TypeSafe não é aplicada automaticamente');
    await page.getByRole('button', {name: 'Usar', exact: true}).click();
    assert.equal(await page.getByLabel('Custo', {exact: true}).inputValue(), 'Coluna de gasto não reconhecida',
      'usar a sugestão só preenche o formulário');
    await page.getByLabel('Justificativa').fill('Cabeçalho revisado pelo operador');
    await page.getByRole('button', {name: 'Aplicar às linhas pendentes'}).click();
    assert.ok(state.calls.some(item => item.path === `/imports/${importId}/map-columns`),
      'a aplicação só é enviada após a confirmação no formulário');

    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#reports`);
    await page.getByRole('heading', {name: 'Relatórios', level: 1}).waitFor();
    // Same account block as the Workspace sidebar (SidebarAccount): credits usage above the profile link.
    const profile = page.locator('.cadu-sidebar-account__profile');
    const usage = page.locator('.cadu-sidebar-account__usage');
    assert.match(await profile.getAttribute('href'), /conta\?section=perfil/);
    assert.match(await usage.getAttribute('href'), /creditos/);
    await page.getByText('88,3%', {exact: true}).waitFor();
    assert.match(await usage.getAttribute('class'), /is-high/, 'uso acima de 80% fica destacado');
    await page.getByRole('button', {name: /Relatório de teste/}).click();
    await page.getByRole('button', {name: 'Planejar próximo passo'}).click();
    await page.getByText('Reunir evidência suficiente', {exact: true}).waitFor();
    await page.getByRole('button', {name: 'Incorporar às notas'}).click();
    assert.match(await page.getByLabel('Contexto de gestão').inputValue(), /Reunir evidência suficiente/,
      'o operador incorpora o plano ao rascunho antes de salvar');
    await page.getByRole('button', {name: 'Revisar', exact: true}).click();
    await page.getByRole('button', {name: 'Comparar trechos com TypeSafe'}).click();
    await page.getByText('Trecho compatível · 90%').waitFor();
    assert.equal(state.calls.some(item => item.path === '/workspaces/5/document'), false,
      'planejar e revisar não gravam o relatório sem confirmação');

    for (const [section, title] of [
      // Old #section links land on the page's current area (hub title in the header).
      ['overview', 'Visão geral'], ['accounts', 'Clientes e contas'], ['campaigns', 'Mídia'], ['reports', 'Relatórios'],
      ['imports', 'Fontes de dados'], ['monitor', 'Fontes de dados'], ['supertag', 'Fontes de dados'],
      ['flow', 'Site & Jornada'], ['events', 'Fontes de dados'], ['links', 'Link Tester'],
    ]) {
      await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#${section}`);
      await page.locator('.reports-shell h1, main.reports-content[role="alert"]').first().waitFor();
      assert.equal(await page.getByText('Não foi possível exibir o Reports').count(), 0, `${title} (#${section}) renderiza sem cair no ErrorBoundary`);
      await page.getByRole('heading', {name: title, level: 1}).waitFor();
      assert.equal(await page.locator('.reports-content .reports-error').count(), 0, `${title} abre sem erro da API`);
    }
    canManageAccess = true;
    await page.goto(`http://127.0.0.1:${address.port}/connect/app?client_id=${clientId}#access`);
    await page.getByRole('heading', {name: 'Acessos', level: 1}).waitFor();
    assert.equal(await page.locator('.reports-content .reports-error').count(), 0, 'Acessos abre para perfil autorizado');

    const testedClientIds = state.calls.filter(item => item.path === '/accounts' || item.path === '/campaigns' || item.path.startsWith('/flow/flows')).map(item => Number(item.client_id));
    assert.ok(testedClientIds.length >= 6, 'cadastros, associações e monitoramento foram executados pela interface');
    assert.ok(testedClientIds.every(id => id === clientId), 'conta, campanha e fluxo mantêm o mesmo client_id');

    await page.goto('https://example.test/');
    const collectResponse = page.waitForResponse(response => response.url() === `${publicTagBase}/collect`);
    // Consent belongs to the website: the tag collects without a banner of its own.
    await page.waitForFunction(() => window.CaduSuperTag && window.CaduSuperTag.getSessionId());
    assert.equal(await page.getByRole('button', {name: 'Aceitar analytics'}).count(), 0, 'a tag não mostra aviso de consentimento');
    await page.evaluate(() => window.CaduSuperTag.trackConversion('test_conversion'));
    await collectResponse;
    assert.ok(!publicTagCalls.some(item => item.url.endsWith('/consent')), 'a tag não chama o endpoint de consentimento');
    const collectedEvents = publicTagCalls.filter(item => item.body?.includes('events')).flatMap(item => JSON.parse(item.body).events);
    assert.ok(collectedEvents.some(item => item.kind === 'page_view'), `a tag envia visualização sem etapa de consentimento: ${JSON.stringify(publicTagCalls)}`);
    assert.ok(collectedEvents.some(item => item.kind === 'conversion' && item.event_name === 'test_conversion'),
      'a tag envia conversões próprias');

    assert.deepEqual(errors, [], `erros JavaScript de interface: ${errors.join('; ')}`);
    process.stdout.write('Reports UI e Super Tag: cadastros, links, fluxos, monitoramento, coleta sem consentimento próprio e conversão passaram.\n');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { process.stderr.write(`${error.stack || error}\n`); process.exitCode = 1; });
