document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('[data-connect-tab]');
  const panels = document.querySelectorAll('[data-connect-panel]');
  const selectPanel = (name) => {
    tabs.forEach((tab) => tab.classList.toggle('is-current', tab.dataset.connectTab === name));
    panels.forEach((panel) => {
      const active = panel.dataset.connectPanel === name;
      panel.hidden = !active;
      panel.classList.toggle('is-current', active);
      if (active) {
        panel.classList.remove('is-entering');
        requestAnimationFrame(() => panel.classList.add('is-entering'));
      }
    });
  };
  tabs.forEach((tab) => tab.addEventListener('click', (event) => {
    event.preventDefault();
    selectPanel(tab.dataset.connectTab);
    history.replaceState(null, '', `#${tab.dataset.connectTab}`);
  }));
  document.querySelectorAll('[data-connect-open]').forEach((button) => button.addEventListener('click', () => {
    const panel = button.dataset.connectOpen;
    selectPanel(panel);
    history.replaceState(null, '', `#${panel}`);
    document.querySelector(`[data-connect-panel="${panel}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  if (location.hash) selectPanel(location.hash.slice(1));

  const contextSelector = document.querySelector('.connect-context-selector');
  const clientSelect = contextSelector?.querySelector('[data-workspace-client]');
  const projectSelect = contextSelector?.querySelector('[data-workspace-project]');
  clientSelect?.addEventListener('change', () => {
    if (projectSelect) projectSelect.value = '';
    contextSelector.submit();
  });
  projectSelect?.addEventListener('change', () => contextSelector.submit());

  document.querySelectorAll('[data-campaign-project]').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    const status = form.querySelector('[data-status]');
    button.disabled = true;
    status.textContent = 'Salvando…';
    try {
      const response = await fetch(form.dataset.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: form.elements.project_id.value }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'Não foi possível salvar.');
      status.textContent = body.message;
    } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  }));

  const toast = document.querySelector('[data-connect-toast]');
  let toastTimer;
  document.querySelectorAll('[data-connect-notice]').forEach((button) => button.addEventListener('click', () => {
    if (!toast) return;
    toast.textContent = button.dataset.connectNotice;
    toast.classList.add('is-visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 3600);
  }));
});
