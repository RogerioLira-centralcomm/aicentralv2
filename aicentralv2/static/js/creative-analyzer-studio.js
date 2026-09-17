(() => {
  const root = document.getElementById('creativeAnalyzer');
  if (!root) return;
  const grid = document.getElementById('analyzerGrid');
  const status = document.getElementById('analyzerStatus');
  const more = document.getElementById('analyzerMore');
  const form = document.getElementById('analyzerUpload');
  const file = document.getElementById('analyzerFile');
  const result = document.getElementById('analyzerResult');
  const project = document.getElementById('analyzerProject');
  const progress = document.getElementById('analyzerProgress');
  const progressTitle = document.getElementById('analyzerProgressTitle');
  const progressDetail = document.getElementById('analyzerProgressDetail');
  const progressTimer = document.getElementById('analyzerProgressTimer');
  const progressSteps = document.getElementById('analyzerProgressSteps');
  let nextOffset = 0;
  let historyLoading = false;
  let uploadLoading = false;
  let historyItems = [];
  const transferred = new Map();
  let progressInterval = null;

  function startProgress(mediaType) {
    if (!progress) return;
    const stages = mediaType === 'video'
      ? ['Preparar arquivo', 'Ler quatro momentos do vídeo', 'Interpretar a narrativa', 'Organizar o diagnóstico']
      : ['Preparar arquivo', 'Ler composição e texto', 'Interpretar a peça', 'Organizar o diagnóstico'];
    progressSteps.replaceChildren(...stages.map(stage => element('li', '', stage)));
    const startedAt = Date.now();
    const update = () => {
      const seconds = Math.floor((Date.now() - startedAt) / 1000);
      const stage = Math.min(stages.length - 1, Math.floor(seconds / 7));
      progressTitle.textContent = stages[stage];
      progressDetail.textContent = stage === 0 ? 'Validando o criativo e preparando a leitura.' : stage === 1 ? 'Buscando texto, elementos e hierarquia visual.' : stage === 2 ? 'Avaliando mensagem, atenção e adequação por canal.' : 'Consolidando o resultado para sua revisão.';
      const elapsed = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
      progressTimer.value = elapsed;
      progressTimer.textContent = elapsed;
      Array.from(progressSteps.children).forEach((item, index) => item.dataset.state = index < stage ? 'done' : index === stage ? 'current' : 'pending');
    };
    update(); clearInterval(progressInterval); progressInterval = setInterval(update, 1000);
    if (!progress.open) {
      if (typeof progress.showModal === 'function') progress.showModal();
      else progress.setAttribute('open', '');
    }
  }
  function stopProgress() {
    clearInterval(progressInterval); progressInterval = null;
    if (progress?.open) {
      if (typeof progress.close === 'function') progress.close();
      else progress.removeAttribute('open');
    }
  }

  const element = (name, className, text) => {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function card(item) {
    const link = element('a', 'analyzer-card');
    link.href = item.result_url;
    if (item.opens_legacy) link.rel = 'noopener';
    const media = element('div', 'analyzer-card-media');
    if (item.thumbnail && /^(data:image\/|https:\/\/|\/studio\/api\/analyzer\/)/.test(String(item.thumbnail))) {
      const image = document.createElement('img');
      image.src = item.thumbnail;
      image.alt = '';
      image.loading = 'lazy';
      image.addEventListener('error', () => image.remove(), { once: true });
      media.appendChild(image);
    }
    media.appendChild(element('span', 'analyzer-media-type', item.media_type === 'video' ? 'Vídeo' : 'Imagem'));
    if (item.score !== null && item.score !== undefined) media.appendChild(element('b', 'analyzer-score', String(item.score)));
    const body = element('div', 'analyzer-card-body');
    body.appendChild(element('strong', '', item.name || 'Criativo'));
    const meta = [item.creative_type, item.funnel, item.opens_legacy ? 'Acervo anterior' : 'Studio'].filter(Boolean).join(', ');
    body.appendChild(element('small', '', meta));
    link.append(media, body);
    return link;
  }

  function renderHistory() {
    grid.replaceChildren();
    const groups = new Map();
    historyItems.forEach(item => {
      const key = item.opens_legacy ? 'legacy' : (item.project_ref || 'unassigned');
      if (!groups.has(key)) groups.set(key, { name: item.project_name || (key === 'unassigned' ? 'Sem projeto' : 'Acervo anterior'), items: [] });
      groups.get(key).items.push(item);
    });
    groups.forEach(group => {
      const section = element('section', 'analyzer-project-group');
      const heading = element('header');
      heading.append(element('h3', '', group.name), element('span', '', `${group.items.length} ${group.items.length === 1 ? 'análise' : 'análises'}`));
      const shelf = element('div', 'analyzer-grid');
      group.items.forEach(item => shelf.appendChild(card(item)));
      section.append(heading, shelf);
      grid.appendChild(section);
    });
  }

  const value = (object, path, fallback = '—') => {
    let current = object;
    for (const key of path.split('.')) current = current && current[key];
    return current === null || current === undefined || current === '' ? fallback : current;
  };

  const clampCoordinate = value => Math.max(0, Math.min(100, Number(value) || 0));

  function attentionMap(analysis, report) {
    const hierarchy = report.attention_analysis?.visual_hierarchy || {};
    let sequence = Array.isArray(hierarchy.sequence) ? hierarchy.sequence.filter(item => item && item.x != null && item.y != null).slice(0, 8) : [];
    if (!sequence.length && hierarchy.first_fixation_coords) {
      sequence = [{ element: hierarchy.first_fixation || 'Primeira fixação', ...hierarchy.first_fixation_coords }];
    }
    if (!sequence.length || !analysis.thumbnail_url) return null;
    const section = element('section', 'analyzer-attention-map');
    const heading = element('header');
    heading.append(element('h3', '', 'Caminho estimado do olhar'), element('p', '', 'A posição indica a ordem provável de leitura, não rastreamento observado.'));
    const stage = element('figure', 'analyzer-attention-stage');
    const image = document.createElement('img');
    image.src = analysis.thumbnail_url;
    image.alt = `Mapa de atenção de ${analysis.original_name || 'criativo'}`;
    const overlay = element('div', 'analyzer-attention-overlay');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 100 100');
    svg.setAttribute('aria-hidden', 'true');
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', sequence.map(item => `${clampCoordinate(item.x)},${clampCoordinate(item.y)}`).join(' '));
    svg.appendChild(line);
    overlay.appendChild(svg);
    sequence.forEach((item, index) => {
      const marker = element('span', 'analyzer-attention-point', String(index + 1));
      marker.style.left = `${clampCoordinate(item.x)}%`;
      marker.style.top = `${clampCoordinate(item.y)}%`;
      marker.title = item.element || `Fixação ${index + 1}`;
      overlay.appendChild(marker);
    });
    stage.append(image, overlay);
    const list = element('ol', 'analyzer-attention-sequence');
    sequence.forEach(item => list.appendChild(element('li', '', item.element || 'Elemento visual')));
    section.append(heading, stage, list);
    return section;
  }

  function renderResult(analysis) {
    const report = analysis.result_json || {};
    result.replaceChildren();
    const head = element('header');
    const title = element('div');
    title.append(element('h2', '', analysis.original_name || 'Criativo'));
    const actions = element('div', 'analyzer-result-actions');
    const share = shareButton(analysis.public_id, actions);
    const library = element('button', '', 'Adicionar à Biblioteca');
    library.type = 'button';
    library.addEventListener('click', () => sendToLibrary(analysis, library));
    const editor = element('button', '', analysis.media_type === 'video' ? 'Abrir editor de vídeo' : 'Abrir editor de imagem');
    editor.type = 'button';
    editor.addEventListener('click', () => openEditor(analysis, editor));
    actions.append(library, editor, share, element('strong', 'analyzer-result-score', String(value(report, 'score.geral', 0))));
    head.append(title, actions);
    result.appendChild(head);
    const media = element('div', `analyzer-result-media is-${analysis.media_type || 'image'}`);
    if (analysis.media_type === 'video') {
      const video = document.createElement('video');
      video.controls = true;
      video.preload = 'metadata';
      video.src = `/studio/api/analyzer/assets/${encodeURIComponent(analysis.public_id)}/source`;
      media.appendChild(video);
      const strip = element('div', 'analyzer-frame-strip');
      for (let index = 0; index < 4; index += 1) {
        const figure = document.createElement('figure');
        const image = document.createElement('img');
        image.src = `/studio/api/analyzer/assets/${encodeURIComponent(analysis.public_id)}/frame-${index}`;
        image.alt = `Frame ${index + 1} do vídeo`;
        image.loading = 'lazy';
        figure.append(image, element('figcaption', '', `Frame ${index + 1}`));
        strip.appendChild(figure);
      }
      media.appendChild(strip);
    } else if (analysis.thumbnail_url) {
      const image = document.createElement('img');
      image.src = analysis.thumbnail_url;
      image.alt = `Prévia de ${analysis.original_name || 'criativo'}`;
      media.appendChild(image);
    }
    if (media.childElementCount) result.appendChild(media);
    const map = attentionMap(analysis, report);
    if (map) result.appendChild(map);
    const areas = element('div', 'analyzer-result-areas');
    const specs = [
      ['Visão geral', value(report, 'score.explanations.geral', 'Diagnóstico concluído.'), `Clareza ${value(report, 'score.clareza', 0)} / Impacto ${value(report, 'score.impacto_visual', 0)}`],
      ['Atenção e visual', value(report, 'attention_analysis.visual_hierarchy.first_fixation', 'Fixação não identificada'), `Atenção ${value(report, 'attention_analysis.attention_score', 0)} / Hook ${value(report, 'attention_analysis.hook_score', 0)}`],
      ['Mensagem e público', value(report, 'message.value_proposition', 'Proposta não identificada'), value(report, 'audience.life_moment', 'Público em revisão')],
      ['Canais e ação', value(report, 'performance_prediction.best_channel', 'Canal não definido'), `${(report.recommendations || []).length} recomendações`],
    ];
    specs.forEach(([heading, body, meta]) => {
      const area = element('article');
      area.append(element('h3', '', heading), element('p', '', String(body)), element('small', '', String(meta)));
      areas.appendChild(area);
    });
    result.appendChild(areas);
    result.hidden = false;
    result.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }

  async function sourceBlob(analysis) {
    const response = await fetch(`/studio/api/analyzer/assets/${encodeURIComponent(analysis.public_id)}/source`);
    if (!response.ok) throw new Error('Não foi possível ler o arquivo desta análise.');
    return response.blob();
  }

  function dataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Não foi possível preparar a imagem.'));
      reader.readAsDataURL(blob);
    });
  }

  async function transferToLibrary(analysis) {
    if (transferred.has(analysis.public_id)) return transferred.get(analysis.public_id);
    const promise = (async () => {
      const blob = await sourceBlob(analysis);
      let response;
      if (analysis.media_type === 'video') {
        const body = new FormData();
        body.append('client_id', root.dataset.clientId);
        body.append('file', blob, analysis.original_name || 'criativo.mp4');
        response = await fetch(root.dataset.libraryVideoUrl, {
          method: 'POST', body, headers: { Accept: 'application/json', 'X-Trocr-CSRF-Token': root.dataset.csrf },
        });
      } else {
        response = await fetch(root.dataset.libraryStillUrl, {
          method: 'POST',
          headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Trocr-CSRF-Token': root.dataset.csrf },
          body: JSON.stringify({ client_id: root.dataset.clientId, image: await dataUrl(blob), name: analysis.original_name, new_piece: true }),
        });
      }
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.success === false) throw new Error(payload.error || 'Não foi possível adicionar à Biblioteca.');
      return payload.data !== undefined ? payload.data : payload;
    })();
    transferred.set(analysis.public_id, promise);
    try { return await promise; } catch (error) { transferred.delete(analysis.public_id); throw error; }
  }

  async function sendToLibrary(analysis, button) {
    button.disabled = true;
    button.textContent = 'Adicionando…';
    try {
      await transferToLibrary(analysis);
      button.textContent = 'Na Biblioteca';
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message || 'Tentar novamente';
    }
  }

  async function openEditor(analysis, button) {
    button.disabled = true;
    button.textContent = 'Preparando editor…';
    try {
      const item = await transferToLibrary(analysis);
      const target = new URL(analysis.media_type === 'video' ? root.dataset.videoEditorUrl : root.dataset.imageEditorUrl, window.location.origin);
      target.searchParams.set('client', root.dataset.clientId);
      if (analysis.media_type === 'video' && item.id) target.searchParams.set('clip', item.id);
      if (analysis.media_type !== 'video' && item.run_id) target.searchParams.set('run', item.run_id);
      window.location.assign(target.toString());
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message || 'Tentar novamente';
    }
  }

  function shareButton(id, actions) {
    const button = element('button', '', 'Criar link público');
    button.type = 'button';
    button.addEventListener('click', () => createShare(id, actions, button));
    return button;
  }

  async function createShare(id, actions, button) {
    button.disabled = true;
    button.textContent = 'Criando link…';
    try {
      const response = await fetch(root.dataset.detailRoot + encodeURIComponent(id) + root.dataset.shareSuffix, {
        method: 'POST', headers: { Accept: 'application/json', 'X-Trocr-CSRF-Token': root.dataset.csrf },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Não foi possível criar o link.');
      const box = element('div', 'analyzer-share-link');
      const input = document.createElement('input');
      input.readOnly = true;
      input.value = new URL(payload.url, window.location.origin).toString();
      const copy = element('button', '', 'Copiar');
      copy.type = 'button';
      copy.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(input.value); }
        catch (_) { input.select(); document.execCommand('copy'); }
        copy.textContent = 'Copiado';
      });
      const revoke = element('button', '', 'Revogar');
      revoke.type = 'button';
      revoke.addEventListener('click', () => revokeShare(id, actions, box, revoke));
      box.append(input, copy, revoke);
      actions.appendChild(box);
      button.remove();
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message || 'Tentar novamente';
    }
  }

  async function revokeShare(id, actions, box, button) {
    button.disabled = true;
    button.textContent = 'Revogando…';
    const response = await fetch(root.dataset.detailRoot + encodeURIComponent(id) + root.dataset.shareSuffix, {
      method: 'DELETE', headers: { Accept: 'application/json', 'X-Trocr-CSRF-Token': root.dataset.csrf },
    });
    if (!response.ok) {
      button.disabled = false;
      button.textContent = 'Tentar revogar';
      return;
    }
    box.remove();
    actions.prepend(shareButton(id, actions));
  }

  async function loadDetail(id) {
    status.textContent = 'Carregando resultado…';
    const response = await fetch(root.dataset.detailRoot + encodeURIComponent(id), { headers: { Accept: 'application/json' } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'Não foi possível abrir a análise.');
    renderResult(payload.analysis);
  }

  async function load(reset = false) {
    if (historyLoading) return;
    historyLoading = true;
    more.disabled = true;
    if (reset) {
      nextOffset = 0;
      historyItems = [];
      grid.replaceChildren();
    }
    status.hidden = false;
    status.textContent = 'Carregando análises…';
    try {
      const url = new URL(root.dataset.historyUrl, window.location.origin);
      url.searchParams.set('limit', '24');
      url.searchParams.set('offset', String(nextOffset || 0));
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Não foi possível carregar as análises.');
      historyItems.push(...(payload.items || []));
      renderHistory();
      nextOffset = payload.next_offset;
      more.hidden = nextOffset === null || nextOffset === undefined;
      status.textContent = historyItems.length ? `${historyItems.length} análises em ${grid.children.length} projetos ou acervos.` : 'Nenhuma análise encontrada para esta marca.';
    } catch (error) {
      status.textContent = error.message || 'Não foi possível carregar as análises.';
      more.hidden = true;
    } finally {
      historyLoading = false;
      more.disabled = false;
    }
  }

  async function loadProjects() {
    try {
      const response = await fetch(root.dataset.projectsUrl, { headers: { Accept: 'application/json' } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error();
      (payload.items || []).forEach(item => {
        const option = document.createElement('option');
        option.value = item.ref;
        option.textContent = item.name;
        project.appendChild(option);
      });
    } catch (_error) {
      project.disabled = true;
      project.title = 'Projetos indisponíveis neste momento';
    }
  }

  async function loadOperationalStatus() {
    if (!root.dataset.statusUrl) return;
    try {
      const response = await fetch(root.dataset.statusUrl, { headers: { Accept: 'application/json' } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) return;
      const submit = form.querySelector('button[type="submit"]');
      const estimates = payload.credit_estimates || {};
      file.addEventListener('change', () => {
        const media = String(file.files?.[0]?.type || '').startsWith('video/') ? 'video' : 'image';
        const estimate = Number(estimates[media] || 0);
        submit.dataset.defaultLabel = estimate ? `Analisar criativo · até ${estimate.toLocaleString('pt-BR')} créditos` : 'Analisar criativo';
        if (!uploadLoading) submit.textContent = submit.dataset.defaultLabel;
      });
      if (payload.writes_enabled !== false) return;
      submit.disabled = true;
      submit.textContent = 'Novas análises pausadas';
      status.hidden = false;
      status.textContent = 'O acervo continua disponível. O processamento novo está temporariamente pausado.';
    } catch (_error) {
      /* A telemetria não bloqueia a ferramenta quando está indisponível. */
    }
  }

  more.addEventListener('click', () => load(false));
  document.addEventListener('cadu:brand-change', () => load(true));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!file.files.length || uploadLoading) return;
    uploadLoading = true;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = 'Analisando…';
    startProgress(String(file.files[0]?.type || '').startsWith('video/') ? 'video' : 'image');
    status.hidden = false;
    status.textContent = 'Lendo textos, composição e atenção. Isso pode levar alguns minutos.';
    try {
      const response = await fetch(root.dataset.createUrl, {
        method: 'POST', body: new FormData(form),
        headers: { Accept: 'application/json', 'X-Trocr-CSRF-Token': root.dataset.csrf },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Não foi possível analisar a imagem.');
      renderResult(payload.analysis);
      history.replaceState({}, '', `/analyzer/${payload.analysis.public_id}`);
      form.reset();
      load(true);
    } catch (error) {
      status.textContent = error.message || 'Não foi possível analisar a imagem.';
    } finally {
      stopProgress();
      uploadLoading = false;
      button.disabled = false;
      button.textContent = button.dataset.defaultLabel || 'Analisar criativo';
    }
  });
  loadProjects();
  loadOperationalStatus();
  load(true);
  if (root.dataset.analysisId) loadDetail(root.dataset.analysisId).catch(error => { status.textContent = error.message; });
})();
