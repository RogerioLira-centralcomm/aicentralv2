/* Read-only catalog detail. All provider and catalog text uses textContent. */
(() => {
  'use strict';
  const dialog = document.getElementById('planner-catalog-dialog');
  const content = document.getElementById('planner-catalog-dialog-content');
  if (!dialog || !content) return;
  let opener = null;
  const close = () => { dialog.close(); opener?.focus(); };
  dialog.querySelector('[data-catalog-close]').addEventListener('click', close);
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  const row = (label, value) => {
    if (value === null || value === undefined || value === '') return null;
    const item = document.createElement('div'), term = document.createElement('dt'), description = document.createElement('dd');
    term.textContent = label; description.textContent = value; item.append(term, description); return item;
  };
  document.querySelectorAll('[data-catalog-kind][data-catalog-id]').forEach(button => button.addEventListener('click', async () => {
    opener = button; content.replaceChildren(Object.assign(document.createElement('p'), {textContent: 'Carregando detalhes…'})); dialog.showModal();
    try {
      const response = await fetch('/familia/api/planner/catalog/' + encodeURIComponent(button.dataset.catalogKind) + '/' + encodeURIComponent(button.dataset.catalogId), {credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível carregar os detalhes.');
      dialog.querySelector('h2').textContent = data.record.name || 'Detalhes do catálogo';
      const list = document.createElement('dl');
      [['Descrição', data.record.description], ['Categoria', data.record.category], ['Alcance', data.record.audience], ['Dimensões', data.record.dimensions], ['Arquivos aceitos', data.record.files]].forEach(([label, value]) => { const item = row(label, value); if (item) list.append(item); });
      content.replaceChildren(list.childElementCount ? list : Object.assign(document.createElement('p'), {textContent: 'Não há detalhes adicionais para este item.'}));
    } catch (error) { content.replaceChildren(Object.assign(document.createElement('p'), {textContent: error.message})); }
  }));
})();
