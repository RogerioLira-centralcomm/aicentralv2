/**
 * Contatos do PI / Cotação: modal de criar/editar + lista para escolher responsável.
 */
(function (global) {
  'use strict';

  var PARTY_HIDDEN_DEFAULT = {
    cliente: 'hidden_id_cliente',
    agencia: 'hidden_id_agencia',
    parceiro: 'hidden_id_parceiro',
  };

  var ROLE_SETOR = {
    midia: 'operacoes',
    fin: 'financeiro',
    comercial: 'comercial',
  };

  var ROLE_LABEL = {
    midia: 'Resp. de mídia',
    fin: 'Resp. financeiro',
    comercial: 'Contato',
  };

  var pickerContext = null;

  function cfg() {
    var el =
      document.getElementById('pi-contatos-config') ||
      document.getElementById('contatos-entity-config');
    if (!el) return {};
    try {
      return JSON.parse(el.textContent);
    } catch (_) {
      return {};
    }
  }

  function partyHiddenMap() {
    var c = cfg();
    return c.partyHidden || PARTY_HIDDEN_DEFAULT;
  }

  function escapeHtml(val) {
    return String(val == null ? '' : val)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatarTelefone(val) {
    var digits = String(val || '').replace(/\D/g, '');
    if (digits.startsWith('55') && digits.length > 11) digits = digits.slice(2);
    var limited = digits.slice(0, 11);
    if (limited.length <= 2) return limited ? '(' + limited : '';
    if (limited.length <= 6) return '(' + limited.slice(0, 2) + ') ' + limited.slice(2);
    if (limited.length <= 10) {
      return '(' + limited.slice(0, 2) + ') ' + limited.slice(2, 6) + '-' + limited.slice(6);
    }
    return '(' + limited.slice(0, 2) + ') ' + limited.slice(2, 7) + '-' + limited.slice(7);
  }

  function getModal() {
    return document.getElementById('modal_contato');
  }

  function isEntityContatoContext() {
    return !!(
      document.getElementById('pi-contatos-config') ||
      document.getElementById('contatos-entity-config')
    );
  }

  function syncWasenderVisibility() {
    var box = document.getElementById('contato_wasender_container');
    if (!box) return;
    box.hidden = isEntityContatoContext();
  }

  function getListaModal() {
    return document.getElementById('modal_pi_lista_contatos');
  }

  function partyClienteId(party) {
    var hidId = partyHiddenMap()[party];
    if (!hidId) return null;
    var hid = document.getElementById(hidId);
    return hid && hid.value ? parseInt(hid.value, 10) : null;
  }

  function setorIdForRole(role) {
    var c = cfg();
    if (role === 'midia') return c.setorOperacoesId || null;
    if (role === 'fin') return c.setorFinanceiroId || null;
    if (role === 'comercial') return c.setorComercialId || null;
    return null;
  }

  async function carregarCargosPorSetor(setorId) {
    var cargoSelect = document.getElementById('contato_cargo');
    if (!cargoSelect) return;
    if (!setorId) {
      cargoSelect.innerHTML = '<option value="">Selecione primeiro o setor</option>';
      return;
    }
    try {
      var response = await fetch('/api/setor/' + setorId + '/cargos');
      if (!response.ok) throw new Error('cargos');
      var cargos = await response.json();
      cargoSelect.innerHTML = '<option value="">Selecione o cargo</option>';
      cargos.forEach(function (cargo) {
        var option = document.createElement('option');
        option.value = cargo.id_cargo_contato;
        option.textContent = cargo.descricao;
        cargoSelect.appendChild(option);
      });
    } catch (e) {
      console.error(e);
      cargoSelect.innerHTML = '<option value="">Erro ao carregar cargos</option>';
    }
  }

  function abrirModalNovoContato(clienteId, options) {
    options = options || {};
    var modal = getModal();
    if (!modal || !clienteId) {
      if (typeof showToast === 'function') showToast('Selecione o cliente ou agência primeiro.', 'warning');
      return;
    }
    document.getElementById('form_contato').reset();
    document.getElementById('contato_id').value = '';
    document.getElementById('contato_cliente_id').value = String(clienteId);
    document.getElementById('contato_modal_title').textContent = 'Novo contato';
    document.getElementById('contato_btn_text').textContent = 'Criar contato';
    var linhaTel = document.getElementById('contato_linha_telefones');
    if (linhaTel) linhaTel.classList.add('hidden');
    var foto = document.getElementById('contato_foto_container');
    if (foto) foto.classList.add('hidden');
    document.getElementById('contato_cargo').innerHTML = '<option value="">Selecione setor</option>';
    var setorEl = document.getElementById('contato_setor');
    if (setorEl) {
      setorEl.value = options.setorId ? String(options.setorId) : '';
      if (options.setorId) carregarCargosPorSetor(options.setorId);
    }
    var respEl = document.getElementById('contato_responsavel_setor');
    if (respEl) respEl.checked = options.marcarResponsavel !== false;
    syncWasenderVisibility();
    modal.showModal();
  }

  async function abrirModalEditarContato(contatoId) {
    try {
      var response = await fetch('/api/contato/' + contatoId);
      if (!response.ok) throw new Error('fetch');
      var contato = await response.json();
      document.getElementById('contato_id').value = contato.id_contato_cliente;
      document.getElementById('contato_cliente_id').value = contato.pk_id_tbl_cliente;
      document.getElementById('contato_nome_completo').value = contato.nome_completo || '';
      document.getElementById('contato_email').value = contato.email || '';
      document.getElementById('contato_telefone').value = formatarTelefone(contato.telefone || '');
      document.getElementById('contato_telefone_secundario').value = formatarTelefone(
        contato.telefone_secundario || ''
      );
      var respEl = document.getElementById('contato_responsavel_setor');
      if (respEl) respEl.checked = !!contato.responsavel_setor;
      var linhaTel = document.getElementById('contato_linha_telefones');
      if (linhaTel) linhaTel.classList.remove('hidden');
      var setorId = contato.pk_id_tbl_setor;
      document.getElementById('contato_setor').value = setorId || '';
      if (setorId) {
        await carregarCargosPorSetor(setorId);
        document.getElementById('contato_cargo').value = contato.pk_id_tbl_cargo || '';
      } else {
        document.getElementById('contato_cargo').innerHTML =
          '<option value="">Selecione o setor primeiro</option>';
      }
      document.getElementById('contato_modal_title').textContent = 'Editar contato';
      document.getElementById('contato_btn_text').textContent = 'Atualizar contato';
      syncWasenderVisibility();
      getModal().showModal();
    } catch (e) {
      console.error(e);
      if (typeof showToast === 'function') showToast('Erro ao carregar contato.', 'error');
    }
  }

  function emptySlotLabel(slot) {
    var role = slot && slot.getAttribute('data-pi-role');
    return role === 'comercial' ? 'Sem contato' : 'Sem responsável';
  }

  function syncSlotDisplay(selectId) {
    var sel = document.getElementById(selectId);
    if (!sel) return;
    var display = document.querySelector('[data-pi-contato-display-for="' + selectId + '"]');
    var slot = sel.closest('.pi-contato-slot');
    var opt = sel.options[sel.selectedIndex];
    var fallback = emptySlotLabel(slot);
    var text = opt && opt.value ? opt.textContent : fallback;
    if (display) display.textContent = text;
    if (slot) slot.classList.toggle('is-empty', !sel.value);
  }

  function syncAllDisplays() {
    document.querySelectorAll('.pi-contato-slot__select').forEach(function (sel) {
      syncSlotDisplay(sel.id);
    });
  }

  function selecionarContatoParaSlot(selectId, contatoId) {
    var sel = document.getElementById(selectId);
    if (!sel) return;
    sel.value = String(contatoId);
    syncSlotDisplay(selectId);
    if (typeof window.syncPiInlineFields === 'function') window.syncPiInlineFields();
  }

  function renderListaRow(contato, selectId, showRespBadge) {
    var U = global.ContatosSetorUtils;
    var label = U ? U.formatarLabelContato(contato) : escapeHtml(contato.nome_completo || '');
    var resp =
      showRespBadge && contato.responsavel_setor
        ? '<span class="cx-badge cx-badge-muted text-[10px]">Resp. e-mails</span>'
        : '';
    var pickable = selectId ? ' pi-lista-contato-row--pickable' : '';
    var pickAttr = selectId
      ? ' data-contato-id="' + contato.id_contato_cliente + '" role="button" tabindex="0"'
      : '';
    return (
      '<div class="pi-lista-contato-row' +
      pickable +
      '">' +
      '<div class="pi-lista-contato-row__main"' +
      pickAttr +
      '>' +
      '<span class="pi-lista-contato-row__label">' +
      label +
      '</span>' +
      resp +
      '</div>' +
      '<div class="pi-lista-contato-row__actions">' +
      '<button type="button" class="cx-btn cx-btn-xs cx-btn-ghost pi-lista-contato-edit" data-contato-id="' +
      contato.id_contato_cliente +
      '">Editar</button>' +
      '</div></div>'
    );
  }

  async function abrirListaContatos(options) {
    options = options || {};
    var party = options.party;
    var role = options.role || null;
    var selectId = options.selectId || null;
    var clienteId = partyClienteId(party);
    if (!clienteId) {
      if (typeof showToast === 'function') showToast('Selecione a entidade antes.', 'warning');
      return;
    }
    var modal = getListaModal();
    var body = document.getElementById('modal_pi_lista_contatos_body');
    var title = document.getElementById('modal_pi_lista_contatos_title');
    var sub = document.getElementById('modal_pi_lista_contatos_sub');
    if (!modal || !body) return;

    pickerContext = {
      party: party,
      role: role,
      selectId: selectId,
      clienteId: clienteId,
      todos: !!options.todos,
    };

    title.textContent = options.todos ? 'Todos os contatos' : ROLE_LABEL[role] || 'Contatos';
    sub.textContent = options.todos
      ? 'Carregando…'
      : 'Clique no contato para atribuir ou use Editar para alterar os dados.';

    body.innerHTML = '<p class="text-xs text-slate-400 py-4 text-center">Carregando…</p>';
    modal.showModal();

    try {
      var resp = await fetch('/api/clientes/' + clienteId + '/todos-contatos');
      var contatos = await resp.json();
      var U = global.ContatosSetorUtils;
      var lista;
      if (options.todos) {
        lista = U ? U.ordenarContatosLista(contatos) : contatos;
      } else if (role && U) {
        lista = U.listaContatosSetor(contatos, ROLE_SETOR[role]);
      } else {
        lista = contatos;
      }
      if (!lista.length) {
        body.innerHTML =
          '<p class="text-xs text-slate-500 py-6 text-center">Nenhum contato neste filtro.</p>';
        sub.textContent = options.todos ? 'Nenhum contato ativo.' : '';
        return;
      }
      if (options.todos) {
        sub.textContent =
          lista.length +
          ' contato(s) ativo(s) — use Editar para alterar ou marcar Resp. e-mails.';
      }
      body.innerHTML = lista
        .map(function (c) {
          return renderListaRow(c, selectId, !!options.todos);
        })
        .join('');
    } catch (e) {
      console.error(e);
      body.innerHTML =
        '<p class="text-xs text-red-500 py-4 text-center">Erro ao carregar contatos.</p>';
    }
  }

  function reloadPartyContatos(party) {
    if (typeof global.carregarContatos !== 'function') return Promise.resolve();
    var clienteId = partyClienteId(party);
    if (!clienteId) return Promise.resolve();

    var selCom = document.querySelector(
      '.pi-contato-slot[data-pi-party="' + party + '"][data-pi-role="comercial"] select'
    );
    if (selCom) {
      var valCom = selCom.value ? selCom.value : '';
      return global.carregarContatos(clienteId, party, valCom).then(function () {
        syncAllDisplays();
      });
    }

    var selMidia = document.querySelector(
      '.pi-contato-slot[data-pi-party="' + party + '"][data-pi-role="midia"] select'
    );
    var selFin = document.querySelector(
      '.pi-contato-slot[data-pi-party="' + party + '"][data-pi-role="fin"] select'
    );
    var mid = selMidia && selMidia.value ? selMidia.value : '';
    var fin = selFin && selFin.value ? selFin.value : '';
    return global.carregarContatos(clienteId, party, mid, fin).then(function () {
      syncAllDisplays();
    });
  }

  function bindEvents() {
    var setorEl = document.getElementById('contato_setor');
    if (setorEl) {
      setorEl.addEventListener('change', function () {
        carregarCargosPorSetor(this.value ? parseInt(this.value, 10) : null);
      });
    }
    var cancel = document.getElementById('contato_modal_cancel');
    if (cancel) {
      cancel.addEventListener('click', function () {
        var m = getModal();
        if (m) m.close();
      });
    }
    var form = document.getElementById('form_contato');
    if (form) {
      form.addEventListener('submit', async function (e) {
        e.preventDefault();
        var contatoId = document.getElementById('contato_id').value;
        var clienteId = document.getElementById('contato_cliente_id').value;
        var formData = new FormData(form);
        var setorValue = formData.get('pk_id_aux_setor');
        var cargoValue = formData.get('pk_id_tbl_cargo');
        var data = {
          nome_completo: (formData.get('nome_completo') || '').trim(),
          email: (formData.get('email') || '').trim(),
          telefone: (formData.get('telefone') || '').trim(),
          telefone_secundario: (formData.get('telefone_secundario') || '').trim(),
          pk_id_aux_setor: setorValue ? parseInt(setorValue, 10) : null,
          pk_id_tbl_cargo: cargoValue ? parseInt(cargoValue, 10) : null,
          cohorts: 1,
          user_type: 'client',
        };
        var respCb = document.getElementById('contato_responsavel_setor');
        if (respCb) data.responsavel_setor = respCb.checked;
        try {
          var response;
          if (contatoId) {
            response = await fetch('/api/contato/' + contatoId + '/editar', {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(data),
            });
          } else {
            response = await fetch('/api/cliente/' + clienteId + '/criar-contato', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(data),
            });
          }
          var result = await response.json();
          if (result.success) {
            if (typeof showToast === 'function') showToast(result.message || 'Salvo.', 'success');
            getModal().close();
            var parties = ['cliente', 'agencia', 'parceiro'];
            await Promise.all(
              parties.map(function (p) {
                if (partyClienteId(p) === parseInt(clienteId, 10)) return reloadPartyContatos(p);
                return Promise.resolve();
              })
            );
            var listaDlg = getListaModal();
            if (pickerContext && listaDlg && listaDlg.open) {
              abrirListaContatos({
                party: pickerContext.party,
                role: pickerContext.role,
                selectId: pickerContext.selectId,
                todos: !!pickerContext.todos,
              });
            }
          } else if (typeof showToast === 'function') {
            showToast(result.message || 'Erro ao salvar.', 'error');
          }
        } catch (err) {
          console.error(err);
          if (typeof showToast === 'function') showToast('Erro ao salvar contato.', 'error');
        }
      });
    }

    document.addEventListener('click', function (ev) {
      var t = ev.target.closest('[data-pi-action]');
      if (!t) return;
      var action = t.getAttribute('data-pi-action');
      var slot = t.closest('.pi-contato-slot');
      var party = slot && slot.getAttribute('data-pi-party');
      var role = slot && slot.getAttribute('data-pi-role');
      var selectId = slot && slot.getAttribute('data-pi-select-id');
      var clienteId = party && partyClienteId(party);

      if (action === 'contatos-lista-todos') {
        ev.preventDefault();
        ev.stopPropagation();
        party = t.getAttribute('data-pi-party');
        abrirListaContatos({ party: party, todos: true, selectId: null });
        return;
      }

      if (action === 'contato-create') {
        ev.preventDefault();
        ev.stopPropagation();
        abrirModalNovoContato(clienteId, {
          setorId: setorIdForRole(role),
          marcarResponsavel: true,
        });
      } else if (action === 'contato-pick') {
        ev.preventDefault();
        ev.stopPropagation();
        abrirListaContatos({ party: party, role: role, selectId: selectId });
      }
    });

    var listaBody = document.getElementById('modal_pi_lista_contatos_body');
    if (listaBody) {
      listaBody.addEventListener('click', function (ev) {
        if (ev.target.closest('.pi-lista-contato-edit')) {
          var editBtn = ev.target.closest('.pi-lista-contato-edit');
          if (editBtn) abrirModalEditarContato(editBtn.dataset.contatoId);
          return;
        }
        var main = ev.target.closest('.pi-lista-contato-row__main[data-contato-id]');
        if (main && pickerContext && pickerContext.selectId) {
          selecionarContatoParaSlot(pickerContext.selectId, main.dataset.contatoId);
          getListaModal().close();
        }
      });
      listaBody.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Enter' && ev.key !== ' ') return;
        var main = ev.target.closest('.pi-lista-contato-row__main[data-contato-id]');
        if (!main || !pickerContext || !pickerContext.selectId) return;
        ev.preventDefault();
        selecionarContatoParaSlot(pickerContext.selectId, main.dataset.contatoId);
        getListaModal().close();
      });
    }
    var fecharLista = document.getElementById('modal_pi_lista_contatos_fechar');
    if (fecharLista) {
      fecharLista.addEventListener('click', function () {
        getListaModal().close();
      });
    }

    [document.getElementById('contato_telefone'), document.getElementById('contato_telefone_secundario')]
      .filter(Boolean)
      .forEach(function (inputTel) {
        inputTel.addEventListener('input', function (e) {
          e.target.value = formatarTelefone(e.target.value);
        });
      });
  }

  global.PiContatos = {
    syncAllDisplays: syncAllDisplays,
    abrirModalNovoContato: abrirModalNovoContato,
    abrirModalEditarContato: abrirModalEditarContato,
    abrirListaContatos: abrirListaContatos,
    reloadPartyContatos: reloadPartyContatos,
  };

  function shouldInitContatos() {
    var c = cfg();
    if (c.appRoot && document.getElementById(c.appRoot)) return true;
    if (document.getElementById('pi-operacao-app')) return true;
    if (document.getElementById('cotacao_form')) return true;
    return false;
  }

  function initPiContatos() {
    if (!shouldInitContatos()) return;
    bindEvents();
    syncAllDisplays();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPiContatos);
  } else {
    initPiContatos();
  }
})(window);
