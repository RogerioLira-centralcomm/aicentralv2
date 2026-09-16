(() => {
  document.querySelectorAll('[data-source-remove]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm('Remover esta fonte do projeto? O arquivo original será movido para a lixeira interna.')) event.preventDefault();
    });
  });

  const sourceStatus = document.querySelector('[data-source-status-url]');
  if (sourceStatus) {
    let sawPending = false;
    const pollSources = async () => {
      try {
        const response = await fetch(sourceStatus.dataset.sourceStatusUrl, {headers: {'Accept': 'application/json'}});
        if (!response.ok) return;
        const payload = await response.json();
        const pending = (payload.sources || []).some((item) => ['queued', 'indexing'].includes(item.status));
        if (pending) {
          sawPending = true;
          window.setTimeout(pollSources, 5000);
        } else if (sawPending) {
          window.location.reload();
        }
      } catch (_) { /* A falha de rede não impede o restante do dossiê. */ }
    };
    pollSources();
  }

  document.querySelectorAll('[data-open-project-create]').forEach((button) => {
    button.addEventListener('click', () => {
      const createPanel = document.querySelector('.workspace-projects-create');
      if (!createPanel) return;
      createPanel.open = true;
      createPanel.querySelector('input[name="name"]')?.focus();
    });
  });

  const sourceFileInput = document.querySelector('.workspace-source-ingest input[type="file"]');
  if (sourceFileInput) {
    const sourceForm = sourceFileInput.closest('form');
    const sourceArea = sourceFileInput.closest('.workspace-source-ingest');
    const openSource = () => sourceFileInput.closest('details')?.setAttribute('open', '');
    sourceFileInput.addEventListener('change', openSource);
    document.addEventListener('dragover', (event) => {
      if (!event.dataTransfer?.types?.includes('Files')) return;
      event.preventDefault();
      sourceArea?.classList.add('is-dragging');
    });
    document.addEventListener('dragleave', (event) => {
      if (!event.relatedTarget) sourceArea?.classList.remove('is-dragging');
    });
    document.addEventListener('drop', (event) => {
      if (!event.dataTransfer?.files?.length) return;
      event.preventDefault();
      sourceArea?.classList.remove('is-dragging');
      if (!window.DataTransfer) return;
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      sourceFileInput.files = transfer.files;
      openSource();
    });
    const dialog = document.createElement('dialog');
    dialog.className = 'workspace-upload-dialog';
    dialog.innerHTML = '<div class="workspace-upload-dialog__body"><span class="workspace-upload-dialog__mark"><i class="fa-solid fa-file-arrow-up" aria-hidden="true"></i></span><h2>Adicionar à base do projeto?</h2><p>O arquivo original ficará privado. Vamos extrair o conteúdo para que o Cadu use este contexto em conversas futuras.</p><strong class="workspace-upload-dialog__file"></strong><footer><button type="button" data-upload-cancel>Voltar</button><button type="button" data-upload-confirm>Adicionar e indexar</button></footer></div>';
    document.body.append(dialog);
    let pendingSubmit = false;
    sourceForm?.addEventListener('submit', (event) => {
      if (pendingSubmit || !sourceFileInput.files.length) return;
      event.preventDefault();
      dialog.querySelector('.workspace-upload-dialog__file').textContent = sourceFileInput.files[0].name;
      dialog.showModal();
    });
    dialog.querySelector('[data-upload-cancel]').addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-upload-confirm]').addEventListener('click', () => {
      pendingSubmit = true; dialog.close(); sourceForm.requestSubmit();
    });
  }

  const form = document.querySelector('[data-project-query]');
  const output = document.querySelector('[data-query-results]');
  if (!form || !output) return;

  const escape = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const button = form.querySelector('button');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = form.elements.query.value.trim();
    if (query.length < 3) { output.textContent = 'Escreva ao menos três caracteres para consultar.'; return; }
    if (!token) { output.textContent = 'Atualize a página para consultar a base com segurança.'; return; }
    output.textContent = 'Consultando fontes indexadas…';
    output.setAttribute('aria-busy', 'true');
    button.disabled = true;
    try {
      const response = await fetch(form.dataset.url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, body: JSON.stringify({query})});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Não foi possível consultar a base.');
      output.innerHTML = payload.results.length ? `<p class="workspace-query-count">${payload.result_count} ${payload.result_count === 1 ? 'fonte encontrada' : 'fontes encontradas'}</p>${payload.results.map((item) => `<article><small>Trecho de fonte</small><b>${escape(item.source)}</b><p>${escape(item.excerpt)}</p></article>`).join('')}` : '<p>Nenhum trecho indexado corresponde a esta consulta.</p>';
    } catch (error) { output.textContent = error.message || 'Não foi possível consultar a base.'; }
    finally { output.removeAttribute('aria-busy'); button.disabled = false; }
  });
})();
