(function () {
  'use strict';

  var cities = {
    bh: { name: 'Belo Horizonte', position: '52% center' },
    rio: { name: 'Rio de Janeiro', position: '48% center' }
  };

  function selectCity() {
    var image = document.getElementById('authCityImage');
    var label = document.getElementById('authCityName');
    if (!image || !label) return;

    var cityKey = null;
    try {
      cityKey = sessionStorage.getItem('cx-auth-city');
      if (!cities[cityKey]) {
        cityKey = Math.random() >= 0.5 ? 'rio' : 'bh';
        sessionStorage.setItem('cx-auth-city', cityKey);
      }
    } catch (error) {
      cityKey = new Date().getDate() % 2 ? 'bh' : 'rio';
    }

    var source = cityKey === 'rio' ? image.dataset.rioSrc : image.dataset.bhSrc;
    image.classList.add('is-changing');
    var preload = new Image();
    preload.onload = function () {
      image.src = source;
      image.style.objectPosition = cities[cityKey].position;
      label.textContent = cities[cityKey].name;
      image.classList.remove('is-changing');
    };
    preload.onerror = function () {
      image.classList.remove('is-changing');
    };
    preload.src = source;
  }

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
    if (!form || !password || !confirmation || !error) return;

    function validateMatch() {
      var mismatched = confirmation.value && password.value !== confirmation.value;
      confirmation.setCustomValidity(mismatched ? 'As senhas não coincidem.' : '');
      confirmation.setAttribute('aria-invalid', mismatched ? 'true' : 'false');
      error.textContent = mismatched ? 'As senhas não coincidem.' : '';
      return !mismatched;
    }

    password.addEventListener('input', validateMatch);
    confirmation.addEventListener('input', validateMatch);
    form.addEventListener('submit', validateMatch);
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

  function setupFlashMessages() {
    document.querySelectorAll('[data-auth-flash-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        var flash = button.closest('.auth-flash');
        if (flash) flash.remove();
      });
    });
  }

  window.showToast = window.showToast || function (message, type) {
    var container = document.querySelector('.auth-flashes');
    if (!container) {
      container = document.createElement('div');
      container.className = 'auth-flashes';
      container.setAttribute('aria-live', 'polite');
      var content = document.querySelector('.auth-page-content');
      if (content) content.before(container);
    }
    if (!container) return;
    var flash = document.createElement('div');
    flash.className = 'auth-flash auth-flash--' + (type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'info');
    flash.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i><span></span>';
    flash.querySelector('span').textContent = message;
    container.appendChild(flash);
  };

  document.addEventListener('DOMContentLoaded', function () {
    selectCity();
    setupPasswordToggles();
    setupPasswordStrength();
    setupMatchingPasswords();
    setupForms();
    setupFlashMessages();
  });
})();
