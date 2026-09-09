(() => {
  'use strict';

  const root = document.querySelector('[data-typed-items]');
  if (!root) return;

  const apiBase = root.dataset.apiBase;
  const list = root.querySelector('[data-items-list]');
  const status = root.querySelector('[data-items-status]');
  const dialog = document.querySelector('[data-item-dialog]');
  const form = dialog?.querySelector('[data-item-form]');
  const confirmDialog = document.querySelector('[data-item-confirm]');
  const fieldDefinitions = JSON.parse(document.getElementById('cotacao-campos-item')?.textContent || '[]');
  let items = JSON.parse(document.getElementById('cotacao-itens-iniciais')?.textContent || '[]');

  const money = (value) => Number(value || 0).toLocaleString('pt-BR', {
    style: 'currency', currency: 'BRL'
  });
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  function setStatus(message = '', kind = '') {
    status.textContent = message;
    status.dataset.kind = kind;
  }

  function render() {
    const total = items.reduce((sum, item) => sum + Number(item.subtotal ?? (item.quantidade * item.valor_unitario)), 0);
    document.querySelectorAll('[data-item-count]').forEach((node) => { node.textContent = items.length; });
    document.querySelectorAll('[data-items-total]').forEach((node) => { node.textContent = money(total); });

    if (!items.length) {
      list.innerHTML = `
        <div class="cot-items-empty">
          <i class="fa-regular fa-rectangle-list" aria-hidden="true"></i>
          <strong>Nenhuma entrega adicionada</strong>
          <span>Comece a montagem definindo a primeira entrega comercial.</span>
          <button type="button" class="cx-btn cx-btn-primary" data-add-item>Adicionar entrega</button>
        </div>`;
      return;
    }

    list.innerHTML = items.map((item, index) => {
      const metadata = fieldDefinitions
        .map(([key, label]) => item.metadata?.[key]
          ? `<span><b>${escapeHtml(label)}</b>${escapeHtml(item.metadata[key])}</span>` : '')
        .join('');
      return `
        <article class="cot-item-row" data-item-id="${Number(item.id)}">
          <div class="cot-item-order">
            <button type="button" data-action="up" ${index === 0 ? 'disabled' : ''} aria-label="Mover para cima"><i class="fa-solid fa-chevron-up"></i></button>
            <button type="button" data-action="down" ${index === items.length - 1 ? 'disabled' : ''} aria-label="Mover para baixo"><i class="fa-solid fa-chevron-down"></i></button>
          </div>
          <div class="cot-item-content">
            <strong>${escapeHtml(item.titulo)}</strong>
            <p>${escapeHtml(item.descricao || 'Sem descrição.')}</p>
            <div class="cot-item-metadata">${metadata}</div>
          </div>
          <div class="cot-item-values">
            <span>${escapeHtml(item.quantidade)} × ${money(item.valor_unitario)}</span>
            <strong>${money(item.subtotal)}</strong>
          </div>
          <div class="cot-item-actions">
            <button type="button" data-action="edit" aria-label="Editar"><i class="fa-solid fa-pen"></i></button>
            <button type="button" data-action="delete" aria-label="Excluir"><i class="fa-solid fa-trash"></i></button>
          </div>
        </article>`;
    }).join('');
  }

  async function request(url, options = {}) {
    setStatus('Salvando alterações…', 'loading');
    const response = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) {
      throw new Error(result.error || 'Não foi possível concluir a alteração.');
    }
    if (result.data) items = result.data;
    render();
    setStatus('Alterações salvas.', 'success');
    return result;
  }

  function openItem(item = null) {
    form.reset();
    form.elements.item_id.value = item?.id || '';
    form.elements.titulo.value = item?.titulo || '';
    form.elements.descricao.value = item?.descricao || '';
    form.elements.quantidade.value = item?.quantidade || 1;
    form.elements.valor_unitario.value = item?.valor_unitario || 0;
    fieldDefinitions.forEach(([key]) => {
      form.elements[`meta_${key}`].value = item?.metadata?.[key] || '';
    });
    dialog.querySelector('[data-dialog-title]').textContent = item ? 'Editar entrega' : 'Nova entrega';
    dialog.showModal();
    form.elements.titulo.focus();
  }

  async function reorder(index, direction) {
    const destination = index + direction;
    if (destination < 0 || destination >= items.length) return;
    [items[index], items[destination]] = [items[destination], items[index]];
    render();
    await request(`${apiBase}/reordenar`, {
      method: 'PUT',
      body: JSON.stringify({ item_ids: items.map((item) => item.id) })
    });
  }

  function confirmDelete() {
    return new Promise((resolve) => {
      const handleClose = () => resolve(confirmDialog.returnValue === 'confirm');
      confirmDialog.addEventListener('close', handleClose, { once: true });
      confirmDialog.showModal();
    });
  }

  document.addEventListener('click', (event) => {
    const add = event.target.closest('[data-add-item]');
    if (add) openItem();
  });

  list.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action]');
    const row = event.target.closest('[data-item-id]');
    if (!button || !row) return;
    const index = items.findIndex((item) => Number(item.id) === Number(row.dataset.itemId));
    if (index < 0) return;
    try {
      if (button.dataset.action === 'edit') openItem(items[index]);
      if (button.dataset.action === 'up') await reorder(index, -1);
      if (button.dataset.action === 'down') await reorder(index, 1);
      if (button.dataset.action === 'delete' && await confirmDelete()) {
        await request(`${apiBase}/${items[index].id}`, { method: 'DELETE' });
      }
    } catch (error) {
      setStatus(error.message, 'error');
      render();
    }
  });

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const itemId = form.elements.item_id.value;
    const metadata = {};
    fieldDefinitions.forEach(([key]) => { metadata[key] = form.elements[`meta_${key}`].value; });
    const payload = {
      titulo: form.elements.titulo.value,
      descricao: form.elements.descricao.value,
      quantidade: form.elements.quantidade.value,
      valor_unitario: form.elements.valor_unitario.value,
      metadata
    };
    try {
      await request(itemId ? `${apiBase}/${itemId}` : apiBase, {
        method: itemId ? 'PUT' : 'POST',
        body: JSON.stringify(payload)
      });
      dialog.close();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  render();
})();
