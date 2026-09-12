(() => {
  const API = {
    formats: '/parametros/api/format-lab/formats',
    quote: '/parametros/api/format-lab/quote',
    sessions: '/parametros/api/format-lab/sessions',
    clients: '/parametros/api/clients',
  };
  const MODEL_BRANDS = [
    { slug: 'tim-controle-ctv', match: 'tim', label: 'Tim' },
    { slug: 'vivara-presente-ctv', match: 'vivara', label: 'Vivara' },
    { slug: 'rededor-cuidado-ctv', match: 'rede d', label: "Rede D’Or" },
  ];
  const OBJECTIVES = ['Reconhecimento', 'Consideração', 'Conversão', 'Lançamento'];

  const state = {
    formats: [],
    formatGroups: [],
    models: [],
    clients: [],
    clientId: '',
    formatKey: 'video-linear-15',
    formatTouched: false,
    variant: 'A',
    sceneCount: 4,
    objective: 'Reconhecimento',
    density: 'tv',
    hookTension: 0.55,
    castLock: true,
    productLock: true,
    campaignSlug: '',
    campaign: null,
    sessionId: '',
    mounting: false,
    session: null,
    storyboard: [],
    sceneId: 'scene_01',
    images: [],
    keyVisuals: {},
    versionAttempt: 0,
    quote: null,
    zoom: 1,
    offer: 'O presente que marca o momento',
    baseSkills: [
      { id: 'create', label: 'Conceito' },
      { id: 'implement', label: 'HTML' },
      { id: 'video-15', label: 'Video 15s' },
    ],
    visualSkills: [],
    selectedSkills: ['imagegen-frontend-web'],
    runOp: 'concept',
  };

  const RUN_BEATS = [
    { id: 'concept', title: 'Conceito', run: 'Montar o conceito' },
    { id: 'base', title: 'Base', run: 'Montar a base' },
    { id: 'scene', title: 'Cena', run: 'Montar a cena' },
    { id: 'close', title: 'Fechar', run: 'Fechar o still' },
    { id: 'approve', title: 'Aprovar', run: 'Mandar à Bancada' },
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function setStatus(text) {
    const node = $('mcMesaStatus');
    if (node) node.textContent = text;
    setBaseNote(text);
  }

  function mesaToast(message, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type || 'success', 2800);
    }
  }

  function setModalState(next, extra) {
    const dialog = $('mcMesaBaseDialog');
    if (!dialog) return;
    const payload = extra || {};
    dialog.dataset.state = next;
    dialog.classList.toggle('is-busy', next === 'loading');
    const badge = $('mcMesaRunBadge');
    if (badge) {
      badge.textContent = (
        next === 'loading' ? 'Em revisão'
          : next === 'success' ? 'Pronto'
            : next === 'warning' ? 'Em revisão'
              : next === 'error' ? 'Erro'
                : 'Rascunho'
      );
    }
    const wait = $('mcMesaBaseWait');
    if (wait) wait.hidden = next !== 'loading';
    if (next === 'loading') {
      if (payload.label && $('mcMesaBaseWaitLabel')) {
        $('mcMesaBaseWaitLabel').textContent = payload.label;
      }
      if (payload.hint && $('mcMesaBaseWaitHint')) {
        $('mcMesaBaseWaitHint').textContent = payload.hint;
      }
      paintLoadSteps(payload.load || state.runOp || currentOp());
    }
    const success = $('mcMesaSuccess');
    const errorBox = $('mcMesaError');
    const warning = $('mcMesaWarning');
    if (success) {
      success.hidden = next !== 'success';
      if (payload.title && $('mcMesaSuccessTitle')) $('mcMesaSuccessTitle').textContent = payload.title;
      if (payload.text && $('mcMesaSuccessText')) $('mcMesaSuccessText').textContent = payload.text;
    }
    if (errorBox) {
      errorBox.hidden = next !== 'error';
      if (payload.title && $('mcMesaErrorTitle')) $('mcMesaErrorTitle').textContent = payload.title;
      if (payload.text && $('mcMesaErrorText')) $('mcMesaErrorText').textContent = payload.text;
      const tech = $('mcMesaErrorTech');
      if (tech) {
        tech.hidden = true;
        tech.textContent = payload.detail || '';
      }
    }
    if (warning) {
      warning.hidden = next !== 'warning';
      if (payload.title && $('mcMesaWarningTitle')) $('mcMesaWarningTitle').textContent = payload.title;
      if (payload.text && $('mcMesaWarningText')) $('mcMesaWarningText').textContent = payload.text;
    }
    const run = $('mcMesaBaseRun');
    if (run && next === 'loading') run.disabled = true;
    if (run && next !== 'loading') labelRunButton();
  }

  function paintLoadSteps(op) {
    const order = ['analyze', 'concept', 'finish'];
    const current = (
      op === 'concept' ? 'analyze'
        : op === 'base' ? 'concept'
          : 'finish'
    );
    const idx = order.indexOf(current);
    document.querySelectorAll('#mcMesaLoadSteps [data-load]').forEach((item) => {
      const key = item.getAttribute('data-load');
      const position = order.indexOf(key);
      item.classList.toggle('is-current', key === current);
      item.classList.toggle('is-done', position > -1 && position < idx);
    });
  }

  function showInspectorTab(name) {
    document.querySelectorAll('[data-insp]').forEach((button) => {
      const current = button.getAttribute('data-insp') === name;
      button.setAttribute('aria-selected', current ? 'true' : 'false');
    });
    document.querySelectorAll('[data-insp-panel]').forEach((panel) => {
      panel.hidden = panel.getAttribute('data-insp-panel') !== name;
    });
  }

  function paintFieldHints() {
    const headline = $('mcMesaHeadline');
    const support = $('mcMesaSupport');
    const hHint = $('mcMesaHeadlineHint');
    const sHint = $('mcMesaSupportHint');
    if (headline && hHint) {
      const count = headline.value.length;
      hHint.textContent = count > 55
        ? `${count} caracteres — a TV lê melhor até 55.`
        : 'Até 55 caracteres na TV.';
      hHint.classList.toggle('is-warn', count > 55);
    }
    if (support && sHint) {
      const count = support.value.length;
      sHint.textContent = count > 90
        ? `${count} caracteres — o apoio cabe em 90.`
        : 'Até 90 caracteres de apoio.';
      sHint.classList.toggle('is-warn', count > 90);
    }
  }

  function askConfirm({ title, body, confirmLabel }) {
    return new Promise((resolve) => {
      const dialog = $('mcMesaConfirm');
      if (!dialog) {
        resolve(true);
        return;
      }
      if (title && $('mcMesaConfirmTitle')) $('mcMesaConfirmTitle').textContent = title;
      if (body && $('mcMesaConfirmText')) $('mcMesaConfirmText').textContent = body;
      if (confirmLabel && $('mcMesaConfirmOk')) $('mcMesaConfirmOk').textContent = confirmLabel;
      const finish = (ok) => {
        if (dialog.open) dialog.close();
        resolve(Boolean(ok));
      };
      $('mcMesaConfirmOk')?.addEventListener('click', () => finish(true), { once: true });
      $('mcMesaConfirmCancel')?.addEventListener('click', () => finish(false), { once: true });
      dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        finish(false);
      }, { once: true });
      dialog.showModal();
    });
  }

  function pickKeyVisual(event) {
    event?.preventDefault();
    event?.stopPropagation();
    showInspectorTab('assets');
    if (brandVisuals().length) {
      $('mcMesaKeys')?.querySelector('[data-visual]')?.focus();
      return;
    }
    $('mcMesaFiles')?.click();
  }

  function toggleHistory(forceOpen) {
    const drawer = $('mcMesaDrawer');
    if (!drawer) return;
    drawer.hidden = forceOpen == null ? !drawer.hidden : !forceOpen;
  }

  async function readJson(response) {
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || 'A mesa não concluiu.');
    }
    return payload.data;
  }

  async function boot() {
    if (!$('mcMesa')) return;
    bind();
    renderObjectives();
    renderStrip();
    try {
      const [catalog, clients] = await Promise.all([
        fetch(API.formats, { credentials: 'same-origin' }).then(readJson),
        fetch(API.clients, { credentials: 'same-origin' }).then(readJson),
      ]);
      state.formats = catalog.formats || [];
      state.formatGroups = catalog.format_groups || [];
      state.models = catalog.campaigns || [];
      state.clients = clients || [];
      state.quote = catalog.quote || null;
      state.baseSkills = catalog.base_skills || state.baseSkills;
      state.visualSkills = catalog.visual_skills || [];
      state.selectedSkills = state.visualSkills
        .filter((item) => item.default)
        .map((item) => item.id);
      renderFormats();
      renderBrands();
      renderSelects();
      renderSkills();
      renderCost();
      autofillVivara();
      renderDna();
      await resumeDesk();
      renderOps();
      fitStage();
    } catch (error) {
      setStatus(error.message);
    }
  }

  function bind() {
    $('mcMesaClient')?.addEventListener('change', (event) => selectClient(event.target.value));
    $('mcMesaHistory')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-session]');
      if (!button) return;
      openSavedSession(button.getAttribute('data-session'));
    });
    $('mcMesaCounts')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-count]');
      if (!button) return;
      state.sceneCount = Number(button.getAttribute('data-count'));
      document.querySelectorAll('#mcMesaCounts [data-count]').forEach((node) => {
        node.classList.toggle('is-current', node === button);
      });
      renderStrip();
      refreshQuote();
    });
    $('mcMesaObjectives')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-objective]');
      if (!button) return;
      state.objective = button.getAttribute('data-objective');
      renderObjectives();
    });
    $('mcMesaDensity')?.addEventListener('input', (event) => {
      state.density = Number(event.target.value) ? 'tv' : 'low';
    });
    $('mcMesaTension')?.addEventListener('input', (event) => {
      state.hookTension = Number(event.target.value) / 100;
    });
    $('mcMesaCastLock')?.addEventListener('change', (event) => {
      state.castLock = event.target.checked;
    });
    $('mcMesaProductLock')?.addEventListener('change', (event) => {
      state.productLock = event.target.checked;
    });
    $('mcMesaBrands')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-model]');
      if (!button) return;
      pickModel(button.getAttribute('data-model'));
    });
    const drop = $('mcMesaDrop');
    const input = $('mcMesaFiles');
    drop?.addEventListener('click', () => input?.click());
    drop?.addEventListener('dragover', (event) => {
      event.preventDefault();
      drop.classList.add('is-dragging');
    });
    drop?.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
    drop?.addEventListener('drop', (event) => {
      event.preventDefault();
      drop.classList.remove('is-dragging');
      takeFiles(event.dataTransfer?.files);
    });
    input?.addEventListener('change', () => takeFiles(input.files));
    document.querySelectorAll('[data-insp]').forEach((button) => {
      button.addEventListener('click', () => showInspectorTab(button.getAttribute('data-insp')));
    });
    $('mcMesaPickKey')?.addEventListener('click', pickKeyVisual);
    $('mcMesaGuide')?.addEventListener('click', () => {
      setStatus('Guia: margem segura de 8%, headline no terço superior, logo só no fechamento.');
    });
    $('mcMesaHistoryToggle')?.addEventListener('click', () => toggleHistory());
    $('mcMesaDrawerClose')?.addEventListener('click', () => toggleHistory(false));
    $('mcMesaAnalyze')?.addEventListener('click', () => {
      openBaseDialog('concept');
      mountConcept();
    });
    $('mcMesaMockup')?.addEventListener('click', () => openBaseDialog('base'));
    $('mcMesaBaseRun')?.addEventListener('click', () => runCurrentBeat());
    $('mcMesaBaseCancel')?.addEventListener('click', () => leaveBaseDialog());
    $('mcMesaBaseDialog')?.addEventListener('cancel', (event) => {
      if ($('mcMesaBaseDialog')?.classList.contains('is-busy') || $('mcMesaBaseDialog')?.dataset.state === 'loading') {
        event.preventDefault();
      }
    });
    $('mcMesaBaseDialog')?.querySelector('.mc-run-top')?.addEventListener('submit', (event) => {
      if ($('mcMesaBaseDialog')?.classList.contains('is-busy') || $('mcMesaBaseDialog')?.dataset.state === 'loading') {
        event.preventDefault();
      }
    });
    $('mcMesaErrorRetry')?.addEventListener('click', () => runCurrentBeat());
    $('mcMesaErrorKv')?.addEventListener('click', () => {
      $('mcMesaBaseDialog')?.close();
      pickKeyVisual();
    });
    $('mcMesaErrorSkip')?.addEventListener('click', () => {
      $('mcMesaBaseDialog')?.close();
      setStatus('Cena pulada. Siga para a próxima da tira.');
    });
    $('mcMesaErrorDetails')?.addEventListener('click', () => {
      const tech = $('mcMesaErrorTech');
      if (tech) tech.hidden = !tech.hidden;
    });
    $('mcMesaRunSeq')?.addEventListener('click', (event) => {
      if ($('mcMesaBaseDialog')?.classList.contains('is-busy')) return;
      const button = event.target.closest('[data-op]');
      if (!button) return;
      openBaseDialog(button.getAttribute('data-op'));
    });
    $('mcMesaGenerate')?.addEventListener('click', () => {
      openBaseDialog('scene');
      assembleSceneOne();
    });
    $('mcMesaClose')?.addEventListener('click', () => {
      openBaseDialog('close');
      closeScene();
    });
    $('mcMesaApprove')?.addEventListener('click', (event) => {
      openBaseDialog('approve');
      handoff(event);
    });
    $('mcMesaRunTakes')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-attempt]');
      if (!button) return;
      state.versionAttempt = Number(button.getAttribute('data-attempt'));
      showScene();
      paintRunStill();
    });
    $('mcMesaSkills')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-skill]');
      if (!button) return;
      toggleSkill(button.getAttribute('data-skill'));
    });
    $('mcMesaLogo')?.addEventListener('change', (event) => lockSceneField('logo_visible', event.target.checked));
    $('mcMesaOffer')?.addEventListener('input', (event) => {
      state.offer = event.target.value;
    });
    $('mcMesaHeadline')?.addEventListener('input', (event) => {
      lockSceneField('headline', event.target.value);
      paintFieldHints();
    });
    $('mcMesaSupport')?.addEventListener('input', (event) => {
      lockSceneField('support', event.target.value);
      paintFieldHints();
    });
    $('mcMesaKeys')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-visual]');
      if (!button) return;
      pinKeyVisual(button.getAttribute('data-visual'));
    });
    $('mcMesaVersions')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-attempt]');
      if (!button) return;
      state.versionAttempt = Number(button.getAttribute('data-attempt'));
      showScene();
      mesaToast(`Versão v${state.versionAttempt} no quadro.`);
    });
    $('mcMesaStrip')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-scene]');
      if (!button) return;
      state.sceneId = button.getAttribute('data-scene');
      state.versionAttempt = 0;
      renderStrip();
      renderKeys();
      renderEdit();
      showScene();
      renderLayers();
    });
    window.addEventListener('resize', fitStage);
    document.querySelectorAll('.mc-desk-nav details').forEach((item) => {
      item.addEventListener('toggle', () => {
        if (!item.open) return;
        document.querySelectorAll('.mc-desk-nav details').forEach((other) => {
          if (other !== item) other.removeAttribute('open');
        });
      });
    });
  }

  function knobs() {
    return {
      format: state.formatKey,
      variant: state.variant,
      intent: 'create',
      campaign_slug: state.campaignSlug,
      scene_count: state.sceneCount,
      objective: state.objective,
      density: state.density,
      hook_tension: state.hookTension,
      cast_lock: state.castLock,
      product_lock: state.productLock,
      images: selectedVisuals(),
      key_visuals: { ...state.keyVisuals },
      storyboard: state.storyboard.map((item) => ({
        id: item.id,
        headline: item.headline,
        support: item.support,
        cta: item.cta,
        set_note: item.set_note,
        action_note: item.action_note,
        logo_visible: item.logo_visible,
      })),
      mockup_passes: 3,
      message: state.offer || state.campaign?.title || state.objective,
      offer: state.offer || state.campaign?.offer || state.campaign?.title || '',
      selected_skills: [...state.selectedSkills],
    };
  }

  function currentClient() {
    return state.clients.find((item) => String(item.id) === String(state.clientId));
  }

  function selectClient(id) {
    if (String(state.clientId) !== String(id)) {
      state.sessionId = '';
      state.session = null;
      state.storyboard = [];
    }
    state.clientId = id;
    const client = currentClient();
    const match = MODEL_BRANDS.find((item) => nameMatches(client?.name, item.match));
    if (match) {
      state.campaignSlug = match.slug;
      state.campaign = state.models.find((item) => item.slug === match.slug) || null;
      if (!state.formatTouched && state.campaign?.format) state.formatKey = state.campaign.format;
    } else {
      state.campaignSlug = '';
      state.campaign = null;
    }
    if (state.campaign?.offer || state.campaign?.title) {
      state.offer = state.campaign.offer || state.campaign.title;
    }
    preselectBrandVisuals();
    renderDna();
    renderKeys();
    renderEdit();
    renderBrands();
    renderFormats();
    $('mcMesaAnalyze').disabled = !state.clientId;
    $('mcMesaGenerate').disabled = !state.clientId;
    labelGenerate();
    setStatus(state.clientId ? 'Marca pronta. Escolha o key visual e monte a cena 1.' : 'Escolha a marca. O 15s se monta em seguida.');
    resumeDesk();
  }

  function pickModel(slug) {
    state.campaignSlug = slug;
    state.campaign = state.models.find((item) => item.slug === slug) || null;
    const model = MODEL_BRANDS.find((item) => item.slug === slug);
    const client = state.clients.find((item) => nameMatches(item.name, model?.match));
    if (client) {
      state.clientId = String(client.id);
      const select = $('mcMesaClient');
      if (select) select.value = state.clientId;
    }
    if (!state.formatTouched && state.campaign?.format) state.formatKey = state.campaign.format;
    if (state.campaign?.variant) state.variant = state.campaign.variant;
    if (state.campaign?.offer || state.campaign?.title) {
      state.offer = state.campaign.offer || state.campaign.title;
    }
    if (state.campaign?.objective) state.objective = /consider/i.test(state.campaign.objective) ? 'Consideração' : state.objective;
    preselectBrandVisuals();
    renderBrands();
    renderFormats();
    renderObjectives();
    renderDna();
    renderKeys();
    renderEdit();
    $('mcMesaAnalyze').disabled = !state.clientId;
    if (!state.clientId) {
      setStatus(`Campanha ${model?.label || slug} pronta. Selecione a marca para usar o payload.`);
    }
    resumeDesk();
  }

  function autofillVivara() {
    pickModel('vivara-presente-ctv');
    const offer = $('mcMesaOffer');
    if (offer && !offer.value) offer.value = state.offer;
    if (state.clientId) {
      setStatus('Vivara na mesa. Escolha as imagens da marca para o key visual.');
    } else {
      setStatus('Campanha Vivara pronta. Se a marca existir no seletor, ela entra sozinha.');
    }
  }

  function historyLabel(item) {
    if (item.stage === 'base') return 'Base';
    if (item.stage === 'scene') return 'Cena';
    if (item.stage === 'close') return 'Still';
    if (item.stage === 'approve') return 'Aprovado';
    return 'Conceito';
  }

  function renderHistory(items) {
    const list = $('mcMesaHistory');
    if (!list) return;
    const rows = (items || []).filter((item) => item.stage && item.stage !== 'draft');
    list.hidden = !rows.length;
    list.innerHTML = rows.slice(0, 4).map((item) => (
      `<li data-stage="${item.stage || 'concept'}">
        <button type="button" data-session="${item.session_id || item.id || ''}">${historyLabel(item)} · ${item.headline || item.format || '15s'}</button>
      </li>`
    )).join('');
  }

  async function resumeDesk() {
    if (!state.clientId) {
      renderHistory([]);
      return null;
    }
    const params = new URLSearchParams({
      client_id: state.clientId,
      format: state.formatKey || '',
      campaign_slug: state.campaignSlug || '',
    });
    try {
      const data = await fetch(`${API.sessions}?${params}`, { credentials: 'same-origin' }).then(readJson);
      renderHistory(data.history?.length ? data.history : data.sessions || []);
      if (data.active?.storyboard?.length || data.active?.base_html) {
        applySession(data.active);
        setStatus(
          data.active.base_html
            ? 'Base desta campanha retomada. Siga para a cena.'
            : 'Conceito desta campanha retomado. Monte a base.'
        );
      }
      return data.active || null;
    } catch (_error) {
      renderHistory([]);
      return null;
    }
  }

  async function openSavedSession(sessionId) {
    if (!sessionId) return;
    const data = await fetch(`${API.sessions}/${sessionId}`, { credentials: 'same-origin' }).then(readJson);
    applySession(data);
    setStatus(
      data.base_html
        ? 'Base salva neste formato. Siga para a cena.'
        : 'Conceito salvo nesta campanha. Monte a base.'
    );
    openBaseDialog(data.base_html ? 'base' : 'concept');
  }

  function nameMatches(name, needle) {
    return String(name || '').toLowerCase().includes(String(needle || '').toLowerCase());
  }

  function renderBrands() {
    const root = $('mcMesaBrands');
    if (!root) return;
    root.innerHTML = MODEL_BRANDS.map((item) => {
      const current = state.campaignSlug === item.slug;
      return `<button type="button" data-model="${item.slug}" class="${current ? 'is-current' : ''}">${item.label}</button>`;
    }).join('');
  }

  function currentFormat() {
    return (state.formats || []).find((item) => item.key === state.formatKey) || {
      key: 'video-linear-15',
      label: 'Video 15s',
      size_label: '1920×1080',
      aspect_ratio: '16:9',
      orientation: 'horizontal',
      group: '15s',
      kind: 'video',
    };
  }

  function applyStage() {
    const format = currentFormat();
    const viewport = $('mcMesaViewport');
    const [width, height] = String(format.aspect_ratio || '16:9').split(':').map(Number);
    if (viewport && width && height) {
      viewport.style.setProperty('--mc-stage-ratio', `${width} / ${height}`);
      viewport.classList.toggle('is-vertical', height > width);
      viewport.classList.toggle('is-wide', width / height >= 3);
    }
    const summary = $('mcFormatSummary');
    if (summary) {
      summary.textContent = `${format.label} · ${format.size_label || format.platform_label || format.aspect_ratio}`;
    }
    const stage = $('mcMesaStage');
    if (stage) {
      stage.setAttribute('aria-label', `Palco ${format.size_label || format.aspect_ratio}`);
    }
    const title = document.querySelector('#mcMesaDrop .mc-mesa-plate strong');
    const drop = document.querySelector('#mcMesaDrop .mc-mesa-lead');
    if (title) {
      title.textContent = format.kind === 'banner'
        ? `Monte o banner ${format.size_label}`
        : 'Escolha o key visual e monte o 15s';
    }
    if (drop) {
      drop.textContent = format.kind === 'banner'
        ? `Quatro ou cinco cenas no retângulo ${format.size_label}.`
        : 'Selecione um asset da campanha ou envie uma nova imagem.';
    }
    const meta = $('mcMesaStageMeta');
    if (meta) {
      meta.textContent = `${format.aspect_ratio || '16:9'} · ${format.size_label || '1920 × 1080'}`;
    }
  }

  function renderFormats() {
    const groups = state.formatGroups || [];
    const menu = $('mcFormatMenu');
    if (menu) {
      const order = groups.length
        ? groups
        : [{ key: '15s', label: '15s na TV' }];
      menu.innerHTML = order.map((group) => {
        const items = (state.formats || []).filter((item) => (item.group || '15s') === group.key);
        if (!items.length) return '';
        return `<p class="mc-format-group">${group.label}</p>` + items.map((item) => (
          `<button type="button" data-format="${item.key}" class="${item.key === state.formatKey ? 'is-current' : ''}">${item.label} · ${item.size_label || ''}</button>`
        )).join('');
      }).join('');
      menu.querySelectorAll('[data-format]').forEach((button) => {
        button.addEventListener('click', () => {
          state.formatKey = button.getAttribute('data-format');
          state.formatTouched = true;
          $('mcFormatDrop')?.removeAttribute('open');
          renderFormats();
        });
      });
    }
    applyStage();
  }

  function renderObjectives() {
    const root = $('mcMesaObjectives');
    if (!root) return;
    root.innerHTML = OBJECTIVES.map((item) => (
      `<button type="button" data-objective="${item}" class="${item === state.objective ? 'is-current' : ''}">${item}</button>`
    )).join('');
  }

  function renderSelects() {
    const client = $('mcMesaClient');
    if (!client) return;
    client.innerHTML = '<option value="">Marca</option>' + state.clients.map((item) => (
      `<option value="${item.id}">${item.name || item.id}</option>`
    )).join('');
  }

  function renderDna() {
    const box = $('mcMesaDna');
    const client = currentClient();
    const name = $('mcMesaBrandName');
    const tag = $('mcMesaBrandTag');
    const logo = $('mcMesaBrandLogo');
    if (!client) {
      if (name) name.textContent = 'Marca';
      if (tag) tag.textContent = 'Selecione uma marca para ver o sistema.';
      if (logo) {
        logo.removeAttribute('src');
        logo.hidden = true;
      }
      if (box) box.innerHTML = '<p>Selecione uma marca. O payload entra no quadro, não só ao lado.</p>';
      return;
    }
    const profile = client.brand_profile || {};
    const colors = (profile.color_palette || []).map((item) => item.hex || item).filter(Boolean);
    if (client.primary_color) colors.unshift(client.primary_color);
    const line = profile.creative_line || {};
    const summary = profile.brand_summary || line.signature_summary || client.tone_of_voice || '';
    if (name) name.textContent = client.name || 'Marca';
    if (tag) {
      const tagline = profile.tagline || line.tagline || '';
      tag.textContent = tagline || 'Sistema da marca';
    }
    const logoUrl = client.logo_url || client.logo || profile.logo_url || '';
    if (logo) {
      if (logoUrl) logo.src = logoUrl;
      else logo.removeAttribute('src');
      logo.hidden = !logoUrl;
    }
    if (!box) return;
    const short = summary.length > 140 ? `${summary.slice(0, 137).trim()}…` : summary;
    box.innerHTML = `
      <p>${short}</p>
      <ul>${colors.slice(0, 5).map((hex) => `<li style="background:${hex}"></li>`).join('')}</ul>
    `;
  }

  function brandAssetUrl(asset) {
    return asset?.asset_path || asset?.source_url || asset?.asset_url || asset?.stored_url || '';
  }

  function brandVisuals() {
    const client = currentClient();
    return (client?.brand_assets || []).filter((asset) => {
      const role = asset.role || 'reference';
      return role !== 'logo' && brandAssetUrl(asset);
    });
  }

  function preselectBrandVisuals() {
    const urls = brandVisuals().map(brandAssetUrl).filter(Boolean).slice(0, state.sceneCount);
    urls.forEach((url, index) => {
      const sceneId = `scene_0${index + 1}`;
      if (!state.keyVisuals[sceneId]) state.keyVisuals[sceneId] = url;
    });
  }

  function selectedVisuals() {
    const pinned = Object.values(state.keyVisuals).filter(Boolean);
    return [...new Set([...pinned, ...state.images])].slice(0, 8);
  }

  function pinKeyVisual(url) {
    if (!url) return;
    state.keyVisuals[state.sceneId] = url;
    renderKeys();
    const card = state.storyboard.find((item) => item.id === state.sceneId);
    if (card) card.key_visual = url;
    setStatus('Key visual desta cena saiu da marca.');
    mesaToast('Key visual atualizado.');
  }

  function lockSceneField(field, value) {
    let card = state.storyboard.find((item) => item.id === state.sceneId);
    if (!card) {
      card = { id: state.sceneId, position: Number(state.sceneId.slice(-1)) || 1 };
      state.storyboard.push(card);
    }
    if (field === 'logo_visible' && isLastScene(card.purpose || state.sceneId)) {
      card[field] = true;
      return;
    }
    card[field] = value;
  }

  function renderKeys() {
    const root = $('mcMesaKeys');
    if (!root) return;
    const assets = brandVisuals();
    if (!assets.length) {
      root.innerHTML = '<p>Nenhuma imagem na marca. Abra Marcas e grave criativos — eles viram o key visual.</p>';
      return;
    }
    const current = state.keyVisuals[state.sceneId];
    root.innerHTML = `<p>Key visual da campanha — clique para esta cena</p>` + assets.slice(0, 8).map((asset) => {
      const url = brandAssetUrl(asset);
      const selected = current === url;
      return `<button type="button" data-visual="${url}" class="${selected ? 'is-current' : ''}">
        <img src="${url}" alt="${asset.role || 'referência'}">
      </button>`;
    }).join('');
  }

  function renderEdit() {
    const card = state.storyboard.find((item) => item.id === state.sceneId) || {};
    const offer = $('mcMesaOffer');
    const headline = $('mcMesaHeadline');
    const support = $('mcMesaSupport');
    if (offer && document.activeElement !== offer) offer.value = state.offer || '';
    if (headline && document.activeElement !== headline) headline.value = card.headline || '';
    if (support && document.activeElement !== support) support.value = card.support || '';
    const logo = $('mcMesaLogo');
    if (logo && document.activeElement !== logo) {
      const last = isLastScene(card.purpose || state.sceneId);
      logo.checked = last
        ? true
        : (Object.prototype.hasOwnProperty.call(card, 'logo_visible')
          ? !!card.logo_visible
          : defaultLogoVisible(card.purpose || state.sceneId));
      logo.disabled = last;
      const caption = logo.parentElement?.querySelector('span');
      if (caption) {
        caption.textContent = last
          ? 'Logomarca no centro (fechamento)'
          : 'Logomarca nesta cena';
      }
    }
    paintFieldHints();
  }

  function plateLabel(purposeOrId) {
    const key = String(purposeOrId || '').toLowerCase();
    if (/cta|response|scene_04|scene_05/.test(key)) return 'Cartão final';
    if (/proof|lifestyle|experience|discovery|context|scene_03/.test(key)) return 'Foto no quadro';
    return 'Produto à direita';
  }

  function isLastScene(purposeOrId) {
    const key = String(purposeOrId || '').toLowerCase();
    const count = Number(state.sceneCount || state.storyboard.length || 4);
    if (/cta|response/.test(key)) return true;
    if (count >= 5) return /scene_05/.test(key);
    return /scene_04/.test(key);
  }

  function defaultLogoVisible(purposeOrId) {
    const purpose = String(purposeOrId || '').toLowerCase();
    if (isLastScene(purpose)) return true;
    return /brand/.test(purpose);
  }

  function renderCost() {
    const node = $('mcMesaCost');
    if (!node) return;
    const quote = state.session?.cost || state.quote;
    const brl = quote?.spent_brl ?? quote?.estimated_brl ?? quote?.spent_brl;
    const usd = quote?.cost_usd ?? quote?.estimated_cost_usd ?? 0;
    const label = quote?.spent_brl != null
      ? `R$ ${Number(quote.spent_brl).toFixed(2)}`
      : (brl != null ? `R$ ${Number(brl).toFixed(2)}` : `US$ ${Number(usd).toFixed(2)}`);
    node.textContent = label;
  }

  async function refreshQuote() {
    try {
      state.quote = await fetch(API.quote, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene_count: state.sceneCount, kind: 'full' }),
      }).then(readJson);
      renderCost();
    } catch (_error) {
      renderCost();
    }
  }

  function renderStrip() {
    const strip = $('mcMesaStrip');
    if (!strip) return;
    const cards = state.storyboard.length
      ? state.storyboard
      : Array.from({ length: state.sceneCount }, (_, index) => ({
        id: `scene_0${index + 1}`,
        position: index + 1,
        headline: '',
      }));
    strip.innerHTML = cards.map((item, index) => {
      const id = item.id || `scene_0${index + 1}`;
      const current = id === state.sceneId;
      const plate = plateLabel(item.purpose || id);
      const scene = (state.session?.scenes || []).find((row) => row.id === id);
      const done = Boolean(scene?.html || scene?.stack || (item.headline && !current));
      const errored = item.status === 'error' || scene?.status === 'error';
      const classes = [
        current ? 'is-current' : '',
        done && !current && !errored ? 'is-done' : '',
        errored ? 'is-error' : '',
      ].filter(Boolean).join(' ');
      return `<li class="${classes}">
        <button type="button" data-scene="${id}" class="${current ? 'is-current' : ''}">
          <em>${String(index + 1).padStart(2, '0')}</em>
          <span>${item.headline || plate}</span>
        </button>
      </li>`;
    }).join('');
  }

  function currentOp() {
    if (state.session?.qa?.passed || state.session?.closed?.png_data_url) return 'approve';
    const sceneReady = (state.session?.scenes || []).some(
      (item) => item.id === state.sceneId && (item.html || item.stack)
    );
    if (sceneReady) return 'close';
    if (state.session?.base_html) return 'scene';
    if (state.storyboard.length) return 'base';
    return 'concept';
  }

  function renderOps(busy) {
    const root = $('mcMesaOps');
    if (!root) return;
    const order = ['concept', 'base', 'scene', 'close', 'approve'];
    const active = currentOp();
    const idx = order.indexOf(active);
    root.querySelectorAll('[data-op]').forEach((item) => {
      const op = item.getAttribute('data-op');
      const position = order.indexOf(op);
      item.classList.toggle('is-current', op === active);
      item.classList.toggle('is-done', position > -1 && position < idx);
      item.classList.toggle('is-waiting', position > idx);
      item.classList.toggle('is-busy', Boolean(busy) && op === busy);
      if (op === active) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
  }

  function renderTrace(steps) {
    const list = $('mcMesaTrace');
    if (!list) return;
    list.innerHTML = (steps || []).map((item) => (
      `<li data-id="${item.id || ''}" data-status="${item.status || 'queued'}"><strong>${item.label || item.id}</strong></li>`
    )).join('');
    renderOps();
  }

  function renderLayers() {
    const list = $('mcMesaLayers');
    const scene = (state.session?.scenes || []).find((item) => item.id === state.sceneId)
      || (state.session?.scenes || [])[0];
    if (!list) return;
    const layers = scene?.layers || [];
    list.hidden = !layers.length;
    list.innerHTML = layers.slice(0, 8).map((item) => (
      `<li>
        <button type="button" data-layer="${item.id || ''}">${(item.id || '').replace(/^scene_0\d-/, '') || item.tipo}</button>
      </li>`
    )).join('');
    list.querySelectorAll('[data-layer]').forEach((button) => {
      button.addEventListener('click', () => patchLayer(button.getAttribute('data-layer')));
    });
  }

  function takeFiles(fileList) {
    const files = Array.from(fileList || []);
    files.forEach((file) => {
      if (!file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = () => state.images.push(reader.result);
      reader.readAsDataURL(file);
    });
    if (files.length) setStatus('Referência na mesa. A marca e o conceito entram juntos.');
  }

  async function ensureSession() {
    if (state.sessionId) return state.sessionId;
    const clientId = Number(state.clientId);
    if (!Number.isFinite(clientId) || clientId <= 0) {
      throw new Error('Escolha a marca. O 15s se monta em seguida.');
    }
    const data = await fetch(API.sessions, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: clientId,
        format: state.formatKey || 'video-linear-15',
        variant: state.variant || 'A',
        intent: 'create',
        campaign_slug: state.campaignSlug || '',
      }),
    }).then(readJson);
    state.sessionId = data.id;
    if (data.storyboard?.length || data.base_html) applySession(data);
    return state.sessionId;
  }

  async function mountConcept() {
    if (state.mounting) return;
    if (state.session?.qa?.passed) {
      const ok = await askConfirm({
        title: 'Regenerar o conceito aprovado?',
        body: 'O 15s aprovado será substituído.',
        confirmLabel: 'Regenerar conceito',
      });
      if (!ok) return;
    }
    state.mounting = true;
    const dialog = $('mcMesaBaseDialog');
    if (dialog && !dialog.open) openBaseDialog('concept');
    try {
      $('mcMesaAnalyze').disabled = true;
      renderOps('concept');
      state.runOp = 'concept';
      paintRunSeq();
      startRunProgress([
        { id: 'create', label: 'Conceito', status: 'running' },
        { id: 'refine', label: 'Melhor roteiro', status: 'queued' },
      ], 'Montando o conceito', 'Sessão → roteiro → tira');
      setStatus('Define a direção da cena. O retorno entra neste quadro.');
      const sessionId = await ensureSession();
      markRunProgress('create', 'done');
      markRunProgress('refine', 'running');
      const data = await fetch(`${API.sessions}/${sessionId}/storyboard`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(knobs()),
      }).then(readJson);
      state.session = data;
      state.sessionId = data.id;
      state.storyboard = data.storyboard || [];
      state.sceneId = (state.storyboard[0] || {}).id || 'scene_01';
      if (data.quote || data.cost) state.quote = data.cost || data.quote;
      renderStrip();
      renderTrace(data.passes || []);
      renderCost();
      $('mcMesaGenerate').disabled = !state.clientId;
      $('mcMesaMockup').disabled = !state.storyboard.length;
      $('mcMesaAnalyze').disabled = false;
      labelGenerate();
      renderEdit();
      const first = state.storyboard[0];
      $('mcMesaCaption').textContent = first?.headline || '';
      setStatus(
        data.provider === 'campaign'
          ? 'Roteiro da campanha na mesa. O provedor não respondeu; o conceito-base entrou.'
          : 'Conceito pronto. O retorno do roteiro está na tira. Siga para a base.'
      );
      revealStrip();
      state.runOp = 'base';
      paintRunStill();
      paintRunSeq();
      renderOps();
      setModalState('success', {
        title: 'Conceito pronto',
        text: 'O roteiro está na tira. Siga para a base.',
      });
      mesaToast('Conceito salvo.');
    } catch (error) {
      setStatus(error.message);
      $('mcMesaAnalyze').disabled = !state.clientId;
      paintRunSeq();
      renderOps();
      setModalState('error', {
        title: 'Não foi possível montar o conceito',
        text: error.message,
        detail: error.stack || error.message,
      });
    } finally {
      state.mounting = false;
      setRunBusy(false);
    }
  }

  function openBaseDialog(op) {
    const dialog = $('mcMesaBaseDialog');
    if (!dialog) {
      if (op === 'base') modelBase();
      return;
    }
    state.runOp = op || currentOp();
    paintRunSeq();
    paintRunStill();
    labelRunButton();
    if (dialog.dataset.state !== 'loading') setModalState('idle');
    if (!dialog.open) dialog.showModal();
  }

  async function leaveBaseDialog() {
    const dialog = $('mcMesaBaseDialog');
    if (!dialog) return;
    if (dialog.classList.contains('is-busy') || dialog.dataset.state === 'loading') return;
    const dirty = Boolean(state.storyboard.length && !state.session?.qa?.passed && dialog.dataset.state === 'warning');
    if (dirty) {
      const ok = await askConfirm({
        title: 'Voltar e perder esta passagem?',
        body: 'Há revisão pendente neste quadro.',
        confirmLabel: 'Voltar à mesa',
      });
      if (!ok) return;
    }
    dialog.close();
  }

  function runCurrentBeat() {
    const op = state.runOp || currentOp();
    if (op === 'concept') return mountConcept();
    if (op === 'base') return modelBase();
    if (op === 'scene') {
      if (!state.storyboard.length) {
        state.runOp = 'concept';
        paintRunSeq();
        setStatus('O roteiro ainda não está na mesa. Monte o conceito.');
        return null;
      }
      if (!state.session?.base_html) {
        state.runOp = 'base';
        paintRunSeq();
        setStatus('A base ainda não está no quadro. Monte a base.');
        return null;
      }
      return generateScene();
    }
    if (op === 'close') return closeScene();
    if (op === 'approve') return handoff();
    return null;
  }

  function setRunBusy(busy, label, hint) {
    if (busy) {
      setModalState('loading', {
        label,
        hint,
        load: state.runOp || currentOp(),
      });
      const node = $('mcMesaBaseRun');
      if (node) node.disabled = true;
      return;
    }
    const wait = $('mcMesaBaseWait');
    if (wait) wait.hidden = true;
    $('mcMesaBaseDialog')?.classList.remove('is-busy');
    labelRunButton();
  }

  function startRunProgress(steps, label, hint) {
    setRunBusy(true, label, hint);
    renderTrace(steps);
  }

  function markRunProgress(id, status) {
    const item = document.querySelector(`#mcMesaTrace [data-id="${id}"]`);
    if (item) item.dataset.status = status || 'done';
  }

  function paintRunSeq() {
    const active = state.runOp || currentOp();
    const order = RUN_BEATS.map((item) => item.id);
    const ready = currentOp();
    const readyIdx = order.indexOf(ready);
    const now = RUN_BEATS.find((item) => item.id === active);
    if ($('mcMesaRunNow') && now) $('mcMesaRunNow').textContent = now.title;
    if ($('mcMesaRunMark')) {
      const client = currentClient();
      $('mcMesaRunMark').textContent = client?.name ? `15s · ${client.name}` : '15s';
    }
    document.querySelectorAll('#mcMesaRunSeq [data-op]').forEach((item) => {
      const op = item.getAttribute('data-op');
      const position = order.indexOf(op);
      item.classList.toggle('is-current', op === active);
      item.classList.toggle('is-done', readyIdx > -1 && position < readyIdx);
      item.classList.toggle('is-waiting', position > readyIdx);
      if (op === active) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    labelRunButton();
  }

  function labelRunButton() {
    const node = $('mcMesaBaseRun');
    if (!node) return;
    const beat = RUN_BEATS.find((item) => item.id === (state.runOp || currentOp())) || RUN_BEATS[1];
    node.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i> ${beat.run}`;
    node.disabled = beat.id === 'concept' || beat.id === 'base'
      ? !state.clientId
      : beat.id === 'approve'
        ? !state.session?.qa?.passed
        : !state.storyboard.length;
  }

  function setBaseNote(text) {
    const node = $('mcMesaBaseNote');
    if (node && text) node.textContent = text;
  }

  function currentKeyVisual() {
    const scene = state.storyboard.find((item) => item.id === state.sceneId) || state.storyboard[0] || {};
    return state.keyVisuals[state.sceneId] || scene.key_visual || '';
  }

  function showBasePreview({ still, html, key } = {}) {
    const stillNode = $('mcMesaBaseStill');
    const frame = $('mcMesaBaseFrame');
    const keyNode = $('mcMesaBaseKey');
    const voidBox = $('mcMesaBaseVoid');
    const railKey = $('mcMesaRunKey');
    const railImg = $('mcMesaRunKeyImg');
    const hasStill = Boolean(still);
    const hasHtml = Boolean(html);
    const hasKey = Boolean(key);
    if (stillNode) {
      if (hasStill) stillNode.src = still;
      else stillNode.removeAttribute('src');
      stillNode.hidden = !hasStill;
    }
    if (frame) {
      if (hasHtml && !hasStill) frame.srcdoc = html;
      else frame.removeAttribute('srcdoc');
      frame.hidden = !(hasHtml && !hasStill);
    }
    if (keyNode) {
      const showKey = hasKey && !hasStill && !hasHtml;
      if (showKey) keyNode.src = key;
      else keyNode.removeAttribute('src');
      keyNode.hidden = !showKey;
    }
    if (voidBox) voidBox.hidden = hasStill || hasHtml || hasKey;
    if (railKey && railImg) {
      const showRail = hasKey && (hasStill || hasHtml);
      if (showRail) railImg.src = key;
      else railImg.removeAttribute('src');
      railKey.hidden = !showRail;
    }
  }

  function paintRunStill() {
    const versions = sceneVersions(state.sceneId);
    const mockupVersions = (state.session?.mockup?.versions || []).filter((item) => item.png_data_url || item.html);
    const chosen = versions.find((item) => item.attempt === state.versionAttempt)
      || versions.find((item) => item.chosen)
      || versions[versions.length - 1]
      || mockupVersions.find((item) => item.chosen)
      || (state.session?.mockup && {
        png_data_url: state.session.mockup.render_url,
        html: state.session.mockup.html || state.session.base_html,
      });
    showBasePreview({
      still: chosen?.png_data_url || '',
      html: chosen?.html || state.session?.base_html || state.session?.mockup?.html || '',
      key: currentKeyVisual(),
    });
    paintConceptBeats();
    paintRunTakes(versions.length ? versions : mockupVersions, chosen);
  }

  function paintConceptBeats() {
    const list = $('mcMesaRunBeats');
    if (!list) return;
    const hasPreview = Boolean(
      sceneVersions(state.sceneId).length
      || state.session?.mockup?.render_url
      || state.session?.base_html
    );
    list.hidden = hasPreview || !state.storyboard.length;
    list.innerHTML = state.storyboard.map((item, index) => (
      `<li><strong>${index + 1}</strong><span>${item.headline || item.purpose || `Cena ${index + 1}`}</span></li>`
    )).join('');
  }

  function paintRunTakes(versions, chosen) {
    const list = $('mcMesaRunTakes');
    if (!list) return;
    const frames = (versions || []).filter((item) => item.png_data_url);
    list.hidden = !frames.length;
    list.innerHTML = frames.map((item) => {
      const current = chosen && item.attempt === chosen.attempt;
      const label = item.discarded ? `v${item.attempt} fora` : `v${item.attempt}`;
      return `<li>
        <button type="button" data-attempt="${item.attempt}" class="${current ? 'is-current' : ''} ${item.discarded ? 'is-discarded' : ''}">
          <img src="${item.png_data_url}" alt="${label}">
          <em>${label}</em>
        </button>
      </li>`;
    }).join('');
  }

  async function modelBase() {
    if (state.session?.base_html) {
      const ok = await askConfirm({
        title: 'Substituir o HTML da base?',
        body: 'A base atual sai do quadro.',
        confirmLabel: 'Substituir HTML',
      });
      if (!ok) return;
    }
    const run = $('mcMesaBaseRun');
    const dialog = $('mcMesaBaseDialog');
    if (dialog && !dialog.open) openBaseDialog('base');
    try {
      $('mcMesaMockup').disabled = true;
      if (run) run.disabled = true;
      renderOps('base');
      state.runOp = 'base';
      paintRunSeq();
      startRunProgress([
        { id: 'session', label: 'Sessão', status: 'running' },
        { id: 'html', label: 'HTML da marca', status: 'queued' },
        { id: 'layers', label: 'Camadas', status: 'queued' },
        { id: 'still', label: 'Still 16:9', status: 'queued' },
      ], 'Montando a base', 'Sessão → HTML → camadas → still');
      setStatus('Montando o HTML da marca no quadro 16:9.');
      const sessionId = await ensureSession();
      markRunProgress('session', 'done');
      markRunProgress('html', 'running');
      setStatus('Ajustando as camadas. Se o provedor falhar, a placa entra do mesmo jeito.');
      markRunProgress('layers', 'running');
      const data = await fetch(`${API.sessions}/${sessionId}/mockup`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...knobs(),
          spec: state.session?.spec,
          mockup_passes: 3,
        }),
      }).then(readJson);
      applySession(data);
      markRunProgress('html', 'done');
      markRunProgress('layers', 'done');
      markRunProgress('still', 'done');
      const plateOnly = data.mockup?.provider === 'plate';
      setStatus(
        plateOnly
          ? 'Base no quadro. O provedor não refinou; o HTML da marca entrou.'
          : 'Base no quadro. As camadas passaram pelo provedor.'
      );
      $('mcMesaGenerate').disabled = !data.base_html;
      $('mcMesaMockup').disabled = false;
      labelGenerate();
      state.runOp = 'scene';
      paintRunStill();
      paintRunSeq();
      renderOps();
      setModalState('success', {
        title: 'Base pronta',
        text: 'O HTML da marca está no quadro. Siga para a cena.',
      });
    } catch (error) {
      setStatus(error.message);
      $('mcMesaMockup').disabled = !state.storyboard.length;
      renderOps();
      setModalState('error', {
        title: 'Não foi possível modelar a base',
        text: error.message,
        detail: error.stack || error.message,
      });
    } finally {
      setRunBusy(false);
    }
  }

  async function generateScene() {
    if (sceneVersions(state.sceneId).length) {
      const ok = await askConfirm({
        title: 'Substituir esta cena?',
        body: 'Os takes atuais saem do quadro.',
        confirmLabel: 'Substituir cena',
      });
      if (!ok) return;
    }
    const dialog = $('mcMesaBaseDialog');
    if (dialog && !dialog.open) openBaseDialog('scene');
    try {
      if (!state.session?.base_html) {
        await modelBase();
        if (!state.session?.base_html) return;
      }
      $('mcMesaGenerate').disabled = true;
      renderOps('scene');
      state.runOp = 'scene';
      paintRunSeq();
      startRunProgress([
        { id: 'v1', label: `${state.sceneId} v1`, status: 'running' },
        { id: 'v2', label: 'v2', status: 'queued' },
        { id: 'v3', label: 'v3', status: 'queued' },
      ], 'Montando a cena', 'Três takes voltam para o quadro');
      setStatus(`Gerando ${state.sceneId}. Três takes voltam para o quadro.`);
      const sessionId = await ensureSession();
      const data = await fetch(`${API.sessions}/${sessionId}/run`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...knobs(),
          spec: state.session?.spec,
          scenes: state.session?.scenes || [],
          versions: state.session?.versions || [],
          base_html: state.session?.base_html,
          mockup: state.session?.mockup,
          scene_id: state.sceneId,
          renders: 3,
        }),
      }).then(readJson);
      applySession(data);
      $('mcMesaClose').disabled = !data.scenes?.some((item) => item.id === state.sceneId && item.html);
      $('mcMesaGenerate').disabled = !state.clientId;
      labelGenerate();
      state.runOp = 'close';
      paintRunStill();
      paintRunSeq();
      renderOps();
      setModalState('success', {
        title: 'Cena pronta',
        text: 'Compare os takes e feche o still.',
      });
    } catch (error) {
      setStatus(error.message);
      $('mcMesaGenerate').disabled = !state.clientId;
      labelGenerate();
      paintRunSeq();
      renderOps();
      setModalState('error', {
        title: 'Não foi possível montar a cena',
        text: error.message,
        detail: error.stack || error.message,
      });
    } finally {
      setRunBusy(false);
    }
  }

  async function assembleSceneOne() {
    state.sceneId = state.sceneId || 'scene_01';
    if (!state.storyboard.length) {
      await mountConcept();
      if (!state.storyboard.length) return;
    }
    if (!state.session?.base_html) {
      await modelBase();
      if (!state.session?.base_html) return;
    }
    if (state.sceneId === 'scene_01' || !state.session?.scenes?.some((item) => item.id === state.sceneId && item.html)) {
      state.sceneId = state.sceneId || 'scene_01';
    }
    await generateScene();
  }

  function toggleSkill(id) {
    if (state.selectedSkills.includes(id)) {
      state.selectedSkills = state.selectedSkills.filter((item) => item !== id);
    } else {
      state.selectedSkills.push(id);
    }
    renderSkills();
    const on = state.selectedSkills.length
      ? state.selectedSkills.join(', ')
      : 'nenhuma overlay — só a base HTML';
    setStatus(`Skills da campanha: ${on}.`);
  }

  function renderSkills() {
    const locked = $('mcMesaBaseSkills');
    if (locked) {
      locked.innerHTML = state.baseSkills.map((item) => (
        `<button type="button" disabled class="is-current">${item.label || item.id}</button>`
      )).join('');
    }
    const root = $('mcMesaSkills');
    if (!root) return;
    root.innerHTML = state.visualSkills.map((item) => {
      const current = state.selectedSkills.includes(item.id);
      return `<button type="button" data-skill="${item.id}" class="${current ? 'is-current' : ''}" title="${item.note || ''}">${item.label}</button>`;
    }).join('');
  }

  function labelGenerate() {
    const node = $('mcMesaGenerate');
    if (!node) return;
    const hasFirst = state.session?.scenes?.some((item) => item.id === 'scene_01' && item.html);
    node.textContent = hasFirst ? 'Gerar esta cena' : 'Montar cena 1';
  }

  async function closeScene() {
    const dialog = $('mcMesaBaseDialog');
    if (dialog && !dialog.open) openBaseDialog('close');
    try {
      $('mcMesaClose').disabled = true;
      renderOps('close');
      state.runOp = 'close';
      setRunBusy(true);
      paintRunSeq();
      setStatus('Fechando o still 1920×1080 com margem segura.');
      const sessionId = await ensureSession();
      const data = await fetch(`${API.sessions}/${sessionId}/close`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene_id: state.sceneId }),
      }).then(readJson);
      applySession(data);
      if (data.closed?.png_data_url) {
        $('mcMesaPreview').hidden = false;
        $('mcMesaDrop').hidden = true;
        $('mcMesaFrame').src = data.closed.png_data_url;
      }
      const report = data.closed?.guidelines || {};
      setStatus(
        report.passed
          ? 'Still fechado no 1920×1080. O quadro está pronto para a Bancada.'
          : (report.defects || []).join(' ') || 'Still fechado. Revise a margem.'
      );
      if (report.passed) {
        setModalState('success', {
          title: 'Still fechado',
          text: 'O quadro está pronto para a Bancada.',
        });
      } else {
        setModalState('warning', {
          title: 'Revise antes de seguir',
          text: (report.defects || []).join(' ') || 'Ajuste a margem e feche de novo.',
        });
      }
      state.runOp = 'approve';
      paintRunStill();
      paintRunSeq();
      renderOps();
    } catch (error) {
      setStatus(error.message);
      $('mcMesaClose').disabled = false;
      paintRunSeq();
      renderOps();
      setModalState('error', {
        title: 'Não foi possível fechar a cena',
        text: error.message,
        detail: error.stack || error.message,
      });
    } finally {
      setRunBusy(false);
    }
  }

  function applySession(data) {
    state.session = data;
    state.sessionId = data.id;
    if (data.storyboard?.length) state.storyboard = data.storyboard;
    else if (data.scenes?.length) {
      state.storyboard = data.scenes.map((item, index) => ({
        id: item.id,
        position: index + 1,
        headline: item.headline,
        purpose: item.purpose,
      }));
    }
    if (data.cost) state.quote = data.cost;
    $('mcMesaGenerate').disabled = !data.base_html && !state.storyboard.length;
    $('mcMesaMockup').disabled = !state.storyboard.length;
    $('mcMesaAnalyze').disabled = false;
    $('mcMesaApprove').disabled = !data.qa?.passed;
    if ($('mcMesaClose')) {
      $('mcMesaClose').disabled = !(data.scenes || []).some((item) => item.id === state.sceneId && (item.html || item.stack));
    }
    renderStrip();
    renderTrace(data.trace?.steps || data.passes || []);
    renderOps();
    renderLayers();
    renderCost();
    const defects = $('mcMesaDefects');
    const notes = data.qa?.defects || [];
    if (defects) {
      defects.hidden = !notes.length;
      defects.innerHTML = notes.map((item) => `<li>${item}</li>`).join('');
    }
    renderEdit();
    renderKeys();
    labelGenerate();
    const versions = sceneVersions(state.sceneId);
    const discarded = versions.filter((item) => item.discarded).length;
    const hasScene = (data.scenes || []).some((item) => item.html);
    if (hasScene) {
      setStatus(
        data.qa?.passed
          ? `QA passou nesta cena. ${discarded ? `${discarded} take(s) ficaram de fora.` : ''}`.trim()
          : 'Cena no quadro. Compare os takes ou ajuste a linha.'
      );
    }
    showScene();
    paintRunStill();
    paintRunSeq();
    if (data.id && (data.storyboard?.length || data.base_html)) {
      renderHistory([{
        session_id: data.id,
        id: data.id,
        stage: data.base_html ? 'base' : 'concept',
        headline: (data.storyboard || state.storyboard || [])[0]?.headline || '',
        format: data.format || state.formatKey,
      }]);
    }
  }

  function sceneVersions(sceneId) {
    return (state.session?.versions || []).filter((item) => item.scene_id === sceneId);
  }

  function showScene() {
    const preview = $('mcMesaPreview');
    const drop = $('mcMesaDrop');
    const scene = (state.session?.scenes || []).find((item) => item.id === state.sceneId)
      || (state.session?.scenes || [])[0];
    const versions = sceneVersions(state.sceneId);
    const chosen = versions.find((item) => item.attempt === state.versionAttempt)
      || versions.find((item) => item.chosen)
      || versions[versions.length - 1];
    const render = chosen
      || (state.session?.renders || []).find((item) => item.scene_id === (scene && scene.id))
      || (state.session?.mockup && { png_data_url: state.session.mockup.render_url });
    const card = state.storyboard.find((item) => item.id === state.sceneId);
    $('mcMesaCaption').textContent = scene?.headline || card?.headline || (state.session?.mockup ? 'Base da marca' : '');
    renderVersions(versions.length ? versions : (state.session?.mockup?.versions || []), chosen);
    if (!render?.png_data_url) return;
    drop.hidden = true;
    preview.hidden = false;
    $('mcMesaFrame').src = render.png_data_url;
    fitStage();
  }

  function renderVersions(versions, chosen) {
    const list = $('mcMesaVersions');
    if (!list) return;
    list.hidden = !versions.length;
    list.innerHTML = versions.map((item) => {
      const current = chosen && item.attempt === chosen.attempt;
      const label = item.discarded ? `v${item.attempt} descartada` : `v${item.attempt}`;
      return `<li>
        <button type="button" data-attempt="${item.attempt}" class="${current ? 'is-current' : ''} ${item.discarded ? 'is-discarded' : ''}">
          <img src="${item.png_data_url}" alt="${label}">
          <em>${label}</em>
        </button>
      </li>`;
    }).join('');
  }

  function fitStage() {
    const frame = $('mcMesaFrameWrap');
    if (!frame) return;
    frame.style.width = '';
    frame.style.height = '';
    frame.style.transform = '';
    state.zoom = 1;
  }

  function revealStrip() {
    const strip = $('mcMesaStrip');
    if (!strip) return;
    strip.classList.add('is-live');
  }

  async function patchLayer(layerId) {
    if (!layerId || !state.sessionId) return;
    const scene = (state.session?.scenes || []).find((item) => item.id === state.sceneId);
    if (!scene) return;
    try {
      const data = await fetch(`${API.sessions}/${state.sessionId}/patch`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_id: state.sceneId,
          patches: [{ layer_id: layerId.replace(/^scene_0\d-/, ''), text: scene.headline }],
        }),
      }).then(readJson);
      applySession(data);
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function handoff(event) {
    event?.preventDefault();
    const dialog = $('mcMesaBaseDialog');
    if (dialog && !dialog.open) openBaseDialog('approve');
    try {
      setRunBusy(true);
      setStatus('Mandando o 15s para a Bancada.');
      const data = await fetch(`${API.sessions}/${state.sessionId}/handoff`, {
        method: 'POST',
        credentials: 'same-origin',
      }).then(readJson);
      window.location.href = `/parametros/modelagem-criativos/bancada?campaign=${encodeURIComponent(data.campaign_id || '')}`;
    } catch (error) {
      setStatus(error.message);
      setModalState('error', {
        title: 'Não foi possível aprovar',
        text: error.message,
        detail: error.stack || error.message,
      });
    } finally {
      setRunBusy(false);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
