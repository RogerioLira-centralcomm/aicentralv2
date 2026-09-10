(function () {
  var app = document.getElementById('pi-operacao-app');
  if (!app) return;

  var piId = app.getAttribute('data-pi-id');
  var modo = app.getAttribute('data-fechamento-modo');
  var btnEnviar = document.getElementById('btn_enviar_financeiro');
  var btnConfirmar = document.getElementById('btn_confirmar_financeiro');
  var modal = document.getElementById('modal_confirmar_financeiro');
  var obs = document.getElementById('obs_operacao_fechamento');

  function toast(message, type) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type || 'info');
      return;
    }
    window.alert(message);
  }

  if (btnEnviar && modal) {
    btnEnviar.addEventListener('click', function () {
      if (btnEnviar.disabled) {
        toast('Resolva as pendências do fechamento antes de enviar.', 'error');
        return;
      }
      modal.showModal();
    });
  }

  if (btnConfirmar) {
    btnConfirmar.addEventListener('click', function () {
      var btn = btnConfirmar;
      btn.disabled = true;
      btn.textContent = 'Enviando...';
      var payload = {};
      if (obs && obs.value.trim()) {
        payload.observacoes_operacao = obs.value.trim();
      }
      fetch('/api/cadu_pi/' + piId + '/enviar-financeiro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(function (resp) { return resp.json().then(function (data) { return { ok: resp.ok, status: resp.status, data: data }; }); })
        .then(function (result) {
          if (result.data && result.data.success) {
            if (modal) modal.close();
            toast('PI enviado ao financeiro.', 'success');
            window.setTimeout(function () {
              window.location.href = result.data.redirect || ('/cadu_pi/' + piId + '/financeiro');
            }, 700);
            return;
          }
          var pendencias = (result.data && result.data.pendencias) || [];
          if (pendencias.length) {
            toast(pendencias[0].mensagem || 'Pendências de fechamento.', 'error');
          } else {
            toast((result.data && result.data.message) || 'Erro ao enviar ao financeiro.', 'error');
          }
        })
        .catch(function () {
          toast('Erro ao enviar ao financeiro.', 'error');
        })
        .finally(function () {
          btn.disabled = false;
          btn.textContent = 'Confirmar envio';
        });
    });
  }

  if (modo === 'fechamento') {
    fetch('/api/cadu_pi/' + piId + '/resultado-fechamento/preview')
      .then(function (resp) { return resp.json(); })
      .then(function (payload) {
        var data = payload && payload.data;
        if (!data || !btnEnviar) return;
        btnEnviar.disabled = !data.gate_ok;
        btnEnviar.setAttribute('data-gate-ok', data.gate_ok ? 'true' : 'false');
      })
      .catch(function () {});
  }
})();
