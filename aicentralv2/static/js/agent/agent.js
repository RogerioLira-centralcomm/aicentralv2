(function () {
  'use strict';

  var dock = document.getElementById('cx-agent-dock');
  var trigger = document.getElementById('cx-agent-trigger');
  if (!dock || !trigger) return;

  var PREFS_KEY = 'centralx_agent_prefs';
  var defaultPrefs = { saveHistory: true, usePageContext: true, notifications: true };

  var state = {
    bootstrapped: false,
    csrf: '',
    conversationId: sessionStorage.getItem('centralx_agent_conversation_id') || '',
    context: readBodyContext(),
    contextSource: 'page',
    explorerStack: [],
    explorerView: null,
    lastQuery: { text: '', entityId: '', message: '' },
    suggestions: [],
    insights: { entity: null, alerts: [], prompts: [] },
    attachments: [],
    conversations: [],
    historyFilter: 'all',
    prefs: loadPrefs(),
    controller: null,
    lastFocus: null,
    capabilities: [],
    commercialController: null,
    commercialTimer: null,
    loadingTimer: null,
    record: null,
    recordKey: '',
    activeView: 'conversation',
    contextWallOpen: false,
    contextPersistTimer: null,
    currentUser: { id: '', name: '', photo_url: '' }
  };

  var els = {
    status: document.getElementById('cx-agent-status'),
    entity: document.getElementById('cx-agent-entity'),
    contextLabel: document.getElementById('cx-agent-context-label'),
    contextType: document.getElementById('cx-agent-context-type'),
    messages: document.getElementById('cx-agent-messages'),
    prompts: document.getElementById('cx-agent-quick-prompts'),
    actions: document.getElementById('cx-agent-actions'),
    suggestions: document.getElementById('cx-agent-suggestions'),
    history: document.getElementById('cx-agent-history'),
    historyQuery: document.getElementById('cx-agent-history-query'),
    historyFilter: document.getElementById('cx-agent-history-filter'),
    input: document.getElementById('cx-agent-input'),
    composer: document.getElementById('cx-agent-composer'),
    send: document.getElementById('cx-agent-send'),
    attach: document.getElementById('cx-agent-attach'),
    fileInput: document.getElementById('cx-agent-file-input'),
    attachments: document.getElementById('cx-agent-attachments'),
    feedback: document.getElementById('cx-agent-composer-feedback'),
    characterCount: document.getElementById('cx-agent-character-count'),
    modelLabel: document.getElementById('cx-agent-model-label'),
    modelSelect: document.getElementById('cx-agent-model-select'),
    userName: document.getElementById('cx-agent-user-name'),
    close: document.getElementById('cx-agent-close'),
    minimize: document.getElementById('cx-agent-minimize'),
    settings: document.getElementById('cx-agent-settings'),
    settingsPanel: document.getElementById('cx-agent-settings-panel'),
    settingsBack: document.getElementById('cx-agent-settings-back'),
    workspace: document.getElementById('cx-agent-workspace'),
    newConversation: document.getElementById('cx-agent-new-conversation'),
    extract: document.getElementById('cx-agent-extract'),
    extractName: document.getElementById('cx-agent-extract-name'),
    extractSize: document.getElementById('cx-agent-extract-size'),
    prefHistory: document.getElementById('cx-agent-pref-history'),
    prefContext: document.getElementById('cx-agent-pref-context'),
    prefNotify: document.getElementById('cx-agent-pref-notify'),
    commercialQuery: document.getElementById('cx-agent-commercial-query'),
    commercialScope: document.getElementById('cx-agent-commercial-scope'),
    scopeTrigger: document.getElementById('cx-agent-scope-trigger'),
    scopeSheet: document.getElementById('cx-agent-scope-sheet'),
    commercialResults: document.getElementById('cx-agent-commercial-results'),
    record: document.getElementById('cx-agent-record'),
    recordTitle: document.getElementById('cx-agent-record-title'),
    recordOpen: document.getElementById('cx-agent-record-open'),
    recordClose: document.getElementById('cx-agent-record-close'),
    recordBody: document.getElementById('cx-agent-record-body'),
    commercialSearch: document.getElementById('cx-agent-commercial-search'),
    searchToggle: document.getElementById('cx-agent-search-toggle'),
    searchClose: document.getElementById('cx-agent-search-close'),
    moreToggle: document.getElementById('cx-agent-more-toggle'),
    moreMenu: document.getElementById('cx-agent-more-menu'),
    historyOpen: document.getElementById('cx-agent-history-open'),
    historyBack: document.getElementById('cx-agent-history-back'),
    composerSuggestions: document.getElementById('cx-agent-composer-suggestions'),
    consulting: document.getElementById('cx-agent-consulting'),
    consultingName: document.getElementById('cx-agent-consulting-name'),
    consultingType: document.getElementById('cx-agent-consulting-type'),
    breadcrumb: document.getElementById('cx-agent-breadcrumb'),
    recordMore: document.getElementById('cx-agent-record-more'),
    recordMoreMenu: document.getElementById('cx-agent-record-more-menu'),
    recordCopyLink: document.getElementById('cx-agent-record-copy-link'),
    recordSwitch: document.getElementById('cx-agent-record-switch'),
    recordMoreExtra: document.getElementById('cx-agent-record-more-extra'),
    mediaDialog: document.getElementById('cx-agent-media-dialog'),
    mediaTitle: document.getElementById('cx-agent-media-title'),
    mediaTabs: document.getElementById('cx-agent-media-tabs'),
    mediaContent: document.getElementById('cx-agent-media-content'),
    mediaCopy: document.getElementById('cx-agent-media-copy'),
    mediaOpen: document.getElementById('cx-agent-media-open'),
    mediaDownload: document.getElementById('cx-agent-media-download'),
    clearConversation: document.getElementById('cx-agent-clear-conversation')
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char];
    });
  }

  function loadPrefs() {
    try {
      var raw = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
      return Object.assign({}, defaultPrefs, raw);
    } catch (error) {
      return Object.assign({}, defaultPrefs);
    }
  }

  function savePrefs() {
    localStorage.setItem(PREFS_KEY, JSON.stringify(state.prefs));
  }

  function readBodyContext() {
    var data = document.body.dataset;
    return {
      module: data.cxModule || '',
      screen: data.cxScreen || '',
      entity_type: data.cxEntityType || '',
      entity_id: data.cxEntityId || '',
      entity_label: data.cxEntityLabel || '',
      entity_subtype: data.cxEntitySubtype || ''
    };
  }

  function outgoingContext() {
    var ctx = Object.assign({
      module: '', screen: '', entity_type: '', entity_id: '',
      entity_label: '', entity_subtype: ''
    }, state.context || {});
    if (!state.prefs.usePageContext && state.contextSource !== 'agent') {
      ctx.entity_type = '';
      ctx.entity_id = '';
      ctx.entity_label = '';
      ctx.entity_subtype = '';
    }
    return ctx;
  }

  function contextQuery(context) {
    var params = new URLSearchParams();
    Object.keys(context || {}).forEach(function (key) {
      if (context[key]) params.set(key, context[key]);
    });
    if (state.conversationId) params.set('conversation_id', state.conversationId);
    return params.toString();
  }

  function api(url, options) {
    options = options || {};
    options.headers = Object.assign({ 'Accept': 'application/json' }, options.headers || {});
    if (options.body) {
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-Agent-CSRF-Token'] = state.csrf;
    }
    return fetch(url, options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (payload) {
        if (!response.ok || payload.success === false) {
          var message = payload.error;
          if (!message) {
            if (response.status === 401) message = 'Sessão expirada.';
            else if (response.status === 403) message = 'Acesso restrito à equipe CentralComm.';
            else message = 'Não foi possível concluir a operação. HTTP ' + response.status;
          }
          var error = new Error(message);
          error.status = response.status;
          error.requestId = payload.request_id || '';
          throw error;
        }
        return payload;
      });
    });
  }

  function setStatus(text, online) {
    var isOnline = online !== false && text !== 'Indisponível';
    els.status.classList.toggle('is-offline', !isOnline);
    els.status.innerHTML = '<i class="cx-agent-status-dot" aria-hidden="true"></i> ' + (isOnline ? (text || 'Online') : text);
  }

  function entityTypeLabel(type, subtype) {
    var normalized = String(type || '').toLowerCase();
    var kind = String(subtype || '').toLowerCase();
    if (normalized === 'agencia' || normalized === 'agency' || kind === 'agencia') return 'Agência';
    if (normalized === 'cliente' || normalized === 'client') return 'Cliente final';
    var map = {
      cliente: 'Cliente final', client: 'Cliente final',
      contato: 'Contato', contact: 'Contato',
      cotacao: 'Cotação', quote: 'Cotação',
      pi: 'PI',
      campanha: 'Campanha', campaign: 'Campanha'
    };
    return map[normalized] || 'Registro';
  }

  function clientContext() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if (['cliente', 'client', 'agencia', 'agency'].indexOf(type) >= 0 && ctx.entity_id) return ctx;
    return null;
  }

  function commercialContext() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    return ['cliente', 'client', 'agencia', 'agency', 'contato', 'contact', 'cotacao', 'quote', 'pi', 'campanha', 'campaign'].indexOf(type) >= 0 && ctx.entity_id
      ? ctx : null;
  }

  function persistConversationContext() {
    window.clearTimeout(state.contextPersistTimer);
    if (!state.bootstrapped || !state.conversationId) return;
    state.contextPersistTimer = window.setTimeout(function () {
      api('/api/agent/conversations/' + encodeURIComponent(state.conversationId) + '/context', {
        method: 'PATCH',
        body: JSON.stringify({ context: outgoingContext() })
      }).catch(function () {
        showComposerFeedback('O contexto continua disponível nesta tela, mas não pôde ser salvo na conversa.', true);
      });
    }, 240);
  }

  function updateContext() {
    var ctx = outgoingContext();
    var hasEntity = Boolean(ctx.entity_id);
    var typeLabel = entityTypeLabel(ctx.entity_type, ctx.entity_subtype);
    if (els.entity) {
      els.contextLabel.textContent = hasEntity ? ctx.entity_label : 'Nenhum registro na tela';
      els.contextType.textContent = hasEntity ? typeLabel : 'Busque ou peça detalhes ao agente';
      els.entity.classList.toggle('is-empty', !hasEntity);
      var icon = els.entity.querySelector('.cx-agent-entity-icon i');
      if (icon) {
        icon.className = 'fa-regular ' + (
          String(ctx.entity_type || '').toLowerCase() === 'contato' ? 'fa-user' :
          String(ctx.entity_type || '').toLowerCase() === 'campanha' ? 'fa-bullhorn' :
          ['cotacao', 'pi'].indexOf(String(ctx.entity_type || '').toLowerCase()) >= 0 ? 'fa-file-lines' : 'fa-building'
        );
      }
    }
    if (els.consulting) {
      els.consulting.hidden = !hasEntity;
      if (els.consultingName) els.consultingName.textContent = ctx.entity_label || '';
      if (els.consultingType) els.consultingType.textContent = hasEntity ? typeLabel : '';
    }
    if (els.input) {
      els.input.placeholder = hasEntity
        ? ('Pergunte sobre ' + (ctx.entity_label || typeLabel) + '...')
        : 'Pergunte ao CentralX...';
    }
    renderActions();
    if (state.contextWallOpen) loadCommercialRecord();
    persistConversationContext();
  }

  function openEntity() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if (ctx.entity_id && commercialContext()) {
      openContextWall();
      return;
    }
    switchTab('chat');
    els.input.focus();
  }

  function switchWorkspaceView(name) {
    if (name === 'record') {
      openContextWall();
      return;
    }
    closeContextWall();
  }

  function syncWorkspaceView(name) {
    state.activeView = name === 'record' ? 'record' : 'conversation';
    els.workspace.dataset.activeView = state.activeView;
    dock.querySelectorAll('[data-agent-view]').forEach(function (button) {
      var active = button.dataset.agentView === state.activeView;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
  }

  function openContextWall(context) {
    if (context) setAgentContext(context, true);
    if (!commercialContext()) {
      switchTab('chat');
      els.input.focus();
      return;
    }
    state.contextWallOpen = true;
    dock.dataset.contextWall = 'open';
    els.record.setAttribute('aria-hidden', 'false');
    syncWorkspaceView('record');
    loadCommercialRecord();
  }

  function closeContextWall() {
    state.contextWallOpen = false;
    dock.dataset.contextWall = 'closed';
    els.record.setAttribute('aria-hidden', 'true');
    syncWorkspaceView('conversation');
  }

  function clearSelectedContext() {
    state.explorerStack = [];
    state.explorerView = null;
    state.contextSource = 'page';
    setAgentContext({
      entity_type: '',
      entity_id: '',
      entity_label: '',
      entity_subtype: ''
    }, true, 'page');
    closeContextWall();
    setSearchOpen(true);
    if (els.commercialQuery) els.commercialQuery.focus();
  }

  function setRecordEmpty(message) {
    state.record = null;
    els.recordTitle.textContent = 'Selecione um registro';
    els.recordOpen.hidden = true;
    els.recordBody.innerHTML =
      '<div class="cx-agent-record-empty">' +
      '<i class="fa-regular fa-address-card" aria-hidden="true"></i>' +
      '<strong>O contexto aparece quando for útil</strong>' +
      '<p>' + escapeHtml(message || 'Selecione um registro ou peça detalhes ao agente.') + '</p>' +
      '</div>';
  }

  function commercialMeta(label, value) {
    if (!value) return '';
    return '<div><span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(value) + '</strong></div>';
  }

  function renderRecordInsights(insights) {
    var alerts = (insights && insights.alerts) || [];
    if (!alerts.length) return '';
    return '<section class="cx-agent-record-section"><h3>Próximas ações</h3><div class="cx-agent-record-insights">' +
      alerts.slice(0, 3).map(function (item) {
        return '<button type="button" data-record-prompt="' + escapeHtml(item.prompt || '') + '">' +
          '<i class="fa-solid ' + escapeHtml(item.icon || 'fa-lightbulb') + '"></i>' +
          '<span><strong>' + escapeHtml(item.title) + '</strong><small>' + escapeHtml(item.body) + '</small></span>' +
          '</button>';
      }).join('') + '</div></section>';
  }

  function renderClientRecord(data) {
    var client = data.record || {};
    var contacts = data.contacts || [];
    var quotes = data.quotes || [];
    var classifications = ['Prospecção', 'Ativo', 'Geladeira'];
    return '' +
      '<div class="cx-agent-record-identity">' +
        '<span class="cx-agent-record-avatar">' + escapeHtml((client.nome || 'CL').slice(0, 2).toUpperCase()) + '</span>' +
        '<div><strong>' + escapeHtml(client.nome || 'Cliente') + '</strong><span>' +
          escapeHtml([client.tipo_label, client.cidade, client.uf].filter(Boolean).join(' · ')) +
        '</span></div>' +
      '</div>' +
      '<div class="cx-agent-record-metrics">' +
        commercialMeta('Responsável', client.responsavel || 'Não atribuído') +
        commercialMeta('Classificação', client.classificacao || 'Prospecção') +
        commercialMeta('Cotações', String(quotes.length)) +
      '</div>' +
      renderRecordInsights(data.insights) +
      '<section class="cx-agent-record-section"><h3>Dados do cliente</h3>' +
        '<form id="cx-agent-client-form" class="cx-agent-client-form">' +
          '<label><span>Nome fantasia</span><input name="nome" value="' + escapeHtml(client.nome || '') + '" required maxlength="200"></label>' +
          '<label><span>Razão social</span><input name="razao_social" value="' + escapeHtml(client.razao_social || '') + '" maxlength="200"></label>' +
          '<div class="cx-agent-form-row">' +
            '<label><span>Classificação</span><select name="classificacao_cliente">' +
              classifications.map(function (item) {
                return '<option' + (item === client.classificacao ? ' selected' : '') + '>' + escapeHtml(item) + '</option>';
              }).join('') +
            '</select></label>' +
            '<label><span>CNPJ</span><input name="cnpj" value="' + escapeHtml(client.cnpj || '') + '" maxlength="18"></label>' +
          '</div>' +
          '<label><span>Site</span><input name="site_url" value="' + escapeHtml(client.site_url || '') + '" maxlength="500" placeholder="https://"></label>' +
          '<label><span>Nota do executivo</span><textarea name="nota_executivo" maxlength="4000">' + escapeHtml(client.nota_executivo || '') + '</textarea></label>' +
          '<div class="cx-agent-client-signals">' +
            '<label><input type="checkbox" name="opera_midia"' + (client.opera_midia ? ' checked' : '') + '> Opera mídia</label>' +
            '<label><input type="checkbox" name="demanda_dados"' + (client.demanda_dados ? ' checked' : '') + '> Demanda dados</label>' +
            '<label><input type="checkbox" name="demanda_programatica_canais"' + (client.demanda_programatica_canais ? ' checked' : '') + '> Programática/canais</label>' +
          '</div>' +
          '<button class="cx-agent-record-save" type="submit"><i class="fa-solid fa-check"></i> Salvar alterações</button>' +
        '</form>' +
      '</section>' +
      '<section class="cx-agent-record-section"><h3>Contatos recentes</h3><div class="cx-agent-record-list">' +
        (contacts.length ? contacts.map(function (item) {
          return '<div><i class="fa-regular fa-user"></i><span><strong>' + escapeHtml(item.nome || 'Contato') +
            '</strong><small>' + escapeHtml(item.cargo || item.email || '') + '</small></span></div>';
        }).join('') : '<p>Nenhum contato cadastrado.</p>') +
      '</div></section>' +
      '<section class="cx-agent-record-section"><h3>Cotações recentes</h3><div class="cx-agent-record-list">' +
        (quotes.length ? quotes.map(function (item) {
          return '<button type="button" data-select-record="cotacao" data-record-id="' + escapeHtml(item.id) +
            '" data-record-label="' + escapeHtml(item.titulo || item.numero_cotacao || 'Cotação') + '">' +
            '<i class="fa-regular fa-file-lines"></i><span><strong>' + escapeHtml(item.titulo || item.numero_cotacao || 'Cotação') +
            '</strong><small>' + escapeHtml([item.status_label, item.valor].filter(Boolean).join(' · ')) + '</small></span></button>';
        }).join('') : '<p>Nenhuma cotação cadastrada.</p>') +
      '</div></section>';
  }

  function renderQuoteRecord(data) {
    var quote = data.record || {};
    var client = data.client || {};
    return '' +
      '<div class="cx-agent-record-identity">' +
        '<span class="cx-agent-record-avatar is-quote"><i class="fa-regular fa-file-lines"></i></span>' +
        '<div><strong>' + escapeHtml(quote.titulo || quote.numero_cotacao || 'Cotação') + '</strong>' +
        '<span>' + escapeHtml(quote.numero_cotacao || '') + '</span></div>' +
      '</div>' +
      '<div class="cx-agent-record-metrics">' +
        commercialMeta('Status', quote.status_label || quote.status) +
        commercialMeta('Valor', quote.valor) +
        commercialMeta('Responsável', quote.vendedor_nome || 'Não atribuído') +
      '</div>' +
      renderRecordInsights(data.insights) +
      '<section class="cx-agent-record-section"><h3>Resumo da cotação</h3><div class="cx-agent-record-details">' +
        commercialMeta('Cliente', client.nome || quote.cliente_nome) +
        commercialMeta('Período', [quote.periodo_inicio, quote.periodo_fim].filter(Boolean).join(' a ')) +
        commercialMeta('Objetivo', quote.objetivo) +
        commercialMeta('Plataformas', (quote.plataformas || []).join(', ')) +
      '</div></section>' +
      (client.id ? '<button type="button" class="cx-agent-record-client-link" data-select-record="cliente" data-record-id="' +
        escapeHtml(client.id) + '" data-record-label="' + escapeHtml(client.nome || 'Cliente') +
        '"><i class="fa-regular fa-building"></i> Ver cliente no painel</button>' : '');
  }

  function contextIcon(type) {
    return {
      cliente: 'fa-building',
      contato: 'fa-user',
      cotacao: 'fa-file-lines',
      pi: 'fa-receipt',
      campanha: 'fa-bullhorn',
      canal: 'fa-tower-broadcast',
      audiencia: 'fa-users'
    }[String(type || '').toLowerCase()] || 'fa-address-card';
  }

  function contextValue(value) {
    if (value == null || value === '') return '';
    if (typeof value === 'number') {
      return value.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
    }
    return String(value);
  }

  function safeActionUrl(url, allowExternal) {
    if (safeInternalUrl(url)) return url;
    if (!allowExternal || typeof url !== 'string') return '';
    try {
      var parsed = new URL(url, window.location.origin);
      return ['http:', 'https:'].indexOf(parsed.protocol) >= 0 ? parsed.href : '';
    } catch (_error) {
      return '';
    }
  }

  function renderContextFacts(facts) {
    var valid = (facts || []).filter(function (item) { return contextValue(item.value); });
    if (!valid.length) return '';
    return '<dl class="cx-agent-context-facts">' + valid.map(function (item) {
      var value = contextValue(item.value);
      return '<div><dt>' + escapeHtml(item.label || '') + '</dt><dd>' +
        '<span>' + escapeHtml(value) + '</span>' +
        (item.copy ? '<button type="button" data-copy-value="' + escapeHtml(value) +
          '" aria-label="Copiar ' + escapeHtml(item.label || 'valor') + '"><i class="fa-regular fa-copy"></i></button>' : '') +
        '</dd></div>';
    }).join('') + '</dl>';
  }

  function platformIcon(name) {
    var n = String(name || '').toLowerCase();
    if (/meta|facebook|instagram/.test(n)) return 'fa-brands fa-meta';
    if (/youtube/.test(n)) return 'fa-brands fa-youtube';
    if (/google/.test(n)) return 'fa-brands fa-google';
    if (/spotify/.test(n)) return 'fa-brands fa-spotify';
    if (/tiktok/.test(n)) return 'fa-brands fa-tiktok';
    if (/linkedin/.test(n)) return 'fa-brands fa-linkedin';
    if (/twitter|\bx\b/.test(n)) return 'fa-brands fa-x-twitter';
    return 'fa-solid fa-bullhorn';
  }

  function renderPlatformChips(platforms) {
    var names = (platforms || []).filter(Boolean);
    if (!names.length) return '';
    return '<div class="cx-agent-platforms">' +
      '<span>Plataformas</span>' +
      '<div>' + names.map(function (name) {
        return '<em title="' + escapeHtml(name) + '"><i class="' + platformIcon(name) + '" aria-hidden="true"></i>' +
          escapeHtml(name) + '</em>';
      }).join('') + '</div></div>';
  }

  function renderPerson(name, photo, role) {
    if (!name) return '';
    var img = safeInternalUrl(photo) ? '<img src="' + escapeHtml(photo) + '" alt="">' : '<i class="fa-regular fa-user"></i>';
    return '<div class="cx-agent-person">' + img + '<div><strong>' + escapeHtml(name) + '</strong>' +
      (role ? '<small>' + escapeHtml(role) + '</small>' : '') + '</div></div>';
  }

  function renderDisclosure(key, title, count, body, open) {
    return '<details class="cx-agent-disclosure" data-disclosure="' + escapeHtml(key) + '"' +
      (open ? ' open' : '') + '>' +
      '<summary><span>' + escapeHtml(title) + '</span>' +
      (count != null ? '<strong>' + escapeHtml(String(count)) + '</strong>' : '') +
      '<i class="fa-solid fa-chevron-right" aria-hidden="true"></i></summary>' +
      '<div>' + (body || '') + '</div></details>';
  }

  function renderQuoteItems(items) {
    if (!items || !items.length) return '<p class="cx-agent-empty">Nenhum item nesta proposta.</p>';
    return '<div class="cx-agent-quote-items">' + items.map(function (item) {
      var metrics = (item.metrics || []).map(function (metric) {
        return '<div><dt>' + escapeHtml(metric.label || '') + '</dt><dd>' + escapeHtml(metric.value || '') + '</dd></div>';
      }).join('');
      var facts = (item.facts || []).filter(function (fact) {
        return ['Valor líquido', 'Valor bruto', 'Custo base', 'Tech fee', 'Comissão'].indexOf(fact.label) >= 0;
      }).map(function (fact) {
        return '<div><dt>' + escapeHtml(fact.label || '') + '</dt><dd>' + escapeHtml(contextValue(fact.value)) + '</dd></div>';
      }).join('');
      return '<article class="cx-agent-quote-item">' +
        '<header><strong>' + escapeHtml(item.title || 'Item') + '</strong>' +
        (item.subtitle ? '<small>' + escapeHtml(item.subtitle) + '</small>' : '') + '</header>' +
        (metrics ? '<dl>' + metrics + '</dl>' : '') +
        (facts ? '<dl>' + facts + '</dl>' : '') +
        '</article>';
    }).join('') + '</div>';
  }

  function renderPriceBreakdown(rows) {
    if (!rows || !rows.length) return '<p class="cx-agent-empty">Sem composição de preço.</p>';
    return '<dl class="cx-agent-price-breakdown">' + rows.map(function (row) {
      return '<div' + (row.emphasis ? ' class="is-emphasis"' : '') + '><dt>' +
        escapeHtml(row.label || '') + '</dt><dd>' + escapeHtml(row.value || '') + '</dd></div>';
    }).join('') + '</dl>';
  }

  function renderCampaignMiniList(items) {
    if (!items || !items.length) return '<p class="cx-agent-empty">Nenhuma campanha.</p>';
    return '<div class="cx-agent-context-list">' + items.map(function (item) {
      return '<button type="button" class="cx-agent-entity-row" data-select-record="campanha" data-record-id="' +
        escapeHtml(item.id || '') + '" data-record-label="' + escapeHtml(item.title || 'Campanha') + '">' +
        '<span><strong>' + escapeHtml(item.title || 'Campanha') + '</strong>' +
        '<small>' + escapeHtml([item.status, item.period || item.subtitle].filter(Boolean).join(' · ')) + '</small></span>' +
        '<i class="fa-solid fa-chevron-right" aria-hidden="true"></i></button>';
    }).join('') + '</div>';
  }

  function syncSecondaryActions(actions) {
    if (!els.recordMoreExtra) return;
    els.recordMoreExtra.innerHTML = (actions || []).map(function (action) {
      if (action.kind === 'copy' && action.value) {
        return '<button type="button" data-copy-value="' + escapeHtml(action.value) + '">' +
          '<i class="fa-regular fa-copy" aria-hidden="true"></i><span>' + escapeHtml(action.label || 'Copiar') + '</span></button>';
      }
      if (action.kind === 'prompt' && action.prompt) {
        return '<button type="button" data-record-prompt="' + escapeHtml(action.prompt) + '">' +
          '<i class="fa-regular fa-comments" aria-hidden="true"></i><span>' + escapeHtml(action.label || 'Consultar') + '</span></button>';
      }
      if (action.kind === 'use_context' && action.entity_id) {
        return '<button type="button" data-select-record="' + escapeHtml(action.entity_type || '') +
          '" data-record-id="' + escapeHtml(action.entity_id || '') +
          '" data-record-label="' + escapeHtml(action.entity_label || '') +
          '" data-record-subtype="' + escapeHtml(action.entity_subtype || '') + '">' +
          '<i class="fa-regular fa-folder-open" aria-hidden="true"></i><span>' + escapeHtml(action.label || 'Abrir') + '</span></button>';
      }
      return '';
    }).join('');
  }

  function recordSkeleton(type) {
    var kind = String(type || '').toLowerCase();
    if (kind === 'cotacao' || kind === 'quote') {
      return '<div class="cx-agent-skeleton cx-agent-quote-summary" aria-hidden="true">' +
        '<i></i><i></i><i></i><i></i><i></i><i></i></div>';
    }
    return '<div class="cx-agent-skeleton" aria-hidden="true"><i></i><i></i><i></i></div>';
  }

  function mediaKind(url) {
    var value = String(url || '').toLowerCase();
    if (/\.(mp4|webm|mov)(\?|$)/.test(value) || /\/video\//.test(value)) return 'video';
    if (/\.(mp3|wav|ogg|m4a)(\?|$)/.test(value) || /\/audio\//.test(value)) return 'audio';
    if (/drive\.google\.com/.test(value)) return 'drive';
    return 'iframe';
  }

  function driveFolderId(url) {
    try {
      var parsed = new URL(url);
      if (parsed.protocol !== 'https:' || parsed.hostname !== 'drive.google.com') return '';
      var folder = parsed.pathname.match(/\/folders\/([a-zA-Z0-9_-]+)/);
      if (folder) return folder[1];
      var file = parsed.pathname.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
      if (file) return file[1];
      return parsed.searchParams.get('id') || '';
    } catch (_error) {
      return '';
    }
  }

  function renderMediaPane(item) {
    var url = safeActionUrl(item.url, true);
    if (!els.mediaContent) return;
    els.mediaOpen.href = url || '#';
    els.mediaOpen.hidden = !url;
    var folderId = driveFolderId(url);
    var download = folderId
      ? 'https://drive.google.com/uc?export=download&id=' + encodeURIComponent(folderId)
      : url;
    els.mediaDownload.href = download || '#';
    els.mediaDownload.hidden = !download;
    els.mediaCopy.dataset.copyValue = url || '';
    var kind = mediaKind(url);
    if (!url) {
      els.mediaContent.innerHTML = '<div class="cx-agent-record-empty"><strong>Pasta ainda não gerada</strong><p>Não há um endereço válido para esta pasta.</p></div>';
      return;
    }
    if (kind === 'video') {
      els.mediaContent.innerHTML = '<video controls src="' + escapeHtml(url) + '"></video>';
      return;
    }
    if (kind === 'audio') {
      els.mediaContent.innerHTML = '<audio controls src="' + escapeHtml(url) + '"></audio>';
      return;
    }
    var embed = folderId
      ? 'https://drive.google.com/embeddedfolderview?id=' + encodeURIComponent(folderId) + '#grid'
      : url;
    els.mediaContent.innerHTML = '<iframe title="' + escapeHtml(item.label || 'Conteúdo') +
      '" src="' + escapeHtml(embed) + '" loading="eager" allow="autoplay"></iframe>';
  }

  function openMediaModal(title, items) {
    var folders = (items || []).filter(function (item) { return item && item.url; });
    if (!els.mediaDialog || !folders.length) return;
    els.mediaTitle.textContent = title || 'Arquivos';
    els.mediaTabs.innerHTML = folders.map(function (item, index) {
      return '<button type="button" role="tab" aria-selected="' + (index === 0 ? 'true' : 'false') +
        '" data-media-url="' + escapeHtml(item.url) + '">' + escapeHtml(item.label || 'Arquivo') + '</button>';
    }).join('');
    renderMediaPane(folders[0]);
    if (!els.mediaDialog.open) els.mediaDialog.showModal();
  }

  function renderContextRelations(relations) {
    return (relations || []).map(function (section) {
      var count = section.count == null ? (section.items || []).length : section.count;
      return '<button type="button" class="cx-agent-relation-row" data-explore-key="' +
        escapeHtml(section.key || '') + '" data-explore-title="' + escapeHtml(section.title || 'Relacionados') + '">' +
        '<span>' + escapeHtml(section.title || 'Relacionados') + '</span>' +
        '<strong>' + escapeHtml(String(count)) + '</strong>' +
        '<i class="fa-solid fa-chevron-right" aria-hidden="true"></i></button>';
    }).join('');
  }

  function renderExplorerList(title, items) {
    if (!items || !items.length) {
      return '<div class="cx-agent-empty">Nenhum registro em ' + escapeHtml(title) + '.</div>';
    }
    return '<div class="cx-agent-context-list">' + items.map(function (item) {
      var typeLabel = item.type_label || entityTypeLabel(item.type, item.entity_subtype);
      var meta = item.subtitle && item.subtitle !== typeLabel ? item.subtitle : (item.email || item.phone || '');
      return '<button type="button" class="cx-agent-entity-row" data-select-record="' +
        escapeHtml(item.type || '') + '" data-record-id="' + escapeHtml(item.id || '') +
        '" data-record-label="' + escapeHtml(item.title || 'Registro') +
        '" data-record-subtype="' + escapeHtml(item.entity_subtype || '') + '">' +
        '<span><strong>' + escapeHtml(item.title || 'Registro') + '</strong>' +
        '<small>' + escapeHtml(typeLabel) + '</small>' +
        (meta ? '<small>' + escapeHtml(meta) + '</small>' : '') +
        '</span><i class="fa-solid fa-chevron-right" aria-hidden="true"></i></button>';
    }).join('') + '</div>';
  }

  function renderContextActions(actions) {
    var html = (actions || []).filter(function (action) {
      return action.kind !== 'copy';
    }).map(function (action) {
      if (action.kind === 'open') {
        var href = safeActionUrl(action.url, action.external);
        if (!href) return '';
        return '<a href="' + escapeHtml(href) + '"' +
          (action.external ? ' target="_blank" rel="noopener noreferrer"' : '') +
          '><i class="fa-solid fa-arrow-up-right-from-square"></i>' + escapeHtml(action.label || 'Abrir registro') + '</a>';
      }
      if (action.kind === 'prompt' && action.prompt) {
        return '<button type="button" data-record-prompt="' + escapeHtml(action.prompt) +
          '">' + escapeHtml(action.label || 'Usar no agente') + '</button>';
      }
      if (action.kind === 'drive') {
        return '<button type="button" data-open-drive="' + encodeURIComponent(JSON.stringify(action.folders || [])) +
          '" data-drive-title="' + escapeHtml(action.label || 'Pasta do Drive') +
          '"><i class="fa-brands fa-google-drive"></i>' + escapeHtml(action.label || 'Pasta do Drive') + '</button>';
      }
      if (action.kind === 'dashboard') {
        var items = action.items || (action.url ? [{ label: action.label || 'Dashboard', url: action.url }] : []);
        return '<button type="button" data-open-dashboard="' + encodeURIComponent(JSON.stringify(items)) +
          '"><i class="fa-solid fa-chart-line"></i>' + escapeHtml(action.label || 'Dashboard') + '</button>';
      }
      return '';
    }).join('');
    html += '<button type="button" data-switch-context>Trocar</button>';
    return html ? '<div class="cx-agent-context-actions">' + html + '</div>' : '';
  }

  function renderBreadcrumb() {
    if (!els.breadcrumb) return;
    var stack = state.explorerStack || [];
    if (!stack.length) {
      els.breadcrumb.hidden = true;
      els.breadcrumb.innerHTML = '';
      return;
    }
    els.breadcrumb.hidden = false;
    els.breadcrumb.innerHTML = stack.map(function (crumb, index) {
      return '<button type="button" data-breadcrumb-index="' + index + '">' +
        escapeHtml(crumb.label || crumb.title || 'Registro') + '</button>';
    }).join('<span aria-hidden="true">›</span>');
  }

  function renderCommercialRecord(data) {
    state.record = data;
    if (data.context && data.context.entity_subtype) {
      state.context.entity_subtype = data.context.entity_subtype;
      if (data.context.entity_label) state.context.entity_label = data.context.entity_label;
      if (els.consulting) {
        els.consulting.hidden = !state.context.entity_id;
        if (els.consultingName) els.consultingName.textContent = state.context.entity_label || '';
        if (els.consultingType) {
          els.consultingType.textContent = entityTypeLabel(state.context.entity_type, state.context.entity_subtype);
        }
      }
      if (els.input && state.context.entity_label) {
        els.input.placeholder = 'Pergunte sobre ' + state.context.entity_label + '...';
      }
    }
    var identity = data.identity || {};
    var title = identity.title || 'Registro';
    var typeLabel = identity.type_label || entityTypeLabel(data.type, identity.entity_subtype || (data.context || {}).entity_subtype);
    var openUrl = safeActionUrl(data.url, false);
    var identityPhoto = safeInternalUrl(identity.photo_url) ? identity.photo_url : '';
    els.recordTitle.textContent = title;
    els.recordOpen.href = openUrl || '#';
    els.recordOpen.hidden = !openUrl;
    if (els.recordCopyLink) els.recordCopyLink.dataset.copyValue = openUrl || '';
    syncSecondaryActions(data.actions_secondary);
    if (state.explorerView) {
      renderBreadcrumb();
      els.recordBody.innerHTML =
        '<div class="cx-agent-context-explorer">' +
          '<header><h3>' + escapeHtml(state.explorerView.title || 'Explorar') + '</h3>' +
          '<span>' + escapeHtml(String((state.explorerView.items || []).length)) + '</span></header>' +
          renderExplorerList(state.explorerView.title, state.explorerView.items) +
        '</div>';
      return;
    }
    renderBreadcrumb();
    var responsible = identity.responsible || '';
    var location = identity.location || identity.subtitle || '';
    var meta = identity.meta || '';
    var code = identity.code || identity.subtitle || '';
    var identityHtml =
      '<div class="cx-agent-context-identity is-' + escapeHtml(data.type || 'record') + '">' +
        '<span>' + (identityPhoto
          ? '<img src="' + escapeHtml(identityPhoto) + '" alt="">'
          : '<i class="fa-regular ' + contextIcon(data.type) + '"></i>') + '</span>' +
        '<div><small>' + escapeHtml(typeLabel) + '</small>' +
        '<strong>' + escapeHtml(title) + '</strong>' +
        (code && code !== title ? '<p>' + escapeHtml(code) + '</p>' : '') +
        (meta ? '<p>' + escapeHtml(meta) + '</p>' : '') +
        (responsible ? renderPerson(responsible, identity.responsible_photo || identity.photo_url, identity.role) : '') +
        (location && !meta ? '<p>' + escapeHtml(location) + '</p>' : '') + '</div>' +
      '</div>';
    var extra = '';
    if (data.type === 'cotacao') {
      extra = renderPlatformChips(data.platforms) +
        renderDisclosure('items', 'Itens da proposta', (data.quote_items || []).length, renderQuoteItems(data.quote_items)) +
        renderDisclosure('pricing', 'Composição de preço', null, renderPriceBreakdown(data.price_breakdown));
    }
    if (data.type === 'pi') {
      extra = renderDisclosure('campaigns', 'Campanhas', (data.campaigns || []).length, renderCampaignMiniList(data.campaigns), true);
    }
    els.recordBody.innerHTML =
      identityHtml +
      renderContextActions(data.actions) +
      renderContextFacts(data.facts) +
      extra +
      '<section class="cx-agent-context-explorer">' +
        '<header><h3>Explorar</h3></header>' +
        renderContextRelations(data.relations) +
      '</section>';
  }

  function loadCommercialRecord(force) {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if (!state.contextWallOpen) return Promise.resolve();
    if (!ctx.entity_id || ['cliente', 'client', 'agencia', 'agency', 'contato', 'contact', 'cotacao', 'quote', 'pi', 'campanha', 'campaign'].indexOf(type) === -1) {
      state.recordKey = '';
      setRecordEmpty();
      return Promise.resolve();
    }
    var key = type + ':' + ctx.entity_id;
    if (!force && key === state.recordKey && state.record) return Promise.resolve();
    state.recordKey = key;
    els.recordTitle.textContent = 'Carregando registro...';
    els.recordOpen.hidden = true;
    els.recordBody.innerHTML = recordSkeleton(type);
    return api('/api/agent/context/' + encodeURIComponent(type) + '/' + encodeURIComponent(ctx.entity_id))
      .then(function (payload) { renderCommercialRecord(payload.data || {}); })
      .catch(function (error) {
        state.record = null;
        els.recordBody.innerHTML = '<div class="cx-agent-record-empty is-error"><strong>Registro indisponível</strong><p>' +
          escapeHtml(error.message) + '</p></div>';
      });
  }

  function selectCommercialRecord(type, id, label, subtype) {
    var normalized = type === 'client' ? 'cliente' : type === 'quote' ? 'cotacao' :
      type === 'contact' ? 'contato' : type === 'campaign' ? 'campanha' :
      type === 'agency' || type === 'agencia' ? 'cliente' : type;
    if (['atividade', 'canal', 'audiencia'].indexOf(normalized) >= 0) return;
    var resolvedSubtype = subtype || (type === 'agencia' || type === 'agency' ? 'agencia' : '');
    var operational = ['pi', 'campanha'].indexOf(normalized) >= 0;
    var stack = state.explorerStack || [];
    var last = stack[stack.length - 1];
    if (!last || last.id !== String(id || '') || last.type !== normalized) {
      state.explorerStack = stack.concat([{
        type: normalized, id: String(id || ''), label: String(label || ''), subtype: resolvedSubtype
      }]);
    }
    state.explorerView = null;
    setAgentContext({
      module: operational ? 'operacao' : (normalized === 'cotacao' ? 'comercial' : 'crm'),
      screen: normalized,
      entity_type: normalized,
      entity_id: String(id || ''),
      entity_label: String(label || ''),
      entity_subtype: resolvedSubtype
    }, true, 'agent');
    els.commercialResults.hidden = true;
    els.commercialQuery.value = '';
    openContextWall();
    if (state.record) renderCommercialRecord(state.record);
  }

  function renderCommercialResults(data) {
    var clients = data.clients || [];
    var agencies = clients.filter(function (item) { return item.is_agencia; });
    var clientRecords = clients.filter(function (item) { return !item.is_agencia; });
    var contacts = data.contacts || [];
    var quotes = data.quotes || [];
    var pis = data.pis || [];
    var campaigns = data.campaigns || [];
    var channels = data.channels || [];
    var audiences = data.audiences || [];
    if (!clientRecords.length && !agencies.length && !contacts.length && !quotes.length &&
        !pis.length && !campaigns.length && !channels.length && !audiences.length) {
      els.commercialResults.innerHTML = '<p class="cx-agent-commercial-empty">Nenhum registro encontrado.</p>';
      els.commercialResults.hidden = false;
      return;
    }
    var groups = [];
    function addGroup(title, type, items, mapper) {
      if (!items.length) return;
      groups.push('<section><h3>' + escapeHtml(title) + '</h3>' + items.map(function (raw) {
        var item = mapper(raw);
        var attrs = item.interactive === false ? '' :
          ' data-search-record="' + type + '" data-record-id="' + escapeHtml(item.id) +
          '" data-record-label="' + escapeHtml(item.title) +
          '" data-record-subtype="' + escapeHtml(item.subtype || (type === 'agencia' ? 'agencia' : '')) + '"';
        return '<button type="button"' + attrs + '><i class="fa-regular ' + contextIcon(type) + '"></i>' +
          '<span><strong>' + escapeHtml(item.title) + '</strong>' +
          (item.subtitle ? '<small>' + escapeHtml(item.subtitle) + '</small>' : '') +
          (item.phone ? '<small><i class="fa-solid fa-phone"></i> ' + escapeHtml(item.phone) + '</small>' : '') +
          (item.email ? '<small><i class="fa-regular fa-envelope"></i> ' + escapeHtml(item.email) + '</small>' : '') +
          '</span></button>';
      }).join('') + '</section>');
    }
    function mapParty(item) {
      return {
        id: item.id,
        title: item.nome || 'Cliente',
        subtype: item.is_agencia ? 'agencia' : 'cliente_final',
        subtitle: [item.tipo_label || (item.is_agencia ? 'Agência' : 'Cliente final'), item.responsavel].filter(Boolean).join(' · ')
      };
    }
    addGroup('Clientes', 'cliente', clientRecords, mapParty);
    addGroup('Agências', 'agencia', agencies, mapParty);
    addGroup('Contatos', 'contato', contacts, function (item) {
      return {
        id: item.id,
        title: item.nome || 'Contato',
        subtitle: [item.cargo, item.setor, item.cliente_nome].filter(Boolean).join(' · '),
        phone: item.telefone,
        email: item.email
      };
    });
    addGroup('Cotações', 'cotacao', quotes, function (item) {
      return {
        id: item.id,
        title: item.titulo || item.numero_cotacao || 'Cotação',
        subtitle: [item.cliente_nome, item.status_label, item.valor].filter(Boolean).join(' · ')
      };
    });
    addGroup('PIs', 'pi', pis, function (item) { return item; });
    addGroup('Campanhas', 'campanha', campaigns, function (item) { return item; });
    addGroup('Canais e plataformas', 'canal', channels, function (item) {
      return {
        id: item.id,
        title: item.nome || 'Plataforma',
        subtitle: [item.canais, item.total_audiencias ? item.total_audiencias + ' audiência(s)' : ''].filter(Boolean).join(' · '),
        interactive: false
      };
    });
    addGroup('Audiências', 'audiencia', audiences, function (item) {
      return {
        id: item.id,
        title: item.nome || 'Audiência',
        subtitle: [item.plataforma_nome, item.perfil].filter(Boolean).join(' · '),
        interactive: false
      };
    });
    els.commercialResults.innerHTML = groups.join('');
    els.commercialResults.hidden = false;
  }

  function openExplorer(key, title, push) {
    var relations = (state.record && state.record.relations) || [];
    var section = relations.filter(function (item) { return item.key === key; })[0];
    if (!section) return;
    var ctx = outgoingContext();
    state.explorerView = { key: key, title: title || section.title, items: section.items || [] };
    if (push !== false) {
      if (!state.explorerStack.length && ctx.entity_id) {
        state.explorerStack = [{
          type: ctx.entity_type, id: ctx.entity_id, label: ctx.entity_label, subtype: ctx.entity_subtype || ''
        }];
      }
      state.explorerStack = (state.explorerStack || []).concat([{
        type: 'relation', id: key, label: title || section.title, subtype: ''
      }]);
    }
    renderCommercialRecord(state.record);
  }

  function popExplorer(index) {
    var stack = (state.explorerStack || []).slice(0, index + 1);
    var crumb = stack[stack.length - 1];
    state.explorerStack = stack;
    if (!crumb) {
      state.explorerView = null;
      if (state.record) renderCommercialRecord(state.record);
      return;
    }
    if (crumb.type === 'relation') {
      openExplorer(crumb.id, crumb.label, false);
      return;
    }
    state.explorerView = null;
    selectCommercialRecord(crumb.type, crumb.id, crumb.label, crumb.subtype);
  }

  function searchCommercial() {
    var query = els.commercialQuery.value.trim();
    clearTimeout(state.commercialTimer);
    if (state.commercialController) state.commercialController.abort();
    if (query.length < 2) {
      els.commercialResults.hidden = true;
      return;
    }
    state.commercialTimer = setTimeout(function () {
      state.commercialController = new AbortController();
      var params = new URLSearchParams({
        q: query,
        scope: els.commercialScope.value || 'all',
        limit: '8'
      });
      api('/api/agent/commercial/search?' + params.toString(), {
        signal: state.commercialController.signal
      }).then(function (payload) {
        renderCommercialResults(payload.data || {});
      }).catch(function (error) {
        if (error.name !== 'AbortError') {
          els.commercialResults.innerHTML = '<p class="cx-agent-commercial-empty">' + escapeHtml(error.message) + '</p>';
          els.commercialResults.hidden = false;
        }
      });
    }, 240);
  }

  function syncCommercialScope(value) {
    var scope = value === 'all' ? 'all' : 'mine';
    els.commercialScope.value = scope;
    els.scopeTrigger.querySelector('span').textContent =
      scope === 'all' ? 'Toda a Centralcomm' : 'Meus registros';
    els.scopeSheet.querySelectorAll('[data-commercial-scope]').forEach(function (button) {
      var selected = button.dataset.commercialScope === scope;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }

  function saveClientRecord(form) {
    var ctx = outgoingContext();
    var data = new FormData(form);
    var payload = {
      nome: data.get('nome'),
      razao_social: data.get('razao_social'),
      cnpj: data.get('cnpj'),
      classificacao_cliente: data.get('classificacao_cliente'),
      site_url: data.get('site_url'),
      nota_executivo: data.get('nota_executivo'),
      opera_midia: data.has('opera_midia'),
      demanda_dados: data.has('demanda_dados'),
      demanda_programatica_canais: data.has('demanda_programatica_canais')
    };
    var submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    return api('/api/agent/commercial/clients/' + encodeURIComponent(ctx.entity_id), {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }).then(function (response) {
      renderCommercialRecord(response.data || {});
      var updated = response.data && response.data.record;
      if (updated) {
        state.context.entity_label = updated.nome || state.context.entity_label;
        updateContext();
      }
      window.dispatchEvent(new CustomEvent('centralx:entity-updated', {
        detail: { entity_type: 'cliente', entity_id: String(ctx.entity_id) }
      }));
      showComposerFeedback('Cliente atualizado no CRM.', false);
    }).catch(function (error) {
      showComposerFeedback(error.message, true);
    }).finally(function () {
      if (submit.isConnected) submit.disabled = false;
    });
  }

  function setOpen(open) {
    if (open) {
      state.lastFocus = document.activeElement;
      dock.classList.add('is-open');
      dock.classList.remove('is-minimized');
      dock.setAttribute('aria-hidden', 'false');
      trigger.setAttribute('aria-expanded', 'true');
      bootstrap().finally(function () { els.input.focus(); });
    } else {
      dock.classList.remove('is-open', 'is-minimized', 'is-settings');
      dock.setAttribute('aria-hidden', 'true');
      trigger.setAttribute('aria-expanded', 'false');
      els.settingsPanel.hidden = true;
      els.workspace.hidden = false;
      if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus();
    }
  }

  function minimize() {
    var minimized = dock.classList.toggle('is-minimized');
    dock.classList.add('is-open');
    dock.setAttribute('aria-hidden', 'false');
    els.minimize.setAttribute('aria-label', minimized ? 'Restaurar agente' : 'Minimizar agente');
    els.minimize.querySelector('i').className = minimized ? 'fa-solid fa-up-right-and-down-left-from-center' : 'fa-solid fa-minus';
  }

  function showSettings(open) {
    setMoreOpen(false);
    dock.classList.toggle('is-settings', open);
    els.settingsPanel.hidden = !open;
    els.workspace.hidden = open;
  }

  function setMoreOpen(open) {
    if (!els.moreMenu) return;
    els.moreMenu.hidden = !open;
    els.moreToggle.setAttribute('aria-expanded', String(open));
  }

  function setSearchOpen(open) {
    els.commercialSearch.hidden = !open;
    els.searchToggle.setAttribute('aria-expanded', String(open));
    if (open) {
      setMoreOpen(false);
      window.setTimeout(function () { els.commercialQuery.focus(); }, 0);
    } else {
      els.commercialResults.hidden = true;
    }
  }

  function switchTab(name) {
    dock.classList.toggle('is-history', name === 'history');
    setMoreOpen(false);
    document.querySelectorAll('[data-agent-tab]').forEach(function (tab) {
      var active = tab.dataset.agentTab === name;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('[data-agent-panel]').forEach(function (panel) {
      var active = panel.dataset.agentPanel === name;
      panel.classList.toggle('is-active', active);
      panel.hidden = !active;
    });
    if (name === 'history') loadHistory();
    if (name === 'suggestions') loadInsights();
    if (name === 'actions') renderActions();
  }

  function rowButton(label, icon, className, onClick, extra) {
    var item = document.createElement('button');
    item.type = 'button';
    item.className = className;
    var glyph = document.createElement('i');
    glyph.className = 'fa-solid ' + (icon || 'fa-arrow-right');
    glyph.setAttribute('aria-hidden', 'true');
    var copy = document.createElement('span');
    var title = document.createElement('strong');
    title.textContent = label;
    copy.appendChild(title);
    if (extra) {
      var body = document.createElement('em');
      body.textContent = extra;
      copy.appendChild(body);
    }
    var chevron = document.createElement('i');
    chevron.className = 'fa-solid fa-chevron-right';
    chevron.setAttribute('aria-hidden', 'true');
    item.append(glyph, copy, chevron);
    item.addEventListener('click', onClick);
    return item;
  }

  function usePrompt(prompt) {
    switchTab('chat');
    els.input.value = prompt;
    resizeInput();
    renderComposerSuggestions();
    els.input.focus();
  }

  function goCrm(prompt) {
    usePrompt(prompt);
  }

  function heading(text) {
    var node = document.createElement('h3');
    node.className = 'cx-agent-group-title';
    node.textContent = text;
    return node;
  }

  function empty(text) {
    var node = document.createElement('div');
    node.className = 'cx-agent-empty';
    node.textContent = text;
    return node;
  }

  function renderActions() {
    var client = clientContext();
    els.actions.replaceChildren();
    if (!client) {
      els.actions.appendChild(heading('Ações mais utilizadas'));
      [
        { label: 'Buscar cliente', prompt: 'Busque um cliente pelo nome.', icon: 'fa-magnifying-glass' },
        { label: 'Analisar um documento', prompt: 'Vou anexar um documento. Analise, resuma e destaque riscos e próximos passos.', icon: 'fa-file-lines' }
      ].forEach(function (item) {
        els.actions.appendChild(rowButton(item.label, item.icon, 'cx-agent-action', function () { usePrompt(item.prompt); }));
      });
      return;
    }
    var name = client.entity_label || 'este cliente';
    els.actions.appendChild(heading('Ações mais utilizadas'));
    [
      { label: 'Adicionar contato', icon: 'fa-user-plus', prompt: 'Quero criar um contato neste cliente: ' + name + '.' },
      { label: 'Criar atividade', icon: 'fa-calendar-plus', prompt: 'Quero criar uma atividade para ' + name + '.' },
      { label: 'Registrar observação', icon: 'fa-sticky-note', prompt: 'Quero registrar uma observação neste cliente: ' + name + '.' },
      { label: 'Criar cotação', icon: 'fa-file-invoice', prompt: 'Quero criar uma cotação para ' + name + '.' },
      { label: 'Atualizar follow-up', icon: 'fa-clock-rotate-left', prompt: 'Com base neste cliente, redija um follow-up profissional para ' + name + '.' }
    ].forEach(function (item) {
      els.actions.appendChild(rowButton(item.label, item.icon, 'cx-agent-action', function () { goCrm(item.prompt); }));
    });
    els.actions.appendChild(heading('Outras ações'));
    [
      { label: 'Listar contatos', icon: 'fa-users', prompt: 'Liste os contatos deste cliente.' },
      { label: 'Listar cotações', icon: 'fa-file-lines', prompt: 'Liste as cotações deste cliente.' },
      { label: 'Ver histórico do cliente', icon: 'fa-clock-rotate-left', prompt: 'Liste as atividades deste cliente.' }
    ].forEach(function (item) {
      els.actions.appendChild(rowButton(item.label, item.icon, 'cx-agent-action', function () { usePrompt(item.prompt); }));
    });
  }

  function renderSuggestions(payload) {
    var data = payload || {};
    var prompts = data.prompts || data;
    if (Array.isArray(payload)) {
      prompts = payload;
      data = { alerts: [], prompts: payload };
    }
    state.suggestions = prompts || [];
    state.insights = data.entity || data.alerts ? data : state.insights;
    els.prompts.replaceChildren();
    state.suggestions.slice(0, 4).forEach(function (item) {
      els.prompts.appendChild(rowButton(item.label, item.icon || 'fa-magnifying-glass', 'cx-agent-prompt', function () {
        usePrompt(item.prompt);
      }));
    });
    els.suggestions.replaceChildren();
    var alerts = data.alerts || [];
    if (!commercialContext()) {
      els.suggestions.appendChild(empty('Abra um cliente ou cotação para ver alertas.'));
    } else if (alerts.length) {
      els.suggestions.appendChild(heading('Sugestões para você'));
      alerts.forEach(function (item) {
        var btn = rowButton(item.title, item.icon || 'fa-lightbulb', 'cx-agent-insight is-' + (item.tone || 'info'), function () {
          usePrompt(item.prompt);
        }, item.body);
        els.suggestions.appendChild(btn);
      });
    } else {
      els.suggestions.appendChild(empty('Nenhuma próxima ação recomendada agora.'));
    }
    if (state.suggestions.length) {
      els.suggestions.appendChild(heading('Perguntas comuns'));
      state.suggestions.forEach(function (item) {
        els.suggestions.appendChild(rowButton(item.label, item.icon || 'fa-magnifying-glass', 'cx-agent-suggestion', function () {
          usePrompt(item.prompt);
        }));
      });
    }
    renderActions();
    renderComposerSuggestions();
  }

  function suggestionCatalog() {
    return (state.suggestions || []).slice();
  }

  function renderComposerSuggestions() {
    if (!els.composerSuggestions) return;
    var query = String(els.input.value || '').trim().toLowerCase();
    var words = query.split(/\s+/).filter(function (word) { return word.length > 2; });
    var catalog = suggestionCatalog().map(function (item, index) {
      var haystack = String((item.label || '') + ' ' + (item.prompt || '')).toLowerCase();
      var score = words.reduce(function (total, word) {
        return total + (haystack.indexOf(word) >= 0 ? 3 : 0);
      }, 0) - (index / 100);
      return { item: item, score: score };
    });
    if (words.length) {
      catalog = catalog.filter(function (entry) { return entry.score > 0; });
    }
    catalog.sort(function (a, b) { return b.score - a.score; });
    els.composerSuggestions.replaceChildren();
    catalog.slice(0, 4).forEach(function (entry) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'cx-agent-composer-suggestion';
      button.textContent = entry.item.label;
      button.addEventListener('click', function () { usePrompt(entry.item.prompt); });
      els.composerSuggestions.appendChild(button);
    });
    els.composerSuggestions.hidden = !els.composerSuggestions.children.length;
  }

  function applyPrefsUi() {
    els.prefHistory.checked = state.prefs.saveHistory !== false;
    els.prefContext.checked = state.prefs.usePageContext !== false;
    els.prefNotify.checked = state.prefs.notifications !== false;
  }

  function bootstrap(force) {
    if (state.bootstrapped && !force) return Promise.resolve();
    setStatus('Conectando...', true);
    return api('/api/agent/bootstrap?' + contextQuery(outgoingContext()))
      .then(function (payload) {
        var data = payload.data || {};
        state.csrf = data.csrf_token || '';
        state.capabilities = data.capabilities || [];
        els.commercialScope.hidden = state.capabilities.indexOf('commercial.read.global') === -1;
        els.scopeTrigger.hidden = els.commercialScope.hidden;
        if (els.commercialScope.hidden) els.commercialScope.value = 'mine';
        else if (!els.commercialScope.value) els.commercialScope.value = 'all';
        syncCommercialScope(els.commercialScope.value || 'all');
        state.bootstrapped = true;
        state.currentUser = data.user || state.currentUser;
        els.userName.textContent = (data.user && data.user.name) || 'tudo bem?';
        var model = data.model || 'openai/gpt-4o-mini';
        var modelName = model === 'openai/gpt-4o-mini' ? 'Padrão (OpenRouter)' : model.split('/').pop();
        els.modelLabel.textContent = modelName;
        els.modelSelect.replaceChildren();
        var option = document.createElement('option');
        option.value = model;
        option.textContent = modelName;
        els.modelSelect.appendChild(option);
        renderSuggestions(data.insights || { prompts: data.suggestions || [], alerts: [] });
        if (data.active_conversation) {
          state.conversationId = String(data.active_conversation.id);
          sessionStorage.setItem('centralx_agent_conversation_id', state.conversationId);
          return loadConversation(state.conversationId);
        }
        setStatus('Online', true);
      })
      .catch(function (error) {
        setStatus('Indisponível', false);
        appendMessage('assistant', error.message || 'Agente temporariamente indisponível.');
      });
  }

  function ensureConversation() {
    if (state.conversationId) return Promise.resolve(state.conversationId);
    return api('/api/agent/conversations', {
      method: 'POST',
      body: JSON.stringify({ context: outgoingContext() })
    }).then(function (payload) {
      state.conversationId = String(payload.data.id);
      sessionStorage.setItem('centralx_agent_conversation_id', state.conversationId);
      return state.conversationId;
    });
  }

  function clearConversationView() {
    els.messages.querySelectorAll('.cx-agent-message').forEach(function (node) { node.remove(); });
    var welcome = els.messages.querySelector('.cx-agent-welcome');
    if (welcome) welcome.hidden = false;
  }

  function appendInline(parent, text) {
    var source = String(text || '');
    var pattern = /(\[[^\]\n]+\]\((?:https?:\/\/|mailto:|tel:|\/)[^)\s]+\)|`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g;
    var cursor = 0;
    var match;
    while ((match = pattern.exec(source))) {
      if (match.index > cursor) parent.appendChild(document.createTextNode(source.slice(cursor, match.index)));
      var token = match[0];
      var node;
      if (token.startsWith('[')) {
        var linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        var href = linkMatch && safeMarkdownHref(linkMatch[2]);
        if (!href) {
          node = document.createTextNode(linkMatch ? linkMatch[1] : token);
        } else {
          node = document.createElement('a');
          node.href = href;
          node.textContent = linkMatch[1];
          if (/^https?:/i.test(href) && !href.startsWith(window.location.origin)) {
            node.target = '_blank';
            node.rel = 'noopener noreferrer';
          }
        }
      } else if (token.startsWith('`')) {
        node = document.createElement('code');
        node.textContent = token.slice(1, -1);
      } else if (token.startsWith('**')) {
        node = document.createElement('strong');
        node.textContent = token.slice(2, -2);
      } else {
        node = document.createElement('em');
        node.textContent = token.slice(1, -1);
      }
      parent.appendChild(node);
      cursor = match.index + token.length;
    }
    if (cursor < source.length) parent.appendChild(document.createTextNode(source.slice(cursor)));
  }

  function safeMarkdownHref(value) {
    var href = String(value || '').trim();
    if (/^(mailto:|tel:)/i.test(href) || safeInternalUrl(href)) return href;
    try {
      var parsed = new URL(href);
      if (parsed.protocol !== 'https:' || parsed.origin !== 'https://ai.centralcomm.media') return '';
      return parsed.href;
    } catch (_error) {
      return '';
    }
  }

  function markdownCells(line) {
    return line.trim().replace(/^\||\|$/g, '').split('|').map(function (cell) { return cell.trim(); });
  }

  function isMarkdownBoundary(lines, index) {
    var line = lines[index] || '';
    var next = lines[index + 1] || '';
    return !line.trim() || /^#{1,3}\s/.test(line) || /^```/.test(line) ||
      /^>\s?/.test(line) || /^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line) ||
      (line.includes('|') && /^\s*\|?[\s:|-]+\|[\s:|-]+/.test(next));
  }

  function renderMarkdown(content) {
    var root = document.createElement('div');
    root.className = 'cx-agent-markdown';
    var normalized = String(content || '')
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p\s*>/gi, '\n\n')
      .replace(/<li[^>]*>/gi, '- ')
      .replace(/<\/li\s*>/gi, '\n')
      .replace(/<[^>]+>/g, '');
    var lines = normalized.replace(/\r\n/g, '\n').split('\n');
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (!line.trim()) { i += 1; continue; }

      if (/^```/.test(line)) {
        var language = line.slice(3).trim();
        var codeLines = [];
        i += 1;
        while (i < lines.length && !/^```/.test(lines[i])) {
          codeLines.push(lines[i]);
          i += 1;
        }
        if (i < lines.length) i += 1;
        var pre = document.createElement('pre');
        var code = document.createElement('code');
        if (language) code.dataset.language = language;
        code.textContent = codeLines.join('\n');
        pre.appendChild(code);
        root.appendChild(pre);
        continue;
      }

      var headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
      if (headingMatch) {
        var headingEl = document.createElement('h' + headingMatch[1].length);
        appendInline(headingEl, headingMatch[2]);
        root.appendChild(headingEl);
        i += 1;
        continue;
      }

      if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]+/.test(lines[i + 1])) {
        var headers = markdownCells(line);
        var table = document.createElement('table');
        var thead = document.createElement('thead');
        var headRow = document.createElement('tr');
        headers.forEach(function (value) {
          var th = document.createElement('th');
          appendInline(th, value);
          headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);
        var tbody = document.createElement('tbody');
        i += 2;
        while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
          var row = document.createElement('tr');
          markdownCells(lines[i]).forEach(function (value) {
            var td = document.createElement('td');
            appendInline(td, value);
            row.appendChild(td);
          });
          tbody.appendChild(row);
          i += 1;
        }
        table.appendChild(tbody);
        var tableWrap = document.createElement('div');
        tableWrap.className = 'cx-agent-table-wrap';
        tableWrap.appendChild(table);
        root.appendChild(tableWrap);
        continue;
      }

      if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
        var ordered = /^\d+\.\s+/.test(line);
        var list = document.createElement(ordered ? 'ol' : 'ul');
        var listPattern = ordered ? /^\d+\.\s+(.+)$/ : /^[-*]\s+(.+)$/;
        while (i < lines.length && listPattern.test(lines[i])) {
          var li = document.createElement('li');
          appendInline(li, lines[i].match(listPattern)[1]);
          list.appendChild(li);
          i += 1;
        }
        root.appendChild(list);
        continue;
      }

      if (/^>\s?/.test(line)) {
        var quote = document.createElement('blockquote');
        var quoteLines = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          quoteLines.push(lines[i].replace(/^>\s?/, ''));
          i += 1;
        }
        appendInline(quote, quoteLines.join(' '));
        root.appendChild(quote);
        continue;
      }

      var paragraphLines = [line.trim()];
      i += 1;
      while (i < lines.length && !isMarkdownBoundary(lines, i)) {
        paragraphLines.push(lines[i].trim());
        i += 1;
      }
      var paragraph = document.createElement('p');
      appendInline(paragraph, paragraphLines.join(' '));
      root.appendChild(paragraph);
    }
    return root;
  }

  function renderAttachmentSummary(parent, attachments) {
    if (!Array.isArray(attachments) || !attachments.length) return;
    var summary = document.createElement('div');
    summary.className = 'cx-agent-attachment-summary';
    attachments.forEach(function (file) {
      var chip = document.createElement('span');
      chip.textContent = file.name || 'Anexo';
      summary.appendChild(chip);
    });
    parent.appendChild(summary);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try {
        if (!document.execCommand('copy')) throw new Error('copy unavailable');
        resolve();
      } catch (error) {
        reject(error);
      } finally {
        area.remove();
      }
    });
  }

  function addAssistantMessageExtras(wrapper, body, content, display) {
    renderAttachmentSummary(body, display && display.attachments);
    var cards = document.createElement('div');
    cards.className = 'cx-agent-message-cards';
    renderDisplay(cards, display);
    if (cards.children.length) wrapper.appendChild(cards);
    var actions = document.createElement('div');
    actions.className = 'cx-agent-message-actions';
    var menu = document.createElement('div');
    menu.className = 'cx-agent-message-more';
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'cx-agent-message-action';
    toggle.setAttribute('aria-label', 'Ações da resposta');
    toggle.innerHTML = '<i class="fa-solid fa-ellipsis" aria-hidden="true"></i>';
    var panel = document.createElement('div');
    panel.className = 'cx-agent-message-menu';
    panel.hidden = true;
    var copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = 'Copiar resposta';
    copy.addEventListener('click', function () {
      copyText(String(content || '')).then(function () {
        copy.textContent = 'Copiado';
        setTimeout(function () { copy.textContent = 'Copiar resposta'; }, 1200);
      });
    });
    var reuse = document.createElement('button');
    reuse.type = 'button';
    reuse.textContent = 'Reutilizar';
    reuse.addEventListener('click', function () {
      els.input.value = String(content || '');
      resizeInput();
      els.input.focus();
    });
    panel.append(copy, reuse);
    toggle.addEventListener('click', function (event) {
      event.stopPropagation();
      panel.hidden = !panel.hidden;
    });
    menu.append(toggle, panel);
    actions.appendChild(menu);
    wrapper.appendChild(actions);
  }

  function messageAvatar(role) {
    var avatar = document.createElement('span');
    avatar.className = 'cx-agent-message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    var photo = role === 'user' && state.currentUser ? state.currentUser.photo_url : '';
    if (safeInternalUrl(photo)) {
      var image = document.createElement('img');
      image.src = photo;
      image.alt = '';
      image.addEventListener('error', function () {
        image.remove();
        avatar.textContent = String(state.currentUser.name || 'EU').slice(0, 2).toUpperCase();
      });
      avatar.appendChild(image);
    } else if (role === 'user') {
      avatar.textContent = String((state.currentUser && state.currentUser.name) || 'EU').slice(0, 2).toUpperCase();
    } else {
      avatar.innerHTML = '<i class="fa-solid fa-sparkles"></i>';
    }
    return avatar;
  }

  function structuredDisplaySummary(display) {
    var groups = display && Array.isArray(display.results) ? display.results : [];
    if (!groups.length && display && (display.items || display.empty || display.summary)) groups = [display];
    var summaries = groups.map(function (group) { return String(group.summary || '').trim(); }).filter(Boolean);
    if (summaries.length) return summaries[summaries.length - 1];
    return '';
  }

  function hasStructuredResults(display) {
    var groups = display && Array.isArray(display.results) ? display.results : [];
    if (!groups.length && display && (display.items || display.empty || display.type)) groups = [display];
    return groups.some(function (group) {
      return (group.items && group.items.length) || group.empty || group.type === 'operation_summary' || group.type === 'empty';
    });
  }

  function appendMessage(role, content, display, extraClass) {
    var welcome = els.messages.querySelector('.cx-agent-welcome');
    if (welcome) welcome.hidden = true;
    var wrapper = document.createElement('article');
    wrapper.className = 'cx-agent-message is-' + role + (extraClass ? ' ' + extraClass : '');
    var body = document.createElement('div');
    body.className = 'cx-agent-message-body';
    var text = content || '';
    if (role === 'assistant' && !extraClass && hasStructuredResults(display)) {
      text = structuredDisplaySummary(display) || text;
      body.textContent = text;
    } else if (role === 'assistant' && !extraClass) {
      body.appendChild(renderMarkdown(content));
    } else {
      body.textContent = text;
    }
    if (role === 'user') wrapper.append(body, messageAvatar(role));
    else wrapper.append(messageAvatar(role), body);
    if (role === 'assistant' && !extraClass) {
      addAssistantMessageExtras(wrapper, body, text, display);
    } else {
      renderAttachmentSummary(body, display && display.attachments);
    }
    els.messages.appendChild(wrapper);
    els.messages.scrollTop = els.messages.scrollHeight;
    return wrapper;
  }

  function appendProgressiveMessage(content, display) {
    appendMessage('assistant', String(content || ''), display);
    return Promise.resolve();
  }

  function loadingStepsFor(text) {
    var t = String(text || '').toLowerCase();
    if (/cotac|proposta/.test(t)) return ['Consultando cotação…', 'Buscando itens da proposta…'];
    if (/\bpi\b|pedido de inserção/.test(t)) return ['Consultando PI…'];
    if (/campanha/.test(t)) return ['Carregando campanhas…'];
    if (/nota fiscal|nfe|nfs-e/.test(t)) return ['Consultando nota fiscal…'];
    if (/anexo|pdf|documento/.test(t)) return ['Lendo documento…', 'Relacionando com o CentralX…'];
    return ['Consultando…'];
  }

  function appendLoadingProgress(query) {
    var steps = loadingStepsFor(query);
    var node = appendMessage('assistant', '', null, 'is-loading');
    var body = node.querySelector('.cx-agent-message-body');
    var index = 0;
    function renderStep() {
      body.innerHTML = '<span class="cx-agent-progress"><i aria-hidden="true"></i><strong>' +
        escapeHtml(steps[Math.min(index, steps.length - 1)]) + '</strong></span>';
      index += 1;
    }
    renderStep();
    if (steps.length > 1) state.loadingTimer = window.setInterval(renderStep, 1600);
    return node;
  }

  function clearLoadingProgress(node) {
    window.clearInterval(state.loadingTimer);
    state.loadingTimer = null;
    if (node) node.remove();
  }

  function safeInternalUrl(url) {
    return typeof url === 'string' && /^\/(?!\/)[a-zA-Z0-9/_?#=&.%+-]*$/.test(url);
  }

  function relativeTime(value) {
    if (!value) return '';
    var parsed = Date.parse(String(value).indexOf('/') >= 0
      ? String(value).split('/').reverse().join('-')
      : value);
    if (Number.isNaN(parsed)) return String(value);
    var days = Math.round((Date.now() - parsed) / 86400000);
    if (days <= 0) return 'Atualizada hoje';
    if (days === 1) return 'Atualizada há 1 dia';
    return 'Atualizada há ' + days + ' dias';
  }

  function recordCtaLabel(item, ambiguous) {
    var type = String(item.type || '').toLowerCase();
    var subtype = String(item.entity_subtype || '').toLowerCase();
    if (ambiguous || item.primary_action === 'use_context') return 'Usar como contexto';
    if (type === 'cliente' && subtype === 'agencia') return 'Abrir agência';
    if (type === 'cliente') return 'Abrir cliente';
    if (type === 'cotacao') return 'Abrir cotação';
    if (type === 'pi') return 'Abrir PI';
    if (type === 'campanha') return 'Abrir campanha';
    if (type === 'contato') return 'Abrir contato';
    return 'Usar como contexto';
  }

  function bindSelect(node, item) {
    if (!item.type || !item.id) return;
    node.classList.add('is-selectable');
    node.setAttribute('role', 'button');
    node.tabIndex = 0;
    node.addEventListener('click', function () {
      selectCommercialRecord(item.type, item.id, item.title || 'Registro', item.entity_subtype || '');
    });
    node.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCommercialRecord(item.type, item.id, item.title || 'Registro', item.entity_subtype || '');
      }
    });
  }

  function renderEntityRow(item, ambiguous) {
    var row = document.createElement('div');
    row.className = 'cx-agent-entity-row';
    var typeLabel = item.type_label || entityTypeLabel(item.type, item.entity_subtype);
    var details = [];
    if (item.responsible && item.responsible !== 'Não informado') details.push(item.responsible);
    if (item.email) details.push(item.email);
    else if (item.phone) details.push(item.phone);
    if (item.status) details.push(item.status);
    if (item.value) details.push(item.value);
    if (item.updated) details.push(relativeTime(item.updated));
    row.innerHTML =
      '<span><strong>' + escapeHtml(item.title || 'Registro') + '</strong>' +
      '<small>' + escapeHtml(typeLabel) + '</small>' +
      (details.length ? '<small>' + escapeHtml(details.join(' · ')) + '</small>' : '') +
      '</span>' +
      '<em>' + escapeHtml(recordCtaLabel(item, ambiguous)) + '</em>' +
      '<i class="fa-solid fa-chevron-right" aria-hidden="true"></i>';
    bindSelect(row, item);
    return row;
  }

  function renderEmptyState(group) {
    var empty = group.empty || {};
    var box = document.createElement('div');
    box.className = 'cx-agent-empty';
    var title = document.createElement('strong');
    title.textContent = empty.title || group.title || 'Nenhum resultado';
    box.appendChild(title);
    if (empty.body) {
      var body = document.createElement('p');
      body.textContent = empty.body;
      box.appendChild(body);
    }
    (empty.related_candidates || []).forEach(function (item) {
      box.appendChild(renderEntityRow(item, true));
    });
    var actions = empty.actions || group.actions || [];
    if (actions.length) {
      var bar = document.createElement('div');
      bar.className = 'cx-agent-empty-actions';
      actions.forEach(function (action) {
        var button = document.createElement('button');
        button.type = 'button';
        button.textContent = action.label || 'Continuar';
        button.addEventListener('click', function () {
          if (action.kind === 'use_context' && action.entity_id) {
            selectCommercialRecord(
              action.entity_type || 'cliente', action.entity_id,
              action.entity_label || '', action.entity_subtype || ''
            );
            return;
          }
          if (action.prompt) usePrompt(action.prompt);
        });
        bar.appendChild(button);
      });
      box.appendChild(bar);
    }
    return box;
  }

  function renderPeriodHeader(parent, period) {
    if (!period) return;
    var row = document.createElement('div');
    row.className = 'cx-agent-period';
    row.innerHTML = '<span>Período</span><strong>' + escapeHtml(String(period.value || period)) + '</strong>' +
      (period.change_prompt ? '<button type="button">' + escapeHtml('Alterar período') + '</button>' : '');
    var button = row.querySelector('button');
    if (button && period.change_prompt) {
      button.addEventListener('click', function () { usePrompt(period.change_prompt); });
    }
    parent.appendChild(row);
  }

  function renderChatSummaryCard(parent, item, type) {
    var card = document.createElement('article');
    card.className = 'cx-agent-' + String(type || 'summary').replace(/_/g, '-');
    var rows = [];
    if (item.status || item.kind) rows.push(['', [item.status, item.kind].filter(Boolean).join(' · ')]);
    if (item.gross) rows.push(['Valor bruto', item.gross]);
    if (item.net) rows.push(['Valor líquido', item.net]);
    if (item.cost) rows.push(['Custo', item.cost]);
    if (item.margin) rows.push(['Margem', item.margin]);
    if (item.period) rows.push(['Período', item.period]);
    if (item.client) rows.push(['Cliente', item.client]);
    if (item.responsible) rows.push(['Executivo responsável', item.responsible]);
    if (item.start) rows.push(['Início', item.start]);
    if (item.end) rows.push(['Término previsto', item.end]);
    if (item.budget) rows.push(['Budget', Number(item.budget).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })]);
    if (item.delivery_percent != null) rows.push(['Entrega', item.delivery_percent + '%']);
    if (item.campaign_count) rows.push(['Campanhas', String(item.campaign_count)]);
    card.innerHTML = '<header><strong>' + escapeHtml(item.title || 'Registro') + '</strong>' +
      (item.code ? '<small>' + escapeHtml(item.code) + '</small>' : '') + '</header>' +
      (item.platforms && item.platforms.length ? renderPlatformChips(item.platforms) : '') +
      '<dl>' + rows.filter(function (row) { return row[1]; }).map(function (row) {
        return '<div>' + (row[0] ? '<dt>' + escapeHtml(row[0]) + '</dt>' : '') +
          '<dd>' + escapeHtml(String(row[1])) + '</dd></div>';
      }).join('') + '</dl>';
    if (item.type && item.id) bindSelect(card, item);
    parent.appendChild(card);
  }

  function renderOperationSummary(parent, group) {
    var summary = document.createElement('div');
    summary.className = 'cx-agent-summary cx-agent-status-summary';
    var heading = document.createElement('h3');
    heading.textContent = group.title || 'Operação';
    summary.appendChild(heading);
    renderPeriodHeader(summary, group.period);
    var metrics = document.createElement('div');
    metrics.className = 'cx-agent-summary-metrics';
    (group.metrics || []).forEach(function (metric) {
      var cell = document.createElement('div');
      var value = metric.kind === 'currency' && metric.value
        ? Number(metric.value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
        : String(metric.value);
      cell.innerHTML = '<strong>' + escapeHtml(value) + '</strong><span>' + escapeHtml(metric.label || '') + '</span>';
      metrics.appendChild(cell);
    });
    summary.appendChild(metrics);
    (group.groups || []).forEach(function (block) {
      var list = document.createElement('div');
      list.className = 'cx-agent-status-list';
      var title = document.createElement('h4');
      title.textContent = block.title || '';
      list.appendChild(title);
      (block.items || []).forEach(function (item) {
        var row = document.createElement('div');
        row.className = 'cx-agent-metric-row';
        row.innerHTML = '<span>' + escapeHtml(item.label || item.title || '') + '</span><strong>' +
          escapeHtml(String(item.count || 0)) + '</strong>';
        list.appendChild(row);
      });
      summary.appendChild(list);
    });
    if ((group.actions || []).length) {
      var bar = document.createElement('div');
      bar.className = 'cx-agent-empty-actions';
      group.actions.forEach(function (action) {
        var button = document.createElement('button');
        button.type = 'button';
        button.textContent = action.label || 'Ver';
        button.addEventListener('click', function () {
          if (action.prompt) usePrompt(action.prompt);
        });
        bar.appendChild(button);
      });
      summary.appendChild(bar);
    }
    parent.appendChild(summary);
  }

  function renderDisplay(parent, display) {
    var groups = display && Array.isArray(display.results) ? display.results : [];
    groups.forEach(function (group) {
      if (group.type === 'operation_summary' || group.type === 'status_summary') {
        renderOperationSummary(parent, group);
        return;
      }
      if (group.period) renderPeriodHeader(parent, group.period);
      if (group.type === 'empty' || (group.empty && !(group.items || []).length)) {
        parent.appendChild(renderEmptyState(group));
        return;
      }
      if (group.type === 'quote_summary' || group.type === 'pi_summary' || group.type === 'campaign_summary' || group.type === 'document_summary' || group.type === 'invoice_summary') {
        (group.items || []).slice(0, 4).forEach(function (item) {
          renderChatSummaryCard(parent, item, group.type);
        });
        return;
      }
      var results = document.createElement('div');
      results.className = 'cx-agent-result-list cx-agent-results cx-agent-entity-list';
      var items = group.items || [];
      var ambiguous = Boolean(group.ambiguous);
      items.slice(0, 8).forEach(function (item) {
        results.appendChild(renderEntityRow(item, ambiguous));
      });
      (group.actions || []).filter(function (action) { return action.kind === 'prompt'; }).forEach(function (action) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'cx-agent-suggestion';
        button.textContent = action.label || 'Continuar';
        button.addEventListener('click', function () { usePrompt(action.prompt); });
        results.appendChild(button);
      });
      if (results.children.length) parent.appendChild(results);
    });
  }

  function setAgentContext(patch, persist, source) {
    state.context = Object.assign({}, state.context, patch || {});
    Object.keys(state.context).forEach(function (key) {
      state.context[key] = String(state.context[key] || '').slice(0, key === 'entity_label' ? 200 : 80);
    });
    if (source) state.contextSource = source;
    else if (patch && patch.entity_id) state.contextSource = 'agent';
    updateContext();
    if (persist === false) window.clearTimeout(state.contextPersistTimer);
    if (state.bootstrapped) loadInsights();
  }

  function loadConversation(id) {
    return api('/api/agent/conversations/' + encodeURIComponent(id))
      .then(function (payload) {
        var conversation = payload.data.conversation || {};
        setAgentContext(conversation.context || readBodyContext(), false);
        closeContextWall();
        clearConversationView();
        (payload.data.messages || []).forEach(function (message) {
          appendMessage(message.role, message.content, message.display);
        });
        setStatus('Online', true);
      })
      .catch(function () {
        state.conversationId = '';
        sessionStorage.removeItem('centralx_agent_conversation_id');
        clearConversationView();
        setStatus('Online', true);
      });
  }

  function renderContactConfirmation(confirmation) {
    var labels = {
      nome: 'Nome',
      email: 'E-mail',
      telefone: 'Telefone',
      telefone_secundario: 'Telefone secundário'
    };
    var changes = confirmation.changes || {};
    var before = confirmation.before || {};
    var rows = Object.keys(changes).map(function (key) {
      return '<div><span>' + escapeHtml(labels[key] || key) + '</span><del>' +
        escapeHtml(before[key] || 'Não informado') + '</del><strong>' +
        escapeHtml(changes[key] || 'Remover') + '</strong></div>';
    }).join('');
    state.pendingConfirmation = confirmation;
    els.recordTitle.textContent = confirmation.title || 'Revisar contato';
    els.recordOpen.hidden = true;
    els.recordBody.innerHTML =
      '<section class="cx-agent-confirmation">' +
        '<header><i class="fa-regular fa-address-card"></i><div><strong>' +
        escapeHtml(confirmation.title || 'Revisar contato') + '</strong><span>' +
        escapeHtml(confirmation.client_label || '') + '</span></div></header>' +
        '<p>Confira os dados antes de salvar no CRM.</p>' +
        '<div class="cx-agent-confirmation-diff">' + rows + '</div>' +
        '<footer><button type="button" data-contact-cancel>Cancelar</button>' +
        '<button type="button" data-contact-confirm><i class="fa-solid fa-check"></i> Confirmar e salvar</button></footer>' +
      '</section>';
    state.contextWallOpen = true;
    dock.dataset.contextWall = 'open';
    els.record.setAttribute('aria-hidden', 'false');
    syncWorkspaceView('record');
  }

  function applyContactConfirmation() {
    var confirmation = state.pendingConfirmation;
    if (!confirmation) return;
    var button = els.recordBody.querySelector('[data-contact-confirm]');
    if (button) {
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Salvando';
    }
    api('/api/agent/context/contact-changes', {
      method: 'POST',
      body: JSON.stringify({
        confirmed: true,
        operation: confirmation.operation,
        cliente_id: confirmation.cliente_id,
        contato_id: confirmation.contato_id,
        changes: confirmation.changes
      })
    }).then(function (payload) {
      state.pendingConfirmation = null;
      setAgentContext(payload.data.context || {}, true);
      showComposerFeedback('Contato atualizado no CRM.');
      openContextWall();
    }).catch(function (error) {
      showComposerFeedback(error.message, true);
      if (button) {
        button.disabled = false;
        button.innerHTML = '<i class="fa-solid fa-check"></i> Confirmar e salvar';
      }
    });
  }

  function handleAssistantUi(message) {
    var display = message.display || {};
    var ui = message.ui || display.ui || {};
    if (ui.ambiguous) return;
    if (ui.context_focus) {
      setAgentContext(ui.context_focus, true, 'agent');
      openContextWall();
    }
    if (ui.confirmation) renderContactConfirmation(ui.confirmation);
  }

  function dayLabel(iso) {
    if (!iso) return 'Anteriores';
    var date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'Anteriores';
    var today = new Date();
    var startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    var startThat = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    var diff = Math.round((startToday - startThat) / 86400000);
    if (diff === 0) return 'Hoje';
    if (diff === 1) return 'Ontem';
    return date.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long' });
  }

  function renderHistory() {
    els.history.replaceChildren();
    if (!state.prefs.saveHistory) {
      els.history.appendChild(empty('O histórico está oculto nas configurações.'));
      return;
    }
    var query = (els.historyQuery.value || '').trim().toLowerCase();
    var items = state.conversations.filter(function (conversation) {
      var hay = ((conversation.title || '') + ' ' + (conversation.context && conversation.context.entity_label || '')).toLowerCase();
      return !query || hay.indexOf(query) !== -1;
    });
    if (!items.length) {
      els.history.appendChild(empty(query ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa ainda.'));
      return;
    }
    var groups = [];
    items.forEach(function (conversation) {
      var label = dayLabel(conversation.updated_at || conversation.created_at);
      var last = groups[groups.length - 1];
      if (!last || last.label !== label) {
        last = { label: label, items: [] };
        groups.push(last);
      }
      last.items.push(conversation);
    });
    groups.forEach(function (group) {
      els.history.appendChild(heading(group.label));
      group.items.forEach(function (conversation) {
        var item = document.createElement('div');
        item.className = 'cx-agent-history-item';
        var open = document.createElement('button');
        open.type = 'button';
        open.className = 'cx-agent-history-main';
        var glyph = document.createElement('i');
        glyph.className = 'fa-regular fa-comments';
        var copy = document.createElement('span');
        var title = document.createElement('strong');
        title.textContent = conversation.title || 'Nova conversa';
        var meta = document.createElement('em');
        var when = conversation.updated_at ? new Date(conversation.updated_at) : null;
        meta.textContent = (conversation.context && conversation.context.entity_label) || 'Conversa';
        copy.append(title, meta);
        var time = document.createElement('time');
        time.textContent = when && !Number.isNaN(when.getTime())
          ? when.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
          : '';
        open.append(glyph, copy, time);
        open.addEventListener('click', function () {
          state.conversationId = String(conversation.id);
          sessionStorage.setItem('centralx_agent_conversation_id', state.conversationId);
          loadConversation(state.conversationId).then(function () { switchTab('chat'); });
        });
        var menu = document.createElement('button');
        menu.type = 'button';
        menu.className = 'cx-agent-icon-btn';
        menu.setAttribute('aria-label', 'Abrir conversa');
        menu.innerHTML = '<i class="fa-solid fa-ellipsis-vertical" aria-hidden="true"></i>';
        menu.addEventListener('click', function () { open.click(); });
        item.append(open, menu);
        els.history.appendChild(item);
      });
    });
  }

  function loadHistory() {
    if (!state.prefs.saveHistory) {
      renderHistory();
      return;
    }
    els.history.replaceChildren(empty('Carregando histórico...'));
    api('/api/agent/history?page=1').then(function (payload) {
      state.conversations = payload.data || [];
      renderHistory();
    }).catch(function (error) {
      els.history.replaceChildren(empty(error.message));
    });
  }

  function loadInsights() {
    api('/api/agent/insights?' + contextQuery(outgoingContext())).then(function (payload) {
      renderSuggestions(payload.data || {});
    }).catch(function () {
      renderSuggestions({ alerts: [], prompts: state.suggestions });
    });
  }

  function loadSuggestions() {
    loadInsights();
  }

  function showComposerFeedback(message, isError) {
    els.feedback.textContent = message || '';
    els.feedback.hidden = !message;
    els.feedback.classList.toggle('is-error', Boolean(isError));
  }

  function humanSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1).replace('.', ',') + ' MB';
  }

  function readDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(new Error('Não foi possível ler ' + file.name + '.')); };
      reader.readAsDataURL(file);
    });
  }

  function optimizeImage(file) {
    return readDataUrl(file).then(function (source) {
      return new Promise(function (resolve, reject) {
        var image = new Image();
        image.onload = function () {
          var maxSide = 2048;
          var ratio = Math.min(1, maxSide / Math.max(image.width, image.height));
          var canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(image.width * ratio));
          canvas.height = Math.max(1, Math.round(image.height * ratio));
          var context = canvas.getContext('2d');
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          var mime = file.type === 'image/png' && file.size < 1500000 ? 'image/png' : 'image/jpeg';
          var data = canvas.toDataURL(mime, mime === 'image/jpeg' ? 0.86 : undefined);
          resolve({ data: data, mime: mime, size: Math.round((data.length * 3) / 4) });
        };
        image.onerror = function () { reject(new Error('Imagem inválida: ' + file.name)); };
        image.src = source;
      });
    });
  }

  function prepareAttachment(file) {
    var allowed = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf', 'text/plain', 'text/csv', 'application/json'];
    if (!allowed.includes(file.type)) return Promise.reject(new Error('Formato não aceito: ' + file.name));
    var limit = file.type === 'application/pdf' ? 12 * 1024 * 1024 :
      (file.type.startsWith('image/') ? 8 * 1024 * 1024 : 1024 * 1024);
    if (file.size > limit) return Promise.reject(new Error(file.name + ' excede o limite de ' + humanSize(limit) + '.'));
    var prepared = file.type.startsWith('image/') ? optimizeImage(file) : readDataUrl(file).then(function (data) {
      return { data: data, mime: file.type, size: file.size };
    });
    return prepared.then(function (result) {
      return {
        id: String(Date.now()) + Math.random().toString(16).slice(2),
        name: file.name.slice(0, 180),
        mime: result.mime,
        size: result.size,
        data: result.data
      };
    });
  }

  function renderPendingAttachments() {
    els.attachments.replaceChildren();
    state.attachments.forEach(function (file) {
      var chip = document.createElement('div');
      chip.className = 'cx-agent-attachment';
      var icon = document.createElement('i');
      icon.className = 'fa-regular ' + (file.mime === 'application/pdf' ? 'fa-file-pdf' : (file.mime.startsWith('image/') ? 'fa-file-image' : 'fa-file-lines'));
      var info = document.createElement('div');
      info.className = 'cx-agent-attachment-info';
      var name = document.createElement('strong');
      name.textContent = file.name;
      var size = document.createElement('span');
      size.textContent = humanSize(file.size);
      info.append(name, size);
      var remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'cx-agent-attachment-remove';
      remove.setAttribute('aria-label', 'Remover ' + file.name);
      remove.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
      remove.addEventListener('click', function () {
        state.attachments = state.attachments.filter(function (item) { return item.id !== file.id; });
        renderPendingAttachments();
      });
      chip.append(icon, info, remove);
      els.attachments.appendChild(chip);
    });
    els.attachments.hidden = !state.attachments.length;
  }

  function addFiles(fileList) {
    var files = Array.from(fileList || []);
    showComposerFeedback('');
    if (!files.length) return;
    if (state.attachments.length + files.length > 4) {
      showComposerFeedback('Anexe no máximo 4 arquivos por mensagem.', true);
      files = files.slice(0, Math.max(0, 4 - state.attachments.length));
    }
    if (!files.length) return;
    showComposerFeedback('Preparando anexos…');
    Promise.all(files.map(prepareAttachment)).then(function (prepared) {
      var total = state.attachments.concat(prepared).reduce(function (sum, file) { return sum + file.size; }, 0);
      if (total > 20 * 1024 * 1024) throw new Error('Os anexos somados devem ter no máximo 20 MB.');
      state.attachments = state.attachments.concat(prepared);
      renderPendingAttachments();
      showComposerFeedback('');
      els.input.focus();
    }).catch(function (error) {
      showComposerFeedback(error.message, true);
    }).finally(function () {
      els.fileInput.value = '';
    });
  }

  function resizeInput() {
    els.input.style.height = 'auto';
    els.input.style.height = Math.min(Math.round(window.innerHeight * 0.38), els.input.scrollHeight) + 'px';
    if (els.characterCount) {
      els.characterCount.textContent = els.input.value.length.toLocaleString('pt-BR') + ' / 12.000';
    }
  }

  function showExtract(files) {
    var extractable = (files || []).find(function (file) {
      return file.mime === 'application/pdf' || String(file.mime || '').indexOf('image/') === 0;
    });
    if (!extractable) {
      els.extract.hidden = true;
      return false;
    }
    els.extractName.textContent = extractable.name;
    els.extractSize.textContent = humanSize(extractable.size);
    els.extract.hidden = false;
    return true;
  }

  function hideExtract() {
    els.extract.hidden = true;
  }

  function setSending(sending) {
    els.input.disabled = sending;
    els.attach.disabled = sending;
    els.fileInput.disabled = sending;
    els.send.disabled = false;
    els.send.setAttribute('aria-label', sending ? 'Cancelar consulta' : 'Enviar mensagem');
    els.send.querySelector('i').className = sending ? 'fa-solid fa-stop' : 'fa-solid fa-paper-plane';
    setStatus(sending ? 'Consultando…' : 'Online', true);
  }

  function sendMessage() {
    var content = els.input.value.trim();
    if (!content && !state.attachments.length) return;
    if (!content) content = 'Analise os arquivos anexados e apresente os pontos mais importantes.';
    var ctx = outgoingContext();
    var normalized = content.replace(/\s+/g, ' ').toLowerCase();
    if (!state.attachments.length && state.lastQuery.text === normalized && state.lastQuery.entityId === String(ctx.entity_id || '')) {
      appendMessage('assistant', state.lastQuery.message || 'O resultado continua o mesmo.');
      els.input.value = '';
      resizeInput();
      return;
    }
    var outgoingAttachments = state.attachments.slice();
    var attachmentMetadata = outgoingAttachments.map(function (file) {
      return { name: file.name, mime: file.mime, size: file.size };
    });
    appendMessage('user', content, { attachments: attachmentMetadata });
    els.input.value = '';
    state.attachments = [];
    renderPendingAttachments();
    showComposerFeedback('');
    resizeInput();
    setSending(true);
    var extracting = showExtract(outgoingAttachments);
    var loading = extracting ? null : appendLoadingProgress(content);
    state.controller = new AbortController();
    ensureConversation().then(function (id) {
      return api('/api/agent/conversations/' + encodeURIComponent(id) + '/messages', {
        method: 'POST',
        signal: state.controller.signal,
        body: JSON.stringify({
          message: content,
          context: outgoingContext(),
          attachments: outgoingAttachments.map(function (file) {
            return { name: file.name, mime: file.mime, size: file.size, data: file.data };
          })
        })
      });
    }).then(function (payload) {
      clearLoadingProgress(loading);
      hideExtract();
      var message = payload.data.message;
      state.lastQuery = {
        text: normalized,
        entityId: String(outgoingContext().entity_id || ''),
        message: structuredDisplaySummary(message.display) || message.content || 'O resultado continua o mesmo.'
      };
      return appendProgressiveMessage(message.content, message.display).then(function () {
        handleAssistantUi(message);
      });
    }).catch(function (error) {
      clearLoadingProgress(loading);
      hideExtract();
      var errorMessage = error.name === 'AbortError' ? 'Consulta cancelada.' : error.message;
      if (error.requestId) errorMessage += '\n\nReferência técnica: `' + error.requestId + '`';
      appendMessage('assistant', errorMessage);
    }).finally(function () {
      state.controller = null;
      setSending(false);
      setStatus('Online', true);
      els.input.disabled = false;
      els.input.focus();
    });
  }

  window.CentralXAgent = {
    open: function () { setOpen(true); },
    close: function () { setOpen(false); },
    setContext: function (patch) { setAgentContext(patch, true); },
    openContext: function (context) {
      setOpen(true);
      openContextWall(context);
    },
    closeContext: closeContextWall,
    getContext: function () { return Object.assign({}, state.context); }
  };

  trigger.addEventListener('click', function () { setOpen(true); });
  els.close.addEventListener('click', function () { setOpen(false); });
  els.minimize.addEventListener('click', minimize);
  els.settings.addEventListener('click', function () { showSettings(true); });
  els.searchToggle.addEventListener('click', function () {
    setSearchOpen(els.commercialSearch.hidden);
  });
  els.searchClose.addEventListener('click', function () { setSearchOpen(false); });
  els.moreToggle.addEventListener('click', function () {
    setMoreOpen(els.moreMenu.hidden);
  });
  els.historyOpen.addEventListener('click', function () { switchTab('history'); });
  els.historyBack.addEventListener('click', function () { switchTab('chat'); });
  els.settingsBack.addEventListener('click', function () { showSettings(false); });
  if (els.entity) els.entity.addEventListener('click', openEntity);
  els.recordClose.addEventListener('click', closeContextWall);
  els.commercialQuery.addEventListener('input', searchCommercial);
  els.commercialScope.addEventListener('change', function () {
    syncCommercialScope(els.commercialScope.value);
    searchCommercial();
  });
  els.scopeTrigger.addEventListener('click', function () {
    syncCommercialScope(els.commercialScope.value);
    els.scopeSheet.showModal();
  });
  els.scopeSheet.querySelector('[data-scope-sheet-close]').addEventListener('click', function () {
    els.scopeSheet.close();
  });
  els.scopeSheet.querySelectorAll('[data-commercial-scope]').forEach(function (button) {
    button.addEventListener('click', function () {
      syncCommercialScope(button.dataset.commercialScope);
      els.scopeSheet.close();
      searchCommercial();
      els.commercialQuery.focus();
    });
  });
  els.commercialQuery.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown') {
      var first = els.commercialResults.querySelector('button');
      if (first) {
        event.preventDefault();
        first.focus();
      }
    } else if (event.key === 'Enter') {
      var match = els.commercialResults.querySelector('button');
      if (match) {
        event.preventDefault();
        match.click();
      }
    }
  });
  els.commercialResults.addEventListener('click', function (event) {
    var button = event.target.closest('[data-search-record]');
    if (button) {
      selectCommercialRecord(
        button.dataset.searchRecord,
        button.dataset.recordId,
        button.dataset.recordLabel,
        button.dataset.recordSubtype
      );
    }
  });
  els.recordBody.addEventListener('click', function (event) {
    var copy = event.target.closest('[data-copy-value]');
    if (copy) {
      copyText(copy.dataset.copyValue || '').then(function () {
        copy.classList.add('is-copied');
        window.setTimeout(function () { copy.classList.remove('is-copied'); }, 900);
      });
      return;
    }
    if (event.target.closest('[data-contact-confirm]')) {
      applyContactConfirmation();
      return;
    }
    if (event.target.closest('[data-contact-cancel]')) {
      state.pendingConfirmation = null;
      if (state.record) renderCommercialRecord(state.record);
      else closeContextWall();
      return;
    }
    var drive = event.target.closest('[data-open-drive]');
    if (drive) {
      try {
        openMediaModal(drive.dataset.driveTitle || 'Pasta do Drive', JSON.parse(decodeURIComponent(drive.dataset.openDrive || '[]')));
      } catch (_error) {}
      return;
    }
    var dashboard = event.target.closest('[data-open-dashboard]');
    if (dashboard) {
      try {
        openMediaModal('Dashboard', JSON.parse(decodeURIComponent(dashboard.dataset.openDashboard || '[]')));
      } catch (_error) {}
      return;
    }
    var explorer = event.target.closest('[data-explore-key]');
    if (explorer) {
      openExplorer(explorer.dataset.exploreKey, explorer.dataset.exploreTitle);
      return;
    }
    if (event.target.closest('[data-switch-context]')) {
      clearSelectedContext();
      return;
    }
    var selector = event.target.closest('[data-select-record]');
    if (selector) {
      selectCommercialRecord(
        selector.dataset.selectRecord,
        selector.dataset.recordId,
        selector.dataset.recordLabel,
        selector.dataset.recordSubtype
      );
      return;
    }
    var prompt = event.target.closest('[data-record-prompt]');
    if (prompt) {
      closeContextWall();
      usePrompt(prompt.dataset.recordPrompt);
    }
  });
  els.recordBody.addEventListener('submit', function (event) {
    var form = event.target.closest('#cx-agent-client-form');
    if (!form) return;
    event.preventDefault();
    var run = function () { saveClientRecord(form); };
    if (typeof window.showConfirm === 'function') {
      window.showConfirm({
        title: 'Salvar alterações do cliente',
        message: 'Os dados serão atualizados no CRM para toda a equipe.',
        confirmText: 'Salvar alterações',
        onConfirm: run
      });
    } else {
      showComposerFeedback('A confirmação não pôde ser exibida. Nenhuma alteração foi salva.', true);
    }
  });
  dock.querySelectorAll('[data-agent-view]').forEach(function (button) {
    button.addEventListener('click', function () {
      switchWorkspaceView(button.dataset.agentView);
    });
  });
  dock.querySelector('.cx-agent-header').addEventListener('click', function (event) {
    if (dock.classList.contains('is-minimized') && !event.target.closest('button')) minimize();
  });
  document.querySelectorAll('[data-agent-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () { switchTab(tab.dataset.agentTab); });
    tab.addEventListener('keydown', function (event) {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      var tabs = Array.from(document.querySelectorAll('[data-agent-tab]'));
      var next = (tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus();
      switchTab(tabs[next].dataset.agentTab);
    });
  });
  els.composer.addEventListener('submit', function (event) {
    event.preventDefault();
    if (state.controller) state.controller.abort();
    else sendMessage();
  });
  els.input.addEventListener('input', function () {
    resizeInput();
    renderComposerSuggestions();
  });
  els.input.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!state.controller) sendMessage();
    }
  });
  els.newConversation.addEventListener('click', function () {
    setMoreOpen(false);
    state.conversationId = '';
    sessionStorage.removeItem('centralx_agent_conversation_id');
    state.context = readBodyContext();
    state.contextSource = 'page';
    state.explorerStack = [];
    state.explorerView = null;
    state.lastQuery = { text: '', entityId: '', message: '' };
    updateContext();
    closeContextWall();
    clearConversationView();
    switchTab('chat');
    els.input.focus();
  });
  if (els.clearConversation) {
    els.clearConversation.addEventListener('click', function () {
      setMoreOpen(false);
      state.lastQuery = { text: '', entityId: '', message: '' };
      clearConversationView();
      switchTab('chat');
      els.input.focus();
    });
  }
  if (els.breadcrumb) {
    els.breadcrumb.addEventListener('click', function (event) {
      var crumb = event.target.closest('[data-breadcrumb-index]');
      if (crumb) popExplorer(Number(crumb.dataset.breadcrumbIndex));
    });
  }
  if (els.recordMoreMenu) {
    els.recordMoreMenu.addEventListener('click', function (event) {
      var copy = event.target.closest('[data-copy-value]');
      if (copy && copy.id !== 'cx-agent-record-copy-link') {
        copyText(copy.dataset.copyValue || '').then(function () {
          showComposerFeedback('Copiado.');
        });
        els.recordMoreMenu.hidden = true;
        return;
      }
      var prompt = event.target.closest('[data-record-prompt]');
      if (prompt) {
        els.recordMoreMenu.hidden = true;
        usePrompt(prompt.dataset.recordPrompt);
        return;
      }
      var selector = event.target.closest('[data-select-record]');
      if (selector) {
        els.recordMoreMenu.hidden = true;
        selectCommercialRecord(
          selector.dataset.selectRecord,
          selector.dataset.recordId,
          selector.dataset.recordLabel,
          selector.dataset.recordSubtype
        );
      }
    });
  }
  if (els.recordMore) {
    els.recordMore.addEventListener('click', function (event) {
      event.stopPropagation();
      if (els.recordMoreMenu) els.recordMoreMenu.hidden = !els.recordMoreMenu.hidden;
      els.recordMore.setAttribute('aria-expanded', String(els.recordMoreMenu && !els.recordMoreMenu.hidden));
    });
  }
  if (els.recordCopyLink) {
    els.recordCopyLink.addEventListener('click', function () {
      copyText(els.recordCopyLink.dataset.copyValue || els.recordOpen.href || '').then(function () {
        showComposerFeedback('Link copiado.');
      });
      if (els.recordMoreMenu) els.recordMoreMenu.hidden = true;
    });
  }
  if (els.recordSwitch) {
    els.recordSwitch.addEventListener('click', function () {
      if (els.recordMoreMenu) els.recordMoreMenu.hidden = true;
      clearSelectedContext();
    });
  }
  els.historyQuery.addEventListener('input', renderHistory);
  els.historyFilter.addEventListener('click', function () {
    state.historyFilter = state.historyFilter === 'all' ? 'all' : 'all';
    els.historyFilter.textContent = 'Todos';
    renderHistory();
  });
  [els.prefHistory, els.prefContext, els.prefNotify].forEach(function (input) {
    input.addEventListener('change', function () {
      state.prefs.saveHistory = els.prefHistory.checked;
      state.prefs.usePageContext = els.prefContext.checked;
      state.prefs.notifications = els.prefNotify.checked;
      savePrefs();
      updateContext();
      if (state.bootstrapped) loadInsights();
    });
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && els.scopeSheet.open) {
      els.scopeSheet.close();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      setOpen(true);
      setSearchOpen(true);
      els.commercialQuery.select();
      return;
    }
    if (event.key === 'Escape' && dock.classList.contains('is-open')) {
      if (!els.moreMenu.hidden) setMoreOpen(false);
      else if (!els.commercialSearch.hidden) setSearchOpen(false);
      else if (!els.settingsPanel.hidden) showSettings(false);
      else if (state.contextWallOpen) closeContextWall();
      else setOpen(false);
    }
  });
  window.addEventListener('centralx:contextchange', function (event) {
    if (state.contextSource === 'agent' && outgoingContext().entity_id) return;
    setAgentContext((event && event.detail) || {}, true, 'page');
  });
  window.addEventListener('centralx:entity-updated', function (event) {
    var detail = (event && event.detail) || {};
    var ctx = outgoingContext();
    if (
      String(detail.entity_type || '').toLowerCase() === String(ctx.entity_type || '').toLowerCase()
      && String(detail.entity_id || '') === String(ctx.entity_id || '')
    ) {
      loadCommercialRecord(true);
      loadInsights();
    }
  });
  els.attach.addEventListener('click', function () { els.fileInput.click(); });
  els.fileInput.addEventListener('change', function () { addFiles(els.fileInput.files); });
  ['dragenter', 'dragover'].forEach(function (name) {
    els.composer.addEventListener(name, function (event) {
      event.preventDefault();
      els.composer.classList.add('is-dragover');
    });
  });
  ['dragleave', 'drop'].forEach(function (name) {
    els.composer.addEventListener(name, function (event) {
      event.preventDefault();
      els.composer.classList.remove('is-dragover');
      if (name === 'drop' && event.dataTransfer) addFiles(event.dataTransfer.files);
    });
  });

  document.addEventListener('click', function () {
    dock.querySelectorAll('.cx-agent-message-menu').forEach(function (menu) { menu.hidden = true; });
    if (els.recordMoreMenu) els.recordMoreMenu.hidden = true;
  });

  if (els.mediaDialog) {
    els.mediaDialog.querySelectorAll('[data-agent-media-close]').forEach(function (button) {
      button.addEventListener('click', function () { els.mediaDialog.close(); });
    });
    els.mediaDialog.addEventListener('click', function (event) {
      if (event.target === els.mediaDialog) els.mediaDialog.close();
    });
    if (els.mediaTabs) {
      els.mediaTabs.addEventListener('click', function (event) {
        var tab = event.target.closest('[data-media-url]');
        if (!tab) return;
        els.mediaTabs.querySelectorAll('[role="tab"]').forEach(function (item) {
          item.setAttribute('aria-selected', item === tab ? 'true' : 'false');
        });
        renderMediaPane({ label: tab.textContent, url: tab.dataset.mediaUrl });
      });
    }
    if (els.mediaCopy) {
      els.mediaCopy.addEventListener('click', function () {
        copyText(els.mediaCopy.dataset.copyValue || '').then(function () {
          showComposerFeedback('URL copiada.');
        });
      });
    }
  }

  applyPrefsUi();
  closeContextWall();
  updateContext();
  renderActions();
  renderComposerSuggestions();
  resizeInput();
}());
