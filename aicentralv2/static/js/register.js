/**
 * AIcentralv2 - Scripts da Página de Registro
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('📝 Register page loaded');
    
    const registerForm = document.querySelector('form');
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegisterSubmit);
    }
    
    // Validação em tempo real
    initRealTimeValidation();
});

/**
 * Valida e processa o submit do registro
 */
function handleRegisterSubmit(e) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const nomeCompleto = document.getElementById('nome_completo').value.trim();
    
    // Validações
    if (!username || !password || !confirmPassword || !nomeCompleto) {
        e.preventDefault();
        showAlert('Todos os campos são obrigatórios!', 'error');
        return false;
    }
    
    if (username.length < 3) {
        e.preventDefault();
        showAlert('Usuário deve ter pelo menos 3 caracteres!', 'error');
        return false;
    }
    
    if (password.length < 6) {
        e.preventDefault();
        showAlert('Senha deve ter pelo menos 6 caracteres!', 'error');
        return false;
    }
    
    if (password !== confirmPassword) {
        e.preventDefault();
        showAlert('As senhas não coincidem!', 'error');
        return false;
    }
    
    // Verificar força da senha
    const strength = checkPasswordStrength(password);
    if (strength < 2) {
        const confirm = window.confirm('Senha fraca! Deseja continuar mesmo assim?');
        if (!confirm) {
            e.preventDefault();
            return false;
        }
    }
    
    // Mostrar loading
    showLoading();
}

/**
 * Inicializa validação em tempo real
 */
function initRealTimeValidation() {
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    
    if (password && confirmPassword) {
        // Indicador de força da senha
        const strengthIndicator = createStrengthIndicator();
        password.parentElement.appendChild(strengthIndicator);
        
        password.addEventListener('input', () => {
            updateStrengthIndicator(password.value, strengthIndicator);
        });
        
        // Validação de confirmação de senha
        confirmPassword.addEventListener('input', () => {
            validatePasswordMatch(password.value, confirmPassword.value);
        });
    }
}

/**
 * Cria indicador de força da senha
 */
function createStrengthIndicator() {
    const container = document.createElement('div');
    container.id = 'strength-indicator';
    container.style.cssText = 'margin-top: 0.5rem;';
    
    const bar = document.createElement('div');
    bar.id = 'strength-bar';
    bar.style.cssText = 'height: 5px; border-radius: 3px; background: #ddd; transition: all 0.3s;';
    
    const text = document.createElement('small');
    text.id = 'strength-text';
    text.style.cssText = 'display: block; margin-top: 0.3rem; font-size: 0.85rem;';
    
    container.appendChild(bar);
    container.appendChild(text);
    
    return container;
}

/**
 * Atualiza indicador de força da senha
 */
function updateStrengthIndicator(password, container) {
    const strength = checkPasswordStrength(password);
    const bar = container.querySelector('#strength-bar');
    const text = container.querySelector('#strength-text');
    
    const colors = ['#e74c3c', '#f39c12', '#2ecc71', '#27ae60'];
    const labels = ['Muito fraca', 'Fraca', 'Boa', 'Forte'];
    const widths = ['25%', '50%', '75%', '100%'];
    
    if (password.length === 0) {
        bar.style.width = '0%';
        text.textContent = '';
        return;
    }
    
    bar.style.width = widths[strength];
    bar.style.background = colors[strength];
    text.style.color = colors[strength];
    text.textContent = `Força: ${labels[strength]}`;
}

/**
 * Verifica força da senha
 */
function checkPasswordStrength(password) {
    let strength = 0;
    
    if (password.length >= 6) strength++;
    if (password.length >= 10) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;
    
    return Math.min(strength, 3);
}

/**
 * Valida se as senhas coincidem
 */
function validatePasswordMatch(password, confirmPassword) {
    const confirmInput = document.getElementById('confirm_password');
    
    if (confirmPassword.length === 0) {
        confirmInput.style.borderColor = '';
        return;
    }
    
    if (password === confirmPassword) {
        confirmInput.style.borderColor = '#2ecc71';
    } else {
        confirmInput.style.borderColor = '#e74c3c';
    }
}

/**
 * Mostra loading
 */
function showLoading() {
    const button = document.querySelector('.btn-login');
    if (button) {
        button.innerHTML = '⏳ Criando conta...';
        button.disabled = true;
    }
}

/**
 * Mostra alert temporário
 */
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    const form = document.querySelector('form');
    form.parentNode.insertBefore(alert, form);
    
    setTimeout(() => {
        alert.remove();
    }, 3000);
}