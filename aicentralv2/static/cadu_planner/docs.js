(() => {
  'use strict';
  const root = document.querySelector('[data-planner-docs]');
  const dialog = document.querySelector('[data-doc-dialog]');
  const createDialog = document.querySelector('[data-doc-create-dialog]');
  if (!root || !dialog) return;

  const writable = root.dataset.writable === 'true';
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const preview = dialog.querySelector('[data-doc-preview]');
  const editor = dialog.querySelector('[data-doc-editor]');
  const actions = dialog.querySelector('[data-doc-actions]');
  const heading = dialog.querySelector('[data-doc-heading]');
  const type = dialog.querySelector('[data-doc-type]');
  const meta = dialog.querySelector('[data-doc-meta]');
  const title = dialog.querySelector('[data-doc-title]');
  const content = dialog.querySelector('[data-doc-content]');
  const status = dialog.querySelector('[data-doc-status]');
  let opener = null;
  let current = null;

  const request = async (path, options = {}) => {
    const response = await fetch('/familia/api/planner/docs' + path, {
      credentials: 'same-origin',
      headers: {...(options.body ? {'Content-Type': 'application/json'} : {}), ...(options.body ? {'X-CSRF-Token': csrf} : {})},
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Não foi possível concluir esta ação.');
    return data;
  };
  const close = () => { dialog.close(); opener?.focus(); };
  const showPreview = () => { editor.hidden = true; preview.hidden = false; };
  const showEditor = () => { editor.hidden = false; preview.hidden = true; title.focus(); };

  dialog.querySelector('[data-doc-close]').addEventListener('click', close);
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });

  root.querySelectorAll('[data-doc-open]').forEach(button => button.addEventListener('click', async () => {
    opener = button; current = null; heading.textContent = 'Carregando documento…'; type.textContent = ''; meta.textContent = ''; preview.textContent = 'Preparando a prévia…'; actions.hidden = true; showPreview(); dialog.showModal();
    try {
      const data = await request('/' + encodeURIComponent(button.dataset.docOpen));
      current = data.document;
      heading.textContent = current.title || 'Documento';
      type.textContent = current.type || 'Documento';
      meta.textContent = current.updated_at ? 'Atualizado em ' + current.updated_at : '';
      preview.textContent = (current.html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() || 'Este documento não possui texto para prévia.';
      title.value = current.title || '';
      content.innerHTML = current.html || '';
      status.value = current.status || 'draft';
      actions.hidden = !writable || !current.is_owner;
    } catch (error) { heading.textContent = 'Documento indisponível'; preview.textContent = error.message; }
  }));

  actions.querySelector('[data-doc-edit]').addEventListener('click', showEditor);
  actions.querySelector('[data-doc-save]').addEventListener('click', async () => {
    if (!current) return;
    try {
      const data = await request('/' + current.id, {method: 'PUT', body: JSON.stringify({title: title.value, html: content.innerHTML, status: status.value})});
      current = data.document; heading.textContent = current.title; meta.textContent = 'Alterações salvas agora'; preview.textContent = content.textContent.trim() || 'Este documento não possui texto para prévia.'; showPreview();
    } catch (error) { meta.textContent = error.message; }
  });
  actions.querySelector('[data-doc-review]').addEventListener('click', async event => {
    if (!current) return;
    const button = event.currentTarget;
    if (!editor.hidden) {
      meta.textContent = 'Salve as alterações do documento antes de pedir uma revisão.';
      return;
    }
    button.disabled = true;
    meta.textContent = 'O Cadu está fazendo as três revisões…';
    try {
      const estimate = await request('/' + current.id + '/review/estimate');
      if (!window.confirm(`O Cadu fará ${estimate.passes} revisões e pode usar até ${estimate.estimated_tokens.toLocaleString('pt-BR')} créditos. Continuar?`)) {
        meta.textContent = 'Revisão cancelada.';
        return;
      }
      meta.textContent = 'O Cadu está fazendo as três revisões…';
      const data = await request('/' + current.id + '/review', {method: 'POST', body: '{}'});
      current = data.document;
      content.innerHTML = current.html || '';
      preview.textContent = content.textContent.trim() || 'Este documento não possui texto para prévia.';
      meta.textContent = `Versão ${data.review.applied_pass} aplicada${data.review.charged_tokens ? ` · ${data.review.charged_tokens} créditos usados` : ''}.`;
      showPreview();
    } catch (error) { meta.textContent = error.message; }
    finally { button.disabled = false; }
  });
  actions.querySelector('[data-doc-duplicate]').addEventListener('click', async () => {
    if (!current) return;
    try { await request('/' + current.id + '/duplicate', {method: 'POST', body: '{}'}); window.location.reload(); } catch (error) { meta.textContent = error.message; }
  });
  actions.querySelector('[data-doc-share]').addEventListener('click', async () => {
    if (!current) return;
    try {
      const data = await request('/' + current.id + '/share', {method: 'POST', body: JSON.stringify({enabled: !current.share_enabled})});
      current = data.document;
      if (current.share_enabled && current.share_token) {
        const url = new URL('/docs/public/' + encodeURIComponent(current.share_token), window.location.origin).href;
        try { await navigator.clipboard?.writeText(url); meta.textContent = 'Link publicado e copiado para a área de transferência.'; }
        catch (_) { meta.textContent = 'Link publicado; a cópia automática não está disponível neste navegador.'; }
      } else meta.textContent = 'Compartilhamento desativado.';
    } catch (error) { meta.textContent = error.message; }
  });
  actions.querySelector('[data-doc-export]').addEventListener('click', async () => {
    if (!current) return;
    try {
      const response = await fetch('/familia/api/planner/docs/' + current.id + '/export', {method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrf}});
      if (!response.ok) throw new Error('Não foi possível exportar o PDF.');
      const link = Object.assign(document.createElement('a'), {href: URL.createObjectURL(await response.blob()), download: 'documento-' + current.id + '.pdf'});
      link.click(); URL.revokeObjectURL(link.href);
    } catch (error) { meta.textContent = error.message; }
  });

  if (!writable || !createDialog) return;
  root.querySelector('[data-doc-create]').addEventListener('click', async () => {
    const select = createDialog.querySelector('[data-doc-template]');
    try {
      const data = await request('');
      select.replaceChildren(new Option('Em branco', ''));
      (data.templates || []).forEach(item => select.add(new Option(item.name, item.id)));
    } catch (_) { /* Template is optional; creating a blank document remains available. */ }
    createDialog.showModal();
  });
  createDialog.querySelector('form').addEventListener('submit', async event => {
    const submitter = event.submitter;
    if (submitter?.value !== 'create') return;
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await request('', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form)))});
      createDialog.close(); window.location.reload();
    } catch (error) { form.querySelector('footer').dataset.error = error.message; }
  });
})();
