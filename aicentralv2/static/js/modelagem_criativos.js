(() => {
  'use strict';

  // ====== CONSTANTS ======
  const API = {
    formats: '/parametros/api/formats',
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/campaigns',
    history: '/parametros/api/history',
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
    campaigns: [],
    campaign: null,
    activeStepId: null,
    selectedFormatId: null,
    selectedAssets: new Set(),
    campaignAssets: [],
    publicLinks: [],
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
    try {
      [state.formats, state.clients, state.campaigns] = await Promise.all([
        api(API.formats), api(API.clients), api(API.campaigns),
      ]);
      renderClientOptions();
      renderCampaignOptions();
      renderFormatBrowser();
      renderLibrary();
      renderClients();
    } catch (error) {
      setPageError(error.message);
    }
  }

  function renderClientOptions() {
    const select = $('#mcCampaignClient');
    const current = select.value;
    select.innerHTML = '<option value="">Selecione um cliente</option>' + state.clients
      .map((client) => `<option value="${client.id}">${escapeHtml(client.name)}</option>`).join('');
    select.value = current;
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
      select.value = current || (state.campaign ? String(state.campaign.id) : '');
    });
  }

  // ====== GERADOR ======
  function renderClientPreview() {
    const client = state.clients.find((item) => String(item.id) === $('#mcCampaignClient').value);
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
      </div>`;
  }

  async function createCampaign(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('button[type="submit"]', form);
    await withLock('create-campaign', button, async () => {
      const data = Object.fromEntries(new FormData(form));
      data.client_id = Number(data.client_id);
      data.budget_usd = Number(data.budget_usd || 0);
      data.show_price = new FormData(form).has('show_price');
      try {
        const created = await api(API.campaigns, { method: 'POST', body: JSON.stringify(data) });
        state.campaigns = await api(API.campaigns);
        renderCampaignOptions();
        await selectCampaign(created.id);
        form.reset();
        toast('Campanha criada com a variação A.', 'success');
        activateTab('variacoes');
      } catch (error) {
        $('#mcCampaignFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  // ====== VARIAÇÕES ======
  async function selectCampaign(id) {
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
    state.activeStepId = preserveStep;
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
      <tr tabindex="0" data-library-format="${format.id}">
        <td><strong>${escapeHtml(format.name_pt)}</strong><br><span class="mc-section-note">${escapeHtml(format.category)}</span></td>
        <td>${escapeHtml(format.default_size || format.aspect_ratio || 'Flexível')}</td>
        <td>${escapeHtml(format.mechanic || '—')}</td>
        <td>${engineBadge(format)}</td>
        <td>${(format.references || []).length}/4</td>
      </tr>`).join('') || '<tr><td colspan="5">Nenhum formato encontrado.</td></tr>';
  }

  function renderLibraryDetail(format) {
    const refs = format.references || [];
    $('#mcLibraryDetail').innerHTML = `
      <div class="mc-inspector-section"><h3>${escapeHtml(format.name_pt)}</h3>${engineBadge(format)}<span class="cx-badge">${escapeHtml(format.default_size || format.aspect_ratio || '')}</span></div>
      <form class="mc-inspector-section" id="mcFormatModelForm" data-format-id="${format.id}">
        <label class="cx-field"><span class="cx-label">Background/base</span><textarea class="cx-textarea" name="background_guidance">${escapeHtml(format.background_guidance || '')}</textarea></label>
        <label class="cx-field"><span class="cx-label">Foreground/conteúdo</span><textarea class="cx-textarea" name="foreground_guidance">${escapeHtml(format.foreground_guidance || '')}</textarea></label>
        <label class="cx-field"><span class="cx-label">Comportamento responsivo</span><textarea class="cx-textarea" name="responsive_rules">${escapeHtml(format.responsive_rules || '')}</textarea></label>
        <label class="cx-field"><span class="cx-label">Área segura (JSON)</span><textarea class="cx-textarea" name="safe_area">${escapeHtml(JSON.stringify(format.safe_area || {}, null, 2))}</textarea></label>
        <button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-action="save-format-model">Salvar modelagem</button>
      </form>
      <div class="mc-reference-grid">${[1, 2, 3, 4].map((slot) => {
        const ref = refs.find((item) => Number(item.slot) === slot);
        return `<div class="mc-reference-slot">${ref ? `<img src="${escapeHtml(ref.asset_url)}" alt="Referência ${slot}">` : `<span>Slot ${slot}</span>`}</div>`;
      }).join('')}</div>`;
  }

  // ====== CLIENTES ======
  function renderClients() {
    const root = $('#mcClientTableBody');
    if (!root) return;
    root.innerHTML = state.clients.map((client) => {
      const logo = client.logo_upload_path || client.logo_url;
      return `<tr>
        <td><strong>${escapeHtml(client.name)}</strong><br><span class="mc-section-note">${escapeHtml(client.sector || 'Sem setor')}</span></td>
        <td><span class="mc-swatch" style="display:inline-block;background:${escapeHtml(client.primary_color || '#ffffff')}"></span> <span class="mc-swatch" style="display:inline-block;background:${escapeHtml(client.secondary_color || '#ffffff')}"></span></td>
        <td>${logo ? `<img src="${escapeHtml(logo)}" alt="" style="width:40px;height:32px;object-fit:contain">` : '<span class="cx-badge cx-badge-muted">Sem logo</span>'}</td>
        <td><div class="mc-inspector-actions"><button class="cx-btn cx-btn-secondary cx-btn-sm" data-action="open-logo" data-client-id="${client.id}" type="button">Logo</button><button class="cx-btn cx-btn-danger cx-btn-sm" data-action="delete-client" data-client-id="${client.id}" type="button">Remover</button></div></td>
      </tr>`;
    }).join('') || '<tr><td colspan="4">Cadastre o primeiro perfil de marca.</td></tr>';
  }

  async function createClient(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('button[type="submit"]', form);
    await withLock('create-client', button, async () => {
      const data = Object.fromEntries(new FormData(form));
      data.show_price = new FormData(form).has('show_price');
      try {
        await api(API.clients, { method: 'POST', body: JSON.stringify(data) });
        state.clients = await api(API.clients);
        renderClients();
        renderClientOptions();
        form.reset();
        toast('Perfil de marca salvo.', 'success');
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
        await withLock(`${action}-${step.id}`, button, () => api(routes[action][0], {
          method: routes[action][1],
          body: JSON.stringify({ asset_ids: Array.from(state.selectedAssets) }),
        }));
        toast(action === 'generate-script' ? 'Roteiro criado para revisão.' : 'Payload Higgsfield preparado.', 'success');
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
    const formatButton = event.target.closest('[data-format-id]');
    if (formatButton) {
      const format = state.formats.find((item) => String(item.id) === formatButton.dataset.formatId);
      if (format) renderFormatInspector(format);
      return;
    }
    const libraryRow = event.target.closest('[data-library-format]');
    if (libraryRow) {
      const format = state.formats.find((item) => String(item.id) === libraryRow.dataset.libraryFormat);
      if (format) renderLibraryDetail(format);
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
        data.safe_area = JSON.parse(data.safe_area || '{}');
        await api(`${API.formats}/${form.dataset.formatId}`, {
          method: 'PUT', body: JSON.stringify(data),
        });
        state.formats = await api(API.formats);
        const updated = state.formats.find((item) => String(item.id) === form.dataset.formatId);
        renderLibrary();
        renderLibraryDetail(updated);
        toast('Modelagem do formato atualizada.', 'success');
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
    $('#mcCampaignForm').addEventListener('submit', createCampaign);
    $('#mcClientForm').addEventListener('submit', createClient);
    $('#mcCampaignClient').addEventListener('change', renderClientPreview);
    $('#mcCampaignSelect').addEventListener('change', (event) => selectCampaign(event.target.value).catch((error) => toast(error.message, 'error')));
    $('#mcAddVariation').addEventListener('click', (event) => addVariation(event.currentTarget));
    $('#mcCreatePublicLink').addEventListener('click', () => {
      if (!state.campaignAssets.length) {
        toast('Adicione ao menos um criativo antes de publicar.', 'warning');
        return;
      }
      $('#mcShareForm [name="title"]').value = state.campaign?.name || '';
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
          const created = await api(`${API.campaigns}/${state.campaign.id}/public-collections`, {
            method: 'POST',
            body: JSON.stringify(Object.fromEntries(new FormData(form))),
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
