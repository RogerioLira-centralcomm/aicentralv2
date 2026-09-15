(function () {
  'use strict';
  document.querySelectorAll('tr[data-href]').forEach(function (row) {
    row.addEventListener('click', function (event) {
      if (!event.target.closest('a,button,input,select')) window.location.href = row.dataset.href;
    });
    row.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') window.location.href = row.dataset.href;
    });
  });
  document.addEventListener('click', function (event) {
    var opener = event.target.closest('[data-open-credit-dialog]');
    if (opener) {
      var dialog = document.getElementById(opener.dataset.openCreditDialog);
      if (dialog && typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
      return;
    }
    var closer = event.target.closest('[data-close-credit-dialog]');
    if (closer) {
      var current = closer.closest('dialog');
      if (current) current.close();
    }
  });
  document.querySelectorAll('.credit-dialog').forEach(function (dialog) {
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) dialog.close();
    });
    var form = dialog.querySelector('form');
    if (!form) return;
    form.addEventListener('submit', function (event) {
      var feedback = form.querySelector('.credit-dialog-feedback');
      if (!form.checkValidity()) {
        event.preventDefault();
        if (feedback) feedback.textContent = 'Revise os campos obrigatórios antes de continuar.';
        var invalid = form.querySelector(':invalid');
        if (invalid) invalid.focus();
        return;
      }
      var submit = form.querySelector('[type="submit"]');
      if (submit) { submit.disabled = true; submit.textContent = 'Registrando…'; }
      if (feedback) feedback.textContent = 'Registrando a operação…';
    });
  });
  var tabs = document.querySelectorAll('[data-credit-tab]');
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (item) {
        var selected = item === tab;
        item.setAttribute('aria-selected', selected ? 'true' : 'false');
        var panel = document.getElementById(item.dataset.creditTab);
        if (panel) panel.hidden = !selected;
      });
    });
  });
  var page = document.querySelector('[data-credit-dialog-on-load]');
  if (page) {
    var initialDialog = document.getElementById(page.dataset.creditDialogOnLoad);
    if (initialDialog && typeof initialDialog.showModal === 'function') initialDialog.showModal();
  }
})();
