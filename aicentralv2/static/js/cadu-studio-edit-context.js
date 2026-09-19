(() => {
  const project = document.getElementById('mcCaduProject');
  const refs = document.querySelector('#mcTrocrGlobalRefs');
  const card = document.querySelector('#mcTrocrBrandContextCard');
  const apiRoot = document.querySelector('#mcCaduBar')?.dataset.mcApiRoot || '/parametros/api';
  if (!project || !refs) return;
  const escape = value => String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const imageUrl = item => String(item?.image_url || item?.thumb_url || item?.asset_url || item?.url || '').trim();
  const render = items => {
    refs.innerHTML = items.length ? items.slice(0, 10).map(item => `<button type="button" class="mc-trocr-global-ref" data-reference-url="${escape(imageUrl(item))}" title="${escape(item.label || item.name || 'Referência global')}"><img src="${escape(imageUrl(item))}" alt=""><span>${escape(item.label || item.name || 'Composição')}</span></button>`).join('') : '<span>Nenhuma referência disponível para este formato.</span>';
  };
  document.addEventListener('cadu:project-ready', async event => {
    const detail = event.detail || {};
    const option = project.selectedOptions[0];
    let brand = {};
    try { brand = JSON.parse(option?.dataset.brandContext || '{}'); } catch (_) {}
    if (card) card.hidden = !detail.projectId;
    const projectName = document.querySelector('#mcTrocrProjectName');
    if (projectName) projectName.textContent = detail.projectId
      ? `${option?.textContent || 'Projeto ativo'}`
      : 'Criação sem projeto';
    const name = document.querySelector('#mcTrocrBrandName'); if (name) name.textContent = detail.brandName || brand.name || 'Marca do projeto';
    const summary = document.querySelector('#mcTrocrBrandSummary'); if (summary) summary.textContent = brand.brand_summary || 'DNA, ativos e referências aplicados à edição';
    const avatar = document.querySelector('#mcTrocrBrandAvatar'); if (avatar) { avatar.style.backgroundImage = brand.logo_url ? `url("${brand.logo_url}")` : ''; avatar.textContent = brand.logo_url ? '' : (detail.brandName || 'M').slice(0, 1); }
    try {
      const query = detail.clientId ? `?client_id=${encodeURIComponent(detail.clientId)}` : '';
      const response = await fetch(`${apiRoot}/format-lab/studio/library-sessions${query}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      const payload = await response.json();
      // Studio APIs are enveloped as { success, data }. Accepting the bare
      // payload too keeps this rail compatible with the local test server.
      const data = payload?.data || payload || {};
      render(Array.isArray(data.reference_masks) ? data.reference_masks : []);
    } catch (_) { render([]); }
  });
  refs.addEventListener('click', event => {
    const button = event.target.closest('.mc-trocr-global-ref');
    if (!button) return;
    refs.querySelector('.is-selected')?.classList.remove('is-selected');
    button.classList.add('is-selected');
    document.dispatchEvent(new CustomEvent('cadu:global-reference-selected', { detail: { url: button.dataset.referenceUrl, label: button.title, source: 'global', role: 'composition' } }));
  });
})();
