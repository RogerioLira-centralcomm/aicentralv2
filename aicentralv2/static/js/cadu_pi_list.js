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
  let filterDebounceTimer = null;
  let clientDebounceTimer = null;
  let sidebarCloseTimer = null;
  let subStatusAtual = new URLSearchParams(window.location.search).get('id_sub_status_pi') || '';
  let visaoComercial = new URLSearchParams(window.location.search).get('visao') || '';
  const origemLista = new URLSearchParams(window.location.search).get('origem') || '';

  function setFilterFeedback(message) {
    const feedback = document.querySelector('[data-filter-feedback]');
    if (feedback) feedback.textContent = message || '';
  }

  function activeFilterEntries() {
    const params = new URLSearchParams(window.location.search);
    const labels = {
      resp_comercial: 'Executivo',
      id_cliente: 'Cliente',
      tipo_entidade: 'Entidade',
      mes_ref_comp: 'Mês',
      ano_ref_comp: 'Ano',
      busca: 'Busca',
      nf_status: 'Status da NF',
    };
    return Object.keys(labels)
      .filter(function (key) { return params.get(key); })
      .map(function (key) { return { key: key, label: labels[key], value: params.get(key) }; });
  }

  function renderActiveFilters() {
    const wrap = document.querySelector('[data-active-filters]');
    const list = document.querySelector('[data-active-filter-list]');
    const count = document.querySelector('[data-filter-count]');
    const entries = activeFilterEntries();
    if (count) {
      count.hidden = entries.length === 0;
      count.textContent = String(entries.length);
      count.setAttribute('aria-label', entries.length + ' filtros ativos');
    }
    if (!wrap || !list) return;
    wrap.hidden = entries.length === 0;
    list.innerHTML = entries.map(function (entry) {
      const value = entry.key === 'id_cliente'
        ? ((document.getElementById('filtro_cliente_busca') || {}).value || entry.value)
        : entry.value;
      return '<button type="button" class="pi-active-filter" data-remove-filter="' + entry.key + '">' +
        '<span>' + entry.label + ': ' + value + '</span><i class="fa-solid fa-xmark" aria-hidden="true"></i>' +
        '<span class="sr-only">Remover filtro</span></button>';
    }).join('');
  }

  function buildFilterParams() {
    const params = new URLSearchParams();
    const exec = (document.getElementById('filtro_executivo') || {}).value || '';
    const mes = (document.getElementById('filtro_mes_ref') || {}).value || '';
    const busca = ((document.getElementById('filtro_busca') || {}).value || '').trim();
    const ano = (document.getElementById('filtro_ano_ref') || {}).value || '';
    const tipoEntidade = (document.getElementById('filtro_tipo_entidade') || {}).value || '';
    const clienteId = (document.getElementById('filtro_cliente_id') || {}).value || '';

    setCookie('cc_filtro_exec', exec, 30);
    if (origemLista === 'faturamento' || origemLista === 'nf_emitida') {
      setCookie('cc_pi_origem_lista', origemLista, 30);
      setCookie('cc_filtro_mes_' + origemLista, mes, 30);
      setCookie('cc_filtro_ano_' + origemLista, ano, 30);
      setCookie('cc_filtro_tipo_entidade_' + origemLista, tipoEntidade, 30);
    } else {
      setCookie('cc_filtro_mes', mes, 30);
      if (origemLista === 'operacao') setCookie('cc_pi_origem_lista', 'operacao', 30);
    }

    if (exec) params.set('resp_comercial', exec);
    if (tipoEntidade) params.set('tipo_entidade', tipoEntidade);
    else if (clienteId) params.set('id_cliente', clienteId);
    if (subStatusAtual) params.set('id_sub_status_pi', subStatusAtual);
    if (visaoComercial) params.set('visao', visaoComercial);
    let mesVal = mes;
    if (mesVal && ano && mesVal.split('/')[1] !== ano) mesVal = '';
    if (mesVal) params.set('mes_ref_comp', mesVal);
    else if (ano) params.set('ano_ref_comp', ano);
    if (busca) params.set('busca', busca);
    if (origemLista) params.set('origem', origemLista);
    if (origemLista === 'nf_emitida') {
      const nfStatus = new URLSearchParams(window.location.search).get('nf_status');
      if (nfStatus) params.set('nf_status', nfStatus);
    }
    params.set('_f', '1');
    return params;
  }

  window.aplicarFiltros = function () {
    setFilterFeedback('Aplicando…');
    const params = buildFilterParams();
    window.location.href = '/cadu_pi' + (params.toString() ? '?' + params.toString() : '');
  };

  window.debounceAplicarFiltros = function () {
    clearTimeout(filterDebounceTimer);
    setFilterFeedback('Aguardando…');
    filterDebounceTimer = setTimeout(window.aplicarFiltros, 500);
  };

  window.filtrarVisaoComercial = function (visao) {
    subStatusAtual = '2';
    visaoComercial = visao || '';
    window.aplicarFiltros();
  };

  window.filtrarSubStatus = function (key) {
    subStatusAtual = subStatusAtual === key ? '' : key;
    window.aplicarFiltros();
  };

  window.filtrarNfStatus = function (status) {
    const params = new URLSearchParams(window.location.search);
    if (status) params.set('nf_status', status);
    else params.delete('nf_status');
    params.set('origem', 'nf_emitida');
    window.location.href = '/cadu_pi?' + params.toString();
  };

  window.filtrarMesesPorAno = function () {
    const year = document.getElementById('filtro_ano_ref');
    const month = document.getElementById('filtro_mes_ref');
    if (!year || !month) return;
    Array.prototype.forEach.call(month.options, function (option) {
      option.hidden = Boolean(year.value && option.value && option.value.split('/')[1] !== year.value);
      if (option.hidden && option.selected) month.value = '';
    });
  };

  function selectClientFilter(id, name) {
    document.getElementById('filtro_cliente_id').value = id;
    document.getElementById('filtro_cliente_busca').value = name;
    document.getElementById('resultados_clientes_filtro').classList.add('hidden');
    document.getElementById('btn_limpar_cliente').classList.remove('hidden');
    window.aplicarFiltros();
  }

  window.buscarClientesFiltro = function (term) {
    clearTimeout(clientDebounceTimer);
    const results = document.getElementById('resultados_clientes_filtro');
    if (!results) return;
    if ((term || '').trim().length < 2) {
      results.classList.add('hidden');
      return;
    }
    results.innerHTML = '<span class="pi-client-results__state">Buscando clientes…</span>';
    results.classList.remove('hidden');
    clientDebounceTimer = setTimeout(function () {
      fetch('/api/clientes/buscar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome: term, razao: term }),
      })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          const clients = data.success && Array.isArray(data.clientes) ? data.clientes : [];
          if (!clients.length) {
            results.innerHTML = '<span class="pi-client-results__state">Nenhum cliente encontrado</span>';
            return;
          }
          results.innerHTML = '';
          clients.forEach(function (client) {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = 'pi-client-option';
            option.setAttribute('role', 'option');
            option.innerHTML = '<strong></strong><span></span>';
            option.querySelector('strong').textContent = client.nome_fantasia || client.razao_social || 'Cliente';
            option.querySelector('span').textContent = client.razao_social || '';
            option.addEventListener('click', function () {
              selectClientFilter(client.id_cliente || client.pk_id_tbl_cliente, client.nome_fantasia || client.razao_social || '');
            });
            results.appendChild(option);
          });
        })
        .catch(function () {
          results.innerHTML = '<span class="pi-client-results__state is-error">Não foi possível buscar clientes. Tente novamente.</span>';
        });
    }, 300);
  };

  window.selecionarClienteFiltro = selectClientFilter;

  window.limparFiltroCliente = function () {
    document.getElementById('filtro_cliente_id').value = '';
    document.getElementById('filtro_cliente_busca').value = '';
    document.getElementById('btn_limpar_cliente').classList.add('hidden');
    window.aplicarFiltros();
  };

  function restoreFilters() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('_restored')) return;
    const exec = getCookie('cc_filtro_exec');
    const month = (origemLista === 'faturamento' || origemLista === 'nf_emitida')
      ? (getCookie('cc_filtro_mes_' + origemLista) || getCookie('cc_filtro_mes'))
      : getCookie('cc_filtro_mes');
    const year = (origemLista === 'faturamento' || origemLista === 'nf_emitida')
      ? (getCookie('cc_filtro_ano_' + origemLista) || getCookie('cc_filtro_ano')) : '';
    const entity = (origemLista === 'faturamento' || origemLista === 'nf_emitida')
      ? getCookie('cc_filtro_tipo_entidade_' + origemLista) : '';
    const restored = new URLSearchParams(params);
    let changed = false;

    [['resp_comercial', exec], ['tipo_entidade', entity]].forEach(function (entry) {
      if (entry[1] && !params.has(entry[0])) {
        restored.set(entry[0], entry[1]);
        changed = true;
      }
    });
    if (year && !params.has('ano_ref_comp') && !params.has('mes_ref_comp')) {
      const yearSelect = document.getElementById('filtro_ano_ref');
      if (yearSelect && Array.prototype.some.call(yearSelect.options, function (option) { return option.value === year; })) {
        restored.set('ano_ref_comp', year);
        changed = true;
      }
    }
    if (month && !params.has('mes_ref_comp') && !restored.has('ano_ref_comp')) {
      const monthSelect = document.getElementById('filtro_mes_ref');
      const matching = monthSelect && Array.prototype.find.call(monthSelect.options, function (option) {
        return option.value === month || parseInt(option.value, 10) === parseInt(month, 10);
      });
      if (matching && (!year || matching.value.split('/')[1] === year)) {
        restored.set('mes_ref_comp', matching.value);
        changed = true;
      }
    }
    if (!changed) return;
    if (visaoComercial && !restored.has('visao')) restored.set('visao', visaoComercial);
    if (origemLista && !restored.has('origem')) restored.set('origem', origemLista);
    else if (!restored.has('origem') && subStatusAtual === '4') {
      const savedOrigin = getCookie('cc_pi_origem_lista');
      if (['faturamento', 'operacao', 'nf_emitida'].indexOf(savedOrigin) !== -1) restored.set('origem', savedOrigin);
    }
    restored.set('_restored', '1');
    window.location.href = '/cadu_pi?' + restored.toString();
  }

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
    return UI.formatBrlPtBR(v);
  }

  function fmtInt(v) {
    return UI.formatVolumeIntPtBR(v);
  }

  function parseBrl(v) {
    return UI.parseBrlMoeda(v);
  }

  function escapeHtml(value) {
    const node = document.createElement('span');
    node.textContent = value == null ? '' : String(value);
    return node.innerHTML;
  }

  function updateFlagSummary(idPi, campanhaIds) {
    const el = document.getElementById('pi-flag-summary-' + idPi);
    if (!el || !campanhaIds || !campanhaIds.length) return;
    const text = UI.aggregateFlagsForCampanhas(campanhaIds);
    el.textContent = text;
    el.style.display = text ? '' : 'none';
  }

  function campaignStatusPillClass(statusName) {
    const status = (statusName || '').toLowerCase();
    if (status.indexOf('ativa') !== -1 || status.indexOf('veicul') !== -1) return 'is-active';
    if (status.indexOf('análise') !== -1 || status.indexOf('analise') !== -1 || status.indexOf('revis') !== -1) return 'is-review';
    if (status.indexOf('pend') !== -1 || status.indexOf('paus') !== -1) return 'is-pending';
    return '';
  }

  function buildCampaignDetailRowHtml(idPi, c) {
    const objContratadoNum = UI.parseVolume(c.obj_contratados);
    const objAtingidoNum = UI.parseVolume(c.totalizador_atingido);
    const pctObj = c.pct_objetivo != null ? Number(c.pct_objetivo) : (objContratadoNum > 0 ? Math.round((objAtingidoNum / objContratadoNum) * 100) : 0);

    const gasto = c.custo_midia_realizado != null ? parseBrl(c.custo_midia_realizado) : parseBrl(c.totalizador_gasto);
    const previsto = c.custo_midia_previsto != null ? parseBrl(c.custo_midia_previsto) : parseBrl(c.valor_plataforma);
    const pctMidia = c.pct_custo_midia != null ? Number(c.pct_custo_midia) : (previsto > 0 ? Math.round((gasto / previsto) * 100) : 0);

    const periodoLinha1 = '<strong class="pi-inner-flight">' + escapeHtml(c.periodo_inicio || '—') + (c.periodo_fim ? ' — ' + escapeHtml(c.periodo_fim) : '') + '</strong>';
    const periodoLinha2 = (c.periodo_dias != null && c.periodo_dias !== '')
      ? '<span class="pi-inner-muted">' + escapeHtml(c.periodo_dias) + ' dias</span>' : '';
    const pctPeriodo = c.periodo_pct_elapsed != null ? Number(c.periodo_pct_elapsed) : null;
    let celPeriodo = periodoLinha1 + periodoLinha2;
    if (pctPeriodo != null && !isNaN(pctPeriodo)) {
      celPeriodo += '<div class="pi-inner-progress">' + UI.buildProgressHtml(pctPeriodo, { small: true }) + '</div>';
    }

    const payload = encodeURIComponent(JSON.stringify(c));
    const platId = c.id_plataforma != null ? c.id_plataforma : '';
    const platNome = escapeHtml(c.plataforma_nome || 'Não informado');
    const statusNome = c.status_nome || 'Status não informado';
    const statusClass = campaignStatusPillClass(statusNome);
    const linkCount = (c.googled_pi_princ ? 1 : 0) + (c.link_dash ? 1 : 0);

    let celObjetivo = UI.cellEmptyHtml('empty-na');
    if (objContratadoNum > 0) {
      celObjetivo = UI.buildProgressHtml(pctObj, { small: true }) +
        '<strong class="pi-inner-value">' + fmtInt(objAtingidoNum) + ' entregues</strong>' +
        '<span class="pi-inner-muted">de ' + fmtInt(objContratadoNum) + ' contratados</span>';
    }

    let celMidia = UI.cellEmptyHtml('empty-pending');
    if (previsto > 0 || gasto > 0) {
      celMidia = UI.buildProgressHtml(pctMidia, { small: true }) +
        '<strong class="pi-inner-value">' + fmtBrl(gasto) + '</strong>' +
        '<span class="pi-inner-muted">de ' + fmtBrl(previsto) + '</span>';
    }

    return '<tr class="pi-campaign-detail-row pi-campaign-row row-campaign--child" data-campaign-parent="' + idPi + '" data-plataforma-id="' + platId + '" data-plataforma-nome="' + platNome + '" data-camp-payload="' + payload + '" tabindex="0" title="Ver detalhes da campanha">' +
      '<td data-label="Nome" class="pi-campaign-detail-name"><strong>' + escapeHtml(c.nome_campanha || 'Campanha sem nome') + '</strong>' +
      '<span class="pi-campaign-status-pill ' + statusClass + '">' + escapeHtml(statusNome) + '</span></td>' +
      '<td data-label="Cliente" class="pi-campaign-detail-platform platform-cell"><div class="platform-badge" data-platform-badge><span class="platform-icon-wrap" title="' + platNome + '"><i class="platform-icon fa-solid fa-bullhorn"></i></span>' +
      '<span class="link-count-badge' + (linkCount === 0 ? ' empty' : '') + '">L' + linkCount + '</span></div>' +
      '<span>' + platNome + '</span></td>' +
      '<td data-label="Responsável" class="pi-commercial-owner"><span class="cx-cell-empty empty-na">—</span></td>' +
      '<td data-label="Veiculação" class="pi-inner-flight-cell">' + celPeriodo + '</td>' +
      '<td data-label="Entrega" class="pi-inner-delivery">' + celObjetivo + '</td>' +
      '<td data-label="Investimento" class="pi-campaign-detail-money pi-inner-investment">' + celMidia + '</td>' +
      '<td data-label="Ações" class="pi-commercial-actions" aria-hidden="true"></td>' +
      '</tr>';
  }

  function buildCampanhaRowHtml(c) {
    const objContratadoNum = UI.parseVolume(c.obj_contratados);
    const objAtingidoNum = UI.parseVolume(c.totalizador_atingido);
    const pctObj = c.pct_objetivo != null ? Number(c.pct_objetivo) : (objContratadoNum > 0 ? Math.round((objAtingidoNum / objContratadoNum) * 100) : 0);

    const gasto = c.custo_midia_realizado != null ? parseBrl(c.custo_midia_realizado) : parseBrl(c.totalizador_gasto);
    const previsto = c.custo_midia_previsto != null ? parseBrl(c.custo_midia_previsto) : parseBrl(c.valor_plataforma);
    const pctMidia = c.pct_custo_midia != null ? Number(c.pct_custo_midia) : (previsto > 0 ? Math.round((gasto / previsto) * 100) : 0);

    const precoOrc = c.preco_unitario_orcado_brl != null ? Number(c.preco_unitario_orcado_brl) : null;
    const precoReal = c.preco_unitario_realizado_brl != null ? Number(c.preco_unitario_realizado_brl) : null;
    const sigla = siglaMetricaPreco(c.objetivo_nome, c.preco_metrica_modalidade);

    const periodoLinha1 = '<strong class="pi-inner-flight">' + (c.periodo_inicio || '—') + (c.periodo_fim ? ' — ' + c.periodo_fim : '') + '</strong>';
    const periodoLinha2 = (c.periodo_dias != null && c.periodo_dias !== '')
      ? '<span class="pi-inner-muted">' + c.periodo_dias + ' dias</span>' : '';
    const pctPeriodo = c.periodo_pct_elapsed != null ? Number(c.periodo_pct_elapsed) : null;
    let celPeriodo = periodoLinha1 + periodoLinha2;
    if (pctPeriodo != null && !isNaN(pctPeriodo)) {
      celPeriodo += '<div class="pi-inner-progress">' + UI.buildProgressHtml(pctPeriodo, { small: true }) + '</div>';
    }

    const payload = encodeURIComponent(JSON.stringify(c));
    const platId = c.id_plataforma != null ? c.id_plataforma : '';
    const platNome = (c.plataforma_nome || '').replace(/"/g, '&quot;');

    let celCustos = UI.cellEmptyHtml('empty-na');
    if (precoOrc != null || precoReal != null) {
      celCustos = '<span class="pi-inner-kpi">' + sigla + '</span>';
      if (precoOrc != null) {
        celCustos += '<span class="pi-inner-muted">Orçado ' + fmtBrl(precoOrc) + '</span>';
      }
      if (precoReal != null) {
        celCustos += '<strong class="pi-inner-value">Realizado ' + fmtBrl(precoReal) + '</strong>';
      }
    }

    let celObjetivo = UI.cellEmptyHtml('empty-na');
    if (objContratadoNum > 0) {
      celObjetivo = UI.buildProgressHtml(pctObj, { small: true }) +
        '<strong class="pi-inner-value">' + fmtInt(objAtingidoNum) + ' entregues</strong>' +
        '<span class="pi-inner-muted">de ' + fmtInt(objContratadoNum) + ' contratados</span>';
    }

    let celMidia = UI.cellEmptyHtml('empty-pending');
    if (previsto > 0 || gasto > 0) {
      celMidia = UI.buildProgressHtml(pctMidia, { small: true }) +
        '<strong class="pi-inner-value">' + fmtBrl(gasto) + ' investidos</strong>' +
        '<span class="pi-inner-muted">de ' + fmtBrl(previsto) + ' previstos</span>';
    }

    const linkCount = (c.googled_pi_princ ? 1 : 0) + (c.link_dash ? 1 : 0);

    return '<tr class="pi-campaign-row" data-plataforma-id="' + platId + '" data-plataforma-nome="' + platNome + '" data-camp-payload="' + payload + '" tabindex="0" title="Ver detalhes da campanha">' +
      '<td data-label="Campanha" class="pi-inner-campaign"><span class="pi-campaign-name">' + (c.nome_campanha || 'Campanha sem nome') + '</span>' +
      '<span class="pi-campaign-status">' + (c.status_nome || 'Status não informado') + '</span></td>' +
      '<td data-label="Plataforma" class="platform-cell pi-inner-platform"><div class="platform-badge" data-platform-badge><span class="platform-icon-wrap" title="' + platNome + '"><i class="platform-icon fa-solid fa-bullhorn"></i></span>' +
      '<span class="link-count-badge' + (linkCount === 0 ? ' empty' : '') + '">L' + linkCount + '</span></div>' +
      '<span class="pi-campaign-platform">' + (c.plataforma_nome || 'Não informado') + '</span></td>' +
      '<td data-label="Veiculação" class="pi-inner-flight-cell">' + celPeriodo + '</td>' +
      '<td data-label="Custo unitário" class="pi-inner-unit-cost">' + celCustos + '</td>' +
      '<td data-label="Entrega" class="pi-inner-delivery">' + celObjetivo + '</td>' +
      '<td data-label="Investimento" class="pi-inner-investment">' + celMidia + '</td>' +
      '</tr>';
  }

  function removeCampaignRowsForPi(idPi) {
    document.querySelectorAll('[data-campaign-parent="' + idPi + '"], [data-campaign-loading="' + idPi + '"]').forEach(function (row) {
      row.remove();
    });
  }

  function buildCampaignLoadingRow(idPi) {
    return '<tr class="pi-campaign-loading-row" data-campaign-loading="' + idPi + '" data-campaign-parent="' + idPi + '">' +
      '<td colspan="7"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Carregando campanhas…</td></tr>';
  }

  function insertCampaignRowsAfterPi(piRow, idPi, campanhas) {
    removeCampaignRowsForPi(idPi);
    if (!campanhas || !campanhas.length) return [];
    const campIds = [];
    let html = '';
    campanhas.forEach(function (c) {
      if (c.id_campanha) campIds.push(c.id_campanha);
      html += buildCampaignDetailRowHtml(idPi, c);
    });
    piRow.insertAdjacentHTML('afterend', html);
    const inserted = [];
    let node = piRow.nextElementSibling;
    while (node && node.getAttribute('data-campaign-parent') === String(idPi)) {
      inserted.push(node);
      node = node.nextElementSibling;
    }
    UI.applyPlatformIcons(piRow.parentElement);
    updateFlagSummary(idPi, campIds);
    return inserted;
  }

  function setPiGroupExpanded(idPi, expanded) {
    document.querySelectorAll('[data-campaign-parent="' + idPi + '"]').forEach(function (row) {
      row.hidden = !expanded;
    });
    const toggle = document.querySelector('[data-pi-group-toggle="' + idPi + '"]');
    if (toggle) {
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.setAttribute('aria-label', expanded ? 'Recolher campanhas do PI' : 'Expandir campanhas do PI');
    }
  }

  function loadCampaignsForPi(idPi) {
    const piRow = document.getElementById('pi-' + idPi);
    if (!piRow || loadedCampanhas[idPi] === true) return Promise.resolve();
    if (loadedCampanhas[idPi] === 'loading') return loadedCampanhas[idPi + '_promise'] || Promise.resolve();
    loadedCampanhas[idPi] = 'loading';
    piRow.insertAdjacentHTML('afterend', buildCampaignLoadingRow(idPi));

    const promise = fetch('/api/cadu-pi/' + idPi + '/campanhas')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        loadedCampanhas[idPi] = true;
        if (!piRow.isConnected) return;
        if (!data.success || !data.campanhas || !data.campanhas.length) {
          removeCampaignRowsForPi(idPi);
          return;
        }
        insertCampaignRowsAfterPi(piRow, idPi, data.campanhas);
        const toggle = document.querySelector('[data-pi-group-toggle="' + idPi + '"]');
        const expanded = !toggle || toggle.getAttribute('aria-expanded') !== 'false';
        setPiGroupExpanded(idPi, expanded);
      })
      .catch(function () {
        loadedCampanhas[idPi] = false;
        removeCampaignRowsForPi(idPi);
        piRow.insertAdjacentHTML('afterend',
          '<tr class="pi-campaign-loading-row" data-campaign-parent="' + idPi + '"><td colspan="7">' +
          '<span class="pi-campaign-error" role="alert"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>' +
          ' Não foi possível carregar as campanhas. ' +
          '<button type="button" class="cx-btn cx-btn-sm cx-btn-outline" onclick="retryCampanhas(' + idPi + ')">Tentar novamente</button></span></td></tr>');
      });
    loadedCampanhas[idPi + '_promise'] = promise;
    return promise;
  }

  function autoLoadHierarchyCampaigns() {
    const piRows = Array.prototype.slice.call(document.querySelectorAll('tr.pi-row.row-pi[data-campaign-count]'));
    const queue = piRows.filter(function (row) {
      return parseInt(row.getAttribute('data-campaign-count') || '0', 10) > 0;
    });
    if (!queue.length) return;

    let index = 0;
    const concurrency = 4;
    function pump() {
      const batch = queue.slice(index, index + concurrency);
      index += concurrency;
      if (!batch.length) return;
      Promise.all(batch.map(function (row) {
        const idPi = parseInt(row.getAttribute('data-pi-id') || row.id.replace('pi-', ''), 10);
        return loadCampaignsForPi(idPi);
      })).finally(function () {
        if (index < queue.length) {
          if (typeof window.requestIdleCallback === 'function') {
            window.requestIdleCallback(pump);
          } else {
            window.setTimeout(pump, 0);
          }
        }
      });
    }
    pump();
  }

  window.togglePiGroup = function (idPi, event) {
    if (event && event.stopPropagation) event.stopPropagation();
    const toggle = document.querySelector('[data-pi-group-toggle="' + idPi + '"]');
    const shouldExpand = toggle ? toggle.getAttribute('aria-expanded') !== 'true' : true;
    if (shouldExpand && !loadedCampanhas[idPi]) {
      loadCampaignsForPi(idPi).then(function () {
        setPiGroupExpanded(idPi, true);
      });
      return;
    }
    setPiGroupExpanded(idPi, shouldExpand);
  };

  window.toggleCampanhas = function (idPi, event) {
    if (document.getElementById('camp-collapse-' + idPi)) {
      if (event && event.stopPropagation) event.stopPropagation();
      const row = document.getElementById('camp-collapse-' + idPi);
      const chevron = document.getElementById('chevron-' + idPi);
      if (!row) return;

      const toggle = document.querySelector('[data-campaign-toggle="' + idPi + '"]');
      const shouldExpand = !toggle || toggle.getAttribute('aria-expanded') !== 'true';
      row.classList.toggle('hidden', !shouldExpand);
      if (chevron) chevron.classList.toggle('open', shouldExpand);
      if (toggle) {
        toggle.setAttribute('aria-expanded', String(shouldExpand));
        const count = toggle.getAttribute('data-campaign-count') || '';
        const label = toggle.querySelector('[data-campaign-toggle-label]');
        if (label) label.textContent = shouldExpand ? 'Ocultar campanhas' : ('Mostrar ' + count + ' campanha' + (count === '1' ? '' : 's'));
      }

      if (shouldExpand && !loadedCampanhas[idPi]) {
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
            let html = '<table class="camp-table camp-table--operational"><colgroup>' +
              '<col style="width:24%"><col style="width:12%"><col style="width:18%"><col style="width:14%"><col style="width:16%"><col style="width:16%">' +
              '</colgroup><thead><tr>' +
              '<th class="text-left">Campanha</th><th class="text-left">Plataforma</th><th class="text-left">Veiculação</th>' +
              '<th class="text-left">Custo unitário</th><th class="text-left">Entrega</th><th class="text-left">Investimento</th>' +
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
            if (!container) return;
            container.innerHTML = '<div class="pi-campaign-error" role="alert"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>' +
              '<span>Não foi possível carregar as campanhas.</span>' +
              '<button type="button" class="cx-btn cx-btn-sm cx-btn-outline" onclick="retryCampanhas(' + idPi + ')">Tentar novamente</button></div>';
          });
      }
      return;
    }
    window.togglePiGroup(idPi, event);
  };

  window.retryCampanhas = function (idPi) {
    loadedCampanhas[idPi] = false;
    delete loadedCampanhas[idPi + '_promise'];
    removeCampaignRowsForPi(idPi);
    if (document.getElementById('camp-collapse-' + idPi)) {
      const row = document.getElementById('camp-collapse-' + idPi);
      if (row) row.classList.add('hidden');
      window.toggleCampanhas(idPi, { stopPropagation: function () {} });
      return;
    }
    loadCampaignsForPi(idPi);
  };

  window.toggleAgenciaPis = function (idAgencia, event) {
    if (event && event.stopPropagation) event.stopPropagation();
    const row = document.getElementById('ag-pis-' + idAgencia);
    const chevron = document.getElementById('chevron-ag-' + idAgencia);
    if (!row) return;
    const isHidden = row.classList.contains('hidden');
    row.classList.toggle('hidden');
    if (chevron) chevron.classList.toggle('open', isHidden);
    const toggle = document.querySelector('[aria-controls="ag-pis-' + idAgencia + '"]');
    if (toggle) toggle.setAttribute('aria-expanded', String(isHidden));
  };

  window.toggleTodasCampanhas = function () {
    window.todasExpandidas = !window.todasExpandidas;
    const hierarchyRows = document.querySelectorAll('tr.pi-row.row-pi[data-pi-id]');
    if (hierarchyRows.length) {
      hierarchyRows.forEach(function (row) {
        const idPi = parseInt(row.getAttribute('data-pi-id') || '0', 10);
        if (!idPi) return;
        const toggle = document.querySelector('[data-pi-group-toggle="' + idPi + '"]');
        const isExpanded = toggle ? toggle.getAttribute('aria-expanded') === 'true' : window.todasExpandidas;
        if (window.todasExpandidas !== isExpanded) {
          if (window.todasExpandidas) {
            if (!loadedCampanhas[idPi]) {
              loadCampaignsForPi(idPi).then(function () { setPiGroupExpanded(idPi, true); });
            } else {
              setPiGroupExpanded(idPi, true);
            }
          } else {
            setPiGroupExpanded(idPi, false);
          }
        }
      });
    } else {
      document.querySelectorAll('tr.collapse-camp-row').forEach(function (row) {
        const idPi = row.id.replace('camp-collapse-', '');
        const toggle = document.querySelector('[data-campaign-toggle="' + idPi + '"]');
        const isExpanded = toggle && toggle.getAttribute('aria-expanded') === 'true';
        if (window.todasExpandidas !== isExpanded) {
          toggleCampanhas(parseInt(idPi, 10), { stopPropagation: function () {} });
        }
      });
    }
    const label = document.getElementById('label_expandir_todas');
    const icon = document.getElementById('icon_expandir_todas');
    const button = document.getElementById('btn_expandir_todas');
    if (label) label.textContent = window.todasExpandidas ? 'Recolher todas' : 'Expandir todas';
    if (icon) icon.className = window.todasExpandidas ? 'fa-solid fa-angles-up' : 'fa-solid fa-angles-down';
    if (button) button.setAttribute('aria-expanded', String(window.todasExpandidas));
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
    clearTimeout(sidebarCloseTimer);
    panel.hidden = false;
    overlay.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sidebar-open');
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        panel.classList.add('open');
        overlay.classList.add('open');
      });
    });
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
    if (panel) panel.setAttribute('aria-hidden', 'true');
    if (overlay) overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('sidebar-open');
    clearTimeout(sidebarCloseTimer);
    sidebarCloseTimer = window.setTimeout(function () {
      if (panel && !panel.classList.contains('open')) panel.hidden = true;
      if (overlay && !overlay.classList.contains('open')) overlay.hidden = true;
    }, 360);
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

  function assignMobileCellLabels() {
    document.querySelectorAll('.pi-list-table-detail').forEach(function (table) {
      const labels = Array.prototype.map.call(table.querySelectorAll(':scope > thead th'), function (header) {
        return (header.textContent || '').trim() || 'Ações';
      });
      table.querySelectorAll(':scope > tbody > .pi-row').forEach(function (row) {
        Array.prototype.forEach.call(row.children, function (cell, index) {
          if (cell.tagName === 'TD' && !cell.hasAttribute('data-label')) {
            cell.setAttribute('data-label', labels[index] || 'Informação');
          }
        });
      });
    });
  }

  function toggleInvoiceGroup(button) {
    const key = button.getAttribute('data-nf-group-toggle');
    const expanded = button.getAttribute('aria-expanded') !== 'false';
    button.setAttribute('aria-expanded', String(!expanded));
    document.querySelectorAll('[data-nf-group-item="' + key + '"]').forEach(function (row) {
      row.hidden = expanded;
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    restoreFilters();
    window.filtrarMesesPorAno();
    renderActiveFilters();
    assignMobileCellLabels();
    UI.updatePiStickyTop();
    if (document.querySelector('.pi-list-table--hierarchy')) {
      window.todasExpandidas = true;
      autoLoadHierarchyCampaigns();
    }
    window.addEventListener('resize', function () {
      UI.updatePiStickyTop();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') fecharSidebarPi();
    });
    document.querySelectorAll('.pi-sidebar-tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchPiSidebarTab(btn.getAttribute('data-tab'));
      });
    });
    document.querySelectorAll('[data-nf-group-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        toggleInvoiceGroup(button);
      });
    });
    const search = document.getElementById('filtro_busca');
    if (search) search.addEventListener('input', window.debounceAplicarFiltros);
    ['filtro_executivo', 'filtro_tipo_entidade', 'filtro_mes_ref'].forEach(function (id) {
      const field = document.getElementById(id);
      if (field) field.addEventListener('change', window.aplicarFiltros);
    });
    const year = document.getElementById('filtro_ano_ref');
    if (year) year.addEventListener('change', function () {
      window.filtrarMesesPorAno();
      window.aplicarFiltros();
    });
    const clientSearch = document.getElementById('filtro_cliente_busca');
    if (clientSearch) {
      clientSearch.addEventListener('input', function () { window.buscarClientesFiltro(clientSearch.value); });
      clientSearch.addEventListener('focus', function () { window.buscarClientesFiltro(clientSearch.value); });
    }
    const clearClient = document.getElementById('btn_limpar_cliente');
    if (clearClient) clearClient.addEventListener('click', window.limparFiltroCliente);
    document.querySelectorAll('[data-remove-filter]').forEach(function (button) {
      button.addEventListener('click', function () {
        const params = new URLSearchParams(window.location.search);
        params.delete(button.getAttribute('data-remove-filter'));
        params.set('_f', '1');
        window.location.href = '/cadu_pi?' + params.toString();
      });
    });
    document.addEventListener('click', function (event) {
      const results = document.getElementById('resultados_clientes_filtro');
      if (results && clientSearch && !results.contains(event.target) && event.target !== clientSearch) {
        results.classList.add('hidden');
      }
    });
    document.addEventListener('keydown', function (event) {
      const row = event.target.closest('.pi-campaign-row, .pi-campaign-detail-row');
      if (row && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        row.click();
      }
    });
    document.addEventListener('click', function (event) {
      if (event.target.closest('.pi-group-toggle, .cx-btn, a.pi-code-link')) return;
      const row = event.target.closest('.pi-campaign-detail-row, .pi-campaign-row[data-camp-payload]');
      if (!row || row.classList.contains('pi-campaign-loading-row')) return;
      try {
        const campaign = JSON.parse(decodeURIComponent(row.getAttribute('data-camp-payload')));
        if (typeof abrirViewCampanhaLista === 'function') abrirViewCampanhaLista(campaign);
      } catch (error) {
        console.error(error);
      }
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
