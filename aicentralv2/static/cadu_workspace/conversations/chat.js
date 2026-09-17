/* Shared Workspace chat; independent of product navigation. */
(() => {
  'use strict';
  async function api(path, method = 'GET', data, signal) {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    const timeout = AbortSignal.timeout(20000);
    const response = await fetch('/familia/api/' + path, {method, credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers: {'Content-Type': 'application/json', ...(csrf ? {'X-CSRF-Token': csrf} : {})},
      ...(data ? {body: JSON.stringify(data)} : {})});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.error || 'Não foi possível concluir. Tente novamente.');
      error.status = response.status;
      throw error;
    }
    return result;
  }
  function unavailableMessage(action, error) {
    const code = Number.isInteger(error?.status) ? ' (erro ' + error.status + ')' : '';
    const detail = typeof error?.message === 'string' ? error.message.trim() : '';
    return detail && detail !== 'Não foi possível concluir. Tente novamente.'
      ? action + code + '. ' + detail
      : action + code + '. Tente novamente em instantes.';
  }
  function queuedEvents(run, signal) {
    return CaduConversationStream.queued(run, {
      signal,
      fetchPage: (cursor, activeSignal) => api('conversations/runs/' + encodeURIComponent(run.run_id) + '/events?after=' + cursor, 'GET', undefined, activeSignal),
      onRetry: () => { status.textContent = 'Reconectando ao Cadu sem reenviar sua mensagem…'; }
    });
  }
  const panel = document.getElementById('conversation-panel');
  if (!panel) return;
  const pageMode = panel.dataset.conversationPage === 'true';
  const opener = document.getElementById('conversation-open');
  const backdrop = document.getElementById('conversation-backdrop');
  const history = document.getElementById('conversation-history');
  const recent = document.getElementById('conversation-recent');
  const status = document.getElementById('conversation-status');
  const updateStatusTone = () => {
    const value = status?.textContent?.toLowerCase() || '';
    status?.setAttribute('data-tone', /não foi|falhou|erro|interrompid|indisponível/.test(value) ? 'error'
      : /conectando|respondendo|verificando|retomando|reconectando|processando/.test(value) ? 'working'
      : value ? 'success' : '');
  };
  if (status) new MutationObserver(updateStatusTone).observe(status, {childList:true, characterData:true, subtree:true});
  const historyToggle = document.getElementById('conversation-history-toggle');
  const workMemoryToggle = document.getElementById('conversation-work-memory-toggle');
  const workMemoryPanel = document.getElementById('conversation-work-memory');
  const workMemoryContent = document.getElementById('conversation-work-memory-content');
  const conversationShell = document.querySelector('.workspace-conversations');
  const desktopHistory = () => window.matchMedia('(min-width:821px)').matches;
  const closeHistory = () => {
    conversationShell?.classList.remove('history-open');
    if (desktopHistory()) conversationShell?.classList.add('history-collapsed');
    historyToggle?.setAttribute('aria-expanded', 'false');
    if (historyToggle) historyToggle.textContent = 'Conversas';
  };
  historyToggle?.addEventListener('click', () => {
    const collapsed = desktopHistory() && conversationShell?.classList.contains('history-collapsed');
    const open = desktopHistory() ? collapsed : !conversationShell?.classList.contains('history-open');
    if (desktopHistory()) conversationShell?.classList.toggle('history-collapsed', !open);
    else conversationShell?.classList.toggle('history-open', open);
    historyToggle.setAttribute('aria-expanded', String(open));
    historyToggle.textContent = open ? 'Ocultar conversas' : 'Conversas';
  });
  // A new conversation starts with the reading surface clear. The recent
  // list remains one intentional click away instead of competing for focus.
  if (desktopHistory()) closeHistory();
  const closeWorkMemory = () => { if (workMemoryPanel) workMemoryPanel.hidden = true; workMemoryToggle?.setAttribute('aria-expanded', 'false'); };
  let conversationId = null, runId = null, sending = false, controller = null;
  let renderFrame = null, renderTarget = null, renderContent = '';
  let followStreaming = true;
  const isNearHistoryEnd = () => history && (history.scrollHeight - history.scrollTop - history.clientHeight) < 96;
  const isImageGenerationRequest = message => /^(?:agora\s+)?(?:crie|cria|gere|gerar|criar|faca)\s+(?:(?:uma?|a|o)\s+)?(?:imagem|foto|ilustracao|criativo)\b/i.test(
    String(message || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim());
  const isExternalResearchRequest = message => /\b(deep research|pesquisa aprofundada|pesquisa profunda|atualiza[çc][ãa]o de mercado|atualize o mercado|mercado recente)\b/i.test(String(message || ''));
  history?.addEventListener('scroll', () => { followStreaming = isNearHistoryEnd(); }, {passive:true});
  const scrollHistoryToEnd = (force = false) => {
    if (!history || (!force && !isNearHistoryEnd())) return;
    history.scrollTop = history.scrollHeight;
  };
  const renderStreaming = (target, content) => {
    renderTarget = target; renderContent = content;
    if (renderFrame !== null) return;
    const shouldFollow = followStreaming && isNearHistoryEnd();
    renderFrame = requestAnimationFrame(() => {
      renderFrame = null;
      if (renderTarget) {
        CaduConversationRenderer.render(renderTarget, renderContent, true);
        if (shouldFollow) scrollHistoryToEnd(true);
      }
    });
  };
  const flushStreaming = (target, content) => {
    if (renderFrame !== null) cancelAnimationFrame(renderFrame);
    renderFrame = null; renderTarget = null; renderContent = '';
    if (target) CaduConversationRenderer.render(target, content);
  };
  let initialized = false, initializing = null, canSend = false, canReplay = false;
  let loadingThread = false, threadRequest = 0, historyRequest = 0;
  let historyQuery = '';
  const drafts = new Map();
  const pendingKey = 'cadu-pending:' + panel.dataset.draftScope + ':' + document.body.dataset.product;
  let pending = null;
  try {
    const stored = JSON.parse(sessionStorage.getItem(pendingKey) || 'null');
    if (stored && /^[a-f0-9-]{36}$/i.test(stored.id) && typeof stored.signature === 'string') pending = stored;
  } catch (_) { /* Recovery remains available in memory. */ }
  const storePending = value => {
    pending = value;
    try {
      if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value));
      else sessionStorage.removeItem(pendingKey);
    } catch (_) { /* Do not block sending when storage is unavailable. */ }
  };
  async function requestId(payload) {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(payload)));
    const signature = Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
    if (pending?.signature === signature) return pending.id;
    const id = crypto.randomUUID();
    storePending({id, signature});
    return id;
  }
  const draftKeyFor = id => 'cadu-draft:' + panel.dataset.draftScope + ':' + (id || 'new:' + document.body.dataset.product);
  const writeDraft = (id, value) => {
    drafts.set(id || 'new', value);
    try {
      if (value) sessionStorage.setItem(draftKeyFor(id), value);
      else sessionStorage.removeItem(draftKeyFor(id));
    } catch (_) { /* Memory remains usable when browser storage is unavailable. */ }
  };
  const readDraft = id => {
    if (drafts.has(id || 'new')) return drafts.get(id || 'new');
    try { return (sessionStorage.getItem(draftKeyFor(id)) || '').slice(0, 20000); }
    catch (_) { return ''; }
  };
  const saveDraft = () => writeDraft(conversationId, composerValue());
  const searchForm = document.getElementById('conversation-search');
  const mode = document.getElementById('conversation-mode');
  const projectSelect = document.getElementById('conversation-project');
  const contextNote = document.getElementById('conversation-context-note');
  let contextEntities = [], activeContext = {}, boundProjectRef = null;
  const composer = document.getElementById('conversation-message');
  const editor = document.getElementById('conversation-editor') || composer;
  const composerValue = () => editor === composer ? composer.value : editor.textContent || '';
  const setComposerValue = value => {
    const safe = String(value || '').slice(0, 20000);
    composer.value = safe;
    if (editor !== composer) editor.textContent = safe;
  };
  const insertEditorText = value => {
    // Keep rich clipboard markup out of the editable surface while preserving
    // normal caret behavior for pasted text and Shift+Enter line breaks.
    if (document.execCommand?.('insertText', false, value)) return;
    const selection = window.getSelection();
    if (!selection?.rangeCount) { editor.append(document.createTextNode(value)); return; }
    const range = selection.getRangeAt(0); range.deleteContents();
    const node = document.createTextNode(value); range.insertNode(node);
    range.setStartAfter(node); range.collapse(true); selection.removeAllRanges(); selection.addRange(range);
  };
  let modeEntries = [];
  const applyModes = (items, selected) => {
    modeEntries = Array.isArray(items) ? items : [];
    const active = selected || modeEntries.find(item => item.active)?.id || mode.value;
    mode.replaceChildren(...modeEntries.map(item => new Option(item.title, item.id, false, item.id === active)));
    mode.disabled = !modeEntries.length;
  };
  setComposerValue(readDraft(null));
  const contextOptions = (select, rows, emptyLabel, selected) => {
    if (!select) return;
    select.replaceChildren(new Option(emptyLabel, ''), ...rows.map(row => {
      const linkedBrands = (row.related_refs || []).map(ref => contextEntities.find(item => item.ref === ref && item.kind === 'brand')).filter(Boolean);
      const suffix = linkedBrands.length === 1 ? ' · ' + linkedBrands[0].name : '';
      return new Option(row.name + suffix, row.ref, false, row.ref === selected);
    }));
    select.disabled = false;
  };
  const brandForProject = (projectRef, currentBrandRef = '') => {
    const project = contextEntities.find(item => item.kind === 'project' && item.ref === projectRef);
    const brands = (project?.related_refs || []).filter(ref => contextEntities.some(item => item.kind === 'brand' && item.ref === ref));
    return brands.includes(currentBrandRef) ? currentBrandRef : (brands.length === 1 ? brands[0] : null);
  };
  const renderContext = (selected = activeContext) => {
    const projectRef = conversationId && boundProjectRef !== null ? boundProjectRef : selected.project_ref;
    const brandRef = brandForProject(projectRef, selected.brand_ref);
    const brand = contextEntities.find(item => item.kind === 'brand' && item.ref === brandRef);
    contextOptions(projectSelect, contextEntities.filter(item => item.kind === 'project'), 'Sem projeto', projectRef);
    if (projectSelect) projectSelect.disabled = Boolean(conversationId);
    if (contextNote) contextNote.textContent = conversationId
      ? (projectRef ? ('Projeto' + (brand ? ' e marca' : '') + ' definidos na criação desta conversa.') : 'Esta conversa foi criada sem projeto.')
      : projectSelect?.value ? ('Projeto' + (brand ? ' e marca vinculada' : '') + ' para a nova conversa.') : 'Sem projeto: a nova conversa usará apenas o contexto geral.';
    renderWorkMemoryIdentity(project, brand);
    if (pageMode && !conversationId && !sending && history?.querySelector('.workspace-conversation-empty')) renderEmptyState();
  };
  function renderWorkMemoryIdentity(project, brand) {
    const title = document.getElementById('conversation-work-memory-title');
    if (title) title.textContent = project?.name || 'Contexto do projeto';
    const header = workMemoryPanel?.querySelector('header');
    if (!header) return;
    header.querySelector('.conversation-work-memory-identity')?.remove();
    if (!project) return;
    const identity = document.createElement('div'); identity.className = 'conversation-work-memory-identity';
    const mark = document.createElement('span'); mark.className = 'conversation-work-memory-mark';
    if (brand?.logo_url) {
      const image = document.createElement('img'); image.src = brand.logo_url; image.alt = 'Logo de ' + brand.name;
      image.addEventListener('error', () => image.remove()); mark.append(image);
    }
    if (!mark.childElementCount) mark.textContent = (brand?.name || project.name).split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase();
    const copy = document.createElement('span');
    const label = document.createElement('b'); label.textContent = brand?.name || 'Projeto selecionado';
    const detail = document.createElement('small'); detail.textContent = brand ? 'Marca vinculada' : 'Sem marca vinculada';
    copy.append(label, detail); identity.append(mark, copy); header.append(identity);
  }
  async function loadContext() {
    if (!projectSelect) return;
    try {
      const data = await api('context');
      contextEntities = Array.isArray(data.entities) ? data.entities : [];
      activeContext = data.context || {};
      const requestedProject = pageMode && new URLSearchParams(window.location.search).get('project');
      const projectRef = requestedProject && contextEntities.some(item => item.kind === 'project' && item.ref === requestedProject)
        ? requestedProject : activeContext.project_ref;
      const brandRef = brandForProject(projectRef, activeContext.brand_ref);
      if (brandRef !== activeContext.brand_ref || projectRef !== activeContext.project_ref) {
        activeContext = {...activeContext, project_ref: projectRef, brand_ref: brandRef};
        await api('context', 'POST', activeContext);
      }
      renderContext();
      if (pageMode && projectRef) await openWorkMemoryForProject();
    } catch (_) {
      projectSelect.replaceChildren(new Option('Projetos indisponíveis', ''));
      if (contextNote) contextNote.textContent = 'O contexto será disponibilizado quando a conexão do Workspace estiver ativa.';
    }
  }
  async function saveContext() {
    if (!projectSelect) return;
    projectSelect.disabled = true;
    try {
      const data = await api('context', 'POST', {project_ref: projectSelect.value || null, brand_ref: activeContext.brand_ref || null});
      activeContext = data.context || {};
      renderContext(activeContext);
      status.textContent = 'Contexto salvo para a próxima conversa.';
    } catch (error) {
      renderContext(activeContext);
      status.textContent = unavailableMessage('Não foi possível salvar o contexto', error);
    }
  }
  projectSelect?.addEventListener('change', () => {
    const brandRef = brandForProject(projectSelect.value, activeContext.brand_ref);
    activeContext = {...activeContext, project_ref: projectSelect.value, brand_ref: brandRef};
    renderContext(activeContext);
    saveContext();
    void openWorkMemoryForProject();
  });
  async function openWorkMemoryForProject() {
    const projectRef = conversationId ? boundProjectRef : (activeContext?.project_ref || projectSelect?.value || '');
    if (!projectRef || !workMemoryPanel) return;
    workMemoryPanel.hidden = false;
    workMemoryToggle?.setAttribute('aria-expanded', 'true');
    await loadWorkMemory();
  }
  async function loadWorkMemory() {
    const projectRef = conversationId ? boundProjectRef : (activeContext?.project_ref || projectSelect?.value || '');
    if (!projectRef || !workMemoryContent) return;
    workMemoryContent.textContent = 'Carregando contexto…';
    try {
      const data = await api('conversations/work-memory?project=' + encodeURIComponent(projectRef));
      workMemoryContent.replaceChildren();
      const render = (title, items, review) => {
        const section = document.createElement('section'); section.className = 'conversation-work-memory-section';
        const heading = document.createElement('h3'); heading.textContent = title; section.append(heading);
        if (!items?.length) { const empty = document.createElement('p'); empty.textContent = 'Nada registrado ainda.'; section.append(empty); }
        const visibleItems = (items || []).slice(0, 2);
        const remainingItems = (items || []).slice(2);
        const addRow = item => { const row = document.createElement('article'); const label = document.createElement('small'); label.textContent = ({decision:'Decisão',constraint:'Restrição',risk:'Risco',next_step:'Próximo passo',brand_context:'Marca'}[item.kind] || 'Registro'); const text = document.createElement('p'); text.textContent = item.summary; row.append(label,text); if (review) { const actions=document.createElement('div'); for (const [action,name] of [['confirm','Confirmar'],['dismiss','Descartar'],...(item.kind === 'brand_context' ? [['promote','Usar no cliente']] : [])]) { const button=document.createElement('button'); button.type='button'; button.textContent=name; button.addEventListener('click', async () => { await api('conversations/work-memory/'+item.id,'PATCH',{action}); loadWorkMemory(); }); actions.append(button); } row.append(actions); } return row; };
        visibleItems.forEach(item => section.append(addRow(item)));
        if (remainingItems.length) { const more = document.createElement('details'); more.className = 'conversation-work-memory-more'; const summary = document.createElement('summary'); summary.textContent = 'Ver mais ' + remainingItems.length + ' registro' + (remainingItems.length === 1 ? '' : 's'); more.append(summary); remainingItems.forEach(item => more.append(addRow(item))); section.append(more); }
        workMemoryContent.append(section);
      };
      render('Contexto confirmado', data.confirmed, false); render('Para revisar', data.proposals, true);
      const section=document.createElement('section'); section.className='conversation-work-memory-section'; const h=document.createElement('h3'); h.textContent='Discussões da equipe'; section.append(h);
      data.weeks?.forEach(week => week.conversations.forEach(conversation => { const button=document.createElement('button'); button.type='button'; button.textContent=(conversation.author_name || 'Equipe') + ' · ' + (conversation.title || 'Conversa'); button.addEventListener('click', () => { closeWorkMemory(); openConversation(String(conversation.id)); }); section.append(button); })); if (!data.weeks?.length) { const p=document.createElement('p'); p.textContent='As novas conversas do projeto aparecerão aqui por semana.'; section.append(p); } workMemoryContent.append(section);
    } catch (error) { workMemoryContent.textContent = error.message || 'Não foi possível carregar o caderno.'; }
  }
  workMemoryToggle?.addEventListener('click', async () => { const projectRef = conversationId ? boundProjectRef : (activeContext?.project_ref || projectSelect?.value || ''); if (!projectRef) { status.textContent='Selecione um projeto para abrir o contexto.'; return; } const open=workMemoryPanel.hidden; workMemoryPanel.hidden=!open; workMemoryToggle.setAttribute('aria-expanded',String(open)); if (open) await loadWorkMemory(); });
  document.getElementById('conversation-work-memory-close')?.addEventListener('click', closeWorkMemory);
  const attachments = new CaduAttachments(panel, status);
  const sendButton = document.getElementById('conversation-send');
  const updateSend = () => {
    const disabled = sending || loadingThread || !canSend || mode.disabled;
    composer.disabled = disabled;
    editor.contentEditable = String(!disabled);
    editor.setAttribute('aria-disabled', String(disabled));
    if (sendButton) sendButton.disabled = disabled || (!composerValue().trim() && !attachments.items.length);
  };
  const resizeComposer = () => {
    if (!editor || !pageMode) return;
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    editor.style.height = '0px';
    editor.style.height = Math.min(Math.max(editor.scrollHeight, 58), Math.round(viewportHeight * 0.36)) + 'px';
  };
  let viewportFrame = null;
  const syncConversationViewport = () => {
    if (!pageMode) return;
    if (viewportFrame !== null) cancelAnimationFrame(viewportFrame);
    viewportFrame = requestAnimationFrame(() => {
      viewportFrame = null;
      const height = Math.round(window.visualViewport?.height || window.innerHeight);
      document.documentElement.style.setProperty('--conversation-viewport-height', height + 'px');
      resizeComposer();
    });
  };
  window.addEventListener('resize', syncConversationViewport);
  window.visualViewport?.addEventListener('resize', syncConversationViewport);
  window.visualViewport?.addEventListener('scroll', syncConversationViewport);
  panel.addEventListener('attachmentschange', updateSend);
  mode?.addEventListener('change', async () => {
    const selected = mode.value;
    const previous = modeEntries.find(item => item.active)?.id;
    mode.disabled = true; updateSend();
    try {
      const data = await api('conversations/modes/active', 'POST', {mode: selected});
      applyModes(data.modes, selected);
      status.textContent = 'Modo salvo para as próximas conversas.';
    } catch (error) {
      applyModes(modeEntries, previous);
      status.textContent = unavailableMessage('Não foi possível trocar o modo', error);
    } finally { updateSend(); }
  });
  // PHP chat-v2: Enter sends; Shift+Enter inserts a line. Never send mid-IME.
  editor.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (editor.contentEditable === 'true' && !sending && !mode?.disabled) {
        document.getElementById('conversation-form').requestSubmit();
      }
    } else if (event.key === 'Enter' && event.shiftKey && !event.isComposing) {
      event.preventDefault();
      insertEditorText('\n');
    }
  });
  editor.addEventListener('paste', event => {
    if (event.defaultPrevented || editor.contentEditable !== 'true') return;
    const text = event.clipboardData?.getData('text/plain') || '';
    event.preventDefault(); if (text) insertEditorText(text);
  });
  editor.addEventListener('input', () => {
    if (editor !== composer && composerValue().length > 20000) setComposerValue(composerValue());
    else if (editor !== composer) composer.value = composerValue();
    saveDraft();
    resizeComposer();
    updateSend();
  });
  editor.addEventListener('focus', () => {
    // Mobile Safari can report the reduced viewport a beat after focus.
    // Re-measuring keeps the composer above the software keyboard without
    // scrolling the full document or disturbing the reading position.
    window.setTimeout(syncConversationViewport, 120);
  });
  const background = [...document.querySelectorAll('.family-nav, .family-layout, .cadu-skills-top-nav, .cadu-app-shell, .portal > #content, .portal > footer')];
  let previousOverflow = '';
  const close = () => {
    if (pageMode) return;
    panel.hidden = true; backdrop.hidden = true; background.forEach(node => { node.inert = false; }); document.body.style.overflow = previousOverflow;
    opener?.setAttribute('aria-expanded', 'false'); opener?.focus();
  };
  function setConversationUrl(id) {
    if (!pageMode) return;
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('conversation', id); else url.searchParams.delete('conversation');
    window.history.replaceState({}, '', url);
  }
  async function openConversation(id, recovering = false) {
    if (sending && !recovering) return false;
    saveDraft();
    const request = ++threadRequest;
    loadingThread = true; updateSend();
    try {
      const result = await api('conversations/' + encodeURIComponent(id) + '/messages');
      if (request !== threadRequest) return;
      history.replaceChildren(); conversationId = id; boundProjectRef = result.context?.project_ref || '';
      attachments.clear(); setComposerValue(readDraft(id)); resizeComposer();
      renderContext();
      recent?.querySelectorAll('button[data-conversation-id]').forEach(button => {
        if (button.dataset.conversationId === id) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
      });
      for (const message of result.messages) addMessage(message.role, message.content, message.files, message.metadata, result.context?.project_ref || '');
      setConversationUrl(id);
      status.textContent = result.context ? 'Conversa retomada com o projeto e perfil de origem.' : 'Conversa anterior carregada. O próximo envio usará o projeto ativo.';
      return true;
    } catch (error) { if (request === threadRequest) status.textContent = error.message; }
    finally { if (request === threadRequest) { loadingThread = false; updateSend(); } }
  }
  async function loadHistory() {
    if (sending) return;
    const request = ++historyRequest;
    const target = recent || history;
    try {
      const params = new URLSearchParams({q: historyQuery});
      const data = await api('conversations?' + params);
      if (request !== historyRequest) return;
      if (!recent) { saveDraft(); conversationId = null; setComposerValue(readDraft(null)); resizeComposer(); }
      target.replaceChildren();
      const isArchived = thread => ['arquivada', 'archived'].includes(String(thread.status || '').toLowerCase());
      const renderConversation = thread => {
        const row = document.createElement('article');
        const button = document.createElement('button'); button.type = 'button'; button.textContent = thread.title || 'Conversa sem título';
        button.dataset.conversationId = String(thread.id);
        if (String(thread.id) === conversationId) button.setAttribute('aria-current', 'page');
        row.append(button); target.append(row);
        button.addEventListener('click', () => { closeHistory(); openConversation(String(thread.id)); });
        if (recent && data.can_manage === true) {
          const actions = document.createElement('details');
          const summary = document.createElement('summary'); summary.textContent = 'Opções';
          summary.setAttribute('aria-label', 'Opções de ' + (thread.title || 'conversa'));
          const form = document.createElement('form');
          const title = document.createElement('input'); title.value = thread.title || ''; title.maxLength = 150; title.required = true;
          title.setAttribute('aria-label', 'Título da conversa');
          const save = document.createElement('button'); save.type = 'submit'; save.textContent = 'Salvar título';
          const archivedConversation = isArchived(thread);
          const archive = document.createElement('button'); archive.type = 'button'; archive.textContent = archivedConversation ? 'Restaurar' : 'Arquivar';
          const update = async data => {
            if (sending || loadingThread) return;
            save.disabled = archive.disabled = true;
            try {
              await api('conversations/' + encodeURIComponent(thread.id), 'PATCH', data);
              await loadHistory();
              status.textContent = 'title' in data ? 'Título salvo.' : data.archived ? 'Conversa arquivada.' : 'Conversa restaurada.';
            } catch (error) { status.textContent = error.message; }
            finally { save.disabled = archive.disabled = false; }
          };
          form.addEventListener('submit', event => { event.preventDefault(); update({title: title.value.trim()}); });
          archive.addEventListener('click', () => update({archived: !archivedConversation}));
          form.append(title, save); actions.append(summary, form, archive); row.append(actions);
        }
      };
      const appendGroup = (title, rows) => {
        if (!rows.length) return;
        const heading = document.createElement('p'); heading.className = 'conversation-history-group'; heading.textContent = title;
        target.append(heading); rows.forEach(renderConversation);
      };
      appendGroup('Recentes', data.conversations.filter(thread => !isArchived(thread)));
      appendGroup('Arquivadas', data.conversations.filter(isArchived));
      if (!data.conversations.length) target.textContent = 'Nenhuma conversa encontrada.';
    } catch (error) { if (request === historyRequest) status.textContent = unavailableMessage('Não foi possível carregar seu histórico', error); }
  }
  searchForm?.addEventListener('submit', event => { event.preventDefault(); historyQuery = new FormData(searchForm).get('q').trim(); loadHistory(); });
  function addSources(sources) {
    if (!Array.isArray(sources) || !sources.length) return;
    const card = document.createElement('section'); card.className = 'conversation-sources';
    const heading = document.createElement('strong'); heading.textContent = 'Fontes do projeto consultadas'; card.append(heading);
    const list = document.createElement('ul');
    sources.slice(0, 4).forEach(source => {
      if (!source || typeof source !== 'object') return;
      const item = document.createElement('li'), excerpt = document.createElement('span'); let title = document.createElement('b');
      title.textContent = source.title || 'Fonte sem título'; if (source.url) { try { const url = new URL(source.url); if (url.protocol === 'https:') { const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener'; link.textContent = title.textContent; title = link; } } catch (_) {} } excerpt.textContent = source.excerpt || '';
      item.append(title); if (excerpt.textContent) item.append(excerpt); list.append(item);
    });
    if (list.childElementCount) { card.append(list); history.append(card); }
  }
  function planTitle(content) {
    const heading = String(content || '').match(/^#{1,6}\s+(.+)$/m);
    return (heading?.[1] || 'Plano Cadu').replace(/[*`]/g, '').trim().slice(0, 255) || 'Plano Cadu';
  }
  function actionBarFor(text) {
    let actions = text.parentElement?.querySelector('.conversation-message-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'conversation-message-actions';
      text.parentElement?.append(actions);
    }
    return actions;
  }
  function addMessageActions(text, content) {
    if (!text || text.parentElement?.querySelector('[data-conversation-copy]')) return;
    const actions = actionBarFor(text);
    const icon = {copy:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>', continue:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h12"/><path d="m13 6 6 6-6 6"/></svg>'};
    const copy = document.createElement('button'); copy.type = 'button'; copy.dataset.conversationCopy = ''; copy.className = 'conversation-message-action'; copy.setAttribute('aria-label', 'Copiar resposta'); copy.setAttribute('title', 'Copiar resposta'); copy.innerHTML = icon.copy;
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(String(content || '')); copy.setAttribute('title', 'Copiado'); }
      catch (_) { status.textContent = 'Não foi possível copiar a resposta neste navegador.'; }
    });
    const continueButton = document.createElement('button'); continueButton.type = 'button'; continueButton.className = 'conversation-message-action'; continueButton.setAttribute('aria-label', 'Continuar esta resposta'); continueButton.setAttribute('title', 'Continuar esta resposta'); continueButton.innerHTML = icon.continue;
    continueButton.addEventListener('click', () => {
      setComposerValue('Continue a partir da resposta anterior e aprofunde os próximos passos.');
      resizeComposer(); updateSend(); editor.focus();
    });
    actions.append(copy, continueButton);
  }
  function addSavePlanAction(text, content, projectRef) {
    if (!text || !content?.trim() || typeof projectRef !== 'string' || !projectRef.startsWith('ci:')) return;
    const projectId = projectRef.slice(3);
    if (!/^[a-f0-9-]{36}$/i.test(projectId) || text.parentElement?.querySelector('[data-save-plan]')) return;
    const actions = actionBarFor(text);
    const save = document.createElement('button'); save.type = 'button'; save.dataset.savePlan = projectId;
    save.className = 'conversation-message-action conversation-message-action--save';
    save.setAttribute('aria-label', 'Salvar no projeto'); save.setAttribute('title', 'Salvar no projeto');
    save.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h11l3 3v13H5z"/><path d="M8 4v6h8V4M8 20v-6h8v6"/></svg>';
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
        const response = await fetch('/workspace/api/projetos/' + encodeURIComponent(projectId) + '/documentos', {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', ...(csrf ? {'X-CSRF-Token': csrf} : {})},
          body: JSON.stringify({title: planTitle(content), content})
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || 'Não foi possível salvar o plano.');
        save.setAttribute('title', 'Salvo no projeto');
        status.textContent = 'Salvo no projeto.';
      } catch (error) {
        save.disabled = false;
        status.textContent = error.message || 'Não foi possível salvar o plano.';
      }
    });
    actions.append(save);
  }
  function addMessage(role, content, files = [], metadata = {}, projectRef = '') {
    const entry = document.createElement('article'); entry.className = 'conversation-message ' + (role === 'user' ? 'from-user' : 'from-cadu');
    const label = document.createElement('strong'); label.textContent = role === 'user' ? 'Você' : 'Resposta';
    if (role === 'assistant') { const elapsed = document.createElement('p'); elapsed.className = 'conversation-work-time'; elapsed.textContent = 'Trabalhando…'; entry.append(elapsed); }
    const text = document.createElement('div');
    if (role === 'assistant') CaduConversationRenderer.render(text, content);
    else {
      // A sent prompt is context, not the focal point of the reading flow.
      // Keep it one click away, with enough of the request visible to orient
      // the person when revisiting a long conversation.
      const details = document.createElement('details'); details.className = 'conversation-user-context';
      const summary = document.createElement('summary');
      const normalized = String(content || '').replace(/\s+/g, ' ').trim();
      summary.textContent = normalized.length > 88 ? normalized.slice(0, 88).trimEnd() + '…' : normalized || 'Mensagem enviada';
      const full = document.createElement('p'); full.textContent = content;
      details.append(summary, full); text.append(details);
    }
    entry.append(label, text);
    CaduConversationRenderer.renderFiles(entry, files);
    history.append(entry);
    if (role === 'assistant') addSources(metadata?.project_sources);
    if (role === 'assistant' && content?.trim()) {
      addMessageActions(text, content);
      addSavePlanAction(text, content, projectRef);
    }
    scrollHistoryToEnd(true);
    return text;
  }
  function setMessageElapsed(text, startedAt) {
    const note = text?.parentElement?.querySelector('.conversation-work-time');
    if (!note || !startedAt) return;
    const seconds = Math.max(1, Math.round((performance.now() - startedAt) / 1000));
    note.textContent = seconds < 60 ? 'Trabalhou por ' + seconds + ' s' : 'Trabalhou por ' + Math.floor(seconds / 60) + ' min ' + (seconds % 60) + ' s';
  }
  function renderEmptyState() {
    if (!pageMode) return;
    history.replaceChildren();
    const projectRef = activeContext?.project_ref || projectSelect?.value || '';
    const project = contextEntities.find(item => item.kind === 'project' && item.ref === projectRef);
    const projectName = String(project?.name || '').trim();
    const suggestionsForProject = projectName ? [
      ['Faça a leitura de partida', 'Objetivo, entregas, riscos e decisões que faltam',
        `Faça uma leitura de partida do projeto ${projectName}: objetivo, entregas, riscos e as decisões que preciso tomar agora.`],
      ['Estruture o próximo movimento', 'Plano de ação com responsáveis, dependências e prazo',
        `Com base no projeto ${projectName} e na marca vinculada, proponha o próximo movimento em ordem de execução. Para cada passo, explique o que fazer na prática, qual resultado ele destrava, como a marca deve aparecer, responsável, dependência e prazo sugerido. Numere 1, 2, 3… sem repetir o número e diferencie o que é fato, premissa e pendência.`],
      ['Transforme em plano de mídia', 'Estratégia, audiências, canais, formatos e operação',
        `Transforme o contexto do projeto ${projectName} em um plano de mídia: estratégia, audiências, canais, formatos, etapas e critérios de otimização.`],
      ['Encontre as lacunas do briefing', 'O que validar antes de produzir ou ativar',
        `Quais informações críticas ainda faltam no projeto ${projectName} antes de avançar? Ordene por impacto e proponha como validar cada uma.`],
      ['Compare caminhos estratégicos', 'Três escolhas com benefícios, riscos e implicações',
        `Proponha três caminhos estratégicos para o projeto ${projectName}. Compare benefício, risco, dependência e quando cada um faz sentido.`],
      ['Prepare uma atualização objetiva', 'Resumo executivo para alinhar equipe e cliente',
        `Prepare uma atualização objetiva do projeto ${projectName}: onde estamos, o que foi decidido, o que está em risco e o próximo passo.`],
      ['Atualização de mercado', 'Fontes recentes, impactos e próximos sinais',
        `Faça uma atualização de mercado recente para o projeto ${projectName}. Pesquise fontes públicas, traga links e datas, destaque impactos para a marca e recomende os próximos sinais para acompanhar.`, '≈ 900 créditos'],
      ['Pesquisa aprofundada', 'Cenário, concorrência, tendências e implicações',
        `Faça uma pesquisa aprofundada (deep research) para o projeto ${projectName}. Investigue mercado, concorrentes, tendências e evidências recentes; cite fontes e datas, diferencie fatos de inferências e consolide implicações estratégicas para a marca.`, '≈ 4.200 créditos'],
    ] : [
      ['Estruture um novo projeto', 'Briefing mínimo para sair da conversa com direção',
        'Quero estruturar um novo projeto. Faça as perguntas essenciais e, onde faltar dado, avance com premissas claramente marcadas.'],
      ['Transforme um briefing em plano', 'Estratégia, audiências, canais, formatos e etapas',
        'Vou colar um briefing. Transforme-o em estratégia, audiências, plano de mídia, etapas e decisões pendentes.'],
      ['Decida antes de produzir', 'Opções, trade-offs e recomendação objetiva',
        'Tenho uma decisão de comunicação ou mídia para tomar. Ajude-me a comparar opções, riscos, dependências e uma recomendação final.'],
      ['Mapeie uma audiência', 'Necessidade, sinais, jornada e ativação possível',
        'Ajude-me a definir uma audiência prioritária: necessidade, sinais de afinidade, jornada, mensagem e formas de ativação.'],
      ['Revise uma proposta', 'Pontos fortes, lacunas e como torná-la defensável',
        'Vou colar uma proposta. Revise criticamente: o que está forte, o que falta provar, riscos e como melhorar a recomendação.'],
      ['Organize a próxima reunião', 'Pauta, decisões necessárias e materiais de apoio',
        'Prepare uma pauta de trabalho para a próxima reunião com cliente: decisões necessárias, perguntas, materiais e próximos passos.'],
    ];
    const empty = document.createElement('div'); empty.className = 'workspace-conversation-empty';
    const heading = document.createElement('strong'); heading.textContent = projectName ? `Vamos avançar ${projectName}` : 'Vamos começar por uma decisão';
    const description = document.createElement('span'); description.textContent = projectName
      ? 'Escolha uma ação que use o contexto do projeto já selecionado.'
      : 'Escolha um ponto de partida concreto ou selecione um projeto para usar seu contexto.';
    const suggestions = document.createElement('div'); suggestions.className = 'conversation-suggestions';
    suggestionsForProject.forEach(([prompt, detail, request, estimate]) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'conversation-suggestion';
      const title = document.createElement('strong'); title.textContent = prompt;
      const copy = document.createElement('span'); copy.textContent = detail;
      button.append(title, copy);
      if (estimate) { const cost = document.createElement('em'); cost.textContent = estimate; cost.setAttribute('aria-label', 'Estimativa de consumo: ' + estimate); button.append(cost); }
      button.addEventListener('click', () => { setComposerValue(request); resizeComposer(); updateSend(); editor.focus(); });
      suggestions.append(button);
    });
    empty.append(heading, description, suggestions);
    history.append(empty);
  }
  function addCatalogCard(data) {
    if (!Array.isArray(data.records) || !data.records.length) return;
    if (data.catalog_kind === 'canal') { addChannelCard(data.records[0]); return; }
    const card = document.createElement('section'); card.className = 'conversation-catalog-card';
    const kind = String(data.catalog_kind || '');
    card.classList.add('is-' + kind.replace(/[^a-z-]/g, ''));
    const heading = document.createElement('h4'); heading.textContent = ({canais:'Canais recomendados', formatos:'Formatos compatíveis', interativos:'Experiências interativas', audiencias:'Audiências', places:'Places', planos:'Planos'})[kind] || 'Catálogo'; card.append(heading);
    const list = document.createElement('ul');
    data.records.forEach(record => {
      const item = document.createElement('li'), name = document.createElement('strong'), detail = document.createElement('span');
      name.textContent = record.name || 'Item do catálogo';
      detail.textContent = [record.description || record.category || record.dimensions || '', record.audience || ''].filter(Boolean).join(' · ');
      item.append(name); if (detail.textContent) item.append(detail); list.append(item);
    });
    const shouldFollow = isNearHistoryEnd();
    card.append(list); history.append(card); if (shouldFollow) scrollHistoryToEnd(true);
  }
  function addChannelCard(channel) {
    if (!channel || typeof channel !== 'object') return;
    const card = document.createElement('section'); card.className = 'conversation-channel-card';
    const head = document.createElement('header');
    const mark = document.createElement('span'); mark.className = 'conversation-channel-mark';
    if (channel.logo_url) { const image = document.createElement('img'); image.src = channel.logo_url; image.alt = 'Logo de ' + (channel.name || 'canal'); image.addEventListener('error', () => image.remove()); mark.append(image); }
    if (!mark.childElementCount) mark.textContent = String(channel.name || 'Canal').slice(0, 2).toUpperCase();
    const title = document.createElement('div'); const name = document.createElement('h4'); name.textContent = channel.name || 'Canal'; const category = document.createElement('p'); category.textContent = [channel.category, channel.audience].filter(Boolean).join(' · ') || 'Canal do catálogo'; title.append(name, category); head.append(mark, title); card.append(head);
    if (channel.description) { const description = document.createElement('p'); description.className = 'conversation-channel-description'; description.textContent = channel.description; card.append(description); }
    const section = (label, values) => { if (!values?.length) return; const block = document.createElement('section'); const heading = document.createElement('strong'); heading.textContent = label; const list = document.createElement('ul'); values.slice(0, 4).forEach(value => { const item = document.createElement('li'); item.textContent = value; list.append(item); }); block.append(heading, list); card.append(block); };
    section('Formatos disponíveis', channel.formats); section('Diferenciais', channel.differences);
    const facts = document.createElement('dl');
    for (const [label, value] of [['Modelo de compra', channel.buying_model], ['Prazo', channel.lead_time], ['Investimento mínimo', channel.budget_minimum]]) { if (!value) continue; const term = document.createElement('dt'); term.textContent = label; const definition = document.createElement('dd'); definition.textContent = String(value); facts.append(term, definition); }
    if (facts.childElementCount) { const factsSection = document.createElement('section'); factsSection.className = 'conversation-channel-facts'; factsSection.append(facts); card.append(factsSection); }
    const caveat = document.createElement('small'); caveat.className = 'conversation-channel-caveat'; caveat.textContent = channel.budget_status || 'Dados sujeitos à validação.'; card.append(caveat);
    const actions = document.createElement('footer');
    const action = (label, prompt, primary = false) => { const button = document.createElement('button'); button.type = 'button'; button.textContent = label; if (primary) button.className = 'is-primary'; button.addEventListener('click', () => { setComposerValue(prompt); resizeComposer(); updateSend(); editor.focus(); }); actions.append(button); };
    action('Criar briefing', `Crie um briefing de campanha usando ${channel.name} como canal prioritário. Traga objetivo, público, formato, entregas, pendências e o que deve ser validado comercialmente.`, true);
    action('Adicionar ao plano', `Avalie ${channel.name} para o plano atual: papel no funil, formato, audiência, dependências, riscos e critério de decisão.`);
    action('Comparar', `Compare ${channel.name} com outro canal mais adequado ao objetivo deste projeto. Mostre diferenças, complementaridade, riscos e quando escolher cada um.`);
    if (channel.detail_url) { const link = document.createElement('a'); link.href = channel.detail_url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Ver detalhes'; actions.append(link); }
    card.append(actions); history.append(card); scrollHistoryToEnd(true);
  }
  function addDocumentCard(data) {
    if (!data.document || typeof data.preview !== 'string') return;
    const card = document.createElement('section'); card.className = 'conversation-catalog-card conversation-document-card';
    const heading = document.createElement('h4'); heading.textContent = 'SmartDoc consultado';
    const title = document.createElement('strong'); title.textContent = data.document.title || 'Documento';
    const meta = document.createElement('span'); meta.textContent = [data.document.type, data.document.status].filter(Boolean).join(' · ');
    const preview = document.createElement('p'); preview.textContent = data.preview;
    card.append(heading, title); if (meta.textContent) card.append(meta); card.append(preview);
    const shouldFollow = isNearHistoryEnd();
    history.append(card); if (shouldFollow) scrollHistoryToEnd(true);
  }
  function addResultCard(data) {
    const result = data?.result;
    if (!result || typeof result !== 'object' || !result.type) return;
    const card = document.createElement('section');
    card.className = 'conversation-result-card is-' + String(result.type).replace(/[^a-z-]/g, '');
    const header = document.createElement('header');
    const type = document.createElement('span'); type.className = 'conversation-result-type';
    type.textContent = ({research:'Pesquisa', audience:'Audiências', link:'Verificação', document:'Documento'})[result.type] || 'Resultado';
    const title = document.createElement('h4'); title.textContent = result.title || 'Resultado disponível';
    header.append(type, title);
    if (result.status) { const statusBadge = document.createElement('span'); statusBadge.className = 'conversation-result-status'; statusBadge.textContent = result.status; header.append(statusBadge); }
    card.append(header);
    if (result.summary) { const summary = document.createElement('p'); summary.className = 'conversation-result-summary'; summary.textContent = result.summary; card.append(summary); }
    (Array.isArray(result.media) ? result.media : []).slice(0, 3).forEach(media => {
      if (media?.kind !== 'image' || typeof media.url !== 'string') return;
      try { const url = new URL(media.url); if (url.protocol !== 'https:') return; } catch (_) { return; }
      const image = document.createElement('img'); image.className = 'conversation-result-media'; image.src = media.url; image.alt = media.alt || ''; image.loading = 'lazy'; card.append(image);
    });
    const items = Array.isArray(result.items) ? result.items : [];
    if (items.length) {
      const list = document.createElement('div'); list.className = 'conversation-result-items';
      items.slice(0, 10).forEach(item => {
        const row = document.createElement('article');
        const rowTitle = document.createElement('strong'); rowTitle.textContent = item?.title || 'Resultado'; row.append(rowTitle);
        if (item?.excerpt) { const excerpt = document.createElement('span'); excerpt.textContent = item.excerpt; row.append(excerpt); }
        if (Array.isArray(item?.metrics) && item.metrics.length) {
          const metrics = document.createElement('div'); metrics.className = 'conversation-result-metrics';
          item.metrics.slice(0, 3).forEach(metric => { const value = document.createElement('span'); value.textContent = (metric.label || '') + ': ' + (metric.value || ''); metrics.append(value); });
          row.append(metrics);
        }
        if (item?.url) {
          try { const url = new URL(item.url); if (url.protocol === 'https:') { const source = document.createElement('a'); source.href = url.href; source.target = '_blank'; source.rel = 'noopener'; source.textContent = 'Abrir fonte'; row.append(source); } } catch (_) {}
        }
        list.append(row);
      });
      card.append(list);
    }
    const actions = Array.isArray(result.actions) ? result.actions : [];
    if (actions.length) {
      const footer = document.createElement('footer'); footer.className = 'conversation-result-actions';
      actions.slice(0, 3).forEach(action => {
        if (!action?.label) return;
        const button = document.createElement('button'); button.type = 'button'; button.textContent = action.label;
        button.className = action.style === 'primary' ? 'is-primary' : '';
        button.addEventListener('click', () => {
          if (action.prompt) { setComposerValue(action.prompt); resizeComposer(); updateSend(); editor.focus(); return; }
          if (action.id === 'open_link' && action.url) {
            try { const url = new URL(action.url); if (url.protocol === 'https:') window.open(url.href, '_blank', 'noopener'); } catch (_) {}
          }
        });
        footer.append(button);
      });
      if (footer.childElementCount) card.append(footer);
    }
    const shouldFollow = isNearHistoryEnd();
    history.append(card); if (shouldFollow) scrollHistoryToEnd(true);
  }
  async function resumePending(requested) {
    if (!canReplay || !pending || sending || loadingThread) return;
    const pendingId = pending.id;
    const previousModeDisabled = mode.disabled;
    const stop = document.getElementById('conversation-stop');
    const previousStatus = status.textContent;
    let output = null, answer = '', terminal = null, recoveredConversation = null;
    sending = true; mode.disabled = true; attachments.lock(true); updateSend();
    controller = new AbortController(); runId = null;
    status.textContent = 'Verificando o envio anterior…';
    try {
      const run = await api('conversations/runs/' + encodeURIComponent(pendingId), 'GET', undefined, controller.signal);
      if ((requested && requested !== run.conversation_id) || !run.replay) {
        status.textContent = previousStatus;
        return; // Honor explicit navigation; old synchronous runs have no journal.
      }
      recoveredConversation = run.conversation_id;
      if (!await openConversation(run.conversation_id, true)) return;
      // Recheck after fetching history: final persistence may have raced the load.
      const latest = await api('conversations/runs/' + encodeURIComponent(pendingId), 'GET', undefined, controller.signal);
      if (latest.status !== 'running') {
        terminal = latest.status;
        storePending(null);
        return;
      }
      runId = pendingId;
      stop.hidden = !canSend;
      status.textContent = 'Retomando a resposta já iniciada…';
      output = addMessage('assistant', '');
      // After reload replay from zero: the page has no cached partial response.
      // A transient network retry inside queuedEvents keeps its existing cursor.
      for await (const data of queuedEvents(run, controller.signal)) {
        if (data.event === 'message' || data.event === 'replace') {
          answer = data.event === 'replace' ? data.text : answer + data.text;
          renderStreaming(output, answer);
        } else if (data.event === 'catalog') addCatalogCard(data);
        else if (data.event === 'result') addResultCard(data);
        else if (data.event === 'sources') addSources(data.sources);
        else if (data.event === 'document') addDocumentCard(data);
        else if (data.event === 'progress' || data.event === 'error') status.textContent = data.message;
        else if (data.event === 'done') { terminal = data.status; storePending(null); }
      }
    } catch (error) {
      status.textContent = error.name === 'AbortError'
        ? 'Acompanhamento interrompido. Consulte o histórico para conferir o estado da resposta.'
        : 'Não foi possível retomar agora. Nenhuma mensagem foi reenviada. ' + error.message;
    } finally {
      flushStreaming(output, answer);
      sending = false; controller = null; runId = null; stop.hidden = true;
      mode.disabled = previousModeDisabled; attachments.lock(false); updateSend();
      if (terminal && recoveredConversation) {
        await openConversation(recoveredConversation);
        status.textContent = terminal === 'completed' ? 'Resposta recuperada do histórico.'
          : terminal === 'stopped' ? 'Geração interrompida. Confira o conteúdo salvo no histórico.'
          : 'A geração falhou. Confira o conteúdo parcial salvo no histórico.';
      }
    }
  }
  async function initialize() {
    if (document.body.dataset.authenticated !== 'true' || sending || initialized) return;
    if (initializing) return initializing;
    initializing = (async () => {
      mode.disabled = true; canSend = false; updateSend();
      // History and context enrich the page, but neither should sit on the
      // critical path to a usable composer.
      const backgroundLoad = Promise.all([loadHistory(), loadContext()]);
      try {
        const capabilities = await api('conversations/capabilities');
        canSend = capabilities.send === true;
        canReplay = capabilities.replay === true;
        // Routing is server-owned and automatic. Loading a hidden selector
        // before enabling the editor added a full, serial round trip.
        mode.disabled = !canSend;
        attachments.configure({...capabilities, attachments: canSend && capabilities.attachments === true});
        initialized = true;
        status.textContent = !canSend
          ? (capabilities.reason || 'Envio indisponível. Você pode consultar seu histórico.')
          : '';
      } catch (error) {
        canSend = false; mode.disabled = true; attachments.configure({attachments:false});
        status.textContent = unavailableMessage('Não foi possível iniciar as conversas', error);
      } finally { updateSend(); }
      await backgroundLoad;
      const starterPrompt = pageMode && new URLSearchParams(window.location.search).get('prompt');
      if (starterPrompt && !conversationId && !composerValue().trim()) {
        setComposerValue(starterPrompt);
        resizeComposer();
        updateSend();
      }
      resizeComposer();
      const requested = pageMode && new URLSearchParams(window.location.search).get('conversation');
      if (requested && !conversationId) await openConversation(requested);
      else if (recent && !conversationId) renderEmptyState();
      await resumePending(requested);
    })();
    try { await initializing; } finally { initializing = null; }
  }
  opener?.addEventListener('click', async () => {
    if (!panel.hidden) return;
    const alreadyInitialized = initialized;
    previousOverflow = document.body.style.overflow;
    panel.hidden = false; backdrop.hidden = false; background.forEach(node => node.inert = true); document.body.style.overflow = 'hidden'; opener.setAttribute('aria-expanded', 'true'); panel.focus();
    await initialize();
    if (alreadyInitialized) await resumePending(conversationId);
  });
  window.addEventListener('online', () => {
    if (initialized && !panel.hidden) resumePending(conversationId);
  });
  if (pageMode) initialize();
  document.getElementById('conversation-list')?.addEventListener('click', () => loadHistory());
  document.getElementById('conversation-close')?.addEventListener('click', close); backdrop?.addEventListener('click', close);
  document.addEventListener('keydown', event => {
    if (pageMode || panel.hidden) return;
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key !== 'Tab') return;
    const nodes = [...panel.querySelectorAll('a[href],button,input,textarea,select')].filter(node => !node.disabled && node.getClientRects().length);
    if (!nodes.length) return;
    if (!panel.contains(document.activeElement)) { event.preventDefault(); nodes[0].focus(); return; }
    if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === panel)) { event.preventDefault(); nodes.at(-1).focus(); }
    else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus(); }
  });
  document.getElementById('conversation-width')?.addEventListener('input', event => panel.style.setProperty('--panel-width', event.target.value + 'px'));
  document.getElementById('conversation-new')?.addEventListener('click', () => {
    if (sending) return;
    closeHistory();
    saveDraft(); ++threadRequest; loadingThread = false; attachments.clear(); setComposerValue(readDraft(null)); resizeComposer(); setConversationUrl(null); updateSend();
    conversationId = null; boundProjectRef = null; renderContext(); if (pageMode) renderEmptyState(); else history.replaceChildren(); status.textContent = '';
    recent?.querySelectorAll('[aria-current]').forEach(node => node.removeAttribute('aria-current'));
    editor.focus();
  });
  document.getElementById('conversation-stop')?.addEventListener('click', async () => {
    if (!runId) { controller?.abort(); return; }
    try {
      await api('conversations/runs/' + encodeURIComponent(runId) + '/stop', 'POST', {});
      controller?.abort();
    } catch (error) { status.textContent = error.message; }
  });
  document.getElementById('conversation-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.getElementById('conversation-send');
    const input = editor;
    const stop = document.getElementById('conversation-stop');
    if (!button || sending || loadingThread || !canSend || (!composerValue().trim() && !attachments.items.length) || mode.disabled) return;
    const message = composerValue().trim() || 'Analise os arquivos anexados.', selectedMode = mode.value, newThread = !conversationId;
    if (isExternalResearchRequest(message) && !window.confirm('Esta consulta envia um resumo do projeto ao Perplexity via OpenRouter para buscar fontes públicas. O uso será debitado do saldo pelo consumo efetivo. Continuar?')) return;
    if (isImageGenerationRequest(message)) {
      const guide = 'A criação de imagem não está disponível nesta conversa.\n\nPara criar ou editar uma imagem com o contexto adequado de marca e projeto, use o [Cadu Studio](https://studio.centralcomm.media/criar).';
      addMessage('user', message, attachments.items.map(item => ({name:item.file.name})));
      const response = addMessage('assistant', guide);
      response.parentElement?.querySelector('.conversation-work-time')?.remove();
      setComposerValue(''); resizeComposer(); attachments.clear(); status.textContent = '';
      updateSend();
      return;
    }
    const draftKey = conversationId || 'new';
    sending = true; button.disabled = true; mode.disabled = true; runId = null;
    input.contentEditable = 'false'; input.setAttribute('aria-disabled', 'true'); attachments.lock(true);
    stop.hidden = false;
    controller = new AbortController(); status.textContent = 'Preparando sua conversa…'; followStreaming = true;
    const runProjectRef = activeContext?.project_ref || projectSelect?.value || '';
    let terminalStatus = null, output = null, answer = '', recovered = null, optimisticUser = null, serverStarted = false;
    const generationStartedAt = performance.now();
    try {
      // prepare() validates and routes the message again on the server before
      // it creates a run. Skipping the duplicate preflight removes one full
      // request from the time to the first streamed token.
      // Show the user's turn immediately. The server still remains the source
      // of truth; a rejected request restores the draft and removes this pair.
      optimisticUser = addMessage('user', message, attachments.items.map(item => ({name:item.file.name})));
      optimisticUser.querySelector('.conversation-user-context')?.removeAttribute('open');
      output = addMessage('assistant', '');
      scrollHistoryToEnd(true);
      status.textContent = 'Conectando ao Cadu…';
      const fileIds = await attachments.upload(controller.signal);
      const payload = {message, files:fileIds, mode: selectedMode, profile: document.body.dataset.product,
        conversation_id: conversationId};
      const id = await requestId(payload);
      const response = await fetch('/familia/api/conversations/send', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', ...(document.querySelector('meta[name="csrf-token"]')?.content ? {'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content} : {})},
        body: JSON.stringify({...payload, request_id: id})
      });
      if (!response.ok) throw new Error((await response.json()).error || 'Não foi possível iniciar a conversa.');
      let eventSource;
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json();
        if (result.accepted) {
          eventSource = queuedEvents(result, controller.signal);
        } else {
          recovered = result;
          if (!recovered.recovered || !recovered.conversation_id) throw new Error('Não foi possível recuperar este envio.');
          writeDraft(draftKey === 'new' ? null : draftKey, '');
          setComposerValue(''); attachments.clear();
          if (recovered.status !== 'running') storePending(null);
          return;
        }
      }
      for await (const data of eventSource || CaduConversationStream.events(response.body)) {
          if (data.event === 'start') {
            serverStarted = true;
            conversationId = data.conversation_id; boundProjectRef = runProjectRef || ''; renderContext(); runId = data.run_id; stop.hidden = false;
            setConversationUrl(conversationId);
            if (newThread) history.replaceChildren();
            if (newThread) {
              // The history clear also removes the optimistic pair. Recreate
              // it only after the server has accepted the run.
              optimisticUser = addMessage('user', message, attachments.items.map(item => ({name:item.file.name})));
              optimisticUser.querySelector('.conversation-user-context')?.removeAttribute('open');
              output = addMessage('assistant', '');
            }
            setComposerValue(''); resizeComposer(); attachments.clear();
            scrollHistoryToEnd(true);
            writeDraft(draftKey === 'new' ? null : draftKey, '');
            status.textContent = 'Cadu está respondendo…';
          } else if ((data.event === 'message' || data.event === 'replace') && output) {
            answer = data.event === 'replace' ? data.text : answer + data.text;
            renderStreaming(output, answer);
          }
          else if (data.event === 'progress') status.textContent = data.message;
          else if (data.event === 'catalog') addCatalogCard(data);
          else if (data.event === 'result') addResultCard(data);
          else if (data.event === 'sources') addSources(data.sources);
          else if (data.event === 'document') addDocumentCard(data);
          else if (data.event === 'error') status.textContent = data.message;
          else if (data.event === 'done') {
            terminalStatus = data.status || 'failed';
            storePending(null);
            if (terminalStatus === 'completed') status.textContent = '';
            else if (!status.textContent) status.textContent = terminalStatus === 'stopped'
              ? 'Geração interrompida. O conteúdo parcial foi salvo no histórico.'
              : 'A geração falhou. O conteúdo parcial foi salvo no histórico.';
          }
      }
      if (!terminalStatus) throw new Error('A conexão foi interrompida. Confira o histórico antes de reenviar.');
    } catch (error) {
      if (!serverStarted) { optimisticUser?.remove(); output?.remove(); output = null; }
      status.textContent = error.name === 'AbortError' ? 'Envio interrompido. Confira o histórico antes de reenviar; arquivos já recebidos pelo servidor podem ter sido preservados.' : error.message;
    } finally {
      flushStreaming(output, answer);
      setMessageElapsed(output, generationStartedAt);
      if (terminalStatus === 'completed') { addMessageActions(output, answer); addSavePlanAction(output, answer, runProjectRef); }
      sending = false; mode.disabled = false; stop.hidden = true; controller = null;
      input.contentEditable = 'true'; input.setAttribute('aria-disabled', 'false'); attachments.lock(false); updateSend();
      if (recovered) {
        await openConversation(recovered.conversation_id);
        status.textContent = recovered.status === 'running'
          ? 'Este envio já está em processamento. Abra o histórico novamente para conferir a resposta; ele não foi executado outra vez.'
          : 'Envio anterior recuperado do histórico, sem gerar outra resposta.';
        if (recovered.status === 'running') await resumePending(recovered.conversation_id);
      }
      if (!panel.hidden && (!panel.contains(document.activeElement) || document.activeElement === button)) input.focus();
    }
  });
})();
