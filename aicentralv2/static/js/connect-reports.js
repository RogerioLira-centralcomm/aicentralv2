(() => {
  'use strict';
  const entitiesNode = document.getElementById('report-entities');
  const entities = entitiesNode ? JSON.parse(entitiesNode.textContent) : [];
  document.querySelector('.cr-filter')?.remove();
  document.querySelectorAll('[data-cx-dialog="campaign-wizard"]').forEach(button => {
    button.setAttribute('aria-label', 'Criar relatório de campanha');
    const label = [...button.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    if (label) label.textContent = ' Criar relatório';
  });
  const forms = document.querySelectorAll('#report-form, #campaign-form');
  const updatePreview = form => {
    const preview = form.closest('.cr-editor')?.querySelector('#report-preview') || document.querySelector('#campaign-wizard #report-preview');
    if (!preview) return;
    const value = name => form.elements[name]?.value || '';
    const brand = form.elements.brand_ref;
    const brandName = brand?.value ? brand.selectedOptions[0].textContent : 'Marca do projeto';
    const set = (id, content) => { const node = preview.querySelector(id); if (node) node.textContent = content; };
    set('#preview-brand', brandName); set('#preview-campaign', value('campaign_name') || 'Nome da campanha');
    set('#preview-period', `Período previsto: ${value('start_date') || 'a definir'} até ${value('end_date') || 'a definir'}`);
    set('#preview-objective', value('objective') || 'Defina o objetivo para orientar a leitura dos resultados.');
    set('#preview-goals', value('goals') || 'Registre os indicadores e o período de avaliação.');
    const client = preview.querySelector('#preview-client'); if (client) client.hidden = value('brand_mode') === 'project' || brandName.trim().toLowerCase() === client.textContent.trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/i.test(value('accent'))) preview.style.setProperty('--report-accent', value('accent'));
  };
  forms.forEach(form => {
    const select = form.elements.project_ref, brand = form.elements.brand_ref;
    const constrainBrands = () => { if (!select || !brand) return; const project = entities.find(item => item.ref === select.value); const refs = project?.related_refs || []; Array.from(brand.options).forEach(option => { option.hidden = Boolean(option.value && !refs.includes(option.value)); option.disabled = option.hidden; }); if (brand.selectedOptions[0]?.disabled) brand.value = ''; const allowed = Array.from(brand.options).filter(o => o.value && !o.disabled); if (!brand.value && allowed.length === 1) brand.value = allowed[0].value; };
    form.addEventListener('input', () => updatePreview(form)); select?.addEventListener('change', () => { constrainBrands(); updatePreview(form); }); constrainBrands(); updatePreview(form);
    form.addEventListener('submit', event => { if (!form.checkValidity()) return; const button = event.submitter; window.ConnectUI?.setBusy(button, true, 'Salvando'); });
  });
  document.querySelectorAll('[data-cx-upload]').forEach(form => {
    const input = form.querySelector('input[type=file]'), zone = form.querySelector('[data-dropzone]'), count = form.querySelector('.cr-upload-count');
    const render = files => { const amount = files?.length || 0; count.textContent = amount ? `${amount} print${amount === 1 ? '' : 's'} pronto${amount === 1 ? '' : 's'} para receber.` : ''; };
    input?.addEventListener('change', () => render(input.files)); ['dragenter','dragover'].forEach(type => zone?.addEventListener(type, event => { event.preventDefault(); zone.classList.add('is-over'); })); ['dragleave','drop'].forEach(type => zone?.addEventListener(type, event => { event.preventDefault(); zone.classList.remove('is-over'); })); zone?.addEventListener('drop', event => { if (event.dataTransfer.files.length) { input.files = event.dataTransfer.files; render(input.files); } });
    form.addEventListener('submit', event => { if (!form.checkValidity()) return; window.ConnectUI?.setBusy(event.submitter, true, 'Recebendo'); });
  });
  document.querySelectorAll('[data-cx-flash]').forEach(node => { const text = node.dataset.cxFlash; if (text) setTimeout(() => window.ConnectUI?.toast(text, node.classList.contains('cx-banner--error') ? 'error' : 'info'), 280); });
  document.querySelectorAll('[data-preview-toggle]').forEach(button => button.addEventListener('click', () => { const documentCard = button.closest('.cr-preview').querySelector('.cr-document'); const hidden = documentCard.hidden = !documentCard.hidden; button.textContent = hidden ? 'Mostrar' : 'Ocultar'; }));
})();
