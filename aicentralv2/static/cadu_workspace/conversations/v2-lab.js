(() => {
  const root = document.querySelector('[data-v2-lab]');
  if (!root) return;
  const form = root.querySelector('[data-form]');
  const input = root.querySelector('[data-message]');
  const send = root.querySelector('[data-send]');
  const thread = root.querySelector('[data-thread]');
  const trace = root.querySelector('[data-trace]');
  const artifact = root.querySelector('[data-artifact]');
  const runtime = root.querySelector('[data-runtime-state]');
  const surface = root.querySelector('[data-surface]');
  let conversationId = null;
  let running = false;

  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const scrollThread = () => { thread.scrollTop = thread.scrollHeight; };
  const setRuntime = (label, busy = false) => { runtime.textContent = label; root.classList.toggle('is-running', busy); };
  const addTrace = (title, detail = '', tone = '') => {
    if (trace.querySelector(':scope > p')) trace.innerHTML = '';
    const row = document.createElement('div');
    row.className = `v2-trace-row ${tone}`;
    row.innerHTML = `<i></i><div><b>${escape(title)}</b>${detail ? `<small>${escape(detail)}</small>` : ''}</div>`;
    trace.append(row);
  };
  const addUser = message => {
    thread.querySelector('.v2-lab-empty')?.remove();
    const node = document.createElement('article');
    node.className = 'v2-lab-message is-user';
    node.innerHTML = `<p>${escape(message)}</p>`;
    thread.append(node); scrollThread();
  };
  const showArtifact = patch => {
    if (!patch || typeof patch !== 'object') return;
    root.querySelector('[data-artifact-count]').textContent = '1';
    const fields = Array.isArray(patch.fields) ? patch.fields : [];
    artifact.innerHTML = `<article><h2>${escape(patch.title || 'Artefato')}</h2><p>${escape(patch.summary || '')}</p><div>${fields.map(field => `<div class="v2-artifact-field"><b>${escape(field.key)}</b><span>${escape(field.value)}</span><em>${escape(field.state)}</em></div>`).join('')}</div></article>`;
  };
  const addAnswer = response => {
    const node = document.createElement('article');
    node.className = 'v2-lab-message is-cadu';
    const questions = (response.questions || []).map(item => `<p>${escape(item)}</p>`).join('');
    const actions = (response.actions || []).map(item => `<button type="button" data-action-prompt="${escape(item.prompt || '')}">${escape(item.label)}</button>`).join('');
    node.innerHTML = `<p>${escape(response.answer)}</p><div class="v2-lab-meta"><span>confiança ${escape(response.confidence)}</span>${(response.assumptions || []).length ? `<span>${response.assumptions.length} premissa(s)</span>` : ''}</div>${questions ? `<div class="v2-lab-questions">${questions}</div>` : ''}${actions ? `<div class="v2-lab-actions">${actions}</div>` : ''}`;
    thread.append(node); showArtifact(response.artifact_patch); scrollThread();
  };
  const handleEvent = event => {
    const kind = event.event || 'evento';
    if (kind === 'run.started') { conversationId = event.conversation_id; addTrace('Execução iniciada', event.run_id, 'is-ok'); }
    else if (kind === 'route.selected') addTrace('Rota selecionada', `${event.route?.domain || ''} / ${event.route?.action || ''} · ${event.policy?.mode || ''}`, 'is-ok');
    else if (kind === 'tool.completed') addTrace('Tool concluída', event.name, 'is-ok');
    else if (kind === 'tool.unavailable') addTrace('Tool indisponível', `${event.name} · ${event.code || ''}`, 'is-error');
    else if (kind === 'artifact.created') { addTrace('Artefato persistido', event.artifact?.id || '', 'is-ok'); showArtifact(event.artifact?.content || event.artifact); }
    else if (kind === 'answer.completed') { addAnswer(event.response || {}); addTrace('Resposta normalizada', event.response?.confidence || '', 'is-ok'); }
    else if (kind === 'run.failed') { addTrace('Execução interrompida', event.message || '', 'is-error'); setRuntime('Falhou'); }
    else if (kind === 'run.completed') { addTrace('Execução concluída', event.status || '', event.status === 'completed' ? 'is-ok' : 'is-error'); setRuntime(event.status === 'completed' ? 'Concluído' : 'Falhou'); }
  };
  const parseStream = async response => {
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || `Falha HTTP ${response.status}`); }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      const frames = buffer.split('\n\n'); buffer = frames.pop() || '';
      frames.forEach(frame => {
        const raw = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (raw) handleEvent(JSON.parse(raw));
      });
      if (done) break;
    }
  };
  const submit = async message => {
    if (running || !message.trim()) return;
    running = true; send.disabled = true; setRuntime('Executando', true); addUser(message.trim()); input.value = '';
    try {
      const response = await fetch(root.dataset.endpoint, {
        method: 'POST', headers: {'Content-Type':'application/json','X-CSRF-Token':csrf()},
        body: JSON.stringify({message: message.trim(), request_id: crypto.randomUUID(), conversation_id: conversationId, surface: surface.value})
      });
      await parseStream(response);
    } catch (error) { addTrace('Falha no teste', error.message, 'is-error'); setRuntime('Falhou'); }
    finally { running = false; send.disabled = false; root.classList.remove('is-running'); input.focus(); }
  };
  root.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => { input.value = button.dataset.prompt; input.focus(); }));
  root.addEventListener('click', event => { const action = event.target.closest('[data-action-prompt]'); if (action) { input.value = action.dataset.actionPrompt; input.focus(); } });
  root.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => {
    root.querySelectorAll('[data-tab]').forEach(item => item.classList.toggle('is-active', item === button));
    root.querySelectorAll('[data-panel]').forEach(panel => { panel.hidden = panel.dataset.panel !== button.dataset.tab; });
  }));
  root.querySelector('[data-reset]').addEventListener('click', () => { conversationId = null; trace.innerHTML = '<p>Nenhuma execução iniciada.</p>'; artifact.innerHTML = '<p>Artefatos estruturados aparecerão aqui.</p>'; root.querySelector('[data-artifact-count]').textContent = '0'; thread.innerHTML = '<div class="v2-lab-empty"><i>C</i><h2>Teste uma conversa completa</h2><p>Escolha um cenário ou escreva um pedido. A resposta, as perguntas e as ações aparecem aqui; o diagnóstico fica separado.</p></div>'; setRuntime('Pronto'); });
  form.addEventListener('submit', event => { event.preventDefault(); submit(input.value); });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
})();
