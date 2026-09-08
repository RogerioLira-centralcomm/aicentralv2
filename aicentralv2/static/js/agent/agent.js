(function () {
  'use strict';

  var dock = document.getElementById('cx-agent-dock');
  var trigger = document.getElementById('cx-agent-trigger');
  if (!dock || !trigger) return;

  var state = {
    bootstrapped: false,
    csrf: '',
    conversationId: sessionStorage.getItem('centralx_agent_conversation_id') || '',
    context: readBodyContext(),
    suggestions: [],
    attachments: [],
    controller: null,
    lastFocus: null
  };

  var els = {
    status: document.getElementById('cx-agent-status'),
    context: document.getElementById('cx-agent-context'),
    contextLabel: document.getElementById('cx-agent-context-label'),
    messages: document.getElementById('cx-agent-messages'),
    prompts: document.getElementById('cx-agent-quick-prompts'),
    actions: document.getElementById('cx-agent-actions'),
    suggestions: document.getElementById('cx-agent-suggestions'),
    history: document.getElementById('cx-agent-history'),
    input: document.getElementById('cx-agent-input'),
    composer: document.getElementById('cx-agent-composer'),
    send: document.getElementById('cx-agent-send'),
    attach: document.getElementById('cx-agent-attach'),
    fileInput: document.getElementById('cx-agent-file-input'),
    attachments: document.getElementById('cx-agent-attachments'),
    feedback: document.getElementById('cx-agent-composer-feedback'),
    characterCount: document.getElementById('cx-agent-character-count'),
    modelLabel: document.getElementById('cx-agent-model-label'),
    userName: document.getElementById('cx-agent-user-name'),
    close: document.getElementById('cx-agent-close'),
    minimize: document.getElementById('cx-agent-minimize'),
    newConversation: document.getElementById('cx-agent-new-conversation')
  };

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

  function setStatus(text) {
    els.status.textContent = text;
  }

  function updateContext() {
    var label = state.context.entity_label ||
      [state.context.module, state.context.screen].filter(Boolean).join(' · ') ||
      'CentralX';
    els.contextLabel.textContent = label;
    els.context.hidden = !label;
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
      dock.classList.remove('is-open', 'is-minimized');
      dock.setAttribute('aria-hidden', 'true');
      trigger.setAttribute('aria-expanded', 'false');
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
    if (name === 'suggestions') loadSuggestions();
  }

  function button(label, icon, className, onClick) {
    var item = document.createElement('button');
    item.type = 'button';
    item.className = className;
    var glyph = document.createElement('i');
    glyph.className = 'fa-solid ' + (icon || 'fa-arrow-right');
    glyph.setAttribute('aria-hidden', 'true');
    var text = document.createElement('span');
    text.textContent = label;
    item.append(glyph, text);
    item.addEventListener('click', onClick);
    return item;
  }

  function usePrompt(prompt) {
    switchTab('chat');
    els.input.value = prompt;
    resizeInput();
    els.input.focus();
  }

  function renderSuggestions(items) {
    state.suggestions = items || [];
    els.prompts.replaceChildren();
    els.suggestions.replaceChildren();
    state.suggestions.forEach(function (item) {
      els.prompts.appendChild(button(item.label, item.icon, 'cx-agent-prompt', function () {
        usePrompt(item.prompt);
      }));
      els.suggestions.appendChild(button(item.label, item.icon, 'cx-agent-suggestion', function () {
        usePrompt(item.prompt);
      }));
    });
    if (!state.suggestions.length) {
      els.suggestions.appendChild(empty('Nenhuma sugestão para este contexto.'));
    }
    renderActions();
  }

  function renderActions() {
    var items = [
      { label: 'Buscar cliente', prompt: 'Busque um cliente pelo nome.', icon: 'fa-magnifying-glass' },
      { label: 'Listar contatos', prompt: 'Liste os contatos de um cliente.', icon: 'fa-address-book' },
      { label: 'Consultar atividades', prompt: 'Liste as atividades de um cliente.', icon: 'fa-calendar-check' },
      { label: 'Consultar cotações', prompt: 'Liste as cotações de um cliente.', icon: 'fa-file-invoice-dollar' },
      { label: 'Analisar um documento', prompt: 'Vou anexar um documento. Analise, resuma e destaque riscos e próximos passos.', icon: 'fa-file-lines' },
      { label: 'Organizar em tabela', prompt: 'Organize as informações abaixo em uma tabela clara e comparável:', icon: 'fa-table' },
      { label: 'Redigir e-mail', prompt: 'Redija um e-mail profissional, objetivo e cordial sobre:', icon: 'fa-envelope' },
      { label: 'Criar plano de ação', prompt: 'Transforme o contexto abaixo em um plano de ação com responsáveis, prioridades e prazos:', icon: 'fa-list-check' }
    ];
    els.actions.replaceChildren();
    items.forEach(function (item) {
      els.actions.appendChild(button(item.label, item.icon, 'cx-agent-action', function () {
        usePrompt(item.prompt);
      }));
    });
  }

  function empty(text) {
    var node = document.createElement('div');
    node.className = 'cx-agent-empty';
    node.textContent = text;
    return node;
  }

  function bootstrap(force) {
    if (state.bootstrapped && !force) return Promise.resolve();
    setStatus('Conectando...');
    return api('/api/agent/bootstrap?' + contextQuery(state.context))
      .then(function (payload) {
        var data = payload.data || {};
        state.csrf = data.csrf_token || '';
        state.bootstrapped = true;
        els.userName.textContent = (data.user && data.user.name) || 'tudo bem?';
        if (data.model) {
          els.modelLabel.textContent = data.model === 'openai/gpt-4o-mini' ? 'GPT-4o mini' : data.model.split('/').pop();
        }
        renderSuggestions(data.suggestions || []);
        if (data.active_conversation) {
          state.conversationId = String(data.active_conversation.id);
          sessionStorage.setItem('centralx_agent_conversation_id', state.conversationId);
          return loadConversation(state.conversationId);
        }
        setStatus('Pronto para ajudar');
      })
      .catch(function (error) {
        setStatus('Indisponível');
        appendMessage('assistant', error.message || 'Agente temporariamente indisponível.');
      });
  }

  function ensureConversation() {
    if (state.conversationId) return Promise.resolve(state.conversationId);
    return api('/api/agent/conversations', {
      method: 'POST',
      body: JSON.stringify({ context: state.context })
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
        var heading = document.createElement('h' + headingMatch[1].length);
        appendInline(heading, headingMatch[2]);
        root.appendChild(heading);
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
    renderAttachmentSummary(body, display && display.attachments);
    renderDisplay(body, display);
    if (role === 'assistant' && !extraClass) {
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
    els.messages.appendChild(wrapper);
    els.messages.scrollTop = els.messages.scrollHeight;
    return wrapper;
  }

  function safeInternalUrl(url) {
    return typeof url === 'string' && /^\/(?!\/)[a-zA-Z0-9/_?#=&.%+-]*$/.test(url);
  }

  function renderDisplay(parent, display) {
    var groups = display && Array.isArray(display.results) ? display.results : [];
    groups.forEach(function (group) {
      var results = document.createElement('div');
      results.className = 'cx-agent-results';
      if (group.title) {
        var heading = document.createElement('strong');
        heading.textContent = group.title;
        results.appendChild(heading);
      }
      (group.items || []).slice(0, 20).forEach(function (item) {
        var card = document.createElement('div');
        card.className = 'cx-agent-result';
        var title = document.createElement('strong');
        title.textContent = item.title || 'Resultado';
        card.appendChild(title);
        var details = [item.subtitle, item.responsible ? 'Responsável: ' + item.responsible : ''].filter(Boolean);
        details.forEach(function (value) {
          var line = document.createElement('span');
          line.textContent = value;
          card.appendChild(line);
        });
        if (safeInternalUrl(item.url)) {
          var link = document.createElement('a');
          link.href = item.url;
          link.textContent = 'Abrir registro';
          card.appendChild(link);
        }
        results.appendChild(card);
      });
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
        setStatus('Pronto para ajudar');
      })
      .catch(function () {
        state.conversationId = '';
        sessionStorage.removeItem('centralx_agent_conversation_id');
        clearConversationView();
        setStatus('Pronto para ajudar');
      });
  }

  function loadHistory() {
    els.history.replaceChildren(empty('Carregando histórico...'));
    api('/api/agent/history?page=1').then(function (payload) {
      els.history.replaceChildren();
      (payload.data || []).forEach(function (conversation) {
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'cx-agent-history-item';
        var title = document.createElement('strong');
        title.textContent = conversation.title || 'Nova conversa';
        var date = document.createElement('span');
        date.textContent = conversation.updated_at ? new Date(conversation.updated_at).toLocaleString('pt-BR') : '';
        item.append(title, date);
        item.addEventListener('click', function () {
          state.conversationId = String(conversation.id);
          sessionStorage.setItem('centralx_agent_conversation_id', state.conversationId);
          loadConversation(state.conversationId).then(function () { switchTab('chat'); });
        });
        els.history.appendChild(item);
      });
      if (!(payload.data || []).length) els.history.appendChild(empty('Nenhuma conversa ainda.'));
    }).catch(function (error) {
      els.history.replaceChildren(empty(error.message));
    });
  }

  function loadSuggestions() {
    api('/api/agent/suggestions?' + contextQuery(state.context)).then(function (payload) {
      renderSuggestions(payload.data || []);
    }).catch(function () {});
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
    els.characterCount.textContent = els.input.value.length.toLocaleString('pt-BR') + ' / 12.000';
  }

  function setSending(sending) {
    els.input.disabled = sending;
    els.attach.disabled = sending;
    els.fileInput.disabled = sending;
    els.send.disabled = false;
    els.send.setAttribute('aria-label', sending ? 'Cancelar consulta' : 'Enviar mensagem');
    els.send.querySelector('i').className = sending ? 'fa-solid fa-stop' : 'fa-solid fa-arrow-up';
    setStatus(sending ? 'Analisando...' : 'Pronto para ajudar');
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
    var loading = appendMessage('assistant', 'Consultando informações…', null, 'is-loading');
    state.controller = new AbortController();
    ensureConversation().then(function (id) {
      return api('/api/agent/conversations/' + encodeURIComponent(id) + '/messages', {
        method: 'POST',
        signal: state.controller.signal,
        body: JSON.stringify({
          message: content,
          context: state.context,
          attachments: outgoingAttachments.map(function (file) {
            return { name: file.name, mime: file.mime, size: file.size, data: file.data };
          })
        })
      });
    }).then(function (payload) {
      loading.remove();
      var message = payload.data.message;
      appendMessage('assistant', message.content, message.display);
    }).catch(function (error) {
      loading.remove();
      var errorMessage = error.name === 'AbortError' ? 'Consulta cancelada.' : error.message;
      if (error.requestId) errorMessage += '\n\nReferência técnica: `' + error.requestId + '`';
      appendMessage('assistant', errorMessage);
    }).finally(function () {
      state.controller = null;
      setSending(false);
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
      if (state.bootstrapped) loadSuggestions();
    },
    getContext: function () { return Object.assign({}, state.context); }
  };

  trigger.addEventListener('click', function () { setOpen(true); });
  els.close.addEventListener('click', function () { setOpen(false); });
  els.minimize.addEventListener('click', minimize);
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
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && dock.classList.contains('is-open')) setOpen(false);
  });
  window.addEventListener('centralx:contextchange', function (event) {
    window.CentralXAgent.setContext((event && event.detail) || {});
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

  updateContext();
  renderActions();
  resizeInput();
}());
