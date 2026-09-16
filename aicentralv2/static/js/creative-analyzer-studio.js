(() => {
  const root = document.getElementById('creativeAnalyzer');
  if (!root) return;
  const grid = document.getElementById('analyzerGrid');
  const status = document.getElementById('analyzerStatus');
  const more = document.getElementById('analyzerMore');
  const form = document.getElementById('analyzerUpload');
  const file = document.getElementById('analyzerFile');
  const result = document.getElementById('analyzerResult');
  let nextOffset = 0;
  let historyLoading = false;
  let uploadLoading = false;

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
    if (item.thumbnail && String(item.thumbnail).startsWith('data:image/')) {
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

  const value = (object, path, fallback = '—') => {
    let current = object;
    for (const key of path.split('.')) current = current && current[key];
    return current === null || current === undefined || current === '' ? fallback : current;
  };

  function renderResult(analysis) {
    const report = analysis.result_json || {};
    result.replaceChildren();
    const head = element('header');
    const title = element('div');
    title.append(element('p', 'analyzer-section-note', 'Resultado da análise'), element('h2', '', analysis.original_name || 'Criativo'));
    head.append(title, element('strong', 'analyzer-result-score', String(value(report, 'score.geral', 0))));
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
      (payload.items || []).forEach(item => grid.appendChild(card(item)));
      nextOffset = payload.next_offset;
      more.hidden = nextOffset === null || nextOffset === undefined;
      status.textContent = grid.children.length ? `${grid.children.length} análises carregadas.` : 'Nenhuma análise encontrada para esta marca.';
    } catch (error) {
      status.textContent = error.message || 'Não foi possível carregar as análises.';
      more.hidden = true;
    } finally {
      historyLoading = false;
      more.disabled = false;
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
      uploadLoading = false;
      button.disabled = false;
      button.textContent = 'Analisar criativo';
    }
  });
  load(true);
  if (root.dataset.analysisId) loadDetail(root.dataset.analysisId).catch(error => { status.textContent = error.message; });
})();
