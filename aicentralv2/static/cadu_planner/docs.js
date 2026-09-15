/* SmartPlanner Docs, read-only while write confirmations are being migrated. */
(() => {
  'use strict';
  const root = document.querySelector('[data-planner-docs]');
  const dialog = document.querySelector('[data-doc-dialog]');
  if (!root || !dialog) return;
  const preview = dialog.querySelector('[data-doc-preview]');
  const heading = dialog.querySelector('[data-doc-heading]');
  const type = dialog.querySelector('[data-doc-type]');
  const meta = dialog.querySelector('[data-doc-meta]');
  let opener = null;
  const close = () => { dialog.close(); opener?.focus(); };
  dialog.querySelector('[data-doc-close]').addEventListener('click', close);
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
  root.querySelectorAll('[data-doc-open]').forEach(button => button.addEventListener('click', async () => {
    opener = button; heading.textContent = 'Carregando documento…'; type.textContent = ''; meta.textContent = ''; preview.textContent = 'Preparando a prévia…'; dialog.showModal();
    try {
      const response = await fetch('/familia/api/planner/documents/' + encodeURIComponent(button.dataset.docOpen), {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível abrir este documento.');
      heading.textContent = data.document.title || 'Documento';
      type.textContent = data.document.type || 'Documento';
      meta.textContent = data.document.updated_at ? 'Atualizado em ' + data.document.updated_at : '';
      preview.textContent = data.preview || 'Este documento não possui texto para prévia.';
    } catch (error) { heading.textContent = 'Documento indisponível'; preview.textContent = error.message; }
  }));
})();
