(() => {
  const menu = document.querySelector('.skills-topbar__menu');
  const nav = document.querySelector('.skills-topbar__links');
  if (menu && nav) {
    menu.addEventListener('click', () => {
      const open = nav.classList.toggle('is-open');
      menu.setAttribute('aria-expanded', String(open));
    });
  }

  const productSwitch = document.querySelector('.skills-solutions');
  document.addEventListener('click', (event) => {
    if (productSwitch?.open && !productSwitch.contains(event.target)) productSwitch.open = false;
  });
  productSwitch?.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') productSwitch.open = false;
  });

  const normalize = (value) => (value || '')
    .toLocaleLowerCase('pt-BR')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  const searchForm = document.querySelector('.skills-topbar__search');
  const searchInput = searchForm?.querySelector('input[name="q"]');
  const methods = [...document.querySelectorAll('[data-skills-method]')];
  const searchEmpty = document.querySelector('[data-skills-search-empty]');
  const renderSearch = (query) => {
    if (!methods.length) return;
    const term = normalize(query.trim());
    let visible = 0;
    methods.forEach((method) => {
      const matches = !term || normalize(method.dataset.searchText).includes(term);
      method.hidden = !matches;
      if (matches) visible += 1;
    });
    if (searchEmpty) searchEmpty.hidden = visible !== 0;
  };
  if (methods.length) {
    const initialQuery = new URLSearchParams(window.location.search).get('q') || '';
    if (searchInput) searchInput.value = initialQuery;
    renderSearch(initialQuery);
  }
  searchForm?.addEventListener('submit', (event) => {
    if (!methods.length || !searchInput) return;
    event.preventDefault();
    const query = searchInput.value.trim();
    const url = new URL(window.location.href);
    if (query) url.searchParams.set('q', query);
    else url.searchParams.delete('q');
    url.hash = 'metodos';
    window.history.replaceState({}, '', url);
    renderSearch(query);
    document.getElementById('metodos')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  const cards = {
    briefing: ['Briefing', 'Transforme objetivos dispersos em um ponto de partida claro.', 'objetivo, público, restrições', 'briefing de trabalho'],
    publico: ['Público', 'Entenda quem importa antes de definir uma resposta.', 'público, sinais, contexto', 'leitura de audiência'],
    planejamento: ['Planejamento', 'Escolha os canais certos antes de dividir o orçamento.', 'objetivo, público, verba', 'matriz de canais'],
    ativacao: ['Ativação', 'Coloque a decisão em movimento e acompanhe o que aprende.', 'plano, canais, responsáveis', 'roteiro de ativação'],
  };
  const recommendation = document.querySelector('[data-skills-recommendation]');
  document.querySelectorAll('[data-skills-journey] [data-stage]').forEach((stop) => {
    stop.addEventListener('click', () => {
      document.querySelectorAll('[data-skills-journey] [data-stage]').forEach((item) => item.classList.toggle('is-active', item === stop));
      const value = cards[stop.dataset.stage];
      if (!recommendation || !value) return;
      recommendation.querySelector('p').textContent = value[0];
      recommendation.querySelector('h2').textContent = value[1];
      recommendation.querySelector('dt').textContent = 'Insumos';
      recommendation.querySelector('dd').textContent = value[2];
      recommendation.querySelectorAll('dt')[1].textContent = 'Entrega';
      recommendation.querySelectorAll('dd')[1].textContent = value[3];
    });
  });
})();
