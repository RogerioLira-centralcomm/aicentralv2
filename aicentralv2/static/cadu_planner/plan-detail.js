(() => {
  'use strict';
  const desk = document.querySelector('[data-plan-desk]');
  if (!desk) return;
  const planId = desk.dataset.planId;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const request = (path, method, payload) => fetch(path, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(payload)}).then(async response => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar o plano.');
    return data;
  });
  const allocationSummary = desk.querySelector('[data-allocation-summary]');
  const number = value => {
    const raw = String(value || '').trim();
    return Number(raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw) || 0;
  };
  const refreshAllocationSummary = () => {
    if (!allocationSummary) return;
    const rows = [...desk.querySelectorAll('[data-allocation-row]')];
    const investment = rows.reduce((total, row) => total + number(row.querySelector('[data-allocation-investment]')?.value), 0);
    const weight = rows.reduce((total, row) => total + number(row.querySelector('[data-allocation-weight]')?.value), 0);
    allocationSummary.textContent = `${rows.length} canal${rows.length === 1 ? '' : 'is'} · ${new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(investment)} direcionados · ${weight.toLocaleString('pt-BR', {maximumFractionDigits: 2})}% informado`;
  };
  desk.querySelectorAll('[data-allocation-investment],[data-allocation-weight]').forEach(input => input.addEventListener('input', refreshAllocationSummary));
  refreshAllocationSummary();
  desk.querySelector('[data-plan-briefing]')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget, status = desk.querySelector('[data-plan-save-status]');
    const briefing = Object.fromEntries(new FormData(form).entries());
    status.textContent = 'Salvando…';
    try { await request('/familia/api/planner/plans/' + encodeURIComponent(planId), 'PUT', {briefing, advertiser_name: briefing.advertiser_name, campaign_name: briefing.campaign_name}); status.textContent = 'Direção salva.'; }
    catch (error) { status.textContent = error.message; }
  });
  desk.querySelector('[data-plan-briefing-review]')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    const status = desk.querySelector('[data-plan-review-status]');
    button.disabled = true;
    status.textContent = 'Salvando a direção antes da revisão…';
    try {
      const form = desk.querySelector('[data-plan-briefing]');
      const briefing = Object.fromEntries(new FormData(form).entries());
      await request('/familia/api/planner/plans/' + encodeURIComponent(planId), 'PUT', {briefing, advertiser_name: briefing.advertiser_name, campaign_name: briefing.campaign_name});
      const estimate = await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/briefing-review/estimate', 'GET');
      if (!window.confirm(`O Cadu fará ${estimate.passes} revisões e pode usar até ${estimate.estimated_tokens.toLocaleString('pt-BR')} créditos. Continuar?`)) {
        status.textContent = 'Revisão cancelada.';
        button.disabled = false;
        return;
      }
      status.textContent = 'O Cadu está fazendo as três revisões…';
      const result = await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/briefing-review', 'POST', {});
      status.textContent = `Versão ${result.review.applied_pass} aplicada${result.review.charged_tokens ? ` · ${result.review.charged_tokens} créditos usados` : ''}.`;
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  });
  desk.querySelector('[data-save-allocations]')?.addEventListener('click', async event => {
    const button = event.currentTarget, status = desk.querySelector('[data-allocation-save-status]');
    const allocations = [...desk.querySelectorAll('[data-allocation-row]')].map(row => ({
      resource_id: row.dataset.resourceId,
      investment: row.querySelector('[data-allocation-investment]')?.value || 0,
      weight: row.querySelector('[data-allocation-weight]')?.value || 0,
      flight: row.querySelector('[data-allocation-flight]')?.value || '',
      notes: row.querySelector('[data-allocation-notes]')?.value || ''
    }));
    button.disabled = true; status.textContent = 'Salvando…';
    try { await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/allocations', 'PUT', {allocations}); status.textContent = 'Distribuição salva.'; }
    catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  desk.querySelector('[data-plan-status]')?.addEventListener('click', async event => {
    const button = event.currentTarget, message = desk.querySelector('[data-plan-status-message]');
    button.disabled = true; message.textContent = 'Atualizando status…';
    try { await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/status', 'PUT', {status: button.dataset.planStatus}); window.location.reload(); }
    catch (error) { message.textContent = error.message; button.disabled = false; }
  });
  desk.querySelectorAll('[data-plan-remove]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/items/toggle', 'POST', {kind: button.dataset.kind, resource_id: button.dataset.resourceId}); window.location.reload(); }
    catch (error) { button.disabled = false; alert(error.message); }
  }));
  const shareButton = desk.querySelector('[data-plan-share]');
  shareButton?.addEventListener('click', async () => {
    const status = desk.querySelector('[data-plan-share-status]');
    shareButton.disabled = true;
    status.textContent = 'Preparando link público…';
    try {
      const data = await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/share', 'POST', {enabled: true});
      const url = new URL('/planos/public/' + encodeURIComponent(data.plan.share_token), window.location.origin).href;
      await navigator.clipboard?.writeText(url);
      shareButton.textContent = 'Copiar link público';
      status.textContent = 'Link público copiado.';
    } catch (error) { status.textContent = error.message; }
    finally { shareButton.disabled = false; }
  });
  desk.querySelector('[data-plan-unshare]')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    const status = desk.querySelector('[data-plan-share-status]');
    button.disabled = true;
    status.textContent = 'Removendo acesso público…';
    try {
      await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/share', 'POST', {enabled: false});
      window.location.reload();
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  });
  const quoteButton = desk.querySelector('[data-quote-request]');
  const quoteDialog = desk.querySelector('[data-quote-request-dialog]');
  const quoteStatus = desk.querySelector('[data-quote-request-status]');
  quoteButton?.addEventListener('click', () => quoteDialog?.showModal());
  quoteDialog?.addEventListener('close', async () => {
    if (quoteDialog.returnValue !== 'request') return;
    const form = quoteDialog.querySelector('form');
    if (!form.reportValidity()) return;
    quoteStatus.textContent = 'Enviando solicitação…';
    try {
      await request('/familia/api/planner/plans/' + encodeURIComponent(planId) + '/quote-requests', 'POST', Object.fromEntries(new FormData(form)));
      quoteStatus.textContent = 'Solicitação enviada ao time comercial.';
      quoteButton.disabled = true;
    } catch (error) { quoteStatus.textContent = error.message; }
  });
  const reviewDialog = desk.querySelector('[data-planner-review-dialog]');
  desk.querySelector('[data-planner-review-open]')?.addEventListener('click', () => reviewDialog?.showModal());
  desk.querySelectorAll('[data-planner-review-close]').forEach(button => button.addEventListener('click', () => reviewDialog?.close()));
  const comparison = desk.querySelector('[data-plan-comparison]');
  if (comparison) {
    const items = JSON.parse(comparison.dataset.items || '[]');
    const select = comparison.querySelector('[data-compare-kind]');
    const table = comparison.querySelector('[data-comparison-table]');
    const fields = [
      ['Categoria', record => record.category || record.city],
      ['Alcance', record => record.audience],
      ['Especificação', record => record.dimensions || record.files],
      ['Descrição', record => record.description]
    ];
    const renderComparison = () => {
      const selected = items.filter(item => item.kind === select.value);
      table.replaceChildren();
      if (!selected.length) {
        table.append(Object.assign(document.createElement('p'), {className: 'planner-comparison-empty', textContent: 'Adicione pelo menos uma escolha deste tipo para compará-la aqui.'}));
        return;
      }
      const grid = document.createElement('div'); grid.className = 'planner-comparison-grid';
      const label = document.createElement('div'); label.className = 'planner-comparison-labels';
      label.append(Object.assign(document.createElement('strong'), {textContent: 'Referência'}));
      fields.forEach(([name]) => label.append(Object.assign(document.createElement('span'), {textContent: name})));
      grid.append(label);
      selected.forEach(item => {
        const column = document.createElement('article');
        const snapshot = item.snapshot || {};
        column.append(Object.assign(document.createElement('strong'), {textContent: snapshot.name || item.resource_id}));
        fields.forEach(([, value]) => column.append(Object.assign(document.createElement('span'), {textContent: value(snapshot) || '—'})));
        grid.append(column);
      });
      table.append(grid);
    };
    select.addEventListener('change', renderComparison); renderComparison();
  }
})();
