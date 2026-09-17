(() => {
  const form = document.querySelector('[data-brand-asset-upload]');
  const dropzone = document.querySelector('[data-brand-asset-dropzone]');
  const input = document.querySelector('[data-brand-asset-input]');
  const output = document.querySelector('[data-brand-asset-files]');
  const assets = document.querySelector('#brand-assets');
  const review = document.querySelector('[data-brand-review-summary]');
  const editor = document.querySelector('.workspace-brand-editor');
  const activity = document.querySelector('.workspace-brand-activity')?.closest('article');
  const process = document.querySelector('.workspace-brand-process-callout');
  const readiness = document.querySelector('.workspace-brand-readiness');
  const details = document.querySelector('.workspace-brand-detail-grid');
  if (assets && review) review.after(assets);
  if (details) details.style.gridTemplateColumns = '1fr';
  if (activity) activity.remove();
  if (process) process.remove();
  if (readiness) readiness.classList.add('is-compact');
  const summary = document.querySelector('[data-brand-review-summary]');
  const audit = document.querySelector('.workspace-brand-audit-form');
  const emptyAssets = Boolean(assets?.querySelector('.workspace-empty'));
  if (emptyAssets) {
    readiness?.remove();
    editor?.remove();
    document.querySelector('#brand-projects')?.remove();
    if (summary) {
      summary.classList.add('is-onboarding');
      const copy = summary.querySelector('p');
      if (copy) copy.textContent = 'Comece adicionando o logo e referências visuais, ou analise o site oficial para preencher a identidade automaticamente.';
    }
  }
  const reviewTitle = summary?.querySelector('h2')?.textContent.trim() || '';
  if (summary && audit && !['Análise em andamento', 'Proposta pronta para decisão'].includes(reviewTitle)) {
    const actions = summary.querySelector('.workspace-brand-review-actions');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = reviewTitle === 'Ainda não analisada' ? 'Analisar marca' : 'Reanalisar marca';
    button.addEventListener('click', () => audit.requestSubmit());
    actions?.append(button);
  }
  if (!form || !dropzone || !input || !output) return;
  const render = () => {
    const files = [...(input.files || [])];
    output.textContent = files.length ? `${files.length} ${files.length === 1 ? 'imagem pronta para enviar' : 'imagens prontas para enviar'}` : 'Nenhum arquivo selecionado';
    dropzone.classList.toggle('has-files', files.length > 0);
  };
  input.addEventListener('change', render);
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
})();
