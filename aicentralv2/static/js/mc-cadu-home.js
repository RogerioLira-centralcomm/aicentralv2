(function () {
  const app = document.querySelector('.mc-studio-home');
  if (!app || !window.McStudioLibrary) return;
  const $ = id => document.getElementById(id);
  const list = $('studioItems');
  const status = $('studioStatus');
  const errors = $('studioErrors');
  const search = $('studioSearch');
  const more = $('studioMore');
  const store = window.McStudioLibrary.createStore(get, render);
  const brandLinks = Array.from(app.querySelectorAll('[data-brand-link]'));
  brandLinks.forEach(link => { link.dataset.baseHref = link.getAttribute('href'); });

  function sync(event) {
    const select = $('mcCaduBarClient');
    const clientId = String(event.detail?.clientId || '');
    const context = event.detail?.error ? 'error' : clientId ? 'ready' : 'empty';
    $('studioBrandName').textContent = context === 'error' ? 'Marcas indisponíveis' : clientId ? select?.selectedOptions[0]?.textContent || 'Marca selecionada' : 'Selecione ou cadastre uma marca';
    if (store.state.clientId !== clientId || store.state.context !== context) search.value = '';
    brandLinks.forEach(link => {
      const url = new URL(link.dataset.baseHref, window.location.origin);
      if (clientId) url.searchParams.set('client', clientId);
      link.href = url.pathname + url.search;
    });
    store.context(clientId, context);
  }
  document.addEventListener('cadu:brand-ready', sync);
  document.addEventListener('cadu:brand-change', sync);
  // Navigation owns initial context validation; never fetch using stale storage here.
  if (window.McCaduContext) sync({ detail: window.McCaduContext });
  app.querySelectorAll('[data-media]').forEach(button => button.addEventListener('click', () => store.filter(button.dataset.media)));
  search.addEventListener('input', () => store.search(search.value));
  more.addEventListener('click', () => store.more());
  $('studioRefresh').addEventListener('click', () => {
    if (store.state.context === 'error') document.dispatchEvent(new CustomEvent('cadu:context-retry'));
    else store.retry();
  });

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }
  function render(state) {
    const view = store.view();
    list.replaceChildren();
    errors.replaceChildren();
    more.hidden = view.items.length >= view.total;
    list.setAttribute('aria-busy', String(view.loading));
    app.querySelectorAll('[data-media]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.media === state.media)));
    if (state.context !== 'ready' || !state.clientId) {
      const text = state.context === 'loading' ? 'Carregando contexto da marca…' : state.context === 'error' ? 'Não foi possível carregar as marcas. Use Atualizar para tentar novamente.' : 'Nenhuma marca disponível. Cadastre uma marca para começar.';
      status.textContent = text;
      if (state.context === 'loading') skeleton();
      else empty('Sua produção começa com uma marca', text, app.dataset.brandManageUrl || '/workspace/app/marcas', 'Gerenciar marcas');
      return;
    }
    view.errors.forEach(media => {
      const box = node('div', 'studio-error');
      box.setAttribute('role', 'alert');
      box.append(node('span', '', `Não foi possível carregar ${media === 'video' ? 'os vídeos' : 'as imagens'} desta marca.`));
      const retry = node('button', 'studio-button', 'Tentar novamente');
      retry.type = 'button';
      retry.addEventListener('click', () => store.retry(media));
      box.append(retry); errors.append(box);
    });
    status.textContent = view.loading ? 'Carregando biblioteca da marca…' : `${view.items.length} de ${view.total} resultado(s)${state.query ? ' para esta busca' : ''}.${view.errors.length ? ' Biblioteca parcialmente indisponível.' : ' Busca em toda a biblioteca da marca.'}`;
    view.items.forEach(item => list.append(card(item, state.clientId)));
    if (view.loading) skeleton();
    else if (!view.total && !view.errors.length) {
      empty(state.query ? 'Nenhum resultado encontrado' : 'Ainda não há conteúdo nesta seleção', state.query ? 'Tente outro nome, texto ou formato.' : 'Comece ajustando uma peça ou montando um vídeo com as cenas da biblioteca.', state.query ? null : brandLinks[0]?.href, 'Ajustar peça');
    }
  }
  function skeleton() {
    for (let i = 0; i < 3; i++) { const item = node('li', 'studio-skeleton'); item.setAttribute('aria-hidden', 'true'); list.append(item); }
  }
  function empty(title, description, href, label) {
    const item = node('li', 'studio-empty');
    item.append(node('strong', '', title), node('p', '', description));
    if (href) { const link = node('a', 'studio-button', label); link.href = href; item.append(link); }
    list.append(item);
  }
  function safeImage(value) {
    if (!value) return '';
    try { const url = new URL(value, window.location.origin); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; } catch (_) { return ''; }
  }
  function card(item, clientId) {
    const li = node('li', 'studio-card');
    const link = node('a');
    const params = new URLSearchParams({ run: String(item.run_id || ''), client: clientId });
    if (item.media === 'video') params.set('clip', String(item.id || ''));
    link.href = `/studio/modelagem-criativos/${item.media === 'video' ? 'video' : 'trocar'}?${params}`;
    const thumb = node('div', 'studio-thumb');
    const src = safeImage(item.thumb_url || item.poster_url || item.image_url);
    const fallback = node('span', '', 'Prévia indisponível');
    thumb.append(fallback);
    if (src && !item.broken) {
      const image = node('img'); image.alt = ''; image.loading = 'lazy'; image.decoding = 'async'; image.width = 480; image.height = 300;
      fallback.hidden = true;
      image.addEventListener('error', () => { image.remove(); fallback.hidden = false; });
      image.src = src; thumb.append(image);
    }
    const body = node('div', 'studio-card-body');
    const title = String(item.headline || item.name || item.title || (item.media === 'video' ? 'Clipe' : 'Peça'));
    const strong = node('strong', '', title); strong.title = title;
    const meta = node('div', 'studio-card-meta');
    const ratio = /^\d{1,4}:\d{1,4}$/.test(String(item.aspect_ratio)) ? item.aspect_ratio : 'Formato não informado';
    meta.append(node('span', 'studio-kind', item.media === 'video' ? 'Vídeo' : 'Imagem'), node('span', '', ratio));
    body.append(strong, meta);
    const rawDate = String(item.created_at || '');
    const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? `${rawDate}T12:00:00` : rawDate);
    if (item.created_at && Number.isFinite(date.getTime())) {
      const time = node('time', '', date.toLocaleDateString('pt-BR')); time.dateTime = date.toISOString(); body.append(time);
    }
    link.append(thumb, body); li.append(link); return li;
  }
  async function get(url, options) {
    const response = await fetch(url, { ...options, credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok || payload.success === false) throw new Error('Falha na leitura');
    return payload.data !== undefined ? payload.data : payload;
  }
})();
