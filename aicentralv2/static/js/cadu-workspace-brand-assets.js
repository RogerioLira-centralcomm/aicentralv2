(() => {
  const form = document.querySelector('[data-brand-asset-upload]');
  const dropzone = document.querySelector('[data-brand-asset-dropzone]');
  const input = document.querySelector('[data-brand-asset-input]');
  const output = document.querySelector('[data-brand-asset-files]');
  const role = document.querySelector('[data-brand-asset-role]');
  const prompt = document.querySelector('[data-brand-asset-prompt]');
  if (!form || !dropzone || !input || !output) return;
  const render = () => {
    const files = [...(input.files || [])];
    output.textContent = files.length ? `${files.length} ${files.length === 1 ? 'imagem pronta para enviar' : 'imagens prontas para enviar'}` : 'Nenhum arquivo selecionado';
    dropzone.classList.toggle('has-files', files.length > 0);
  };
  const syncRole = () => {
    const isLogo = role?.value === 'logo';
    input.multiple = !isLogo;
    if (prompt) prompt.textContent = isLogo ? 'Escolha o arquivo do logo oficial' : 'Arraste imagens ou clique para escolher';
    if (input.files.length && isLogo && input.files.length > 1) input.value = '';
    render();
  };
  input.addEventListener('change', render);
  role?.addEventListener('change', syncRole);
  ['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add('is-dragging'); }));
  ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove('is-dragging'); }));
  dropzone.addEventListener('drop', (event) => {
    const files = [...(event.dataTransfer?.files || [])].filter((file) => file.type.startsWith('image/')).slice(0, 8);
    if (!files.length || !window.DataTransfer) return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    render();
  });
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"], button:not([type])');
    if (button) { button.disabled = true; button.textContent = 'Enviando imagens…'; }
  });
  syncRole();
})();
