/* Read-only catalog detail. All provider and catalog text uses textContent. */
(() => {
  'use strict';
  const dialog = document.getElementById('planner-catalog-dialog');
  const content = document.getElementById('planner-catalog-dialog-content');
  let opener = null;
  const close = () => { dialog?.close(); opener?.focus(); };
  const row = (label, value) => {
    if (value === null || value === undefined || value === '') return null;
    const item = document.createElement('div'), term = document.createElement('dt'), description = document.createElement('dd');
    term.textContent = label; description.textContent = value; item.append(term, description); return item;
  };
  if (dialog && content) {
    dialog.querySelector('[data-catalog-close]')?.addEventListener('click', close);
    dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    document.querySelectorAll('[data-catalog-kind][data-catalog-id]').forEach(button => button.addEventListener('click', async () => {
    if (button.matches('[data-planner-select]')) return;
    opener = button; content.replaceChildren(Object.assign(document.createElement('p'), {textContent: 'Carregando detalhes…'})); dialog.showModal();
    try {
      const kind = button.dataset.catalogKind;
      const encodedKind = encodeURIComponent(button.dataset.catalogKind);
      const endpoint = kind === 'places'
        ? '/familia/api/planner/places/' + encodeURIComponent(button.dataset.catalogId)
        : '/familia/api/planner/catalog/' + encodedKind + '/' + encodeURIComponent(button.dataset.catalogId);
      const response = await fetch(endpoint, {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar os detalhes.');
      dialog.querySelector('h2').textContent = data.record.name || 'Detalhes do catálogo';
      const list = document.createElement('dl');
      const points = (data.record.points || []).map(item => item.audience ? `${item.name} — ${item.audience}` : item.name).join(', ');
      [['Descrição', data.record.description], ['Categoria', data.record.category], ['Cidade', data.record.city], ['Alcance', data.record.audience], ['Dimensões', data.record.dimensions], ['Arquivos aceitos', data.record.files], ['Pontos e alcance', points]].forEach(([label, value]) => { const item = row(label, value); if (item) list.append(item); });
      content.replaceChildren(list.childElementCount ? list : Object.assign(document.createElement('p'), {textContent: 'Não há detalhes adicionais para este item.'}));
    } catch (error) { content.replaceChildren(Object.assign(document.createElement('p'), {textContent: error.message})); }
    }));
  }
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const activePlan = new URLSearchParams(window.location.search).get('plan');
  const selectionEndpoint = activePlan
    ? '/familia/api/planner/plans/' + encodeURIComponent(activePlan)
    : '/familia/api/planner/selections';
  fetch(selectionEndpoint, {credentials: 'same-origin'}).then(response => response.ok ? response.json() : {selections: []}).then(data => {
    const selections = activePlan ? ((data.plan || {}).items || []) : (data.selections || []);
    const selected = new Set(selections.map(item => item.kind + ':' + item.resource_id));
    document.querySelectorAll('[data-planner-select]').forEach(button => {
      const on = selected.has(button.dataset.catalogKind + ':' + button.dataset.catalogId);
      button.textContent = on ? 'Remover do plano' : 'Selecionar para o plano'; button.setAttribute('aria-pressed', String(on));
    });
  }).catch(() => {});
  document.querySelectorAll('[data-planner-select]').forEach(button => button.addEventListener('click', async () => {
    try {
      const endpoint = activePlan
        ? '/familia/api/planner/plans/' + encodeURIComponent(activePlan) + '/items/toggle'
        : '/familia/api/planner/selections/toggle';
      const response = await fetch(endpoint, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify({kind: button.dataset.catalogKind, resource_id: button.dataset.catalogId})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar o plano.');
      button.textContent = data.selected ? 'Remover do plano' : 'Selecionar para o plano';
      button.setAttribute('aria-pressed', String(data.selected));
    } catch (error) { alert(error.message); }
  }));
  document.querySelectorAll('[data-copy-link]').forEach(button => button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copyLink || '');
      const label = button.textContent; button.textContent = 'Link copiado';
      window.setTimeout(() => { button.textContent = label; }, 1800);
    } catch (_) { window.prompt('Copie o link público:', button.dataset.copyLink || ''); }
  }));
})();
