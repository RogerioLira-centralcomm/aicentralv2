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
  document.querySelectorAll('[data-project-brand-link]').forEach(input => input.addEventListener('change', async () => {
    input.disabled = true;
    try {
      await api('project-brand-links', 'PUT', {project_ref: input.dataset.projectRef, brand_ref: input.dataset.brandRef, linked: input.checked});
      location.reload();
    } catch (error) {
      input.checked = !input.checked;
      input.disabled = false;
      feedback.textContent = error.message;
    }
  }));
  document.querySelectorAll('.family-switch, .family-context-menu').forEach(details => {
    details.addEventListener('toggle', () => {
      if (details.open) document.querySelectorAll('.family-switch, .family-context-menu').forEach(other => {
        if (other !== details) other.open = false;
      });
    });
    document.addEventListener('click', event => { if (!details.contains(event.target)) details.open = false; });
    details.addEventListener('keydown', event => { if (event.key === 'Escape') { details.open = false; details.querySelector('summary').focus(); } });
  });
})();
