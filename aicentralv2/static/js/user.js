/**
 * Script para página de usuários - VERSÃO MELHORADA
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 user.js carregado');

    // Elementos
    const nomeInput = document.getElementById('nome');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const idadeInput = document.getElementById('idade');
    const passwordInput = document.getElementById('password');
    const form = document.querySelector('form');
    const submitBtn = document.querySelector('.btn-submit');

    /**
     * Normaliza string
     */
    function normalizarString(str) {
        return str
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9\s]/g, '')
            .replace(/\s+/g, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '')
            .substring(0, 50);
    }

    /**
     * Preview de username
     */
    if (nomeInput && usernameInput) {
        let previewDiv = document.getElementById('username-preview');
        if (!previewDiv) {
            previewDiv = document.createElement('div');
            previewDiv.id = 'username-preview';
            usernameInput.parentNode.appendChild(previewDiv);
        }

        nomeInput.addEventListener('input', function() {
            const nome = this.value.trim();

            if (nome && !usernameInput.value) {
                const username = normalizarString(nome);

                if (username) {
                    previewDiv.innerHTML = `💡 Sugestão de username: <strong>${username}</strong>`;
                    previewDiv.classList.add('show');
                    usernameInput.placeholder = username;
                } else {
                    previewDiv.classList.remove('show');
                }
            } else {
                previewDiv.classList.remove('show');
            }
        });

        usernameInput.addEventListener('input', function() {
            if (this.value) {
                previewDiv.classList.remove('show');
            }
        });

        usernameInput.addEventListener('blur', function() {
            if (this.value) {
                this.value = normalizarString(this.value);
            }
        });
    }

    /**
     * Validação de email
     */
    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            const email = this.value.trim();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (email && !emailRegex.test(email)) {
                this.setCustomValidity('Email inválido');
                this.reportValidity();
            } else {
                this.setCustomValidity('');
            }
        });

        emailInput.addEventListener('input', function() {
            this.setCustomValidity('');
        });
    }

    /**
     * Validação de idade
     */
    if (idadeInput) {
        idadeInput.addEventListener('blur', function() {
            const idade = parseInt(this.value);

            if (isNaN(idade)) {
                this.setCustomValidity('Idade deve ser um número');
                this.reportValidity();
            } else if (idade < 0 || idade > 150) {
                this.setCustomValidity('Idade deve estar entre 0 e 150');
                this.reportValidity();
            } else {
                this.setCustomValidity('');
            }
        });

        idadeInput.addEventListener('input', function() {
            this.setCustomValidity('');
        });
    }

    /**
     * Indicador de força da senha - MELHORADO
     */
    if (passwordInput) {
        let strengthDiv = document.getElementById('password-strength');
        if (!strengthDiv) {
            strengthDiv = document.createElement('div');
            strengthDiv.id = 'password-strength';
            passwordInput.parentNode.appendChild(strengthDiv);
        }

        passwordInput.addEventListener('input', function() {
            const senha = this.value;

            if (!senha) {
                strengthDiv.style.display = 'none';
                strengthDiv.className = '';
                return;
            }

            // Calcular força
            let forca = 0;
            let criterios = [];

            if (senha.length >= 8) {
                forca++;
                criterios.push('8+ caracteres');
            }
            if (senha.length >= 12) {
                forca++;
                criterios.push('12+ caracteres');
            }
            if (/[a-z]/.test(senha)) {
                forca++;
                criterios.push('minúsculas');
            }
            if (/[A-Z]/.test(senha)) {
                forca++;
                criterios.push('MAIÚSCULAS');
            }
            if (/[0-9]/.test(senha)) {
                forca++;
                criterios.push('números');
            }
            if (/[^a-zA-Z0-9]/.test(senha)) {
                forca++;
                criterios.push('símbolos');
            }

            // Exibir força
            strengthDiv.style.display = 'block';
            strengthDiv.className = '';

            if (forca <= 2) {
                strengthDiv.innerHTML = '🔴 Senha fraca - ' + criterios.join(', ');
                strengthDiv.classList.add('weak');
            } else if (forca <= 4) {
                strengthDiv.innerHTML = '🟡 Senha média - ' + criterios.join(', ');
                strengthDiv.classList.add('medium');
            } else {
                strengthDiv.innerHTML = '🟢 Senha forte - ' + criterios.join(', ');
                strengthDiv.classList.add('strong');
            }
        });
    }

    /**
     * Loading state
     */
    if (form && submitBtn) {
        form.addEventListener('submit', function() {
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;

            setTimeout(function() {
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
            }, 5000);
        });
    }

    /**
     * Confirmação ao cancelar
     */
    const btnCancel = document.querySelector('.btn-cancel');
    if (btnCancel && form) {
        btnCancel.addEventListener('click', function(e) {
            const inputs = form.querySelectorAll('input[type="text"], input[type="email"], input[type="number"], input[type="password"]');
            let temDados = false;

            inputs.forEach(function(input) {
                if (input.value.trim()) {
                    temDados = true;
                }
            });

            if (temDados) {
                const confirmar = confirm('Você tem dados não salvos. Deseja realmente cancelar?');
                if (!confirmar) {
                    e.preventDefault();
                }
            }
        });
    }

    /**
     * Copiar credenciais - MELHORADO
     */
    const credentialValues = document.querySelectorAll('.credential-value');
    credentialValues.forEach(function(element) {
        element.addEventListener('click', function() {
            const texto = this.textContent;

            navigator.clipboard.writeText(texto).then(function() {
                const original = element.textContent;
                const originalBg = element.style.background;
                const originalColor = element.style.color;

                element.textContent = '✓ Copiado!';
                element.style.background = 'var(--success-color)';
                element.style.color = 'white';
                element.style.borderColor = 'var(--success-color)';

                setTimeout(function() {
                    element.textContent = original;
                    element.style.background = originalBg;
                    element.style.color = originalColor;
                    element.style.borderColor = '';
                }, 2000);
            }).catch(function(err) {
                console.error('Erro ao copiar:', err);

                // Fallback: criar input temporário
                const tempInput = document.createElement('input');
                tempInput.value = texto;
                document.body.appendChild(tempInput);
                tempInput.select();
                document.execCommand('copy');
                document.body.removeChild(tempInput);

                alert('Copiado: ' + texto);
            });
        });
    });

    /**
     * Auto-scroll para primeiro erro
     */
    window.addEventListener('load', function() {
        const primeiroErro = document.querySelector('.alert-error');
        if (primeiroErro) {
            primeiroErro.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }
    });

    console.log('✅ user.js inicializado com sucesso!');
});