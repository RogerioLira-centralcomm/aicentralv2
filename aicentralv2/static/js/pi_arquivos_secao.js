(function () {
  'use strict';

  var root = document.getElementById('pi-arq-upload');
  if (!root) return;

  var piId = root.dataset.piId;
  var secao = root.dataset.secao;
  var drop = document.getElementById('pi-arq-dropzone');
  var input = document.getElementById('pi-arq-file');
  var statusBox = document.getElementById('pi-arq-import-status');
  var statusText = document.getElementById('pi-arq-import-status-text');
  function uploadFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;

    if (statusBox) statusBox.classList.remove('hidden');
    if (statusText) {
      statusText.textContent =
        files.length === 1 ? 'Enviando 1 arquivo…' : 'Enviando ' + files.length + ' arquivos…';
    }
    if (drop) drop.classList.add('is-uploading');

    var fd = new FormData();
    files.forEach(function (f) {
      fd.append('arquivo', f);
    });

    var url = '/api/cadu_pi/' + encodeURIComponent(piId) + '/arquivos/' + encodeURIComponent(secao);

    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      body: fd,
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, status: r.status, data: data };
        });
      })
      .then(function (res) {
        var data = res.data || {};
        if (!data.success) {
          var msg = data.message || 'Não foi possível enviar os arquivos.';
          if (typeof showToast === 'function') showToast(msg, 'error');
          else alert(msg);
          return;
        }

        var created = data.created != null ? data.created : (data.saved || []).length;
        var total = data.total != null ? data.total : created;
        var failed = data.failed || [];

        if (failed.length === 0) {
          var okMsg =
            created === 1 ? 'Arquivo enviado.' : created + ' arquivo(s) enviado(s).';
          if (typeof showToast === 'function') showToast(okMsg, 'success');
        } else if (created > 0) {
          if (typeof showToast === 'function') {
            showToast(created + ' de ' + total + ' arquivo(s) enviado(s).', 'warning');
            failed.forEach(function (item) {
              showToast((item.filename || 'arquivo') + ': ' + (item.message || ''), 'error', 6000);
            });
          }
        }

        window.location.reload();
      })
      .catch(function () {
        if (typeof showToast === 'function') {
          showToast('Erro de rede ao enviar arquivos.', 'error');
        }
      })
      .then(function () {
        if (statusBox) statusBox.classList.add('hidden');
        if (drop) drop.classList.remove('is-uploading');
        if (input) input.value = '';
      });
  }

  if (drop && input) {
    drop.addEventListener('click', function () {
      input.click();
    });
    drop.addEventListener('dragover', function (e) {
      e.preventDefault();
      drop.classList.add('is-dragover');
    });
    drop.addEventListener('dragleave', function () {
      drop.classList.remove('is-dragover');
    });
    drop.addEventListener('drop', function (e) {
      e.preventDefault();
      drop.classList.remove('is-dragover');
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        uploadFiles(e.dataTransfer.files);
      }
    });
    input.addEventListener('change', function () {
      if (input.files && input.files.length) uploadFiles(input.files);
    });
    drop.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        input.click();
      }
    });
  }
})();