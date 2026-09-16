(() => {
  const dialog = document.querySelector('[data-brand-create-dialog]');
  const form = document.querySelector('[data-brand-create-form]');
  if (!dialog || !form) return;
  const open = () => { dialog.showModal(); form.querySelector('input[name="name"]')?.focus(); };
  document.querySelectorAll('[data-brand-create-open]').forEach((button) => button.addEventListener('click', open));
  dialog.querySelectorAll('[data-brand-create-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  const dropzone = dialog.querySelector('[data-brand-dropzone]');
  const input = dialog.querySelector('[data-brand-file-input]');
  const output = dialog.querySelector('[data-brand-file-list]');
  const renderFiles = () => { const files = [...(input.files || [])]; output.textContent = files.length ? `${files.length} ${files.length === 1 ? 'arquivo selecionado' : 'arquivos selecionados'}: ${files.slice(0, 2).map((file) => file.name).join(', ')}${files.length > 2 ? '…' : ''}` : ''; dropzone.classList.toggle('has-files', files.length > 0); };
  input?.addEventListener('change', renderFiles);
  const website = form.querySelector('input[name="website_url"]');
  const name = form.querySelector('input[name="name"]');
  const normaliseWebsite = () => {
    let value = website?.value.trim();
    if (!value) return;
    if (!/^https?:\/\//i.test(value)) value = `https://${value.replace(/^\/+/, '')}`;
    try {
      const url = new URL(value);
      website.value = url.toString();
      if (!name?.value.trim() && url.hostname) name.value = url.hostname.replace(/^www\./, '').split('.')[0].replace(/[-_.]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
    } catch (_) { /* O servidor mantém a validação final. */ }
  };
  website?.addEventListener('blur', normaliseWebsite);
  ['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add('is-dragging'); }));
  ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove('is-dragging'); }));
  dropzone.addEventListener('drop', (event) => { if (!event.dataTransfer?.files?.length || !window.DataTransfer) return; const transfer = new DataTransfer(); [...event.dataTransfer.files].slice(0, 8).forEach((file) => transfer.items.add(file)); input.files = transfer.files; renderFiles(); });
  form.addEventListener('submit', () => { const button = form.querySelector('[data-brand-create-submit]'); if (button) { button.disabled = true; button.innerHTML = 'Preparando marca…'; } });
})();
