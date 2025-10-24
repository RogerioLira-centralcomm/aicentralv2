/**
 * =====================================================
 * FORGOT PASSWORD - JavaScript
 * Validação e funcionalidades da página de recuperação
 * =====================================================
 */

'use strict';

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Forgot Password JS carregado');
    
    initForgotPasswordForm();
});

/**
 * Inicializa o formulário de recuperação de senha
 */
function initForgotPasswordForm() {
    const form = document.getElementById('forgotPasswordForm');
    const emailInput = document.getElementById('email');
    const submitBtn = document.getElementById('submitBtn');
    
    if (!form) return;
    
    // Validação no submit
    form.addEventListener('submit', function(e) {
        const email = emailInput.value.trim();
        
        // Validar se campo está preenchido
        if (!email) {
            e.preventDefault();
            showAlert('❌ Por favor, digite seu email!', 'error');
            emailInput.focus();
            return false;
        }
        
        // Validar formato de email
        if (!isValidEmail(email)) {
            e.preventDefault();
            showAlert('❌ Por favor, digite um email válido!', 'error');
            emailInput.focus();
            return false;
        }
        
        // Desabilitar botão e mostrar loading
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Enviando...';
        
        // Permitir submit
        return true;
    });
    
    // Limpar erros ao digitar
    emailInput.addEventListener('input', function() {
        this.style.borderColor = '#e0e0e0';
        removeAlerts();
    });
}

/**
 * Valida formato de email
 */
function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

/**
 * Mostra alerta temporário
 */
function showAlert(message, type = 'error') {
    removeAlerts();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    const form = document.getElementById('forgotPasswordForm');
    form.parentNode.insertBefore(alert, form);
    
    // Auto-remover após 5 segundos
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

/**
 * Remove todos os alertas
 */
function removeAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        if (!alert.hasAttribute('data-flash')) {
            alert.remove();
        }
    });
}

console.log('%c✨ Forgot Password Ready', 'color: #667eea; font-weight: bold;');