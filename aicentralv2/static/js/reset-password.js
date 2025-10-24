/**
 * =====================================================
 * RESET PASSWORD - JavaScript
 * Validação e funcionalidades da página de reset
 * =====================================================
 */

'use strict';

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Reset Password JS carregado');
    
    initResetPasswordForm();
    initPasswordStrengthChecker();
    initPasswordToggles();
});

/**
 * Inicializa o formulário de reset
 */
function initResetPasswordForm() {
    const form = document.getElementById('resetForm');
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const submitBtn = document.getElementById('submitBtn');
    
    if (!form) return;
    
    // Validação no submit
    form.addEventListener('submit', function(e) {
        const password = passwordInput.value;
        const confirm = confirmInput.value;
        
        // Validar senhas coincidem
        if (password !== confirm) {
            e.preventDefault();
            showAlert('❌ As senhas não coincidem!');
            confirmInput.focus();
            return false;
        }
        
        // Validar tamanho mínimo
        if (password.length < 6) {
            e.preventDefault();
            showAlert('❌ A senha deve ter no mínimo 6 caracteres!');
            passwordInput.focus();
            return false;
        }
        
        // Desabilitar botão
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Redefinindo...';
        
        return true;
    });
}

/**
 * Inicializa verificador de força de senha
 */
function initPasswordStrengthChecker() {
    const passwordInput = document.getElementById('password');
    const strengthBar = document.getElementById('strengthBar');
    const strengthText = document.getElementById('strengthText');
    
    if (!passwordInput || !strengthBar) return;
    
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        const strength = calculatePasswordStrength(password);
        
        // Remover todas as classes
        strengthBar.className = 'strength-fill';
        
        // Adicionar classe baseada na força
        if (strength.level === 'weak') {
            strengthBar.classList.add('strength-weak');
            strengthText.textContent = '⚠️ Senha fraca';
            strengthText.style.color = '#f44336';
        } else if (strength.level === 'medium') {
            strengthBar.classList.add('strength-medium');
            strengthText.textContent = '⚡ Senha média';
            strengthText.style.color = '#ff9800';
        } else if (strength.level === 'strong') {
            strengthBar.classList.add('strength-strong');
            strengthText.textContent = '✅ Senha forte';
            strengthText.style.color = '#4caf50';
        } else {
            strengthText.textContent = '';
        }
    });
}

/**
 * Calcula força da senha
 */
function calculatePasswordStrength(password) {
    let score = 0;
    
    if (password.length === 0) {
        return { level: 'none', score: 0 };
    }
    
    // Critérios de força
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;
    
    // Determinar nível
    if (score <= 2) {
        return { level: 'weak', score };
    } else if (score <= 3) {
        return { level: 'medium', score };
    } else {
        return { level: 'strong', score };
    }
}

/**
 * Inicializa toggles de visibilidade de senha
 */
function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('.toggle-password');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const input = this.parentElement.querySelector('input');
            const icon = this.querySelector('i');
            
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });
}

/**
 * Toggle visibilidade de um campo específico
 * (função global para uso no HTML se necessário)
 */
window.togglePassword = function(fieldId) {
    const field = document.getElementById(fieldId);
    const wrapper = field.parentElement;
    const button = wrapper.querySelector('.toggle-password');
    const icon = button.querySelector('i');
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
};

/**
 * Mostra alerta
 */
function showAlert(message) {
    alert(message);
}

console.log('%c✨ Reset Password Ready', 'color: #667eea; font-weight: bold;');