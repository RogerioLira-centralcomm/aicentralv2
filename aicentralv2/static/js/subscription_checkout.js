/**
 * Subscription Checkout - Masks, validation, CEP lookup, form submit
 */

(function () {
  'use strict';

  // ── Masks ──

  function maskCNPJ(v) {
    v = v.replace(/\D/g, '').slice(0, 14);
    v = v.replace(/^(\d{2})(\d)/, '$1.$2');
    v = v.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
    v = v.replace(/\.(\d{3})(\d)/, '.$1/$2');
    v = v.replace(/(\d{4})(\d)/, '$1-$2');
    return v;
  }

  function maskCEP(v) {
    v = v.replace(/\D/g, '').slice(0, 8);
    v = v.replace(/^(\d{5})(\d)/, '$1-$2');
    return v;
  }

  function maskPhone(v) {
    v = v.replace(/\D/g, '').slice(0, 11);
    if (v.length > 10) {
      v = v.replace(/^(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    } else if (v.length > 6) {
      v = v.replace(/^(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
    } else if (v.length > 2) {
      v = v.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
    }
    return v;
  }

  function applyMask(input, maskFn) {
    if (!input) return;
    input.addEventListener('input', function () {
      var pos = this.selectionStart;
      var oldLen = this.value.length;
      this.value = maskFn(this.value);
      var newLen = this.value.length;
      this.setSelectionRange(pos + (newLen - oldLen), pos + (newLen - oldLen));
    });
  }

  // ── CEP Lookup ──

  function setupCEPLookup() {
    var cepInput = document.getElementById('cep');
    if (!cepInput) return;

    cepInput.addEventListener('blur', function () {
      var cep = this.value.replace(/\D/g, '');
      if (cep.length !== 8) return;

      fetch('https://viacep.com.br/ws/' + cep + '/json/')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.erro) return;
          var cidade = document.getElementById('cidade');
          var endereco = document.getElementById('endereco');
          var bairro = document.getElementById('bairro');
          var estado = document.getElementById('estado');

          if (cidade && data.localidade) cidade.value = data.localidade;
          if (endereco && data.logradouro) endereco.value = data.logradouro;
          if (bairro && data.bairro) bairro.value = data.bairro;
          if (estado && data.uf) estado.value = data.uf;
        })
        .catch(function () { /* ignore */ });
    });
  }

  // ── Plan selection ──

  window.selectPlan = function (card) {
    document.querySelectorAll('.plan-card').forEach(function (c) {
      c.classList.remove('selected');
    });
    card.classList.add('selected');

    document.getElementById('selectedPlanId').value = card.dataset.planId;
    document.getElementById('selectedPlanType').value = card.dataset.planType;
    document.getElementById('planError').classList.add('hidden');

    updateSummary();
  };

  function updateSummary() {
    var selected = document.querySelector('.plan-card.selected');
    if (!selected) {
      document.getElementById('summarySection').classList.add('hidden');
      return;
    }

    document.getElementById('summarySection').classList.remove('hidden');
    document.getElementById('summaryPlanName').textContent = selected.dataset.planName;
    document.getElementById('summaryPrice').textContent = 'R$ ' + parseFloat(selected.dataset.planPrice).toFixed(2).replace('.', ',') + '/mês';

    var empresa = document.getElementById('nome_fantasia');
    var cnpj = document.getElementById('cnpj');
    var email = document.getElementById('email_faturamento');

    document.getElementById('summaryEmpresa').textContent = empresa ? empresa.value || '-' : '-';
    document.getElementById('summaryCnpj').textContent = cnpj ? cnpj.value || '-' : '-';
    document.getElementById('summaryEmail').textContent = email ? email.value || '-' : '-';
  }

  // ── Validation ──

  function validate() {
    var planId = document.getElementById('selectedPlanId').value;
    if (!planId) {
      document.getElementById('planError').classList.remove('hidden');
      document.querySelector('.plan-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
      return false;
    }

    var required = document.querySelectorAll('#checkoutForm [required]');
    for (var i = 0; i < required.length; i++) {
      if (!required[i].value.trim()) {
        required[i].classList.add('input-error', 'select-error');
        required[i].focus();
        if (typeof showToast === 'function') {
          showToast('Preencha todos os campos obrigatórios.', 'warning');
        }
        return false;
      }
      required[i].classList.remove('input-error', 'select-error');
    }

    var cnpj = document.getElementById('cnpj').value.replace(/\D/g, '');
    if (cnpj.length !== 14) {
      document.getElementById('cnpj').classList.add('input-error');
      document.getElementById('cnpj').focus();
      if (typeof showToast === 'function') showToast('CNPJ inválido.', 'warning');
      return false;
    }

    var emailField = document.getElementById('email_faturamento');
    if (emailField && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailField.value)) {
      emailField.classList.add('input-error');
      emailField.focus();
      if (typeof showToast === 'function') showToast('Email inválido.', 'warning');
      return false;
    }

    return true;
  }

  // ── Submit ──

  function handleSubmit(e) {
    e.preventDefault();
    if (!validate()) return;

    var btn = document.getElementById('submitBtn');
    btn.classList.add('loading');
    btn.disabled = true;

    var selected = document.querySelector('.plan-card.selected');

    var payload = {
      plan_id: parseInt(document.getElementById('selectedPlanId').value),
      plan_type: document.getElementById('selectedPlanType').value,
      plan_price: parseFloat(selected.dataset.planPrice),
      tokens_monthly_limit: parseInt(selected.dataset.tokens),
      image_credits_monthly: parseInt(selected.dataset.images),
      max_users: parseInt(selected.dataset.users),
      cnpj: document.getElementById('cnpj').value,
      razao_social: document.getElementById('razao_social').value,
      nome_fantasia: document.getElementById('nome_fantasia').value,
      cep: document.getElementById('cep').value,
      cidade: document.getElementById('cidade').value,
      estado: document.getElementById('estado').value,
      endereco: document.getElementById('endereco').value,
      bairro: document.getElementById('bairro').value || '',
      responsavel_nome: document.getElementById('responsavel_nome').value,
      email_faturamento: document.getElementById('email_faturamento').value,
      telefone: document.getElementById('telefone').value
    };

    fetch('/api/subscription/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        btn.classList.remove('loading');
        btn.disabled = false;

        if (res.ok && res.data.success) {
          document.getElementById('modalInvoiceNumber').textContent = res.data.invoice_number || '-';
          document.getElementById('successModal').showModal();
        } else {
          showToast(res.data.error || 'Erro ao processar assinatura.', 'error');
        }
      })
      .catch(function (err) {
        btn.classList.remove('loading');
        btn.disabled = false;
        showToast('Erro de conexão. Tente novamente.', 'error');
      });
  }

  // ── Init ──

  document.addEventListener('DOMContentLoaded', function () {
    applyMask(document.getElementById('cnpj'), maskCNPJ);
    applyMask(document.getElementById('cep'), maskCEP);
    applyMask(document.getElementById('telefone'), maskPhone);
    setupCEPLookup();

    // Update summary on field changes
    ['nome_fantasia', 'cnpj', 'email_faturamento'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input', updateSummary);
    });

    var form = document.getElementById('checkoutForm');
    if (form) form.addEventListener('submit', handleSubmit);
  });
})();
