(function () {
  const API = {
    swap: '/parametros/api/format-lab/swap',
    read: '/parametros/api/format-lab/swap/read',
    prompt: '/parametros/api/format-lab/swap/prompt',
    history: '/parametros/api/format-lab/swap/history',
    quote: '/parametros/api/format-lab/quote',
    clients: '/parametros/api/clients',
    viewers: '/parametros/api/viewer-profiles',
    formats: '/parametros/api/formats',
  };
  const OUTPUTS = [
    { ratio: '16:9', family: 'h', value: 16 / 9 },
    { ratio: '9:16', family: 'v', value: 9 / 16 },
    { ratio: '4:5', family: 'v', value: 4 / 5 },
    { ratio: '1:1', family: 's', value: 1 },
  ];
  const ROLE_LABEL = {
    logo: 'Logo',
    headline: 'Headline',
    support: 'Apoio',
    cta: 'CTA',
    product: 'Produto',
    price: 'Preço',
    person: 'Pessoa',
    background: 'Fundo',
    graphic: 'Grafismo',
  };
  const FLOW = ['upload', 'ocr', 'analysis', 'edit', 'generate', 'review'];
  const ORIGIN_LABEL = {
    original: 'Original',
    edited: 'Editado',
    draft: 'Rascunho',
    production: 'Produção',
    typeset: 'Tipo na foto',
    recrop: 'Recorte + tipo',
  };

  const Desk = window.McDeskBrand || {
    read() { return ''; },
    write() {},
    branded(list) { return Array.isArray(list) ? list : []; },
    forSelect(list) { return Array.isArray(list) ? list : []; },
    pick(_list, fallback) { return String(fallback || ''); },
    label(client) { return client?.name || ''; },
    hasInfo() { return true; },
  };

  const state = {
    versions: [],
    activeId: '',
    baseId: '',
    viewMode: 'view',
    compareIds: ['', ''],
    flow: 'upload',
    flowError: '',
    clientId: '',
    clients: [],
    allClients: [],
    aspectRatio: '16:9',
    userPickedFormat: false,
    forcedFormat: false,
    pendingForce: '',
    runId: '',
    runs: [],
    viewerProfiles: [],
    formats: [],
    viewerSlug: '',
    viewerPicked: false,
    presentation: 'final',
    quality: 'draft',
    brandContext: false,
    promptEdited: false,
    promptLocked: false,
    lastRead: null,
    mode: 'image',
    optimizedPrompt: '',
    optimizedPreview: '',
    zoom: 1,
    lastAction: '',
    replaceSession: false,
    cache: {},
    planHash: '',
    planSeq: 0,
    planBlocked: false,
    planNoop: false,
    conflicts: [],
    region: null,
    picking: false,
    pickStart: null,
    revision: 0,
    csrf: '',
  };

  let readAbort = null;
  let promptAbort = null;
  let promptTimer = 0;
  let persistTimer = 0;
  let persistBusy = false;
  let persistAgain = false;
  let waitTimer = 0;
  let waitStarted = 0;

  document.addEventListener('DOMContentLoaded', boot);

  function $(id) {
    return document.getElementById(id);
  }

  async function boot() {
    state.csrf = $('mcSwap')?.dataset?.csrf || '';
    bind();
    applyRatio(state.aspectRatio);
    applyPresentation();
    renderFlow();
    renderVersions();
    highlightQuality();
    renderEditPanels();
    try {
      const clients = await request(API.clients);
      state.allClients = Array.isArray(clients) ? clients : (clients?.items || clients?.clients || []);
      applyDeskBrand();
    } catch (_error) {
      setStatus('Não deu para carregar as marcas. Você ainda pode escrever o nome no pedido.');
    }
    await Promise.all([loadHistory(), loadViewerCatalog()]);
    await consumeHandoff();
    refreshQuote();
  }

  function bind() {
    const drop = $('mcSwapDrop');
    const input = $('mcSwapFile');
    drop?.addEventListener('click', () => input?.click());
    drop?.addEventListener('dragover', (event) => {
      event.preventDefault();
      drop.classList.add('is-dragging');
    });
    drop?.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
    drop?.addEventListener('drop', (event) => {
      event.preventDefault();
      drop.classList.remove('is-dragging');
      takeFile(event.dataTransfer?.files?.[0]);
    });
    input?.addEventListener('change', () => takeFile(input.files?.[0]));
    $('mcSwapClient')?.addEventListener('change', async (event) => {
      await persistHistory();
      selectBrand(event.target.value);
      state.runId = '';
      const restored = await loadHistory();
      if (!restored && state.versions.length) schedulePersist();
      refreshPrompt();
    });
    document.querySelectorAll('input[name="mcSwapOut"]').forEach((node) => {
      node.addEventListener('change', () => {
        if (!node.checked) return;
        onFormatPick(node.value);
      });
    });
    document.querySelectorAll('input[name="mcTrocrPresent"]').forEach((node) => {
      node.addEventListener('change', () => {
        if (!node.checked) return;
        state.presentation = node.value;
        state.viewerPicked = false;
        applyPresentation();
      });
    });
    document.querySelectorAll('input[name="mcTrocrQuality"]').forEach((node) => {
      node.addEventListener('change', () => {
        if (!node.checked) return;
        state.quality = node.value;
        highlightQuality();
        refreshQuote();
        refreshPrompt();
      });
    });
    $('mcTrocrBrandContext')?.addEventListener('change', (event) => {
      state.brandContext = event.target.checked;
      syncBrandOption();
      refreshPrompt();
    });
    ['mcSwapHeadline', 'mcSwapSupport', 'mcTrocrSubtitle', 'mcTrocrDates', 'mcTrocrVenue', 'mcTrocrPrice', 'mcSwapCta', 'mcTrocrCta2', 'mcTrocrLogo', 'mcTrocrDisclaimer', 'mcSwapNote'].forEach((id) => {
      $(id)?.addEventListener('input', () => {
        if (id === 'mcSwapNote') updateNoteCount();
        if (state.versions.length) setFlow('edit');
        refreshPrompt();
      });
    });
    document.querySelectorAll('input[name="mcTrocrPreserve"], input[name="mcTrocrAlter"]').forEach((node) => {
      node.addEventListener('change', refreshPrompt);
    });
    document.querySelectorAll('input[name="mcTrocrAnalysis"]').forEach((node) => {
      node.addEventListener('change', renderEditPanels);
    });
    $('mcSwapRun')?.addEventListener('click', () => {
      const quality = (state.mode === 'typeset' || state.mode === 'recrop') ? 'production' : state.quality;
      runSwap(quality);
    });
    $('mcTrocrDraft')?.addEventListener('click', () => runSwap('draft'));
    $('mcTrocrHistoryBtn')?.addEventListener('click', openHistory);
    $('mcTrocrOpenHistory')?.addEventListener('click', openHistory);
    $('mcTrocrHistoryClose')?.addEventListener('click', closeHistory);
    $('mcTrocrHistory')?.addEventListener('click', (event) => {
      if (event.target === event.currentTarget) closeHistory();
    });
    $('mcSwapImage')?.addEventListener('click', (event) => {
      if (!canMarkOnImage() || state.picking) return;
      event.preventDefault();
      togglePickRegion();
    });
    $('mcTrocrForceImage')?.addEventListener('change', () => {
      refreshPrompt();
      refreshQuote();
    });
    $('mcTrocrConfirmConflicts')?.addEventListener('change', () => {
      refreshPrompt();
      enableGenerate(canGenerate());
    });
    $('mcTrocrViewBtn')?.addEventListener('click', () => setViewMode('view'));
    $('mcTrocrCompareBtn')?.addEventListener('click', () => setViewMode('compare'));
    $('mcTrocrZoomIn')?.addEventListener('click', () => setZoom(state.zoom + 0.1));
    $('mcTrocrZoomOut')?.addEventListener('click', () => setZoom(state.zoom - 0.1));
    $('mcTrocrZoomFit')?.addEventListener('click', () => setZoom(1));
    window.addEventListener('resize', () => fitCreative());
    $('mcTrocrPickRegion')?.addEventListener('click', togglePickRegion);
    const region = $('mcTrocrRegion');
    region?.addEventListener('pointerdown', onRegionDown);
    region?.addEventListener('pointermove', onRegionMove);
    region?.addEventListener('pointerup', onRegionUp);
    region?.addEventListener('pointercancel', onRegionUp);
    $('mcTrocrDownload')?.addEventListener('click', downloadActive);
    $('mcTrocrFullscreen')?.addEventListener('click', toggleFullscreen);
    $('mcTrocrUsePrompt')?.addEventListener('click', () => {
      state.promptLocked = true;
      toast('Prompt otimizado será usado na próxima geração.', 'success');
    });
    $('mcTrocrEditPrompt')?.addEventListener('click', () => {
      const box = $('mcTrocrPrompt');
      if (!box) return;
      box.readOnly = false;
      box.focus();
      state.promptEdited = true;
    });
    $('mcTrocrPrompt')?.addEventListener('input', () => {
      state.promptEdited = true;
      state.optimizedPreview = $('mcTrocrPrompt').value;
    });
    $('mcTrocrNewEdit')?.addEventListener('click', () => {
      const current = currentVersion();
      if (current) useAsBase(current.id);
    });
    $('mcTrocrRetry')?.addEventListener('click', retryLast);
    $('mcTrocrEditInputs')?.addEventListener('click', () => {
      hideError();
      setFlow('edit');
      $('mcSwapNote')?.focus();
    });
    $('mcTrocrBackVersion')?.addEventListener('click', () => {
      hideError();
      const previous = state.versions[state.versions.length - 2] || state.versions[0];
      if (previous) selectVersion(previous.id);
    });
    $('mcTrocrResetPanel')?.addEventListener('click', resetPanel);
    $('mcTrocrNewPiece')?.addEventListener('click', onNewPiece);
    $('mcTrocrRotate')?.addEventListener('click', rotateLayout);
    $('mcTrocrVersions')?.addEventListener('click', onVersionClick);
    $('mcTrocrHistoryList')?.addEventListener('click', onVersionClick);
    $('mcTrocrRunList')?.addEventListener('click', onRunClick);
    $('mcTrocrReelSessions')?.addEventListener('click', onRunClick);
    $('mcTrocrViewerPicks')?.addEventListener('click', onViewerPick);
    $('mcTrocrReelToggle')?.addEventListener('click', () => {
      setReelCollapsed(!$('mcTrocrReel')?.classList.contains('is-collapsed'));
    });
    setReelCollapsed(window.localStorage.getItem('cx-trocr-reel') === '1');
  }

  function currentClient() {
    return state.clients.find((item) => String(item.id) === String(state.clientId))
      || state.allClients.find((item) => String(item.profile_id || item.id) === String(state.clientId))
      || null;
  }

  function applyDeskBrand() {
    state.clients = Desk.forSelect(state.allClients, state.clientId);
    if (!state.clientId) state.clientId = Desk.pick(state.allClients, state.clientId);
    if (state.clientId) Desk.write(state.clientId);
    renderClients();
  }

  function selectBrand(id) {
    state.clientId = String(id || '');
    if (state.clientId) Desk.write(state.clientId);
    renderClients();
  }

  function brandHasDna(client) {
    return Boolean(client && Desk.hasInfo(client));
  }

  function syncBrandOption() {
    const row = $('mcTrocrBrandRow');
    const box = $('mcTrocrBrandContext');
    const ready = brandHasDna(currentClient());
    if (!ready) state.brandContext = false;
    if (row) row.hidden = !ready;
    if (box) box.checked = Boolean(ready && state.brandContext);
    renderBrandHint();
  }

  function renderBrandHint() {
    const hint = $('mcTrocrBrandHint');
    if (!hint) return;
    const client = currentClient();
    if (!state.clients.length) {
      hint.textContent = 'Nenhuma marca com perfil. O pedido segue só com a foto.';
      return;
    }
    if (!client) {
      hint.textContent = 'Escolha a marca da Mesa. O histórico fica nesta sessão.';
      return;
    }
    if (!brandHasDna(client)) {
      hint.textContent = 'Sem perfil desta marca. O pedido segue só com a foto.';
      return;
    }
    hint.textContent = state.brandContext
      ? `${client.name} da Mesa. DNA entra nesta versão.`
      : `${client.name} da Mesa. DNA só entra se você ligar abaixo.`;
  }

  function renderClients() {
    const select = $('mcSwapClient');
    if (!select) return;
    if (!state.clients.length) {
      select.innerHTML = '<option value="">Nenhuma marca com perfil</option>';
      syncBrandOption();
      return;
    }
    select.innerHTML = state.clients.map((item) => (
      `<option value="${escapeHtml(String(item.id))}">${escapeHtml(Desk.label(item))}</option>`
    )).join('');
    if (state.clientId && Array.from(select.options).some((option) => option.value === String(state.clientId))) {
      select.value = String(state.clientId);
    } else if (select.options.length) {
      state.clientId = select.value;
      Desk.write(state.clientId);
    }
    syncBrandOption();
  }

  function takeFile(file) {
    if (!file || !file.type.startsWith('image/')) {
      setStatus('Solte uma imagem. PNG ou JPG.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => ingestStill(String(reader.result || ''));
    reader.readAsDataURL(file);
  }

  function isAllowedStill(value) {
    const text = String(value || '').trim();
    if (text.startsWith('data:image/')) return true;
    try {
      const url = new URL(text, window.location.origin);
      if (url.origin !== window.location.origin) return false;
      return url.pathname.startsWith('/static/')
        || url.pathname.includes('/swap/still/');
    } catch (_error) {
      return false;
    }
  }

  async function materializeStill(value) {
    const text = String(value || '').trim();
    if (text.startsWith('data:image/')) return text;
    const response = await fetch(text, { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Não deu para ler o still do Studio.');
    const blob = await response.blob();
    if (!String(blob.type || '').startsWith('image/')) {
      throw new Error('O still do Studio não é uma imagem.');
    }
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Não deu para ler o still do Studio.'));
      reader.readAsDataURL(blob);
    });
  }

  function applyStudioCopy(copy) {
    if (!copy) return;
    [
      ['mcSwapHeadline', copy.headline],
      ['mcSwapSupport', copy.support],
      ['mcSwapCta', copy.cta],
    ].forEach(([id, value]) => {
      if (value && $(id) && !$(id).value) $(id).value = value;
    });
    refreshPrompt();
  }

  function applyHandoffChrome(options) {
    if (options?.aspect) {
      state.userPickedFormat = true;
      selectFormat(options.aspect);
    }
    if (options?.presentation) {
      state.presentation = options.presentation;
      state.viewerPicked = false;
      const radio = document.querySelector(`input[name="mcTrocrPresent"][value="${options.presentation}"]`);
      if (radio) radio.checked = true;
      applyPresentation();
    }
  }

  async function ingestStill(raw, options) {
    let image = '';
    try {
      if (!isAllowedStill(raw)) throw new Error('O still do Studio não pôde ser aberto.');
      image = await materializeStill(raw);
    } catch (error) {
      setStatus(error.message || 'O still do Studio não pôde ser aberto.');
      return false;
    }
    if (!image) {
      setStatus('O still do Studio não pôde ser aberto.');
      return false;
    }
    if (!options?.skipReset) {
      if (state.versions.length) {
        await persistHistory();
        await startNewRun();
      } else {
        await startFresh({ persistEmpty: false });
      }
    }
    const thumb = await makeThumb(image);
    const version = pushVersion({
      name: options?.name || 'Original',
      origin: 'original',
      image,
      thumb,
    }, { persist: false });
    showPreview(image);
    applyHandoffChrome(options);
    if (!state.userPickedFormat && !options?.aspect) {
      const guessed = await guessAspect(image);
      if (guessed) {
        selectFormat(guessed);
        setFormatHint(`Saída ${guessed}, a mais próxima da peça. Depois você pode forçar outra.`);
      }
    } else if (options?.aspect) {
      setFormatHint(`Saída ${options.aspect}, vinda do Studio. Depois você pode forçar outra.`);
    }
    setStatus(options?.from === 'studio'
      ? 'Still do Studio. O OCR roda automaticamente.'
      : 'Ao enviar uma nova imagem, o OCR é executado automaticamente.');
    await readReference(version, { force: true, reference: image });
    applyHandoffChrome(options);
    applyStudioCopy(options?.copy);
    schedulePersist();
    return true;
  }

  async function consumeHandoff() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('from') !== 'studio') return false;
    let payload = null;
    try {
      payload = JSON.parse(sessionStorage.getItem('cx-trocr-handoff') || '');
    } catch (_error) {
      payload = null;
    }
    if (!payload?.still || payload.from !== 'studio') {
      sessionStorage.removeItem('cx-trocr-handoff');
      if (window.history.replaceState) {
        window.history.replaceState({}, '', window.location.pathname);
      }
      setStatus('O Studio não enviou um still. Solte uma imagem para começar.');
      return false;
    }
    if (payload.clientId) {
      selectBrand(payload.clientId);
      await loadHistory();
    }
    if (state.versions.length) await persistHistory();
    await startNewRun();
    const loaded = await ingestStill(payload.still, {
      from: 'studio',
      skipReset: true,
      name: payload.title || 'Studio',
      aspect: payload.aspect || '16:9',
      presentation: payload.presentation || 'ctv',
      copy: {
        headline: payload.headline || '',
        support: payload.support || '',
        cta: payload.cta || '',
      },
    });
    if (!loaded) return false;
    sessionStorage.removeItem('cx-trocr-handoff');
    if (window.history.replaceState) {
      window.history.replaceState({}, '', window.location.pathname);
    }
    return true;
  }

  function pushVersion(partial, options) {
    const attempt = state.versions.length + 1;
    const version = {
      id: `v${attempt}`,
      attempt,
      name: partial.name || `v${attempt}`,
      origin: partial.origin || 'edited',
      quality: partial.quality || '',
      status: 'ready',
      createdAt: new Date(),
      image: partial.image || '',
      thumb: partial.thumb || '',
      ocr: partial.ocr || null,
      analysis: partial.analysis || null,
      qa: partial.qa || null,
      plan_hash: partial.plan_hash || '',
      parent_id: partial.parent_id || (partial.origin === 'original' ? '' : (state.baseId || '')),
    };
    state.versions.push(version);
    state.activeId = version.id;
    if (!state.baseId || partial.asBase !== false) state.baseId = version.id;
    enableGenerate(canGenerate());
    renderVersions();
    renderBaseMeta();
    renderEditPanels();
    if (options?.persist !== false) schedulePersist();
    return version;
  }

  async function readReference(version, options) {
    const force = Boolean(options?.force);
    const source = options?.reference || version?.image;
    if (!source) return;
    if (!force && state.cache[version.id]) {
      applyRead(state.cache[version.id], version, { cached: true });
      return;
    }
    if (readAbort) readAbort.abort();
    readAbort = new AbortController();
    setFlow('ocr');
    setStatus('OCR processando…');
    hideError();
    try {
      const reference = await downscaleImage(source, 1280, 0.82, { forceJpeg: true });
      const data = await request(API.read, { reference }, { signal: readAbort.signal });
      state.cache[version.id] = data;
      version.ocr = data;
      version.analysis = data.analysis || null;
      applyRead(data, version, { cached: false });
      if (data.status === 'completed' || data.status === 'partial') {
        toast(data.status === 'partial' ? 'OCR parcial. Confira os textos.' : 'OCR atualizado', 'success');
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      setFlow('ocr', 'error');
      showError('Falha ao executar OCR', error.message || 'Não deu para ler os textos.', 'ocr');
      setStatus('Não deu para ler os textos. Você ainda pode escrever na mão.');
    }
  }

  function applyRead(data, version, meta) {
    state.lastRead = data || null;
    fillFields(data);
    applyAnalysis(data.analysis || {}, data.elements || []);
    renderLocks(data);
    paintOcrStatus(data);
    if (data.aspect_hint && !state.userPickedFormat) selectFormat(data.aspect_hint);
    renderEditPanels();
    const failed = ['unavailable', 'provider_error', 'invalid', 'unreadable'].includes(data.status);
    if (failed) {
      setFlow('ocr', 'error');
      showError('Falha ao executar OCR', data.error || 'Não deu para ler os textos. Escreva na mão.', 'ocr');
    } else {
      setFlow(meta?.cached ? 'edit' : 'analysis');
      window.setTimeout(() => {
        if (state.flow === 'analysis') setFlow('edit');
      }, 280);
    }
    setStatus(ocrStatusCopy(data, meta));
    refreshPrompt();
    renderBaseMeta();
    schedulePersist();
  }

  function ocrStatusCopy(data, meta) {
    if (data.status === 'unavailable' || data.status === 'provider_error') {
      return data.error || 'OCR indisponível. Escreva os textos na mão.';
    }
    if (data.status === 'invalid' || data.status === 'unreadable') {
      return data.error || 'A leitura não veio. Escreva os textos na mão.';
    }
    if (data.status === 'partial') {
      return 'Leitura parcial. Confira os campos antes de gerar.';
    }
    if (meta?.cached) {
      return 'Elementos da base ativa. Edite o texto e gere uma nova versão.';
    }
    return 'A leitura preencheu. Confira o pedido à direita.';
  }

  function paintOcrStatus(data) {
    const banner = $('mcTrocrOcrBanner');
    if (!banner) return;
    const status = data?.status || '';
    const failed = ['unavailable', 'provider_error', 'invalid', 'unreadable', 'partial'].includes(status);
    banner.hidden = !failed;
    banner.dataset.status = status;
    banner.textContent = data?.error || (
      status === 'partial'
        ? 'Leitura parcial. Confira os campos.'
        : 'Não deu para ler os textos. Escreva na mão.'
    );
    const hint = $('mcTrocrOcrHint');
    if (hint && failed) {
      hint.textContent = status === 'partial' ? 'Leitura parcial.' : 'OCR sem leitura. Escreva na mão.';
    }
  }

  function fillFields(data) {
    const headline = $('mcSwapHeadline');
    const support = $('mcSwapSupport');
    const subtitle = $('mcTrocrSubtitle');
    const dates = $('mcTrocrDates');
    const venue = $('mcTrocrVenue');
    const price = $('mcTrocrPrice');
    const cta = $('mcSwapCta');
    const cta2 = $('mcTrocrCta2');
    const logo = $('mcTrocrLogo');
    const disclaimer = $('mcTrocrDisclaimer');
    const ctas = (data.elements || []).filter((item) => item.role === 'cta' && item.text);
    if (headline) headline.value = data.headline || '';
    if (support) support.value = data.support || '';
    if (subtitle) subtitle.value = data.subtitle || '';
    if (dates) dates.value = data.dates || '';
    if (venue) venue.value = data.venue || '';
    if (price) price.value = data.price || '';
    if (cta) cta.value = data.cta || ctas[0]?.text || '';
    if (cta2) cta2.value = ctas[1]?.text || '';
    if ($('mcTrocrCta2Field')) $('mcTrocrCta2Field').hidden = !ctas[1] && !cta2?.value;
    if (logo) logo.value = data.logo_text || '';
    if (disclaimer) disclaimer.value = data.disclaimer || '';
  }

  function applyAnalysis(analysis, elements) {
    const flags = { ...(analysis || {}) };
    elements.forEach((item) => {
      const role = item.role;
      if (role === 'background') flags.background = true;
      if (role === 'person' || role === 'product') flags.images = true;
      if (role === 'logo') flags.logo = true;
      if (role === 'headline') flags.headline = true;
      if (role === 'support') flags.secondary = true;
      if (role === 'cta') flags.cta = true;
      if (role === 'price') flags.supports = true;
      if (role === 'graphic') flags.graphic = true;
    });
    document.querySelectorAll('input[name="mcTrocrAnalysis"]').forEach((node) => {
      node.checked = Boolean(flags[node.value]);
    });
    const preserveMap = {
      background: 'background',
      images: 'people',
      logo: 'logo',
      graphic: 'graphic',
    };
    document.querySelectorAll('input[name="mcTrocrPreserve"]').forEach((node) => {
      if (node.value === 'layout' || node.value === 'style') return;
      const key = Object.keys(preserveMap).find((item) => preserveMap[item] === node.value);
      if (key && flags[key]) node.checked = true;
    });
  }

  function renderLocks(read) {
    const data = read || {};
    const list = $('mcSwapElements');
    const box = $('mcTrocrLocks');
    const locks = [];
    (data.elements || []).forEach((item) => {
      if (item.role === 'person' && item.text) locks.push(item.text);
    });
    if (data.dates) locks.push(data.dates);
    if (data.venue) locks.push(data.venue);
    if (data.logo_text) locks.push(data.logo_text);
    if (data.disclaimer) locks.push(data.disclaimer);
    if (list) {
      list.innerHTML = locks.map((text) => `<li>${escapeHtml(text)}</li>`).join('');
      if (data.style) list.innerHTML += `<li class="is-style">${escapeHtml(data.style)}</li>`;
    }
    if (box) box.hidden = locks.length === 0;
  }

  function selectFormat(ratio) {
    const input = document.querySelector(`input[name="mcSwapOut"][value="${ratio}"]`);
    if (!input) return;
    input.checked = true;
    state.aspectRatio = ratio;
    state.viewerPicked = false;
    applyRatio(ratio);
    applyPresentation();
  }

  function familyOf(ratio) {
    return (OUTPUTS.find((item) => item.ratio === ratio) || {}).family || '';
  }

  function nearestOutput(ratioValue, family) {
    const pool = family ? OUTPUTS.filter((item) => item.family === family) : OUTPUTS;
    return (pool.length ? pool : OUTPUTS).reduce((best, item) => (
      Math.abs(ratioValue - item.value) < Math.abs(ratioValue - best.value) ? item : best
    )).ratio;
  }

  function sourceRatioValue() {
    const hint = state.lastRead?.aspect_hint;
    if (hint && hint.includes(':')) {
      const [width, height] = hint.split(':').map(Number);
      if (width && height) return width / height;
    }
    const image = $('mcSwapImage');
    if (image?.naturalWidth && image.naturalHeight) {
      return image.naturalWidth / image.naturalHeight;
    }
    return null;
  }

  function setFormatHint(text) {
    if ($('mcTrocrFormatHint')) $('mcTrocrFormatHint').textContent = text;
  }

  function onFormatPick(clicked) {
    const source = sourceRatioValue();
    const nearest = source != null ? nearestOutput(source) : clicked;
    state.userPickedFormat = true;
    state.forcedFormat = clicked !== nearest;
    state.pendingForce = '';
    selectFormat(clicked);
    setFormatHint(state.forcedFormat
      ? `Saída forçada: ${clicked}. A mais próxima da peça é ${nearest}.`
      : `Saída ${clicked}, a mais próxima da peça.`);
    refreshPrompt();
  }

  function rotateLayout() {
    const next = ({
      '16:9': '9:16',
      '9:16': '16:9',
      '4:5': '16:9',
      '1:1': '9:16',
    })[state.aspectRatio] || '9:16';
    const source = sourceRatioValue();
    const nearest = source != null ? nearestOutput(next === '16:9' ? 16 / 9 : 9 / 16, familyOf(next)) : next;
    state.userPickedFormat = true;
    state.forcedFormat = false;
    state.pendingForce = '';
    selectFormat(nearest);
    setFormatHint(`Rotação para ${nearest}. Clique em outro formato para forçar.`);
    refreshPrompt();
    setStatus(`Layout da peça em ${nearest}.`);
  }

  function guessAspect(src) {
    return new Promise((resolve) => {
      const image = new Image();
      image.onload = () => {
        const ratio = image.width / image.height;
        if (Math.abs(ratio - 1) < 0.08) resolve('1:1');
        else if (ratio < 0.72) resolve('9:16');
        else if (ratio < 0.92) resolve('4:5');
        else resolve('16:9');
      };
      image.onerror = () => resolve('');
      image.src = src;
    });
  }

  function applyRatio(ratio) {
    const [width, height] = String(ratio || '16:9').split(':').map(Number);
    const stage = $('mcTrocrViewport') || $('mcSwapStage');
    if (!stage || !width || !height) return;
    stage.style.setProperty('--mc-swap-ratio', `${width} / ${height}`);
    stage.classList.toggle('is-vertical', height > width);
    fitCreative();
  }

  function placeCreative(host) {
    const image = $('mcSwapImage');
    const region = $('mcTrocrRegion');
    if (!host || !image) return;
    if (image.parentElement !== host) host.appendChild(image);
    if (region && region.parentElement !== host) host.appendChild(region);
  }

  function applyPresentation() {
    const frame = document.querySelector('.mc-trocr-frame');
    const device = $('mcTrocrDevice');
    const shell = $('mcTrocrViewerShell');
    const picks = $('mcTrocrViewerPicks');
    const image = $('mcSwapImage');
    if (frame) frame.dataset.mockup = state.presentation;
    $('mcTrocrViewport')?.setAttribute('data-presentation', state.presentation);
    const mockup = state.presentation !== 'final';
    if (picks) picks.hidden = !mockup;
    if (!mockup || !device || !shell || !window.McViewerShell) {
      if (device) device.hidden = true;
      if (frame) frame.hidden = false;
      placeCreative(frame);
      return;
    }
    const profiles = window.McViewerShell.profilesFor(state.viewerProfiles, state.presentation);
    state.viewerSlug = preferredViewerSlug(profiles);
    const profile = profiles.find((item) => item.slug === state.viewerSlug) || profiles[0];
    if (!profile) {
      device.hidden = true;
      if (frame) frame.hidden = false;
      return;
    }
    device.hidden = false;
    if (frame) frame.hidden = true;
    window.McViewerShell.applyPalette(device, profile);
    device.classList.add('is-paused');
    shell.innerHTML = window.McViewerShell.shellHtml(profile, state.aspectRatio);
    if ($('mcTrocrViewerDisclaimer')) {
      $('mcTrocrViewerDisclaimer').textContent = profile.disclaimer
        || 'Simulação de ambiente · sem afiliação com o veículo';
    }
    const holder = document.createElement('div');
    holder.className = 'mc-production-creative mc-trocr-creative';
    placeCreative(holder);
    if (profile.viewer_kind === 'tv') {
      shell.appendChild(holder);
    } else {
      window.McViewerShell.mountCreative(shell, holder, profile.viewer_kind);
    }
    paintViewerPicks(profiles);
  }

  function paintViewerPicks(profiles) {
    const root = $('mcTrocrViewerPicks');
    if (!root) return;
    root.innerHTML = profiles.map((item) => `
      <button type="button" data-viewer="${escapeHtml(item.slug)}" class="${item.slug === state.viewerSlug ? 'is-active' : ''}">
        ${item.logo_asset_ref ? `<img src="${escapeHtml(item.logo_asset_ref)}" alt="">` : ''}
        <span>${escapeHtml(item.name)}</span>
      </button>`).join('');
  }

  function onViewerPick(event) {
    const button = event.target.closest('[data-viewer]');
    if (!button) return;
    state.viewerSlug = button.getAttribute('data-viewer') || '';
    state.viewerPicked = true;
    applyPresentation();
  }

  function preferredViewerSlug(profiles) {
    const list = Array.isArray(profiles) ? profiles : [];
    if (!list.length) return '';
    if (state.viewerPicked && list.some((item) => item.slug === state.viewerSlug)) {
      return state.viewerSlug;
    }
    const byId = new Map((state.viewerProfiles || []).map((item) => [String(item.id), item]));
    const linked = (state.formats || []).filter((item) => {
      const profile = byId.get(String(item.default_viewer_profile_id));
      return profile && list.some((row) => row.slug === profile.slug);
    });
    const sameAspect = linked.find((item) => normalizeAspect(item.aspect_ratio) === state.aspectRatio)
      || linked.find((item) => familyOf(normalizeAspect(item.aspect_ratio)) === familyOf(state.aspectRatio));
    const pick = sameAspect || linked[0];
    if (pick) {
      const profile = byId.get(String(pick.default_viewer_profile_id));
      if (profile) return profile.slug;
    }
    const preferred = {
      ctv: { '16:9': ['netflix', 'disney-plus', 'hbo-max', 'prime-video'] },
      portal: { '16:9': ['g1'], '4:5': ['g1'], '1:1': ['g1'] },
      mobile: {
        '9:16': ['tiktok', 'instagram'],
        '4:5': ['instagram', 'facebook'],
        '1:1': ['instagram', 'linkedin'],
      },
    };
    const slugs = (preferred[state.presentation] || {})[state.aspectRatio] || [];
    return slugs.find((slug) => list.some((item) => item.slug === slug)) || list[0].slug || '';
  }

  function normalizeAspect(value) {
    const text = String(value || '').replace(/\s/g, '');
    if (OUTPUTS.some((item) => item.ratio === text)) return text;
    const [width, height] = text.split(':').map(Number);
    if (!width || !height) return '';
    return nearestOutput(width / height);
  }

  async function loadViewerCatalog() {
    const [viewers, formats] = await Promise.all([
      request(API.viewers).catch(() => []),
      request(API.formats).catch(() => []),
    ]);
    state.viewerProfiles = Array.isArray(viewers) ? viewers : [];
    state.formats = Array.isArray(formats) ? formats : [];
    applyPresentation();
  }

  function editFields() {
    const client = currentClient();
    const read = state.lastRead || {};
    const faces = Number.isInteger(read.faces)
      ? read.faces
      : (read.elements || []).filter((item) => (
        item.kind === 'face' || (item.role === 'person' && !item.text && !item.kind)
      )).length;
    return {
      client_id: state.clientId || undefined,
      brand_name: client?.name || '',
      headline: $('mcSwapHeadline')?.value || '',
      support: $('mcSwapSupport')?.value || '',
      price: $('mcTrocrPrice')?.value || '',
      cta: $('mcSwapCta')?.value || '',
      note: $('mcSwapNote')?.value || '',
      instruction: $('mcSwapNote')?.value || '',
      aspect_ratio: state.aspectRatio,
      aspect_hint: read.aspect_hint || '',
      run_id: state.runId || undefined,
      dates: $('mcTrocrDates')?.value || read.dates || '',
      venue: $('mcTrocrVenue')?.value || read.venue || '',
      subtitle: $('mcTrocrSubtitle')?.value || read.subtitle || '',
      logo_text: $('mcTrocrLogo')?.value || read.logo_text || '',
      disclaimer: $('mcTrocrDisclaimer')?.value || read.disclaimer || '',
      faces,
      force_image: Boolean($('mcTrocrForceImage')?.checked),
      presentation: state.presentation,
      quality: state.quality,
      use_brand_context: state.brandContext,
      preserve: checkedValues('mcTrocrPreserve'),
      alter: checkedValues('mcTrocrAlter'),
      prompt_override: (state.promptEdited || state.promptLocked) ? ($('mcTrocrPrompt')?.value || '') : undefined,
      base_id: state.baseId || undefined,
      plan_hash: state.planHash || undefined,
      confirm_conflicts: Boolean($('mcTrocrConfirmConflicts')?.checked),
      ref_width: state.region?.ref_width || undefined,
      ref_height: state.region?.ref_height || undefined,
      regions: state.region?.box ? { [state.region.field]: state.region.box } : undefined,
      elements: withRegion(withCtas(read.elements || [])),
    };
  }

  function regionField() {
    const alter = checkedValues('mcTrocrAlter');
    const order = ['price', 'headline', 'cta', 'secondary'];
    return order.find((item) => alter.includes(item)) || 'price';
  }

  function withCtas(elements) {
    const first = $('mcSwapCta')?.value || '';
    const second = $('mcTrocrCta2')?.value || '';
    const rows = (elements || []).map((item) => ({ ...item }));
    const ctas = rows.filter((item) => item.role === 'cta');
    if (ctas[0] && first) ctas[0].text = first;
    if (ctas[1] && second) ctas[1].text = second;
    if (!ctas[1] && second) {
      rows.push({ role: 'cta', kind: 'type', text: second, source: 'manual' });
    }
    if ($('mcTrocrCta2Field')) $('mcTrocrCta2Field').hidden = !second && !ctas[1];
    return rows;
  }

  function withRegion(elements) {
    if (!state.region?.box) return elements;
    const role = state.region.field === 'secondary' ? 'support' : state.region.field;
    let found = false;
    const rows = (elements || []).map((item) => {
      if (item.role === role && !found) {
        found = true;
        return { ...item, bbox_px: state.region.box, source: item.source || 'manual' };
      }
      return item;
    });
    if (!found) {
      rows.push({
        role,
        kind: 'type',
        text: '',
        bbox_px: state.region.box,
        source: 'manual',
      });
    }
    return rows;
  }

  function payload() {
    return { ...editFields(), reference: baseVersion()?.image || '' };
  }

  async function refreshPrompt() {
    updateNoteCount();
    if (!baseVersion()?.image) return;
    window.clearTimeout(promptTimer);
    promptTimer = window.setTimeout(() => {
      loadPlan().catch((error) => {
        if (error.name === 'AbortError') return;
      });
    }, 220);
  }

  async function loadPlan() {
    window.clearTimeout(promptTimer);
    if (promptAbort) promptAbort.abort();
    promptAbort = new AbortController();
    const seq = ++state.planSeq;
    const fields = { ...editFields() };
    delete fields.plan_hash;
    const data = await request(API.prompt, fields, { signal: promptAbort.signal });
    if (seq !== state.planSeq) return data;
    applyPlan(data);
    return data;
  }

  function applyPlan(data) {
    state.optimizedPrompt = data.prompt || '';
    if (!state.promptEdited) {
      state.optimizedPreview = data.preview || data.prompt || '';
      const box = $('mcTrocrPrompt');
      if (box && box.readOnly) box.value = state.optimizedPreview;
    }
    state.planHash = data.plan_hash || '';
    state.planBlocked = Boolean(data.blocked);
    state.planNoop = Boolean(data.noop);
    state.conflicts = data.conflicts || [];
    paintRoute(data.risk, data.mode, data.quote, data);
    enableGenerate(canGenerate());
  }

  async function refreshQuote() {
    try {
      const quote = await request(API.quote, { kind: 'swap', quality: state.quality, ...editFields() });
      paintCost(quote);
    } catch (_error) {
      /* custo é auxiliar */
    }
  }

  async function runSwap(quality) {
    const base = baseVersion();
    if (!base?.image) return;
    state.quality = quality;
    document.querySelectorAll('input[name="mcTrocrQuality"]').forEach((node) => {
      node.checked = node.value === quality;
    });
    highlightQuality();
    enableGenerate(false);
    setFlow('generate');
    showWait(quality, state.mode);
    setStatus(state.mode === 'typeset'
      ? 'Compondo o tipo na foto…'
      : (quality === 'draft' ? 'Gerando rascunho…' : 'Gerando produção…'));
    hideError();
    state.lastAction = 'generate';
    try {
      try {
        await loadPlan();
      } catch (error) {
        if (error.name !== 'AbortError') throw error;
      }
      if (state.planBlocked && !$('mcTrocrConfirmConflicts')?.checked) {
        const first = state.conflicts.find((item) => item.blocking) || state.conflicts[0] || {};
        throw new Error(conflictCopy(first) || 'Ajuste o pedido antes de gerar.');
      }
      const data = await request(API.swap, {
        ...editFields(),
        quality,
        reference: base.image,
        base_id: state.baseId || undefined,
        revision: state.revision || 0,
      });
      state.planHash = data.plan_hash || state.planHash;
      state.planBlocked = Boolean(data.blocked);
      state.planNoop = Boolean(data.noop);
      state.conflicts = data.conflicts || state.conflicts;
      paintRoute(data.risk, data.mode, data.quote, data);
      if (data.noop || data.mode === 'noop') {
        setFlow('edit');
        toast('Nada para trocar. Nenhuma versão nova.', 'success');
        setStatus(data.preview || 'Nada para trocar. Marque um item ou escreva a instrução.');
        return null;
      }
      const still = data.image_url || data.png_data_url;
      if (!still) throw new Error(data.preview || 'A geração não devolveu a imagem.');
      const thumb = await makeThumb(still);
      const typeset = data.mode === 'typeset';
      const recrop = data.mode === 'recrop';
      const version = pushVersion({
        name: typeset ? 'Tipo na foto' : (recrop ? 'Recorte + tipo' : (quality === 'draft' ? 'Rascunho' : 'Produção')),
        origin: typeset ? 'typeset' : (recrop ? 'recrop' : (quality === 'draft' ? 'draft' : 'production')),
        quality: typeset ? 'typeset' : quality,
        image: still,
        thumb,
        qa: data.qa || null,
        plan_hash: data.plan_hash || '',
        parent_id: base.id,
      });
      if (data.history) applyStoredUrls(data.history);
      state.compareIds = [base.id, version.id];
      showPreview(still);
      state.promptLocked = false;
      state.promptEdited = false;
      setFlow('review');
      toast(data.mode === 'typeset'
        ? 'Tipo composto na foto. Elenco intacto.'
        : (data.mode === 'recrop'
          ? 'Formato virado. Tipo composto na foto.'
          : 'Nova versão criada com sucesso'), 'success');
      setStatus(data.mode === 'typeset'
        ? 'Tipo composto na foto original. Os selos de nome não foram redesenhados.'
        : (data.mode === 'recrop'
          ? 'O formato virou. Preço e headline entraram na foto.'
          : (data.logo_used
            ? 'Nova versão criada. A logo oficial entrou no quadro.'
            : 'Nova versão criada. Use esta versão como base para continuar editando.')));
      renderCompare();
      await persistHistory();
      return version;
    } catch (error) {
      setFlow('generate', 'error');
      showError('Falha ao gerar nova versão', error.message, 'generate');
      setStatus(error.message);
    } finally {
      hideWait();
      enableGenerate(canGenerate());
    }
  }

  function selectVersion(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    state.activeId = version.id;
    showPreview(version.image);
    renderVersions();
    renderBaseMeta();
    renderCompare();
  }

  function useAsBase(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    state.baseId = version.id;
    state.activeId = version.id;
    state.promptEdited = false;
    state.promptLocked = false;
    delete state.cache[version.id];
    showPreview(version.image);
    renderVersions();
    renderBaseMeta();
    toast('Versão definida como base', 'success');
    setStatus('Use esta versão como base para continuar editando.');
    state.lastAction = 'ocr';
    schedulePersist();
    readReference(version, { force: true, reference: version.image });
  }

  function duplicateVersion(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    const copy = pushVersion({
      name: `${version.name} copiada`,
      origin: 'edited',
      image: version.image,
      thumb: version.thumb,
      ocr: version.ocr,
      analysis: version.analysis,
      asBase: false,
    });
    if (version.ocr) state.cache[copy.id] = version.ocr;
    toast('Versão duplicada. O original permanece no histórico.', 'success');
  }

  async function renameVersion(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    const next = await askName('Nome da versão', version.name);
    if (!next) return;
    version.name = next.replace(/^v\d+\s*·\s*/i, '').trim() || version.name;
    renderVersions();
    schedulePersist();
  }

  function deleteVersion(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version || version.origin === 'original') {
      setStatus('A versão original não pode ser excluída.');
      return;
    }
    if (state.versions.length <= 1) return;
    state.versions = state.versions.filter((item) => item.id !== id);
    if (state.activeId === id) state.activeId = state.versions[state.versions.length - 1].id;
    if (state.baseId === id) state.baseId = state.versions[0].id;
    const current = currentVersion();
    if (current) showPreview(current.image);
    renderVersions();
    renderBaseMeta();
    schedulePersist();
  }

  function restoreContext(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    selectVersion(id);
    if (version.ocr) applyRead(version.ocr, version, { cached: true });
  }

  function onVersionClick(event) {
    const button = event.target.closest('button[data-action]');
    const card = event.target.closest('[data-version]');
    if (!card) return;
    const id = card.getAttribute('data-version');
    const action = button?.getAttribute('data-action');
    if (!action && event.target.closest('summary, menu, details')) return;
    if (action === 'base') useAsBase(id);
    else if (action === 'compare') {
      state.compareIds = [state.baseId || state.versions[0]?.id, id];
      setViewMode('compare');
    } else if (action === 'duplicate') duplicateVersion(id);
    else if (action === 'rename') renameVersion(id);
    else if (action === 'delete') deleteVersion(id);
    else if (action === 'restore') restoreContext(id);
    else selectVersion(id);
    if (event.currentTarget.id === 'mcTrocrHistoryList') closeHistory();
  }

  function renderVersions() {
    const list = $('mcTrocrVersions');
    const count = $('mcTrocrVersionCount');
    const create = $('mcTrocrNewEdit');
    if (create) create.disabled = !state.versions.length;
    const historyCount = state.runs.length || state.versions.length;
    if ($('mcTrocrHistoryBtn')) $('mcTrocrHistoryBtn').disabled = !historyCount;
    if ($('mcTrocrOpenHistory')) $('mcTrocrOpenHistory').disabled = !historyCount;
    if ($('mcTrocrHistoryCount')) $('mcTrocrHistoryCount').textContent = String(historyCount);
    const versionLabel = state.versions.length
      ? `${state.versions.length} ${state.versions.length === 1 ? 'versão' : 'versões'} nesta troca`
      : 'Nenhuma versão ainda';
    if (count) count.textContent = versionLabel;
    if ($('mcTrocrReelLabel')) {
      const run = state.runs.find((item) => item.run_id === state.runId);
      $('mcTrocrReelLabel').textContent = run?.title
        ? `${run.title} · ${versionLabel}`
        : versionLabel;
    }
    if (!list) return;
    if ($('mcTrocrCompareBtn')) $('mcTrocrCompareBtn').disabled = state.versions.length < 2;
    list.innerHTML = state.versions.map((item) => {
      const current = item.id === state.activeId;
      const base = item.id === state.baseId;
      const when = formatWhen(item.createdAt);
      return `<li class="mc-trocr-take${current ? ' is-active' : ''}${base ? ' is-base' : ''}" data-version="${item.id}">
        <button type="button" class="mc-trocr-take-still" data-action="view">
          ${item.thumb ? `<img src="${item.thumb}" alt="${escapeHtml(item.name)}">` : '<span class="mc-trocr-thumb"></span>'}
          ${base ? '<em>Base</em>' : ''}
        </button>
        <p>
          <strong>${escapeHtml(item.id)} ${escapeHtml(item.name)}</strong>
          <small>${escapeHtml(ORIGIN_LABEL[item.origin] || item.origin)} ${when}${item.parent_id ? ` · de ${escapeHtml(item.parent_id)}` : ''}</small>
        </p>
        <div class="mc-trocr-take-cta">
          <button type="button" data-action="base">Usar como base</button>
          <details>
            <summary aria-label="Mais ações"><svg class="mc-trocr-ico" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="3.5" cy="8" r="1.15" fill="currentColor"/><circle cx="8" cy="8" r="1.15" fill="currentColor"/><circle cx="12.5" cy="8" r="1.15" fill="currentColor"/></svg></summary>
            <menu>
              <button type="button" data-action="compare">Comparar</button>
              <button type="button" data-action="duplicate">Duplicar</button>
              <button type="button" data-action="rename">Renomear</button>
              <button type="button" data-action="restore">Restaurar contexto</button>
              ${item.origin === 'original' ? '' : '<button type="button" data-action="delete">Excluir</button>'}
            </menu>
          </details>
        </div>
      </li>`;
    }).join('');
    const history = $('mcTrocrHistoryList');
    if (history) history.innerHTML = list.innerHTML;
    renderReelSessions();
    renderRuns();
    fitCreative();
  }

  function renderReelSessions() {
    const host = $('mcTrocrReelSessions');
    if (!host) return;
    const others = (state.runs || []).filter((item) => item.run_id && item.run_id !== state.runId);
    host.hidden = !others.length;
    host.innerHTML = others.map((item) => `
      <button type="button" class="mc-trocr-reel-bin" data-run="${escapeHtml(item.run_id)}">
        ${item.thumb_url ? `<img src="${escapeHtml(item.thumb_url)}" alt="">` : '<span></span>'}
        <span>
          <strong>${escapeHtml(item.title || 'Troca')}</strong>
          <small>${item.version_count || 0} versões</small>
        </span>
      </button>`).join('');
  }

  function setReelCollapsed(collapsed) {
    const reel = $('mcTrocrReel');
    const toggle = $('mcTrocrReelToggle');
    if (!reel) return;
    reel.classList.toggle('is-collapsed', Boolean(collapsed));
    toggle?.setAttribute('aria-expanded', String(!collapsed));
    try {
      window.localStorage.setItem('cx-trocr-reel', collapsed ? '1' : '0');
    } catch (_error) {}
    window.requestAnimationFrame(fitCreative);
  }

  function fitCreative() {
    const stage = $('mcTrocrViewport');
    if (!stage?.classList.contains('has-image')) return;
    const [wide, tall] = String(state.aspectRatio || '16:9').split(':').map(Number);
    const ratio = wide && tall ? wide / tall : 16 / 9;
    const pad = 20;
    const availW = Math.max(96, stage.clientWidth - pad);
    const availH = Math.max(96, stage.clientHeight - pad);
    let width = availW;
    let height = width / ratio;
    if (height > availH) {
      height = availH;
      width = height * ratio;
    }
    stage.style.setProperty('--mc-fit-w', `${Math.floor(width)}px`);
    stage.style.setProperty('--mc-fit-h', `${Math.floor(height)}px`);
    applyUserZoom();
  }

  function applyUserZoom() {
    const scale = state.zoom;
    const stage = $('mcTrocrViewport');
    document.documentElement.style.setProperty('--mc-trocr-zoom', String(scale));
    if (stage) stage.style.setProperty('--mc-trocr-zoom', String(scale));
    if ($('mcTrocrZoomLabel')) {
      $('mcTrocrZoomLabel').textContent = Math.abs(scale - 1) < 0.02
        ? 'Caber'
        : `${Math.round(scale * 100)}%`;
    }
  }

  function renderCompare() {
    const firstId = state.compareIds[0] || state.versions[0]?.id;
    let secondId = state.compareIds[1] || state.activeId;
    if (secondId === firstId && state.versions.length > 1) {
      secondId = (state.versions.find((item) => item.id !== firstId) || {}).id;
    }
    const first = state.versions.find((item) => item.id === firstId);
    const second = state.versions.find((item) => item.id === secondId);
    if ($('mcTrocrCompareA') && first) $('mcTrocrCompareA').src = first.image;
    if ($('mcTrocrCompareB') && second) $('mcTrocrCompareB').src = second.image;
    if ($('mcTrocrCompareALabel') && first) $('mcTrocrCompareALabel').textContent = `${first.id} · ${first.name}`;
    if ($('mcTrocrCompareBLabel') && second) $('mcTrocrCompareBLabel').textContent = `${second.id} · ${second.name}`;
  }

  function setViewMode(mode) {
    state.viewMode = mode;
    $('mcTrocrViewBtn')?.classList.toggle('is-active', mode === 'view');
    $('mcTrocrCompareBtn')?.classList.toggle('is-active', mode === 'compare');
    const hasImage = Boolean(currentVersion()?.image);
    $('mcSwapDrop').hidden = hasImage;
    $('mcSwapPreview').hidden = !hasImage || mode === 'compare';
    $('mcTrocrCompare').hidden = mode !== 'compare' || state.versions.length < 2;
    $('mcTrocrViewport')?.classList.toggle('has-image', hasImage);
    renderEditPanels();
    if (mode === 'compare') renderCompare();
    fitCreative();
  }

  function showPreview(src) {
    if ($('mcSwapImage') && src) {
      $('mcSwapImage').src = src;
      $('mcSwapImage').onload = () => {
        fitCreative();
        paintRegionBox();
      };
    }
    $('mcSwapPreview').hidden = state.viewMode === 'compare';
    $('mcSwapDrop').hidden = true;
    $('mcTrocrViewport')?.classList.add('has-image');
    applyPresentation();
    renderEditPanels();
    if (state.viewMode === 'compare') renderCompare();
    window.requestAnimationFrame(fitCreative);
  }

  function renderEditPanels() {
    const ready = Boolean(baseVersion()?.image || currentVersion()?.image);
    ['mcTrocrOcr', 'mcSwapRead', 'mcTrocrPreserveAlter', 'mcTrocrEditBlock'].forEach((id) => {
      if ($(id)) $(id).hidden = !ready;
    });
    const generate = document.querySelector('.mc-trocr-generate');
    if (generate) generate.hidden = !ready;
    $('mcTrocrViewport')?.classList.toggle('has-image', ready && $('mcSwapDrop')?.hidden);
    const filled = Boolean(
      $('mcSwapHeadline')?.value
      || $('mcSwapSupport')?.value
      || $('mcTrocrSubtitle')?.value
      || $('mcTrocrDates')?.value
      || $('mcTrocrVenue')?.value
      || $('mcTrocrPrice')?.value
      || $('mcSwapCta')?.value
      || $('mcTrocrCta2')?.value
      || $('mcTrocrLogo')?.value
      || $('mcTrocrDisclaimer')?.value
    );
    const ocr = $('mcTrocrOcr');
    const banner = $('mcTrocrOcrBanner');
    const filledCount = [
      'mcSwapHeadline', 'mcSwapSupport', 'mcTrocrSubtitle', 'mcTrocrDates', 'mcTrocrVenue',
      'mcTrocrPrice', 'mcSwapCta', 'mcTrocrCta2', 'mcTrocrLogo', 'mcTrocrDisclaimer',
    ].filter((id) => Boolean($(id)?.value)).length;
    const ocrFailed = Boolean(banner && !banner.hidden);
    if (ocr && ocr.tagName === 'DETAILS') {
      if (ocrFailed) ocr.open = true;
      if ($('mcTrocrOcrHint') && !ocrFailed) {
        $('mcTrocrOcrHint').textContent = filled
          ? 'A leitura preencheu. Abra só se algo estiver errado.'
          : 'Nenhum texto para mostrar.';
      }
    }
    const analysisCount = document.querySelectorAll('input[name="mcTrocrAnalysis"]:checked').length;
    const readSignal = $('mcTrocrReadSignal');
    if (readSignal) {
      const parts = [];
      if (ocrFailed) parts.push('Sem leitura');
      else if (filledCount) parts.push(`${filledCount} textos`);
      if (analysisCount) parts.push(`${analysisCount} na foto`);
      readSignal.hidden = !parts.length;
      readSignal.textContent = parts.join(' · ');
    }
  }

  function renderBaseMeta() {
    const active = currentVersion();
    const base = baseVersion();
    const node = $('mcTrocrBaseMeta');
    if (!node) return;
    if (!active) {
      node.textContent = 'Nenhuma versão selecionada';
      return;
    }
    const route = state.mode === 'typeset' ? 'Tipo na foto.' : '';
    node.textContent = `Editando ${active.id} · ${active.name}. Base ativa: ${base ? `${base.id} · ${base.name}` : '—'}.${route ? ` ${route}` : ''}`;
  }

  function setFlow(step, error) {
    state.flow = step;
    state.flowError = error || '';
    $('mcSwap')?.setAttribute('data-flow', step);
    renderFlow();
  }

  function renderFlow() {
    const currentIndex = FLOW.indexOf(state.flow);
    document.querySelectorAll('#mcTrocrSteps [data-step]').forEach((node) => {
      const index = FLOW.indexOf(node.getAttribute('data-step'));
      node.classList.toggle('is-current', index === currentIndex && !state.flowError);
      node.classList.toggle('is-done', index < currentIndex);
      node.classList.toggle('is-error', Boolean(state.flowError) && index === currentIndex);
    });
  }

  function highlightQuality() {
    paintGoLabel();
  }

  function enableGenerate(enabled) {
    if ($('mcSwapRun')) $('mcSwapRun').disabled = !enabled;
    if ($('mcTrocrDraft')) $('mcTrocrDraft').disabled = !enabled;
  }

  function paintGoLabel() {
    const button = $('mcSwapRun');
    if (!button) return;
    if (state.mode === 'noop' || state.planNoop) button.textContent = 'Nada para trocar';
    else if (state.mode === 'blocked' || state.planBlocked) button.textContent = 'Gerar bloqueado';
    else if (state.mode === 'typeset') button.textContent = 'Compor na foto';
    else if (state.mode === 'recrop') button.textContent = 'Recortar e compor';
    else button.textContent = state.quality === 'draft' ? 'Gerar rascunho' : 'Gerar produção';
  }

  function showWait(quality, mode) {
    const box = $('mcTrocrWait');
    if (!box) return;
    const typeset = mode === 'typeset';
    const draft = quality === 'draft' && !typeset;
    if ($('mcTrocrWaitTitle')) {
      $('mcTrocrWaitTitle').textContent = typeset
        ? 'Compondo o tipo na foto'
        : (draft ? 'Gerando rascunho' : 'Gerando produção');
    }
    if ($('mcTrocrWaitCopy')) {
      $('mcTrocrWaitCopy').textContent = typeset
        ? 'Isso costuma ser imediato.'
        : (draft
          ? 'Rascunho costuma levar menos de 30 segundos.'
          : 'Produção costuma passar de um minuto.');
    }
    waitStarted = Date.now();
    if ($('mcTrocrWaitTime')) $('mcTrocrWaitTime').textContent = '0:00';
    box.hidden = false;
    window.clearInterval(waitTimer);
    waitTimer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - waitStarted) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = String(elapsed % 60).padStart(2, '0');
      if ($('mcTrocrWaitTime')) $('mcTrocrWaitTime').textContent = `${minutes}:${seconds}`;
    }, 250);
  }

  function hideWait() {
    window.clearInterval(waitTimer);
    waitTimer = 0;
    if ($('mcTrocrWait')) $('mcTrocrWait').hidden = true;
  }

  function openHistory() {
    const dialog = $('mcTrocrHistory');
    if (!dialog || !(state.versions.length || state.runs.length)) return;
    renderRuns();
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.hidden = false;
  }

  function closeHistory() {
    const dialog = $('mcTrocrHistory');
    if (!dialog) return;
    if (typeof dialog.close === 'function' && dialog.open) dialog.close();
    else dialog.hidden = true;
  }

  function setZoom(value) {
    state.zoom = Math.min(2.5, Math.max(0.25, Number(value.toFixed(2))));
    applyUserZoom();
    paintRegionBox();
  }

  function downloadActive() {
    const version = currentVersion();
    if (!version?.image) return;
    const link = document.createElement('a');
    link.href = version.image;
    link.download = `${version.id}-${version.origin}.png`;
    link.click();
  }

  function toggleFullscreen() {
    const stage = $('mcTrocrViewport');
    if (!stage) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else stage.requestFullscreen?.();
  }

  function updateNoteCount() {
    const note = $('mcSwapNote');
    const count = $('mcTrocrNoteCount');
    if (!note || !count) return;
    count.textContent = `${note.value.length}/500`;
  }

  async function onNewPiece() {
    if (state.versions.length) {
      const ok = await askConfirm(
        'Nova troca',
        'A troca atual fica no histórico da marca. Começar outro conjunto?',
      );
      if (!ok) return;
      await persistHistory();
    }
    await startNewRun();
    setStatus('Solte uma imagem. PNG ou JPG.');
  }

  async function startFresh(options) {
    if (readAbort) readAbort.abort();
    if (promptAbort) promptAbort.abort();
    const hadSession = Boolean(state.versions.length || state.revision);
    state.versions = [];
    state.cache = {};
    state.activeId = '';
    state.baseId = '';
    state.lastRead = null;
    state.planHash = '';
    state.planBlocked = false;
    state.planNoop = false;
    state.conflicts = [];
    state.region = null;
    state.replaceSession = true;
    state.forcedFormat = false;
    state.pendingForce = '';
    resetPanel();
    hideError();
    hideWait();
    closeHistory();
    setFlow('upload');
    setViewMode('view');
    if ($('mcSwapImage')) $('mcSwapImage').removeAttribute('src');
    if ($('mcSwapPreview')) $('mcSwapPreview').hidden = true;
    if ($('mcSwapDrop')) $('mcSwapDrop').hidden = false;
    $('mcTrocrViewport')?.classList.remove('has-image');
    renderVersions();
    renderBaseMeta();
    renderEditPanels();
    if (options?.persistEmpty && hadSession) {
      await resetHistory();
    }
  }

  async function startNewRun() {
    await startFresh({ persistEmpty: false });
    await resetHistory();
  }

  async function resetHistory() {
    const body = {
      client_id: state.clientId || undefined,
      new_run: true,
      reset: true,
      run_id: state.runId || undefined,
      revision: state.revision || 0,
      versions: [],
      active_id: '',
      base_id: '',
      aspect_ratio: state.aspectRatio,
    };
    try {
      applyHistoryMeta(await request(API.history, body));
    } catch (error) {
      if (!String(error.message || '').toLowerCase().includes('histórico mudou')) return;
      const data = await request(`${API.history}${historyQuery()}`);
      state.revision = Number(data?.revision) || 0;
      applyHistoryMeta(await request(API.history, { ...body, revision: state.revision }));
    }
    renderVersions();
  }

  function resetPanel() {
    ['mcSwapHeadline', 'mcSwapSupport', 'mcTrocrSubtitle', 'mcTrocrDates', 'mcTrocrVenue', 'mcTrocrPrice', 'mcSwapCta', 'mcTrocrCta2', 'mcTrocrLogo', 'mcTrocrDisclaimer', 'mcSwapNote', 'mcTrocrPrompt'].forEach((id) => {
      if ($(id)) $(id).value = '';
    });
    state.promptEdited = false;
    updateNoteCount();
    renderEditPanels();
    refreshPrompt();
  }

  function retryLast() {
    hideError();
    if (state.lastAction === 'generate') runSwap(state.quality);
    else {
      const version = baseVersion();
      if (version) readReference(version, { force: true });
    }
  }

  function showError(title, text, action) {
    state.lastAction = action || state.lastAction;
    const box = $('mcTrocrError');
    if ($('mcTrocrErrorTitle')) $('mcTrocrErrorTitle').textContent = title;
    if ($('mcTrocrErrorText')) $('mcTrocrErrorText').textContent = text;
    if (box) box.hidden = false;
  }

  function hideError() {
    if ($('mcTrocrError')) $('mcTrocrError').hidden = true;
  }

  function toast(text, kind) {
    const node = $('mcTrocrToast');
    if (!node) return;
    node.textContent = text;
    node.classList.toggle('is-success', kind === 'success');
    node.hidden = false;
    window.setTimeout(() => {
      node.hidden = true;
    }, 2600);
  }

  function paintCost(quote) {
    if (!$('mcSwapCost') || quote?.spent_brl == null) return;
    const value = Number(quote.spent_brl);
    $('mcSwapCost').textContent = value === 0 ? 'R$ 0' : `R$ ${value.toFixed(2)}`;
  }

  function paintRoute(risk, mode, quote, plan) {
    state.mode = ['typeset', 'recrop', 'noop', 'blocked'].includes(mode) ? mode : 'image';
    if (plan) {
      state.planBlocked = Boolean(plan.blocked);
      state.planNoop = Boolean(plan.noop);
      state.conflicts = plan.conflicts || [];
      if (plan.plan_hash) state.planHash = plan.plan_hash;
    }
    paintConflicts(state.conflicts, state.planBlocked);
    const typeset = state.mode === 'typeset';
    const recrop = state.mode === 'recrop';
    const noop = state.mode === 'noop' || state.planNoop;
    const blocked = state.mode === 'blocked' || state.planBlocked;
    const forced = Boolean($('mcTrocrForceImage')?.checked);
    const generate = document.querySelector('.mc-trocr-generate');
    generate?.setAttribute('data-route', noop ? 'noop' : (blocked ? 'blocked' : (typeset ? 'typeset' : (recrop ? 'recrop' : 'image'))));
    const route = $('mcTrocrRoute');
    route?.setAttribute('data-mode', typeset || recrop ? 'typeset' : (noop || blocked ? 'noop' : 'image'));
    if ($('mcTrocrRouteName')) {
      $('mcTrocrRouteName').textContent = noop
        ? 'Nada para trocar'
        : (blocked
          ? 'Pedido bloqueado'
          : (typeset
            ? 'Tipo na foto'
            : (recrop ? 'Recorte + tipo na foto' : 'A peça é redesenhada')));
    }
    if ($('mcTrocrRouteCopy')) {
      $('mcTrocrRouteCopy').textContent = noop
        ? 'Falta dizer o que muda. Marque um item ou escreva a frase.'
        : (blocked
          ? 'Ajuste o pedido antes de gerar.'
          : (typeset
            ? 'O texto novo entra na foto. A imagem não muda.'
            : (recrop
              ? 'O formato muda. O texto entra na foto depois.'
              : (risk?.level === 'high'
                ? safeReason(risk, 'Os selos desta cartela costumam embaralhar se a peça for redesenhada.')
                : 'A peça é redesenhada com o pedido.'))));
    }
    paintCost(quote);
    paintRisk(risk, state.mode);
    const destLead = document.querySelector('.mc-trocr-dest-lead');
    if (destLead) destLead.hidden = typeset || noop || blocked;
    if ($('mcTrocrQualityBox')) $('mcTrocrQualityBox').hidden = typeset || noop || blocked;
    if ($('mcTrocrDraft')) $('mcTrocrDraft').hidden = true;
    paintGoLabel();
    if ($('mcTrocrForceRow')) $('mcTrocrForceRow').hidden = !(typeset || recrop || risk?.level === 'high' || forced);
    if ($('mcTrocrPromptHint')) {
      $('mcTrocrPromptHint').textContent = typeset
        ? 'O texto entra na foto. A imagem não muda.'
        : (recrop
          ? 'O formato muda. O texto entra na foto depois.'
          : 'Uma frase basta: o item novo e o que não pode mexer.');
    }
    if ($('mcTrocrStepGenHint')) {
      $('mcTrocrStepGenHint').textContent = typeset ? 'Tipo na foto' : (recrop ? 'Recorte + tipo' : 'Rascunho ou produção');
    }
    highlightQuality();
    enableGenerate(canGenerate());
    paintQa(plan?.qa);
    paintRegionHint();
    paintMarkable();
    renderBaseMeta();
  }

  function canMarkOnImage() {
    if (state.viewMode !== 'view' || !baseVersion()?.image) return false;
    if ($('mcTrocrWait') && !$('mcTrocrWait').hidden) return false;
    return state.mode === 'typeset'
      || state.mode === 'recrop'
      || state.conflicts.some((item) => item.code === 'needs_region');
  }

  function paintMarkable() {
    $('mcTrocrViewport')?.classList.toggle('is-markable', canMarkOnImage() && !state.picking);
  }

  function paintQa(qa) {
    const node = $('mcTrocrQa');
    if (!node) return;
    if (!qa || !qa.status || qa.status === 'unchecked') {
      node.hidden = true;
      node.textContent = '';
      return;
    }
    node.hidden = false;
    node.dataset.status = qa.status;
    node.textContent = qa.status === 'pass'
      ? 'QA: pixels fora da região iguais à base.'
      : 'QA: a pintura saiu da região. Selecione de novo.';
  }

  function paintRegionHint() {
    const node = $('mcTrocrRegionHint');
    if (!node) return;
    if (state.picking) {
      node.hidden = false;
      node.textContent = `Arraste a região do ${regionLabel(regionField())} no still.`;
      return;
    }
    if (state.region?.box) {
      const box = state.region.box;
      node.hidden = false;
      node.textContent = `Região do ${regionLabel(state.region.field)}: ${box[2] - box[0]}×${box[3] - box[1]} px.`;
      return;
    }
    if (state.conflicts.some((item) => item.code === 'needs_region')) {
      node.hidden = false;
      node.textContent = 'Marque na foto a área do texto.';
      return;
    }
    node.hidden = state.mode !== 'typeset';
    node.textContent = 'Selecione a região do item para o tipo pintar só ali.';
  }

  function regionLabel(field) {
    return ({
      price: 'preço',
      headline: 'headline',
      cta: 'CTA',
      secondary: 'apoio',
    })[field] || field;
  }

  function togglePickRegion() {
    state.picking = !state.picking;
    $('mcTrocrViewport')?.classList.toggle('is-picking', state.picking);
    $('mcTrocrPickRegion')?.classList.toggle('is-on', state.picking);
    const layer = $('mcTrocrRegion');
    if (layer) layer.hidden = !state.picking && !state.region?.box;
    paintRegionHint();
    paintMarkable();
    setStatus(state.picking
      ? `Arraste a região do ${regionLabel(regionField())}.`
      : (state.region?.box ? 'Região marcada. O tipo pinta só ali.' : 'Seleção de região desligada.'));
  }

  function imageContentRect(img) {
    if (!img?.naturalWidth) return null;
    const rect = img.getBoundingClientRect();
    const scale = Math.min(rect.width / img.naturalWidth, rect.height / img.naturalHeight);
    const width = img.naturalWidth * scale;
    const height = img.naturalHeight * scale;
    return {
      left: rect.left + (rect.width - width) / 2,
      top: rect.top + (rect.height - height) / 2,
      width,
      height,
      scale,
      nw: img.naturalWidth,
      nh: img.naturalHeight,
    };
  }

  function clientToImagePx(event) {
    const box = imageContentRect($('mcSwapImage'));
    if (!box || !box.scale) return null;
    const x = Math.round((event.clientX - box.left) / box.scale);
    const y = Math.round((event.clientY - box.top) / box.scale);
    return {
      x: Math.max(0, Math.min(box.nw, x)),
      y: Math.max(0, Math.min(box.nh, y)),
      nw: box.nw,
      nh: box.nh,
    };
  }

  function onRegionDown(event) {
    if (!state.picking) return;
    const point = clientToImagePx(event);
    if (!point) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    state.pickStart = point;
    state.region = {
      field: regionField(),
      box: [point.x, point.y, point.x + 8, point.y + 8],
      ref_width: point.nw,
      ref_height: point.nh,
    };
    paintRegionBox();
  }

  function onRegionMove(event) {
    if (!state.picking || !state.pickStart) return;
    const point = clientToImagePx(event);
    if (!point) return;
    const start = state.pickStart;
    state.region = {
      field: regionField(),
      box: [
        Math.min(start.x, point.x),
        Math.min(start.y, point.y),
        Math.max(start.x, point.x),
        Math.max(start.y, point.y),
      ],
      ref_width: point.nw,
      ref_height: point.nh,
    };
    paintRegionBox();
  }

  function onRegionUp() {
    if (!state.pickStart) return;
    state.pickStart = null;
    const box = state.region?.box;
    if (!box || box[2] - box[0] < 8 || box[3] - box[1] < 8) {
      state.region = null;
      paintRegionBox();
      paintRegionHint();
      return;
    }
    state.picking = false;
    $('mcTrocrViewport')?.classList.remove('is-picking');
    $('mcTrocrPickRegion')?.classList.remove('is-on');
    paintRegionBox();
    paintRegionHint();
    refreshPrompt();
    setStatus(`Região do ${regionLabel(state.region.field)} marcada.`);
  }

  function paintRegionBox() {
    const layer = $('mcTrocrRegion');
    const node = $('mcTrocrRegionBox');
    const img = $('mcSwapImage');
    if (!layer || !node) return;
    if (!state.region?.box || !img) {
      node.hidden = true;
      layer.hidden = !state.picking;
      return;
    }
    const content = imageContentRect(img);
    const frame = img.parentElement?.getBoundingClientRect();
    if (!content || !frame) {
      node.hidden = true;
      return;
    }
    const box = state.region.box;
    layer.hidden = false;
    node.hidden = false;
    node.style.left = `${content.left - frame.left + box[0] * content.scale}px`;
    node.style.top = `${content.top - frame.top + box[1] * content.scale}px`;
    node.style.width = `${(box[2] - box[0]) * content.scale}px`;
    node.style.height = `${(box[3] - box[1]) * content.scale}px`;
  }

  function safeReason(risk, fallback) {
    const text = String(risk?.reason || '');
    if (!text || /image\s*2|modelo/i.test(text)) return fallback;
    return text;
  }

  function conflictCopy(item) {
    const code = item?.code || '';
    if (code === 'logo_locked') return 'A logo oficial fica. O pedido não troca o mark.';
    if (code === 'preserve_and_alter') {
      const named = String(item.message || '').split(':').pop()?.replace(/\.$/, '').trim();
      return named
        ? `${named} está em Fica e em Troca. Deixe só um lado.`
        : 'O mesmo item está em Fica e em Troca. Deixe só um lado.';
    }
    if (code === 'field_without_operation') {
      const label = String(item.message || '').split(' ')[0];
      return label ? `${label} mudou. Marque ${label} em Troca.` : 'Um campo mudou. Marque o item em Troca.';
    }
    if (code === 'layout_vs_format') return 'O formato muda e o layout está em Fica. Confirme a recomposição.';
    if (code === 'note_mismatch') return 'A frase pede algo que não está em Troca.';
    if (code === 'needs_region') return 'Marque na foto a área do texto.';
    return item?.message || code || '';
  }

  function paintConflicts(conflicts, blocked) {
    const box = $('mcTrocrConflicts');
    const list = $('mcTrocrConflictList');
    const row = $('mcTrocrConfirmRow');
    const note = $('mcTrocrBrandNote');
    const raw = Array.isArray(conflicts) ? conflicts : [];
    const logoNote = raw.find((item) => item.code === 'logo_locked');
    const items = raw.filter((item) => item.code !== 'logo_locked');
    if (note) {
      note.hidden = !(state.brandContext && logoNote);
      note.textContent = state.brandContext && logoNote ? conflictCopy(logoNote) : '';
    }
    if (box) box.hidden = items.length === 0;
    if (list) {
      list.innerHTML = items.map((item) => (
        `<li class="${item.blocking ? 'is-block' : ''}">${escapeHtml(conflictCopy(item))}</li>`
      )).join('');
    }
    const confirmable = items.some((item) => item.blocking && item.code !== 'needs_region');
    if (row) row.hidden = !confirmable;
  }

  function canGenerate() {
    if (!baseVersion()?.image) return false;
    if (state.conflicts.some((item) => item.code === 'needs_region')) return false;
    if (state.planBlocked && !$('mcTrocrConfirmConflicts')?.checked) return false;
    return true;
  }

  function paintRisk(risk, mode) {
    const node = $('mcTrocrRisk');
    if (!node) return;
    const forced = Boolean($('mcTrocrForceImage')?.checked);
    const warn = risk?.level === 'high' && (mode !== 'typeset' || forced);
    node.hidden = !warn;
    node.classList.toggle('is-on', warn);
    node.textContent = warn
      ? safeReason(risk, 'Os selos desta cartela costumam embaralhar se a peça for redesenhada.')
      : '';
  }

  function currentVersion() {
    return state.versions.find((item) => item.id === state.activeId) || null;
  }

  function baseVersion() {
    return state.versions.find((item) => item.id === state.baseId) || currentVersion();
  }

  function checkedValues(name) {
    return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((node) => node.value);
  }

  function formatWhen(value) {
    if (!(value instanceof Date)) return '';
    return value.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function downscaleImage(dataUrl, maxSide, quality, options) {
    return new Promise((resolve) => {
      const image = new Image();
      image.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(image.width || 1, image.height || 1));
        const alreadyJpeg = String(dataUrl || '').startsWith('data:image/jpeg');
        if (scale >= 1 && !options?.forceJpeg && alreadyJpeg) {
          resolve(dataUrl);
          return;
        }
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round((image.width || 1) * scale));
        canvas.height = Math.max(1, Math.round((image.height || 1) * scale));
        canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      image.onerror = () => resolve(dataUrl);
      image.src = dataUrl;
    });
  }

  function makeThumb(dataUrl) {
    return downscaleImage(dataUrl, 160, 0.72);
  }

  function historyQuery(runId) {
    const parts = [];
    if (state.clientId) parts.push(`client_id=${encodeURIComponent(state.clientId)}`);
    const wanted = runId === undefined ? state.runId : runId;
    if (wanted) parts.push(`run_id=${encodeURIComponent(wanted)}`);
    return parts.length ? `?${parts.join('&')}` : '';
  }

  function hydrateVersions(items) {
    return (Array.isArray(items) ? items : []).map((item, index) => ({
      id: item.id || `v${index + 1}`,
      attempt: item.attempt || index + 1,
      name: item.name || item.id || `v${index + 1}`,
      origin: item.origin || 'edited',
      quality: item.quality || '',
      status: item.status || 'ready',
      createdAt: item.created_at || item.createdAt
        ? new Date(item.created_at || item.createdAt)
        : new Date(),
      image: item.image_url || item.image || '',
      thumb: item.thumb_url || item.thumb || item.image_url || item.image || '',
      ocr: item.ocr || null,
      analysis: item.analysis || null,
      qa: item.qa || null,
      plan_hash: item.plan_hash || '',
      parent_id: item.parent_id || '',
    })).filter((item) => item.image);
  }

  function applyHistoryMeta(data) {
    if (!data) return;
    if (data.run_id) state.runId = data.run_id;
    if (Array.isArray(data.runs)) state.runs = data.runs;
    if (data.revision != null) state.revision = Number(data.revision) || 0;
  }

  function applyHistory(data) {
    applyHistoryMeta(data);
    state.versions = hydrateVersions(data?.versions || []);
    state.cache = {};
    state.versions.forEach((item) => {
      if (item.ocr) state.cache[item.id] = item.ocr;
    });
    state.activeId = data?.active_id && state.versions.some((item) => item.id === data.active_id)
      ? data.active_id
      : (state.versions[state.versions.length - 1]?.id || '');
    state.baseId = data?.base_id && state.versions.some((item) => item.id === data.base_id)
      ? data.base_id
      : (state.versions[0]?.id || '');
    if (data?.aspect_ratio) {
      state.userPickedFormat = true;
      selectFormat(data.aspect_ratio);
    }
    if (data?.revision != null) state.revision = Number(data.revision) || 0;
    const current = currentVersion();
    const base = baseVersion();
    renderVersions();
    renderBaseMeta();
    renderEditPanels();
    if (!current) return;
    showPreview(current.image);
    enableGenerate(canGenerate());
    setFlow('review');
    if (base?.ocr) applyRead(base.ocr, base, { cached: true });
  }

  async function loadHistory(runId) {
    try {
      const data = await request(`${API.history}${historyQuery(runId === undefined ? '' : runId)}`);
      applyHistoryMeta(data);
      if (!data?.versions?.length) {
        renderVersions();
        return false;
      }
      if (data.client_id && !state.clientId) {
        selectBrand(data.client_id);
      }
      applyHistory(data);
      setStatus('Histórico da marca restaurado. Continue editando a partir da base ativa.');
      return true;
    } catch (_error) {
      return false;
    }
  }

  function applyStoredUrls(saved) {
    applyHistoryMeta(saved);
    (saved?.versions || []).forEach((item) => {
      const local = state.versions.find((version) => version.id === item.id);
      if (!local) return;
      if (item.image_url && String(local.image || '').startsWith('data:')) local.image = item.image_url;
      if (item.thumb_url && String(local.thumb || '').startsWith('data:')) local.thumb = item.thumb_url;
      if (item.parent_id && !local.parent_id) local.parent_id = item.parent_id;
      if (item.plan_hash && !local.plan_hash) local.plan_hash = item.plan_hash;
    });
  }

  function schedulePersist() {
    window.clearTimeout(persistTimer);
    persistTimer = window.setTimeout(() => {
      persistHistory().catch(() => {});
    }, 400);
  }

  async function persistHistory() {
    if (!state.versions.length) return null;
    if (persistBusy) {
      persistAgain = true;
      return null;
    }
    persistBusy = true;
    window.clearTimeout(persistTimer);
    let saved = null;
    try {
      do {
        persistAgain = false;
        try {
          saved = await request(API.history, {
            client_id: state.clientId || undefined,
            run_id: state.runId || undefined,
            reset: Boolean(state.replaceSession) && !state.runId,
            active_id: state.activeId,
            base_id: state.baseId,
            aspect_ratio: state.aspectRatio,
            revision: state.revision || 0,
            versions: state.versions.map((item) => ({
              id: item.id,
              attempt: item.attempt,
              name: item.name,
              origin: item.origin,
              quality: item.quality,
              status: item.status,
              created_at: item.createdAt instanceof Date ? item.createdAt.toISOString() : item.createdAt,
              image: item.image,
              thumb: item.thumb,
              ocr: item.ocr,
              analysis: item.analysis,
              qa: item.qa || null,
              plan_hash: item.plan_hash || '',
              parent_id: item.parent_id || '',
            })),
          });
          applyStoredUrls(saved);
          state.replaceSession = false;
        } catch (error) {
          if (!String(error.message || '').toLowerCase().includes('histórico mudou')) {
            return null;
          }
          const data = await request(`${API.history}${historyQuery()}`);
          state.revision = Number(data?.revision) || 0;
          if (state.replaceSession) {
            persistAgain = true;
          } else {
            applyHistory(data);
            return null;
          }
        }
      } while (persistAgain);
      renderVersions();
      return saved;
    } finally {
      persistBusy = false;
    }
  }

  async function request(url, body, options) {
    const response = await fetch(url, {
      method: options?.method || (body ? 'POST' : 'GET'),
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(state.csrf ? { 'X-Trocr-CSRF-Token': state.csrf } : {}),
      },
      signal: options?.signal,
      body: body ? JSON.stringify(body) : undefined,
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    if (response.status === 401 || response.status === 403) {
      throw new Error('Sua sessão expirou. Entre de novo para continuar.');
    }
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || payload.error || (
        response.status >= 500
          ? 'O servidor não concluiu. Tente de novo.'
          : 'Não deu para trocar o anúncio.'
      ));
    }
    return payload.data || payload;
  }

  function setStatus(text) {
    const node = $('mcSwapStatus');
    if (node) node.textContent = text;
  }

  function renderRuns() {
    const list = $('mcTrocrRunList');
    if (!list) return;
    const runs = state.runs.length ? state.runs : (state.runId ? [{
      run_id: state.runId,
      title: 'Troca atual',
      version_count: state.versions.length,
      aspect_ratio: state.aspectRatio,
      active: true,
    }] : []);
    if ($('mcTrocrHistoryRunTitle')) {
      const current = runs.find((item) => item.run_id === state.runId) || runs[0];
      $('mcTrocrHistoryRunTitle').textContent = current
        ? `${current.title || 'Troca'} · ${current.version_count || state.versions.length} versões`
        : 'Versões desta troca';
    }
    list.innerHTML = runs.map((item) => `
      <li>
        <button type="button" data-run="${escapeHtml(item.run_id)}" class="${item.run_id === state.runId ? 'is-active' : ''}">
          ${item.thumb_url ? `<img src="${escapeHtml(item.thumb_url)}" alt="">` : '<span></span>'}
          <strong>${escapeHtml(item.title || 'Troca')}</strong>
          <small>${escapeHtml(item.aspect_ratio || '')} · ${item.version_count || 0} versões</small>
        </button>
      </li>`).join('') || '<li class="is-empty">Nenhuma troca desta marca ainda.</li>';
  }

  async function onRunClick(event) {
    const button = event.target.closest('[data-run]');
    if (!button) return;
    const runId = button.getAttribute('data-run');
    if (!runId || runId === state.runId) return;
    await persistHistory();
    const restored = await loadHistory(runId);
    if (!restored) {
      state.runId = runId;
      state.versions = [];
      renderVersions();
    }
    setStatus('Troca da marca aberta no canvas.');
  }

  function askConfirm(title, text) {
    const dialog = $('mcTrocrConfirm');
    if (!dialog || typeof dialog.showModal !== 'function') {
      return Promise.resolve(false);
    }
    if ($('mcTrocrConfirmTitle')) $('mcTrocrConfirmTitle').textContent = title;
    if ($('mcTrocrConfirmText')) $('mcTrocrConfirmText').textContent = text;
    dialog.showModal();
    return new Promise((resolve) => {
      const ok = $('mcTrocrConfirmOk');
      const cancel = $('mcTrocrConfirmCancel');
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        ok?.removeEventListener('click', onOk);
        cancel?.removeEventListener('click', onCancel);
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
      ok?.addEventListener('click', onOk);
      cancel?.addEventListener('click', onCancel);
      dialog.addEventListener('cancel', onCancel);
    });
  }

  function askName(title, value) {
    const dialog = $('mcTrocrName');
    const input = $('mcTrocrNameInput');
    if (!dialog || !input || typeof dialog.showModal !== 'function') {
      return Promise.resolve('');
    }
    if ($('mcTrocrNameTitle')) $('mcTrocrNameTitle').textContent = title;
    input.value = value || '';
    dialog.showModal();
    input.focus();
    input.select();
    return new Promise((resolve) => {
      const ok = $('mcTrocrNameOk');
      const cancel = $('mcTrocrNameCancel');
      let settled = false;
      const finish = (next) => {
        if (settled) return;
        settled = true;
        ok?.removeEventListener('click', onOk);
        cancel?.removeEventListener('click', onCancel);
        dialog.removeEventListener('cancel', onCancel);
        if (dialog.open) dialog.close();
        resolve(next);
      };
      const onOk = (event) => {
        event.preventDefault();
        finish(input.value.trim());
      };
      const onCancel = (event) => {
        event.preventDefault();
        finish('');
      };
      ok?.addEventListener('click', onOk);
      cancel?.addEventListener('click', onCancel);
      dialog.addEventListener('cancel', onCancel);
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') onOk(event);
      }, { once: true });
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
