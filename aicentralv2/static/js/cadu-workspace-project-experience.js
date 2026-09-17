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
    const url = new URL('/conversas', window.location.origin);
    const project = document.querySelector('[data-project-ref]')?.dataset.projectRef;
    if (project) url.searchParams.set('project', project);
    url.searchParams.set('prompt', button.dataset.prompt || 'Ajude a estruturar este projeto.');
    window.location.assign(url);
  }));
  const balanceTarget = document.querySelector('.workspace-project-knowledge-summary');
  if (balanceTarget) {
    if (!document.getElementById('workspace-token-balance-style')) {
      const style = document.createElement('style'); style.id = 'workspace-token-balance-style';
      style.textContent = '.workspace-token-balance{display:grid;grid-template-columns:1fr auto;gap:5px 14px;margin:12px 0 0;padding:11px 12px;border:1px solid #c9e4da;border-radius:10px;background:linear-gradient(100deg,#edf9f4,#fff);color:#244b41}.workspace-token-balance>span{grid-column:1/-1;color:#287160;font-size:10px;font-weight:750}.workspace-token-balance strong{font-size:18px;letter-spacing:-.04em}.workspace-token-balance strong small{font-size:10px;font-weight:650;letter-spacing:0}.workspace-token-balance p{grid-column:1/-1;margin:0;color:#5b7069;font-size:10px;line-height:1.4}.workspace-token-balance a{grid-column:2;grid-row:2;align-self:end;color:#176b5e;font-size:10px;font-weight:700;text-decoration:none}.workspace-token-balance a:hover{text-decoration:underline}';
      document.head.append(style);
    }
    fetch('/workspace/api/creditos/resumo', {headers: {'Accept': 'application/json'}, cache: 'no-store'})
      .then(response => response.ok ? response.json() : null)
      .then(credit => {
        if (!credit?.configured) return;
        const card = document.createElement('aside');
        card.className = 'workspace-token-balance';
        const available = Number(credit.available || 0).toLocaleString('pt-BR');
        card.innerHTML = `<span>Saldo compartilhado</span><strong>${available} <small>tokens disponíveis</small></strong><p>Indexar ou reprocessar fontes desconta tokens conforme o texto processado.</p><a href="/uso">Ver consumo e histórico</a>`;
        balanceTarget.append(card);
      }).catch(() => {});
  }
  let form = document.querySelector('[data-project-brand-import]');
  const progress = document.querySelector('[data-project-brand-progress]');
  if (!form || !progress) return;
  const connectedBrand = document.querySelector('.workspace-project-brand-connection__showcase');
  if (connectedBrand) {
    const brandId = connectedBrand.getAttribute('href')?.match(/\/marcas\/(\d+)/)?.[1];
    const brandName = connectedBrand.querySelector('.workspace-project-brand-connection__copy b')?.textContent?.trim() || 'marca atual';
    const csrf = form.querySelector('input[name="_csrf"]')?.value || '';
    if (brandId) {
      form.action = `/workspace/app/marcas/${brandId}/auditoria`;
      form.innerHTML = '<input type="hidden" name="_csrf"><div class="workspace-brand-import__current"><h3></h3><p>Reprocessar consulta o site e atualiza a proposta para revisão. A marca continua vinculada a este projeto.</p><button>Reprocessar marca</button></div>';
      form.querySelector('input[name="_csrf"]').value = csrf;
      form.querySelector('h3').textContent = brandName;
      const existing = brandDialog?.querySelector('.workspace-project-brand-existing');
      if (existing) {
        existing.querySelector('summary').textContent = 'Trocar por uma marca já cadastrada';
        const submit = existing.querySelector('form button');
        if (submit) submit.textContent = 'Usar esta marca no projeto';
      }
    }
  }
  const websiteInput = form.elements.website_url;
  const normalizeWebsite = () => {
    const value = websiteInput?.value.trim();
    if (value && !/^https?:\/\//i.test(value)) websiteInput.value = `https://${value.replace(/^\/+/, '')}`;
  };
  if (websiteInput) {
    // Browsers reject a naked domain for type=url before the submit handler
    // runs. Let people type a normal domain, then make its protocol explicit.
    websiteInput.type = 'text';
    websiteInput.inputMode = 'url';
    websiteInput.addEventListener('blur', normalizeWebsite);
  }
  document.querySelectorAll('[data-brand-dropzone]').forEach(zone => {
    const input = zone.querySelector('input[type="file"]');
    const label = zone.querySelector('[data-brand-file-label]');
    const preview = document.createElement('output');
    preview.className = `workspace-brand-upload-preview workspace-brand-upload-preview--${zone.dataset.brandDropzone}`;
    preview.setAttribute('aria-live', 'polite');
    zone.append(preview);
    let previewUrls = [];
    const renderPreview = files => {
      previewUrls.forEach(url => URL.revokeObjectURL(url));
      previewUrls = [];
      preview.replaceChildren();
      const selected = Array.from(files || []);
      if (!selected.length) return;
      selected.slice(0, input?.multiple ? 4 : 1).forEach(file => {
        const url = URL.createObjectURL(file);
        previewUrls.push(url);
        const image = document.createElement('img');
        image.src = url;
        image.alt = input?.multiple ? `Prévia de ${file.name}` : `Prévia do logo ${file.name}`;
        preview.append(image);
      });
      if (selected.length > 4 && input?.multiple) {
        const extra = document.createElement('span');
        extra.textContent = `+${selected.length - 4}`;
        preview.append(extra);
      }
    };
    const describe = () => {
      const count = input.files?.length || 0;
      if (label) label.textContent = count ? `${count} arquivo${count === 1 ? '' : 's'} selecionado${count === 1 ? '' : 's'}` : 'Opcional';
      zone.classList.toggle('has-files', Boolean(count));
      renderPreview(input.files);
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
      files.slice(0, input.multiple ? 8 : 1).forEach(file => transfer.items.add(file));
      input.files = transfer.files; describe();
    });
    window.addEventListener('beforeunload', () => previewUrls.forEach(url => URL.revokeObjectURL(url)));
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
    normalizeWebsite();
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
