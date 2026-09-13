(() => {
  const API = {
    clients: '/parametros/api/clients',
    campaigns: '/parametros/api/format-lab/campaigns',
    quote: '/parametros/api/format-lab/prototype/quote',
    script: '/parametros/api/format-lab/prototype/script',
    refs: '/parametros/api/format-lab/prototype/refs',
    scenes: '/parametros/api/format-lab/prototype/scenes',
    animate: '/parametros/api/format-lab/prototype/animate',
    video: '/parametros/api/format-lab/prototype/video',
  };
  const OBJECTIVES = ['Reconhecimento', 'Consideração', 'Conversão', 'Lançamento'];
  const FORMATS = [
    ['video-linear-15', 'Video 15s · 1920×1080'],
    ['video-cta-15', 'Video 15s + CTA'],
    ['video-qr-15', 'Video 15s + QR'],
  ];
  const TOGGLES = [
    ['pessoa', 'pessoa'],
    ['cta', 'cta'],
    ['logo', 'logo'],
    ['titulo', 'título'],
    ['texto_curto', 'texto curto'],
    ['texto_longo', 'texto longo'],
    ['imagem_apoio', 'imagem de apoio'],
    ['grafico', 'gráfico'],
  ];

  const state = {
    clients: [],
    campaigns: [],
    campaign: null,
    clientId: '',
    formatKey: 'video-linear-15',
    sceneCount: 4,
    objective: 'Reconhecimento',
    variant: 'C',
    campaignSlug: '',
    step: 'script',
    version: 'v3',
    script: null,
    storyboard: [],
    refs: null,
    scenes: [],
    sceneIndex: 0,
    recipes: {},
    persona: { elenco: '1 pessoa', idade: '25-34', fundo: 'lavagem' },
    quote: null,
    playTimer: 0,
    busy: false,
  };

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function csrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  async function request(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify(body || {}),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || 'A chamada do Studio falhou.');
    }
    return payload.data || payload;
  }

  function brand() {
    return window.McDeskBrand || {
      read() { return ''; },
      write() {},
      forSelect(list) { return Array.isArray(list) ? list : []; },
      pick(_list, fallback) { return String(fallback || ''); },
      label(client) { return client?.name || client?.id || 'Marca'; },
    };
  }

  function payload(extra) {
    return {
      client_id: state.clientId || undefined,
      campaign_slug: state.campaignSlug || (/g1/i.test(brand().label(state.clients.find((item) => String(item.id) === String(state.clientId)) || {}))
        ? 'g1-ctv'
        : undefined),
      format_key: state.formatKey,
      scene_count: state.sceneCount,
      objective: state.objective,
      variant: state.variant,
      offer: state.campaign?.offer || undefined,
      cta: state.campaign?.cta || undefined,
      elenco: $('mcStudioCast')?.value || state.persona.elenco,
      idade: $('mcStudioAge')?.value || state.persona.idade,
      fundo: $('mcStudioGround')?.value || state.persona.fundo,
      storyboard: state.storyboard,
      refs: state.refs,
      recipes: state.recipes,
      scenes: state.scenes,
      seconds: Number($('mcStudioSeconds')?.value || 5),
      ...extra,
    };
  }

  function setBusy(on, text) {
    state.busy = Boolean(on);
    $('mcStudio')?.classList.toggle('is-busy', state.busy);
    ['mcStudioScript', 'mcStudioRefs', 'mcStudioScenes', 'mcStudioAnimate', 'mcStudioVideo'].forEach((id) => {
      const node = $(id);
      if (node) node.disabled = state.busy;
    });
    status(text || '');
  }

  function status(text) {
    const node = $('mcStudioStatus');
    const tally = $('mcStudioTally');
    if (node) node.textContent = text || '';
    if (tally) tally.textContent = text || '';
  }

  function money(quote) {
    const node = $('mcStudioQuote');
    if (!node) return;
    const brl = quote?.spent_brl ?? quote?.cost_brl ?? quote?.estimated_cost_brl;
    const usd = quote?.estimated_cost_usd ?? quote?.cost_usd;
    if (brl != null) node.textContent = `R$ ${Number(brl).toFixed(2)}`;
    else if (usd != null) node.textContent = `US$ ${Number(usd).toFixed(2)}`;
    else node.textContent = 'R$ 0';
  }

  function setStep(step) {
    state.step = step;
    document.querySelectorAll('.mc-studio-nav button').forEach((button) => {
      button.classList.toggle('is-current', button.getAttribute('data-step') === step);
    });
    document.querySelectorAll('.mc-studio-side [data-pane]').forEach((pane) => {
      pane.hidden = pane.getAttribute('data-pane') !== step;
    });
    $('mcStudioVersions').hidden = step !== 'script' || !state.script;
    paintStage();
    refreshQuote();
  }

  function renderBeats() {
    const pack = state.script || {};
    const rows = (pack[state.version] && pack[state.version].storyboard) || state.storyboard;
    const list = $('mcStudioBeats');
    if (!list) return;
    list.innerHTML = rows.map((item) => (
      `<li><em>${escapeHtml(item.purpose || '')}</em><strong>${escapeHtml(item.headline || '')}</strong><span>${escapeHtml(item.support || '')}</span></li>`
    )).join('');
  }

  function renderToggles() {
    const scene = state.scenes[state.sceneIndex] || {};
    const recipe = state.recipes[scene.id] || scene.recipe || {};
    const list = $('mcStudioToggles');
    if (!list) return;
    list.innerHTML = TOGGLES.map(([key, label]) => (
      `<li><label><input type="checkbox" data-toggle="${key}" ${recipe[key] ? 'checked' : ''}> ${label}</label></li>`
    )).join('');
    list.querySelectorAll('input').forEach((input) => {
      input.addEventListener('change', () => {
        const id = scene.id || 'scene_01';
        state.recipes[id] = { ...(state.recipes[id] || recipe) };
        state.recipes[id][input.getAttribute('data-toggle')] = input.checked;
      });
    });
  }

  function paintStage() {
    const frame = $('mcStudioFrame');
    const still = $('mcStudioStill');
    const empty = $('mcStudioEmpty');
    const scene = state.scenes[state.sceneIndex];
    if (scene?.html && frame) {
      frame.hidden = false;
      if (still) {
        still.hidden = true;
        still.removeAttribute('src');
      }
      empty.hidden = true;
      frame.srcdoc = scene.html;
      $('mcStudioPrev').hidden = state.scenes.length < 2;
      $('mcStudioNext').hidden = state.scenes.length < 2;
      $('mcStudioDots').textContent = `cena ${state.sceneIndex + 1} de ${state.scenes.length}`;
      renderToggles();
      return;
    }
    const url = state.refs?.cast?.url || state.refs?.ground?.url || '';
    if (url && still) {
      frame.hidden = true;
      still.hidden = false;
      still.src = url;
      empty.hidden = true;
      $('mcStudioPrev').hidden = true;
      $('mcStudioNext').hidden = true;
      $('mcStudioDots').textContent = state.refs?.ground?.url && state.refs?.cast?.url
        ? 'elenco'
        : 'referência';
      return;
    }
    if (frame) frame.hidden = true;
    if (still) {
      still.hidden = true;
      still.removeAttribute('src');
    }
    empty.hidden = false;
    $('mcStudioPrev').hidden = true;
    $('mcStudioNext').hidden = true;
    $('mcStudioDots').textContent = '';
  }

  function showScene(index) {
    if (!state.scenes.length) return;
    state.sceneIndex = (index + state.scenes.length) % state.scenes.length;
    paintStage();
  }

  async function refreshQuote() {
    try {
      state.quote = await request(API.quote, payload({ video: state.step === 'play' }));
      money(state.quote);
    } catch (_error) {
      money(null);
    }
  }

  function askConfirm(title, text) {
    const dialog = $('mcStudioConfirm');
    if (!dialog || typeof dialog.showModal !== 'function') {
      return Promise.resolve(window.confirm(text));
    }
    $('mcStudioConfirmTitle').textContent = title;
    $('mcStudioConfirmText').textContent = text;
    dialog.showModal();
    return new Promise((resolve) => {
      const ok = $('mcStudioConfirmOk');
      const cancel = $('mcStudioConfirmCancel');
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        ok.removeEventListener('click', onOk);
        cancel.removeEventListener('click', onCancel);
        dialog.removeEventListener('cancel', onCancel);
        if (dialog.open) dialog.close();
        resolve(value);
      };
      const onOk = (event) => {
        event.preventDefault();
        finish(true);
      };
      const onCancel = (event) => {
        event.preventDefault();
        finish(false);
      };
      ok.addEventListener('click', onOk);
      cancel.addEventListener('click', onCancel);
      dialog.addEventListener('cancel', onCancel);
    });
  }

  async function loadClients() {
    const response = await fetch(API.clients);
    const payload = await response.json().catch(() => ({}));
    const rows = payload.data || payload.clients || payload || [];
    state.clients = Array.isArray(rows) ? rows : (rows.clients || []);
    const select = $('mcStudioClient');
    const options = brand().forSelect(state.clients);
    select.innerHTML = '<option value="">Marca</option>' + options.map((item) => (
      `<option value="${escapeHtml(item.id)}">${escapeHtml(brand().label(item))}</option>`
    )).join('');
    const picked = brand().pick(options, brand().read());
    if (picked) {
      select.value = picked;
      state.clientId = picked;
    }
    const name = brand().label(options.find((item) => String(item.id) === String(select.value)) || {});
    if (/g1/i.test(name)) applyCase('g1-ctv');
  }

  function applyCase(slug) {
    const select = $('mcStudioCase');
    const item = state.campaigns.find((row) => row.slug === slug) || null;
    state.campaignSlug = slug || '';
    state.campaign = item;
    if (select) select.value = slug || '';
    if (!item) return;
    state.formatKey = item.format || state.formatKey;
    state.variant = (item.variant || state.variant || 'C').toUpperCase();
    if (item.objective) state.objective = item.objective.split(':')[0].trim() || state.objective;
    if (item.scenes?.length) {
      state.sceneCount = item.scenes.length === 6 ? 6 : 4;
      document.querySelectorAll('.mc-studio-counts button').forEach((button) => {
        button.classList.toggle('is-current', Number(button.getAttribute('data-count')) === state.sceneCount);
      });
    }
    paintFormat();
    const objectives = $('mcStudioObjectives');
    objectives?.querySelectorAll('button').forEach((button) => {
      button.classList.toggle('is-current', button.getAttribute('data-objective') === state.objective);
    });
  }

  async function loadCampaigns() {
    const response = await fetch(API.campaigns);
    const payload = await response.json().catch(() => ({}));
    const rows = payload.data || payload.campaigns || payload || [];
    state.campaigns = Array.isArray(rows) ? rows : [];
    const select = $('mcStudioCase');
    if (!select) return;
    select.innerHTML = '<option value="">Caso</option>' + state.campaigns.map((item) => (
      `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.brand_name || item.title || item.slug)}</option>`
    )).join('');
    if (state.campaignSlug) applyCase(state.campaignSlug);
  }

  function paintFormat() {
    const summary = $('mcFormatSummary');
    const found = FORMATS.find(([key]) => key === state.formatKey);
    if (summary) summary.textContent = found ? found[1] : state.formatKey;
    document.querySelectorAll('#mcFormatMenu [data-format]').forEach((button) => {
      button.classList.toggle('is-current', button.getAttribute('data-format') === state.formatKey);
    });
  }

  function bindFormatMenu() {
    const menu = $('mcFormatMenu');
    if (!menu) return;
    menu.innerHTML = FORMATS.map(([key, label]) => (
      `<button type="button" data-format="${key}">${label}</button>`
    )).join('');
    menu.querySelectorAll('[data-format]').forEach((button) => {
      button.addEventListener('click', () => {
        state.formatKey = button.getAttribute('data-format');
        paintFormat();
        $('mcFormatDrop')?.removeAttribute('open');
        refreshQuote();
      });
    });
    paintFormat();
  }

  function bind() {
    bindFormatMenu();
    document.querySelectorAll('.mc-studio-nav button').forEach((button) => {
      button.addEventListener('click', () => setStep(button.getAttribute('data-step')));
    });
    document.querySelectorAll('.mc-studio-counts button').forEach((button) => {
      button.addEventListener('click', () => {
        state.sceneCount = Number(button.getAttribute('data-count')) || 4;
        document.querySelectorAll('.mc-studio-counts button').forEach((item) => {
          item.classList.toggle('is-current', item === button);
        });
        refreshQuote();
      });
    });
    const objectives = $('mcStudioObjectives');
    objectives.innerHTML = OBJECTIVES.map((item, index) => (
      `<button type="button" class="${index === 0 ? 'is-current' : ''}" data-objective="${item}">${item}</button>`
    )).join('');
    objectives.querySelectorAll('button').forEach((button) => {
      button.addEventListener('click', () => {
        state.objective = button.getAttribute('data-objective');
        objectives.querySelectorAll('button').forEach((item) => item.classList.toggle('is-current', item === button));
      });
    });
    $('mcStudioClient').addEventListener('change', () => {
      state.clientId = $('mcStudioClient').value;
      brand().write(state.clientId);
      const current = state.clients.find((item) => String(item.id) === String(state.clientId));
      if (/g1/i.test(brand().label(current || {}))) applyCase('g1-ctv');
      else if (state.campaignSlug === 'g1-ctv') applyCase('');
      refreshQuote();
    });
    $('mcStudioCase')?.addEventListener('change', () => {
      applyCase($('mcStudioCase').value);
      refreshQuote();
    });
    document.querySelectorAll('#mcStudioVersions button').forEach((button) => {
      button.addEventListener('click', () => {
        state.version = button.getAttribute('data-version');
        document.querySelectorAll('#mcStudioVersions button').forEach((item) => {
          item.classList.toggle('is-current', item === button);
        });
        state.storyboard = (state.script[state.version] || {}).storyboard || state.storyboard;
        renderBeats();
      });
    });
    $('mcStudioScript').addEventListener('click', async () => {
      setBusy(true, 'Gerando roteiro…');
      try {
        state.script = await request(API.script, payload());
        state.version = state.script.selected || 'v3';
        state.storyboard = state.script.storyboard || [];
        state.persona = state.script.persona || state.persona;
        if (state.persona.elenco) $('mcStudioCast').value = state.persona.elenco;
        if (state.persona.idade) $('mcStudioAge').value = state.persona.idade;
        $('mcStudioVersions').hidden = false;
        renderBeats();
        setBusy(false, state.script.early_exit ? 'Roteiro pronto. Crítica sem problemas — early-exit.' : 'Roteiro v3 pronto.');
        setStep('refs');
      } catch (error) {
        setBusy(false, error.message);
      }
    });
    $('mcStudioRefs').addEventListener('click', async () => {
      setBusy(true, 'Gerando referências…');
      try {
        state.refs = await request(API.refs, payload());
        paintStage();
        setBusy(false, 'Referências prontas. Monte as cenas.');
        setStep('scenes');
      } catch (error) {
        setBusy(false, error.message);
      }
    });
    $('mcStudioScenes').addEventListener('click', async () => {
      setBusy(true, 'Montando cenas…');
      try {
        const result = await request(API.scenes, payload());
        state.scenes = result.scenes || [];
        state.scenes.forEach((scene) => {
          state.recipes[scene.id] = scene.recipe || {};
        });
        showScene(0);
        setBusy(false, 'Cenas montadas em HTML. Sem chamada de imagem por quadro.');
      } catch (error) {
        setBusy(false, error.message);
      }
    });
    $('mcStudioReset').addEventListener('click', () => {
      const scene = state.scenes[state.sceneIndex];
      if (!scene) return;
      delete state.recipes[scene.id];
      renderToggles();
    });
    $('mcStudioPrev').addEventListener('click', () => showScene(state.sceneIndex - 1));
    $('mcStudioNext').addEventListener('click', () => showScene(state.sceneIndex + 1));
    document.addEventListener('keydown', (event) => {
      if (!state.scenes.length || state.busy) return;
      if (event.key === 'ArrowLeft') showScene(state.sceneIndex - 1);
      if (event.key === 'ArrowRight') showScene(state.sceneIndex + 1);
    });
    $('mcStudioAnimate').addEventListener('click', async () => {
      if (!state.scenes.length) {
        status('Monte as cenas antes de animar.');
        return;
      }
      const spec = await request(API.animate, payload());
      let index = 0;
      clearInterval(state.playTimer);
      showScene(0);
      state.playTimer = window.setInterval(() => {
        index += 1;
        if (index >= state.scenes.length) {
          clearInterval(state.playTimer);
          return;
        }
        showScene(index);
      }, Math.max(400, (spec.seconds || 5) * 1000 / state.scenes.length));
      status(`Display ${spec.seconds}s · CSS · R$ 0`);
    });
    $('mcStudioVideo').addEventListener('click', async () => {
      setBusy(true, 'Cotando Seedance…');
      try {
        const plan = await request(API.video, payload({ submit: false, resolution: '720p' }));
        money(plan.quote);
        setBusy(false, '');
        const cost = plan.quote?.estimated_cost_usd || 0.38;
        const ok = await askConfirm(
          'Gravar CTV',
          `Seedance 5s, 720p, sem áudio. Cerca de US$ ${cost}.`,
        );
        if (!ok) {
          status('Vídeo cancelado.');
          return;
        }
        setBusy(true, 'Enviando Seedance…');
        const job = await request(API.video, payload({ submit: true, resolution: '720p' }));
        $('mcStudioVideoStatus').textContent = job.job?.id
          ? `Job ${job.job.id} · ${job.job.status || 'pending'}`
          : 'Pedido enviado.';
        setBusy(false, 'Vídeo em fila. CTV 5s, 720p, sem áudio.');
      } catch (error) {
        setBusy(false, error.message);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (!$('mcStudio')) return;
    bind();
    try {
      await Promise.all([loadClients(), loadCampaigns()]);
    } catch (_error) {
      status('Não carregou as marcas.');
    }
    refreshQuote();
  });
})();
