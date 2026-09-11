(() => {
  const API = {
    plates: '/parametros/api/format-lab/plates',
    bind: '/parametros/api/format-lab/plates/bind',
    clients: '/parametros/api/clients',
  };

  const state = {
    clients: [],
    clientId: '',
    kit: null,
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

  function stageStyle(canvas) {
    const width = Number(canvas?.width) || 1080;
    const height = Number(canvas?.height) || 1080;
    const scale = Math.min(360 / width, 280 / height, 0.38);
    return `width:${Math.max(72, Math.round(width * scale))}px;aspect-ratio:${width} / ${height}`;
  }

  function renderClients() {
    const select = $('mcPlacasClient');
    if (!select) return;
    select.innerHTML = '<option value="">Marca</option>' + state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || item.id)}</option>`
    )).join('');
    if (state.clientId) select.value = state.clientId;
  }

  function renderWall() {
    const wall = $('mcPlacasWall');
    const empty = $('mcPlacasEmpty');
    const offer = $('mcPlacasOffer');
    const kit = state.kit;
    if (!wall) return;
    if (!kit) {
      wall.hidden = true;
      if (empty) empty.hidden = false;
      if (offer) offer.textContent = 'Escolha a marca. O kit nasce no retângulo de cada formato.';
      return;
    }
    if (empty) empty.hidden = true;
    wall.hidden = false;
    const campaign = kit.campaign || {};
    if (offer) {
      offer.textContent = [campaign.headline, campaign.cta].filter(Boolean).join(' · ');
    }
    wall.innerHTML = (kit.plates || []).map((plate) => {
      const selected = new Set(state.bindings[plate.key] || plate.selected_channels || []);
      const checked = selected.size > 0;
      return `
        <article class="mc-placa ${checked ? 'is-checked' : ''}" data-plate="${escapeHtml(plate.key)}">
          <div class="mc-placa-stage" style="${stageStyle(plate.canvas)}">
            <iframe title="${escapeHtml(plate.label)}" sandbox="allow-same-origin" srcdoc="${escapeHtml(plate.html)}"></iframe>
          </div>
          <header>
            <strong>${escapeHtml(plate.label)}</strong>
            <span>${escapeHtml(plate.size_label)}</span>
            ${checked ? '<em>Checado</em>' : ''}
          </header>
          <fieldset>
            <legend>Canais</legend>
            ${(plate.channels || []).map((channel) => `
              <label>
                <input type="checkbox" data-channel="${escapeHtml(channel.key)}" ${selected.has(channel.key) ? 'checked' : ''}>
                ${escapeHtml(channel.label)}
              </label>
            `).join('')}
          </fieldset>
        </article>
      `;
    }).join('');
    const count = (kit.plates || []).filter((item) => (state.bindings[item.key] || []).length).length;
    setStatus(count ? `${count} ${count === 1 ? 'peça ligada' : 'peças ligadas'} a canal.` : 'Marque o canal de cada retângulo.');
  }

  async function buildKit() {
    if (!state.clientId) {
      setStatus('Escolha a marca.');
      return;
    }
    $('mcPlacasBuild').disabled = true;
    setStatus('Montando o kit da marca…');
    try {
      const kit = await fetch(API.plates, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: Number(state.clientId) }),
      }).then(readJson);
      state.kit = kit;
      state.bindings = {};
      (kit.plates || []).forEach((plate) => {
        state.bindings[plate.key] = [...(plate.selected_channels || [])];
      });
      renderWall();
    } catch (error) {
      setStatus(error.message || 'Não foi possível montar as placas.');
    } finally {
      $('mcPlacasBuild').disabled = !state.clientId;
    }
  }

  function markPlate(formatKey) {
    const card = document.querySelector(`[data-plate="${formatKey}"]`);
    if (!card) return;
    const selected = state.bindings[formatKey] || [];
    card.classList.toggle('is-checked', selected.length > 0);
    const header = card.querySelector('header');
    if (header) {
      header.querySelector('em')?.remove();
      if (selected.length) {
        const mark = document.createElement('em');
        mark.textContent = 'Checado';
        header.appendChild(mark);
      }
    }
    const count = Object.values(state.bindings).filter((item) => item.length).length;
    setStatus(count ? `${count} ${count === 1 ? 'peça ligada' : 'peças ligadas'} a canal.` : 'Marque o canal de cada retângulo.');
  }

  async function bindPlate(formatKey, channelKey, on) {
    const current = new Set(state.bindings[formatKey] || []);
    if (on) current.add(channelKey);
    else current.delete(channelKey);
    state.bindings[formatKey] = [...current];
    markPlate(formatKey);
    try {
      await fetch(API.bind, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: Number(state.clientId),
          bindings: state.bindings,
        }),
      }).then(readJson);
    } catch (error) {
      setStatus(error.message || 'Não foi possível ligar o canal.');
    }
  }

  function bind() {
    $('mcPlacasClient')?.addEventListener('change', (event) => {
      state.clientId = event.target.value;
      state.kit = null;
      $('mcPlacasBuild').disabled = !state.clientId;
      renderWall();
      const client = currentClient();
      setStatus(client ? 'Marca pronta. Monte as placas.' : '');
    });
    $('mcPlacasBuild')?.addEventListener('click', buildKit);
    $('mcPlacasWall')?.addEventListener('change', (event) => {
      const input = event.target.closest('input[data-channel]');
      const card = event.target.closest('[data-plate]');
      if (!input || !card) return;
      bindPlate(card.getAttribute('data-plate'), input.getAttribute('data-channel'), input.checked);
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
