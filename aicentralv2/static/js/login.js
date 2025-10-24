/**
 * =====================================================
 * LOGIN - JavaScript
 * Validação e funcionalidades da página de login
 * =====================================================
 */

'use strict';

// Elementos do DOM
let loginForm;
let emailInput;
let passwordInput;
let submitBtn;
let loadingOverlay;

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Login JS carregado');
    
    initElements();
    initFormValidation();
    initFlashMessages();
    loadRememberedCredentials();
});

/**
 * Inicializa elementos do DOM
 */
function initElements() {
    loginForm = document.getElementById('loginForm');
    emailInput = document.getElementById('email');
    passwordInput = document.getElementById('password');
    submitBtn = document.getElementById('submitBtn');
    loadingOverlay = document.getElementById('loadingOverlay');
}

/**
 * Inicializa validação do formulário
 */
function initFormValidation() {
    if (!loginForm) return;
    
    // Validação no submit
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Limpar erros anteriores
        clearErrors();
        
        // Validar campos
        let isValid = true;
        
        // Validar email
        const email = emailInput.value.trim();
        if (!email) {
            showError('email', 'Email é obrigatório');
            isValid = false;
        } else if (!isValidEmail(email)) {
            showError('email', 'Email inválido');
            isValid = false;
        }
        
        // Validar senha
        const password = passwordInput.value;
        if (!password) {
            showError('password', 'Senha é obrigatória');
            isValid = false;
        } else if (password.length < 6) {
            showError('password', 'Senha deve ter no mínimo 6 caracteres');
            isValid = false;
        }
        
        // Se válido, enviar
        if (isValid) {
            showLoading();
            saveCredentials();
            this.submit();
        }
    });
    
    // Limpar erro ao digitar
    emailInput.addEventListener('input', () => clearFieldError('email'));
    passwordInput.addEventListener('input', () => clearFieldError('password'));
}

/**
 * Valida formato de email
 */
function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

/**
 * Mostra erro em campo
 */
function showError(field, message) {
    const errorElement = document.getElementById(`${field}Error`);
    const inputGroup = document.querySelector(`#${field}`).closest('.input-group');
    
    if (errorElement) {
        errorElement.textContent = message;
    }
    
    if (inputGroup) {
        inputGroup.classList.add('has-error');
    }
}

/**
 * Limpa erro de campo específico
 */
function clearFieldError(field) {
    const errorElement = document.getElementById(`${field}Error`);
    const inputGroup = document.querySelector(`#${field}`).closest('.input-group');
    
    if (errorElement) {
        errorElement.textContent = '';
    }
    
    if (inputGroup) {
        inputGroup.classList.remove('has-error');
    }
}

/**
 * Limpa todos os erros
 */
function clearErrors() {
    const errorElements = document.querySelectorAll('.input-error');
    errorElements.forEach(el => el.textContent = '');
    
    const inputGroups = document.querySelectorAll('.input-group');
    inputGroups.forEach(group => group.classList.remove('has-error'));
}

/**
 * Mostra overlay de loading
 */
function showLoading() {
    if (loadingOverlay) {
        loadingOverlay.classList.add('active');
    }
    
    if (submitBtn) {
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;
    }
}

/**
 * Esconde overlay de loading
 */
function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.classList.remove('active');
    }
    
    if (submitBtn) {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

/**
 * Toggle visibilidade da senha
 */
function togglePassword() {
    const toggleIcon = document.getElementById('toggleIcon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye');
    }
}

/**
 * Salva credenciais se "lembrar" estiver marcado
 */
function saveCredentials() {
    const rememberCheckbox = document.getElementById('remember');
    
    if (rememberCheckbox && rememberCheckbox.checked) {
        localStorage.setItem('rememberedEmail', emailInput.value.trim());
    } else {
        localStorage.removeItem('rememberedEmail');
    }
}

/**
 * Carrega credenciais salvas
 */
function loadRememberedCredentials() {
    const rememberedEmail = localStorage.getItem('rememberedEmail');
    
    if (rememberedEmail) {
        emailInput.value = rememberedEmail;
        document.getElementById('remember').checked = true;
    }
}

/**
 * Inicializa flash messages (auto-close)
 */
function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(message => {
        // Auto-close após 5 segundos (exceto erros)
        const category = message.dataset.category;
        if (category !== 'error') {
            setTimeout(() => {
                message.style.animation = 'fadeOut 0.3s ease-out';
                setTimeout(() => message.remove(), 300);
            }, 5000);
        }
    });
}

/**
 * Abre WhatsApp para suporte
 */
function openWhatsAppSupport() {
    const phoneNumber = '5511999999999'; // Ajuste o número
    const message = encodeURIComponent('Olá! Preciso de ajuda com o login no CentralComm AI.');
    const url = `https://wa.me/${phoneNumber}?text=${message}`;
    
    window.open(url, '_blank');
}

// Expor funções globais
window.togglePassword = togglePassword;
window.openWhatsAppSupport = openWhatsAppSupport;

console.log('%c✨ Login Ready', 'color: #667eea; font-weight: bold;');