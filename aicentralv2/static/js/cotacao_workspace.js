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
  const workspaceMeta = JSON.parse(document.getElementById('cotacao-workspace-meta')?.textContent || '{}');
  const itemLabel = workspaceMeta.item_label || 'entrega';
  const workspaceType = document.querySelector('[data-workspace-type]')?.dataset.workspaceType || '';
  const legacyMetadataLabels = {
    fonte: 'Fonte (legado)',
    periodo_uso: 'Período de uso (legado)',
  };
  let items = JSON.parse(document.getElementById('cotacao-itens-iniciais')?.textContent || '[]');
  let busy = false;

  const money = (value) => Number(value || 0).toLocaleString('pt-BR', {
    style: 'currency', currency: 'BRL'
  });
  const parseMoedaBr = (valor) => {
    if (!valor) return 0;
    if (typeof valor === 'number') return valor;
    return parseFloat(String(valor).replace(/\./g, '').replace(',', '.')) || 0;
  };
  const formatMoedaDigits = (valor) => Number(valor || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const formatDateBr = (iso) => {
    const raw = String(iso || '').slice(0, 10);
    const parts = raw.split('-');
    if (parts.length !== 3) return raw;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  };
  const formatMetadataValue = (key, value) => {
    if (key === 'data_inicio' || key === 'data_fim') return formatDateBr(value);
    return String(value ?? '');
  };

  function setStatus(message = '', kind = '') {
    status.textContent = message;
    status.dataset.kind = kind;
  }

  function collectPlataformasItens() {
    const seen = new Set();
    const out = [];
    items.forEach((item) => {
      const nome = String(item.metadata?.plataforma_campanha || '').trim();
      if (!nome || seen.has(nome)) return;
      seen.add(nome);
      out.push(nome);
    });
    return out;
  }

  function updateDadosPlatformBadge() {
    if (workspaceType !== 'dados') return;
    const badge = document.querySelector('[data-dados-plataforma-badge]');
    if (!badge) return;
    const plats = collectPlataformasItens();
    const trilhaRotulo = (badge.dataset.trilhaRotulo || '').trim();
    const trilhaSuffix = trilhaRotulo
      ? ` <span>· Trilha ${escapeHtml(trilhaRotulo)}</span>`
      : '';
    badge.classList.toggle('is-missing', !plats.length);
    if (!plats.length) {
      badge.innerHTML = 'Defina a <strong>plataforma de dados</strong> em cada segmento na montagem.';
      const sideRow = document.querySelector('[data-dados-sidebar-plataformas-row]');
      if (sideRow) sideRow.hidden = true;
      return;
    }
    if (plats.length === 1) {
      badge.innerHTML = `<strong>Plataforma:</strong> ${escapeHtml(plats[0])}${trilhaSuffix}`;
    } else {
      badge.innerHTML = `<strong>Plataformas nos segmentos:</strong> ${plats.map(escapeHtml).join(', ')}`;
    }
    const sideRow = document.querySelector('[data-dados-sidebar-plataformas-row]');
    const sideDd = document.querySelector('[data-dados-sidebar-plataformas]');
    if (sideRow) sideRow.hidden = false;
    if (sideDd) sideDd.textContent = plats.join(', ');
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
          <span>Use o botão acima para adicionar o primeiro ${escapeHtml(itemLabel.toLowerCase())}.</span>
        </div>`;
      updateDadosPlatformBadge();
      return;
    }

    list.innerHTML = items.map((item, index) => {
      let metadata = fieldDefinitions
        .map(([key, label]) => item.metadata?.[key]
          ? `<span><b>${escapeHtml(label)}</b>${escapeHtml(formatMetadataValue(key, item.metadata[key]))}</span>` : '')
        .join('');
      if (workspaceType === 'dados' && item.metadata) {
        Object.entries(legacyMetadataLabels).forEach(([key, label]) => {
          if (!item.metadata[key]) return;
          metadata += `<span class="cot-item-metadata-legacy"><b>${escapeHtml(label)}</b>${escapeHtml(item.metadata[key])}</span>`;
        });
      }
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
    updateDadosPlatformBadge();
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

  function syncValorUnitarioHidden() {
    const display = form.elements.valor_unitario_display;
    const hidden = form.elements.valor_unitario;
    if (!display || !hidden) return;
    hidden.value = String(parseMoedaBr(display.value));
  }

  function setValorUnitarioFields(valorNumerico) {
    const display = form.elements.valor_unitario_display;
    const hidden = form.elements.valor_unitario;
    if (!display || !hidden) return;
    const n = Number(valorNumerico || 0);
    hidden.value = String(n);
    display.value = formatMoedaDigits(n);
  }

  function openItem(item = null) {
    form.reset();
    form.elements.item_id.value = item?.id || '';
    form.elements.titulo.value = item?.titulo || '';
    form.elements.descricao.value = item?.descricao || '';
    form.elements.quantidade.value = item?.quantidade || 1;
    setValorUnitarioFields(item?.valor_unitario ?? 0);
    fieldDefinitions.forEach(([key]) => {
      const el = form.elements[`meta_${key}`];
      if (el) el.value = item?.metadata?.[key] || '';
    });
    if (workspaceType === 'dados' && !item) {
      const legacy = (root.dataset.legacyPlataforma || '').trim();
      const platSel = form.elements.meta_plataforma_campanha;
      if (legacy && platSel && !platSel.value) platSel.value = legacy;
      const di = String(workspaceMeta.vigencia_proposta_inicio || '').slice(0, 10);
      const df = String(workspaceMeta.vigencia_proposta_fim || '').slice(0, 10);
      if (di && form.elements.meta_data_inicio) form.elements.meta_data_inicio.value = di;
      if (df && form.elements.meta_data_fim) form.elements.meta_data_fim.value = df;
    }
    const titleNode = dialog.querySelector('[data-dialog-title]');
    if (titleNode) {
      titleNode.textContent = item ? `Editar ${itemLabel.toLowerCase()}` : itemLabel;
    }
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

  dialog?.querySelectorAll('[data-item-dialog-close]').forEach((button) => {
    button.addEventListener('click', () => {
      if (dialog.open) dialog.close('cancel');
    });
  });

  form?.addEventListener('submit', async (event) => {
    const submitter = event.submitter;
    const isSave = submitter && submitter.matches('[data-save-item]');
    if (!isSave) {
      if (submitter?.value === 'cancel') dialog.close('cancel');
      return;
    }
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    if (workspaceType === 'dados') {
      const qty = Number(form.elements.quantidade.value);
      if (!Number.isInteger(qty) || qty < 1) {
        setStatus('A quantidade deve ser um número inteiro maior que zero.', 'error');
        return;
      }
      const plat = form.elements.meta_plataforma_campanha?.value?.trim();
      const di = form.elements.meta_data_inicio?.value;
      const df = form.elements.meta_data_fim?.value;
      if (!plat) {
        setStatus('Selecione a plataforma de dados do segmento.', 'error');
        return;
      }
      if (!di || !df) {
        setStatus('Informe data de início e término do segmento.', 'error');
        return;
      }
      if (df < di) {
        setStatus('A data de término deve ser igual ou posterior à data de início.', 'error');
        return;
      }
    }
    syncValorUnitarioHidden();
    const valorUnitario = parseMoedaBr(form.elements.valor_unitario.value);
    if (valorUnitario < 0 || Number.isNaN(valorUnitario)) {
      setStatus('Informe um valor unitário válido.', 'error');
      return;
    }
    const itemId = form.elements.item_id.value;
    const metadata = {};
    fieldDefinitions.forEach(([key]) => { metadata[key] = form.elements[`meta_${key}`].value; });
    const payload = {
      titulo: form.elements.titulo.value,
      descricao: form.elements.descricao.value,
      quantidade: form.elements.quantidade.value,
      valor_unitario: valorUnitario,
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

  const valorDisplay = form?.elements.valor_unitario_display;
  valorDisplay?.addEventListener('input', () => {
    let digits = valorDisplay.value.replace(/\D/g, '');
    if (digits === '') {
      valorDisplay.value = '';
      form.elements.valor_unitario.value = '0';
      return;
    }
    const cents = parseInt(digits, 10);
    valorDisplay.value = formatMoedaDigits(cents / 100);
    form.elements.valor_unitario.value = String(cents / 100);
  });

  render();

  const layout = document.querySelector('.cot-workspace-layout[data-cotacao-id]');
  const cotacaoId = layout ? Number(layout.dataset.cotacaoId || 0) : 0;
  if (cotacaoId && typeof window.initCotacaoComunicacao === 'function') {
    window.initCotacaoComunicacao({ cotacaoId, readOnly: false });
  }
})();
