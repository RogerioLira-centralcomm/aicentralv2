(() => {
  const API = {
    plates: '/parametros/api/format-lab/plates',
    bind: '/parametros/api/format-lab/plates/bind',
    patch: '/parametros/api/format-lab/plates/patch',
    clients: '/parametros/api/clients',
  };

  const state = {
    clients: [],
    clientId: '',
    product: '',
    kits: [],
    kit: null,
    selectedKey: '',
    bindings: {},
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
      throw new Error(payload.error || 'As placas não concluíram.');
    }
    return payload.data;
  }

  function setStatus(text) {
    const node = $('mcPlacasStatus');
    if (node) node.textContent = text;
  }

  function currentClient() {
    return state.clients.find((item) => String(item.id) === String(state.clientId));
  }

  function currentPlate() {
    return (state.kit?.plates || []).find((item) => item.key === state.selectedKey)
      || (state.kit?.plates || [])[0]
      || null;
  }

  function clientProducts(client) {
    const profile = client?.brand_profile || {};
    return (profile.products_services || []).filter(Boolean);
  }

  function chosenProduct() {
    const select = $('mcPlacasProduct');
    const custom = $('mcPlacasProductCustom');
    if (select?.value === '__custom') {
      return String(custom?.value || '').trim();
    }
    return String(select?.value || state.product || '').trim();
  }

  function stageStyle(canvas) {
    const width = Number(canvas?.width) || 1080;
    const height = Number(canvas?.height) || 1080;
    const scale = Math.min(720 / width, 560 / height, 1);
    return `width:${Math.max(160, Math.round(width * scale))}px;aspect-ratio:${width} / ${height}`;
  }

  function renderClients() {
    const select = $('mcPlacasClient');
    if (!select) return;
    select.innerHTML = '<option value="">Marca</option>' + state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
    )).join('');
    if (state.clientId) select.value = state.clientId;
  }

  function renderProducts() {
    const select = $('mcPlacasProduct');
    const customWrap = document.querySelector('.mc-placas-product-custom');
    if (!select) return;
    const products = clientProducts(currentClient());
    select.innerHTML = '<option value="">Produto</option>'
      + products.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')
      + '<option value="__custom">Outro…</option>';
    select.disabled = !state.clientId;
    if (state.product && products.includes(state.product)) {
      select.value = state.product;
    } else if (state.product) {
      select.value = '__custom';
      if ($('mcPlacasProductCustom')) $('mcPlacasProductCustom').value = state.product;
    }
    if (customWrap) customWrap.hidden = select.value !== '__custom';
  }

  function renderKits() {
    const select = $('mcPlacasKits');
    if (!select) return;
    select.innerHTML = '<option value="">Gerações</option>' + state.kits.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
    )).join('');
    select.disabled = !state.kits.length;
    if (state.kit?.id) select.value = String(state.kit.id);
  }

  function renderList() {
    const list = $('mcPlacasList');
    if (!list) return;
    list.innerHTML = (state.kit?.plates || []).map((plate) => {
      const selected = plate.key === state.selectedKey;
      const checked = (state.bindings[plate.key] || plate.selected_channels || []).length > 0;
      return `
        <button type="button" class="mc-placas-item${selected ? ' is-active' : ''}${checked ? ' is-checked' : ''}" data-plate="${escapeHtml(plate.key)}">
          <strong>${escapeHtml(plate.label)}</strong>
          <span>${escapeHtml(plate.size_label)}</span>
        </button>
      `;
    }).join('');
  }

  function renderPreview() {
    const stage = $('mcPlacasStage');
    const caption = $('mcPlacasCaption');
    const plate = currentPlate();
    if (!stage) return;
    if (!plate) {
      stage.removeAttribute('style');
      stage.innerHTML = '';
      if (caption) caption.textContent = '';
      return;
    }
    stage.style.cssText = stageStyle(plate.canvas);
    stage.innerHTML = `<iframe title="${escapeHtml(plate.label)}" sandbox="allow-same-origin" srcdoc="${escapeHtml(plate.html)}"></iframe>`;
    if (caption) {
      caption.textContent = `${plate.label} · ${plate.size_label} · cena 1`;
    }
  }

  function renderSide() {
    const kit = state.kit;
    const plate = currentPlate();
    const copy = kit?.campaign || {};
    if ($('mcPlacasHeadline')) $('mcPlacasHeadline').value = copy.headline || '';
    if ($('mcPlacasSupport')) $('mcPlacasSupport').value = copy.support || '';
    if ($('mcPlacasCta')) $('mcPlacasCta').value = copy.cta || '';
    const channels = $('mcPlacasChannels');
    if (channels) {
      const selected = new Set(state.bindings[plate?.key] || plate?.selected_channels || []);
      channels.innerHTML = '<legend>Canais</legend>' + ((plate?.channels || []).map((channel) => `
        <label>
          <input type="checkbox" data-channel="${escapeHtml(channel.key)}" ${selected.has(channel.key) ? 'checked' : ''}>
          ${escapeHtml(channel.label)}
        </label>
      `).join('') || '<p>Sem canal neste retângulo.</p>');
    }
  }

  function renderStudio() {
    const studio = $('mcPlacasStudio');
    const empty = $('mcPlacasEmpty');
    const offer = $('mcPlacasOffer');
    const kit = state.kit;
    if (!studio) return;
    if (!kit) {
      studio.hidden = true;
      if (empty) empty.hidden = false;
      if (offer) offer.textContent = 'Escolha a marca. O kit nasce no retângulo de cada formato.';
      return;
    }
    if (empty) empty.hidden = true;
    studio.hidden = false;
    const campaign = kit.campaign || {};
    if (offer) {
      offer.textContent = [kit.name, campaign.headline, campaign.cta].filter(Boolean).join(' · ');
    }
    if (!state.selectedKey) {
      state.selectedKey = (kit.plates || [])[0]?.key || '';
    }
    renderList();
    renderPreview();
    renderSide();
    const passes = kit.pass_count || (kit.passes || []).length;
    const count = Object.values(state.bindings).filter((item) => item.length).length;
    setStatus(
      [
        kit.name,
        passes ? `${passes} ${passes === 1 ? 'passada' : 'passadas'}` : '',
        count ? `${count} ${count === 1 ? 'peça ligada' : 'peças ligadas'} a canal` : 'Marque o canal da peça.',
      ].filter(Boolean).join(' · ')
    );
  }

  function adoptKit(kit) {
    state.kit = kit;
    state.bindings = {};
    (kit.plates || []).forEach((plate) => {
      state.bindings[plate.key] = [...(plate.selected_channels || [])];
    });
    if (!state.selectedKey || !(kit.plates || []).some((item) => item.key === state.selectedKey)) {
      state.selectedKey = (kit.plates || [])[0]?.key || '';
    }
    if (kit.product) state.product = kit.product;
    renderProducts();
    renderStudio();
  }

  async function loadKits() {
    if (!state.clientId) {
      state.kits = [];
      renderKits();
      return;
    }
    try {
      const kits = await fetch(`${API.plates}?client_id=${encodeURIComponent(state.clientId)}`, {
        credentials: 'same-origin',
      }).then(readJson);
      state.kits = kits || [];
      renderKits();
    } catch (error) {
      state.kits = [];
      renderKits();
      setStatus(error.message || 'Não foi possível ler as gerações.');
    }
  }

  async function buildKit() {
    if (!state.clientId) {
      setStatus('Escolha a marca.');
      return;
    }
    $('mcPlacasBuild').disabled = true;
    setStatus('Montando o IAB base…');
    try {
      const kit = await fetch(API.plates, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: Number(state.clientId),
          product: chosenProduct(),
        }),
      }).then(readJson);
      adoptKit(kit);
      await loadKits();
      if (kit.id) $('mcPlacasKits').value = String(kit.id);
    } catch (error) {
      setStatus(error.message || 'Não foi possível montar as placas.');
    } finally {
      $('mcPlacasBuild').disabled = !state.clientId;
    }
  }

  async function openKit(kitId) {
    if (!kitId) return;
    setStatus('Abrindo a geração…');
    try {
      const kit = await fetch(`${API.plates}/${kitId}`, { credentials: 'same-origin' }).then(readJson);
      adoptKit(kit);
    } catch (error) {
      setStatus(error.message || 'Não foi possível abrir a geração.');
    }
  }

  async function patchKit(extra) {
    if (!state.kit?.id) {
      setStatus('Monte o IAB base antes de ajustar.');
      return;
    }
    const body = {
      kit_id: state.kit.id,
      format_key: state.selectedKey,
      apply_to_all: Boolean($('mcPlacasApplyAll')?.checked),
      headline: $('mcPlacasHeadline')?.value || '',
      support: $('mcPlacasSupport')?.value || '',
      cta: $('mcPlacasCta')?.value || '',
      product_scale: $('mcPlacasScale')?.value || '1',
      product_x: $('mcPlacasOffsetX')?.value || '0',
      product_y: $('mcPlacasOffsetY')?.value || '0',
      ...(extra || {}),
    };
    setStatus(extra?.refine ? 'Passando de novo no HTML…' : 'Aplicando o ajuste…');
    try {
      const kit = await fetch(API.patch, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(readJson);
      adoptKit(kit);
    } catch (error) {
      setStatus(error.message || 'Não foi possível ajustar as placas.');
    }
  }

  async function bindPlate(formatKey, channelKey, on) {
    const current = new Set(state.bindings[formatKey] || []);
    if (on) current.add(channelKey);
    else current.delete(channelKey);
    state.bindings[formatKey] = [...current];
    renderList();
    try {
      const kit = await fetch(API.bind, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: Number(state.clientId),
          kit_id: state.kit?.id,
          bindings: state.bindings,
        }),
      }).then(readJson);
      if (kit?.plates) adoptKit(kit);
    } catch (error) {
      setStatus(error.message || 'Não foi possível ligar o canal.');
    }
  }

  function bind() {
    $('mcPlacasClient')?.addEventListener('change', async (event) => {
      state.clientId = event.target.value;
      state.kit = null;
      state.product = '';
      state.selectedKey = '';
      $('mcPlacasBuild').disabled = !state.clientId;
      renderProducts();
      renderStudio();
      await loadKits();
      const client = currentClient();
      setStatus(client ? 'Marca pronta. Monte o IAB base.' : '');
    });
    $('mcPlacasProduct')?.addEventListener('change', (event) => {
      const customWrap = document.querySelector('.mc-placas-product-custom');
      if (customWrap) customWrap.hidden = event.target.value !== '__custom';
      state.product = chosenProduct();
    });
    $('mcPlacasProductCustom')?.addEventListener('input', (event) => {
      state.product = String(event.target.value || '').trim();
    });
    $('mcPlacasBuild')?.addEventListener('click', buildKit);
    $('mcPlacasKits')?.addEventListener('change', (event) => openKit(event.target.value));
    $('mcPlacasList')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-plate]');
      if (!button) return;
      state.selectedKey = button.getAttribute('data-plate');
      renderList();
      renderPreview();
      renderSide();
    });
    $('mcPlacasEdit')?.addEventListener('submit', (event) => {
      event.preventDefault();
      patchKit();
    });
    $('mcPlacasRefine')?.addEventListener('click', () => patchKit({ refine: true }));
    $('mcPlacasChannels')?.addEventListener('change', (event) => {
      const input = event.target.closest('input[data-channel]');
      const plate = currentPlate();
      if (!input || !plate) return;
      bindPlate(plate.key, input.getAttribute('data-channel'), input.checked);
    });
  }

  async function boot() {
    if (!$('mcPlacas')) return;
    bind();
    try {
      const clients = await fetch(API.clients, { credentials: 'same-origin' }).then(readJson);
      state.clients = clients || [];
      renderClients();
    } catch (error) {
      setStatus(error.message || 'Não foi possível ler as marcas.');
    }
  }

  boot();
})();
