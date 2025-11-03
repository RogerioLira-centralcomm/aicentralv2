/**
 * Contato Form Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CONTATO FORM LOADED ===');
    console.log('URL:', window.location.href);
    
    const isEdit = window.location.href.includes('/editar');
    console.log('Modo:', isEdit ? 'Editar' : 'Novo');

    // Função para limpar e proteger campo contra preenchimento automático
    function protegerCampo(campo) {
        if (!campo) return;
        
        // Desabilita temporariamente
        campo.disabled = true;
        const valorOriginal = campo.value;
        
        // Força limpeza após um momento
        setTimeout(() => {
            campo.disabled = false;
            campo.value = valorOriginal;
            
            // Previne o preenchimento automático mesmo após o foco
            campo.addEventListener('focus', function(e) {
                if (this.value !== valorOriginal) {
                    setTimeout(() => this.value = valorOriginal, 10);
                }
            });
        }, 100);
    }

    // Limpa campos para evitar preenchimento automático
    if (!isEdit) {
        // Protege todos os campos de input
        const camposParaProteger = [
            'nome_completo',
            'email',
            'telefone',
            'senha_visible'
        ];

        camposParaProteger.forEach(id => {
            const campo = document.getElementById(id);
            if (campo) {
                campo.value = ''; // Limpa inicialmente
                
                // Previne preenchimento automático
                campo.setAttribute('autocomplete', 'new-' + id);
                campo.setAttribute('data-form-type', 'other');
                
                // Adiciona proteção especial
                protegerCampo(campo);
                
                // Previne preenchimento automático no foco
                campo.addEventListener('focus', function() {
                    if (this.value && !isEdit) {
                        setTimeout(() => this.value = '', 1);
                    }
                });
            }
        });

        // Espera um pouco e limpa novamente
        setTimeout(() => {
            camposParaProteger.forEach(id => {
                const campo = document.getElementById(id);
                if (campo) campo.value = '';
            });
        }, 500);
    }
    
    // Máscara de telefone
    const telefoneInput = document.querySelector('#telefone');
    if (telefoneInput) {
        telefoneInput.addEventListener('input', function(e) {
            const cursorPos = this.selectionStart;
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length <= 11) {
                value = value.replace(/^(\d{2})(\d)/, '($1) $2');
                value = value.replace(/(\d{5})(\d)/, '$1-$2');
            }
            
            e.target.value = value;

            // Mantém o cursor na posição correta após a formatação
            const newPos = Math.max(0, Math.min(value.length, cursorPos));
            this.setSelectionRange(newPos, newPos);
        });
        console.log('✓ Phone mask initialized');
    }

    // Se for um novo contato, garante campos limpos sem chamar funções inexistentes
    if (!isEdit) {
        const campos = ['nome_completo', 'email', 'telefone', 'senha_visible'];
        campos.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
    }
    
    // Toggle password visibility
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const container = this.closest('.relative') || this.parentElement;
            if (!container) return;
            // Seleciona os campos visíveis (text com -webkit-text-security)
            const input = container.querySelector('#senha_visible, #nova_senha_visible');
            if (!input) return;

            const revealed = input.dataset.revealed === '1';
            if (revealed) {
                input.style.webkitTextSecurity = 'disc';
                input.dataset.revealed = '0';
                this.classList.remove('fa-eye-slash');
                this.classList.add('fa-eye');
            } else {
                input.style.webkitTextSecurity = 'none';
                input.dataset.revealed = '1';
                this.classList.remove('fa-eye');
                this.classList.add('fa-eye-slash');
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
            const setorEl = document.getElementById('setor_select');
            const cargoEl = document.getElementById('cargo_select');
            const setor = setorEl ? setorEl.value : '';
            const cargo = cargoEl ? cargoEl.value : '';
            
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

            // Validação obrigatória de Setor e Cargo
            if (!setor) {
                alert('Selecione um setor!');
                e.preventDefault();
                return false;
            }

            if (!cargo) {
                alert('Selecione um cargo!');
                e.preventDefault();
                return false;
            }

            if (cargoEl && cargoEl.disabled) {
                alert('Escolha um setor para habilitar os cargos e selecione um cargo.');
                e.preventDefault();
                return false;
            }

            // Coerência: o cargo selecionado precisa pertencer ao setor selecionado
            if (cargoEl && cargoEl.selectedOptions && cargoEl.selectedOptions.length > 0) {
                const selectedOpt = cargoEl.selectedOptions[0];
                const cargoSetorId = selectedOpt && selectedOpt.dataset ? selectedOpt.dataset.setorId : undefined;
                if (cargoSetorId && String(cargoSetorId).trim() !== String(setor).trim()) {
                    alert('O cargo selecionado não pertence ao setor escolhido.');
                    e.preventDefault();
                    return false;
                }
            }
            
            // Validar senha apenas para novo contato (campo visível)
            if (!isEdit) {
                const senha = (document.getElementById('senha_visible') || {}).value || '';
                if (!senha || senha.length < 6) {
                    alert('Senha deve ter no mínimo 6 caracteres!');
                    e.preventDefault();
                    return false;
                }
            }
            
            // Sincroniza campos visíveis -> reais antes de enviar
            const senhaVisible = document.getElementById('senha_visible');
            const senhaReal = document.getElementById('senha_real');
            if (senhaVisible && senhaReal) senhaReal.value = senhaVisible.value || '';

            const novaSenhaVisible = document.getElementById('nova_senha_visible');
            const novaSenhaReal = document.getElementById('nova_senha_real');
            if (novaSenhaVisible && novaSenhaReal) novaSenhaReal.value = novaSenhaVisible.value || '';
            
            console.log('Enviando formulário:', {
                nome_completo: nomeCompleto,
                email: email,
                cliente_id: cliente,
                setor_id: setor,
                cargo_id: cargo
            });
        });
    }
    
    // Inicializa campos visíveis de senha mascarados e limpos
    ['senha_visible', 'nova_senha_visible'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.value = '';
            el.style.webkitTextSecurity = 'disc';
            el.dataset.revealed = '0';
        }
    });

    // Foca no primeiro campo após um breve delay
    setTimeout(() => {
        const nomeInput = document.getElementById('nome_completo');
        if (nomeInput) {
            nomeInput.focus();
            // Limpa novamente caso o navegador tenha preenchido
            if (!isEdit) nomeInput.value = '';
        }
    }, 100);
});

console.log('Contato_form.js loaded successfully');