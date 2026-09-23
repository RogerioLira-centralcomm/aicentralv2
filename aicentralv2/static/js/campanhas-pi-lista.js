/* Campanhas PI lista — page logic */
(function () {
  var cfgEl = document.getElementById('campanhas-lista-config');
  var cfg = cfgEl ? JSON.parse(cfgEl.textContent) : {};
  var isDiariosView = Boolean(cfg.isDiariosView);
  var LISTA_URL = cfg.listaUrl || '/campanhas-pi/lista';
  var CAMPANHA_NOVA_URL = cfg.campanhaNovaUrl || '/campanhas-pi/nova';
  var CAMPANHA_EDITAR_URL_TPL = cfg.campanhaEditarUrlTemplate || '/campanhas-pi/0/editar';
  var CAMPANHA_EXCLUIR_URL_TPL = cfg.campanhaExcluirUrlTemplate || '/campanhas-pi/0/excluir';
  function campanhaEditarUrl(id) {
    return String(CAMPANHA_EDITAR_URL_TPL).replace('/0/', '/' + id + '/');
  }
  function campanhaExcluirUrl(id) {
    return String(CAMPANHA_EXCLUIR_URL_TPL).replace('/0/', '/' + id + '/');
  }

let currentSidebarCamp = null;
  Object.defineProperty(window, 'currentSidebarCamp', {
    configurable: true,
    get: function () { return currentSidebarCamp; },
    set: function (v) { currentSidebarCamp = v; },
  });
  let sidebarChartInstance = null;
  let sidebarCloseTimer = null;
  let selectedEmailTemplate = 'relatorio';
  function notifyCampAction(message, type) {
    const status = document.getElementById('campActionStatus');
    if (status) status.textContent = message;
    if (typeof window.showToast === 'function') window.showToast(message, type || 'info');
  }

  function requestCampConfirmation(options) {
    if (typeof window.showConfirm === 'function') {
      window.showConfirm(options);
      return true;
    }
    notifyCampAction('A confirmação não pôde ser aberta. Recarregue a página e tente novamente.', 'error');
    return false;
  }

  function setCampFormStatus(message, type) {
    const status = document.getElementById('campanhaFormStatus');
    if (!status) return;
    status.textContent = message || '';
    status.dataset.type = type || 'info';
    status.hidden = !message;
  }

  /** Alinhado a _parse_brl_float / parseBrlMoedaJs: número JSON; vírgula = BR; vários pontos = milhar; um ponto = decimal. */
  function parseBrlMoedaJs(val) {
    if (val == null || val === '') return 0;
    if (typeof val === 'number' && Number.isFinite(val)) return val;
    var s = String(val).trim().replace(/R\$\s*/gi, '').replace(/\s/g, '');
    if (!s) return 0;
    if (s.indexOf(',') >= 0) {
      return parseFloat(s.replace(/\./g, '').replace(',', '.')) || 0;
    }
    var parts = s.split('.');
    if (parts.length > 2) return parseFloat(s.replace(/\./g, '')) || 0;
    if (parts.length === 2) return parseFloat(s) || 0;
    return parseFloat(s) || 0;
  }
  // ==================== MÁSCARAS DE INPUT ====================
  function formatarNumero(valor) {
    if (!valor && valor !== 0) return '';
    const num = String(valor).replace(/[^\d]/g, '');
    if (!num) return '';
    return num.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function formatarReal(valor) {
    if (!valor && valor !== 0) return '';
    const num = parseBrlMoedaJs(valor);
    if (!Number.isFinite(num)) return '';
    return 'R$ ' + num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function rawParaFormatado(valor, tipo) {
    if (!valor && valor !== 0) return '';
    const v = String(valor).trim();
    if (!v) return '';
    if (tipo === 'real') return formatarReal(v);
    if (tipo === 'numero') return formatarNumero(v);
    return v;
  }

  function aplicarMascaraNumero(input) {
    input.addEventListener('input', function() {
      const pos = this.selectionStart;
      const antes = this.value.length;
      const digits = this.value.replace(/[^\d]/g, '');
      this.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
      const diff = this.value.length - antes;
      this.setSelectionRange(pos + diff, pos + diff);
    });
  }

  function aplicarMascaraReal(input) {
    input.addEventListener('input', function() {
      let v = this.value.replace(/\D/g, '');
      if (!v) { this.value = ''; return; }
      v = (parseInt(v, 10) / 100).toFixed(2);
      this.value = 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    });
  }

  document.querySelectorAll('[data-mask="numero"]').forEach(aplicarMascaraNumero);
  document.querySelectorAll('[data-mask="real"]').forEach(aplicarMascaraReal);
  document.querySelectorAll('[data-open-date]').forEach(function(button) {
    button.addEventListener('click', function() {
      const input = document.getElementById(button.dataset.openDate);
      if (input && typeof input.showPicker === 'function') input.showPicker();
      else if (input) input.focus();
    });
  });

  // ==================== DISTRIBUIÇÃO % ====================
  var vrPlatMax = 0;
  function parseRealVal(s) {
    return parseBrlMoedaJs(s);
  }
  function calcDistribuicao() {
    var inp = document.getElementById('valor_plataforma');
    var out = document.getElementById('dist_pct');
    if (!inp || !out) return;
    var v = parseRealVal(inp.value);
    var pct = vrPlatMax > 0 ? (v / vrPlatMax) * 100 : 0;
    out.value = pct.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';
  }
  (function() {
    var vpInput = document.getElementById('valor_plataforma');
    if (vpInput) {
      vpInput.addEventListener('input', function() { setTimeout(calcDistribuicao, 0); });
      vpInput.addEventListener('change', function() { setTimeout(calcDistribuicao, 0); });
    }
  })();

  // ==================== AUTO-CÁLCULO PERC/VAL CAMPANHA ====================
  var PERC_VAL_CAMP_PARES = [
    ['perc_margem_cc', 'val_margem_cc'],
    ['perc_tech_fee', 'val_tech_fee'],
    ['perc_com_vendas', 'val_com_vendas'],
    ['perc_pl_incentivos', 'val_pl_incentivos'],
    ['perc_impostos', 'val_impostos'],
  ];
  function maskPctCamp(input) {
    var v = input.value.replace(/\D/g, '').slice(0, 4);
    if (!v) { input.value = ''; return; }
    if (v.length <= 2) { input.value = v; return; }
    input.value = v.slice(0, v.length - 2) + ',' + v.slice(v.length - 2);
  }
  function recalcPercValCampanha() {
    var vpEl = document.getElementById('valor_plataforma');
    var base = vpEl ? parseRealVal(vpEl.value) : 0;
    PERC_VAL_CAMP_PARES.forEach(function(par) {
      var pEl = document.getElementById(par[0]);
      var vEl = document.getElementById(par[1]);
      if (!pEl || !vEl) return;
      var pct = parseRealVal(pEl.value);
      var v = (base > 0 && pct > 0) ? base * pct / 100 : 0;
      vEl.value = v > 0 ? formatarReal(v) : '';
    });
  }
  (function() {
    PERC_VAL_CAMP_PARES.forEach(function(par) {
      var pEl = document.getElementById(par[0]);
      if (pEl) {
        pEl.addEventListener('input', function() { maskPctCamp(this); recalcPercValCampanha(); });
      }
    });
    var vpInput = document.getElementById('valor_plataforma');
    if (vpInput) {
      vpInput.addEventListener('input', function() { setTimeout(recalcPercValCampanha, 0); });
      vpInput.addEventListener('change', function() { setTimeout(recalcPercValCampanha, 0); });
    }
  })();

  // ==================== PLATAFORMA, FLAG E PROGRESSO (UI) ====================
  const CAMP_FLAG_STORAGE_KEY = CampanhasUI.CAMP_FLAG_STORAGE_KEY;
  const CAMP_FLAG_ORDER = CampanhasUI.CAMP_FLAG_ORDER;
  let campFlagSortActive = false;
  let campFlagMenuTarget = null;
  const campFlagMenu = document.getElementById('campFlagMenu');

  function loadCampFlags() {
    try {
      const raw = localStorage.getItem(CAMP_FLAG_STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
  }

  function saveCampFlags(flags) {
    try { localStorage.setItem(CAMP_FLAG_STORAGE_KEY, JSON.stringify(flags)); } catch (e) {}
  }

  function getCampFlag(campanhaId) {
    const flags = loadCampFlags();
    const v = flags[String(campanhaId)];
    return (v === 'critico' || v === 'atencao' || v === 'ok') ? v : 'none';
  }

  function setCampFlag(campanhaId, value) {
    const flags = loadCampFlags();
    const id = String(campanhaId);
    if (value === 'none') delete flags[id];
    else flags[id] = value;
    saveCampFlags(flags);
    syncCampFlagMarkers();
    aplicarVisibilidadeLinhas();
    if (campFlagSortActive) aplicarFlagSort();
  }

  function syncCampFlagMarkers() {
    document.querySelectorAll('[data-flag-for]').forEach(function(el) {
      el.setAttribute('data-flag', getCampFlag(el.getAttribute('data-flag-for')));
    });
    document.querySelectorAll('.campanhas-table-body tr[data-campanha-id]').forEach(function(row) {
      row.dataset.flag = getCampFlag(row.dataset.campanhaId);
    });
  }

  function closeCampFlagMenu() {
    if (!campFlagMenu) return;
    campFlagMenu.classList.remove('open');
    campFlagMenu.setAttribute('aria-hidden', 'true');
    campFlagMenuTarget = null;
  }

  function openCampFlagMenu(btn, campanhaId) {
    if (!campFlagMenu || !btn) return;
    campFlagMenuTarget = String(campanhaId);
    const rect = btn.getBoundingClientRect();
    campFlagMenu.style.left = Math.min(rect.left, window.innerWidth - 180) + 'px';
    campFlagMenu.style.top = (rect.bottom + 4) + 'px';
    campFlagMenu.classList.add('open');
    campFlagMenu.setAttribute('aria-hidden', 'false');
  }

  function initCampFlags() {
    syncCampFlagMarkers();
    document.querySelectorAll('[data-flag-btn]').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        const id = btn.getAttribute('data-flag-btn');
        if (campFlagMenuTarget === id && campFlagMenu && campFlagMenu.classList.contains('open')) {
          closeCampFlagMenu();
        } else {
          openCampFlagMenu(btn, id);
        }
      });
    });
    if (campFlagMenu) {
      campFlagMenu.querySelectorAll('[data-flag-value]').forEach(function(item) {
        item.addEventListener('click', function(e) {
          e.stopPropagation();
          if (campFlagMenuTarget) setCampFlag(campFlagMenuTarget, item.getAttribute('data-flag-value'));
          closeCampFlagMenu();
        });
      });
    }
    document.addEventListener('click', function() { closeCampFlagMenu(); });
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeCampFlagMenu(); });
  }

  function aplicarFlagSort() {
    const tbody = document.querySelector('[data-status-tbody="ativas"]');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[data-campanha-id]'));
    rows.sort(function(a, b) {
      const fa = CAMP_FLAG_ORDER[a.dataset.flag || 'none'] ?? 3;
      const fb = CAMP_FLAG_ORDER[b.dataset.flag || 'none'] ?? 3;
      return fa - fb;
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
  }

  function restaurarOrdemOriginal() {
    const tbody = document.querySelector('[data-status-tbody="ativas"]');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[data-campanha-id]'));
    rows.sort(function(a, b) {
      const oa = parseInt(a.dataset.originalIndex || '0', 10);
      const ob = parseInt(b.dataset.originalIndex || '0', 10);
      return oa - ob;
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
  }

  function toggleFlagSort() {
    campFlagSortActive = !campFlagSortActive;
    const button = document.getElementById('campFlagSortButton');
    if (button) {
      button.classList.toggle('sorted', campFlagSortActive);
      button.setAttribute('aria-pressed', campFlagSortActive ? 'true' : 'false');
      button.setAttribute(
        'aria-label',
        campFlagSortActive ? 'Restaurar ordem das campanhas ativas' : 'Ordenar campanhas ativas por prioridade'
      );
    }
    if (campFlagSortActive) aplicarFlagSort();
    else restaurarOrdemOriginal();
    aplicarVisibilidadeLinhas();
  }

  function aplicarVisibilidadeLinhas() {
    const searchTerm = ((document.getElementById('searchInput') || {}).value || '').toLowerCase();
    const rows = document.querySelectorAll(
      isDiariosView
        ? '#tabelaDiariosMassa tr[data-campanha-id]'
        : '.campanhas-table-body tr[data-campanha-id]'
    );
    let visibleCount = 0;
    rows.forEach(function(row) {
      const textMatch = !searchTerm || row.textContent.toLowerCase().includes(searchTerm);
      row.style.display = textMatch ? '' : 'none';
      if (textMatch) visibleCount++;
    });
    document.querySelectorAll('[data-campaign-group]').forEach(function(group) {
      const groupRows = Array.from(group.querySelectorAll('tr[data-campanha-id]'));
      const groupVisible = groupRows.filter(function(row) { return row.style.display !== 'none'; }).length;
      const counter = group.querySelector('[data-group-visible-count]');
      if (counter) counter.textContent = groupVisible;
      group.hidden = Boolean(searchTerm) && groupVisible === 0;
    });
    const history = document.querySelector('[data-history-container]');
    if (history) {
      const historyVisible = Array.from(history.querySelectorAll('tr[data-campanha-id]'))
        .filter(function(row) { return row.style.display !== 'none'; }).length;
      const counter = history.querySelector('[data-history-visible-count]');
      if (counter) counter.textContent = historyVisible;
      history.hidden = Boolean(searchTerm) && historyVisible === 0;
      if (searchTerm && historyVisible > 0) {
        if (!history.dataset.searchOpen) {
          history.dataset.wasOpen = history.open ? 'true' : 'false';
          history.dataset.searchOpen = 'true';
        }
        history.open = true;
      } else if (!searchTerm && history.dataset.searchOpen) {
        history.open = history.dataset.wasOpen === 'true';
        delete history.dataset.searchOpen;
        delete history.dataset.wasOpen;
      }
    }
    const tc = document.getElementById('totalCampanhas');
    if (tc) tc.textContent = visibleCount;
    const fb = document.getElementById('campSearchFeedback');
    if (fb) {
      if (searchTerm) fb.textContent = visibleCount + ' visíveis';
      else fb.textContent = '';
    }
  }

  function initCampanhasTableUi() {
    document.querySelectorAll('.campanhas-table-body').forEach(function(tbody) {
      tbody.querySelectorAll('tr[data-campanha-id]').forEach(function(row, idx) {
        row.dataset.originalIndex = String(idx);
        row.addEventListener('keydown', function(event) {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            window.location.href = row.dataset.detailUrl;
          }
        });
        const editButton = row.querySelector('[data-row-edit]');
        if (editButton) {
          editButton.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            try {
              abrirModalEditar(JSON.parse(row.dataset.camp));
            } catch (error) {
              console.error('Erro ao abrir edição:', error);
              notifyCampAction('Não foi possível abrir a edição desta campanha.', 'error');
            }
          });
        }
        const diariosButton = row.querySelector('[data-open-diarios]');
        if (diariosButton) {
          diariosButton.addEventListener('click', function() {
            abrirModalDiarios(
              diariosButton.dataset.id,
              diariosButton.dataset.codigo || '',
              diariosButton.dataset.titulo || '',
              diariosButton.dataset.nome || ''
            );
          });
        }
      });
    });
    applyPlatformIcons(document);
    initCampFlags();
    aplicarVisibilidadeLinhas();
  }

  initCampanhasTableUi();

  // ==================== FILTROS ====================
  function aplicarFiltros() {
    const params = new URLSearchParams();
    const execEl = document.getElementById('filtroExecutivo');
    const exec = execEl ? execEl.value : '';

    setCookie('cc_filtro_exec', exec, 30);
    setCookie('cc_filtro_mes', '', -1);

    if (isDiariosView) params.set('view', 'diarios');
    if (exec) params.set('resp_comercial', exec);
    window.location.href = LISTA_URL + (params.toString() ? '?' + params.toString() : '');
  }

  (function restoreCampPiFilters() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('id_status') || params.has('mes_ref_comp') || params.has('_restored')) {
      params.delete('id_status');
      params.delete('mes_ref_comp');
      params.delete('_restored');
      setCookie('cc_filtro_mes', '', -1);
      window.location.replace(LISTA_URL + (params.toString() ? '?' + params.toString() : ''));
      return;
    }
    const cExec = getCookie('cc_filtro_exec');
    setCookie('cc_filtro_mes', '', -1);
    let needsRedirect = false;
    const rp = new URLSearchParams(params);
    if (isDiariosView) rp.set('view', 'diarios');
    if (cExec && !params.has('resp_comercial')) { rp.set('resp_comercial', cExec); needsRedirect = true; }
    if (!needsRedirect) return;
    rp.set('_restored', '1');
    window.location.href = LISTA_URL + '?' + rp.toString();
  })();

  (function () {
    var si = document.getElementById('searchInput');
    if (!si) return;
    var debounceTimer = null;
    si.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(aplicarVisibilidadeLinhas, 200);
    });
  })();

  function parseVolumeCampanhaJs(val) {
    if (val == null || val === '') return 0;
    if (typeof val === 'number' && Number.isFinite(val)) return val;
    const s = String(val).trim();
    if (!s) return 0;
    if (s.indexOf(',') >= 0) {
      const x = s.replace(/\./g, '').replace(',', '.');
      const n = parseFloat(x);
      return Number.isFinite(n) ? n : 0;
    }
    const parts = s.split('.');
    if (parts.length > 2) {
      const n = parseFloat(s.replace(/\./g, ''));
      return Number.isFinite(n) ? n : 0;
    }
    if (parts.length === 2) {
      if (parts[1].length <= 2) return parseFloat(s) || 0;
      const n = parseFloat(s.replace(/\./g, ''));
      return Number.isFinite(n) ? n : 0;
    }
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
  }
  function formatVolumeIntPtBR(n) {
    return Math.round(Number(n) || 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  }
  function metaContratadaPreenchida(camp) {
    if (camp == null || !Object.prototype.hasOwnProperty.call(camp, 'obj_contratados')) return false;
    const v = camp.obj_contratados;
    if (v == null) return false;
    return String(v).trim() !== '';
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

  // ==================== SIDEBAR ====================
  function abrirSidebar(camp) {
    currentSidebarCamp = camp;

    document.querySelectorAll('#campanhasTableBody tr.active').forEach(c => c.classList.remove('active'));
    const row = document.querySelector(`tr[data-campanha-id="${camp.id_campanha}"]`);
    if (row) row.classList.add('active');

    document.getElementById('sidebarTitle').textContent = camp.nome_campanha || 'Campanha';
    document.getElementById('sidebarCliente').textContent = camp.cliente_nome || '—';
    document.getElementById('sidebarExecutivo').textContent = camp.executivo_nome || '—';
    document.getElementById('sidebarPlataforma').textContent = camp.plataforma_nome || '—';
    const sigla = siglaMetricaPreco(camp.objetivo_nome, camp.preco_metrica_modalidade);
    const siglaPrecoEl = document.getElementById('sidebarPrecoSigla');
    const precoOrcLbl = document.getElementById('sidebarPrecoOrcLabel');
    const precoRealLbl = document.getElementById('sidebarPrecoRealLabel');
    const precoOrcEl = document.getElementById('sidebarPrecoOrcado');
    const precoRealEl = document.getElementById('sidebarPrecoRealizado');
    if (siglaPrecoEl) siglaPrecoEl.textContent = sigla !== '—' ? sigla : '';
    if (precoOrcLbl) precoOrcLbl.textContent = (sigla !== '—' ? sigla + ' ' : '') + 'Orçado (cotação)';
    if (precoRealLbl) precoRealLbl.textContent = (sigla !== '—' ? sigla + ' ' : '') + 'Realizado';
    const precoOrc = camp.preco_unitario_orcado_brl != null ? Number(camp.preco_unitario_orcado_brl) : null;
    const precoReal = camp.preco_unitario_realizado_brl != null ? Number(camp.preco_unitario_realizado_brl) : null;
    if (precoOrcEl) precoOrcEl.textContent = precoOrc != null && !isNaN(precoOrc) ? formatarReal(precoOrc) : '—';
    if (precoRealEl) precoRealEl.textContent = precoReal != null && !isNaN(precoReal) ? formatarReal(precoReal) : '—';
    document.getElementById('sidebarStatus').textContent = camp.status_nome || 'N/A';
    document.getElementById('sidebarMesRef').textContent = camp.mes_ref_comp || '—';

    const vlPi = parseBrlMoedaJs(camp.valor_liquido_pi);
    document.getElementById('sidebarVlLiquido').textContent = vlPi > 0 ? 'R$ ' + vlPi.toLocaleString('pt-BR', {minimumFractionDigits: 2}) : '—';

    let periodoText = '—';
    if (camp.periodo_inicio && camp.periodo_fim) {
      const di = new Date(camp.periodo_inicio);
      const df = new Date(camp.periodo_fim);
      const dias = Math.round((df - di) / (1000 * 60 * 60 * 24));
      periodoText = di.toLocaleDateString('pt-BR', {day:'2-digit',month:'2-digit'}) + ' — ' + df.toLocaleDateString('pt-BR', {day:'2-digit',month:'2-digit',year:'numeric'}) + ' (' + dias + 'd)';
    }
    document.getElementById('sidebarPeriodo').textContent = periodoText;

    const objVal = parseVolumeCampanhaJs(camp.obj_contratados);
    const atingVal = parseVolumeCampanhaJs(camp.totalizador_atingido);
    const pctObj = camp.pct_objetivo != null ? Number(camp.pct_objetivo) : (objVal > 0 ? Math.round((atingVal / objVal) * 100) : 0);
    document.getElementById('sidebarPctObj').textContent = pctObj + '%';
    document.getElementById('sidebarBarObj').style.width = Math.min(pctObj, 100) + '%';
    document.getElementById('sidebarAtingido').textContent = formatVolumeIntPtBR(atingVal);
    document.getElementById('sidebarObjContratados').textContent = '/ ' + (metaContratadaPreenchida(camp) ? formatVolumeIntPtBR(objVal) : '—');

    const prevVal = camp.custo_midia_previsto != null ? parseBrlMoedaJs(camp.custo_midia_previsto) : parseBrlMoedaJs(camp.valor_plataforma);
    const gastoVal = parseBrlMoedaJs(camp.totalizador_gasto);
    const pctInv = camp.pct_custo_midia != null ? Number(camp.pct_custo_midia) : (prevVal > 0 ? Math.round((gastoVal / prevVal) * 100) : 0);
    document.getElementById('sidebarPctInv').textContent = pctInv + '%';
    document.getElementById('sidebarBarInv').style.width = Math.min(pctInv, 100) + '%';
    document.getElementById('sidebarGasto').textContent = 'R$ ' + gastoVal.toLocaleString('pt-BR', {minimumFractionDigits: 2});
    document.getElementById('sidebarPrevisto').textContent = '/ R$ ' + prevVal.toLocaleString('pt-BR', {minimumFractionDigits: 2});

    loadSidebarChart(camp.id_campanha);

    document.getElementById('emailSubject').value = 'Relatório — ' + (camp.nome_campanha || 'Campanha');

    switchSidebarTab('detalhes');
    const panel = document.getElementById('sidebarPanel');
    const overlay = document.getElementById('sidebarOverlay');
    clearTimeout(sidebarCloseTimer);
    panel.hidden = false;
    overlay.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sidebar-open');
    window.requestAnimationFrame(function() {
      window.requestAnimationFrame(function() {
        panel.classList.add('open');
        overlay.classList.add('open');
      });
    });

    loadSidebarDiarios(camp.id_campanha);
  }

  function fecharSidebar() {
    const panel = document.getElementById('sidebarPanel');
    const overlay = document.getElementById('sidebarOverlay');
    panel.classList.remove('open');
    overlay.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('sidebar-open');
    clearTimeout(sidebarCloseTimer);
    sidebarCloseTimer = window.setTimeout(function() {
      if (!panel.classList.contains('open')) panel.hidden = true;
      if (!overlay.classList.contains('open')) overlay.hidden = true;
    }, 360);
    document.querySelectorAll('#campanhasTableBody tr.active').forEach(c => c.classList.remove('active'));
    currentSidebarCamp = null;
  }

  function switchSidebarTab(tabName) {
    document.querySelectorAll('.sidebar-tab-content').forEach(function (t) { t.classList.add('hidden'); });
    document.querySelectorAll('.camp-sidebar-tab').forEach(function (b) {
      b.classList.remove('cx-tab-active');
      b.setAttribute('aria-selected', 'false');
    });
    var panel = document.getElementById('tab-' + tabName);
    if (panel) panel.classList.remove('hidden');
    var activeBtn = document.querySelector('.camp-sidebar-tab[data-tab="' + tabName + '"]');
    if (activeBtn) {
      activeBtn.classList.add('cx-tab-active');
      activeBtn.setAttribute('aria-selected', 'true');
    }
  }

  function loadSidebarChart(campId) {
    if (sidebarChartInstance) { sidebarChartInstance.destroy(); sidebarChartInstance = null; }
    fetch(`/api/campanhas-pi/${campId}/diarios-chart`)
      .then(r => r.json())
      .then(data => {
        if (!data.labels || data.labels.length === 0) return;
        const ctx = document.getElementById('sidebarChart');
        sidebarChartInstance = new Chart(ctx, {
          type: 'line',
          data: {
            labels: data.labels,
            datasets: [
              { label: 'Atingido', data: data.atingido, borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.08)', fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2 },
              { label: 'Gasto', data: data.gasto, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.08)', fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2 }
            ]
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { font: { size: 10 }, boxWidth: 10, padding: 8 } } }, scales: { x: { ticks: { font: { size: 9 } }, grid: { display: false } }, y: { ticks: { font: { size: 9 } }, grid: { color: '#f1f5f9' }, beginAtZero: true } } }
        });
      });
  }

  // ==================== SIDEBAR DIÁRIOS ====================
  function loadSidebarDiarios(campId) {
    const lista = document.getElementById('sidebarDiariosLista');
    const empty = document.getElementById('sidebarDiariosEmpty');
    lista.innerHTML = '<div class="text-center py-4 text-gray-400"><i class="fas fa-spinner fa-spin"></i></div>';
    empty.classList.add('hidden');

    fetch(`/api/campanhas-pi/${campId}/diarios`)
      .then(r => r.json())
      .then(data => {
        if (!data.diarios || data.diarios.length === 0) {
          lista.innerHTML = '';
          empty.classList.remove('hidden');
          document.getElementById('sidebarDiariosCount').textContent = '0 diários';
          return;
        }
        empty.classList.add('hidden');
        document.getElementById('sidebarDiariosCount').textContent = data.diarios.length + ' diário(s)';
        lista.innerHTML = data.diarios.map(d => {
          const payload = encodeURIComponent(JSON.stringify({
            id: d.id,
            data_evento: d.data_evento || '',
            atingido: d.atingido != null ? String(d.atingido) : '',
            gasto: d.gasto != null ? String(d.gasto) : ''
          }));
          return `
          <div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 text-sm">
            <div class="flex items-center gap-3">
              <span class="text-gray-500 font-medium">${d.data_evento_fmt}</span>
              <span class="text-emerald-600 font-semibold">${d.atingido || '—'}</span>
              <span class="text-amber-600 font-semibold">${d.gasto || '—'}</span>
            </div>
            <div class="flex gap-1">
              <button type="button" data-action="edit-diario-sidebar" data-payload="${payload}" class="p-1 text-gray-400 hover:text-gray-700 rounded" title="Editar"><i class="fas fa-edit text-xs pointer-events-none"></i></button>
              <button type="button" data-action="del-diario-sidebar" data-id="${d.id}" class="p-1 text-red-400 hover:text-red-600 rounded" title="Excluir"><i class="fas fa-trash text-xs pointer-events-none"></i></button>
            </div>
          </div>`;
        }).join('');
      });
  }

  function toggleSidebarNovoDiario() {
    const form = document.getElementById('sidebarFormDiario');
    form.classList.toggle('hidden');
    if (!form.classList.contains('hidden')) {
      document.getElementById('sidebarDiarioData').value = new Date().toISOString().slice(0, 10);
      document.getElementById('sidebarDiarioAtingido').value = '';
      document.getElementById('sidebarDiarioGasto').value = '';
      document.getElementById('sidebarDiarioEditId').value = '';
    }
  }

  function editarSidebarDiario(id, dataEvento, atingido, gasto) {
    const form = document.getElementById('sidebarFormDiario');
    form.classList.remove('hidden');
    document.getElementById('sidebarDiarioData').value = dataEvento ? String(dataEvento).slice(0, 10) : '';
    document.getElementById('sidebarDiarioAtingido').value = atingido || '';
    document.getElementById('sidebarDiarioGasto').value = gasto || '';
    document.getElementById('sidebarDiarioEditId').value = id;
  }

  function salvarSidebarDiario() {
    if (!currentSidebarCamp) return;
    const editId = document.getElementById('sidebarDiarioEditId').value;
    const payload = {
      data_evento: document.getElementById('sidebarDiarioData').value,
      atingido: document.getElementById('sidebarDiarioAtingido').value || '0',
      gasto: document.getElementById('sidebarDiarioGasto').value || '0',
    };
    if (!payload.data_evento) { if (typeof showToast === 'function') showToast('Data é obrigatória.', 'error'); return; }
    let url, method;
    if (editId) { url = `/api/campanhas-pi/diarios/${editId}`; method = 'PUT'; }
    else { url = `/api/campanhas-pi/${currentSidebarCamp.id_campanha}/diarios`; method = 'POST'; }

    fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          if (typeof showToast === 'function') showToast(editId ? 'Diário atualizado!' : 'Diário criado!', 'success');
          document.getElementById('sidebarFormDiario').classList.add('hidden');
          loadSidebarDiarios(currentSidebarCamp.id_campanha);
          loadSidebarChart(currentSidebarCamp.id_campanha);
        } else {
          if (typeof showToast === 'function') showToast('Erro: ' + (data.error || ''), 'error');
        }
      });
  }

  function excluirSidebarDiario(id) {
    const nid = parseInt(id, 10);
    if (!nid || !currentSidebarCamp) return;
    const runDelete = () => {
      fetch(`/api/campanhas-pi/diarios/${nid}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            if (typeof showToast === 'function') showToast('Diário excluído!', 'success');
            loadSidebarDiarios(currentSidebarCamp.id_campanha);
            loadSidebarChart(currentSidebarCamp.id_campanha);
          } else if (typeof showToast === 'function') {
            showToast('Erro: ' + (data.error || ''), 'error');
          }
        })
        .catch(() => {
          if (typeof showToast === 'function') showToast('Erro de conexão.', 'error');
        });
    };
    requestCampConfirmation({
      title: 'Excluir diário',
      message: 'Este registro será removido definitivamente.',
      detail: 'Os totais da campanha serão recalculados após a exclusão.',
      theme: 'danger',
      confirmText: 'Excluir diário',
      onConfirm: runDelete
    });
  }

  // ==================== EMAIL ====================
  function selecionarTemplate(tipo) {
    selectedEmailTemplate = tipo;
    document.querySelectorAll('.email-template-card').forEach(c => c.classList.remove('selected'));
    document.querySelector(`.email-template-card[data-template="${tipo}"]`).classList.add('selected');

    if (currentSidebarCamp) {
      if (tipo === 'relatorio') {
        document.getElementById('emailSubject').value = 'Relatório Mensal — ' + (currentSidebarCamp.nome_campanha || '');
        document.getElementById('emailMessage').placeholder = 'Mensagem personalizada para acompanhar o relatório (opcional)...';
      } else if (tipo === 'atualizacao') {
        document.getElementById('emailSubject').value = 'Atualização de Campanha — ' + (currentSidebarCamp.nome_campanha || '');
        document.getElementById('emailMessage').placeholder = 'Descreva as atualizações da campanha...';
      } else {
        document.getElementById('emailSubject').value = '';
        document.getElementById('emailMessage').placeholder = 'Escreva sua mensagem...';
      }
    }
  }

  function enviarEmail() {
    if (!currentSidebarCamp) return;
    const btn = document.getElementById('btnEnviarEmail');
    const toEmail = document.getElementById('emailTo').value.trim();
    const toName = document.getElementById('emailToName').value.trim();
    const subject = document.getElementById('emailSubject').value.trim();
    const message = document.getElementById('emailMessage').value.trim();

    if (!toEmail || !subject) {
      if (typeof showToast === 'function') showToast('Email e assunto são obrigatórios.', 'error');
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1.5"></i> Enviando...';

    fetch('/api/campanhas-pi/enviar-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        to_email: toEmail,
        to_name: toName,
        subject: subject,
        message: message,
        template_type: selectedEmailTemplate,
        campanha_id: currentSidebarCamp.id_campanha,
      })
    })
    .then(r => r.json())
    .then(data => {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-paper-plane mr-1.5"></i> Enviar Email';
      const resultado = document.getElementById('emailResultado');
      resultado.classList.remove('hidden');
      if (data.success) {
        resultado.querySelector('div').className = 'p-3 rounded-lg text-sm bg-green-100 text-green-800';
        resultado.querySelector('div').innerHTML = '<i class="fas fa-check-circle mr-1"></i> Email enviado com sucesso!';
        if (typeof showToast === 'function') showToast('Email enviado!', 'success');
      } else {
        resultado.querySelector('div').className = 'p-3 rounded-lg text-sm bg-red-100 text-red-800';
        resultado.querySelector('div').innerHTML = '<i class="fas fa-times-circle mr-1"></i> Erro: ' + (data.error || 'Falha ao enviar');
      }
      setTimeout(() => resultado.classList.add('hidden'), 5000);
    })
    .catch(() => {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-paper-plane mr-1.5"></i> Enviar Email';
      if (typeof showToast === 'function') showToast('Erro de conexão.', 'error');
    });
  }

  // ==================== MODAL EDIÇÃO ====================
  function formatDateForInput(val) {
    if (!val) return '';
    const d = new Date(val);
    if (isNaN(d)) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function formatDatetimeForInput(val) {
    if (!val) return '';
    const d = new Date(val);
    if (isNaN(d)) return '';
    return d.toISOString().slice(0, 16);
  }

  function resetForm() {
    currentModalCampId = null;
    currentModalCampData = null;
    document.getElementById('modal_title').innerHTML = 'Operação: <span class="font-normal text-gray-200 ml-1">Adicionar Campanha</span>';
    document.getElementById('campanhaForm').action = CAMPANHA_NOVA_URL;
    document.getElementById('campanhaForm').reset();
    document.getElementById('campanha_timestamps').classList.add('hidden');
    document.getElementById('btnDiariosCampanha').classList.add('hidden');
    setCampFormStatus('', 'info');
  }

  let currentModalCampId = null;
  let currentModalCampData = null;

  function abrirModalEditar(c) {
    try {
      setCampFormStatus('', 'info');
      currentModalCampId = c.id_campanha;
      currentModalCampData = c;
      document.getElementById('modal_title').innerHTML = 'Operação: <span class="font-normal text-gray-200 ml-1">Editar Campanha</span>';
      document.getElementById('campanhaForm').action = campanhaEditarUrl(c.id_campanha);

      document.getElementById('nome_campanha').value = c.nome_campanha || '';
      document.getElementById('id_pi').value = c.id_pi || '';
      document.getElementById('id_cliente').value = c.id_cliente || '';
      document.getElementById('id_cliente_hidden').value = c.id_cliente || '';
      document.getElementById('id_objetivos_campanha').value = c.id_objetivos_campanha || '';
      document.getElementById('id_plataforma').value = c.id_plataforma || '';
      document.getElementById('id_status').value = c.id_status || '';
      document.getElementById('obj_contratados').value = rawParaFormatado(c.obj_contratados, 'numero');
      document.getElementById('mes_ref').value = formatDateForInput(c.mes_ref);
      document.getElementById('mes_ref_comp').value = c.mes_ref_comp || '';
      document.getElementById('link_dash').value = c.link_dash || '';
      document.getElementById('periodo_inicio').value = formatDateForInput(c.periodo_inicio);
      document.getElementById('periodo_fim').value = formatDateForInput(c.periodo_fim);
      document.getElementById('under').checked = !!c.under;
      document.getElementById('totalizador_atingido').value = rawParaFormatado(c.totalizador_atingido, 'numero');
      document.getElementById('totalizador_gasto').value = rawParaFormatado(c.totalizador_gasto, 'real');
      document.getElementById('valor_plataforma').value = rawParaFormatado(c.valor_plataforma, 'real');
      document.getElementById('custo_midia_orcado').value = rawParaFormatado(c.custo_midia_orcado, 'real');
      document.getElementById('id_centralx').value = c.id_centralx || '';

      ['perc_margem_cc','perc_tech_fee','perc_com_vendas','perc_pl_incentivos','perc_impostos'].forEach(function(k) {
        var el = document.getElementById(k);
        if (el) el.value = c[k] || '';
      });
      if (typeof recalcPercValCampanha === 'function') recalcPercValCampanha();

      vrPlatMax = parseRealVal(c.valor_plataformas_pi);
      calcDistribuicao();

      const tsBlock = document.getElementById('campanha_timestamps');
      document.getElementById('campanha_created_at').textContent = c.created_at || '—';
      document.getElementById('campanha_updated_at').textContent = c.updated_at || '—';
      tsBlock.classList.toggle('hidden', !c.created_at && !c.updated_at);

      const btnDiarios = document.getElementById('btnDiariosCampanha');
      btnDiarios.classList.remove('hidden');

      modal_campanha.showModal();
      var focusEl = document.getElementById('nome_campanha');
      if (focusEl) setTimeout(function () { focusEl.focus(); }, 50);
    } catch (error) {
      console.error('Erro em abrirModalEditar:', error);
      showToast('Erro ao abrir modal de edição: ' + error.message, 'error');
    }
  }

  function abrirDiariosDoCampanhaModal() {
    if (!currentModalCampId) return;
    modal_campanha.close();
    var d = currentModalCampData || {};
    abrirModalDiarios(currentModalCampId, d.codigo_pi || '', d.titulo_pi || '', d.nome_campanha || '');
  }

  function editarCampanhaSidebar() {
    if (currentSidebarCamp) abrirModalEditar(currentSidebarCamp);
  }

  function verCampanhasDoPi() {
    if (!currentSidebarCamp || !currentSidebarCamp.id_pi) return;
    window.location.href = LISTA_URL + '?id_pi=' + currentSidebarCamp.id_pi;
  }

  function excluirCampanhaSidebar() {
    if (!currentSidebarCamp) return;
    requestCampConfirmation({
      title: 'Excluir campanha',
      message: 'A campanha selecionada será removida definitivamente.',
      detail: 'Confira o nome da campanha antes de continuar. Esta ação não pode ser desfeita.',
      theme: 'danger',
      confirmText: 'Excluir campanha',
      onConfirm: () => {
        fetch(campanhaExcluirUrl(currentSidebarCamp.id_campanha), {
          method: 'POST',
          redirect: 'manual',
          headers: { 'X-Campanhas-Retorno': 'lista' }
        }).then(() => {
          if (typeof showToast === 'function') showToast('Campanha excluída!', 'success');
          fecharSidebar();
          setTimeout(() => location.reload(), 600);
        }).catch(() => {
          if (typeof showToast === 'function') showToast('Erro ao excluir.', 'error');
        });
      }
    });
  }

  document.getElementById('modal_campanha').addEventListener('close', resetForm);

  document.getElementById('campanhaForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const form = this;
    const btn = document.getElementById('btnSalvarCampanha');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Salvando...';
    setCampFormStatus('Salvando alterações da campanha…', 'info');

    const formData = new FormData(form);
    formData.set('campanhas_retorno', 'lista');

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-Campanhas-Retorno': 'lista'
      },
      redirect: 'manual'
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        setCampFormStatus(data.message || 'Campanha salva com sucesso.', 'success');
        if (typeof showToast === 'function') showToast(data.message || 'Campanha salva com sucesso!', 'success');
        modal_campanha.close();
        setTimeout(() => location.reload(), 600);
      } else {
        setCampFormStatus(data.error || 'Não foi possível salvar a campanha.', 'error');
        if (typeof showToast === 'function') showToast(data.error || 'Erro ao salvar.', 'error');
        btn.disabled = false;
        btn.innerHTML = 'Salvar campanha';
      }
    })
    .catch(() => {
      setCampFormStatus('Não foi possível conectar ao servidor. Tente novamente.', 'error');
      if (typeof showToast === 'function') showToast('Erro ao salvar campanha.', 'error');
      btn.disabled = false;
      btn.innerHTML = 'Salvar campanha';
    });
  });

  // ==================== MODAL DIÁRIOS ====================
  let currentDiarioCampId = null;

  function abrirModalDiarios(campId, codPi, tituloPi, nomeCamp) {
    currentDiarioCampId = campId;
    document.getElementById('modal_diarios_codpi').textContent = codPi || '-';
    document.getElementById('modal_diarios_titulo').textContent = tituloPi || '-';
    document.getElementById('modal_diarios_campanha').textContent = nomeCamp || '-';
    document.getElementById('diarios_loading').style.display = '';
    document.getElementById('diarios_content').style.display = 'none';
    document.getElementById('form_novo_diario').style.display = 'none';
    document.getElementById('diario_edit_id').value = '';
    modal_diarios.showModal();
    carregarDiarios(campId);
  }

  function carregarDiarios(campId) {
    fetch(`/api/campanhas-pi/${campId}/diarios`)
      .then(r => r.json())
      .then(data => {
        document.getElementById('diarios_loading').style.display = 'none';
        document.getElementById('diarios_content').style.display = '';

        if (data.campanha) {
          document.getElementById('modal_diarios_title').textContent =
            'Diários — ' + (data.campanha.nome_campanha || 'Campanha');
        }

        const tbody = document.getElementById('diarios_tbody');
        const emptyMsg = document.getElementById('diarios_empty');
        tbody.innerHTML = '';

        if (!data.diarios || data.diarios.length === 0) {
          emptyMsg.style.display = '';
          document.getElementById('diarios_count').textContent = '0 diários';
          return;
        }

        emptyMsg.style.display = 'none';
        document.getElementById('diarios_count').textContent = data.diarios.length + ' diário(s)';

        data.diarios.forEach(d => {
          const payload = encodeURIComponent(JSON.stringify({
            id: d.id,
            data_evento: d.data_evento || '',
            atingido: d.atingido != null ? String(d.atingido) : '',
            gasto: d.gasto != null ? String(d.gasto) : ''
          }));
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-gray-50';
          tr.innerHTML = `
            <td class="py-2 px-3 text-gray-700">${d.data_evento_fmt}</td>
            <td class="py-2 px-3 text-right text-gray-700">${d.atingido || '—'}</td>
            <td class="py-2 px-3 text-right text-gray-700">${d.gasto || '—'}</td>
            <td class="py-2 px-3 text-center">
              <div class="flex items-center justify-center gap-1">
                <button type="button" data-action="edit-diario-modal" data-payload="${payload}"
                        class="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded" title="Editar">
                  <i class="fas fa-edit text-xs pointer-events-none"></i>
                </button>
                <button type="button" data-action="del-diario-modal" data-id="${d.id}"
                        class="p-1 text-red-500 hover:text-red-800 hover:bg-red-50 rounded" title="Excluir">
                  <i class="fas fa-trash text-xs pointer-events-none"></i>
                </button>
              </div>
            </td>`;
          tbody.appendChild(tr);
        });
      })
      .catch(() => {
        document.getElementById('diarios_loading').style.display = 'none';
        document.getElementById('diarios_content').style.display = '';
        document.getElementById('diarios_empty').style.display = '';
        document.getElementById('diarios_empty').textContent = 'Erro ao carregar diários.';
      });
  }

  function toggleNovoDiario() {
    const form = document.getElementById('form_novo_diario');
    const isVisible = form.style.display !== 'none';
    form.style.display = isVisible ? 'none' : '';
    if (!isVisible) {
      document.getElementById('diario_data').value = new Date().toISOString().slice(0, 10);
      document.getElementById('diario_atingido').value = '';
      document.getElementById('diario_gasto').value = '';
      document.getElementById('diario_edit_id').value = '';
      document.getElementById('btnSalvarDiario').textContent = 'Salvar';
    }
  }

  function editarDiario(id, dataEvento, atingido, gasto) {
    document.getElementById('form_novo_diario').style.display = '';
    document.getElementById('diario_data').value = dataEvento ? String(dataEvento).slice(0, 10) : '';
    document.getElementById('diario_atingido').value = atingido || '';
    document.getElementById('diario_gasto').value = gasto || '';
    document.getElementById('diario_edit_id').value = id;
    document.getElementById('btnSalvarDiario').textContent = 'Atualizar';
  }

  function salvarDiario() {
    const editId = document.getElementById('diario_edit_id').value;
    const payload = {
      data_evento: document.getElementById('diario_data').value,
      atingido: document.getElementById('diario_atingido').value || '0',
      gasto: document.getElementById('diario_gasto').value || '0',
    };

    if (!payload.data_evento) {
      if (typeof showToast === 'function') showToast('Data é obrigatória.', 'error');
      return;
    }

    let url, method;
    if (editId) { url = `/api/campanhas-pi/diarios/${editId}`; method = 'PUT'; }
    else { url = `/api/campanhas-pi/${currentDiarioCampId}/diarios`; method = 'POST'; }

    const btn = document.getElementById('btnSalvarDiario');
    btn.disabled = true;

    fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(r => r.json())
    .then(data => {
      btn.disabled = false;
      if (data.success) {
        if (typeof showToast === 'function') showToast(editId ? 'Diário atualizado!' : 'Diário criado!', 'success');
        document.getElementById('form_novo_diario').style.display = 'none';
        carregarDiarios(currentDiarioCampId);
      } else {
        if (typeof showToast === 'function') showToast('Erro: ' + (data.error || ''), 'error');
      }
    })
    .catch(() => {
      btn.disabled = false;
      if (typeof showToast === 'function') showToast('Erro de conexão.', 'error');
    });
  }

  function excluirDiario(id) {
    const nid = parseInt(id, 10);
    if (!nid) {
      if (typeof showToast === 'function') showToast('Diário inválido.', 'error');
      return;
    }
    const runDelete = () => {
      fetch(`/api/campanhas-pi/diarios/${nid}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            if (typeof showToast === 'function') showToast('Diário excluído!', 'success');
            carregarDiarios(currentDiarioCampId);
          } else {
            if (typeof showToast === 'function') showToast('Erro: ' + (data.error || ''), 'error');
          }
        })
        .catch(() => {
          if (typeof showToast === 'function') showToast('Erro de conexão.', 'error');
        });
    };
    requestCampConfirmation({
      title: 'Excluir diário',
      message: 'Este registro será removido definitivamente.',
      detail: 'Os totais da campanha serão recalculados após a exclusão.',
      theme: 'danger',
      confirmText: 'Excluir diário',
      onConfirm: runDelete
    });
  }

  (function initDiarioListaClickDelegation() {
    const modalTbody = document.getElementById('diarios_tbody');
    if (modalTbody && !modalTbody.dataset.diarioClickBound) {
      modalTbody.dataset.diarioClickBound = '1';
      modalTbody.addEventListener('click', function (e) {
        const editBtn = e.target.closest('[data-action="edit-diario-modal"]');
        if (editBtn) {
          e.preventDefault();
          try {
            const o = JSON.parse(decodeURIComponent(editBtn.getAttribute('data-payload')));
            editarDiario(o.id, o.data_evento, o.atingido, o.gasto);
          } catch (err) {
            console.error(err);
            if (typeof showToast === 'function') showToast('Erro ao abrir edição.', 'error');
          }
          return;
        }
        const delBtn = e.target.closest('[data-action="del-diario-modal"]');
        if (delBtn) {
          e.preventDefault();
          excluirDiario(delBtn.getAttribute('data-id'));
        }
      });
    }
    const sidebarLista = document.getElementById('sidebarDiariosLista');
    if (sidebarLista && !sidebarLista.dataset.diarioClickBound) {
      sidebarLista.dataset.diarioClickBound = '1';
      sidebarLista.addEventListener('click', function (e) {
        const editBtn = e.target.closest('[data-action="edit-diario-sidebar"]');
        if (editBtn) {
          e.preventDefault();
          try {
            const o = JSON.parse(decodeURIComponent(editBtn.getAttribute('data-payload')));
            editarSidebarDiario(o.id, o.data_evento, o.atingido, o.gasto);
          } catch (err) {
            console.error(err);
            if (typeof showToast === 'function') showToast('Erro ao abrir edição.', 'error');
          }
          return;
        }
        const delBtn = e.target.closest('[data-action="del-diario-sidebar"]');
        if (delBtn) {
          e.preventDefault();
          excluirSidebarDiario(parseInt(delBtn.getAttribute('data-id'), 10));
        }
      });
    }
  })();

  // ==================== DIÁRIOS EM MASSA ====================
  (function() {
    const hoje = new Date().toISOString().slice(0, 10);
    document.querySelectorAll('#tabelaDiariosMassa .dm-data').forEach(el => { el.value = hoje; });
    document.querySelectorAll('#tabelaDiariosMassa [data-mask="numero"]').forEach(aplicarMascaraNumero);
    document.querySelectorAll('#tabelaDiariosMassa [data-mask="real"]').forEach(aplicarMascaraReal);
  })();

  function coletarDiariosMassaValidos() {
    const rows = document.querySelectorAll('#tabelaDiariosMassa .diario-massa-row');
    const validos = [];
    rows.forEach(row => {
      const data = row.querySelector('.dm-data').value.trim();
      const atingido = row.querySelector('.dm-atingido').value.trim();
      const gasto = row.querySelector('.dm-gasto').value.trim();
      if (data && atingido && gasto) {
        validos.push({
          id_campanha: row.dataset.campanhaId,
          id_pi: row.dataset.idPi,
          data_evento: data,
          atingido: atingido,
          gasto: gasto,
          row: row
        });
      }
    });
    return validos;
  }

  function confirmarAtualizarDiariosMassa() {
    const validos = coletarDiariosMassaValidos();
    if (validos.length === 0) {
      showToast('Nenhuma linha com os 3 campos preenchidos (data, atingido, gasto).', 'warning');
      return;
    }
    requestCampConfirmation({
      title: 'Adicionar diários',
      message: `<strong>${validos.length}</strong> diário${validos.length > 1 ? 's' : ''} ser${validos.length > 1 ? 'ão adicionados' : 'á adicionado'}.`,
      detail: '<span class="text-gray-500">Apenas linhas com data, valor atingido e valor gasto preenchidos serão processadas.</span>',
      theme: 'info',
      confirmText: 'Adicionar diários',
      onConfirm: () => enviarDiariosMassa(validos)
    });
  }

  async function enviarDiariosMassa(items) {
    const button = document.getElementById('btnAtualizarDiariosMassa');
    if (button) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
    }
    let ok = 0, erros = 0;
    for (let index = 0; index < items.length; index++) {
      const item = items[index];
      const progressMessage = `Atualizando ${index + 1} de ${items.length}`;
      if (button) button.innerHTML = `<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> ${progressMessage}`;
      const status = document.getElementById('campActionStatus');
      if (status) status.textContent = progressMessage;
      try {
        const resp = await fetch(`/api/campanhas-pi/${item.id_campanha}/diarios`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_evento: item.data_evento,
            atingido: item.atingido,
            gasto: item.gasto
          })
        });
        const data = await resp.json();
        if (resp.ok && data.success) {
          ok++;
          item.row.dataset.saveState = 'success';
        } else {
          erros++;
          item.row.dataset.saveState = 'error';
        }
      } catch (e) {
        erros++;
        item.row.dataset.saveState = 'error';
      }
    }
    if (button) {
      button.removeAttribute('aria-busy');
      button.innerHTML = '<i class="fas fa-layer-group" aria-hidden="true"></i> Atualizar todos';
    }
    if (erros === 0) {
      notifyCampAction(`${ok} diário${ok > 1 ? 's adicionados' : ' adicionado'} com sucesso.`, 'success');
    } else {
      notifyCampAction(`${ok} atualizado${ok !== 1 ? 's' : ''}; ${erros} com erro. Revise as linhas marcadas.`, 'warning');
    }
    if (erros === 0) setTimeout(() => location.reload(), 1200);
    else if (button) button.disabled = false;
  }

  // ==================== KEYBOARD ====================
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') fecharSidebar();
  });
  window.aplicarFiltros = aplicarFiltros;
  window.fecharSidebar = fecharSidebar;
  window.switchSidebarTab = switchSidebarTab;
  window.abrirModalEditar = abrirModalEditar;
  window.abrirModalDiarios = abrirModalDiarios;
  window.toggleFlagSort = toggleFlagSort;
  window.selecionarTemplate = selecionarTemplate;
  window.enviarEmail = enviarEmail;
  window.editarCampanhaSidebar = editarCampanhaSidebar;
  window.excluirCampanhaSidebar = excluirCampanhaSidebar;
  window.verCampanhasDoPi = verCampanhasDoPi;
  window.toggleSidebarNovoDiario = toggleSidebarNovoDiario;
  window.salvarSidebarDiario = salvarSidebarDiario;
  window.abrirDiariosDoCampanhaModal = abrirDiariosDoCampanhaModal;
  window.toggleNovoDiario = toggleNovoDiario;
  window.salvarDiario = salvarDiario;
  window.confirmarAtualizarDiariosMassa = confirmarAtualizarDiariosMassa;
})();
