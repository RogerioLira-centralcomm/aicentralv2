(function () {
  'use strict';

  function setupPasswordToggles() {
    document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        var input = document.getElementById(button.dataset.passwordToggle);
        var icon = button.querySelector('i');
        if (!input) return;

        var reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        button.setAttribute('aria-label', reveal ? 'Ocultar senha' : 'Mostrar senha');
        button.setAttribute('aria-pressed', reveal ? 'true' : 'false');
        if (icon) {
          icon.classList.toggle('fa-eye', !reveal);
          icon.classList.toggle('fa-eye-slash', reveal);
        }
      });
    });
  }

  function passwordScore(password) {
    var score = 0;
    if (password.length >= 8) score += 1;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
    if (/\d/.test(password)) score += 1;
    if (/[^A-Za-z0-9]/.test(password)) score += 1;
    return score;
  }

  function setupPasswordStrength() {
    var input = document.querySelector('[data-password-strength]');
    var bar = document.getElementById('passwordStrengthBar');
    var text = document.getElementById('passwordStrengthText');
    if (!input || !bar || !text) return;

    input.addEventListener('input', function () {
      var value = input.value;
      var score = passwordScore(value);
      var labels = ['Muito fraca', 'Fraca', 'Razoável', 'Forte', 'Muito forte'];
      var colors = ['#b42318', '#c2410c', '#a56b00', '#1e6c53', '#157347'];
      if (!value) {
        bar.style.width = '0';
        text.textContent = '';
        return;
      }
      bar.style.width = ((score + 1) * 20) + '%';
      bar.style.backgroundColor = colors[score];
      text.textContent = labels[score];
    });
  }

  function setupMatchingPasswords() {
    var form = document.getElementById('resetPasswordForm');
    var password = document.getElementById('new_password');
    var confirmation = document.getElementById('new_password_confirm');
    var error = document.getElementById('confirmPasswordError');
    if (form && password && confirmation && error) {
      function validateResetMatch() {
        var mismatched = confirmation.value && password.value !== confirmation.value;
        confirmation.setCustomValidity(mismatched ? 'As senhas não coincidem.' : '');
        confirmation.setAttribute('aria-invalid', mismatched ? 'true' : 'false');
        error.textContent = mismatched ? 'As senhas não coincidem.' : '';
      }
      password.addEventListener('input', validateResetMatch);
      confirmation.addEventListener('input', validateResetMatch);
      form.addEventListener('submit', validateResetMatch);
    }

    document.querySelectorAll('[data-password-confirm]').forEach(function (confirmationField) {
      var original = document.getElementById(confirmationField.dataset.passwordConfirm);
      if (!original) return;
      function validateInviteMatch() {
        var mismatched = confirmationField.value && original.value !== confirmationField.value;
        confirmationField.setCustomValidity(mismatched ? 'As senhas não coincidem.' : '');
        confirmationField.setAttribute('aria-invalid', mismatched ? 'true' : 'false');
      }
      original.addEventListener('input', validateInviteMatch);
      confirmationField.addEventListener('input', validateInviteMatch);
    });
  }

  var LOGIN_EMAIL_DOMAIN = 'centralcomm.media';
  var LOGIN_LOCAL_RE = /^[a-z0-9](?:[a-z0-9._+-]*[a-z0-9])?$/i;

  function setupCorporateEmail() {
    document.querySelectorAll('[data-email-lock]').forEach(function (lock) {
      var form = lock.closest('form');
      var local = lock.querySelector('.auth-email-local');
      var hidden = form ? form.querySelector('input[name="email"]') : null;
      var error = form ? form.querySelector('#emailDomainError') : null;
      if (!local) return;

      function showError(message) {
        lock.classList.toggle('is-invalid', Boolean(message));
        local.setCustomValidity(message || '');
        local.setAttribute('aria-invalid', message ? 'true' : 'false');
        if (error) {
          error.hidden = !message;
          if (message) error.textContent = message;
        }
      }

      function compose() {
        var value = local.value.trim().toLowerCase();
        if (value.indexOf('@') !== -1) {
          var parts = value.split('@');
          var domain = parts.slice(1).join('@');
          if (domain && domain !== LOGIN_EMAIL_DOMAIN) {
            if (hidden) hidden.value = '';
            showError('Use apenas o email @' + LOGIN_EMAIL_DOMAIN + '.');
            return '';
          }
          value = parts[0];
          if (local.value !== value) local.value = value;
        }

        if (!value) {
          if (hidden) hidden.value = '';
          showError('');
          return '';
        }

        if (!LOGIN_LOCAL_RE.test(value)) {
          if (hidden) hidden.value = '';
          showError('Informe só o nome do email, sem espaços ou símbolos extras.');
          return '';
        }

        var email = value + '@' + LOGIN_EMAIL_DOMAIN;
        if (hidden) hidden.value = email;
        showError('');
        return email;
      }

      local.addEventListener('input', compose);
      local.addEventListener('blur', compose);
      local.addEventListener('paste', function () {
        window.setTimeout(compose, 0);
      });
      compose();
    });
  }

  function setupForms() {
    document.querySelectorAll('[data-auth-form]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!form.checkValidity()) {
          event.preventDefault();
          form.reportValidity();
          return;
        }
        var button = form.querySelector('[type="submit"]');
        if (button) {
          button.disabled = true;
          button.classList.add('is-loading');
        }
      });
    });
  }

  function setupSignupFlow() {
    document.querySelectorAll('[data-auth-signup]').forEach(function (form) {
      var steps = Array.prototype.slice.call(form.querySelectorAll('[data-signup-step]'));
      var progress = Array.prototype.slice.call(form.querySelectorAll('[data-signup-progress]'));
      var name = form.elements.nome;
      if (!steps.length || !name) return;

      function showStep(stepNumber, focusHeading) {
        steps.forEach(function (step) {
          var active = Number(step.dataset.signupStep) === stepNumber;
          step.hidden = !active;
          step.setAttribute('aria-hidden', active ? 'false' : 'true');
        });
        progress.forEach(function (item) {
          var active = Number(item.dataset.signupProgress) === stepNumber;
          item.classList.toggle('is-active', active);
          item.classList.toggle('is-complete', Number(item.dataset.signupProgress) < stepNumber);
          if (active) item.setAttribute('aria-current', 'step');
          else item.removeAttribute('aria-current');
        });
        if (focusHeading) {
          var heading = form.querySelector('[data-signup-step="' + stepNumber + '"] h2');
          if (heading) heading.focus();
        }
      }

      form.querySelectorAll('[data-signup-next]').forEach(function (button) {
        button.addEventListener('click', function () {
          if (!name.checkValidity()) {
            name.reportValidity();
            return;
          }
          showStep(2, true);
        });
      });
      form.querySelectorAll('[data-signup-back]').forEach(function (button) {
        button.addEventListener('click', function () { showStep(1, true); });
      });

      showStep(Number(form.dataset.signupStartStep) === 2 ? 2 : 1, false);
    });
  }

  function setupFlashMessages() {
    document.querySelectorAll('[data-auth-flash-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        var flash = button.closest('.auth-flash');
        if (flash) flash.remove();
      });
    });
  }

  function setupViewportLock() {
    var root = document.documentElement;

    function applyViewport() {
      var viewport = window.visualViewport;
      var height = viewport ? viewport.height : window.innerHeight;
      root.style.setProperty('--vvh', Math.round(height) + 'px');
      var keyboardOpen = Boolean(viewport && (window.innerHeight - viewport.height) > 140);
      document.body.classList.toggle('is-keyboard-open', keyboardOpen);
      if (window.scrollY || window.scrollX) {
        window.scrollTo(0, 0);
      }
    }

    applyViewport();
    window.addEventListener('resize', applyViewport);
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', applyViewport);
      window.visualViewport.addEventListener('scroll', applyViewport);
    }
    document.addEventListener('focusin', function () {
      window.setTimeout(applyViewport, 80);
    });
    document.addEventListener('focusout', function () {
      window.setTimeout(applyViewport, 80);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupViewportLock();
    setupPasswordToggles();
    setupPasswordStrength();
    setupMatchingPasswords();
    setupCorporateEmail();
    setupForms();
    setupSignupFlow();
    setupFlashMessages();
  });
})();
