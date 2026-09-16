document.addEventListener('DOMContentLoaded', () => {
  const normalize = value => (value || '').toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const show = (node, value) => { node.textContent = value || ''; node.hidden = !value; };
  const copyText = async value => {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const field = document.createElement('textarea');
    field.value = value; field.setAttribute('readonly', ''); field.style.position = 'fixed'; field.style.opacity = '0';
    document.body.appendChild(field); field.select();
    const copied = document.execCommand('copy'); field.remove();
    if (!copied) throw new Error('copy unavailable');
  };
  const catalog = document.querySelector('[data-catalog]');
  if (catalog) {
    const search = catalog.querySelector('[data-search]');
    const input = search.querySelector('input');
    const rows = [...catalog.querySelectorAll('[data-item]')];
    const empty = catalog.querySelector('[data-empty]');
    const title = catalog.querySelector('[data-catalog-title]');
    const eyebrow = catalog.querySelector('[data-catalog-eyebrow]');
    const summary = catalog.querySelector('[data-catalog-summary]');
    const activeFilter = catalog.querySelector('[data-active-filter]');
    const activeFilterText = activeFilter.querySelector('span');
    const labels = {
      market: ['Curadoria de mercado', 'Top 10 para conhecer', 'Capacidades relevantes para comunicação, conteúdo, dados e crescimento.'],
      official: ['Inteligência proprietária', 'Família oficial Cadu', 'Especialistas instaláveis que conectam planejamento, canais, audiências e formatos.'],
      directory: ['Diretório de referências', 'Todas as referências', 'Capacidades disponíveis para consulta e comparação.'],
      all: ['Catálogo completo', 'Encontre a skill para a tarefa', 'Compare resultados, método e acesso antes de abrir uma skill.'],
    };
    const params = new URLSearchParams(window.location.search);
    let state = {query: params.get('q') || '', category: params.get('category') || '', collection: params.get('collection') || 'all'};
    input.value = state.query;
    const updateUrl = () => {
      const next = new URLSearchParams();
      if (state.query) next.set('q', state.query);
      if (state.category) next.set('category', state.category);
      if (state.collection && state.collection !== 'all') next.set('collection', state.collection);
      const suffix = next.toString(); window.history.replaceState({}, '', `${window.location.pathname}${suffix ? `?${suffix}` : ''}${window.location.hash}`);
    };
    const collectionMatch = (row, collection) => collection === 'all' || row.dataset.collection.split(' ').includes(collection);
    const render = () => {
      const query = normalize(state.query); let visible = 0;
      rows.forEach(row => {
        const showRow = normalize(row.dataset.text).includes(query) && (!state.category || row.dataset.category === state.category) && collectionMatch(row, state.collection);
        row.hidden = !showRow; if (showRow) visible += 1;
      });
      catalog.querySelectorAll('[data-table-group]').forEach(group => {
        group.hidden = ![...group.querySelectorAll('[data-item]')].some(row => !row.hidden);
      });
      catalog.querySelectorAll('[data-collection-link]').forEach(link => link.classList.toggle('is-active', link.dataset.collectionLink === state.collection));
      catalog.querySelectorAll('[data-category-link]').forEach(link => link.classList.toggle('is-active', link.dataset.categoryLink === state.category));
      const [eyebrowText, titleText, summaryText] = labels[state.collection] || labels.all;
      eyebrow.textContent = state.category ? 'Categoria' : eyebrowText;
      title.textContent = state.category || titleText;
      summary.textContent = state.category ? `${visible} skill${visible === 1 ? '' : 's'} para comparar nesta categoria.` : summaryText;
      const filterName = state.category || (state.collection !== 'all' ? titleText : '');
      activeFilter.hidden = !filterName; activeFilterText.textContent = filterName;
      empty.hidden = visible > 0; updateUrl();
    };
    search.addEventListener('submit', event => { event.preventDefault(); state.query = input.value.trim(); render(); });
    input.addEventListener('input', () => { state.query = input.value.trim(); render(); });
    catalog.querySelectorAll('[data-collection-link]').forEach(link => link.addEventListener('click', () => { state.collection = link.dataset.collectionLink; state.category = ''; render(); }));
    catalog.querySelectorAll('[data-category-link]').forEach(link => link.addEventListener('click', () => { state.category = link.dataset.categoryLink; state.collection = 'all'; render(); }));
    catalog.querySelector('[data-active-filter] button')?.addEventListener('click', () => { state = {query: '', category: '', collection: 'all'}; input.value = ''; render(); });
    catalog.querySelector('[data-clear-search]')?.addEventListener('click', () => { state = {query: '', category: '', collection: 'all'}; input.value = ''; render(); });
    render();
  }
  document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {
    const composer = document.querySelector('[data-public-composer], [data-composer]');
    if (composer) { composer.value = button.textContent.trim(); composer.focus(); }
  }));
  document.querySelectorAll('[data-copy-value]').forEach(button => button.addEventListener('click', async () => {
    const original = button.dataset.copyLabel || button.textContent;
    try {
      await copyText(button.dataset.copyValue || ''); button.textContent = 'Copiado';
    } catch (_) { button.textContent = 'Não foi possível copiar'; }
    window.setTimeout(() => { button.textContent = original; }, 1800);
  }));
  const runButton = document.querySelector('[data-run]');
  runButton?.addEventListener('click', async () => {
    const answer = document.querySelector('[data-message]'); runButton.disabled = true; show(answer, 'Executando e verificando créditos…');
    try {
      const response = await fetch(runButton.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:document.querySelector('[data-composer]').value})});
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível executar.');
      show(answer, `${body.answer}\n\n${body.charged_credits} crédito(s) utilizado(s). Saldo: ${body.remaining_credits}.`);
    } catch (error) { show(answer, error.message); } finally { runButton.disabled = false; }
  });
  const sharedForm = document.querySelector('[data-shared-run]');
  sharedForm?.addEventListener('submit', async event => {
    event.preventDefault(); const button = sharedForm.querySelector('button[type="submit"]'), status = sharedForm.querySelector('[data-run-status]'), answer = sharedForm.querySelector('[data-run-answer]');
    button.disabled = true; status.textContent = 'Executando e verificando créditos…'; answer.hidden = true;
    try {
      const response = await fetch(sharedForm.dataset.url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:sharedForm.querySelector('textarea').value})});
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Não foi possível executar.');
      status.textContent = `${body.charged_credits} crédito(s) utilizado(s). Saldo: ${body.remaining_credits}.`; show(answer, body.answer);
    } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  });
});
