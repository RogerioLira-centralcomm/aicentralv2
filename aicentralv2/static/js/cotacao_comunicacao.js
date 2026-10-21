(function () {
  'use strict';

  function esc(value) {
    var node = document.createElement('span');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  function recipientId(item) {
    if (item == null) return '';
    if (typeof item !== 'object') return String(item);
    return String(item.id_contato_cliente || item.contato_id || item.id || '');
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

  function init(options) {
    if (!options || !options.cotacaoId) return;
    var cotacaoId = Number(options.cotacaoId);
    var readOnly = Boolean(options.readOnly);
    var base = '/api/cotacoes/' + cotacaoId + '/comunicacao';
    var state = null;
    var saveBtn = document.querySelector('.cot-recipients-save');

    if (readOnly && saveBtn) {
      saveBtn.hidden = true;
    }

    var sentEmailDialogCtrl = window.ComunicacaoSidebar
      ? window.ComunicacaoSidebar.initSentEmailDialog(
        document.getElementById('cot-sent-email-dialog'),
        {
          frame: '#cot-sent-email-frame',
          title: '#cot-sent-email-title',
          context: '#cot-sent-email-context',
          veil: '#cot-sent-email-preview-state',
          close: '[data-cot-sent-email-close]'
        }
      )
      : null;

    async function request(url, opts) {
      var response = await fetch(url, Object.assign({ credentials: 'same-origin' }, opts || {}));
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message || payload.error || 'Não foi possível concluir a solicitação.');
      }
      return payload.data != null ? payload.data : payload;
    }

    function notify(message, type) {
      if (typeof window.showToast === 'function') {
        window.showToast(message, type || 'info');
      }
    }

    function updateRecipientCount() {
      var form = document.getElementById('cot-recipients-form');
      var count = document.getElementById('cot-recipient-count');
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

    function renderRecipients(data) {
      var target = document.getElementById('cot-recipient-options');
      if (!target) return;
      data = data && typeof data === 'object' ? data : {};
      var form = document.getElementById('cot-recipients-form');
      if (data.recipient_error) {
        target.className = '';
        target.innerHTML = '<div class="pi-op-error">' + esc(data.recipient_error) + '</div>';
        if (form) form.dataset.savedRecipientSignature = '';
        return;
      }
      var selected = list(data.destinatarios);
      var available = list(data.contatos_disponiveis);
      if (form) {
        form.dataset.savedRecipientSignature = data.destinatarios_confirmados
          ? recipientSignature(selected)
          : '';
      }
      var selectedById = {};
      selected.forEach(function (item) {
        var id = recipientId(item);
        if (id) selectedById[id] = item;
      });
      var availableIds = {};
      available = available.filter(function (item) {
        var id = recipientId(item);
        if (!id || availableIds[id]) return false;
        availableIds[id] = true;
        return true;
      });
      var cot = data.cotacao || {};
      var groups = { cliente_final: [], agencia: [], parceiro: [] };
      available.forEach(function (item) {
        var id = recipientId(item);
        var active = selectedById[id];
        var role = (active && active.papel) ||
          (cot.id_parceiro && String(item.pk_id_tbl_cliente) === String(cot.id_parceiro) ? 'parceiro' :
            (cot.id_agencia && String(item.pk_id_tbl_cliente) === String(cot.id_agencia) ? 'agencia' : 'cliente_final'));
        if (!groups[role]) role = 'cliente_final';
        groups[role].push({ item: item, id: id, active: active, role: role });
      });
      function groupHtml(role, label) {
        var entityId = role === 'agencia' ? cot.id_agencia : role === 'parceiro' ? cot.id_parceiro : cot.id_cliente;
        var items = groups[role] || [];
        if (!items.length && !entityId) return '';
        if (!items.length) {
          return '<fieldset class="pi-op-recipient-group"><legend>' + esc(label) + '</legend>' +
            '<p class="pi-op-state">Nenhum contato neste grupo.</p></fieldset>';
        }
        return '<fieldset class="pi-op-recipient-group"><legend>' + esc(label) + '</legend>' +
          items.map(function (entry) {
            var item = entry.item;
            var hasEmail = Boolean(String(item.email || '').trim());
            var disabled = readOnly || (!hasEmail && !entry.active);
            var setorLine = (item.setor || '').trim() || 'Sem setor';
            var detail = hasEmail
              ? esc(item.email) + ' · ' + esc(setorLine)
              : '<span class="pi-op-recipient-missing">Sem e-mail cadastrado</span>';
            return '<label class="pi-op-check pi-op-recipient' + (!hasEmail ? ' has-warning' : '') + '">' +
              '<input type="checkbox" data-recipient-id="' + esc(entry.id) +
              '" data-recipient-role="' + esc(entry.role) + '" data-has-email="' + (hasEmail ? 'true' : 'false') + '"' +
              (entry.active ? ' checked' : '') + (disabled ? ' disabled' : '') + '>' +
              '<span><strong>' + esc(item.nome_completo || item.email || 'Contato') +
              '</strong><small class="block">' + detail + '</small></span></label>';
          }).join('') + '</fieldset>';
      }
      target.className = 'pi-op-recipient-groups';
      target.innerHTML = groupHtml('cliente_final', 'Cliente') +
        groupHtml('agencia', 'Agência') +
        groupHtml('parceiro', 'Parceiro');
      updateRecipientCount();
      if (window.ComunicacaoSidebar) {
        window.ComunicacaoSidebar.renderRecipientSummary(
          document.getElementById('cot-recipient-summary'),
          data
        );
      }
    }

    function renderSentEmailHistory(data) {
      var target = document.getElementById('cot-email-sent-list');
      if (!target || !window.ComunicacaoSidebar) return;
      window.ComunicacaoSidebar.renderSentEmails(target, list(data && data.emails));
      window.ComunicacaoSidebar.bindSentEmailClicks(target, async function (logId) {
        if (!sentEmailDialogCtrl) return;
        var meta = list(state && state.emails).find(function (item) {
          return String(item.id) === String(logId);
        }) || { id: logId };
        await sentEmailDialogCtrl.open(meta, async function () {
          var row = await request(base + '/emails/' + encodeURIComponent(logId));
          return row.html;
        });
      });
    }

    function syncCcEditor(data) {
      if (!window.ComunicacaoCcEditor) return;
      if (!window.cotacaoEmailCc) {
        window.cotacaoEmailCc = window.ComunicacaoCcEditor.create(null);
      }
      var ccHost = document.getElementById('cotacao-email-cc');
      if (!ccHost) return;
      var emails = list(data && data.cc_emails_padrao);
      window.cotacaoEmailCc.mount(ccHost);
      window.cotacaoEmailCc.reset(emails);
      window.cotacaoCcPadrao = emails.slice();
    }

    async function load() {
      try {
        state = await request(base);
        renderRecipients(state);
        syncCcEditor(state);
        renderSentEmailHistory(state);
      } catch (error) {
        var target = document.getElementById('cot-recipient-options');
        if (target) target.innerHTML = '<div class="pi-op-error">' + esc(error.message) + '</div>';
        renderSentEmailHistory({});
      }
    }

    var form = document.getElementById('cot-recipients-form');
    if (form && !readOnly) {
      form.addEventListener('change', function (event) {
        if (event.target.matches('[data-recipient-id]')) updateRecipientCount();
      });
      form.addEventListener('submit', async function (event) {
        event.preventDefault();
        var checked = form.querySelectorAll('[data-recipient-id]:checked');
        if (!checked.length) {
          notify('Selecione ao menos um destinatário.', 'warning');
          return;
        }
        var defaultRoles = {};
        var recipients = Array.prototype.map.call(checked, function (input) {
          var role = input.dataset.recipientRole;
          var isDefault = !defaultRoles[role];
          defaultRoles[role] = true;
          return {
            id_contato_cliente: Number(input.dataset.recipientId),
            papel: role,
            padrao: isDefault
          };
        });
        var button = form.querySelector('button[type="submit"]');
        if (button) button.disabled = true;
        try {
          await request(base + '/destinatarios', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destinatarios: recipients })
          });
          notify('Destinatários salvos.', 'success');
          await load();
        } catch (error) {
          notify(error.message, 'error');
        } finally {
          updateRecipientCount();
        }
      });
    }

    load();
    window.CotacaoComunicacao = { reload: load, syncCcEditor: syncCcEditor };
  }

  window.initCotacaoComunicacao = init;
})();
