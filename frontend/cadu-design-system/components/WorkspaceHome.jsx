import React, {useCallback, useMemo, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceChatComposer} from './WorkspaceChatComposer';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {WorkspacePromptSuggestions} from './WorkspacePromptSuggestions';
import {ShortcutManagerDialog, UndoToast, WorkspaceAccountMenu} from './WorkspaceFeedback';
import {csrf, request} from '../../conversations-v2/lib/api';
import {attachmentIssues, createStagedAttachment, MAX_ATTACHMENTS, validateAttachment} from '../../conversations-v2/lib/attachmentModel.mjs';
import {uploadAttachments} from '../../conversations-v2/lib/attachmentUpload.mjs';
import {openWorkspaceDetail} from '../workspaceNavigation';

function withQuery(url, values) {
  const target = new URL(url, window.location.origin);
  Object.entries(values).forEach(([key, value]) => { if (value) target.searchParams.set(key, value); });
  return target.pathname + target.search;
}

const isDockResource = item => Boolean(item?.resourceRef) || item?.kind === 'resource';

export function WorkspaceHome({bootstrap}) {
  const home = bootstrap.home || {};
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get('prompt') || '');
  const [projectRef, setProjectRef] = useState('');
  const [shortcutsOpen, setShortcutsOpen] = useState(() => window.location.hash === '#atalhos');
  const [accountOpen, setAccountOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [executionMode, setExecutionMode] = useState('analysis');
  const [brandRef, setBrandRef] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [attachmentDestination, setAttachmentDestination] = useState('conversation');
  const projects = home.projects || [];
  const brands = home.brands || [];
  const catalogBrands = home.catalogBrands || brands;
  const [dockItems, setDockItems] = useState(home.dock?.items || []);
  const selectedProject = useMemo(() => projects.find(item => item.id === projectRef), [projects, projectRef]);
  const selectedBrand = useMemo(() => brands.find(item => item.id === brandRef || `studio:${item.id}` === brandRef), [brands, brandRef]);
  const composerContext = selectedProject ? {label: selectedProject.name, text: selectedProject.brandName || 'projeto'} : selectedBrand ? {label: 'Marca', text: selectedBrand.name} : null;
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
  const submit = async () => {
    const prompt = value.trim();
    if (!prompt) return;
    try {
      const staged = attachments.length ? await uploadAttachments({attachments, projectRef, uploadsEndpoint: bootstrap.endpoints.uploads, requestFn: request, fetchFn: fetch, csrfToken: csrf, uuid: () => crypto.randomUUID(), onProgress: setAttachments}) : [];
      const pending = staged.filter(item => item.id).map(item => ({id: item.id, name: item.name}));
      if (pending.length) sessionStorage.setItem('cadu:home-pending-attachments', JSON.stringify(pending));
      setAttachments(items => { releasePreviews(items); return []; });
      window.location.assign(withQuery(bootstrap.urls.newConversation, {prompt, project_ref: projectRef, brand_ref: brandRef, mode: executionMode, auto_send: '1'}));
    } catch (error) { setToast(error.message || 'Não foi possível preparar os anexos.'); }
  };
  const dropContext = payload => {
    if (payload.projectRef || payload.type === 'project') { setProjectRef(payload.projectRef || payload.id); setBrandRef(''); setAttachmentDestination('conversation'); }
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
      await request(`${bootstrap.endpoints.dockShortcuts}/order`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({ids: explicit.map(candidate => candidate.shortcutId)})});
    } catch (error) { setDockItems(before); setToast(error.message || 'Não foi possível salvar a ordem dos atalhos.'); }
  };
  return <div className="cadu-ds-home-shell">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea">
      <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={projects} brands={catalogBrands} usagePercent={home.usagePercent} onManageShortcuts={() => { setAccountOpen(false); setShortcutsOpen(true); }}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={home.brands || []} resources={home.resources || []} shortcutItems={dockItems} usagePercent={home.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onDropItem={addDroppedShortcut} onReorderShortcuts={reorderShortcuts} onOpenUsage={() => setAccountOpen(true)}/>
      <WorkspaceContextSidebar mode="home" active="home" links={bootstrap.urls} agencyName={home.agency?.name} projects={projects} brands={home.catalogBrands || home.brands || []} resources={home.resources || []} conversations={home.recentConversations || home.conversations || []}/>
        <section className="cadu-ds-home-content">
        <div className="cadu-ds-home-intro"><p className="cadu-ds-home-kicker">Workspace</p><h1>{selectedProject ? selectedProject.name : 'Por onde começamos?'}</h1><p>{selectedProject ? `Trabalhe no contexto de ${selectedProject.brandName || 'seu projeto'}.` : 'Escreva uma demanda ou escolha uma sugestão para começar.'}</p></div>
        <WorkspaceChatComposer value={value} onChange={setValue} onSubmit={submit} attachments={attachments} onRemoveAttachment={removeAttachment} onAttachmentPurposeChange={setAttachmentPurpose} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={setAttachmentDestination} hasProject={Boolean(projectRef)} executionMode={executionMode} onExecutionModeChange={setExecutionMode} composerContext={composerContext} onClearContext={() => { setProjectRef(''); setBrandRef(''); setAttachmentDestination('conversation'); }} onContextDrop={dropContext} onAttach={addFiles} embedded homeMode/>
        {!value.trim() && (
          <WorkspacePromptSuggestions project={selectedProject} brand={selectedBrand} home={home} onSelect={setValue}/>
        )}
        </section>
      </div>
    </main>
    <ShortcutManagerDialog open={shortcutsOpen} onClose={() => { setShortcutsOpen(false); if (window.location.hash === '#atalhos') window.history.replaceState(null, '', window.location.pathname + window.location.search); }} items={managerItems} onToggle={toggleShortcut} onReorder={reorderShortcuts}/>
    <UndoToast message={toast} onDismiss={() => setToast('')}/>
  </div>;
}
