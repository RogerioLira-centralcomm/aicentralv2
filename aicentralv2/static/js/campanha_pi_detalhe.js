(function () {
  'use strict';

  var root = document.getElementById('pi-operacao-app');
  if (!root || !root.classList.contains('campaign-detail-page')) return;

  var campaignId = Number(root.dataset.campanhaId || 0);
  var form = document.getElementById('campanhaDetalheForm');
  var dailyForm = document.getElementById('campaignDailyForm');
  var status = document.getElementById('campanhaDetalheStatus');
  var saveButton = document.getElementById('salvarCampanhaDetalhe');

  function parseNumber(value) {
    var raw = String(value == null ? '' : value)
      .replace(/R\$\s*/gi, '')
      .replace(/\s/g, '');
    if (!raw) return 0;
    if (raw.indexOf(',') >= 0) return Number(raw.replace(/\./g, '').replace(',', '.')) || 0;
    var dots = raw.split('.');
    if (dots.length > 2 || (dots.length === 2 && dots[1].length === 3)) {
      return Number(raw.replace(/\./g, '')) || 0;
    }
    return Number(raw) || 0;
  }

  function formatMoney(value) {
    return 'R$ ' + Number(value || 0).toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function notify(message, type) {
    if (status) {
      status.textContent = message || '';
      status.className = type ? 'is-' + type : '';
    }
    if (typeof window.showToast === 'function') window.showToast(message, type || 'info');
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i> ' + label;
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
    }
  }

  document.querySelectorAll('[data-open-date]').forEach(function (button) {
    button.addEventListener('click', function () {
      var input = document.getElementById(button.dataset.openDate);
      if (input && typeof input.showPicker === 'function') input.showPicker();
      else if (input) input.focus();
    });
  });

  document.querySelectorAll('[data-mask="numero"]').forEach(function (input) {
    input.addEventListener('input', function () {
      var digits = input.value.replace(/\D/g, '');
      input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    });
  });

  document.querySelectorAll('[data-mask="real"]').forEach(function (input) {
    input.addEventListener('input', function () {
      var digits = input.value.replace(/\D/g, '');
      input.value = digits ? formatMoney(Number(digits) / 100) : '';
    });
  });

  var financialPairs = [
    ['perc_margem_cc', 'val_margem_cc'],
    ['perc_tech_fee', 'val_tech_fee'],
    ['perc_com_vendas', 'val_com_vendas'],
    ['perc_pl_incentivos', 'val_pl_incentivos'],
    ['perc_impostos', 'val_impostos']
  ];

  function recalculateFinancials() {
    var platform = document.getElementById('valor_plataforma');
    var base = platform ? parseNumber(platform.value) : 0;
    financialPairs.forEach(function (pair) {
      var percentage = document.getElementById(pair[0]);
      var result = document.getElementById(pair[1]);
      if (!percentage || !result) return;
      var calculated = base * parseNumber(percentage.value) / 100;
      result.value = calculated > 0 ? formatMoney(calculated) : '';
    });
    var distribution = document.getElementById('dist_pct');
    var platformBase = parseNumber(root.dataset.basePlataformas);
    if (distribution) {
      var value = platformBase > 0 ? (base / platformBase) * 100 : 0;
      distribution.value = value.toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + '%';
    }
  }

  financialPairs.forEach(function (pair) {
    var input = document.getElementById(pair[0]);
    if (input) input.addEventListener('input', recalculateFinancials);
  });
  var platformInput = document.getElementById('valor_plataforma');
  if (platformInput) platformInput.addEventListener('input', recalculateFinancials);
  recalculateFinancials();

  if (form) {
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (!form.reportValidity()) return;
      setBusy(saveButton, true, 'Salvando…');
      notify('Salvando alterações…', 'info');
      try {
        var response = await fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: new FormData(form)
        });
        var payload = await response.json();
        if (!response.ok || payload.success === false) {
          throw new Error(payload.error || 'Não foi possível salvar a campanha.');
        }
        notify(payload.message || 'Campanha atualizada com sucesso.', 'success');
        window.setTimeout(function () { window.location.reload(); }, 650);
      } catch (error) {
        notify(error.message, 'error');
        setBusy(saveButton, false);
      }
    });
  }

  if (dailyForm) {
    dailyForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (!dailyForm.reportValidity()) return;
      var button = dailyForm.querySelector('button[type="submit"]');
      setBusy(button, true, 'Registrando…');
      try {
        var values = new FormData(dailyForm);
        var response = await fetch('/api/campanhas-pi/' + campaignId + '/diarios', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_evento: values.get('data_evento'),
            atingido: values.get('atingido'),
            gasto: values.get('gasto')
          })
        });
        var payload = await response.json();
        if (!response.ok || payload.success === false) {
          throw new Error(payload.error || 'Não foi possível registrar a atualização.');
        }
        notify('Atualização diária registrada.', 'success');
        window.setTimeout(function () { window.location.reload(); }, 500);
      } catch (error) {
        notify(error.message, 'error');
        setBusy(button, false);
      }
    });
  }
})();
