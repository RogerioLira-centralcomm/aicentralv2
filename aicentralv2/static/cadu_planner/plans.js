(() => {
  const root = document.querySelector('[data-planner-plans]');
  const dialog = document.querySelector('[data-plan-create-dialog]');
  if (!root || !dialog) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  document.querySelectorAll('[data-plan-create]').forEach((trigger) => {
    trigger.addEventListener('click', () => dialog.showModal());
  });
  if (new URLSearchParams(window.location.search).get('create') === '1') {
    dialog.showModal();
    const url = new URL(window.location.href);
    url.searchParams.delete('create');
    window.history.replaceState({}, '', url);
  }
  dialog.addEventListener('close', async () => {
    if (dialog.returnValue !== 'create') return;
    const form = dialog.querySelector('form');
    if (!form.reportValidity()) return;
    const status = dialog.querySelector('[data-plan-create-status]');
    const fields = Object.fromEntries(new FormData(form));
    const payload = {title: fields.title, objective: fields.objective, advertiser_name: fields.advertiser_name, campaign_name: fields.campaign_name, briefing: {budget: fields.budget, period: fields.period, geography: fields.geography, kpis: fields.kpis, notes: fields.notes}};
    status.textContent = 'Criando plano…';
    try {
      const response = await fetch('/familia/api/planner/plans', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível criar o plano.');
      window.location.assign('/planos/' + encodeURIComponent(data.plan.id));
    } catch (error) { status.textContent = error.message; dialog.showModal(); }
  });
})();
