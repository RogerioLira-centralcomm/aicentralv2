(() => {
  'use strict';

  // ====== CONSTANTS ======
  const API = {
    formats: '/parametros/api/formats',
    clients: '/parametros/api/clients',
    campaignClients: '/parametros/api/campaign-clients',
    analyzeBrand: '/parametros/api/clients/analyze-brand',
    campaigns: '/parametros/api/campaigns',
    history: '/parametros/api/history',
    viewerProfiles: '/parametros/api/viewer-profiles',
  };
  const MOCKUPS = {
    portal: { label: 'Portal', icon: 'fa-desktop' },
    tv: { label: 'Smart TV', icon: 'fa-tv' },
    celular: { label: 'Celular', icon: 'fa-mobile-screen' },
    tablet: { label: 'Tablet', icon: 'fa-tablet-screen-button' },
  };
  const state = {
    formats: [],
    clients: [],
    campaignClients: [],
    campaigns: [],
    campaign: null,
    activeStepId: null,
    selectedFormatId: null,
    selectedAssets: new Set(),
    campaignAssets: [],
    publicLinks: [],
    formatJobs: [],
    viewerProfiles: [],
    selectedViewerProfileId: null,
    generatorFormatId: null,
    placementDraft: null,
    originalPlacement: null,
    brandAnalysis: null,
    locks: new Set(),
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
  }[char]));
  const money = (value) => `US$ ${Number(value || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2, maximumFractionDigits: 4,
  })}`;
  const toast = (message, type = 'info') => {
    if (typeof window.showToast === 'function') window.showToast(message, type);
  };
  const setPageError = (message = '') => {
    const alert = $('#mcPageAlert');
    alert.textContent = message;
    alert.classList.toggle('hidden', !message);
  };
  const withLock = async (key, button, callback) => {
    if (state.locks.has(key)) return;
    state.locks.add(key);
    const original = button ? button.innerHTML : '';
    if (button) {
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processando…';
    }
    try {
      return await callback();
    } finally {
      state.locks.delete(key);
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  };

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: options.body instanceof FormData
        ? (options.headers || {})
        : { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      const error = new Error(payload.error || `Erro HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload.data;
  }

  // ====== TAB NAVIGATION ======
  function activateTab(name, updateHash = true) {
    $$('#mcTabs [data-tab]').forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle('cx-tab-active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    $$('.mc-panel').forEach((panel) => panel.classList.toggle('hidden', panel.dataset.panel !== name));
    if (updateHash) history.replaceState(null, '', `#${name}`);
    if (name === 'biblioteca') renderLibrary();
    if (name === 'clientes') renderClients();
    if (name === 'historico') loadHistory();
    if (name === 'variacoes') renderWorkspace();
  }

  // ====== LOADERS ======
  async function loadBaseData() {
    setPageError('');
    const resources = [
      ['formats', 'formatos', API.formats],
      ['clients', 'clientes', API.clients],
      ['campaignClients', 'clientes para campanha', API.campaignClients],
      ['campaigns', 'campanhas', API.campaigns],
      ['viewerProfiles', 'ambientes de mídia', API.viewerProfiles],
    ];
    const results = await Promise.allSettled(resources.map(([, , url]) => api(url)));
    const failures = [];
    results.forEach((result, index) => {
      const [key, label] = resources[index];
      if (result.status === 'fulfilled') state[key] = result.value;
      else failures.push(`${label}: ${result.reason.message}`);
    });
    renderClientOptions();
    renderCampaignOptions();
    renderFormatBrowser();
    renderGeneratorFormats();
    renderLibrary();
    renderClients();
    if (failures.length) {
      setPageError(`Não foi possível carregar ${failures.join(' | ')}`);
    }
  }

  function renderClientOptions() {
    const select = $('#mcCampaignClient');
    const current = select.value;
    select.innerHTML = '<option value="">Selecione um cliente</option>' + state.campaignClients
      .map((client) => {
        const suffix = client.source === 'crm'
          ? (client.profile_status === 'ready' ? 'CRM · marca pronta' : 'CRM · perfil será criado')
          : 'Perfil de marca';
        return `<option value="${escapeHtml(client.selection_key)}">${escapeHtml(client.name)} — ${suffix}</option>`;
      }).join('');
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('client_ref')
      || (params.get('crm_client_id') ? `crm:${params.get('crm_client_id')}` : '')
      || (params.get('creative_client_id') ? `profile:${params.get('creative_client_id')}` : '');
    const preferred = current || requested;
    if (preferred && Array.from(select.options).some((option) => option.value === preferred)) {
      select.value = preferred;
    }
    renderClientPreview();
    renderGeneratorSummary();
    updateGeneratorAvailability();
  }

  function renderCampaignOptions() {
    ['#mcCampaignSelect', '#mcHistoryCampaign'].forEach((selector) => {
      const select = $(selector);
      if (!select) return;
      const current = select.value;
      const first = selector === '#mcHistoryCampaign' ? 'Todas as campanhas' : 'Escolha uma campanha';
      select.innerHTML = `<option value="">${first}</option>` + state.campaigns.map((campaign) => (
        `<option value="${campaign.id}">${escapeHtml(campaign.name)} — ${escapeHtml(campaign.client)}</option>`
      )).join('');
      select.value = selector === '#mcCampaignSelect' && state.campaign
        ? String(state.campaign.id)
        : current;
    });
  }

  // ====== GERADOR ======
  function renderClientPreview() {
    const client = state.campaignClients.find(
      (item) => item.selection_key === $('#mcCampaignClient').value,
    );
    const root = $('#mcClientPreview');
    if (!client) {
      root.innerHTML = '<div class="cx-empty-state"><p>Escolha um cliente para conferir sua identidade.</p></div>';
      return;
    }
    const logo = client.logo_upload_path || client.logo_url;
    root.innerHTML = `
      <div class="mc-identity">
        <div class="mc-identity-brand">
          <span class="mc-logo">${logo ? `<img src="${escapeHtml(logo)}" alt="">` : '<i class="fa-regular fa-building"></i>'}</span>
          <div><strong>${escapeHtml(client.name)}</strong><p class="mc-section-note">${escapeHtml(client.sector || 'Setor não informado')}</p></div>
        </div>
        <div class="mc-swatches" aria-label="Cores da marca">
          ${client.primary_color ? `<span class="mc-swatch" style="background:${escapeHtml(client.primary_color)}" title="${escapeHtml(client.primary_color)}"></span>` : ''}
          ${client.secondary_color ? `<span class="mc-swatch" style="background:${escapeHtml(client.secondary_color)}" title="${escapeHtml(client.secondary_color)}"></span>` : ''}
        </div>
        <div><strong>Tom de voz</strong><p>${escapeHtml(client.tone_of_voice || 'Não informado')}</p></div>
        ${client.brand_profile?.target_audience ? `<div><strong>Público prioritário</strong><p>${escapeHtml(client.brand_profile.target_audience)}</p></div>` : ''}
      </div>`;
  }

  function generatorSelectedFormat() {
    return state.formats.find((item) => String(item.id) === String(state.generatorFormatId));
  }

  function renderGeneratorFormats() {
    const root = $('#mcGeneratorFormatList');
    if (!root) return;
    const category = $('#mcGeneratorFormatCategory')?.value || '';
    const formats = state.formats.filter((format) => !category || format.category === category);
    if (!formats.some((format) => String(format.id) === String(state.generatorFormatId))) {
      state.generatorFormatId = formats[0]?.id || null;
    }
    root.innerHTML = formats.map((format) => `
      <button class="mc-generator-format ${String(format.id) === String(state.generatorFormatId) ? 'is-active' : ''}"
              type="button" data-generator-format="${format.id}">
        <span class="mc-generator-format-icon"><i class="fa-solid ${format.media_type === 'video' ? 'fa-circle-play' : 'fa-image'}"></i></span>
        <span><strong>${escapeHtml(format.name_pt)}</strong><small>${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')}</small></span>
        ${engineBadge(format)}
      </button>`).join('') || '<div class="mc-generator-no-format">Nenhum formato nesta categoria.</div>';
    renderGeneratorFormatPreview();
    renderGeneratorSummary();
    updateGeneratorAvailability();
  }

  function updateGeneratorAvailability() {
    const button = $('#mcCampaignFormSubmit');
    const status = $('#mcCampaignFormStatus');
    if (!button || !status) return;
    const issue = !state.campaignClients.length
      ? 'Nenhum cliente disponível para iniciar a campanha.'
      : !generatorSelectedFormat()
        ? 'Nenhum formato disponível para o primeiro step.'
        : '';
    button.disabled = Boolean(issue);
    button.title = issue;
    if (issue) {
      status.textContent = issue;
      status.dataset.availability = 'true';
    } else if (status.dataset.availability === 'true') {
      status.textContent = '';
      delete status.dataset.availability;
    }
  }

  function renderGeneratorFormatPreview() {
    const root = $('#mcGeneratorFormatPreview');
    if (!root) return;
    const format = generatorSelectedFormat();
    if (!format) {
      root.innerHTML = '<p>Escolha um formato para definir o primeiro step.</p>';
      return;
    }
    const placement = clonePlacement(format);
    const context = placement.context || 'portal';
    const mockup = $('#mcGeneratorMockup');
    if (mockup) {
      mockup.value = ['portal', 'tv', 'celular', 'tablet'].includes(context) ? context : 'portal';
    }
    root.innerHTML = `
      <div class="mc-generator-preview-screen is-${escapeHtml(context)}">
        <span class="mc-generator-preview-chrome">${context === 'tv' ? 'CTV / streaming' : 'Portal / display'}</span>
        <span class="mc-generator-preview-slot" style="left:${placement.slot.x}%;top:${placement.slot.y}%;width:${placement.slot.width}%;height:${placement.slot.height}%">
          <i class="fa-solid ${format.media_type === 'video' ? 'fa-play' : 'fa-bullseye'}"></i>
        </span>
      </div>
      <div class="mc-generator-preview-copy">
        <span><strong>${escapeHtml(format.name_pt)}</strong><small>${escapeHtml(format.mechanic || 'Estático')}</small></span>
        <span class="cx-badge cx-badge-muted">${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')}</span>
      </div>`;
  }

  function renderGeneratorSummary() {
    const root = $('#mcGeneratorSummary');
    const form = $('#mcCampaignForm');
    if (!root || !form) return;
    const client = state.campaignClients.find(
      (item) => item.selection_key === $('#mcCampaignClient')?.value,
    );
    const format = generatorSelectedFormat();
    const name = form.elements.name?.value.trim();
    const budget = form.elements.budget_usd?.value;
    root.innerHTML = `
      <span><small>Marca</small><strong>${escapeHtml(client?.name || 'Não selecionada')}</strong></span>
      <span><small>Campanha</small><strong>${escapeHtml(name || 'Sem nome')}</strong></span>
      <span><small>Primeiro step</small><strong>${escapeHtml(format?.name_pt || 'Não selecionado')}</strong></span>
      <span><small>Limite inicial</small><strong>${money(budget)}</strong></span>`;
  }

  async function createCampaign(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('#mcCampaignFormSubmit');
    $('#mcCampaignFormStatus').textContent = '';
    const format = generatorSelectedFormat();
    if (!format) {
      $('#mcCampaignFormStatus').textContent = 'Escolha o formato do primeiro step.';
      return;
    }
    await withLock('create-campaign', button, async () => {
      const data = Object.fromEntries(new FormData(form));
      const [clientSource, clientId] = String(data.client_ref || '').split(':');
      delete data.client_ref;
      data.client_source = clientSource === 'crm' ? 'crm' : 'creative';
      data.client_id = Number(clientId);
      data.budget_usd = Number(data.budget_usd || 0);
      data.show_price = new FormData(form).has('show_price');
      data.first_step = {
        format_template_id: Number(format.id),
        mockup: $('#mcGeneratorMockup')?.value || clonePlacement(format).context || 'portal',
        scene_description: null,
      };
      try {
        const created = await api(API.campaigns, { method: 'POST', body: JSON.stringify(data) });
        state.campaigns = await api(API.campaigns);
        await selectCampaign(created.id, created.created_step_id);
        form.reset();
        renderClientPreview();
        renderGeneratorSummary();
        toast('Campanha criada com a variação A.', 'success');
        activateTab('variacoes');
      } catch (error) {
        $('#mcCampaignFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  // ====== VARIAÇÕES ======
  async function selectCampaign(id, preferredStepId = null) {
    if (!id) {
      state.campaign = null;
      renderWorkspace();
      return;
    }
    const preserveStep = state.campaign && String(state.campaign.id) === String(id)
      ? state.activeStepId : null;
    const [campaign, assets, publicLinks] = await Promise.all([
      api(`${API.campaigns}/${id}`),
      api(`${API.campaigns}/${id}/assets`),
      api(`${API.campaigns}/${id}/public-collections`),
    ]);
    state.campaign = campaign;
    state.campaignAssets = assets;
    state.publicLinks = publicLinks;
    state.activeStepId = preferredStepId || preserveStep;
    state.selectedAssets.clear();
    renderCampaignOptions();
    renderWorkspace();
  }

  function renderBudget() {
    const c = state.campaign || {};
    const values = [
      ['Orçamento', c.budget_usd], ['Reservado', c.reserved_usd],
      ['Consumido', c.spent_usd], ['Saldo', c.balance_usd],
    ];
    $('#mcBudgetStrip').innerHTML = values.map(([label, value], index) => (
      `<span class="${index === 3 ? 'is-balance' : ''}"><small>${label}</small><strong>${money(value)}</strong></span>`
    )).join('');
    $('#mcGlobalContext').innerHTML = state.campaign
      ? `<span class="cx-badge cx-badge-info">${escapeHtml(c.name)}</span><span class="cx-badge cx-badge-success">Saldo ${money(c.balance_usd)}</span>`
      : '<span class="cx-badge cx-badge-muted">Nenhuma campanha selecionada</span>';
  }

  function renderWorkspace() {
    const hasCampaign = Boolean(state.campaign);
    $('#mcVariationEmpty').classList.toggle('hidden', hasCampaign);
    $('#mcVariationWorkspace').classList.toggle('hidden', !hasCampaign);
    renderBudget();
    if (!hasCampaign) return;
    const c = state.campaign;
    $('#mcCampaignBrief').innerHTML = `
      <strong>${escapeHtml(c.client.name)}</strong>
      <span>${escapeHtml(c.objective || 'Sem objetivo')}</span>
      <span>${escapeHtml(c.campaign_text || 'Sem mensagem principal')}</span>`;
    renderFormatBrowser();
    renderVariations();
    renderSideBySide();
    renderAssetPlan();
    const active = findStep(state.activeStepId);
    if (active) renderStepInspector(active.step, active.variation);
  }

  function formatOptions(selected) {
    return '<option value="">Escolha o formato</option>' + state.formats.map((format) => (
      `<option value="${format.id}" ${String(format.id) === String(selected) ? 'selected' : ''}>${escapeHtml(format.name_pt)}</option>`
    )).join('');
  }

  function mockupOptions(selected = 'portal') {
    return Object.entries(MOCKUPS).map(([value, item]) => (
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${item.label}</option>`
    )).join('');
  }

  function ensureDraftSteps(variation) {
    return variation.steps.length ? variation.steps : [{
      id: '', format_template_id: '', mockup: 'portal', scene_description: '',
    }];
  }

  function renderVariations() {
    $('#mcAddVariation').disabled = state.campaign.variations.length >= 4;
    $('#mcVariationList').innerHTML = state.campaign.variations.map((variation) => {
      const steps = ensureDraftSteps(variation);
      return `
        <article class="mc-variation-card" data-variation-id="${variation.id}">
          <header class="mc-variation-head">
            <span class="mc-variation-label">${escapeHtml(variation.label)}</span>
            <input class="cx-input mc-notes" value="${escapeHtml(variation.notes || '')}" placeholder="Hipótese desta variação">
            <button class="mc-icon-btn" type="button" data-action="delete-variation" title="Remover variação" ${state.campaign.variations.length <= 1 ? 'disabled' : ''}><i class="fa-solid fa-trash"></i></button>
          </header>
          <div class="mc-step-list">
            ${steps.map((step, index) => renderStepRow(step, index, steps.length)).join('')}
          </div>
          <footer class="mc-form-footer">
            <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="add-step"><i class="fa-solid fa-plus"></i> Adicionar step</button>
            <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="save-variation">Salvar sequência</button>
          </footer>
        </article>`;
    }).join('');
  }

  function renderStepRow(step, index, total) {
    const format = state.formats.find((item) => String(item.id) === String(step.format_template_id));
    const engine = format ? engineBadge(format) : '<span class="cx-badge cx-badge-muted">Engine</span>';
    return `
      <div class="mc-step ${String(step.id) === String(state.activeStepId) ? 'is-active' : ''}" data-step-id="${step.id || ''}">
        <button class="mc-step-position mc-icon-btn" type="button" data-action="inspect-step" title="Abrir step">${index + 1}</button>
        <select class="cx-select mc-step-format">${formatOptions(step.format_template_id)}</select>
        <select class="cx-select mc-step-mockup">${mockupOptions(step.mockup)}</select>
        <div class="mc-step-actions">
          ${engine}
          <button class="mc-icon-btn" type="button" data-action="move-up" title="Mover acima" ${index === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-up"></i></button>
          <button class="mc-icon-btn" type="button" data-action="move-down" title="Mover abaixo" ${index === total - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-down"></i></button>
          <button class="mc-icon-btn" type="button" data-action="remove-step" title="Remover"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <input class="cx-input mc-step-scene" value="${escapeHtml(step.scene_description || '')}" placeholder="Cena específica (opcional)" style="grid-column:2/-1">
      </div>`;
  }

  function engineBadge(format) {
    return format.media_type === 'image'
      ? '<span class="cx-badge cx-badge-success">GPT Image 2</span>'
      : '<span class="cx-badge cx-badge-warning">Higgsfield</span>';
  }

  function collectVariation(card) {
    return {
      notes: $('.mc-notes', card).value.trim(),
      steps: $$('.mc-step', card).map((row) => ({
        id: row.dataset.stepId ? Number(row.dataset.stepId) : undefined,
        format_template_id: Number($('.mc-step-format', row).value),
        mockup: $('.mc-step-mockup', row).value,
        scene_description: $('.mc-step-scene', row).value.trim() || null,
      })).filter((step) => step.format_template_id),
    };
  }

  async function saveVariation(card, button, silent = false) {
    const id = card.dataset.variationId;
    return withLock(`variation-${id}`, button, async () => {
      const result = await api(`/parametros/api/variations/${id}`, {
        method: 'PUT', body: JSON.stringify(collectVariation(card)),
      });
      if (!silent) toast('Sequência salva.', 'success');
      return result;
    });
  }

  async function addVariation(button) {
    await withLock('add-variation', button, async () => {
      try {
        await api(`${API.campaigns}/${state.campaign.id}/variations`, {
          method: 'POST', body: '{}',
        });
        await selectCampaign(state.campaign.id);
        toast('Nova variação adicionada.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    });
  }

  function findStep(id) {
    if (!state.campaign || !id) return null;
    for (const variation of state.campaign.variations) {
      const step = variation.steps.find((item) => String(item.id) === String(id));
      if (step) return { step, variation };
    }
    return null;
  }

  function renderSideBySide() {
    const root = $('#mcSideBySide');
    if (!state.campaign.variations.length) {
      root.innerHTML = '<div class="cx-empty-state"><p>Adicione steps para comparar as sequências.</p></div>';
      return;
    }
    root.innerHTML = state.campaign.variations.map((variation) => `
      <article class="mc-compare-column">
        <header>Variação ${escapeHtml(variation.label)} <span class="cx-badge cx-badge-muted">${variation.steps.length} steps</span></header>
        ${variation.steps.length ? variation.steps.map((step) => `
          <button class="mc-compare-step" type="button" data-action="inspect-persisted-step" data-step-id="${step.id}">
            <strong>${step.position}. ${escapeHtml(step.format_name)}</strong>
            <span>${escapeHtml(MOCKUPS[step.mockup]?.label || step.mockup)}</span>
            <span>${engineBadge({ media_type: step.media_type })} <span class="cx-badge cx-badge-muted">${escapeHtml(step.asset_status)}</span></span>
          </button>`).join('') : '<div class="mc-compare-step">Sequência vazia</div>'}
      </article>`).join('');
  }

  // ====== PLANO DE CRIATIVOS ======
  function renderAssetPlan() {
    const strip = $('#mcAssetStrip');
    if (!strip || !state.campaign) return;
    $('#mcDownloadAssets').href = `${API.campaigns}/${state.campaign.id}/assets/download`;
    strip.innerHTML = state.campaignAssets.map((asset, index) => `
      <article class="mc-plan-asset" data-plan-asset-id="${asset.id}">
        <div class="mc-plan-preview">
          ${asset.asset_type === 'video'
            ? `<video src="${escapeHtml(asset.asset_url)}" controls preload="metadata"></video>`
            : `<img src="${escapeHtml(asset.asset_url)}" alt="${escapeHtml(asset.title || asset.format_name || 'Criativo')}">`}
          <span class="mc-plan-index">${index + 1}</span>
        </div>
        <div class="mc-plan-content">
          <input class="cx-input mc-asset-title" value="${escapeHtml(asset.title || asset.format_name || '')}" maxlength="200" aria-label="Título do criativo">
          <span class="mc-format-meta">${escapeHtml(asset.variation_label ? `Variação ${asset.variation_label}` : '')}<span>${escapeHtml(asset.default_size || asset.aspect_ratio || '')}</span>${statusBadge(asset.status)}</span>
          <div class="mc-inspector-actions">
            <button class="mc-icon-btn" type="button" data-action="asset-left" title="Mover à esquerda" ${index === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-left"></i></button>
            <button class="mc-icon-btn" type="button" data-action="asset-right" title="Mover à direita" ${index === state.campaignAssets.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-right"></i></button>
            ${asset.status === 'approved' && ['image', 'mockup'].includes(asset.asset_type)
              ? '<button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-action="prepare-display-motion"><i class="fa-solid fa-film"></i> Animar 3s</button>'
              : ''}
            <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="save-asset-meta">Salvar</button>
            <button class="mc-icon-btn" type="button" data-action="delete-plan-asset" title="Excluir criativo"><i class="fa-solid fa-trash"></i></button>
          </div>
        </div>
      </article>`).join('') || '<div class="cx-empty-state"><p>Gere imagens para montar o plano de criativos.</p></div>';
    renderPublicLinks();
  }

  function renderPublicLinks() {
    const root = $('#mcPublicLinks');
    root.innerHTML = state.publicLinks.length ? `
      <h3>Links publicados</h3>
      ${state.publicLinks.map((link) => `
        <div class="mc-public-link ${link.is_active ? '' : 'is-revoked'}">
          <span><strong>${escapeHtml(link.title)}</strong><small>${link.asset_count} criativos · ${link.is_active ? 'Ativo' : 'Revogado'}</small></span>
          <code>${escapeHtml(link.public_url)}</code>
          <div class="mc-inspector-actions">
            ${link.is_active ? `<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="copy-public-link" data-public-url="${escapeHtml(link.public_url)}">Copiar</button><button class="cx-btn cx-btn-danger cx-btn-sm" type="button" data-action="revoke-public-link" data-link-id="${link.id}">Revogar</button>` : ''}
          </div>
        </div>`).join('')}` : '';
  }

  function renderShareEnvironments() {
    const root = $('#mcShareEnvironmentList');
    if (!root) return;
    root.innerHTML = state.campaignAssets.map((asset) => {
      const context = asset.placement_spec?.context || 'portal';
      const profiles = viewerProfilesFor(context);
      const automatic = state.viewerProfiles.find((profile) => (
        String(profile.id) === String(asset.default_viewer_profile_id)
      ));
      return `
        <label class="mc-share-environment">
          <span><strong>${escapeHtml(asset.title || asset.format_name || `Criativo ${asset.id}`)}</strong><small>${escapeHtml(asset.default_size || context)}</small></span>
          <select class="cx-select" data-share-asset="${asset.id}">
            <option value="auto">Automático${automatic ? ` · ${escapeHtml(automatic.name)}` : ''}</option>
            ${profiles.map((profile) => `<option value="${profile.id}">${escapeHtml(profile.name)}</option>`).join('')}
          </select>
        </label>`;
    }).join('');
  }

  async function persistAssetOrder() {
    await api(`${API.campaigns}/${state.campaign.id}/assets/reorder`, {
      method: 'PUT',
      body: JSON.stringify({ asset_ids: state.campaignAssets.map((asset) => asset.id) }),
    });
  }

  // ====== FORMATOS E INSPETOR ======
  function filteredFormats(searchSelector, categorySelector) {
    const term = ($(searchSelector)?.value || '').trim().toLowerCase();
    const category = $(categorySelector)?.value || '';
    return state.formats.filter((format) => {
      const haystack = `${format.name_pt} ${format.mechanic} ${format.default_size}`.toLowerCase();
      return (!term || haystack.includes(term)) && (!category || format.category === category);
    });
  }

  function renderFormatBrowser() {
    const root = $('#mcFormatList');
    if (!root) return;
    root.innerHTML = filteredFormats('#mcFormatSearch', '#mcFormatCategory').map((format) => `
      <button class="mc-format-item ${String(format.id) === String(state.selectedFormatId) ? 'is-active' : ''}" type="button" data-format-id="${format.id}">
        <strong>${escapeHtml(format.name_pt)}</strong>
        <span class="mc-format-meta"><span>${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')}</span><span>${escapeHtml(format.mechanic || '')}</span></span>
        <span>${engineBadge(format)}</span>
      </button>`).join('') || '<div class="cx-empty-state"><p>Nenhum formato corresponde aos filtros.</p></div>';
  }

  function renderFormatInspector(format) {
    state.selectedFormatId = format.id;
    renderFormatBrowser();
    const refs = format.references || [];
    $('#mcInspectorBody').innerHTML = `
      <div class="mc-inspector-section">
        <strong>${escapeHtml(format.name_pt)}</strong>
        <div class="mc-format-meta">${engineBadge(format)} <span class="cx-badge">${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')}</span></div>
        <p>${escapeHtml(format.background_guidance || 'Background definido pelas camadas do formato.')}</p>
        <p>${escapeHtml(format.foreground_guidance || '')}</p>
      </div>
      <div class="mc-inspector-section">
        <strong>Regras</strong>
        <p>${escapeHtml(format.responsive_rules || 'Preservar área segura, marca e chamada para ação.')}</p>
        <span class="mc-section-note">${(format.layers || []).length} camadas modeladas</span>
      </div>
      <div class="mc-inspector-section">
        <strong>Referências aprovadas (${refs.length}/4)</strong>
        <div class="mc-reference-grid">${[1, 2, 3, 4].map((slot) => {
          const ref = refs.find((item) => Number(item.slot) === slot);
          return `<div class="mc-reference-slot">${ref ? `<img src="${escapeHtml(ref.asset_url)}" alt="Referência ${slot}">` : `<span>${slot}</span>`}</div>`;
        }).join('')}</div>
      </div>`;
  }

  function renderStepInspector(step, variation) {
    state.activeStepId = step.id;
    const format = state.formats.find((item) => Number(item.id) === Number(step.format_template_id)) || {};
    const assets = step.assets || [];
    $('#mcInspectorBody').innerHTML = `
      <div class="mc-inspector-section">
        <strong>Variação ${escapeHtml(variation.label)} · Step ${step.position}</strong>
        <div class="mc-format-meta">${engineBadge(format)} <span class="cx-badge">${escapeHtml(format.default_size || '')}</span><span class="cx-badge">${escapeHtml(MOCKUPS[step.mockup]?.label || step.mockup)}</span></div>
      </div>
      <div class="mc-inspector-section">
        <strong>Prompt <span class="cx-badge cx-badge-muted">${escapeHtml(step.prompt_status || 'draft')}</span></strong>
        <textarea class="cx-textarea" id="mcPromptEditor" placeholder="Gere ou escreva o prompt">${escapeHtml(step.rendered_prompt || '')}</textarea>
        <div class="mc-inspector-actions">
          <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="generate-ai-prompt">Gerar com GPT</button>
          <button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-action="save-prompt">Salvar revisão</button>
          <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="approve-prompt">Aprovar prompt</button>
        </div>
      </div>
      <div class="mc-inspector-section">
        <strong>Referências de entrada</strong>
        <input class="cx-input" id="mcImageReferences" type="file" accept=".png,.jpg,.jpeg,.webp" multiple>
        <span class="cx-help">Até duas imagens por geração.</span>
        <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="generate-image" ${step.prompt_status !== 'approved' ? 'disabled title="Aprove o prompt primeiro"' : ''}>Gerar imagem</button>
      </div>
      <div class="mc-inspector-section">
        <strong>Assets (${assets.length})</strong>
        <div class="mc-asset-grid">${assets.map((asset) => `
          <div class="mc-asset ${state.selectedAssets.has(asset.id) ? 'is-selected' : ''}" data-asset-id="${asset.id}">
            <img src="${escapeHtml(asset.asset_url)}" alt="Asset gerado">
            <button type="button" data-action="toggle-asset" aria-label="Selecionar asset"></button>
          </div>`).join('') || '<span class="mc-section-note">Nenhuma imagem gerada.</span>'}</div>
        <div class="mc-inspector-actions">
          ${assets.filter((asset) => asset.status === 'done').map((asset) => `<button class="cx-btn cx-btn-secondary cx-btn-sm" data-action="approve-asset" data-asset-id="${asset.id}" type="button">Aprovar #${asset.id}</button>`).join('')}
          ${assets.filter((asset) => asset.status === 'approved').map((asset) => `<button class="cx-btn cx-btn-outline cx-btn-sm" data-action="promote-asset" data-asset-id="${asset.id}" data-format-id="${format.id}" type="button">Usar como referência</button>`).join('')}
        </div>
      </div>
      ${format.media_type === 'video' ? renderVideoControls(step) : ''}`;
    renderVariations();
  }

  function renderVideoControls(step) {
    return `
      <div class="mc-inspector-section">
        <strong>Vídeo <span class="cx-badge cx-badge-info">${state.selectedAssets.size}/4 imagens</span></strong>
        <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="generate-script" ${state.selectedAssets.size !== 4 ? 'disabled' : ''}>Gerar roteiro</button>
        <textarea class="cx-textarea" id="mcScriptEditor" placeholder="Roteiro com quatro cenas">${escapeHtml(step.script_text || '')}</textarea>
        <div class="mc-inspector-actions">
          <button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-action="save-script">Salvar roteiro</button>
          <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="approve-script">Aprovar roteiro</button>
        </div>
        <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="prepare-higgsfield" ${step.script_status !== 'approved' || state.selectedAssets.size !== 4 ? 'disabled' : ''}>Preparar Higgsfield</button>
      </div>`;
  }

  // ====== BIBLIOTECA ======
  function renderLibrary() {
    const root = $('#mcFormatTableBody');
    if (!root) return;
    const formats = filteredFormats('#mcLibrarySearch', '#mcLibraryCategory');
    root.innerHTML = formats.map((format) => `
      <button class="mc-catalog-format ${String(format.id) === String(state.selectedFormatId) ? 'is-active' : ''}"
              type="button" data-library-format="${format.id}">
        <span class="mc-catalog-format-icon"><i class="fa-solid ${format.media_type === 'video' ? 'fa-circle-play' : 'fa-image'}" aria-hidden="true"></i></span>
        <span>
          <strong>${escapeHtml(format.name_pt)}</strong>
          <small>${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')} · ${escapeHtml(format.mechanic || 'Estático')}</small>
        </span>
        <em>${(format.references || []).length}/4</em>
      </button>`).join('') || '<div class="cx-empty-state"><p>Nenhum formato encontrado.</p></div>';
  }

  function clonePlacement(format) {
    const fallback = {
      context: format.channel && ['netflix', 'hbomax', 'disneyplus'].includes(format.channel) ? 'tv' : 'portal',
      viewport: { width: 1280, height: 800 },
      slot: { x: 65, y: 20, width: 28, height: 38 },
      fit: 'contain',
      responsive: 'scale',
    };
    return JSON.parse(JSON.stringify(Object.keys(format.placement_spec || {}).length ? format.placement_spec : fallback));
  }

  function viewerProfilesFor(context) {
    const kind = context === 'tv' ? 'tv' : 'portal';
    return state.viewerProfiles.filter((profile) => profile.viewer_kind === kind);
  }

  function activeViewerProfile(format, placement) {
    const compatible = viewerProfilesFor(placement.context);
    let profile = compatible.find((item) => (
      String(item.id) === String(state.selectedViewerProfileId)
    ));
    if (!profile) {
      profile = compatible.find((item) => (
        String(item.id) === String(format.default_viewer_profile_id)
      )) || compatible[0] || null;
    }
    state.selectedViewerProfileId = profile?.id || null;
    return profile;
  }

  function safeViewerColor(value, fallback) {
    return /^#[0-9a-f]{6}$/i.test(String(value || '')) ? value : fallback;
  }

  function viewerLogo(profile) {
    return profile?.logo_asset_ref
      ? `<img src="${escapeHtml(profile.logo_asset_ref)}" alt="">`
      : `<strong>${escapeHtml(profile?.name || 'Mídia')}</strong>`;
  }

  function renderViewerShell(profile) {
    const shell = $('#mcViewerShell');
    const frame = $('#mcDeviceFrame');
    if (!shell || !frame) return;
    if (!profile) {
      shell.innerHTML = '<div class="mc-viewer-missing">Cadastre um ambiente compatível.</div>';
      return;
    }
    const palette = profile.palette || {};
    frame.dataset.viewer = profile.slug;
    frame.style.setProperty('--viewer-primary', safeViewerColor(palette.primary, '#1e4d4f'));
    frame.style.setProperty('--viewer-secondary', safeViewerColor(palette.secondary, '#173436'));
    frame.style.setProperty('--viewer-surface', safeViewerColor(palette.surface, '#ffffff'));
    frame.style.setProperty('--viewer-canvas', safeViewerColor(palette.canvas, '#edf2f1'));
    frame.style.setProperty('--viewer-text', safeViewerColor(palette.text, '#1f2937'));
    const nav = Array.isArray(profile.shell_spec?.nav) ? profile.shell_spec.nav.slice(0, 5) : [];
    const navHtml = nav.map((item) => `<span>${escapeHtml(item)}</span>`).join('');
    if (profile.viewer_kind === 'tv') {
      shell.innerHTML = `
        <div class="mc-tv-backdrop"></div>
        <header class="mc-tv-nav">${viewerLogo(profile)}<nav>${navHtml}</nav><i class="fa-regular fa-user"></i></header>
        <section class="mc-tv-hero">
          <span>Conteúdo em destaque</span>
          <strong>Uma história para continuar assistindo</strong>
          <small>Prévia ilustrativa do ambiente de streaming.</small>
        </section>
        <div class="mc-tv-rail" aria-hidden="true"><b></b><b></b><b></b><b></b><b></b></div>
        <div class="mc-tv-controls"><i class="fa-solid fa-play"></i><span></span><i class="fa-solid fa-volume-high"></i></div>`;
    } else {
      shell.innerHTML = `
        <div class="mc-portal-network"><span>notícias</span><span>ao vivo</span><span>conta</span></div>
        <header class="mc-portal-masthead"><i class="fa-solid fa-bars"></i>${viewerLogo(profile)}<i class="fa-solid fa-magnifying-glass"></i></header>
        <nav class="mc-portal-nav">${navHtml}</nav>
        <div class="mc-portal-ticker"><b>Agora</b><span>Informação atualizada em um ambiente editorial simulado</span></div>
        <section class="mc-portal-grid" aria-hidden="true">
          <div class="mc-portal-lead"><small>Conteúdo editorial</small><strong>Manchete demonstrativa para contextualizar o inventário</strong><span></span></div>
          <div class="mc-portal-stack"><b></b><span></span><b></b><span></span></div>
          <aside><strong>Mais lidas</strong><span></span><span></span><span></span></aside>
        </section>`;
    }
    $('#mcViewerDisclaimer').textContent = profile.disclaimer
      || 'Simulação de ambiente · sem afiliação com o veículo';
  }

  function renderViewerToolbar(format, placement, profile) {
    const root = $('#mcViewerToolbar');
    if (!root) return;
    const profiles = viewerProfilesFor(placement.context);
    root.innerHTML = `
      <span>Visualizar em</span>
      <div>${profiles.map((item) => `
        <button type="button" data-viewer-profile="${item.id}"
                class="${profile && String(item.id) === String(profile.id) ? 'is-active' : ''}"
                aria-pressed="${profile && String(item.id) === String(profile.id)}">
          ${viewerLogo(item)}<span>${escapeHtml(item.name)}</span>
        </button>`).join('')}</div>`;
  }

  function adCreativeHtml(format) {
    const reference = (format.references || [])[0];
    const visual = reference
      ? `<img class="mc-ad-reference" src="${escapeHtml(reference.asset_url)}" alt="">`
      : '';
    return `${visual}<span class="mc-ad-demo-layer">${behaviorDemo(format.behavior_spec)}</span><small id="mcAdSlotSize"></small>`;
  }

  function behaviorDemo(spec = {}) {
    const type = spec.type || 'static';
    if (type === 'hotspot') return '<span class="mc-demo-hotspot">+</span><span class="mc-demo-copy">Descubra detalhes</span>';
    if (type === 'flip') return '<span class="mc-demo-card"><b>Frente</b><i>Verso</i></span>';
    if (type === 'quiz') return '<span class="mc-demo-question">Qual opção combina com você?</span><span class="mc-demo-options"><b>A</b><b>B</b></span>';
    if (type === 'compare') return '<span class="mc-demo-compare"><i></i></span>';
    if (type === 'reveal') return '<span class="mc-demo-reveal"><i></i></span>';
    if (type === 'video') return '<span class="mc-demo-play"><i class="fa-solid fa-play"></i></span>';
    return '<span class="mc-demo-static">Criativo<br>da marca</span>';
  }

  function renderFormatStage(format, preserveDraft = false) {
    if (!format) return;
    if (!preserveDraft || !state.placementDraft) {
      state.placementDraft = clonePlacement(format);
      state.originalPlacement = clonePlacement(format);
    }
    const placement = state.placementDraft;
    const slot = placement.slot;
    $('#mcStageEmpty').classList.add('hidden');
    $('#mcFormatStage').classList.remove('hidden');
    $('#mcStageTitle').textContent = format.name_pt;
    $('#mcStageMetrics').innerHTML = `<span>${escapeHtml(placement.context)}</span><strong>${escapeHtml(format.default_size || format.aspect_ratio || '')}</strong>`;
    $('#mcDeviceFrame').className = `mc-device-frame is-${escapeHtml(placement.context)}`;
    $('#mcDeviceFrame').style.aspectRatio = `${Number(placement.viewport.width) || 1280} / ${Number(placement.viewport.height) || 800}`;
    const profile = activeViewerProfile(format, placement);
    renderViewerToolbar(format, placement, profile);
    renderViewerShell(profile);
    $('#mcAdSlot').style.left = `${slot.x}%`;
    $('#mcAdSlot').style.top = `${slot.y}%`;
    $('#mcAdSlot').style.width = `${slot.width}%`;
    $('#mcAdSlot').style.height = `${slot.height}%`;
    $('#mcAdSlotContent').innerHTML = adCreativeHtml(format);
    $('#mcAdSlotSize').textContent = `${Math.round(slot.width)}% × ${Math.round(slot.height)}%`;
    $('#mcResetPlacement').disabled = false;
    syncPlacementFields();
  }

  function syncPlacementFields() {
    const form = $('#mcFormatModelForm');
    if (!form || !state.placementDraft) return;
    const placement = state.placementDraft;
    ['x', 'y', 'width', 'height'].forEach((key) => {
      if (form.elements[`slot_${key}`]) form.elements[`slot_${key}`].value = placement.slot[key];
    });
    if (form.elements.context) form.elements.context.value = placement.context;
    if (form.elements.viewport_width) form.elements.viewport_width.value = placement.viewport.width;
    if (form.elements.viewport_height) form.elements.viewport_height.value = placement.viewport.height;
    if (form.elements.default_viewer_profile_id && state.selectedViewerProfileId) {
      form.elements.default_viewer_profile_id.value = state.selectedViewerProfileId;
    }
  }

  function formatJobCard(job) {
    const cost = job.actual_cost_usd ?? job.estimated_cost_usd;
    return `
      <article class="mc-model-job" data-model-job="${job.id}">
        <div class="mc-model-job-preview">
          ${job.asset_url ? `<img src="${escapeHtml(job.asset_url)}" alt="Mockup gerado para revisão">` : '<i class="fa-solid fa-circle-notch fa-spin"></i>'}
          <span>${statusBadge(job.status)}</span>
        </div>
        <div class="mc-model-job-body">
          <span><strong>Slot ${job.slot}</strong><small>${escapeHtml(job.reference_type === 'background' ? 'Ambiente' : 'Mockup completo')} · ${money(cost)}</small></span>
          ${job.error_message ? `<p class="mc-job-error">${escapeHtml(job.error_message)}</p>` : ''}
          ${job.asset_url && job.status !== 'approved' ? `
            <label>Refinar esta versão
              <textarea class="cx-textarea mc-refine-instruction" rows="2" placeholder="Ex.: preserve o layout e aumente o contraste da peça"></textarea>
            </label>
            <div class="mc-inspector-actions">
              <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="refine-format-mockup">Refinar</button>
              <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="approve-format-mockup">Aprovar no slot ${job.slot}</button>
              <button class="mc-icon-btn" type="button" data-action="archive-format-mockup" title="Arquivar versão"><i class="fa-solid fa-box-archive"></i></button>
            </div>` : ''}
        </div>
      </article>`;
  }

  function renderLibraryDetail(format) {
    const refs = format.references || [];
    $('#mcLibraryDetail').innerHTML = `
      <div class="mc-studio-detail-head">
        <div><strong>${escapeHtml(format.name_pt)}</strong><small>${escapeHtml(format.channel_name || format.category || '')}</small></div>
        ${engineBadge(format)}
      </div>
      <div class="mc-detail-tabs" role="tablist">
        <button class="is-active" type="button" data-studio-detail-tab="technical">Layout</button>
        <button type="button" data-studio-detail-tab="visual">Image 2</button>
      </div>
      <form class="mc-studio-detail-pane" id="mcFormatModelForm" data-studio-detail-pane="technical" data-format-id="${format.id}">
        <div class="mc-field-pair">
          <label class="cx-field"><span class="cx-label">Contexto</span><select class="cx-select" name="context">
            ${Object.entries(MOCKUPS).map(([value, item]) => `<option value="${value}">${item.label}</option>`).join('')}
          </select></label>
          <label class="cx-field"><span class="cx-label">Ajuste</span><select class="cx-select" name="fit">
            <option value="contain">Conter</option><option value="cover">Cobrir</option><option value="fill">Preencher</option>
          </select></label>
        </div>
        <label class="cx-field"><span class="cx-label">Ambiente padrão</span>
          <select class="cx-select" name="default_viewer_profile_id">
            ${state.viewerProfiles.map((profile) => `<option value="${profile.id}" data-viewer-kind="${profile.viewer_kind}">${escapeHtml(profile.name)} · ${profile.viewer_kind === 'tv' ? 'TV' : 'Portal'}</option>`).join('')}
          </select>
        </label>
        <div class="mc-field-pair">
          <label class="cx-field"><span class="cx-label">Viewport L</span><input class="cx-input" name="viewport_width" type="number" min="240" max="7680"></label>
          <label class="cx-field"><span class="cx-label">Viewport A</span><input class="cx-input" name="viewport_height" type="number" min="240" max="4320"></label>
        </div>
        <div class="mc-placement-fields">
          ${['x', 'y', 'width', 'height'].map((key) => `<label><span>${key === 'x' ? 'X' : key === 'y' ? 'Y' : key === 'width' ? 'Largura' : 'Altura'} %</span><input class="cx-input" name="slot_${key}" type="number" min="${['width', 'height'].includes(key) ? 1 : 0}" max="100" step="0.5"></label>`).join('')}
        </div>
        <div class="mc-field-pair">
          <label class="cx-field"><span class="cx-label">Mecânica</span><select class="cx-select" name="behavior_type">
            ${['static', 'hotspot', 'flip', 'reveal', 'compare', 'quiz', 'video'].map((value) => `<option value="${value}">${value}</option>`).join('')}
          </select></label>
          <label class="cx-field"><span class="cx-label">Acionamento</span><select class="cx-select" name="behavior_trigger">
            ${['none', 'hover_tap', 'click', 'drag_vertical', 'drag_horizontal', 'view'].map((value) => `<option value="${value}">${value}</option>`).join('')}
          </select></label>
        </div>
        <label class="cx-field"><span class="cx-label">Background/base</span><textarea class="cx-textarea" name="background_guidance">${escapeHtml(format.background_guidance || '')}</textarea></label>
        <label class="cx-field"><span class="cx-label">Foreground/conteúdo</span><textarea class="cx-textarea" name="foreground_guidance">${escapeHtml(format.foreground_guidance || '')}</textarea></label>
        <label class="cx-field"><span class="cx-label">Comportamento responsivo</span><textarea class="cx-textarea" name="responsive_rules">${escapeHtml(format.responsive_rules || '')}</textarea></label>
        <button class="cx-btn cx-btn-primary" type="button" data-action="save-format-model">Salvar modelagem técnica</button>
      </form>
      <div class="mc-studio-detail-pane hidden" data-studio-detail-pane="visual">
        <form class="mc-mockup-generator" id="mcMockupGenerator" data-format-id="${format.id}">
          <div class="mc-field-pair">
            <label class="cx-field"><span class="cx-label">Tipo</span><select class="cx-select" name="reference_type">
              <option value="full_mockup">Mockup completo</option><option value="background">Somente ambiente</option>
            </select></label>
            <label class="cx-field"><span class="cx-label">Slot</span><select class="cx-select" name="slot">
              ${[1, 2, 3, 4].map((slot) => `<option value="${slot}">${slot}</option>`).join('')}
            </select></label>
          </div>
          <label class="cx-field"><span class="cx-label">Cliente opcional</span><select class="cx-select" name="client_id">
            <option value="">Marca neutra</option>
            ${state.clients.map((client) => `<option value="${client.id}">${escapeHtml(client.name)}</option>`).join('')}
          </select></label>
          <label class="cx-field"><span class="cx-label">Composição</span><select class="cx-select" name="presentation_mode">
            <option value="single" ${format.media_type !== 'video' && format.behavior_spec?.type === 'static' ? 'selected' : ''}>Um mockup</option>
            <option value="four_horizontal" ${format.media_type === 'video' || format.behavior_spec?.type !== 'static' ? 'selected' : ''}>Quatro estados horizontais</option>
            <option value="multi_format_board">Quatro formatos da mesma campanha</option>
          </select></label>
          <span class="cx-help">O mockup usa o ambiente nativo modelado: portal, CTV/streaming ou mobile. Interativos e vídeos começam com quatro variações; qualquer estático aprovado pode receber animação de 3 segundos.</span>
          <label class="cx-field"><span class="cx-label">Conteúdo e variações</span><textarea class="cx-textarea" name="instructions" rows="5" placeholder="Informe headline, CTA, perguntas, produtos ou os quatro formatos. Marca, dispositivos e direção visual serão preservados."></textarea></label>
          <label class="mc-reference-upload">
            <input name="references" type="file" accept=".png,.jpg,.jpeg,.webp" multiple>
            <i class="fa-solid fa-paperclip" aria-hidden="true"></i>
            <span>Até duas referências visuais</span>
          </label>
          <button class="cx-btn cx-btn-primary" type="button" data-action="generate-format-mockup"><i class="fa-solid fa-wand-magic-sparkles"></i> Gerar com Image 2</button>
        </form>
        <div class="mc-approved-reference-grid">
          ${[1, 2, 3, 4].map((slot) => {
            const ref = refs.find((item) => Number(item.slot) === slot);
            return `<div class="mc-reference-slot">${ref ? `<img src="${escapeHtml(ref.asset_url)}" alt="Referência aprovada ${slot}"><span>Slot ${slot}</span>` : `<span>Slot ${slot}<small>Disponível</small></span>`}</div>`;
          }).join('')}
        </div>
        <div class="mc-model-job-list">
          <h3>Versões recentes</h3>
          ${state.formatJobs.map(formatJobCard).join('') || '<div class="cx-empty-state"><p>Gere o primeiro mockup deste formato.</p></div>'}
        </div>
      </div>`;
    const placement = state.placementDraft || clonePlacement(format);
    const behavior = format.behavior_spec || { type: 'static', trigger: 'none', transition_ms: 0 };
    const form = $('#mcFormatModelForm');
    form.elements.fit.value = placement.fit || 'contain';
    form.elements.default_viewer_profile_id.value = state.selectedViewerProfileId || format.default_viewer_profile_id || '';
    form.elements.behavior_type.value = behavior.type || 'static';
    form.elements.behavior_trigger.value = behavior.trigger || 'none';
    syncPlacementFields();
  }

  // ====== CLIENTES ======
  function renderClients() {
    const root = $('#mcClientTableBody');
    if (!root) return;
    root.innerHTML = state.clients.map((client) => {
      const logo = client.logo_upload_path || client.logo_url;
      return `<tr>
        <td><strong>${escapeHtml(client.name)}</strong><br><span class="mc-section-note">${escapeHtml(client.sector || 'Sem setor')}</span>${client.analysis_metadata?.model ? '<br><span class="cx-badge cx-badge-info">Perfil analisado</span>' : ''}</td>
        <td><span class="mc-swatch" style="display:inline-block;background:${escapeHtml(client.primary_color || '#ffffff')}"></span> <span class="mc-swatch" style="display:inline-block;background:${escapeHtml(client.secondary_color || '#ffffff')}"></span></td>
        <td>${logo ? `<img src="${escapeHtml(logo)}" alt="" style="width:40px;height:32px;object-fit:contain">` : '<span class="cx-badge cx-badge-muted">Sem logo</span>'}</td>
        <td><div class="mc-inspector-actions"><button class="cx-btn cx-btn-secondary cx-btn-sm" data-action="open-logo" data-client-id="${client.id}" type="button">Logo</button><button class="cx-btn cx-btn-danger cx-btn-sm" data-action="delete-client" data-client-id="${client.id}" type="button">Remover</button></div></td>
      </tr>`;
    }).join('') || '<tr><td colspan="4">Cadastre o primeiro perfil de marca.</td></tr>';
  }

  function lines(value) {
    return String(value || '').split('\n').map((item) => item.trim()).filter(Boolean);
  }

  function setFormValue(form, name, value) {
    if (value === null || value === undefined) return;
    const field = form.elements[name];
    if (field) field.value = value;
  }

  function renderBrandAnalysisSummary(data) {
    const root = $('#mcBrandAnalysisSummary');
    const confidence = data.confidence || {};
    const percentages = [
      ['Identidade', confidence.identity],
      ['Público', confidence.audience],
      ['Visual', confidence.visual],
    ].filter(([, value]) => Number.isFinite(Number(value)));
    const sources = (data.sources || []).slice(0, 3);
    root.innerHTML = `
      <strong>Leitura concluída.</strong>
      ${percentages.map(([label, value]) => `<span class="cx-badge cx-badge-muted">${escapeHtml(label)} ${Math.round(Number(value) * 100)}%</span>`).join('')}
      ${sources.length ? `<span>Fontes: ${sources.map((url, index) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${index + 1}</a>`).join(', ')}</span>` : ''}
      <span>Revise os campos antes de salvar.</span>`;
    root.classList.remove('hidden');
  }

  async function analyzeBrand(event) {
    const button = event.currentTarget;
    const form = $('#mcClientForm');
    const websiteUrl = form.elements.website_url.value.trim();
    const image = form.elements.brand_image.files[0];
    if (!websiteUrl && !image) {
      toast('Informe o site ou envie uma imagem de referência.', 'warning');
      form.elements.website_url.focus();
      return;
    }
    await withLock('analyze-brand', button, async () => {
      const body = new FormData();
      if (websiteUrl) body.append('website_url', websiteUrl);
      if (image) body.append('image', image);
      $('#mcClientFormStatus').textContent = 'Lendo site, identidade e oportunidades…';
      try {
        const data = await api(API.analyzeBrand, { method: 'POST', body });
        state.brandAnalysis = data;
        [
          'name', 'sector', 'website_url', 'logo_url', 'primary_color',
          'secondary_color', 'tone_of_voice', 'brand_summary',
          'target_audience', 'creative_guidelines',
        ].forEach((name) => setFormValue(form, name, data[name]));
        setFormValue(form, 'ad_segments_text', (data.ad_segments || []).join('\n'));
        setFormValue(
          form,
          'campaign_opportunities_text',
          (data.campaign_opportunities || []).join('\n'),
        );
        renderBrandAnalysisSummary(data);
        $('#mcClientFormStatus').textContent = '';
        toast('Leitura da marca concluída. Revise as sugestões.', 'success');
      } catch (error) {
        $('#mcClientFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  async function createClient(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('button[type="submit"]', form);
    await withLock('create-client', button, async () => {
      const formData = new FormData(form);
      const data = {
        name: formData.get('name'),
        sector: formData.get('sector'),
        website_url: formData.get('website_url'),
        logo_url: formData.get('logo_url'),
        primary_color: formData.get('primary_color'),
        secondary_color: formData.get('secondary_color'),
        tone_of_voice: formData.get('tone_of_voice'),
        brand_summary: formData.get('brand_summary'),
        target_audience: formData.get('target_audience'),
        ad_segments: lines(formData.get('ad_segments_text')),
        creative_guidelines: formData.get('creative_guidelines'),
        campaign_opportunities: lines(formData.get('campaign_opportunities_text')),
        analysis_metadata: state.brandAnalysis?.analysis_metadata || {},
        show_price: formData.has('show_price'),
      };
      try {
        const created = await api(API.clients, { method: 'POST', body: JSON.stringify(data) });
        const image = form.elements.brand_image.files[0];
        if (image && formData.has('use_image_as_logo')) {
          const logoBody = new FormData();
          logoBody.append('logo', image);
          await api(`${API.clients}/${created.id}/logo`, { method: 'POST', body: logoBody });
        }
        state.clients = await api(API.clients);
        state.campaignClients = await api(API.campaignClients);
        renderClients();
        renderClientOptions();
        const campaignClient = $('#mcCampaignClient');
        campaignClient.value = `profile:${created.id}`;
        renderClientPreview();
        renderGeneratorSummary();
        form.reset();
        state.brandAnalysis = null;
        $('#mcBrandAnalysisSummary').classList.add('hidden');
        $('#mcBrandAnalysisSummary').innerHTML = '';
        $('#mcClientFormStatus').textContent = '';
        toast('Perfil de marca salvo.', 'success');
        activateTab('gerador');
      } catch (error) {
        $('#mcClientFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  // ====== HISTÓRICO ======
  async function loadHistory() {
    const root = $('#mcHistoryList');
    root.innerHTML = '<div class="mc-skeleton-list"><span></span><span></span><span></span></div>';
    try {
      const campaignId = $('#mcHistoryCampaign').value;
      const jobs = await api(`${API.history}${campaignId ? `?campaign_id=${campaignId}` : ''}`);
      root.innerHTML = jobs.map((job) => `
        <details class="mc-history-item">
          <summary>
            <span><strong>${escapeHtml(job.campaign_name)}</strong><br><small>${escapeHtml(job.job_type)} · ${escapeHtml(job.model)}</small></span>
            <span>${statusBadge(job.status)} ${money(job.actual_cost_usd ?? job.estimated_cost_usd)}</span>
          </summary>
          <div class="mc-history-body">
            ${job.error_message ? `<div class="cx-alert cx-alert-danger">${escapeHtml(job.error_message)}</div>` : ''}
            ${job.prompt ? `<pre class="mc-prompt-text">${escapeHtml(job.prompt)}</pre>` : ''}
            ${job.script_text ? `<pre class="mc-prompt-text">${escapeHtml(job.script_text)}</pre>` : ''}
          </div>
        </details>`).join('') || '<div class="cx-empty-state"><p>Nenhuma produção registrada.</p></div>';
    } catch (error) {
      root.innerHTML = `<div class="cx-alert cx-alert-danger">${escapeHtml(error.message)}</div>`;
    }
  }

  function statusBadge(status) {
    const kind = status === 'done' || status === 'approved' || status === 'ready_for_higgsfield'
      ? 'success' : status === 'failed' ? 'danger' : status === 'review' ? 'warning' : 'info';
    return `<span class="cx-badge cx-badge-${kind}">${escapeHtml(status)}</span>`;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, Math.round(value * 10) / 10));
  }

  function selectedLibraryFormat() {
    return state.formats.find((item) => String(item.id) === String(state.selectedFormatId));
  }

  function updatePlacementFromForm(form) {
    if (!state.placementDraft) return;
    const slot = state.placementDraft.slot;
    slot.width = clamp(Number(form.elements.slot_width.value), 1, 100 - slot.x);
    slot.height = clamp(Number(form.elements.slot_height.value), 1, 100 - slot.y);
    slot.x = clamp(Number(form.elements.slot_x.value), 0, 100 - slot.width);
    slot.y = clamp(Number(form.elements.slot_y.value), 0, 100 - slot.height);
    state.placementDraft.context = form.elements.context.value;
    state.placementDraft.fit = form.elements.fit.value;
    state.placementDraft.viewport.width = Number(form.elements.viewport_width.value) || 1280;
    state.placementDraft.viewport.height = Number(form.elements.viewport_height.value) || 800;
    const format = selectedLibraryFormat();
    if (format) {
      format.behavior_spec = {
        type: form.elements.behavior_type.value,
        trigger: form.elements.behavior_trigger.value,
        transition_ms: format.behavior_spec?.transition_ms || 220,
      };
      renderFormatStage(format, true);
    }
  }

  function setupPlacementInteraction() {
    const slotNode = $('#mcAdSlot');
    const stageNode = $('#mcDeviceFrame');
    let gesture = null;
    let suppressDemoClick = false;
    slotNode.addEventListener('pointerdown', (event) => {
      if (!state.placementDraft || !selectedLibraryFormat()) return;
      event.preventDefault();
      const resizing = Boolean(event.target.closest('.mc-resize-handle'));
      gesture = {
        pointerId: event.pointerId,
        resizing,
        startX: event.clientX,
        startY: event.clientY,
        moved: false,
        slot: { ...state.placementDraft.slot },
      };
      slotNode.setPointerCapture(event.pointerId);
      slotNode.classList.add(resizing ? 'is-resizing' : 'is-dragging');
    });
    slotNode.addEventListener('pointermove', (event) => {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      const rect = stageNode.getBoundingClientRect();
      const dx = ((event.clientX - gesture.startX) / rect.width) * 100;
      const dy = ((event.clientY - gesture.startY) / rect.height) * 100;
      if (Math.abs(event.clientX - gesture.startX) > 3 || Math.abs(event.clientY - gesture.startY) > 3) {
        gesture.moved = true;
      }
      const next = state.placementDraft.slot;
      if (gesture.resizing) {
        next.width = clamp(gesture.slot.width + dx, 1, 100 - gesture.slot.x);
        next.height = clamp(gesture.slot.height + dy, 1, 100 - gesture.slot.y);
      } else {
        next.x = clamp(gesture.slot.x + dx, 0, 100 - gesture.slot.width);
        next.y = clamp(gesture.slot.y + dy, 0, 100 - gesture.slot.height);
      }
      renderFormatStage(selectedLibraryFormat(), true);
    });
    function finishGesture(event) {
      if (!gesture || gesture.pointerId !== event.pointerId) return;
      suppressDemoClick = gesture.moved;
      slotNode.classList.remove('is-dragging', 'is-resizing');
      gesture = null;
    }
    slotNode.addEventListener('pointerup', finishGesture);
    slotNode.addEventListener('pointercancel', finishGesture);
    slotNode.addEventListener('click', () => {
      if (suppressDemoClick) {
        suppressDemoClick = false;
        return;
      }
      slotNode.classList.toggle('is-demo-active');
    });
    slotNode.addEventListener('keydown', (event) => {
      if (!state.placementDraft || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      event.preventDefault();
      const slot = state.placementDraft.slot;
      const amount = event.shiftKey ? 5 : 0.5;
      if (event.key === 'ArrowLeft') slot.x = clamp(slot.x - amount, 0, 100 - slot.width);
      if (event.key === 'ArrowRight') slot.x = clamp(slot.x + amount, 0, 100 - slot.width);
      if (event.key === 'ArrowUp') slot.y = clamp(slot.y - amount, 0, 100 - slot.height);
      if (event.key === 'ArrowDown') slot.y = clamp(slot.y + amount, 0, 100 - slot.height);
      renderFormatStage(selectedLibraryFormat(), true);
    });
  }

  // ====== ACTIONS ======
  async function refreshCampaign() {
    if (state.campaign) await selectCampaign(state.campaign.id);
  }

  async function inspectorAction(action, button) {
    const found = findStep(state.activeStepId);
    if (!found) return;
    const { step } = found;
    const routes = {
      'generate-ai-prompt': [`/parametros/api/steps/${step.id}/prompt/generate`, 'POST'],
      'generate-image': [`/parametros/api/steps/${step.id}/image/generate`, 'POST'],
      'generate-script': [`/parametros/api/steps/${step.id}/script/generate`, 'POST'],
      'prepare-higgsfield': [`/parametros/api/steps/${step.id}/higgsfield/prepare`, 'POST'],
    };
    try {
      if (action === 'save-prompt' || action === 'approve-prompt') {
        await api(`/parametros/api/steps/${step.id}/prompt`, {
          method: 'PUT',
          body: JSON.stringify({ prompt: $('#mcPromptEditor').value, approved: action === 'approve-prompt' }),
        });
        toast(action === 'approve-prompt' ? 'Prompt aprovado.' : 'Revisão salva.', 'success');
      } else if (action === 'save-script' || action === 'approve-script') {
        await api(`/parametros/api/steps/${step.id}/script`, {
          method: 'PUT',
          body: JSON.stringify({ script: $('#mcScriptEditor').value, approved: action === 'approve-script' }),
        });
        toast(action === 'approve-script' ? 'Roteiro aprovado.' : 'Roteiro salvo.', 'success');
      } else if (action === 'generate-image') {
        const files = Array.from($('#mcImageReferences').files || []);
        if (files.length > 2) throw new Error('Escolha no máximo duas referências.');
        const form = new FormData();
        files.forEach((file) => form.append('references', file));
        await withLock(`${action}-${step.id}`, button, () => api(routes[action][0], { method: 'POST', body: form }));
        toast('Imagem gerada e adicionada aos assets.', 'success');
      } else if (action === 'generate-script' || action === 'prepare-higgsfield') {
        const result = await withLock(`${action}-${step.id}`, button, () => api(routes[action][0], {
          method: routes[action][1],
          body: JSON.stringify({ asset_ids: Array.from(state.selectedAssets) }),
        }));
        const provider = result?.payload?.provider_configuration;
        toast(
          action === 'generate-script'
            ? 'Roteiro criado para revisão.'
            : provider?.configured
              ? 'Payload Higgsfield preparado com provedor configurado.'
              : 'Payload preparado. Configure a credencial Higgsfield em Parâmetros para executar.',
          action === 'prepare-higgsfield' && !provider?.configured ? 'warning' : 'success',
        );
      } else if (routes[action]) {
        await withLock(`${action}-${step.id}`, button, () => api(routes[action][0], {
          method: routes[action][1], body: '{}',
        }));
        toast('Prompt criado para revisão.', 'success');
      }
      await refreshCampaign();
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function confirmCostAndRun(action, button) {
    const found = findStep(state.activeStepId);
    if (!found) return;
    const estimated = action === 'generate-image' ? 0.15 : action === 'generate-script' ? 0.03 : 0.02;
    if (typeof window.showConfirm === 'function') {
      window.showConfirm({
        title: 'Confirmar consumo de saldo',
        message: `Executar ${action === 'generate-image' ? 'geração de imagem' : action === 'generate-script' ? 'geração de roteiro' : 'geração de prompt'}?`,
        detail: `Estimativa: ${money(estimated)} · Saldo atual: ${money(state.campaign.balance_usd)}`,
        confirmText: 'Gerar',
        onConfirm: () => inspectorAction(action, button),
      });
    } else inspectorAction(action, button);
  }

  async function handleClick(event) {
    const tab = event.target.closest('[data-tab]');
    if (tab) return activateTab(tab.dataset.tab);
    const generatorFormat = event.target.closest('[data-generator-format]');
    if (generatorFormat) {
      state.generatorFormatId = Number(generatorFormat.dataset.generatorFormat);
      renderGeneratorFormats();
      return;
    }
    const formatButton = event.target.closest('[data-format-id]');
    if (formatButton) {
      const format = state.formats.find((item) => String(item.id) === formatButton.dataset.formatId);
      if (format) renderFormatInspector(format);
      return;
    }
    const libraryRow = event.target.closest('[data-library-format]');
    if (libraryRow) {
      const format = state.formats.find((item) => String(item.id) === libraryRow.dataset.libraryFormat);
      if (format) {
        state.selectedFormatId = format.id;
        state.selectedViewerProfileId = null;
        state.placementDraft = clonePlacement(format);
        state.originalPlacement = clonePlacement(format);
        renderLibrary();
        renderFormatStage(format);
        state.formatJobs = [];
        renderLibraryDetail(format);
        try {
          state.formatJobs = await api(`${API.formats}/${format.id}/modeling-jobs`);
          renderLibraryDetail(format);
        } catch (error) { toast(error.message, 'error'); }
      }
      return;
    }
    const viewerButton = event.target.closest('[data-viewer-profile]');
    if (viewerButton) {
      state.selectedViewerProfileId = Number(viewerButton.dataset.viewerProfile);
      const form = $('#mcFormatModelForm');
      if (form?.elements.default_viewer_profile_id) {
        form.elements.default_viewer_profile_id.value = state.selectedViewerProfileId;
      }
      const format = selectedLibraryFormat();
      if (format) renderFormatStage(format, true);
      return;
    }
    const detailTab = event.target.closest('[data-studio-detail-tab]');
    if (detailTab) {
      $$('[data-studio-detail-tab]').forEach((item) => item.classList.toggle('is-active', item === detailTab));
      $$('[data-studio-detail-pane]').forEach((pane) => pane.classList.toggle('hidden', pane.dataset.studioDetailPane !== detailTab.dataset.studioDetailTab));
      return;
    }
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    const card = button.closest('[data-variation-id]');
    const row = button.closest('.mc-step');
    if (action === 'add-step') {
      $('.mc-step-list', card).insertAdjacentHTML('beforeend', renderStepRow({
        id: '', format_template_id: state.selectedFormatId || '', mockup: 'portal', scene_description: '',
      }, $$('.mc-step', card).length, $$('.mc-step', card).length + 1));
    } else if (action === 'remove-step') {
      row.remove();
    } else if (action === 'move-up' && row.previousElementSibling) {
      row.parentNode.insertBefore(row, row.previousElementSibling);
    } else if (action === 'move-down' && row.nextElementSibling) {
      row.parentNode.insertBefore(row.nextElementSibling, row);
    } else if (action === 'save-variation') {
      try { await saveVariation(card, button); await refreshCampaign(); } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'delete-variation') {
      window.showConfirm({
        title: 'Remover variação',
        message: 'A sequência e seus jobs vinculados serão removidos.',
        theme: 'danger',
        confirmText: 'Remover',
        onConfirm: async () => {
          try {
            await api(`/parametros/api/variations/${card.dataset.variationId}`, { method: 'DELETE' });
            await refreshCampaign();
            toast('Variação removida.', 'success');
          } catch (error) { toast(error.message, 'error'); }
        },
      });
    } else if (action === 'inspect-step' || action === 'inspect-persisted-step') {
      const id = button.dataset.stepId || row?.dataset.stepId;
      const found = findStep(id);
      if (found) renderStepInspector(found.step, found.variation);
    } else if (['generate-ai-prompt', 'generate-image', 'generate-script'].includes(action)) {
      confirmCostAndRun(action, button);
    } else if (['save-prompt', 'approve-prompt', 'save-script', 'approve-script', 'prepare-higgsfield'].includes(action)) {
      inspectorAction(action, button);
    } else if (action === 'toggle-asset') {
      const assetId = Number(button.closest('[data-asset-id]').dataset.assetId);
      state.selectedAssets.has(assetId) ? state.selectedAssets.delete(assetId) : state.selectedAssets.add(assetId);
      const found = findStep(state.activeStepId);
      if (found) renderStepInspector(found.step, found.variation);
    } else if (action === 'approve-asset') {
      try {
        await api(`/parametros/api/assets/${button.dataset.assetId}/review`, {
          method: 'PUT', body: JSON.stringify({ status: 'approved' }),
        });
        await refreshCampaign();
        toast('Asset aprovado.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'promote-asset') {
      const format = state.formats.find((item) => Number(item.id) === Number(button.dataset.formatId));
      const occupied = new Set((format?.references || []).map((item) => Number(item.slot)));
      const slot = [1, 2, 3, 4].find((value) => !occupied.has(value)) || 4;
      try {
        await api(`/parametros/api/assets/${button.dataset.assetId}/promote`, {
          method: 'POST',
          body: JSON.stringify({
            format_template_id: Number(button.dataset.formatId),
            slot,
            reference_type: 'full_mockup',
            prompt: $('#mcPromptEditor')?.value || '',
          }),
        });
        state.formats = await api(API.formats);
        await refreshCampaign();
        renderLibrary();
        toast(`Referência salva no slot ${slot}.`, 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'save-format-model') {
      const form = button.closest('#mcFormatModelForm');
      try {
        const data = Object.fromEntries(new FormData(form));
        data.safe_area = state.formats.find((item) => String(item.id) === form.dataset.formatId)?.safe_area || {};
        data.placement_spec = {
          context: data.context,
          viewport: { width: Number(data.viewport_width), height: Number(data.viewport_height) },
          slot: {
            x: Number(data.slot_x), y: Number(data.slot_y),
            width: Number(data.slot_width), height: Number(data.slot_height),
          },
          fit: data.fit,
          responsive: state.placementDraft?.responsive || 'scale',
        };
        data.behavior_spec = {
          type: data.behavior_type,
          trigger: data.behavior_trigger,
          transition_ms: 220,
        };
        await api(`${API.formats}/${form.dataset.formatId}`, {
          method: 'PUT', body: JSON.stringify(data),
        });
        state.formats = await api(API.formats);
        const updated = state.formats.find((item) => String(item.id) === form.dataset.formatId);
        state.placementDraft = clonePlacement(updated);
        state.originalPlacement = clonePlacement(updated);
        renderLibrary();
        renderFormatStage(updated);
        renderLibraryDetail(updated);
        toast('Modelagem do formato atualizada.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'generate-format-mockup') {
      const form = button.closest('#mcMockupGenerator');
      const files = Array.from(form.elements.references.files || []);
      if (files.length > 2) return toast('Escolha no máximo duas referências.', 'error');
      const run = async () => {
        const data = new FormData(form);
        try {
          await withLock(`format-mockup-${form.dataset.formatId}`, button, () => api(
            `${API.formats}/${form.dataset.formatId}/mockups/generate`,
            { method: 'POST', body: data },
          ));
          state.formatJobs = await api(`${API.formats}/${form.dataset.formatId}/modeling-jobs`);
          const format = state.formats.find((item) => String(item.id) === form.dataset.formatId);
          renderLibraryDetail(format);
          $$('[data-studio-detail-tab]')[1]?.click();
          toast('Mockup gerado para revisão.', 'success');
        } catch (error) { toast(error.message, 'error'); }
      };
      if (typeof window.showConfirm === 'function') {
        window.showConfirm({
          title: 'Gerar referência visual',
          message: 'Criar uma nova versão com Image 2?',
          detail: `Estimativa: ${money(0.15)}. O custo ficará registrado no catálogo.`,
          confirmText: 'Gerar mockup',
          onConfirm: run,
        });
      } else await run();
    } else if (action === 'refine-format-mockup') {
      const holder = button.closest('[data-model-job]');
      const instruction = $('.mc-refine-instruction', holder).value.trim();
      if (!instruction) return toast('Descreva o que deve ser refinado.', 'warning');
      const data = new FormData();
      data.append('instruction', instruction);
      try {
        await withLock(`refine-${holder.dataset.modelJob}`, button, () => api(
          `/parametros/api/format-modeling-jobs/${holder.dataset.modelJob}/refine`,
          { method: 'POST', body: data },
        ));
        state.formatJobs = await api(`${API.formats}/${state.selectedFormatId}/modeling-jobs`);
        renderLibraryDetail(state.formats.find((item) => String(item.id) === String(state.selectedFormatId)));
        $$('[data-studio-detail-tab]')[1]?.click();
        toast('Nova versão criada.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'approve-format-mockup') {
      const holder = button.closest('[data-model-job]');
      const job = state.formatJobs.find((item) => String(item.id) === holder.dataset.modelJob);
      try {
        await api(`/parametros/api/format-modeling-jobs/${job.id}/approve`, {
          method: 'PUT', body: JSON.stringify({ slot: job.slot }),
        });
        [state.formats, state.formatJobs] = await Promise.all([
          api(API.formats),
          api(`${API.formats}/${state.selectedFormatId}/modeling-jobs`),
        ]);
        const format = state.formats.find((item) => String(item.id) === String(state.selectedFormatId));
        renderLibrary(); renderLibraryDetail(format);
        $$('[data-studio-detail-tab]')[1]?.click();
        toast(`Referência aprovada no slot ${job.slot}.`, 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'archive-format-mockup') {
      const holder = button.closest('[data-model-job]');
      try {
        await api(`/parametros/api/format-modeling-jobs/${holder.dataset.modelJob}`, { method: 'DELETE' });
        state.formatJobs = await api(`${API.formats}/${state.selectedFormatId}/modeling-jobs`);
        renderLibraryDetail(state.formats.find((item) => String(item.id) === String(state.selectedFormatId)));
        $$('[data-studio-detail-tab]')[1]?.click();
        toast('Versão arquivada.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'asset-left' || action === 'asset-right') {
      const holder = button.closest('[data-plan-asset-id]');
      const assetId = Number(holder.dataset.planAssetId);
      const index = state.campaignAssets.findIndex((asset) => asset.id === assetId);
      const target = action === 'asset-left' ? index - 1 : index + 1;
      if (target < 0 || target >= state.campaignAssets.length) return;
      [state.campaignAssets[index], state.campaignAssets[target]] = [state.campaignAssets[target], state.campaignAssets[index]];
      renderAssetPlan();
      try {
        await persistAssetOrder();
        toast('Ordem atualizada.', 'success');
      } catch (error) {
        toast(error.message, 'error');
        await refreshCampaign();
      }
    } else if (action === 'prepare-display-motion') {
      const holder = button.closest('[data-plan-asset-id]');
      try {
        const result = await withLock(`display-motion-${holder.dataset.planAssetId}`, button, () => api(
          `/parametros/api/assets/${holder.dataset.planAssetId}/display-motion/prepare`,
          { method: 'POST', body: '{}' },
        ));
        await refreshCampaign();
        const provider = result?.payload?.provider_configuration;
        toast(
          provider?.configured
            ? 'Complemento de 3 segundos preparado com Higgsfield configurado.'
            : 'Complemento preparado. Configure o Higgsfield em Parâmetros para executar.',
          provider?.configured ? 'success' : 'warning',
        );
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'save-asset-meta') {
      const holder = button.closest('[data-plan-asset-id]');
      try {
        await api(`${API.campaigns}/${state.campaign.id}/assets/${holder.dataset.planAssetId}`, {
          method: 'PUT',
          body: JSON.stringify({ title: $('.mc-asset-title', holder).value }),
        });
        await refreshCampaign();
        toast('Título atualizado.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    } else if (action === 'delete-plan-asset') {
      const holder = button.closest('[data-plan-asset-id]');
      window.showConfirm({
        title: 'Excluir criativo',
        message: 'O arquivo e sua inclusão em apresentações serão removidos.',
        theme: 'danger',
        confirmText: 'Excluir',
        onConfirm: async () => {
          try {
            await api(`${API.campaigns}/${state.campaign.id}/assets/${holder.dataset.planAssetId}`, { method: 'DELETE' });
            await refreshCampaign();
            toast('Criativo excluído.', 'success');
          } catch (error) { toast(error.message, 'error'); }
        },
      });
    } else if (action === 'copy-public-link') {
      try {
        await navigator.clipboard.writeText(new URL(button.dataset.publicUrl, location.origin).href);
        toast('Link público copiado.', 'success');
      } catch (_) { toast('Não foi possível copiar o link.', 'error'); }
    } else if (action === 'revoke-public-link') {
      window.showConfirm({
        title: 'Revogar link público',
        message: 'Quem recebeu o link deixará de acessar a apresentação.',
        theme: 'danger',
        confirmText: 'Revogar',
        onConfirm: async () => {
          try {
            await api(`${API.campaigns}/${state.campaign.id}/public-collections/${button.dataset.linkId}/revoke`, { method: 'POST', body: '{}' });
            await refreshCampaign();
            toast('Link revogado.', 'success');
          } catch (error) { toast(error.message, 'error'); }
        },
      });
    } else if (action === 'close-share') {
      $('#mcShareDialog').close();
    } else if (action === 'open-logo') {
      $('#mcLogoForm [name="client_id"]').value = button.dataset.clientId;
      $('#mcLogoDialog').showModal();
    } else if (action === 'delete-client') {
      window.showConfirm({
        title: 'Remover perfil de marca', message: 'Perfis vinculados a campanhas não podem ser removidos.',
        theme: 'danger', confirmText: 'Remover',
        onConfirm: async () => {
          try {
            await api(`${API.clients}/${button.dataset.clientId}`, { method: 'DELETE' });
            state.clients = await api(API.clients);
            renderClients(); renderClientOptions();
            toast('Perfil removido.', 'success');
          } catch (error) { toast(error.message, 'error'); }
        },
      });
    }
  }

  // ====== EVENTS ======
  document.addEventListener('DOMContentLoaded', () => {
    $('#mcApp').addEventListener('click', handleClick);
    setupPlacementInteraction();
    $('#mcLibraryDetail').addEventListener('input', (event) => {
      const form = event.target.closest('#mcFormatModelForm');
      if (event.target.matches('[name="default_viewer_profile_id"]')) {
        state.selectedViewerProfileId = Number(event.target.value) || null;
      }
      if (form && (
        event.target.matches('[name^="slot_"]')
        || event.target.matches('[name^="viewport_"]')
        || event.target.matches('[name="context"], [name="fit"], [name="behavior_type"], [name="behavior_trigger"], [name="default_viewer_profile_id"]')
      )) updatePlacementFromForm(form);
    });
    $('#mcResetPlacement').addEventListener('click', () => {
      if (!state.originalPlacement || !selectedLibraryFormat()) return;
      state.placementDraft = JSON.parse(JSON.stringify(state.originalPlacement));
      renderFormatStage(selectedLibraryFormat(), true);
    });
    $('#mcCampaignForm').addEventListener('submit', createCampaign);
    $('#mcClientForm').addEventListener('submit', createClient);
    $('#mcAnalyzeBrand').addEventListener('click', analyzeBrand);
    $('#mcCampaignClient').addEventListener('change', () => {
      renderClientPreview();
      renderGeneratorSummary();
    });
    $('#mcCampaignForm').addEventListener('input', renderGeneratorSummary);
    $('#mcGeneratorFormatCategory').addEventListener('change', renderGeneratorFormats);
    $('#mcGeneratorMockup').addEventListener('change', renderGeneratorSummary);
    $('#mcCampaignSelect').addEventListener('change', (event) => selectCampaign(event.target.value).catch((error) => toast(error.message, 'error')));
    $('#mcAddVariation').addEventListener('click', (event) => addVariation(event.currentTarget));
    $('#mcCreatePublicLink').addEventListener('click', () => {
      if (!state.campaignAssets.length) {
        toast('Adicione ao menos um criativo antes de publicar.', 'warning');
        return;
      }
      $('#mcShareForm [name="title"]').value = state.campaign?.name || '';
      renderShareEnvironments();
      $('#mcShareDialog').showModal();
    });
    $('#mcGenerateAllPrompts').addEventListener('click', (event) => {
      const button = event.currentTarget;
      const total = state.campaign?.variations.reduce((sum, item) => sum + Math.max(item.steps.length, 1), 0) || 0;
      const run = () => withLock('all-prompts', button, async () => {
        try {
          const cards = $$('#mcVariationList [data-variation-id]');
          for (const card of cards) await saveVariation(card, null, true);
          await refreshCampaign();
          const groups = [];
          for (const variation of state.campaign.variations) {
            groups.push({ variation, prompts: await api(`/parametros/api/variations/${variation.id}/generate-prompts`, { method: 'POST', body: '{}' }) });
          }
          $('#mcPromptResults').classList.remove('hidden');
          $('#mcPromptResultBody').innerHTML = groups.flatMap(({ variation, prompts }) => prompts.map((item) => `
            <details class="mc-prompt-card"><summary><strong>Variação ${variation.label} · Step ${item.position}</strong><button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-copy-prompt>Copiar</button></summary><div class="mc-prompt-body"><pre class="mc-prompt-text">${escapeHtml(item.prompt)}</pre></div></details>`)).join('');
          toast('Prompts base gerados.', 'success');
        } catch (error) { toast(error.message, 'error'); }
      });
      window.showConfirm({
        title: 'Gerar prompts com GPT',
        message: `Gerar os prompts de ${total} steps?`,
        detail: `Estimativa total: ${money(total * 0.02)} · Saldo atual: ${money(state.campaign?.balance_usd)}`,
        confirmText: 'Gerar prompts',
        onConfirm: run,
      });
    });
    $('#mcFormatSearch').addEventListener('input', renderFormatBrowser);
    $('#mcFormatCategory').addEventListener('change', renderFormatBrowser);
    $('#mcLibrarySearch').addEventListener('input', renderLibrary);
    $('#mcLibraryCategory').addEventListener('change', renderLibrary);
    $('#mcRefreshHistory').addEventListener('click', loadHistory);
    $('#mcHistoryCampaign').addEventListener('change', loadHistory);
    $('#mcLogoForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const id = form.elements.client_id.value;
      const data = new FormData();
      data.append('logo', form.elements.logo.files[0]);
      try {
        await api(`${API.clients}/${id}/logo`, { method: 'POST', body: data });
        state.clients = await api(API.clients);
        renderClients(); renderClientOptions();
        $('#mcLogoDialog').close();
        form.reset();
        toast('Logo atualizado.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    });
    $('#mcShareForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = $('button[type="submit"]', form);
      await withLock('create-public-link', button, async () => {
        try {
          const payload = Object.fromEntries(new FormData(form));
          payload.asset_ids = state.campaignAssets.map((asset) => asset.id);
          payload.viewer_profiles = {};
          $$('[data-share-asset]', form).forEach((select) => {
            if (select.value !== 'auto') {
              payload.viewer_profiles[select.dataset.shareAsset] = Number(select.value);
            }
          });
          const created = await api(`${API.campaigns}/${state.campaign.id}/public-collections`, {
            method: 'POST',
            body: JSON.stringify(payload),
          });
          $('#mcShareDialog').close();
          form.reset();
          state.publicLinks = await api(`${API.campaigns}/${state.campaign.id}/public-collections`);
          renderPublicLinks();
          await navigator.clipboard.writeText(new URL(created.public_url, location.origin).href).catch(() => {});
          toast('Link público criado e copiado.', 'success');
        } catch (error) { toast(error.message, 'error'); }
      });
    });
    $('#mcPromptResultBody').addEventListener('click', async (event) => {
      const button = event.target.closest('[data-copy-prompt]');
      if (!button) return;
      const text = button.closest('details').querySelector('pre').textContent;
      try { await navigator.clipboard.writeText(text); toast('Prompt copiado.', 'success'); }
      catch (_) { toast('Não foi possível copiar automaticamente.', 'error'); }
    });
    const initialTab = location.hash.replace('#', '');
    activateTab(['gerador', 'variacoes', 'biblioteca', 'clientes', 'historico'].includes(initialTab) ? initialTab : 'gerador', false);
    loadBaseData();
  });
})();
