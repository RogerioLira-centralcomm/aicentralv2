/**
 * PIs list — sidebar complementar, sub-tabela de campanhas, flags agregadas
 */
(function () {
  'use strict';

  const UI = window.CampanhasUI;
  if (!UI) return;

  const SOMENTE_LEITURA = window.PI_LISTA_SOMENTE_LEITURA === true;
  let loadedCampanhas = {};
  window.todasExpandidas = false;
  let currentPiSidebar = null;

  function siglaMetricaPreco(nomeObjetivo, modalidade) {
    if (modalidade === 'cpm') return 'CPM';
    const n = (nomeObjetivo || '').toUpperCase();
    const keys = ['CPV', 'CPA', 'CPC', 'CPL', 'CPI'];
    for (let i = 0; i < keys.length; i++) {
      if (n.indexOf(keys[i]) !== -1) return keys[i];
    }
    return '—';
  }

  function fmtBrl(v) {
    return 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtInt(v) {
    return Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  }

  function updateFlagSummary(idPi, campanhaIds) {
    const el = document.getElementById('pi-flag-summary-' + idPi);
    if (!el || !campanhaIds || !campanhaIds.length) return;
    const text = UI.aggregateFlagsForCampanhas(campanhaIds);
    el.textContent = text;
    el.style.display = text ? '' : 'none';
  }

  function buildCampanhaRowHtml(c) {
    const objContratadoNum = UI.parseVolume(c.obj_contratados);
    const objAtingidoNum = UI.parseVolume(c.totalizador_atingido);
    const pctObj = objContratadoNum > 0 ? Math.round((objAtingidoNum / objContratadoNum) * 100) : 0;
    const tier = UI.calcProgressTier(pctObj);
    const progWidth = pctObj > 0 ? Math.min(pctObj, 100) : 0;
    const gasto = c.totalizador_gasto != null ? UI.parseVolume(c.totalizador_gasto) : 0;
    const previsto = c.valor_plataforma != null ? UI.parseVolume(c.valor_plataforma) : 0;
    const precoM = c.preco_metrica_brl != null && !isNaN(Number(c.preco_metrica_brl)) ? Number(c.preco_metrica_brl) : null;
    const sigla = siglaMetricaPreco(c.objetivo_nome, c.preco_metrica_modalidade);
    const periodoLinha1 = (c.periodo_inicio || '—') + (c.periodo_fim ? ' – ' + c.periodo_fim : '');
    const periodoLinha2 = (c.periodo_dias != null && c.periodo_dias !== '')
      ? '<span class="block text-[10px] text-gray-400">(' + c.periodo_dias + 'd)</span>' : '';
    const payload = encodeURIComponent(JSON.stringify(c));
    const platId = c.id_plataforma != null ? c.id_plataforma : '';
    const platNome = (c.plataforma_nome || '').replace(/"/g, '&quot;');

    let celPreco = UI.cellEmptyHtml('empty-na');
    if (precoM != null) {
      celPreco = '<span class="text-[10px] font-semibold text-emerald-800">' + sigla + '</span>' +
        '<span class="block text-xs font-semibold tabular-nums text-gray-800">' + fmtBrl(precoM) + '</span>';
    }

    let celMeta = UI.cellEmptyHtml('empty-na');
    if (objContratadoNum > 0) {
      celMeta = '<div class="text-[11px] font-semibold text-gray-700">' + pctObj + '%</div>' +
        '<div class="text-[11px] text-gray-600">' + fmtInt(objAtingidoNum) + '</div>' +
        '<div class="text-[10px] text-gray-400">' + fmtInt(objContratadoNum) + '</div>';
    }

    const progressHtml = '<div class="flex items-center justify-end gap-1.5 mb-0.5">' +
      '<div class="camp-progress camp-progress-sm" data-tier="' + tier + '" title="Progresso: ' + pctObj + '%">' +
      '<div class="camp-progress-fill" style="width:' + progWidth + '%"></div></div>' +
      '<span class="camp-progress-pct" data-tier="' + tier + '">' + pctObj + '%</span></div>' +
      '<div class="text-[11px] text-gray-600">' + fmtInt(objAtingidoNum) + '</div>';

    const linkCount = (c.googled_pi_princ ? 1 : 0) + (c.link_dash ? 1 : 0);

    return '<tr class="hover:bg-slate-100 cursor-pointer transition-colors" data-plataforma-id="' + platId + '" data-plataforma-nome="' + platNome + '" data-camp-payload="' + payload + '" title="Ver detalhes da campanha">' +
      '<td class="text-left"><span class="text-xs font-semibold text-gray-800 truncate block">' + (c.nome_campanha || '—') + '</span>' +
      '<span class="block text-[11px] text-gray-400 truncate">' + (c.status_nome || '') + '</span></td>' +
      '<td class="text-center platform-cell"><div class="platform-badge" data-platform-badge><span class="platform-icon-wrap" title="' + platNome + '"><i class="platform-icon fa-solid fa-bullhorn"></i></span>' +
      '<span class="link-count-badge' + (linkCount === 0 ? ' empty' : '') + '">L' + linkCount + '</span></div>' +
      '<div class="text-[10px] text-gray-400 mt-0.5 truncate">' + (c.plataforma_nome || '') + '</div></td>' +
      '<td class="text-center text-[11px] text-gray-600">' + periodoLinha1 + periodoLinha2 + '</td>' +
      '<td class="text-right">' + celPreco + '</td>' +
      '<td class="text-right">' + celMeta + '</td>' +
      '<td class="text-right">' + progressHtml + '</td>' +
      '<td class="text-right"><span class="text-xs font-semibold tabular-nums text-gray-800">' + fmtBrl(gasto) + '</span>' +
      '<span class="block text-[10px] text-gray-400">de ' + fmtBrl(previsto) + '</span></td>' +
      '</tr>';
  }

  window.toggleCampanhas = function (idPi, event) {
    if (event && event.stopPropagation) event.stopPropagation();
    const row = document.getElementById('camp-collapse-' + idPi);
    const piRow = document.getElementById('pi-' + idPi);
    const chevron = document.getElementById('chevron-' + idPi);
    if (!row) return;

    const isHidden = row.classList.contains('hidden');
    row.classList.toggle('hidden');
    if (chevron) chevron.classList.toggle('open', isHidden);
    if (piRow) {
      piRow.classList.toggle('pi-row-sticky-expanded', isHidden);
      if (isHidden) {
        piRow.style.top = UI.getPiStickyTop() + 'px';
      } else {
        piRow.style.top = '';
      }
    }

    if (isHidden && !loadedCampanhas[idPi]) {
      fetch('/api/cadu-pi/' + idPi + '/campanhas')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          loadedCampanhas[idPi] = true;
          const container = document.getElementById('camp-content-' + idPi);
          if (!data.success || !data.campanhas || data.campanhas.length === 0) {
            container.innerHTML = '<div class="text-center py-4"><i class="fa-solid fa-inbox text-gray-300 text-lg mb-1"></i>' +
              '<p class="text-[11px] text-gray-400">Nenhuma campanha vinculada a este PI</p></div>';
            return;
          }
          if (!container.dataset.campRowClickDelegated) {
            container.dataset.campRowClickDelegated = '1';
            container.addEventListener('click', function (e) {
              const tr = e.target.closest('tr[data-camp-payload]');
              if (!tr) return;
              e.stopPropagation();
              try {
                const camp = JSON.parse(decodeURIComponent(tr.getAttribute('data-camp-payload')));
                if (typeof abrirViewCampanhaLista === 'function') abrirViewCampanhaLista(camp);
              } catch (err) { console.error(err); }
            });
          }
          let html = '<table class="camp-table w-full"><colgroup>' +
            '<col style="width:22%"><col style="width:12%"><col style="width:14%"><col style="width:14%"><col style="width:14%"><col style="width:12%"><col style="width:12%">' +
            '</colgroup><thead><tr>' +
            '<th class="text-left">Campanha</th><th class="text-center">Plataforma</th><th class="text-center">Período</th>' +
            '<th class="text-right">Preço (R$)</th><th class="text-right">Meta</th><th class="text-right">Atingido</th><th class="text-right">Gasto / previsto</th>' +
            '</tr></thead><tbody>';
          const campIds = [];
          data.campanhas.forEach(function (c) {
            if (c.id_campanha) campIds.push(c.id_campanha);
            html += buildCampanhaRowHtml(c);
          });
          html += '</tbody></table>';
          container.innerHTML = html;
          UI.applyPlatformIcons(container);
          updateFlagSummary(idPi, campIds);
        })
        .catch(function () {
          const container = document.getElementById('camp-content-' + idPi);
          container.innerHTML = '<div class="text-center py-3 text-[11px] text-red-400"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Erro ao carregar campanhas</div>';
        });
    }
  };

  window.toggleTodasCampanhas = function () {
    window.todasExpandidas = !window.todasExpandidas;
    document.querySelectorAll('tr.collapse-camp-row').forEach(function (row) {
      const isHidden = row.classList.contains('hidden');
      if (window.todasExpandidas === isHidden) {
        const idPi = row.id.replace('camp-collapse-', '');
        toggleCampanhas(parseInt(idPi, 10), { stopPropagation: function () {} });
      }
    });
    const label = document.getElementById('label_expandir_todas');
    const icon = document.getElementById('icon_expandir_todas');
    if (label) label.textContent = window.todasExpandidas ? 'Recolher todas' : 'Expandir todas';
    if (icon) icon.className = (window.todasExpandidas ? 'fa-solid fa-angles-up' : 'fa-solid fa-angles-down') + ' text-[9px]';
  };

  /* ==================== SIDEBAR PI ==================== */
  function switchPiSidebarTab(tab) {
    document.querySelectorAll('.pi-sidebar-tab-content').forEach(function (el) {
      el.classList.toggle('hidden', el.id !== 'pi-tab-' + tab);
    });
    document.querySelectorAll('.pi-sidebar-tab-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tab);
    });
  }

  function renderHistorico(items) {
    const list = document.getElementById('piHistoricoLista');
    const empty = document.getElementById('piHistoricoEmpty');
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    list.innerHTML = items.map(function (h) {
      const dt = h.data_acao ? new Date(h.data_acao).toLocaleString('pt-BR') : '—';
      return '<div class="border-b border-gray-100 py-2"><div class="text-[11px] font-semibold text-gray-800">' + (h.descricao || h.acao || 'Alteração') + '</div>' +
        '<div class="text-[10px] text-gray-500">' + (h.usuario_nome || 'Sistema') + ' · ' + dt + '</div></div>';
    }).join('');
  }

  function renderLinkDestinos(links) {
    const list = document.getElementById('piLinksLista');
    const empty = document.getElementById('piLinksEmpty');
    if (!list) return;
    if (!links || !links.length) {
      list.innerHTML = '';
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');
    list.innerHTML = links.map(function (ld) {
      const deleteBtn = SOMENTE_LEITURA ? '' :
        '<button type="button" onclick="PiListUI.excluirLink(' + ld.id_link_destino + ')" class="text-gray-400 hover:text-red-500 p-1"><i class="fa-solid fa-trash text-[10px]"></i></button>';
      return '<div class="flex items-center justify-between gap-2 py-1.5 border-b border-gray-50">' +
        '<a href="' + ld.link + '" target="_blank" class="text-[11px] text-indigo-600 hover:underline truncate">' + (ld.descricao || ld.link) + '</a>' +
        deleteBtn + '</div>';
    }).join('');
  }

  function aplicarSidebarSomenteLeitura() {
    if (!SOMENTE_LEITURA) return;
    document.querySelectorAll('#piSidebarPanel .pi-sidebar-save-btn').forEach(function (el) {
      el.classList.add('hidden');
    });
    document.querySelectorAll('#piSidebarPanel .pi-sidebar-edit-row').forEach(function (el) {
      el.classList.add('hidden');
    });
    document.querySelectorAll('#piSidebarPanel input, #piSidebarPanel textarea, #piSidebarPanel select').forEach(function (el) {
      el.disabled = true;
      el.classList.add('bg-gray-50', 'cursor-default');
    });
  }

  function fillContactSelects(contatos, pi) {
    const fields = [
      'contato_fin_cliente', 'contato_midia_cliente',
      'contato_fin_agencia', 'contato_midia_agencia',
      'contato_fin_parceiro', 'contato_midia_parceiro',
    ];
    fields.forEach(function (field) {
      const sel = document.getElementById('pi_' + field);
      if (!sel) return;
      const cur = pi[field];
      sel.innerHTML = '<option value="">— Nenhum —</option>' + (contatos || []).map(function (c) {
        const id = c.id_contato_cliente;
        const nome = c.nome_completo || '';
        return '<option value="' + id + '"' + (String(cur) === String(id) ? ' selected' : '') + '>' + nome + '</option>';
      }).join('');
    });
  }

  window.abrirSidebarPi = function (idPi) {
    currentPiSidebar = idPi;
    const panel = document.getElementById('piSidebarPanel');
    const overlay = document.getElementById('piSidebarOverlay');
    if (!panel || !overlay) return;
    panel.classList.add('open');
    overlay.classList.add('open');
    switchPiSidebarTab('resumo');
    document.getElementById('piSidebarTitle').textContent = (SOMENTE_LEITURA ? 'Visualizar PI #' : 'PI #') + idPi;
    aplicarSidebarSomenteLeitura();
    fetch('/api/cadu_pi/' + idPi + '/complementar')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) throw new Error(data.message || 'Erro');
        const pi = data.pi;
        currentPiSidebar = pi;
        document.getElementById('piSidebarTitle').textContent =
          (SOMENTE_LEITURA ? 'Visualizar: ' : '') + (pi.codigo_pi_cc || pi.codigo_pi_ag || ('PI #' + pi.id_pi));
        document.getElementById('piResumoCliente').textContent = pi.cliente_nome || '—';
        document.getElementById('piResumoAgencia').textContent = pi.agencia_nome || '—';
        document.getElementById('piResumoExecutivo').textContent = pi.resp_comercial_nome || '—';
        document.getElementById('piResumoStatus').textContent = pi.status_descricao || '—';
        document.getElementById('piObsOperacao').value = pi.obs_operacao || '';
        document.getElementById('piObsFinanceiro').value = pi.obs_financeiro || '';
        document.getElementById('piGdrivePrinc').value = pi.googled_pi_princ || '';
        document.getElementById('piGdriveFinanc').value = pi.googled_pi_financ || '';
        document.getElementById('piGdrivePecas').value = pi.googled_pi_pecas || '';
        document.getElementById('piGdriveArq').value = pi.googled_pi_arq_ass || '';
        fillContactSelects(data.contatos, pi);
        aplicarSidebarSomenteLeitura();
      })
      .catch(function (e) {
        if (typeof showToast === 'function') showToast(e.message || 'Erro ao carregar PI', 'error');
      });
    fetch('/api/cadu_pi/' + idPi + '/link-destinos')
      .then(function (r) { return r.json(); })
      .then(function (data) { if (data.success) renderLinkDestinos(data.links); })
      .catch(function () {});
    fetch('/api/cadu_pi/' + idPi + '/historico')
      .then(function (r) { return r.json(); })
      .then(function (data) { if (data.success) renderHistorico(data.historico); })
      .catch(function () {});
  };

  window.fecharSidebarPi = function () {
    const panel = document.getElementById('piSidebarPanel');
    const overlay = document.getElementById('piSidebarOverlay');
    if (panel) panel.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    currentPiSidebar = null;
  };

  function collectPatchBody() {
    const elMap = {
      obs_operacao: 'piObsOperacao',
      obs_financeiro: 'piObsFinanceiro',
      googled_pi_princ: 'piGdrivePrinc',
      googled_pi_financ: 'piGdriveFinanc',
      googled_pi_pecas: 'piGdrivePecas',
      googled_pi_arq_ass: 'piGdriveArq',
      contato_fin_cliente: 'pi_contato_fin_cliente',
      contato_midia_cliente: 'pi_contato_midia_cliente',
      contato_fin_agencia: 'pi_contato_fin_agencia',
      contato_midia_agencia: 'pi_contato_midia_agencia',
      contato_fin_parceiro: 'pi_contato_fin_parceiro',
      contato_midia_parceiro: 'pi_contato_midia_parceiro',
    };
    const body = {};
    Object.keys(elMap).forEach(function (key) {
      const el = document.getElementById(elMap[key]);
      if (el) body[key] = el.value;
    });
    return body;
  }

  window.PiListUI = {
    switchTab: switchPiSidebarTab,
    salvarComplementar: function () {
      if (SOMENTE_LEITURA) return;
      const id = currentPiSidebar && currentPiSidebar.id_pi ? currentPiSidebar.id_pi : currentPiSidebar;
      if (!id) return;
      fetch('/api/cadu_pi/' + id + '/complementar', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collectPatchBody()),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) throw new Error(data.message);
          currentPiSidebar = data.pi;
          if (typeof showToast === 'function') showToast('Dados salvos', 'success');
        })
        .catch(function (e) {
          if (typeof showToast === 'function') showToast(e.message || 'Erro ao salvar', 'error');
        });
    },
    adicionarLink: function () {
      if (SOMENTE_LEITURA) return;
      const id = currentPiSidebar && currentPiSidebar.id_pi ? currentPiSidebar.id_pi : currentPiSidebar;
      const link = (document.getElementById('piNovoLinkUrl') || {}).value || '';
      const desc = (document.getElementById('piNovoLinkDesc') || {}).value || '';
      if (!id || !link.trim()) return;
      fetch('/api/cadu_pi/' + id + '/link-destinos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: link.trim(), descricao: desc.trim() }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) throw new Error(data.message);
          document.getElementById('piNovoLinkUrl').value = '';
          document.getElementById('piNovoLinkDesc').value = '';
          return fetch('/api/cadu_pi/' + id + '/link-destinos');
        })
        .then(function (r) { return r.json(); })
        .then(function (data) { if (data.success) renderLinkDestinos(data.links); })
        .catch(function (e) {
          if (typeof showToast === 'function') showToast(e.message || 'Erro', 'error');
        });
    },
    excluirLink: function (idLd) {
      if (SOMENTE_LEITURA) return;
      const id = currentPiSidebar && currentPiSidebar.id_pi ? currentPiSidebar.id_pi : currentPiSidebar;
      if (!id) return;
      fetch('/api/cadu_pi/link-destinos/' + idLd, { method: 'DELETE' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) throw new Error(data.message);
          return fetch('/api/cadu_pi/' + id + '/link-destinos');
        })
        .then(function (r) { return r.json(); })
        .then(function (data) { if (data.success) renderLinkDestinos(data.links); })
        .catch(function (e) {
          if (typeof showToast === 'function') showToast(e.message || 'Erro', 'error');
        });
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    UI.updatePiStickyTop();
    window.addEventListener('resize', UI.updatePiStickyTop);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') fecharSidebarPi();
    });
    document.querySelectorAll('.pi-sidebar-tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchPiSidebarTab(btn.getAttribute('data-tab'));
      });
    });
    document.querySelectorAll('[data-campanha-ids]').forEach(function (el) {
      try {
        const ids = JSON.parse(el.getAttribute('data-campanha-ids') || '[]');
        const idPi = el.getAttribute('data-pi-id');
        if (ids.length && idPi) updateFlagSummary(idPi, ids);
      } catch (err) { /* ignore */ }
    });
  });
})();
