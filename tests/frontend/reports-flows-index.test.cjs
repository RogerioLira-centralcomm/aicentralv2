const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
// The flows page moved out of main.jsx; static checks read the whole Reports entry.
const main = ['main.jsx','FlowsPage.jsx','reportsCommon.jsx'].map(file=>read(`frontend/reports-v1/${file}`)).join('\n');
const css = read('frontend/reports-v1/reports-refinement.css');

test('flow list is a searchable table with one primary action and creation in a drawer', () => {
  assert.match(main, /className="reports-flow-table"/);
  assert.match(main, /Novo fluxo/);
  assert.match(main, /<ReportsDrawer open=\{flowCreateOpen\}/);
  assert.match(main, /aria-label="Buscar fluxo"/);
  assert.match(main, /aria-label="Estado do fluxo"/);
  assert.doesNotMatch(main, /reports-flow-index-heading/);
  assert.doesNotMatch(main, /Criar fluxo e Super Tag/);
  assert.doesNotMatch(main, /reports-flow-index-layout/);
});

test('the create button explains why it is disabled and internal codes stay out of the row', () => {
  assert.match(main, /Valide o domínio para continuar\./);
  assert.match(main, /aria-describedby="flow-create-hint"/);
  assert.match(main, /title=\{item\.flow_code\}/);
  assert.doesNotMatch(main, /\{item\.flow_code\} · \{item\.status/);
});

test('global filters only show on flows while following results, not on the list', () => {
  assert.match(main, /pageSection === 'flow' && new URLSearchParams\(location\.search\)\.get\('flow_view'\) === 'monitor'/);
  assert.doesNotMatch(main, /\['campaigns', 'flow', 'events'\]\.includes\(pageSection\)/);
});

test('sidebar groups do not repeat a single item as its own label and icons are distinct', () => {
  assert.match(main, /\{label:'',items:navItems\(\['overview'\]\)\}/);
  assert.match(main, /customers:'users',accounts:'table'/);
});

test('page header has one canonical definition and the brand row is compact', () => {
  assert.match(css, /\.portal--connect \.reports-shell > \.reports-main > \.reports-page-header\{min-height:56px;margin-bottom:16px\}/);
  assert.match(css, /\.cadu-solution-sidebar__switcher \.cadu-ds-solution-switcher summary\{height:30px/);
  assert.match(css, /\.cadu-solution-sidebar__footer\{display:flex/);
});

test('solution menu opens inside the expanded sidebar instead of over the page', () => {
  const selectors = read('frontend/cadu-design-system/components/WorkspaceSelectors.jsx');
  assert.match(selectors, /sidebarRect\.width >= 160/);
  assert.match(selectors, /top = rect\.bottom \+ 6/);
});

test('pages do not repeat the page title inside their first card', () => {
  assert.doesNotMatch(main, /<h2>Campanhas cadastradas<\/h2>/);
  assert.doesNotMatch(main, /<h2>Biblioteca<\/h2>/);
  assert.doesNotMatch(main, /<strong>Contas de mídia<\/strong>/);
  assert.doesNotMatch(read('frontend/reports-v1/ReportsCustomers.jsx'), /<h2>Clientes e anunciantes<\/h2>/);
  assert.match(main, /aria-label="Buscar contas"/);
});

test('empty states and product names follow one wording', () => {
  assert.match(main, /Nenhuma campanha ainda\./);
  assert.match(main, /Nenhuma conta ainda\./);
  assert.match(main, /Nenhum relatório ainda\./);
  assert.doesNotMatch(main, /Funnel Flow/);
  assert.match(main, /Abrir Fluxos/);
});

test('access list shows role names in Portuguese, filters by person and marks revoke as destructive', () => {
  assert.match(main, /ACCESS_ROLE_LABELS = \{viewer: 'Visualização', member: 'Operação', admin: 'Administração de dados'\}/);
  assert.match(main, /aria-label="Buscar pessoa"/);
  assert.match(main, /className="reports-danger-button" disabled=\{busy\} onClick=\{\(\) => setRevokeUser\(user\)\}/);
});

test('flow editor shows the draft state once and keeps the publish blocker short', () => {
  assert.doesNotMatch(main, /<summary role="status">\{selectedFlow\?\.status==='published'\?'Publicado · ': 'Rascunho · '\}/);
  assert.match(main, /`Ver \$\{plural\(blockingIssues\.length,'bloqueio','bloqueios'\)\}`/);
  assert.match(main, /title=\{`Resolva \$\{plural\(blockingIssues\.length/);
});

test('primary buttons inside panel heads keep their own text color', () => {
  assert.match(css, /\.reports-main \.reports-panel-head button span\{color:inherit;font-size:inherit\}/);
  assert.match(css, /\.reports-campaign-open>span\{display:grid/);
});

test('opening a flow never maps the site on its own; mapping is an explicit action', () => {
  assert.doesNotMatch(main, /autoDiscover/);
  assert.match(main, /Mapear site/);
});

test('Reports adapters delegate to the shared Cadu design system', () => {
  for (const [file, component] of [['ReportsFieldInput', 'CaduTextField'], ['ReportsNativeSelect', 'CaduSelectField'], ['ReportsTextArea', 'CaduTextAreaField'], ['ReportsDrawer', 'CaduDrawer'], ['ReportsConfirmDialog', 'CaduConfirmDialog'], ['ReportsTabs', 'CaduTabs']]) {
    assert.match(read(`frontend/reports-v1/${file}.jsx`), new RegExp(component), file);
  }
  assert.doesNotMatch(main, /UntitledInput|reports-untitled-drawer\b/);
  const primitives = read('frontend/cadu-design-system/primitives.css');
  assert.match(primitives, /\.cadu-ds-drawer\[data-entering\]/);
  assert.match(primitives, /prefers-reduced-motion: reduce/);
});

test('site discovery runs one bounded batch per click and the explorer never lists every link', () => {
  assert.doesNotMatch(main, /while\(run\?\.status==='partial'/);
  assert.match(main, /Mapear mais páginas/);
  assert.match(main, /limite de \$\{discovery\.limit\?\.cap\|\|100\} páginas por mapeamento/);
  const catalog = read('frontend/reports-v1/FlowCatalog.jsx');
  assert.match(catalog, /pageWindow\(/);
  assert.doesNotMatch(catalog, /setShown\(count=>count\+100\)/);
  assert.match(read('frontend/reports-v1/flowCatalogModel.js'), /CATALOG_PAGE_SIZE=10/);
});

test('editor feedback messages are shown and dead editor code is gone', () => {
  assert.match(main, /<FlowToast message=\{flowLayoutNote\}/);
  for (const dead of ['associatePageCampaign', 'verifyInstall', 'visibleSitePages', 'scannedPageCount', 'discoveryLoadedId']) {
    assert.doesNotMatch(main, new RegExp(dead), dead);
  }
});
