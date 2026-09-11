(function () {
  const API = {
    swap: '/parametros/api/format-lab/swap',
    read: '/parametros/api/format-lab/swap/read',
    prompt: '/parametros/api/format-lab/swap/prompt',
    quote: '/parametros/api/format-lab/quote',
    clients: '/parametros/api/clients',
  };
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
    aspectRatio: '16:9',
    userPickedFormat: false,
    presentation: 'final',
    quality: 'production',
    brandContext: true,
    promptEdited: false,
    promptLocked: false,
    optimizedPrompt: '',
    optimizedPreview: '',
    zoom: 1,
    lastAction: '',
    cache: {},
  };

  let readAbort = null;
  let promptAbort = null;
  let promptTimer = 0;

  document.addEventListener('DOMContentLoaded', boot);

  function $(id) {
    return document.getElementById(id);
  }

  async function boot() {
    bind();
    applyRatio(state.aspectRatio);
    applyPresentation();
    renderFlow();
    renderVersions();
    highlightQuality();
    try {
      const clients = await request(API.clients);
      state.clients = Array.isArray(clients) ? clients : (clients?.items || clients?.clients || []);
      renderClients();
    } catch (_error) {
      setStatus('Não deu para carregar as marcas. Você ainda pode escrever o nome no pedido.');
    }
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
    $('mcSwapClient')?.addEventListener('change', (event) => {
      state.clientId = event.target.value;
      refreshPrompt();
    });
    document.querySelectorAll('input[name="mcSwapOut"]').forEach((node) => {
      node.addEventListener('change', () => {
        if (!node.checked) return;
        state.userPickedFormat = true;
        state.aspectRatio = node.value;
        applyRatio(node.value);
        refreshPrompt();
      });
    });
    document.querySelectorAll('input[name="mcTrocrPresent"]').forEach((node) => {
      node.addEventListener('change', () => {
        if (!node.checked) return;
        state.presentation = node.value;
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
      refreshPrompt();
    });
    ['mcSwapHeadline', 'mcSwapSupport', 'mcTrocrPrice', 'mcSwapCta', 'mcSwapNote'].forEach((id) => {
      $(id)?.addEventListener('input', () => {
        if (id === 'mcSwapNote') updateNoteCount();
        if (state.versions.length) setFlow('edit');
        refreshPrompt();
      });
    });
    document.querySelectorAll('input[name="mcTrocrPreserve"], input[name="mcTrocrAlter"]').forEach((node) => {
      node.addEventListener('change', refreshPrompt);
    });
    $('mcSwapRun')?.addEventListener('click', () => runSwap('production'));
    $('mcTrocrDraft')?.addEventListener('click', () => runSwap('draft'));
    $('mcTrocrViewBtn')?.addEventListener('click', () => setViewMode('view'));
    $('mcTrocrCompareBtn')?.addEventListener('click', () => setViewMode('compare'));
    $('mcTrocrZoomIn')?.addEventListener('click', () => setZoom(state.zoom + 0.1));
    $('mcTrocrZoomOut')?.addEventListener('click', () => setZoom(state.zoom - 0.1));
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
    $('mcTrocrVersions')?.addEventListener('click', onVersionClick);
  }

  function renderClients() {
    const select = $('mcSwapClient');
    if (!select) return;
    select.innerHTML = '<option value="">Marca da mesa</option>' + state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || '')}</option>`
    )).join('');
  }

  function takeFile(file) {
    if (!file || !file.type.startsWith('image/')) {
      setStatus('Solte uma imagem. PNG ou JPG.');
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      const image = String(reader.result || '');
      const thumb = await makeThumb(image);
      const version = pushVersion({
        name: 'Original',
        origin: 'original',
        image,
        thumb,
      });
      showPreview(image);
      setStatus('Ao enviar uma nova imagem, o OCR é executado automaticamente.');
      readReference(version, { force: true });
    };
    reader.readAsDataURL(file);
  }

  function pushVersion(partial) {
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
    };
    state.versions.push(version);
    state.activeId = version.id;
    if (!state.baseId || partial.asBase !== false) state.baseId = version.id;
    enableGenerate(true);
    renderVersions();
    renderBaseMeta();
    return version;
  }

  async function readReference(version, options) {
    const force = Boolean(options?.force);
    if (!version?.image) return;
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
      const reference = await downscaleImage(version.image, 1280, 0.82);
      const data = await request(API.read, { reference }, { signal: readAbort.signal });
      state.cache[version.id] = data;
      version.ocr = data;
      version.analysis = data.analysis || null;
      applyRead(data, version, { cached: false });
      toast('OCR atualizado', 'success');
    } catch (error) {
      if (error.name === 'AbortError') return;
      setFlow('ocr', 'error');
      showError('Falha ao executar OCR', error.message || 'Não deu para ler os textos.', 'ocr');
      setStatus('Não deu para ler os textos. Você ainda pode escrever na mão.');
    }
  }

  function applyRead(data, version, meta) {
    fillFields(data);
    applyAnalysis(data.analysis || {}, data.elements || []);
    renderElements(data.elements || [], data.style || '');
    if (data.aspect_hint && !state.userPickedFormat) selectFormat(data.aspect_hint);
    setFlow(meta?.cached ? 'edit' : 'analysis');
    window.setTimeout(() => {
      if (state.flow === 'analysis') setFlow('edit');
    }, 280);
    setStatus(meta?.cached
      ? 'Elementos da base ativa. Edite o texto e gere uma nova versão.'
      : 'Elementos identificados na imagem. Selecione o que deseja preservar ou alterar.');
    refreshPrompt();
    renderBaseMeta();
  }

  function fillFields(data) {
    const headline = $('mcSwapHeadline');
    const support = $('mcSwapSupport');
    const price = $('mcTrocrPrice');
    const cta = $('mcSwapCta');
    if (headline) headline.value = data.headline || '';
    if (support) support.value = data.support || '';
    if (price) price.value = data.price || '';
    if (cta) cta.value = data.cta || '';
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

  function renderElements(items, style) {
    const list = $('mcSwapElements');
    if (!list) return;
    const rows = Array.isArray(items) ? items : [];
    list.innerHTML = rows.map((item) => {
      const label = ROLE_LABEL[item.role] || item.role || 'Elemento';
      const text = item.text || item.note || '';
      return `<li><strong>${escapeHtml(label)}</strong>${text ? ` ${escapeHtml(text)}` : ''}</li>`;
    }).join('');
    if (style) list.innerHTML += `<li class="is-style">${escapeHtml(style)}</li>`;
  }

  function selectFormat(ratio) {
    const input = document.querySelector(`input[name="mcSwapOut"][value="${ratio}"]`);
    if (!input) return;
    input.checked = true;
    state.aspectRatio = ratio;
    applyRatio(ratio);
  }

  function applyRatio(ratio) {
    const [width, height] = String(ratio || '16:9').split(':').map(Number);
    const stage = $('mcTrocrViewport') || $('mcSwapStage');
    if (!stage || !width || !height) return;
    stage.style.setProperty('--mc-swap-ratio', `${width} / ${height}`);
    stage.classList.toggle('is-vertical', height > width);
  }

  function applyPresentation() {
    const frame = document.querySelector('.mc-trocr-frame');
    if (frame) frame.dataset.mockup = state.presentation;
    $('mcTrocrViewport')?.setAttribute('data-presentation', state.presentation);
  }

  function editFields() {
    const client = state.clients.find((item) => String(item.id) === String(state.clientId));
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
      presentation: state.presentation,
      quality: state.quality,
      use_brand_context: state.brandContext,
      preserve: checkedValues('mcTrocrPreserve'),
      alter: checkedValues('mcTrocrAlter'),
      prompt_override: (state.promptEdited || state.promptLocked) ? ($('mcTrocrPrompt')?.value || '') : undefined,
    };
  }

  function payload() {
    return { ...editFields(), reference: baseVersion()?.image || '' };
  }

  async function refreshPrompt() {
    updateNoteCount();
    if (!baseVersion()?.image || state.promptEdited) return;
    window.clearTimeout(promptTimer);
    promptTimer = window.setTimeout(async () => {
      if (promptAbort) promptAbort.abort();
      promptAbort = new AbortController();
      try {
        const data = await request(API.prompt, editFields(), { signal: promptAbort.signal });
        state.optimizedPrompt = data.prompt || '';
        state.optimizedPreview = data.preview || data.prompt || '';
        const box = $('mcTrocrPrompt');
        if (box && box.readOnly) box.value = state.optimizedPreview;
        paintCost(data.quote);
      } catch (error) {
        if (error.name === 'AbortError') return;
      }
    }, 220);
  }

  async function refreshQuote() {
    try {
      const quote = await request(API.quote, { kind: 'swap', quality: state.quality });
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
    showGenSteps('analysis');
    setStatus(quality === 'draft' ? 'Gerando rascunho…' : 'Gerando nova versão…');
    hideError();
    state.lastAction = 'generate';
    try {
      showGenSteps('prompt');
      const data = await request(API.swap, { ...editFields(), quality, reference: base.image });
      showGenSteps('generate');
      if (!data.png_data_url) throw new Error('A geração não devolveu a imagem.');
      const thumb = await makeThumb(data.png_data_url);
      showGenSteps('finish');
      const version = pushVersion({
        name: quality === 'draft' ? 'Rascunho' : 'Produção',
        origin: quality === 'draft' ? 'draft' : 'production',
        quality,
        image: data.png_data_url,
        thumb,
      });
      state.compareIds = [base.id, version.id];
      showPreview(data.png_data_url);
      paintCost(data.quote);
      state.promptLocked = false;
      state.promptEdited = false;
      setFlow('review');
      toast('Nova versão criada com sucesso', 'success');
      setStatus(data.logo_used
        ? 'Nova versão criada. A logo oficial entrou no quadro.'
        : 'Nova versão criada. Use esta versão como base para continuar editando.');
      renderCompare();
      return version;
    } catch (error) {
      setFlow('generate', 'error');
      showError('Falha ao gerar nova versão', error.message, 'generate');
      setStatus(error.message);
    } finally {
      hideGenSteps();
      enableGenerate(Boolean(baseVersion()?.image));
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
    readReference(version, { force: true });
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

  function renameVersion(id) {
    const version = state.versions.find((item) => item.id === id);
    if (!version) return;
    const next = window.prompt('Nome da versão', `${version.id} · ${version.name}`);
    if (!next) return;
    version.name = next.replace(/^v\d+\s*·\s*/i, '').trim() || version.name;
    renderVersions();
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
  }

  function renderVersions() {
    const list = $('mcTrocrVersions');
    const count = $('mcTrocrVersionCount');
    const create = $('mcTrocrNewEdit');
    if (create) create.disabled = !state.versions.length;
    if (count) {
      count.textContent = state.versions.length
        ? `${state.versions.length} ${state.versions.length === 1 ? 'versão' : 'versões'}. Nenhuma versão será sobrescrita.`
        : 'Nenhuma versão. O histórico será criado ao enviar o criativo.';
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
          <small>${escapeHtml(ORIGIN_LABEL[item.origin] || item.origin)} ${when}</small>
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
    $('mcTrocrCompare').hidden = mode !== 'compare' || state.versions.length < 1;
    if (mode === 'compare') renderCompare();
  }

  function showPreview(src) {
    if ($('mcSwapImage') && src) $('mcSwapImage').src = src;
    $('mcSwapPreview').hidden = state.viewMode === 'compare';
    $('mcSwapDrop').hidden = true;
    if (state.viewMode === 'compare') renderCompare();
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
    node.textContent = `Editando ${active.id} · ${active.name}. Base ativa: ${base ? `${base.id} · ${base.name}` : '—'}.`;
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
    const draft = $('mcTrocrDraft');
    const prod = $('mcSwapRun');
    const draftOn = state.quality === 'draft';
    draft?.classList.toggle('cx-btn-primary', draftOn);
    draft?.classList.toggle('cx-btn-secondary', !draftOn);
    prod?.classList.toggle('cx-btn-primary', !draftOn);
    prod?.classList.toggle('cx-btn-secondary', draftOn);
  }

  function enableGenerate(enabled) {
    if ($('mcSwapRun')) $('mcSwapRun').disabled = !enabled;
    if ($('mcTrocrDraft')) $('mcTrocrDraft').disabled = !enabled;
  }

  function showGenSteps(current) {
    const list = $('mcTrocrGenSteps');
    if (!list) return;
    list.hidden = false;
    const order = ['analysis', 'prompt', 'generate', 'finish'];
    const index = order.indexOf(current);
    list.querySelectorAll('[data-gen]').forEach((node) => {
      const pos = order.indexOf(node.getAttribute('data-gen'));
      node.classList.toggle('is-done', pos < index);
      node.classList.toggle('is-current', pos === index);
    });
  }

  function hideGenSteps() {
    const list = $('mcTrocrGenSteps');
    if (list) list.hidden = true;
  }

  function setZoom(value) {
    state.zoom = Math.min(2, Math.max(0.5, Number(value.toFixed(2))));
    document.documentElement.style.setProperty('--mc-trocr-zoom', String(state.zoom));
    const stage = $('mcTrocrViewport');
    if (stage) stage.style.setProperty('--mc-trocr-zoom', String(state.zoom));
    if ($('mcTrocrZoomLabel')) $('mcTrocrZoomLabel').textContent = `${Math.round(state.zoom * 100)}%`;
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

  function resetPanel() {
    ['mcSwapHeadline', 'mcSwapSupport', 'mcTrocrPrice', 'mcSwapCta', 'mcSwapNote', 'mcTrocrPrompt'].forEach((id) => {
      if ($(id)) $(id).value = '';
    });
    state.promptEdited = false;
    updateNoteCount();
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
    if (quote?.spent_brl != null && $('mcSwapCost')) {
      $('mcSwapCost').textContent = `R$ ${Number(quote.spent_brl).toFixed(2)}`;
    }
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

  function downscaleImage(dataUrl, maxSide, quality) {
    return new Promise((resolve) => {
      const image = new Image();
      image.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
        if (scale >= 1) {
          resolve(dataUrl);
          return;
        }
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * scale);
        canvas.height = Math.round(image.height * scale);
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

  async function request(url, body, options) {
    const response = await fetch(url, {
      method: options?.method || (body ? 'POST' : 'GET'),
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
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

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
