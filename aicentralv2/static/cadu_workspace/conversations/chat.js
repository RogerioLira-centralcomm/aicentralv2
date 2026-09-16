/* Shared Workspace chat; independent of product navigation. */
(() => {
  'use strict';
  async function api(path, method = 'GET', data) {
    const response = await fetch('/familia/api/' + path, {method, credentials: 'same-origin', signal: AbortSignal.timeout(20000),
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      ...(data ? {body: JSON.stringify(data)} : {})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Não foi possível concluir. Tente novamente.');
    return result;
  }
  const panel = document.getElementById('conversation-panel');
  if (!panel) return;
  const pageMode = panel.dataset.conversationPage === 'true';
  const opener = document.getElementById('conversation-open');
  const backdrop = document.getElementById('conversation-backdrop');
  const history = document.getElementById('conversation-history');
  const recent = document.getElementById('conversation-recent');
  const status = document.getElementById('conversation-status');
  let conversationId = null, runId = null, sending = false, controller = null;
  let initialized = false, canSend = false;
  const mode = document.getElementById('conversation-mode');
  const composer = document.getElementById('conversation-message');
  const attachments = new CaduAttachments(panel, status);
  const sendButton = document.getElementById('conversation-send');
  const updateSend = () => { if (sendButton) sendButton.disabled = sending || !canSend || mode.disabled || (!composer.value.trim() && !attachments.items.length); };
  panel.addEventListener('attachmentschange', updateSend);
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
    composer.style.height = 'auto';
    composer.style.height = Math.min(composer.scrollHeight, window.innerHeight * .3) + 'px';
    updateSend();
  });
  const background = [document.querySelector('.family-nav'), document.querySelector('.family-layout')];
  const close = () => {
    if (pageMode) return;
    panel.hidden = true; backdrop.hidden = true; background.forEach(node => { if (node) node.inert = false; }); document.body.style.overflow = '';
    opener?.setAttribute('aria-expanded', 'false'); opener?.focus();
  };
  async function loadHistory() {
    if (sending) return;
    const target = recent || history;
    try {
      const data = await api('conversations'); target.replaceChildren(); conversationId = null;
      if (recent) history.innerHTML = '<div class="workspace-conversation-empty"><strong>Como posso ajudar?</strong><span>Use esta conversa para reunir informações do cliente e seguir para Planner, Skills, Studio ou Connect.</span></div>';
      for (const thread of data.conversations.slice(0, 15)) {
        const row = document.createElement('article');
        const button = document.createElement('button'); button.textContent = thread.title; row.append(button); target.append(row);
        button.addEventListener('click', async () => {
          if (sending) return;
          try {
            const result = await api('conversations/' + encodeURIComponent(thread.id) + '/messages');
            history.replaceChildren(); conversationId = thread.id;
            recent?.querySelectorAll('[aria-current]').forEach(node => node.removeAttribute('aria-current'));
            button.setAttribute('aria-current', 'page');
            for (const message of result.messages) addMessage(message.role, message.content, message.files);
          } catch (error) { status.textContent = error.message; }
        });
      }
      if (!data.conversations.length) target.textContent = 'Nenhuma conversa para este cliente.';
    } catch (error) { target.textContent = error.message; }
  }
  function addMessage(role, content, files = []) {
    const entry = document.createElement('article'); entry.className = 'conversation-message ' + (role === 'user' ? 'from-user' : 'from-cadu');
    const label = document.createElement('strong'); label.textContent = role === 'user' ? 'Você' : 'Cadu';
    const text = document.createElement('div');
    if (role === 'assistant') CaduConversationRenderer.render(text, content);
    else text.textContent = content;
    entry.append(label, text);
    if (Array.isArray(files)) files.forEach(file => { const name = document.createElement('small'); name.textContent = file.name || 'Anexo'; entry.append(name); });
    history.append(entry); return text;
  }
  function addCatalogCard(data) {
    if (!Array.isArray(data.records) || !data.records.length) return;
    const card = document.createElement('section'); card.className = 'conversation-catalog-card';
    const heading = document.createElement('h4'); heading.textContent = ({canais:'Canais', formatos:'Formatos', audiencias:'Audiências'})[data.catalog_kind] || 'Catálogo'; card.append(heading);
    const list = document.createElement('ul');
    data.records.forEach(record => {
      const item = document.createElement('li'), name = document.createElement('strong'), detail = document.createElement('span');
      name.textContent = record.name || 'Item do catálogo';
      detail.textContent = record.description || record.category || record.dimensions || '';
      item.append(name); if (detail.textContent) item.append(detail); list.append(item);
    });
    card.append(list); history.append(card); card.scrollIntoView({block:'nearest'});
  }
  async function initialize() {
    if (document.body.dataset.authenticated !== 'true' || sending || initialized) return;
    initialized = true;
    mode.disabled = true;
    api('conversations/capabilities').then(data => {
      canSend = data.send === true; attachments.configure(data); updateSend();
      if (!canSend) status.textContent = 'Modo de consulta: envio e anexos ainda não estão habilitados nesta instalação.';
    }).catch(() => { canSend = false; updateSend(); initialized = false; status.textContent = 'Não foi possível verificar a disponibilidade. Tente recarregar a página.'; });
    api('conversations/modes').then(data => {
      mode.replaceChildren(...data.modes.map(item => new Option(item.title, item.id)));
      mode.disabled = !data.modes.length;
      updateSend();
      if (!data.modes.length) status.textContent = 'Nenhum modo disponível. Você ainda pode consultar o histórico.';
    }).catch(() => {
      mode.replaceChildren(new Option('Modos indisponíveis', ''));
      initialized = false; updateSend();
      status.textContent = 'Não foi possível carregar os modos. O histórico continua disponível.';
    });
    await loadHistory();
  }
  opener?.addEventListener('click', async () => {
    panel.hidden = false; backdrop.hidden = false; background.forEach(node => node.inert = true); document.body.style.overflow = 'hidden'; opener.setAttribute('aria-expanded', 'true'); panel.focus();
    await initialize();
  });
  if (pageMode) initialize();
  document.getElementById('conversation-list')?.addEventListener('click', loadHistory);
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
    conversationId = null; history.innerHTML = pageMode ? '<div class="workspace-conversation-empty"><strong>Como posso ajudar?</strong><span>Use esta conversa para reunir informações do cliente e seguir para Planner, Skills, Studio ou Connect.</span></div>' : ''; status.textContent = '';
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
    if (!button || sending || !canSend || (!input.value.trim() && !attachments.items.length) || mode.disabled) return;
    const message = input.value.trim() || 'Analise os arquivos anexados.', selectedMode = mode.value, newThread = !conversationId;
    sending = true; button.disabled = true; mode.disabled = true; runId = null;
    input.disabled = true; attachments.lock(true);
    stop.hidden = false;
    controller = new AbortController(); status.textContent = 'Conectando ao Cadu…';
    let completed = false, output = null, answer = '';
    try {
      await api('conversations/preflight', 'POST', {message});
      if (controller.signal.aborted) throw new DOMException('Envio interrompido', 'AbortError');
      const fileIds = await attachments.upload(controller.signal);
      const response = await fetch('/familia/api/conversations/send', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({message, files:fileIds, mode: selectedMode, profile: document.body.dataset.product,
          conversation_id: conversationId, request_id: crypto.randomUUID()})
      });
      if (!response.ok) throw new Error((await response.json()).error || 'Não foi possível iniciar a conversa.');
      for await (const data of CaduConversationStream.events(response.body)) {
          if (data.event === 'start') {
            conversationId = data.conversation_id; runId = data.run_id; stop.hidden = false;
            if (newThread) history.replaceChildren();
            addMessage('user', message, attachments.items.map(item => ({name:item.file.name})));
            output = addMessage('assistant', ''); input.value = ''; input.style.height = ''; attachments.clear();
            status.textContent = 'Cadu está respondendo…';
          } else if ((data.event === 'message' || data.event === 'replace') && output) {
            answer = data.event === 'replace' ? data.text : answer + data.text;
            CaduConversationRenderer.render(output, answer, true);
          }
          else if (data.event === 'progress') status.textContent = data.message;
          else if (data.event === 'catalog') addCatalogCard(data);
          else if (data.event === 'error') status.textContent = data.message;
          else if (data.event === 'done') {
            completed = true;
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
      if (!panel.hidden && (!panel.contains(document.activeElement) || document.activeElement === button)) input.focus();
    }
  });
})();
