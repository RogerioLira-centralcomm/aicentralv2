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
  var scrollKey = 'cx:pi-operacao:' + piId + ':sidebar-scroll';
  var selectedCampaign = null;
  var operationData = null;
  var communicationCatalog = [];
  var emailPreviewData = null;
  var feedbackTimer = null;
  var confirmationResolve = null;
  var sidebarOpener = null;

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

  function renderRelatedCampaigns(data) {
    var target = document.getElementById('pi-related-campaigns');
    if (!target) return;
    var back = document.getElementById('pi-related-back');
    if (back) back.href = piDetailUrl();
    var campaigns = list(data.campanhas_relacionadas);
    target.className = '';
    target.innerHTML = campaigns.length
      ? '<div class="pi-op-related__list">' + campaigns.map(function (campaign) {
          var current = Boolean(campaign.atual) ||
            Number(campaign.id_campanha) === campaignId;
          return '<a class="pi-op-related__item' + (current ? ' is-current' : '') +
            '" href="' + esc(campaignDetailUrl(campaign.id_campanha)) + '"' +
            (current ? ' aria-current="page"' : '') + '><span>' +
            esc(campaign.nome || ('Campanha ' + campaign.id_campanha)) +
            '</span><small>' + esc(current ? 'Atual' : (campaign.plataforma || 'Abrir')) +
            '</small></a>';
        }).join('') + '</div>'
      : '<div class="pi-op-state">Nenhuma outra campanha neste PI.</div>';
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
      if (submit) submit.disabled = true;
      return;
    }
    var selected = list(data.destinatarios || data.recipients);
    var available = list(data.contatos_disponiveis || data.available_contacts);
    var recipientId = function (item) {
      if (item == null) return '';
      if (typeof item !== 'object') return String(item);
      return String(item.id_contato_cliente || item.contato_id || item.id || '');
    };
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
    if (submit) submit.disabled = readOnly || total === 0 || invalid;
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
    target.innerHTML = '<div class="pi-op-stack">' + communicationCatalog.map(function (item) {
      return '<button type="button" class="pi-op-btn pi-op-btn--secondary" data-communication="' +
        esc(communicationId(item)) + '"><i class="fa-regular fa-envelope" aria-hidden="true"></i>' +
        esc(communicationName(item)) + '</button>';
    }).join('') + '</div>';
  }

  async function loadOperation() {
    if (!piId) return;
    try {
      operationData = await request(stateUrl);
      renderRecommendation(operationData);
      renderChecklist(operationData);
      renderRelatedCampaigns(operationData);
      renderTimeline(operationData);
      renderRecipients(operationData);
    } catch (error) {
      var target = document.getElementById('pi-operation-recommendation');
      if (target) target.innerHTML = errorHtml(error.message);
      renderChecklist({});
      renderRelatedCampaigns({});
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
    sidebarScroll.scrollTo({ top: panel.offsetTop - 12, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    document.querySelectorAll('#pi_campanhas_container details').forEach(function (details) {
      details.classList.toggle('pi-op-campaign-selected', details.textContent.indexOf(campaign.nome_campanha || '\0') !== -1);
    });
    openSidebar();
    window.setTimeout(function () { title.focus({ preventScroll: true }); }, 0);
  }

  function legacyCampaignAction(action) {
    if (!selectedCampaign) return;
    if (action === 'edit' && typeof window.abrirModalEditarCampanha === 'function') {
      window.abrirModalEditarCampanha(selectedCampaign);
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
      var communications = document.getElementById('pi-communications-panel');
      if (communications) sidebarScroll.scrollTo({ top: communications.offsetTop - 12, behavior: 'smooth' });
      if (!communicationCatalog.length) notify('Nenhuma comunicação disponível para esta etapa.', 'warning');
    }
  }

  function emailDraft(type, campaignId) {
    var subject = document.getElementById('pi-email-subject');
    var message = document.getElementById('pi-email-message');
    return {
      tipo: type,
      id_campanha: campaignId || null,
      assunto: subject ? subject.value.trim() : '',
      mensagem: message ? message.value.trim() : ''
    };
  }

  async function previewEmail(type, campaignId, draft) {
    var target = document.getElementById('pi-context-content');
    try {
      var payload = Object.assign({ tipo: type, id_campanha: campaignId || null }, draft || {});
      var data = await request(base + '/email/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (target) {
        emailPreviewData = data;
        var recipients = list(data.destinatarios);
        var audience = recipients.length
          ? '<div class="pi-op-email-audience"><strong>Destinatários: ' + esc(recipients.length) + '</strong><br>' +
            recipients.map(function (item) { return esc(item.nome_completo || item.email); }).join(', ') + '</div>'
          : '<div class="pi-op-error">Selecione ao menos um destinatário antes de enviar.</div>';
        target.innerHTML = '<div class="pi-op-stack">' +
          '<label for="pi-email-subject"><strong>Assunto</strong></label>' +
          '<input id="pi-email-subject" maxlength="180" value="' + esc(data.assunto || payload.assunto || '') + '">' +
          '<label for="pi-email-message"><strong>Mensagem complementar</strong></label>' +
          '<textarea id="pi-email-message" rows="4" maxlength="5000" placeholder="Inclua contexto adicional, se necessário.">' + esc(payload.mensagem || '') + '</textarea>' +
          audience +
          (data.html
            ? '<iframe class="pi-op-email-frame" sandbox="" title="Pré-visualização do e-mail" srcdoc="' + esc(data.html) + '"></iframe>'
            : '<div class="pi-op-email-preview">' + esc(data.corpo_texto || data.corpo || data.preview || 'Preview sem conteúdo.') + '</div>') +
          (!readOnly
            ? '<div class="pi-op-context-actions">' +
                '<button type="button" class="pi-op-btn pi-op-btn--secondary" data-refresh-email="' + esc(type) + '">Atualizar prévia</button>' +
                '<button type="button" class="pi-op-btn pi-op-btn--primary" data-send-email="' + esc(type) + '">Enviar e-mail</button>' +
              '</div>'
            : '') + '</div>';
        document.getElementById('pi-context-panel').hidden = false;
      }
    } catch (error) { notify(error.message, 'error'); }
  }

  async function sendEmail(type, campaignId, button) {
    var recipients = list(emailPreviewData && emailPreviewData.destinatarios);
    if (!recipients.length) {
      notify('Selecione os destinatários e atualize a prévia antes de enviar.', 'warning');
      return;
    }
    var confirmed = await confirmAction({
      title: 'Enviar comunicação',
      message: 'Enviar este e-mail para ' + recipients.length +
        (recipients.length === 1 ? ' destinatário?' : ' destinatários?'),
      confirmText: 'Enviar e-mail'
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
      loadOperation();
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

  if (sidebarTrigger) sidebarTrigger.addEventListener('click', openSidebar);
  if (confirmDialog) {
    confirmDialog.addEventListener('close', function () {
      if (!confirmationResolve) return;
      var resolve = confirmationResolve;
      confirmationResolve = null;
      resolve(confirmDialog.returnValue === 'confirm');
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
      finally { setBusy(button, false); }
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
      previewEmail(communication.dataset.communication, selectedCampaign && selectedCampaign.id_campanha);
      openSidebar();
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
    campaignPanel(campaign, action);
  }, true);

  var previewAll = document.getElementById('pi-preview-emails');
  if (previewAll) previewAll.addEventListener('click', function () {
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
    etapa: stage
  };
})();
