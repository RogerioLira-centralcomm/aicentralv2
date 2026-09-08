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
    activeView: 'conversation'
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
    recordBody: document.getElementById('cx-agent-record-body')
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
      entity_label: data.cxEntityLabel || ''
    };
  }

  function outgoingContext() {
    if (state.prefs.usePageContext) return Object.assign({}, state.context);
    return {
      module: state.context.module || '',
      screen: state.context.screen || '',
      entity_type: '',
      entity_id: '',
      entity_label: ''
    };
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
          var error = new Error(payload.error || 'Não foi possível concluir a operação.');
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

  function entityTypeLabel(type) {
    var map = { cliente: 'Cliente', client: 'Cliente', cotacao: 'Cotação', quote: 'Cotação', pi: 'PI' };
    return map[String(type || '').toLowerCase()] || 'Registro';
  }

  function clientContext() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if ((type === 'cliente' || type === 'client') && ctx.entity_id) return ctx;
    return null;
  }

  function commercialContext() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    return ['cliente', 'client', 'cotacao', 'quote'].indexOf(type) >= 0 && ctx.entity_id
      ? ctx : null;
  }

  function updateContext() {
    var ctx = outgoingContext();
    var hasEntity = Boolean(ctx.entity_id && ctx.entity_label);
    els.contextLabel.textContent = hasEntity ? ctx.entity_label : 'Nenhum registro na tela';
    els.contextType.textContent = hasEntity ? entityTypeLabel(ctx.entity_type) : 'Busque no chat ou abra um cliente';
    els.entity.classList.toggle('is-empty', !hasEntity);
    var icon = els.entity.querySelector('.cx-agent-entity-icon i');
    if (icon) {
      icon.className = 'fa-regular ' + (
        String(ctx.entity_type || '').toLowerCase() === 'cotacao' ? 'fa-file-lines' :
        String(ctx.entity_type || '').toLowerCase() === 'pi' ? 'fa-file-lines' : 'fa-building'
      );
    }
    renderActions();
    loadCommercialRecord();
  }

  function openEntity() {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if ((type === 'cliente' || type === 'client') && ctx.entity_id) {
      window.location.href = '/crm-v3/#cliente=' + encodeURIComponent(ctx.entity_id);
      return;
    }
    switchTab('chat');
    els.input.focus();
  }

  function switchWorkspaceView(name) {
    state.activeView = name === 'record' ? 'record' : 'conversation';
    els.workspace.dataset.activeView = state.activeView;
    dock.querySelectorAll('[data-agent-view]').forEach(function (button) {
      var active = button.dataset.agentView === state.activeView;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
  }

  function setRecordEmpty(message) {
    state.record = null;
    els.recordTitle.textContent = 'Selecione um cliente ou cotação';
    els.recordOpen.hidden = true;
    els.recordBody.innerHTML =
      '<div class="cx-agent-record-empty">' +
      '<i class="fa-regular fa-address-card" aria-hidden="true"></i>' +
      '<strong>O contexto comercial aparece aqui</strong>' +
      '<p>' + escapeHtml(message || 'Busque pelo nome, campanha ou número da cotação para começar.') + '</p>' +
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

  function renderCommercialRecord(data) {
    state.record = data;
    var record = data.record || {};
    els.recordTitle.textContent = record.nome || record.titulo || record.numero_cotacao || 'Registro';
    els.recordOpen.href = data.url || '/crm-v3/';
    els.recordOpen.hidden = false;
    els.recordBody.innerHTML = data.type === 'cliente' ? renderClientRecord(data) : renderQuoteRecord(data);
  }

  function loadCommercialRecord(force) {
    var ctx = outgoingContext();
    var type = String(ctx.entity_type || '').toLowerCase();
    if (!ctx.entity_id || ['cliente', 'client', 'cotacao', 'quote'].indexOf(type) === -1) {
      state.recordKey = '';
      setRecordEmpty();
      return Promise.resolve();
    }
    var key = type + ':' + ctx.entity_id;
    if (!force && key === state.recordKey && state.record) return Promise.resolve();
    state.recordKey = key;
    els.recordTitle.textContent = 'Carregando registro...';
    els.recordOpen.hidden = true;
    els.recordBody.innerHTML = '<div class="cx-agent-record-loading"><i class="fa-solid fa-circle-notch fa-spin"></i><span>Sincronizando com o CRM...</span></div>';
    return api('/api/agent/commercial/record/' + encodeURIComponent(type) + '/' + encodeURIComponent(ctx.entity_id))
      .then(function (payload) { renderCommercialRecord(payload.data || {}); })
      .catch(function (error) {
        state.record = null;
        els.recordBody.innerHTML = '<div class="cx-agent-record-empty is-error"><strong>Registro indisponível</strong><p>' +
          escapeHtml(error.message) + '</p></div>';
      });
  }

  function selectCommercialRecord(type, id, label) {
    window.CentralXAgent.setContext({
      module: type === 'cotacao' ? 'comercial' : 'crm',
      screen: type === 'cotacao' ? 'cotacao' : 'cliente_detalhe',
      entity_type: type,
      entity_id: String(id || ''),
      entity_label: String(label || '')
    });
    els.commercialResults.hidden = true;
    els.commercialQuery.value = '';
    switchWorkspaceView('record');
  }

  function renderCommercialResults(data) {
    var clients = data.clients || [];
    var quotes = data.quotes || [];
    if (!clients.length && !quotes.length) {
      els.commercialResults.innerHTML = '<p class="cx-agent-commercial-empty">Nenhum cliente ou cotação encontrado.</p>';
      els.commercialResults.hidden = false;
      return;
    }
    var groups = [];
    if (clients.length) {
      groups.push('<section><h3>Clientes</h3>' + clients.map(function (item) {
        return '<button type="button" data-search-record="cliente" data-record-id="' + escapeHtml(item.id) +
          '" data-record-label="' + escapeHtml(item.nome || 'Cliente') + '"><i class="fa-regular fa-building"></i>' +
          '<span><strong>' + escapeHtml(item.nome || 'Cliente') + '</strong><small>' +
          escapeHtml([item.responsavel, item.cidade, item.uf].filter(Boolean).join(' · ')) + '</small></span></button>';
      }).join('') + '</section>');
    }
    if (quotes.length) {
      groups.push('<section><h3>Cotações</h3>' + quotes.map(function (item) {
        return '<button type="button" data-search-record="cotacao" data-record-id="' + escapeHtml(item.id) +
          '" data-record-label="' + escapeHtml(item.titulo || item.numero_cotacao || 'Cotação') +
          '"><i class="fa-regular fa-file-lines"></i><span><strong>' +
          escapeHtml(item.titulo || item.numero_cotacao || 'Cotação') + '</strong><small>' +
          escapeHtml([item.cliente_nome, item.status_label, item.valor].filter(Boolean).join(' · ')) + '</small></span></button>';
      }).join('') + '</section>');
    }
    els.commercialResults.innerHTML = groups.join('');
    els.commercialResults.hidden = false;
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
        scope: els.commercialScope.value || 'mine',
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
    dock.classList.toggle('is-settings', open);
    els.settingsPanel.hidden = !open;
    els.workspace.hidden = open;
  }

  function switchTab(name) {
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
    els.input.focus();
  }

  function goCrm(prompt) {
    var client = clientContext();
    if (client) {
      window.location.href = '/crm-v3/#cliente=' + encodeURIComponent(client.entity_id);
    }
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
        syncCommercialScope(els.commercialScope.value);
        state.bootstrapped = true;
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
    var pattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g;
    var cursor = 0;
    var match;
    while ((match = pattern.exec(source))) {
      if (match.index > cursor) parent.appendChild(document.createTextNode(source.slice(cursor, match.index)));
      var token = match[0];
      var node;
      if (token.startsWith('`')) {
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
    var lines = String(content || '').replace(/\r\n/g, '\n').split('\n');
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
    renderDisplay(body, display);
    var actions = document.createElement('div');
    actions.className = 'cx-agent-message-actions';
    var copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'cx-agent-message-action';
    copy.innerHTML = '<i class="fa-regular fa-copy" aria-hidden="true"></i> Copiar';
    copy.addEventListener('click', function () {
      copyText(String(content || '')).then(function () {
        copy.textContent = 'Copiado';
        setTimeout(function () { copy.innerHTML = '<i class="fa-regular fa-copy" aria-hidden="true"></i> Copiar'; }, 1200);
      }).catch(function () {
        copy.textContent = 'Não foi possível copiar';
      });
    });
    actions.appendChild(copy);
    wrapper.appendChild(actions);
  }

  function appendMessage(role, content, display, extraClass) {
    var welcome = els.messages.querySelector('.cx-agent-welcome');
    if (welcome) welcome.hidden = true;
    var wrapper = document.createElement('article');
    wrapper.className = 'cx-agent-message is-' + role + (extraClass ? ' ' + extraClass : '');
    var body = document.createElement('div');
    body.className = 'cx-agent-message-body';
    if (role === 'assistant' && !extraClass) body.appendChild(renderMarkdown(content));
    else body.textContent = content || '';
    wrapper.appendChild(body);
    if (role === 'assistant' && !extraClass) {
      addAssistantMessageExtras(wrapper, body, content, display);
    } else {
      renderAttachmentSummary(body, display && display.attachments);
      renderDisplay(body, display);
    }
    els.messages.appendChild(wrapper);
    els.messages.scrollTop = els.messages.scrollHeight;
    return wrapper;
  }

  function appendProgressiveMessage(content, display) {
    var text = String(content || '');
    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion || text.length < 24) {
      appendMessage('assistant', text, display);
      return Promise.resolve();
    }
    var wrapper = appendMessage('assistant', '', null, 'is-progressive');
    var body = wrapper.querySelector('.cx-agent-message-body');
    var visual = document.createElement('span');
    visual.className = 'cx-agent-progressive-text';
    visual.setAttribute('aria-hidden', 'true');
    var cursor = document.createElement('i');
    cursor.className = 'cx-agent-progressive-cursor';
    cursor.setAttribute('aria-hidden', 'true');
    body.setAttribute('aria-label', text);
    body.append(visual, cursor);
    var chunkSize = Math.max(2, Math.ceil(text.length / 95));
    var position = 0;
    return new Promise(function (resolve) {
      function reveal() {
        position = Math.min(text.length, position + chunkSize);
        visual.textContent = text.slice(0, position);
        els.messages.scrollTop = els.messages.scrollHeight;
        if (position < text.length) {
          window.setTimeout(reveal, 18);
          return;
        }
        wrapper.classList.remove('is-progressive');
        body.removeAttribute('aria-label');
        body.replaceChildren(renderMarkdown(text));
        addAssistantMessageExtras(wrapper, body, text, display);
        els.messages.scrollTop = els.messages.scrollHeight;
        resolve();
      }
      reveal();
    });
  }

  function appendLoadingProgress() {
    var steps = [
      ['Consultando dados', 'Buscando informações comerciais e contexto da conversa.'],
      ['Organizando contexto', 'Relacionando cliente, cotação e histórico recente.'],
      ['Preparando resposta', 'Estruturando uma resposta prática para você.']
    ];
    var node = appendMessage('assistant', '', null, 'is-loading');
    var body = node.querySelector('.cx-agent-message-body');
    var index = 0;
    function renderStep() {
      var step = steps[Math.min(index, steps.length - 1)];
      body.innerHTML = '<span class="cx-agent-thinking"><i aria-hidden="true"></i><span><strong>' +
        escapeHtml(step[0]) + '</strong><small>' + escapeHtml(step[1]) + '</small></span></span>';
      index += 1;
    }
    renderStep();
    state.loadingTimer = window.setInterval(renderStep, 1350);
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

  function looksOpen(text) {
    var value = String(text || '').toLowerCase();
    return /andamento|abert|enviad|rascunho|aprovad/.test(value);
  }

  function renderDisplay(parent, display) {
    var groups = display && Array.isArray(display.results) ? display.results : [];
    groups.forEach(function (group) {
      var results = document.createElement('div');
      results.className = 'cx-agent-results';
      var items = group.items || [];
      items.slice(0, 8).forEach(function (item) {
        var card = document.createElement('div');
        card.className = 'cx-agent-result';
        var title = document.createElement('strong');
        title.textContent = item.title || 'Resultado';
        card.appendChild(title);
        if (item.subtitle || item.period || item.status) {
          var meta = document.createElement('span');
          var status = item.status || item.subtitle || '';
          meta.className = 'cx-agent-result-meta';
          if (looksOpen(status)) {
            var dot = document.createElement('i');
            dot.className = 'cx-agent-live-dot';
            meta.appendChild(dot);
            meta.appendChild(document.createTextNode('Em andamento'));
          } else {
            meta.textContent = item.subtitle || '';
          }
          card.appendChild(meta);
        }
        if (item.period) {
          var period = document.createElement('span');
          period.textContent = item.period;
          card.appendChild(period);
        } else if (item.responsible) {
          var line = document.createElement('span');
          line.textContent = item.responsible;
          card.appendChild(line);
        }
        results.appendChild(card);
      });
      var more = (group.links && group.links[0]) || (items.length > 8 ? { url: (items[0] || {}).url, label: 'Ver todas' } : null);
      if (more && safeInternalUrl(more.url || (items[0] || {}).url)) {
        var link = document.createElement('a');
        link.href = more.url || items[0].url;
        link.textContent = (more.label || 'Ver todas') + ' →';
        results.appendChild(link);
      }
      parent.appendChild(results);
    });
  }

  function loadConversation(id) {
    return api('/api/agent/conversations/' + encodeURIComponent(id))
      .then(function (payload) {
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
    setStatus(sending ? 'Analisando…' : 'Online', true);
  }

  function sendMessage() {
    var content = els.input.value.trim();
    if (!content && !state.attachments.length) return;
    if (!content) content = 'Analise os arquivos anexados e apresente os pontos mais importantes.';
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
    setStatus('Analisando...', true);
    var extracting = showExtract(outgoingAttachments);
    var loading = extracting ? null : appendLoadingProgress();
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
      return appendProgressiveMessage(message.content, message.display);
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
    setContext: function (patch) {
      state.context = Object.assign({}, state.context, patch || {});
      Object.keys(state.context).forEach(function (key) {
        state.context[key] = String(state.context[key] || '').slice(0, key === 'entity_label' ? 200 : 80);
      });
      updateContext();
      if (state.bootstrapped) loadInsights();
    },
    getContext: function () { return Object.assign({}, state.context); }
  };

  trigger.addEventListener('click', function () { setOpen(true); });
  els.close.addEventListener('click', function () { setOpen(false); });
  els.minimize.addEventListener('click', minimize);
  els.settings.addEventListener('click', function () { showSettings(true); });
  els.settingsBack.addEventListener('click', function () { showSettings(false); });
  els.entity.addEventListener('click', openEntity);
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
        button.dataset.recordLabel
      );
    }
  });
  els.recordBody.addEventListener('click', function (event) {
    var selector = event.target.closest('[data-select-record]');
    if (selector) {
      selectCommercialRecord(
        selector.dataset.selectRecord,
        selector.dataset.recordId,
        selector.dataset.recordLabel
      );
      return;
    }
    var prompt = event.target.closest('[data-record-prompt]');
    if (prompt) {
      switchWorkspaceView('conversation');
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
      run();
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
  els.input.addEventListener('input', resizeInput);
  els.input.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!state.controller) sendMessage();
    }
  });
  els.newConversation.addEventListener('click', function () {
    state.conversationId = '';
    sessionStorage.removeItem('centralx_agent_conversation_id');
    clearConversationView();
    switchTab('chat');
    els.input.focus();
  });
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
      els.commercialQuery.focus();
      els.commercialQuery.select();
      return;
    }
    if (event.key === 'Escape' && dock.classList.contains('is-open')) {
      if (!els.commercialResults.hidden) els.commercialResults.hidden = true;
      else if (!els.settingsPanel.hidden) showSettings(false);
      else setOpen(false);
    }
  });
  window.addEventListener('centralx:contextchange', function (event) {
    window.CentralXAgent.setContext((event && event.detail) || {});
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

  applyPrefsUi();
  updateContext();
  renderActions();
  resizeInput();
}());
