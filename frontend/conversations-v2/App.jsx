import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Sidebar} from './components/Sidebar';
import {Conversation} from './components/Conversation';
import {ArtifactPane} from './components/ArtifactPane';
import {ConfirmDialog} from './components/ConfirmDialog';
import {csrf, request, streamEvents, uid} from './lib/api';
import {chatFailure} from './lib/errorModel.mjs';
import {insertWorkedBeforeResult} from './lib/responseModel.mjs';
import {attachmentIssues, createStagedAttachment, MAX_ATTACHMENTS, validateAttachment} from './lib/attachmentModel.mjs';
import {recentConversations, restoreConversationMessages} from './lib/historyModel.mjs';
import {brandContextPayload, conversationPayload, projectContextPayload} from './lib/contextModel.mjs';
import {uploadAttachments} from './lib/attachmentUpload.mjs';
import {Icon} from './lib/icons';
import {CaduDock, WorkspaceAccountMenu} from '../cadu-design-system';

const emptyTitle = 'Novo chat';

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
  const [artifactOpen, setArtifactOpen] = useState(false);
  const [artifactDirty, setArtifactDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState([]);
  const [running, setRunning] = useState(false);
  const [runtime, setRuntime] = useState('');
  const [diagnostics, setDiagnostics] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(() => !window.matchMedia('(max-width: 900px)').matches);
  const [accountOpen, setAccountOpen] = useState(false);
  const [conversationDockItems, setConversationDockItems] = useState(() => bootstrap.dock?.items || []);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
  const [openingId, setOpeningId] = useState(null);
  const [notice, setNotice] = useState(null);
  const [discardRequest, setDiscardRequest] = useState(null);
  const [dropActive, setDropActive] = useState(false);
  const conversationRef = useRef(null);
  const artifactRef = useRef(null);
  const runRef = useRef(null);
  const runStartedRef = useRef(0);
  const discardResolverRef = useRef(null);
  const dragDepthRef = useRef(0);

  useEffect(() => { conversationRef.current = conversationId; }, [conversationId]);
  useEffect(() => { artifactRef.current = artifact; }, [artifact]);

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
    if (tone === 'error') setNotice({id: uid(), tone: 'error', title: eventTitle, detail});
  }, []);

  const releasePreviews = useCallback(items => items.forEach(item => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  }), []);

  const fetchArtifact = useCallback(async id => {
    const data = await request(`${bootstrap.endpoints.artifacts}/${encodeURIComponent(id)}`);
    setArtifact(data.artifact);
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
      setContext(data.context || {});
      setProjects(current => (data.entities || []).filter(item => item.kind === 'project').map(item => ({
        ...item,
        ...(current.find(existing => (existing.ref || existing.projectRef || existing.id) === item.ref) || {}),
      })));
      setBrands(current => {
        const fromContext = (data.entities || []).filter(item => item.kind === 'brand').map(item => ({
          ...item, logoUrl: item.logo_url, visualInitials: item.name, visualColor: '#176b5e',
        }));
        return fromContext.map(item => ({...item, ...(current.find(existing => (existing.ref || existing.brandRef) === item.ref) || {})}));
      });
    } catch (error) {
      trace('Contexto indisponível', error.message, 'error');
    } finally { setContextLoading(false); }
  }, [bootstrap.endpoints.context, trace]);

  useEffect(() => { loadContext(); loadRecent(); }, [loadContext, loadRecent]);

  useEffect(() => {
    const guard = event => {
      if (!artifactDirty && !attachments.length) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [artifactDirty, attachments.length]);

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
    setArtifact(null); artifactRef.current = null; setArtifactOpen(false); setArtifactDirty(false);
    setDiagnostics([]); setRuntime(''); runRef.current = null;
  }, [releasePreviews]);

  const focusComposer = useCallback(() => {
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);

  const newConversation = useCallback(async () => {
    if (running || !(await confirmDiscard())) return;
    reset();
    setHistoryOpen(false);
    focusComposer();
  }, [running, confirmDiscard, reset, focusComposer]);

  const openConversation = useCallback(async (id, conversationTitle) => {
    if (running || !(await confirmDiscard())) return;
    setOpeningId(id);
    setRuntime('Abrindo conversa');
    try {
      const data = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}/messages`);
      setConversationId(id); conversationRef.current = id;
      setTitle(conversationTitle || 'Conversa');
      if (data.context) setContext(data.context);
      setAttachments(items => { releasePreviews(items); return []; }); setComposerContext(null); setArtifact(null); artifactRef.current = null; setArtifactDirty(false); setArtifactOpen(false);
      const {messages: restored, selectedContext: restoredContext, lastArtifact} = restoreConversationMessages(data.messages, uid);
      setMessages(restored);
      setComposerContext(restoredContext);
      if (lastArtifact) await fetchArtifact(lastArtifact);
      setRuntime('');
      if (window.matchMedia('(max-width: 900px)').matches) setHistoryOpen(false);
    } catch (error) {
      setRuntime('Não foi possível abrir');
      trace('Falha ao abrir conversa', error.message, 'error');
    } finally { setOpeningId(null); }
  }, [running, confirmDiscard, bootstrap.endpoints.history, fetchArtifact, trace, releasePreviews]);

  const changeProject = useCallback(async (projectRef, {showHistory = true} = {}) => {
    if (running || !(await confirmDiscard())) return;
    setContextLoading(true);
    setRuntime('Atualizando contexto');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(projectContextPayload(projectRef)),
      });
      setContext(data.context || {});
      reset();
      setHistoryOpen(showHistory);
      trace('Contexto alterado', projects.find(item => item.ref === projectRef)?.name || 'Contexto pessoal');
    } catch (error) {
      trace('Falha ao alterar contexto', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.context, reset, trace, projects, loadContext]);

  const loadBrandIdentity = useCallback(async brandRef => {
    const brandId = String(brandRef || '').replace(/^studio:/, '');
    if (!/^\d+$/.test(brandId)) return;
    const data = await request(`/workspace/api/v2/brands/${brandId}/identity`);
    if (Array.isArray(data.projects)) setProjects(data.projects);
    if (data.artifact) {
      setArtifact(data.artifact); artifactRef.current = data.artifact;
      setArtifactDirty(false); setArtifactOpen(true);
    }
  }, []);

  const changeBrand = useCallback(async brandRef => {
    if (running || !(await confirmDiscard())) return;
    setContextLoading(true); setRuntime('Atualizando marca');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(brandContextPayload(brandRef)),
      });
      setContext(data.context || {}); reset(); setHistoryOpen(true);
      await loadBrandIdentity(brandRef);
      trace('Marca aplicada à conversa');
    } catch (error) {
      trace('Falha ao abrir a marca', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.context, reset, loadBrandIdentity, trace, loadContext]);

  const dropContext = useCallback(payload => {
    if (payload?.projectRef || payload?.type === 'project') {
      changeProject(payload.projectRef || payload.id);
      return;
    }
    if (payload?.type === 'brand') changeBrand(payload.brandRef || (payload.id ? `studio:${payload.id}` : ''));
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
      for (const file of files) {
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
        staged.push(item); next.push(item);
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

  const uploadFiles = useCallback(() => uploadAttachments({
      attachments,
      projectRef: context.project_ref,
      uploadsEndpoint: bootstrap.endpoints.uploads,
      requestFn: request,
      fetchFn: fetch,
      csrfToken: csrf,
      uuid: () => crypto.randomUUID(),
      onProgress: setAttachments,
    }), [attachments, context.project_ref, bootstrap.endpoints.uploads]);

  const submit = useCallback(async (requestedInput = input) => {
    const clean = requestedInput.trim();
    if (!clean || running) return;
    if (artifactDirty && !(await confirmDiscard(false))) return;
    if (artifactDirty && artifactRef.current?.id) {
      try { await fetchArtifact(artifactRef.current.id); } catch (error) { trace('Não foi possível restaurar o artefato', error.message, 'error'); return; }
    }
    setRunning(true); setRuntime(attachments.length ? 'Enviando arquivos' : 'Trabalhando');
    if (!conversationRef.current && window.matchMedia('(max-width: 900px)').matches) setHistoryOpen(false);
    let staged;
    try { staged = attachments.length ? await uploadFiles() : []; }
    catch (error) { setRunning(false); setRuntime('Não foi possível anexar'); trace('Falha no anexo', error.message, 'error'); return; }
    const files = [...staged.map(item => ({id: item.id, name: item.name, source: item.source || null})), ...homeAttachments];
    const providerFileIds = files.map(item => item.id).filter(Boolean);
    const turnId = uid();
    setMessages(items => [...items, {id: uid(), turnId, role: 'user', content: clean, files}]);
    setTitle(current => current === emptyTitle ? clean.slice(0, 62) : current);
    setInput(''); setComposerContext(null); setHomeAttachments([]); setAttachments(items => { releasePreviews(items); return []; }); setRuntime('Trabalhando');
    let terminal = false;
    let runStarted = false;
    let latestArtifact = null;
    const startedAt = Date.now();
    try {
      const response = await fetch(bootstrap.endpoints.messages, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify(conversationPayload({
          message: clean,
          requestId: crypto.randomUUID(),
          conversationId: conversationRef.current,
          providerFileIds,
          executionMode,
          context,
          selectedContext: composerContext,
          activeArtifact: artifactRef.current,
        })),
      });
      await streamEvents(response, event => {
        const kind = event.event;
        if (kind === 'run.started') {
          runStarted = true;
          setConversationId(event.conversation_id); conversationRef.current = event.conversation_id;
          runRef.current = event.run_id; runStartedRef.current = Date.now();
          trace('Execução iniciada', event.run_id);
        } else if (kind === 'route.selected') {
          if (event.policy?.execution_mode) setExecutionMode(event.policy.execution_mode);
          trace('Preparando trabalho', event.route?.action || '');
        }
        else if (kind === 'tool.completed') trace('Consulta concluída', event.name || '');
        else if (kind === 'tool.unavailable') trace('Recurso indisponível', event.code || '', 'error');
        else if (kind === 'action.proposed') setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', kind: 'action', action: event.action, runId: runRef.current}]);
        else if (kind === 'artifact.created') {
          latestArtifact = event.artifact || null;
          if (latestArtifact) { setArtifact(latestArtifact); artifactRef.current = latestArtifact; setArtifactDirty(false); setArtifactOpen(true); }
          trace('Artefato criado', event.artifact?.title || '');
        } else if (kind === 'answer.completed') {
          const responseData = event.response || {};
          if (responseData.artifact_patch && !latestArtifact?.id) {
            const draft = {type: responseData.artifact_patch.type || 'document', title: responseData.artifact_patch.title, content: responseData.artifact_patch};
            setArtifact(draft); artifactRef.current = draft; setArtifactOpen(true);
          }
          setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', response: responseData, artifact: latestArtifact}]);
          trace('Resposta concluída', responseData.confidence || '');
        } else if (kind === 'run.failed') {
          terminal = true; setRuntime('Não foi possível concluir'); trace('Execução interrompida', event.message || '', 'error');
          setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', kind: 'failure', failure: chatFailure({message: event.message, status: 503}), prompt: clean}]);
          setInput(clean);
        } else if (kind === 'run.cancelled' || (kind === 'run.completed' && event.status === 'cancelled')) {
          terminal = true; setRuntime('Interrompido'); trace('Execução interrompida');
        } else if (kind === 'run.completed') {
          terminal = true; setRuntime(event.status === 'completed' ? '' : 'Não foi possível concluir'); trace('Execução concluída', event.status || '');
        }
      });
      if (!terminal) throw new Error('A conexão terminou antes da conclusão.');
    } catch (error) {
      const detail = String(error?.message || '').trim();
      setRuntime('Não foi possível concluir'); trace('Falha na conversa', detail, 'error');
      setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', kind: 'failure', failure: chatFailure(error), prompt: clean}]);
      setInput(clean);
    } finally {
      if (runStarted) {
        const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
        const worked = {id: uid(), turnId, role: 'assistant', kind: 'worked', seconds};
        setMessages(items => insertWorkedBeforeResult(items, turnId, worked));
      }
      setRunning(false); runRef.current = null; await loadRecent();
    }
  }, [input, running, artifactDirty, confirmDiscard, attachments, homeAttachments, context, composerContext, executionMode, fetchArtifact, trace, bootstrap.endpoints.messages, loadRecent, releasePreviews, uploadFiles]);

  const initialPromptRef = useRef(initialQuery.get('auto_send') === '1' ? initialQuery.get('prompt') || '' : '');
  useEffect(() => {
    if (!initialPromptRef.current || running || contextLoading) return;
    const prompt = initialPromptRef.current;
    initialPromptRef.current = '';
    submit(prompt);
  }, [contextLoading, running, submit]);

  const stop = useCallback(async () => {
    if (!runRef.current) return;
    setRuntime('Interrompendo');
    try { await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(runRef.current)}/stop`, {method: 'POST', headers: {'X-CSRF-Token': csrf()}}); }
    catch (error) { setRuntime('Não foi possível interromper'); trace('Falha ao interromper', error.message, 'error'); }
  }, [bootstrap.endpoints.runs, trace]);

  const decide = useCallback(async (message, approved) => {
    try {
      const data = await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(message.runId)}/steps/${encodeURIComponent(message.action.step_id)}/decision`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({approved})});
      const completion = data.step?.output_snapshot?.completion || {};
      const response = data.step?.status === 'completed'
        ? {answer: completion.answer || 'Ação concluída.', blocks: completion.blocks || []}
        : {answer: approved ? 'Ação confirmada.' : 'Ação cancelada.'};
      setMessages(items => items.map(item => item.id === message.id ? {...item, kind: undefined, response} : item));
      if (data.step?.status === 'completed' && completion.refresh_context) {
        try { await loadContext(); }
        catch (error) { trace('Contexto será atualizado em seguida', error.message); }
      }
    } catch (error) { trace('Falha na ação', error.message, 'error'); }
  }, [bootstrap.endpoints.runs, trace, loadContext]);

  const changeArtifact = useCallback(content => {
    setArtifact(current => current ? {...current, content} : current);
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
    const resource = {type: 'resource', title: item.title || 'Arquivo', content: item};
    setArtifact(resource); artifactRef.current = resource;
    setArtifactDirty(false); setArtifactOpen(true);
  }, [confirmDiscard, fetchArtifact, trace]);

  const revisitFailedPrompt = useCallback(prompt => {
    setInput(prompt || '');
    window.requestAnimationFrame(() => document.querySelector('.cv-composer-input')?.focus());
  }, []);
  const openHistory = useCallback(() => setHistoryOpen(true), []);
  const closeHistory = useCallback(() => setHistoryOpen(false), []);

  const activeProjectRef = String(context?.project_ref || '');
  const activeBrandRef = String(context?.brand_ref || '');
  const dockItems = conversationDockItems;
  const sharedDockItems = dockItems.map(item => ({
    ...item,
    active: item.kind === 'project' && String(item.projectRef || '') === activeProjectRef || item.kind === 'brand' && String(item.brandRef || (item.id ? `studio:${item.id}` : '')) === activeBrandRef,
  }));
  const canReorderDock = dockItems.length > 0 && dockItems.every(item => item.shortcutId);
  const dockShortcutEndpoint = bootstrap.endpoints?.dockShortcuts || '/workspace/api/dock/shortcuts';
  const reorderDockShortcuts = useCallback(async next => {
    const before = conversationDockItems;
    setConversationDockItems(next);
    try {
      await request(`${dockShortcutEndpoint}/order`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({ids: next.map(item => item.shortcutId)}),
      });
    } catch (error) {
      setConversationDockItems(before);
      trace('Falha ao ordenar atalhos', error.message, 'error');
    }
  }, [conversationDockItems, dockShortcutEndpoint, trace]);
  return <div className="cadu-ds-home-shell cv-conversations-shell">
    <main className="cadu-ds-home-main">
      <div onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} className="cadu-ds-home-workarea cv-conversations-workarea">
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark || bootstrap.logo} homeUrl={bootstrap.urls?.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={projects} brands={brands} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} shortcutItems={sharedDockItems} onReorderShortcuts={canReorderDock ? reorderDockShortcuts : undefined} usagePercent={bootstrap.usagePercent} onNewConversation={newConversation} onOpenBrand={item => changeBrand(item.brandRef || `studio:${item.id}`)} onOpenResource={item => item.projectRef && changeProject(item.projectRef, {showHistory: true})} onOpenUsage={() => setAccountOpen(true)}/>
        <Sidebar conversations={conversations} projects={projects} brands={brands} activeProjectRef={activeProjectRef} activeId={conversationId} onOpen={openConversation} open={historyOpen} onClose={closeHistory} loading={historyLoading} openingId={openingId}/>
        {dropActive && <div className="cv-drop-overlay" role="status"><div className="cv-drop-overlay-card"><Icon name="file" size={24}/><strong>Solte para anexar ao chat</strong><span>Imagens aparecem como miniaturas. Os demais arquivos entram com nome e tipo.</span></div></div>}
        <div className="cv-relative cv-flex cv-min-w-0 cv-flex-1">
          <Conversation title={title} context={context} projects={projects} brands={brands} onProjectChange={changeProject} onBrandChange={changeBrand} contextLoading={contextLoading} runtime={runtime} diagnostics={diagnostics} messages={messages} input={input} setInput={setInput} onSubmit={submit} attachments={attachments} onRemoveAttachment={removeAttachment} onAttachmentPurposeChange={setAttachmentPurpose} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={setAttachmentDestination} executionMode={executionMode} onExecutionModeChange={setExecutionMode} running={running} onStop={stop} onPrompt={(prompt, selected) => { setInput(prompt); if (selected) setComposerContext(selected); }} onOpenArtifact={item => item?.id && item.id !== artifactRef.current?.id ? fetchArtifact(item.id) : setArtifactOpen(true)} onOpenResource={openResource} onDecision={decide} onRevisitPrompt={revisitFailedPrompt} creditsUrl={bootstrap.urls?.credits || ''} onOpenHistory={openHistory} historyOpen={historyOpen} artifactOpen={artifactOpen} notice={notice} onDismissNotice={() => setNotice(null)} composerContext={composerContext} onClearContext={() => setComposerContext(null)} onAttach={addFiles} onContextDrop={dropContext}/>
          {artifactOpen && <ArtifactPane artifact={artifact} dirty={artifactDirty} saving={saving} onChange={changeArtifact} onClose={() => setArtifactOpen(false)} onSave={saveArtifact} onLoadVersions={loadVersions} versions={versions} onRestoreVersion={restoreVersion}/>}
        </div>
        <ConfirmDialog request={discardRequest} onResolve={resolveDiscard}/>
      </div>
    </main>
  </div>;
}
