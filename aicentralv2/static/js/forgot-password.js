/**
 * AIcentralv2 - Scripts da Página de Recuperação de Senha
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔑 Forgot password page loaded');
    
    const form = document.getElementById('forgotPasswordForm');
    const submitBtn = document.getElementById('submitBtn');
    
    if (form) {
        form.addEventListener('submit', handleSubmit);
    }
    
    // Validação em tempo real
    initRealTimeValidation();
});

/**
 * Processa o envio do formulário
 */
function handleSubmit(e) {
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const submitBtn = document.getElementById('submitBtn');
    
    // Validações básicas
    if (!username || !email) {
        e.preventDefault();
        showAlert('Todos os campos são obrigatórios!', 'error');
        return false;
    }
    
    if (!validateEmail(email)) {
        e.preventDefault();
        showAlert('Email inválido!', 'error');
        return false;
    }
    
    // Desabilitar botão e mostrar loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ Enviando email...';
}

/**
 * Validação em tempo real
 */
function initRealTimeValidation() {
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    
    if (usernameInput) {
        usernameInput.addEventListener('blur', () => {
            const value = usernameInput.value.trim();
            if (value.length < 3) {
                highlightField(usernameInput, false);
                showFieldError(usernameInput, 'Nome de usuário muito curto');
            } else {
                highlightField(usernameInput, true);
                clearFieldError(usernameInput);
            }
        });
        
        usernameInput.addEventListener('input', () => {
            clearFieldError(usernameInput);
        });
    }
    
    if (emailInput) {
        emailInput.addEventListener('blur', () => {
            const value = emailInput.value.trim();
            if (!validateEmail(value)) {
                highlightField(emailInput, false);
                showFieldError(emailInput, 'Email inválido');
            } else {
                highlightField(emailInput, true);
                clearFieldError(emailInput);
            }
        });
        
        emailInput.addEventListener('input', () => {
            clearFieldError(emailInput);
            emailInput.value = emailInput.value.toLowerCase();
        });
    }
}

/**
 * Valida email
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Destaca campo
 */
function highlightField(field, isValid) {
    field.style.borderColor = isValid ? '#2ecc71' : '#e74c3c';
}

/**
 * Mostra erro no campo
 */
function showFieldError(field, message) {
    clearFieldError(field);
    
    const error = document.createElement('small');
    error.className = 'field-error';
    error.style.cssText = 'color: #e74c3c; display: block; margin-top: 0.3rem; font-size: 0.85rem;';
    error.textContent = message;
    
    field.parentElement.appendChild(error);
}

/**
 * Remove erro do campo
 */
function clearFieldError(field) {
    const error = field.parentElement.querySelector('.field-error');
    if (error) {
        error.remove();
    }
}

/**
 * Mostra alert
 */
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    const form = document.getElementById('forgotPasswordForm');
    form.parentNode.insertBefore(alert, form);
    
    setTimeout(() => {
        alert.remove();
    }, 5000);
}