(function () {
  'use strict';

  var root = document.getElementById('pi-operacao-app');
  if (!root) return;

  var piId = Number(root.dataset.piId || 0);
  var campaignId = Number(root.dataset.campanhaId || 0);
  var stage = String(root.dataset.stage || '');
  var readOnly = root.dataset.readonly === 'true';
  var base = '/api/cadu_pi/' + piId + '/operacao';
  var stateUrl = campaignId ? base + '/campanhas/' + campaignId : base;
  var sidebar = document.getElementById('pi-operation-sidebar');
  var sidebarScroll = document.getElementById('pi-sidebar-scroll');
  var sidebarTrigger = document.getElementById('pi-sidebar-mobile-trigger');
  var sidebarBackdrop = document.getElementById('pi-sidebar-backdrop');
  var feedback = document.getElementById('pi-operation-feedback');
  var confirmDialog = document.getElementById('pi-confirm-dialog');
  var emailDialog = document.getElementById('pi-email-dialog');
  var scrollKey = 'cx:pi-operacao:' + piId + ':sidebar-scroll';
  var selectedCampaign = null;
  var operationData = null;
  var communicationCatalog = [];
  var emailPreviewData = null;
  var feedbackTimer = null;
  var confirmationResolve = null;
  var sidebarOpener = null;
  var emailDialogOpener = null;
  var currentEmailType = '';
  var currentEmailCampaignId = null;
  var emailPreviewReady = false;
  var userEmail = String(root.dataset.userEmail || '').trim();
  var userName = String(root.dataset.userName || '').trim();
  var mobileMedia = window.matchMedia('(max-width: 900px)');
  var mobileTabs = Array.prototype.slice.call(root.querySelectorAll('[data-mobile-tab]'));
  var mobileViews = ['summary', 'edit', 'operation'];

  function esc(value) {
    var node = document.createElement('span');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  function piDetailUrl() {
    return '/cadu_pi/editar/' + encodeURIComponent(piId);
  }

  function campaignDetailUrl(id) {
    return '/campanhas-pi/' + encodeURIComponent(Number(id)) +
      '?return_url=' + encodeURIComponent(piDetailUrl());
  }

  async function request(url, options) {
    var response = await fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
    var type = response.headers.get('content-type') || '';
    var data = type.indexOf('application/json') !== -1 ? await response.json() : null;
    if (!response.ok) {
      var detail = data && (data.message || data.error);
      if (detail && typeof detail === 'object') detail = detail.message;
      throw new Error(detail || 'Não foi possível concluir a solicitação.');
    }
    if (data && data.success === false) throw new Error(data.error || data.message || 'A solicitação falhou.');
    return data && Object.prototype.hasOwnProperty.call(data, 'data') ? data.data : (data || {});
  }

  function notify(message, type) {
    if (typeof window.showToast === 'function') window.showToast(message, type || 'info');
    if (!feedback) return;
    window.clearTimeout(feedbackTimer);
    feedback.hidden = false;
    feedback.className = 'pi-op-feedback is-' + (type || 'info');
    feedback.textContent = message;
    feedbackTimer = window.setTimeout(function () {
      feedback.hidden = true;
    }, type === 'error' ? 8000 : 4500);
  }

  function confirmAction(options) {
    options = options || {};
    if (!confirmDialog) {
      notify('Não foi possível abrir a confirmação desta ação.', 'error');
      return Promise.resolve(false);
    }
    if (confirmDialog.open) confirmDialog.close('cancel');
    document.getElementById('pi-confirm-title').textContent = options.title || 'Confirmar ação';
    document.getElementById('pi-confirm-message').textContent = options.message || '';
    var details = document.getElementById('pi-confirm-details');
    var detailItems = list(options.details);
    confirmDialog.classList.toggle('is-email', options.kind === 'email');
    if (details) {
      details.replaceChildren();
      details.hidden = !detailItems.length;
      detailItems.forEach(function (item) {
        var row = document.createElement('div');
        var identity = document.createElement('span');
        var name = document.createElement('strong');
        var email = document.createElement('small');
        var role = document.createElement('em');
        name.textContent = item.nome_completo || item.nome || item.email || 'Contato';
        email.textContent = item.email || 'Sem e-mail';
        role.textContent = String(item.papel || item.role || '').replace('_', ' ') || 'Destinatário';
        identity.append(name, email);
        row.append(identity, role);
        details.appendChild(row);
      });
    }
    var accept = document.getElementById('pi-confirm-accept');
    accept.textContent = options.confirmText || 'Confirmar';
    accept.className = 'pi-op-btn ' + (options.danger ? 'pi-op-btn--danger' : 'pi-op-btn--primary');
    confirmDialog.returnValue = 'cancel';
    confirmDialog.showModal();
    return new Promise(function (resolve) {
      confirmationResolve = resolve;
    });
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.originalLabel = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i>' + esc(label || 'Processando…');
    } else {
      button.disabled = false;
      if (button.dataset.originalLabel) button.innerHTML = button.dataset.originalLabel;
    }
  }

  function mobileViewFromHash() {
    var view = String(window.location.hash || '').replace(/^#/, '');
    return mobileViews.indexOf(view) !== -1 ? view : '';
  }

  function setMobileView(view, options) {
    options = options || {};
    if (!mobileTabs.length || mobileViews.indexOf(view) === -1) return;
    root.dataset.mobileView = view;
    mobileTabs.forEach(function (tab) {
      var selected = tab.dataset.mobileTab === view;
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.tabIndex = selected ? 0 : -1;
    });
    root.querySelectorAll('[data-mobile-panel]').forEach(function (panel) {
      panel.setAttribute('aria-hidden', panel.dataset.mobilePanel === view ? 'false' : 'true');
    });
    if (sidebar) sidebar.classList.remove('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-open');
    if (sidebarTrigger) sidebarTrigger.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('pi-op-lock');
    if (options.updateHash !== false && window.location.hash !== '#' + view) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search + '#' + view);
    }
    if (options.focusPanel) {
      var panel = root.querySelector('[data-mobile-panel="' + view + '"]');
      if (panel) window.setTimeout(function () { panel.focus({ preventScroll: true }); }, 0);
    }
  }

  function syncMobileWorkspace() {
    if (!mobileTabs.length) return;
    if (mobileMedia.matches) {
      setMobileView(mobileViewFromHash() || root.dataset.mobileView || 'summary', { updateHash: false });
      return;
    }
    root.querySelectorAll('[data-mobile-panel]').forEach(function (panel) {
      panel.removeAttribute('aria-hidden');
    });
    document.body.classList.remove('pi-op-lock');
  }

  function initMobileWorkspace() {
    if (!mobileTabs.length) return;
    mobileTabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () {
        setMobileView(tab.dataset.mobileTab, { focusPanel: false });
      });
      tab.addEventListener('keydown', function (event) {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        var direction = event.key === 'ArrowRight' ? 1 : -1;
        var next = mobileTabs[(index + direction + mobileTabs.length) % mobileTabs.length];
        next.focus();
        setMobileView(next.dataset.mobileTab);
      });
    });
    root.addEventListener('click', function (event) {
      var button = event.target.closest('[data-mobile-go]');
      if (button) setMobileView(button.dataset.mobileGo, { focusPanel: true });
    });
    root.addEventListener('invalid', function () {
      if (mobileMedia.matches) setMobileView('edit');
    }, true);
    window.addEventListener('hashchange', function () {
      var view = mobileViewFromHash();
      if (view && mobileMedia.matches) setMobileView(view, { updateHash: false });
    });
    if (typeof mobileMedia.addEventListener === 'function') {
      mobileMedia.addEventListener('change', syncMobileWorkspace);
    } else {
      mobileMedia.addListener(syncMobileWorkspace);
    }
    syncMobileWorkspace();
  }

  function errorHtml(message) {
    return '<div class="pi-op-error"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i> ' + esc(message) + '</div>';
  }

  function renderRecommendation(data) {
    var target = document.getElementById('pi-operation-recommendation');
    if (!target) return;
    var next = data.checklist_operacional && data.checklist_operacional.proxima_pendencia;
    if (next) {
      target.innerHTML = '<strong>' + esc(next.descricao || 'Concluir pendência') + '</strong>' +
        (next.nome_campanha ? '<small class="block">' + esc(next.nome_campanha) + '</small>' : '');
      return;
    }
    if (data.checklist_operacional && data.checklist_operacional.progresso &&
        data.checklist_operacional.progresso.total) {
      target.innerHTML = '<strong>Checklist concluído.</strong>';
      return;
    }
    var recommendation = data.recomendacao || data.recommendation || data.recomendacoes;
    if (Array.isArray(recommendation)) {
      target.innerHTML = recommendation.length
        ? '<ul class="pi-op-list">' + recommendation.map(function (item) { return '<li>' + esc(item) + '</li>'; }).join('') + '</ul>'
        : 'Nenhuma recomendação no momento.';
      return;
    }
    if (recommendation && typeof recommendation === 'object') {
      recommendation = recommendation.texto || recommendation.descricao || recommendation.titulo;
    }
    target.innerHTML = recommendation ? '<strong>' + esc(recommendation) + '</strong>' : 'Nenhuma recomendação no momento.';
  }

  function checklistItemHtml(item, index) {
    var id = item.id || item.id_item || index;
    var checked = Boolean(item.concluido || item.completed);
    var automatic = item.modo_conclusao === 'automatico';
    var evidence = item.evidencia || (
      checked
        ? (automatic ? 'Confirmado pelos dados do CentralX' : 'Confirmado pela equipe')
        : (automatic ? 'Aguardando evidência no CentralX' : 'Marque quando esta etapa for concluída')
    );
    var control = automatic
      ? '<span class="pi-op-check__status" aria-hidden="true"><i class="fa-solid ' +
        (checked ? 'fa-circle-check' : 'fa-clock') + '"></i></span>'
      : '<input type="checkbox" data-checklist-id="' + esc(id) + '"' +
        (checked ? ' checked' : '') + (readOnly ? ' disabled' : '') + '>';
    return '<label class="pi-op-check' + (checked ? ' is-complete' : '') +
      (automatic ? ' is-automatic' : '') + '">' + control + '<span><strong>' +
      esc(item.titulo || item.descricao || item.label || 'Item') + '</strong>' +
      '<small class="block">' + esc(evidence) + '</small>' +
      '</span></label>';
  }

  function renderChecklist(data) {
    var piTarget = document.getElementById('pi-checklist-pi');
    var campaignTarget = document.getElementById('pi-checklist-campaigns');
    if (!piTarget || !campaignTarget) return;
    var structure = data.checklist_operacional || {};
    var progress = structure.progresso || { concluidos: 0, total: 0, percentual: 0 };
    var label = document.getElementById('pi-checklist-progress-label');
    var value = document.getElementById('pi-checklist-progress-value');
    var bar = document.getElementById('pi-checklist-progress-bar');
    var track = bar && bar.parentElement;
    if (label) label.textContent = progress.total ? 'Progresso geral' : 'Checklist não iniciado';
    if (value) value.textContent = progress.total ? progress.concluidos + '/' + progress.total : '';
    if (bar) bar.style.width = Math.max(0, Math.min(100, Number(progress.percentual) || 0)) + '%';
    if (track) track.setAttribute('aria-valuenow', String(Number(progress.percentual) || 0));

    var piItems = list(structure.itens_pi);
    piTarget.className = '';
    piTarget.innerHTML = piItems.length
      ? piItems.map(checklistItemHtml).join('')
      : '<div class="pi-op-state">Atualize para criar as etapas do PI.</div>';

    var campaigns = list(structure.campanhas);
    var completedCampaigns = campaigns.filter(function (item) { return item.completo; }).length;
    var count = document.getElementById('pi-checklist-campaign-count');
    if (count) {
      count.textContent = campaignId && campaigns.length
        ? progress.concluidos + '/' + progress.total + ' etapas'
        : (campaigns.length ? completedCampaigns + '/' + campaigns.length + ' prontas' : '');
    }
    var mobileCount = document.getElementById('pi-mobile-operation-count');
    if (mobileCount) {
      mobileCount.textContent = progress.total ? progress.concluidos + '/' + progress.total : '';
      mobileCount.setAttribute('aria-label', progress.total
        ? progress.concluidos + ' de ' + progress.total + ' etapas concluídas'
        : '');
    }
    campaignTarget.className = '';
    campaignTarget.innerHTML = campaigns.length
      ? campaigns.map(function (campaign, campaignIndex) {
          var items = list(campaign.itens);
          return '<details class="pi-op-campaign-checklist"' +
            (!campaign.completo && campaignIndex === 0 ? ' open' : '') + '><summary>' +
            '<a class="pi-op-campaign-checklist__link" data-campaign-link href="' +
            esc(campaignDetailUrl(campaign.id_campanha)) + '"><strong>' +
            esc(campaign.nome) + '</strong><small>' +
            esc(campaign.plataforma || 'Sem plataforma') + '</small></a>' +
            '<span class="pi-op-campaign-checklist__count">' + esc(campaign.concluidos) + '/' +
            esc(campaign.total) + '<i class="fa-solid fa-chevron-down" aria-hidden="true"></i></span>' +
            '</summary><div class="pi-op-campaign-checklist__items">' +
            items.map(checklistItemHtml).join('') + '</div></details>';
        }).join('')
      : '<div class="pi-op-state">Nenhuma campanha vinculada ao PI.</div>';
  }

  function shortDate(value) {
    if (!value) return '';
    var raw = String(value).trim();
    var iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return [iso[3], iso[2], iso[1]].join('/');
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) return raw;
    var parsed = new Date(raw);
    if (!isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        timeZone: 'UTC'
      }).format(parsed);
    }
    return raw;
  }

  function renderPiOrigin(data) {
    var pi = data.pi || {};
    var summary = data.resumo || {};
    var setText = function (id, value, fallback) {
      var target = document.getElementById(id);
      if (target) target.textContent = value || fallback || '—';
    };
    setText('pi-origin-code', pi.codigo_pi_cc || (pi.id_pi ? 'PI ' + pi.id_pi : ''), 'Abrir PI');
    setText('pi-origin-title', pi.titulo_pi, 'Título não informado');
    setText('pi-origin-status', pi.sub_status_descricao || pi.status_descricao, 'Sem status');
    setText('pi-origin-client', pi.cliente_nome || pi.nome_cliente, 'Não informado');
    var agency = summary.agencia || pi.agencia_nome || '';
    var agencyRow = document.getElementById('pi-origin-agency-row');
    setText('pi-origin-agency', agency, '');
    if (agencyRow) agencyRow.hidden = !agency;
    var partner = pi.parceiro_nome || '';
    var partnerRow = document.getElementById('pi-origin-partner-row');
    setText('pi-origin-partner', partner, '');
    if (partnerRow) partnerRow.hidden = !partner;
    var start = shortDate(pi.periodo_inicio);
    var finish = shortDate(pi.periodo_fim);
    setText('pi-origin-period', start || finish ? (start || '—') + ' a ' + (finish || '—') : '', 'Não informado');
  }

  function renderRouteMap(data) {
    var target = document.getElementById('pi-route-campaigns');
    if (!target) return;
    var piLink = document.getElementById('pi-route-pi');
    var position = document.getElementById('pi-route-position');
    var cycle = document.getElementById('pi-route-cycle');
    var previous = document.getElementById('pi-route-prev');
    var next = document.getElementById('pi-route-next');
    if (piLink) {
      piLink.href = piDetailUrl();
      piLink.classList.toggle('is-current', !campaignId);
      if (!campaignId) piLink.setAttribute('aria-current', 'page');
      else piLink.removeAttribute('aria-current');
    }
    var campaigns = list(data.campanhas_relacionadas).length
      ? list(data.campanhas_relacionadas)
      : list(data.campanhas).map(function (item) {
          return {
            id_campanha: item.id_campanha,
            nome: item.nome_campanha || item.nome,
            plataforma: item.plataforma_nome || item.plataforma,
            atual: Number(item.id_campanha) === campaignId
          };
        });
    target.className = '';
    target.innerHTML = campaigns.length
      ? '<div class="pi-op-route-map__list">' + campaigns.map(function (campaign) {
          var current = Boolean(campaign.atual) ||
            Number(campaign.id_campanha) === campaignId;
          return '<a class="pi-op-route-map__item' + (current ? ' is-current' : '') +
            '" href="' + esc(campaignDetailUrl(campaign.id_campanha)) + '"' +
            (current ? ' aria-current="page"' : '') + '><span>' +
            esc(campaign.nome || ('Campanha ' + campaign.id_campanha)) +
            '</span><small>' + esc(campaign.plataforma || 'Abrir campanha') +
            '</small><i class="fa-solid fa-chevron-right" aria-hidden="true"></i></a>';
        }).join('') + '</div>'
      : '<div class="pi-op-state">Este PI ainda não possui campanhas.</div>';
    if (position) {
      var currentIndex = campaigns.findIndex(function (item) {
        return Boolean(item.atual) || Number(item.id_campanha) === campaignId;
      });
      position.textContent = currentIndex >= 0
        ? (currentIndex + 1) + ' de ' + campaigns.length
        : campaigns.length + (campaigns.length === 1 ? ' campanha' : ' campanhas');
    }
    if (!cycle || !previous || !next) return;
    var index = campaigns.findIndex(function (item) {
      return Boolean(item.atual) || Number(item.id_campanha) === campaignId;
    });
    cycle.hidden = index < 0 || campaigns.length < 2;
    if (!cycle.hidden) {
      var previousCampaign = campaigns[(index - 1 + campaigns.length) % campaigns.length];
      var nextCampaign = campaigns[(index + 1) % campaigns.length];
      previous.href = campaignDetailUrl(previousCampaign.id_campanha);
      previous.title = previousCampaign.nome || 'Campanha anterior';
      next.href = campaignDetailUrl(nextCampaign.id_campanha);
      next.title = nextCampaign.nome || 'Próxima campanha';
    }
  }

  function renderTimeline(data) {
    var target = document.getElementById('pi-operation-timeline');
    if (!target) return;
    var entries = list(data.timeline || data.interacoes || data.historico).filter(function (entry) {
      return entry.concluida !== false;
    });
    target.innerHTML = entries.length
      ? '<ul class="pi-op-list">' + entries.map(function (entry) {
          var text = entry.descricao || entry.texto || entry.acao || entry.titulo || String(entry.etapa || '').replace(/_/g, ' ');
          var labels = {
            dados_validados: 'Dados validados',
            campanhas_configuradas: 'Campanhas configuradas',
            materiais_recebidos: 'Materiais recebidos',
            campanha_iniciada: 'Campanha iniciada',
            otimizacao_enviada: 'Otimização enviada',
            fechamento_comunicado: 'Fechamento comunicado',
            enviado_financeiro: 'Enviado ao Financeiro'
          };
          text = labels[entry.etapa] || text;
          var date = entry.data_formatada || entry.data || entry.concluida_em || entry.created_at || '';
          return '<li><strong>' + esc(text) + '</strong>' + (date ? '<small class="block">' + esc(date) + '</small>' : '') + '</li>';
        }).join('') + '</ul>'
      : '<div class="pi-op-state">Nenhuma atividade registrada.</div>';
  }

  function recipientId(item) {
    if (item == null) return '';
    if (typeof item !== 'object') return String(item);
    return String(item.id_contato_cliente || item.contato_id || item.id || '');
  }

  function savedEmailRecipients(data) {
    if (!data || data.destinatarios_confirmados !== true) return [];
    return list(data && (data.destinatarios || data.recipients)).filter(function (item) {
      return item && typeof item === 'object' && recipientId(item) &&
        Boolean(String(item.email || '').trim());
    });
  }

  function recipientSignature(items) {
    return list(items).map(function (item) {
      return recipientId(item) + ':' + String(item.papel || item.role || '');
    }).filter(function (item) {
      return item.charAt(0) !== ':';
    }).sort().join('|');
  }

  function selectedRecipientSignature(form) {
    if (!form) return '';
    return Array.prototype.map.call(
      form.querySelectorAll('[data-recipient-id]:checked'),
      function (input) {
        return String(input.dataset.recipientId || '') + ':' +
          String(input.dataset.recipientRole || '');
      }
    ).sort().join('|');
  }

  function focusRecipientSelection() {
    var form = document.getElementById('pi-recipients-form');
    var panel = form && form.closest('.pi-op-panel');
    openSidebar();
    if (panel) scrollSidebarTo(panel);
    notify('Selecione e salve ao menos um destinatário antes de preparar o e-mail.', 'warning');
    window.setTimeout(function () {
      var first = form && form.querySelector('[data-recipient-id]:not(:disabled)');
      if (first) first.focus({ preventScroll: true });
    }, 0);
  }

  function renderRecipients(data) {
    var target = document.getElementById('pi-recipient-options');
    if (!target) return;
    data = data && typeof data === 'object' ? data : {};
    var count = document.getElementById('pi-recipient-count');
    var form = document.getElementById('pi-recipients-form');
    var submit = form && form.querySelector('button[type="submit"]');
    if (data.recipient_error) {
      target.className = '';
      target.innerHTML = errorHtml(data.recipient_error) +
        '<button type="button" class="pi-op-text-btn pi-op-recipient-retry" data-retry-recipients>Tentar novamente</button>';
      if (count) count.textContent = '';
      if (form) form.dataset.savedRecipientSignature = '';
      if (submit) submit.disabled = true;
      return;
    }
    var selected = list(data.destinatarios || data.recipients);
    var available = list(data.contatos_disponiveis || data.available_contacts);
    if (form) {
      form.dataset.savedRecipientSignature = data.destinatarios_confirmados
        ? recipientSignature(selected)
        : '';
    }
    var selectedById = {};
    selected.forEach(function (item) {
      var id = recipientId(item);
      if (id) selectedById[id] = typeof item === 'object' ? item : { id_contato_cliente: id };
    });
    var availableIds = {};
    available = available.filter(function (item) {
      var id = recipientId(item);
      if (!id || availableIds[id]) return false;
      availableIds[id] = true;
      return true;
    });
    selected.forEach(function (item) {
      var id = recipientId(item);
      if (id && !availableIds[id] && typeof item === 'object') {
        available.push(Object.assign({ indisponivel: true }, item));
        availableIds[id] = true;
      }
    });
    if (!available.length) {
      target.className = '';
      target.innerHTML = '<div class="pi-op-state">Nenhum contato com vínculo ativo foi encontrado para o cliente ou agência deste PI.</div>';
      if (count) count.textContent = '0 selecionados';
      if (submit) submit.disabled = true;
      return;
    }
    var groups = { cliente_final: [], agencia: [] };
    available.forEach(function (item) {
      var id = recipientId(item);
      var active = selectedById[id];
      var role = (active && active.papel) ||
        (data.pi && String(item.pk_id_tbl_cliente) === String(data.pi.id_agencia) ? 'agencia' : 'cliente_final');
      if (!groups[role]) role = 'cliente_final';
      groups[role].push({ item: item, id: id, active: active, role: role });
    });
    function groupHtml(role, label) {
      var items = groups[role];
      if (!items.length) return '';
      return '<fieldset class="pi-op-recipient-group"><legend>' + esc(label) + '</legend>' +
        items.map(function (entry) {
          var item = entry.item;
          var hasEmail = Boolean(String(item.email || '').trim());
          var disabled = readOnly || (!hasEmail && !entry.active) ||
            (item.indisponivel && !entry.active);
          var detail = hasEmail ? esc(item.email) : '<span class="pi-op-recipient-missing">Sem e-mail cadastrado</span>';
          if (item.indisponivel) detail += ' <span class="pi-op-recipient-unavailable">Contato inativo</span>';
          return '<label class="pi-op-check pi-op-recipient' + (!hasEmail ? ' has-warning' : '') + '">' +
            '<input type="checkbox" data-recipient-id="' + esc(entry.id) +
            '" data-recipient-role="' + esc(entry.role) + '" data-has-email="' + (hasEmail ? 'true' : 'false') + '"' +
            (entry.active ? ' checked' : '') + (disabled ? ' disabled' : '') + '>' +
            '<span><strong>' + esc(item.nome_completo || item.email || 'Contato sem nome') +
            '</strong><small class="block">' + detail + '</small></span></label>';
        }).join('') + '</fieldset>';
    }
    target.className = 'pi-op-recipient-groups';
    target.innerHTML = groupHtml('cliente_final', 'Cliente') + groupHtml('agencia', 'Agência');
    updateRecipientCount();
  }

  function updateRecipientCount() {
    var form = document.getElementById('pi-recipients-form');
    var count = document.getElementById('pi-recipient-count');
    if (!form || !count) return;
    var checked = form.querySelectorAll('[data-recipient-id]:checked');
    var invalid = Array.prototype.some.call(checked, function (input) {
      return input.dataset.hasEmail !== 'true';
    });
    var total = checked.length;
    count.textContent = total + (total === 1 ? ' selecionado' : ' selecionados') +
      (invalid ? ' · revisar e-mail' : '');
    var submit = form.querySelector('button[type="submit"]');
    if (submit) {
      var dirty = selectedRecipientSignature(form) !==
        String(form.dataset.savedRecipientSignature || '');
      submit.disabled = readOnly || total === 0 || invalid || !dirty;
      submit.textContent = dirty ? 'Salvar destinatários' : 'Destinatários salvos';
    }
  }

  function communicationName(item) {
    return item.nome || item.titulo || item.assunto_padrao || item.descricao || item.label || item.tipo || item.slug || 'Comunicação';
  }

  function communicationId(item) {
    return item.id || item.codigo || item.tipo || item.slug || '';
  }

  function renderCommunications() {
    var target = document.getElementById('pi-operation-communications');
    if (!target) return;
    if (!communicationCatalog.length) {
      target.innerHTML = '<div class="pi-op-state">Nenhum tipo de comunicação disponível para esta etapa.</div>';
      return;
    }
    var recipientsReady = savedEmailRecipients(operationData).length > 0;
    var guidance = recipientsReady ? '' :
      '<div class="pi-op-communication-warning">' +
        '<strong>Defina quem receberá os e-mails</strong>' +
        '<span>Selecione e salve ao menos um destinatário para liberar as comunicações.</span>' +
        '<button type="button" class="pi-op-text-btn" data-choose-recipients>Selecionar destinatários</button>' +
      '</div>';
    target.innerHTML = guidance + '<div class="pi-op-communication-list">' + communicationCatalog.map(function (item) {
      return '<button type="button" class="pi-op-btn pi-op-btn--secondary" data-communication="' +
        esc(communicationId(item)) + '"><i class="fa-regular fa-envelope" aria-hidden="true"></i>' +
        '<span>' + esc(communicationName(item)) + '</span></button>';
    }).join('') + '</div>';
    target.querySelectorAll('[data-communication]').forEach(function (button) {
      button.disabled = !recipientsReady;
      button.title = recipientsReady ? '' : 'Selecione e salve os destinatários primeiro';
    });
  }

  async function loadOperation() {
    if (!piId) return;
    try {
      operationData = await request(stateUrl);
      if (campaignId && operationData.campanha) {
        selectedCampaign = operationData.campanha;
      }
      renderRecommendation(operationData);
      renderChecklist(operationData);
      renderPiOrigin(operationData);
      renderRouteMap(operationData);
      renderTimeline(operationData);
      renderRecipients(operationData);
      renderCommunications();
    } catch (error) {
      var target = document.getElementById('pi-operation-recommendation');
      if (target) target.innerHTML = errorHtml(error.message);
      renderChecklist({});
      renderRouteMap({});
      renderTimeline({});
      renderRecipients({ recipient_error: error.message });
    }
  }

  async function loadCatalog() {
    if (!piId) return;
    var target = document.getElementById('pi-operation-communications');
    try {
      var data;
      try {
        data = await request(base + '/comunicacoes');
      } catch (primaryError) {
        data = await request(base + '/comunicacoes/catalogo');
      }
      communicationCatalog = list(data.comunicacoes || data.tipos || data.items || data);
      renderCommunications();
    } catch (error) {
      if (target) target.innerHTML = errorHtml(error.message);
    }
  }

  function openSidebar() {
    if (!sidebar) return;
    if (mobileMedia.matches && mobileTabs.length) {
      setMobileView('operation');
      return;
    }
    if (document.activeElement && !sidebar.contains(document.activeElement)) {
      sidebarOpener = document.activeElement;
    }
    sidebar.classList.add('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('is-open');
    if (sidebarTrigger) sidebarTrigger.setAttribute('aria-expanded', 'true');
    if (window.innerWidth <= 1050) document.body.classList.add('pi-op-lock');
    var close = sidebar.querySelector('[data-sidebar-close]');
    if (close && window.innerWidth <= 1050) close.focus();
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-open');
    if (sidebarTrigger) sidebarTrigger.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('pi-op-lock');
    if (window.innerWidth <= 1050 && sidebarOpener && typeof sidebarOpener.focus === 'function') {
      sidebarOpener.focus();
    }
  }

  function scrollSidebarTo(element) {
    if (!element) return;
    var behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    if (window.innerWidth <= 1050 && sidebarScroll) {
      sidebarScroll.scrollTo({ top: element.offsetTop - 12, behavior: behavior });
      return;
    }
    element.scrollIntoView({ block: 'start', behavior: behavior });
  }

  function decodePayload(encoded) {
    try { return JSON.parse(decodeURIComponent(escape(atob(encoded)))); } catch (_) { return null; }
  }

  function campaignPanel(campaign, action) {
    selectedCampaign = campaign;
    var panel = document.getElementById('pi-context-panel');
    var title = document.getElementById('pi-context-title');
    var content = document.getElementById('pi-context-content');
    if (!panel || !content || !campaign) return;
    var actionNames = { edit: 'Editar campanha', follow: 'Acompanhar campanha', duplicate: 'Duplicar campanha', email: 'Enviar e-mail' };
    var buttonClass = function (name) {
      return 'pi-op-btn ' + (action === name ? 'pi-op-btn--primary' : 'pi-op-btn--secondary');
    };
    title.textContent = actionNames[action] || 'Campanha';
    title.setAttribute('tabindex', '-1');
    content.innerHTML =
      '<div class="pi-op-stack"><h4 class="pi-op-context-name">' + esc(campaign.nome_campanha || 'Campanha') + '</h4>' +
      '<div class="pi-op-context-meta"><span>' + esc(campaign.plataforma_nome || 'Plataforma não informada') + '</span>' +
      '<span>' + esc(campaign.status_nome || campaign.status_descricao || 'Sem status') + '</span></div>' +
      '<div class="pi-op-campaign-facts">' +
        '<div><span>Objetivo contratado</span><strong>' + esc(campaign.obj_contratados || '—') + '</strong></div>' +
        '<div><span>Objetivo atingido</span><strong>' + esc(campaign.totalizador_atingido || '—') + '</strong></div>' +
      '</div></div>' +
      '<div class="pi-op-context-actions">' +
        (!readOnly ? '<button type="button" class="' + buttonClass('edit') + '" data-context-action="edit">Editar campanha</button>' : '') +
        '<button type="button" class="' + buttonClass('follow') + '" data-context-action="follow">Ver acompanhamento</button>' +
        (!readOnly ? '<button type="button" class="' + buttonClass('duplicate') + '" data-context-action="duplicate">Duplicar campanha</button>' : '') +
        '<button type="button" class="' + buttonClass('email') + '" data-context-action="email">Preparar e-mail</button>' +
      '</div>';
    panel.hidden = false;
    scrollSidebarTo(panel);
    document.querySelectorAll('#pi_campanhas_container details').forEach(function (details) {
      details.classList.toggle('pi-op-campaign-selected', details.textContent.indexOf(campaign.nome_campanha || '\0') !== -1);
    });
    openSidebar();
    window.setTimeout(function () { title.focus({ preventScroll: true }); }, 0);
  }

  function legacyCampaignAction(action) {
    if (!selectedCampaign) return;
    if (action === 'edit') {
      if (typeof window.abrirModalEditarCampanha === 'function') {
        window.abrirModalEditarCampanha(selectedCampaign);
        return;
      }
      notify('Não foi possível abrir o editor desta campanha.', 'error');
      return;
    }
    if (action === 'follow' && mobileMedia.matches) {
      window.location.href = campaignDetailUrl(selectedCampaign.id_campanha);
      return;
    }
    if (action === 'follow' && typeof window.abrirViewCampanha === 'function') {
      window.abrirViewCampanha(selectedCampaign);
      return;
    }
    if (action === 'duplicate') {
      if (typeof window.abrirModalNovaCampanha === 'function') {
        window.abrirModalNovaCampanha();
        var form = document.getElementById('formNovaCampanha');
        if (form) {
          var name = form.querySelector('[name="nome_campanha"]');
          if (name) name.value = (selectedCampaign.nome_campanha || '') + ' (cópia)';
        }
      } else notify('Duplicação indisponível neste estágio.', 'warning');
      return;
    }
    if (action === 'email') {
      if (!savedEmailRecipients(operationData).length) {
        focusRecipientSelection();
        return;
      }
      var communications = document.getElementById('pi-communications-panel');
      scrollSidebarTo(communications);
      if (!communicationCatalog.length) notify('Nenhuma comunicação disponível para esta etapa.', 'warning');
    }
  }

  function emailDraft(type, campaignId, extra) {
    var subject = document.getElementById('pi-email-subject');
    var message = document.getElementById('pi-email-message');
    var sender = document.getElementById('pi-email-sender');
    var draft = {
      tipo: type,
      id_campanha: campaignId || null,
      assunto: subject ? subject.value.trim() : '',
      mensagem: message ? message.value.trim() : ''
    };
    if (sender && sender.value) draft.remetente_id = Number(sender.value);
    return Object.assign(draft, extra || {});
  }

  function senderLabel(item) {
    var name = item.nome || item.email || 'Pessoa da operação';
    var origin = item.origem === 'voce' ? 'Você'
      : item.origem === 'comercial' ? 'Comercial'
      : 'Operação';
    return origin + ' · ' + name;
  }

  function fillSenders(remetentes, selected) {
    var sender = document.getElementById('pi-email-sender');
    if (!sender) return;
    var items = list(remetentes);
    var selectedId = selected && selected.id != null ? String(selected.id) : '';
    if (!items.length && userName) {
      items = [{ id: root.dataset.userId, nome: userName, email: userEmail, origem: 'voce' }];
    }
    sender.innerHTML = items.map(function (item) {
      var id = item.id != null ? String(item.id) : '';
      return '<option value="' + esc(id) + '"' +
        (id && id === selectedId ? ' selected' : '') + '>' +
        esc(senderLabel(item)) + '</option>';
    }).join('');
  }

  function showPreviewVeil(mode, text) {
    var previewState = document.getElementById('pi-email-preview-state');
    if (!previewState) return;
    previewState.hidden = false;
    previewState.className = mode === 'error' ? 'pi-email-preview-veil is-error' : 'pi-email-preview-veil';
    previewState.innerHTML = mode === 'error'
      ? esc(text || 'Não foi possível gerar a prévia.')
      : '<span><i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i>' +
        esc(text || 'Gerando prévia') + '</span>';
  }

  function hidePreviewVeil() {
    var previewState = document.getElementById('pi-email-preview-state');
    if (previewState) previewState.hidden = true;
  }

  function recipientLabel(item) {
    var name = item.nome_completo || item.nome || item.email || 'Contato';
    var email = item.email && item.email !== name ? item.email : '';
    return '<li><span><strong>' + esc(name) + '</strong>' +
      (email ? '<small>' + esc(email) + '</small>' : '') +
      '</span><em>' + esc(String(item.papel || item.role || 'destinatário').replace('_', ' ')) +
      '</em></li>';
  }

  async function previewEmail(type, campaignId, draft) {
    if (!type) {
      notify('Selecione uma comunicação para gerar a prévia.', 'warning');
      var communications = document.getElementById('pi-communications-panel');
      openSidebar();
      scrollSidebarTo(communications);
      return;
    }
    if (!savedEmailRecipients(operationData).length) {
      focusRecipientSelection();
      return;
    }
    if (!emailDialog) {
      notify('Não foi possível abrir a preparação do e-mail.', 'error');
      return;
    }
    currentEmailType = type;
    currentEmailCampaignId = campaignId || null;
    if (!emailDialog.open) emailDialogOpener = document.activeElement;
    var context = document.getElementById('pi-email-context');
    var title = document.getElementById('pi-email-title');
    var frame = document.getElementById('pi-email-frame');
    var textPreview = document.getElementById('pi-email-text-preview');
    var status = document.getElementById('pi-email-status');
    var selectedCommunication = communicationCatalog.find(function (item) {
      return String(communicationId(item)) === String(type);
    });
    var communicationLabel = selectedCommunication ? communicationName(selectedCommunication) : 'Comunicação do PI';
    if (context) context.textContent = campaignId && selectedCampaign
      ? communicationLabel + ' · ' + (selectedCampaign.nome_campanha || 'Campanha')
      : communicationLabel;
    if (title) title.textContent = 'Preparar e-mail';
    if (status) status.textContent = '';
    emailPreviewReady = false;
    showPreviewVeil('loading');
    if (textPreview) textPreview.hidden = true;
    if (!emailDialog.open) emailDialog.showModal();
    try {
      var payload = Object.assign({ tipo: type, id_campanha: campaignId || null }, draft || emailDraft(type, campaignId));
      var data = await request(base + '/email/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      emailPreviewData = data;
      var recipients = list(data.destinatarios);
      var subject = document.getElementById('pi-email-subject');
      var message = document.getElementById('pi-email-message');
      var audience = document.getElementById('pi-email-audience');
      fillSenders(data.remetentes, data.remetente);
      if (subject && !subject.value) subject.value = data.assunto || '';
      if (audience) {
        audience.innerHTML = recipients.length
          ? '<strong>Para quem vai</strong><ul>' +
            recipients.map(recipientLabel).join('') + '</ul>'
          : '<div class="pi-op-error">Selecione ao menos um destinatário antes de enviar.</div>';
      }
      if (data.html && frame) {
        frame.hidden = false;
        frame.srcdoc = data.html;
      } else if (textPreview) {
        textPreview.textContent = data.corpo_texto || data.corpo || data.preview || 'Prévia sem conteúdo.';
        textPreview.hidden = false;
        hidePreviewVeil();
        emailPreviewReady = true;
      } else {
        hidePreviewVeil();
      }
      if (status) status.textContent = 'Prévia atualizada.';
      if (subject && !emailDialog.dataset.focused) {
        subject.focus({ preventScroll: true });
        emailDialog.dataset.focused = '1';
      }
    } catch (error) {
      showPreviewVeil('error', error.message);
      if (status) status.textContent = 'Não foi possível gerar a prévia.';
      notify(error.message, 'error');
    }
  }

  async function sendEmail(type, campaignId, button) {
    var recipients = list(emailPreviewData && emailPreviewData.destinatarios);
    if (!recipients.length) {
      notify('Selecione os destinatários e atualize a prévia antes de enviar.', 'warning');
      return;
    }
    var confirmed = await confirmAction({
      title: 'Enviar comunicação',
      message: 'Revise quem receberá esta comunicação. O envio não poderá ser desfeito.',
      details: recipients,
      kind: 'email',
      confirmText: recipients.length === 1 ? 'Enviar para 1 pessoa' : 'Enviar para ' + recipients.length + ' pessoas'
    });
    if (!confirmed) return;
    setBusy(button, true, 'Enviando…');
    try {
      var data = await request(base + '/email/enviar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emailDraft(type, campaignId))
      });
      notify(data.message || 'E-mail enviado com sucesso.', 'success');
      if (emailDialog && emailDialog.open) emailDialog.close('sent');
      loadOperation();
    } catch (error) { notify(error.message, 'error'); }
    finally { setBusy(button, false); }
  }

  async function sendTestEmail(type, campaignId, button) {
    if (!userEmail) {
      notify('Seu usuário não tem e-mail para receber o teste.', 'warning');
      return;
    }
    if (!emailPreviewData) {
      notify('Gere a prévia antes de enviar o teste.', 'warning');
      return;
    }
    setBusy(button, true, 'Enviando teste…');
    try {
      var data = await request(base + '/email/enviar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emailDraft(type, campaignId, { teste: true }))
      });
      notify(data.message || ('Teste enviado para ' + userEmail + '.'), 'success');
      var status = document.getElementById('pi-email-status');
      if (status) status.textContent = 'Teste enviado para ' + userEmail + '.';
    } catch (error) { notify(error.message, 'error'); }
    finally { setBusy(button, false); }
  }

  function initDrive() {
    var dialog = document.getElementById('modal_arquivos_pi');
    if (!dialog) return;
    var content = document.getElementById('pi-drive-content');
    var external = document.getElementById('pi-drive-external');

    function folderIdFromUrl(url) {
      try {
        var parsed = new URL(url);
        if (parsed.protocol !== 'https:' || parsed.hostname !== 'drive.google.com') return null;
        var pathMatch = parsed.pathname.match(/\/folders\/([a-zA-Z0-9_-]+)/);
        if (pathMatch) return pathMatch[1];
        var fileMatch = parsed.pathname.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
        if (fileMatch) return fileMatch[1];
        return parsed.searchParams.get('id');
      } catch (_) { return null; }
    }

    function validDrive(url) {
      return Boolean(folderIdFromUrl(url));
    }

    function embedUrl(url) {
      var folderId = folderIdFromUrl(url);
      return folderId
        ? 'https://drive.google.com/embeddedfolderview?id=' + encodeURIComponent(folderId) + '#grid'
        : null;
    }

    function showTab(button) {
      dialog.querySelectorAll('[data-drive-tab]').forEach(function (tab) {
        tab.setAttribute('aria-selected', tab === button ? 'true' : 'false');
      });
      var raw = button.dataset.driveUrl || '';
      var folderId = folderIdFromUrl(raw);
      var hasDriveLink = Boolean(folderId);
      external.hidden = !hasDriveLink;
      external.href = hasDriveLink ? raw : '#';
      var embedded = embedUrl(raw);
      if (!raw) {
        content.innerHTML = '<div class="pi-op-state">Esta pasta ainda não foi gerada.</div>';
      } else if (!embedded) {
        content.innerHTML = errorHtml('O endereço informado não é uma pasta permitida do Google Drive.');
      } else {
        content.innerHTML = '';
        var wrap = document.createElement('div');
        wrap.className = 'pi-drive-embed-wrap';
        var fallback = document.createElement('div');
        fallback.className = 'pi-drive-fallback';
        fallback.innerHTML = 'Se a visualização abaixo não carregar, ' +
          '<a href="' + esc(raw) + '" target="_blank" rel="noopener noreferrer">abra esta pasta no Google Drive</a>.';
        wrap.appendChild(fallback);
        var iframe = document.createElement('iframe');
        iframe.title = 'Conteúdo da pasta ' + button.textContent.trim();
        iframe.loading = 'eager';
        iframe.allow = 'autoplay';
        iframe.src = embedded;
        wrap.appendChild(iframe);
        content.appendChild(wrap);
      }
    }
    window.abrirArquivosPi = function () {
      if (!dialog.open) dialog.showModal();
      showTab(dialog.querySelector('[data-drive-tab][aria-selected="true"]'));
    };
    dialog.querySelectorAll('[data-drive-tab]').forEach(function (button) {
      button.addEventListener('click', function () { showTab(button); });
    });
    dialog.querySelectorAll('[data-drive-close]').forEach(function (button) {
      button.addEventListener('click', function () { dialog.close(); });
    });
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });
  }

  initMobileWorkspace();
  if (sidebarTrigger) sidebarTrigger.addEventListener('click', openSidebar);
  if (confirmDialog) {
    confirmDialog.addEventListener('close', function () {
      if (!confirmationResolve) return;
      var resolve = confirmationResolve;
      confirmationResolve = null;
      resolve(confirmDialog.returnValue === 'confirm');
    });
  }
  if (emailDialog) {
    emailDialog.querySelectorAll('[data-email-close]').forEach(function (button) {
      button.addEventListener('click', function () { emailDialog.close('cancel'); });
    });
    emailDialog.addEventListener('click', function (event) {
      if (event.target === emailDialog) emailDialog.close('cancel');
    });
    emailDialog.addEventListener('close', function () {
      delete emailDialog.dataset.focused;
      emailPreviewReady = false;
      if (emailDialogOpener && typeof emailDialogOpener.focus === 'function') {
        emailDialogOpener.focus({ preventScroll: true });
      }
      emailDialogOpener = null;
    });
    var frame = document.getElementById('pi-email-frame');
    if (frame) {
      frame.addEventListener('load', function () {
        if (!frame.getAttribute('srcdoc')) return;
        hidePreviewVeil();
        emailPreviewReady = true;
      });
    }
    var sender = document.getElementById('pi-email-sender');
    if (sender) {
      sender.addEventListener('change', function () {
        if (!currentEmailType) return;
        previewEmail(
          currentEmailType,
          currentEmailCampaignId,
          emailDraft(currentEmailType, currentEmailCampaignId)
        );
      });
    }
    var refreshEmail = document.getElementById('pi-email-refresh');
    if (refreshEmail) refreshEmail.addEventListener('click', function () {
      previewEmail(
        currentEmailType,
        currentEmailCampaignId,
        emailDraft(currentEmailType, currentEmailCampaignId)
      );
    });
    var testEmailButton = document.getElementById('pi-email-test');
    if (testEmailButton) {
      if (userEmail) {
        testEmailButton.textContent = 'Enviar teste para ' + userEmail;
      }
      testEmailButton.addEventListener('click', function () {
        sendTestEmail(currentEmailType, currentEmailCampaignId, testEmailButton);
      });
    }
    var sendEmailButton = document.getElementById('pi-email-send');
    if (sendEmailButton) sendEmailButton.addEventListener('click', function () {
      sendEmail(currentEmailType, currentEmailCampaignId, sendEmailButton);
    });
  }
  document.querySelectorAll('[data-sidebar-close]').forEach(function (button) { button.addEventListener('click', closeSidebar); });
  if (sidebarScroll) {
    sidebarScroll.scrollTop = Number(sessionStorage.getItem(scrollKey) || 0);
    sidebarScroll.addEventListener('scroll', function () { sessionStorage.setItem(scrollKey, String(sidebarScroll.scrollTop)); }, { passive: true });
  }
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) closeSidebar();
  });
  document.addEventListener('toggle', function (event) {
    var current = event.target;
    if (!current.matches || !current.matches('.pi-op-campaign-checklist') || !current.open) return;
    document.querySelectorAll('.pi-op-campaign-checklist[open]').forEach(function (item) {
      if (item !== current) item.open = false;
    });
  }, true);

  var checklistGenerate = document.getElementById('pi-checklist-generate');
  if (checklistGenerate) {
    checklistGenerate.hidden = readOnly;
    checklistGenerate.addEventListener('click', async function () {
      setBusy(this, true, 'Atualizando…');
      try {
        var options = { method: 'POST' };
        if (campaignId) {
          options.headers = { 'Content-Type': 'application/json' };
          options.body = JSON.stringify({ campanhas: [campaignId] });
        }
        var data = await request(base + '/checklist/gerar', options);
        if (campaignId) {
          await loadOperation();
        } else {
          renderChecklist(data);
          renderRecommendation(data);
        }
        notify(data.message || 'Checklist atualizado.', 'success');
      } catch (error) { notify(error.message, 'error'); }
      finally { setBusy(this, false); }
    });
  }

  document.addEventListener('change', async function (event) {
    var checkbox = event.target.closest('[data-checklist-id]');
    if (!checkbox) return;
    checkbox.disabled = true;
    try {
      await request(base + '/checklist/' + encodeURIComponent(checkbox.dataset.checklistId), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concluido: checkbox.checked })
      });
      await loadOperation();
    } catch (error) {
      checkbox.checked = !checkbox.checked;
      notify(error.message, 'error');
    } finally { checkbox.disabled = false; }
  });

  var interactionForm = document.getElementById('pi-interaction-form');
  if (interactionForm) {
    if (readOnly) interactionForm.hidden = true;
    interactionForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      var input = document.getElementById('pi-interaction-text');
      var text = input.value.trim();
      if (!text) { input.focus(); return; }
      var button = interactionForm.querySelector('button');
      setBusy(button, true, 'Registrando…');
      try {
        var data = await request(base + '/interacoes', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ descricao: text, tipo: 'nota' })
        });
        input.value = '';
        notify(data.message || 'Interação registrada.', 'success');
        loadOperation();
      } catch (error) { notify(error.message, 'error'); }
      finally { setBusy(button, false); }
    });
  }

  var recipientsForm = document.getElementById('pi-recipients-form');
  if (recipientsForm && !readOnly) {
    recipientsForm.addEventListener('change', function (event) {
      if (event.target.matches('[data-recipient-id]')) updateRecipientCount();
    });
    recipientsForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      var checked = recipientsForm.querySelectorAll('[data-recipient-id]:checked');
      if (!checked.length) {
        notify('Selecione ao menos um destinatário.', 'warning');
        return;
      }
      var withoutEmail = Array.prototype.find.call(checked, function (input) {
        return input.dataset.hasEmail !== 'true';
      });
      if (withoutEmail) {
        notify('Remova os contatos sem e-mail antes de salvar.', 'warning');
        withoutEmail.focus();
        return;
      }
      var defaultRoles = {};
      var recipients = Array.prototype.map.call(
        checked,
        function (input) {
          var role = input.dataset.recipientRole;
          var isDefault = !defaultRoles[role];
          defaultRoles[role] = true;
          return {
            id_contato_cliente: Number(input.dataset.recipientId),
            papel: role,
            padrao: isDefault
          };
        }
      );
      var button = recipientsForm.querySelector('button');
      setBusy(button, true, 'Atualizando…');
      try {
        var data = await request(base + '/destinatarios', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ destinatarios: recipients })
        });
        notify(data.message || 'Destinatários salvos.', 'success');
        await loadOperation();
      } catch (error) { notify(error.message, 'error'); }
      finally {
        setBusy(button, false);
        updateRecipientCount();
      }
    });
  }

  document.addEventListener('click', function (event) {
    var campaignLink = event.target.closest('[data-campaign-link]');
    if (campaignLink) {
      event.stopPropagation();
      return;
    }
    var retryRecipients = event.target.closest('[data-retry-recipients]');
    if (retryRecipients) {
      var recipientTarget = document.getElementById('pi-recipient-options');
      if (recipientTarget) {
        recipientTarget.className = 'pi-op-state';
        recipientTarget.textContent = 'Carregando contatos disponíveis…';
      }
      loadOperation();
      return;
    }
    var communication = event.target.closest('[data-communication]');
    if (communication) {
      if (!savedEmailRecipients(operationData).length) {
        focusRecipientSelection();
        return;
      }
      previewEmail(communication.dataset.communication, selectedCampaign && selectedCampaign.id_campanha);
      openSidebar();
      return;
    }
    var chooseRecipients = event.target.closest('[data-choose-recipients]');
    if (chooseRecipients) {
      focusRecipientSelection();
      return;
    }
    var send = event.target.closest('[data-send-email]');
    if (send) {
      sendEmail(send.dataset.sendEmail, selectedCampaign && selectedCampaign.id_campanha, send);
      return;
    }
    var refresh = event.target.closest('[data-refresh-email]');
    if (refresh) {
      var draft = emailDraft(refresh.dataset.refreshEmail, selectedCampaign && selectedCampaign.id_campanha);
      previewEmail(refresh.dataset.refreshEmail, selectedCampaign && selectedCampaign.id_campanha, draft);
      return;
    }
    var contextual = event.target.closest('[data-context-action]');
    if (contextual) legacyCampaignAction(contextual.dataset.contextAction);
  });

  document.addEventListener('click', function (event) {
    var button = event.target.closest('.btn-editar-camp, .btn-ver-camp, .btn-duplicar-camp, .btn-email-camp');
    if (!button) return;
    var payload = button.dataset.campEdit || button.dataset.campView || button.dataset.campContext;
    var campaign = decodePayload(payload);
    if (!campaign) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    var action = button.classList.contains('btn-editar-camp') ? 'edit'
      : button.classList.contains('btn-duplicar-camp') ? 'duplicate'
      : button.classList.contains('btn-email-camp') ? 'email'
      : 'follow';
    selectedCampaign = campaign;
    if (action === 'edit') {
      campaignPanel(campaign, 'edit');
      legacyCampaignAction('edit');
      return;
    }
    if (action === 'follow' && mobileMedia.matches) {
      legacyCampaignAction('follow');
      return;
    }
    campaignPanel(campaign, action);
  }, true);

  var previewAll = document.getElementById('pi-preview-emails');
  if (previewAll) previewAll.addEventListener('click', function () {
    if (!savedEmailRecipients(operationData).length) {
      focusRecipientSelection();
      return;
    }
    if (!campaignId) selectedCampaign = null;
    var communications = document.getElementById('pi-communications-panel');
    openSidebar();
    if (communications) sidebarScroll.scrollTop = communications.offsetTop - 12;
  });

  var driveButton = document.getElementById('pi-open-drive');
  if (driveButton) driveButton.addEventListener('click', function () {
    if (typeof window.abrirArquivosPi === 'function') window.abrirArquivosPi();
  });

  initDrive();
  if (piId) {
    loadOperation();
    if (document.getElementById('pi-operation-communications')) loadCatalog();
  }

  window.piOperacao = {
    abrirCampanha: campaignPanel,
    recarregar: function () { return Promise.all([loadOperation(), loadCatalog()]); },
    atualizarDestinatarios: function (destinatarios) {
      return request(base + '/destinatarios', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destinatarios: destinatarios })
      });
    },
    confirmar: confirmAction,
    mostrarArea: function (view, focusPanel) {
      setMobileView(view, { focusPanel: Boolean(focusPanel) });
    },
    etapa: stage
  };
})();
