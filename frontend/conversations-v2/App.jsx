import React, {useCallback, useEffect, useReducer, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Sidebar} from './components/Sidebar';
import {Conversation} from './components/Conversation';
import {ArtifactPane} from './components/ArtifactPane';
import {ConfirmDialog} from './components/ConfirmDialog';
import {csrf, request, streamEvents, uid} from './lib/api';
import {chatFailure} from './lib/errorModel.mjs';
import {insertWorkedBeforeResult, normalizeAnswerText, reconcileCompletedResponse} from './lib/responseModel.mjs';
import {attachmentIssues, attachmentSubmissionMessage, createStagedAttachment, MAX_ATTACHMENTS, validateAttachment} from './lib/attachmentModel.mjs';
import {recentConversations, restoreConversationMessages} from './lib/historyModel.mjs';
import {brandContextPayload, conversationPayload, projectContextPayload} from './lib/contextModel.mjs';
import {uploadAttachments} from './lib/attachmentUpload.mjs';
import {enqueue, MAX_QUEUED_TURNS, moveQueued, readQueue, updateQueued, writeQueue} from './lib/executionQueue.mjs';
import {acceptAgentEvent} from './lib/agentEvents.mjs';
import {executionReducer, initialExecutionState, isExecutionActive} from './lib/executionState.mjs';
import {Icon} from './lib/icons';
import {CaduDock, WorkspaceAccountMenu} from '../cadu-design-system';

const emptyTitle = 'Novo chat';
const ARTIFACT_SIDE_COOKIE = 'cadu-artifact-side';
const artifactKey = item => String(item?.tabKey || item?.id || '');

function readCookie(key) {
  return document.cookie.match(new RegExp(`(?:^|; )${key}=([^;]+)`))?.[1] || '';
}

function writeCookie(key, value) {
  document.cookie = `${key}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`;
}

async function copyText(value) {
  if (!value) return false;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return true;
  }
  const field = document.createElement('textarea');
  field.value = value;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.appendChild(field);
  field.select();
  let copied = false;
  try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
  field.remove();
  return copied;
}

export default function App({bootstrap}) {
  const initialQuery = new URLSearchParams(window.location.search);
  const [context, setContext] = useState({});
  const [projects, setProjects] = useState([]);
  const [brands, setBrands] = useState(() => bootstrap.brands || []);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [title, setTitle] = useState(emptyTitle);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(() => initialQuery.get('auto_send') === '1' ? initialQuery.get('prompt') || '' : '');
  const [homeAttachments, setHomeAttachments] = useState(() => {
    try {
      const raw = sessionStorage.getItem('cadu:home-pending-attachments');
      sessionStorage.removeItem('cadu:home-pending-attachments');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter(item => item?.id) : [];
    } catch (_) { return []; }
  });
  const [executionMode, setExecutionMode] = useState(() => initialQuery.get('mode') || 'analysis');
  const [composerContext, setComposerContext] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [attachmentDestination, setAttachmentDestination] = useState('conversation');
  const [artifact, setArtifact] = useState(null);
  const [artifactTabs, setArtifactTabs] = useState([]);
  const [artifactOpen, setArtifactOpen] = useState(false);
  const [artifactSide, setArtifactSide] = useState(() => readCookie(ARTIFACT_SIDE_COOKIE) === 'left' ? 'left' : 'right');
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
  const [historyOpen, setHistoryOpen] = useState(() => !window.matchMedia('(max-width: 900px)').matches);
  const [accountOpen, setAccountOpen] = useState(false);
  const [conversationDockItems, setConversationDockItems] = useState(() => bootstrap.dock?.items || []);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
  const [openingId, setOpeningId] = useState(null);
  const [discardRequest, setDiscardRequest] = useState(null);
  const [dropActive, setDropActive] = useState(false);
  const conversationRef = useRef(null);
  const artifactRef = useRef(null);
  useEffect(() => {
    if (!artifact?.id) return;
    const saved = readCookie(`${ARTIFACT_SIDE_COOKIE}:${artifact.id}`) || readCookie(ARTIFACT_SIDE_COOKIE);
    setArtifactSide(saved === 'left' ? 'left' : 'right');
  }, [artifact?.id]);
  useEffect(() => { if (artifactOpen) setHistoryOpen(false); }, [artifactOpen]);
  const changeArtifactSide = useCallback(side => {
    const next = side === 'left' ? 'left' : 'right';
    setArtifactSide(next);
    writeCookie(ARTIFACT_SIDE_COOKIE, next);
    if (artifact?.id) writeCookie(`${ARTIFACT_SIDE_COOKIE}:${artifact.id}`, next);
  }, [artifact?.id]);
  const runRef = useRef(null);
  const longJobRef = useRef(null);
  const streamControllerRef = useRef(null);
  const recoveryTimerRef = useRef(null);
  const runStartedRef = useRef(0);
  const drainingQueueRef = useRef(false);
  const discardResolverRef = useRef(null);
  const dragDepthRef = useRef(0);

  useEffect(() => {
    // Nested drop targets (notably the composer) stop propagation after they
    // accept the file. Capture the terminal browser events first so the
    // full-screen affordance never remains over an attachment that was added.
    const closeFileDrop = () => {
      dragDepthRef.current = 0;
      setDropActive(false);
    };
    window.addEventListener('drop', closeFileDrop, true);
    window.addEventListener('dragend', closeFileDrop, true);
    window.addEventListener('blur', closeFileDrop);
    return () => {
      window.removeEventListener('drop', closeFileDrop, true);
      window.removeEventListener('dragend', closeFileDrop, true);
      window.removeEventListener('blur', closeFileDrop);
    };
  }, []);
  useEffect(() => () => {
    streamControllerRef.current?.abort();
    if (recoveryTimerRef.current) window.clearTimeout(recoveryTimerRef.current);
  }, []);

  const rememberContext = useCallback(next => {
    setContext(next || {});
    try {
      if (next?.project_ref || next?.brand_ref) localStorage.setItem('cadu:workspace-chat-context', JSON.stringify(next));
      else localStorage.removeItem('cadu:workspace-chat-context');
    } catch (_) { /* storage can be unavailable in private browsing */ }
  }, []);

  useEffect(() => { conversationRef.current = conversationId; }, [conversationId]);
  useEffect(() => { artifactRef.current = artifact; }, [artifact]);
  useEffect(() => {
    const key = artifactKey(artifact);
    if (!key) return;
    setArtifactTabs(items => {
      const existing = items.findIndex(item => artifactKey(item) === key);
      return existing >= 0 ? items.map((item, index) => index === existing ? artifact : item) : [...items, artifact];
    });
  }, [artifact]);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 900px)');
    const adaptHistory = event => {
      if (event.matches) setHistoryOpen(false);
      else if (!conversationRef.current) setHistoryOpen(true);
    };
    if (media.addEventListener) media.addEventListener('change', adaptHistory);
    else media.addListener(adaptHistory);
    return () => {
      if (media.removeEventListener) media.removeEventListener('change', adaptHistory);
      else media.removeListener(adaptHistory);
    };
  }, []);

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
      const data = await request(bootstrap.endpoints.history);
      setConversations(recentConversations(data.conversations, 500));
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
      setProjects(current => (data.entities || []).filter(item => item.kind === 'project').map(item => ({
        ...item,
        ...(current.find(existing => (existing.ref || existing.projectRef || existing.id) === item.ref) || {}),
      })));
      setBrands(current => {
        const fromContext = (data.entities || []).filter(item => item.kind === 'brand').map(item => ({
          ...item, logoUrl: item.logo_url, visualInitials: item.name, visualColor: item.color || item.visualColor || '#176b5e',
        }));
        return fromContext.map(item => ({...item, ...(current.find(existing => (existing.ref || existing.brandRef) === item.ref) || {})}));
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

  useEffect(() => { loadContext(); loadRecent(); }, [loadContext, loadRecent]);
  useEffect(() => {
    if (!historyOpen) return undefined;
    const interval = window.setInterval(loadRecent, conversations.some(item => item.running) ? 4000 : 12000);
    return () => window.clearInterval(interval);
  }, [conversations, historyOpen, loadRecent]);

  const confirmDiscard = useCallback((includeAttachments = true) => {
    const hasAttachments = includeAttachments && attachments.length > 0;
    if (!artifactDirty && !hasAttachments) return Promise.resolve(true);
    const copy = artifactDirty && hasAttachments ? 'O artefato e os anexos preparados ainda não foram salvos.'
      : artifactDirty ? 'O artefato tem alterações que ainda não foram salvas.'
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
    setArtifact(null); setArtifactTabs([]); artifactRef.current = null; setArtifactOpen(false); setArtifactDirty(false); setPublishedUrl('');
    setDiagnostics([]); setRuntime(''); runRef.current = null;
    setQueuedTurns([]);
  }, [releasePreviews]);

  const focusComposer = useCallback(() => {
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);

  const newConversation = useCallback(async () => {
    if (running) return;
    reset();
    setHistoryOpen(false);
    focusComposer();
  }, [running, reset, focusComposer]);

  const openConversation = useCallback(async (id, conversationTitle) => {
    if (running) return;
    setOpeningId(id);
    setRuntime('Abrindo conversa');
    try {
      const data = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}/messages`);
      setConversationId(id); conversationRef.current = id;
      try {
        const queued = await request(queueEndpoint(id));
        setQueuedTurns((queued.items || []).map(item => ({...item, executionMode: item.execution_mode, context: item.selected_context})));
      } catch (_) { setQueuedTurns(readQueue(id)); }
      setTitle(conversationTitle || 'Conversa');
      if (data.context) setContext(data.context);
      setAttachments(items => { releasePreviews(items); return []; }); setComposerContext(null); setArtifact(null); setArtifactTabs([]); artifactRef.current = null; setArtifactDirty(false); setPublishedUrl(''); setArtifactOpen(false);
      const {messages: restored, selectedContext: restoredContext, lastArtifact} = restoreConversationMessages(data.messages, uid);
      setMessages(restored);
      setComposerContext(restoredContext);
      if (lastArtifact) await fetchArtifact(lastArtifact);
      const active = await request(`/workspace/api/v2/conversations/${encodeURIComponent(id)}/active-run`).catch(() => ({run: null}));
      if (active.run?.id) {
        const pendingActions = (active.run.actions || []).map(action => ({
          id: uid(), role: 'assistant', kind: 'action',
          action: {...action, run_id: active.run.id}, runId: active.run.id,
        }));
        if (pendingActions.length) setMessages(items => [...items, ...pendingActions]);
        runRef.current = active.run.id;
        if (active.run.status !== 'running') {
          setRuntime('');
          runRef.current = null;
          setOpeningId('');
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
      if (window.matchMedia('(max-width: 900px)').matches) setHistoryOpen(false);
    } catch (error) {
      setRuntime('Não foi possível abrir');
      trace('Falha ao abrir conversa', error.message, 'error');
    } finally { setOpeningId(null); }
  }, [running, bootstrap.endpoints.history, bootstrap.endpoints.runs, fetchArtifact, trace, releasePreviews, queueEndpoint]);

  const changeProject = useCallback(async (projectRef, {showHistory = true} = {}) => {
    if (running) return;
    setContextLoading(true);
    setRuntime('Atualizando contexto');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(projectContextPayload(projectRef)),
      });
      rememberContext(data.context || {});
      reset();
      setHistoryOpen(showHistory);
      trace('Contexto alterado', projects.find(item => item.ref === projectRef)?.name || 'Contexto pessoal');
    } catch (error) {
      trace('Falha ao alterar contexto', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, bootstrap.endpoints.context, reset, trace, projects, loadContext]);

  const loadBrandIdentity = useCallback(async brandRef => {
    const brandId = String(brandRef || '').replace(/^studio:/, '');
    if (!/^\d+$/.test(brandId)) return;
    const data = await request(`/workspace/api/v2/brands/${brandId}/identity`);
    if (Array.isArray(data.projects)) setProjects(data.projects);
    if (data.artifact) {
      setArtifact(data.artifact); artifactRef.current = data.artifact;
      setPublishedUrl(''); setArtifactDirty(false); setArtifactOpen(true);
    }
  }, []);

  const changeBrand = useCallback(async brandRef => {
    if (running) return;
    setContextLoading(true); setRuntime('Atualizando marca');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(brandContextPayload(brandRef)),
      });
      rememberContext(data.context || {}); reset(); setHistoryOpen(true);
      await loadBrandIdentity(brandRef);
      trace('Marca aplicada à conversa');
    } catch (error) {
      trace('Falha ao abrir a marca', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, bootstrap.endpoints.context, reset, loadBrandIdentity, trace, loadContext]);

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

  const requestedProjectRef = useRef(new URLSearchParams(window.location.search).get('project_ref') || new URLSearchParams(window.location.search).get('project') || '');
  const requestedBrandRef = useRef(new URLSearchParams(window.location.search).get('brand_ref') || '');
  const requestedHistoryOpen = useRef(new URLSearchParams(window.location.search).get('history') === '1');
  const requestedConversationId = useRef(new URLSearchParams(window.location.search).get('conversation_id') || '');
  useEffect(() => {
    if (!requestedProjectRef.current || contextLoading || running) return;
    const projectRef = requestedProjectRef.current;
    requestedProjectRef.current = '';
    request(bootstrap.endpoints.context, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
      body: JSON.stringify(projectContextPayload(projectRef)),
    }).then(async data => {
      setContext(data.context || {});
      if (requestedHistoryOpen.current) setHistoryOpen(true);
      requestedHistoryOpen.current = false;
    }).catch(error => trace('Não foi possível aplicar o projeto selecionado', error.message, 'error'));
  }, [contextLoading, running, bootstrap.endpoints.context, trace]);

  useEffect(() => {
    if (!requestedBrandRef.current || contextLoading || running) return;
    const brandRef = requestedBrandRef.current;
    requestedBrandRef.current = '';
    request(bootstrap.endpoints.context, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
      body: JSON.stringify(brandContextPayload(brandRef)),
    }).then(async data => {
      setContext(data.context || {});
      if (requestedHistoryOpen.current) setHistoryOpen(true);
      requestedHistoryOpen.current = false;
      await loadBrandIdentity(brandRef);
    }).catch(error => trace('Não foi possível aplicar a marca selecionada', error.message, 'error'));
  }, [contextLoading, running, bootstrap.endpoints.context, loadBrandIdentity, trace]);

  useEffect(() => {
    if (!requestedConversationId.current || historyLoading || running) return;
    const id = requestedConversationId.current;
    requestedConversationId.current = '';
    const item = conversations.find(conversation => String(conversation.id) === id);
    if (item) openConversation(id, item.title);
    else trace('Conversa não encontrada', 'Ela pode ter sido arquivada ou não estar disponível para esta conta.', 'error');
  }, [conversations, historyLoading, running, openConversation, trace]);

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
  const handleDragEnter = useCallback(event => { if (!Array.from(event.dataTransfer?.types || []).includes('Files')) return; event.preventDefault(); dragDepthRef.current += 1; setDropActive(true); }, []);
  const handleDragOver = useCallback(event => { if (event.dataTransfer?.types?.includes('Files')) event.preventDefault(); }, []);
  const handleDragLeave = useCallback(event => { event.preventDefault(); dragDepthRef.current = Math.max(0, dragDepthRef.current - 1); if (!dragDepthRef.current) setDropActive(false); }, []);
  const handleDrop = useCallback(event => { event.preventDefault(); dragDepthRef.current = 0; setDropActive(false); addFiles(Array.from(event.dataTransfer?.files || [])); }, [addFiles]);

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
    if (artifactDirty && !(await confirmDiscard(false))) return;
    if (artifactDirty && artifactRef.current?.id) {
      try { await fetchArtifact(artifactRef.current.id); } catch (error) { trace('Não foi possível restaurar o artefato', error.message, 'error'); return; }
    }
    dispatchExecution({type: 'submitted'}); setDiagnostics([]); setRuntime(turnAttachments.length ? 'Enviando arquivos' : 'Trabalhando');
    if (!conversationRef.current && window.matchMedia('(max-width: 900px)').matches) setHistoryOpen(false);
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
    setTitle(current => current === emptyTitle ? clean.slice(0, 62) : current);
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
      const failed = {...pendingArtifact, pending: false, failed: true, title: 'Artefato não concluído', error: message || 'A geração terminou antes de preparar o conteúdo.'};
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
          runRef.current = event.run_id; runStartedRef.current = Date.now();
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
            pendingArtifact = {tabKey: `pending:${turnId}`, type: event.policy.artifact_type, title: 'Preparando artefato', pending: true};
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
          trace('Artefato criado', event.artifact?.title || '');
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
          failPendingArtifact('A geração foi interrompida antes de concluir o artefato.');
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
  }, [input, running, queuedTurns.length, artifactDirty, confirmDiscard, attachments, homeAttachments, context, composerContext, executionMode, fetchArtifact, trace, rememberContext, bootstrap.endpoints.messages, bootstrap.endpoints.route, loadRecent, releasePreviews, uploadFiles, queueEndpoint]);

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
    if (!initialPromptRef.current || running || contextLoading) return;
    const prompt = initialPromptRef.current;
    initialPromptRef.current = '';
    submit(prompt);
  }, [contextLoading, running, submit]);

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
      if (data.step?.status === 'completed' && completion.refresh_context) {
        try { await loadContext(); }
        catch (error) { trace('Contexto será atualizado em seguida', error.message); }
      }
    } catch (error) {
      const detail = String(error?.message || 'Não foi possível concluir esta ação.');
      setMessages(items => items.map(item => item.id === message.id ? {...item, actionPending: false, actionError: detail} : item));
      trace('Falha na ação', detail, 'error');
    }
  }, [bootstrap.endpoints.runs, trace, loadContext]);

  const changeArtifact = useCallback(content => {
    setArtifact(current => current ? {...current, content} : current);
    setArtifactDirty(true);
  }, []);

  const changeArtifactTitle = useCallback(title => {
    setArtifact(current => current ? {...current, title: String(title || '').slice(0, 180)} : current);
    setArtifactDirty(true);
  }, []);

  const saveArtifact = useCallback(async () => {
    if (!artifact?.id) return;
    setSaving(true);
    try {
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Revisão na conversa'})});
      setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false);
    } catch (error) {
      trace(error.status === 409 ? 'Artefato alterado em outra sessão' : 'Falha ao salvar artefato', error.message, 'error');
    } finally { setSaving(false); }
  }, [artifact, bootstrap.endpoints.artifacts, conversationId, trace]);

  const saveArtifactToProject = useCallback(async () => {
    if (!artifact?.id || !context.project_ref) return;
    setSaving(true);
    try {
      if (artifactDirty) {
        const saved = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Rascunho salvo automaticamente'}),
        });
        if (!saved.artifact?.id) throw new Error('O rascunho não pôde ser salvo antes de vincular ao projeto.');
      }
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/save-project`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId, project_ref: context.project_ref}),
      });
      setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false);
      trace('Rascunho salvo no projeto', data.artifact?.title || 'Documento');
    } catch (error) {
      trace('Falha ao salvar no projeto', error.message, 'error');
    } finally { setSaving(false); }
  }, [artifact, artifactDirty, bootstrap.endpoints.artifacts, conversationId, context.project_ref, trace]);

  const publishArtifact = useCallback(async () => {
    if (!artifact?.id || publishing || saving) return;
    if (publishedUrl) {
      const popup = window.open(publishedUrl, '_blank', 'noopener,noreferrer');
      const copied = await copyText(publishedUrl);
      trace('URL da página', copied ? 'Copiada para a área de transferência.' : 'A página foi aberta em uma nova aba.');
      if (!popup) trace('Abertura bloqueada', 'Permita novas abas para abrir a página publicada automaticamente.');
      return;
    }
    setPublishing(true);
    const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
    try {
      let currentArtifact = artifact;
      if (artifactDirty) {
        const saved = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {
          method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
          body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: artifact.content, title: artifact.title, change_summary: 'Rascunho publicado'}),
        });
        currentArtifact = saved.artifact;
      }
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(currentArtifact.id)}/publish`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({conversation_id: conversationId}),
      });
      const url = data.url || '';
      setArtifact(data.artifact || currentArtifact);
      artifactRef.current = data.artifact || currentArtifact;
      setArtifactDirty(false);
      setPublishedUrl(url);
      if (url) {
        const copied = await copyText(url);
        if (popup && !popup.closed) popup.location.href = url;
        else window.open(url, '_blank', 'noopener,noreferrer');
        if (!copied) trace('URL da página', 'A página foi aberta, mas o navegador não permitiu copiar automaticamente.');
      }
      trace('Página publicada', url ? 'A URL foi copiada para a área de transferência.' : 'A página foi publicada.');
    } catch (error) {
      if (popup && !popup.closed) popup.close();
      trace('Falha ao publicar página', error.message, 'error');
    } finally { setPublishing(false); }
  }, [artifact, artifactDirty, bootstrap.endpoints.artifacts, conversationId, publishedUrl, publishing, saving, trace]);

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
      trace('Página retirada da publicação', 'O artefato continua salvo e pode ser publicado novamente.');
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
      const snapshot = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}/versions/${version}`);
      const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(artifact.id)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({conversation_id: conversationId, expected_version: artifact.current_version, content: snapshot.version.content, title: artifact.title, change_summary: `Versão ${version} restaurada`})});
      setArtifact(data.artifact); artifactRef.current = data.artifact; setArtifactDirty(false);
    } catch (error) { trace('Falha ao restaurar versão', error.message, 'error'); }
  }, [artifact, artifactDirty, confirmDiscard, bootstrap.endpoints.artifacts, conversationId, trace]);

  const openResource = useCallback(async item => {
    if (!item || !(await confirmDiscard(false))) return;
    if (item.artifact_id) {
      try { await fetchArtifact(item.artifact_id); }
      catch (error) { trace('Não foi possível abrir o artefato', error.message, 'error'); }
      return;
    }
    const resource = ['image', 'logo'].includes(String(item.kind || '').toLowerCase())
      ? {tabKey: `resource:${item.id || item.url}`, type: 'image', title: item.title || 'Imagem do Studio', content: {url: item.url, alt: item.title || 'Imagem do Studio', source: item.source || 'studio'}}
      : item.url ? {tabKey: `resource:${item.id || item.url}`, type: 'link_reader', title: item.title || 'Link externo', content: item} : {tabKey: `resource:${item.id || item.title}`, type: 'resource', title: item.title || 'Arquivo', content: item};
    setArtifact(resource); artifactRef.current = resource;
    setArtifactDirty(false); setArtifactOpen(true);
  }, [confirmDiscard, fetchArtifact, trace]);

  const openLibrary = useCallback(async () => {
    if (!(await confirmDiscard(false))) return;
    const libraryProjectRef = String(context?.project_ref || '');
    const libraryBrandRef = String(context?.brand_ref || '');
    const tabKey = `library:${libraryProjectRef || libraryBrandRef || 'personal'}`;
    const pending = {tabKey, type: 'library', title: 'Biblioteca', pending: true};
    setArtifact(pending); artifactRef.current = pending; setArtifactOpen(true);
    try {
      const endpoint = bootstrap.endpoints?.studioLibrary || '/workspace/api/v2/studio/library';
      const suffix = libraryProjectRef ? `?project_ref=${encodeURIComponent(libraryProjectRef)}` : '';
      const data = await request(`${endpoint}${suffix}`);
      const asset = (item, source) => ({id: `${source}:${item.id}`, title: item.metadata?.display_name || item.metadata?.original_name || item.title || item.name || 'Sem título', preview: item.display_url || item.asset_url || item.image_url || item.thumb_url || item.asset_path || item.source_url, url: item.display_url || item.asset_url || item.image_url || item.url || item.asset_path || item.source_url, kind: item.role === 'logo' ? 'logo' : item.kind || 'image', source});
      const resources = (data.resources || []).map(item => ({id: item.id, title: item.title || 'Referência', url: item.editor_url || item.download_url || item.url, kind: item.type || item.resource_type || 'file', detail: item.category || item.mime_type || ''}));
      const library = {tabKey, type: 'library', title: 'Biblioteca', content: {groups: [
        {id: 'brand', title: 'Criativos da marca', layout: 'carousel', items: (data.brand_assets || []).map(item => asset(item, 'brand'))},
        {id: 'created', title: 'Criações', layout: 'carousel', items: (data.personal_assets || []).map(item => asset(item, 'personal'))},
        {id: 'references', title: 'Arquivos e links importantes', layout: 'list', items: resources},
      ]}};
      setArtifact(library); artifactRef.current = library; setArtifactDirty(false);
      setArtifactTabs(items => [...items.filter(item => artifactKey(item) !== tabKey), library]);
    } catch (error) {
      const failed = {...pending, pending: false, failed: true, error: error.message || 'Biblioteca indisponível.'};
      setArtifact(failed); artifactRef.current = failed;
    }
  }, [bootstrap.endpoints, confirmDiscard, context?.brand_ref, context?.project_ref]);

  const openDockBrand = useCallback(item => {
    const brandRef = item?.brandRef || (item?.id ? `studio:${item.id}` : '');
    if (brandRef) changeBrand(brandRef);
  }, [changeBrand]);

  const openDockItem = useCallback(item => {
    const kind = String(item?.kind || item?.type || '').toLowerCase();
    const resourceKinds = new Set(['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link']);
    if (item?.resourceRef || resourceKinds.has(kind)) {
      openResource(item);
      return;
    }
    const projectRef = item?.projectRef || item?.ref || (item?.id ? `ci:${item.id}` : '');
    if (projectRef) changeProject(projectRef, {showHistory: true});
  }, [changeProject, openResource]);

  const revisitFailedPrompt = useCallback(prompt => {
    setInput(prompt || '');
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);
  const openHistory = useCallback(() => setHistoryOpen(true), []);
  const closeHistory = useCallback(() => setHistoryOpen(false), []);
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
      await request(`${dockShortcutEndpoint}/order`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({ids: explicit.map(item => item.shortcutId)}),
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
  return <div className="cadu-ds-home-shell cv-conversations-shell">
    <main className="cadu-ds-home-main">
      <div onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} className="cadu-ds-home-workarea cv-conversations-workarea">
        <CaduDock bootstrap={bootstrap} sharedDock={bootstrap.sharedDock} conversationMode logo={bootstrap.caduMark || bootstrap.logo} homeUrl={bootstrap.urls?.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={projects} brands={brands} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={brands} resources={projects} shortcutItems={sharedDockItems} onDropItem={addDroppedDockItem} onReorderShortcuts={reorderDockShortcuts} usagePercent={bootstrap.usagePercent} onNewConversation={newConversation} onOpenBrand={openDockBrand} onOpenResource={openDockItem} onOpenUsage={() => setAccountOpen(true)}/>
          <Sidebar conversations={conversations} projects={projects} brands={brands} activeProjectRef={activeProjectRef} projectResourcesEndpoint={bootstrap.endpoints?.projectResources || '/workspace/api/v2/projects'} studioLibraryEndpoint={bootstrap.endpoints?.studioLibrary || '/workspace/api/v2/studio/library'} activeId={conversationId} onOpen={openConversation} onOpenResource={openResource} onOrganize={organizeConversation} onConversationAction={conversationAction} open={historyOpen} onClose={closeHistory} loading={historyLoading} openingId={openingId}/>
        {dropActive && createPortal(<div className="cv-drop-overlay" role="status" aria-live="polite"><div className="cv-drop-overlay-card"><Icon name="file" size={28}/><strong>Solte o arquivo para anexar</strong><span>PDF, documento, planilha ou imagem</span></div></div>, document.body)}
        <div className="cv-conversation-stage cv-relative cv-flex cv-min-w-0 cv-flex-1">
          <Conversation conversationId={conversationId} title={title} context={context} projects={projects} brands={brands} starterProject={starterProject} starterBrand={starterBrand} starterHome={bootstrap.home} contextLoading={contextLoading} runtime={runtime} diagnostics={diagnostics} messages={messages} input={input} setInput={setInput} onSubmit={submit} attachments={attachments} onRemoveAttachment={removeAttachment} onAttachmentPurposeChange={setAttachmentPurpose} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={setAttachmentDestination} executionMode={executionMode} onExecutionModeChange={setExecutionMode} running={running} onStop={stop} onPrompt={(prompt, selected) => { if (prompt) setInput(prompt); if (selected) { setComposerContext(selected); focusComposer(); } }} onOpenArtifact={item => item?.id && item.id !== artifactRef.current?.id ? fetchArtifact(item.id) : setArtifactOpen(true)} onOpenResource={openResource} onDecision={decide} onRevisitPrompt={revisitFailedPrompt} creditsUrl={bootstrap.urls?.credits || ''} onOpenHistory={openHistory} historyOpen={historyOpen} artifactOpen={artifactOpen} composerContext={composerContext} onClearContext={() => setComposerContext(null)} onAttach={addFiles} onContextDrop={dropContext} queuedTurns={queuedTurns} onUpdateQueuedTurn={(id, prompt) => persistQueuedTurns(updateQueued(queuedTurns, id, prompt))} onRemoveQueuedTurn={removeQueuedTurn} onMoveQueuedTurn={(id, direction) => persistQueuedTurns(moveQueued(queuedTurns, id, direction))} onOpenLibrary={openLibrary} automation={activeConversationState}/>
          {artifactOpen && <ArtifactPane
            artifact={artifact} dirty={artifactDirty} saving={saving} publishing={publishing} publishedUrl={publishedUrl}
            tabs={artifactTabs} activeTabKey={artifactKey(artifact)}
            onSelectTab={async next => {
              if (artifactDirty) await saveArtifact();
              setArtifact(next); artifactRef.current = next; setArtifactDirty(false); setPublishedUrl('');
            }}
            onCloseTab={async key => {
              if (key === artifactKey(artifact) && artifactDirty && !(await confirmDiscard(false))) return;
              const remaining = artifactTabs.filter(item => artifactKey(item) !== key);
              setArtifactTabs(remaining);
              if (key === artifactKey(artifact)) {
                const next = remaining[remaining.length - 1] || null;
                setArtifact(next); artifactRef.current = next; setArtifactDirty(false); setPublishedUrl('');
                if (!next) setArtifactOpen(false);
              }
            }}
            onCloseOtherTabs={async key => {
              const selected = artifactTabs.find(item => artifactKey(item) === key);
              if (!selected) return;
              if (key !== artifactKey(artifact) && artifactDirty && !(await confirmDiscard(false))) return;
              setArtifactTabs([selected]);
              setArtifact(selected); artifactRef.current = selected; setArtifactDirty(false); setPublishedUrl('');
            }}
            onCloseAllTabs={async () => {
              if (artifactDirty && !(await confirmDiscard(false))) return;
              setArtifactTabs([]); setArtifact(null); artifactRef.current = null; setArtifactDirty(false); setPublishedUrl(''); setArtifactOpen(false);
            }}
            side={artifactSide} onSideChange={changeArtifactSide}
            onChange={changeArtifact} onTitleChange={changeArtifactTitle} projectRef={activeProjectRef}
            studioEditorUrl={bootstrap.urls?.studioEditor}
            onSaveToProject={saveArtifactToProject} onPublish={publishArtifact} onUnpublish={unpublishArtifact} onClose={() => setArtifactOpen(false)}
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
                onOpenResource={openResource}
          />}
        </div>
        <ConfirmDialog request={discardRequest} onResolve={resolveDiscard}/>
      </div>
    </main>
  </div>;
}
