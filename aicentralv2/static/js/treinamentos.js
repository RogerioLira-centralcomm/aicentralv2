(function () {
  'use strict';

  var root = document.querySelector('[data-training-studio]');
  if (!root) return;

  // FUTURO: quebra do HTML em slides, canvas com drag-and-drop e export PPTX/PDF.
  var state = {
    treinamentoId: null,
    sessaoId: null,
    selection: '',
    range: null,
    pendingFonteId: null,
    lastImage: null,
    lastEdit: '',
    lastResearch: '',
    guia: {},
    sessoes: [],
    saving: null,
    enriching: false
  };

  var editor = document.getElementById('tsEditor');
  var costEl = document.getElementById('tsCost');
  var selectionCard = document.getElementById('tsSelectionCard');
  var selectionText = document.getElementById('tsSelectionText');
  var importCard = document.getElementById('tsImportCard');
  var thumbs = document.getElementById('tsThumbs');
  var chatLog = document.getElementById('tsChatLog');

  function api(path, options) {
    options = options || {};
    return fetch('/parametros/api' + path, {
      method: options.method || 'GET',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok || data.success === false) {
          throw new Error(data.error || 'Não foi possível concluir a operação.');
        }
        return data.data;
      });
    });
  }

  function notify(message, error) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, error ? 'error' : 'success');
      return;
    }
    window.alert(message);
  }

  function rememberRange() {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    var range = sel.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;
    state.range = range;
    state.selection = sel.toString();
  }

  function restoreRange() {
    if (!state.range) return;
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(state.range);
  }

  function setBusy(busy) {
    root.classList.toggle('ts-busy', Boolean(busy));
  }

  function renderCost(consumo, total) {
    consumo = consumo || {};
    total = total || {};
    var label = consumo.cost_brl_label || 'R$ 0,00';
    var totalLabel = total.cost_brl_label || 'R$ 0,00';
    var parts = Object.keys(consumo.by_kind || {}).map(function (kind) {
      return kind + ': ' + (consumo.by_kind[kind].cost_brl_label || 'R$ 0,00');
    });
    costEl.innerHTML = 'Sessão <strong>' + label + '</strong> <span id="tsCostTotal">Treino ' + totalLabel + '</span>';
    costEl.title = parts.length ? parts.join(' · ') : 'Nenhuma chamada de IA nesta sessão';
  }

  function renderSessions(sessoes) {
    var list = document.getElementById('tsSessionList');
    list.innerHTML = '';
    state.sessoes = sessoes || [];
    state.sessoes.forEach(function (item) {
      var li = document.createElement('li');
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'ts-session' + (item.id === state.sessaoId ? ' is-active' : '');
      button.dataset.sessaoId = String(item.id);
      var who = (item.facilitadores || []).join(', ');
      button.innerHTML =
        '<small>' + escapeHtml((item.horario_inicio || '') + '–' + (item.horario_fim || '')) + '</small>' +
        '<strong>' + escapeHtml(item.titulo) + '</strong>' +
        (who ? '<small>' + escapeHtml(who) + '</small>' : '');
      button.addEventListener('click', function () {
        openSession(item.id);
      });
      li.appendChild(button);
      list.appendChild(li);
    });
  }

  function openSession(sessaoId) {
    if (!sessaoId || sessaoId === state.sessaoId) return;
    Promise.resolve(saveDocument()).then(function () {
      return api('/sessoes/' + sessaoId);
    }).then(function (sessao) {
      applySessao(sessao);
      renderSessions(state.sessoes);
      chatLog.innerHTML = '';
      (sessao.mensagens || []).forEach(function (item) {
        appendChat(item.role, item.content, item.tool_used);
      });
    }).catch(function (error) {
      notify(error.message, true);
    });
  }

  function applySessao(sessao) {
    state.sessaoId = sessao.id;
    state.imagens = sessao.imagens || [];
    editor.innerHTML = sessao.conteudo_html || '';
    renderCost(sessao.consumo, state.consumoTreino);
    renderThumbs(state.imagens);
  }

  function renderSwatches(guia) {
    var box = document.getElementById('tsSwatches');
    box.innerHTML = '';
    ((guia && guia.palette) || []).forEach(function (item) {
      var swatch = document.createElement('i');
      swatch.style.background = item.hex || '#071422';
      swatch.title = item.name || item.hex;
      box.appendChild(swatch);
    });
  }

  function renderThumbs(imagens) {
    thumbs.innerHTML = '';
    (imagens || []).forEach(function (item) {
      var button = document.createElement('button');
      button.type = 'button';
      button.title = item.prompt || 'Inserir imagem';
      button.innerHTML = '<img src="' + item.asset_url + '" alt="">';
      button.addEventListener('click', function () {
        insertImage(item.asset_url);
      });
      thumbs.appendChild(button);
    });
  }

  function appendChat(role, text, tool) {
    var article = document.createElement('article');
    article.innerHTML =
      '<strong>' + (role === 'user' ? 'Você' : 'Agente') + '</strong>' +
      (tool ? ' <span class="ts-badge" data-tool="' + tool + '">' + tool + '</span>' : '') +
      '<div>' + escapeHtml(text || '') + '</div>';
    chatLog.appendChild(article);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function hidePanels() {
    document.getElementById('tsPanelEdit').hidden = true;
    document.getElementById('tsPanelResearch').hidden = true;
    document.getElementById('tsPanelImage').hidden = true;
    root.querySelectorAll('.ts-actions button').forEach(function (button) {
      button.classList.remove('is-active');
    });
  }

  function showPanel(name) {
    hidePanels();
    var map = {
      reescrever: 'tsPanelEdit',
      expandir: 'tsPanelEdit',
      resumir: 'tsPanelEdit',
      ajustar_tom: 'tsPanelEdit',
      continuar: 'tsPanelEdit',
      pesquisar: 'tsPanelResearch',
      gerar_imagem: 'tsPanelImage'
    };
    var id = map[name];
    if (id) document.getElementById(id).hidden = false;
    var button = root.querySelector('.ts-actions [data-action="' + name + '"]');
    if (button) button.classList.add('is-active');
  }

  function updateSelectionUi() {
    var has = Boolean(state.selection && state.selection.trim());
    selectionCard.hidden = !has;
    selectionText.textContent = state.selection;
    root.querySelectorAll('.ts-actions button, #tsMoreMenu button').forEach(function (button) {
      button.disabled = !has && button.getAttribute('data-action') !== 'continuar';
    });
    if (has) {
      var prompt = document.getElementById('tsImagePrompt');
      if (!prompt.value.trim()) {
        prompt.value = 'Ilustração minimalista sobre: ' + state.selection.trim();
      }
    }
  }

  function documentHtml() {
    return editor.innerHTML;
  }

  function scheduleSave() {
    clearTimeout(state.saving);
    state.saving = setTimeout(saveDocument, 900);
  }

  function saveDocument() {
    if (!state.sessaoId) return Promise.resolve();
    return api('/sessoes/' + state.sessaoId, {
      method: 'PATCH',
      body: { conteudo_html: documentHtml() }
    }).catch(function (error) {
      notify(error.message, true);
    });
  }

  function replaceSelection(html) {
    restoreRange();
    if (!state.range) {
      editor.insertAdjacentHTML('beforeend', html);
    } else {
      state.range.deleteContents();
      var node = document.createElement('div');
      node.innerHTML = html;
      var frag = document.createDocumentFragment();
      while (node.firstChild) frag.appendChild(node.firstChild);
      state.range.insertNode(frag);
    }
    scheduleSave();
  }

  function insertImage(url) {
    replaceSelection(
      '<figure class="ts-inline-image"><img src="' + url + '" alt=""></figure>'
    );
  }

  function payload(extra) {
    extra = extra || {};
    extra.selection = state.selection;
    extra.document = editor.innerText || '';
    return extra;
  }

  function runAction(action, extra) {
    if (!state.sessaoId) return;
    if (action === 'gerar_imagem' && !extra) {
      showPanel(action);
      return;
    }
    setBusy(true);
    showPanel(action);
    api('/sessoes/' + state.sessaoId + '/agente', {
      method: 'POST',
      body: payload(Object.assign({ action: action }, extra || {}))
    }).then(function (data) {
      renderCost(data.consumo, state.consumoTreino);
      appendChat('assistant', data.content, data.tool_used);
      if (action === 'pesquisar') {
        state.lastResearch = data.content || '';
        document.getElementById('tsResearchPreview').textContent = state.lastResearch;
      } else if (action === 'gerar_imagem') {
        if (data.image) {
          state.lastImage = data.image;
          document.getElementById('tsImagePreview').src = data.image.asset_url;
          document.getElementById('tsImageResult').hidden = false;
          state.imagens = (state.imagens || []).concat([data.image]);
          renderThumbs(state.imagens);
        }
      } else {
        state.lastEdit = data.content || '';
        document.getElementById('tsPanelEditTitle').textContent = titleFor(action);
        document.getElementById('tsEditPreview').textContent = state.lastEdit;
      }
    }).catch(function (error) {
      notify(error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  }

  function titleFor(action) {
    return {
      reescrever: 'Reescrever',
      expandir: 'Expandir',
      resumir: 'Resumir',
      ajustar_tom: 'Ajustar tom',
      continuar: 'Continuar'
    }[action] || 'Edição';
  }

  function bootstrap() {
    api('/treinamentos/bootstrap').then(function (data) {
      state.treinamentoId = data.treinamento.id;
      state.guia = data.treinamento.guia_estilo || data.sessao.guia_estilo || {};
      state.consumoTreino = data.consumo_treinamento || {};
      applySessao(data.sessao);
      renderSessions(data.sessoes || []);
      renderSwatches(state.guia);
      chatLog.innerHTML = '';
      (data.mensagens || []).forEach(function (item) {
        appendChat(item.role, item.content, item.tool_used);
      });
      if (data.pesquisa_pendente) enrichChannels(true);
    }).catch(function (error) {
      notify(error.message, true);
    });
  }

  function enrichChannels(silent) {
    if (!state.treinamentoId || state.enriching) return;
    state.enriching = true;
    var button = document.getElementById('tsEnrichBtn');
    button.disabled = true;
    button.textContent = 'Enriquecendo canais…';
    setBusy(true);
    api('/treinamentos/' + state.treinamentoId + '/pesquisar-canais', { method: 'POST' })
      .then(function (data) {
        state.consumoTreino = data.consumo_treinamento || state.consumoTreino;
        if (data.sessao && data.sessao.id === state.sessaoId) {
          applySessao(data.sessao);
        }
        if (!silent) notify('Canais atualizados com pesquisa e logos.');
      })
      .catch(function (error) {
        notify(error.message, true);
      })
      .finally(function () {
        state.enriching = false;
        button.disabled = false;
        button.textContent = 'Enriquecer canais';
        setBusy(false);
      });
  }

  editor.addEventListener('mouseup', rememberRange);
  editor.addEventListener('keyup', rememberRange);
  editor.addEventListener('input', scheduleSave);
  document.addEventListener('selectionchange', function () {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    var range = sel.getRangeAt(0);
    if (!editor.contains(range.commonAncestorContainer)) return;
    rememberRange();
    updateSelectionUi();
  });

  root.querySelectorAll('.ts-format [data-cmd]').forEach(function (button) {
    button.addEventListener('click', function () {
      restoreRange();
      var cmd = button.getAttribute('data-cmd');
      if (cmd === 'createLink') {
        var href = window.prompt('URL do link');
        if (href) document.execCommand('createLink', false, href);
      } else {
        document.execCommand(cmd, false, null);
      }
      scheduleSave();
    });
  });

  document.getElementById('tsBlock').addEventListener('change', function (event) {
    restoreRange();
    document.execCommand('formatBlock', false, event.target.value);
    scheduleSave();
  });

  root.querySelectorAll('[data-action]').forEach(function (button) {
    button.addEventListener('click', function () {
      document.getElementById('tsMoreMenu').hidden = true;
      runAction(button.getAttribute('data-action'));
    });
  });

  document.getElementById('tsMoreToggle').addEventListener('click', function () {
    var menu = document.getElementById('tsMoreMenu');
    menu.hidden = !menu.hidden;
  });

  document.getElementById('tsApplyEdit').addEventListener('click', function () {
    if (!state.lastEdit) return;
    replaceSelection('<p>' + escapeHtml(state.lastEdit).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') + '</p>');
  });

  document.getElementById('tsApplyResearch').addEventListener('click', function () {
    if (!state.lastResearch) return;
    replaceSelection('<p>' + escapeHtml(state.lastResearch).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') + '</p>');
  });

  document.getElementById('tsGenerateImage').addEventListener('click', function () {
    runAction('gerar_imagem', { prompt: document.getElementById('tsImagePrompt').value });
  });

  document.getElementById('tsInsertImage').addEventListener('click', function () {
    if (state.lastImage) insertImage(state.lastImage.asset_url);
  });

  document.getElementById('tsImportBtn').addEventListener('click', function () {
    var url = document.getElementById('tsImportUrl').value.trim();
    if (!url || !state.sessaoId) return;
    setBusy(true);
    api('/sessoes/' + state.sessaoId + '/importar-url', {
      method: 'POST',
      body: { url: url }
    }).then(function (data) {
      state.pendingFonteId = data.fonte.id;
      document.getElementById('tsImportTitle').textContent = data.fonte.titulo || data.fonte.url;
      document.getElementById('tsImportSummary').textContent = data.fonte.resumo;
      importCard.hidden = false;
      renderCost(data.consumo, state.consumoTreino);
    }).catch(function (error) {
      notify(error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  });

  document.getElementById('tsImportApply').addEventListener('click', function () {
    if (!state.pendingFonteId) return;
    api('/sessoes/' + state.sessaoId + '/fontes/' + state.pendingFonteId + '/aplicar', {
      method: 'POST'
    }).then(function () {
      importCard.hidden = true;
      notify('Fonte adicionada ao contexto da sessão.');
    }).catch(function (error) {
      notify(error.message, true);
    });
  });

  document.getElementById('tsImportDismiss').addEventListener('click', function () {
    importCard.hidden = true;
    state.pendingFonteId = null;
  });

  document.getElementById('tsChatForm').addEventListener('submit', function (event) {
    event.preventDefault();
    var input = document.getElementById('tsChatInput');
    var message = input.value.trim();
    if (!message || !state.sessaoId) return;
    appendChat('user', message);
    input.value = '';
    setBusy(true);
    api('/sessoes/' + state.sessaoId + '/agente', {
      method: 'POST',
      body: payload({ message: message })
    }).then(function (data) {
      renderCost(data.consumo, state.consumoTreino);
      appendChat('assistant', data.content, data.tool_used);
      if (data.image) {
        state.lastImage = data.image;
        showPanel('gerar_imagem');
        document.getElementById('tsImagePreview').src = data.image.asset_url;
        document.getElementById('tsImageResult').hidden = false;
      } else if (data.tool_used === 'pesquisa') {
        state.lastResearch = data.content;
        showPanel('pesquisar');
        document.getElementById('tsResearchPreview').textContent = data.content;
      } else {
        state.lastEdit = data.content;
        showPanel('reescrever');
        document.getElementById('tsEditPreview').textContent = data.content;
      }
    }).catch(function (error) {
      notify(error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  });

  document.getElementById('tsEnrichBtn').addEventListener('click', function () {
    enrichChannels(false);
  });

  bootstrap();
})();
