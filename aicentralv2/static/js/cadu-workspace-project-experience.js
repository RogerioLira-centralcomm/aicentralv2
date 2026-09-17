(() => {
  'use strict';
  const bindDialog = (dialog, opener, closer) => {
    if (!dialog) return;
    document.querySelectorAll(opener).forEach(button => button.addEventListener('click', () => dialog.showModal()));
    document.querySelectorAll(closer).forEach(button => button.addEventListener('click', () => dialog.close()));
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  };
  bindDialog(document.querySelector('[data-project-quality-dialog]'), '[data-project-quality-open]', '[data-project-quality-close]');
  const brandDialog = document.querySelector('[data-project-brand-dialog]');
  bindDialog(brandDialog, '[data-project-brand-open]', '[data-project-brand-close]');
  brandDialog?.querySelectorAll('input[name="brand_ids"]').forEach(input => input.addEventListener('change', () => {
    if (input.checked) brandDialog.querySelectorAll('input[name="brand_ids"]').forEach(other => { if (other !== input) other.checked = false; });
  }));
  bindDialog(document.querySelector('[data-project-identity-dialog]'), '[data-project-identity-open]', '[data-project-identity-close]');
  bindDialog(document.querySelector('[data-project-sources-dialog]'), '[data-project-sources-open]', '[data-project-sources-close]');
  const qualityHelp = document.querySelector('.workspace-project-quality-dialog__body section:nth-child(2) > p');
  if (qualityHelp) qualityHelp.textContent = 'O Cadu pode preparar uma primeira versão para revisão humana. Nada é publicado ou aplicado automaticamente.';
  document.querySelectorAll('[data-project-starter]').forEach(button => button.addEventListener('click', () => {
    const url = new URL('/workspace/app/conversas', window.location.origin);
    const project = document.querySelector('[data-project-ref]')?.dataset.projectRef;
    if (project) url.searchParams.set('project', project);
    url.searchParams.set('prompt', button.dataset.prompt || 'Ajude a estruturar este projeto.');
    window.location.assign(url);
  }));
  const form = document.querySelector('[data-project-brand-import]');
  const progress = document.querySelector('[data-project-brand-progress]');
  if (!form || !progress) return;
  document.querySelectorAll('[data-brand-dropzone]').forEach(zone => {
    const input = zone.querySelector('input[type="file"]');
    const label = zone.querySelector('[data-brand-file-label]');
    const describe = () => {
      const count = input.files?.length || 0;
      if (label) label.textContent = count ? `${count} arquivo${count === 1 ? '' : 's'} selecionado${count === 1 ? '' : 's'}` : 'Opcional';
      zone.classList.toggle('has-files', Boolean(count));
    };
    input?.addEventListener('change', describe);
    ['dragenter', 'dragover'].forEach(eventName => zone.addEventListener(eventName, event => {
      event.preventDefault(); zone.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach(eventName => zone.addEventListener(eventName, event => {
      event.preventDefault(); zone.classList.remove('is-dragging');
    }));
    zone.addEventListener('drop', event => {
      if (!event.dataTransfer?.files?.length || !input) return;
      const files = Array.from(event.dataTransfer.files).filter(file => /^image\/(png|jpeg|webp)$/.test(file.type));
      if (!files.length) return;
      const transfer = new DataTransfer();
      files.slice(0, input.multiple ? 7 : 1).forEach(file => transfer.items.add(file));
      input.files = transfer.files; describe();
    });
  });
  let timer;
  const setProgress = (message, state = '') => {
    progress.hidden = false; progress.className = 'workspace-project-brand-import__progress ' + state;
    progress.textContent = message;
  };
  const poll = async url => {
    try {
      const response = await fetch(url, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível acompanhar a análise.');
      if (['queued', 'running'].includes(data.status)) {
        setProgress(data.message || 'Processando a marca…');
        timer = window.setTimeout(() => poll(url), 1500);
      } else if (data.status === 'pending_approval') {
        setProgress('A proposta da marca está pronta para revisão. Atualizando o projeto…', 'is-ready');
        timer = window.setTimeout(() => window.location.reload(), 900);
      } else if (data.status === 'failed') setProgress(data.error || 'A análise não foi concluída.', 'is-error');
    } catch (error) { setProgress(error.message || 'Não foi possível acompanhar a análise.', 'is-error'); }
  };
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = form.querySelector('button');
    if (submit.disabled) return;
    submit.disabled = true; setProgress('Criando a marca e preparando as evidências oficiais…');
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'Accept': 'application/json'}});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || data.description || 'Não foi possível iniciar a importação.');
      await poll(data.status_url);
    } catch (error) { setProgress(error.message || 'Não foi possível iniciar a importação.', 'is-error'); }
    finally { submit.disabled = false; }
  });
  window.addEventListener('beforeunload', () => window.clearTimeout(timer));
})();
