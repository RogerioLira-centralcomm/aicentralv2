import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Sidebar} from './components/Sidebar';
import {Conversation} from './components/Conversation';
import {ArtifactPane} from './components/ArtifactPane';
import {ConfirmDialog} from './components/ConfirmDialog';
import {csrf, request, streamEvents, uid} from './lib/api';
import {insertWorkedBeforeResult} from './lib/responseModel.mjs';

const emptyTitle = 'Nova conversa';

export default function App({bootstrap}) {
  const [context, setContext] = useState({});
  const [projects, setProjects] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [title, setTitle] = useState(emptyTitle);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [composerContext, setComposerContext] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [artifact, setArtifact] = useState(null);
  const [artifactOpen, setArtifactOpen] = useState(false);
  const [artifactDirty, setArtifactDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState([]);
  const [running, setRunning] = useState(false);
  const [runtime, setRuntime] = useState('');
  const [diagnostics, setDiagnostics] = useState([]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
  const [openingId, setOpeningId] = useState(null);
  const [notice, setNotice] = useState(null);
  const [discardRequest, setDiscardRequest] = useState(null);
  const conversationRef = useRef(null);
  const artifactRef = useRef(null);
  const runRef = useRef(null);
  const runStartedRef = useRef(0);
  const fileRef = useRef(null);
  const discardResolverRef = useRef(null);

  useEffect(() => { conversationRef.current = conversationId; }, [conversationId]);
  useEffect(() => { artifactRef.current = artifact; }, [artifact]);

  const trace = useCallback((eventTitle, detail = '', tone = '') => {
    setDiagnostics(items => [...items, {id: uid(), title: eventTitle, detail, tone}].slice(-30));
    if (tone === 'error') setNotice({id: uid(), tone: 'error', title: eventTitle, detail});
  }, []);

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
      setConversations((data.conversations || []).filter(item => !['arquivada', 'archived'].includes(String(item.status || '').toLowerCase())).slice(0, 30));
    } catch (_) {
      setConversations([]);
    } finally { setHistoryLoading(false); }
  }, [bootstrap.endpoints.history]);

  const loadContext = useCallback(async () => {
    setContextLoading(true);
    try {
      const data = await request(bootstrap.endpoints.context);
      setContext(data.context || {});
      setProjects((data.entities || []).filter(item => item.kind === 'project'));
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
    setTitle(emptyTitle); setMessages([]); setInput(''); setComposerContext(null); setAttachments([]);
    setArtifact(null); artifactRef.current = null; setArtifactOpen(false); setArtifactDirty(false);
    setDiagnostics([]); setRuntime(''); runRef.current = null;
  }, []);

  const newConversation = useCallback(async () => {
    if (!running && await confirmDiscard()) reset();
  }, [running, confirmDiscard, reset]);

  const openConversation = useCallback(async (id, conversationTitle) => {
    if (running || !(await confirmDiscard())) return;
    setOpeningId(id);
    setRuntime('Abrindo conversa');
    try {
      const data = await request(`${bootstrap.endpoints.history}/${encodeURIComponent(id)}/messages`);
      setConversationId(id); conversationRef.current = id;
      setTitle(conversationTitle || 'Conversa');
      if (data.context) setContext(data.context);
      setAttachments([]); setComposerContext(null); setArtifact(null); artifactRef.current = null; setArtifactDirty(false); setArtifactOpen(false);
      let lastArtifact = '';
      const restored = (data.messages || []).map(item => {
        if (item.role === 'user') return {id: uid(), role: 'user', content: item.content || '', files: item.files || []};
        const metadata = item.metadata && typeof item.metadata === 'object' ? item.metadata : {};
        const response = metadata.response && typeof metadata.response === 'object' ? {...metadata.response, answer: metadata.response.answer || item.content || ''} : {answer: item.content || ''};
        if (metadata.artifact_id) lastArtifact = String(metadata.artifact_id);
        return {id: uid(), role: 'assistant', response, artifact: metadata.artifact_id ? {id: String(metadata.artifact_id), title: response.artifact_patch?.title || 'artefato', type: response.artifact_patch?.type} : null};
      });
      setMessages(restored);
      if (lastArtifact) await fetchArtifact(lastArtifact);
      setRuntime('');
      setMobileOpen(false);
    } catch (error) {
      setRuntime('Não foi possível abrir');
      trace('Falha ao abrir conversa', error.message, 'error');
    } finally { setOpeningId(null); }
  }, [running, confirmDiscard, bootstrap.endpoints.history, fetchArtifact, trace]);

  const changeProject = useCallback(async projectRef => {
    if (running || !(await confirmDiscard())) return;
    setContextLoading(true);
    setRuntime('Atualizando contexto');
    try {
      const data = await request(bootstrap.endpoints.context, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({project_ref: projectRef || null, brand_ref: context.brand_ref || null}),
      });
      setContext(data.context || {});
      reset();
      trace('Contexto alterado', projects.find(item => item.ref === projectRef)?.name || 'Contexto pessoal');
    } catch (error) {
      trace('Falha ao alterar contexto', error.message, 'error');
      await loadContext();
    } finally { setRuntime(''); setContextLoading(false); }
  }, [running, confirmDiscard, bootstrap.endpoints.context, context.brand_ref, reset, trace, projects, loadContext]);

  const addFiles = useCallback(files => {
    setAttachments(current => {
      const next = [...current];
      for (const file of files) {
        if (next.length >= 3) { trace('Limite de anexos', 'Envie no máximo três arquivos.', 'error'); break; }
        if (!file.size || file.size > 15 * 1024 * 1024 || !/\.(png|jpe?g|webp|gif|pdf|txt|csv|md|json|docx|xlsx|pptx)$/i.test(file.name)) {
          trace('Arquivo não aceito', 'Use imagem, PDF, texto ou Office de até 15 MB.', 'error'); continue;
        }
        next.push({name: file.name, file, id: null, uploading: false, error: false});
      }
      return next;
    });
  }, [trace]);

  const uploadFiles = async () => {
    const staged = [...attachments];
    for (let index = 0; index < staged.length; index += 1) {
      if (staged[index].id) continue;
      staged[index] = {...staged[index], uploading: true, error: false}; setAttachments([...staged]);
      const body = new FormData(); body.append('file', staged[index].file);
      try {
        const response = await fetch(bootstrap.endpoints.uploads, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrf()}, body});
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.file?.id) throw new Error(data.error || 'Não foi possível anexar o arquivo.');
        staged[index] = {...staged[index], id: data.file.id, uploading: false};
      } catch (error) {
        staged[index] = {...staged[index], uploading: false, error: true}; setAttachments([...staged]); throw error;
      }
      setAttachments([...staged]);
    }
    return staged;
  };

  const submit = useCallback(async () => {
    const clean = input.trim();
    if (!clean || running) return;
    if (artifactDirty && !(await confirmDiscard(false))) return;
    if (artifactDirty && artifactRef.current?.id) {
      try { await fetchArtifact(artifactRef.current.id); } catch (error) { trace('Não foi possível restaurar o artefato', error.message, 'error'); return; }
    }
    setRunning(true); setRuntime(attachments.length ? 'Enviando arquivos' : 'Trabalhando');
    let staged;
    try { staged = attachments.length ? await uploadFiles() : []; }
    catch (error) { setRunning(false); setRuntime('Não foi possível anexar'); trace('Falha no anexo', error.message, 'error'); return; }
    const files = staged.map(item => ({id: item.id, name: item.name}));
    const turnId = uid();
    setMessages(items => [...items, {id: uid(), turnId, role: 'user', content: clean, files}]);
    setTitle(current => current === emptyTitle ? clean.slice(0, 62) : current);
    setInput(''); setComposerContext(null); setAttachments([]); setRuntime('Trabalhando');
    let terminal = false;
    let runStarted = false;
    let latestArtifact = null;
    const startedAt = Date.now();
    try {
      const response = await fetch(bootstrap.endpoints.messages, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
        body: JSON.stringify({
          message: clean, request_id: crypto.randomUUID(), conversation_id: conversationRef.current,
          surface: 'conversations', files: files.map(item => item.id),
          selected_context: composerContext ? {type: composerContext.type, text: composerContext.text} : null,
          active_object: artifactRef.current?.id ? {type: `artifact:${artifactRef.current.type}`, id: artifactRef.current.id} : null,
        }),
      });
      await streamEvents(response, event => {
        const kind = event.event;
        if (kind === 'run.started') {
          runStarted = true;
          setConversationId(event.conversation_id); conversationRef.current = event.conversation_id;
          runRef.current = event.run_id; runStartedRef.current = Date.now();
          trace('Execução iniciada', event.run_id);
        } else if (kind === 'route.selected') trace('Preparando trabalho', event.route?.action || '');
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
          setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', response: {answer: event.message || 'O agente não conseguiu concluir esta solicitação. Tente novamente em instantes.'}}]);
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
      const answer = detail && !/^HTTP\s+\d+/i.test(detail)
        ? detail
        : 'O agente desta conversa está temporariamente indisponível. Tente novamente em instantes.';
      setRuntime('Não foi possível concluir'); trace('Falha na conversa', detail, 'error');
      setMessages(items => [...items, {id: uid(), turnId, role: 'assistant', response: {answer}}]);
      setInput(clean);
    } finally {
      if (runStarted) {
        const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
        const worked = {id: uid(), turnId, role: 'assistant', kind: 'worked', seconds};
        setMessages(items => insertWorkedBeforeResult(items, turnId, worked));
      }
      setRunning(false); runRef.current = null; await loadRecent();
    }
  }, [input, running, artifactDirty, confirmDiscard, attachments, composerContext, fetchArtifact, trace, bootstrap.endpoints.messages, loadRecent]);

  const stop = useCallback(async () => {
    if (!runRef.current) return;
    setRuntime('Interrompendo');
    try { await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(runRef.current)}/stop`, {method: 'POST', headers: {'X-CSRF-Token': csrf()}}); }
    catch (error) { setRuntime('Não foi possível interromper'); trace('Falha ao interromper', error.message, 'error'); }
  }, [bootstrap.endpoints.runs, trace]);

  const decide = useCallback(async (message, approved) => {
    try {
      const data = await request(`${bootstrap.endpoints.runs}/${encodeURIComponent(message.runId)}/steps/${encodeURIComponent(message.action.step_id)}/decision`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({approved})});
      setMessages(items => items.map(item => item.id === message.id ? {...item, kind: undefined, response: {answer: data.step?.status === 'completed' ? 'Ação concluída.' : approved ? 'Ação confirmada.' : 'Ação cancelada.'}} : item));
    } catch (error) { trace('Falha na ação', error.message, 'error'); }
  }, [bootstrap.endpoints.runs, trace]);

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

  return <div className="cv-flex cv-h-full cv-min-h-0 cv-w-full cv-overflow-hidden cv-bg-ink">
    <Sidebar bootstrap={bootstrap} conversations={conversations} activeId={conversationId} onOpen={openConversation} onNew={newConversation} mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} loading={historyLoading} openingId={openingId}/>
    <div className="cv-relative cv-flex cv-min-w-0 cv-flex-1">
      <Conversation title={title} context={context} projects={projects} onProjectChange={changeProject} contextLoading={contextLoading} runtime={runtime} diagnostics={diagnostics} messages={messages} input={input} setInput={setInput} onSubmit={submit} onAttach={() => fileRef.current?.click()} attachments={attachments} onRemoveAttachment={index => setAttachments(items => items.filter((_, itemIndex) => itemIndex !== index))} running={running} onStop={stop} onNew={newConversation} onPrompt={(prompt, selected) => { setInput(prompt); if (selected) setComposerContext(selected); }} onOpenArtifact={item => item?.id && item.id !== artifactRef.current?.id ? fetchArtifact(item.id) : setArtifactOpen(true)} onOpenResource={openResource} onDecision={decide} mobileMenu={() => setMobileOpen(true)} artifactOpen={artifactOpen} notice={notice} onDismissNotice={() => setNotice(null)} composerContext={composerContext} onClearContext={() => setComposerContext(null)}/>
      {artifactOpen && <ArtifactPane artifact={artifact} dirty={artifactDirty} saving={saving} onChange={changeArtifact} onClose={() => setArtifactOpen(false)} onSave={saveArtifact} onLoadVersions={loadVersions} versions={versions} onRestoreVersion={restoreVersion}/>}
    </div>
    <input ref={fileRef} type="file" hidden multiple accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.csv,.md,.json,.docx,.xlsx,.pptx" onChange={event => { addFiles(Array.from(event.target.files || [])); event.target.value = ''; }}/>
    <ConfirmDialog request={discardRequest} onResolve={resolveDiscard}/>
  </div>;
}
