/**
 * Página de agências do CRM v3: árvore de agências com seus clientes finais.
 *
 * Fonte: /crm-v3/api/clientes (já traz `is_agencia` e `agencias_vinculadas`
 * por cliente), então a árvore é montada no cliente sem N chamadas extras.
 * Mutações: POST/DELETE /crm-v3/api/agencias/<agencia>/clientes/<cliente>.
 * Após cada mutação recarregamos a lista para refletir principal/vínculos.
 */
(function () {
  'use strict';

  var API = '/crm-v3/api';
  var state = {
    clientes: [],
    agencias: [],
    filhos: {},
    aberta: {},
    busca: '',
    soVazias: false
  };

  var el = {
    tree: document.getElementById('crm-ag-tree'),
    status: document.getElementById('crm-ag-status'),
    resumo: document.getElementById('crm-ag-resumo'),
    busca: document.getElementById('crm-ag-busca'),
    soVazias: document.getElementById('crm-ag-so-vazias')
  };

  function esc(valor) {
    return String(valor == null ? '' : valor).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function norm(texto) {
    return String(texto || '').toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function nomeDe(c) {
    return c.nome || c.nome_fantasia || c.razao_social || '—';
  }

  function porNome(a, b) {
    return norm(nomeDe(a)).localeCompare(norm(nomeDe(b)));
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' }
    }).then(function (res) {
      return res.text().then(function (texto) {
        var data;
        try {
          data = texto ? JSON.parse(texto) : {};
        } catch (e) {
          throw new Error('Resposta inválida do servidor (HTTP ' + res.status + ')');
        }
        if (!res.ok || data.success === false) {
          throw new Error(data.error || 'Erro na requisição');
        }
        return data;
      });
    });
  }

  function setStatus(msg, erro) {
    if (!el.status) return;
    el.status.hidden = !msg;
    el.status.textContent = msg || '';
    el.status.classList.toggle('is-erro', !!erro);
  }

  /** Reconstrói agências e clientes finais a partir de state.clientes. */
  function reconstruir() {
    state.agencias = state.clientes.filter(function (c) { return c.is_agencia; }).sort(porNome);
    state.filhos = {};
    state.agencias.forEach(function (a) { state.filhos[a.id] = []; });
    state.clientes.forEach(function (c) {
      if (c.is_agencia) return;
      (c.agencias_vinculadas || []).forEach(function (v) {
        var id = String(v.agencia_id);
        if (state.filhos[id]) {
          state.filhos[id].push({ cliente: c, principal: !!v.is_principal });
        }
      });
    });
    Object.keys(state.filhos).forEach(function (id) {
      state.filhos[id].sort(function (a, b) { return porNome(a.cliente, b.cliente); });
    });
  }

  function agenciaCorresponde(agencia, termo) {
    if (!termo) return true;
    if (norm(nomeDe(agencia)).indexOf(termo) !== -1) return true;
    return state.filhos[agencia.id].some(function (f) {
      return norm(nomeDe(f.cliente)).indexOf(termo) !== -1;
    });
  }

  function agenciasVisiveis() {
    var termo = norm(state.busca.trim());
    return state.agencias.filter(function (a) {
      if (state.soVazias && state.filhos[a.id].length) return false;
      return agenciaCorresponde(a, termo);
    });
  }

  function renderResumo() {
    var comFilhos = state.agencias.filter(function (a) { return state.filhos[a.id].length; }).length;
    var vinculos = Object.keys(state.filhos).reduce(function (t, id) { return t + state.filhos[id].length; }, 0);
    el.resumo.textContent = state.agencias.length + ' agências · ' + comFilhos + ' com clientes finais · '
      + vinculos + ' vínculos';
  }

  function renderFilho(agencia, f) {
    var c = f.cliente;
    return '<li class="crm-ag-filho" role="listitem">'
      + '<div class="crm-ag-filho-info">'
      + '<span class="crm-ag-filho-nome">' + esc(nomeDe(c)) + '</span>'
      + (f.principal ? ' <span class="crm-ag-badge is-principal">Principal</span>' : '')
      + (c.classificacao_cliente ? ' <span class="crm-ag-badge">' + esc(c.classificacao_cliente) + '</span>' : '')
      + (c.responsavel ? ' <span class="crm-ag-meta">Resp.: ' + esc(c.responsavel) + '</span>' : '')
      + '</div>'
      + '<button type="button" class="crm-ag-btn is-danger" data-acao="remover" '
      + 'data-agencia="' + esc(agencia.id) + '" data-cliente="' + esc(c.id) + '" '
      + 'data-nome="' + esc(nomeDe(c)) + '" '
      + 'aria-label="Remover ' + esc(nomeDe(c)) + ' da agência">Remover</button>'
      + '</li>';
  }

  function renderAgencia(agencia, termo) {
    var filhos = state.filhos[agencia.id];
    var aberta = termo ? true : !!state.aberta[agencia.id];
    var nomeHtml = esc(nomeDe(agencia));
    var filhosVisiveis = termo
      ? filhos.filter(function (f) { return norm(nomeDe(f.cliente)).indexOf(termo) !== -1 || norm(nomeDe(agencia)).indexOf(termo) !== -1; })
      : filhos;
    var lista = filhosVisiveis.length
      ? '<ul class="crm-ag-filhos" role="list">' + filhosVisiveis.map(function (f) { return renderFilho(agencia, f); }).join('') + '</ul>'
      : '<p class="crm-ag-vazio">Sem clientes finais vinculados.</p>';

    return '<section class="crm-ag-agencia' + (aberta ? ' is-aberta' : '') + '" role="listitem">'
      + '<header class="crm-ag-agencia-head">'
      + '<button type="button" class="crm-ag-toggle" data-acao="alternar" data-agencia="' + esc(agencia.id) + '" '
      + 'aria-expanded="' + (aberta ? 'true' : 'false') + '">'
      + '<i class="fa-solid ' + (aberta ? 'fa-chevron-down' : 'fa-chevron-right') + '" aria-hidden="true"></i>'
      + '<span class="crm-ag-agencia-nome">' + nomeHtml + '</span>'
      + '<span class="crm-ag-contagem">' + filhos.length + ' cliente' + (filhos.length === 1 ? '' : 's') + '</span>'
      + '</button>'
      + '</header>'
      + (aberta
        ? '<div class="crm-ag-corpo">'
          + lista
          + '<div class="crm-ag-adicionar">'
          + '<label class="crm-ag-label" for="add-' + esc(agencia.id) + '">Adicionar cliente final</label>'
          + '<input type="search" class="crm-ag-input" id="add-' + esc(agencia.id) + '" '
          + 'data-acao="buscar-cliente" data-agencia="' + esc(agencia.id) + '" placeholder="Digite o nome do cliente">'
          + '<div class="crm-ag-resultados" data-resultados="' + esc(agencia.id) + '"></div>'
          + '</div>'
          + '</div>'
        : '')
      + '</section>';
  }

  function render() {
    renderResumo();
    var termo = norm(state.busca.trim());
    var visiveis = agenciasVisiveis();
    if (!state.agencias.length) {
      el.tree.innerHTML = '<p class="crm-ag-vazio">Nenhuma agência cadastrada.</p>';
      return;
    }
    if (!visiveis.length) {
      el.tree.innerHTML = '<p class="crm-ag-vazio">Nenhuma agência encontrada para esta busca.</p>';
      return;
    }
    el.tree.innerHTML = visiveis.map(function (a) { return renderAgencia(a, termo); }).join('');
  }

  /** Candidatos a cliente final: não-agências ainda não vinculadas à agência. */
  function renderResultados(agenciaId, termo) {
    var box = el.tree.querySelector('[data-resultados="' + agenciaId + '"]');
    if (!box) return;
    var jaVinculados = {};
    (state.filhos[agenciaId] || []).forEach(function (f) { jaVinculados[f.cliente.id] = true; });
    var t = norm(termo.trim());
    if (t.length < 2) {
      box.innerHTML = '';
      return;
    }
    var achados = state.clientes.filter(function (c) {
      return !c.is_agencia && !jaVinculados[c.id] && norm(nomeDe(c)).indexOf(t) !== -1;
    }).sort(porNome).slice(0, 8);
    box.innerHTML = achados.length
      ? achados.map(function (c) {
        return '<button type="button" class="crm-ag-resultado" data-acao="adicionar" '
          + 'data-agencia="' + esc(agenciaId) + '" data-cliente="' + esc(c.id) + '">'
          + esc(nomeDe(c))
          + (c.responsavel ? ' <span class="crm-ag-meta">' + esc(c.responsavel) + '</span>' : '')
          + '</button>';
      }).join('')
      : '<p class="crm-ag-meta">Nenhum cliente encontrado.</p>';
  }

  function recarregar(mensagem) {
    return api('/clientes').then(function (body) {
      state.clientes = body.data || body.clientes || [];
      reconstruir();
      render();
      if (mensagem) setStatus(mensagem, false);
    }).catch(function (err) {
      setStatus('Erro ao carregar: ' + err.message, true);
    });
  }

  function vincular(agenciaId, clienteId, ativo) {
    var caminho = '/agencias/' + encodeURIComponent(agenciaId) + '/clientes/' + encodeURIComponent(clienteId);
    setStatus(ativo ? 'Adicionando…' : 'Removendo…', false);
    return api(caminho, { method: ativo ? 'POST' : 'DELETE' })
      .then(function () {
        return recarregar(ativo ? 'Cliente adicionado à agência.' : 'Cliente removido da agência.');
      })
      .catch(function (err) {
        setStatus(err.message, true);
      });
  }

  el.tree.addEventListener('click', function (ev) {
    var alvo = ev.target.closest('[data-acao]');
    if (!alvo) return;
    var acao = alvo.getAttribute('data-acao');
    if (acao === 'alternar') {
      var id = alvo.getAttribute('data-agencia');
      state.aberta[id] = !state.aberta[id];
      render();
    } else if (acao === 'remover') {
      var nome = alvo.getAttribute('data-nome') || 'este cliente';
      if (window.confirm('Remover "' + nome + '" desta agência?')) {
        vincular(alvo.getAttribute('data-agencia'), alvo.getAttribute('data-cliente'), false);
      }
    } else if (acao === 'adicionar') {
      vincular(alvo.getAttribute('data-agencia'), alvo.getAttribute('data-cliente'), true);
    }
  });

  el.tree.addEventListener('input', function (ev) {
    var alvo = ev.target;
    if (alvo.getAttribute('data-acao') !== 'buscar-cliente') return;
    renderResultados(alvo.getAttribute('data-agencia'), alvo.value);
  });

  el.busca.addEventListener('input', function () {
    state.busca = el.busca.value;
    render();
  });

  el.soVazias.addEventListener('change', function () {
    state.soVazias = el.soVazias.checked;
    render();
  });

  setStatus('Carregando agências…', false);
  recarregar('');
})();
