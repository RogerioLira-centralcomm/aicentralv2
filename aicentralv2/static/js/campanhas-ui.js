/**
 * Campanhas UI — utilitários compartilhados (PI list + Acompanhamento)
 */
(function (global) {
  'use strict';

  const CAMP_FLAG_STORAGE_KEY = 'cc_camp_flag_v1';
  const CAMP_FLAG_ORDER = { critico: 0, atencao: 1, ok: 2, none: 3 };

  const PLATFORM_ICON_MAP = {
    byId: {},
    byPattern: [
      { re: /spotify/i, icon: 'fa-brands fa-spotify', bg: '#1ed76022', color: '#1db954' },
      { re: /amazon\s*dsp|amazon\s*ads/i, icon: 'fa-brands fa-amazon', bg: '#ff990022', color: '#ff9900' },
      { re: /dv\s*360|display\s*&?\s*video|google\s*ads/i, icon: 'fa-brands fa-google', bg: '#4285f422', color: '#4285f4' },
      { re: /meta|facebook|instagram/i, icon: 'fa-brands fa-meta', bg: '#0668e122', color: '#0668e1' },
      { re: /tiktok/i, icon: 'fa-brands fa-tiktok', bg: '#01010112', color: '#010101' },
      { re: /linkedin/i, icon: 'fa-brands fa-linkedin', bg: '#0a66c222', color: '#0a66c2' },
      { re: /twitter|x\s*ads/i, icon: 'fa-brands fa-x-twitter', bg: '#00000012', color: '#14171a' },
      { re: /youtube/i, icon: 'fa-brands fa-youtube', bg: '#ff000022', color: '#ff0000' },
      { re: /pinterest/i, icon: 'fa-brands fa-pinterest', bg: '#e6002322', color: '#e60023' },
      { re: /program[aá]tica|dsp/i, icon: 'fa-solid fa-chart-network', bg: '#6366f122', color: '#6366f1' },
    ],
    fallback: { icon: 'fa-solid fa-bullhorn', bg: '#f1f5f9', color: '#64748b' }
  };

  function calcProgressTier(pct) {
    const p = Number(pct) || 0;
    if (p <= 0) return 'empty';
    if (p < 34) return 'low';
    if (p < 70) return 'mid';
    if (p < 100) return 'high';
    if (p === 100) return 'complete';
    return 'over';
  }

  function resolvePlatformIcon(idPlataforma, nomePlataforma) {
    const idKey = idPlataforma != null && idPlataforma !== '' ? String(idPlataforma) : '';
    if (idKey && PLATFORM_ICON_MAP.byId[idKey]) return PLATFORM_ICON_MAP.byId[idKey];
    const nome = (nomePlataforma || '').trim();
    for (const entry of PLATFORM_ICON_MAP.byPattern) {
      if (nome && entry.re.test(nome)) return entry;
    }
    return PLATFORM_ICON_MAP.fallback;
  }

  function applyPlatformIcons(root) {
    const scope = (root && root.querySelectorAll) ? root : document;
    scope.querySelectorAll('tr[data-plataforma-id], tr[data-plataforma-nome]').forEach(function (row) {
      const wrap = row.querySelector('[data-platform-badge] .platform-icon-wrap')
        || row.querySelector('.platform-icon-wrap');
      const iconEl = row.querySelector('.platform-icon');
      if (!wrap || !iconEl) return;
      const id = row.dataset.plataformaId || row.getAttribute('data-plataforma-id');
      const nome = row.dataset.plataformaNome || row.getAttribute('data-plataforma-nome');
      const cfg = resolvePlatformIcon(id, nome);
      iconEl.className = 'platform-icon ' + cfg.icon;
      wrap.style.background = cfg.bg;
      wrap.style.color = cfg.color;
    });
  }

  function buildProgressHtml(pct, opts) {
    opts = opts || {};
    const tier = calcProgressTier(pct);
    const width = pct > 0 ? Math.min(pct, 100) : 0;
    const sm = opts.small ? ' camp-progress-sm' : '';
    const showPct = opts.showPct !== false;
    let html = '<div class="flex items-center justify-end gap-1.5">';
    html += '<div class="camp-progress' + sm + '" data-tier="' + tier + '" title="Progresso: ' + pct + '%">';
    html += '<div class="camp-progress-fill" style="width:' + width + '%"></div></div>';
    if (showPct) {
      html += '<span class="camp-progress-pct" data-tier="' + tier + '">' + pct + '%</span>';
    }
    html += '</div>';
    return html;
  }

  function parseVolume(value) {
    if (value == null || value === '') return 0;
    if (typeof value === 'number') return value;
    const s = String(value).trim();
    if (!s) return 0;
    if (s.indexOf(',') !== -1) {
      return parseFloat(s.replace(/\./g, '').replace(',', '.')) || 0;
    }
    return parseFloat(s.replace(/[^\d.-]/g, '')) || 0;
  }

  function loadCampFlags() {
    try {
      const raw = localStorage.getItem(CAMP_FLAG_STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
  }

  function getCampFlag(campanhaId) {
    const flags = loadCampFlags();
    const v = flags[String(campanhaId)];
    return (v === 'critico' || v === 'atencao' || v === 'ok') ? v : 'none';
  }

  function aggregateFlagsForCampanhas(campanhaIds) {
    const counts = { ok: 0, atencao: 0, critico: 0, none: 0 };
    (campanhaIds || []).forEach(function (id) {
      const f = getCampFlag(id);
      counts[f] = (counts[f] || 0) + 1;
    });
    const parts = [];
    if (counts.ok) parts.push(counts.ok + ' ok');
    if (counts.atencao) parts.push(counts.atencao + ' atenção');
    if (counts.critico) parts.push(counts.critico + ' crítico');
    return parts.length ? parts.join(' · ') : '';
  }

  function cellEmptyHtml(variant, label) {
    const v = variant || 'empty-na';
    const text = label || (v === 'empty-pending' ? 'Pendente' : '—');
    if (v === 'empty-pending') {
      return '<span class="cx-cell-empty empty-pending" title="Ainda não preenchido">' +
        '<i class="fa-regular fa-circle-dashed text-[10px]"></i>' + text + '</span>';
    }
    if (v === 'empty-zero') {
      return '<span class="cx-cell-empty empty-zero" title="Valor zero">' + text + '</span>';
    }
    return '<span class="cx-cell-empty empty-na" title="Não se aplica ou não informado">' + text + '</span>';
  }

  function execInitials(nome) {
    const parts = (nome || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    const first = parts[0][0] || '';
    const last = parts.length > 1 ? (parts[parts.length - 1][0] || '') : '';
    return (first + last).toUpperCase() || '?';
  }

  function getPiStickyTop() {
    const bar = document.querySelector('.pi-filter-sticky');
    return bar ? bar.offsetHeight : 48;
  }

  function updatePiStickyTop() {
    const top = getPiStickyTop() + 'px';
    document.querySelectorAll('.pi-row-sticky-expanded').forEach(function (el) {
      el.style.top = top;
    });
  }

  global.CampanhasUI = {
    CAMP_FLAG_STORAGE_KEY: CAMP_FLAG_STORAGE_KEY,
    CAMP_FLAG_ORDER: CAMP_FLAG_ORDER,
    PLATFORM_ICON_MAP: PLATFORM_ICON_MAP,
    calcProgressTier: calcProgressTier,
    resolvePlatformIcon: resolvePlatformIcon,
    applyPlatformIcons: applyPlatformIcons,
    buildProgressHtml: buildProgressHtml,
    parseVolume: parseVolume,
    loadCampFlags: loadCampFlags,
    getCampFlag: getCampFlag,
    aggregateFlagsForCampanhas: aggregateFlagsForCampanhas,
    cellEmptyHtml: cellEmptyHtml,
    execInitials: execInitials,
    getPiStickyTop: getPiStickyTop,
    updatePiStickyTop: updatePiStickyTop,
  };

  /* Backward compat for campanhas_pi_lista inline refs */
  global.calcProgressTier = calcProgressTier;
  global.resolvePlatformIcon = resolvePlatformIcon;
  global.applyPlatformIcons = function (root) { applyPlatformIcons(root || document); };
  global.getCampFlag = getCampFlag;
  global.loadCampFlags = loadCampFlags;
})(typeof window !== 'undefined' ? window : this);
