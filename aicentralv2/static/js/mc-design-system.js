(() => {
  const API = {
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/campaigns',
    brand: (id) => `/parametros/api/design-system/brand/${id}`,
    refine: (id) => `/parametros/api/design-system/brand/${id}/refine`,
    approve: (id) => `/parametros/api/design-system/brand/${id}/approve`,
    adapt: (id) => `/parametros/api/design-system/brand/${id}/adapt`,
    campaign: (id) => `/parametros/api/design-system/campaign/${id}`,
    campaignAdapt: (id) => `/parametros/api/design-system/campaign/${id}/adapt`,
  };

  const state = {
    clients: [],
    campaigns: [],
    clientId: 'centralcomm',
    campaignId: '',
    format: 'iab-billboard',
    layers: 4,
    selected: [],
    swaps: [],
    system: null,
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

  function specimenUrl(system) {
    if (system?.specimen_url) return system.specimen_url;
    if (isCampaign()) {
      return `/lab/design-system/campanha/${state.campaignId}?format=${state.format}&layers=${state.layers}`;
    }
    return `/lab/design-system/marca/${currentId()}?format=${state.format}&layers=${state.layers}`;
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
    select.innerHTML = `<option value="">Marca</option><option value="centralcomm-verao">Verao · CentralComm</option>${extras}`;
    if (state.campaignId && ![...select.options].some((item) => item.value === String(state.campaignId))) {
      state.campaignId = '';
    }
    select.value = state.campaignId;
  }

  function renderFormats(system) {
    const select = $('mcDsaFormat');
    if (!select) return;
    const formats = system?.iab_formats || [];
    if (!formats.length) return;
    select.innerHTML = formats.map((item) => (
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)} · ${escapeHtml(item.size_label)}</option>`
    )).join('');
    if (!formats.some((item) => item.key === state.format)) {
      state.format = formats[0].key;
    }
    select.value = state.format;
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
    if (label) label.textContent = `${state.layers} camadas`;
  }

  function renderLayerList(system) {
    const list = $('mcDsaLayerList');
    if (!list) return;
    const layers = system?.adapt?.layers || [];
    list.innerHTML = layers.map((item) => {
      const selected = state.selected.includes(item.id) ? ' is-selected' : '';
      return `<li><button type="button" class="mc-dsa-layer${selected}" data-layer="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${escapeHtml(item.role)}</button></li>`;
    }).join('');
    const swap = $('mcDsaSwap');
    if (swap) swap.disabled = state.selected.length !== 2;
  }

  function renderTable(system) {
    const host = $('mcDsaTable');
    if (!host) return;
    host.innerHTML = system?.table_html || '<p>A tabela aparece quando o sistema for criado.</p>';
  }

  function renderPass(system) {
    const node = $('mcDsaPass');
    if (!node) return;
    const passes = system?.passes || [];
    const last = passes[passes.length - 1];
    const score = last ? ` · ${Math.round((last.score || 0) * 100)}%` : '';
    node.textContent = `Passe ${passes.length}/4${score}`;
  }

  function renderSystem(system) {
    state.system = system;
    if (system?.adapt?.format?.key) state.format = system.adapt.format.key;
    if (system?.adapt?.layer_count) state.layers = system.adapt.layer_count;
    const exists = Boolean(system?.exists);
    const approved = system?.status === 'approved';
    const offer = $('mcDsaOffer');
    const create = $('mcDsaCreate');
    const refine = $('mcDsaRefine');
    const approve = $('mcDsaApprove');
    const open = $('mcDsaOpen');
    const frame = $('mcDsaFrame');
    const url = specimenUrl(system);
    if (offer) {
      if (system?.scope === 'campaign' && system?.preset) {
        offer.textContent = 'Campanha herda a marca. Linha criativa e recortes assentam no IAB.';
      } else if (system?.scope === 'campaign' && !exists) {
        offer.textContent = 'A campanha ainda não tem Design System Ads. Gerar a partir da marca.';
      } else if (system?.scope === 'campaign') {
        offer.textContent = system.creative_line || 'Campanha herda os tokens da marca. Copy e recortes mudam.';
      } else if (system?.preset) {
        offer.textContent = 'CentralComm Ads no retângulo IAB. Copy respira dentro da área segura.';
      } else if (!exists) {
        offer.textContent = 'A marca ainda não tem Design System Ads. Criar a partir do logo e da paleta.';
      } else if (approved) {
        offer.textContent = 'Sistema aprovado. Troque camadas e teste o formato.';
      } else {
        offer.textContent = 'Sistema em rascunho. Refine, depois assente no IAB.';
      }
    }
    if (create) {
      create.textContent = isCampaign() ? 'Gerar campanha' : 'Criar sistema';
      create.disabled = exists && !system?.preset && system?.scope !== 'campaign';
    }
    if (refine) refine.disabled = !exists || system?.scope === 'campaign';
    if (approve) approve.disabled = !exists || approved || system?.scope === 'campaign';
    if (open) open.href = url;
    if (frame) frame.src = url;
    renderCampaigns();
    renderFormats(system);
    renderLayerControl(system);
    renderTable(system);
    renderLayerList(system);
    renderPass(system);
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
      }),
    }));
    renderSystem(data);
  }

  async function createSystem() {
    setStatus(isCampaign() ? 'Gerando o sistema da campanha.' : 'Criando o sistema.');
    const url = isCampaign() ? API.campaign(state.campaignId) : API.brand(currentId());
    const data = await readJson(await fetch(url, { method: 'POST' }));
    renderSystem(data);
    await adaptSystem();
    setStatus(isCampaign() ? 'Sistema da campanha gerado.' : 'Sistema criado.');
  }

  async function refineSystem() {
    setStatus('Refinando tokens.');
    const data = await readJson(await fetch(API.refine(currentId()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attempts: 4 }),
    }));
    renderSystem(data);
    await adaptSystem();
    setStatus('Refino concluído.');
  }

  async function approveSystem() {
    setStatus('Aprovando o sistema.');
    const data = await readJson(await fetch(API.approve(currentId()), { method: 'POST' }));
    renderSystem(data);
    setStatus('Sistema aprovado.');
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
      state.selected = [];
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
      state.selected = [];
      setStatus('');
      try {
        await loadSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaFormat')?.addEventListener('change', async (event) => {
      state.format = event.target.value || 'iab-billboard';
      state.swaps = [];
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerCount')?.addEventListener('input', (event) => {
      state.layers = Number(event.target.value) || 4;
      const label = $('mcDsaLayerLabel');
      if (label) label.textContent = `${state.layers} camadas`;
    });
    $('mcDsaLayerCount')?.addEventListener('change', async () => {
      state.swaps = [];
      try {
        await adaptSystem();
      } catch (error) {
        setStatus(error.message);
      }
    });
    $('mcDsaLayerList')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-layer]');
      if (!button) return;
      const id = button.getAttribute('data-layer');
      if (state.selected.includes(id)) {
        state.selected = state.selected.filter((item) => item !== id);
      } else if (state.selected.length < 2) {
        state.selected = [...state.selected, id];
      } else {
        state.selected = [state.selected[1], id];
      }
      renderLayerList(state.system);
    });
    $('mcDsaSwap')?.addEventListener('click', async () => {
      if (state.selected.length !== 2) return;
      state.swaps = [...state.swaps, [state.selected[0], state.selected[1]]];
      state.selected = [];
      try {
        await adaptSystem();
        setStatus('Posições trocadas.');
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
