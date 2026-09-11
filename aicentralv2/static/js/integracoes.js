(function () {
  'use strict';

  var root = document.querySelector('[data-integration-app]');
  if (!root) return;
  var apiBase = '/parametros/api/integrations';
  var feedback = root.querySelector('[data-integration-feedback]');

  function request(path, options) {
    options = options || {};
    return fetch(apiBase + path, {
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
    feedback.hidden = false;
    feedback.textContent = message;
    feedback.classList.toggle('is-error', Boolean(error));
    if (typeof window.showToast === 'function') {
      window.showToast(message, error ? 'error' : 'success');
    }
  }

  function renderSummary(summary) {
    var form = root.querySelector('[data-integration-form="' + summary.provider + '"]');
    if (!form) return;
    Object.keys(summary.public_config || {}).forEach(function (field) {
      var input = form.elements[field];
      if (input) input.value = summary.public_config[field] || '';
    });
    if (summary.provider === 'd4sign' && form.elements.ambiente && !form.elements.ambiente.value) {
      form.elements.ambiente.value = 'producao';
    }
    var status = form.querySelector('[data-integration-status]');
    status.textContent = summary.configured ? 'Configurado' : 'Configuração pendente';
    status.classList.toggle('is-ready', summary.configured);
    status.classList.toggle('is-missing', !summary.configured);
    var secretState = form.querySelector('[data-secret-state]');
    if (secretState) {
      secretState.textContent = summary.unreadable_secret
        ? 'Esta credencial foi gravada com outra chave do servidor. Cole o token e a crypt key e salve de novo.'
        : summary.has_secret
          ? summary.source === 'environment'
            ? 'Segredo disponível no ambiente do servidor.'
            : 'Segredo armazenado: ' + summary.secret_mask + '. Deixe vazio para mantê-lo.'
          : 'Nenhum segredo armazenado no banco.';
    }
    form.dataset.configured = summary.configured ? 'true' : 'false';
    form.dataset.source = summary.source || 'database';
    var webhook = form.querySelector('[data-webhook-url]');
    if (webhook) webhook.value = summary.webhook_url || '';
  }

  function load() {
    request('').then(function (items) {
      (items || []).forEach(renderSummary);
    }).catch(function (error) {
      notify(error.message, true);
    });
  }

  function formPayload(form) {
    var data = {};
    Array.prototype.forEach.call(form.elements, function (element) {
      if (!element.name) return;
      data[element.name] = element.value.trim();
    });
    return data;
  }

  root.querySelectorAll('[data-integration-form]').forEach(function (form) {
    var provider = form.dataset.integrationForm;
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      request('/' + encodeURIComponent(provider), {
        method: 'PUT',
        body: formPayload(form)
      }).then(function (summary) {
        renderSummary(summary);
        form.querySelectorAll('input[type="password"]').forEach(function (input) {
          input.value = '';
        });
        notify('Credencial salva com segurança.');
      }).catch(function (error) {
        notify(error.message, true);
      }).finally(function () {
        submit.disabled = false;
      });
    });

    form.querySelector('[data-integration-action="validate"]').addEventListener('click', function (event) {
      var button = event.currentTarget;
      button.disabled = true;
      request('/' + encodeURIComponent(provider) + '/validate', {
        method: 'POST'
      }).then(function (result) {
        notify(result.message, !result.valid);
        fillSafes(form, result);
        if (result.valid) load();
      }).catch(function (error) {
        notify(error.message, true);
      }).finally(function () {
        button.disabled = false;
      });
    });

    form.querySelector('[data-integration-action="remove"]').addEventListener('click', function () {
      window.showConfirm({
        title: 'Remover credencial',
        message: 'A integração voltará a usar apenas a configuração do ambiente, quando disponível.',
        theme: 'danger',
        confirmText: 'Remover',
        onConfirm: function () {
          request('/' + encodeURIComponent(provider), { method: 'DELETE' })
            .then(function () {
              Array.prototype.forEach.call(form.elements, function (element) {
                if (element.tagName === 'INPUT') element.value = '';
              });
              notify('Credencial removida do banco.');
              load();
            })
            .catch(function (error) { notify(error.message, true); });
        }
      });
    });
  });

  function fillSafes(form, result) {
    var list = form.querySelector('[data-safes-list]');
    if (!list || !result || !result.safes) return;
    list.innerHTML = result.safes.map(function (safe) {
      return '<option value="' + (safe.uuid || '') + '">' + (safe.name || safe.uuid || '') + '</option>';
    }).join('');
    var input = form.elements.uuid_safe;
    if (input && !input.value && result.suggested_safe) {
      input.value = result.suggested_safe;
    }
  }

  load();
})();
