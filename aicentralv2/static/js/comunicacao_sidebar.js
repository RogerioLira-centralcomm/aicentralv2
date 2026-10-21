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

  function roleLabel(papel) {
    var map = {
      cliente_final: 'Cliente',
      agencia: 'Agência',
      parceiro: 'Parceiro'
    };
    return map[papel] || String(papel || '').replace('_', ' ') || 'Contato';
  }

  function formatDate(value) {
    if (!value) return '';
    try {
      var date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return new Intl.DateTimeFormat('pt-BR', {
        dateStyle: 'short',
        timeStyle: 'short'
      }).format(date);
    } catch (_) {
      return String(value);
    }
  }

  function summaryContacts(data) {
    data = data && typeof data === 'object' ? data : {};
    var saved = data.destinatarios_confirmados === true
      ? list(data.destinatarios || data.recipients)
      : [];
    var withEmail = saved.filter(function (item) {
      return item && String(item.email || '').trim();
    });
    if (withEmail.length) {
      return withEmail.map(function (item) {
        return {
          email: String(item.email).trim(),
          nome: item.nome_completo || item.nome || item.email,
          papel: item.papel || item.role || ''
        };
      });
    }
    var suggested = list(data.destinatarios || data.recipients);
    var fromSuggested = suggested.filter(function (item) {
      return item && (item.responsavel_setor === true || item.sugerido) &&
        String(item.email || '').trim();
    });
    if (fromSuggested.length) {
      return fromSuggested.map(function (item) {
        return {
          email: String(item.email).trim(),
          nome: item.nome_completo || item.email,
          papel: item.papel || ''
        };
      });
    }
    return list(data.contatos_disponiveis).filter(function (item) {
      return item && item.responsavel_setor === true && String(item.email || '').trim();
    }).map(function (item) {
      var pi = data.pi || data.cotacao || {};
      var empresa = item.pk_id_tbl_cliente;
      var papel = 'cliente_final';
      if (pi.id_agencia && String(empresa) === String(pi.id_agencia)) papel = 'agencia';
      else if (pi.agencia_id && String(empresa) === String(pi.agencia_id)) papel = 'agencia';
      else if (pi.id_parceiro && String(empresa) === String(pi.id_parceiro)) papel = 'parceiro';
      return {
        email: String(item.email).trim(),
        nome: item.nome_completo || item.email,
        papel: papel
      };
    });
  }

  function renderRecipientSummary(container, data) {
    if (!container) return;
    var contacts = summaryContacts(data);
    if (!contacts.length) {
      container.innerHTML = '<span class="pi-op-state pi-op-recipient-summary-empty">Nenhum responsável com e-mail</span>';
      return;
    }
    container.innerHTML = contacts.map(function (item) {
      return '<span class="pi-op-recipient-chip" title="' + esc(roleLabel(item.papel)) + '">' +
        esc(item.email) + '</span>';
    }).join('');
  }

  function statusLabel(status) {
    if (status === 'sucesso') return 'Enviado';
    if (status === 'erro') return 'Falha';
    if (status === 'pendente') return 'Pendente';
    return status || '';
  }

  function renderSentEmails(container, emails, options) {
    if (!container) return;
    options = options || {};
    var items = list(emails);
    if (!items.length) {
      container.innerHTML = '<div class="pi-op-state">Nenhum e-mail registrado para cliente, agência ou parceiro.</div>';
      return;
    }
    container.innerHTML = '<ul class="pi-op-sent-email-list">' + items.map(function (item) {
      var id = item.id != null ? String(item.id) : '';
      var when = formatDate(item.enviado_em || item.created_at);
      var subject = item.assunto || item.tipo || 'Comunicação';
      var dest = item.destinatario_email || '';
      var destName = item.destinatario_nome || dest;
      var status = statusLabel(item.status);
      var disabled = !id || item.status === 'erro' && !options.allowErrorPreview;
      return '<li><button type="button" class="pi-op-sent-email"' +
        (id ? ' data-sent-email-id="' + esc(id) + '"' : '') +
        (disabled ? ' disabled' : '') + '>' +
        '<strong>' + esc(subject) + '</strong>' +
        '<small>' + esc(destName) + (dest && destName !== dest ? ' · ' + esc(dest) : '') + '</small>' +
        (when ? '<em>' + esc(when) + ' · ' + esc(status) + '</em>' : '<em>' + esc(status) + '</em>') +
        '</button></li>';
    }).join('') + '</ul>';
  }

  function bindSentEmailClicks(container, fetchEmail) {
    if (!container || typeof fetchEmail !== 'function') return;
    container.querySelectorAll('[data-sent-email-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        var logId = button.dataset.sentEmailId;
        if (!logId) return;
        fetchEmail(logId);
      });
    });
  }

  function initSentEmailDialog(dialog, selectors) {
    if (!dialog) return {};
    selectors = selectors || {};
    var frame = document.querySelector(selectors.frame || '#pi-sent-email-frame');
    var title = document.querySelector(selectors.title || '#pi-sent-email-title');
    var context = document.querySelector(selectors.context || '#pi-sent-email-context');
    var veil = document.querySelector(selectors.veil || '#pi-sent-email-preview-state');
    var closeSelector = selectors.close || '[data-sent-email-close]';

    dialog.querySelectorAll(closeSelector).forEach(function (button) {
      button.addEventListener('click', function () {
        if (dialog.open) dialog.close();
      });
    });

    function showVeil(text) {
      if (!veil) return;
      veil.hidden = false;
      veil.innerHTML = '<span><i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i>' +
        esc(text || 'Carregando e-mail') + '</span>';
    }

    function hideVeil() {
      if (veil) veil.hidden = true;
    }

    async function open(logMeta, loadHtml) {
      if (!dialog.open) dialog.showModal();
      if (context) context.textContent = logMeta.tipo || 'E-mail enviado';
      if (title) title.textContent = logMeta.assunto || 'Comunicação';
      if (frame) frame.hidden = true;
      showVeil();
      try {
        var html = typeof loadHtml === 'function' ? await loadHtml(logMeta) : logMeta.html;
        if (!html) {
          showVeil('Conteúdo indisponível para este envio.');
          return;
        }
        hideVeil();
        if (frame) {
          frame.hidden = false;
          frame.srcdoc = html;
        }
      } catch (error) {
        showVeil(error.message || 'Não foi possível abrir o e-mail.');
      }
    }

    return { open: open };
  }

  function createCcEditor(container) {
    var host = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    var emails = [];

    function render() {
      if (!host) return;
      if (!emails.length) {
        host.innerHTML = '<span class="comm-cc-empty">Nenhum endereço em cópia (Cc).</span>';
        return;
      }
      host.innerHTML = emails.map(function (email, index) {
        return '<span class="comm-cc-chip">' +
          '<span class="comm-cc-chip__label">' + esc(email) + '</span>' +
          '<button type="button" class="comm-cc-chip__remove" data-cc-index="' + index + '" ' +
          'aria-label="Remover ' + esc(email) + ' da cópia">&times;</button>' +
          '</span>';
      }).join('');
      host.querySelectorAll('[data-cc-index]').forEach(function (button) {
        button.addEventListener('click', function () {
          var idx = Number(button.getAttribute('data-cc-index'));
          if (Number.isNaN(idx)) return;
          emails.splice(idx, 1);
          render();
        });
      });
    }

    return {
      mount: function (target) {
        if (target) host = target;
        render();
        return this;
      },
      reset: function (incoming) {
        emails = list(incoming).map(function (item) {
          return String(item || '').trim();
        }).filter(Boolean);
        render();
        return this;
      },
      setEmails: function (list) {
        return this.reset(list);
      },
      getEmails: function () {
        return emails.slice();
      }
    };
  }

  window.ComunicacaoCcEditor = {
    create: createCcEditor
  };

  window.ComunicacaoSidebar = {
    summaryContacts: summaryContacts,
    renderRecipientSummary: renderRecipientSummary,
    renderSentEmails: renderSentEmails,
    bindSentEmailClicks: bindSentEmailClicks,
    initSentEmailDialog: initSentEmailDialog,
    formatDate: formatDate
  };
})();
