(() => {
  const API = {
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/campaigns',
    brand: (id) => `/parametros/api/design-system/brand/${id}`,
    refine: (id) => `/parametros/api/design-system/brand/${id}/refine`,
    approve: (id) => `/parametros/api/design-system/brand/${id}/approve`,
    tokens: (id) => `/parametros/api/design-system/brand/${id}/tokens`,
    compose: (id) => `/parametros/api/design-system/brand/${id}/compose`,
    loop: (id) => `/parametros/api/design-system/brand/${id}/loop`,
    track: (id, track) => `/parametros/api/design-system/brand/${id}/tracks/${track}`,
    adapt: (id) => `/parametros/api/design-system/brand/${id}/adapt`,
    campaign: (id) => `/parametros/api/design-system/campaign/${id}`,
    campaignAdapt: (id) => `/parametros/api/design-system/campaign/${id}/adapt`,
  };

  const COLOR_TOKENS = new Set(['paper', 'ink', 'accent', 'muted', 'cta_ink', 'highlight', 'hairline']);
  const CORE_ROLES = new Set(['visual', 'logo', 'headline', 'support', 'cta']);

  const state = {
    clients: [],
    campaigns: [],
    clientId: 'centralcomm',
    campaignId: '',
    format: 'iab-billboard',
    layers: 4,
    highlight: '',
    swaps: [],
    mode: 'sistema',
    archetype: 'brand',
    looping: false,
    system: null,
    patchTimer: 0,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function readJson(response) {
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || 'O Design System Ads não concluiu.');
    }
    return payload.data;
  }

  function setStatus(text) {
    const node = $('mcDsaStatus');
    if (node) node.textContent = text || '';
  }

  function currentId() {
    return state.clientId || 'centralcomm';
  }

  function isCampaign() {
    return Boolean(state.campaignId);
  }

  function brandUrl() {
    return `/lab/design-system/marca/${currentId()}`;
  }

  function pieceUrl(system) {
    if (system?.specimen_url && state.mode === 'peca') {
      const base = system.specimen_url;
      return state.highlight ? `${base}${base.includes('?') ? '&' : '?'}highlight=${encodeURIComponent(state.highlight)}` : base;
    }
    if (isCampaign()) {
      return `/lab/design-system/campanha/${state.campaignId}?format=${state.format}&layers=${state.layers}${state.highlight ? `&highlight=${encodeURIComponent(state.highlight)}` : ''}`;
    }
    return `${brandUrl()}?format=${state.format}&layers=${state.layers}${state.highlight ? `&highlight=${encodeURIComponent(state.highlight)}` : ''}`;
  }

  function setMode(mode) {
    state.mode = mode;
    const root = $('mcDsa');
    if (root) root.dataset.mode = mode;
    document.querySelectorAll('.mc-dsa-modes [data-mode]').forEach((button) => {
      const active = button.getAttribute('data-mode') === mode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('.mc-dsa-pane').forEach((pane) => {
      pane.hidden = pane.getAttribute('data-pane') !== mode;
    });
    syncFrames();
  }

  function renderClients() {
    const select = $('mcDsaClient');
    if (!select) return;
    const extras = state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
    )).join('');
    select.innerHTML = `<option value="centralcomm">CentralComm Ads</option>${extras}`;
    select.value = currentId();
  }

  function renderCampaigns() {
    const select = $('mcDsaCampaign');
    if (!select) return;
    const extras = state.campaigns
      .filter((item) => !state.clientId || state.clientId === 'centralcomm' || String(item.client_id) === String(state.clientId))
      .map((item) => (
        `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
      )).join('');
    select.innerHTML = `<option value="">Só a marca</option><option value="centralcomm-verao">Verao · CentralComm</option>${extras}`;
    if (state.campaignId && ![...select.options].some((item) => item.value === String(state.campaignId))) {
      state.campaignId = '';
    }
    select.value = state.campaignId;
  }

  function renderFormats(system) {
    const host = $('mcDsaFormats');
    if (!host) return;
    const formats = system?.iab_formats || [];
    if (!formats.length) return;
    if (!formats.some((item) => item.key === state.format)) {
      state.format = 'iab-billboard';
      if (!formats.some((item) => item.key === state.format)) state.format = formats[0].key;
    }
    host.innerHTML = formats.map((item) => {
      const width = Number(item.width) || 970;
      const height = Number(item.height) || 250;
      const active = item.key === state.format ? ' is-active' : '';
      return (
        `<button type="button" role="option" class="mc-dsa-format${active}" data-format="${escapeHtml(item.key)}" aria-selected="${item.key === state.format}">`
        + `<span class="mc-dsa-format-box" style="aspect-ratio:${width}/${height}"></span>`
        + `<strong>${escapeHtml(item.size_label || item.label)}</strong>`
        + `<em>${escapeHtml(item.density || '')}</em>`
        + `</button>`
      );
    }).join('');
  }

  function renderLayerControl(system) {
    const input = $('mcDsaLayerCount');
    const label = $('mcDsaLayerLabel');
    const spec = system?.layers || {};
    if (input) {
      input.min = spec.min || 4;
      input.max = spec.max || 40;
      input.value = state.layers;
    }
    if (label) {
      const extras = Math.max(0, state.layers - 4);
      label.textContent = extras ? `${state.layers} camadas · ${extras} no poço` : '4 camadas';
    }
  }

  function renderLayerList(system) {
    const list = $('mcDsaLayerList');
    if (!list) return;
    const layers = [...(system?.adapt?.layers || [])].sort((left, right) => (right.z || 0) - (left.z || 0));
    list.innerHTML = layers.map((item) => {
      const selected = state.highlight === item.id ? ' is-selected' : '';
      const parked = item.parked ? ' no poço' : '';
      const core = CORE_ROLES.has(item.role) && !item.parked;
      return (
        `<li class="${core ? 'is-core' : 'is-extra'}">`
        + `<button type="button" class="mc-dsa-layer${selected}" data-layer="${escapeHtml(item.id)}">`
        + `<strong>${escapeHtml(item.label)}</strong>`
        + `<small>${escapeHtml(item.role)}${parked} · ${Math.round(item.w)}×${Math.round(item.h)}</small>`
        + `</button>`
        + `<span class="mc-dsa-layer-move">`
        + `<button type="button" data-move="${escapeHtml(item.id)}" data-dir="-1" aria-label="Subir">↑</button>`
        + `<button type="button" data-move="${escapeHtml(item.id)}" data-dir="1" aria-label="Descer">↓</button>`
        + `</span></li>`
      );
    }).join('');
  }

  function renderBoard(system) {
    const host = $('mcDsaBoard');
    if (!host) return;
    const tokens = system?.tokens || {};
    const copy = system?.ad_copy || {};
    const pairs = system?.contrast?.pairs || {};
    const swatches = ['paper', 'ink', 'accent', 'highlight']
      .map((key) => (
        `<button type="button" class="mc-dsa-swatch" data-token="${key}" title="${escapeHtml(key)} ${escapeHtml(tokens[key] || '')}" style="--swatch:${escapeHtml(tokens[key] || '#fff')}"><i></i></button>`
      )).join('');
    host.innerHTML = (
      `<div class="mc-dsa-swatches">${swatches}</div>`
      + `<p class="mc-dsa-lockup" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif;font-weight:${escapeHtml(tokens['weight-display'] || '700')};letter-spacing:${escapeHtml(tokens.tracking || '0')}">${escapeHtml(copy.headline || '')}</p>`
      + `<p class="mc-dsa-support-line">${escapeHtml(copy.support || '')}</p>`
      + `<span class="mc-dsa-cta-chip" style="background:${escapeHtml(tokens.accent || '#111')};color:${escapeHtml(tokens.cta_ink || '#fff')};border-radius:${escapeHtml(tokens['cta-radius'] || '0.25rem')};padding:${escapeHtml(tokens['cta-pad'] || '0.7em 1.2em')};box-shadow:${escapeHtml(tokens['cta-shadow'] || 'none')}">${escapeHtml(copy.cta || '')}</span>`
      + `<dl class="mc-dsa-contrast${system?.contrast?.passed ? ' is-ok' : ' is-bad'}">`
      + `<div><dt>Texto</dt><dd>${pairs.ink_on_paper || '—'} : 1</dd></div>`
      + `<div><dt>Botão</dt><dd>${pairs.cta_on_accent || '—'} : 1</dd></div>`
      + `</dl>`
    );
  }

  function renderCopy(system) {
    const form = $('mcDsaCopy');
    if (!form) return;
    const copy = system?.ad_copy || {};
    ['headline', 'support', 'cta', 'legal'].forEach((key) => {
      const field = form.elements[key];
      if (field && document.activeElement !== field) field.value = copy[key] || '';
    });
  }

  function renderGrounds(system) {
    const host = $('mcDsaGrounds');
    if (!host) return;
    const active = system?.tokens?.['ground-kind'] || 'paper';
    const shortGround = { paper: 'Papel', wash: 'Lavagem', image: 'Imagem' };
    const rows = system?.backgrounds || [
      { id: 'paper', label: 'Papel' },
      { id: 'wash', label: 'Lavagem' },
      { id: 'image', label: 'Imagem' },
    ];
    const tokens = system?.tokens || {};
    const fill = { paper: tokens.paper, wash: tokens.ink, image: tokens.highlight };
    host.innerHTML = rows.map((item) => (
      `<button type="button" class="mc-dsa-ground${item.id === active ? ' is-active' : ''}" data-ground="${escapeHtml(item.id)}" style="--swatch:${escapeHtml(fill[item.id] || '#fff')}"><i></i>${escapeHtml(shortGround[item.id] || item.label)}</button>`
    )).join('');
    const url = $('mcDsaGroundUrl');
    if (url && document.activeElement !== url) url.value = system?.tokens?.ground || '';
  }

  function renderTracks(system) {
    const host = $('mcDsaTracks');
    if (!host) return;
    const shortTrack = { packshot: 'Produto', kv: 'KV', lifestyle: 'Cena', wash: 'Tinta' };
    const tracks = system?.tracks || [];
    host.innerHTML = tracks.map((item) => {
      const label = shortTrack[item.id] || item.label;
      return (
        `<button type="button" class="mc-dsa-track" data-track="${escapeHtml(item.id)}">`
        + (item.url
          ? `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(label)}">`
          : `<span class="mc-dsa-track-empty">${escapeHtml(label)}</span>`)
        + `</button>`
      );
    }).join('');
  }

  function renderGroups(system) {
    const host = $('mcDsaGroups');
    if (!host) return;
    const groups = system?.token_groups || [];
    host.innerHTML = groups.map((group, index) => (
      `<details class="mc-dsa-group"${index === 0 ? ' open' : ''}><summary>${escapeHtml(group.label)}</summary>`
      + group.tokens.map((item) => {
        const value = item.value || '';
        if (COLOR_TOKENS.has(item.id)) {
          return (
            `<label class="mc-dsa-color"><span>${escapeHtml(item.id)}</span>`
            + `<input type="color" data-token="${escapeHtml(item.id)}" value="${escapeHtml(/^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#000000')}">`
            + `<input type="text" data-token="${escapeHtml(item.id)}" value="${escapeHtml(value)}" maxlength="7"></label>`
          );
        }
        return (
          `<label class="mc-dsa-field"><span>${escapeHtml(item.id)}</span>`
          + `<input type="text" data-token="${escapeHtml(item.id)}" value="${escapeHtml(String(value))}" maxlength="80"></label>`
        );
      }).join('')
      + `</details>`
    )).join('');
  }

  function renderIntents(system) {
    const host = $('mcDsaIntents');
    if (!host) return;
    const intents = system?.intents || [];
    host.innerHTML = intents.map((item) => (
      `<button type="button" class="mc-dsa-intent" data-intent="${escapeHtml(item.id)}" title="${escapeHtml(item.hint || '')}">${escapeHtml(item.label)}</button>`
    )).join('');
  }

  function renderPasses(system) {
    const host = $('mcDsaPasses');
    if (!host) return;
    const passes = system?.passes || [];
    if (!passes.length) {
      host.innerHTML = '<li>Nenhuma melhoria ainda. Escolha um eixo.</li>';
      return;
    }
    host.innerHTML = passes.map((item, index) => {
      const patches = (item.patches || []).map((patch) => `${patch.token_id} → ${patch.css}`).join('; ');
      const notes = (item.notes || []).join(' ');
      return `<li><strong>${index + 1}/${passes.length}</strong> ${escapeHtml(notes || 'Passe')}<small>${escapeHtml(patches || 'sem patch')}</small></li>`;
    }).join('');
  }

  function renderCatalog(system) {
    const host = $('mcDsaCatalog');
    if (!host) return;
    const catalog = system?.catalog || {};
    const dna = catalog.dna || system?.dna || {};
    const tokens = system?.tokens || {};
    const copy = system?.ad_copy || {};
    const personality = (dna.personality || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const must = (dna.must || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const avoid = (dna.avoid || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const colors = (catalog.token_roles || []).find((item) => item.id === 'colors');
    const swatches = (colors?.items || []).map((item) => (
      `<i style="--swatch:${escapeHtml(item.value || '#fff')}" title="${escapeHtml(item.label)} ${escapeHtml(item.value || '')}"></i>`
    )).join('');
    const components = (catalog.components || []).map((item) => (
      `<article class="mc-dsa-comp" data-comp="${escapeHtml(item.id)}">`
      + (item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : `<span class="mc-dsa-comp-mark" style="color:${escapeHtml(tokens.ink || '#1E4D4F')};font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">${escapeHtml(item.text || item.label)}</span>`)
      + `<strong>${escapeHtml(item.label)}</strong>`
      + `<small>P${item.priority}</small>`
      + `</article>`
    )).join('');
    const formats = (catalog.iab_formats || []).map((item) => (
      `<button type="button" class="mc-dsa-format" data-format="${escapeHtml(item.key)}">`
      + `<span class="mc-dsa-format-box" style="aspect-ratio:${item.width || 1}/${item.height || 1}"></span>`
      + `<strong>${escapeHtml(item.size_label || item.label)}</strong>`
      + `<em>${escapeHtml(item.density || '')}</em>`
      + `</button>`
    )).join('');
    const archetypes = (catalog.archetypes || []).map((item) => (
      `<button type="button" class="mc-dsa-arch${item.active ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format)}">`
      + `<span class="mc-dsa-arch-stage" style="background:${escapeHtml(item.ground === 'wash' ? tokens.ink : tokens.paper)};color:${escapeHtml(item.ground === 'wash' ? tokens.paper : tokens.ink)}">`
      + `<strong>${escapeHtml(item.headline || item.label)}</strong>`
      + `<em>${escapeHtml(item.cta || '')}</em>`
      + `</span>`
      + `<b>${escapeHtml(item.label)}</b>`
      + `</button>`
    )).join('');
    const flow = (catalog.flow || []).map((item) => (
      `<li class="${item.current ? 'is-current' : ''}${item.done ? ' is-done' : ''}">${escapeHtml(item.label)}</li>`
    )).join('');
    host.innerHTML = (
      `<p class="mc-dsa-tagline">${escapeHtml(catalog.tagline || '')}</p>`
      + `<section class="mc-dsa-block" data-block="dna">`
      + `<h2>DNA</h2>`
      + `<div class="mc-dsa-dna">`
      + (dna.logo_url || dna.product_url ? `<img src="${escapeHtml(dna.product_url || dna.logo_url)}" alt="">` : '')
      + `<div>`
      + `<p class="mc-dsa-lockup" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif;font-weight:${escapeHtml(tokens['weight-display'] || '700')}">${escapeHtml(copy.headline || dna.name || '')}</p>`
      + `<ul class="mc-dsa-chips">${personality}</ul>`
      + `</div>`
      + `<div class="mc-dsa-type-spec" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">Aa <small>${escapeHtml(tokens['font-display'] || 'Inter')}</small></div>`
      + `<div class="mc-dsa-dna-swatches">${swatches}</div>`
      + `</div>`
      + `<form class="mc-dsa-dna-form" id="mcDsaDna">`
      + `<label>Personalidade <input name="personality" value="${escapeHtml((dna.personality || []).join(', '))}" maxlength="180"></label>`
      + `<label>Obrigatório <input name="must" value="${escapeHtml((dna.must || []).join(', '))}" maxlength="240"></label>`
      + `<label>Evitar <input name="avoid" value="${escapeHtml((dna.avoid || []).join(', '))}" maxlength="240"></label>`
      + `</form>`
      + `<div class="mc-dsa-rules"><p>Fazer</p><ul>${must}</ul><p>Não fazer</p><ul>${avoid}</ul></div>`
      + `</section>`
      + `<section class="mc-dsa-block" data-block="tokens"><h2>Tokens</h2><div class="mc-dsa-token-roles">${(catalog.token_roles || []).map((role) => (
        `<article><h3>${escapeHtml(role.label)}</h3>`
        + (role.id === 'cta'
          ? `<span class="mc-dsa-cta-chip" style="background:${escapeHtml(tokens.accent || '#111')};color:${escapeHtml(tokens.cta_ink || '#fff')}">${escapeHtml(copy.cta || 'CTA')}</span>`
          : role.id === 'type'
            ? `<p class="mc-dsa-lockup" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif;font-weight:${escapeHtml(tokens['weight-display'] || '700')}">${escapeHtml(copy.headline || 'Aa')}</p>`
            : role.id === 'legal'
              ? `<small>${escapeHtml(copy.legal || '')}</small>`
              : `<div class="mc-dsa-dna-swatches">${(role.items || []).map((item) => `<i style="--swatch:${escapeHtml(item.value || '#fff')}"></i>`).join('')}</div>`)
        + `</article>`
      )).join('')}</div></section>`
      + `<section class="mc-dsa-block" data-block="components"><h2>Componentes</h2><div class="mc-dsa-comps">${components}</div></section>`
      + `<section class="mc-dsa-block" data-block="formats"><h2>Formatos IAB</h2><div class="mc-dsa-formats is-catalog">${formats}</div></section>`
      + `<section class="mc-dsa-block" data-block="templates"><h2>Templates</h2><div class="mc-dsa-arches">${archetypes}</div></section>`
      + `<section class="mc-dsa-block" data-block="flow"><h2>Recomposição</h2><ol class="mc-dsa-flow">${flow}</ol><p>${escapeHtml(catalog.loop?.label || '')}</p></section>`
    );
  }

  function renderFlow(system) {
    const host = $('mcDsaFlow');
    if (!host) return;
    const flow = system?.flow || system?.catalog?.flow || [];
    host.innerHTML = flow.map((item) => (
      `<li class="${item.current ? 'is-current' : ''}${item.done ? ' is-done' : ''}">${escapeHtml(item.label)}</li>`
    )).join('');
    const lead = $('mcDsaLoopLead');
    if (lead) lead.textContent = system?.loop?.label || 'Um eixo por vez. O loop fecha DNA, contraste, trilhas e regras.';
  }

  function renderArchetypes(system) {
    const host = $('mcDsaArchetypes');
    if (!host) return;
    const rows = system?.archetypes || system?.catalog?.archetypes || [];
    host.innerHTML = rows.map((item) => (
      `<button type="button" class="mc-dsa-arch${item.id === state.archetype || item.active ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format)}">${escapeHtml(item.label)}</button>`
    )).join('');
  }

  function renderTable(system) {
    const host = $('mcDsaTable');
    if (!host) return;
    host.innerHTML = system?.table_html || '<p>A tabela aparece quando o sistema for criado.</p>';
  }

  function renderPassMeta(system) {
    const node = $('mcDsaPass');
    if (!node) return;
    const format = system?.adapt?.format || {};
    node.textContent = format.size_label
      ? `${format.label} · ${format.size_label} · ${state.layers} camadas`
      : '';
  }

  function syncFrames() {
    const system = state.system;
    const sheet = brandUrl();
    const piece = pieceUrl(system);
    const improveFrame = $('mcDsaImproveSheet');
    const pieceFrame = $('mcDsaFrame');
    const open = $('mcDsaOpen');
    if (state.mode === 'peca') {
      if (pieceFrame && pieceFrame.src !== new URL(piece, window.location.origin).href) {
        pieceFrame.src = piece;
      }
      if (open) open.href = piece;
    } else {
      if (improveFrame) improveFrame.src = sheet;
      if (open) open.href = sheet;
    }
  }

  function renderSystem(system) {
    state.system = system;
    if (system?.adapt?.format?.key && state.mode === 'peca') {
      state.format = system.adapt.format.key;
    }
    if (system?.adapt?.layer_count) state.layers = system.adapt.layer_count;
    if (system?.archetype) state.archetype = system.archetype;
    const exists = Boolean(system?.exists);
    const approved = system?.status === 'approved';
    const offer = $('mcDsaOffer');
    const create = $('mcDsaCreate');
    const refine = $('mcDsaRefine');
    const approve = $('mcDsaApprove');
    if (offer) {
      if (system?.scope === 'campaign' && !exists) {
        offer.textContent = 'A campanha ainda não herdou o sistema da marca.';
      } else if (system?.scope === 'campaign') {
        offer.textContent = system.creative_line || 'Campanha herda a tinta. Copy e recortes mudam.';
      } else if (system?.preset) {
        offer.textContent = 'CentralComm Ads. Ajuste a tinta, depois assente no IAB.';
      } else if (!exists) {
        offer.textContent = 'A marca ainda não tem Design System Ads. Criar a partir do logo e da paleta.';
      } else if (approved) {
        offer.textContent = 'Sistema aprovado. Melhore um eixo ou monte a peça.';
      } else {
        offer.textContent = 'Rascunho da marca. Parametrize, melhore, depois aprove.';
      }
    }
    if (create) {
      create.textContent = isCampaign() ? 'Gerar campanha' : 'Criar sistema';
      create.disabled = exists && !system?.preset && system?.scope !== 'campaign';
    }
    if (refine) refine.disabled = !exists || system?.scope === 'campaign';
    if (approve) approve.disabled = !exists || approved || system?.scope === 'campaign';
    renderCampaigns();
    renderCatalog(system);
    renderFlow(system);
    renderArchetypes(system);
    renderFormats(system);
    renderLayerControl(system);
    renderLayerList(system);
    renderTracks(system);
    renderIntents(system);
    renderPasses(system);
    renderPassMeta(system);
    syncFrames();
  }

  async function loadSystem() {
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url));
    renderSystem(data);
    if (state.mode === 'peca' && (data.exists || data.preset)) await adaptSystem();
  }

  async function adaptSystem() {
    const url = isCampaign() ? API.campaignAdapt(state.campaignId) : API.adapt(currentId());
    const data = await readJson(await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: state.format,
        layers: state.layers,
        swaps: state.swaps,
        archetype: state.archetype,
      }),
    }));
    renderSystem(data);
  }

  async function createSystem() {
    setStatus(isCampaign() ? 'Gerando o sistema da campanha.' : 'Criando o sistema.');
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url, { method: 'POST' }));
    renderSystem(data);
    if (state.mode === 'peca') await adaptSystem();
    setStatus(isCampaign() ? 'Sistema da campanha gerado.' : 'Sistema criado.');
  }

  async function improveSystem(intent) {
    setStatus(`Melhorando ${intent}.`);
    const data = await readJson(await fetch(API.refine(currentId()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent }),
    }));
    renderSystem(data);
    setStatus('Melhoria aplicada. Confira a folha.');
  }

  async function refineSystem() {
    setStatus('Refinando com o modelo.');
    const data = await readJson(await fetch(API.refine(currentId()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attempts: 4 }),
    }));
    renderSystem(data);
    setStatus('Refino com modelo concluído.');
  }

  async function approveSystem() {
    setStatus('Aprovando o sistema.');
    const data = await readJson(await fetch(API.approve(currentId()), { method: 'POST' }));
    renderSystem(data);
    setStatus('Sistema aprovado.');
  }

  async function patchSystem(tokens, adCopy, dna, archetype) {
    const data = await readJson(await fetch(API.tokens(currentId()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tokens: tokens || undefined,
        ad_copy: adCopy || undefined,
        dna: dna || undefined,
        archetype: archetype || undefined,
      }),
    }));
    renderSystem(data);
  }

  async function generateTrack(trackId) {
    const data = await readJson(await fetch(API.track(currentId(), trackId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }));
    renderSystem(data);
    return data;
  }

  async function continueLoop() {
    if (state.looping) return;
    state.looping = true;
    try {
      for (let hop = 0; hop < 8; hop += 1) {
        setStatus('Rodando o loop do sistema.');
        const data = await readJson(await fetch(API.loop(currentId()), { method: 'POST' }));
        renderSystem(data);
        const info = data.loop || {};
        setStatus(info.label || '');
        if (info.action === 'track' && info.track_id) {
          setStatus(`Gerando ${info.track_id}.`);
          try {
            await generateTrack(info.track_id);
          } catch (error) {
            setStatus(error.message);
            break;
          }
          continue;
        }
        if (info.ready) {
          setStatus('Sistema pronto para a peça.');
          break;
        }
        if (!['compose', 'contrast', 'rules'].includes(info.action)) break;
      }
    } finally {
      state.looping = false;
    }
  }

  function queuePatch(tokens, adCopy, dna) {
    window.clearTimeout(state.patchTimer);
    state.patchTimer = window.setTimeout(async () => {
      try {
        await patchSystem(tokens, adCopy, dna);
        setStatus('Token gravado.');
      } catch (error) {
        setStatus(error.message);
      }
    }, 280);
  }

  function neighborId(layerId, dir) {
    const layers = [...(state.system?.adapt?.layers || [])].sort((left, right) => (left.z || 0) - (right.z || 0));
    const index = layers.findIndex((item) => item.id === layerId);
    const other = layers[index + Number(dir)];
    return other?.id || '';
  }

  async function boot() {
    try {
      state.clients = await readJson(await fetch(API.clients));
    } catch (_error) {
      state.clients = [];
    }
    try {
      const campaigns = await readJson(await fetch(API.campaigns));
      state.campaigns = Array.isArray(campaigns) ? campaigns : [];
    } catch (_error) {
      state.campaigns = [];
    }
    renderClients();
    renderCampaigns();
    document.querySelector('.mc-dsa-modes')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-mode]');
      if (!button) return;
      setMode(button.getAttribute('data-mode'));
      if (state.mode === 'peca' && state.system) {
        adaptSystem().catch((error) => setStatus(error.message));
      }
    });
    $('mcDsaClient')?.addEventListener('change', async (event) => {
      state.clientId = event.target.value || 'centralcomm';
      state.campaignId = '';
      state.swaps = [];
      state.highlight = '';
      setStatus('');
      renderCampaigns();
      try {
        await loadSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCampaign')?.addEventListener('change', async (event) => {
      state.campaignId = event.target.value || '';
      state.swaps = [];
      state.highlight = '';
      setStatus('');
      try {
        await loadSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaFormats')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-format]');
      if (!button) return;
      state.format = button.getAttribute('data-format') || 'iab-billboard';
      state.swaps = [];
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerCount')?.addEventListener('input', (event) => {
      state.layers = Number(event.target.value) || 4;
      renderLayerControl(state.system);
    });
    $('mcDsaLayerCount')?.addEventListener('change', async () => {
      state.swaps = [];
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerList')?.addEventListener('click', async (event) => {
      const move = event.target.closest('[data-move]');
      if (move) {
        const other = neighborId(move.getAttribute('data-move'), move.getAttribute('data-dir'));
        if (!other) return;
        state.swaps = [...state.swaps, [move.getAttribute('data-move'), other]];
        try {
          await adaptSystem();
          setStatus('Camada movida.');
        } catch (error) {
          setStatus(error.message);
        }
        return;
      }
      const button = event.target.closest('[data-layer]');
      if (!button) return;
      const id = button.getAttribute('data-layer');
      state.highlight = state.highlight === id ? '' : id;
      renderLayerList(state.system);
      syncFrames();
    });
    $('mcDsaGroups')?.addEventListener('input', (event) => {
      const field = event.target.closest('[data-token]');
      if (!field) return;
      const key = field.getAttribute('data-token');
      let value = field.value;
      if (field.type === 'color') value = value.toUpperCase();
      const pair = field.parentElement?.querySelectorAll(`[data-token="${key}"]`) || [];
      pair.forEach((item) => {
        if (item !== field) item.value = value;
      });
      queuePatch({ [key]: value });
    });
    $('mcDsaCopy')?.addEventListener('input', () => {
      const form = $('mcDsaCopy');
      queuePatch(null, {
        headline: form.elements.headline.value,
        support: form.elements.support.value,
        cta: form.elements.cta.value,
        legal: form.elements.legal.value,
      });
    });
    $('mcDsaGrounds')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-ground]');
      if (!button) return;
      const kind = button.getAttribute('data-ground');
      const image = $('mcDsaGroundUrl')?.value || '';
      queuePatch({ 'ground-kind': kind, ground: image });
    });
    $('mcDsaGroundUrl')?.addEventListener('change', () => {
      queuePatch({ 'ground-kind': 'image', ground: $('mcDsaGroundUrl').value });
    });
    $('mcDsaBoard')?.addEventListener('click', (event) => {
      const swatch = event.target.closest('[data-token]');
      if (!swatch) return;
      const field = document.querySelector(`.mc-dsa-groups input[type="color"][data-token="${swatch.getAttribute('data-token')}"]`);
      field?.click();
    });
    $('mcDsaTracks')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-track]');
      if (!button) return;
      button.disabled = true;
      setStatus(`Gerando ${button.getAttribute('data-track')} no GPT Image 2.`);
      try {
        await generateTrack(button.getAttribute('data-track'));
        setStatus('Trilha gerada. Confira o fundo e o produto.');
      } catch (error) {
        setStatus(error.message);
      } finally {
        button.disabled = false;
      }
    });
    $('mcDsaCatalog')?.addEventListener('click', async (event) => {
      const archetype = event.target.closest('[data-archetype]');
      const format = event.target.closest('[data-format]');
      if (archetype) {
        state.archetype = archetype.getAttribute('data-archetype') || 'brand';
        state.format = archetype.getAttribute('data-format') || state.format;
        setMode('peca');
        try {
          await adaptSystem();
        } catch (error) {
          setStatus(error.message);
        }
        return;
      }
      if (format) {
        state.format = format.getAttribute('data-format') || 'iab-billboard';
        setMode('peca');
        try {
          await adaptSystem();
        } catch (error) {
          setStatus(error.message);
        }
      }
    });
    $('mcDsaCatalog')?.addEventListener('change', (event) => {
      const form = event.target.closest('#mcDsaDna');
      if (!form) return;
      queuePatch(null, null, {
        personality: form.elements.personality.value,
        must: form.elements.must.value,
        avoid: form.elements.avoid.value,
      });
    });
    $('mcDsaArchetypes')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-archetype]');
      if (!button) return;
      state.archetype = button.getAttribute('data-archetype') || 'brand';
      state.format = button.getAttribute('data-format') || state.format;
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLoop')?.addEventListener('click', async () => {
      try {
        await continueLoop();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCompose')?.addEventListener('click', async () => {
      setStatus('Montando o sistema no OpenRouter.');
      try {
        const data = await readJson(await fetch(API.compose(currentId()), { method: 'POST' }));
        renderSystem(data);
        setStatus('Sistema montado. Gere as trilhas se faltar imagem.');
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaIntents')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-intent]');
      if (!button) return;
      try {
        await improveSystem(button.getAttribute('data-intent'));
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCreate')?.addEventListener('click', async () => {
      try {
        await createSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaRefine')?.addEventListener('click', async () => {
      try {
        await refineSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaApprove')?.addEventListener('click', async () => {
      try {
        await approveSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    try {
      await loadSystem();
    } catch (error) {
      setStatus(error.message);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
