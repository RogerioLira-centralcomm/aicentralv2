(() => {
  const root = document.querySelector('[data-observability-root]');
  if (!root) return;
  const improvementList = root.querySelector('[data-improvement-list]');
  const improvementMessage = root.querySelector('[data-improvement-message]');
  const improvementEndpoint = root.dataset.improvementEndpoint;
  const csrf = root.dataset.csrf;
  const requestImprovement = async (url, method, payload = {}) => {
    const options = {method, headers:{Accept:'application/json'}};
    if (method !== 'GET') { options.headers = {...options.headers, 'Content-Type':'application/json', 'X-CSRF-Token':csrf}; options.body=JSON.stringify(payload); }
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar a melhoria.');
    return data;
  };
  const renderImprovements = items => {
    if (!items.length) { const empty=document.createElement('p'); empty.className='cadu-observability__empty'; empty.textContent='Nenhuma recomendação acionável foi identificada nesta análise.'; improvementList.replaceChildren(empty); return; }
    improvementList.querySelector('.cadu-observability__empty')?.remove();
    items.forEach(item => {
      const card = document.createElement('article'); card.className = 'cadu-observability__improvement'; card.dataset.improvementId = item.id;
      const copy = document.createElement('div'); const state = document.createElement('span'); state.className = 'is-identified'; state.textContent = 'Identificada';
      const heading = document.createElement('b'); heading.textContent = item.title;
      const rationale = document.createElement('small'); rationale.textContent = item.rationale;
      const recommendation = document.createElement('p'); recommendation.textContent = item.recommendation;
      const confidence = document.createElement('small'); confidence.textContent = `Prioridade ${item.priority} · confiança ${Math.round((item.confidence || 0)*100)}%`;
      copy.append(state, heading, rationale, recommendation, confidence);
      const nav = document.createElement('nav');
      if (root.dataset.canManageImprovements !== 'true') { card.append(copy); improvementList.prepend(card); return; }
      const review = document.createElement('button'); review.type='button'; review.dataset.reviewImprovement=''; review.textContent='Marcar em revisão'; nav.append(review);
      const form = document.createElement('form'); form.dataset.applyImprovement=''; const label=document.createElement('label'); label.textContent='Commit ou PR'; const input=document.createElement('input'); input.name='applied_ref'; input.required=true; input.maxLength=240; input.placeholder='abc123 ou https://…'; const apply=document.createElement('button'); apply.type='submit'; apply.textContent='Marcar aplicada'; label.append(input); form.append(label,apply); nav.append(form);
      const dismiss=document.createElement('button'); dismiss.type='button'; dismiss.dataset.dismissImprovement=''; dismiss.textContent='Descartar'; nav.append(dismiss);
      card.append(copy,nav); improvementList.prepend(card);
    });
  };
  if (root.dataset.canManageImprovements === 'true') root.querySelector('[data-analyze-improvements]')?.addEventListener('click', async event => {
    const button=event.currentTarget; button.disabled=true; improvementMessage.textContent='Analisando métricas agregadas…';
    try { const data=await requestImprovement(`${improvementEndpoint}/analyze`,'POST'); renderImprovements(data.recommendations || []); improvementMessage.textContent=(data.recommendations || []).length ? 'Análise concluída. Revise as recomendações abaixo.' : 'Análise concluída sem recomendação acionável.'; }
    catch(error) { improvementMessage.textContent=error.message; }
    finally { button.disabled=root.dataset.typesafeConfigured!=='true'; }
  });
  if (improvementList && root.dataset.canManageImprovements === 'true') {
    requestImprovement(improvementEndpoint, 'GET').then(data => {
      (data.items || []).forEach(item => {
        const card=improvementList.querySelector(`[data-improvement-id="${item.id}"]`);
        if (!card) return;
        const badge=card.querySelector('span');
        if (badge) { badge.textContent={identified:'Identificada',in_review:'Em revisão',applied:'Aplicada',dismissed:'Descartada'}[item.status] || item.status; badge.className=`is-${item.status}`; }
        if (item.status === 'applied') { const note=document.createElement('small'); note.textContent=`Aplicada em ${item.applied_ref || ''}`; card.querySelector('div')?.append(note); card.querySelector('nav')?.remove(); }
        if (item.status === 'dismissed') card.querySelector('nav')?.remove();
      });
    }).catch(() => {});
  }
  if (root.dataset.canManageImprovements !== 'true') return;
  improvementList?.addEventListener('click', async event => {
    const button=event.target.closest('[data-review-improvement],[data-dismiss-improvement]'); if (!button) return;
    const card=button.closest('[data-improvement-id]'); const status=button.hasAttribute('data-review-improvement')?'in_review':'dismissed';
    try { const data=await requestImprovement(`${improvementEndpoint}/${card.dataset.improvementId}`,'PATCH',{status}); const badge=card.querySelector('span'); badge.textContent=status==='in_review'?'Em revisão':'Descartada'; badge.className=`is-${status}`; if (status==='dismissed') card.querySelector('nav').remove(); }
    catch(error) { improvementMessage.textContent=error.message; }
  });
  improvementList?.addEventListener('submit', async event => {
    const form=event.target.closest('[data-apply-improvement]'); if (!form) return; event.preventDefault();
    const card=form.closest('[data-improvement-id]'); const applied_ref=new FormData(form).get('applied_ref');
    try { const data=await requestImprovement(`${improvementEndpoint}/${card.dataset.improvementId}`,'PATCH',{status:'applied',applied_ref}); const badge=card.querySelector('span'); badge.textContent='Aplicada'; badge.className='is-applied'; const note=document.createElement('small'); note.textContent=`Aplicada em ${data.item.applied_ref}`; card.querySelector('div').append(note); card.querySelector('nav').remove(); }
    catch(error) { improvementMessage.textContent=error.message; }
  });
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
        ['Cliente', data.scope?.client_id], ['Projeto', data.scope?.project_ref], ['Marca', data.scope?.brand_ref],
        ['Mensagens persistidas', data.transcript?.message_count],
        ['Sequência', data.transcript?.sequence_start && data.transcript?.sequence_end ? `${data.transcript.sequence_start}–${data.transcript.sequence_end}` : '—'],
        ['Mensagens no contexto', data.diagnostics?.history_message_count],
        ['Janela recente', data.diagnostics?.recent_sequence_start && data.diagnostics?.recent_sequence_end ? `${data.diagnostics.recent_sequence_start}–${data.diagnostics.recent_sequence_end}` : '—'],
        ['Caracteres estimados', data.diagnostics?.history_chars],
        ['Memória', data.diagnostics?.memory_present ? `v${data.diagnostics.memory_version || '?'} · até ${data.diagnostics.memory_covers_through || 0}` : 'Não utilizada'],
        ['Mensagens recuperadas', data.diagnostics?.retrieved_message_count],
        ['Referência resolvida', data.diagnostics?.resolved_reference],
        ['Busca enviada ao modelo', (data.payload_diagnostics?.project_evidence_tools || []).join(', ') || 'Nenhuma'],
        ['Evidência compactada', data.payload_diagnostics?.evidence_truncated ? 'Sim' : 'Não'],
        ['Tamanho da evidência', data.payload_diagnostics?.evidence_chars],
      ]);
      addFacts('Rollout', Object.entries(data.rollout || {}).map(([name, enabled]) => [name, enabled ? 'Ativo' : 'Legado']));
      addFacts('Tools', (data.tools || []).length ? data.tools.map(tool => [tool.tool_name, `${tool.status}${tool.duration_ms != null ? ` · ${tool.duration_ms} ms` : ''}${tool.error_code ? ` · ${tool.error_code}` : ''}`]) : [['Chamadas', 0]]);
      (data.tools || []).filter(tool => tool.project_evidence).forEach(tool => {
        const evidence = tool.project_evidence;
        addFacts(`Recuperação do projeto · ${tool.tool_name}`, [
          ['Contexto', evidence.context_status], ['Busca em fontes', evidence.source_retrieval_status],
          ['Resultados', evidence.result_count], ['Trechos indexados', evidence.indexed_source_count],
          ['Memórias confirmadas', evidence.confirmed_memory_count],
          ['Mensagens de conversas anteriores', evidence.conversation_history_count],
          ['Fontes pendentes', evidence.source_inventory?.needs_index],
          ['Cobertura indisponível', (evidence.unavailable_scopes || []).join(', ') || 'Nenhuma'],
        ]);
      });
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
