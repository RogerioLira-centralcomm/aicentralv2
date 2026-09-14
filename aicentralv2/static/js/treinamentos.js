(function () {
  'use strict';

  var root = document.querySelector('[data-training-studio]');
  if (!root) return;

  // FUTURO: canvas com drag-and-drop e export PPTX/PDF.
  var state = {
    treinamentoId: null,
    sessaoId: null,
    sessaoSlug: '',
    selection: '',
    range: null,
    pendingFonteId: null,
    pendingImport: null,
    lastImage: null,
    lastEdit: '',
    lastResearch: '',
    guia: {},
    sessoes: [],
    saving: null,
    enriching: false,
    notas: {}
  };

  var editor = document.getElementById('tsEditor');
  var costEl = document.getElementById('tsCost');
  var selectionCard = document.getElementById('tsSelectionCard');
  var selectionText = document.getElementById('tsSelectionText');
  var importModal = document.getElementById('tsImportModal');
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
      return response.text().then(function (text) {
        var data = {};
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (error) {
            throw new Error(
              response.ok
                ? 'A resposta do servidor não pôde ser lida.'
                : 'Não foi possível concluir a operação.'
            );
          }
        }
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
      button.className = 'ts-session' + (sameSession(item.id) ? ' is-active' : '');
      button.dataset.sessaoId = String(item.id);
      button.dataset.tipo = item.tipo || 'bloco';
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

  function sameSession(sessaoId) {
    return Number(sessaoId) > 0 && Number(sessaoId) === Number(state.sessaoId);
  }

  function openSession(sessaoId) {
    if (!sessaoId || sameSession(sessaoId)) return;
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
    state.sessaoSlug = sessao.slug || '';
    state.imagens = sessao.imagens || [];
    state.notas = sessao.notas_instrutor || {};
    editor.innerHTML = sessao.conteudo_html || '';
    renderCost(sessao.consumo, state.consumoTreino);
    renderThumbs(state.imagens);
    renderNotes(state.notas);
    renderFontes(sessao.fontes || []);
    markFocusPage();
    var project = document.getElementById('tsProjectBtn');
    if (project) {
      project.href = state.sessaoSlug
        ? '/parametros/treinamentos/projetar/' + encodeURIComponent(state.sessaoSlug)
        : '/parametros/treinamentos/projetar';
    }
  }

  function renderFontes(fontes) {
    var list = document.getElementById('tsFontes');
    if (!list) return;
    list.innerHTML = '';
    (fontes || []).forEach(function (item) {
      var li = document.createElement('li');
      li.innerHTML = '<strong>' + escapeHtml(item.titulo || item.url || 'Fonte') + '</strong>' +
        (item.resumo ? '<span>' + escapeHtml(String(item.resumo).slice(0, 180)) + '</span>' : '');
      list.appendChild(li);
    });
  }

  function renderNotes(notas) {
    var box = document.getElementById('tsNotes');
    notas = notas || {};
    var has = Boolean(notas.tese || notas.pergunta || notas.nao_repetir);
    box.hidden = !has;
    document.getElementById('tsNotesTese').textContent = notas.tese || '';
    document.getElementById('tsNotesAsk').textContent = notas.pergunta ? 'Pergunta: ' + notas.pergunta : '';
    document.getElementById('tsNotesAvoid').textContent = notas.nao_repetir ? 'Não repetir: ' + notas.nao_repetir : '';
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
      button.innerHTML = '<img src="' + escapeAttr(item.asset_url) + '" alt="">';
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

  function escapeAttr(value) {
    return escapeHtml(value).replace(/"/g, '&quot;');
  }

  function isTrustedMarkup(html) {
    return /^(?:\s*)<(?:section|figure|article|p|h[23])\b/i.test(html || '');
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
      var action = button.getAttribute('data-action');
      var needsSelection = action === 'reescrever' || action === 'expandir' || action === 'resumir' || action === 'ajustar_tom';
      button.disabled = needsSelection && !has;
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

  function currentPage() {
    var node = state.range && state.range.commonAncestorContainer;
    if (node && node.nodeType === 3) node = node.parentNode;
    if (node && editor.contains(node)) {
      var page = node.closest ? node.closest('.ts-page') : null;
      if (page) return page;
    }
    return editor.querySelector('.ts-page:last-of-type');
  }

  function emptyPageHtml(layout, surface) {
    layout = layout || 'split';
    surface = surface || 'roteiro';
    var art = layout === 'split'
      ? '<figure class="ts-page-art" data-slot="ilustracao"></figure>'
      : '';
    return (
      '<article class="ts-page" data-layout="' + layout + '" data-surface="' + surface + '">' +
        '<div class="ts-page-copy"><h3>Nova página</h3><p></p></div>' +
        art +
      '</article>'
    );
  }

  function insertPage() {
    var layout = (document.getElementById('tsPageLayout') || {}).value || 'split';
    var page = currentPage();
    var html = emptyPageHtml(layout);
    if (page && page.insertAdjacentHTML) {
      page.insertAdjacentHTML('afterend', html);
    } else {
      editor.insertAdjacentHTML('beforeend', html);
    }
    scheduleSave();
  }

  function setPageLayout(layout) {
    var page = currentPage();
    if (!page) return;
    page.setAttribute('data-layout', layout);
    var art = page.querySelector('.ts-page-art');
    if (layout === 'split' && !art) {
      page.insertAdjacentHTML(
        'beforeend',
        '<figure class="ts-page-art" data-slot="ilustracao"></figure>'
      );
    }
    if (layout !== 'split' && art && !art.querySelector('img')) {
      art.remove();
    }
    scheduleSave();
  }

  function insertImage(url) {
    var page = currentPage();
    var slot = page && page.querySelector('.ts-page-art');
    var markup = '<img src="' + escapeAttr(url) + '" alt="">';
    if (slot) {
      slot.innerHTML = markup;
      if (page && page.getAttribute('data-layout') === 'copy') {
        page.setAttribute('data-layout', 'split');
      }
      scheduleSave();
      return;
    }
    if (page) {
      page.setAttribute('data-layout', 'split');
      page.insertAdjacentHTML(
        'beforeend',
        '<figure class="ts-page-art" data-slot="ilustracao">' + markup + '</figure>'
      );
      scheduleSave();
      return;
    }
    replaceSelection(
      '<figure class="ts-inline-image"><img src="' + escapeAttr(url) + '" alt=""></figure>'
    );
  }

  function pageSurface(page) {
    return (page && page.getAttribute('data-surface')) || 'roteiro';
  }

  function pageIndex(page) {
    if (!page) return 0;
    return Array.prototype.indexOf.call(editor.querySelectorAll('.ts-page'), page) + 1;
  }

  function markFocusPage() {
    editor.querySelectorAll('.ts-page.is-focus').forEach(function (item) {
      item.classList.remove('is-focus');
    });
    var page = currentPage();
    if (page) page.classList.add('is-focus');
    var focus = document.getElementById('tsFocus');
    var label = document.getElementById('tsFocusLabel');
    if (!focus || !label) return;
    if (!page) {
      focus.hidden = true;
      return;
    }
    focus.hidden = false;
    label.textContent =
      (pageSurface(page) === 'slide' ? 'Palco ' : 'Roteiro ') +
      pageIndex(page) +
      ' · o agente age nesta página';
    var surfaceBtn = document.getElementById('tsSurfaceBtn');
    if (surfaceBtn) {
      surfaceBtn.textContent = pageSurface(page) === 'slide' ? 'Roteiro' : 'Palco';
    }
  }

  function replaceCurrentPage(html) {
    var page = currentPage();
    if (!page) {
      editor.insertAdjacentHTML('beforeend', html);
      scheduleSave();
      return;
    }
    page.insertAdjacentHTML('afterend', html);
    var next = page.nextElementSibling;
    page.remove();
    if (next && next.classList.contains('ts-page')) {
      state.range = null;
      next.scrollIntoView({ block: 'nearest' });
    }
    scheduleSave();
    markFocusPage();
  }

  function applyTextToPage(text) {
    var html = '<p>' + escapeHtml(text).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') + '</p>';
    if (state.range && state.selection && state.selection.trim()) {
      replaceSelection(html);
      return;
    }
    var page = currentPage();
    var copy = page && page.querySelector('.ts-page-copy');
    if (copy) {
      var last = copy.querySelector('p:last-of-type');
      if (last) last.outerHTML = html;
      else copy.insertAdjacentHTML('beforeend', html);
      scheduleSave();
      return;
    }
    replaceSelection(html);
  }

  function payload(extra) {
    extra = extra || {};
    var page = currentPage();
    extra.selection = state.selection;
    extra.document = editor.innerText || '';
    extra.page_html = page ? page.outerHTML : '';
    extra.surface = pageSurface(page);
    extra.buscar_web = Boolean(document.getElementById('tsWebSearch').checked);
    return extra;
  }

  function runAction(action, extra) {
    if (!state.sessaoId) return;
    if ((action === 'gerar_slide' || action === 'reorganizar_slide') && !currentPage()) {
      insertPage();
    }
    if (action === 'gerar_imagem' && !extra) {
      showPanel(action);
      return;
    }
    if (action === 'pesquisar' && !extra && !(state.selection && state.selection.trim())) {
      extra = { instrucao: window.prompt('O que pesquisar?') || '' };
      if (!extra.instrucao) return;
    }
    setBusy(true);
    showPanel(action === 'gerar_slide' || action === 'reorganizar_slide' ? 'reescrever' : action);
    api('/sessoes/' + state.sessaoId + '/agente', {
      method: 'POST',
      body: payload(Object.assign({ action: action }, extra || {}))
    }).then(function (data) {
      renderCost(data.consumo, state.consumoTreino);
      appendChat('assistant', data.content, data.tool_used);
      applyAgentResult(data);
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
        state.lastEdit = data.html || data.content || '';
        document.getElementById('tsPanelEditTitle').textContent = titleFor(action);
        document.getElementById('tsEditPreview').textContent = data.content || '';
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
      continuar: 'Continuar',
      gerar_slide: 'Gerar palco',
      reorganizar_slide: 'Reorganizar palco'
    }[action] || 'Edição';
  }

  function applyAgentResult(data) {
    if (data.fontes) renderFontes(data.fontes);
    if (data.sessoes) renderSessions(data.sessoes);
    if (data.sessao) {
      var next = data.sessao;
      var persist = sameSession(next.id) ? Promise.resolve() : Promise.resolve(saveDocument());
      persist.then(function () {
        applySessao(next);
        renderSessions(state.sessoes);
      });
      return;
    }
    if (data.apply && data.html) {
      if (data.modo === 'substituir') {
        editor.innerHTML = data.html;
      } else if (data.modo === 'pagina' || /class="[^"]*ts-page/.test(data.html)) {
        replaceCurrentPage(data.html);
      } else {
        replaceSelection(data.html);
      }
      scheduleSave();
    }
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
      updateSelectionUi();
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
    markFocusPage();
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
    if (/class="[^"]*ts-page/.test(state.lastEdit)) {
      replaceCurrentPage(state.lastEdit);
      return;
    }
    applyTextToPage(state.lastEdit);
  });

  document.getElementById('tsApplyResearch').addEventListener('click', function () {
    if (!state.lastResearch) return;
    if (isTrustedMarkup(state.lastResearch)) {
      replaceSelection(state.lastResearch);
      return;
    }
    replaceSelection(
      '<section class="ts-block" data-bloco="dado"><p>' +
        escapeHtml(state.lastResearch).replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') +
        '</p></section>'
    );
  });

  document.getElementById('tsGenerateImage').addEventListener('click', function () {
    runAction('gerar_imagem', { prompt: document.getElementById('tsImagePrompt').value });
  });

  document.getElementById('tsInsertImage').addEventListener('click', function () {
    if (state.lastImage) insertImage(state.lastImage.asset_url);
  });

  function openImportModal(url) {
    var field = document.getElementById('tsImportModalUrl');
    field.value = url || document.getElementById('tsImportUrl').value.trim();
    if (importModal && typeof importModal.showModal === 'function') {
      importModal.showModal();
    }
    if (field.value && !state.pendingImport) {
      runImport(field.value);
    }
  }

  function renderImportPipeline(steps) {
    var list = document.getElementById('tsImportPipeline');
    list.innerHTML = '';
    list.hidden = !steps || !steps.length;
    (steps || []).forEach(function (step) {
      var li = document.createElement('li');
      li.setAttribute('data-status', step.status || 'wait');
      li.innerHTML = '<strong>' + escapeHtml(step.label) + '</strong>' + escapeHtml(step.detail || '');
      list.appendChild(li);
    });
  }

  function showImportTab(name) {
    document.querySelectorAll('.ts-import-tabs [data-tab]').forEach(function (button) {
      button.setAttribute('aria-selected', button.getAttribute('data-tab') === name ? 'true' : 'false');
    });
    document.querySelectorAll('.ts-import-tab').forEach(function (panel) {
      panel.hidden = panel.getAttribute('data-tab') !== name;
    });
  }

  function selectedImportFrames() {
    var boxes = document.querySelectorAll('#tsImportTabQuadros input[type="checkbox"]:checked');
    return Array.prototype.map.call(boxes, function (box) {
      return box.value;
    });
  }

  function renderImportResult(data) {
    state.pendingImport = data;
    state.pendingFonteId = data.fonte && data.fonte.id;
    document.getElementById('tsImportEmpty').hidden = true;
    document.getElementById('tsImportBody').hidden = false;
    document.getElementById('tsImportApply').disabled = !state.pendingFonteId;
    document.getElementById('tsImportApplyRoteiro').disabled = !state.pendingFonteId;
    renderImportPipeline(data.pipeline || []);
    var stage = document.getElementById('tsImportStageMedia');
    if (data.embed_url) {
      stage.innerHTML = '<iframe src="' + escapeAttr(data.embed_url) + '" title="' + escapeAttr(data.titulo) + '" allow="encrypted-media; picture-in-picture" allowfullscreen></iframe>';
    } else if (data.hero_url) {
      stage.innerHTML = '<img src="' + escapeAttr(data.hero_url) + '" alt="">';
    } else {
      stage.innerHTML = '';
    }
    var mins = data.duracao_s ? Math.round(data.duracao_s / 60) + ' min' : 'página';
    document.getElementById('tsImportMeta').textContent =
      (data.kind === 'youtube' ? 'YouTube · ' : 'Página · ') +
      (data.autor ? data.autor + ' · ' : '') +
      mins;
    document.getElementById('tsImportTabFonte').innerHTML =
      '<h3>' + escapeHtml(data.titulo || data.url) + '</h3>' +
      '<p>' + escapeHtml(data.autor || data.url) + '</p>' +
      '<p>' + escapeHtml(data.resumo || 'Sem resumo.') + '</p>';
    var spoken = data.transcript || data.descricao || '';
    document.getElementById('tsImportTabTexto').innerHTML =
      '<p>' + escapeHtml(data.transcript_source === 'legendas' ? 'Transcrição (legendas)' : (data.transcript_source === 'firecrawl' ? 'Texto da página do vídeo' : 'Descrição do player')) + '</p>' +
      '<p>' + escapeHtml(spoken || 'Não houve fala extraída. O briefing usou descrição e quadros.') + '</p>';
    var frames = data.frames || [];
    document.getElementById('tsImportTabQuadros').innerHTML = frames.length
      ? '<div class="ts-import-frames">' + frames.map(function (frame, index) {
          var url = frame.asset_url || frame.source_url;
          return '<label><input type="checkbox" value="' + escapeAttr(url) + '"' + (index < 2 ? ' checked' : '') + '><img src="' + escapeAttr(url) + '" alt=""><span>' + escapeHtml(frame.label || 'Quadro') + '</span></label>';
        }).join('') + '</div>'
      : '<p>Nenhum quadro deste vídeo ficou disponível.</p>';
    document.getElementById('tsImportTabBriefing').innerHTML = data.briefing_html || '<p>Sem briefing.</p>';
    var plan = document.getElementById('tsImportPlan');
    if (plan) {
      var items = data.plan || [];
      plan.hidden = !items.length;
      plan.textContent = items.length
        ? (items.length === 1
          ? 'Vamos abrir 1 sessão: ' + items[0].titulo
          : 'Fonte longa: ' + items.length + ' sessões — ' + items.map(function (item) { return item.titulo; }).join(' · '))
        : '';
    }
    showImportTab(data.kind === 'youtube' ? 'quadros' : 'fonte');
    if (data.imagens) {
      state.imagens = (state.imagens || []).concat(data.imagens);
      renderThumbs(state.imagens);
    }
  }

  function runImport(url) {
    if (!url) return;
    if (!state.sessaoId) {
      notify('Abra uma sessão antes de importar.', true);
      return;
    }
    document.getElementById('tsImportUrl').value = url;
    document.getElementById('tsImportEmpty').hidden = true;
    document.getElementById('tsImportBody').hidden = true;
    document.getElementById('tsImportApply').disabled = true;
    document.getElementById('tsImportApplyRoteiro').disabled = true;
    renderImportPipeline([
      { key: 'detect', label: 'Fonte', status: 'run', detail: 'Lendo a URL' },
      { key: 'firecrawl', label: 'Firecrawl', status: 'wait', detail: 'Página' },
      { key: 'gemini', label: 'Gemini', status: 'wait', detail: 'Visão' },
      { key: 'gpt', label: 'GPT OpenAI', status: 'wait', detail: 'Briefing' }
    ]);
    var runBtn = document.getElementById('tsImportRun');
    runBtn.disabled = true;
    runBtn.textContent = 'Lendo…';
    api('/sessoes/' + state.sessaoId + '/importar-url', {
      method: 'POST',
      body: { url: url }
    }).then(function (data) {
      renderImportResult(data);
      renderCost(data.consumo, state.consumoTreino);
    }).catch(function (error) {
      renderImportPipeline([{ key: 'detect', label: 'Fonte', status: 'error', detail: error.message }]);
      document.getElementById('tsImportEmpty').hidden = false;
      document.getElementById('tsImportEmpty').textContent = error.message;
      notify(error.message, true);
    }).finally(function () {
      runBtn.disabled = false;
      runBtn.textContent = 'Ler';
    });
  }

  function applyImportedFonte(mode) {
    if (!state.pendingFonteId || !state.sessaoId) return;
    var pending = state.pendingImport || {};
    api('/sessoes/' + state.sessaoId + '/fontes/' + state.pendingFonteId + '/aplicar', {
      method: 'POST',
      body: {
        mode: mode,
        importacao_id: pending.importacao && pending.importacao.id,
        titulo: pending.titulo || '',
        autor: pending.autor || '',
        url: pending.url || '',
        briefing_html: pending.briefing_html || '',
        transcript: pending.transcript || '',
        descricao: pending.descricao || '',
        duracao_s: pending.duracao_s || 0,
        hero_url: pending.hero_url || '',
        frame_urls: selectedImportFrames()
      }
    }).then(function (data) {
      if (data.sessoes) renderSessions(data.sessoes);
      if (data.fontes) renderFontes(data.fontes);
      if (data.imagens) {
        state.imagens = data.imagens;
        renderThumbs(state.imagens);
      }
      if (data.sessao) applySessao(data.sessao);
      if (importModal && importModal.open) importModal.close();
      state.pendingImport = null;
      var count = (data.criadas || []).length;
      notify(
        mode === 'sessions'
          ? (count > 1 ? count + ' sessões criadas a partir da fonte.' : 'Sessão nova criada com a fonte.')
          : 'Fonte adicionada ao contexto desta sessão.'
      );
    }).catch(function (error) {
      notify(error.message, true);
    });
  }

  document.getElementById('tsImportBtn').addEventListener('click', function () {
    openImportModal(document.getElementById('tsImportUrl').value.trim());
  });

  document.getElementById('tsImportUrl').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      openImportModal(event.target.value.trim());
    }
  });

  document.getElementById('tsImportRun').addEventListener('click', function () {
    runImport(document.getElementById('tsImportModalUrl').value.trim());
  });

  document.getElementById('tsImportModalUrl').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      runImport(event.target.value.trim());
    }
  });

  document.querySelectorAll('.ts-import-tabs [data-tab]').forEach(function (button) {
    button.addEventListener('click', function () {
      showImportTab(button.getAttribute('data-tab'));
    });
  });

  document.getElementById('tsImportApply').addEventListener('click', function () {
    applyImportedFonte('context');
  });

  document.getElementById('tsImportApplyRoteiro').addEventListener('click', function () {
    applyImportedFonte('sessions');
  });

  if (importModal) {
    importModal.addEventListener('close', function () {
      if (!importModal.open) return;
      state.pendingImport = null;
    });
  }

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
      applyAgentResult(data);
      if (data.apply) {
        return;
      }
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

  var addPage = document.getElementById('tsAddPage');
  if (addPage) {
    addPage.addEventListener('click', insertPage);
  }
  var pageLayout = document.getElementById('tsPageLayout');
  if (pageLayout) {
    pageLayout.addEventListener('change', function () {
      setPageLayout(pageLayout.value);
    });
  }
  var surfaceBtn = document.getElementById('tsSurfaceBtn');
  if (surfaceBtn) {
    surfaceBtn.addEventListener('click', function () {
      var page = currentPage();
      if (!page) {
        insertPage();
        page = editor.querySelector('.ts-page:last-of-type');
      }
      if (!page) return;
      var next = pageSurface(page) === 'slide' ? 'roteiro' : 'slide';
      page.setAttribute('data-surface', next);
      if (next === 'slide' && page.getAttribute('data-layout') === 'copy') {
        page.setAttribute('data-layout', 'statement');
      }
      scheduleSave();
      markFocusPage();
    });
  }

  document.getElementById('tsAddSession').addEventListener('click', function () {
    var titulo = window.prompt('Título da nova sessão');
    if (!titulo || !state.treinamentoId) return;
    setBusy(true);
    api('/treinamentos/' + state.treinamentoId + '/sessoes', {
      method: 'POST',
      body: { titulo: titulo }
    }).then(function (data) {
      if (data.sessoes) renderSessions(data.sessoes);
      if (data.sessao) openSession(data.sessao.id);
    }).catch(function (error) {
      notify(error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  });

  document.getElementById('tsIllustrateBtn').addEventListener('click', function () {
    if (!state.treinamentoId) return;
    setBusy(true);
    api('/treinamentos/' + state.treinamentoId + '/ilustracoes', { method: 'POST' })
      .then(function (data) {
        state.consumoTreino = data.consumo_treinamento || state.consumoTreino;
        if (data.sessoes) renderSessions(data.sessoes);
        if (state.sessaoId) return api('/sessoes/' + state.sessaoId);
      })
      .then(function (sessao) {
        if (sessao) applySessao(sessao);
        notify('Ilustrações geradas.');
      })
      .catch(function (error) {
        notify(error.message, true);
      })
      .finally(function () {
        setBusy(false);
      });
  });

  document.getElementById('tsUploadFile').addEventListener('change', function (event) {
    var file = event.target.files && event.target.files[0];
    event.target.value = '';
    if (!file || !state.sessaoId) return;
    var body = new FormData();
    body.append('file', file);
    setBusy(true);
    fetch('/parametros/api/sessoes/' + state.sessaoId + '/anexos', {
      method: 'POST',
      credentials: 'same-origin',
      body: body
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok || data.success === false) {
          throw new Error(data.error || 'Não foi possível enviar o arquivo.');
        }
        return data.data;
      });
    }).then(function (data) {
      state.lastResearch = data.classificacao || data.extracted || '';
      document.getElementById('tsResearchPreview').textContent = state.lastResearch;
      showPanel('pesquisar');
      renderCost(data.consumo, state.consumoTreino);
      if (data.fontes) renderFontes(data.fontes);
      if (data.apply && data.sessao) {
        applySessao(data.sessao);
        notify('Anexo encaixado na sessão.');
      } else {
        if (data.html) {
          state.lastResearch = data.html;
          document.getElementById('tsResearchPreview').textContent = data.classificacao || data.html;
        }
        if (data.sessao_slug) {
          notify('Anexo classificado para ' + data.sessao_slug + '. Incorpore se estiver certo.');
        } else {
          notify('Anexo classificado. Incorpore ao texto se estiver certo.');
        }
      }
    }).catch(function (error) {
      notify(error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  });

  bootstrap();
})();
