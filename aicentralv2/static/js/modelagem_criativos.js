(() => {
  'use strict';

  // ====== CONSTANTS ======
  const API = {
    formats: '/parametros/api/formats',
    clients: '/parametros/api/clients',
    campaignClients: '/parametros/api/campaign-clients',
    analyzeBrand: '/parametros/api/clients/analyze-brand',
    enhanceBrief: '/parametros/api/campaigns/enhance-brief',
    readPack: '/parametros/api/campaigns/read-pack',
    campaigns: '/parametros/api/campaigns',
    history: '/parametros/api/history',
    viewerProfiles: '/parametros/api/viewer-profiles',
    unfoldings: '/parametros/api/unfoldings',
    readKv: '/parametros/api/unfoldings/read-kv',
    exampleKv: '/parametros/api/unfoldings/example-kv',
    unfoldQuote: '/parametros/api/unfoldings/quote',
    unfoldPaths: '/parametros/api/unfoldings/paths',
    imageTiers: '/parametros/api/image-tiers',
    composeLibrary: '/parametros/api/compose-library',
  };
  const MOCKUPS = {
    portal: { label: 'Portal', icon: 'fa-desktop' },
    tv: { label: 'Smart TV', icon: 'fa-tv' },
    celular: { label: 'Celular', icon: 'fa-mobile-screen' },
    tablet: { label: 'Tablet', icon: 'fa-tablet-screen-button' },
    social: { label: 'Rede social', icon: 'fa-share-nodes' },
  };
  const FORMAT_SHORT_NAMES = {
    'instagram-feed': 'Feed 1:1',
    'instagram-feed-4x5': 'Feed 4:5',
    'instagram-story': 'Story',
    'instagram-reels': 'Reels',
    'facebook-feed': 'Feed 1:1',
    'linkedin-share': 'Paisagem',
    'linkedin-feed': 'Quadrado',
    'linkedin-portrait': 'Retrato',
    'tiktok-vertical': 'In-feed 9:16',
    'youtube-infeed': 'In-feed 16:9',
    'youtube-shorts': 'Shorts 9:16',
    'iab-medium-rectangle': '300×250',
    'iab-leaderboard': '728×90',
    'iab-half-page': '300×600',
    'iab-mobile-banner': '320×50',
  };
  const SOCIAL_NETWORKS = {
    instagram: { label: 'Instagram', prefix: 'instagram-' },
    facebook: { label: 'Facebook', prefix: 'facebook-' },
    linkedin: { label: 'LinkedIn', prefix: 'linkedin-' },
    tiktok: { label: 'TikTok', prefix: 'tiktok-' },
    youtube: { label: 'YouTube', prefix: 'youtube-' },
  };
  const state = {
    formats: [],
    clients: [],
    campaignClients: [],
    campaigns: [],
    campaign: null,
    production: null,
    productionByCampaign: new Map(),
    activeSceneId: null,
    previewAssetId: null,
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
    previewDevice: 'desktop',
    productionCarouselTimer: null,
    pauseAdTimer: null,
    pauseAdInterval: null,
    brandAnalysis: null,
    brandAssetCandidates: [],
    selectedBrandAssets: new Set(),
    brandAssetFilter: 'all',
    brandFiles: [],
    primaryBrandAssetUrl: null,
    primaryBrandFileIndex: -1,
    creativeLineFiles: [],
    creativeLineClientId: null,
    selectedBrandId: null,
    refineIntent: 'copy',
    renderMode: null,
    enhancedBrief: null,
    campaignPack: { files: [], url: '', extracted: {}, sources: [], previewUrls: [] },
    sceneRefFiles: [],
    sceneRefPreviewUrls: [],
    locks: new Set(),
    unfoldFormatIds: new Set(),
    unfoldCampaign: null,
    unfoldLibrary: [],
    publishModalCampaignId: null,
    imageTiers: [],
    publishPicks: {},
    unfoldPaths: null,
    unfoldQuote: null,
    unfoldItems: {},
    composeLibrary: { visual_systems: [], templates: [], variations: [] },
    selectedVariationId: null,
    selectedLibraryTemplateSlug: null,
    selectedLibraryVariationId: null,
  };

  const KV_ITEM_ORDER = [
    ['logo', 'Logo'],
    ['product_lockup', 'Produto'],
    ['talent', 'Foto'],
    ['headline', 'Headline'],
    ['offer', 'Oferta'],
    ['benefits', 'Benefícios'],
    ['cta', 'CTA'],
    ['legal', 'Legal'],
    ['background', 'Fundo'],
  ];
  const SCENE_LABELS = {
    square: 'feed',
    story: 'story',
    landscape: 'paisagem',
    half_page: 'half page',
    rectangle: 'rectangle',
    wide: 'faixa',
    mobile: 'mobile',
  };

  const $ = (selector, root = document) => (
    root && typeof root.querySelector === 'function' ? root.querySelector(selector) : null
  );
  const $$ = (selector, root = document) => (
    root && typeof root.querySelectorAll === 'function'
      ? Array.from(root.querySelectorAll(selector))
      : []
  );
  const bind = (selector, event, handler) => {
    const node = typeof selector === 'string' ? $(selector) : selector;
    if (!node) return;
    node.addEventListener(event, handler);
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
  }[char]));
  const money = (value) => `US$ ${Number(value || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2, maximumFractionDigits: 4,
  })}`;
  const brl = (value) => `R$ ${Number(value || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`;
  const spendValue = (record) => {
    const value = Number(record?.spent_brl ?? record?.total_brl ?? 0);
    return Number.isFinite(value) ? value : 0;
  };
  const campaignCost = (campaign) => brl(spendValue(campaign));
  const assetFidelity = (asset) => asset?.metadata?.fidelity || asset?.fidelity || (asset?.id ? 'draft' : '');
  const campaignConstruct = (campaign) => {
    const brief = (campaign || state.campaign || {}).creative_brief || {};
    return (brief.construct_path?.engine || brief.engine) === 'construct';
  };
  const previousSceneApproved = (scenes, index) => {
    if (index <= 0) return true;
    return sceneAssets(scenes[index - 1] || {}).some((asset) => (
      asset.asset_type !== 'video' && asset.status === 'approved'
    ));
  };
  const publishHold = (asset) => {
    if (!asset?.id || assetFidelity(asset) === 'publish') return '';
    const meta = asset.metadata || {};
    if (meta.require_logo && !meta.logo_applied) {
      return 'Falta o PNG da marca no perfil. Sem ele a peça não fecha publicável.';
    }
    if (meta.needs_retry || meta.safe_area_clear === false) {
      return 'A foto ainda tinha texto na caixa. Gere de novo.';
    }
    if (meta.composed === false) {
      return 'A montagem não colou. Gere de novo.';
    }
    return '';
  };
  const layerCaption = (asset) => {
    const meta = asset?.metadata || {};
    if (meta.derived_from_master || meta.source_scene_id) {
      return 'Mesma foto de outro retângulo deste lote.';
    }
    if (meta.engine === 'construct') return 'Foto gerada; texto e logo entram na montagem.';
    if (meta.engine === 'paint') return 'A IA pintou a peça inteira.';
    return '';
  };
  const publishUnitBrl = () => {
    const tier = (state.imageTiers || []).find((item) => item.name === 'publish');
    const value = Number(tier?.estimated_brl ?? tier?.spent_brl ?? 0);
    return Number.isFinite(value) ? value : 0;
  };
  const draftUnitBrl = () => {
    const tier = (state.imageTiers || []).find((item) => item.name === 'draft');
    const value = Number(tier?.estimated_brl ?? tier?.spent_brl ?? 0);
    return Number.isFinite(value) ? value : 0;
  };
  let historyRequestId = 0;
  const toast = (message, type = 'info') => {
    if (typeof window.showToast === 'function') window.showToast(message, type);
  };
  const setPageError = (message = '') => {
    const alert = $('#mcPageAlert');
    if (!alert) return;
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
      let message = payload.error || `Erro HTTP ${response.status}`;
      if (response.status === 504) {
        message = 'O servidor cortou o pedido por tempo. No Montar em camadas as peças saem do KV, sem foto nova.';
      }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload.data;
  }

  async function apiFirst(requests) {
    let lastError;
    for (const request of requests) {
      try {
        return await api(request.url, request.options);
      } catch (error) {
        lastError = error;
        if (![404, 405].includes(error.status)) throw error;
      }
    }
    throw lastError;
  }

  // ====== TAB NAVIGATION ======
  function deskPath(name) {
    if (name === 'formatos') return 'biblioteca';
    return name;
  }

  function activateTab(name, updateHash = true) {
    const dest = deskPath(name);
    const page = $('#mcApp')?.dataset.mcPage;
    if (page && page !== dest && dest !== 'hub') {
      window.location.href = `/parametros/modelagem-criativos/${dest}`;
      return;
    }
    $$('#mcTabs [data-tab]').forEach((tab) => {
      const active = deskPath(tab.dataset.tab) === dest || tab.dataset.tab === name;
      tab.classList.toggle('cx-tab-active', active);
      tab.classList.toggle('is-current', active);
      tab.setAttribute('aria-selected', String(active));
    });
    $$('.mc-panel').forEach((panel) => panel.classList.toggle('hidden', panel.dataset.panel !== dest && panel.dataset.panel !== name));
    if (updateHash) history.replaceState(null, '', `#${name}`);
    if (dest === 'biblioteca' || name === 'formatos') renderLibrary();
    if (name === 'marcas') renderClients();
    if (name === 'historico' && state.campaigns.length) loadHistory();
    if (name === 'produzir') renderWorkspace();
    if (name === 'desdobrar') {
      renderClientOptions();
      renderUnfoldFormats();
      renderUnfoldLibrary();
      fillUnfoldModels();
      quoteUnfoldPath();
      syncUnfoldProgress();
      if (state.unfoldCampaign) {
        renderUnfoldSpend(state.unfoldCampaign);
        syncPublishTriggers();
        refreshPublishModal();
      }
    }
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
      ['imageTiers', 'preços de imagem', API.imageTiers],
      ['unfoldPaths', 'caminhos do desdobrador', API.unfoldPaths],
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
    renderUnfoldFormats();
    renderUnfoldLibrary();
    fillUnfoldModels();
    fillPrepareModels();
    quoteUnfoldPath();
    quotePreparePath();
    syncUnfoldProgress();
    loadComposeLibrary();
    if (failures.length) {
      setPageError(`Não foi possível carregar ${failures.join(' | ')}`);
    }
    const page = $('#mcApp')?.dataset.mcPage;
    if (page === 'historico') loadHistory();
    const campaignId = new URLSearchParams(location.search).get('campaign');
    if (campaignId && (page === 'produzir' || page === 'preparar' || page === 'historico')) {
      selectCampaign(campaignId).catch((error) => toast(error.message, 'error'));
    }
  }

  function brandedCampaignClients() {
    return (state.campaignClients || []).filter((client) => (
      client.profile_id && client.profile_status !== 'minimal'
    ));
  }

  function clientOptionLabel(client) {
    const suffix = client.source === 'crm'
      ? 'CRM · marca pronta'
      : (client.house || Number(client.crm_client_id) === 174
        ? 'CentralComm · marca'
        : 'Perfil de marca');
    return `${escapeHtml(client.name)} — ${suffix}`;
  }

  function requestedClientRef() {
    const params = new URLSearchParams(window.location.search);
    return params.get('client_ref')
      || (params.get('crm_client_id') ? `crm:${params.get('crm_client_id')}` : '')
      || (params.get('creative_client_id') ? `profile:${params.get('creative_client_id')}` : '');
  }

  function fillClientSelect(select, placeholder) {
    if (!select) return;
    const current = select.value;
    const branded = brandedCampaignClients();
    select.innerHTML = `<option value="">${placeholder}</option>` + branded
      .map((client) => `<option value="${escapeHtml(client.selection_key)}">${clientOptionLabel(client)}</option>`)
      .join('');
    const preferred = current || requestedClientRef();
    if (preferred && Array.from(select.options).some((option) => option.value === preferred)) {
      select.value = preferred;
    }
  }

  function renderClientOptions() {
    fillClientSelect($('#mcCampaignClient'), 'Selecione um cliente');
    fillClientSelect($('#mcUnfoldClient'), 'Selecione a marca');
    renderClientPreview();
    renderGeneratorSummary();
    updateGeneratorAvailability();
    renderUnfoldBrand();
    syncUnfoldProgress();
  }

  function modelCampaigns() {
    return state.campaigns.filter((item) => (item.flow_kind || 'model') !== 'unfold');
  }

  function renderCampaignOptions() {
    ['#mcCampaignSelect', '#mcHistoryCampaign'].forEach((selector) => {
      const select = $(selector);
      if (!select) return;
      const current = select.value;
      const first = selector === '#mcHistoryCampaign' ? 'Todas as modelagens' : 'Escolha uma campanha';
      select.innerHTML = `<option value="">${first}</option>` + modelCampaigns().map((campaign) => (
        `<option value="${campaign.id}">${escapeHtml(campaign.name)} — ${escapeHtml(campaign.client)} · ${campaignCost(campaign)}</option>`
      )).join('');
      select.value = selector === '#mcCampaignSelect' && state.campaign
        ? String(state.campaign.id)
        : current;
    });
  }

  // ====== GERADOR ======
  function brandLine(client) {
    return client?.brand_profile?.creative_line || {};
  }

  function brandPalette(client) {
    const profile = client?.brand_profile || {};
    const palette = Array.isArray(profile.color_palette) ? profile.color_palette : [];
    const learned = Array.isArray(brandLine(client).color_palette)
      ? brandLine(client).color_palette
      : [];
    return palette.length ? palette : learned;
  }

  function brandTone(client) {
    const learned = (brandLine(client).copy_patterns || []).filter(Boolean).slice(0, 2).join(' ');
    return client?.tone_of_voice || learned || '';
  }

  function brandSummary(client) {
    return client?.brand_profile?.brand_summary || brandLine(client).signature_summary || '';
  }

  function brandPrimaryColor(client) {
    if (client?.primary_color) return client.primary_color;
    const usable = brandPalette(client).find((color) => color?.hex && String(color.hex).toUpperCase() !== '#FFFFFF');
    return usable?.hex || brandPalette(client)[0]?.hex || '';
  }

  function brandSecondaryColor(client) {
    if (client?.secondary_color) return client.secondary_color;
    const primary = brandPrimaryColor(client);
    const match = brandPalette(client).find((color) => (
      color?.hex && color.hex !== primary && String(color.hex).toUpperCase() !== '#FFFFFF'
    ));
    return match?.hex || '';
  }

  function renderClientPreview() {
    const root = $('#mcClientPreview');
    if (!root) return;
    const client = state.campaignClients.find(
      (item) => item.selection_key === $('#mcCampaignClient')?.value,
    );
    if (!client) {
      root.innerHTML = '<div class="cx-empty-state"><p>Escolha um cliente para conferir sua identidade.</p></div>';
      return;
    }
    const logo = client.logo_upload_path || client.logo_url;
    const primary = brandPrimaryColor(client);
    const secondary = brandSecondaryColor(client);
    const summary = brandSummary(client);
    const tone = brandTone(client);
    root.innerHTML = `
      <div class="mc-identity">
        <div class="mc-identity-brand">
          <span class="mc-logo">${logo ? `<img src="${escapeHtml(logo)}" alt="">` : '<i class="fa-regular fa-building"></i>'}</span>
          <div><strong>${escapeHtml(client.name)}</strong><p class="mc-section-note">${escapeHtml(client.sector || 'Setor não informado')}</p></div>
        </div>
        <div class="mc-swatches" aria-label="Cores da marca">
          ${primary ? `<span class="mc-swatch" style="background:${escapeHtml(primary)}" title="${escapeHtml(primary)}"></span>` : ''}
          ${secondary ? `<span class="mc-swatch" style="background:${escapeHtml(secondary)}" title="${escapeHtml(secondary)}"></span>` : ''}
        </div>
        <div><strong>Tom de voz</strong><p>${escapeHtml(tone || 'Não informado')}</p></div>
        ${summary ? `<div><strong>Assinatura visual</strong><p>${escapeHtml(summary)}</p></div>` : ''}
        ${client.brand_profile?.target_audience ? `<div><strong>Público prioritário</strong><p>${escapeHtml(client.brand_profile.target_audience)}</p></div>` : ''}
        ${brandInventoryChips(client)}
      </div>`;
  }

  function brandFonts(source) {
    const profile = source?.brand_profile || source || {};
    const fonts = Array.isArray(profile.fonts) ? profile.fonts : [];
    const lineFont = brandLine(source).copy_system?.typography?.family;
    if (fonts.length) return fonts;
    return lineFont ? [{ family: lineFont, role: 'display' }] : [];
  }

  function brandInventoryChips(client) {
    const assets = client?.brand_assets || [];
    const fonts = brandFonts(client);
    const chips = [
      brandLine(client).signature_summary && 'Linha criativa',
      fonts[0]?.family && `Fonte ${fonts[0].family}`,
      assets.filter((item) => item.role === 'logo').length && 'Logo',
      assets.filter((item) => item.role === 'reference').length
        && `${assets.filter((item) => item.role === 'reference').length} refs`,
      assets.filter((item) => item.role === 'creative').length
        && `${assets.filter((item) => item.role === 'creative').length} peças`,
    ].filter(Boolean);
    if (!chips.length) return '';
    return `<div class="mc-brand-inventory-chips">${chips.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div>`;
  }

  function generatorSelectedFormat() {
    return state.formats.find((item) => String(item.id) === String(state.generatorFormatId));
  }

  function formatGroupLabel(format) {
    if (format.channel_name) return format.channel_name;
    if (format.category === 'social') return 'Redes sociais';
    if (format.category === 'streaming') return 'Streaming';
    return 'Programática';
  }

  function catalogTypeKey(format) {
    if (format?.category === 'social') return 'social';
    if (format?.category === 'streaming') return 'streaming';
    return 'programatica';
  }

  function catalogTypeLabel(key) {
    if (key === 'social') return 'Redes sociais';
    if (key === 'streaming') return 'Streaming';
    return 'Programática';
  }

  function socialNetworkKey(format) {
    const slug = String(format?.slug || '');
    return Object.keys(SOCIAL_NETWORKS).find((key) => slug.startsWith(SOCIAL_NETWORKS[key].prefix)) || null;
  }

  function catalogNetworkKey(format) {
    const social = socialNetworkKey(format);
    if (social) return social;
    return format?.channel || format?.channel_name || 'outros';
  }

  function catalogNetworkLabel(format) {
    const social = socialNetworkKey(format);
    if (social) return SOCIAL_NETWORKS[social].label;
    return format?.channel_name || formatGroupLabel(format);
  }

  function catalogNetworkLogo(format) {
    const social = socialNetworkKey(format);
    if (!social) return '';
    const profile = state.viewerProfiles.find((item) => item.slug === social);
    return profile?.logo_asset_ref || `/static/images/creative-viewers/${social}.svg`;
  }

  function formatShortName(format) {
    return FORMAT_SHORT_NAMES[format?.slug] || formatDisplayName(format);
  }

  function isSocialFormat(format) {
    return format?.category === 'social' || Boolean(socialNetworkKey(format));
  }

  function groupedCatalogFormats(formats) {
    const typeOrder = { programatica: 0, streaming: 1, social: 2 };
    const types = new Map();
    formats.forEach((format) => {
      const type = catalogTypeKey(format);
      if (!types.has(type)) types.set(type, new Map());
      const networks = types.get(type);
      const network = catalogNetworkKey(format);
      if (!networks.has(network)) {
        networks.set(network, {
          key: network,
          label: catalogNetworkLabel(format),
          logo: catalogNetworkLogo(format),
          formats: [],
        });
      }
      networks.get(network).formats.push(format);
    });
    return Array.from(types.entries())
      .sort((left, right) => (typeOrder[left[0]] ?? 9) - (typeOrder[right[0]] ?? 9))
      .map(([type, networks]) => ({
        type,
        label: catalogTypeLabel(type),
        networks: Array.from(networks.values()),
      }));
  }

  function formatDisplayName(format) {
    const group = formatGroupLabel(format);
    const name = String(format.name_pt || '');
    const prefix = `${group} — `;
    return name.startsWith(prefix) ? name.slice(prefix.length) : name;
  }

  function formatOrientationKey(format) {
    const key = formatDirection(format).orientation;
    if (key) return key;
    const size = parseDefaultSize(format?.default_size || format?.target_size);
    if (!size) return 'square';
    const ratio = size.w / Math.max(size.h, 1);
    if (ratio >= 1.15) return 'horizontal';
    if (ratio <= 0.87) return 'vertical';
    return 'square';
  }

  function groupedGeneratorFormats(formats) {
    const catalog = groupedCatalogFormats(formats);
    return catalog.flatMap((group) => group.networks.map((network) => [
      group.type === 'programatica' ? group.label : network.label,
      network.formats,
    ]));
  }

  function renderGeneratorFormats() {
    const root = $('#mcGeneratorFormatList');
    if (!root) return;
    const category = $('#mcGeneratorFormatCategory')?.value || '';
    const formats = state.formats.filter((format) => (
      format.media_type === 'image' && (!category || format.category === category)
    ));
    if (!formats.some((format) => String(format.id) === String(state.generatorFormatId))) {
      const standard = formats.find((format) => format.slug === 'netflix-anuncio-simulado');
      state.generatorFormatId = (standard || formats[0])?.id || null;
    }
    const groups = groupedGeneratorFormats(formats);
    root.innerHTML = groups.length
      ? groups.map(([label, items]) => `
        <section class="mc-format-group">
          <h3>${escapeHtml(label)}</h3>
          ${items.map((format) => {
            const orientation = formatOrientationKey(format);
            return `<button class="mc-generator-format ${String(format.id) === String(state.generatorFormatId) ? 'is-active' : ''}"
                    type="button" data-generator-format="${format.id}">
              <span class="mc-orient is-${orientation}" aria-hidden="true"></span>
              <span>
                <strong>${escapeHtml(formatDisplayName(format))}</strong>
                <small>${escapeHtml(formatSizeLabel(format))}</small>
              </span>
              <em>${escapeHtml(formatOrientationLabel(format) || '')}</em>
            </button>`;
          }).join('')}
        </section>`).join('')
      : '<div class="mc-generator-no-format">Nenhum formato nesta categoria.</div>';
    renderGeneratorFormatPreview();
    renderGeneratorSummary();
    renderContextDesign();
    renderComposeVariations();
    updateGeneratorAvailability();
    quotePreparePath();
  }

  function updateGeneratorAvailability() {
    const button = $('#mcCampaignFormSubmit');
    const status = $('#mcCampaignFormStatus');
    if (!button || !status) return;
    const issue = !brandedCampaignClients().length
      ? 'Nenhum cliente com marca. Monte o perfil em Marcas.'
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
      root.innerHTML = '<p>Escolha um formato para definir a produção.</p>';
      $('#mcGeneratorScenePlan').innerHTML = '';
      return;
    }
    const sceneCount = sceneCountForFormat(format);
    const direction = formatDirection(format);
    root.innerHTML = `
      <div class="mc-generator-preview-copy">
        <span><strong>${escapeHtml(formatDisplayName(format))}</strong><small>${direction.animated ? 'Anúncio em sequência' : 'Peça única'}</small></span>
        <span class="mc-format-size-stack">
          <span class="cx-badge cx-badge-muted">${escapeHtml(formatSizeLabel(format))}</span>
          ${formatOrientationLabel(format) ? `<span class="cx-badge">${escapeHtml(formatOrientationLabel(format))}</span>` : ''}
        </span>
      </div>
      ${renderFormatSlotMap(format)}
      ${direction.layout?.summary ? `<p class="mc-format-layout-note">${escapeHtml(direction.layout.summary)}</p>` : ''}
      ${renderFormatElementChips(format)}`;
    const beats = prepareBeats(format, sceneCount);
    const orientation = formatOrientationLabel(format);
    $('#mcGeneratorScenePlan').innerHTML = `
      <strong>${sceneCount === 1 ? '1 quadro' : `${sceneCount} batidas`}</strong>
      <span>${sceneCount === 1
        ? `Um retângulo ${orientation ? orientation.toLowerCase() : ''}. Os elementos sentam nas zonas da modelagem.`
        : `A bancada abre com ${sceneCount} batidas no retângulo ${orientation ? orientation.toLowerCase() : 'deste formato'}.`}</span>
      <div>${beats.map((beat, index) => `<i title="${escapeHtml(beat.job || '')}">${beat.position || index + 1}</i>`).join('')}</div>
      ${beats.length ? `<ol class="mc-beat-plan">${beats.map((beat) => `<li><strong>${escapeHtml(beat.label)}</strong> ${escapeHtml(beat.job)}</li>`).join('')}</ol>` : ''}`;
  }

  function parseDefaultSize(value) {
    const match = String(value || '').match(/(\d+)\s*[xX×]\s*(\d+)/);
    return match ? { w: Number(match[1]), h: Number(match[2]) } : null;
  }

  function formatSizeLabel(format) {
    const direction = formatDirection(format);
    if (direction.size_label) return direction.size_label;
    const size = parseDefaultSize(format?.default_size || format?.target_size);
    if (size) return `${size.w} × ${size.h} px`;
    return format?.default_size || format?.aspect_ratio || 'Flexível';
  }

  function formatDirection(format) {
    return format?.direction || {};
  }

  function formatOrientationLabel(format) {
    const direction = formatDirection(format);
    if (direction.orientation_label) return direction.orientation_label;
    const map = { horizontal: 'Horizontal', vertical: 'Vertical', square: 'Quadrado' };
    return map[direction.orientation] || '';
  }

  function formatBeat(format, position) {
    return (formatDirection(format).beats || []).find(
      (item) => Number(item.position) === Number(position),
    ) || null;
  }

  function renderFormatSlotMap(format, beat) {
    const direction = formatDirection(format);
    const slots = (beat?.slots?.length ? beat.slots : direction.layout?.slots) || [];
    if (!slots.length || !direction.width || !direction.height) return '';
    const orientation = direction.orientation || formatOrientationKey(format);
    const strip = direction.width / direction.height >= 4;
    return `<div class="mc-slot-map is-${escapeHtml(orientation)}${strip ? ' is-strip' : ''}" style="aspect-ratio:${direction.width}/${direction.height}" aria-label="Onde sentam os elementos neste retângulo">
      ${slots.map((slot) => `
        <i class="is-${escapeHtml(slot.key)}" style="left:${slot.x}%;top:${slot.y}%;width:${slot.width}%;height:${slot.height}%">${escapeHtml(slot.label)}</i>
      `).join('')}
    </div>`;
  }

  function renderFormatElementChips(format) {
    const elements = formatDirection(format).elements || [];
    if (!elements.length) return '';
    return `<ul class="mc-format-elements">${elements.map((item) => `
      <li class="${item.present ? 'is-on' : 'is-off'}">${escapeHtml(item.label)}</li>
    `).join('')}</ul>`;
  }

  function isSequenceFormat(format) {
    return format?.iab_family === 'sequence_16x9'
      || format?.slug === 'netflix-anuncio-simulado'
      || format?.slug === 'netflix-logo-bumper';
  }

  function isLibraryFormat(format) {
    return [
      'sequence_16x9', 'square_1x1', 'rectangle', 'wide_banner',
      'half_page', 'story_9x16', 'landscape_social', 'slate_16x9', 'portrait_4x5',
    ].includes(format?.iab_family) || isSequenceFormat(format);
  }

  function variationsForFormat(format) {
    const family = format?.iab_family;
    return (state.composeLibrary?.variations || []).filter((item) => (
      item.family === family && item.status !== 'archived'
    ));
  }

  async function loadComposeLibrary() {
    const requested = new URLSearchParams(location.search).get('variation');
    if (requested) state.selectedVariationId = requested;
    try {
      state.composeLibrary = await api(API.composeLibrary) || {
        visual_systems: [], templates: [], variations: [],
      };
    } catch (error) {
      state.composeLibrary = { visual_systems: [], templates: [], variations: [] };
    }
    renderComposeVariations();
    renderLibraryVariations();
  }

  function variationStatusLabel(status) {
    if (status === 'approved') return 'Aprovada';
    if (status === 'archived') return 'Arquivada';
    return 'Experimental';
  }

  function renderComposeVariations() {
    const root = $('#mcComposeVariations');
    if (!root) return;
    const format = generatorSelectedFormat();
    const items = variationsForFormat(format);
    if (!isLibraryFormat(format) || !items.length) {
      root.classList.add('hidden');
      root.innerHTML = '';
      if (!items.some((item) => String(item.id) === String(state.selectedVariationId))) {
        state.selectedVariationId = null;
      }
      return;
    }
    if (!items.some((item) => String(item.id) === String(state.selectedVariationId))) {
      const preferred = items.find((item) => item.status === 'approved') || items[0];
      state.selectedVariationId = preferred?.id || null;
    }
    root.classList.remove('hidden');
    root.innerHTML = `
      <header>
        <strong>Rascunho HTML</strong>
        <small>O mapa extraído posiciona foto, logo e textos no HTML</small>
      </header>
      <div class="mc-compose-variation-grid">
        ${items.map((item) => `
          <button class="mc-compose-card ${String(item.id) === String(state.selectedVariationId) ? 'is-active' : ''}"
                  type="button" data-compose-variation="${escapeHtml(String(item.id))}">
            <span class="mc-compose-card-status is-${escapeHtml(item.status || 'experimental')}">${escapeHtml(variationStatusLabel(item.status))}</span>
            <strong>${escapeHtml(item.name || 'Variação')}</strong>
            <small>${escapeHtml(item.kind === 'script' ? 'Roteiro' : 'Layout')}${Array.isArray(item.params?.regions) && item.params.regions.length ? ` · ${item.params.regions.length} regiões` : ''}</small>
          </button>
        `).join('')}
      </div>`;
  }

  function renderLibraryVariations() {
    const root = $('#mcLibraryVariations');
    if (!root) return;
    const items = (state.composeLibrary?.variations || []).filter((item) => item.status !== 'archived');
    if (!items.length) {
      root.innerHTML = '';
      return;
    }
    root.innerHTML = `
      <header>
        <strong>Variações da marca</strong>
        <small>Aprovação no Produzir promove a carta. Sem HTML na mesa.</small>
      </header>
      <div class="mc-compose-variation-grid">
        ${items.map((item) => `
          <article class="mc-compose-card">
            <span class="mc-compose-card-status is-${escapeHtml(item.status || 'experimental')}">${escapeHtml(variationStatusLabel(item.status))}</span>
            <strong>${escapeHtml(item.name || 'Variação')}</strong>
            <small>${escapeHtml(item.family)} · ${item.approve_count || 0} aprovações</small>
          </article>
        `).join('')}
      </div>`;
  }

  function activeRenderMode() {
    if (isSequenceFormat(activeProductionFormat() || generatorSelectedFormat())) return 'native';
    if (state.renderMode === 'native' || state.renderMode === 'mockup') return state.renderMode;
    return activeProductionFormat()?.default_render_mode || 'mockup';
  }

  function suggestedSceneCount(format) {
    const canonical = Number(format?.scene_count);
    if ([1, 4, 6, 8].includes(canonical)) return canonical;
    const behavior = String(format?.behavior_spec?.type || format?.mechanic || '').toLowerCase();
    const mechanic = String(format?.mechanic || '').toLowerCase();
    const name = String(format?.name_pt || '').toLowerCase();
    const isStaticBanner = behavior === 'static'
      && (mechanic === 'static_display'
        || name.includes('banner')
        || ['leaderboard', 'billboard', 'halfpage'].some((term) => name.includes(term)));
    return isStaticBanner ? 1 : 4;
  }

  function prepareEngine() {
    return $('#mcPreparePathBar input[name="prepare_engine"]:checked')?.value || 'construct';
  }

  function preparePack() {
    const selected = Number($('#mcPreparePathBar input[name="prepare_pack"]:checked')?.value);
    return [4, 6, 8].includes(selected) ? selected : 4;
  }

  function sceneCountForFormat(format) {
    const selected = Number($('#mcPreparePathBar input[name="prepare_pack"]:checked')?.value);
    if ([1, 4, 6, 8].includes(selected)) return selected;
    const suggested = suggestedSceneCount(format);
    return suggested === 1 ? 4 : suggested;
  }

  const PREPARE_BEATS = {
    4: [
      { label: 'Gancho', job: 'Primeiro quadro do mesmo anúncio.' },
      { label: 'Contexto', job: 'O produto entra. Não é variação.' },
      { label: 'Benefício', job: 'O valor fica visível neste instante.' },
      { label: 'Fechamento', job: 'Último quadro. CTA só se o formato tiver.' },
    ],
    6: [
      { label: 'Gancho', job: 'Primeiro quadro do mesmo anúncio.' },
      { label: 'Contexto', job: 'O produto entra. Não é variação.' },
      { label: 'Benefício', job: 'O valor fica visível neste instante.' },
      { label: 'Oferta', job: 'A oferta ou a prova entra. Continua o mesmo anúncio.' },
      { label: 'Reforço', job: 'Outro recorte do mesmo talent.' },
      { label: 'Fechamento', job: 'Último quadro. CTA só se o formato tiver.' },
    ],
    8: [
      { label: 'Gancho', job: 'Primeiro quadro do mesmo anúncio.' },
      { label: 'Contexto', job: 'O produto entra. Não é variação.' },
      { label: 'Benefício', job: 'O valor fica visível neste instante.' },
      { label: 'Oferta', job: 'A oferta ou a prova entra. Continua o mesmo anúncio.' },
      { label: 'Reforço', job: 'Outro recorte do mesmo talent.' },
      { label: 'Segundo gancho', job: 'A/B de talent. Não é outra campanha.' },
      { label: 'Segundo fechamento', job: 'Fechamento alternativo. A/B de talent.' },
      { label: 'Fechamento', job: 'Último quadro. CTA só se o formato tiver.' },
    ],
  };

  function prepareBeats(format, sceneCount) {
    const directionBeats = formatDirection(format).beats || [];
    if (directionBeats.length === sceneCount) return directionBeats;
    return (PREPARE_BEATS[sceneCount] || PREPARE_BEATS[4]).map((beat, index) => ({
      ...beat,
      position: index + 1,
    }));
  }

  function collectContextDesign(sceneCount) {
    const count = Number(sceneCount) || 4;
    const scenes = [];
    for (let position = 1; position <= count; position += 1) {
      scenes.push({
        position,
        job: $(`[data-context-job="${position}"]`)?.value || '',
        set_note: $(`[data-context-set="${position}"]`)?.value || '',
        action_note: $(`[data-context-action="${position}"]`)?.value || '',
        copy_on_frame: Boolean($(`[data-context-copy="${position}"]`)?.checked),
      });
    }
    return {
      cast_count: Number($('#mcContextCast')?.value || 1) === 2 ? 2 : 1,
      cast_lock: $('#mcContextCastLock')?.checked !== false,
      product_lock: $('#mcContextProductLock')?.checked !== false,
      scenography: $('#mcContextScenography')?.value === 'change' ? 'change' : 'line',
      scenes,
    };
  }

  function campaignContextDesign() {
    return (state.campaign?.creative_brief || {}).context_design || {};
  }

  function renderContextDesign() {
    const root = $('#mcContextDesign');
    if (!root) return;
    const format = generatorSelectedFormat();
    const show = isSequenceFormat(format);
    root.classList.toggle('hidden', !show);
    if (!show) {
      root.innerHTML = '';
      return;
    }
    const sceneCount = sceneCountForFormat(format);
    const beats = prepareBeats(format, sceneCount);
    const previous = collectContextDesign(sceneCount);
    root.innerHTML = `
      <header>
        <div><strong>Engenheiro de contexto</strong><small>Trava elenco, produto e set nas ${sceneCount} batidas.</small></div>
      </header>
      <div class="mc-context-locks">
        <label class="cx-field">
          <span class="cx-label">Pessoas</span>
          <select class="cx-select" id="mcContextCast">
            <option value="1" ${previous.cast_count !== 2 ? 'selected' : ''}>1 pessoa</option>
            <option value="2" ${previous.cast_count === 2 ? 'selected' : ''}>2 pessoas</option>
          </select>
        </label>
        <label class="mc-check">
          <input type="checkbox" id="mcContextCastLock" ${previous.cast_lock ? 'checked' : ''}>
          <span>As mesmas pessoas em todas as cenas</span>
        </label>
        <label class="mc-check">
          <input type="checkbox" id="mcContextProductLock" ${previous.product_lock ? 'checked' : ''}>
          <span>O mesmo produto em todas as cenas</span>
        </label>
        <label class="cx-field">
          <span class="cx-label">Cenografia</span>
          <select class="cx-select" id="mcContextScenography">
            <option value="line" ${previous.scenography !== 'change' ? 'selected' : ''}>Mesma linha</option>
            <option value="change" ${previous.scenography === 'change' ? 'selected' : ''}>Muda o set a cada cena</option>
          </select>
        </label>
      </div>
      <div class="mc-context-beats">
        ${beats.map((beat, index) => {
          const position = beat.position || index + 1;
          const saved = previous.scenes.find((item) => Number(item.position) === position) || {};
          const copyOn = saved.copy_on_frame != null ? saved.copy_on_frame : position >= sceneCount;
          return `
            <article class="mc-context-beat">
              <span><i>${position}</i><strong>${escapeHtml(beat.label || `Cena ${position}`)}</strong></span>
              <input class="cx-input" data-context-job="${position}" maxlength="400" value="${escapeHtml(saved.job || beat.job || '')}" placeholder="Trabalho desta batida">
              <textarea class="cx-textarea" data-context-set="${position}" rows="2" maxlength="1000" placeholder="Set / cenografia desta cena">${escapeHtml(saved.set_note || '')}</textarea>
              <textarea class="cx-textarea" data-context-action="${position}" rows="2" maxlength="1000" placeholder="Ação / encenação">${escapeHtml(saved.action_note || '')}</textarea>
              <label class="mc-check">
                <input type="checkbox" data-context-copy="${position}" ${copyOn ? 'checked' : ''}>
                <span>Colar texto e logo neste quadro</span>
              </label>
            </article>`;
        }).join('')}
      </div>`;
  }

  function renderStoryboardEditor() {
    const root = $('#mcStoryboardEditor');
    const brief = state.enhancedBrief;
    if (!root) return;
    root.classList.toggle('hidden', !brief?.scenes?.length);
    if (!brief?.scenes?.length) {
      root.innerHTML = '';
      return;
    }
    root.innerHTML = `
      <header>
        <div><strong>Storyboard proposto</strong><small>Revise a progressão antes de iniciar.</small></div>
        <span>${brief.scenes.length} ${brief.scenes.length === 1 ? 'cena' : 'cenas'}</span>
      </header>
      <p class="mc-visual-bible"><strong>Bíblia visual</strong>${escapeHtml(brief.visual_bible || '')}</p>
      <div class="mc-storyboard-grid">
        ${brief.scenes.map((scene, index) => `
          <label class="mc-storyboard-card">
            <span><i>${index + 1}</i><strong>${escapeHtml(String(scene.role || 'cena').replaceAll('_', ' '))}</strong></span>
            <textarea class="cx-textarea" rows="4" maxlength="8000" data-storyboard-scene="${index}">${escapeHtml(scene.description || '')}</textarea>
          </label>`).join('')}
      </div>`;
  }

  async function enhanceCampaignBrief(button) {
    const form = $('#mcCampaignForm');
    const format = generatorSelectedFormat();
    const client = state.campaignClients.find(
      (item) => item.selection_key === $('#mcCampaignClient')?.value,
    );
    const data = Object.fromEntries(new FormData(form));
    const hasMessage = Boolean(String(data.campaign_text || '').trim());
    const hasPack = Boolean(
      state.campaignPack.files.length
      || String(state.campaignPack.url || '').trim()
      || state.campaignPack.extracted?.headline
      || state.campaignPack.extracted?.offer
    );
    if (!client || !format || !String(data.name || '').trim() || (!hasMessage && !hasPack)) {
      toast('Selecione a marca e o formato e informe a mensagem ou um criativo/link da campanha.', 'warning');
      return;
    }
    await withLock('enhance-brief', button, async () => {
      try {
        const improved = await api(API.enhanceBrief, {
          method: 'POST',
          body: JSON.stringify({
            client_name: client.name,
            client_profile: client.brand_profile || {},
            name: data.name,
            objective: data.objective,
            campaign_text: data.campaign_text,
            campaign_pack: campaignPackPayload(),
            cta_text: data.cta_text,
            format_name: format.name_pt,
            format_slug: format.slug,
            mechanic: format.mechanic,
            default_size: format.default_size || format.target_size,
            behavior_spec: format.behavior_spec || {},
            layers: format.layers || [],
            scene_count: sceneCountForFormat(format),
          }),
        });
        state.enhancedBrief = improved;
        form.elements.campaign_text.value = improved.campaign_text || data.campaign_text;
        if (improved.cta_text) form.elements.cta_text.value = improved.cta_text;
        renderStoryboardEditor();
        renderGeneratorSummary();
        toast('Briefing aprimorado. Revise o storyboard antes de produzir.', 'success');
      } catch (error) {
        toast(error.message, 'error');
      }
    });
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
    const sceneCount = format ? sceneCountForFormat(format) : null;
    root.innerHTML = `
      <span><small>Marca</small><strong>${escapeHtml(client?.name || 'Não selecionada')}</strong></span>
      <span><small>Campanha</small><strong>${escapeHtml(name || 'Sem nome')}</strong></span>
      <span><small>Formato</small><strong>${escapeHtml(format?.name_pt || 'Não selecionado')}</strong></span>
      <span><small>Cenas</small><strong>${sceneCount ? `${sceneCount} ${sceneCount === 1 ? 'imagem' : 'cenas'}` : '—'}</strong></span>`;
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
      data.show_price = new FormData(form).has('show_price');
      data.scene_count = sceneCountForFormat(format);
      data.format_template_id = Number(format.id);
      data.engine = prepareEngine();
      data.scene_pack = preparePack();
      data.image_model = $('#mcPrepareModel')?.value || '';
      data.fidelity = prepareEngine() === 'construct' ? 'publish' : 'draft';
      data.construct_path = {
        engine: data.engine,
        scene_pack: data.scene_pack,
        image_model: data.image_model,
        fidelity: data.fidelity,
      };
      data.locks = collectPrepareLocks(data);
      data.productions = [{
        format_template_id: Number(format.id),
        scene_count: data.scene_count,
        scene_descriptions: state.enhancedBrief?.scenes?.length === sceneCountForFormat(format)
          ? state.enhancedBrief.scenes.map((scene) => scene.description)
          : [],
      }];
      data.visual_bible = state.enhancedBrief?.visual_bible || '';
      if (isSequenceFormat(format)) {
        data.context_design = collectContextDesign(data.scene_count);
        data.render_mode = 'native';
      }
      if (state.selectedVariationId) data.variation_id = state.selectedVariationId;
      data.campaign_pack = campaignPackPayload();
      data.first_step = {
        format_template_id: Number(format.id),
        mockup: clonePlacement(format).context || 'portal',
        scene_description: null,
      };
      try {
        const request = { method: 'POST', body: JSON.stringify(data) };
        const created = await apiFirst([
          { url: '/parametros/api/production-plans', options: request },
          { url: API.campaigns, options: request },
        ]);
        state.campaigns = await api(API.campaigns);
        const campaign = created.campaign || created;
        const production = created.production || created.productions?.[0] || null;
        if (production) state.productionByCampaign.set(String(campaign.id), production);
        await selectCampaign(campaign.id, production?.scenes?.[0]?.id || created.created_scene_id);
        seedSceneRefsFromPack();
        form.reset();
        state.enhancedBrief = null;
        resetCampaignPack();
        renderStoryboardEditor();
        renderContextDesign();
        renderClientPreview();
        renderGeneratorSummary();
        toast('Produção iniciada.', 'success');
        activateTab('produzir');
      } catch (error) {
        $('#mcCampaignFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  // ====== VARIAÇÕES ======
  async function selectCampaign(id, preferredSceneId = null) {
    if (!id) {
      state.campaign = null;
      state.production = null;
      renderWorkspace();
      return;
    }
    if (!state.campaign || String(state.campaign.id) !== String(id)) {
      setSceneRefFiles([]);
    }
    const preserveScene = state.campaign && String(state.campaign.id) === String(id)
      ? state.activeSceneId : null;
    const [campaign, assets, publicLinks] = await Promise.all([
      api(`${API.campaigns}/${id}`),
      api(`${API.campaigns}/${id}/assets`),
      api(`${API.campaigns}/${id}/public-collections`),
    ]);
    state.campaign = campaign;
    state.campaignAssets = assets;
    state.publicLinks = publicLinks;
    state.production = campaign.production
      || campaign.productions?.[0]
      || state.productionByCampaign.get(String(id))
      || null;
    if (state.production?.id) {
      try {
        state.production = await api(`/parametros/api/productions/${state.production.id}`);
      } catch (error) {
        if (error.status !== 404) toast(error.message, 'error');
      }
    }
    const scenes = productionScenes();
    state.activeSceneId = preferredSceneId || preserveScene || scenes[0]?.id || null;
    state.previewAssetId = state.production?.selected_asset_id
      || activeScene()?.preview_asset_id
      || activeScene()?.approved_asset_id
      || activeScene()?.assets?.find((asset) => asset.status === 'approved')?.id
      || sceneAssets(activeScene())[0]?.id
      || null;
    state.selectedAssets.clear();
    renderCampaignOptions();
    renderWorkspace();
  }

  function renderWorkspace() {
    const hasCampaign = Boolean(state.campaign);
    $('#mcVariationEmpty').classList.toggle('hidden', hasCampaign);
    $('#mcVariationWorkspace').classList.toggle('hidden', !hasCampaign);
    syncPublishTriggers();
    if (!hasCampaign) {
      syncShareTriggers();
      return;
    }
    const c = state.campaign;
    $('#mcCampaignBrief').innerHTML = `
      <strong>${escapeHtml(c.client.name)}</strong>
      <span>${escapeHtml(c.objective || 'Sem objetivo')}</span>
      <span>${escapeHtml(c.campaign_text || 'Sem mensagem principal')}</span>
      <em class="mc-campaign-cost" title="Soma de todas as IAs desta modelagem">${campaignCost(c)}</em>`;
    renderProduction();
    renderAssetPlan();
    syncShareTriggers();
  }

  function productionScenes() {
    return Array.isArray(state.production?.scenes) ? state.production.scenes : [];
  }

  function activeScene() {
    return productionScenes().find((scene) => String(scene.id) === String(state.activeSceneId));
  }

  function sceneAssets(scene) {
    return Array.isArray(scene?.assets) ? scene.assets.filter((asset) => asset.asset_type !== 'video') : [];
  }

  function assetUrl(asset) {
    return asset?.asset_url || asset?.url || asset?.preview_url || '';
  }

  function collectDraftPieces(productions, approvedOnly = false) {
    return (productions || []).flatMap((production) => {
      const format = state.formats.find((item) => String(item.id) === String(production.format_template_id));
      return (production.scenes || []).flatMap((scene) => (
        sceneAssets(scene)
          .filter((asset) => {
            if (assetFidelity(asset) === 'publish') return false;
            if (approvedOnly && asset.status !== 'approved') return false;
            return true;
          })
          .map((asset) => ({
            asset_id: asset.id,
            scene_id: scene.id,
            label: format?.name_pt || scene.description || `Cena ${scene.position || ''}`,
            size: format?.target_size || format?.default_size || '',
          }))
      ));
    });
  }

  function publishProductionsFor(campaignId) {
    if (state.campaign && String(state.campaign.id) === String(campaignId)) {
      return [state.production].filter(Boolean);
    }
    if (state.unfoldCampaign && String(state.unfoldCampaign.id) === String(campaignId)) {
      return state.unfoldCampaign.productions || [];
    }
    return [];
  }

  function syncPublishTriggers() {
    const produce = $('#mcOpenPublishBatch');
    if (produce) produce.hidden = true;
    const unfold = $('#mcUnfoldOpenPublish');
    if (unfold) unfold.hidden = !state.unfoldCampaign;
  }

  function renderPublishBatch(root, productions, campaignId) {
    if (!root) return;
    const drafts = collectDraftPieces(productions);
    if (!drafts.length || !campaignId) {
      root.innerHTML = '<p>Não há rascunhos para gerar em alta.</p>';
      return;
    }
    const key = String(campaignId);
    if (!state.publishPicks[key]) {
      state.publishPicks[key] = new Set(drafts.map((item) => String(item.asset_id)));
    } else {
      const valid = new Set(drafts.map((item) => String(item.asset_id)));
      Array.from(state.publishPicks[key]).forEach((id) => {
        if (!valid.has(id)) state.publishPicks[key].delete(id);
      });
    }
    const picks = state.publishPicks[key];
    const selected = drafts.filter((item) => picks.has(String(item.asset_id)));
    const total = selected.length * publishUnitBrl();
    root.innerHTML = `
      <p>Os rascunhos saem em low/1K. A alta (high/2K) só roda neste lote, sem mudar a montagem.</p>
      <ul class="mc-publish-list">
        ${drafts.map((item) => `
          <li>
            <label>
              <input type="checkbox" data-publish-asset="${item.asset_id}" data-publish-campaign="${campaignId}" ${picks.has(String(item.asset_id)) ? 'checked' : ''}>
              <span>${escapeHtml(item.label)}${item.size ? ` · ${escapeHtml(item.size)}` : ''}</span>
            </label>
          </li>`).join('')}
      </ul>
      <p class="mc-publish-quote"><strong>${selected.length} peça${selected.length === 1 ? '' : 's'} · ${brl(total)}</strong></p>
      <button class="cx-btn cx-btn-primary" type="button" data-publish-batch="${campaignId}" ${selected.length ? '' : 'disabled'}>
        Gerar publicáveis
      </button>`;
  }

  function openPublishModal(productions, campaignId) {
    if (!campaignId) {
      toast('Escolha uma campanha ativa.', 'warning');
      return;
    }
    state.publishModalCampaignId = campaignId;
    renderPublishBatch($('#mcPublishBatch'), productions, campaignId);
    $('#mcPublishDialog')?.showModal();
  }

  function refreshPublishModal() {
    const dialog = $('#mcPublishDialog');
    const campaignId = state.publishModalCampaignId;
    if (!dialog?.open || !campaignId) return;
    renderPublishBatch($('#mcPublishBatch'), publishProductionsFor(campaignId), campaignId);
  }

  async function publishSelectedBatch(button) {
    const campaignId = button.dataset.publishBatch;
    const assetIds = Array.from(state.publishPicks[String(campaignId)] || []);
    if (!campaignId || !assetIds.length) {
      toast('Selecione ao menos um rascunho.', 'warning');
      return;
    }
    await withLock(`publish-${campaignId}`, button, async () => {
      await api(`${API.campaigns}/${campaignId}/publish`, {
        method: 'POST',
        body: JSON.stringify({ asset_ids: assetIds.map(Number) }),
      });
      toast('Versões publicáveis geradas.', 'success');
      if (state.unfoldCampaign && String(state.unfoldCampaign.id) === String(campaignId)) {
        state.unfoldCampaign = await api(`${API.campaigns}/${campaignId}`);
        renderUnfoldPieces(state.unfoldCampaign);
      }
      if (state.campaign && String(state.campaign.id) === String(campaignId)) {
        await selectCampaign(campaignId, state.activeSceneId);
      }
      syncPublishTriggers();
      refreshPublishModal();
    });
  }

  function renderProduction() {
    const scenes = productionScenes();
    const status = state.production?.status || (scenes.length ? 'Em produção' : 'Aguardando cenas');
    $('#mcProductionState').textContent = status;
    $('#mcSceneRail').innerHTML = scenes.map((scene, index) => {
      const assets = sceneAssets(scene);
      const thumb = assets.find((asset) => asset.status === 'approved') || assets[0];
      const approved = Boolean(thumb && thumb.status === 'approved') || scene.status === 'approved';
      return `
        <button type="button" class="mc-scene-stop ${String(scene.id) === String(state.activeSceneId) ? 'is-active' : ''} ${approved ? 'is-approved' : ''}"
                data-scene-id="${scene.id}" aria-current="${String(scene.id) === String(state.activeSceneId) ? 'step' : 'false'}">
          <span class="mc-scene-thumb">${thumb
            ? `<img src="${escapeHtml(assetUrl(thumb))}" alt="">`
            : `<i>${index + 1}</i>`}</span>
          <span><strong>${escapeHtml(formatBeat(activeProductionFormat(), index + 1)?.label || `Cena ${index + 1}`)}</strong><small>${escapeHtml(scene.description || (approved ? 'Imagem aprovada' : 'Em preparação'))}</small></span>
        </button>`;
    }).join('') || '<div class="mc-scene-rail-empty">Esta campanha ainda não possui cenas.</div>';
    renderContinuitySpine();
    renderSceneReview(activeScene());
    syncPublishTriggers();
    refreshPublishModal();
    renderProductionViewer();
    renderProductionStage();
  }

  function campaignBible() {
    return state.campaign?.creative_brief?.visual_bible || '';
  }

  function campaignCopySystem() {
    return state.campaign?.client?.brand_profile?.creative_line?.copy_system || null;
  }

  function renderContextSpine(beats = []) {
    const design = campaignContextDesign();
    if (!design.scenes && !design.cast_count) return '';
    const people = Number(design.cast_count) === 2 ? '2 pessoas' : '1 pessoa';
    const set = design.scenography === 'change' ? 'Set muda a cada cena' : 'Mesma linha de set';
    const scenes = design.scenes || [];
    return `
      <div class="mc-context-spine">
        <span>Engenheiro de contexto</span>
        <p>${escapeHtml(people)}${design.cast_lock ? ' travadas' : ''} · ${design.product_lock !== false ? 'mesmo produto' : 'produto livre'} · ${escapeHtml(set)}</p>
        ${scenes.length ? `<ol>${scenes.map((item, index) => {
          const beat = beats[index] || {};
          return `<li><strong>${escapeHtml(beat.label || `Cena ${item.position}`)}</strong> ${item.copy_on_frame ? 'com copy' : 'só foto'}${item.set_note ? ` · ${escapeHtml(item.set_note)}` : ''}${item.action_note ? ` · ${escapeHtml(item.action_note)}` : ''}</li>`;
        }).join('')}</ol>` : ''}
      </div>`;
  }

  function renderContinuitySpine() {
    const root = $('#mcContinuitySpine');
    if (!root) return;
    const format = activeProductionFormat();
    const copy = campaignCopySystem();
    const zones = copy?.placement
      ? ['logo', 'headline', 'product', 'cta']
          .map((key) => {
            const zone = copy.placement[key];
            if (!zone?.anchor && !zone?.prose) return '';
            return `<li><strong>${escapeHtml(key)}</strong> ${escapeHtml(zone.anchor || '')} ${escapeHtml(zone.prose || '')}</li>`;
          })
          .filter(Boolean)
          .join('')
      : '';
    const direction = formatDirection(format);
    const beats = direction.beats || [];
    const offer = state.campaign?.campaign_text || state.campaign?.creative_brief?.campaign_pack?.extracted?.headline || '';
    root.innerHTML = `
      <p>Ficha do formato</p>
      <strong>${escapeHtml(state.campaign?.name || 'Campanha')}</strong>
      <small>${escapeHtml(format.name_pt || format.mechanic || 'Formato')}</small>
      ${direction.size_label ? `<p class="mc-spine-size">${escapeHtml(direction.size_label)}</p>` : ''}
      ${offer ? `<p class="mc-spine-brief">${escapeHtml(offer)}</p>` : ''}
      <details class="mc-bench-ficha">
        <summary>Modelagem e bíblia</summary>
        ${direction.layout?.summary ? `<p class="mc-spine-layout">${escapeHtml(direction.layout.summary)}</p>` : ''}
        ${renderFormatSlotMap(format)}
        ${renderFormatElementChips(format)}
        ${campaignBible() ? `<blockquote>${escapeHtml(campaignBible())}</blockquote>` : '<blockquote>Bíblia visual ainda não registrada.</blockquote>'}
        ${renderContextSpine(beats)}
        ${beats.length ? `<ol class="mc-beat-plan">${beats.map((beat) => `<li><strong>${escapeHtml(beat.label)}</strong> ${escapeHtml(beat.job)}</li>`).join('')}</ol>` : ''}
        <dl>
          ${direction.elements?.length
            ? (direction.elements.some((item) => item.key === 'cta' && item.present)
              ? `<div><dt>CTA</dt><dd>${escapeHtml(state.campaign?.cta_text || 'Sem texto de CTA')}</dd></div>`
              : '<div><dt>CTA</dt><dd>Este formato não tem</dd></div>')
            : `<div><dt>CTA</dt><dd>${escapeHtml(state.campaign?.cta_text || 'Sem CTA')}</dd></div>`}
          <div><dt>Mecânica</dt><dd>${escapeHtml(direction.behavior || format.mechanic || 'imagem')}</dd></div>
        </dl>
        ${copy ? `<div class="mc-spine-copy">
          <span>Sistema de copy</span>
          ${copy.headline_structure ? `<p>${escapeHtml(copy.headline_structure)}</p>` : ''}
          ${copy.cta?.visual_pattern ? `<p>${escapeHtml(copy.cta.visual_pattern)}${copy.cta.confidence === 'hypothesis' ? ' · hipótese' : ''}</p>` : ''}
          ${zones ? `<ul>${zones}</ul>` : ''}
        </div>` : ''}
      </details>`;
  }

  function campaignPackPayload() {
    return {
      sources: state.campaignPack.sources || [],
      extracted: state.campaignPack.extracted || {},
      locks: state.campaignPack.locks || {},
    };
  }

  function collectPrepareLocks(data = {}) {
    const extracted = state.campaignPack.extracted || {};
    const headline = String(extracted.headline || data.campaign_text || '').trim();
    const offer = String(extracted.offer || extracted.subhead || '').trim();
    const cta = String(extracted.cta || data.cta_text || '').trim();
    const statusOf = (text) => (text ? 'seen' : 'absent');
    return {
      headline,
      subhead: offer,
      cta,
      has_logo: extracted.has_logo !== false,
      items: {
        headline: { text: headline, status: statusOf(headline) },
        offer: { text: offer, status: statusOf(offer) },
        cta: { text: cta, status: statusOf(cta) },
      },
    };
  }

  function fillPrepareModels() {
    const select = $('#mcPrepareModel');
    const models = state.unfoldPaths?.models;
    if (!select || !models?.length) return;
    const current = select.value;
    select.innerHTML = models.map((model) => (
      `<option value="${escapeHtml(model.id)}">${escapeHtml(model.label)}</option>`
    )).join('');
    select.value = models.some((model) => model.id === current)
      ? current
      : (prepareEngine() === 'construct'
        ? 'black-forest-labs/flux.2-pro'
        : 'openai/gpt-image-2');
  }

  async function quotePreparePath() {
    const box = $('#mcPrepareQuote');
    if (!box) return;
    const format = generatorSelectedFormat();
    const sceneCount = format ? sceneCountForFormat(format) : 0;
    const engine = prepareEngine();
    const fallback = () => {
      box.querySelector('strong').textContent = 'R$ 0,00';
      const detail = $('#mcPrepareQuoteDetail');
      if (detail) {
        detail.textContent = format
          ? 'Não foi possível cotar este lote.'
          : 'Marque o formato para ver o lote.';
      }
    };
    if (!format || !sceneCount) {
      fallback();
      return;
    }
    try {
      const quoted = await api(API.unfoldQuote, {
        method: 'POST',
        body: JSON.stringify({
          engine,
          scene_pack: preparePack(),
          scene_count: sceneCount,
          image_model: $('#mcPrepareModel')?.value,
          fidelity: engine === 'construct' ? 'publish' : 'draft',
          format_slugs: [format.slug].filter(Boolean),
          format_ids: [format.id],
        }),
      });
      box.querySelector('strong').textContent = brl(quoted.total_brl);
      const detail = $('#mcPrepareQuoteDetail');
      if (detail) {
        const verb = engine === 'construct'
          ? 'montadas. Logo e texto entram depois da foto'
          : 'pintadas';
        detail.textContent = `${sceneCount} ${sceneCount === 1 ? 'batida' : 'batidas'} ${verb}`;
      }
    } catch (error) {
      fallback();
    }
  }

  function resetCampaignPack() {
    (state.campaignPack.previewUrls || []).forEach((url) => URL.revokeObjectURL(url));
    state.campaignPack = { files: [], url: '', extracted: {}, sources: [], previewUrls: [], locks: {} };
    const urlInput = $('#mcCampaignPackUrl');
    if (urlInput) urlInput.value = '';
    const status = $('#mcCampaignPackStatus');
    if (status) status.textContent = '';
    renderCampaignPackPreviews();
  }

  function renderCampaignPackPreviews() {
    const root = $('#mcCampaignPackPreviews');
    if (!root) return;
    root.innerHTML = state.campaignPack.files.map((file, index) => `
      <article>
        <img src="${escapeHtml(state.campaignPack.previewUrls[index] || '')}" alt="${escapeHtml(file.name)}">
        <button type="button" data-pack-remove="${index}">Remover</button>
      </article>
    `).join('');
  }

  function acceptCampaignPackFiles(files) {
    const accepted = Array.from(files || []).filter(
      (file) => /^image\/(png|jpeg|webp)$/.test(file.type) && file.size <= 5 * 1024 * 1024,
    );
    if (!accepted.length) {
      toast('Use PNG, JPG ou WEBP de até 5 MB.', 'warning');
      return;
    }
    (state.campaignPack.previewUrls || []).forEach((url) => URL.revokeObjectURL(url));
    state.campaignPack.files = [...state.campaignPack.files, ...accepted].slice(0, 4);
    state.campaignPack.previewUrls = state.campaignPack.files.map((file) => URL.createObjectURL(file));
    renderCampaignPackPreviews();
    readCampaignPack().catch((error) => toast(error.message, 'warning'));
    if (accepted.length !== Array.from(files || []).length) {
      toast('Algumas imagens foram ignoradas. Use PNG, JPG ou WEBP de até 5 MB.', 'warning');
    }
  }

  async function readCampaignPack({ url } = {}) {
    const pageUrl = (url ?? $('#mcCampaignPackUrl')?.value ?? state.campaignPack.url ?? '').trim();
    state.campaignPack.url = pageUrl;
    if (!state.campaignPack.files.length && !pageUrl) return null;
    const status = $('#mcCampaignPackStatus');
    if (status) status.textContent = 'Lendo os criativos desta campanha…';
    const body = new FormData();
    state.campaignPack.files.forEach((file) => body.append('images', file));
    if (pageUrl) body.append('page_url', pageUrl);
    try {
      const data = await api(API.readPack, { method: 'POST', body });
      state.campaignPack.extracted = data?.extracted || data?.campaign_pack?.extracted || {};
      state.campaignPack.sources = data?.campaign_pack?.sources || [];
      state.campaignPack.locks = data?.locks || data?.campaign_pack?.locks || {};
      const extracted = state.campaignPack.extracted;
      const bits = [extracted.headline, extracted.cta, extracted.offer].filter(Boolean);
      if (status) status.textContent = bits.length
        ? bits.slice(0, 2).join(' · ')
        : 'Pacote recebido. Gere o roteiro.';
      const form = $('#mcCampaignForm');
      if (extracted.cta && form?.elements.cta_text && !form.elements.cta_text.value.trim()) {
        form.elements.cta_text.value = extracted.cta;
      }
      return data;
    } catch (error) {
      if (status) status.textContent = 'Não deu para ler o pack. A mensagem ainda vale.';
      throw error;
    }
  }

  function sceneReferenceFiles() {
    if (state.sceneRefFiles.length) return state.sceneRefFiles;
    return (state.campaignPack.files || []).slice(0, 2);
  }

  function sceneReferencePreviewUrls() {
    if (state.sceneRefFiles.length) return state.sceneRefPreviewUrls;
    return (state.campaignPack.previewUrls || []).slice(0, 2);
  }

  function setSceneRefFiles(files) {
    (state.sceneRefPreviewUrls || []).forEach((url) => URL.revokeObjectURL(url));
    state.sceneRefFiles = Array.from(files || []).slice(0, 2);
    state.sceneRefPreviewUrls = state.sceneRefFiles.map((file) => URL.createObjectURL(file));
  }

  function seedSceneRefsFromPack() {
    if (state.sceneRefFiles.length || !state.campaignPack.files.length) return;
    setSceneRefFiles(state.campaignPack.files.slice(0, 2));
  }

  function sceneReferenceEmptyState(index) {
    const files = sceneReferenceFiles();
    const previews = sceneReferencePreviewUrls();
    if (files.length) {
      return `
        <div class="mc-scene-assets-empty">
          <div class="mc-scene-ref-previews">${previews.map((url, offset) => `
            <img src="${escapeHtml(url)}" alt="${escapeHtml(files[offset]?.name || `Referência ${offset + 1}`)}">
          `).join('')}</div>
          <p>Referência da cena ${index + 1} pronta. Solte outra imagem para trocar.</p>
        </div>`;
    }
    return `
      <div class="mc-scene-assets-empty">
        <p>Arraste uma referência desta campanha</p>
        <small>Até duas imagens. Elas entram na geração desta cena.</small>
      </div>`;
  }

  function syncSceneRefInput() {
    const input = $('#mcImageReferences');
    if (!input) return;
    const transfer = new DataTransfer();
    sceneReferenceFiles().forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
  }

  function acceptSceneReferences(files) {
    const accepted = Array.from(files || []).filter(
      (file) => /^image\/(png|jpeg|webp)$/.test(file.type) && file.size <= 5 * 1024 * 1024,
    );
    if (!accepted.length) {
      toast('Use PNG, JPG ou WEBP de até 5 MB.', 'warning');
      return;
    }
    setSceneRefFiles(accepted);
    const scene = activeScene();
    if (scene) renderSceneReview(scene);
    else syncSceneRefInput();
  }

  function setupSceneReferenceDrop() {
    const root = $('#mcSceneReview');
    if (!root || root.dataset.refDropBound) return;
    root.dataset.refDropBound = '1';
    const mark = (on) => root.querySelector('.mc-scene-dropzone')?.classList.toggle('is-dragging', on);
    ['dragenter', 'dragover'].forEach((type) => root.addEventListener(type, (event) => {
      if (![...((event.dataTransfer && event.dataTransfer.types) || [])].includes('Files')) return;
      event.preventDefault();
      mark(true);
    }));
    root.addEventListener('dragleave', (event) => {
      if (event.relatedTarget && root.contains(event.relatedTarget)) return;
      mark(false);
    });
    root.addEventListener('drop', (event) => {
      event.preventDefault();
      mark(false);
      if (event.dataTransfer?.files?.length) acceptSceneReferences(event.dataTransfer.files);
    });
    root.addEventListener('click', (event) => {
      if (event.target.closest('[data-scene-action], button, a, textarea, input, summary, label')) return;
      if (!event.target.closest('.mc-scene-dropzone')) return;
      $('#mcImageReferences')?.click();
    });
    root.addEventListener('change', (event) => {
      if (event.target.id !== 'mcImageReferences') return;
      acceptSceneReferences(event.target.files);
    });
  }

  function renderSceneReview(scene) {
    const root = $('#mcSceneReview');
    if (!scene) {
      root.innerHTML = '<div class="cx-empty-state"><p>Esta produção ainda não possui cenas.</p></div>';
      return;
    }
    const scenes = productionScenes();
    const index = scenes.findIndex((item) => String(item.id) === String(scene.id));
    const assets = sceneAssets(scene);
    const prompt = scene.rendered_prompt || scene.prompt || '';
    const hasPrompt = Boolean(prompt.trim());
    const format = activeProductionFormat();
    const beat = formatBeat(format, index + 1);
    const hero = assets.find((asset) => String(asset.id) === String(state.previewAssetId))
      || assets.find((asset) => asset.status === 'approved')
      || assets[0];
    const size = parseDefaultSize(
      formatDirection(format).target_size || format.default_size || format.target_size,
    );
    const renderMode = activeRenderMode();
    const briefLock = state.campaign?.campaign_text
      || state.campaign?.creative_brief?.campaign_pack?.extracted?.headline
      || '';
    const directionActions = [
      ['refine-logo', 'Colocar logo'],
      ['refine-remove-cta', 'Tirar CTA'],
      ['refine-remove-lines', 'Tirar linhas'],
      ['refine-ai-look', 'Tirar cara de IA'],
      ['refine-brand', 'Manter a marca'],
      ['refine-chrome', 'Limpar chrome'],
      ['refine-geometry', 'Recentrar'],
    ];
    const frameStyle = size
      ? `--frame-w:${size.w};--frame-h:${size.h};aspect-ratio:${size.w}/${size.h}`
      : '';
    const hasRoteiro = scene.prompt_status === 'approved' || hasPrompt;
    const hasEdit = assets.some((asset) => asset.metadata?.refinement_instruction);
    const canIterateMockup = renderMode === 'mockup'
      && hasRoteiro
      && Boolean(hero)
      && hero.status !== 'approved'
      && !hasEdit;
    const waitsPrevious = campaignConstruct() && !previousSceneApproved(scenes, index);
    const hold = publishHold(hero);
    const caption = layerCaption(hero);
    const canRetryLayer = Boolean(hero) && hero.status !== 'approved' && (
      Boolean(hold) || hero.metadata?.needs_retry
    );
    root.innerHTML = `
      <header class="mc-scene-review-head">
        <div>
          <span>${escapeHtml(beat?.label || `Cena ${index + 1}`)} ${index + 1} de ${scenes.length}</span>
          <p class="mc-scene-px">${escapeHtml(formatSizeLabel(format))}${formatOrientationLabel(format) ? ` ${escapeHtml(formatOrientationLabel(format))}` : ''}</p>
          <h3>${escapeHtml(beat?.job || scene.description || `Cena ${index + 1}`)}</h3>
        </div>
        ${statusBadge(scene.status || scene.prompt_status || 'draft')}
      </header>
      <section class="mc-scene-delta">
        <p class="mc-scene-story">${escapeHtml(scene.description || beat?.job || 'Sem roteiro desta batida.')}</p>
        ${briefLock ? `<p class="mc-scene-lock">${escapeHtml(briefLock)}</p>` : ''}
        <textarea class="cx-textarea" id="mcSceneDelta" rows="2" placeholder="Ajuste só se esta batida precisar furar o roteiro."></textarea>
        <details class="mc-scene-direction">
          <summary>Direção</summary>
          <textarea class="cx-textarea" id="mcPromptEditor" rows="6" placeholder="Gere ou escreva a direção desta cena">${escapeHtml(prompt)}</textarea>
          <div class="mc-inspector-actions">
            ${!hasPrompt ? '<button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-scene-action="generate-prompt">Gerar roteiro desta cena</button>' : ''}
            ${hasPrompt && scene.prompt_status !== 'approved' ? '<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-scene-action="approve-prompt">Aprovar direção</button>' : ''}
            <button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-scene-action="save-prompt">Salvar</button>
          </div>
        </details>
      </section>
      <section class="mc-scene-frame">
        <div class="mc-scene-frame-toolbar">
          <div class="mc-render-mode" role="group" aria-label="Modo de render">
            <button type="button" data-render-mode="native" class="${renderMode === 'native' ? 'is-active' : ''}">Peça nativa</button>
            <button type="button" data-render-mode="mockup" class="${renderMode === 'mockup' ? 'is-active' : ''}">Mockup</button>
          </div>
          <p class="mc-frame-meta">${escapeHtml(formatSizeLabel(format) || 'Retângulo do formato')}</p>
        </div>
        <figure class="mc-native-frame${!hero ? ' mc-scene-dropzone' : ''}" style="${frameStyle}" ${!hero ? 'tabindex="0"' : ''}>
          ${hero
            ? `<img src="${escapeHtml(assetUrl(hero))}" alt="Imagem gerada da cena ${index + 1}">`
            : sceneReferenceEmptyState(index)}
        </figure>
        ${caption || hold ? `<p class="mc-layer-note">${escapeHtml(hold || caption)}</p>` : ''}
        <div class="mc-scene-frame-actions">
          ${hero ? `
            ${statusBadge(hero.status || 'review')}
            <span class="mc-fidelity-chip ${assetFidelity(hero) === 'publish' ? 'is-publish' : 'is-draft'}">${assetFidelity(hero) === 'publish' ? 'Publicável' : 'Rascunho'}</span>
            ${canRetryLayer ? '<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-scene-action="generate-image">Gerar de novo</button>' : ''}
            ${canIterateMockup && !canRetryLayer ? '<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-scene-action="generate-image">Gerar outra</button>' : ''}
          ` : waitsPrevious ? `
            <p class="mc-layer-note">Aprove a batida anterior primeiro. Esta cena herda a foto aprovada.</p>
            <button class="cx-btn cx-btn-primary" type="button" data-scene-action="confirm-generate" disabled>
              Confirmar e gerar
            </button>
          ` : `
            <button class="cx-btn cx-btn-primary" type="button" data-scene-action="confirm-generate">
              Confirmar e gerar
            </button>
            <label class="mc-reference-upload">
              <input id="mcImageReferences" type="file" accept=".png,.jpg,.jpeg,.webp" multiple>
              <i class="fa-solid fa-paperclip" aria-hidden="true"></i>
              <span>${sceneReferenceFiles().length
                ? `${sceneReferenceFiles().length} referência${sceneReferenceFiles().length === 1 ? '' : 's'}`
                : 'Referência da cena'}</span>
            </label>
          `}
        </div>
      </section>
      ${hero ? `
      <section class="mc-scene-adjust">
        <div class="mc-refine-bar">
          <strong>Direção visual</strong>
          <div class="mc-refine-intents">
            ${directionActions.map(([action, label]) => `
              <button type="button" data-scene-action="${action}" data-asset-id="${hero.id}">${escapeHtml(label)}</button>
            `).join('')}
          </div>
          <input class="cx-input" id="mcRefineInstruction" maxlength="400" placeholder="Uma linha: o que mudar nesta imagem">
          <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-scene-action="refine-asset" data-asset-id="${hero.id}">Ajustar imagem</button>
        </div>
        <div class="mc-scene-decide">
          ${hero.status === 'approved'
            ? `<button class="cx-btn cx-btn-secondary" type="button" data-scene-action="choose-preview" data-asset-id="${hero.id}">Simular esta</button>`
            : `<button class="cx-btn cx-btn-primary" type="button" data-scene-action="approve-asset" data-asset-id="${hero.id}">Aprovar</button>
               <button class="cx-btn cx-btn-outline" type="button" data-scene-action="reject-asset" data-asset-id="${hero.id}">Rejeitar</button>`}
          <button class="cx-btn cx-btn-ghost" type="button" data-scene-action="edit-asset" data-asset-id="${hero.id}">Editar</button>
        </div>
        ${hero.metadata?.source_job_prompt || hero.metadata?.refinement_instruction ? `
          <details class="mc-asset-history">
            <summary>Histórico do asset</summary>
            ${hero.metadata?.source_job_prompt ? `<pre>${escapeHtml(hero.metadata.source_job_prompt)}</pre>` : ''}
            ${hero.metadata?.refinement_instruction ? `<p>${escapeHtml(hero.metadata.refinement_instruction)}</p>` : ''}
          </details>` : ''}
      </section>` : ''}
      ${assets.length > 1 ? `<div class="mc-scene-assets">${assets.map((asset) => `
        <article class="mc-scene-asset ${String(asset.id) === String(hero?.id) ? 'is-preview' : ''}">
          <img src="${escapeHtml(assetUrl(asset))}" alt="Variante da cena ${index + 1}">
          ${asset.metadata?.refinement_instruction ? `<p class="mc-asset-delta">${escapeHtml(asset.metadata.refinement_instruction)}</p>` : ''}
          <div>
            ${statusBadge(asset.status || 'review')}
            <span class="mc-fidelity-chip ${assetFidelity(asset) === 'publish' ? 'is-publish' : 'is-draft'}">${assetFidelity(asset) === 'publish' ? 'Publicável' : 'Rascunho'}</span>
            ${asset.status === 'approved'
              ? `<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-scene-action="choose-preview" data-asset-id="${asset.id}">Simular esta</button>`
              : `<button class="cx-btn cx-btn-primary cx-btn-sm" type="button" data-scene-action="approve-asset" data-asset-id="${asset.id}">Aprovar</button>
                 <button class="cx-btn cx-btn-outline cx-btn-sm" type="button" data-scene-action="reject-asset" data-asset-id="${asset.id}">Rejeitar</button>`}
          </div>
        </article>`).join('')}</div>` : ''}`;
    syncSceneRefInput();
  }

  function renderProductionViewer() {
    const select = $('#mcProductionViewer');
    if (!select) return;
    const context = activeProductionFormat()?.placement_spec?.context || 'portal';
    const profiles = viewerProfilesFor(context);
    const current = String(state.selectedViewerProfileId || '');
    select.innerHTML = profiles.map((profile) => `<option value="${profile.id}">${escapeHtml(profile.name)}</option>`).join('')
      || '<option value="">Ambiente padrão</option>';
    if (profiles.some((profile) => String(profile.id) === current)) select.value = current;
    else state.selectedViewerProfileId = Number(select.value) || null;
  }

  function activeProductionFormat() {
    const scene = activeScene();
    const formatId = scene?.format_template_id || state.production?.format_template_id;
    return state.formats.find((format) => String(format.id) === String(formatId)) || {};
  }

  function liveComposeCopy() {
    const campaign = state.campaign || {};
    const brief = campaign.creative_brief || {};
    const locks = brief.locks || {};
    const items = locks.items || {};
    const client = campaign.client || {};
    const omitCta = (items.cta || {}).status === 'absent';
    return {
      headline: locks.headline || campaign.campaign_text || '',
      cta: omitCta ? '' : (locks.cta || campaign.cta_text || ''),
      legal: (items.legal || {}).text || '',
      brandColor: brandPrimaryColor(client) || '#1E4D4F',
      logoUrl: client.logo_upload_path || client.logo_url || '',
    };
  }

  function assetCopyOnFrame(asset, format) {
    const design = campaignContextDesign();
    const position = Number(asset?.metadata?.scene_position || asset?.scene_position || 0);
    const saved = (design.scenes || []).find((item) => Number(item.position) === position);
    if (saved && saved.copy_on_frame != null) return Boolean(saved.copy_on_frame);
    const total = productionScenes().length;
    return isSequenceFormat(format) && position > 0 && position >= total;
  }

  function isLiveSequenceCompose(asset, format) {
    const meta = asset?.metadata || {};
    return campaignConstruct()
      && meta.composed
      && isSequenceFormat(format)
      && assetCopyOnFrame(asset, format)
      && Boolean(meta.source_raster || assetUrl(asset));
  }

  function liveStudioFrame(asset, format, index, activeIndex) {
    const active = index === activeIndex ? 'is-active' : '';
    if (!isLiveSequenceCompose(asset, format)) {
      return `<img class="${active}" data-production-carousel-image="${index}" src="${escapeHtml(assetUrl(asset))}" alt="Cena ${index + 1} aplicada ao ambiente">`;
    }
    const copy = liveComposeCopy();
    const still = (asset.metadata || {}).source_raster || assetUrl(asset);
    return `
      <article class="mc-html-ad mc-html-ad-sequence ${active}" data-production-carousel-image="${index}" style="--mc-ad-brand:${escapeHtml(copy.brandColor)}">
        <div class="mc-html-ad-visual"><img src="${escapeHtml(still)}" alt=""></div>
        ${copy.logoUrl ? `<img class="mc-html-ad-logo" src="${escapeHtml(copy.logoUrl)}" alt="">` : ''}
        <p class="mc-html-ad-headline">${escapeHtml(copy.headline)}</p>
        ${copy.legal ? `<small class="mc-html-ad-legal">${escapeHtml(copy.legal)}</small>` : ''}
        ${copy.cta ? `<span class="mc-html-ad-cta">${escapeHtml(copy.cta)}</span>` : ''}
      </article>`;
  }

  function renderProductionStage() {
    const root = $('#mcProductionStage');
    $$('[data-preview-device]').forEach((button) => {
      const active = button.dataset.previewDevice === state.previewDevice;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    if (state.productionCarouselTimer) {
      window.clearInterval(state.productionCarouselTimer);
      state.productionCarouselTimer = null;
    }
    const scene = activeScene();
    const allAssets = productionScenes().flatMap(sceneAssets);
    const approvedFrames = productionScenes().map((item) => (
      sceneAssets(item).find((asset) => asset.status === 'approved')
    )).filter(Boolean);
    const previewStatus = $('#mcProductionPreviewStatus');
    if (previewStatus) {
      previewStatus.textContent = approvedFrames.length
        ? `${approvedFrames.length} de ${productionScenes().length} cenas no carrossel`
        : 'O rascunho aparece aqui no ambiente';
    }
    const approved = allAssets.find((asset) => String(asset.id) === String(state.previewAssetId))
      || sceneAssets(scene).find((asset) => asset.status === 'approved')
      || sceneAssets(scene)[0];
    if (!approved) {
      root.innerHTML = '<div class="mc-production-stage-empty"><i class="fa-regular fa-image"></i><strong>Gere o rascunho</strong><p>A peça entra neste ambiente no retângulo do formato.</p></div>';
      return;
    }
    const format = activeProductionFormat();
    const pauseSequence = isSequenceFormat(format);
    const canonicalPlacement = clonePlacement(format);
    if (pauseSequence || canonicalPlacement.context === 'tv') {
      canonicalPlacement.context = 'tv';
      if (pauseSequence) {
        canonicalPlacement.viewport = { width: 1920, height: 1080 };
        canonicalPlacement.slot = { x: 3, y: 6, width: 94, height: 82 };
      }
    }
    const productionDeviceSwitch = $('.mc-production-preview-controls .mc-viewer-device-switch');
    productionDeviceSwitch?.classList.toggle(
      'hidden',
      canonicalPlacement.context === 'tv',
    );
    const placement = previewPlacement(canonicalPlacement, state.previewDevice, format);
    const profile = state.viewerProfiles.find((item) => String(item.id) === String(state.selectedViewerProfileId));
    const zone = placement.placement_zone;
    const iabSize = iabDisplaySize(format, state.previewDevice);
    const isPortalPage = placement.context !== 'tv';
    const isTvPause = placement.context === 'tv';
    const carouselAssets = [...approvedFrames];
    if (!carouselAssets.some((asset) => String(asset.id) === String(approved.id))) {
      carouselAssets.unshift(approved);
    }
    let activeCarouselIndex = Math.max(
      0,
      carouselAssets.findIndex((asset) => String(asset.id) === String(approved.id)),
    );
    const creativeStyle = isPortalPage
      ? `width:${iabSize.w}px;height:${iabSize.h}px`
      : `left:${placement.slot?.x || 10}%;top:${placement.slot?.y || 18}%;width:${placement.slot?.width || 76}%;height:${placement.slot?.height || 42}%`;
    root.innerHTML = `
      <div class="mc-production-device is-${escapeHtml(placement.context || 'portal')}${isTvPause ? ' is-pause is-playing' : ''}${isPortalPage ? ' is-page' : ''}"
           data-viewer="${escapeHtml(profile?.slug || 'automatico')}"
           data-layout="${escapeHtml(isTvPause ? 'pause' : (profile?.shell_spec?.layout || 'standard'))}"
           data-zone="${escapeHtml(zone || '')}"
           ${isPortalPage ? '' : `style="aspect-ratio:${Number(placement.viewport?.width) || 1920}/${Number(placement.viewport?.height) || 1080}"`}>
        <div class="mc-production-context">
          ${isTvPause
            ? tvPlaybackShellHtml(profile)
            : portalPageHtml(profile)}
        </div>
        <div class="mc-production-creative ${carouselAssets.length > 1 ? 'has-carousel' : ''}" style="${creativeStyle}">
          ${carouselAssets.map((asset, index) => liveStudioFrame(asset, format, index, activeCarouselIndex)).join('')}
          ${carouselAssets.length > 1 ? `<div class="mc-production-carousel-dots">${carouselAssets.map((asset, index) => `<button type="button" data-production-carousel-go="${index}" aria-label="Ver cena ${index + 1}" ${index === activeCarouselIndex ? 'aria-current="true"' : ''}></button>`).join('')}</div>` : ''}
        </div>
        <small>${escapeHtml(profile?.disclaimer || 'Simulação de ambiente')}</small>
      </div>`;
    if (isPortalPage) {
      const device = $('.mc-production-device', root);
      const palette = profile?.palette || {};
      if (device) {
        device.style.setProperty('--viewer-primary', safeViewerColor(palette.primary, '#1e4d4f'));
        device.style.setProperty('--viewer-secondary', safeViewerColor(palette.secondary, '#173436'));
        device.style.setProperty('--viewer-surface', safeViewerColor(palette.surface, '#ffffff'));
        device.style.setProperty('--viewer-canvas', safeViewerColor(palette.canvas, '#edf2f1'));
        device.style.setProperty('--viewer-text', safeViewerColor(palette.text, '#1f2937'));
      }
      mountNodeInZone($('.mc-production-context', root), $('.mc-production-creative', root), zone);
      const creative = $('.mc-production-creative', root);
      const pageWidth = state.previewDevice === 'mobile' ? 390 : 1280;
      const scale = Math.min(1, (device?.clientWidth || 576) / pageWidth);
      if (creative) {
        creative.style.width = `${Math.round(iabSize.w * scale)}px`;
        creative.style.height = `${Math.round(iabSize.h * scale)}px`;
      }
    }
    if (isTvPause) {
      armPauseAd($('.mc-production-device', root));
    }
    const showCarouselFrame = (nextIndex) => {
      activeCarouselIndex = (nextIndex + carouselAssets.length) % carouselAssets.length;
      $$('[data-production-carousel-image]', root).forEach((image, index) => {
        image.classList.toggle('is-active', index === activeCarouselIndex);
      });
      $$('[data-production-carousel-go]', root).forEach((dot, index) => {
        if (index === activeCarouselIndex) dot.setAttribute('aria-current', 'true');
        else dot.removeAttribute('aria-current');
      });
    };
    $$('[data-production-carousel-go]', root).forEach((dot) => {
      dot.addEventListener('click', () => {
        showCarouselFrame(Number(dot.dataset.productionCarouselGo));
      });
    });
    if (carouselAssets.length > 1 && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      state.productionCarouselTimer = window.setInterval(
        () => showCarouselFrame(activeCarouselIndex + 1),
        3600,
      );
    }
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
    const imageAssets = state.campaignAssets.filter((asset) => asset.asset_type !== 'video');
    strip.innerHTML = imageAssets.map((asset, index) => `
      <article class="mc-plan-asset" data-plan-asset-id="${asset.id}">
        <div class="mc-plan-preview">
          <img src="${escapeHtml(asset.asset_url)}" alt="${escapeHtml(asset.title || asset.format_name || 'Criativo')}">
          <span class="mc-plan-index">${index + 1}</span>
        </div>
        <div class="mc-plan-content">
          <input class="cx-input mc-asset-title" value="${escapeHtml(asset.title || asset.format_name || '')}" maxlength="200" aria-label="Título do criativo">
          <span class="mc-format-meta"><span>${escapeHtml(asset.default_size || asset.aspect_ratio || '')}</span>${statusBadge(asset.status)}</span>
          <div class="mc-inspector-actions">
            <button class="mc-icon-btn" type="button" data-action="asset-left" title="Mover à esquerda" ${index === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-left"></i></button>
            <button class="mc-icon-btn" type="button" data-action="asset-right" title="Mover à direita" ${index === imageAssets.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-right"></i></button>
            <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="save-asset-meta">Salvar</button>
            <button class="mc-icon-btn" type="button" data-action="delete-plan-asset" title="Excluir criativo"><i class="fa-solid fa-trash"></i></button>
          </div>
        </div>
      </article>`).join('') || '<div class="cx-empty-state"><p>Gere imagens para montar o plano de criativos.</p></div>';
    renderPublicLinks();
  }

  function publicLinkHref(link) {
    try {
      return new URL(link?.public_url || '', location.origin).href;
    } catch (_) {
      return String(link?.public_url || '');
    }
  }

  function activePublicLink() {
    return (state.publicLinks || []).find((link) => link.is_active) || null;
  }

  function openPublicLink(url) {
    const href = publicLinkHref({ public_url: url });
    if (href) window.open(href, '_blank', 'noopener');
    return href;
  }

  function syncShareTriggers() {
    const create = $('#mcCreatePublicLink');
    const open = $('#mcOpenPresentation');
    const canShare = Boolean(state.campaign && shareableCampaignAssets().length);
    const active = activePublicLink();
    if (create) {
      create.disabled = !canShare;
      create.innerHTML = active
        ? '<i class="fa-solid fa-link" aria-hidden="true"></i> Novo link'
        : '<i class="fa-solid fa-link" aria-hidden="true"></i> Criar link';
    }
    $$('.mc-open-share').forEach((button) => {
      button.disabled = !canShare;
    });
    if (open) {
      if (active) {
        open.hidden = false;
        open.href = publicLinkHref(active);
      } else {
        open.hidden = true;
        open.removeAttribute('href');
      }
    }
  }

  function renderPublicLinks() {
    const root = $('#mcPublicLinks');
    if (!root) return;
    root.innerHTML = state.publicLinks.length ? `
      <h3>Links publicados</h3>
      ${state.publicLinks.map((link) => `
        <div class="mc-public-link ${link.is_active ? '' : 'is-revoked'}">
          <span><strong>${escapeHtml(link.title)}</strong><small>${link.asset_count} criativos · ${link.is_active ? 'Ativo' : 'Revogado'}</small></span>
          <code>${escapeHtml(link.public_url)}</code>
          <div class="mc-inspector-actions">
            ${link.is_active ? `<a class="cx-btn cx-btn-primary cx-btn-sm" href="${escapeHtml(publicLinkHref(link))}" target="_blank" rel="noopener">Abrir</a><button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-action="copy-public-link" data-public-url="${escapeHtml(link.public_url)}">Copiar</button><button class="cx-btn cx-btn-danger cx-btn-sm" type="button" data-action="revoke-public-link" data-link-id="${link.id}">Revogar</button>` : ''}
          </div>
        </div>`).join('')}` : '';
    syncShareTriggers();
  }

  function shareableCampaignAssets() {
    const groups = new Map();
    state.campaignAssets
      .filter((asset) => asset.status === 'approved')
      .forEach((asset) => {
        const key = asset.production_id
          ? `production:${asset.production_id}`
          : `asset:${asset.id}`;
        if (!groups.has(key)) groups.set(key, asset);
      });
    return [...groups.values()];
  }

  function renderShareEnvironments() {
    const root = $('#mcShareEnvironmentList');
    if (!root) return;
    const assets = shareableCampaignAssets();
    root.innerHTML = assets.map((asset) => {
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
    }).join('') || '<span class="mc-section-note">Aprove imagens para montar os carrosséis compartilháveis.</span>';
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
  function formatExperienceIcon(format) {
    const type = format?.behavior_spec?.type;
    const icons = {
      hotspot: 'fa-location-dot',
      flip: 'fa-clone',
      reveal: 'fa-up-down',
      compare: 'fa-left-right',
      quiz: 'fa-circle-question',
      carousel: 'fa-images',
    };
    return icons[type] || 'fa-image';
  }

  function formatExperienceLabel(format) {
    const placement = format?.placement_spec || {};
    const environment = placement.context === 'tv'
      ? 'TV'
      : 'Portal desktop e mobile';
    return suggestedSceneCount(format) > 1
      ? `${suggestedSceneCount(format)} cenas · ${environment}`
      : `${format.default_size || format.aspect_ratio || 'Flexível'} · ${environment}`;
  }

  function renderLibrary() {
    const root = $('#mcFormatTableBody');
    if (!root) return;
    const formats = filteredFormats('#mcLibrarySearch', '#mcLibraryCategory');
    root.innerHTML = formats.map((format) => {
      const orientation = formatOrientationKey(format);
      const orientationLabel = formatOrientationLabel(format) || 'Quadrado';
      return `
      <button class="mc-catalog-format ${String(format.id) === String(state.selectedFormatId) ? 'is-active' : ''}"
              type="button" data-library-format="${format.id}">
        <span class="mc-catalog-format-icon" title="${escapeHtml(orientationLabel)}">
          <span class="mc-orient is-${orientation}" aria-hidden="true"></span>
          <span class="sr-only">${escapeHtml(orientationLabel)}</span>
        </span>
        <span>
          <strong>${escapeHtml(format.name_pt)}</strong>
          <small>${escapeHtml([
            format.iab_family,
            formatSizeLabel(format),
            format.iab_cousin ? `primo ${format.iab_cousin}` : '',
          ].filter(Boolean).join(' · ') || formatExperienceLabel(format))}</small>
        </span>
        <em>${suggestedSceneCount(format) > 1 ? 'Carrossel' : 'Estático'}</em>
      </button>`;
    }).join('') || '<div class="cx-empty-state"><p>Nenhum formato encontrado.</p></div>';
    renderLibraryVariations();
  }

  function clonePlacement(format) {
    const fallback = {
      context: format.channel && ['netflix', 'hbomax', 'disneyplus', 'primevideo'].includes(format.channel) ? 'tv' : 'portal',
      viewport: { width: 1280, height: 800 },
      slot: { x: 65, y: 20, width: 28, height: 38 },
      fit: 'contain',
      responsive: 'scale',
    };
    const spec = Object.keys(format.placement_spec || {}).length ? format.placement_spec : fallback;
    const result = JSON.parse(JSON.stringify(spec));
    if (!result.placement_zone) {
      const zone = format.placement_zone || resolvePlacementZone(format, result, 'desktop');
      if (zone) result.placement_zone = zone;
    }
    return result;
  }

  function resolvePlacementZone(format, placement, device = 'desktop') {
    if ((placement?.context || format?.placement_spec?.context) === 'tv') return null;
    const family = format?.iab_family || '';
    const slug = format?.slug || '';
    const size = parseDefaultSize(format?.default_size || format?.target_size);
    const saved = placement?.placement_zone;
    if (device === 'mobile' || slug === 'iab-mobile-banner' || (size && size.w === 320 && size.h === 50)) {
      if (family === 'wide_banner' || slug === 'iab-mobile-banner' || slug === 'iab-leaderboard' || (size && size.h <= 90)) {
        return 'sticky';
      }
    }
    if (saved && ['leaderboard', 'rail', 'in_feed', 'sticky'].includes(saved) && device !== 'mobile') {
      return saved;
    }
    if (family === 'wide_banner' || slug === 'iab-leaderboard' || (size && size.w === 728 && size.h === 90)) {
      return 'leaderboard';
    }
    if (family === 'half_page' || slug === 'iab-half-page' || (size && size.w === 300 && size.h === 600)) {
      return 'rail';
    }
    return 'in_feed';
  }

  function iabDisplaySize(format, device = 'desktop') {
    const size = parseDefaultSize(format?.default_size || format?.target_size);
    if (device === 'mobile' && (!size || size.h <= 90 || format?.iab_family === 'wide_banner')) {
      return { w: 320, h: 50 };
    }
    if (size) return size;
    return { w: 300, h: 250 };
  }

  function previewPlacement(placement, device = 'desktop', format = null) {
    const result = JSON.parse(JSON.stringify(placement));
    if (result.context === 'tv') return result;
    result.placement_zone = resolvePlacementZone(format, result, device);
    if (device === 'mobile') {
      result.context = 'celular';
      result.viewport = { width: 390, height: 844 };
      result.slot = result.placement_zone === 'sticky'
        ? { x: 5, y: 82, width: 90, height: 12 }
        : { x: 7, y: 28, width: 86, height: 36 };
      return result;
    }
    result.context = 'portal';
    result.viewport = { width: 1280, height: 800 };
    if (placement.context === 'celular') {
      result.slot = { x: 37.5, y: 82, width: 25, height: 8 };
    }
    return result;
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

  function netflixPauseShellHtml(profile) {
    return tvPlaybackShellHtml(profile);
  }

  function tvSceneImage(profile) {
    const hero = profile?.shell_spec?.hero || {};
    if (hero.image) return hero.image;
    return profile?.shell_spec?.sections?.[0]?.items?.[0]?.image || '';
  }

  function tvPlaybackShellHtml(profile) {
    const hero = profile?.shell_spec?.hero || {};
    const slug = profile?.slug || 'tv';
    const scene = tvSceneImage(profile);
    return `
      <div class="mc-tv-playback is-${escapeHtml(slug)}">
        <div class="mc-tv-scene" aria-hidden="true">
          ${scene ? `<img src="${escapeHtml(scene)}" alt="">` : ''}
          <div class="mc-tv-scene-grade"></div>
          <div class="mc-tv-now">
            <small>${escapeHtml(hero.eyebrow || 'Em reprodução')}</small>
            <strong>${escapeHtml(hero.title || 'Uma história para continuar assistindo')}</strong>
          </div>
        </div>
        <div class="mc-tv-player">
          <header>${viewerLogo(profile)}<span data-pause-state>Reproduzindo</span></header>
          <footer>
            <i class="fa-solid fa-pause" data-pause-icon></i>
            <time>12:04</time>
            <b class="mc-tv-progress"><i></i></b>
            <time>48:22</time>
            <i class="fa-solid fa-volume-high"></i>
            <i class="fa-solid fa-closed-captioning"></i>
            <i class="fa-solid fa-expand"></i>
          </footer>
        </div>
        <div class="mc-tv-pause-mark" data-pause-mark hidden>
          <i class="fa-solid fa-pause"></i>
        </div>
        <div class="mc-tv-pause-cue" data-pause-cue>
          <b data-pause-count>3</b>
          <span>O anúncio entra por cima da tela</span>
        </div>
      </div>`;
  }

  function clearPauseAdTimers() {
    if (state.pauseAdTimer) window.clearTimeout(state.pauseAdTimer);
    if (state.pauseAdInterval) window.clearInterval(state.pauseAdInterval);
    state.pauseAdTimer = null;
    state.pauseAdInterval = null;
  }

  function revealPauseAd(root) {
    if (!root) return;
    root.classList.remove('is-playing');
    root.classList.add('is-paused');
    const cue = root.querySelector('[data-pause-cue]');
    if (cue) cue.hidden = true;
    const label = root.querySelector('[data-pause-state]');
    if (label) label.textContent = 'Pausado';
    const icon = root.querySelector('[data-pause-icon]');
    if (icon) icon.className = 'fa-solid fa-play';
    const mark = root.querySelector('[data-pause-mark]');
    if (mark && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      mark.hidden = false;
      window.setTimeout(() => { mark.hidden = true; }, 420);
    }
  }

  function armPauseAd(root, delay = 3000) {
    if (!root) return;
    clearPauseAdTimers();
    root.classList.remove('is-paused');
    root.classList.add('is-playing');
    const cue = root.querySelector('[data-pause-cue]');
    const label = root.querySelector('[data-pause-state]');
    if (label) label.textContent = 'Reproduzindo';
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      revealPauseAd(root);
      return;
    }
    let left = Math.max(1, Math.round(delay / 1000));
    const tick = () => {
      if (!cue) return;
      cue.hidden = false;
      const count = cue.querySelector('[data-pause-count]');
      if (count) count.textContent = String(left);
    };
    tick();
    state.pauseAdInterval = window.setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearPauseAdTimers();
        revealPauseAd(root);
        return;
      }
      tick();
    }, 1000);
  }

  function viewerCatalogHtml(profile) {
    const sections = Array.isArray(profile?.shell_spec?.sections)
      && profile.shell_spec.sections.length
      ? profile.shell_spec.sections.slice(0, 3)
      : [{ title: 'Escolhas para você', items: [] }];
    return sections.map((section) => {
      const items = Array.isArray(section.items) ? section.items.slice(0, 8) : [];
      const fallback = Array.from({ length: 5 }, (_, index) => (
        `<article><b></b><span>Conteúdo ${index + 1}</span></article>`
      )).join('');
      return `
        <section class="mc-tv-catalog is-${escapeHtml(section.card_shape || 'landscape')} ${section.ranked ? 'is-ranked' : ''}">
          <strong>${escapeHtml(section.title || 'Escolhas para você')}</strong>
          <div class="mc-tv-rail" style="--catalog-count:${items.length || 5}">
            ${items.length ? items.map((item, index) => `
              <article>
                ${section.ranked ? `<i>${index + 1}</i>` : ''}
                ${item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : '<b></b>'}
                <span>${escapeHtml(item.title)}</span>
              </article>`).join('') : fallback}
          </div>
        </section>`;
    }).join('');
  }

  function portalEditorialItems(profile) {
    const items = [];
    (profile?.shell_spec?.sections || []).forEach((section) => {
      (section.items || []).forEach((item) => items.push(item));
    });
    return items;
  }

  function portalAdZoneHtml(zone, label = 'Publicidade') {
    return `<div class="mc-ad-zone is-${zone.replace('_', '-')}" data-ad-zone="${zone}"><small>${label}</small></div>`;
  }

  function portalPageHtml(profile) {
    const shell = profile?.shell_spec || {};
    const hero = shell.hero || {};
    const items = portalEditorialItems(profile);
    const highlights = items.slice(0, 2);
    const feed = items.slice(0, 4);
    const rail = items.slice(0, 3);
    const network = (shell.network_links || ['notícias', 'ao vivo', 'conta']).map(
      (item) => `<span>${escapeHtml(item)}</span>`,
    ).join('');
    const nav = (shell.nav || []).map(
      (item) => `<span>${escapeHtml(item)}</span>`,
    ).join('');
    const slug = profile?.slug || 'portal';
    const video = slug === 'sbt-news' ? `
      <article class="mc-portal-video">
        <div class="mc-portal-video-stage">
          ${hero.image ? `<img src="${escapeHtml(hero.image)}" alt="">` : ''}
          <i class="fa-solid fa-play"></i>
          <b>AO VIVO</b>
        </div>
        <small>${escapeHtml(hero.eyebrow || 'Ao vivo')}</small>
        <strong>${escapeHtml(hero.title || 'Edição ao vivo')}</strong>
      </article>` : '';
    return `
      <div class="mc-portal-page">
        <div class="mc-portal-network">${network}</div>
        <header class="mc-portal-masthead">
          <span><i class="fa-solid fa-bars"></i>${viewerLogo(profile)}</span>
          <b>${escapeHtml(shell.edition_label || profile?.name || 'Notícias')}</b>
          <i class="fa-solid fa-magnifying-glass"></i>
        </header>
        <nav class="mc-portal-nav">${nav}</nav>
        ${slug === 'cnn-brasil' ? `<div class="mc-portal-ticker"><b>Agora</b><span>${escapeHtml(hero.description || 'Edição contínua do noticiário')}</span></div>` : ''}
        ${portalAdZoneHtml('leaderboard')}
        <div class="mc-portal-body">
          <div class="mc-portal-main">
            ${video}
            <article class="mc-portal-lead">
              <small>${escapeHtml(hero.eyebrow || 'Destaque')}</small>
              <strong>${escapeHtml(hero.title || 'Manchete demonstrativa')}</strong>
              <span>${escapeHtml(hero.description || '')}</span>
            </article>
            <div class="mc-portal-highlights">${highlights.map((item) => `
              <article>
                ${item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : ''}
                <small>${escapeHtml(item.category || '')}</small>
                <strong>${escapeHtml(item.title || '')}</strong>
              </article>`).join('')}</div>
            ${portalAdZoneHtml('in_feed')}
            <section class="mc-portal-feed">
              <strong>Mais notícias</strong>
              ${feed.map((item) => `
                <article>
                  <span>${escapeHtml(item.category || '')}${item.time ? ` · ${escapeHtml(item.time)}` : ''}</span>
                  <b>${escapeHtml(item.title || '')}</b>
                  ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ''}
                </article>`).join('')}
            </section>
          </div>
          <aside class="mc-portal-rail">
            ${portalAdZoneHtml('rail')}
            <strong>Mais lidas</strong>
            ${rail.map((item, index) => `
              <article>
                <i>${index + 1}</i>
                <span>${escapeHtml(item.title || '')}</span>
              </article>`).join('')}
          </aside>
        </div>
        ${portalAdZoneHtml('sticky')}
      </div>`;
  }

  function g1PortalShellHtml(profile) {
    return portalPageHtml(profile);
  }

  function mountNodeInZone(root, node, zone) {
    if (!node) return;
    const host = zone && root ? root.querySelector(`[data-ad-zone="${zone}"]`) : null;
    root?.querySelectorAll('[data-ad-zone]').forEach((el) => {
      el.classList.toggle('is-active', el === host);
    });
    if (host) {
      host.appendChild(node);
      node.classList.add('is-in-zone');
      return;
    }
    node.classList.remove('is-in-zone');
    if (root && node.parentElement !== root) root.appendChild(node);
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
    frame.dataset.layout = profile.shell_spec?.layout || 'standard';
    frame.style.setProperty('--viewer-primary', safeViewerColor(palette.primary, '#1e4d4f'));
    frame.style.setProperty('--viewer-secondary', safeViewerColor(palette.secondary, '#173436'));
    frame.style.setProperty('--viewer-surface', safeViewerColor(palette.surface, '#ffffff'));
    frame.style.setProperty('--viewer-canvas', safeViewerColor(palette.canvas, '#edf2f1'));
    frame.style.setProperty('--viewer-text', safeViewerColor(palette.text, '#1f2937'));
    if (profile.viewer_kind === 'tv') {
      shell.innerHTML = tvPlaybackShellHtml(profile);
    } else {
      shell.innerHTML = portalPageHtml(profile);
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
        </button>`).join('')}</div>
      ${placement.context !== 'tv' ? `
        <div class="mc-viewer-device-switch" aria-label="Tamanho do portal">
          <button type="button" data-preview-device="desktop" class="${state.previewDevice === 'desktop' ? 'is-active' : ''}" aria-pressed="${state.previewDevice === 'desktop'}"><i class="fa-solid fa-desktop"></i> Desktop</button>
          <button type="button" data-preview-device="mobile" class="${state.previewDevice === 'mobile' ? 'is-active' : ''}" aria-pressed="${state.previewDevice === 'mobile'}"><i class="fa-solid fa-mobile-screen"></i> Mobile</button>
        </div>` : ''}`;
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
    if (type === 'carousel') return '<span class="mc-demo-carousel"><i></i><i></i><i></i><b>Sequência de imagens</b></span>';
    if (type === 'video') return '<span class="mc-demo-play"><i class="fa-solid fa-play"></i></span>';
    return '<span class="mc-demo-static">Criativo<br>da marca</span>';
  }

  function renderFormatStage(format, preserveDraft = false) {
    if (!format) return;
    if (!preserveDraft || !state.placementDraft) {
      state.placementDraft = clonePlacement(format);
      state.originalPlacement = clonePlacement(format);
      state.previewDevice = state.placementDraft.context === 'celular'
        ? 'mobile'
        : 'desktop';
    }
    const placement = state.placementDraft;
    const displayPlacement = previewPlacement(placement, state.previewDevice, format);
    const slot = displayPlacement.slot;
    const zone = displayPlacement.placement_zone;
    const iabSize = iabDisplaySize(format, state.previewDevice);
    $('#mcStageEmpty').classList.add('hidden');
    $('#mcFormatStage').classList.remove('hidden');
    $('#mcStageTitle').textContent = format.name_pt;
    const stageSize = parseDefaultSize(format.default_size || format.target_size);
    $('#mcStageMetrics').innerHTML = `
      <span>${escapeHtml(displayPlacement.context)}</span>
      <strong>${escapeHtml(formatSizeLabel(format))}</strong>
      ${format.iab_family ? `<span>${escapeHtml(format.iab_family)}</span>` : ''}
      ${zone ? `<span>${escapeHtml(zone)}</span>` : ''}
      ${stageSize ? `<small>${stageSize.w} px × ${stageSize.h} px</small>` : ''}`;
    $('#mcDeviceFrame').className = `mc-device-frame is-${escapeHtml(displayPlacement.context)}${zone ? ' is-page' : ''}`;
    if (displayPlacement.context === 'tv') {
      $('#mcDeviceFrame').style.aspectRatio = `${Number(displayPlacement.viewport.width) || 1280} / ${Number(displayPlacement.viewport.height) || 800}`;
    } else {
      $('#mcDeviceFrame').style.aspectRatio = state.previewDevice === 'mobile' ? '390 / 844' : '1280 / 800';
    }
    const profile = activeViewerProfile(format, placement);
    renderViewerToolbar(format, placement, profile);
    renderViewerShell(profile);
    const slotNode = $('#mcAdSlot');
    const frame = $('#mcDeviceFrame');
    frame.dataset.zone = zone || '';
    if (zone) {
      mountNodeInZone($('#mcViewerShell'), slotNode, zone);
      const scale = Math.min(1, (frame.clientWidth || 720) / (state.previewDevice === 'mobile' ? 390 : 1280));
      slotNode.style.width = `${Math.round(iabSize.w * scale)}px`;
      slotNode.style.height = `${Math.round(iabSize.h * scale)}px`;
      slotNode.style.left = '';
      slotNode.style.top = '';
      const original = state.originalPlacement?.slot || slot;
      const dx = (placement.slot?.x ?? original.x) - original.x;
      const dy = (placement.slot?.y ?? original.y) - original.y;
      slotNode.style.transform = (dx || dy) ? `translate(${dx}%, ${dy}%)` : '';
    } else {
      if (slotNode.parentElement !== frame) frame.appendChild(slotNode);
      slotNode.classList.remove('is-in-zone');
      slotNode.style.width = `${slot.width}%`;
      slotNode.style.height = `${slot.height}%`;
      slotNode.style.left = `${slot.x}%`;
      slotNode.style.top = `${slot.y}%`;
      slotNode.style.transform = '';
    }
    $('#mcAdSlotContent').innerHTML = adCreativeHtml(format);
    $('#mcAdSlotSize').textContent = `${iabSize.w} × ${iabSize.h} px`;
    if (displayPlacement.context === 'tv') {
      frame.classList.add('is-playing');
      armPauseAd(frame);
    } else {
      frame.classList.remove('is-playing', 'is-paused');
    }
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
            ${['static', 'hotspot', 'flip', 'reveal', 'compare', 'quiz', 'carousel'].map((value) => `<option value="${value}">${value}</option>`).join('')}
          </select></label>
          <label class="cx-field"><span class="cx-label">Acionamento</span><select class="cx-select" name="behavior_trigger">
            ${['none', 'hover_tap', 'click', 'drag_vertical', 'drag_horizontal', 'view', 'auto'].map((value) => `<option value="${value}">${value}</option>`).join('')}
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
          <span class="cx-help">O mockup usa o ambiente nativo modelado em desktop ou mobile. Formatos interativos usam quatro imagens complementares, exibidas como carrossel animado.</span>
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
  function selectedBrand() {
    return state.clients.find((client) => Number(client.id) === Number(state.selectedBrandId)) || null;
  }

  function resetBrandDraft() {
    state.brandAnalysis = null;
    state.brandAssetCandidates = [];
    state.selectedBrandAssets = new Set();
    state.primaryBrandAssetUrl = null;
    state.primaryBrandFileIndex = -1;
    state.brandFiles = [];
    renderBrandCandidates();
    renderDroppedBrandFiles();
    const summary = $('#mcBrandAnalysisSummary');
    if (summary) {
      summary.classList.add('hidden');
      summary.innerHTML = '';
    }
    renderBrandPalette([]);
    renderBrandInventory(null);
    const status = $('#mcClientFormStatus');
    if (status) status.textContent = '';
  }

  function fillBrandForm(client) {
    const form = $('#mcClientForm');
    if (!form) return;
    form.reset();
    const save = $('#mcClientSave');
    if (save) save.textContent = client ? 'Atualizar perfil' : 'Salvar perfil';
    if (!client) return;
    const profile = client.brand_profile || {};
    const line = brandLine(client);
    const guidelines = profile.creative_guidelines
      || [...(line.composition_rules || []), ...(line.must_preserve || [])].slice(0, 4).join(' ');
    [
      ['name', client.name],
      ['sector', client.sector],
      ['website_url', client.website_url],
      ['logo_url', client.logo_url],
      ['primary_color', brandPrimaryColor(client)],
      ['secondary_color', brandSecondaryColor(client)],
      ['tone_of_voice', brandTone(client)],
      ['brand_summary', brandSummary(client)],
      ['target_audience', profile.target_audience],
      ['creative_guidelines', guidelines],
      ['ad_segments_text', (profile.ad_segments || []).join('\n')],
      ['campaign_opportunities_text', (profile.campaign_opportunities || []).join('\n')],
      ['products_services_text', (profile.products_services || []).join('\n')],
      ['differentiators_text', (profile.differentiators || []).join('\n')],
      ['proof_points_text', (profile.proof_points || []).join('\n')],
      ['visual_motifs_text', (profile.visual_motifs || line.graphic_devices || []).join('\n')],
      ['mandatory_elements_text', (profile.mandatory_elements || []).join('\n')],
      ['forbidden_elements_text', (profile.forbidden_elements || line.avoid || []).join('\n')],
    ].forEach(([name, value]) => setFormValue(form, name, value));
    if (form.elements.show_price) {
      form.elements.show_price.checked = client.price_policy === 'show_price';
    }
    renderBrandPalette(brandPalette(client));
    renderBrandInventory(client);
  }

  function selectBrand(id, { keepDraft = false } = {}) {
    state.selectedBrandId = id ? Number(id) : null;
    state.creativeLineClientId = state.selectedBrandId;
    if (!keepDraft) resetBrandDraft();
    fillBrandForm(selectedBrand());
    renderClients();
    renderCreativeLineWorkspace();
  }

  function renderClients() {
    const root = $('#mcClientTableBody');
    if (!root) return;
    root.innerHTML = state.clients.map((client) => {
      const logo = client.logo_upload_path || client.logo_url;
      const active = Number(client.id) === Number(state.selectedBrandId);
      return `<div class="mc-brand-row ${active ? 'is-active' : ''}">
        <button class="mc-brand-row-main" type="button" data-select-brand="${client.id}">
          ${logo ? `<img src="${escapeHtml(logo)}" alt="">` : '<span class="mc-brand-row-mark"></span>'}
          <span>
            <strong>${escapeHtml(client.name)}</strong>
            <small>${escapeHtml(client.sector || 'Sem setor')}${client.analysis_metadata?.model ? ' · analisada' : ''}${brandLine(client).signature_summary ? ' · linha criativa' : ''}</small>
          </span>
        </button>
        <div class="mc-inspector-actions">
          <button class="cx-btn cx-btn-secondary cx-btn-sm" data-action="open-logo" data-client-id="${client.id}" type="button">Logo</button>
          <button class="cx-btn cx-btn-danger cx-btn-sm" data-action="delete-client" data-client-id="${client.id}" type="button">Remover</button>
        </div>
      </div>`;
    }).join('') || '<p class="mc-section-note">Cadastre o primeiro perfil de marca.</p>';
    renderCreativeLineClientOptions();
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
      ${data.analysis_metadata?.pages_analyzed ? `<span>${escapeHtml(data.analysis_metadata.pages_analyzed)} páginas analisadas</span>` : ''}
      ${data.analysis_metadata?.assets_found ? `<span>${escapeHtml(data.analysis_metadata.assets_found)} imagens encontradas</span>` : ''}
      ${sources.length ? `<span>Fontes: ${sources.map((url, index) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${index + 1}</a>`).join(', ')}</span>` : ''}
      <span>Revise os campos antes de salvar.</span>`;
    root.classList.remove('hidden');
  }

  function renderBrandPalette(palette) {
    const root = $('#mcBrandPalette');
    if (!root) return;
    const colors = Array.isArray(palette) ? palette : [];
    root.classList.toggle('hidden', !colors.length);
    root.innerHTML = colors.length ? `
      <header><strong>Paleta observada</strong><small>Cores ordenadas por presença e função na identidade.</small></header>
      <div>${colors.map((color) => `
        <button type="button" data-palette-color="${escapeHtml(color.hex)}" title="${escapeHtml(color.usage || '')}">
          <span style="--brand-color:${escapeHtml(color.hex)}"></span>
          <strong>${escapeHtml(color.name || color.hex)}</strong>
          <small>${escapeHtml(color.hex)} · ${Math.round(Number(color.confidence || 0) * 100)}%</small>
        </button>        `).join('')}</div>` : '';
  }

  function renderBrandInventory(source) {
    const root = $('#mcBrandInventory');
    if (!root) return;
    const client = source?.id ? source : creativeLineClient();
    const profile = client?.brand_profile || source || {};
    const analysis = source?.asset_candidates ? source : state.brandAnalysis;
    let palette = brandPalette(client || { brand_profile: profile });
    if (!palette.length) {
      palette = analysis?.color_palette || profile.color_palette || [];
    }
    const fonts = brandFonts(client || { brand_profile: { fonts: analysis?.fonts || profile.fonts } });
    const assets = client?.brand_assets || [];
    const candidates = Array.isArray(analysis?.asset_candidates)
      ? analysis.asset_candidates
      : state.brandAssetCandidates;
    const logo = client?.logo_upload_path || client?.logo_url || analysis?.logo_url || '';
    const groups = [
      ['Logo', candidates.filter((item) => item.kind === 'logo').length || (logo ? 1 : 0)],
      ['Produto', candidates.filter((item) => item.category === 'Produto').length],
      ['Campanha', candidates.filter((item) => item.category === 'Campanha').length],
      ['Ambiente', candidates.filter((item) => item.category === 'Ambiente').length],
      ['Refs salvas', assets.filter((item) => item.role === 'reference').length],
      ['Peças reais', assets.filter((item) => item.role === 'creative').length],
    ].filter(([, count]) => count);
    const line = brandLine(client || { brand_profile: profile });
    const rules = [
      ...(profile.visual_motifs || analysis?.visual_motifs || []),
      ...(profile.mandatory_elements || analysis?.mandatory_elements || []),
    ].slice(0, 6);
    if (!logo && !palette.length && !fonts.length && !groups.length && !line.signature_summary) {
      root.innerHTML = '<p>Selecione uma marca ou analise o site para ver logo, paleta, fontes, peças e regras.</p>';
      return;
    }
    root.innerHTML = `
      <header>
        <strong>Assets identificados</strong>
        <small>O que a leitura e a auditoria já separaram para a produção.</small>
      </header>
      <div class="mc-brand-inventory-grid">
        <article>
          <span>Logo</span>
          ${logo ? `<img src="${escapeHtml(logo)}" alt="">` : '<em>Ainda sem arquivo</em>'}
        </article>
        <article>
          <span>Paleta</span>
          <div class="mc-brand-inventory-swatches">
            ${palette.slice(0, 6).map((color) => {
              const hex = color?.hex || color;
              return `<i style="background:${escapeHtml(hex)}" title="${escapeHtml(hex)}"></i>`;
            }).join('') || '<em>Sem cores</em>'}
          </div>
        </article>
        <article>
          <span>Fontes</span>
          ${fonts.length ? `<ul>${fonts.map((item) => `<li>${escapeHtml(item.family)}${item.role ? ` · ${escapeHtml(item.role)}` : ''}</li>`).join('')}</ul>` : '<em>Site ainda sem fonte nomeada</em>'}
        </article>
        <article>
          <span>Peças</span>
          ${groups.length ? `<ul>${groups.map(([label, count]) => `<li>${escapeHtml(label)} · ${count}</li>`).join('')}</ul>` : '<em>Nenhuma peça ainda</em>'}
        </article>
      </div>
      ${line.signature_summary || rules.length ? `<p>${escapeHtml(line.signature_summary || rules.join(' · '))}</p>` : ''}
    `;
  }

  function renderCreativeLineClientOptions() {
    const select = $('#mcCreativeLineClient');
    if (!select) return;
    const current = String(state.creativeLineClientId || select.value || '');
    select.innerHTML = '<option value="">Selecione um perfil</option>' + state.clients.map(
      (client) => `<option value="${client.id}">${escapeHtml(client.name)}</option>`,
    ).join('');
    select.value = current;
    if (current && !select.value) {
      state.creativeLineClientId = null;
      renderCreativeLineWorkspace();
    }
  }

  function creativeLineClient() {
    return state.clients.find(
      (client) => Number(client.id) === Number(state.creativeLineClientId),
    ) || null;
  }

  function renderCreativeLineUploads() {
    const root = $('#mcCreativeLineUploads');
    if (!root) return;
    root.hidden = !state.creativeLineFiles.length;
    root.innerHTML = state.creativeLineFiles.map((file, index) => `
      <article>
        <img src="${URL.createObjectURL(file)}" alt="">
        <button type="button" data-creative-remove="${index}" aria-label="Remover ${escapeHtml(file.name)}"><i class="fa-solid fa-xmark"></i></button>
        <span>${escapeHtml(file.name)}</span>
      </article>`).join('');
  }

  function renderCreativeLineResult(line) {
    const root = $('#mcCreativeLineResult');
    if (!root) return;
    if (!line?.signature_summary) {
      root.innerHTML = `<div class="mc-creative-dna-empty">
        <i class="fa-solid fa-fingerprint" aria-hidden="true"></i>
        <strong>DNA criativo ainda não analisado</strong>
        <p>Adicione peças consistentes para gerar regras de composição, fotografia, tipografia e instruções para o GPT Image 2.</p>
      </div>`;
      return;
    }
    const copy = line.copy_system || {};
    const copyFacts = [
      copy.headline_structure && `Título: ${copy.headline_structure}`,
      copy.body_density && `Densidade: ${copy.body_density}`,
      copy.legal_presence && `Legal: ${copy.legal_presence}`,
      copy.typography?.role && copy.typography.role !== 'unknown'
        && `Fonte: ${copy.typography.role}${copy.typography.family ? ` · ${copy.typography.family}` : ''}${copy.typography.confidence === 'hypothesis' ? ' (hipótese)' : ''}`,
      copy.cta?.visual_pattern && `CTA: ${copy.cta.visual_pattern}${copy.cta.confidence === 'hypothesis' ? ' (hipótese)' : ''}`,
    ].filter(Boolean);
    const sections = [
      ['Composição', line.composition_rules],
      ['Imagem e fotografia', line.imagery_rules],
      ['Tipografia', line.typography_rules],
      ['Recursos gráficos', line.graphic_devices],
      ['Copy e CTA', [...(line.copy_patterns || []), ...copyFacts]],
      ['Preservar', line.must_preserve],
      ['Evitar', line.avoid],
    ].filter(([, values]) => Array.isArray(values) && values.length);
    root.innerHTML = `
      <header><span><i class="fa-solid fa-fingerprint"></i></span><div><strong>DNA criativo aprendido</strong><small>${escapeHtml(line.source_count || 0)} peças · confiança ${Math.round(Number(line.confidence || 0) * 100)}%</small></div></header>
      ${line.stale ? `<div class="mc-creative-stale"><i class="fa-solid fa-rotate"></i> ${escapeHtml(line.stale_reason || 'Analise novamente após alterar as referências.')}</div>` : ''}
      <p class="mc-creative-signature">${escapeHtml(line.signature_summary)}</p>
      ${(line.caveats || []).length ? `<div class="mc-creative-caveats">${line.caveats.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div>` : ''}
      ${(line.color_palette || []).length ? `<div class="mc-creative-palette">${line.color_palette.map((color) => `<span style="--brand-color:${escapeHtml(color.hex)}" title="${escapeHtml(color.name)}"></span>`).join('')}</div>` : ''}
      <div class="mc-creative-rules">${sections.map(([title, values]) => `<details><summary>${escapeHtml(title)} <span>${values.length}</span></summary><ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join('')}</ul></details>`).join('')}</div>
      ${line.gpt_image_instruction ? `<details class="mc-gpt-instruction"><summary>Instrução enviada ao GPT Image 2</summary><pre>${escapeHtml(line.gpt_image_instruction)}</pre></details>` : ''}`;
  }

  function renderCreativeLineWorkspace() {
    const client = creativeLineClient();
    const library = $('#mcCreativeLineLibrary');
    const analyze = $('#mcAnalyzeCreativeLine');
    if (!client) {
      library.innerHTML = '<p>Selecione uma marca para ver sua memória visual.</p>';
      analyze.disabled = true;
      renderCreativeLineResult(null);
      return;
    }
    const assets = (client.brand_assets || []).filter(
      (asset) => asset.role === 'creative',
    );
    library.innerHTML = assets.length ? assets.map((asset) => `
      <article>
        <img src="${escapeHtml(asset.asset_path || asset.source_url)}" alt="${escapeHtml(asset.metadata?.original_name || 'Criativo da marca')}" loading="lazy">
        <button type="button" data-creative-delete="${asset.id}" aria-label="Remover criativo"><i class="fa-solid fa-trash-can"></i></button>
        <span>${escapeHtml(asset.metadata?.original_name || 'Criativo aprovado')}</span>
      </article>`).join('') : '<p>Nenhum criativo real salvo para esta marca.</p>';
    analyze.disabled = !(assets.length || state.creativeLineFiles.length);
    renderCreativeLineResult(client.brand_profile?.creative_line);
    renderBrandInventory(client);
  }

  function brandFileKey(file) {
    return `${file?.name || ''}:${file?.size || 0}:${file?.lastModified || 0}`;
  }

  function brandCandidateRole(asset) {
    if (asset?.kind === 'logo') return 'logo';
    return String(asset?.category || '').toLowerCase() === 'campanha' ? 'creative' : 'reference';
  }

  function syncCreativeLineFromBrandFiles() {
    const logo = state.primaryBrandFileIndex >= 0
      ? state.brandFiles[state.primaryBrandFileIndex]
      : null;
    const logoKey = logo ? brandFileKey(logo) : '';
    const extras = state.brandFiles.filter((_, index) => index !== state.primaryBrandFileIndex);
    const present = new Set(state.creativeLineFiles.map(brandFileKey));
    state.creativeLineFiles = state.creativeLineFiles.filter(
      (file) => brandFileKey(file) !== logoKey,
    );
    extras.forEach((file) => {
      const key = brandFileKey(file);
      if (present.has(key) || state.creativeLineFiles.length >= 6) return;
      state.creativeLineFiles.push(file);
      present.add(key);
    });
    if (state.selectedBrandId) state.creativeLineClientId = state.selectedBrandId;
    renderCreativeLineUploads();
    renderCreativeLineWorkspace();
  }

  function addCreativeLineFiles(files) {
    const incoming = Array.from(files || []).filter(
      (file) => /^image\/(png|jpeg|webp)$/.test(file.type) && file.size <= 5 * 1024 * 1024,
    );
    state.creativeLineFiles = [...state.creativeLineFiles, ...incoming].slice(0, 6);
    renderCreativeLineUploads();
    renderCreativeLineWorkspace();
    if (incoming.length !== Array.from(files || []).length) {
      toast('Use PNG, JPG ou WEBP de até 5 MB.', 'warning');
    }
  }

  async function learnCreativeLine(button) {
    const client = creativeLineClient();
    if (!client) return;
    await withLock('creative-line', button, async () => {
      const body = new FormData();
      state.creativeLineFiles.forEach((file) => body.append('creatives', file));
      $('#mcCreativeLineStatus').textContent = 'Comparando composição, paleta e fotografia…';
      try {
        const result = await api(
          `${API.clients}/${client.id}/creative-line/analyze`,
          { method: 'POST', body },
        );
        state.creativeLineFiles = [];
        state.clients = await api(API.clients);
        renderClients();
        renderCreativeLineUploads();
        renderCreativeLineWorkspace();
        $('#mcCreativeLineStatus').textContent = `${result.creative_line.source_count} peças transformadas em regras para geração.`;
        toast('Linha criativa aprendida e conectada ao GPT Image 2.', 'success');
      } catch (error) {
        $('#mcCreativeLineStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  function brandAssetKey(asset) {
    return String(asset?.url || asset?.source_url || '');
  }

  function selectedBrandCandidates() {
    return state.brandAssetCandidates.filter(
      (asset) => state.selectedBrandAssets.has(brandAssetKey(asset)),
    );
  }

  function renderBrandCandidates() {
    const curator = $('#mcBrandCurator');
    const strip = $('#mcBrandAssetStrip');
    if (!curator || !strip) return;
    const visible = state.brandAssetCandidates.filter(
      (asset) => state.brandAssetFilter === 'all' || asset.category === state.brandAssetFilter,
    );
    curator.classList.toggle('hidden', !state.brandAssetCandidates.length);
    strip.innerHTML = visible.map((asset) => {
      const key = brandAssetKey(asset);
      const selected = state.selectedBrandAssets.has(key);
      const primary = state.primaryBrandAssetUrl === key;
      const dimensions = asset.width && asset.height ? `${asset.width}×${asset.height}` : 'Dimensão não informada';
      return `<article class="mc-brand-asset${selected ? ' is-selected' : ''}${primary ? ' is-primary' : ''}" data-brand-url="${escapeHtml(key)}">
        <button class="mc-brand-asset-select" type="button" data-brand-select="${escapeHtml(key)}" aria-pressed="${selected}">
          <img src="${escapeHtml(key)}" alt="${escapeHtml(asset.alt || asset.category || 'Imagem da marca')}" loading="lazy">
          <span>${selected ? '<i class="fa-solid fa-check"></i> Selecionada' : 'Selecionar'}</span>
        </button>
        <div><strong>${escapeHtml(asset.category || 'Referência')}</strong><small>${escapeHtml(dimensions)} · confiança ${Math.round(Number(asset.score || 0))}%</small></div>
        ${asset.kind === 'logo' ? `<button class="mc-brand-primary" type="button" data-brand-primary="${escapeHtml(key)}">${primary ? 'Logo principal' : 'Usar como logo'}</button>` : ''}
        <a href="${escapeHtml(asset.page_url || key)}" target="_blank" rel="noopener noreferrer">Ver origem</a>
      </article>`;
    }).join('') || '<p class="mc-brand-empty-filter">Nenhuma imagem nesta categoria.</p>';
    $$('img', strip).forEach((image) => {
      image.addEventListener('error', () => image.closest('.mc-brand-asset')?.remove(), { once: true });
    });
    const selected = selectedBrandCandidates();
    $('#mcBrandAssetCount').textContent = `${selected.length} ${selected.length === 1 ? 'selecionada' : 'selecionadas'}`;
    $('#mcBrandSelectionTray').innerHTML = selected.length
      ? `<span><strong>${selected.length}</strong> referências serão salvas com o perfil.</span>`
      : '<span>Nenhuma referência selecionada.</span>';
  }

  function renderDroppedBrandFiles() {
    const root = $('#mcBrandDropped');
    if (!root) return;
    root.hidden = !state.brandFiles.length;
    root.innerHTML = state.brandFiles.map((file, index) => `
      <article class="${state.primaryBrandFileIndex === index ? 'is-primary' : ''}">
        <img src="${URL.createObjectURL(file)}" alt="">
        <span><strong>${escapeHtml(file.name)}</strong><small>${Math.ceil(file.size / 1024)} KB</small></span>
        <button type="button" data-dropped-logo="${index}">${state.primaryBrandFileIndex === index ? 'Logo principal' : 'Usar como logo'}</button>
        <button type="button" data-dropped-remove="${index}" aria-label="Remover ${escapeHtml(file.name)}"><i class="fa-solid fa-xmark"></i></button>
      </article>
    `).join('');
  }

  function addBrandFiles(files) {
    const accepted = Array.from(files || []).filter(
      (file) => /^image\/(png|jpeg|webp)$/.test(file.type) && file.size <= 5 * 1024 * 1024,
    );
    state.brandFiles = [...state.brandFiles, ...accepted].slice(0, 8);
    renderDroppedBrandFiles();
    syncCreativeLineFromBrandFiles();
    if (accepted.length !== Array.from(files || []).length) {
      toast('Algumas imagens foram ignoradas. Use PNG, JPG ou WEBP de até 5 MB.', 'warning');
    }
  }

  function setupBrandDropzone(rootSelector, inputSelector, onFiles) {
    const root = $(rootSelector);
    if (!root) return;
    const input = $(inputSelector, root);
    if (!input) return;
    root.addEventListener('click', (event) => {
      if (event.target === input) return;
      if (event.target.closest('[data-dropped-logo], [data-dropped-remove]')) return;
      input.click();
    });
    root.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      input.click();
    });
    input.addEventListener('change', () => onFiles(input.files));
    ['dragenter', 'dragover'].forEach((type) => root.addEventListener(type, (event) => {
      event.preventDefault();
      root.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach((type) => root.addEventListener(type, (event) => {
      event.preventDefault();
      root.classList.remove('is-dragging');
    }));
    root.addEventListener('drop', (event) => onFiles(event.dataTransfer.files));
  }

  async function analyzeBrand(event) {
    const button = event.currentTarget;
    const form = $('#mcClientForm');
    if (!form) return;
    const websiteUrl = form.elements.website_url.value.trim();
    if (!websiteUrl && !state.brandFiles.length) {
      toast('Informe o site ou envie uma imagem de referência.', 'warning');
      form.elements.website_url.focus();
      return;
    }
    await withLock('analyze-brand', button, async () => {
      const body = new FormData();
      if (websiteUrl) body.append('website_url', websiteUrl);
      state.brandFiles.slice(0, 4).forEach((file) => body.append('images', file));
      const phases = [
        'Lendo a página inicial e a identidade…',
        'Mapeando páginas relevantes da marca…',
        'Verificando logos e imagens do site…',
        'Refinando o contexto para campanhas…',
      ];
      let phase = 0;
      $('#mcClientFormStatus').textContent = phases[phase];
      const progressTimer = window.setInterval(() => {
        phase = Math.min(phase + 1, phases.length - 1);
        $('#mcClientFormStatus').textContent = phases[phase];
      }, 3500);
      try {
        const data = await api(API.analyzeBrand, { method: 'POST', body });
        state.brandAnalysis = data;
        state.brandAssetCandidates = Array.isArray(data.asset_candidates) ? data.asset_candidates : [];
        state.selectedBrandAssets = new Set();
        const logo = state.brandAssetCandidates.find(
          (asset) => asset.kind === 'logo' && asset.url === data.logo_url,
        ) || state.brandAssetCandidates.find((asset) => asset.kind === 'logo' && Number(asset.score) >= 70);
        state.primaryBrandAssetUrl = logo ? brandAssetKey(logo) : null;
        if (logo) state.selectedBrandAssets.add(brandAssetKey(logo));
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
        [
          'products_services', 'differentiators', 'proof_points',
          'visual_motifs', 'mandatory_elements', 'forbidden_elements',
        ].forEach((name) => setFormValue(form, `${name}_text`, (data[name] || []).join('\n')));
        renderBrandAnalysisSummary(data);
        renderBrandPalette(data.color_palette);
        renderBrandInventory(data);
        renderBrandCandidates();
        syncCreativeLineFromBrandFiles();
        $('#mcClientFormStatus').textContent = '';
        toast('Leitura da marca concluída. Revise as sugestões.', 'success');
      } catch (error) {
        $('#mcClientFormStatus').textContent = error.message;
        toast(error.message, 'error');
      } finally {
        window.clearInterval(progressTimer);
      }
    });
  }

  async function persistBrandUploads(clientId) {
    const logoIndex = state.primaryBrandFileIndex;
    const logoFile = logoIndex >= 0 ? state.brandFiles[logoIndex] : null;
    const seen = new Set();
    const creativeFiles = [];
    const take = (file) => {
      if (!file) return;
      const key = brandFileKey(file);
      if (seen.has(key)) return;
      seen.add(key);
      creativeFiles.push(file);
    };
    state.brandFiles.forEach((file, index) => {
      if (index !== logoIndex) take(file);
    });
    state.creativeLineFiles.forEach(take);
    if (logoFile) {
      const assetBody = new FormData();
      assetBody.append('images', logoFile);
      assetBody.append('primary_logo', 'true');
      await api(`${API.clients}/${clientId}/brand-assets`, {
        method: 'POST',
        body: assetBody,
      });
    }
    if (creativeFiles.length) {
      const creativeBody = new FormData();
      creativeFiles.forEach((file) => creativeBody.append('images', file));
      creativeBody.append('role', 'creative');
      await api(`${API.clients}/${clientId}/brand-assets`, {
        method: 'POST',
        body: creativeBody,
      });
    }
  }

  async function saveClient(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('button[type="submit"]', form);
    await withLock('save-client', button, async () => {
      const formData = new FormData(form);
      const current = selectedBrand();
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
        products_services: lines(formData.get('products_services_text')),
        differentiators: lines(formData.get('differentiators_text')),
        proof_points: lines(formData.get('proof_points_text')),
        visual_motifs: lines(formData.get('visual_motifs_text')),
        mandatory_elements: lines(formData.get('mandatory_elements_text')),
        forbidden_elements: lines(formData.get('forbidden_elements_text')),
        color_palette: state.brandAnalysis?.color_palette || current?.brand_profile?.color_palette || [],
        fonts: state.brandAnalysis?.fonts || current?.brand_profile?.fonts || [],
        brand_assets: selectedBrandCandidates().map((asset) => ({
          source_url: brandAssetKey(asset),
          page_url: asset.page_url,
          role: brandCandidateRole(asset),
          category: asset.category,
          reason: asset.reason,
          width: asset.width,
          height: asset.height,
          score: asset.score,
          is_primary: state.primaryBrandFileIndex < 0
            && state.primaryBrandAssetUrl === brandAssetKey(asset),
        })),
        analysis_metadata: state.brandAnalysis?.analysis_metadata || current?.analysis_metadata || {},
        show_price: formData.has('show_price'),
      };
      try {
        const saved = current
          ? await api(`${API.clients}/${current.id}`, { method: 'PUT', body: JSON.stringify(data) })
          : await api(API.clients, { method: 'POST', body: JSON.stringify(data) });
        const clientId = saved.id || current.id;
        await persistBrandUploads(clientId);
        state.clients = await api(API.clients);
        state.campaignClients = await api(API.campaignClients);
        renderClientOptions();
        const campaignClient = $('#mcCampaignClient');
        if (campaignClient) campaignClient.value = `profile:${clientId}`;
        renderClientPreview();
        renderGeneratorSummary();
        selectBrand(clientId, { keepDraft: true });
        state.creativeLineClientId = clientId;
        state.creativeLineFiles = [];
        renderCreativeLineUploads();
        renderCreativeLineWorkspace();
        toast(current ? 'Perfil de marca atualizado.' : 'Perfil de marca salvo.', 'success');
      } catch (error) {
        $('#mcClientFormStatus').textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  // ====== HISTÓRICO ======
  function historyTotal(payload, campaignId) {
    const apiTotal = Number(payload?.total_brl);
    if (Number.isFinite(apiTotal)) return apiTotal;
    const modelings = Array.isArray(payload?.modelings) ? payload.modelings : [];
    if (modelings.length) return modelings.reduce((sum, item) => sum + spendValue(item), 0);
    if (campaignId) {
      const selected = modelCampaigns().find((item) => String(item.id) === String(campaignId));
      if (selected) return spendValue(selected);
    }
    const catalogTotal = modelCampaigns().reduce((sum, item) => sum + spendValue(item), 0);
    if (catalogTotal) return catalogTotal;
    const jobs = Array.isArray(payload) ? payload : (payload?.jobs || []);
    return jobs.reduce((sum, job) => sum + spendValue(job), 0);
  }

  function renderHistorySpend(total) {
    const spend = $('#mcHistorySpend');
    if (!spend) return;
    spend.hidden = false;
    spend.querySelector('strong').textContent = brl(total);
  }

  function renderModelingLedger(modelings, campaignId) {
    const root = $('#mcModelingLedger');
    if (!root) return;
    const rows = (Array.isArray(modelings) && modelings.length)
      ? modelings
      : modelCampaigns();
    if (!rows.length) {
      root.innerHTML = '';
      return;
    }
    root.innerHTML = `
      <header>
        <h3>Modelagens criadas</h3>
        <p>Gasto acumulado de todas as IAs em cada modelagem.</p>
      </header>
      <ul>
        ${rows.map((item) => `
          <li>
            <button type="button" class="mc-modeling-row ${String(item.id) === String(campaignId) ? 'is-active' : ''}" data-modeling-id="${item.id}">
              <span>
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.client || item.client_name || 'Sem cliente')}</small>
              </span>
              <em class="mc-campaign-cost" title="Soma de todas as IAs desta modelagem">${campaignCost(item)}</em>
            </button>
          </li>`).join('')}
      </ul>`;
  }

  async function renderHistoryFinish(campaignId) {
    const root = $('#mcHistoryFinish');
    if (!root) return;
    if (!campaignId) {
      root.innerHTML = '';
      return;
    }
    try {
      const [campaign, quote] = await Promise.all([
        api(`${API.campaigns}/${campaignId}`),
        api(`${API.campaigns}/${campaignId}/publish-quote`),
      ]);
      const productions = campaign.productions || (campaign.production ? [campaign.production] : []);
      const approvedDrafts = collectDraftPieces(productions, true);
      const highCount = productions.reduce((sum, production) => sum + (production.scenes || []).filter((scene) => (
        sceneAssets(scene).some((asset) => asset.status === 'approved' && assetFidelity(asset) === 'publish')
      )).length, 0);
      const pending = Number(quote?.count || approvedDrafts.length || 0);
      const total = Number(quote?.total_brl || pending * publishUnitBrl());
      root.innerHTML = `
        <header>
          <h3>Finalização</h3>
          <p>Mockup já basta para revisar e para o link. Alta resolução é opcional e custa à parte.</p>
        </header>
        <p class="mc-history-finish-quote">
          ${pending
            ? `<strong>${pending} cena${pending === 1 ? '' : 's'} aprovada${pending === 1 ? '' : 's'} sem alta · ${brl(total)}</strong>`
            : highCount
              ? `<strong>${highCount} cena${highCount === 1 ? '' : 's'} já em alta.</strong>`
              : 'Aprove as cenas na bancada para cotar a alta aqui.'}
        </p>
        <div class="mc-history-finish-actions">
          <button class="cx-btn cx-btn-primary" type="button" data-history-publish="${campaignId}" ${pending ? '' : 'disabled'}>
            Gerar alta resolução
          </button>
          <button class="cx-btn cx-btn-secondary" type="button" data-history-video="${campaignId}">
            Gerar vídeo
          </button>
        </div>
        <p class="cx-help">Vídeo é o passo depois da alta. O pipeline ainda não está pronto — o botão só confere se as cenas aprovadas já têm alta.</p>`;
    } catch (error) {
      root.innerHTML = `<p class="cx-help">${escapeHtml(error.message)}</p>`;
    }
  }

  async function publishHistoryCampaign(button) {
    const campaignId = button.dataset.historyPublish;
    const quote = await api(`${API.campaigns}/${campaignId}/publish-quote`);
    const assetIds = (quote.pieces || []).map((item) => item.asset_id);
    if (!assetIds.length) {
      toast('Não há cenas aprovadas para gerar em alta.', 'warning');
      return;
    }
    await withLock(`history-publish-${campaignId}`, button, async () => {
      await api(`${API.campaigns}/${campaignId}/publish`, {
        method: 'POST',
        body: JSON.stringify({ asset_ids: assetIds }),
      });
      toast('Alta resolução gerada só das cenas aprovadas.', 'success');
      await loadHistory();
    });
  }

  async function prepareHistoryVideo(button) {
    const campaignId = button.dataset.historyVideo;
    await withLock(`history-video-${campaignId}`, button, async () => {
      const result = await api(`${API.campaigns}/${campaignId}/video/prepare`, {
        method: 'POST',
        body: '{}',
      });
      toast(result.message || 'Pipeline de vídeo ainda não está pronto.', 'warning');
    });
  }

  async function loadHistory() {
    const root = $('#mcHistoryList');
    const requestId = ++historyRequestId;
    root.innerHTML = '<div class="mc-skeleton-list"><span></span><span></span><span></span></div>';
    try {
      const campaignId = $('#mcHistoryCampaign').value;
      const query = new URLSearchParams({ flow_kind: 'model' });
      if (campaignId) query.set('campaign_id', campaignId);
      const payload = await api(`${API.history}?${query.toString()}`);
      if (requestId !== historyRequestId) return;
      const jobs = Array.isArray(payload) ? payload : (payload.jobs || []);
      const modelings = Array.isArray(payload?.modelings) ? payload.modelings : [];
      const headlineTotal = historyTotal(payload, campaignId);
      renderHistorySpend(headlineTotal);
      renderModelingLedger(modelings, campaignId);
      await renderHistoryFinish(campaignId);
      root.innerHTML = jobs.map((job) => `
        <details class="mc-history-item">
          <summary>
            <span><strong>${escapeHtml(job.campaign_name)}</strong><br><small>${escapeHtml(job.job_type)} · ${escapeHtml(job.model)}</small></span>
            <span>${statusBadge(job.status)} <em class="mc-job-cost">${brl(job.spent_brl)}</em></span>
          </summary>
          <div class="mc-history-body">
            ${job.error_message ? `<div class="cx-alert cx-alert-danger">${escapeHtml(job.error_message)}</div>` : ''}
            ${job.prompt ? `<pre class="mc-prompt-text">${escapeHtml(job.prompt)}</pre>` : ''}
            ${job.script_text ? `<pre class="mc-prompt-text">${escapeHtml(job.script_text)}</pre>` : ''}
          </div>
        </details>`).join('') || '<div class="cx-empty-state"><p>Nenhuma produção registrada.</p></div>';
    } catch (error) {
      if (requestId !== historyRequestId) return;
      renderHistorySpend(0);
      root.innerHTML = `<div class="cx-alert cx-alert-danger">${escapeHtml(error.message)}</div>`;
    }
  }

  function unfoldFormats() {
    const families = new Set([
      'rectangle', 'wide_banner', 'half_page',
      'square_1x1', 'story_9x16', 'landscape_social', 'portrait_4x5',
    ]);
    return state.formats.filter((format) => (
      format.media_type === 'image'
      && Number(format.scene_count || 1) === 1
      && (
        format.category === 'social'
        || String(format.slug || '').startsWith('iab-')
        || families.has(format.iab_family)
      )
    ));
  }

  function unfoldThumbStyle(format) {
    const size = String(format.target_size || format.default_size || '1x1').split(/[xX×]/);
    const width = Number(size[0]) || 1;
    const height = Number(size[1]) || 1;
    return `aspect-ratio:${width}/${height}`;
  }

  function unfoldHasKv() {
    return Boolean($('#mcUnfoldFile')?.files?.length || $('#mcUnfoldSourceAsset')?.value);
  }

  function unfoldHasPieces() {
    return unfoldSceneList(state.unfoldCampaign).some((scene) => (
      (scene.assets || []).some((asset) => asset.asset_type !== 'video' && (asset.asset_url || asset.url))
    ));
  }

  function unfoldSelectedClient() {
    return brandedCampaignClients().find(
      (item) => item.selection_key === $('#mcUnfoldClient')?.value,
    );
  }

  function renderUnfoldBrand() {
    const root = $('#mcUnfoldBrandPreview');
    const empty = $('#mcUnfoldBrandEmpty');
    if (!root) return;
    const client = unfoldSelectedClient();
    const branded = brandedCampaignClients();
    if (empty) empty.hidden = branded.length > 0 || Boolean($('#mcUnfoldClient')?.value);
    if (!client) {
      root.hidden = true;
      root.innerHTML = '';
      return;
    }
    const logo = client.logo_upload_path || client.logo_url;
    const primary = brandPrimaryColor(client);
    const secondary = brandSecondaryColor(client);
    root.hidden = false;
    root.innerHTML = `
      <div class="mc-unfold-brand-row">
        ${logo
          ? `<img src="${escapeHtml(logo)}" alt="">`
          : '<span class="mc-unfold-brand-mark" aria-hidden="true"></span>'}
        <span>
          <strong>${escapeHtml(client.name)}</strong>
          <small>${escapeHtml(client.sector || 'Sem setor')}</small>
        </span>
      </div>
      ${primary || secondary ? `<div class="mc-unfold-swatches" aria-hidden="true">
        ${primary ? `<i style="background:${escapeHtml(primary)}"></i>` : ''}
        ${secondary ? `<i style="background:${escapeHtml(secondary)}"></i>` : ''}
      </div>` : ''}
      ${brandTone(client) ? `<p class="mc-section-note">${escapeHtml(brandTone(client))}</p>` : ''}`;
  }

  function syncUnfoldProgress() {
    if (!$('#mcUnfoldForm')) return;
    const done = {
      marca: Boolean($('#mcUnfoldClient')?.value),
      kv: unfoldHasKv(),
      fecha: unfoldHasKv(),
      retangulos: state.unfoldFormatIds.size > 0,
      pecas: unfoldHasPieces(),
    };
    const order = ['marca', 'kv', 'fecha', 'retangulos', 'pecas'];
    const current = order.find((key) => !done[key]) || 'pecas';
    $$('[data-unfold-step]').forEach((button) => {
      const key = button.dataset.unfoldStep;
      button.classList.toggle('is-done', Boolean(done[key]) && key !== current);
      button.classList.toggle('is-current', key === current);
      if (key === current) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    $$('[data-unfold-col]').forEach((col) => {
      col.classList.toggle('is-current', col.dataset.unfoldCol === current);
    });
    const meta = $('#mcUnfoldFormatMeta');
    if (meta) {
      const count = state.unfoldFormatIds.size;
      meta.textContent = count
        ? `${count} ${count === 1 ? 'retângulo' : 'retângulos'} no lote`
        : 'Clique para ligar ou tirar um retângulo.';
    }
  }

  function focusUnfoldStep(key) {
    const target = $(`[data-unfold-col="${key}"]`);
    if (!target) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    $$('[data-unfold-col]').forEach((col) => col.classList.toggle('is-focus', col === target));
    if (key === 'marca') $('#mcUnfoldClient')?.focus();
    else if (key === 'kv') $('#mcUnfoldDropzone')?.focus();
    else if (key === 'fecha') $('#mcUnfoldModel')?.focus();
    else if (key === 'retangulos') $('#mcUnfoldGenerate')?.focus();
  }

  function renderUnfoldFormats() {
    const root = $('#mcUnfoldFormatList');
    if (!root) return;
    const formats = unfoldFormats();
    if (!state.unfoldFormatIds.size && formats.length) {
      formats.forEach((format) => state.unfoldFormatIds.add(String(format.id)));
    }
    const share = unfoldEngine() === 'construct';
    root.innerHTML = formats.map((format) => `
      <button type="button" class="mc-unfold-format ${state.unfoldFormatIds.has(String(format.id)) ? 'is-active' : ''}"
              data-unfold-format="${format.id}">
        <span class="mc-unfold-thumb" style="${unfoldThumbStyle(format)}"></span>
        <strong>${escapeHtml(formatShortName(format))}</strong>
        <small>${escapeHtml(format.target_size || format.default_size || '')}</small>
        ${share && formatSceneLabel(format)
          ? `<small class="mc-unfold-share">Foto ${escapeHtml(formatSceneLabel(format))}</small>`
          : ''}
      </button>`).join('') || '<p class="mc-section-note">Nenhum retângulo estático neste catálogo.</p>';
    syncUnfoldProgress();
  }

  function renderUnfoldLibrary() {
    const grid = $('#mcUnfoldLibraryGrid');
    if (!grid) return;
    const items = state.unfoldLibrary;
    grid.innerHTML = items.map((asset) => `
      <button type="button" class="${String($('#mcUnfoldSourceAsset')?.value) === String(asset.id) ? 'is-active' : ''}"
              data-unfold-asset="${asset.id}" data-unfold-url="${escapeHtml(asset.preview_url || '')}">
        <img src="${escapeHtml(asset.preview_url || '')}" alt="${escapeHtml(asset.original_name || asset.campaign_name || 'Peça')}">
      </button>`).join('') || '<p class="mc-section-note">Nenhuma peça de modelagem ainda.</p>';
  }

  async function loadUnfoldLibrary() {
    const models = modelCampaigns();
    const results = await Promise.allSettled(
      models.map((campaign) => api(`${API.campaigns}/${campaign.id}/assets`)),
    );
    const items = [];
    results.forEach((result, index) => {
      if (result.status !== 'fulfilled') return;
      const campaign = models[index];
      (result.value || []).forEach((asset) => {
        if (asset.asset_type === 'video') return;
        const url = asset.asset_url || asset.url || '';
        if (!url) return;
        items.push({
          ...asset,
          campaign_name: campaign.name,
          preview_url: url,
        });
      });
    });
    state.unfoldLibrary = items;
    renderUnfoldLibrary();
  }

  function unfoldEngine() {
    return $('#mcUnfoldPathBar input[name="unfold_engine"]:checked')?.value || 'paint';
  }

  function unfoldSceneList(campaign) {
    return (campaign?.productions || []).flatMap((production) => production.scenes || []);
  }

  function unfoldPack() {
    return Number($('#mcUnfoldPathBar input[name="unfold_pack"]:checked')?.value || 6);
  }

  function unfoldSceneKey(format) {
    const pack = unfoldPack();
    const map = state.unfoldPaths?.format_scenes || {};
    let key = map[format.slug];
    if (key === 'mobile' && pack < 8) key = 'wide';
    if (key === 'rectangle' && pack < 6) key = 'half_page';
    if (key === 'wide' && pack < 6) key = 'landscape';
    return key || format.iab_family || format.category || '';
  }

  function formatSceneLabel(format) {
    const key = unfoldSceneKey(format);
    return SCENE_LABELS[key] || key;
  }

  function formatShortName(format) {
    return String(format.name_pt || '')
      .replace(/^IAB\s+/i, '')
      .replace(/^Instagram\s+[—–-]\s+/i, 'IG ')
      .replace(/^Facebook\s+[—–-]\s+/i, 'FB ')
      .replace(/^LinkedIn\s+[—–-]\s+/i, 'LI ')
      .replace(/^TikTok\s+[—–-]\s+/i, 'TT ');
  }

  function fillUnfoldModels() {
    const select = $('#mcUnfoldModel');
    const models = state.unfoldPaths?.models;
    if (!select || !models?.length) return;
    const current = select.value;
    select.innerHTML = models.map((model) => (
      `<option value="${escapeHtml(model.id)}">${escapeHtml(model.label)}</option>`
    )).join('');
    select.value = models.some((model) => model.id === current)
      ? current
      : (unfoldEngine() === 'construct'
        ? 'black-forest-labs/flux.2-pro'
        : 'openai/gpt-image-2');
  }

  function collectUnfoldItems() {
    const items = {};
    KV_ITEM_ORDER.forEach(([id]) => {
      const field = $(`#mcUnfoldItem-${id}`);
      const status = $(`#mcUnfoldItemStatus-${id}`);
      const text = field?.value.trim() || '';
      items[id] = {
        id,
        text,
        status: status?.value || (text ? 'uncertain' : 'absent'),
        lines: id === 'benefits' ? text.split('\n').map((line) => line.trim()).filter(Boolean) : undefined,
      };
    });
    return items;
  }

  function renderUnfoldItems(items = {}) {
    const root = $('#mcUnfoldItems');
    if (!root) return;
    root.innerHTML = KV_ITEM_ORDER.map(([id, label]) => {
      const item = items[id] || {};
      const text = item.text || (Array.isArray(item.lines) ? item.lines.join('\n') : '');
      const status = item.status || (text ? 'uncertain' : 'absent');
      const multiline = id === 'benefits' || id === 'talent' || id === 'legal';
      return `
        <div class="mc-unfold-item is-${status}">
          <span class="mc-unfold-item-name">${escapeHtml(label)}</span>
          <select class="cx-select mc-unfold-item-status" id="mcUnfoldItemStatus-${id}" aria-label="Situação de ${label}">
            <option value="seen" ${status === 'seen' ? 'selected' : ''}>Visto</option>
            <option value="uncertain" ${status === 'uncertain' ? 'selected' : ''}>Conferir</option>
            <option value="absent" ${status === 'absent' ? 'selected' : ''}>Fora</option>
          </select>
          ${multiline
            ? `<textarea class="cx-input" id="mcUnfoldItem-${id}" rows="2">${escapeHtml(text)}</textarea>`
            : `<input class="cx-input" id="mcUnfoldItem-${id}" value="${escapeHtml(text)}">`}
          ${id === 'logo' && unfoldEngine() === 'construct' && status === 'seen'
            ? '<p class="mc-layer-note">O PNG oficial entra na montagem, não na foto.</p>'
            : ''}
        </div>`;
    }).join('');
  }

  function syncUnfoldReview() {
    const name = $('#mcUnfoldReviewName');
    const items = collectUnfoldItems();
    state.unfoldItems = items;
    if ($('#mcUnfoldName')) $('#mcUnfoldName').value = name?.value.trim() || '';
    if ($('#mcUnfoldHeadlineHidden')) $('#mcUnfoldHeadlineHidden').value = items.headline?.text || '';
    if ($('#mcUnfoldCtaHidden')) $('#mcUnfoldCtaHidden').value = items.cta?.text || '';
    if ($('#mcUnfoldItemsHidden')) $('#mcUnfoldItemsHidden').value = JSON.stringify(items);
    if ($('#mcUnfoldEngine')) $('#mcUnfoldEngine').value = unfoldEngine();
    if ($('#mcUnfoldPack')) $('#mcUnfoldPack').value = String(unfoldPack());
    if ($('#mcUnfoldFidelity')) {
      $('#mcUnfoldFidelity').value = unfoldEngine() === 'construct' ? 'publish' : 'draft';
    }
  }

  function applyKvReview(data = {}) {
    const review = $('#mcUnfoldKvReview');
    if (review) review.hidden = false;
    const extras = [
      data.subhead,
      ...(Array.isArray(data.other_lines) ? data.other_lines : []),
    ].filter(Boolean);
    if ($('#mcUnfoldReviewName')) $('#mcUnfoldReviewName').value = data.name || data.headline || '';
    const items = data.items && typeof data.items === 'object' ? data.items : {};
    if (!items.headline) {
      items.headline = { text: data.headline || '', status: data.headline ? 'uncertain' : 'absent' };
    }
    if (!items.cta) {
      items.cta = { text: data.cta || data.cta_text || '', status: (data.cta || data.cta_text) ? 'uncertain' : 'absent' };
    }
    if (!items.offer && data.subhead) {
      items.offer = { text: data.subhead, status: 'uncertain' };
    }
    renderUnfoldItems(items);
    const extra = $('#mcUnfoldReviewExtra');
    if (extra) {
      extra.hidden = !extras.length;
      extra.textContent = extras.join('  ');
    }
    syncUnfoldReview();
    syncUnfoldProgress();
  }

  async function quoteUnfoldPath() {
    const box = $('#mcUnfoldQuote');
    if (!box) return;
    const formats = unfoldFormats().filter((format) => state.unfoldFormatIds.has(String(format.id)));
    const body = {
      engine: unfoldEngine(),
      scene_pack: unfoldPack(),
      image_model: $('#mcUnfoldModel')?.value,
      fidelity: unfoldEngine() === 'construct' ? 'publish' : 'draft',
      format_slugs: formats.map((format) => format.slug),
      format_ids: formats.map((format) => format.id),
    };
    const fallback = () => {
      box.querySelector('strong').textContent = 'R$ 0,00';
      const detail = $('#mcUnfoldQuoteDetail');
      if (detail) detail.textContent = formats.length
        ? 'Não foi possível cotar. Confira os destinos.'
        : 'Marque os retângulos para ver o lote.';
    };
    if (!formats.length) {
      fallback();
      return;
    }
    try {
      const quoted = await api(API.unfoldQuote, { method: 'POST', body: JSON.stringify(body) });
      state.unfoldQuote = quoted;
      box.querySelector('strong').textContent = brl(quoted.total_brl);
      const detail = $('#mcUnfoldQuoteDetail');
      if (detail) {
        const shared = Number(quoted.shared_pieces || 0);
        const photos = Number(quoted.photo_calls || 0);
        if (quoted.engine === 'construct' && photos === 0) {
          detail.textContent = `Montar no KV. ${quoted.pieces} ${quoted.pieces === 1 ? 'peça' : 'peças'} sem foto nova.`;
        } else {
          const how = quoted.engine === 'construct' ? 'Montar em camadas' : 'Pintar a peça';
          detail.textContent = shared
            ? `${how}. ${photos} fotos para ${quoted.pieces} peças, ${shared} no mesmo recorte.`
            : `${how}. ${photos} fotos para ${quoted.pieces} peças.`;
        }
      }
    } catch (_) {
      fallback();
    }
  }

  function showUnfoldPreview(url) {
    const preview = $('#mcUnfoldKvPreview');
    const hint = $('#mcUnfoldDropHint');
    const image = preview?.querySelector('img');
    if (!preview || !image) return;
    if (url) {
      image.src = url;
      preview.hidden = false;
      if (hint) hint.hidden = true;
      $('#mcUnfoldDropzone')?.classList.add('has-kv');
    } else {
      image.removeAttribute('src');
      preview.hidden = true;
      if (hint) hint.hidden = false;
      $('#mcUnfoldDropzone')?.classList.remove('has-kv');
    }
  }

  function setUnfoldFile(file) {
    const input = $('#mcUnfoldFile');
    if (!input) return;
    const transfer = new DataTransfer();
    if (file) transfer.items.add(file);
    input.files = transfer.files;
  }

  async function readUnfoldKv({ file, assetId } = {}) {
    const status = $('#mcUnfoldReadStatus');
    const formStatus = $('#mcUnfoldStatus');
    applyKvReview({});
    if (status) status.textContent = 'Lendo o KV…';
    if (formStatus) formStatus.textContent = 'Lendo o KV…';
    const body = new FormData();
    if (assetId) body.append('source_asset_id', String(assetId));
    else if (file) body.append('kv', file);
    try {
      const data = await api(API.readKv, { method: 'POST', body });
      applyKvReview(data || {});
      if (data?.preview_url && assetId) showUnfoldPreview(data.preview_url);
      if (status) status.textContent = '';
      if (formStatus) formStatus.textContent = '';
    } catch (error) {
      applyKvReview({});
      if (status) status.textContent = 'A leitura falhou. Conferir headline e CTA na lista abaixo.';
      if (formStatus) formStatus.textContent = '';
      toast(error.message, 'warning');
    }
  }

  function dataUrlToFile(dataUrl, name) {
    const [header, encoded] = String(dataUrl || '').split(',');
    const mime = /data:(.*?);/.exec(header)?.[1] || 'image/png';
    const bytes = Uint8Array.from(atob(encoded || ''), (char) => char.charCodeAt(0));
    return new File([bytes], name, { type: mime });
  }

  async function useUnfoldExample(button) {
    const status = $('#mcUnfoldExampleStatus');
    await withLock('unfold-example', button, async () => {
      if (status) status.textContent = 'Gerando o KV ideal no GPT Image 2…';
      try {
        const data = await api(API.exampleKv, { method: 'POST', body: '{}' });
        if (!data?.data_url) throw new Error('O exemplo não veio.');
        acceptUnfoldKv([dataUrlToFile(data.data_url, 'kv-exemplo.png')]);
        if (data.headline || data.cta) applyKvReview(data);
        if (status) status.textContent = 'Exemplo no drop. Confira as zonas e feche as peças.';
      } catch (error) {
        if (status) status.textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  function acceptUnfoldKv(files) {
    const file = Array.from(files || []).find((item) => /^image\/(png|jpeg|webp)$/.test(item.type));
    if (!file) {
      toast('Use PNG, JPG ou WEBP.', 'warning');
      return;
    }
    setUnfoldFile(file);
    if ($('#mcUnfoldSourceAsset')) $('#mcUnfoldSourceAsset').value = '';
    showUnfoldPreview(URL.createObjectURL(file));
    syncUnfoldProgress();
    readUnfoldKv({ file }).catch((error) => toast(error.message, 'error'));
  }

  function chooseUnfoldAsset(button) {
    const assetId = button.dataset.unfoldAsset;
    const url = button.dataset.unfoldUrl;
    if ($('#mcUnfoldSourceAsset')) $('#mcUnfoldSourceAsset').value = assetId;
    setUnfoldFile(null);
    showUnfoldPreview(url);
    $$('#mcUnfoldLibraryGrid [data-unfold-asset]').forEach((node) => {
      node.classList.toggle('is-active', node === button);
    });
    readUnfoldKv({ assetId }).catch((error) => toast(error.message, 'error'));
    syncUnfoldProgress();
  }

  function renderUnfoldSpend(campaign) {
    const spend = $('#mcUnfoldSpend');
    if (!spend) return;
    spend.hidden = !campaign;
    if (campaign) spend.querySelector('strong').textContent = campaignCost(campaign);
  }

  function renderUnfoldPieces(campaign) {
    const root = $('#mcUnfoldPieces');
    if (!root) return;
    const productions = campaign?.productions || [];
    const cards = productions.flatMap((production) => {
      const format = state.formats.find((item) => String(item.id) === String(production.format_template_id));
      return (production.scenes || []).map((scene) => {
        const asset = (scene.assets || []).find((item) => item.asset_type !== 'video') || {};
        const url = asset.asset_url || asset.url || '';
        return `
          <article class="mc-unfold-piece">
            ${url ? `<img src="${escapeHtml(url)}" alt="">` : '<div class="mc-unfold-thumb"></div>'}
            <strong>${escapeHtml(format?.name_pt || 'Formato')}</strong>
            <small>${escapeHtml(format?.target_size || '')} ${brl(asset.spent_brl || campaign?.spent_brl)}</small>
            ${asset.id ? `<span class="mc-fidelity-chip ${assetFidelity(asset) === 'publish' ? 'is-publish' : 'is-draft'}">${assetFidelity(asset) === 'publish' ? 'Publicável' : 'Rascunho'}</span>` : ''}
            ${publishHold(asset) || layerCaption(asset)
              ? `<p class="mc-layer-note">${escapeHtml(publishHold(asset) || layerCaption(asset))}</p>`
              : ''}
            <div class="mc-unfold-piece-actions">
              ${asset.id && (asset.metadata || {}).needs_retry
                ? `<button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-unfold-retry="1" data-scene-id="${scene.id}">Gerar de novo</button>`
                : ''}
              <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-unfold-ab="ab_simple" data-scene-id="${scene.id}" data-asset-id="${asset.id || ''}">Outra cor</button>
              <button class="cx-btn cx-btn-secondary cx-btn-sm" type="button" data-unfold-ab="ab_max" data-scene-id="${scene.id}" data-asset-id="${asset.id || ''}">Outro recorte</button>
            </div>
          </article>`;
      });
    });
    root.innerHTML = cards.join('') || '<div class="cx-empty-state"><p>Feche as peças para ver o contato neste tamanho.</p></div>';
    $('#mcUnfoldResult')?.classList.toggle('has-pieces', cards.length > 0);
    renderUnfoldSpend(campaign);
    syncPublishTriggers();
    refreshPublishModal();
    syncUnfoldProgress();
  }

  async function createUnfolding(button) {
    const form = $('#mcUnfoldForm');
    const status = $('#mcUnfoldStatus');
    await withLock('unfold', button, async () => {
      syncUnfoldReview();
      const data = new FormData(form);
      const formatIds = Array.from(state.unfoldFormatIds);
      if (!$('#mcUnfoldClient')?.value) {
        toast('Selecione a marca que assina o lote.', 'warning');
        focusUnfoldStep('marca');
        return;
      }
      if (!formatIds.length) {
        toast('Marque ao menos um retângulo.', 'warning');
        focusUnfoldStep('retangulos');
        return;
      }
      if (!data.get('kv')?.size && !data.get('source_asset_id')) {
        toast('Solte o KV ou pegue uma peça já gerada.', 'warning');
        focusUnfoldStep('kv');
        return;
      }
      if (!data.get('source_asset_id')) data.delete('source_asset_id');
      if (!data.get('kv') || !data.get('kv').size) data.delete('kv');
      data.set('format_ids', JSON.stringify(formatIds));
      const engine = unfoldEngine();
      data.set('generate', engine === 'construct' ? 'true' : 'false');
      data.set('engine', engine);
      data.set('scene_pack', String(unfoldPack()));
      data.set('image_model', $('#mcUnfoldModel')?.value || '');
      data.set('fidelity', engine === 'construct' ? 'publish' : 'draft');
      data.set('items', JSON.stringify(collectUnfoldItems()));
      data.set('locks', JSON.stringify({
        headline: $('#mcUnfoldHeadlineHidden')?.value || '',
        cta: $('#mcUnfoldCtaHidden')?.value || '',
        items: collectUnfoldItems(),
      }));
      status.textContent = engine === 'construct'
        ? 'Colando texto e logo no KV…'
        : 'Preparando as peças…';
      try {
        const created = await api(API.unfoldings, { method: 'POST', body: data });
        const campaign = created.campaign || created;
        const campaignId = campaign?.id;
        if (!campaignId) throw new Error('A campanha não voltou.');
        state.unfoldCampaign = await api(`${API.campaigns}/${campaignId}`);
        renderUnfoldPieces(state.unfoldCampaign);
        if (engine === 'paint') {
          const scenes = unfoldSceneList(state.unfoldCampaign);
          for (let index = 0; index < scenes.length; index += 1) {
            status.textContent = `Pintando ${index + 1} de ${scenes.length}…`;
            await api(`/parametros/api/scenes/${scenes[index].id}/prompt/generate`, {
              method: 'POST',
              body: JSON.stringify({}),
            });
            const body = new FormData();
            body.append('render_mode', 'native');
            body.append('fidelity', 'draft');
            await apiFirst([
              { url: `/parametros/api/scenes/${scenes[index].id}/image/generate`, options: { method: 'POST', body } },
              { url: `/parametros/api/scenes/${scenes[index].id}/generate`, options: { method: 'POST', body } },
            ]);
            state.unfoldCampaign = await api(`${API.campaigns}/${campaignId}`);
            renderUnfoldPieces(state.unfoldCampaign);
          }
        }
        try {
          state.campaigns = await api(API.campaigns);
          renderCampaignOptions();
          renderUnfoldLibrary();
        } catch (_) { /* o strip de custo já usa a campanha atual */ }
        renderUnfoldPieces(state.unfoldCampaign);
        status.textContent = '';
        toast('Peças fechadas.', 'success');
        focusUnfoldStep('pecas');
      } catch (error) {
        status.textContent = error.message;
        toast(error.message, 'error');
      }
    });
  }

  async function unfoldVariation(button) {
    const sceneId = button.dataset.sceneId;
    const assetId = button.dataset.assetId;
    const level = button.dataset.unfoldAb;
    if (!sceneId || !assetId) {
      toast('Feche a peça antes de pedir outra cor ou recorte.', 'warning');
      return;
    }
    await withLock(`unfold-ab-${assetId}`, button, async () => {
      await api(`/parametros/api/scenes/${sceneId}/assets/${assetId}/refine`, {
        method: 'POST',
        body: JSON.stringify({ intent: level }),
      });
      if (state.unfoldCampaign?.id) {
        state.unfoldCampaign = await api(`${API.campaigns}/${state.unfoldCampaign.id}`);
        renderUnfoldPieces(state.unfoldCampaign);
      }
      toast(level === 'ab_max' ? 'Outro recorte gerado.' : 'Outra cor gerada.', 'success');
    });
  }

  async function retryUnfoldScene(button) {
    const sceneId = button.dataset.sceneId;
    if (!sceneId) return;
    await withLock(`unfold-retry-${sceneId}`, button, async () => {
      const body = new FormData();
      body.append('render_mode', 'native');
      body.append('fidelity', 'publish');
      await apiFirst([
        { url: `/parametros/api/scenes/${sceneId}/image/generate`, options: { method: 'POST', body } },
        { url: `/parametros/api/scenes/${sceneId}/generate`, options: { method: 'POST', body } },
      ]);
      if (state.unfoldCampaign?.id) {
        state.unfoldCampaign = await api(`${API.campaigns}/${state.unfoldCampaign.id}`);
        renderUnfoldPieces(state.unfoldCampaign);
      }
      toast('Nova foto gerada para esta peça.', 'success');
    });
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
    if (!slotNode || !stageNode) return;
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
        const files = sceneReferenceFiles();
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

  function runProductionAction(action, button) {
    const found = findStep(state.activeStepId);
    if (!found) return;
    inspectorAction(action, button);
  }

  async function sceneAction(action, button) {
    const scene = activeScene();
    if (!scene) return;
    const base = `/parametros/api/scenes/${scene.id}`;
    const execute = async () => {
      try {
        if (action === 'generate-prompt') {
          await withLock(`scene-prompt-${scene.id}`, button, () => api(`${base}/prompt/generate`, {
            method: 'POST',
            body: JSON.stringify({
              delta: $('#mcSceneDelta')?.value || '',
              render_mode: activeRenderMode(),
            }),
          }));
          toast(scene.prompt ? 'Cena ajustada a partir do roteiro-mãe.' : 'Direção criada para revisão.', 'success');
        } else if (action === 'save-prompt' || action === 'approve-prompt') {
          await withLock(`scene-prompt-review-${scene.id}`, button, () => api(`${base}/prompt`, {
            method: 'PUT',
            body: JSON.stringify({
              prompt: $('#mcPromptEditor').value,
              approved: action === 'approve-prompt',
            }),
          }));
          toast(action === 'approve-prompt' ? 'Direção aprovada.' : 'Direção salva.', 'success');
        } else if (action === 'confirm-generate' || action === 'generate-image') {
          if (action === 'confirm-generate' && campaignConstruct() && !previousSceneApproved(productionScenes(), productionScenes().findIndex((item) => String(item.id) === String(scene.id)))) {
            toast('Aprove a batida anterior primeiro.', 'warning');
            return;
          }
          if (action === 'confirm-generate' && scene.prompt_status !== 'approved') {
            let nextPrompt = $('#mcPromptEditor')?.value || scene.prompt || '';
            if (!String(nextPrompt).trim()) {
              const generated = await withLock(`scene-prompt-${scene.id}`, button, () => api(`${base}/prompt/generate`, {
                method: 'POST',
                body: JSON.stringify({
                  delta: $('#mcSceneDelta')?.value || '',
                  render_mode: activeRenderMode(),
                }),
              }));
              nextPrompt = generated?.prompt || nextPrompt;
            }
            await api(`${base}/prompt`, {
              method: 'PUT',
              body: JSON.stringify({ prompt: nextPrompt, approved: true }),
            });
          }
          const files = sceneReferenceFiles();
          if (files.length > 2) throw new Error('Escolha no máximo duas referências.');
          const body = new FormData();
          files.forEach((file) => body.append('references', file));
          body.append('render_mode', activeRenderMode());
          body.append('fidelity', campaignConstruct() ? 'publish' : 'draft');
          const generated = await withLock(`scene-image-${scene.id}`, button, () => apiFirst([
            { url: `${base}/image/generate`, options: { method: 'POST', body } },
            { url: `${base}/generate`, options: { method: 'POST', body } },
          ]));
          const hold = publishHold(generated?.asset);
          toast(hold || 'Imagem gerada para revisão.', hold ? 'warning' : 'success');
        } else if (action === 'approve-asset') {
          const review = { method: 'PUT', body: JSON.stringify({
            asset_id: Number(button.dataset.assetId), status: 'approved',
          }) };
          await apiFirst([
            { url: `${base}/review`, options: review },
            { url: `/parametros/api/assets/${button.dataset.assetId}/review`, options: review },
          ]);
          state.previewAssetId = Number(button.dataset.assetId);
          const selection = {
            method: 'PUT', body: JSON.stringify({ asset_id: state.previewAssetId }),
          };
          await apiFirst([
            { url: `${base}/preview-asset`, options: selection },
            { url: `/parametros/api/productions/${state.production.id}/simulation-asset`, options: selection },
          ]);
          toast('Imagem aprovada e aplicada à simulação.', 'success');
        } else if (action === 'reject-asset') {
          const review = { method: 'PUT', body: JSON.stringify({
            asset_id: Number(button.dataset.assetId), status: 'rejected',
          }) };
          await apiFirst([
            { url: `${base}/review`, options: review },
            { url: `/parametros/api/assets/${button.dataset.assetId}/review`, options: review },
          ]);
          toast('Rascunho rejeitado. Gere de novo ou ajuste a direção.', 'success');
        } else if (action === 'edit-asset') {
          $('#mcRefineInstruction')?.focus();
          toast('Diga o ajuste ou use uma ação de direção.', 'warning');
          return;
        } else if (
          action === 'refine-asset'
          || action === 'refine-chrome'
          || action === 'refine-geometry'
          || action === 'refine-logo'
          || action === 'refine-remove-cta'
          || action === 'refine-remove-lines'
          || action === 'refine-ai-look'
          || action === 'refine-brand'
        ) {
          const assetId = Number(button.dataset.assetId);
          const instruction = ($('#mcRefineInstruction')?.value || '').trim();
          const intent = ({
            'refine-chrome': 'chrome',
            'refine-geometry': 'geometry',
            'refine-logo': 'logo',
            'refine-remove-cta': 'remove_cta',
            'refine-remove-lines': 'remove_lines',
            'refine-ai-look': 'ai_look',
            'refine-brand': 'brand',
          })[action] || (state.refineIntent || 'copy');
          if (action === 'refine-asset' && !instruction) {
            throw new Error('Descreva o ajuste em uma linha.');
          }
          await withLock(`scene-refine-${scene.id}-${assetId}`, button, () => api(
            `${base}/assets/${assetId}/refine`,
            {
              method: 'POST',
              body: JSON.stringify({
                instruction,
                intent,
                render_mode: activeRenderMode(),
              }),
            },
          ));
          const refineToasts = {
            'refine-chrome': 'Chrome removido a partir da imagem.',
            'refine-geometry': 'Peça recentrada.',
            'refine-logo': 'Logo aplicado no slot do formato.',
            'refine-remove-cta': 'CTA removido.',
            'refine-remove-lines': 'Linhas extras removidas.',
            'refine-ai-look': 'Cara de IA removida.',
            'refine-brand': 'Padrão da marca restaurado.',
          };
          toast(refineToasts[action] || 'Variante gerada a partir da imagem.', 'success');
        } else if (action === 'choose-preview') {
          state.previewAssetId = Number(button.dataset.assetId);
          const selection = {
            method: 'PUT', body: JSON.stringify({ asset_id: state.previewAssetId }),
          };
          await apiFirst([
            { url: `${base}/preview-asset`, options: selection },
            { url: `/parametros/api/productions/${state.production.id}/simulation-asset`, options: selection },
          ]);
          toast('Simulação atualizada.', 'success');
        }
        await refreshCampaign();
      } catch (error) {
        toast(error.message, 'error');
      }
    };
    await execute();
  }

  async function handleClick(event) {
    const tab = event.target.closest('[data-tab]');
    if (tab) {
      if (tab.tagName === 'A' && tab.getAttribute('href')) return;
      return activateTab(tab.dataset.tab);
    }
    const sceneButton = event.target.closest('[data-scene-id]');
    if (sceneButton) {
      state.activeSceneId = Number(sceneButton.dataset.sceneId);
      const scene = activeScene();
      state.previewAssetId = scene?.preview_asset_id
        || scene?.approved_asset_id
        || sceneAssets(scene).find((asset) => asset.status === 'approved')?.id
        || sceneAssets(scene)[0]?.id
        || null;
      renderProduction();
      return;
    }
    const renderModeButton = event.target.closest('[data-render-mode]');
    if (renderModeButton) {
      state.renderMode = renderModeButton.dataset.renderMode;
      renderProduction();
      return;
    }
    const refineIntent = event.target.closest('[data-refine-intent]');
    if (refineIntent) {
      state.refineIntent = refineIntent.dataset.refineIntent;
      $$('[data-refine-intent]').forEach((button) => {
        button.classList.toggle('is-active', button === refineIntent);
      });
      return;
    }
    const sceneActionButton = event.target.closest('[data-scene-action]');
    if (sceneActionButton) {
      await sceneAction(sceneActionButton.dataset.sceneAction, sceneActionButton);
      return;
    }
    const composeVariation = event.target.closest('[data-compose-variation]');
    if (composeVariation) {
      state.selectedVariationId = composeVariation.dataset.composeVariation;
      renderComposeVariations();
      return;
    }
    const generatorFormat = event.target.closest('[data-generator-format]');
    if (generatorFormat) {
      state.generatorFormatId = Number(generatorFormat.dataset.generatorFormat);
      if (state.enhancedBrief?.scenes?.length !== sceneCountForFormat(generatorSelectedFormat())) {
        state.enhancedBrief = null;
        renderStoryboardEditor();
      }
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
    const deviceButton = event.target.closest('[data-preview-device]');
    if (deviceButton) {
      state.previewDevice = deviceButton.dataset.previewDevice;
      const format = selectedLibraryFormat();
      if (format) renderFormatStage(format, true);
      renderProductionStage();
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
      runProductionAction(action, button);
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
          placement_zone: state.placementDraft?.placement_zone
            || resolvePlacementZone(
              state.formats.find((item) => String(item.id) === String(form.dataset.formatId)),
              state.placementDraft,
              'desktop',
            ),
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
    } else if (action === 'close-publish') {
      $('#mcPublishDialog')?.close();
    } else if (action === 'open-creative-line') {
      selectBrand(button.dataset.clientId);
      $('#mcCreativeLine').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
            if (Number(state.selectedBrandId) === Number(button.dataset.clientId)) {
              selectBrand(null);
            } else {
              renderClients();
            }
            renderClientOptions();
            toast('Perfil removido.', 'success');
          } catch (error) { toast(error.message, 'error'); }
        },
      });
    }
  }

  // ====== EVENTS ======
  document.addEventListener('DOMContentLoaded', () => {
    try {
    bind('#mcApp', 'click', handleClick);
    setupPlacementInteraction();
    bind('#mcLibraryDetail', 'input', (event) => {
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
    bind('#mcResetPlacement', 'click', () => {
      if (!state.originalPlacement || !selectedLibraryFormat()) return;
      state.placementDraft = JSON.parse(JSON.stringify(state.originalPlacement));
      renderFormatStage(selectedLibraryFormat(), true);
    });
    bind('#mcCampaignForm', 'submit', createCampaign);
    bind('#mcEnhanceBrief', 'click', (event) => enhanceCampaignBrief(event.currentTarget));
    setupBrandDropzone('#mcCampaignPackDrop', '#mcCampaignPackFile', acceptCampaignPackFiles);
    $('#mcCampaignPackUrl')?.addEventListener('change', () => {
      readCampaignPack().catch((error) => toast(error.message, 'warning'));
    });
    $('#mcCampaignPackPreviews')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-pack-remove]');
      if (!button) return;
      const index = Number(button.dataset.packRemove);
      state.campaignPack.files = state.campaignPack.files.filter((_, offset) => offset !== index);
      URL.revokeObjectURL(state.campaignPack.previewUrls[index]);
      state.campaignPack.previewUrls = state.campaignPack.previewUrls.filter((_, offset) => offset !== index);
      renderCampaignPackPreviews();
      if (state.campaignPack.files.length || state.campaignPack.url) {
        readCampaignPack().catch((error) => toast(error.message, 'warning'));
      } else {
        state.campaignPack.extracted = {};
        state.campaignPack.sources = [];
        const status = $('#mcCampaignPackStatus');
        if (status) status.textContent = '';
      }
    });
    setupSceneReferenceDrop();
    bind('#mcStoryboardEditor', 'input', (event) => {
      const index = Number(event.target.dataset.storyboardScene);
      if (!Number.isInteger(index) || !state.enhancedBrief?.scenes?.[index]) return;
      state.enhancedBrief.scenes[index].description = event.target.value;
    });
    bind('#mcClientForm', 'submit', saveClient);
    $('#mcNewBrand')?.addEventListener('click', () => selectBrand(null));
    $('#mcClientTableBody')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-select-brand]');
      if (!button) return;
      selectBrand(button.dataset.selectBrand);
    });
    bind('#mcAnalyzeBrand', 'click', analyzeBrand);
    setupBrandDropzone(
      '#mcBrandDropzone',
      'input[name="brand_images"]',
      addBrandFiles,
    );
    setupBrandDropzone(
      '#mcLogoDropzone',
      'input[name="logo"]',
      (files) => {
        const file = Array.from(files || [])[0];
        if (!file) return;
        const input = $('#mcLogoDropzone input[name="logo"]');
        const root = $('#mcLogoDropped');
        if (!input || !root) return;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        root.hidden = false;
        root.innerHTML = `<article><img src="${URL.createObjectURL(file)}" alt=""><span><strong>${escapeHtml(file.name)}</strong><small>Pronto para salvar</small></span></article>`;
      },
    );
    setupBrandDropzone(
      '#mcCreativeLineDropzone',
      'input[name="creative_line_images"]',
      addCreativeLineFiles,
    );
    bind('#mcCreativeLineClient', 'change', (event) => {
      state.creativeLineFiles = [];
      renderCreativeLineUploads();
      selectBrand(event.target.value || null);
    });
    bind('#mcCreativeLineUploads', 'click', (event) => {
      const remove = event.target.closest('[data-creative-remove]');
      if (!remove) return;
      state.creativeLineFiles.splice(Number(remove.dataset.creativeRemove), 1);
      renderCreativeLineUploads();
      renderCreativeLineWorkspace();
    });
    bind('#mcCreativeLineLibrary', 'click', (event) => {
      const remove = event.target.closest('[data-creative-delete]');
      const client = creativeLineClient();
      if (!remove || !client) return;
      window.showConfirm({
        title: 'Remover referência criativa',
        message: 'A próxima análise deixará de usar esta peça como evidência.',
        theme: 'danger',
        confirmText: 'Remover',
        onConfirm: async () => {
          try {
            await api(
              `${API.clients}/${client.id}/brand-assets/${remove.dataset.creativeDelete}`,
              { method: 'DELETE' },
            );
            state.clients = await api(API.clients);
            renderClients();
            renderCreativeLineWorkspace();
            toast('Referência criativa removida.', 'success');
          } catch (error) {
            toast(error.message, 'error');
          }
        },
      });
    });
    bind('#mcAnalyzeCreativeLine', 
      'click',
      (event) => learnCreativeLine(event.currentTarget),
    );
    bind('#mcBrandPalette', 'click', (event) => {
      const colorButton = event.target.closest('[data-palette-color]');
      if (!colorButton) return;
      const form = $('#mcClientForm');
      const next = colorButton.dataset.paletteColor;
      const previous = form.elements.primary_color.value;
      if (previous && previous !== next) form.elements.secondary_color.value = previous;
      form.elements.primary_color.value = next;
      toast(`${next} definida como cor principal.`, 'success');
    });
    bind('#mcBrandCurator', 'click', (event) => {
      const filter = event.target.closest('[data-brand-filter]');
      if (filter) {
        state.brandAssetFilter = filter.dataset.brandFilter;
        $$('[data-brand-filter]', $('#mcBrandFilters')).forEach(
          (button) => button.classList.toggle('is-active', button === filter),
        );
        renderBrandCandidates();
        return;
      }
      const select = event.target.closest('[data-brand-select]');
      if (select) {
        const key = select.dataset.brandSelect;
        if (state.selectedBrandAssets.has(key)) {
          state.selectedBrandAssets.delete(key);
          if (state.primaryBrandAssetUrl === key) state.primaryBrandAssetUrl = null;
        } else {
          if (state.selectedBrandAssets.size >= 9) {
            toast('Use até oito referências e um logo por perfil.', 'warning');
            return;
          }
          state.selectedBrandAssets.add(key);
        }
        renderBrandCandidates();
        return;
      }
      const primary = event.target.closest('[data-brand-primary]');
      if (primary) {
        const key = primary.dataset.brandPrimary;
        if (!state.selectedBrandAssets.has(key) && state.selectedBrandAssets.size >= 9) {
          toast('Remova uma referência antes de definir outro logo.', 'warning');
          return;
        }
        state.primaryBrandAssetUrl = key;
        state.primaryBrandFileIndex = -1;
        state.selectedBrandAssets.add(key);
        setFormValue($('#mcClientForm'), 'logo_url', key);
        renderBrandCandidates();
        renderDroppedBrandFiles();
      }
    });
    bind('#mcBrandDropped', 'click', (event) => {
      const logo = event.target.closest('[data-dropped-logo]');
      const remove = event.target.closest('[data-dropped-remove]');
      if (logo) {
        state.primaryBrandFileIndex = Number(logo.dataset.droppedLogo);
        state.primaryBrandAssetUrl = null;
      }
      if (remove) {
        const index = Number(remove.dataset.droppedRemove);
        const removed = state.brandFiles[index];
        state.brandFiles.splice(index, 1);
        if (removed) {
          const removedKey = brandFileKey(removed);
          state.creativeLineFiles = state.creativeLineFiles.filter(
            (file) => brandFileKey(file) !== removedKey,
          );
        }
        if (state.primaryBrandFileIndex === index) state.primaryBrandFileIndex = -1;
        else if (state.primaryBrandFileIndex > index) state.primaryBrandFileIndex -= 1;
      }
      renderDroppedBrandFiles();
      renderBrandCandidates();
      syncCreativeLineFromBrandFiles();
    });
    document.addEventListener('paste', (event) => {
      if (!$('#mcClientForm')?.offsetParent) return;
      const images = Array.from(event.clipboardData?.files || []).filter(
        (file) => file.type.startsWith('image/'),
      );
      if (images.length) {
        event.preventDefault();
        if ($('#mcCreativeLine')?.contains(document.activeElement)) {
          addCreativeLineFiles(images);
        } else {
          addBrandFiles(images);
        }
      }
    });
    bind('#mcCampaignClient', 'change', () => {
      renderClientPreview();
      renderGeneratorSummary();
    });
    bind('#mcCampaignForm', 'input', renderGeneratorSummary);
    bind('#mcGeneratorFormatCategory', 'change', renderGeneratorFormats);
    $('#mcPreparePathBar')?.addEventListener('change', (event) => {
      if (event.target.name === 'prepare_engine') {
        const select = $('#mcPrepareModel');
        if (select && prepareEngine() === 'construct') {
          select.value = 'black-forest-labs/flux.2-pro';
        } else if (select) {
          select.value = 'openai/gpt-image-2';
        }
      }
      if (event.target.name === 'prepare_pack') {
        if (state.enhancedBrief?.scenes?.length !== sceneCountForFormat(generatorSelectedFormat())) {
          state.enhancedBrief = null;
          renderStoryboardEditor();
        }
        renderContextDesign();
      }
      renderGeneratorFormatPreview();
      renderGeneratorSummary();
      quotePreparePath();
    });
    $('#mcPrepareModel')?.addEventListener('change', quotePreparePath);
    bind('#mcCampaignSelect', 'change', (event) => selectCampaign(event.target.value).catch((error) => toast(error.message, 'error')));
    $('#mcOpenPublishBatch')?.addEventListener('click', () => {
      openPublishModal([state.production].filter(Boolean), state.campaign?.id);
    });
    $('#mcUnfoldOpenPublish')?.addEventListener('click', () => {
      openPublishModal(state.unfoldCampaign?.productions || [], state.unfoldCampaign?.id);
    });
    bind('#mcProductionViewer', 'change', (event) => {
      state.selectedViewerProfileId = Number(event.target.value) || null;
      renderProductionStage();
    });
    const openShareDialog = () => {
      if (!shareableCampaignAssets().length) {
        toast('Aprove ao menos uma imagem antes de publicar.', 'warning');
        return;
      }
      $('#mcShareForm [name="title"]').value = state.campaign?.name || '';
      renderShareEnvironments();
      $('#mcShareDialog').showModal();
    };
    $('#mcCreatePublicLink')?.addEventListener('click', openShareDialog);
    $$('.mc-open-share').forEach((button) => button.addEventListener('click', openShareDialog));
    $('#mcGenerateAllPrompts')?.addEventListener('click', (event) => {
      const button = event.currentTarget;
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
      run();
    });
    $('#mcFormatSearch')?.addEventListener('input', renderFormatBrowser);
    $('#mcFormatCategory')?.addEventListener('change', renderFormatBrowser);
    bind('#mcLibrarySearch', 'input', renderLibrary);
    bind('#mcLibraryCategory', 'change', renderLibrary);
    bind('#mcUnfoldClient', 'change', () => {
      renderUnfoldBrand();
      syncUnfoldProgress();
    });
    $$('.mc-unfold-steps [data-unfold-step]').forEach((button) => {
      button.addEventListener('click', () => focusUnfoldStep(button.dataset.unfoldStep));
    });
    $('#mcUnfoldFormatList')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-unfold-format]');
      if (!button) return;
      const id = String(button.dataset.unfoldFormat);
      if (state.unfoldFormatIds.has(id)) state.unfoldFormatIds.delete(id);
      else state.unfoldFormatIds.add(id);
      renderUnfoldFormats();
      quoteUnfoldPath();
    });
    $('#mcUnfoldFormatsAll')?.addEventListener('click', () => {
      unfoldFormats().forEach((format) => state.unfoldFormatIds.add(String(format.id)));
      renderUnfoldFormats();
      quoteUnfoldPath();
    });
    $('#mcUnfoldFormatsNone')?.addEventListener('click', () => {
      state.unfoldFormatIds.clear();
      renderUnfoldFormats();
      quoteUnfoldPath();
    });
    setupBrandDropzone('#mcUnfoldDropzone', '#mcUnfoldFile', acceptUnfoldKv);
    $('#mcUnfoldDropzone')?.addEventListener('paste', (event) => {
      acceptUnfoldKv(event.clipboardData?.files);
    });
    $('#mcUnfoldUseExample')?.addEventListener('click', (event) => {
      useUnfoldExample(event.currentTarget).catch((error) => toast(error.message, 'error'));
    });
    $('#mcUnfoldUseGenerated')?.addEventListener('click', () => {
      const library = $('#mcUnfoldLibrary');
      if (!library) return;
      library.hidden = !library.hidden;
      if (!library.hidden) {
        loadUnfoldLibrary().catch((error) => toast(error.message, 'error'));
      }
    });
    $('#mcUnfoldLibraryGrid')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-unfold-asset]');
      if (!button) return;
      chooseUnfoldAsset(button);
    });
    $('#mcUnfoldReviewName')?.addEventListener('input', syncUnfoldReview);
    $('#mcUnfoldItems')?.addEventListener('input', syncUnfoldReview);
    $('#mcUnfoldItems')?.addEventListener('change', syncUnfoldReview);
    $('#mcUnfoldPathBar')?.addEventListener('change', (event) => {
      if (event.target.name === 'unfold_engine') {
        const select = $('#mcUnfoldModel');
        if (select && unfoldEngine() === 'construct') {
          select.value = 'black-forest-labs/flux.2-pro';
        } else if (select) {
          select.value = 'openai/gpt-image-2';
        }
        renderUnfoldItems(state.unfoldItems);
        renderUnfoldFormats();
      }
      if (event.target.name === 'unfold_pack') {
        renderUnfoldFormats();
      }
      syncUnfoldReview();
      quoteUnfoldPath();
      syncUnfoldProgress();
    });
    $('#mcUnfoldModel')?.addEventListener('change', quoteUnfoldPath);
    $('#mcUnfoldGenerate')?.addEventListener('click', (event) => {
      createUnfolding(event.currentTarget).catch((error) => toast(error.message, 'error'));
    });
    $('#mcUnfoldPieces')?.addEventListener('click', (event) => {
      const retry = event.target.closest('[data-unfold-retry]');
      if (retry) {
        retryUnfoldScene(retry).catch((error) => toast(error.message, 'error'));
        return;
      }
      const button = event.target.closest('[data-unfold-ab]');
      if (!button) return;
      unfoldVariation(button).catch((error) => toast(error.message, 'error'));
    });
    document.addEventListener('change', (event) => {
      const box = event.target.closest('[data-publish-asset]');
      if (!box) return;
      const campaignId = String(box.dataset.publishCampaign || '');
      const id = String(box.dataset.publishAsset);
      if (!state.publishPicks[campaignId]) state.publishPicks[campaignId] = new Set();
      if (box.checked) state.publishPicks[campaignId].add(id);
      else state.publishPicks[campaignId].delete(id);
      refreshPublishModal();
    });
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-publish-batch]');
      if (!button) return;
      publishSelectedBatch(button).catch((error) => toast(error.message, 'error'));
    });
    bind('#mcRefreshHistory', 'click', loadHistory);
    bind('#mcHistoryCampaign', 'change', loadHistory);
    $('#mcHistoryFinish')?.addEventListener('click', (event) => {
      const publish = event.target.closest('[data-history-publish]');
      if (publish) {
        publishHistoryCampaign(publish).catch((error) => toast(error.message, 'error'));
        return;
      }
      const video = event.target.closest('[data-history-video]');
      if (video) {
        prepareHistoryVideo(video).catch((error) => toast(error.message, 'error'));
      }
    });
    $('#mcModelingLedger')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-modeling-id]');
      if (!button) return;
      const select = $('#mcHistoryCampaign');
      const next = String(button.dataset.modelingId) === String(select.value) ? '' : button.dataset.modelingId;
      select.value = next;
      loadHistory();
    });
    bind('#mcLogoForm', 'submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const id = form.elements.client_id.value;
      const logo = form.elements.logo.files[0];
      if (!logo) {
        toast('Arraste ou escolha uma imagem para o logo.', 'warning');
        return;
      }
      const data = new FormData();
      data.append('logo', logo);
      try {
        await api(`${API.clients}/${id}/logo`, { method: 'POST', body: data });
        state.clients = await api(API.clients);
        renderClients(); renderClientOptions();
        $('#mcLogoDialog').close();
        form.reset();
        $('#mcLogoDropped').hidden = true;
        $('#mcLogoDropped').innerHTML = '';
        toast('Logo atualizado.', 'success');
      } catch (error) { toast(error.message, 'error'); }
    });
    bind('#mcShareForm', 'submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = $('button[type="submit"]', form);
      await withLock('create-public-link', button, async () => {
        try {
          const payload = Object.fromEntries(new FormData(form));
          payload.asset_ids = shareableCampaignAssets().map((asset) => asset.id);
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
          const href = openPublicLink(created.public_url);
          await navigator.clipboard.writeText(href).catch(() => {});
          toast('Link público criado e aberto.', 'success');
        } catch (error) { toast(error.message, 'error'); }
      });
    });
    $('#mcPromptResultBody')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-copy-prompt]');
      if (!button) return;
      const text = button.closest('details').querySelector('pre').textContent;
      try { await navigator.clipboard.writeText(text); toast('Prompt copiado.', 'success'); }
      catch (_) { toast('Não foi possível copiar automaticamente.', 'error'); }
    });
    const tabAliases = {
      gerador: 'preparar',
      variacoes: 'produzir',
      desdobramentos: 'desdobrar',
      biblioteca: 'formatos',
      clientes: 'marcas',
    };
    const requestedTab = tabAliases[location.hash.replace('#', '')] || location.hash.replace('#', '');
    const currentPage = $('#mcApp')?.dataset.mcPage;
    if (!currentPage || currentPage === 'hub') {
      activateTab(['preparar', 'produzir', 'desdobrar', 'formatos', 'marcas', 'historico'].includes(requestedTab) ? requestedTab : 'preparar', false);
    }
    } catch (error) {
      console.error(error);
      setPageError('A mesa não ligou por completo. Recarregue a página.');
    }
    loadBaseData();
  });
})();
