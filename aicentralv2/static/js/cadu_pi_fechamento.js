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

  var desk = document.getElementById('pi-docs-agencia');
  if (desk) {
    desk.addEventListener('click', function (event) {
      var preview = event.target.closest('[data-doc-preview]');
      var send = event.target.closest('[data-doc-send]');
      var card = event.target.closest('[data-doc-tipo]');
      if (!card) return;
      var tipo = card.getAttribute('data-doc-tipo');
      var variante = card.getAttribute('data-doc-variante') || 'agencia';
      var campo = card.querySelector('textarea');
      var mensagem = campo ? campo.value.trim() : '';

      if (preview) {
        event.preventDefault();
        var url = preview.getAttribute('href') || '';
        url += (url.indexOf('?') >= 0 ? '&' : '?') + 'variante=' + encodeURIComponent(variante);
        if (mensagem) url += '&mensagem=' + encodeURIComponent(mensagem);
        window.open(url, '_blank', 'noopener');
        return;
      }

      if (!send || send.disabled) return;
      send.disabled = true;
      var original = send.textContent;
      send.textContent = 'Enviando...';
      fetch('/api/cadu_pi/' + piId + '/documentos/' + encodeURIComponent(tipo) + '/enviar-assinatura', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ mensagem: mensagem, variante: variante })
      })
        .then(function (resp) { return resp.json().then(function (data) { return { ok: resp.ok, data: data }; }); })
        .then(function (result) {
          if (!result.data || !result.data.success) {
            throw new Error((result.data && result.data.message) || 'Não foi possível enviar.');
          }
          var dest = (result.data.data && result.data.data.destinatario) || {};
          toast('Documento enviado para assinatura' + (dest.email ? ' · ' + dest.email : '') + '.', 'success');
          var status = card.querySelector('.pi-doc-card__status');
          if (!status) {
            status = document.createElement('span');
            status.className = 'pi-doc-card__status';
            send.parentNode.appendChild(status);
          }
          status.textContent = 'Enviado para ' + (dest.nome || dest.email || 'a agência');
          var hint = card.querySelector('.pi-doc-card__hint');
          if (hint) hint.remove();
        })
        .catch(function (error) {
          toast(error.message || 'Não foi possível enviar o documento.', 'error');
        })
        .finally(function () {
          send.disabled = false;
          send.textContent = original;
        });
    });
  }

  var dreRoot = document.querySelector('[data-fechamento-dre]');
  var form = document.getElementById('form_provisionamentos');
  if (!dreRoot || !form) return;

  function parsePct(value) {
    var n = parseFloat(String(value || '0').replace(/\./g, '').replace(',', '.'));
    return isFinite(n) ? n : 0;
  }

  function formatBrl(value) {
    return (Number(value) || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  function readPercs() {
    return {
      margem_cc: parsePct(form.perc_margem_cc.value),
      tech_fee: parsePct(form.perc_tech_fee.value),
      com_vendas: parsePct(form.perc_com_vendas.value),
      pl_incentivos: parsePct(form.perc_pl_incentivos.value),
      impostos: parsePct(form.perc_impostos.value),
      comissao_agencia: parsePct(form.perc_comissao_agencia.value),
      comissao_parceiro: parsePct(form.perc_comissao_parceiro.value)
    };
  }

  function computeDre() {
    var gasto = parseFloat(dreRoot.getAttribute('data-gasto') || '0') || 0;
    var objContr = parseFloat(dreRoot.getAttribute('data-obj-contratado') || '0') || 0;
    var objAting = parseFloat(dreRoot.getAttribute('data-obj-atingido') || '0') || 0;
    var cbase = parseFloat(dreRoot.getAttribute('data-cbase') || '0') || 0;
    var cpm = dreRoot.getAttribute('data-cpm') === 'true';
    var perc = readPercs();
    var tf = perc.tech_fee / 100;
    var mcc = perc.margem_cc / 100;
    var com = perc.com_vendas / 100;
    var inc = perc.pl_incentivos / 100;
    var imp = perc.impostos / 100;
    var volumeContr = cpm ? objContr / 1000 : objContr;
    var volumeAting = cpm ? objAting / 1000 : objAting;
    var volume = (cbase > 0 && gasto > 0) ? (gasto / cbase) : (volumeAting || volumeContr);
    var soma = mcc + com + inc + imp;
    var bruto = 0;
    var tfVal = 0;
    if (cbase > 0 && tf < 1 && soma < 1 && volume > 0) {
      var opex = cbase / (1 - tf);
      bruto = volume * (opex / (1 - soma));
      tfVal = volume * (opex - cbase);
    }
    var liquido = bruto - (bruto * perc.comissao_agencia / 100);
    return {
      valor_bruto: bruto,
      valor_liquido: liquido,
      margem_cc: bruto * mcc,
      tech_fee: tfVal,
      com_vendas: bruto * com,
      pl_incentivos: bruto * inc,
      impostos: bruto * imp
    };
  }

  function renderDre() {
    var dre = computeDre();
    Object.keys(dre).forEach(function (key) {
      var el = dreRoot.querySelector('[data-dre="' + key + '"]');
      if (el) el.textContent = formatBrl(dre[key]);
    });
  }

  Array.prototype.forEach.call(form.querySelectorAll('input'), function (input) {
    input.addEventListener('input', renderDre);
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var btn = document.getElementById('btn_salvar_provisionamentos');
    btn.disabled = true;
    fetch('/api/cadu_pi/' + piId + '/provisionamentos', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        percentuais: readPercs(),
        observacoes_operacao: obs ? obs.value.trim() : ''
      })
    })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        if (!data.success) throw new Error(data.message || 'Não foi possível salvar.');
        toast('Provisionamentos atualizados com o total das campanhas.', 'success');
        if (data.data) {
          ['valor_bruto', 'valor_liquido', 'margem_cc', 'tech_fee', 'com_vendas', 'pl_incentivos', 'impostos'].forEach(function (key) {
            var el = dreRoot.querySelector('[data-dre="' + key + '"]');
            if (el && data.data[key] != null) el.textContent = formatBrl(data.data[key]);
          });
        }
      })
      .catch(function (error) {
        toast(error.message || 'Não foi possível salvar os provisionamentos.', 'error');
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
})();
