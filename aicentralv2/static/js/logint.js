/**
 * AIcentralv2 - Scripts da Página de Login
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('📝 Login page loaded');
    
    const loginForm = document.querySelector('form');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLoginSubmit);
    }
    
    // Auto-focus no campo de usuário
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.focus();
    }
    
    // Adicionar indicador de caps lock
    addCapsLockIndicator();
});

/**
 * Valida e processa o submit do login
 */
function handleLoginSubmit(e) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        e.preventDefault();
        showAlert('Por favor, preencha todos os campos!', 'error');
        return false;
    }
    
    if (username.length < 3) {
        e.preventDefault();
        showAlert('Usuário deve ter pelo menos 3 caracteres!', 'error');
        return false;
    }
    
    // Mostrar loading
    showLoading();
}

/**
 * Adiciona indicador de Caps Lock
 */
function addCapsLockIndicator() {
    const passwordInput = document.getElementById('password');
    
    if (passwordInput) {
        const indicator = document.createElement('small');
        indicator.id = 'caps-indicator';
        indicator.style.cssText = 'color: #f39c12; display: none; margin-top: 0.5rem;';
        indicator.textContent = '⚠️ Caps Lock está ativado';
        
        passwordInput.parentElement.appendChild(indicator);
        
        passwordInput.addEventListener('keyup', (e) => {
            const isCapsLock = e.getModifierState('CapsLock');
            indicator.style.display = isCapsLock ? 'block' : 'none';
        });
    }
}

/**
 * Mostra loading
 */
function showLoading() {
    const button = document.querySelector('.btn-login');
    if (button) {
        button.innerHTML = '🔄 Entrando...';
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