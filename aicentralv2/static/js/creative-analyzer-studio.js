(() => {
  const root = document.getElementById('creativeAnalyzer');
  if (!root) return;
  const grid = document.getElementById('analyzerGrid');
  const status = document.getElementById('analyzerStatus');
  const more = document.getElementById('analyzerMore');
  let nextOffset = 0;
  let loading = false;

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

  async function load(reset = false) {
    if (loading) return;
    loading = true;
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
      loading = false;
      more.disabled = false;
    }
  }

  more.addEventListener('click', () => load(false));
  document.addEventListener('cadu:brand-change', () => load(true));
  load(true);
})();
