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
  const historyToggle = document.getElementById('conversation-history-toggle');
  const conversationShell = document.querySelector('.workspace-conversations');
  const closeHistory = () => {
    conversationShell?.classList.remove('history-open');
    historyToggle?.setAttribute('aria-expanded', 'false');
  };
  historyToggle?.addEventListener('click', () => {
    const open = !conversationShell?.classList.contains('history-open');
    conversationShell?.classList.toggle('history-open', open);
    historyToggle.setAttribute('aria-expanded', String(open));
  });
  let conversationId = null, runId = null, sending = false, controller = null;
  let initialized = false, initializing = null, canSend = false, canReplay = false;
  let loadingThread = false, threadRequest = 0, historyRequest = 0, nextOffset = null;
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
  const saveDraft = () => writeDraft(conversationId, composer.value);
  const more = document.getElementById('conversation-more');
  const archivedFilter = document.getElementById('conversation-archived');
  const searchForm = document.getElementById('conversation-search');
  const mode = document.getElementById('conversation-mode');
  const modeEdit = document.getElementById('conversation-mode-edit');
  const modeDialog = document.getElementById('conversation-mode-dialog');
  const modeForm = document.getElementById('conversation-mode-form');
  const modePrompt = document.getElementById('conversation-mode-prompt');
  const projectSelect = document.getElementById('conversation-project');
  const brandSelect = document.getElementById('conversation-brand');
  const contextNote = document.getElementById('conversation-context-note');
  let contextEntities = [], activeContext = {};
  const composer = document.getElementById('conversation-message');
  let modeEntries = [];
  const applyModes = (items, selected) => {
    modeEntries = Array.isArray(items) ? items : [];
    const active = selected || modeEntries.find(item => item.active)?.id || mode.value;
    mode.replaceChildren(...modeEntries.map(item => new Option(item.title, item.id, false, item.id === active)));
    mode.disabled = !modeEntries.length;
    if (modeEdit) modeEdit.disabled = mode.disabled;
  };
  composer.value = readDraft(null);
  const contextOptions = (select, rows, emptyLabel, selected) => {
    if (!select) return;
    select.replaceChildren(new Option(emptyLabel, ''), ...rows.map(row => new Option(row.name, row.ref, false, row.ref === selected)));
    select.disabled = false;
  };
  const visibleBrands = projectRef => {
    const brands = contextEntities.filter(item => item.kind === 'brand');
    const project = contextEntities.find(item => item.ref === projectRef);
    return project?.related_refs?.length ? brands.filter(item => project.related_refs.includes(item.ref)) : brands;
  };
  const renderContext = (selected = activeContext) => {
    contextOptions(projectSelect, contextEntities.filter(item => item.kind === 'project'), 'Sem projeto', selected.project_ref);
    const brands = visibleBrands(projectSelect?.value || selected.project_ref);
    const brandRef = brands.some(item => item.ref === selected.brand_ref) ? selected.brand_ref : '';
    contextOptions(brandSelect, brands, 'Sem marca', brandRef);
    if (contextNote) contextNote.textContent = projectSelect?.value
      ? 'Projeto ativo para novas conversas e mensagens.'
      : 'Selecione um projeto para incluir o contexto no Cadu.';
  };
  async function loadContext() {
    if (!projectSelect || !brandSelect) return;
    try {
      const data = await api('context');
      contextEntities = Array.isArray(data.entities) ? data.entities : [];
      activeContext = data.context || {};
      const requestedProject = pageMode && new URLSearchParams(window.location.search).get('project');
      if (requestedProject && contextEntities.some(item => item.kind === 'project' && item.ref === requestedProject)) {
        activeContext = {...activeContext, project_ref: requestedProject, brand_ref: ''};
        await api('context', 'POST', activeContext);
      }
      renderContext();
    } catch (_) {
      projectSelect.replaceChildren(new Option('Projetos indisponíveis', ''));
      brandSelect.replaceChildren(new Option('Marcas indisponíveis', ''));
      if (contextNote) contextNote.textContent = 'O contexto será disponibilizado quando a conexão do Workspace estiver ativa.';
    }
  }
  async function saveContext() {
    if (!projectSelect || !brandSelect) return;
    projectSelect.disabled = brandSelect.disabled = true;
    try {
      const data = await api('context', 'POST', {project_ref: projectSelect.value || null, brand_ref: brandSelect.value || null});
      activeContext = data.context || {};
      renderContext(activeContext);
      status.textContent = 'Contexto salvo para a próxima conversa.';
    } catch (error) {
      renderContext(activeContext);
      status.textContent = unavailableMessage('Não foi possível salvar o contexto', error);
    }
  }
  projectSelect?.addEventListener('change', () => { renderContext({...activeContext, project_ref: projectSelect.value, brand_ref: ''}); saveContext(); });
  brandSelect?.addEventListener('change', saveContext);
  const attachments = new CaduAttachments(panel, status);
  const sendButton = document.getElementById('conversation-send');
  const updateSend = () => {
    composer.disabled = sending || loadingThread || !canSend || mode.disabled;
    if (sendButton) sendButton.disabled = composer.disabled || (!composer.value.trim() && !attachments.items.length);
  };
  panel.addEventListener('attachmentschange', updateSend);
  mode?.addEventListener('change', async () => {
    const selected = mode.value;
    const previous = modeEntries.find(item => item.active)?.id;
    mode.disabled = true; if (modeEdit) modeEdit.disabled = true; updateSend();
    try {
      const data = await api('conversations/modes/active', 'POST', {mode: selected});
      applyModes(data.modes, selected);
      status.textContent = 'Modo salvo para as próximas conversas.';
    } catch (error) {
      applyModes(modeEntries, previous);
      status.textContent = unavailableMessage('Não foi possível trocar o modo', error);
    } finally { updateSend(); }
  });
  modeEdit?.addEventListener('click', () => {
    const selected = modeEntries.find(item => item.id === mode.value);
    if (!selected || !modeDialog || !modePrompt) return;
    modePrompt.value = selected.prompt || '';
    document.getElementById('conversation-mode-dialog-title').textContent = 'Personalizar: ' + selected.title;
    document.getElementById('conversation-mode-dialog-description').textContent = selected.customized
      ? 'Você está usando instruções personalizadas para este modo.'
      : 'Estas instruções valem somente para a sua conta.';
    if (typeof modeDialog.showModal === 'function') modeDialog.showModal(); else modeDialog.setAttribute('open', '');
    modePrompt.focus();
  });
  document.getElementById('conversation-mode-cancel')?.addEventListener('click', () => modeDialog?.close());
  modeForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const selected = mode.value;
    try {
      const data = await api('conversations/modes/' + encodeURIComponent(selected), 'PUT', {prompt: modePrompt.value});
      applyModes(data.modes, selected); modeDialog.close();
      status.textContent = 'Instruções personalizadas salvas.';
    } catch (error) { status.textContent = unavailableMessage('Não foi possível salvar as instruções', error); }
  });
  document.getElementById('conversation-mode-reset')?.addEventListener('click', async () => {
    const selected = mode.value;
    try {
      const data = await api('conversations/modes/' + encodeURIComponent(selected), 'DELETE');
      applyModes(data.modes, selected); modeDialog?.close();
      status.textContent = 'Modo restaurado ao padrão.';
    } catch (error) { status.textContent = unavailableMessage('Não foi possível restaurar o modo', error); }
  });
  // PHP chat-v2: Enter sends; Shift+Enter inserts a line. Never send mid-IME.
  composer.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!composer.disabled && !sending && !mode?.disabled) {
        document.getElementById('conversation-form').requestSubmit();
      }
    }
  });
  composer.addEventListener('input', () => {
    saveDraft();
    composer.style.height = 'auto';
    composer.style.height = Math.min(composer.scrollHeight, window.innerHeight * .3) + 'px';
    updateSend();
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
      history.replaceChildren(); conversationId = id;
      attachments.clear(); composer.value = readDraft(id); composer.style.height = '';
      recent?.querySelectorAll('button[data-conversation-id]').forEach(button => {
        if (button.dataset.conversationId === id) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
      });
      for (const message of result.messages) addMessage(message.role, message.content, message.files, message.metadata);
      setConversationUrl(id);
      status.textContent = result.context ? 'Conversa retomada com o projeto, marca e perfil de origem.' : 'Conversa anterior carregada. O próximo envio usará o contexto ativo.';
      return true;
    } catch (error) { if (request === threadRequest) status.textContent = error.message; }
    finally { if (request === threadRequest) { loadingThread = false; updateSend(); } }
  }
  async function loadHistory(append = false) {
    if (sending) return;
    const request = ++historyRequest;
    const target = recent || history;
    if (more) more.disabled = true;
    try {
      const params = new URLSearchParams({q: historyQuery, offset: String(append ? nextOffset || 0 : 0), archived: archivedFilter?.checked ? '1' : '0'});
      const data = await api('conversations?' + params);
      if (request !== historyRequest) return;
      if (!recent && !append) { saveDraft(); conversationId = null; composer.value = readDraft(null); }
      if (!append) target.replaceChildren();
      nextOffset = data.next_offset;
      if (more) more.hidden = nextOffset == null;
      for (const thread of data.conversations) {
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
          const archive = document.createElement('button'); archive.type = 'button'; archive.textContent = archivedFilter?.checked ? 'Restaurar' : 'Arquivar';
          const archived = !archivedFilter?.checked;
          const update = async data => {
            if (sending || loadingThread) return;
            save.disabled = archive.disabled = true;
            try {
              await api('conversations/' + encodeURIComponent(thread.id), 'PATCH', data);
              await loadHistory();
              status.textContent = 'title' in data ? 'Título salvo.' : data.archived ? 'Conversa arquivada. Você pode restaurá-la em Mostrar arquivadas.' : 'Conversa restaurada.';
            } catch (error) { status.textContent = error.message; }
            finally { save.disabled = archive.disabled = false; }
          };
          form.addEventListener('submit', event => { event.preventDefault(); update({title: title.value.trim()}); });
          archive.addEventListener('click', () => update({archived}));
          form.append(title, save); actions.append(summary, form, archive); row.append(actions);
        }
      }
      if (!append && !data.conversations.length) target.textContent = 'Nenhuma conversa encontrada.';
    } catch (error) { if (request === historyRequest) status.textContent = unavailableMessage('Não foi possível carregar seu histórico', error); }
    finally { if (more && request === historyRequest) more.disabled = false; }
  }
  searchForm?.addEventListener('submit', event => { event.preventDefault(); historyQuery = new FormData(searchForm).get('q').trim(); loadHistory(); });
  more?.addEventListener('click', () => loadHistory(true));
  archivedFilter?.addEventListener('change', () => loadHistory());
  function addSources(sources) {
    if (!Array.isArray(sources) || !sources.length) return;
    const card = document.createElement('section'); card.className = 'conversation-sources';
    const heading = document.createElement('strong'); heading.textContent = 'Fontes do projeto consultadas'; card.append(heading);
    const list = document.createElement('ul');
    sources.slice(0, 4).forEach(source => {
      if (!source || typeof source !== 'object') return;
      const item = document.createElement('li'), title = document.createElement('b'), excerpt = document.createElement('span');
      title.textContent = source.title || 'Fonte sem título'; excerpt.textContent = source.excerpt || '';
      item.append(title); if (excerpt.textContent) item.append(excerpt); list.append(item);
    });
    if (list.childElementCount) { card.append(list); history.append(card); }
  }
  function addMessage(role, content, files = [], metadata = {}) {
    const entry = document.createElement('article'); entry.className = 'conversation-message ' + (role === 'user' ? 'from-user' : 'from-cadu');
    const label = document.createElement('strong'); label.textContent = role === 'user' ? 'Você' : 'Cadu';
    const text = document.createElement('div');
    if (role === 'assistant') CaduConversationRenderer.render(text, content);
    else text.textContent = content;
    entry.append(label, text);
    CaduConversationRenderer.renderFiles(entry, files);
    history.append(entry);
    if (role === 'assistant') addSources(metadata?.project_sources);
    return text;
  }
  function addCatalogCard(data) {
    if (!Array.isArray(data.records) || !data.records.length) return;
    const card = document.createElement('section'); card.className = 'conversation-catalog-card';
    const heading = document.createElement('h4'); heading.textContent = ({canais:'Canais', formatos:'Formatos', interativos:'Interativos', audiencias:'Audiências'})[data.catalog_kind] || 'Catálogo'; card.append(heading);
    const list = document.createElement('ul');
    data.records.forEach(record => {
      const item = document.createElement('li'), name = document.createElement('strong'), detail = document.createElement('span');
      name.textContent = record.name || 'Item do catálogo';
      detail.textContent = record.description || record.category || record.dimensions || '';
      item.append(name); if (detail.textContent) item.append(detail); list.append(item);
    });
    card.append(list); history.append(card); card.scrollIntoView({block:'nearest'});
  }
  function addDocumentCard(data) {
    if (!data.document || typeof data.preview !== 'string') return;
    const card = document.createElement('section'); card.className = 'conversation-catalog-card conversation-document-card';
    const heading = document.createElement('h4'); heading.textContent = 'SmartDoc consultado';
    const title = document.createElement('strong'); title.textContent = data.document.title || 'Documento';
    const meta = document.createElement('span'); meta.textContent = [data.document.type, data.document.status].filter(Boolean).join(' · ');
    const preview = document.createElement('p'); preview.textContent = data.preview;
    card.append(heading, title); if (meta.textContent) card.append(meta); card.append(preview);
    history.append(card); card.scrollIntoView({block:'nearest'});
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
          CaduConversationRenderer.render(output, answer, true);
        } else if (data.event === 'catalog') addCatalogCard(data);
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
      if (output) CaduConversationRenderer.render(output, answer);
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
      try {
        const [capabilities, data] = await Promise.all([api('conversations/capabilities'), api('conversations/modes')]);
        if (!Array.isArray(data.modes)) throw new Error('Modos indisponíveis');
        applyModes(data.modes);
        canSend = capabilities.send === true;
        canReplay = capabilities.replay === true;
        attachments.configure({...capabilities, attachments: canSend && capabilities.attachments === true});
        initialized = true;
        status.textContent = !canSend
          ? (capabilities.reason || 'Envio indisponível. Você pode consultar seu histórico.')
          : mode.disabled ? 'Nenhum modo disponível. Consulte o histórico.' : '';
      } catch (error) {
        canSend = false; mode.disabled = true; attachments.configure({attachments:false});
        status.textContent = unavailableMessage('Não foi possível iniciar as conversas', error);
      } finally { updateSend(); }
      await loadHistory();
      await loadContext();
      const requested = pageMode && new URLSearchParams(window.location.search).get('conversation');
      if (requested && !conversationId) await openConversation(requested);
      else if (recent && !conversationId) history.innerHTML = '<div class="workspace-conversation-empty"><strong>Como posso ajudar?</strong><span>Escreva uma mensagem ou retome uma conversa anterior.</span></div>';
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
    saveDraft(); ++threadRequest; loadingThread = false; attachments.clear(); composer.value = readDraft(null); setConversationUrl(null); updateSend();
    conversationId = null; history.innerHTML = pageMode ? '<div class="workspace-conversation-empty"><strong>Como posso ajudar?</strong><span>Escreva uma mensagem para começar uma nova conversa.</span></div>' : ''; status.textContent = '';
    recent?.querySelectorAll('[aria-current]').forEach(node => node.removeAttribute('aria-current'));
    document.getElementById('conversation-message').focus();
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
    const input = document.getElementById('conversation-message');
    const stop = document.getElementById('conversation-stop');
    if (!button || sending || loadingThread || !canSend || (!input.value.trim() && !attachments.items.length) || mode.disabled) return;
    const message = input.value.trim() || 'Analise os arquivos anexados.', selectedMode = mode.value, newThread = !conversationId;
    const draftKey = conversationId || 'new';
    sending = true; button.disabled = true; mode.disabled = true; runId = null;
    input.disabled = true; attachments.lock(true);
    stop.hidden = false;
    controller = new AbortController(); status.textContent = 'Conectando ao Cadu…';
    let completed = false, output = null, answer = '', recovered = null;
    try {
      await api('conversations/preflight', 'POST', {message});
      if (controller.signal.aborted) throw new DOMException('Envio interrompido', 'AbortError');
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
          input.value = ''; attachments.clear();
          if (recovered.status !== 'running') storePending(null);
          return;
        }
      }
      for await (const data of eventSource || CaduConversationStream.events(response.body)) {
          if (data.event === 'start') {
            conversationId = data.conversation_id; runId = data.run_id; stop.hidden = false;
            setConversationUrl(conversationId);
            if (newThread) history.replaceChildren();
            addMessage('user', message, attachments.items.map(item => ({name:item.file.name})));
            output = addMessage('assistant', ''); input.value = ''; input.style.height = ''; attachments.clear();
            writeDraft(draftKey === 'new' ? null : draftKey, '');
            status.textContent = 'Cadu está respondendo…';
          } else if ((data.event === 'message' || data.event === 'replace') && output) {
            answer = data.event === 'replace' ? data.text : answer + data.text;
            CaduConversationRenderer.render(output, answer, true);
          }
          else if (data.event === 'progress') status.textContent = data.message;
          else if (data.event === 'catalog') addCatalogCard(data);
          else if (data.event === 'sources') addSources(data.sources);
          else if (data.event === 'document') addDocumentCard(data);
          else if (data.event === 'error') status.textContent = data.message;
          else if (data.event === 'done') {
            completed = true;
            storePending(null);
            if (data.status === 'completed') status.textContent = 'Resposta salva.';
          }
      }
      if (!completed) throw new Error('A conexão foi interrompida. Confira o histórico antes de reenviar.');
    } catch (error) {
      status.textContent = error.name === 'AbortError' ? 'Envio interrompido. Confira o histórico antes de reenviar; arquivos já recebidos pelo servidor podem ter sido preservados.' : error.message;
    } finally {
      if (output) CaduConversationRenderer.render(output, answer);
      sending = false; mode.disabled = false; stop.hidden = true; controller = null;
      input.disabled = false; attachments.lock(false); updateSend();
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
