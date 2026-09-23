const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');

const root = path.resolve(__dirname, '../..');

test('runtime v2 translates internal events into public UI events', () => {
  const window = {};
  vm.runInNewContext(fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/runtime-v2.js'), 'utf8'), {window, TextDecoder});
  const runtime = window.CaduConversationV2;
  assert.equal(runtime.normalize({event:'run.started', conversation_id:'c', run_id:'r'}).event, 'start');
  assert.deepEqual(
    JSON.parse(JSON.stringify(runtime.normalize({event:'route.selected', route:{action:'create_brief'}}))),
    {event:'progress', message:'Preparando o briefing…'}
  );
  assert.equal(runtime.normalize({event:'tool.completed', name:'private.tool'}).message.includes('private.tool'), false);
  assert.deepEqual(
    JSON.parse(JSON.stringify(runtime.normalize({event:'answer.delta', answer:'Primeiro parágrafo'}))),
    {event:'replace', text:'Primeiro parágrafo'}
  );
  assert.equal(runtime.normalize({event:'answer.completed', response:{answer:'Pronto'}}).event, 'v2.answer');
  assert.equal(runtime.normalize({event:'artifact.created', artifact:{id:'a'}}).event, 'v2.artifact');
  assert.equal(runtime.normalize({event:'run.completed', status:'completed'}).event, 'done');
  assert.equal(runtime.normalize({event:'run.completed', status:'cancelled'}).status, 'stopped');
});

test('the old conversation entries now hand off to the React V2 screen', () => {
  const routes = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  assert.match(routes, /Compatibility entry; the customer-facing conversation surface is React V2/);
  assert.match(routes, /target = '\/chat'/);
  assert.doesNotMatch(routes, /render_template\(['"]cadu_workspace\/conversations\.html/);
});

test('Workspace home keeps a functional product switcher and resilient visual dock', () => {
  const home = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceHome.jsx'), 'utf8');
  const feedback = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceFeedback.jsx'), 'utf8');
  const dock = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/CaduDock.jsx'), 'utf8');
  const cards = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/ResumeCards.jsx'), 'utf8');
  const selectors = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceSelectors.jsx'), 'utf8');
  const navigation = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/workspaceNavigation.js'), 'utf8');
  const projects = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceProjects.jsx'), 'utf8');
  const brands = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceBrands.jsx'), 'utf8');
  const sidebar = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Sidebar.jsx'), 'utf8');
  const contextSidebar = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceContextSidebar.jsx'), 'utf8');
  const mobileChrome = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceMobileChrome.jsx'), 'utf8');
  const viewportHook = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/hooks/useUnifiedViewport.js'), 'utf8');
  const designSystemStyles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/workspace_home_chat.html'), 'utf8');
  assert.match(home, /window\.location\.assign\(bootstrap\.urls\.newConversation\)/);
  assert.match(home, /WorkspaceAccountMenu/);
  assert.match(home, /<CaduDock/);
  assert.doesNotMatch(home, /WorkspaceNavbar/);
  assert.doesNotMatch(home, /WorkspaceHomeWidgets/);
  assert.match(contextSidebar, /SidebarCollection/);
  assert.match(contextSidebar, /variant=\{item\.visualVariant\}/);
  assert.doesNotMatch(contextSidebar, /Conversas recentes|recentConversations/);
  assert.match(contextSidebar, /\.slice\(0, 5\)/);
  assert.match(contextSidebar, /\.sort\(operational\)\.slice\(0, 3\)/);
  assert.match(contextSidebar, /recentFiles.length > 0/);
  assert.doesNotMatch(contextSidebar, /Atalhos de trabalho/);
  assert.doesNotMatch(contextSidebar, /\{id: 'recent'/);
  assert.doesNotMatch(contextSidebar, /context-sidebar__footer/);
  assert.match(feedback, /WorkspaceAccountControl/);
  assert.match(feedback, /user\.email \|\| 'Conta e perfil'/);
  assert.doesNotMatch(home, /matchedProjects|Buscar projetos/);
  assert.match(home, /agencyName=\{home\.agency\?\.name\}/);
  assert.match(contextSidebar, /agencyName = ''/);
  assert.match(contextSidebar, /<strong>\{agencyName \|\| 'Cliente'\}<\/strong>/);
  assert.match(contextSidebar, /id: 'integracoes', label: 'Integrações'/);
  assert.match(contextSidebar, /MOBILE_HOME_ITEMS/);
  assert.match(contextSidebar, /max-width: 760px/);
  assert.match(contextSidebar, /cadu-ds-context-sidebar__nav--mobile/);
  assert.match(designSystemStyles, /body\.portal--workspace \.cadu-ds-dock:has[\s\S]*display:none!important/);
  assert.match(designSystemStyles, /cadu-ds-context-sidebar__toggle-mobile/);
  assert.match(mobileChrome, /role="dialog" aria-modal="true"/);
  assert.match(mobileChrome, /document\.body\.style\.overflow = 'hidden'/);
  assert.match(mobileChrome, /event\.key === 'Escape'/);
  assert.match(mobileChrome, /event\.key !== 'Tab'/);
  assert.match(mobileChrome, /event\.preventDefault\(\)/);
  assert.match(viewportHook, /window\.matchMedia\(PHONE_QUERY\)/);
  assert.match(viewportHook, /window\.visualViewport/);
  assert.match(viewportHook, /--workspace-visual-height/);
  assert.match(viewportHook, /data-workspace-keyboard-open/);
  assert.match(home, /isMobile \?\s*\(?\s*<WorkspaceMobileChrome/);
  assert.match(projects, /isMobile \? <WorkspaceMobileChrome/);
  assert.match(brands, /isMobile \? <WorkspaceMobileChrome/);
  assert.match(dock, /workspaceSolutionItems\(bootstrap\)/);
  assert.match(home, /onOpenResource=\{item => isDockResource\(item\) \? openWorkspaceResourceConversation/);
  assert.match(home, /: openWorkspaceDetail\(item\)/);
  assert.match(projects, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(brands, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(sidebar, /Projeto ativo/);
  assert.match(sidebar, /Cadu Chat/);
  assert.match(navigation, /target\.searchParams\.set\('project_ref', projectRef\)/);
  assert.match(navigation, /target\.searchParams\.set\('history', '1'\)/);
  assert.match(dock, /DockTooltip/);
  assert.match(contextSidebar, /const visibleProjects = projects\.filter/);
  assert.match(contextSidebar, /function SidebarRunningProjects/);
  assert.doesNotMatch(contextSidebar, /Projetos em andamento<\/span>\}\{links\.projects/);
  assert.match(contextSidebar, /cadu-ds-context-sidebar__project-child--root/);
  assert.doesNotMatch(contextSidebar, /project-child[^\n]*<VisualIdentity/);
  assert.match(dock, /createPortal/);
  assert.match(dock, /role="tooltip"/);
  assert.match(dock, /const resolvedAccountUrl = accountUrl \|\| bootstrap\?\.urls\?\.agency/);
  assert.match(dock, /const openUsage = \(\) =>/);
  assert.match(dock, /resolvedAccountUrl \? <a href=\{resolvedAccountUrl\}/);
  assert.match(dock, /Conta de \$\{userName\}/);
  assert.match(dock, /onReorderShortcuts/);
  assert.match(dock, /onDropShortcut/);
  assert.doesNotMatch(dock, /Organizar atalhos/);
  assert.doesNotMatch(dock, /Arquivos e documentos/);
  assert.match(dock, /VisualIdentity/);
  assert.match(dock, /variant=\{item\.visualVariant\}/);
  assert.match(cards, /VisualIdentity/);
  assert.match(cards, /cadu-ds-resume-row/);
  assert.match(cards, /typeLabel/);
  assert.doesNotMatch(cards, /Visualização indisponível/);
  assert.match(selectors, /href=\{solution\.href\}/);
  assert.match(template, /'avatar': \(perfil_contato or \{\}\)\.get\('foto_url'\)/);
  assert.match(template, /'planner': product_url\('planner', '\/'\)/);
  assert.match(template, /'skills': product_url\('skills', '\/'\)/);
  assert.match(template, /'logout': product_url\('auth', '\/logout'\)/);
});

test('project dossier reuses the React workspace shell while retaining project actions', () => {
  const project = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceProject.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/project_detail_react.html'), 'utf8');
  const route = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  assert.match(project, /cadu-ds-project-data-index/);
  assert.match(project, /Editar contexto/);
  assert.match(project, /Fontes e arquivos/);
  assert.match(project, /Criar plano de mídia/);
  assert.match(project, /WorkspaceAccountMenu/);
  assert.match(project, /cadu-ds-home-workarea cadu-ds-project-workarea/);
  assert.match(project, /dragDepth = useRef/);
  assert.match(project, /Solte para adicionar ao projeto/);
  assert.match(project, /cadu-ds-project-page-drop__card/);
  assert.match(project, /Preserve primeiro; decida depois/);
  assert.match(project, /sourceErrorMessage/);
  assert.match(project, /cadu-ds-project-brand-feature/);
  assert.match(project, /Criar e auditar marca/);
  assert.match(project, /Definir marca do projeto/);
  assert.match(project, /cadu-ds-project-workspace/);
  assert.match(project, /Continue de onde o time parou/);
  assert.match(project, /ProjectDataIndex/);
  assert.match(project, /Índice do projeto/);
  assert.match(project, /cadu-ds-project-workarea[\s\S]*<CaduDock[\s\S]*cadu-ds-project-content/);
  assert.match(styles, /\.cadu-ds-home-content \{ width:100%; max-width:none; margin:0;/);
  assert.match(styles, /\.cadu-ds-home-content \.cadu-ds-composer,[\s\S]*width:100%; max-width:none;/);
  assert.match(styles, /\.cadu-ds-project-content \{ width:100%; max-width:none;/);
  assert.match(styles, /\.cadu-ds-project-workarea,[\s\S]*display:flex; min-height:100dvh/);
  assert.match(styles, /body\.portal--workspace \.cadu-ds-project-workarea \.cadu-ds-dock,[\s\S]*position:fixed/);
  assert.match(styles, /body\.portal--workspace \.cadu-ds-project-workarea,[\s\S]*padding-left:76px/);
  assert.match(styles, /\.cadu-ds-project-page-drop__card/);
  assert.match(styles, /\.cadu-ds-project-source-section/);
  assert.match(styles, /\.cadu-ds-project-workspace/);
  assert.match(template, /'projectMode': True/);
  assert.match(template, /'updateContext': url_for\('cadu_workspace\.update_project_context'/);
  assert.match(template, /'uploadSource': url_for\('cadu_workspace\.upload_project_source'/);
  assert.match(template, /'updateBrands': url_for\('cadu_workspace\.update_project_brands'/);
  assert.match(template, /'importBrand': url_for\('cadu_workspace\.import_project_brand'/);
  assert.doesNotMatch(template, /'legacy': url_for\('cadu_workspace\.project_detail'/);
  assert.match(template, /'conversation': url_for\('cadu_workspace\.conversations', project_ref='ci:' ~ project_data\.id, history='1'\)/);
  assert.doesNotMatch(template, /'conversation':[^\n]*prompt=/);
  assert.match(route, /request\.args\.get\('legacy'\) == '1':[\s\S]*clean_project_detail/);
  assert.match(route, /project_detail_react\.html/);
  assert.match(route, /'colorPalette':/);
  assert.match(route, /'fonts':/);
  assert.match(route, /cadu_workspace_artifacts/);
  assert.match(route, /'conversations': conversation_items/);
  assert.match(route, /'artifacts': artifact_items/);
  assert.match(route, /project\['smartdocs'\] = \[\]/);
  assert.doesNotMatch(project, /smartdoc/i);
  assert.match(entry, /bootstrap\.projectMode \? <WorkspaceProject/);
  assert.equal(fs.existsSync(path.join(root, 'aicentralv2/templates/cadu_workspace/project_detail.html')), false);
  assert.equal(fs.existsSync(path.join(root, 'aicentralv2/templates/cadu_workspace/projects.html')), false);
});

test('brand dossier uses the shared React dock and design-system dialogs', () => {
  const brand = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceBrand.jsx'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/brand_detail_react.html'), 'utf8');
  const route = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  assert.equal(fs.existsSync(path.join(root, 'aicentralv2/templates/cadu_workspace/brand_detail.html')), false);
  assert.equal(fs.existsSync(path.join(root, 'aicentralv2/templates/cadu_workspace/brands.html')), false);
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  const base = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_portals/base.html'), 'utf8');
  assert.match(brand, /export function WorkspaceBrand/);
  assert.match(brand, /<CaduDock/);
  assert.match(brand, /<CaduDialog/);
  assert.match(brand, /IdentityDialog/);
  assert.match(brand, /LinkProjectsDialog/);
  assert.match(brand, /AuditDialog/);
  assert.match(brand, /insufficient_information/);
  assert.match(brand, /data_available_unverified/);
  assert.match(brand, /showDossier/);
  assert.match(brand, /Ainda não há informações suficientes sobre esta marca/);
  assert.match(entry, /bootstrap\.brandMode \? <WorkspaceBrand/);
  assert.match(entry, /bootstrap\.brandMode \|\| bootstrap\.brandsMode/);
  assert.match(brand, /add_brand_id/);
  assert.match(template, /'brandMode': True/);
  assert.match(route, /brand_detail_react\.html/);
  assert.match(route, /request\.args\.get\('legacy'\) == '1':[\s\S]*clean_brand_detail/);
  assert.match(styles, /\.cadu-ds-brand-content/);
  assert.match(styles, /\.cadu-ds-brand-dialog/);
  assert.doesNotMatch(template, /brand-audit-upload|brand-reprocess/);
  assert.doesNotMatch(base, /portal_product == 'workspace'.*brand-audit-upload/);
  assert.doesNotMatch(base, /portal_product == 'workspace'.*dock-unified/);
  assert.match(base, /portal_product != 'workspace'.*cadu-app-sidebar/);
});

test('Workspace catalogs keep the dock inside the shared work area at full width', () => {
  const projects = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceProjects.jsx'), 'utf8');
  const brands = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceBrands.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  for (const catalog of [projects, brands]) {
    assert.match(catalog, /cadu-ds-home-workarea cadu-ds-catalog-workarea/);
    assert.match(catalog, /cadu-ds-catalog-workarea[\s\S]*<CaduDock[\s\S]*<WorkspaceCatalog/);
  }
  assert.match(styles, /\.cadu-ds-brands-content\{width:100%;max-width:none;/);
});

test('new Workspace surfaces keep structural content fluid at every viewport', () => {
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  const conversations = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.match(styles, /Workspace width contract/);
  assert.match(styles, /\.cadu-ds-home-shell,[\s\S]*?width:100%;[\s\S]*?max-width:none;[\s\S]*?min-width:0;/);
  assert.match(styles, /\.cadu-ds-home-content,[\s\S]*?\.cadu-ds-project-content,[\s\S]*?\.cadu-ds-brands-content,[\s\S]*?width:100%;[\s\S]*?max-width:none;[\s\S]*?min-width:0;/);
  assert.match(styles, /\.cadu-ds-home-content \.cadu-ds-resume-collection[\s\S]*?width:100%;[\s\S]*?max-width:none;/);
  assert.match(conversations, /\.cv-home-mode \.cv-composer-shell \{ width:100%; max-width:none; min-width:0; \}/);
});

test('Cadu primitives own icons, accessible dialogs, selectors and persistent dock interactions', () => {
  const entry = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/index.js'), 'utf8');
  const dock = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/CaduDock.jsx'), 'utf8');
  const feedback = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceFeedback.jsx'), 'utf8');
  const selectors = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceSelectors.jsx'), 'utf8');
  const confirm = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ConfirmDialog.jsx'), 'utf8');
  const studio = fs.readFileSync(path.join(root, 'frontend/cadu-studio-editor/components/StudioModal.jsx'), 'utf8');
  assert.match(entry, /export \{Icon\}/);
  assert.match(entry, /export \{CaduDialog\}/);
  assert.match(entry, /WorkspaceAccountControl/);
  assert.match(entry, /WorkspaceBrands/);
  assert.match(entry, /WorkspaceProjects/);
  assert.doesNotMatch(dock, /conversations-v2\/lib\/icons/);
  assert.match(dock, /const canReorder = isControlled \|\| isWorkspaceSurface/);
  assert.match(dock, /draggable=\{draggable\}/);
  assert.match(feedback, /<CaduDialog className="cadu-ds-activity-drawer"/);
  assert.match(feedback, /const firstName = nameParts\.shift\(\)/);
  assert.match(feedback, /<strong>\{firstName\}<\/strong>/);
  assert.doesNotMatch(selectors, /role="menuitem"/);
  assert.match(selectors, /aria-pressed/);
  assert.match(selectors, /event\.key === 'Escape'/);
  assert.match(confirm, /<CaduDialog/);
  assert.match(studio, /<CaduDialog/);
});

test('Workspace shares catalog primitives and bridges legacy Jinja pages into React chrome', () => {
  const navbar = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceNavbar.jsx'), 'utf8');
  const catalog = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceCatalog.jsx'), 'utf8');
  const legacy = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceLegacyChrome.jsx'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const partial = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/_app_sidebar.html'), 'utf8');
  for (const file of ['WorkspaceHome.jsx', 'WorkspaceProject.jsx', 'WorkspaceProjects.jsx', 'WorkspaceBrands.jsx']) {
    const source = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components', file), 'utf8');
    assert.match(source, /<CaduDock/);
    assert.doesNotMatch(source, /<WorkspaceNavbar/);
  }
  for (const file of ['WorkspaceProjects.jsx', 'WorkspaceBrands.jsx']) {
    const source = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components', file), 'utf8');
    assert.match(source, /<WorkspaceCatalog/);
  }
  assert.match(navbar, /CaduSolutionSwitcher/);
  assert.match(navbar, /WorkspaceAccountControl/);
  assert.match(catalog, /CatalogFilters/);
  assert.match(legacy, /<CaduDock/);
  assert.match(legacy, /main\.dataset\.workspaceSurface = surface/);
  assert.match(entry, /bootstrap\.legacyMode \? <WorkspaceLegacyChrome/);
  assert.match(partial, /cadu-workspace-legacy-chrome-root/);
  assert.match(partial, /'surface':/);
  assert.doesNotMatch(partial, /workspace-app-sidebar/);
});

test('Workspace account routes render the new React account surface', () => {
  const account = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceAccount.jsx'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/account_react.html'), 'utf8');
  const routes = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  assert.match(account, /export function WorkspaceAccount/);
  assert.match(account, /<CaduDock/);
  assert.match(account, /function DataTable/);
  assert.match(entry, /bootstrap\.accountMode \? <WorkspaceAccount/);
  assert.match(template, /'accountMode': True/);
  assert.match(template, /cv-account-root/);
  assert.match(template, /'avatarBadge': .*session\.get\('cadu_avatar_badge'/);
  assert.match(template, /perfil_contato.*cadu_avatar_badge/);
  assert.match(template, /'integracoes': url_for\('cadu_workspace\.integrations'\)/);
  assert.match(styles, /#cadu-conversations-v2-root\.cv-account-root[\s\S]*?overflow-y:auto/);
  assert.match(styles, /#cadu-conversations-v2-root:not\(\.cv-home-root\):not\(\.cv-account-root\)/);
  assert.match(styles, /#cadu-conversations-v2-root:is\(\.cv-home-root, \.cv-account-root\)[\s\S]*?--cadu-nav-bg: #ffffff/);
  assert.match(account, /timeZone: 'UTC'/);
  assert.match(account, /person\.cadu_avatar_badge \|\| bootstrap\.user\.avatarBadge/);
  assert.match(account, /invoiceStatuses\[invoice\.status_normalized\]/);
  assert.match(routes, /cadu_workspace\/account_react\.html/);
});

test('Workspace React surfaces share one product navigation catalog', () => {
  const solutions = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/workspaceSolutions.js'), 'utf8');
  assert.match(solutions, /'workspace', 'Workspace'/);
  assert.match(solutions, /'planner', 'Planner'/);
  assert.match(solutions, /'studio', 'Studio'/);
  assert.match(solutions, /'connect', 'Reports'/);
  assert.match(solutions, /'skills', 'Skills'/);
  for (const file of ['WorkspaceHome.jsx', 'WorkspaceProject.jsx', 'WorkspaceProjects.jsx', 'WorkspaceBrands.jsx']) {
    const source = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components', file), 'utf8');
    assert.match(source, /<CaduDock/);
  }
});

test('v2 artifact surface uses optimistic version checks', () => {
  const artifact = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/artifacts-v2.js'), 'utf8');
  assert.match(artifact, /expected_version/);
  assert.match(artifact, /current_version/);
  assert.match(artifact, /Este artefato mudou em outra sessão/);
});

test('manual artifact edits block tab changes and publishing until their latest revision is saved', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  assert.match(app, /if \(artifactDirty && !\(await saveArtifact\(\)\)\) return;/);
  assert.match(app, /revision !== artifactEditRevisionRef\.current[\s\S]*?Salve a edição mais recente antes de publicar/);
  assert.match(app, /setArtifact\(current => current\?\.id === data\.artifact\.id \? \{\.\.\.current, current_version:data\.artifact\.current_version\}/);
});

test('project document continuation uses the raw artifact id exposed by the project API', () => {
  const portal = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceEntityPortal.jsx'), 'utf8');
  const routes = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  assert.match(portal, /item\.type === type/);
  assert.match(portal, /existing\?\.artifactId/);
  assert.match(routes, /'artifactId': artifact_id/);
  assert.match(routes, /'type': artifact_type/);
});

test('v2 attachments require an explicit project usage choice', () => {
  const attachments = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/attachments.js'), 'utf8');
  assert.match(attachments, /Usar nesta conversa/);
  assert.match(attachments, /Fonte do projeto/);
  assert.match(attachments, /Somente anexar ao projeto/);
  assert.match(attachments, /projects\.prepare_source_upload/);
  assert.match(attachments, /use_as_knowledge/);
});

test('Workspace catalogs expose server-backed filters and preserve personalized dock items', () => {
  const brands = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceBrands.jsx'), 'utf8');
  const projects = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceProjects.jsx'), 'utf8');
  const brandsTemplate = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/brands_react.html'), 'utf8');
  const projectsTemplate = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/projects_react.html'), 'utf8');
  assert.match(brands, /Todas.*Analisadas.*Com ativos/s);
  assert.match(projects, /Ativos.*Arquivados.*Todos/s);
  assert.match(brands, /const dockItems = bootstrap\.dock\?\.items \|\| \[\]/);
  assert.match(projects, /const dockItems = bootstrap\.dock\?\.items \|\| \[\]/);
  assert.match(brandsTemplate, /'filterName':filter_name/);
  assert.match(projectsTemplate, /'dock':\{'items':dock_items\}/);
  assert.doesNotMatch(projectsTemplate, /'dock':\{'items':brand_items\[:3\]\+project_items\[:5\]\}/);
});

test('conversations 2.0 is one React surface with streaming, artifacts and protected work', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const conversationViewport = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/hooks/useUnifiedViewport.js'), 'utf8');
  const responsiveHistory = fs.readFileSync(path.join(root, 'frontend/conversations-v2/hooks/useResponsiveHistory.js'), 'utf8');
  const dock = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/CaduDock.jsx'), 'utf8');
  const sidebar = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Sidebar.jsx'), 'utf8');
  const historyModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/historyModel.mjs'), 'utf8');
  const contextModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/contextModel.mjs'), 'utf8');
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const conversationSupport = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ConversationSupport.jsx'), 'utf8');
  const pendingInteraction = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/PendingInteraction.jsx'), 'utf8');
  const markdown = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Markdown.jsx'), 'utf8');
  const progress = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceTaskProgress.jsx'), 'utf8');
  const composer = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceChatComposer.jsx'), 'utf8');
  const responseBlocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  const executionQueue = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ExecutionQueue.jsx'), 'utf8');
  const promptAssembler = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/agent_v2/prompt_assembler.py'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations_v2_lab.html'), 'utf8');
  const base = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_portals/base.html'), 'utf8');
  assert.match(app, /restoreConversationMessages\(data\.messages, uid\)/);
  assert.match(historyModel, /metadata\.artifact_id/);
  assert.match(app, /fetchArtifact\(lastArtifact\)/);
  assert.match(app, /confirmDiscard/);
  assert.match(app, /setAttachments\(items => \{ releasePreviews\(items\); return \[\]; \}\)/);
  assert.match(app, /const uploadFiles = useCallback/);
  assert.doesNotMatch(app, /window\.confirm/);
  assert.match(app, /ConfirmDialog/);
  assert.doesNotMatch(app, /beforeunload/);
  assert.match(app, /streamEvents/);
  assert.match(app, /<CaduDock/);
  assert.match(app, /const activeProjectRef = String\(context\?\.project_ref \|\| ''\)/);
  assert.match(app, /get\('auto_send'\) === '1'/);
  assert.match(app, /active: item\.kind === 'project' && String\(item\.projectRef \|\| ''\) === activeProjectRef/);
  assert.match(dock, /active=\{item\.active\}/);
  assert.match(dock, /aria-current=\{active \? 'page' : undefined\}/);
  assert.match(app, /<CaduDock/);
  assert.doesNotMatch(app, /cadu-ds-home-navbar cv-conversations-navbar/);
  assert.match(app, /\[historyOpen, setHistoryOpen\] = useResponsiveHistory\(Boolean\(conversationId\)\)/);
  assert.match(responsiveHistory, /CONVERSATION_MOBILE_QUERY/);
  assert.match(responsiveHistory, /adaptHistory\(media\)/);
  assert.match(responsiveHistory, /media\.addEventListener\('change', adaptHistory\)/);
  assert.match(app, /requestedHistoryOpen/);
  assert.match(app, /changeProject\(projectRef, \{showHistory: true\}\)/);
  assert.match(app, /changeProject = useCallback\(async \(projectRef, \{showHistory = true\}/);
  assert.doesNotMatch(app, /loadProjectResources/);
  assert.match(app, /recentConversations\(data\.conversations, 500\)/);
  assert.match(app, /const brandRef = item\?\.brandRef \|\| \(item\?\.id \? `studio:\$\{item\.id\}` : ''\)/);
  assert.match(app, /loadBrandIdentity/);
  assert.match(app, /reset\(\);\s*setHistoryOpen\(false\)/);
  assert.match(app, /if \(!conversationRef\.current && isConversationMobile\(\)\) setHistoryOpen\(false\)/);
  assert.doesNotMatch(app, /window\.matchMedia\('\(max-width: 900px\)'\)/);
  assert.match(sidebar, /cv-recent-sidebar/);
  assert.match(sidebar, /activeProjectRef/);
  assert.match(sidebar, /leftActive/);
  assert.match(sidebar, /Chats recentes/);
  assert.match(sidebar, /projectConversations/);
  assert.match(sidebar, /Últimas 10/);
  assert.match(sidebar, /onOpenLibrary/);
  assert.doesNotMatch(sidebar, /RESOURCE_GROUPS/);
  assert.match(app, /<LibraryView/);
  assert.match(template, /'projectResources': '\/workspace\/api\/v2\/projects'/);
  assert.doesNotMatch(sidebar, /secondaryNav|Áreas principais|Workspace e conta/);
  assert.match(app, /let runStarted = false/);
  assert.match(app, /if \(runStarted\)/);
  assert.match(app, /kind: 'failure'/);
  assert.match(app, /expected_version/);
  assert.match(app, /\/versions\/\$\{version\}/);
  assert.match(artifact, /resource\.editor_url/);
  assert.match(artifact, /resource\.download_url/);
  assert.match(artifact, /sandbox="allow-scripts"/);
  assert.match(artifact, /Despublicar/);
  assert.match(app, /\/unpublish/);
  assert.match(composer, /Ditado por voz não está disponível neste navegador/);
  assert.match(artifact, /static\/css\/tailwind\/artifact\.css/);
  assert.match(artifact, /data-cadu-brand-header/);
  assert.doesNotMatch(artifact, /img-src data: blob: https:/);
  assert.doesNotMatch(conversation, /Ver resposta completa/);
  assert.match(pendingInteraction, /cv-pending-interaction/);
  assert.match(pendingInteraction, /freeform: true/);
  assert.match(pendingInteraction, /cv-pending-interaction__respond/);
  assert.match(conversation, /cv-artifact-result/);
  assert.match(conversation, /Abrir e editar/);
  assert.match(artifact, /return textArtifact/);
  assert.match(promptAssembler, /pergunta exclusivamente em/);
  assert.match(promptAssembler, /Não repita a mesma/);
  assert.match(pendingInteraction, /Adicionar referência/);
  assert.match(pendingInteraction, /Adicionar ao projeto/);
  assert.doesNotMatch(conversation, /cv-action-confirmation/);
  assert.match(app, /active\.run\.actions/);
  assert.match(artifact, /cv-link-embed__frame/);
  assert.match(artifact, /allow-popups-to-escape-sandbox/);
  assert.match(markdown, /onOpenResource\(\{url: href/);
  assert.match(executionQueue, />Orientar</);
  assert.match(executionQueue, />Excluir</);
  assert.match(executionQueue, /aria-label="Executar antes"/);
  assert.match(executionQueue, /aria-label="Executar depois"/);
  assert.match(executionQueue, /cv-execution-queue.*is-expanded/);
  assert.match(executionQueue, /aria-expanded=\{expanded\}/);
  assert.match(app, /active\.run\.status !== 'running'[\s\S]*setHistoryOpen\(false\)/);
  assert.match(app, /useConversationViewport\(\)/);
  assert.match(conversationViewport, /window\.visualViewport/);
  assert.match(conversationViewport, /--cv-visual-height/);
  assert.match(conversationViewport, /cv-keyboard-open/);
  assert.match(conversationViewport, /passive: true/);
  assert.match(styles, /cv-execution-queue:not\(\.is-expanded\) ol/);
  assert.match(styles, /span:not\(\.cv-conversation-needs-action\)/);
  assert.match(styles, /cv-pending-interaction \{ max-height:min\(34dvh,270px\)/);
  assert.match(styles, /height:var\(--cv-visual-height\)/);
  assert.doesNotMatch(styles, /width:100dvw !important/);
  assert.match(conversation, /cv-conversation-needs-action/);
  assert.match(responseBlocks, /cv-inline-decision/);
  assert.match(conversation, /ResponseBlocks/);
  assert.match(conversation, /cv-conversation-title/);
  assert.match(composer, /cv-composer-shell/);
  assert.match(conversation, /cv-thread-content/);
  assert.match(composer, /COMPOSER_MAX_HEIGHT = 120/);
  assert.match(composer, /data-composer-state=\{machine\.status\}/);
  assert.match(composer, /textarea\.current\?\.blur\(\)/);
  assert.match(composer, /cv-composer-action-slot/);
  assert.match(conversation, /data-cv-answer/);
  assert.match(conversation, /label: 'Trecho selecionado'/);
  assert.match(conversation, /cv-chat-failure/);
  assert.match(conversation, /Confian\(\?:ça\|ca\)/);
  assert.match(markdown, /words\.length <= 4 && emphasis\.length <= 44/);
  assert.match(conversation, /Créditos da conta/);
  assert.match(conversation, /Adicionar créditos no Workspace/);
  assert.doesNotMatch(conversation, /Adicionar ao briefing|Perguntar|Resumir/);
  assert.doesNotMatch(conversation, /cv-selection-tools/);
  assert.match(conversation, /closest\('\.cv-prose'\)/);
  assert.match(conversation, /composerContext/);
  assert.match(composer, /Mais recursos/);
  assert.match(composer, /Pesquisar na internet/);
  assert.match(composer, /Intensidade do agente/);
  assert.match(composer, /Ditado por voz/);
  assert.match(composer, /Destino dos anexos/);
  assert.match(composer, /Escolher modo e recursos/);
  assert.match(styles, /\.cv-attachment-chip \{[^}]*width:48px; height:48px/);
  assert.match(styles, /\.cv-assistant-answer \{ padding:0; border:0; border-radius:0; background:transparent; box-shadow:none; \}/);
  assert.match(app, /Solte o arquivo para anexar/);
  assert.match(conversationSupport, /contextLabel/);
  assert.match(conversationSupport, /Apoio à conversa/);
  assert.match(conversationSupport, /Próximos movimentos/);
  assert.match(app, /conversationPayload\(/);
  assert.match(contextModel, /execution_mode: executionMode/);
  assert.match(app, /setExecutionMode\(event\.policy\.execution_mode\)/);
  assert.match(contextModel, /selected_context/);
  assert.match(responseBlocks, /Continuar com/);
  assert.doesNotMatch(responseBlocks, /Responder com fontes/);
  assert.match(responseBlocks, /Leitura indisponível/);
  assert.match(responseBlocks, /onError=\{\(\) => setFailed\(true\)\}/);
  assert.match(responseBlocks, /Copiar referências/);
  assert.match(responseBlocks, /block\.type === 'insights'/);
  assert.match(responseBlocks, /block\.type === 'files'/);
  assert.match(responseBlocks, /block\.type === 'summary'/);
  assert.match(responseBlocks, /block\.type === 'activity' \|\| block\.type === 'progress'/);
  assert.match(responseBlocks, /block\.type === 'source' \|\| block\.type === 'sources'/);
  assert.match(responseBlocks, /block\.type === 'warning' \|\| block\.type === 'error'/);
  assert.match(artifact, /Criar versão editável/);
  assert.match(styles, /cv-artifact-open/);
  assert.match(styles, /prefers-reduced-motion/);
  assert.match(styles, /#cadu-conversations-v2-root \.cv-composer-input/);
  assert.match(styles, /--cadu-nav-bg: #0b171a/);
  assert.match(styles, /\.cv-recent-list \.cv-conversation-card \{[\s\S]*background:transparent !important/);
  assert.match(styles, /\.cv-composer-stage \{[\s\S]*background: transparent/);
  assert.match(styles, /max-height: min\(260px, 38dvh\) !important/);
  assert.match(styles, /\.cv-composer-actions[\s\S]*border-top: 0 !important/);
  assert.match(styles, /\.cv-composer-shell \{[\s\S]*overflow: visible/);
  assert.match(styles, /bottom: calc\(100% \+ 10px\)/);
  assert.match(styles, /padding-bottom: 164px !important/);
  assert.match(styles, /@media \(max-width: 1080px\)[\s\S]*\.cv-artifact-overlay/);
  assert.match(template, /cadu-conversations-v2-root/);
  assert.match(template, /cadu-conversations-v2-bootstrap/);
  assert.match(template, /react\/app\.js/);
  assert.match(template, /'solutions': \{'workspace'/);
  assert.match(template, /'solutionIcons'/);
  assert.match(template, /react\/app\.css'\) }}\?v=\{\{ cadu_workspace_asset_version \}\}/);
  assert.match(template, /react\/app\.js'\) }}\?v=\{\{ cadu_workspace_asset_version \}\}/);
  assert.doesNotMatch(template, /_app_sidebar\.html/);
  assert.doesNotMatch(template, /v2-lab\.js/);
  assert.match(base, /request\.endpoint not in \('cadu_workspace\.dashboard', 'cadu_workspace\.conversations', 'cadu_agent_v2_lab\.conversations_v2_lab', 'cadu_workspace\.account_page'\)/);
});

test('chat theme is locked dark and interaction flows avoid native browser prompts', () => {
  const main = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const provider = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/ThemeProvider.jsx'), 'utf8');
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const tokens = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/tokens.css'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.match(main, /locked=\{!workspaceMode\}/);
  assert.match(provider, /locked = false/);
  assert.match(tokens, /\[data-cadu-skin="conversations"\]\[data-cadu-theme="light"\]/);
  assert.doesNotMatch(`${artifact}\n${app}`, /window\.(?:alert|confirm|prompt)\s*\(/);
  assert.match(artifact, /cv-artifact-url-dialog/);
  assert.match(artifact, /<CaduDialog/);
  assert.match(styles, /@media\(max-width:560px\)[^\n]*cv-conversation-title[^\n]*font-size:15px!important/);
  assert.match(styles, /cv-composer-input \{ min-height:46px;[^\n]*font-size:16px !important/);
});

test('mobile workspace enters the shared chat shell without an intermediate home', () => {
  const main = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const composer = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceChatComposer.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.match(main, /bootstrap\.homeMode && window\.matchMedia\?\.\('\(max-width: 767px\)'\)/);
  assert.match(main, /const conversationBootstrap = mobileHomeEntry/);
  assert.match(main, /mobileHomeEntry \? <App bootstrap=\{conversationBootstrap\}/);
  assert.match(main, /root\.classList\.remove\('cv-home-root'\)/);
  assert.match(main, /root\.classList\.add\('cv-conversation-root'\)/);
  assert.doesNotMatch(main, /window\.location\.replace/);
  assert.match(app, /function setConversationUrl/);
  assert.match(app, /setConversationUrl\(event\.conversation_id, true\)/);
  assert.match(app, /setConversationUrl\('', true\)/);
  assert.match(composer, /cv-composer-mobile-actions/);
  assert.match(composer, /accept="image\/\*"/);
  assert.match(composer, /Disponível após conectar este recurso/);
  assert.match(styles, /@media \(max-width:767px\)[\s\S]*cv-conversation--empty \.cv-empty-state \{ display:none; \}/);
  assert.match(styles, /cv-composer-intensity__trigger \{ display:none; \}/);
  assert.match(styles, /data-keyboard-open="true"\] \.cv-conversation-header \{ height:calc\(58px/);
  assert.match(styles, /cv-conversation--empty>\.cv-composer-stage\[data-composer-state="focused"\]/);
});

test('conversation continuations preserve structured questions and server context', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const pendingInteraction = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/PendingInteraction.jsx'), 'utf8');
  const responseBlocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  const composer = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceChatComposer.jsx'), 'utf8');
  assert.doesNotMatch(conversation, /Sobre “\$\{question\}”/);
  assert.match(pendingInteraction, /type: 'question', label: 'Respondendo'/);
  assert.match(responseBlocks, /type: 'question', label: 'Respondendo'/);
  assert.match(composer, /Digite sua resposta…/);
  assert.match(composer, /composerContext\?\.type !== 'question'/);
  assert.match(app, /resolved_context/);
  assert.match(app, /Contexto sincronizado pelo servidor/);
});

test('source results use resilient favicons, clear actions and hide technical fetch errors', () => {
  const responseBlocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.doesNotMatch(responseBlocks, /Responder com fontes/);
  assert.match(responseBlocks, /Continuar com \{selectedItems\.length\} fonte/);
  assert.match(responseBlocks, /Leitura indisponível/);
  assert.match(responseBlocks, /onError=\{\(\) => setFailed\(true\)\}/);
  assert.match(responseBlocks, /Copiar referências/);
  assert.match(styles, /button\.is-primary:hover/);
});

test('conversation failures are converted into an actionable user-facing state', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/errorModel.mjs')).href);
  const credits = model.chatFailure({
    code: 'credits_insufficient', status: 409,
    message: 'Saldo insuficiente: esta execução estima 8000 tokens e há 0 disponíveis.',
    details: {required_tokens: 8000, available_tokens: 0},
  });
  assert.deepEqual(credits, {
    kind: 'credits',
    title: 'Seus créditos acabaram',
    detail: 'Esta solicitação precisa de 8.000 créditos. O saldo disponível é 0. Adicione créditos no Workspace para continuar.',
    guidance: 'Depois de adicionar créditos, envie a solicitação novamente.',
  });
  assert.equal(model.chatFailure({status: 503}).title, 'Cadu Chat está temporariamente indisponível');
});

test('conversation response model preserves execution order and explicit checklist selection', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/responseModel.mjs')).href);
  const messages = [
    {id: 'u', turnId: 'turn-1', role: 'user'},
    {id: 'a', turnId: 'turn-1', role: 'assistant', response: {answer: 'Pronto'}},
  ];
  const ordered = model.insertWorkedBeforeResult(messages, 'turn-1', {
    id: 'w', turnId: 'turn-1', role: 'assistant', kind: 'worked', seconds: 3,
  });
  assert.deepEqual(ordered.map(item => item.id), ['u', 'w', 'a']);
  assert.equal(model.checklistPrompt([]), '');
  assert.equal(model.checklistPrompt([{title: 'Validar casting', prompt: 'Revise o casting.'}]), 'Revise o casting.');
  assert.equal(model.checklistPrompt([{title: 'Casting'}, {title: 'Locação'}]), 'Revise estes itens comigo: Casting; Locação.');
  assert.equal(model.normalizeAnswerText('{"text":{"content":"Resposta limpa"}}'), 'Resposta limpa');
  assert.equal(model.normalizeAnswerText('```json\n{"text":{"content":"Resposta cercada"}}\n```'), 'Resposta cercada');
  assert.equal(model.normalizeAnswerText('"{\\"text\\":{\\"content\\":\\"Resposta dupla\\"}}"'), 'Resposta dupla');
  assert.equal(model.normalizeAnswerText('{"text":{"content":"Resposta parcial\\ncom dois parágrafos'), 'Resposta parcial\ncom dois parágrafos');
  assert.equal(model.normalizeAnswerText('prefixo {"text":{"content":"Resposta parcial segura'), 'Resposta parcial segura');
  assert.equal(model.normalizeAnswerText('{"text":{'), '');
  assert.equal(model.normalizeAnswerText('{"confidence":"high","blocks":['), '');
  assert.equal(model.normalizeAnswerText('Texto normal'), 'Texto normal');
  const streamed = 'Abertura útil. ' + 'Conteúdo completo transmitido durante o streaming. '.repeat(30);
  assert.equal(model.reconcileCompletedResponse({answer: streamed}, {answer: 'Abertura útil.'}).answer, streamed);
  assert.equal(model.reconcileCompletedResponse({answer: streamed}, {answer: 'Resumo diferente.'}).answer, streamed);
  const visibleDraft = 'Uma resposta já visível não deve desaparecer quando o evento final chegar. '.repeat(2);
  assert.equal(model.reconcileCompletedResponse({answer: visibleDraft}, {answer: 'Outra formulação final.'}).answer, visibleDraft);
  assert.equal(model.reconcileCompletedResponse({answer: streamed}, {answer: 'Abertura útil.'}, true).answer, 'Abertura útil.');
  assert.deepEqual(model.meaningfulResponseBlocks([
    {type: 'insights', items: []},
    {type: 'insights', items: [{title: 'Ponto editorial'}]},
    {type: 'questions', items: []},
    {type: 'summary', text: 'Síntese'},
  ]), [
    {type: 'insights', items: [{title: 'Ponto editorial'}]},
    {type: 'summary', text: 'Síntese'},
  ]);
});

test('completed responses never render a structured provider envelope as prose', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/responseModel.mjs')).href);
  const raw = JSON.stringify({text: {content: 'Resposta limpa para o usuário.'}, ui: {confidence: 'medium'}});
  const response = model.reconcileCompletedResponse({answer: 'Resposta limpa para o usuário.'}, {answer: raw, confidence: 'medium'});
  assert.equal(response.answer, 'Resposta limpa para o usuário.');
  assert.equal(response.confidence, 'medium');
});

test('action confirmations use the server run id and expose pending state', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const interaction = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/PendingInteraction.jsx'), 'utf8');
  const blocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  assert.match(app, /event\.action\?\.run_id \|\| event\.action\?\.runId \|\| runRef\.current/);
  assert.doesNotMatch(app, /event\.action\?\.name === 'projects\.create_link_reference'/);
  assert.match(app, /actionPending: true/);
  assert.match(app, /actionError: detail/);
  assert.match(interaction, /message\.actionPending \? presentation\.progress : presentation\.approve/);
  assert.match(interaction, /onDecision\(interaction\.message, option\.approved\)/);
  assert.match(interaction, /role=\{interaction\.error \? 'alert'/);
  assert.match(app, /options\.submit && prompt/);
  assert.match(blocks, /item\.auto_submit/);
  assert.match(blocks, /onPrompt\(item\.prompt, null, \{submit: true\}\)/);
});

test('conversation response UI never invents follow-up actions for static insights', () => {
  const blocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
  const progress = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceTaskProgress.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const interaction = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/PendingInteraction.jsx'), 'utf8');
  const markdown = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Markdown.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.doesNotMatch(blocks, /Aprofunde este ponto/);
  assert.match(blocks, /item\.prompt\s*\?/);
  assert.match(conversation, /normalizeAnswerText\(response\.answer/);
  assert.doesNotMatch(conversation, /compactAnswer/);
  assert.match(conversation, /pendingInteraction\(messages, running\)/);
  assert.match(interaction, /meaningfulResponseBlocks\(response\.blocks\)/);
  assert.doesNotMatch(conversation, /cv-message__label">Cadu/);
  assert.match(markdown, /paragraph\.join\(' '\)/);
  assert.match(markdown, /words\.length <= 4 && emphasis\.length <= 44/);
  assert.match(markdown, /heading\[1\]\.length <= 2 \? 'h2' : 'h3'/);
  assert.match(styles, /\.cv-prose \{ color:#dbe6e3; font-size:15px; font-weight:400; line-height:1\.62; max-width:68ch; \}/);
  assert.match(fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8'), /kind === 'answer\.delta'/);
  assert.doesNotMatch(progress, /FALLBACK_STEPS/);
  assert.match(progress, /cadu-ds-task-progress__spark/);
  assert.match(progress, /small aria-hidden="true"/);
  assert.doesNotMatch(progress, /Etapas concluídas/);
  assert.match(conversation, /message\.streaming && showActivity/);
  assert.match(conversation, /text\.length > 5000/);
  assert.match(conversation, /Editar em documento/);
  assert.match(conversation, /navigator\.clipboard\?\.writeText/);
  assert.match(conversation, /document\.execCommand\('copy'\)/);
  assert.match(conversation, /aria-live="polite"/);
  assert.match(conversation, /cv-answer-tools/);
  assert.match(conversation, /type:'assistant_response'/);
  assert.match(conversation, /Resposta completa para o documento/);
  assert.doesNotMatch(conversation, />C<\/span>/);
  const designStyles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  assert.match(designStyles, /#cadu-conversations-v2-root \.cadu-ds-prompt-suggestions button \{[^}]*background:#0f1d20/);
});

test('conversation attachment model preserves validation and destination rules', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/attachmentModel.mjs')).href);
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const fileDrop = fs.readFileSync(path.join(root, 'frontend/conversations-v2/hooks/useFileDrop.js'), 'utf8');
  const composer = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceChatComposer.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  assert.equal(model.MAX_ATTACHMENTS, 3);
  assert.equal(model.validateAttachment({name: 'referencia.png', size: 1200}), null);
  assert.equal(model.validateAttachment({name: 'brief.exe', size: 1200}), model.attachmentIssues.invalid);
  assert.equal(model.validateAttachment({name: 'brief.pdf', size: model.MAX_ATTACHMENT_BYTES + 1}), model.attachmentIssues.invalid);
  assert.equal(model.validateAttachment({name: 'vazio.pdf', size: 0}), model.attachmentIssues.invalid);
  const file = {name: 'brief.pdf', size: 1200, type: 'application/pdf'};
  const staged = model.createStagedAttachment(file, 'project_source');
  assert.equal(staged.name, 'brief.pdf');
  assert.equal(staged.file, file);
  assert.equal(staged.destination, 'project_source');
  assert.equal(staged.id, null);
  assert.equal(staged.source, null);
  assert.equal(staged.uploading, false);
  assert.equal(staged.error, false);
  assert.match(staged.localId, /^[0-9a-f-]{36}$/i);
  assert.deepEqual(staged.intake, {state: 'pending'});
  assert.equal(model.attachmentSubmissionMessage([{destination: 'knowledge'}]), 'Confirme os arquivos e imagens adicionados ao projeto.');
  assert.equal(model.attachmentSubmissionMessage([{destination: 'conversation'}]), 'Analise os arquivos e imagens anexados.');
  assert.match(model.attachmentSubmissionMessage([{destination: 'conversation'}, {destination: 'attachment'}]), /confirme os itens/);
  assert.match(app, /createPortal\(.+cv-drop-overlay/s);
  assert.match(app, /document\.body/);
  assert.match(app, /useFileDrop\(addFiles\)/);
  assert.match(fileDrop, /window\.addEventListener\('drop', closeFileDrop, true\)/);
  assert.match(fileDrop, /window\.removeEventListener\('drop', closeFileDrop, true\)/);
  assert.match(composer, /cv-attachment-preview/);
  assert.match(composer, /cv-attachment-list/);
  assert.match(composer, /event\.stopPropagation\(\)/);
  assert.match(app, /known\.has\(key\)/);
  assert.match(styles, /\.cv-drop-overlay \{ position:fixed; inset:0;/);
  assert.doesNotMatch(styles, /\.cv-drop-overlay:before/);
  assert.doesNotMatch(styles, /border:\s*2px dashed/);
  assert.doesNotMatch(composer, /cv-attachment-meta/);
  assert.match(styles, /\.cv-attachment-chip \{[^}]*width:48px; height:48px/);
});

test('conversation browser storage consumes pending attachments once and persists explicit context', async () => {
  const storageModel = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/storage.mjs')).href);
  const browserModel = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/browser.mjs')).href);
  const values = new Map([
    ['cadu:home-pending-attachments', JSON.stringify([{id: 'file-1'}, {name: 'invalid'}, {id: 'file-2'}])],
  ]);
  const storage = {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  assert.deepEqual(storageModel.takePendingHomeAttachments(storage).map(item => item.id), ['file-1', 'file-2']);
  assert.equal(values.has('cadu:home-pending-attachments'), false);
  assert.equal(storageModel.persistConversationContext({project_ref: 'project-1'}, storage), true);
  assert.deepEqual(JSON.parse(values.get('cadu:workspace-chat-context')), {project_ref: 'project-1'});
  assert.equal(storageModel.persistConversationContext({}, storage), true);
  assert.equal(values.has('cadu:workspace-chat-context'), false);
  assert.equal(browserModel.isConversationMobile(() => ({matches: true})), true);
  assert.equal(browserModel.isConversationMobile(() => ({matches: false})), false);

  const matchMediaDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'matchMedia');
  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    value(query) {
      assert.equal(this, globalThis);
      assert.equal(query, browserModel.CONVERSATION_MOBILE_QUERY);
      return {matches: true};
    },
  });
  try {
    assert.equal(browserModel.isConversationMobile(), true);
  } finally {
    if (matchMediaDescriptor) Object.defineProperty(globalThis, 'matchMedia', matchMediaDescriptor);
    else delete globalThis.matchMedia;
  }

  for (const key of ['sessionStorage', 'localStorage']) {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
    Object.defineProperty(globalThis, key, {
      configurable: true,
      get() { throw new DOMException('Storage blocked', 'SecurityError'); },
    });
    try {
      if (key === 'sessionStorage') assert.deepEqual(storageModel.takePendingHomeAttachments(), []);
      else assert.equal(storageModel.persistConversationContext({project_ref: 'project-1'}), false);
    } finally {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});

test('conversation history model restores messages, selected context and latest artifact', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/historyModel.mjs')).href);
  let sequence = 0;
  const restored = model.restoreConversationMessages([
    {role: 'user', content: 'Primeira', files: [{id: 'f1'}], metadata: {selected_context: {type: 'project', id: 'p1'}}},
    {role: 'assistant', content: 'Fallback', metadata: {response: {answer: '', artifact_patch: {title: 'Plano', type: 'document'}}, artifact_id: 41}},
    {role: 'user', content: 'Segunda', metadata: {selected_context: {type: 'project', id: 'p2'}}},
    {role: 'assistant', content: 'Final', metadata: {artifact_id: 42}},
  ], () => `message-${++sequence}`);
  assert.deepEqual(restored.selectedContext, {type: 'project', id: 'p2'});
  assert.equal(restored.lastArtifact, '42');
  assert.deepEqual(restored.messages.map(item => item.id), ['message-1', 'message-2', 'message-3', 'message-4']);
  assert.deepEqual(restored.messages[0].files, [{id: 'f1'}]);
  assert.equal(restored.messages[1].response.answer, 'Fallback');
  assert.deepEqual(restored.messages[1].artifact, {id: '41', title: 'Plano', type: 'document'});
  assert.deepEqual(restored.messages[3].artifact, {id: '42', title: 'artefato', type: undefined});
  assert.deepEqual(model.restoreConversationMessages(null, () => 'unused'), {messages: [], selectedContext: null, lastArtifact: ''});
  assert.deepEqual(model.recentConversations([
    {id: 1, status: 'active'},
    {id: 2, status: 'Arquivada'},
    {id: 3, status: 'ARCHIVED'},
    {id: 4},
  ]).map(item => item.id), [1, 4]);
  assert.deepEqual(model.recentConversations([{id: 1}, {id: 2}], 1).map(item => item.id), [1]);
});

test('conversation context model keeps project, brand and active artifact explicit', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/contextModel.mjs')).href);
  assert.deepEqual(model.projectContextPayload('project-1'), {project_ref: 'project-1', brand_ref: null});
  assert.deepEqual(model.projectContextPayload(''), {project_ref: null, brand_ref: null});
  assert.deepEqual(model.mergeServerEntities(
    [{ref: 'ci:project-1', name: 'Mídia Paga', previewUrl: 'blob:local-preview'}],
    [{ref: 'ci:project-1', kind: 'project', name: 'Campanhas'}],
  ), [{ref: 'ci:project-1', kind: 'project', name: 'Campanhas', previewUrl: 'blob:local-preview'}]);
  assert.deepEqual(model.conversationPayload({
    message: 'Revise', requestId: 'request-1', conversationId: 'conversation-1', providerFileIds: ['file-1'],
    executionMode: 'analysis', context: {project_ref: 'project-1', brand_ref: 'brand-1'},
    selectedContext: {type: 'selection', text: 'Trecho'}, activeArtifact: {id: 'artifact-1', type: 'document'},
  }), {
    message: 'Revise', request_id: 'request-1', conversation_id: 'conversation-1', surface: 'conversations',
    files: ['file-1'], execution_mode: 'analysis', project_ref: 'project-1', brand_ref: 'brand-1',
    selected_context: {type: 'selection', text: 'Trecho'},
    active_object: {type: 'artifact:document', id: 'artifact-1'},
  });
});

test('attachment upload service preserves progress and conversation upload contract', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/attachmentUpload.mjs')).href);
  const progress = [];
  const file = new Blob(['brief'], {type: 'text/plain'});
  const uploaded = await model.uploadAttachments({
    attachments: [{name: 'brief.txt', file, destination: 'conversation', id: null, source: null}],
    projectRef: null,
    uploadsEndpoint: '/uploads',
    requestFn: async () => { throw new Error('MCP não deveria ser chamado'); },
    fetchFn: async (url, options) => {
      assert.equal(url, '/uploads');
      assert.equal(options.method, 'POST');
      assert.equal(options.headers['X-CSRF-Token'], 'csrf-token');
      assert.equal(options.body.get('file').type, 'text/plain');
      assert.equal(options.body.get('execution_mode'), 'agentic');
      assert.equal(await options.body.get('file').text(), 'brief');
      return {ok: true, json: async () => ({file: {id: 'file-1'}})};
    },
    csrfToken: () => 'csrf-token',
    uuid: () => 'uuid-1',
    executionMode: 'agentic',
    onProgress: items => progress.push(items),
  });
  assert.equal(progress[0][0].uploading, true);
  assert.equal(uploaded[0].id, 'file-1');
  assert.equal(uploaded[0].uploading, false);
  assert.equal(progress.length > 0, true);
});

test('image artifacts hand off editing context to Studio', () => {
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const browser = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/browser.mjs'), 'utf8');
  const artifactWorkspace = fs.readFileSync(path.join(root, 'frontend/conversations-v2/hooks/useArtifactWorkspace.js'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  const editor = fs.readFileSync(path.join(root, 'frontend/cadu-studio-editor/StudioEditorApp.jsx'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations_v2_lab.html'), 'utf8');

  assert.match(template, /studioEditor.*studio\/modelagem-criativos\/imagem/);
  assert.match(app, /studioEditorUrl=\{bootstrap\.urls\?\.studioEditor\}/);
  assert.match(artifact, /source_url/);
  assert.match(artifact, /editor_mode/);
  assert.match(artifact, /Marcar uma área/);
  assert.match(artifact, /Remover fundo/);
  assert.match(artifact, /Otimizar para web/);
  assert.match(artifact, /Analisar e organizar arquivo/);
  assert.match(artifact, /Analisando imagem…/);
  assert.match(app, /\/workspace\/api\/v2\/images\/organize/);
  assert.match(app, /Imagem organizada/);
  assert.match(artifact, /function imageFileName/);
  assert.match(artifact, /aria-label=\{type === 'image' \? 'Nome do arquivo' : 'Título do documento'\}/);
  assert.match(artifact, /cv-image-metadata/);
  assert.match(artifact, /Dimensões/);
  assert.match(artifact, /Resolução/);
  assert.match(artifact, /type !== 'image'/);
  assert.match(styles, /justify-content:center/);
  assert.match(styles, /align-items:baseline/);
  assert.doesNotMatch(artifact, /cv-image-artifact__bar/);
  assert.match(editor, /query\.get\('source_url'\)/);
  assert.match(editor, /initialQuery\.get\('instruction'\)/);
  assert.match(editor, /initialQuery\.get\('editor_mode'\)/);
  assert.match(styles, /\.cv-image-metadata \{/);
  assert.doesNotMatch(styles, /\.cv-image-artifact__bar/);
  assert.match(app, /useArtifactWorkspace\(artifact\)/);
  assert.match(artifactWorkspace, /writeCookie\(ARTIFACT_SIDE_COOKIE, next\)/);
  assert.match(artifactWorkspace, /writeCookie\(`\$\{ARTIFACT_SIDE_COOKIE\}:\$\{artifact\.id\}`, next\)/);
  assert.match(artifactWorkspace, /setArtifactTabs/);
  assert.match(browser, /SameSite=Lax/);
  assert.match(browser, /navigator\.clipboard\?\.writeText/);
  assert.match(app, /if \(lastArtifact\) await fetchArtifact\(lastArtifact\)/);
  assert.match(conversation, /stickToLatest/);
  assert.match(conversation, /element\.scrollTop = element\.scrollHeight/);
  assert.match(conversation, /new ResizeObserver/);
  assert.match(conversation, /onWheelCapture=\{handleScrollIntent\}/);
  assert.match(conversation, /onTouchStart=\{stopFollowingLatest\}/);
  assert.match(conversation, /\['ArrowUp', 'PageUp', 'Home'\]/);
  assert.match(styles, /\.cv-conversation-support__meta > div \{ min-width:0; \}/);
  assert.match(styles, /\.cv-conversation-support__request \{[^}]*border-left:2px/);
  assert.match(styles, /\.cv-conversation-support__next button \{[^}]*border:0;[^}]*background:transparent/);
  assert.match(app, /pending:\$\{turnId\}/);
  assert.match(app, /tabs=\{artifactTabs\}/);
  assert.match(app, /onOpenBrand=\{openDockBrand\}/);
  assert.match(app, /onOpenResource=\{openDockItem\}/);
  assert.match(app, /changeProject\(projectRef, \{showHistory: true\}\)/);
  assert.match(app, /changeBrand\(brandRef\)/);
  assert.doesNotMatch(app, /openConversationDockDetail/);
  assert.match(artifact, /cv-artifact-tabs/);
  assert.match(artifact, /compactArtifactTitle/);
  assert.match(artifact, /artifactTabIcon/);
  assert.match(artifact, /onContextMenu/);
  assert.match(artifact, /Fechar outras abas/);
  assert.match(artifact, /Abrir no navegador/);
  assert.match(artifact, /Copiar link/);
  assert.match(artifact, /Link publicado/);
  assert.match(app, /onCloseOtherTabs/);
  assert.match(app, /onCloseAllTabs/);
  assert.match(styles, /\.cv-artifact-tab-menu/);
  assert.match(artifact, /Preparando o artefato/);
  assert.match(styles, /\.cv-artifact-loading/);
});

test('document editor never exposes a provider envelope as editable prose', () => {
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  assert.match(artifact, /decoded\?\.text\?\.content \|\| decoded\?\.answer/);
  assert.match(artifact, /An incomplete protocol envelope must not become editable content/);
  assert.match(artifact, /artifact_patch/);
});

test('meeting summaries use a dedicated semantic React editor', () => {
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');

  assert.match(artifact, /function MeetingSummaryArtifact/);
  assert.match(artifact, /type === 'meeting_summary' \|\| type === 'meeting_agenda'/);
  assert.match(artifact, /Registro da reunião/);
  assert.match(artifact, /meetingSectionAliases/);
  assert.match(styles, /\.cv-meeting-summary__sections/);
  assert.match(styles, /\.cv-meeting-summary__section\.is-decisoes/);
});

test('mobile workspace surfaces share the visual viewport and keep chat styling isolated', () => {
  const viewport = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/hooks/useUnifiedViewport.js'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  const conversationStyles = fs.readFileSync(path.join(root, 'frontend/conversations-v2/styles.css'), 'utf8');
  const layoutFixes = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/react/chat-layout-fixes.css'), 'utf8');

  assert.match(viewport, /--workspace-visual-height/);
  assert.match(viewport, /viewport\?\.addEventListener\('resize'/);
  assert.match(styles, /One mobile contract for authenticated Workspace surfaces/);
  assert.match(conversationStyles, /cv-conversation--empty \.cv-empty-state/);
  assert.match(layoutFixes, /#cadu-conversations-v2-root\.cv-home-root \.cadu-ds-home-workarea/);
  assert.doesNotMatch(layoutFixes, /#cadu-conversations-v2-root \.cadu-ds-home-workarea \{/);
});
