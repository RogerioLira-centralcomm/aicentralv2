(function () {
  'use strict';

  var root = document.getElementById('cotacao-operacao-app');
  if (!root) return;

  var cotacaoId = Number(root.dataset.cotacaoId || 0);
  var sidebar = document.getElementById('cot-operation-sidebar');
  var sidebarTrigger = document.getElementById('cot-sidebar-mobile-trigger');
  var sidebarBackdrop = document.getElementById('cot-sidebar-backdrop');
  var feedback = document.getElementById('cot-operation-feedback');
  var nextActionButton = document.getElementById('cot-next-action');
  var refreshButton = document.getElementById('cot-checklist-refresh');
  var endpoint = '/api/cotacoes/' + cotacaoId + '/workspace-comercial';
  var currentNextAction = null;
  var refreshTimer = null;
  var opener = null;

  function esc(value) {
    var node = document.createElement('span');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  }

  function notify(message, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type || 'info');
    }
    if (!feedback) return;
    feedback.hidden = false;
    feedback.className = 'cot-op-feedback' + (type ? ' is-' + type : '');
    feedback.textContent = message;
  }

  var tabSections = {
    resumo: ['itens', 'audiencias', 'resumo_comercial', 'parametros_proposta'],
    itens: ['itens'],
    audiencias: ['audiencias'],
    historico: ['historico'],
    anexos: ['anexos']
  };

  function showQuoteTab(name) {
    if (name === 'visao_geral') name = 'resumo';
    if (!tabSections[name]) name = 'resumo';
    var visible = tabSections[name];

    document.querySelectorAll('.tab-nav-item[data-tab]').forEach(function (button) {
      var active = button.dataset.tab === name;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-section]').forEach(function (section) {
      section.hidden = visible.indexOf(section.dataset.section) < 0;
    });
    try {
      history.replaceState(null, '', '#' + name);
    } catch (_) {}
  }

  function initQuoteTabs() {
    document.querySelectorAll('.tab-nav-item[data-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        showQuoteTab(button.dataset.tab);
      });
    });
    var initial = (location.hash || '').replace('#', '');
    showQuoteTab(tabSections[initial] ? initial : 'resumo');

    var original = document.getElementById('contador_anexos');
    var mirror = document.getElementById('contador_anexos_nav');
    if (original && mirror) {
      var sync = function () { mirror.textContent = original.textContent; };
      sync();
      if ('MutationObserver' in window) {
        new MutationObserver(sync).observe(original, {
          childList: true, characterData: true, subtree: true
        });
      }
    }
  }

  window.mostrarTabCotacao = showQuoteTab;

  function activateMediaDialogTab(dialog, name) {
    if (!dialog) return;
    dialog.querySelectorAll('[data-media-dialog-tab]').forEach(function (button) {
      var active = button.dataset.tabTrigger === name;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
      button.setAttribute('tabindex', active ? '0' : '-1');
    });
    dialog.querySelectorAll('[data-tabpanel]').forEach(function (panel) {
      panel.classList.toggle('hidden', panel.dataset.tabpanel !== name);
    });
  }

  function syncMediaDialogStatus(dialog) {
    if (!dialog) return;
    var save = dialog.querySelector('[data-save-media-item]');
    var statusNode = dialog.querySelector('[data-media-dialog-status]');
    if (!save || !statusNode) return;
    var ready = !save.disabled;
    statusNode.classList.toggle('is-ready', ready);
    statusNode.textContent = ready
      ? 'Item pronto para salvar.'
      : 'Calcule a precificação antes de salvar.';
  }

  function confirmDeleteMediaItem(lineId) {
    var confirmDialog = document.getElementById('modal_confirmar_exclusao_linha');
    if (!confirmDialog || !lineId) return;
    var handleClose = function () {
      if (confirmDialog.returnValue !== 'confirm') return;
      var editDialog = document.getElementById('modal_editar_linha');
      if (editDialog && editDialog.open) editDialog.close();
      if (typeof window.confirmarRemoverLinha === 'function') {
        window.confirmarRemoverLinha(lineId);
      }
    };
    confirmDialog.addEventListener('close', handleClose, { once: true });
    confirmDialog.showModal();
  }

  function initMediaItems() {
    document.querySelectorAll('[data-media-item-dialog]').forEach(function (dialog) {
      dialog.querySelectorAll('[data-media-dialog-tab]').forEach(function (button) {
        button.addEventListener('click', function () {
          activateMediaDialogTab(dialog, button.dataset.tabTrigger);
        });
      });
      new MutationObserver(function () {
        if (dialog.open) {
          activateMediaDialogTab(dialog, 'inicio');
          syncMediaDialogStatus(dialog);
        }
      }).observe(dialog, { attributes: true, attributeFilter: ['open'] });
      var save = dialog.querySelector('[data-save-media-item]');
      if (save) {
        new MutationObserver(function () {
          syncMediaDialogStatus(dialog);
        }).observe(save, { attributes: true, attributeFilter: ['disabled'] });
      }
    });

    document.addEventListener('click', function (event) {
      var newItem = event.target.closest('[data-open-new-media-item]');
      if (newItem) {
        if (typeof window.abrirModalNovaLinha === 'function') window.abrirModalNovaLinha();
        return;
      }
      var openItem = event.target.closest('[data-open-media-item]');
      if (openItem) {
        var lineId = Number(openItem.dataset.lineId || 0);
        if (lineId && typeof window.visualizarOuEditarLinha === 'function') {
          window.visualizarOuEditarLinha(lineId);
        }
        return;
      }
      var close = event.target.closest('[data-close-media-dialog]');
      if (close) {
        var targetDialog = document.getElementById(close.dataset.closeMediaDialog);
        if (targetDialog) targetDialog.close();
        return;
      }
      var saveItem = event.target.closest('[data-save-media-item]');
      if (saveItem && !saveItem.disabled) {
        if (saveItem.dataset.saveMediaItem === 'create' && typeof window.salvarNovaLinha === 'function') {
          window.salvarNovaLinha();
        }
        if (saveItem.dataset.saveMediaItem === 'edit' && typeof window.salvarEdicaoLinha === 'function') {
          window.salvarEdicaoLinha();
        }
        return;
      }
      if (event.target.closest('[data-duplicate-media-item]')
          && typeof window.duplicarLinhaDoModal === 'function') {
        window.duplicarLinhaDoModal();
        return;
      }
      if (event.target.closest('[data-delete-media-item]')) {
        var idField = document.getElementById('edit_linha_id');
        confirmDeleteMediaItem(idField && idField.value);
      }
    });
  }

  window.CotacaoMediaUI = {
    confirmDelete: confirmDeleteMediaItem,
    open: function (lineId) {
      if (typeof window.visualizarOuEditarLinha === 'function') {
        window.visualizarOuEditarLinha(lineId);
      }
    }
  };

  async function requestState() {
    var response = await fetch(endpoint, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' }
    });
    var payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || 'Não foi possível analisar a proposta.');
    }
    return Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload;
  }

  function openSidebar() {
    if (!sidebar) return;
    opener = document.activeElement;
    sidebar.classList.add('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('is-open');
    if (sidebarTrigger) sidebarTrigger.setAttribute('aria-expanded', 'true');
    if (window.innerWidth <= 1050) {
      document.body.classList.add('cot-op-lock');
      var close = sidebar.querySelector('[data-cot-sidebar-close]');
      if (close) close.focus();
    }
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-open');
    if (sidebarTrigger) sidebarTrigger.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('cot-op-lock');
    if (window.innerWidth <= 1050 && opener && typeof opener.focus === 'function') {
      opener.focus();
    }
  }

  function navigateToAction(action) {
    if (!action || !action.alvo) return;
    if (action.tipo === 'hash') {
      if (typeof window.mostrarTabCotacao === 'function') {
        window.mostrarTabCotacao(action.alvo);
      } else {
        window.location.hash = action.alvo;
      }
      closeSidebar();
      var section = document.querySelector('[data-section="' + action.alvo + '"]');
      if (action.alvo === 'resumo') section = document.querySelector('[data-section="resumo_comercial"]');
      if (section) {
        window.setTimeout(function () {
          section.scrollIntoView({
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
            block: 'start'
          });
        }, 0);
      }
      return;
    }
    if (action.tipo === 'modal') {
      var dialog = document.getElementById(action.alvo);
      if (dialog && typeof dialog.showModal === 'function') {
        closeSidebar();
        dialog.showModal();
      }
      return;
    }
    if (action.tipo === 'funcao' && typeof window[action.alvo] === 'function') {
      closeSidebar();
      window[action.alvo]();
    }
  }

  function renderProgress(progress) {
    progress = progress || {};
    var total = Number(progress.total || 0);
    var completed = Number(progress.concluidos || 0);
    var percent = Math.max(0, Math.min(100, Number(progress.percentual || 0)));
    var label = document.getElementById('cot-checklist-progress-label');
    var value = document.getElementById('cot-checklist-progress-value');
    var bar = document.getElementById('cot-checklist-progress-bar');
    var track = bar && bar.parentElement;
    if (label) label.textContent = total ? completed + ' de ' + total + ' concluídos' : 'Sem etapas obrigatórias';
    if (value) value.textContent = percent + '%';
    if (bar) bar.style.width = percent + '%';
    if (track) track.setAttribute('aria-valuenow', String(percent));
  }

  function renderChecklist(items) {
    var target = document.getElementById('cot-checklist-items');
    if (!target) return;
    items = Array.isArray(items) ? items : [];
    if (!items.length) {
      target.innerHTML = '<div class="cot-op-state">Nenhuma verificação disponível.</div>';
      return;
    }
    target.innerHTML = items.map(function (item, index) {
      var optional = Boolean(item.opcional);
      var complete = Boolean(item.concluido);
      var icon = complete ? 'fa-circle-check' : (optional ? 'fa-circle-minus' : 'fa-square');
      var classes = 'cot-op-check' + (complete ? ' is-complete' : '') + (optional ? ' is-optional' : '');
      return '<button type="button" class="' + classes + '" data-check-index="' + index + '">' +
        '<span class="cot-op-check__status"><i class="fa-solid ' + icon + '" aria-hidden="true"></i></span>' +
        '<span><strong>' + esc(item.titulo || 'Verificação') + '</strong>' +
        '<small>' + esc(item.evidencia || '') + '</small></span>' +
        '<i class="fa-solid fa-chevron-right" aria-hidden="true"></i></button>';
    }).join('');
    target.querySelectorAll('[data-check-index]').forEach(function (button) {
      button.addEventListener('click', function () {
        var item = items[Number(button.dataset.checkIndex)];
        navigateToAction(item && item.acao);
      });
    });
  }

  function renderState(data) {
    var recommendation = document.getElementById('cot-operation-recommendation');
    if (recommendation) {
      recommendation.className = 'cot-op-state';
      recommendation.innerHTML = '<strong>' + esc(data.recomendacao || 'Nenhuma pendência prioritária.') + '</strong>' +
        (data.proxima_pendencia && data.proxima_pendencia.evidencia
          ? '<small class="block">' + esc(data.proxima_pendencia.evidencia) + '</small>'
          : '');
    }
    currentNextAction = data.proxima_pendencia && data.proxima_pendencia.acao;
    if (nextActionButton) {
      nextActionButton.hidden = !currentNextAction;
      nextActionButton.textContent = data.proxima_pendencia
        ? 'Resolver: ' + data.proxima_pendencia.titulo
        : 'Resolver pendência';
    }
    renderProgress(data.progresso);
    renderChecklist(data.checklist);
    if (feedback) feedback.hidden = true;
  }

  async function loadState(showFeedback) {
    if (!cotacaoId) return;
    if (refreshButton) refreshButton.disabled = true;
    try {
      renderState(await requestState());
      if (showFeedback) notify('Pendências atualizadas.', 'success');
    } catch (error) {
      notify(error.message, 'error');
      var recommendation = document.getElementById('cot-operation-recommendation');
      if (recommendation) {
        recommendation.className = 'cot-op-state';
        recommendation.textContent = 'Atualize novamente ou recarregue a página.';
      }
    } finally {
      if (refreshButton) refreshButton.disabled = false;
    }
  }

  function scheduleRefresh() {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(function () { loadState(false); }, 700);
  }

  if (sidebarTrigger) sidebarTrigger.addEventListener('click', openSidebar);
  if (nextActionButton) nextActionButton.addEventListener('click', function () {
    navigateToAction(currentNextAction);
  });
  if (refreshButton) refreshButton.addEventListener('click', function () { loadState(true); });
  document.querySelectorAll('[data-cot-sidebar-close]').forEach(function (button) {
    button.addEventListener('click', closeSidebar);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) closeSidebar();
  });
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) scheduleRefresh();
  });
  document.addEventListener('cotacao:updated', scheduleRefresh);

  var observed = document.querySelector('.cot-op-main');
  if (observed && 'MutationObserver' in window) {
    new MutationObserver(function (mutations) {
      var relevant = mutations.some(function (mutation) {
        var target = mutation.target;
        return target && target.closest && target.closest(
          '#contador_anexos, #lista_anexos, #lista_comentarios, [data-section="itens"], [data-section="audiencias"]'
        );
      });
      if (relevant) scheduleRefresh();
    }).observe(observed, { childList: true, subtree: true });
  }

  initQuoteTabs();
  initMediaItems();
  loadState(false);
})();
