(() => {
  'use strict';
  const feedback = document.querySelector('#family-feedback');
  async function api(path, method = 'GET', data) {
    const response = await fetch('/familia/api/' + path, {method, credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      ...(data ? {body: JSON.stringify(data)} : {})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Não foi possível concluir. Tente novamente.');
    return result;
  }
  const form = document.querySelector('#family-context');
  const selection = () => Object.fromEntries(new FormData(form));
  async function select(data) {
    try { await api('context', 'POST', data); location.reload(); }
    catch (error) { feedback.textContent = error.message; }
  }
  form?.addEventListener('change', event => {
    const data = selection();
    if (event.target.name === 'client_id') { data.brand_ref = null; data.project_ref = null; }
    select(data);
  });
  document.querySelectorAll('[data-client]').forEach(button => button.addEventListener('click', () => select({client_id: button.dataset.client})));
  document.querySelectorAll('[data-entity-select]').forEach(button => button.addEventListener('click', () => {
    select({...selection(), [button.dataset.kind === 'brand' ? 'brand_ref' : 'project_ref']: button.dataset.entitySelect});
  }));
  for (const [id, path, method] of [['family-profile', 'profile', 'PATCH'], ['family-create-entity', 'entities', 'POST']]) {
    document.getElementById(id)?.addEventListener('submit', async event => {
      event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
      try { await api(path, method, Object.fromEntries(new FormData(event.target))); location.reload(); }
      catch (error) { feedback.textContent = error.message; button.disabled = false; }
    });
  }
  document.querySelectorAll('.family-switch').forEach(details => {
    document.addEventListener('click', event => { if (!details.contains(event.target)) details.open = false; });
    details.addEventListener('keydown', event => { if (event.key === 'Escape') { details.open = false; details.querySelector('summary').focus(); } });
  });
  const panel = document.getElementById('conversation-panel');
  if (!panel) return;
  const opener = document.getElementById('conversation-open');
  const backdrop = document.getElementById('conversation-backdrop');
  const history = document.getElementById('conversation-history');
  const status = document.getElementById('conversation-status');
  let conversationId = null, runId = null, sending = false, controller = null;
  const mode = document.getElementById('conversation-mode');
  const background = [document.querySelector('.family-nav'), document.querySelector('.family-layout')];
  const close = () => { panel.hidden = true; backdrop.hidden = true; background.forEach(node => node.inert = false); document.body.style.overflow = ''; opener.setAttribute('aria-expanded', 'false'); opener.focus(); };
  opener.addEventListener('click', async () => {
    panel.hidden = false; backdrop.hidden = false; background.forEach(node => node.inert = true); document.body.style.overflow = 'hidden'; opener.setAttribute('aria-expanded', 'true'); panel.focus();
    if (document.body.dataset.authenticated !== 'true') return;
    if (sending) return;
    mode.disabled = true;
    api('conversations/modes').then(data => {
      mode.replaceChildren(...data.modes.map(item => new Option(item.title, item.id)));
      mode.disabled = !data.modes.length;
      if (!data.modes.length) status.textContent = 'Nenhum modo disponível. Você ainda pode consultar o histórico.';
    }).catch(() => {
      mode.replaceChildren(new Option('Modos indisponíveis', ''));
      status.textContent = 'Não foi possível carregar os modos. O histórico continua disponível; reabra o painel para tentar novamente.';
    });
    try {
      const data = await api('conversations'); history.replaceChildren();
      for (const thread of data.conversations) {
        const row = document.createElement('article');
        const button = document.createElement('button'); button.textContent = thread.title; row.append(button); history.append(row);
        button.addEventListener('click', async () => {
          if (sending) return;
          try {
            const result = await api('conversations/' + encodeURIComponent(thread.id) + '/messages');
            history.replaceChildren();
            conversationId = thread.id;
            for (const message of result.messages) {
              const entry = document.createElement('article');
              const label = document.createElement('strong'); label.textContent = message.role === 'user' ? 'Você' : 'Cadu';
              const text = document.createElement('p'); text.textContent = message.content;
              entry.append(label, text); history.append(entry);
            }
          } catch (error) { status.textContent = error.message; }
        });
      }
      if (!data.conversations.length) history.textContent = 'Nenhuma conversa para este cliente.';
    } catch (error) { history.textContent = error.message; }
  });
  document.getElementById('conversation-close').addEventListener('click', close); backdrop.addEventListener('click', close);
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key !== 'Tab') return;
    const nodes = [...panel.querySelectorAll('a[href],button,input,textarea,select')].filter(node => !node.disabled && node.getClientRects().length);
    if (!nodes.length) return;
    if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === panel)) { event.preventDefault(); nodes.at(-1).focus(); }
    else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus(); }
  });
  document.getElementById('conversation-width').addEventListener('input', event => panel.style.setProperty('--panel-width', event.target.value + 'px'));
  document.getElementById('conversation-new')?.addEventListener('click', () => {
    if (sending) return;
    conversationId = null; history.replaceChildren(); status.textContent = '';
    document.getElementById('conversation-message').focus();
  });
  document.getElementById('conversation-stop')?.addEventListener('click', async () => {
    if (!runId) return;
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
    if (!button || sending || !input.value.trim() || mode.disabled) return;
    sending = true; button.disabled = true; mode.disabled = true; runId = null;
    controller = new AbortController(); status.textContent = 'Conectando ao Cadu…';
    let completed = false, output = null, pending = '';
    try {
      const response = await fetch('/familia/api/conversations/send', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({message: input.value, mode: mode.value, profile: document.body.dataset.product,
          conversation_id: conversationId, request_id: crypto.randomUUID()})
      });
      if (!response.ok) throw new Error((await response.json()).error || 'Não foi possível iniciar a conversa.');
      const reader = response.body.getReader(), decoder = new TextDecoder();
      while (true) {
        const {value, done} = await reader.read();
        pending += decoder.decode(value || new Uint8Array(), {stream: !done}).replace(/\r/g, '');
        let boundary;
        while ((boundary = pending.indexOf('\n\n')) >= 0) {
          const frame = pending.slice(0, boundary); pending = pending.slice(boundary + 2);
          const raw = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
          if (!raw) continue;
          const data = JSON.parse(raw);
          if (data.event === 'start') {
            conversationId = data.conversation_id; runId = data.run_id; stop.hidden = false;
            const question = document.createElement('p'); question.textContent = input.value;
            output = document.createElement('p'); history.append(question, output); input.value = '';
            status.textContent = 'Cadu está respondendo…';
          } else if (data.event === 'message' && output) output.textContent += data.text;
          else if (data.event === 'replace' && output) output.textContent = data.text;
          else if (data.event === 'error') status.textContent = data.message;
          else if (data.event === 'done') {
            completed = true;
            if (data.status === 'completed') status.textContent = 'Resposta salva.';
          }
        }
        if (done) break;
      }
      if (!completed) throw new Error('A conexão foi interrompida. Confira o histórico antes de reenviar.');
    } catch (error) {
      status.textContent = error.name === 'AbortError' ? 'Geração interrompida. Consulte o histórico para ver a resposta salva.' : error.message;
    } finally {
      sending = false; button.disabled = false; mode.disabled = false; stop.hidden = true; controller = null;
    }
  });
})();
