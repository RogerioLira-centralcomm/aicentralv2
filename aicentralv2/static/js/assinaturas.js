(function () {
  'use strict';

  var root = document.querySelector('[data-sign-app]');
  if (!root) return;

  function request(path, options) {
    options = options || {};
    return fetch('/assinaturas/api' + path, {
      method: options.method || 'GET',
      credentials: 'same-origin',
      headers: options.body instanceof FormData
        ? undefined
        : { 'Content-Type': 'application/json' },
      body: options.body
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok || data.success === false) {
          throw new Error(data.error || 'Não foi possível concluir a operação.');
        }
        return data.data;
      });
    });
  }

  function notify(node, message, error) {
    if (!node) return;
    node.hidden = !message;
    node.textContent = message || '';
    node.classList.toggle('is-error', Boolean(error));
    if (message && typeof window.showToast === 'function') {
      window.showToast(message, error ? 'error' : 'success');
    }
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function initMesa() {
    var list = root.querySelector('[data-sign-list]');
    var feedback = root.querySelector('[data-sign-feedback]');
    var eixo = 'todos';

    function query() {
      var params = new URLSearchParams();
      var status = root.querySelector('[data-filter="status"]');
      var q = root.querySelector('[data-filter="q"]');
      if (eixo !== 'todos') params.set('eixo', eixo);
      if (status && status.value) params.set('status', status.value);
      if (q && q.value.trim()) params.set('q', q.value.trim());
      return params.toString() ? ('?' + params.toString()) : '';
    }

    function render(items) {
      if (!items || !items.length) {
        list.innerHTML = '<p class="cx-sign-empty">Nenhum documento nesta fila.</p>';
        return;
      }
      list.innerHTML = items.map(function (doc) {
        var missing = (doc.signatarios || []).filter(function (item) {
          return item.status === 'pendente';
        }).map(function (item) { return item.nome; }).join(', ');
        return '<a class="cx-sign-card is-' + esc(doc.status) + '" href="/assinaturas/' + doc.id + '">' +
          '<div><h2>' + esc(doc.titulo) + '</h2>' +
          '<p>' + esc(doc.tipo_vinculo_label) +
          (doc.vinculo_nome ? ' · ' + esc(doc.vinculo_nome) : '') +
          (missing ? ' · Falta: ' + esc(missing) : '') +
          '</p></div>' +
          '<span class="cx-sign-stamp is-' + esc(doc.status) + '">' + esc(doc.status_label) + '</span>' +
          '</a>';
      }).join('');
    }

    function load() {
      request(query()).then(render).catch(function (error) {
        notify(feedback, error.message, true);
      });
    }

    root.querySelectorAll('[data-eixo]').forEach(function (button) {
      button.addEventListener('click', function () {
        eixo = button.getAttribute('data-eixo');
        root.querySelectorAll('[data-eixo]').forEach(function (item) {
          item.classList.toggle('is-on', item === button);
        });
        load();
      });
    });
    root.querySelectorAll('[data-filter]').forEach(function (field) {
      field.addEventListener('change', load);
      field.addEventListener('input', function () {
        window.clearTimeout(field._timer);
        field._timer = window.setTimeout(load, 250);
      });
    });
    load();
  }

  function initNovo() {
    var form = root.querySelector('[data-sign-form]');
    var feedback = root.querySelector('[data-sign-feedback]');
    var fileName = root.querySelector('[data-file-name]');
    var drop = root.querySelector('[data-drop]');
    var fileInput = form.querySelector('input[name="arquivo"]');
    var tipo = form.elements.tipo_vinculo;
    var search = root.querySelector('[data-vinculo-search]');
    var idField = form.elements.id_vinculo;
    var results = root.querySelector('[data-vinculo-results]');
    var signerSearch = root.querySelector('[data-signer-search]');
    var signerResults = root.querySelector('[data-signer-results]');
    var signerCount = root.querySelector('[data-signer-count]');
    var title = form.elements.titulo;
    var signers = [];

    function fileTitle(file) {
      return String(file && file.name || '').replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function setFile(file) {
      fileName.textContent = file ? file.name : 'Solte o PDF ou clique para escolher';
      if (file && (!title.value.trim() || title.dataset.autoTitle === '1')) {
        title.value = fileTitle(file);
        title.dataset.autoTitle = '1';
      }
    }

    title.addEventListener('input', function () { title.dataset.autoTitle = '0'; });
    fileInput.addEventListener('change', function () { setFile(fileInput.files[0]); });
    ['dragenter', 'dragover'].forEach(function (eventName) {
      drop.addEventListener(eventName, function (event) {
        event.preventDefault();
        drop.classList.add('is-over');
      });
    });
    ['dragleave', 'drop'].forEach(function (eventName) {
      drop.addEventListener(eventName, function (event) {
        event.preventDefault();
        drop.classList.remove('is-over');
      });
    });
    drop.addEventListener('drop', function (event) {
      if (event.dataTransfer.files.length) {
        fileInput.files = event.dataTransfer.files;
        setFile(event.dataTransfer.files[0]);
      }
    });

    function toggleVinculo() {
      var needs = tipo.value !== 'interno';
      search.hidden = !needs;
      results.hidden = true;
      if (!needs) {
        idField.value = '';
        search.value = '';
      }
    }

    function renderSignerCount() {
      signerCount.textContent = signers.length
        ? signers.length + (signers.length === 1 ? ' signatário selecionado' : ' signatários selecionados')
        : 'Nenhum signatário selecionado';
    }

    function renderSigners(items) {
      if (!items.length) {
        signerResults.innerHTML = '<p class="cx-sign-empty">Nenhum signatário encontrado.</p>';
        return;
      }
      signerResults.innerHTML = items.map(function (item) {
        var checked = signers.some(function (signer) { return signer.email === item.email; });
        return '<label class="cx-sign-signer-option">' +
          '<input type="checkbox" data-signer-toggle data-id="' + esc(item.id) + '" data-email="' + esc(item.email) +
          '" data-nome="' + esc(item.label) + '"' + (checked ? ' checked' : '') + '>' +
          '<span><strong>' + esc(item.label) + '</strong><small>' + esc(item.email) + '</small></span></label>';
      }).join('');
    }

    function loadSigners(query) {
      request('/vinculos?tipo=colaborador&q=' + encodeURIComponent(query || '')).then(function (items) {
        renderSigners(items);
      }).catch(function (error) {
        notify(feedback, error.message, true);
      });
    }

    function searchVinculos(query) {
      if (!query || tipo.value === 'interno') {
        results.hidden = true;
        return;
      }
      request('/vinculos?tipo=' + encodeURIComponent(tipo.value) + '&q=' + encodeURIComponent(query))
        .then(function (items) {
          results.hidden = !items.length;
          results.innerHTML = items.map(function (item) {
            return '<button type="button" data-id="' + esc(item.id) + '" data-label="' + esc(item.label) + '">' +
              esc(item.label) + '</button>';
          }).join('');
        });
    }

    tipo.addEventListener('change', toggleVinculo);
    search.addEventListener('input', function () {
      idField.value = '';
      window.clearTimeout(search._timer);
      search._timer = window.setTimeout(function () { searchVinculos(search.value.trim()); }, 220);
    });
    results.addEventListener('click', function (event) {
      var button = event.target.closest('button');
      if (!button) return;
      idField.value = button.getAttribute('data-id');
      search.value = button.getAttribute('data-label');
      form.elements.vinculo_nome.value = button.getAttribute('data-label');
      results.hidden = true;
    });

    signerSearch.addEventListener('input', function () {
      window.clearTimeout(signerSearch._timer);
      signerSearch._timer = window.setTimeout(function () {
        loadSigners(signerSearch.value.trim());
      }, 220);
    });
    signerResults.addEventListener('change', function (event) {
      var input = event.target.closest('[data-signer-toggle]');
      if (!input) return;
      var email = input.getAttribute('data-email');
      if (input.checked && !signers.some(function (item) { return item.email === email; })) {
        signers.push({
          id_contato: input.getAttribute('data-id'),
          email: email,
          nome: input.getAttribute('data-nome')
        });
      } else if (!input.checked) {
        signers = signers.filter(function (item) { return item.email !== email; });
      }
      renderSignerCount();
    });

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!signers.length) {
        notify(feedback, 'Escolha pelo menos um signatário.', true);
        return;
      }
      var body = new FormData(form);
      body.set('signatarios', JSON.stringify(signers));
      var submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      request('', { method: 'POST', body: body }).then(function (doc) {
        window.location.href = '/assinaturas/' + doc.id;
      }).catch(function (error) {
        notify(feedback, error.message, true);
      }).finally(function () {
        submit.disabled = false;
      });
    });
    toggleVinculo();
    renderSignerCount();
    loadSigners('');
  }

  function initViewer() {
    var cancel = root.querySelector('[data-sign-cancel]');
    window.addEventListener('message', function (event) {
      var origin = String(event.origin || '');
      if (!/^https:\/\/(secure|sandbox)\.d4sign\.com\.br$/.test(origin)) return;
      if (event.data === 'signed') {
        window.setTimeout(function () { window.location.reload(); }, 350);
      }
    });
    if (!cancel) return;
    cancel.addEventListener('click', function () {
      if (typeof window.showConfirm !== 'function') return;
      window.showConfirm({
        title: 'Cancelar documento',
        message: 'O documento sai da fila de assinatura na D4Sign e na mesa.',
        theme: 'danger',
        confirmText: 'Cancelar documento',
        onConfirm: function () {
          request('/' + root.dataset.docId + '/cancelar', { method: 'POST' })
            .then(function () { window.location.href = '/assinaturas/'; })
            .catch(function (error) {
              if (typeof window.showToast === 'function') {
                window.showToast(error.message, 'error');
              }
            });
        }
      });
    });
  }

  var page = root.dataset.signApp;
  if (page === 'mesa') initMesa();
  if (page === 'novo') initNovo();
  if (page === 'viewer') initViewer();
})();
