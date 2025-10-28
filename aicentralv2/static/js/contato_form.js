/**
 * Contato Form Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CONTATO FORM LOADED ===');
    console.log('URL:', window.location.href);
    
    const isEdit = window.location.href.includes('/editar');
    console.log('Modo:', isEdit ? 'Editar' : 'Novo');
    
    // Máscara de telefone
    const telefoneInput = document.querySelector('input[name="telefone"]');
    if (telefoneInput) {
        telefoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length <= 11) {
                value = value.replace(/^(\d{2})(\d)/, '($1) $2');
                value = value.replace(/(\d{5})(\d)/, '$1-$2');
            }
            
            e.target.value = value;
        });
        console.log('✓ Phone mask initialized');
    }
    
    // Toggle password visibility
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const wrapper = this.closest('.password-wrapper');
            const input = wrapper.querySelector('input');
            
            if (input.type === 'password') {
                input.type = 'text';
                this.classList.remove('fa-eye');
                this.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                this.classList.remove('fa-eye-slash');
                this.classList.add('fa-eye');
            }
        });
    });
    
    if (passwordToggles.length > 0) {
        console.log(`✓ ${passwordToggles.length} password toggle(s) initialized`);
    }
    
    // Validação do formulário
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const nomeCompleto = document.querySelector('input[name="nome_completo"]').value.trim();
            const email = document.querySelector('input[name="email"]').value.trim();
            const cliente = document.querySelector('select[name="pk_id_tbl_cliente"]').value;
            
            if (!nomeCompleto) {
                alert('Nome Completo é obrigatório!');
                e.preventDefault();
                return false;
            }
            
            if (!email) {
                alert('Email é obrigatório!');
                e.preventDefault();
                return false;
            }
            
            if (!cliente) {
                alert('Selecione um cliente!');
                e.preventDefault();
                return false;
            }
            
            // Validar senha apenas para novo contato
            if (!isEdit) {
                const senha = document.querySelector('input[name="senha"]').value;
                if (!senha || senha.length < 6) {
                    alert('Senha deve ter no mínimo 6 caracteres!');
                    e.preventDefault();
                    return false;
                }
            }
            
            console.log('Enviando formulário:', {
                nome_completo: nomeCompleto,
                email: email,
                cliente_id: cliente
            });
        });
    }
    
    // Auto-focus no primeiro campo
    const firstInput = document.querySelector('input[autofocus]');
    if (firstInput) {
        firstInput.focus();
    }
});

console.log('Contato_form.js loaded successfully');