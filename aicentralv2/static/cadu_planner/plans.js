(() => {
  const root = document.querySelector('[data-planner-plans]');
  const dialog = document.querySelector('[data-plan-create-dialog]');
  if (!root || !dialog) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  root.querySelector('[data-plan-create]').addEventListener('click', () => dialog.showModal());
  dialog.addEventListener('close', async () => {
    if (dialog.returnValue !== 'create') return;
    const form = dialog.querySelector('form');
    if (!form.reportValidity()) return;
    const response = await fetch('/familia/api/planner/plans', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(Object.fromEntries(new FormData(form)))});
    if (!response.ok) return;
    window.location.reload();
  });
})();
