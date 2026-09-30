const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const components = 'frontend/cadu-design-system/components';

test('project, brand and account pages mount the closed Workspace rail, not the retired dock', () => {
  for (const file of ['WorkspaceProject.jsx', 'WorkspaceBrand.jsx', 'WorkspaceAccount.jsx']) {
    const source = read(`${components}/${file}`);
    assert.match(source, /<WorkspaceContextSidebar[^>]*\brail\b/, file);
    assert.doesNotMatch(source, /<CaduDock/, file);
  }
});

test('brand catalog renders the Workspace sidebar instead of the retired dock', () => {
  const source = read(`${components}/WorkspaceBrands.jsx`);
  assert.match(source, /<WorkspaceContextSidebar[^>]*active="marcas"/);
  assert.doesNotMatch(source, /<CaduDock/);
});

test('the sidebar tree comes from one server payload and agency sits beside the user', () => {
  const sidebar = read(`${components}/WorkspaceContextSidebar.jsx`);
  assert.match(sidebar, /bootstrap\.sidebar/);
  assert.match(sidebar, /cadu-ds-context-sidebar__profile-text/);
  assert.doesNotMatch(sidebar, /<span>Agência<\/span>/);
  assert.doesNotMatch(sidebar, /Ver todos<\/a><\/div>\s*\{groups/);
  assert.doesNotMatch(sidebar, /cadu-ds-context-sidebar__usage/);
  assert.match(sidebar, /creditAlertVisible = usagePercent !== null && usagePercent >= 80/);
  assert.match(sidebar, /avatarBadgeSource\(bootstrap\.user\)/);
  assert.match(sidebar, /<span>Projetos<\/span>/);
  assert.match(sidebar, /Sem marca/);
  assert.doesNotMatch(read(`${components}/WorkspaceSelectors.jsx`), /closest\('\.cadu-solution-sidebar'\);/);
  for (const template of ['brands_react', 'projects_react', 'account_react', 'brand_detail_react', 'project_detail_react', 'workspace_home_chat']) {
    assert.match(read(`aicentralv2/templates/cadu_workspace/${template}.html`), /workspace_sidebar\(\)/, template);
  }
  assert.match(read('aicentralv2/cadu_workspace/routes.py'), /def _workspace_sidebar_payload\(/);
});

test('entity navigation starts open and only collapses when the person chooses it', () => {
  assert.match(read(`${components}/WorkspaceEntityPortal.jsx`), /getItem\(storageKey\) === 'collapsed'/);
});

test('project brand colors copy their code on click and the side column drops the duplicate quick access card', () => {
  const project = read(`${components}/WorkspaceProject.jsx`);
  assert.match(project, /function BrandSwatches/);
  assert.match(project, /navigator\.clipboard\.writeText/);
  assert.doesNotMatch(project, /title:'Acesso rápido'/);
});

test('detail rail geometry lives in the canonical chrome file', () => {
  const chrome = read('frontend/cadu-design-system/workspace-chrome.css');
  assert.match(chrome, /\.cadu-ds-context-sidebar\.is-rail/);
  assert.match(chrome, /grid-template-columns:64px minmax\(0,1fr\)!important/);
});

test('legacy server-rendered pages (docs, skills, brand system, observability) mount the closed rail', () => {
  const chrome = read(`${components}/WorkspaceLegacyChrome.jsx`);
  assert.match(chrome, /<WorkspaceContextSidebar[^>]*\brail\b/);
  assert.doesNotMatch(chrome, /<CaduDock/);
  assert.match(read('aicentralv2/templates/cadu_workspace/_app_sidebar.html'), /'conversations': '\/chat'/);
  const css = read('frontend/cadu-design-system/workspace-chrome.css');
  assert.match(css, /workspace-app-shell:has\(> \.cadu-workspace-legacy-chrome-root\) \{\s*grid-template-columns:64px minmax\(0,1fr\)!important;/);
});
