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
  let busy = false;

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

  function setBusy(value) {
    busy = value;
    root.setAttribute('aria-busy', value ? 'true' : 'false');
    document.querySelectorAll('[data-save-item], [data-add-item], [data-action]').forEach((button) => {
      if (value) {
        button.dataset.busyDisabled = 'true';
        button.dataset.busyWasDisabled = button.disabled ? 'true' : 'false';
        button.disabled = true;
      } else if (button.dataset.busyDisabled === 'true') {
        button.disabled = button.dataset.busyWasDisabled === 'true';
        delete button.dataset.busyDisabled;
        delete button.dataset.busyWasDisabled;
      }
    });
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
    if (busy) throw new Error('Aguarde a alteração atual terminar.');
    setBusy(true);
    setStatus('Salvando alterações…', 'loading');
    try {
      const response = await fetch(url, {
        ...options,
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...(options.headers || {})
        }
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Não foi possível concluir a alteração.');
      }
      if (Array.isArray(result.data)) items = result.data;
      render();
      setStatus('Alterações salvas.', 'success');
      return result;
    } finally {
      setBusy(false);
    }
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
    const previousItems = items.slice();
    [items[index], items[destination]] = [items[destination], items[index]];
    render();
    try {
      await request(`${apiBase}/reordenar`, {
        method: 'PUT',
        body: JSON.stringify({ item_ids: items.map((item) => item.id) })
      });
    } catch (error) {
      items = previousItems;
      render();
      throw error;
    }
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
    if (!button || !row || busy) return;
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
    if (busy || !form.reportValidity()) return;
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

  const sectionLinks = Array.from(document.querySelectorAll('.cot-workspace-sidebar nav a[href^="#"]'));
  if ('IntersectionObserver' in window && sectionLinks.length) {
    const sections = sectionLinks
      .map((link) => document.querySelector(link.getAttribute('href')))
      .filter(Boolean);
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      sectionLinks.forEach((link) => {
        const active = link.getAttribute('href') === `#${visible.target.id}`;
        link.classList.toggle('is-active', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }, { rootMargin: '-20% 0px -65% 0px', threshold: [0, 0.25, 0.6] });
    sections.forEach((section) => observer.observe(section));
  }

  render();
})();
