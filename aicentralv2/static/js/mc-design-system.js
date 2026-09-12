(() => {
  const API = {
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/campaigns',
    brand: (id) => `/parametros/api/design-system/brand/${id}`,
    refine: (id) => `/parametros/api/design-system/brand/${id}/refine`,
    approve: (id) => `/parametros/api/design-system/brand/${id}/approve`,
    tokens: (id) => `/parametros/api/design-system/brand/${id}/tokens`,
    loop: (id) => `/parametros/api/design-system/brand/${id}/loop`,
    track: (id, track) => `/parametros/api/design-system/brand/${id}/tracks/${track}`,
    adapt: (id) => `/parametros/api/design-system/brand/${id}/adapt`,
    campaign: (id) => `/parametros/api/design-system/campaign/${id}`,
    campaignAdapt: (id) => `/parametros/api/design-system/campaign/${id}/adapt`,
  };

  const COLOR_TOKENS = new Set(['paper', 'ink', 'accent', 'muted', 'cta_ink', 'highlight', 'hairline']);
  const CORE_ROLES = new Set(['visual', 'product', 'logo', 'headline', 'support', 'cta']);
  const ROLE_INTENT = { colors: 'contrast', type: 'type', cta: 'cta' };
  const INTENT_LABEL = { contrast: 'Contraste', type: 'Tipo', cta: 'CTA' };
  const TRACK_LABEL = { packshot: 'Gerar produto', kv: 'Gerar KV', lifestyle: 'Gerar cena', wash: 'Gerar tinta' };

  const state = {
    clients: [],
    campaigns: [],
    clientId: 'centralcomm',
    campaignId: '',
    format: 'iab-billboard',
    layers: 4,
    highlight: '',
    swaps: [],
    stageOpen: true,
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
      throw new Error(payload.error || 'A mesa de Ads não concluiu.');
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

  function pieceUrl() {
    const extra = state.highlight ? `&highlight=${encodeURIComponent(state.highlight)}` : '';
    if (isCampaign()) {
      return `/lab/design-system/campanha/${state.campaignId}?format=${state.format}&layers=${state.layers}${extra}`;
    }
    return `${brandUrl()}?format=${state.format}&layers=${state.layers}${extra}`;
  }

  function setStage(format, archetype) {
    if (format) state.format = format;
    if (archetype) state.archetype = archetype;
    state.stageOpen = true;
    const stage = $('mcDsaStage');
    if (stage) stage.hidden = false;
    syncFrames();
  }

  function hideStage() {
    state.stageOpen = true;
    const stage = $('mcDsaStage');
    if (stage) stage.hidden = false;
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

  function hexColor(value) {
    return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#000000';
  }

  function renderCatalog(system) {
    const host = $('mcDsaCatalog');
    if (!host) return;
    const catalog = system?.catalog || {};
    const dna = catalog.dna || system?.dna || {};
    const tokens = system?.tokens || {};
    const copy = system?.ad_copy || {};
    const pairs = system?.contrast?.pairs || {};
    const personality = (dna.personality || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const must = (dna.must || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const avoid = (dna.avoid || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
    const colors = (catalog.token_roles || []).find((item) => item.id === 'colors');
    const swatches = (colors?.items || []).map((item) => (
      `<label class="mc-dsa-color" title="${escapeHtml(item.label)}">`
      + `<input type="color" data-token="${escapeHtml(item.id)}" value="${escapeHtml(hexColor(item.value))}" aria-label="${escapeHtml(item.label)}">`
      + `</label>`
    )).join('');
    const components = (catalog.components || []).map((item) => (
      `<article class="mc-dsa-comp" data-comp="${escapeHtml(item.id)}">`
      + (item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : `<span class="mc-dsa-comp-mark" style="color:${escapeHtml(tokens.ink || '#1E4D4F')};font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">${escapeHtml(item.text || item.label)}</span>`)
      + `<strong>${escapeHtml(item.label)}</strong>`
      + `<small>P${item.priority}</small>`
      + `</article>`
    )).join('');
    const tracks = (system?.tracks || []).map((item) => {
      const label = TRACK_LABEL[item.id] || item.label;
      return (
        `<button type="button" class="mc-dsa-track" data-track="${escapeHtml(item.id)}">`
        + (item.url
          ? `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(label)}">`
          : `<span class="mc-dsa-track-empty">${escapeHtml(label)}</span>`)
        + `</button>`
      );
    }).join('');
    const effects = catalog.effects || {};
    const formats = (catalog.iab_formats || []).map((item) => {
      const size = item.size_label || item.label;
      const active = item.key === state.format ? ' is-active' : '';
      return (
        `<button type="button" class="mc-dsa-format${active}" data-format="${escapeHtml(item.key)}">`
        + `<strong>${escapeHtml(size)}</strong>`
        + `<em>${escapeHtml(item.density || '')}</em>`
        + `</button>`
      );
    }).join('');
    host.innerHTML = (
      `<p class="mc-dsa-tagline">${escapeHtml(catalog.tagline || catalog.creative_line || '')}</p>`
      + `<section class="mc-dsa-block" data-block="dna">`
      + `<h2>DNA</h2>`
      + (dna.logo_url || dna.product_url ? `<img src="${escapeHtml(dna.product_url || dna.logo_url)}" alt="">` : '')
      + `<ul class="mc-dsa-chips">${personality}</ul>`
      + `<form class="mc-dsa-dna-form" id="mcDsaDna">`
      + `<label>Personalidade <input name="personality" value="${escapeHtml((dna.personality || []).join(', '))}" maxlength="180"></label>`
      + `<label>Obrigatório <input name="must" value="${escapeHtml((dna.must || []).join(', '))}" maxlength="240"></label>`
      + `<label>Evitar <input name="avoid" value="${escapeHtml((dna.avoid || []).join(', '))}" maxlength="240"></label>`
      + `</form>`
      + `<form class="mc-dsa-copy" id="mcDsaCopy">`
      + `<label>Headline <input name="headline" value="${escapeHtml(copy.headline || '')}" maxlength="80"></label>`
      + `<label>Apoio <input name="support" value="${escapeHtml(copy.support || '')}" maxlength="140"></label>`
      + `<label>CTA <input name="cta" value="${escapeHtml(copy.cta || '')}" maxlength="32"></label>`
      + `<label>Legal <input name="legal" value="${escapeHtml(copy.legal || '')}" maxlength="80"></label>`
      + `</form>`
      + `<div class="mc-dsa-rules"><p>Fazer</p><ul>${must}</ul><p>Não fazer</p><ul>${avoid}</ul></div>`
      + `</section>`
      + `<section class="mc-dsa-block" data-block="tokens"><h2>Tinta</h2>`
      + `<div class="mc-dsa-dna-swatches">${swatches}</div>`
      + `<p class="mc-dsa-lockup" style="font-family:${escapeHtml(tokens['font-display'] || 'Inter')},sans-serif">${escapeHtml(copy.headline || dna.name || '')}</p>`
      + `<span class="mc-dsa-cta-chip" style="background:${escapeHtml(tokens.accent || '#111')};color:${escapeHtml(tokens.cta_ink || '#fff')}">${escapeHtml(copy.cta || 'CTA')}</span>`
      + `<div>${Object.entries(ROLE_INTENT).map(([key, intent]) => (
        `<button type="button" class="mc-dsa-intent" data-intent="${intent}">${INTENT_LABEL[intent]}</button>`
      )).join('')}</div>`
      + `<dl class="mc-dsa-contrast${system?.contrast?.passed ? ' is-ok' : ' is-bad'}">`
      + `<div><dt>Texto</dt><dd>${pairs.ink_on_paper || '—'} : 1</dd></div>`
      + `<div><dt>Botão</dt><dd>${pairs.cta_on_accent || '—'} : 1</dd></div>`
      + `</dl></section>`
      + `<section class="mc-dsa-block" data-block="effects"><h2>Efeito</h2>`
      + `<label>Lavagem <input data-token="wash-strength" value="${escapeHtml(effects['wash-strength'] || tokens['wash-strength'] || '16%')}" maxlength="8"></label>`
      + `<label>Grain <input data-token="grain" value="${escapeHtml(effects.grain || tokens.grain || '0.12')}" maxlength="8"></label>`
      + `</section>`
      + `<section class="mc-dsa-block" data-block="tracks"><h2>Trilhas</h2><div class="mc-dsa-tracks">${tracks}</div></section>`
      + `<section class="mc-dsa-block" data-block="components"><h2>Camadas</h2><div class="mc-dsa-comps">${components}</div></section>`
      + `<section class="mc-dsa-block" data-block="formats"><h2>IAB</h2><div class="mc-dsa-formats is-catalog">${formats}</div></section>`
    );
  }

  function renderGrounds(system) {
    const host = $('mcDsaGrounds');
    if (!host) return;
    const tokens = system?.tokens || {};
    const grounds = system?.catalog?.backgrounds || system?.backgrounds || [];
    host.innerHTML = grounds.map((item) => {
      const kind = item.id || item.kind || 'paper';
      const active = item.active || kind === tokens['ground-kind'] ? ' is-active' : '';
      const fill = item.preview || item.fill || tokens.paper || '#fff';
      const image = item.image || (kind === 'image' ? tokens.ground : '');
      return (
        `<button type="button" class="mc-dsa-ground${active}" data-ground="${escapeHtml(kind)}">`
        + `<i style="background:${image ? `center/cover url('${escapeHtml(image)}')` : escapeHtml(fill)}"></i>`
        + `<span>${escapeHtml(item.label || kind)}</span>`
        + `</button>`
      );
    }).join('');
  }

  function renderArchBoard(system) {
    const host = $('mcDsaArchBoard');
    if (!host) return;
    const tokens = system?.tokens || {};
    const rows = system?.catalog?.archetypes || system?.archetypes || [];
    host.innerHTML = rows.map((item) => {
      const image = item.image || '';
      const wash = item.ground === 'wash';
      const bg = image
        ? `center/cover url('${escapeHtml(image)}')`
        : (wash ? tokens.ink : tokens.paper);
      const fg = wash && !image ? (tokens.paper || '#fff') : (tokens.ink || '#111');
      return (
        `<button type="button" class="mc-dsa-arch${item.active || item.id === state.archetype ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format || 'iab-billboard')}">`
        + `<span class="mc-dsa-arch-stage" style="background:${escapeHtml(bg)};color:${escapeHtml(fg)}">`
        + `<strong>${escapeHtml(item.headline || item.label)}</strong>`
        + `<em>${escapeHtml(item.cta || '')}</em>`
        + `</span>`
        + `<b>${escapeHtml(item.label)}</b>`
        + `</button>`
      );
    }).join('');
  }

  function renderArchetypes(system) {
    const host = $('mcDsaArchetypes');
    if (!host) return;
    const rows = system?.archetypes || system?.catalog?.archetypes || [];
    host.innerHTML = rows.map((item) => (
      `<button type="button" class="mc-dsa-arch${item.id === state.archetype || item.active ? ' is-active' : ''}" data-archetype="${escapeHtml(item.id)}" data-format="${escapeHtml(item.format)}">${escapeHtml(item.label)}</button>`
    )).join('');
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
    if (!state.stageOpen) return;
    const piece = pieceUrl();
    const pieceFrame = $('mcDsaFrame');
    if (pieceFrame && pieceFrame.src !== new URL(piece, window.location.origin).href) {
      pieceFrame.src = piece;
    }
  }

  function renderSystem(system) {
    state.system = system;
    if (system?.adapt?.format?.key && state.stageOpen) {
      state.format = system.adapt.format.key;
    }
    if (system?.adapt?.layer_count) state.layers = system.adapt.layer_count;
    if (system?.archetype) state.archetype = system.archetype;
    const exists = Boolean(system?.exists);
    const approved = system?.status === 'approved';
    const offer = $('mcDsaOffer');
    const create = $('mcDsaCreate');
    const approve = $('mcDsaApprove');
    if (offer) {
      if (system?.scope === 'campaign' && !exists) {
        offer.textContent = 'A campanha ainda não herdou a tinta da marca.';
      } else if (system?.scope === 'campaign') {
        offer.textContent = system.creative_line || 'Campanha herda a tinta. Copy e recortes mudam.';
      } else if (system?.preset) {
        offer.textContent = 'CentralComm Ads. Ajuste a tinta, depois assente no IAB.';
      } else if (!exists) {
        offer.textContent = 'A marca ainda não tem linha de anúncio. Monte a partir do logo e da paleta.';
      } else if (approved) {
        offer.textContent = 'Aprovado. Abra um formato IAB.';
      } else {
        offer.textContent = 'Rascunho da marca. Ajuste no catálogo, depois aprove.';
      }
    }
    if (create) {
      create.textContent = 'Montar a marca';
      create.disabled = state.looping || isCampaign();
    }
    const campaignMount = $('mcDsaCampaignMount');
    if (campaignMount) {
      campaignMount.disabled = state.looping || !state.campaignId;
    }
    if (approve) approve.disabled = !exists || approved || system?.scope === 'campaign';
    renderCampaigns();
    renderCatalog(system);
    renderGrounds(system);
    renderArchBoard(system);
    renderArchetypes(system);
    renderLayerControl(system);
    renderLayerList(system);
    renderPassMeta(system);
    syncFrames();
  }

  async function loadSystem() {
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url));
    renderSystem(data);
    if (data.exists || data.preset) await adaptSystem();
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
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url, { method: 'POST' }));
    renderSystem(data);
    return data;
  }

  async function improveSystem(intent) {
    setStatus(`Ajustando ${INTENT_LABEL[intent] || intent}.`);
    const data = await readJson(await fetch(API.refine(currentId()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent }),
    }));
    renderSystem(data);
    setStatus('Ajuste aplicado no catálogo.');
  }

  async function approveSystem() {
    setStatus('Aprovando a marca.');
    const data = await readJson(await fetch(API.approve(currentId()), { method: 'POST' }));
    renderSystem(data);
    setStatus('Marca aprovada.');
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
    const create = $('mcDsaCreate');
    if (create) create.disabled = true;
    try {
      for (let hop = 0; hop < 8; hop += 1) {
        setStatus('Montando a linha da marca.');
        const data = await readJson(await fetch(API.loop(currentId()), { method: 'POST' }));
        renderSystem(data);
        const info = data.loop || {};
        setStatus(info.label || '');
        if (info.action === 'track' && info.track_id) {
          if (info.track_id === 'wash') continue;
          setStatus(TRACK_LABEL[info.track_id] || `Gerando ${info.track_id}.`);
          try {
            await generateTrack(info.track_id);
          } catch (error) {
            setStatus(error.message);
            break;
          }
          continue;
        }
        if (info.ready) {
          setStatus('Pronto. Abra um formato IAB.');
          break;
        }
        if (!['compose', 'contrast', 'review', 'rules'].includes(info.action)) break;
      }
    } finally {
      state.looping = false;
      if (create) create.disabled = false;
    }
  }

  async function mountBrand() {
    state.campaignId = '';
    renderCampaigns();
    const exists = Boolean(state.system?.exists || state.system?.preset);
    if (!exists || state.system?.scope === 'campaign') {
      setStatus('Montando a marca.');
      await createSystem();
    }
    await continueLoop();
  }

  async function mountCampaign() {
    if (!state.campaignId) {
      throw new Error('Escolha a campanha. A tinta da marca fica travada.');
    }
    setStatus('Montando a campanha.');
    await createSystem();
    setStatus(state.system?.creative_line || 'Campanha na tinta da marca.');
    if (state.system?.exists || state.system?.preset) await adaptSystem();
  }

  function queuePatch(tokens, adCopy, dna) {
    window.clearTimeout(state.patchTimer);
    state.patchTimer = window.setTimeout(async () => {
      try {
        await patchSystem(tokens, adCopy, dna);
        setStatus('Gravado.');
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

  async function openPiece(format, archetype) {
    setStage(format, archetype);
    try {
      await adaptSystem();
    } catch (error) {
      setStatus(error.message);
    }
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
    $('mcDsaClient')?.addEventListener('change', async (event) => {
      state.clientId = event.target.value || 'centralcomm';
      state.campaignId = '';
      state.swaps = [];
      state.highlight = '';
      hideStage();
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
    $('mcDsaCatalog')?.addEventListener('click', async (event) => {
      const track = event.target.closest('[data-track]');
      if (track) {
        track.disabled = true;
        const id = track.getAttribute('data-track');
        setStatus(TRACK_LABEL[id] || `Gerando ${id}.`);
        try {
          await generateTrack(id);
          setStatus('Trilha gerada.');
        } catch (error) {
          setStatus(error.message);
        } finally {
          track.disabled = false;
        }
        return;
      }
      const intent = event.target.closest('[data-intent]');
      if (intent) {
        try {
          await improveSystem(intent.getAttribute('data-intent'));
        } catch (error) {
          setStatus(error.message);
        }
        return;
      }
      const archetype = event.target.closest('[data-archetype]');
      if (archetype) {
        await openPiece(
          archetype.getAttribute('data-format') || state.format,
          archetype.getAttribute('data-archetype') || 'brand',
        );
        return;
      }
      const format = event.target.closest('[data-format]');
      if (format) {
        await openPiece(format.getAttribute('data-format') || 'iab-billboard', state.archetype);
      }
    });
    $('mcDsaCatalog')?.addEventListener('input', (event) => {
      const token = event.target.closest('[data-token]');
      if (token) {
        let value = token.value;
        if (token.type === 'color') value = value.toUpperCase();
        queuePatch({ [token.getAttribute('data-token')]: value });
        return;
      }
      const copy = event.target.closest('#mcDsaCopy');
      if (copy) {
        queuePatch(null, {
          headline: copy.elements.headline.value,
          support: copy.elements.support.value,
          cta: copy.elements.cta.value,
          legal: copy.elements.legal.value,
        });
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
      await openPiece(
        button.getAttribute('data-format') || state.format,
        button.getAttribute('data-archetype') || 'brand',
      );
    });
    $('mcDsaGrounds')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-ground]');
      if (!button) return;
      try {
        await patchSystem({ 'ground-kind': button.getAttribute('data-ground') });
        if (state.system?.exists || state.system?.preset) await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaArchBoard')?.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-archetype]');
      if (!button) return;
      await openPiece(
        button.getAttribute('data-format') || state.format,
        button.getAttribute('data-archetype') || 'brand',
      );
    });
    $('mcDsaCreate')?.addEventListener('click', async () => {
      try {
        await mountBrand();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaCampaignMount')?.addEventListener('click', async () => {
      try {
        await mountCampaign();
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
