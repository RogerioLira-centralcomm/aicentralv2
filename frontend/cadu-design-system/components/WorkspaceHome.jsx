import React, {useCallback, useMemo, useState} from 'react';
import './WorkspaceHome.css';
import {CaduDock} from './CaduDock';
import {WorkspaceChatComposer} from './WorkspaceChatComposer';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {ShortcutManagerDialog, UndoToast, WorkspaceAccountMenu} from './WorkspaceFeedback';
import {csrf, request} from '../../conversations-v2/lib/api';
import {attachmentIssues, createStagedAttachment, MAX_ATTACHMENTS, validateAttachment} from '../../conversations-v2/lib/attachmentModel.mjs';
import {uploadAttachments} from '../../conversations-v2/lib/attachmentUpload.mjs';
import {openWorkspaceDetail, openWorkspaceResourceConversation} from '../workspaceNavigation';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';
import {completeDockOrder} from '../dockPlacement.mjs';
import {markProjectUsed} from '../projectOptions.mjs';

function withQuery(url, values) {
  const target = new URL(url, window.location.origin);
  Object.entries(values).forEach(([key, value]) => { if (value) target.searchParams.set(key, value); });
  return target.pathname + target.search;
}

const isDockResource = item => Boolean(item?.resourceRef) || item?.kind === 'resource';

function HomeCreditAlert({creditAlert}) {
  if (!creditAlert?.visible) return null;
  return <section className={`cadu-ds-home-credit-alert ${creditAlert.isFree ? 'is-free' : 'is-low'}`} aria-live="polite" aria-label="Capacidade de créditos">
    <div className="cadu-ds-home-credit-alert__copy">
      <strong>{creditAlert.title}</strong>
      <p>{creditAlert.description}</p>
    </div>
    <a className="cadu-ds-home-credit-alert__action" href={creditAlert.href}>{creditAlert.cta}<span aria-hidden="true">↗</span></a>
  </section>;
}

const HOME_TITLES = [
  'Por onde começamos?',
  'O que merece atenção hoje?',
  'Qual é o próximo passo?',
  'Vamos tirar isso do papel?',
  'O que você quer resolver?',
  'Que ideia vamos organizar?',
  'Qual decisão está na mesa?',
  'Vamos dar forma ao trabalho?',
  'Onde faz sentido começar?',
  'Qual é a prioridade agora?',
  'Vamos transformar contexto em ação?',
  'O que precisa avançar?',
  'Qual frente você quer destravar?',
  'Que caminho seguimos hoje?',
  'O que podemos simplificar?',
  'Vamos encontrar o fio da meada?',
  'Qual pergunta abre o trabalho?',
  'Por onde seguimos?',
  'O que está pedindo clareza?',
  'Qual projeto chama agora?',
  'Vamos organizar o próximo movimento?',
  'O que você quer colocar em ordem?',
  'Qual tarefa merece foco?',
  'Vamos construir a próxima versão?',
  'O que falta para avançar?',
  'Qual contexto vamos explorar?',
  'Vamos começar pelo que importa?',
  'O que podemos decidir juntos?',
  'Que trabalho começa agora?',
  'Qual é o seu próximo movimento?',
];

export function WorkspaceHome({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const home = bootstrap.home || {};
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get('prompt') || '');
  const [homeTitle] = useState(() => HOME_TITLES[Math.floor(Math.random() * HOME_TITLES.length)]);
  const [projectRef, setProjectRef] = useState('');
  const [shortcutsOpen, setShortcutsOpen] = useState(() => window.location.hash === '#atalhos');
  const [accountOpen, setAccountOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [executionMode, setExecutionMode] = useState('analysis');
  const [brandRef, setBrandRef] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [attachmentDestination, setAttachmentDestination] = useState('conversation');
  const projects = useMemo(() => [...(home.projects || [])].sort((left, right) => {
    const leftDate = Date.parse(left.updatedAt || left.updated_at || '') || 0;
    const rightDate = Date.parse(right.updatedAt || right.updated_at || '') || 0;
    return rightDate - leftDate;
  }), [home.projects]);
  const brands = home.brands || [];
  const catalogBrands = home.catalogBrands || brands;
  const [dockItems, setDockItems] = useState(home.dock?.items || []);
  const sidebarBrands = (catalogBrands.length ? catalogBrands : brands).slice().sort((left, right) => {
    const leftDate = Date.parse(left.updatedAt || left.updated_at || left.createdAt || left.created_at || '') || 0;
    const rightDate = Date.parse(right.updatedAt || right.updated_at || right.createdAt || right.created_at || '') || 0;
    return rightDate - leftDate;
  });
  const composerContext = null;
  const releasePreviews = useCallback(items => items.forEach(item => { if (item.previewUrl) URL.revokeObjectURL(item.previewUrl); }), []);
  const classifyAttachment = useCallback(async file => {
    try {
      const data = await request('/workspace/mcp', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({jsonrpc: '2.0', id: crypto.randomUUID(), method: 'tools/call', params: {name: 'projects.classify_intake', surface: 'conversations', arguments: {filename: file.name, mime_type: file.type || ''}}})});
      return data.result?.structuredContent || {state: 'unavailable'};
    } catch (_) { return {state: 'unavailable'}; }
  }, []);
  const addFiles = useCallback(async files => {
    const staged = [];
    setAttachments(current => {
      const next = [...current];
      for (const file of files) {
        if (next.length >= MAX_ATTACHMENTS) { setToast(attachmentIssues.limit.detail); break; }
        const issue = validateAttachment(file);
        if (issue) { setToast(issue.detail); continue; }
        const previewUrl = file.type?.startsWith('image/') ? URL.createObjectURL(file) : '';
        const item = createStagedAttachment(file, attachmentDestination, previewUrl);
        staged.push(item); next.push(item);
      }
      return next;
    });
    await Promise.all(staged.map(async item => {
      const intake = await classifyAttachment(item.file);
      setAttachments(current => current.map(candidate => candidate.localId === item.localId ? {...candidate, intake} : candidate));
    }));
  }, [attachmentDestination, classifyAttachment]);
  const removeAttachment = useCallback(index => setAttachments(items => { const removed = items[index]; if (removed) releasePreviews([removed]); return items.filter((_, itemIndex) => itemIndex !== index); }), [releasePreviews]);
  const setAttachmentPurpose = useCallback((index, destination) => setAttachments(items => items.map((item, itemIndex) => itemIndex === index ? {...item, destination} : item)), []);
  const submit = async (requestedInput = value, {skipAttachments = false} = {}) => {
    const prompt = String(requestedInput || '').trim();
    if (!prompt) return;
    try {
      let resolvedExecutionMode = executionMode;
      if (!skipAttachments && attachments.some(item => item.destination === 'conversation')) {
        const routeEndpoint = bootstrap.endpoints.route || String(bootstrap.endpoints.uploads || '').replace(/\/uploads$/, '/route');
        const preview = await request(routeEndpoint, {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({message: prompt, execution_mode: executionMode, project_ref: projectRef || null, brand_ref: brandRef || null}),
        });
        resolvedExecutionMode = preview.execution_mode || executionMode;
      }
      const staged = !skipAttachments && attachments.length ? await uploadAttachments({attachments, projectRef, uploadsEndpoint: bootstrap.endpoints.uploads, requestFn: request, fetchFn: fetch, csrfToken: csrf, uuid: () => crypto.randomUUID(), onProgress: setAttachments, executionMode: resolvedExecutionMode}) : [];
      const pending = staged.filter(item => item.id).map(item => ({id: item.id, name: item.name}));
      if (pending.length) sessionStorage.setItem('cadu:home-pending-attachments', JSON.stringify(pending));
      if (!skipAttachments) setAttachments(items => { releasePreviews(items); return []; });
      window.location.assign(withQuery(bootstrap.urls.newConversation, {prompt, project_ref: projectRef, brand_ref: brandRef, context_mode: projectRef || brandRef ? 'bound' : 'free', mode: resolvedExecutionMode, auto_send: '1'}));
    } catch (error) { setToast(error.message || 'Não foi possível preparar os anexos.'); }
  };
  const dropContext = payload => {
    if (payload.projectRef || payload.type === 'project') { const ref = payload.projectRef || payload.id; markProjectUsed(ref); setProjectRef(ref); setBrandRef(''); setAttachmentDestination('conversation'); }
    if (payload.type === 'brand') { setBrandRef(payload.brandRef || (payload.id ? `studio:${payload.id}` : '')); setProjectRef(''); setAttachmentDestination('conversation'); }
  };
  // Automatic items remain limited to brands with a visible logo. Projects
  // are available in the manager because an explicit user choice may use the
  // project's initials when there is no linked brand mark.
  const shortcutCandidates = [...(home.brands || []), ...projects, ...(home.resources || []).filter(isDockResource)]
    .map(item => item.kind === 'project' ? {...item, previewUrl: item.dockLogoUrl, title: item.title || item.name} : {...item, title: item.title || item.name});
  const explicitDockItems = dockItems.filter(item => item.shortcutId);
  const managerItems = [
    ...explicitDockItems,
    ...shortcutCandidates.filter(item => !explicitDockItems.some(dockItem => dockItem.id === item.id)),
  ].map(item => ({...item, pinned: Boolean(item.shortcutId)}));
  const createShortcut = async item => {
    const kind = item.kind === 'brand' ? 'brand' : isDockResource(item) ? 'resource' : 'project';
    const targetRef = kind === 'brand' ? item.id : isDockResource(item) ? item.resourceRef || item.id : item.projectRef || item.id;
    const response = await request(bootstrap.endpoints.dockShortcuts, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({shortcut_type: kind, target_ref: targetRef, project_ref: item.projectRef || null, brand_ref: item.brandRef || null})});
    return {...item, shortcutId: response.shortcut.id, pinned: true};
  };
  const persistShortcut = async item => {
    const next = await createShortcut(item);
    setDockItems(current => [...current.filter(currentItem => currentItem.shortcutId && currentItem.id !== item.id), next]);
  };
  const addDroppedShortcut = async payload => {
    const candidate = payload.type === 'resource' || payload.resourceRef
      ? {...payload, kind: 'resource', id: payload.id || `resource:${payload.resourceRef}`, title: payload.title || 'Recurso'}
      : payload.type === 'brand'
      ? (home.brands || []).find(item => item.id === payload.id)
      : projects.find(item => item.id === (payload.projectRef || payload.id));
    if (!candidate || !['brand', 'project', 'resource'].includes(candidate.kind)) {
      setToast('Apenas marcas, projetos e recursos podem ser fixados na dock.');
      return;
    }
    if (dockItems.some(item => item.id === candidate.id && item.shortcutId)) {
      setToast(`${candidate.title || candidate.name} já está nos seus atalhos.`);
      return;
    }
    try {
      await persistShortcut(candidate);
      setToast(`${candidate.title || candidate.name} fixado nos seus atalhos.`);
    } catch (error) { setToast(error.message || 'Não foi possível fixar este atalho.'); }
  };
  const toggleShortcut = async item => {
    try {
      const current = dockItems.find(dockItem => dockItem.id === item.id || dockItem.shortcutId === item.shortcutId);
      if (current?.shortcutId) {
        await request(`${bootstrap.endpoints.dockShortcuts}/${current.shortcutId}`, {method: 'DELETE', headers: {'X-CSRF-Token': csrf()}});
        setDockItems(values => values.filter(value => value.shortcutId !== current.shortcutId));
        setToast(`${item.title} removido dos seus atalhos.`);
      } else {
        await persistShortcut(item);
        setToast(`${item.title} fixado nos seus atalhos.`);
      }
    } catch (error) { setToast(error.message || 'Não foi possível atualizar os atalhos.'); }
  };
  const reorderShortcuts = async next => {
    const before = dockItems;
    // Move immediately so the dock responds to the drop even while the
    // server is creating first-time personal shortcuts.
    setDockItems(next);
    try {
      const explicit = [];
      for (const item of next) explicit.push(item.shortcutId ? item : await createShortcut(item));
      setDockItems(explicit);
      const current = await request(bootstrap.endpoints.dockShortcuts);
      const allIds = Array.isArray(current.shortcuts) ? current.shortcuts.map(item => item.id) : [];
      await request(`${bootstrap.endpoints.dockShortcuts}/order`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({ids: completeDockOrder(explicit.map(candidate => candidate.shortcutId), allIds)})});
    } catch (error) { setDockItems(before); setToast(error.message || 'Não foi possível salvar a ordem dos atalhos.'); }
  };
  return <div className="cadu-ds-home-shell is-workspace-home">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea">
      {isMobile ? (
        <WorkspaceMobileChrome title={home.agency?.name || 'Workspace'} links={bootstrap.urls} contextItems={[...(home.recentConversations || home.conversations || []).map(item => ({...item, detail:'Conversa recente'})), ...projects.map(item => ({...item, detail:'Projeto'}))]}/>
      ) : (
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={projects} brands={sidebarBrands} usagePercent={home.usagePercent} onManageShortcuts={() => { setAccountOpen(false); setShortcutsOpen(true); }}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={home.brands || []} resources={home.resources || []} shortcutItems={dockItems} usagePercent={home.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={item => isDockResource(item) ? openWorkspaceResourceConversation(bootstrap.urls.newConversation, item) : openWorkspaceDetail(item)} onDropItem={addDroppedShortcut} onReorderShortcuts={reorderShortcuts} onShortcutAdded={(_, next) => setDockItems(next)} onShortcutRemoved={(_, next) => setDockItems(next)} onOpenUsage={() => setAccountOpen(true)}/>
      )}
      {!isMobile && <WorkspaceContextSidebar
        mode="home"
        active="home"
        links={bootstrap.urls}
        agencyName={home.agency?.name}
        projects={projects}
        brands={sidebarBrands}
        resources={home.resources || []}
        conversations={home.recentConversations || home.conversations || []}
      />}
        <section className="cadu-ds-home-content">
        <div className="cadu-ds-home-intro"><h1>{homeTitle}</h1><p>Escreva o que você quer resolver.</p></div>
        <WorkspaceChatComposer value={value} onChange={setValue} onSubmit={submit} attachments={attachments} onRemoveAttachment={removeAttachment} onAttachmentPurposeChange={setAttachmentPurpose} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={setAttachmentDestination} hasProject={Boolean(projectRef)} executionMode={executionMode} onExecutionModeChange={setExecutionMode} composerContext={composerContext} onClearContext={() => { setProjectRef(''); setBrandRef(''); setAttachmentDestination('conversation'); }} onContextDrop={dropContext} onAttach={addFiles} projects={projects} projectRef={projectRef} onProjectChange={id => { setProjectRef(id); setBrandRef(''); setAttachmentDestination('conversation'); }} audioTranscriptionEndpoint={bootstrap.endpoints.audioTranscriptions} csrfToken={csrf()} embedded homeMode/>
        <HomeCreditAlert creditAlert={home.creditAlert}/>
        </section>
      </div>
    </main>
    <ShortcutManagerDialog open={shortcutsOpen} onClose={() => { setShortcutsOpen(false); if (window.location.hash === '#atalhos') window.history.replaceState(null, '', window.location.pathname + window.location.search); }} items={managerItems} onToggle={toggleShortcut} onReorder={reorderShortcuts}/>
    <UndoToast message={toast} onDismiss={() => setToast('')}/>
  </div>;
}
