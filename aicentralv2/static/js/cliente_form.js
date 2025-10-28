/**
 * Cliente Form Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CLIENTE FORM LOADED ===');
    console.log('URL:', window.location.href);
    
    const isEdit = window.location.href.includes('/editar');
    console.log('Modo:', isEdit ? 'Editar' : 'Novo');
    
    // Máscara CNPJ
    const cnpjInput = document.querySelector('input[name="cnpj"]');
    if (cnpjInput) {
        cnpjInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length <= 14) {
                value = value.replace(/^(\d{2})(\d)/, '$1.$2');
                value = value.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
                value = value.replace(/\.(\d{3})(\d)/, '.$1/$2');
                value = value.replace(/(\d{4})(\d)/, '$1-$2');
            }
            
            e.target.value = value;
        });
        console.log('✓ CNPJ mask initialized');
    }
    
    // Validação do formulário
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const razaoSocial = document.querySelector('input[name="razao_social"]').value.trim();
            const nomeFantasia = document.querySelector('input[name="nome_fantasia"]').value.trim();
            
            if (!razaoSocial) {
                alert('Razão Social é obrigatória!');
                e.preventDefault();
                return false;
            }
            
            if (!nomeFantasia) {
                alert('Nome Fantasia é obrigatório!');
                e.preventDefault();
                return false;
            }
            
            console.log('Enviando formulário:', {
                razao_social: razaoSocial,
                nome_fantasia: nomeFantasia
            });
        });
    }
    
    // Auto-focus no primeiro campo
    const firstInput = document.querySelector('input[autofocus]');
    if (firstInput) {
        firstInput.focus();
    }
});

console.log('Cliente_form.js loaded successfully');