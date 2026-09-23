(() => {
  const root = document.querySelector('[data-observability-root]');
  if (!root) return;
  const detail = root.querySelector('[data-observability-detail]');
  const body = root.querySelector('[data-detail-body]');
  const title = root.querySelector('[data-detail-title]');
  const close = () => { detail.hidden = true; body.replaceChildren(); };
  root.querySelector('[data-detail-close]')?.addEventListener('click', close);
  const value = input => input === null || input === undefined || input === '' ? '—' : String(input);
  const addFacts = (label, facts) => {
    const section = document.createElement('section'); section.className = 'cadu-observability__facts';
    const heading = document.createElement('h3'); heading.textContent = label;
    const list = document.createElement('dl');
    facts.forEach(([name, fact]) => {
      const row = document.createElement('div'); const term = document.createElement('dt'); const detail = document.createElement('dd');
      term.textContent = name; detail.textContent = value(fact); row.append(term, detail); list.append(row);
    });
    section.append(heading, list); body.append(section);
  };
  const open = async row => {
    detail.hidden = false; title.textContent = 'Carregando Turn…'; body.textContent = '';
    try {
      const response = await fetch(root.dataset.runEndpoint + row.dataset.observabilityRun, {headers:{Accept:'application/json'}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Turn indisponível.');
      title.textContent = `${data.run.execution_mode} · ${data.run.status}`;
      addFacts('Identidade e execução', [
        ['Run', data.run.id], ['Conversa', data.run.conversation_id], ['Usuário', data.run.user_id],
        ['Modelo/runtime', data.run.runtime_id], ['Configuração', data.run.provider_config_version],
        ['Estado', data.run.status], ['Erro terminal', data.run.terminal_error_code],
      ]);
      addFacts('Contexto canônico', [
        ['Mensagens persistidas', data.transcript?.message_count],
        ['Sequência', data.transcript?.sequence_start && data.transcript?.sequence_end ? `${data.transcript.sequence_start}–${data.transcript.sequence_end}` : '—'],
        ['Mensagens no contexto', data.diagnostics?.history_message_count],
        ['Janela recente', data.diagnostics?.recent_sequence_start && data.diagnostics?.recent_sequence_end ? `${data.diagnostics.recent_sequence_start}–${data.diagnostics.recent_sequence_end}` : '—'],
        ['Caracteres estimados', data.diagnostics?.history_chars],
        ['Memória', data.diagnostics?.memory_present ? `v${data.diagnostics.memory_version || '?'} · até ${data.diagnostics.memory_covers_through || 0}` : 'Não utilizada'],
        ['Mensagens recuperadas', data.diagnostics?.retrieved_message_count],
        ['Referência resolvida', data.diagnostics?.resolved_reference],
      ]);
      addFacts('Rollout', Object.entries(data.rollout || {}).map(([name, enabled]) => [name, enabled ? 'Ativo' : 'Legado']));
      addFacts('Tools', (data.tools || []).length ? data.tools.map(tool => [tool.tool_name, `${tool.status}${tool.duration_ms != null ? ` · ${tool.duration_ms} ms` : ''}${tool.error_code ? ` · ${tool.error_code}` : ''}`]) : [['Chamadas', 0]]);
      addFacts('Etapas', (data.steps || []).length ? data.steps.map(step => [`${step.position}. ${step.name}`, `${step.status}${step.error_code ? ` · ${step.error_code}` : ''}`]) : [['Etapas', 0]]);
      const eventsHeading = document.createElement('h3'); eventsHeading.className = 'cadu-observability__timeline-title'; eventsHeading.textContent = 'Eventos'; body.append(eventsHeading);
      (data.events || []).forEach(event => {
        const article = document.createElement('article'); article.className = 'cadu-observability__event';
        const sequence = document.createElement('span'); sequence.textContent = `#${event.sequence}`;
        const copy = document.createElement('div'); const name = document.createElement('b'); name.textContent = event.event_type;
        const meta = document.createElement('small'); meta.textContent = `${event.item_type}${event.duration_ms != null ? ` · ${event.duration_ms} ms` : ''}`;
        copy.append(name, meta); article.append(sequence, copy); body.append(article);
      });
      if (!data.events?.length) body.textContent = 'Este Turn ainda não possui eventos registrados.';
    } catch (error) { title.textContent = 'Não foi possível abrir o Turn'; body.textContent = error.message; }
  };
  root.querySelectorAll('[data-observability-run]').forEach(row => {
    row.addEventListener('click', () => open(row));
    row.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(row); } });
  });
})();
