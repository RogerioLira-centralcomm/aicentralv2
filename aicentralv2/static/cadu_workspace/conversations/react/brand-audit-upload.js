(() => {
  const MAX_FILES = 4;

  const describeFiles = (files) => {
    const count = files.length;
    if (!count) return 'Arraste ou escolha até quatro versões oficiais.';
    if (count === 1) return files[0].name;
    return `${count} arquivos selecionados: ${Array.from(files).map((file) => file.name).join(', ')}`;
  };

  const prepare = (input) => {
    if (input.dataset.brandDropReady === 'true') return;
    const label = input.closest('label');
    if (!label) return;
    input.dataset.brandDropReady = 'true';
    input.accept = 'image/*';
    label.classList.add('cadu-ds-brand-dropzone');

    const prompt = document.createElement('span');
    prompt.className = 'cadu-ds-brand-dropzone__prompt';
    prompt.innerHTML = '<strong>Solte a família de logos aqui</strong><small>Principal, horizontal, vertical, símbolo e versões claro/escuro.</small>';
    input.before(prompt);

    const status = document.createElement('small');
    status.className = 'cadu-ds-brand-dropzone__status';
    status.textContent = describeFiles(input.files);
    input.after(status);

    const refresh = () => {
      status.textContent = describeFiles(input.files);
      label.classList.toggle('has-files', input.files.length > 0);
    };
    input.addEventListener('change', refresh);

    for (const eventName of ['dragenter', 'dragover']) {
      label.addEventListener(eventName, (event) => {
        event.preventDefault();
        label.classList.add('is-dragging');
      });
    }
    for (const eventName of ['dragleave', 'drop']) {
      label.addEventListener(eventName, (event) => {
        event.preventDefault();
        label.classList.remove('is-dragging');
      });
    }
    label.addEventListener('drop', (event) => {
      const files = Array.from(event.dataTransfer?.files || [])
        .filter((file) => file.type.startsWith('image/'))
        .slice(0, MAX_FILES);
      if (!files.length) return;
      const transfer = new DataTransfer();
      files.forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
  };

  const refresh = () => document
    .querySelectorAll('.cadu-ds-brand-form input[type="file"][name="images"]')
    .forEach(prepare);

  new MutationObserver(refresh).observe(document.documentElement, { childList: true, subtree: true });
  refresh();
})();
