(() => {
  const root = document.querySelector('[data-observability-root]');
  if (!root) return;
  const detail = root.querySelector('[data-observability-detail]');
  const body = root.querySelector('[data-detail-body]');
  const title = root.querySelector('[data-detail-title]');
  const close = () => { detail.hidden = true; body.replaceChildren(); };
  root.querySelector('[data-detail-close]')?.addEventListener('click', close);
  const open = async row => {
    detail.hidden = false; title.textContent = 'Carregando Turn…'; body.textContent = '';
    try {
      const response = await fetch(root.dataset.runEndpoint + row.dataset.observabilityRun, {headers:{Accept:'application/json'}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Turn indisponível.');
      title.textContent = `${data.run.execution_mode} · ${data.run.status}`;
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
