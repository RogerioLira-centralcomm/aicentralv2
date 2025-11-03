document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('contatosSearch');
  const setorSelect = document.getElementById('filtroSetor');
  const cargoSelect = document.getElementById('filtroCargo');
  const ordenarSelect = document.getElementById('ordenarPor');

  const table = document.querySelector('table');
  const tbody = table ? table.querySelector('tbody') : null;
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll('tr'));

  // Popular filtros com opções únicas a partir das linhas
  function populateFilters() {
    const setores = new Set();
    const cargos = new Set();
    rows.forEach(tr => {
      const s = (tr.dataset.setor || '').trim();
      const c = (tr.dataset.cargo || '').trim();
      if (s) setores.add(s);
      if (c) cargos.add(c);
    });

    // Preencher Setor
    const setorCurrent = setorSelect.value;
    setorSelect.innerHTML = '<option value="">Todos os setores</option>';
    Array.from(setores).sort().forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = capitalize(v);
      setorSelect.appendChild(opt);
    });
    setorSelect.value = setorCurrent;

    // Preencher Cargo (poderia ser dependente do setor, mas mantemos geral aqui)
    const cargoCurrent = cargoSelect.value;
    cargoSelect.innerHTML = '<option value="">Todos os cargos</option>';
    Array.from(cargos).sort().forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = capitalize(v);
      cargoSelect.appendChild(opt);
    });
    cargoSelect.value = cargoCurrent;
  }

  function capitalize(text) {
    if (!text) return '';
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function normalize(text) {
    return (text || '').toString().toLowerCase();
  }

  function applyFilters() {
    const query = normalize(searchInput ? searchInput.value : '');
    const setor = normalize(setorSelect ? setorSelect.value : '');
    const cargo = normalize(cargoSelect ? cargoSelect.value : '');

    rows.forEach(tr => {
      const nome = tr.dataset.nome || '';
      const email = tr.dataset.email || '';
      const tel = tr.dataset.telefone || '';
      const s = tr.dataset.setor || '';
      const c = tr.dataset.cargo || '';

      const matchesSearch = !query || nome.includes(query) || email.includes(query) || tel.includes(query);
      const matchesSetor = !setor || s === setor;
      const matchesCargo = !cargo || c === cargo;

      tr.style.display = (matchesSearch && matchesSetor && matchesCargo) ? '' : 'none';
    });
  }

  function applySort() {
    const criteria = ordenarSelect ? ordenarSelect.value : 'nome';
    const visibleRows = rows.filter(tr => tr.style.display !== 'none');

    visibleRows.sort((a, b) => {
      switch (criteria) {
        case 'setor':
          return (a.dataset.setor || '').localeCompare(b.dataset.setor || '');
        case 'cargo':
          return (a.dataset.cargo || '').localeCompare(b.dataset.cargo || '');
        case 'status':
          // Ativo (1) antes de Inativo (0)
          return Number(b.dataset.status || 0) - Number(a.dataset.status || 0);
        case 'nome':
        default:
          return (a.dataset.nome || '').localeCompare(b.dataset.nome || '');
      }
    });

    // Reaplicar a ordem no DOM, mantendo linhas ocultas no final
    visibleRows.forEach(tr => tbody.appendChild(tr));
    // Anexar também as ocultas (para manter DOM consistente)
    rows.filter(tr => tr.style.display === 'none').forEach(tr => tbody.appendChild(tr));
  }

  // Eventos
  if (searchInput) searchInput.addEventListener('input', () => { applyFilters(); applySort(); });
  if (setorSelect) setorSelect.addEventListener('change', () => { applyFilters(); applySort(); });
  if (cargoSelect) cargoSelect.addEventListener('change', () => { applyFilters(); applySort(); });
  if (ordenarSelect) ordenarSelect.addEventListener('change', applySort);

  // Inicialização
  populateFilters();
  applyFilters();
  applySort();
});
