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

test('official conversation screen wires v2 without removing legacy fallback', () => {
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
  const template = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/workspace_home_chat.html'), 'utf8');
  assert.match(home, /window\.location\.assign\(bootstrap\.urls\.newConversation\)/);
  assert.match(home, /WorkspaceAccountMenu/);
  assert.match(home, /WorkspaceNavbar/);
  assert.match(feedback, /WorkspaceAccountControl/);
  assert.match(feedback, /user\.email \|\| 'Conta e perfil'/);
  assert.match(home, /matchedProjects/);
  assert.match(home, /workspaceSolutionItems\(bootstrap\)/);
  assert.match(home, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(projects, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(brands, /onOpenResource=\{openWorkspaceDetail\}/);
  assert.match(sidebar, /Projeto —/);
  assert.match(sidebar, /Marca —/);
  assert.match(navigation, /target\.searchParams\.set\('project_ref', projectRef\)/);
  assert.match(navigation, /target\.searchParams\.set\('history', '1'\)/);
  assert.match(dock, /DockTooltip/);
  assert.match(dock, /createPortal/);
  assert.match(dock, /role="tooltip"/);
  assert.match(dock, /onReorderShortcuts/);
  assert.match(dock, /onDropShortcut/);
  assert.doesNotMatch(dock, /Organizar atalhos/);
  assert.doesNotMatch(dock, /Arquivos e documentos/);
  assert.match(dock, /VisualIdentity/);
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
  assert.match(project, /Enviar arquivo/);
  assert.match(project, /Criar primeira entrega/);
  assert.match(project, /WorkspaceAccountMenu/);
  assert.match(project, /cadu-ds-home-workarea cadu-ds-project-workarea/);
  assert.match(project, /cadu-ds-project-workarea[\s\S]*<CaduDock[\s\S]*cadu-ds-project-content/);
  assert.match(styles, /\.cadu-ds-home-content \{ width:100%; max-width:none; margin:0;/);
  assert.match(styles, /\.cadu-ds-home-content \.cadu-ds-composer,[\s\S]*width:100%; max-width:none;/);
  assert.match(styles, /\.cadu-ds-project-content \{ width:100%; max-width:none;/);
  assert.match(template, /'projectMode': True/);
  assert.match(template, /'updateContext': url_for\('cadu_workspace\.update_project_context'/);
  assert.match(template, /'uploadSource': url_for\('cadu_workspace\.upload_project_source'/);
  assert.match(template, /'legacy': url_for\('cadu_workspace\.project_detail'/);
  assert.match(route, /request\.args\.get\('legacy'\) != '1'/);
  assert.match(route, /project_detail_react\.html/);
  assert.match(entry, /bootstrap\.projectMode \? <WorkspaceProject/);
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
  assert.match(dock, /const canReorder = typeof onReorderShortcuts === 'function'/);
  assert.match(dock, /draggable=\{draggable\}/);
  assert.match(feedback, /<CaduDialog className="cadu-ds-activity-drawer"/);
  assert.doesNotMatch(selectors, /role="menuitem"/);
  assert.match(selectors, /aria-pressed/);
  assert.match(selectors, /event\.key === 'Escape'/);
  assert.match(confirm, /<CaduDialog/);
  assert.match(studio, /<CaduDialog/);
});

test('Workspace shares navbar and catalog primitives and bridges legacy Jinja pages into React chrome', () => {
  const navbar = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceNavbar.jsx'), 'utf8');
  const catalog = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceCatalog.jsx'), 'utf8');
  const legacy = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components/WorkspaceLegacyChrome.jsx'), 'utf8');
  const entry = fs.readFileSync(path.join(root, 'frontend/conversations-v2/main.jsx'), 'utf8');
  const partial = fs.readFileSync(path.join(root, 'aicentralv2/templates/cadu_workspace/_app_sidebar.html'), 'utf8');
  for (const file of ['WorkspaceHome.jsx', 'WorkspaceProject.jsx', 'WorkspaceProjects.jsx', 'WorkspaceBrands.jsx']) {
    const source = fs.readFileSync(path.join(root, 'frontend/cadu-design-system/components', file), 'utf8');
    assert.match(source, /<WorkspaceNavbar/);
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
  assert.match(account, /<WorkspaceNavbar/);
  assert.match(account, /<CaduDock/);
  assert.match(account, /function DataTable/);
  assert.match(entry, /bootstrap\.accountMode \? <WorkspaceAccount/);
  assert.match(template, /'accountMode': True/);
  assert.match(template, /cv-account-root/);
  assert.match(template, /'avatarBadge': session\.get\('cadu_avatar_badge'/);
  assert.match(styles, /#cadu-conversations-v2-root\.cv-account-root[\s\S]*?overflow-y:auto/);
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
    assert.match(source, /workspaceSolutionItems\(bootstrap\)/);
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
  assert.match(brandsTemplate, /'filterName':filter_name/);
  assert.match(projectsTemplate, /'dock':\{'items':dock_items\}/);
  assert.doesNotMatch(projectsTemplate, /'dock':\{'items':brand_items\[:3\]\+project_items\[:5\]\}/);
});

test('conversations 2.0 is one React surface with streaming, artifacts and protected work', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/conversations-v2/App.jsx'), 'utf8');
  const sidebar = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Sidebar.jsx'), 'utf8');
  const historyModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/historyModel.mjs'), 'utf8');
  const contextModel = fs.readFileSync(path.join(root, 'frontend/conversations-v2/lib/contextModel.mjs'), 'utf8');
  const artifact = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/ArtifactPane.jsx'), 'utf8');
  const conversation = fs.readFileSync(path.join(root, 'frontend/conversations-v2/components/Conversation.jsx'), 'utf8');
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
  assert.match(app, /cadu-ds-home-navbar cv-conversations-navbar/);
  assert.match(app, /\[historyOpen, setHistoryOpen\] = useState\(\(\) => !window\.matchMedia/);
  assert.match(app, /requestedHistoryOpen/);
  assert.match(app, /changeProject\(item\.projectRef, \{showHistory: true\}\)/);
  assert.match(app, /changeBrand\(item\.brandRef \|\| `studio:\$\{item\.id\}`\)/);
  assert.match(app, /loadBrandIdentity/);
  assert.match(app, /reset\(\); setHistoryOpen\(false\)/);
  assert.match(app, /if \(!conversationRef\.current\) setHistoryOpen\(false\)/);
  assert.match(sidebar, /cv-recent-sidebar/);
  assert.match(sidebar, /Conversas recentes/);
  assert.doesNotMatch(sidebar, /secondaryNav|Áreas principais|Workspace e conta/);
  assert.match(app, /let runStarted = false/);
  assert.match(app, /if \(runStarted\)/);
  assert.match(app, /kind: 'failure'/);
  assert.match(app, /expected_version/);
  assert.match(app, /\/versions\/\$\{version\}/);
  assert.match(artifact, /resource\.editor_url/);
  assert.match(artifact, /resource\.download_url/);
  assert.match(artifact, /sandbox="allow-scripts"/);
  assert.match(artifact, /Content-Security-Policy/);
  assert.doesNotMatch(artifact, /img-src data: blob: https:/);
  assert.match(conversation, /Ver resposta completa/);
  assert.match(conversation, /ResponseBlocks/);
  assert.match(conversation, /cv-conversation-title/);
  assert.match(conversation, /cv-composer-shell/);
  assert.match(conversation, /cv-thread-content/);
  assert.match(conversation, /COMPOSER_MAX_HEIGHT = 260/);
  assert.match(conversation, /data-cv-answer/);
  assert.match(conversation, /Trecho selecionado/);
  assert.match(conversation, /cv-chat-failure/);
  assert.match(conversation, /Créditos da conta/);
  assert.match(conversation, /Ver créditos/);
  assert.match(conversation, /Adicionar ao briefing/);
  assert.match(conversation, /composerContext/);
  assert.match(conversation, /Escolher modo e recursos/);
  assert.doesNotMatch(conversation, /Anexar arquivo/);
  assert.match(conversation, /Skills e integrações disponíveis/);
  assert.match(styles, /cv-attachment-chip\.is-image/);
  assert.match(app, /Solte para anexar ao chat/);
  assert.doesNotMatch(conversation, /contextLabel/);
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
  assert.match(styles, /max-height: min\(260px, 38dvh\) !important/);
  assert.match(styles, /\.cv-composer-actions[\s\S]*border-top: 0 !important/);
  assert.match(styles, /\.cv-composer-shell \{[\s\S]*overflow: visible/);
  assert.match(styles, /bottom: calc\(100% \+ 10px\)/);
  assert.match(styles, /padding-bottom: 204px !important/);
  assert.match(styles, /@media \(max-width: 1080px\)[\s\S]*\.cv-artifact-overlay/);
  assert.match(template, /cadu-conversations-v2-root/);
  assert.match(template, /cadu-conversations-v2-bootstrap/);
  assert.match(template, /react\/app\.js/);
  assert.match(template, /'solutions': \{'workspace'/);
  assert.match(template, /'solutionIcons'/);
  assert.match(template, /react\/app\.css'\) }}\?v=\d+/);
  assert.match(template, /react\/app\.js'\) }}\?v=\d+/);
  assert.doesNotMatch(template, /_app_sidebar\.html/);
  assert.doesNotMatch(template, /v2-lab\.js/);
  assert.match(base, /request\.endpoint not in \('cadu_workspace\.dashboard', 'cadu_workspace\.conversations', 'cadu_agent_v2_lab\.conversations_v2_lab'\)/);
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
  assert.equal(model.chatFailure({status: 503}).title, 'Conversas está temporariamente indisponível');
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
