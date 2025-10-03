/**
 * AIcentralv2 - Scripts Base
 * Scripts globais da aplicação
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('🤖 AIcentralv2 v2.0.0 - Aplicação carregada');
    
    // Auto-hide alerts após 5 segundos
    initAlerts();
    
    // Animação de cards ao scroll
    initScrollAnimations();
});

/**
 * Inicializa o sistema de alerts com auto-hide
 */
function initAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // Adicionar botão de fechar
        const closeBtn = document.createElement('span');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = 'float: right; font-size: 1.5rem; cursor: pointer; margin-left: 1rem;';
        closeBtn.onclick = () => removeAlert(alert);
        alert.insertBefore(closeBtn, alert.firstChild);
        
        // Auto-hide após 5 segundos
        setTimeout(() => {
            removeAlert(alert);
        }, 5000);
    });
}

/**
 * Remove um alert com animação
 */
function removeAlert(alert) {
    alert.style.opacity = '0';
    alert.style.transform = 'translateY(-20px)';
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 300);
}

/**
 * Inicializa animações de scroll
 */
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // Observar elementos com a classe 'animate-on-scroll'
    document.querySelectorAll('.animate-on-scroll').forEach(element => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        element.style.transition = 'opacity 0.5s, transform 0.5s';
        observer.observe(element);
    });
}

/**
 * Formata email para lowercase
 */
function formatEmail(email) {
    return email.toLowerCase().trim();
}

/**
 * Valida email
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Exibe mensagem de confirmação
 */
function confirm(message) {
    return window.confirm(message);
}