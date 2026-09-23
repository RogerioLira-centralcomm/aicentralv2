import React, {useCallback, useEffect, useReducer, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Sidebar} from './components/Sidebar';
import {Conversation} from './components/Conversation';
import {ArtifactPane} from './components/ArtifactPane';
import {LibraryView} from './components/LibraryView';
import {ConfirmDialog} from './components/ConfirmDialog';
import {csrf, request, streamEvents, uid} from './lib/api';
import {chatFailure} from './lib/errorModel.mjs';
import {insertWorkedBeforeResult, normalizeAnswerText, reconcileCompletedResponse} from './lib/responseModel.mjs';
import {attachmentIssues, attachmentSubmissionMessage, createStagedAttachment, MAX_ATTACHMENTS, validateAttachment} from './lib/attachmentModel.mjs';
import {recentConversations, restoreConversationMessages, restorePendingActions} from './lib/historyModel.mjs';
import {conversationDisplayTitle} from './lib/conversationPresentation.mjs';
import {brandContextPayload, conversationPayload, mergeServerEntities, projectContextPayload} from './lib/contextModel.mjs';
import {uploadAttachments} from './lib/attachmentUpload.mjs';
import {enqueue, MAX_QUEUED_TURNS, moveQueued, readQueue, updateQueued, writeQueue} from './lib/executionQueue.mjs';
import {acceptAgentEvent} from './lib/agentEvents.mjs';
import {executionReducer, initialExecutionState, isExecutionActive} from './lib/executionState.mjs';
import {Icon} from './lib/icons';
import {CaduDock, WorkspaceAccountMenu} from '../cadu-design-system';
import {markProjectUsed} from '../cadu-design-system/projectOptions.mjs';
import {useConversationViewport} from './hooks/useConversationViewport';
import {useArtifactWorkspace} from './hooks/useArtifactWorkspace';
import {useFileDrop} from './hooks/useFileDrop';
import {useResponsiveHistory} from './hooks/useResponsiveHistory';
import {artifactKey, copyText, isConversationMobile} from './lib/browser.mjs';
import {findLibraryItem, libraryGroups} from './lib/libraryModel.mjs';
import {persistConversationContext, takePendingHomeAttachments} from './lib/storage.mjs';
import {completeDockOrder} from '../cadu-design-system/dockPlacement.mjs';

const emptyTitle = 'Cadu';

function sourceDomainLabel(value) {
  try { return new URL(String(value || '')).hostname.replace(/^www\./, ''); }
  catch (_) { return 'Fonte externa'; }
}

function setSurfaceUrl(surface, artifactId = '', replace = false, resource = null) {
  const url = new URL(window.location.href);
  if (surface === 'conversation') url.searchParams.delete('surface');
  else url.searchParams.set('surface', surface);
  if (surface === 'artifact' && artifactId) url.searchParams.set('artifact_id', artifactId);
  else url.searchParams.delete('artifact_id');
  if (surface === 'artifact' && !artifactId && resource?.libraryRef) {
    url.searchParams.set('resource_ref', resource.libraryRef);
    if (resource.project_ref) url.searchParams.set('resource_project_ref', resource.project_ref);
    else url.searchParams.delete('resource_project_ref');
  } else {
    url.searchParams.delete('resource_ref');
    url.searchParams.delete('resource_project_ref');
  }
  window.history[replace ? 'replaceState' : 'pushState']({caduSurface: surface, resource}, '', url);
}

function setConversationUrl(conversationId = '', replace = true) {
  // Entry-only parameters (prompt, project, brand and mode) must never survive
  // the first admitted turn: replaying them on refresh duplicates bootstrap work.
  const url = new URL(window.location.pathname, window.location.origin);
  if (conversationId) url.searchParams.set('conversation_id', String(conversationId));
  else url.searchParams.delete('conversation_id');
  url.searchParams.delete('surface');
  url.searchParams.delete('artifact_id');
  window.history[replace ? 'replaceState' : 'pushState']({caduSurface: 'conversation', conversationId: conversationId || null}, '', url);
}

export default function App({bootstrap}) {
  const shellV2 = bootstrap.rollout?.shell_v2 !== false;
  const viewport = useConversationViewport();
  const {layout, keyboardOpen} = viewport;
  const initialQuery = new URLSearchParams(window.location.search);
  const hasTransferredContext = initialQuery.get('context_mode') === 'free' || Boolean(initialQuery.get('project_ref') || initialQuery.get('project') || initialQuery.get('brand_ref'));
  const requestedConversationId = useRef(initialQuery.get('conversation_id') || '');
  const [context, setContext] = useState({});
  const [projects, setProjects] = useState([]);
  const [brands, setBrands] = useState(() => bootstrap.brands || []);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [title, setTitle] = useState(emptyTitle);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(() => initialQuery.get('prompt') || '');
  const [homeAttachments, setHomeAttachments] = useState(takePendingHomeAttachments);
  const [executionMode, setExecutionMode] = useState(() => initialQuery.get('mode') || 'analysis');
  const [composerContext, setComposerContext] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [attachmentDestination, setAttachmentDestination] = useState('conversation');
  const [artifact, setArtifact] = useState(null);
  const [artifactOpen, setArtifactOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(() => initialQuery.get('surface') === 'library');
  const [library, setLibrary] = useState({loading: false, error: '', groups: []});
  const [artifactWidth, setArtifactWidth] = useState(() => {
    try { const saved = Number(window.sessionStorage.getItem('cadu:artifact-width')); return saved >= 30 && saved <= 60 ? saved : 45; }
    catch (_) { return 45; }
  });
  const [artifactDirty, setArtifactDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishedUrl, setPublishedUrl] = useState('');
  const [versions, setVersions] = useState([]);
  const [execution, dispatchExecution] = useReducer(executionReducer, initialExecutionState);
  const running = isExecutionActive(execution);
  const [queuedTurns, setQueuedTurns] = useState(() => readQueue(null));
  const [runtime, setRuntime] = useState('');
  const [diagnostics, setDiagnostics] = useState([]);
  const [historyOpen, setHistoryOpen] = useResponsiveHistory(Boolean(conversationId));
  useEffect(() => { try { window.sessionStorage.setItem('cadu:artifact-width', String(artifactWidth)); } catch (_) { /* Private browsing can disable storage. */ } }, [artifactWidth]);
  const activeSurface = historyOpen && layout !== 'desktop' ? 'navigation' : libraryOpen ? 'library' : artifactOpen ? 'artifact' : 'conversation';
  const [accountOpen, setAccountOpen] = useState(false);
  const [conversationDockItems, setConversationDockItems] = useState(() => bootstrap.dock?.items || []);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
  const [contextTransferReady, setContextTransferReady] = useState(!hasTransferredContext);
  const [openingId, setOpeningId] = useState(null);
  const [discardRequest, setDiscardRequest] = useState(null);
  const {artifactTabs, setArtifactTabs, artifactSide, changeArtifactSide} = useArtifactWorkspace(artifact);
  const conversationRef = useRef(null);
  const artifactRef = useRef(null);
  const artifactEditRevisionRef = useRef(0);
  useEffect(() => { if (artifactOpen && layout !== 'desktop') setHistoryOpen(false); }, [artifactOpen, layout]);
  const runRef = useRef(null);
  const longJobRef = useRef(null);
  const streamControllerRef = useRef(null);
  const recoveryTimerRef = useRef(null);
  const runStartedRef = useRef(0);
  const drainingQueueRef = useRef(false);
  const discardResolverRef = useRef(null);
  useEffect(() => () => {
    streamControllerRef.current?.abort();
    if (recoveryTimerRef.current) window.clearTimeout(recoveryTimerRef.current);
  }, []);

  const rememberContext = useCallback(next => {
    setContext(next || {});
    persistConversationContext(next);
  }, []);

  useEffect(() => { conversationRef.current = conversationId; }, [conversationId]);
  useEffect(() => { artifactRef.current = artifact; }, [artifact]);
  const trace = useCallback((eventTitle, detail = '', tone = '') => {
    setDiagnostics(items => [...items, {id: uid(), title: eventTitle, detail, tone}].slice(-30));
  }, []);

  const releasePreviews = useCallback(items => items.forEach(item => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  }), []);
  const queueEndpoint = useCallback(id => `/workspace/api/v2/conversations/${encodeURIComponent(id)}/queue`, []);

  useEffect(() => { writeQueue(conversationId, queuedTurns); }, [conversationId, queuedTurns]);

  useEffect(() => {
    if (!conversationId) return;
    const pending = readQueue(null);
    if (!pending.length) return;
    // The same in-memory queue survives run.started; only recover the pending
    // copy when a reload lost that state. Appending here duplicated every item.
    setQueuedTurns(current => current.length ? current : pending.slice(0, MAX_QUEUED_TURNS));
    writeQueue(null, []);
    Promise.all(pending.slice(0, MAX_QUEUED_TURNS).map(item => request(queueEndpoint(conversationId), {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
      body: JSON.stringify({prompt: item.prompt, execution_mode: item.executionMode || 'analysis', selected_context: item.context || null}),
    }).then(data => data.item))).then(items => setQueuedTurns(items.map(item => ({...item, executionMode: item.execution_mode, context: item.selected_context})))).catch(error => trace('Fila salva apenas neste navegador', error.message, 'error'));
  }, [conversationId, queueEndpoint, trace]);

  const fetchArtifact = useCallback(async id => {
    const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(id)}`);
    setArtifact(data.artifact);
    artifactRef.current = data.artifact;
    setPublishedUrl('');
    setArtifactDirty(false);
    setArtifactOpen(true);
    return data.artifact;
  }, [bootstrap.endpoints.artifacts]);

  const loadRecent = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const separator = bootstrap.endpoints.history.includes('?') ? '&' : '?';
      const data = await request(`${bootstrap.endpoints.history}${separator}limit=50`);
      setConversations(recentConversations(data.conversations, 50));
    } catch (_) {
      setConversations([]);
    } finally { setHistoryLoading(false); }
  }, [bootstrap.endpoints.history]);

  const loadContext = useCallback(async () => {
    setContextLoading(true);
    try {
      const data = await request(bootstrap.endpoints.context);
      // The server is authoritative: an empty context means an intentional
      // free session and must not resurrect a stale project from the browser.
      rememberContext(data.context || {});
      setProjects(current => mergeServerEntities(
        current,
        (data.entities || []).filter(item => item.kind === 'project'),
      ));
      setBrands(current => {
        const fromContext = (data.entities || []).filter(item => item.kind === 'brand').map(item => ({
          ...item, logoUrl: item.logo_url, visualInitials: item.name, visualColor: item.color || item.visualColor || '#176b5e',
        }));
        return mergeServerEntities(current, fromContext);
      });
    } catch (error) {
      trace('Contexto indisponível', error.message, 'error');
    } finally { setContextLoading(false); }
  }, [bootstrap.endpoints.context, rememberContext, trace]);

  const organizeConversation = useCallback(async (id, section) => {
    const previous = conversations;
    setConversations(items => items.map(item => String(item.id) === String(id) ? {
      ...item, section, automation_enabled: section === 'automation' ? item.automation_enabled : false,
    } : item));
    try {
      await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({section, ...(section === 'automation' ? {automation_enabled: false} : {})}),
      });
    } catch (error) {
      setConversations(previous);
      trace('Não foi possível mover a conversa', error.message, 'error');
    }
  }, [bootstrap.endpoints.history, conversations, trace]);

  useEffect(() => {
    loadRecent();
    if (!requestedConversationId.current) loadContext();
  }, [loadContext, loadRecent]);
  useEffect(() => {
    if (!historyOpen) return undefined;
    const interval = window.setInterval(loadRecent, conversations.some(item => item.running) ? 4000 : 12000);
    return () => window.clearInterval(interval);
  }, [conversations, historyOpen, loadRecent]);

  const confirmDiscard = useCallback((includeAttachments = true) => {
    const hasAttachments = includeAttachments && attachments.length > 0;
    if (!artifactDirty && !hasAttachments) return Promise.resolve(true);
    const copy = artifactDirty && hasAttachments ? 'A entrega e os anexos preparados ainda não foram salvos.'
      : artifactDirty ? 'A entrega tem alterações que ainda não foram salvas.'
        : 'Os anexos preparados ainda não foram enviados.';
    return new Promise(resolve => {
      discardResolverRef.current = resolve;
      setDiscardRequest({copy});
    });
  }, [artifactDirty, attachments.length]);

  const resolveDiscard = useCallback(value => {
    discardResolverRef.current?.(value);
    discardResolverRef.current = null;
    setDiscardRequest(null);
  }, []);

  const reset = useCallback(() => {
    setConversationId(null); conversationRef.current = null;
    setTitle(emptyTitle); setMessages([]); setInput(''); setComposerContext(null);
    setAttachments(items => { releasePreviews(items); return []; });
    setArtifact(null); setArtifactTabs([]); artifactRef.current = null; setArtifactOpen(false); setLibraryOpen(false); setArtifactDirty(false); setPublishedUrl('');
    setDiagnostics([]); setRuntime(''); runRef.current = null;
    setQueuedTurns([]);
  }, [releasePreviews]);

  const focusComposer = useCallback(() => {
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);

  const newConversation = useCallback(async () => {
    if (running || !(await confirmDiscard())) return;
    reset();
    setHistoryOpen(false);
    setConversationUrl('', true);
    focusComposer();
  }, [running, confirmDiscard, reset, focusComposer]);

  const openConversation = useCallback(async (id, conversationTitle) => {
    if (running || !(await confirmDiscard())) return;
    setOpeningId(id);
    setRuntime('Abrindo conversa');
    try {
      const data = await request(`/workspace/api/v2/conversations/${encodeURIComponent(id)}/bootstrap`);
      setConversationId(id); conversationRef.current = id;
      setQueuedTurns((data.queue || readQueue(id)).map(item => ({...item, executionMode: item.execution_mode, context: item.selected_context})));
      setTitle(conversationDisplayTitle(conversationTitle || data.conversation?.title, 'Conversa'));
      if (data.context) setContext(data.context);
      if (Array.isArray(data.conversations)) setConversations(recentConversations(data.conversations, 30));
      if (Array.isArray(data.entities)) {
        setProjects(data.entities.filter(item => item.kind === 'project'));
        setBrands(current => mergeServerEntities(current, data.entities.filter(item => item.kind === 'brand').map(item => ({
          ...item, logoUrl: item.logo_url, visualInitials: item.name, visualColor: item.color || item.visualColor || '#176b5e',
        }))));
      }
      setAttachments(items => { releasePreviews(items); return []; }); setComposerContext(null); setArtifact(null); setArtifactTabs([]); artifactRef.current = null; setArtifactDirty(false); setPublishedUrl(''); setArtifactOpen(false); setLibraryOpen(false);
      const {messages: restored, selectedContext: restoredContext, lastArtifact} = restoreConversationMessages(data.messages, uid);
      setMessages(restored);
      setComposerContext(restoredContext);
      if (lastArtifact) await fetchArtifact(lastArtifact);
      setConversationUrl(id, true);
      setSurfaceUrl(lastArtifact ? 'artifact' : 'conversation', lastArtifact || '', true);
      const active = {run: data.active_run || null};
      if (active.run?.id) {
        const pendingActions = restorePendingActions(active.run, uid);
        if (pendingActions.length) setMessages(items => [...items, ...pendingActions]);
        runRef.current = active.run.id;
        if (active.run.status !== 'running') {
          setRuntime('');
          runRef.current = null;
          setOpeningId('');
          if (isConversationMobile()) setHistoryOpen(false);
          return;
        }
        dispatchExecution({type: 'event', event: {event: 'run.started', run_id: active.run.id}});
        setRuntime('Retomando o trabalho em andamento');
        const monitor = async () => {
          try {
            const state = await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(active.run.id)}/state`);
            const status = String(state.run?.status || '');
            if (status === 'running') {
              recoveryTimerRef.current = window.setTimeout(monitor, 1800);
              return;
            }
            const refreshed = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}/messages`);
            const recovered = restoreConversationMessages(refreshed.messages, uid);
            setMessages(recovered.messages);
            if (recovered.lastArtifact) await fetchArtifact(recovered.lastArtifact);
            dispatchExecution({type: 'event', event: {event: status === 'failed' ? 'run.failed' : status === 'cancelled' ? 'run.cancelled' : 'run.completed', status}});
            runRef.current = null;
            setRuntime(status === 'completed' ? '' : status === 'cancelled' ? 'Interrompido' : 'Não foi possível concluir');
          } catch (error) {
            dispatchExecution({type: 'connection.lost', error: error.message});
            setRuntime('Reconectando ao trabalho');
            recoveryTimerRef.current = window.setTimeout(monitor, 2500);
          }
        };
        recoveryTimerRef.current = window.setTimeout(monitor, 600);
      } else setRuntime('');
      if (isConversationMobile()) setHistoryOpen(false);
    } catch (error) {
      try {
        const fallback = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}/messages`);
        const recovered = restoreConversationMessages(fallback.messages, uid);
        setConversationId(id); conversationRef.current = id;
        setTitle(conversationDisplayTitle(conversationTitle, 'Conversa'));
        setMessages(recovered.messages);
        setComposerContext(recovered.selectedContext);
        if (recovered.lastArtifact) await fetchArtifact(recovered.lastArtifact);
        try {
          const active = await request(`/workspace/api/v2/conversations/${encodeURIComponent(id)}/active-run`);
          const pendingActions = restorePendingActions(active.run, uid);
          if (pendingActions.length) setMessages(items => [...items, ...pendingActions]);
        } catch (_) { /* The recovered history remains usable without an active action. */ }
        setConversationUrl(id, true);
        setRuntime('');
        trace('Conversa recuperada', 'O histórico foi aberto pelo modo de compatibilidade.');
        await loadContext();
      } catch (fallbackError) {
        setRuntime('Não foi possível abrir');
        trace('Falha ao abrir conversa', fallbackError.message || error.message, 'error');
        await Promise.allSettled([loadContext(), loadRecent()]);
      }
    } finally { setOpeningId(null); setHistoryLoading(false); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.history, bootstrap.endpoints.runs, fetchArtifact, trace, releasePreviews, queueEndpoint, loadContext, loadRecent]);

  const changeProject = useCallback(async (projectRef, {showHistory = true} = {}) => {
    if (running || !(await confirmDiscard())) return;
    setContextLoading(true);
    setRuntime('Atualizando contexto');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(projectContextPayload(projectRef)),
      });
      if (projectRef) markProjectUsed(projectRef);
      rememberContext(data.context || {});
      reset();
      setHistoryOpen(showHistory);
      trace('Contexto alterado', projects.find(item => item.ref === projectRef)?.name || 'Contexto pessoal');
    } catch (error) {
      trace('Falha ao alterar contexto', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.context, rememberContext, reset, trace, projects, loadContext]);

  const loadBrandIdentity = useCallback(async brandRef => {
    const brandId = String(brandRef || '').replace(/^studio:/, '');
    if (!/^\d+$/.test(brandId)) return;
    const data = await request(`/workspace/api/v2/brands/${brandId}/identity`);
    if (data.artifact) {
      setArtifact(data.artifact); artifactRef.current = data.artifact;
      setPublishedUrl(''); setArtifactDirty(false); setArtifactOpen(true);
    }
  }, []);

  const loadProjectProfile = useCallback(async projectRef => {
    if (!projectRef) return;
    const data = await request(`/workspace/api/v2/projects/${encodeURIComponent(projectRef)}/profile`);
    if (data.artifact) {
      setArtifact(data.artifact); artifactRef.current = data.artifact;
      setPublishedUrl(''); setArtifactDirty(false); setArtifactOpen(true);
      setSurfaceUrl('artifact', '');
    }
  }, []);

  const changeBrand = useCallback(async (brandRef, {showHistory = true} = {}) => {
    if (running || !(await confirmDiscard())) return;
    setContextLoading(true); setRuntime('Atualizando marca');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(brandContextPayload(brandRef)),
      });
      rememberContext(data.context || {}); reset(); setHistoryOpen(showHistory);
      await loadBrandIdentity(brandRef);
      trace('Marca aplicada à conversa');
    } catch (error) {
      trace('Falha ao abrir a marca', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.context, rememberContext, reset, loadBrandIdentity, trace, loadContext]);

  const conversationAction = useCallback(async (item, action) => {
    const id = String(item?.id || '');
    if (!id) return;
    const previous = conversations;
    let payload;
    if (action === 'archive') payload = {archived: true};
    else if (action === 'stop-automation') payload = {automation_enabled: false};
    else if (action === 'toggle-pin') payload = {section: item.section === 'pinned' ? 'recent' : 'pinned'};
    else return;
    setConversations(items => action === 'archive'
      ? items.filter(candidate => String(candidate.id) !== id)
      : items.map(candidate => String(candidate.id) === id ? {
        ...candidate,
        ...(payload.section ? {section: payload.section, automation_enabled: false} : {}),
        ...(action === 'stop-automation' ? {automation_enabled: false} : {}),
      } : candidate));
    try {
      await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(payload),
      });
      if (action === 'archive' && String(conversationRef.current) === id) reset();
    } catch (error) {
      setConversations(previous);
      trace('Não foi possível atualizar a conversa', error.message, 'error');
    }
  }, [bootstrap.endpoints.history, conversations, reset, trace]);

  const dropContext = useCallback(payload => {
    if (payload?.projectRef || payload?.type === 'project') {
      changeProject(payload.projectRef || payload.id);
      return;
    }
    if (payload?.type === 'brand') changeBrand(payload.brandRef || (payload.id ? `studio:${payload.id}` : ''));
    else if (payload?.type === 'resource' || payload?.resourceRef) {
      setComposerContext({type: 'resource', label: payload.title || 'Referência', text: JSON.stringify({id: payload.id || payload.resourceRef, title: payload.title, url: payload.url, kind: payload.kind})});
      window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
    }
  }, [changeBrand, changeProject]);

  const requestedContext = useRef({
    projectRef: initialQuery.get('project_ref') || initialQuery.get('project') || '',
    brandRef: initialQuery.get('brand_ref') || '',
    free: initialQuery.get('context_mode') === 'free',
    pending: hasTransferredContext,
  });
  const requestedHistoryOpen = useRef(new URLSearchParams(window.location.search).get('history') === '1');
  useEffect(() => {
    const transfer = requestedContext.current;
    if (!transfer.pending || contextLoading || running) return;
    transfer.pending = false;
    const payload = transfer.free
      ? {project_ref: null, brand_ref: null}
      : {project_ref: transfer.projectRef || null, brand_ref: transfer.brandRef || null};
    request(bootstrap.endpoints.context, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
      body: JSON.stringify(payload),
    }).then(async data => {
      setContext(data.context || {});
      if (requestedHistoryOpen.current) setHistoryOpen(true);
      requestedHistoryOpen.current = false;
      if (transfer.brandRef) await loadBrandIdentity(transfer.brandRef);
    }).catch(error => trace('Não foi possível aplicar o contexto selecionado', error.message, 'error'))
      .finally(() => setContextTransferReady(true));
  }, [contextLoading, running, bootstrap.endpoints.context, loadBrandIdentity, trace]);

  useEffect(() => {
    if (!requestedConversationId.current || running) return;
    const id = requestedConversationId.current;
    requestedConversationId.current = '';
    openConversation(id, '');
  }, [running, openConversation]);

  const classifyAttachment = useCallback(async file => {
    try {
      const data = await request('/workspace/mcp', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({jsonrpc: '2.0', id: crypto.randomUUID(), method: 'tools/call', params: {
          name: 'projects.classify_intake', surface: 'conversations', arguments: {
            filename: file.name, mime_type: file.type || '',
          },
        }}),
      });
      return data.result?.structuredContent || {state: 'unavailable'};
    } catch (_) { return {state: 'unavailable'}; }
  }, []);

  const addFiles = useCallback(async files => {
    const staged = [];
    setAttachments(current => {
      const next = [...current];
      const fileKey = file => [file?.name, file?.size, file?.type, file?.lastModified].join(':');
      const known = new Set(next.map(item => fileKey(item.file)));
      for (const file of files) {
        const key = fileKey(file);
        if (known.has(key)) continue;
        if (next.length >= MAX_ATTACHMENTS) {
          trace(attachmentIssues.limit.title, attachmentIssues.limit.detail, 'error');
          break;
        }
        const issue = validateAttachment(file);
        if (issue) {
          trace(issue.title, issue.detail, 'error');
          continue;
        }
        const previewUrl = file.type?.startsWith('image/') ? URL.createObjectURL(file) : '';
        const item = createStagedAttachment(file, attachmentDestination, previewUrl);
        known.add(key); staged.push(item); next.push(item);
      }
      return next;
    });
    await Promise.all(staged.map(async item => {
      const intake = await classifyAttachment(item.file);
      setAttachments(current => current.map(candidate => candidate.localId === item.localId ? {...candidate, intake} : candidate));
    }));
  }, [trace, attachmentDestination, classifyAttachment]);

  const removeAttachment = useCallback(index => setAttachments(items => { const removed = items[index]; if (removed) releasePreviews([removed]); return items.filter((_, itemIndex) => itemIndex !== index); }), [releasePreviews]);
  const setAttachmentPurpose = useCallback((index, destination) => setAttachments(items => items.map((item, itemIndex) => itemIndex === index ? {...item, destination} : item)), []);
  const {dropActive, handleDragEnter, handleDragOver, handleDragLeave, handleDrop} = useFileDrop(addFiles);

  const uploadFiles = useCallback(resolvedExecutionMode => uploadAttachments({
      attachments,
      projectRef: context.project_ref,
      uploadsEndpoint: bootstrap.endpoints.uploads,
      requestFn: request,
      fetchFn: fetch,
      csrfToken: csrf,
      uuid: () => crypto.randomUUID(),
      onProgress: setAttachments,
      executionMode: resolvedExecutionMode,
    }), [attachments, context.project_ref, bootstrap.endpoints.uploads]);

  const submit = useCallback(async (requestedInput = input, {skipAttachments = false, fromQueue = false, queuedContext = null, queuedMode = null} = {}) => {
    const turnAttachments = skipAttachments ? [] : attachments;
    const clean = requestedInput.trim() || attachmentSubmissionMessage(turnAttachments);
    if (!clean) return;
    if (running && !fromQueue) {
      if (queuedTurns.length >= MAX_QUEUED_TURNS) {
        trace('Fila cheia', 'Aguarde um pedido terminar ou remova um item da fila.', 'error');
        return;
      }
      if (turnAttachments.length) {
        trace('Anexos aguardam envio', 'Pedidos com arquivos entram na fila depois que o envio atual terminar.', 'error');
        return;
      }
      const draft = {id: uid(), prompt: clean, context: composerContext || null, executionMode, createdAt: Date.now()};
      if (conversationRef.current) {
        try {
          const data = await request(queueEndpoint(conversationRef.current), {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
            body: JSON.stringify({prompt: clean, execution_mode: executionMode, selected_context: composerContext || null}),
          });
          const saved = data.item || draft;
          setQueuedTurns(items => enqueue(items, {...saved, executionMode: saved.execution_mode || executionMode, context: saved.selected_context || composerContext || null}));
        } catch (error) { trace('Não foi possível adicionar à fila', error.message, 'error'); return; }
      } else setQueuedTurns(items => enqueue(items, draft));
      setInput(''); setComposerContext(null);
      return;
    }
    if (saving) { trace('Aguarde o salvamento do documento', 'Sua edição está sendo preservada antes da próxima revisão.'); return; }
    if (artifactDirty && artifact?.id) {
      const revision = artifactEditRevisionRef.current;
      try {
        const saved = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {
          method:'PATCH', headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf()},
          body:JSON.stringify({conversation_id:conversationId, expected_version:artifact.current_version, content:artifact.content, title:artifact.title, change_summary:'Edição manual antes da revisão pelo Cadu'}),
        });
        if (revision !== artifactEditRevisionRef.current) {
          setArtifact(current => current?.id === saved.artifact.id ? {...current, current_version:saved.artifact.current_version} : current);
          setArtifactDirty(true);
          trace('Documento alterado durante o salvamento', 'Salve a edição mais recente antes de continuar.');
          return;
        }
        setArtifact(saved.artifact); artifactRef.current = saved.artifact; setArtifactDirty(false);
      } catch (error) { trace('Não foi possível preservar a edição manual', error.message, 'error'); return; }
    }
    dispatchExecution({type: 'submitted'}); setDiagnostics([]); setRuntime(turnAttachments.length ? 'Enviando arquivos' : 'Trabalhando');
    if (!conversationRef.current && isConversationMobile()) setHistoryOpen(false);
    let resolvedExecutionMode = queuedMode || executionMode;
    let staged;
    try {
      if (turnAttachments.some(item => item.destination === 'conversation')) {
        const preview = await request(bootstrap.endpoints.route, {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({
            message: clean,
            conversation_id: conversationRef.current,
            execution_mode: resolvedExecutionMode,
            project_ref: context.project_ref || null,
            brand_ref: context.brand_ref || null,
            active_object: artifactRef.current?.id ? {type: `artifact:${artifactRef.current.type}`, id: artifactRef.current.id} : null,
          }),
        });
        resolvedExecutionMode = preview.execution_mode || resolvedExecutionMode;
      }
      staged = turnAttachments.length ? await uploadFiles(resolvedExecutionMode) : [];
    }
    catch (error) { dispatchExecution({type: 'upload.failed', error: error.message}); setRuntime('Não foi possível anexar'); trace('Falha no anexo', error.message, 'error'); return; }
    const files = [...staged.map(item => ({id: item.id, name: item.name, source: item.source || null})), ...homeAttachments];
    const providerFileIds = files.map(item => item.id).filter(Boolean);
    const projectUploads = files.filter(item => item.source).map(item => ({
      source_id: item.source.source_id, name: item.source.name || item.name,
      purpose: item.source.purpose, category: item.source.category, status: item.source.status,
    }));
    const turnContext = queuedContext || composerContext || (projectUploads.length ? {
      type: 'project_upload_receipt', label: 'Itens adicionados ao projeto',
      text: JSON.stringify(projectUploads),
    } : null);
    const turnId = uid();
    setMessages(items => [...items, {id: uid(), turnId, role: 'user', content: clean, files}]);
    setTitle(current => current === emptyTitle ? conversationDisplayTitle(clean) : current);
    setInput(''); setComposerContext(null); setHomeAttachments([]); if (!skipAttachments) setAttachments(items => { releasePreviews(items); return []; }); setRuntime('Trabalhando');
    let terminal = false;
    let runStarted = false;
    let latestArtifact = null;
    let pendingArtifact = null;
    let artifactResolved = false;
    let longJobPromise = null;
    const monitorLongJob = async job => {
      let openedArtifact = '';
      while (!controller.signal.aborted) {
        const state = await request(`/workspace/api/v2/long-jobs/${encodeURIComponent(job.id)}`);
        const status = String(state.job?.status || '');
        const completed = (state.units || []).filter(item => item.status === 'completed').length;
        const total = (state.units || []).length;
        setRuntime(total ? `Construindo o trabalho · ${completed}/${total}` : 'Construindo o trabalho');
        dispatchExecution({type: 'event', event: {event: 'long_job.progress', job: state.job}});
        if (state.job?.artifact_id && state.job.artifact_id !== openedArtifact) {
          openedArtifact = state.job.artifact_id;
          setArtifactTabs(items => items.filter(item => artifactKey(item) !== `long-job:${job.id}`));
          await fetchArtifact(openedArtifact);
        }
        if (['completed', 'failed', 'cancelled', 'budget_exhausted'].includes(status)) {
          if (status === 'completed') {
            const refreshed = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(conversationRef.current)}/messages`);
            const recovered = restoreConversationMessages(refreshed.messages, uid);
            setMessages(recovered.messages);
            if (recovered.lastArtifact && recovered.lastArtifact !== openedArtifact) await fetchArtifact(recovered.lastArtifact);
            dispatchExecution({type: 'event', event: {event: 'long_job.completed', job: state.job}});
            longJobRef.current = null;
            setRuntime('');
          } else {
            const message = status === 'budget_exhausted' ? 'O limite de tokens deste trabalho foi atingido.' : 'O trabalho longo foi interrompido.';
            dispatchExecution({type: 'event', event: {event: 'long_job.failed', message}});
            longJobRef.current = null;
            setRuntime(message);
            trace('Trabalho longo interrompido', message, 'error');
          }
          return;
        }
        await new Promise(resolve => window.setTimeout(resolve, 1600));
      }
    };
    const failPendingArtifact = message => {
      if (!pendingArtifact) return;
      const failed = {...pendingArtifact, pending: false, failed: true, title: 'Entrega não concluída', error: message || 'A geração terminou antes de preparar o conteúdo.'};
      setArtifactTabs(items => items.map(item => artifactKey(item) === pendingArtifact.tabKey ? failed : item));
      if (artifactKey(artifactRef.current) === pendingArtifact.tabKey) { setArtifact(failed); artifactRef.current = failed; }
    };
    const startedAt = Date.now();
    const controller = new AbortController();
    streamControllerRef.current?.abort();
    streamControllerRef.current = controller;
    const seenEvents = new Set();
    try {
      const response = await fetch(bootstrap.endpoints.messages, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        signal: controller.signal,
        body: JSON.stringify(conversationPayload({
          message: clean,
          requestId: crypto.randomUUID(),
          conversationId: conversationRef.current,
          providerFileIds,
          executionMode: resolvedExecutionMode,
          context,
          selectedContext: turnContext,
          activeArtifact: artifactRef.current,
        })),
      });
      await streamEvents(response, rawEvent => {
        const event = acceptAgentEvent(rawEvent, seenEvents);
        if (!event || controller.signal.aborted) return;
        dispatchExecution({type: 'event', event});
        const kind = event.event;
        if (kind === 'run.started') {
          runStarted = true;
          setConversationId(event.conversation_id); conversationRef.current = event.conversation_id;
          setConversationUrl(event.conversation_id, true);
          runRef.current = event.run_id; runStartedRef.current = Date.now();
          const contextDiagnostics = event.context_diagnostics || {};
          trace('Contexto da conversa preparado', [
            `run ${String(event.run_id || '').slice(0, 8)}`,
            `${contextDiagnostics.history_message_count || 0} mensagens`,
            `${contextDiagnostics.retrieved_message_count || 0} recuperadas`,
            contextDiagnostics.memory_present ? `memória ${contextDiagnostics.memory_version || 'ativa'}` : 'sem resumo',
          ].join(' · '));
          const resolved = event.resolved_context || {};
          if (resolved.project_ref !== (context.project_ref || null) || resolved.brand_ref !== (context.brand_ref || null)) {
            trace('Contexto sincronizado pelo servidor', resolved.project_ref || resolved.brand_ref || 'Conversa sem projeto');
            rememberContext({...context, project_ref: resolved.project_ref || null, brand_ref: resolved.brand_ref || null});
          }
          trace('Entendendo o pedido');
          setRuntime('Entendendo o pedido');
        } else if (kind === 'route.selected') {
          if (event.policy?.execution_mode) setExecutionMode(event.policy.execution_mode);
          if (event.policy?.artifact_type) {
            pendingArtifact = {tabKey: `pending:${turnId}`, type: event.policy.artifact_type, title: 'Preparando entrega', pending: true};
            setArtifactTabs(items => [...items.filter(item => artifactKey(item) !== pendingArtifact.tabKey), pendingArtifact]);
            if (!artifactRef.current || !artifactOpen) {
              setArtifact(pendingArtifact); artifactRef.current = pendingArtifact; setArtifactOpen(true);
            }
          }
          setRuntime('Preparando o contexto');
          trace('Preparando contexto');
        }
        else if (kind === 'tool.started') {
          if (event.name === 'web.search') setRuntime('Buscando fontes relevantes');
          else if (event.name === 'web.read') setRuntime('Lendo as fontes encontradas');
          else setRuntime('Consultando o contexto disponível');
        }
        else if (kind === 'tool.completed') {
          if (event.name === 'web.search') {
            setRuntime('Buscando fontes');
            trace('Pesquisa inicial concluída');
          } else if (event.name === 'web.read') {
            setRuntime('Lendo fontes selecionadas');
            trace('Leitura das fontes concluída');
          } else {
            setRuntime('Consultando contexto');
            trace('Contexto consultado');
          }
        }
        else if (kind === 'tool.unavailable') {
          setRuntime(event.name === 'web.search' || event.name === 'web.read' ? 'Pesquisa indisponível' : 'Trabalhando');
          trace('Recurso indisponível', '', 'error');
        }
        else if (kind === 'action.proposed') {
          const actionMessage = {id: uid(), turnId, role: 'assistant', kind: 'action', action: event.action, runId: event.action?.run_id || event.action?.runId || runRef.current};
          setMessages(items => [...items, actionMessage]);
        }
        else if (kind === 'long_job.created') {
          const job = event.job || {};
          longJobRef.current = job.id || null;
          pendingArtifact = {tabKey: `long-job:${job.id}`, type: 'document', title: job.title || 'Trabalho em elaboração', pending: true};
          setArtifactTabs(items => [...items.filter(item => artifactKey(item) !== pendingArtifact.tabKey), pendingArtifact]);
          if (!artifactRef.current || !artifactOpen) {
            setArtifact(pendingArtifact); artifactRef.current = pendingArtifact; setArtifactOpen(true);
          }
          setRuntime('Organizando as etapas do trabalho');
          longJobPromise = monitorLongJob(job);
        }
        else if (kind === 'artifact.created') {
          setRuntime('Preparando o material');
          latestArtifact = event.artifact || null;
          if (latestArtifact) {
            artifactResolved = true;
            setArtifactTabs(items => {
              const withoutPending = items.filter(item => artifactKey(item) !== pendingArtifact?.tabKey && artifactKey(item) !== artifactKey(latestArtifact));
              return [...withoutPending, latestArtifact];
            });
            if (!artifactRef.current || artifactKey(artifactRef.current) === pendingArtifact?.tabKey) {
              setArtifact(latestArtifact); artifactRef.current = latestArtifact; setPublishedUrl(''); setArtifactDirty(false); setArtifactOpen(true);
            }
          }
          trace('Entrega criada', event.artifact?.title || '');
        } else if (kind === 'provider.first_token') {
          setRuntime('Escrevendo a resposta');
        } else if (kind === 'answer.delta') {
          const answer = normalizeAnswerText(event.answer || '');
          if (!answer) return;
          setRuntime('Escrevendo a resposta');
          setMessages(items => {
            const existing = items.findIndex(item => item.turnId === turnId && item.streaming);
            const draft = {id: existing >= 0 ? items[existing].id : uid(), turnId, role: 'assistant', streaming: true, response: {answer}};
            return existing >= 0 ? items.map((item, index) => index === existing ? draft : item) : [...items, draft];
          });
        } else if (kind === 'answer.completed') {
          const responseData = event.response || {};
          if (responseData.artifact_patch && !latestArtifact?.id) {
            artifactResolved = true;
            const draft = {type: responseData.artifact_patch.type || 'document', title: responseData.artifact_patch.title, content: responseData.artifact_patch};
            draft.tabKey = pendingArtifact?.tabKey || `draft:${turnId}`;
            setArtifactTabs(items => [...items.filter(item => artifactKey(item) !== pendingArtifact?.tabKey), draft]);
            if (!artifactRef.current || artifactKey(artifactRef.current) === pendingArtifact?.tabKey) {
              setArtifact(draft); artifactRef.current = draft; setPublishedUrl(''); setArtifactOpen(true);
            }
          }
          setMessages(items => {
            const existing = items.findIndex(item => item.turnId === turnId && item.streaming);
            const safeResponse = reconcileCompletedResponse(existing >= 0 ? items[existing].response : null, responseData, Boolean(latestArtifact?.id || responseData.artifact_patch));
            const completed = {id: existing >= 0 ? items[existing].id : uid(), turnId, role: 'assistant', response: safeResponse, artifact: latestArtifact};
            return existing >= 0 ? items.map((item, index) => index === existing ? completed : item) : [...items, completed];
          });
          trace('Resposta concluída', responseData.confidence || '');
        } else if (kind === 'run.failed') {
          failPendingArtifact(event.message);
          terminal = true; setRuntime('Não foi possível concluir'); trace('Execução interrompida', event.message || '', 'error');
          setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', kind: 'failure', failure: chatFailure({message: event.message, status: 503}), prompt: clean}]);
          setInput(clean);
        } else if (kind === 'run.cancelled' || (kind === 'run.completed' && event.status === 'cancelled')) {
          failPendingArtifact('A geração foi interrompida antes de concluir a entrega.');
          terminal = true; setRuntime('Interrompido'); trace('Execução interrompida');
        } else if (kind === 'run.completed') {
          if (!longJobPromise && pendingArtifact && !artifactResolved) failPendingArtifact();
          terminal = true;
          if (!longJobPromise) setRuntime(event.status === 'completed' ? '' : 'Não foi possível concluir');
          trace(longJobPromise ? 'Trabalho aceito' : 'Execução concluída', event.status || '');
        }
      });
      if (longJobPromise) await longJobPromise;
      if (!terminal) throw new Error('A conexão terminou antes da conclusão.');
    } catch (error) {
      if (error?.name === 'AbortError' || controller.signal.aborted) {
        terminal = true;
        setRuntime('Interrompido');
        trace('Execução interrompida');
        return;
      }
      dispatchExecution({type: 'connection.lost', error: error?.message});
      const detail = String(error?.message || '').trim();
      setRuntime('Não foi possível concluir'); trace('Falha na conversa', detail, 'error');
      setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', kind: 'failure', failure: chatFailure(error), prompt: clean}]);
      setInput(clean);
      dispatchExecution({type: 'connection.failed', error: detail});
    } finally {
      if (runStarted) {
        const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
        const worked = {id: uid(), turnId, role: 'assistant', kind: 'worked', seconds};
        setMessages(items => insertWorkedBeforeResult(items, turnId, worked));
      }
      if (streamControllerRef.current === controller) streamControllerRef.current = null;
      runRef.current = null; await loadRecent();
    }
  }, [input, running, queuedTurns.length, artifact, artifactDirty, saving, conversationId, attachments, homeAttachments, context, composerContext, executionMode, fetchArtifact, trace, rememberContext, bootstrap.endpoints.messages, bootstrap.endpoints.artifacts, bootstrap.endpoints.route, loadRecent, releasePreviews, uploadFiles, queueEndpoint]);

  useEffect(() => {
    if (running || drainingQueueRef.current || !queuedTurns.length || contextLoading) return;
    const next = queuedTurns[0];
    drainingQueueRef.current = true;
    setQueuedTurns(items => items.filter(item => item.id !== next.id));
    if (conversationRef.current && next.id) request(`${queueEndpoint(conversationRef.current)}/${encodeURIComponent(next.id)}`, {
      method: 'DELETE', headers: {'X-CSRF-Token': csrf()},
    }).catch(error => trace('Fila será reconciliada depois', error.message, 'error'));
    Promise.resolve(submit(next.prompt, {
      skipAttachments: true,
      fromQueue: true,
      queuedContext: next.context,
      queuedMode: next.executionMode,
    })).finally(() => { drainingQueueRef.current = false; });
  }, [contextLoading, queuedTurns, running, submit, queueEndpoint, trace]);

  const initialPromptRef = useRef(initialQuery.get('auto_send') === '1' ? initialQuery.get('prompt') || '' : '');
  useEffect(() => {
    if (!initialPromptRef.current || running || contextLoading || !contextTransferReady) return;
    const prompt = initialPromptRef.current;
    initialPromptRef.current = '';
    submit(prompt);
  }, [contextLoading, contextTransferReady, running, submit]);

  const stop = useCallback(async () => {
    const runId = runRef.current;
    const longJobId = longJobRef.current;
    if (!runId && !longJobId && !streamControllerRef.current) return;
    setRuntime('Interrompendo');
    dispatchExecution({type: 'cancel.requested'});
    streamControllerRef.current?.abort();
    try {
      if (longJobId) {
        await request(`/workspace/api/v2/long-jobs/${encodeURIComponent(longJobId)}/cancel`, {method: 'POST', headers: {'X-CSRF-Token': csrf()}});
        longJobRef.current = null;
      } else if (runId) await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(runId)}/stop`, {method: 'POST', headers: {'X-CSRF-Token': csrf()}});
    }
    catch (error) { setRuntime('Não foi possível interromper'); trace('Falha ao interromper', error.message, 'error'); }
  }, [bootstrap.endpoints.runs, trace]);

  const decide = useCallback(async (message, approved) => {
    setMessages(items => items.map(item => item.id === message.id ? {...item, actionPending: true, actionError: ''} : item));
    try {
      const runId = message.runId || message.action?.run_id || message.action?.runId;
      if (!runId || !message.action?.step_id) throw new Error('A confirmação expirou. Envie o pedido novamente.');
      const data = await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(runId)}/steps/${encodeURIComponent(message.action.step_id)}/decision`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({approved})});
      const completion = data.step?.output_snapshot?.completion || {};
      const response = data.step?.status === 'completed'
        ? {answer: completion.answer || 'Ação concluída.', blocks: completion.blocks || []}
        : {answer: approved ? 'Ação confirmada.' : 'Ação cancelada.'};
      setMessages(items => items.map(item => item.id === message.id ? {...item, kind: undefined, response} : item));
      if (data.step?.status === 'completed' && completion.activate_context) {
        try {
          const activated = await request(bootstrap.endpoints.context, {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
            body: JSON.stringify(completion.activate_context),
          });
          rememberContext(activated.context || {});
          if (completion.activate_context.project_ref) markProjectUsed(completion.activate_context.project_ref);
        } catch (error) {
          trace('A criação foi concluída, mas o novo contexto ainda não foi selecionado', error.message);
        }
      }
      if (data.step?.status === 'completed' && completion.refresh_context) {
        try { await loadContext(); }
        catch (error) { trace('Contexto será atualizado em seguida', error.message); }
      }
      if (data.step?.status === 'completed' && completion.open_surface?.type === 'brand_identity') {
        try {
          await loadBrandIdentity(completion.open_surface.brand_ref);
          setSurfaceUrl('artifact', '');
        } catch (error) {
          trace('A marca foi criada, mas a ficha não pôde ser aberta agora', error.message);
        }
      }
      if (data.step?.status === 'completed' && completion.open_surface?.type === 'project_profile') {
        try { await loadProjectProfile(completion.open_surface.project_ref); }
        catch (error) { trace('O projeto foi criado, mas a ficha não pôde ser aberta agora', error.message); }
      }
    } catch (error) {
      const detail = String(error?.message || 'Não foi possível concluir esta ação.');
      setMessages(items => items.map(item => item.id === message.id ? {...item, actionPending: false, actionError: detail} : item));
      trace('Falha na ação', detail, 'error');
    }
  }, [bootstrap.endpoints.runs, bootstrap.endpoints.context, trace, loadContext, loadBrandIdentity, loadProjectProfile, rememberContext]);

  const changeArtifact = useCallback(content => {
    artifactEditRevisionRef.current += 1;
    setArtifact(current => current ? {...current, content} : current);
    setArtifactDirty(true);
  }, []);

  const changeArtifactTitle = useCallback(title => {
    artifactEditRevisionRef.current += 1;
    setArtifact(current => current ? {...current, title: String(title || '').slice(0, 180)} : current);
    setArtifactDirty(true);
  }, []);

  const saveArtifact = useCallback(async () => {
    if (!artifact?.id) return false;
    const revision = artifactEditRevisionRef.current;
    setSaving(true);
    try {
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Revisão na conversa'})});
      artifactRef.current = data.artifact;
      if (revision === artifactEditRevisionRef.current) { setArtifact(data.artifact); setArtifactDirty(false); return true; }
      setArtifact(current => current?.id === data.artifact.id ? {...current, current_version:data.artifact.current_version} : current);
      setArtifactDirty(true);
      return false;
    } catch (error) {
      trace(error.status === 409 ? 'Entrega alterada em outra sessão' : 'Falha ao salvar entrega', error.message, 'error');
      return false;
    } finally { setSaving(false); }
  }, [artifact, bootstrap.endpoints.artifacts, conversationId, trace]);

  const saveArtifactToProject = useCallback(async () => {
    if (!artifact?.id || !context.project_ref) return;
    const revision = artifactEditRevisionRef.current;
    setSaving(true);
    try {
      let currentArtifact = artifact;
      if (artifactDirty) {
        const saved = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Rascunho salvo automaticamente'}),
        });
        if (!saved.artifact?.id) throw new Error('O rascunho não pôde ser salvo antes de vincular ao projeto.');
        currentArtifact = saved.artifact;
        if (revision !== artifactEditRevisionRef.current) {
          setArtifact(current => current?.id === saved.artifact.id ? {...current, current_version:saved.artifact.current_version} : current);
          setArtifactDirty(true);
          trace('Documento alterado durante o salvamento', 'Salve a edição mais recente antes de finalizar.');
          return;
        }
        setArtifact(currentArtifact); artifactRef.current = currentArtifact; setArtifactDirty(false);
      }
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/finalize-project`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId, project_ref: context.project_ref, expected_version: currentArtifact.current_version}),
      });
      if (revision === artifactEditRevisionRef.current) { setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false); }
      else { setArtifact(current => current?.id === data.artifact.id ? {...current, current_version:data.artifact.current_version, status:data.artifact.status} : current); setArtifactDirty(true); }
      trace('Documento finalizado e indexado no projeto', data.artifact?.title || 'Documento');
    } catch (error) {
      trace('Falha ao finalizar no projeto', error.message, 'error');
    } finally { setSaving(false); }
  }, [artifact, artifactDirty, bootstrap.endpoints.artifacts, conversationId, context.project_ref, trace]);

  const attachArtifactToProject = useCallback(async () => {
    if (!artifact?.id || !context.project_ref || saving) return;
    setSaving(true);
    try {
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/save-project`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId, project_ref: context.project_ref}),
      });
      setArtifact(data.artifact); artifactRef.current = data.artifact;
      trace('Entrega salva no projeto', data.artifact?.title || 'Entrega');
    } catch (error) { trace('Falha ao salvar no projeto', error.message, 'error'); }
    finally { setSaving(false); }
  }, [artifact, bootstrap.endpoints.artifacts, context.project_ref, conversationId, saving, trace]);

  const publishArtifact = useCallback(async () => {
    if (!artifact?.id || publishing || saving) return;
    const revision = artifactEditRevisionRef.current;
    setPublishing(true);
    try {
      let currentArtifact = artifact;
      if (artifactDirty) {
        const saved = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Rascunho publicado'}),
        });
        currentArtifact = saved.artifact;
        if (revision !== artifactEditRevisionRef.current) {
          setArtifact(current => current?.id === saved.artifact.id ? {...current, current_version:saved.artifact.current_version} : current);
          setArtifactDirty(true);
          trace('Página alterada durante o salvamento', 'Salve a edição mais recente antes de publicar.');
          return;
        }
      }
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(currentArtifact.id)}/publish`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId}),
      });
      const url = data.url || '';
      if (revision === artifactEditRevisionRef.current) {
        setArtifact(data.artifact || currentArtifact);
        artifactRef.current = data.artifact || currentArtifact;
        setArtifactDirty(false);
      } else {
        setArtifact(current => current?.id === currentArtifact.id ? {...current, current_version:currentArtifact.current_version, status:'published'} : current);
        setArtifactDirty(true);
      }
      setPublishedUrl(url);
      trace('Página publicada', url ? 'O link está disponível na entrega para abrir ou copiar.' : 'A página foi publicada.');
    } catch (error) {
      trace('Falha ao publicar página', error.message, 'error');
    } finally { setPublishing(false); }
  }, [artifact, artifactDirty, bootstrap.endpoints.artifacts, conversationId, publishing, saving, trace]);

  const copyPublishedUrl = useCallback(async () => {
    if (!artifact?.id || artifact.status !== 'published') return;
    const url = publishedUrl || `${window.location.origin}/public/cadu/artifacts/${encodeURIComponent(artifact.id)}`;
    try {
      const copied = await copyText(url);
      trace('Link da página', copied ? 'Copiado para a área de transferência.' : 'Selecione o link na entrega para copiar.');
    } catch (_) {
      trace('Link da página', 'Selecione o link na entrega para copiar.');
    }
  }, [artifact, publishedUrl, trace]);

  const unpublishArtifact = useCallback(async () => {
    if (!artifact?.id || publishing || saving) return;
    setPublishing(true);
    try {
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/unpublish`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId}),
      });
      setArtifact(data.artifact || {...artifact, status: 'draft'});
      artifactRef.current = data.artifact || {...artifact, status: 'draft'};
      setPublishedUrl('');
      trace('Página retirada da publicação', 'A entrega continua salva e pode ser publicada novamente.');
    } catch (error) {
      trace('Falha ao retirar página da publicação', error.message, 'error');
    } finally { setPublishing(false); }
  }, [artifact, bootstrap.endpoints.artifacts, conversationId, publishing, saving, trace]);

  useEffect(() => {
    if (!artifact?.id || !artifactDirty || saving) return undefined;
    const timer = window.setTimeout(() => saveArtifact(), 900);
    return () => window.clearTimeout(timer);
  }, [artifact?.id, artifactDirty, saving, saveArtifact]);

  const loadVersions = useCallback(async () => {
    if (!artifact?.id) return;
    try { const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/versions`); setVersions(data.versions || []); }
    catch (error) { setVersions([]); trace('Falha ao carregar versões', error.message, 'error'); }
  }, [artifact?.id, bootstrap.endpoints.artifacts, trace]);

  const restoreVersion = useCallback(async version => {
    if (!artifact?.id || (artifactDirty && !(await confirmDiscard(false)))) return;
    try {
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/versions/${version}/restore`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version})});
      setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false);
    } catch (error) { trace('Falha ao restaurar versão', error.message, 'error'); }
  }, [artifact, artifactDirty, confirmDiscard, bootstrap.endpoints.artifacts, conversationId, trace]);

  const openResource = useCallback(async item => {
    if (!item || !(await confirmDiscard(false))) return false;
    if (item.artifact_id) {
      try { await fetchArtifact(item.artifact_id); }
      catch (error) { trace('Não foi possível abrir a entrega', error.message, 'error'); return false; }
      return true;
    }
    const kind = String(item.kind || '').toLowerCase();
    const resource = ['image', 'logo'].includes(kind)
      ? {tabKey: `resource:${item.id || item.url}`, type: 'image', title: item.title || 'Imagem do Studio', content: {url: item.url, alt: item.title || 'Imagem do Studio', source: item.source || 'studio'}}
      : kind === 'source_collection' ? {tabKey: `resource:${item.id || 'sources'}`, type: 'library', title: item.title || 'Fontes da resposta', content: {groups: [{id: 'sources', title: 'Fontes consultadas', layout: 'list', items: (item.items || []).map((source, index) => ({...source, id: source.id || `source-${index}`, kind: 'link', detail: sourceDomainLabel(source.url)}))}]}}
      : ['link', 'website', 'webpage'].includes(kind) && item.url ? {tabKey: `resource:${item.id || item.url}`, type: 'link_reader', title: item.title || 'Link externo', content: item} : {tabKey: `resource:${item.id || item.title}`, type: 'resource', title: item.title || 'Arquivo', content: item};
    setArtifact(resource); artifactRef.current = resource;
    setArtifactDirty(false); setArtifactOpen(true);
    return true;
  }, [confirmDiscard, fetchArtifact, trace]);

  const showResource = useCallback(async item => {
    const resourceRef = String(item?.resourceRef || '');
    const routedItem = resourceRef && !item.libraryRef ? {...item, libraryRef: resourceRef.startsWith('resource:') ? resourceRef : `resource:${resourceRef}`, project_ref: item.project_ref || item.projectRef || context?.project_ref || ''} : item;
    if (!(await openResource(routedItem))) return;
    setLibraryOpen(false);
    if (layout !== 'desktop') setHistoryOpen(false);
    setSurfaceUrl('artifact', routedItem.artifact_id || '', false, routedItem.artifact_id ? null : routedItem);
  }, [context?.project_ref, layout, openResource]);

  const loadResourceReference = useCallback(async (libraryRef, projectRef = '') => {
    const endpoint = bootstrap.endpoints?.studioLibrary || '/workspace/api/v2/studio/library';
    const suffix = projectRef ? `?project_ref=${encodeURIComponent(projectRef)}` : '';
    const data = await request(`${endpoint}${suffix}`);
    const item = findLibraryItem(data, libraryRef);
    if (!item) throw new Error('O recurso não está mais disponível nesta biblioteca.');
    const project = projects.find(candidate => String(candidate.ref || candidate.projectRef || '') === String(item.project_ref || projectRef));
    return openResource({...item, project_href: project?.href || project?.url || bootstrap.urls?.projects || '', project_link_label: project?.href || project?.url ? 'Ver no projeto' : 'Abrir projetos'});
  }, [bootstrap.endpoints?.studioLibrary, bootstrap.urls?.projects, openResource, projects]);

  const openLibrary = useCallback(async (syncUrl = true) => {
    const libraryProjectRef = String(context?.project_ref || '');
    setLibraryOpen(true);
    setArtifactOpen(false);
    if (layout !== 'desktop') setHistoryOpen(false);
    if (syncUrl) setSurfaceUrl('library');
    setLibrary({loading: true, error: '', groups: []});
    try {
      const endpoint = bootstrap.endpoints?.studioLibrary || '/workspace/api/v2/studio/library';
      const suffix = libraryProjectRef ? `?project_ref=${encodeURIComponent(libraryProjectRef)}` : '';
      const data = await request(`${endpoint}${suffix}`);
      const project = projects.find(candidate => String(candidate.ref || candidate.projectRef || '') === String(data.project_ref || libraryProjectRef));
      const projectHref = project?.href || project?.url || bootstrap.urls?.projects || '';
      const groups = libraryGroups(data).map(group => group.id === 'references' ? {...group, items: group.items.map(item => ({...item, project_href: projectHref, project_link_label: project?.href || project?.url ? 'Ver no projeto' : 'Abrir projetos'}))} : group);
      setLibrary({loading: false, error: '', groups});
    } catch (error) {
      setLibrary({loading: false, error: error.message || 'Biblioteca indisponível.', groups: []});
    }
  }, [bootstrap.endpoints, bootstrap.urls?.projects, context?.project_ref, layout, projects]);

  const closeSurface = useCallback(() => {
    setLibraryOpen(false);
    setArtifactOpen(false);
    if (layout !== 'desktop') setHistoryOpen(false);
    setSurfaceUrl('conversation', '', true);
  }, [layout]);

  const showArtifact = useCallback(async item => {
    setLibraryOpen(false);
    if (layout !== 'desktop') setHistoryOpen(false);
    if (item?.id && item.id !== artifactRef.current?.id) {
      try { await fetchArtifact(item.id); }
      catch (error) { setArtifact({tabKey: `failed:${item.id}`, type: 'document', title: 'Entrega indisponível', failed: true, error: error.message}); setArtifactOpen(true); }
    }
    else setArtifactOpen(true);
    setSurfaceUrl('artifact', item?.id || artifactRef.current?.id || '');
  }, [fetchArtifact, layout]);

  const openDockBrand = useCallback(item => {
    const brandRef = item?.brandRef || (item?.id ? `studio:${item.id}` : '');
    if (brandRef) changeBrand(brandRef);
  }, [changeBrand]);

  const openDockItem = useCallback(item => {
    const kind = String(item?.kind || item?.type || '').toLowerCase();
    const resourceKinds = new Set(['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link']);
    if (item?.resourceRef || resourceKinds.has(kind)) {
      showResource(item);
      return;
    }
    const projectRef = item?.projectRef || item?.ref || (item?.id ? `ci:${item.id}` : '');
    if (projectRef) changeProject(projectRef, {showHistory: true});
  }, [changeProject, showResource]);

  const revisitFailedPrompt = useCallback(prompt => {
    setInput(prompt || '');
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);
  const openHistory = useCallback(() => {
    if (layout !== 'desktop') { setLibraryOpen(false); setArtifactOpen(false); }
    setHistoryOpen(true);
    if (layout !== 'desktop') setSurfaceUrl('navigation');
  }, [layout]);
  const closeHistory = useCallback(() => {
    setHistoryOpen(false);
    if (layout !== 'desktop') setSurfaceUrl('conversation', '', true);
  }, [layout]);
  useEffect(() => {
    const restoreSurface = event => {
      const params = new URLSearchParams(window.location.search);
      const surface = params.get('surface');
      if (layout !== 'desktop') setHistoryOpen(surface === 'navigation');
      if (surface === 'library') openLibrary(false);
      else setLibraryOpen(false);
      if (surface === 'artifact') {
        const id = params.get('artifact_id');
        const libraryRef = params.get('resource_ref');
        if (id && id !== artifactRef.current?.id) fetchArtifact(id).catch(error => { setArtifact({tabKey: `failed:${id}`, type: 'document', title: 'Entrega indisponível', failed: true, error: error.message}); setArtifactOpen(true); });
        else if (libraryRef) loadResourceReference(libraryRef, params.get('resource_project_ref') || '').catch(error => { setArtifact({tabKey: `failed:${libraryRef}`, type: 'resource', title: 'Recurso indisponível', failed: true, error: error.message}); setArtifactOpen(true); });
        else if (event.state?.resource) openResource(event.state.resource);
        else if (artifactRef.current) setArtifactOpen(true);
        else { setArtifactOpen(false); setSurfaceUrl('conversation', '', true); }
      } else setArtifactOpen(false);
    };
    window.addEventListener('popstate', restoreSurface);
    return () => window.removeEventListener('popstate', restoreSurface);
  }, [fetchArtifact, layout, loadResourceReference, openLibrary, openResource, trace]);
  const initialResourceRef = useRef(new URLSearchParams(window.location.search).get('resource_ref') || '');
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('surface') === 'navigation') setHistoryOpen(true);
    if (params.get('surface') === 'library') openLibrary(false);
    const artifactId = params.get('surface') === 'artifact' ? params.get('artifact_id') : '';
    const libraryRef = params.get('surface') === 'artifact' ? params.get('resource_ref') : '';
    if (artifactId && artifactId !== artifactRef.current?.id) fetchArtifact(artifactId).catch(error => { setArtifact({tabKey: `failed:${artifactId}`, type: 'document', title: 'Entrega indisponível', failed: true, error: error.message}); setArtifactOpen(true); });
    else if (libraryRef && initialResourceRef.current) {
      initialResourceRef.current = '';
      loadResourceReference(libraryRef, params.get('resource_project_ref') || '').catch(error => { setArtifact({tabKey: `failed:${libraryRef}`, type: 'resource', title: 'Recurso indisponível', failed: true, error: error.message}); setArtifactOpen(true); });
    }
    else if (params.get('surface') === 'artifact' && !libraryRef && window.history.state?.resource) openResource(window.history.state.resource);
    else if (params.get('surface') === 'artifact' && !libraryRef && !window.history.state?.resource && !artifactRef.current) setSurfaceUrl('conversation', '', true);
  }, [fetchArtifact, loadResourceReference, openLibrary, openResource, trace]);
  const persistQueuedTurns = useCallback(async next => {
    setQueuedTurns(next);
    if (!conversationRef.current) return;
    try {
      const data = await request(queueEndpoint(conversationRef.current), {
        method: 'PUT', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({items: next.map(item => ({id: item.id, prompt: item.prompt}))}),
      });
      setQueuedTurns((data.items || next).map(item => ({...item, executionMode: item.execution_mode || item.executionMode, context: item.selected_context || item.context})));
    } catch (error) { trace('Não foi possível atualizar a fila', error.message, 'error'); }
  }, [queueEndpoint, trace]);
  const removeQueuedTurn = useCallback(async id => {
    const next = queuedTurns.filter(item => item.id !== id);
    setQueuedTurns(next);
    if (!conversationRef.current) return;
    try {
      await request(`${queueEndpoint(conversationRef.current)}/${encodeURIComponent(id)}`, {method: 'DELETE', headers: {'X-CSRF-Token': csrf()}});
    } catch (error) { trace('Não foi possível remover da fila', error.message, 'error'); }
  }, [queueEndpoint, queuedTurns, trace]);

  const activeProjectRef = String(context?.project_ref || '');
  const activeBrandRef = String(context?.brand_ref || '');
  const starterProject = projects.find(item => String(item.ref || item.projectRef || item.id) === activeProjectRef);
  const starterBrand = brands.find(item => String(item.ref || item.brandRef || (item.id ? `studio:${item.id}` : '')) === activeBrandRef);
  const activeConversationState = conversations.find(item => String(item.id) === String(conversationId));
  const dockItems = conversationDockItems;
  const sharedDockItems = dockItems.map(item => ({
    ...item,
    active: item.kind === 'project' && String(item.projectRef || '') === activeProjectRef || item.kind === 'brand' && String(item.brandRef || (item.id ? `studio:${item.id}` : '')) === activeBrandRef,
  }));
  const dockShortcutEndpoint = bootstrap.endpoints?.dockShortcuts || '/workspace/api/dock/shortcuts';
  const createDockShortcut = useCallback(async item => {
    const isResource = Boolean(item?.resourceRef) || ['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link'].includes(String(item?.kind || '').toLowerCase());
    const kind = item?.kind === 'brand' ? 'brand' : isResource ? 'resource' : 'project';
    const targetRef = kind === 'brand' ? item.id : kind === 'resource' ? item.resourceRef || item.id : item.projectRef || item.id;
    if (!targetRef) throw new Error('Não foi possível identificar este atalho.');
    const data = await request(dockShortcutEndpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
      body: JSON.stringify({shortcut_type: kind, target_ref: targetRef, project_ref: item.projectRef || null, brand_ref: item.brandRef || null}),
    });
    if (!data.shortcut?.id) throw new Error('Não foi possível salvar este atalho.');
    return {...item, shortcutId: data.shortcut?.id, pinned: true};
  }, [dockShortcutEndpoint]);
  const reorderDockShortcuts = useCallback(async next => {
    const before = conversationDockItems;
    setConversationDockItems(next);
    try {
      const explicit = [];
      for (const item of next) explicit.push(item.shortcutId ? item : await createDockShortcut(item));
      setConversationDockItems(explicit);
      const current = await request(dockShortcutEndpoint);
      const allIds = Array.isArray(current.shortcuts) ? current.shortcuts.map(item => item.id) : [];
      await request(`${dockShortcutEndpoint}/order`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({ids: completeDockOrder(explicit.map(item => item.shortcutId), allIds)}),
      });
    } catch (error) {
      setConversationDockItems(before);
      trace('Falha ao ordenar atalhos', error.message, 'error');
    }
  }, [conversationDockItems, createDockShortcut, dockShortcutEndpoint, trace]);
  const addDroppedDockItem = useCallback(async payload => {
    if (!payload || payload.dockSource === 'dock') return;
    const payloadKind = String(payload.type || payload.kind || '').toLowerCase();
    const isResource = Boolean(payload.resourceRef) || payloadKind === 'resource' || ['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link'].includes(payloadKind);
    const targetProject = String(payload.projectRef || payload.id || '');
    const project = projects.find(item => [item.id, item.ref, item.projectRef, item.id && `ci:${item.id}`].some(ref => String(ref || '') === targetProject));
    const brand = brands.find(item => String(item.id) === String(payload.id) || String(item.brandRef || `studio:${item.id}`) === String(payload.brandRef));
    const candidate = isResource
      ? {...payload, kind: 'resource', id: payload.id || `resource:${payload.resourceRef}`, title: payload.title || 'Recurso'}
      : payloadKind === 'brand'
        ? brand && {...brand, kind: 'brand', brandRef: brand.brandRef || `studio:${brand.id}`, title: brand.title || brand.name}
        : project && {...project, kind: 'project', projectRef: project.projectRef || project.ref || `ci:${project.id}`, title: project.title || project.name};
    if (!candidate || !['brand', 'project', 'resource'].includes(candidate.kind)) {
      trace('Atalho não adicionado', 'A dock aceita apenas marcas, projetos e recursos.', 'error');
      return;
    }
    if (conversationDockItems.some(item => item.shortcutId && (item.id === candidate.id || item.projectRef === candidate.projectRef || item.resourceRef === candidate.resourceRef))) return;
    try {
      const item = await createDockShortcut(candidate);
      setConversationDockItems(current => [...current, item]);
    } catch (error) { trace('Falha ao fixar atalho', error.message, 'error'); }
  }, [brands, conversationDockItems, createDockShortcut, projects, trace]);
  return <div className="cadu-ds-home-shell cv-conversations-shell" data-layout={layout} data-surface={activeSurface} data-artifact-side={artifactSide} data-keyboard-open={keyboardOpen ? 'true' : 'false'} style={{'--cv-artifact-width': `${artifactWidth}%`}}>
    <main className="cadu-ds-home-main">
      <div onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} className="cadu-ds-home-workarea cv-conversations-workarea">
        <CaduDock bootstrap={bootstrap} sharedDock={bootstrap.sharedDock} conversationMode logo={bootstrap.caduMark || bootstrap.logo} homeUrl={bootstrap.urls?.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={projects} brands={brands} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={brands} resources={projects} shortcutItems={sharedDockItems} onDropItem={addDroppedDockItem} onReorderShortcuts={reorderDockShortcuts} onShortcutAdded={(_, next) => setConversationDockItems(next)} onShortcutRemoved={(_, next) => setConversationDockItems(next)} usagePercent={bootstrap.usagePercent} onNewConversation={newConversation} onOpenBrand={openDockBrand} onOpenResource={openDockItem} onOpenUsage={() => setAccountOpen(true)}/>
          <Sidebar conversations={conversations} projects={projects} brands={brands} activeProjectRef={activeProjectRef} navUrls={bootstrap.urls} activeId={conversationId} onOpen={openConversation} onOpenLibrary={openLibrary} onNewConversation={newConversation} onProjectChange={ref => changeProject(ref, {showHistory: false})} onOrganize={organizeConversation} onConversationAction={conversationAction} open={historyOpen} onClose={closeHistory} loading={historyLoading} openingId={openingId}/>
        {dropActive && createPortal(<div className="cv-drop-overlay" role="status" aria-live="polite"><div className="cv-drop-overlay-card"><Icon name="file" size={28}/><strong>Solte o arquivo para anexar</strong><span>PDF, documento, planilha ou imagem</span></div></div>, document.body)}
        <div className="cv-conversation-stage cv-relative cv-flex cv-min-w-0 cv-flex-1">
          <Conversation inactive={layout === 'phone' && activeSurface !== 'conversation'} layout={layout} viewport={viewport} shellV2={shellV2} conversationId={conversationId} title={title} context={context} projects={projects} brands={brands} starterProject={starterProject} starterBrand={starterBrand} starterHome={bootstrap.home} contextLoading={contextLoading} runtime={runtime} diagnostics={diagnostics} messages={messages} input={input} setInput={setInput} onSubmit={submit} attachments={attachments} onRemoveAttachment={removeAttachment} onAttachmentPurposeChange={setAttachmentPurpose} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={setAttachmentDestination} executionMode={executionMode} onExecutionModeChange={setExecutionMode} running={running} onStop={stop} onPrompt={(prompt, selected, options = {}) => { if (options.submit && prompt) { submit(prompt); return; } if (prompt) setInput(prompt); if (selected) { setComposerContext(selected); focusComposer(); } }} onOpenArtifact={showArtifact} onOpenResource={showResource} onDecision={decide} onRevisitPrompt={revisitFailedPrompt} creditsUrl={bootstrap.urls?.credits || ''} onOpenHistory={openHistory} historyOpen={historyOpen} artifactOpen={artifactOpen} composerContext={composerContext} onClearContext={() => setComposerContext(null)} onAttach={addFiles} onContextDrop={dropContext} onProjectChange={ref => changeProject(ref, {showHistory: false})} queuedTurns={queuedTurns} onUpdateQueuedTurn={(id, prompt) => persistQueuedTurns(updateQueued(queuedTurns, id, prompt))} onRemoveQueuedTurn={removeQueuedTurn} onMoveQueuedTurn={(id, direction) => persistQueuedTurns(moveQueued(queuedTurns, id, direction))} onOpenLibrary={openLibrary} automation={activeConversationState}/>
          {libraryOpen && <LibraryView library={library} onClose={closeSurface} onOpenResource={showResource}/>}
          {artifactOpen && layout === 'desktop' && <div className="cv-artifact-resizer" role="separator" aria-label="Ajustar largura da entrega" aria-orientation="vertical" tabIndex={0} aria-valuemin={30} aria-valuemax={60} aria-valuenow={artifactWidth} onKeyDown={event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); setArtifactWidth(value => Math.max(30, Math.min(60, value + (event.key === 'ArrowLeft' ? (artifactSide === 'right' ? 2 : -2) : artifactSide === 'right' ? -2 : 2)))); } }} onPointerDown={event => {
            event.currentTarget.setPointerCapture(event.pointerId);
            const stage = event.currentTarget.parentElement.getBoundingClientRect();
            const move = pointer => setArtifactWidth(Math.max(30, Math.min(60, Math.round((artifactSide === 'right' ? stage.right - pointer.clientX : pointer.clientX - stage.left) / stage.width * 100))));
            const stop = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', stop); };
            window.addEventListener('pointermove', move);
            window.addEventListener('pointerup', stop, {once: true});
          }}/>}
          {artifactOpen && <ArtifactPane
            artifact={artifact} mobile={layout === 'phone'} dirty={artifactDirty} saving={saving} publishing={publishing} publishedUrl={publishedUrl}
            tabs={artifactTabs} activeTabKey={artifactKey(artifact)}
            onSelectTab={async next => {
              if (artifactDirty && !(await saveArtifact())) return;
              setArtifact(next); artifactRef.current = next; setArtifactDirty(false); setPublishedUrl('');
              setSurfaceUrl('artifact', next.id || '', true);
            }}
            onCloseTab={async key => {
              if (key === artifactKey(artifact) && artifactDirty && !(await confirmDiscard(false))) return;
              const remaining = artifactTabs.filter(item => artifactKey(item) !== key);
              setArtifactTabs(remaining);
              if (key === artifactKey(artifact)) {
                const next = remaining[remaining.length - 1] || null;
                setArtifact(next); artifactRef.current = next; setArtifactDirty(false); setPublishedUrl('');
                if (!next) closeSurface();
                else setSurfaceUrl('artifact', next.id || '', true);
              }
            }}
            onCloseOtherTabs={async key => {
              const selected = artifactTabs.find(item => artifactKey(item) === key);
              if (!selected) return;
              if (key !== artifactKey(artifact) && artifactDirty && !(await confirmDiscard(false))) return;
              setArtifactTabs([selected]);
              setArtifact(selected); artifactRef.current = selected; setArtifactDirty(false); setPublishedUrl('');
              setSurfaceUrl('artifact', selected.id || '', true);
            }}
            onCloseAllTabs={async () => {
              if (artifactDirty && !(await confirmDiscard(false))) return;
              setArtifactTabs([]); setArtifact(null); artifactRef.current = null; setArtifactDirty(false); setPublishedUrl(''); closeSurface();
            }}
            side={artifactSide} onSideChange={changeArtifactSide}
            onChange={changeArtifact} onTitleChange={changeArtifactTitle} projectRef={activeProjectRef}
            studioEditorUrl={bootstrap.urls?.studioEditor}
            onSaveToProject={saveArtifactToProject} onAttachToProject={attachArtifactToProject} onPublish={publishArtifact} onCopyPublishedUrl={copyPublishedUrl} onUnpublish={unpublishArtifact} onClose={closeSurface}
            onRequestSummary={url => submit(`Abra e resuma este site público em um texto editável: ${url}`, {skipAttachments: true})}
            onSaveReference={async url => {
              if (activeProjectRef) return submit(`Adicione este link ${url} ao projeto como referência, sem abrir, ler ou indexar.`, {skipAttachments: true});
              try {
                const data = await request(bootstrap.endpoints.artifacts, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({conversation_id: conversationId, surface: 'conversations', type: 'link_reader', title: artifact?.title || 'Link externo', content: {...(artifact?.content || {}), url, access_mode: 'referência pessoal'}})});
                setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false); trace('Referência salva no espaço pessoal', data.artifact?.title || 'Link externo');
              } catch (error) { trace('Falha ao salvar referência', error.message, 'error'); }
            }}
                onRequestMeetingPlan={url => submit(`Prepare uma pauta de reunião para este link: ${url}`, {skipAttachments: true})}
                onOrganizeImage={async item => {
                  const imageUrl = item?.content?.url || item?.content?.image_url || item?.content?.src || '';
                  const imageName = item?.title || item?.content?.filename || 'imagem';
                  const content = item?.content || {};
                  try {
                    const data = await request('/workspace/api/v2/images/organize', {
                      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
                      body: JSON.stringify({id: content.id || item?.id, source_id: content.source_id || content.id || item?.id,
                        source: content.source || content.source_system || '', title: imageName, url: imageUrl,
                        project_ref: activeProjectRef || null, brand_ref: activeBrandRef || null}),
                    });
                    const next = {...item, title: data.title || imageName, content: {...content, filename: data.title || imageName, visual_summary: data.summary || ''}};
                    setArtifact(next); artifactRef.current = next;
                    setArtifactTabs(items => items.map(tab => artifactKey(tab) === artifactKey(item) ? next : tab));
                    trace('Imagem organizada', data.renamed ? 'Nome e resumo atualizados por OCR.' : 'Resumo atualizado; o nome original foi preservado.');
                  } catch (error) { trace('Não foi possível organizar a imagem', error.message, 'error'); }
                }}
                onSave={saveArtifact} onLoadVersions={loadVersions} versions={versions} onRestoreVersion={restoreVersion}
                onOpenResource={showResource}
          />}
        </div>
        <ConfirmDialog request={discardRequest} onResolve={resolveDiscard}/>
      </div>
      <nav className="cv-tablet-dock" aria-label="Navegação do chat no tablet">
        <button type="button" onClick={closeSurface} aria-current={activeSurface === 'conversation' ? 'page' : undefined}><Icon name="newChat" size={18}/><span>Conversa</span></button>
        <button type="button" onClick={openHistory} aria-current={activeSurface === 'navigation' ? 'page' : undefined}><Icon name="menu" size={18}/><span>Recentes</span></button>
        <button type="button" onClick={newConversation}><Icon name="plus" size={18}/><span>Novo chat</span></button>
        <button type="button" onClick={openLibrary} aria-current={activeSurface === 'library' ? 'page' : undefined}><Icon name="file" size={18}/><span>Biblioteca</span></button>
        {bootstrap.urls?.home && <a href={bootstrap.urls.home} onClick={async event => {
          if (!artifactDirty && !attachments.length) return;
          event.preventDefault();
          if (await confirmDiscard()) window.location.assign(bootstrap.urls.home);
        }}><Icon name="home" size={18}/><span>Início</span></a>}
      </nav>
    </main>
  </div>;
}
