/**
 * Cliente Form Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CLIENTE FORM LOADED ===');
    
    const isEdit = window.location.href.includes('/editar');
    console.log('Modo:', isEdit ? 'Editar' : 'Novo');
    
    // Controle de visibilidade baseado no tipo de pessoa
    const pessoaRadios = document.querySelectorAll('input[name="pessoa"]');
    const pessoaJuridicaFields = document.querySelectorAll('.pessoa-juridica');
    const pessoaFisicaFields = document.querySelectorAll('.pessoa-fisica');
    
    function updateFieldsVisibility(pessoaTipo) {
        // Update class-based visibility
        pessoaJuridicaFields.forEach(field => {
            field.classList.toggle('hidden', pessoaTipo !== 'J');
            const inputs = field.querySelectorAll('input, select');
            inputs.forEach(input => input.required = pessoaTipo === 'J');
        });
        
        pessoaFisicaFields.forEach(field => {
            field.classList.toggle('hidden', pessoaTipo !== 'F');
            const inputs = field.querySelectorAll('input, select');
            inputs.forEach(input => input.required = pessoaTipo === 'F');
        });

        // Update placeholders and masks for CNPJ/CPF field
        const documentInput = document.querySelector('input[name="cnpj"]');
        if (documentInput) {
            if (pessoaTipo === 'F') {
                documentInput.placeholder = '000.000.000-00';
                documentInput.maxLength = 14;
            } else {
                documentInput.placeholder = '00.000.000/0000-00';
                documentInput.maxLength = 18;
            }
            documentInput.value = ''; // Clear the field when switching types
        }
    }
    
    pessoaRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            updateFieldsVisibility(e.target.value);
        });
    });
    
    // Inicializar campos com base no tipo de pessoa selecionado
    const selectedPessoa = document.querySelector('input[name="pessoa"]:checked');
    if (selectedPessoa) {
        updateFieldsVisibility(selectedPessoa.value);
    }
    
    // Máscara CNPJ/CPF
    const documentInput = document.querySelector('input[name="cnpj"]');
    if (documentInput) {
        documentInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            const pessoaTipo = document.querySelector('input[name="pessoa"]:checked').value;
            
            if (pessoaTipo === 'F') {
                // CPF mask
                if (value.length <= 11) {
                    value = value.replace(/^(\d{3})(\d)/, '$1.$2');
                    value = value.replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3');
                    value = value.replace(/\.(\d{3})(\d)/, '.$1-$2');
                }
            } else {
                // CNPJ mask
                if (value.length <= 14) {
                    value = value.replace(/^(\d{2})(\d)/, '$1.$2');
                    value = value.replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3');
                    value = value.replace(/\.(\d{3})(\d)/, '.$1/$2');
                    value = value.replace(/(\d{4})(\d)/, '$1-$2');
                }
            }
            
            e.target.value = value;
        });
        console.log('✓ Document mask (CNPJ/CPF) initialized');
    }
    
    // Validação do formulário
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const razaoSocial = document.querySelector('input[name="razao_social"]').value.trim();
            const nomeFantasia = document.querySelector('input[name="nome_fantasia"]').value.trim();
            
            const pessoaTipo = document.querySelector('input[name="pessoa"]:checked').value;

            if (pessoaTipo === 'J') {
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
            } else {
                if (!razaoSocial) {
                    alert('Razão Social é obrigatória!');
                    e.preventDefault();
                    return false;
                }
                
                if (!nomeFantasia) {
                    alert('Nome Completo é obrigatório!');
                    e.preventDefault();
                    return false;
                }
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