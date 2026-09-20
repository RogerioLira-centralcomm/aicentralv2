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
  assert.equal(runtime.normalize({event:'answer.completed', response:{answer:'Pronto'}}).event, 'v2.answer');
  assert.equal(runtime.normalize({event:'artifact.created', artifact:{id:'a'}}).event, 'v2.artifact');
  assert.equal(runtime.normalize({event:'run.completed', status:'completed'}).event, 'done');
  assert.equal(runtime.normalize({event:'run.completed', status:'cancelled'}).status, 'stopped');
});

test('legacy conversation screen stays wired only as a compatibility fallback', () => {
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/conversations.html'), 'utf8');
  const chat = fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_workspace/conversations/chat.js'), 'utf8');
  assert.match(template, /data-runtime=/);
  assert.match(template, /data-v2-endpoint=/);
  assert.match(template, /runtime-v2\.js/);
  assert.match(template, /artifacts-v2\.js/);
  assert.match(chat, /CaduConversationV2\.events/);
  assert.match(chat, /CaduV2Artifacts/);
  assert.match(chat, /\/familia\/api\/conversations\/send/);
});

test('the old conversation entries now hand off to the React V2 screen', () => {
  const routes = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  assert.match(routes, /Compatibility entry; the customer-facing conversation surface is React V2/);
  assert.match(routes, /target = '\/workspace\/conversas-v2-lab'/);
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
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/workspace_home_chat.html'), 'utf8');
  assert.match(home, /window\.location\.assign\(bootstrap\.urls\.newConversation\)/);
  assert.match(home, /WorkspaceAccountMenu/);
  assert.match(home, /<CaduDock/);
  assert.doesNotMatch(home, /WorkspaceNavbar/);
  assert.doesNotMatch(home, /WorkspaceHomeWidgets/);
  assert.match(contextSidebar, /SidebarCollection/);
  assert.match(contextSidebar, /variant=\{item\.visualVariant\}/);
  assert.match(contextSidebar, /recentConversations = useMemo/);
  assert.match(contextSidebar, /recentConversations[\s\S]*?slice\(0, 5\)/);
  assert.match(contextSidebar, /recentFiles.length > 0/);
  assert.doesNotMatch(contextSidebar, /Atalhos de trabalho/);
  assert.doesNotMatch(contextSidebar, /\{id: 'recent'/);
  assert.doesNotMatch(contextSidebar, /context-sidebar__footer/);
  assert.match(feedback, /WorkspaceAccountControl/);
  assert.match(feedback, /user\.email \|\| 'Conta e perfil'/);
  assert.doesNotMatch(home, /matchedProjects|ProjectSelector|Buscar projetos/);
  assert.match(home, /agencyName=\{home\.agency\?\.name\}/);
  assert.match(contextSidebar, /agencyName = ''/);
  assert.match(contextSidebar, /<strong>\{agencyName \|\| 'Cliente'\}<\/strong>/);
  assert.match(contextSidebar, /id: 'integracoes', label: 'Integrações'/);
  assert.match(dock, /workspaceSolutionItems\(bootstrap\)/);
  assert.match(home, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(projects, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(brands, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(sidebar, /Projeto ativo/);
  assert.match(sidebar, /Cadu Chat/);
  assert.match(navigation, /target\.searchParams\.set\('project_ref', projectRef\)/);
  assert.match(navigation, /target\.searchParams\.set\('history', '1'\)/);
  assert.match(dock, /DockTooltip/);
  assert.match(dock, /createPortal/);
  assert.match(dock, /role="tooltip"/);
  assert.match(dock, /const resolvedAccountUrl = accountUrl;/);
  assert.match(dock, /const openUsage = \(\) =>/);
  assert.match(dock, /resolvedAccountUrl \? <a href=\{resolvedAccountUrl\}/);
  assert.match(dock, /Abrir uso e conta de \$\{userName\}/);
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
  assert.match(project, /cadu-ds-project-library/);
  assert.match(project, /Editar contexto/);
  assert.match(project, /Fontes e arquivos/);
  assert.match(project, /Criar primeira entrega/);
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
  assert.match(project, /cadu-ds-project-continuity/);
  assert.match(project, /Conversas do projeto/);
  assert.match(project, /Artefatos salvos/);
  assert.match(project, /Ver todas as/);
  assert.match(project, /Ver todos os/);
  assert.match(project, /cadu-ds-project-library-summary/);
  assert.match(project, /cadu-ds-project-workarea[\s\S]*<CaduDock[\s\S]*cadu-ds-project-content/);
  assert.match(styles, /\.cadu-ds-home-content \{ width:100%; max-width:none; margin:0;/);
  assert.match(styles, /\.cadu-ds-home-content \.cadu-ds-composer,[\s\S]*width:100%; max-width:none;/);
  assert.match(styles, /\.cadu-ds-project-content \{ width:100%; max-width:none;/);
  assert.match(styles, /\.cadu-ds-project-workarea,[\s\S]*display:flex; min-height:100dvh/);
  assert.match(styles, /body\.portal--workspace \.cadu-ds-project-workarea \.cadu-ds-dock,[\s\S]*position:fixed/);
  assert.match(styles, /body\.portal--workspace \.cadu-ds-project-workarea,[\s\S]*padding-left:76px/);
  assert.match(styles, /\.cadu-ds-project-page-drop__card/);
  assert.match(styles, /\.cadu-ds-project-source-section/);
  assert.match(styles, /\.cadu-ds-project-continuity__columns/);
  assert.match(template, /'projectMode': True/);
  assert.match(template, /'updateContext': url_for\('cadu_workspace\.update_project_context'/);
  assert.match(template, /'uploadSource': url_for\('cadu_workspace\.upload_project_source'/);
  assert.match(template, /'updateBrands': url_for\('cadu_workspace\.update_project_brands'/);
  assert.match(template, /'importBrand': url_for\('cadu_workspace\.import_project_brand'/);
  assert.match(template, /'legacy': url_for\('cadu_workspace\.project_detail'/);
  assert.match(template, /'conversation': url_for\('cadu_workspace\.conversations', project_ref='ci:' ~ project_data\.id, history='1'\)/);
  assert.doesNotMatch(template, /'conversation':[^\n]*prompt=/);
  assert.match(route, /request\.args\.get\('legacy'\) != '1'/);
  assert.match(route, /project_detail_react\.html/);
  assert.match(route, /'colorPalette':/);
  assert.match(route, /'fonts':/);
  assert.match(route, /cadu_workspace_artifacts/);
  assert.match(route, /'conversations': conversation_items/);
  assert.match(route, /'artifacts': artifact_items/);
  assert.match(route, /project\['smartdocs'\] = \[\]/);
  assert.doesNotMatch(project, /smartdoc/i);
  assert.match(entry, /bootstrap\.projectMode \? <WorkspaceProject/);
});

test('brand dossier uses the shared React dock and design-system dialogs', () => {
  const brand = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceBrand.jsx'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/brand_detail_react.html'), 'utf8');
  const route = fs.readFileSync(path.join(root, 'aicentralv2/cadu_workspace/routes.py'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/styles.css'), 'utf8');
  assert.match(brand, /export function WorkspaceBrand/);
  assert.match(brand, /<CaduDock/);
  assert.match(brand, /<CaduDialog/);
  assert.match(brand, /IdentityDialog/);
  assert.match(brand, /LinkProjectsDialog/);
  assert.match(brand, /AuditDialog/);
  assert.match(entry, /bootstrap\.brandMode \? <WorkspaceBrand/);
  assert.match(entry, /bootstrap\.brandMode \|\| bootstrap\.brandsMode/);
  assert.match(brand, /add_brand_id/);
  assert.match(template, /'brandMode': True/);
  assert.match(route, /brand_detail_react\.html/);
  assert.match(styles, /\.cadu-ds-brand-content/);
  assert.match(styles, /\.cadu-ds-brand-dialog/);
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
  assert.match(brands, /bootstrap\.dock\?\.items\?\.length \? bootstrap\.dock\.items : \[\.\.\.\(bootstrap\.brands \|\| \[\]\), \.\.\.\(bootstrap\.projects \|\| \[\]\)\]/);
  assert.match(projects, /bootstrap\.dock\?\.items\?\.length \? bootstrap\.dock\.items : \[\.\.\.\(bootstrap\.brands \|\| \[\]\), \.\.\.\(bootstrap\.projects \|\| \[\]\)\]/);
  assert.match(brandsTemplate, /'filterName':filter_name/);
  assert.match(projectsTemplate, /'dock':\{'items':dock_items\}/);
  assert.doesNotMatch(projectsTemplate, /'dock':\{'items':brand_items\[:3\]\+project_items\[:5\]\}/);
});

test('conversations 2.0 is one React surface with streaming, artifacts and protected work', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const dock = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/CaduDock.jsx'), 'utf8');
  const sidebar = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Sidebar.jsx'), 'utf8');
  const historyModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/historyModel.mjs'), 'utf8');
  const contextModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/contextModel.mjs'), 'utf8');
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
  const composer = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceChatComposer.jsx'), 'utf8');
  const responseBlocks = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ResponseBlocks.jsx'), 'utf8');
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
  assert.match(app, /beforeunload/);
  assert.match(app, /streamEvents/);
  assert.match(app, /<CaduDock/);
  assert.match(app, /const activeProjectRef = String\(context\?\.project_ref \|\| ''\)/);
  assert.match(app, /get\('auto_send'\) === '1'/);
  assert.match(app, /active: item\.kind === 'project' && String\(item\.projectRef \|\| ''\) === activeProjectRef/);
  assert.match(dock, /active=\{item\.active\}/);
  assert.match(dock, /aria-current=\{active \? 'page' : undefined\}/);
  assert.match(app, /<CaduDock/);
  assert.doesNotMatch(app, /cadu-ds-home-navbar cv-conversations-navbar/);
  assert.match(app, /\[historyOpen, setHistoryOpen\] = useState\(\(\) => !window\.matchMedia/);
  assert.match(app, /requestedHistoryOpen/);
  assert.match(app, /changeProject\(item\.projectRef, \{showHistory: true\}\)/);
  assert.match(app, /changeProject = useCallback\(async \(projectRef, \{showHistory = true\}/);
  assert.doesNotMatch(app, /loadProjectResources/);
  assert.match(app, /recentConversations\(data\.conversations, 500\)/);
  assert.match(app, /changeBrand\(item\.brandRef \|\| `studio:\$\{item\.id\}`\)/);
  assert.match(app, /loadBrandIdentity/);
  assert.match(app, /reset\(\);\s*setHistoryOpen\(false\)/);
  assert.match(app, /if \(!conversationRef\.current && window\.matchMedia\('\(max-width: 900px\)'\)\.matches\) setHistoryOpen\(false\)/);
  assert.match(sidebar, /cv-recent-sidebar/);
  assert.match(sidebar, /activeProjectRef/);
  assert.match(sidebar, /leftActive/);
  assert.match(sidebar, /Chats recentes/);
  assert.match(sidebar, /Conversas do projeto/);
  assert.match(sidebar, /Últimas 5/);
  assert.match(sidebar, /Biblioteca do projeto/);
  assert.match(sidebar, /RESOURCE_GROUPS/);
  assert.match(sidebar, /projectResourcesEndpoint/);
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
  assert.match(conversation, /Ver resposta completa/);
  assert.match(conversation, /ResponseBlocks/);
  assert.match(conversation, /cv-conversation-title/);
  assert.match(composer, /cv-composer-shell/);
  assert.match(conversation, /cv-thread-content/);
  assert.match(composer, /COMPOSER_MAX_HEIGHT = 260/);
  assert.match(conversation, /data-cv-answer/);
  assert.match(conversation, /Trecho selecionado/);
  assert.match(conversation, /cv-chat-failure/);
  assert.match(conversation, /Créditos da conta/);
  assert.match(conversation, /Ver créditos/);
  assert.match(conversation, /Adicionar ao briefing/);
  assert.match(conversation, /composerContext/);
  assert.match(composer, /Mais recursos/);
  assert.match(composer, /Pesquisar na internet/);
  assert.match(composer, /Intensidade do agente/);
  assert.match(composer, /Ditado por voz/);
  assert.match(composer, /Anexar arquivo/);
  assert.match(composer, /Skills e integrações disponíveis/);
  assert.match(styles, /cv-attachment-chip\.is-image/);
  assert.match(app, /Solte para anexar ao chat/);
  assert.match(conversation, /contextLabel/);
  assert.match(conversation, /Apoio à conversa/);
  assert.match(conversation, /Próximos movimentos/);
  assert.match(app, /conversationPayload\(/);
  assert.match(contextModel, /execution_mode: executionMode/);
  assert.match(app, /setExecutionMode\(event\.policy\.execution_mode\)/);
  assert.match(contextModel, /selected_context/);
  assert.match(responseBlocks, /Usar esta opção/);
  assert.match(responseBlocks, /Continuar com/);
  assert.match(responseBlocks, /block\.type === 'insights'/);
  assert.match(responseBlocks, /block\.type === 'files'/);
  assert.match(responseBlocks, /block\.type === 'summary'/);
  assert.match(responseBlocks, /block\.type === 'activity' \|\| block\.type === 'progress'/);
  assert.match(responseBlocks, /block\.type === 'source' \|\| block\.type === 'sources'/);
  assert.match(responseBlocks, /Próximas decisões/);
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

test('conversation failures are converted into an actionable user-facing state', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/errorModel.mjs')).href);
  const credits = model.chatFailure({
    code: 'credits_insufficient', status: 409,
    message: 'Saldo insuficiente: esta execução estima 8000 tokens e há 0 disponíveis.',
    details: {required_tokens: 8000, available_tokens: 0},
  });
  assert.deepEqual(credits, {
    kind: 'credits',
    title: 'Créditos insuficientes',
    detail: 'Esta solicitação precisa de 8.000 créditos. O saldo disponível é 0.',
    guidance: 'Nenhum crédito foi usado. Adicione créditos à conta antes de enviar novamente.',
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
});

test('conversation attachment model preserves validation and destination rules', async () => {
  const model = await import(pathToFileURL(path.join(root, 'frontend/conversations-v2/lib/attachmentModel.mjs')).href);
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
      assert.equal(await options.body.get('file').text(), 'brief');
      return {ok: true, json: async () => ({file: {id: 'file-1'}})};
    },
    csrfToken: () => 'csrf-token',
    uuid: () => 'uuid-1',
    onProgress: items => progress.push(items),
  });
  assert.equal(progress[0][0].uploading, true);
  assert.equal(uploaded[0].id, 'file-1');
  assert.equal(uploaded[0].uploading, false);
});
