/**
 * Cliente Form Scripts
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CLIENTE FORM LOADED ===');
    // Toast helper
    function showToast(message, type = 'warning') {
        const colors = {
            success: 'bg-green-50 text-green-800 border border-green-200',
            error: 'bg-red-50 text-red-800 border border-red-200',
            warning: 'bg-yellow-50 text-yellow-800 border border-yellow-200',
            info: 'bg-blue-50 text-blue-800 border border-blue-200'
        };
        const wrap = document.createElement('div');
        wrap.className = `fixed top-4 right-4 z-50 shadow-md rounded-lg px-4 py-3 ${colors[type] || colors.info}`;
        wrap.textContent = message;
        document.body.appendChild(wrap);
        setTimeout(() => wrap.remove(), 4500);
    }
    
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
        
        // Atualiza visibilidade da seção de agências
        const agenciaSection = document.querySelector('.pessoa-juridica-agencia');
        if (agenciaSection) {
            agenciaSection.classList.toggle('hidden', pessoaTipo !== 'J');
            const agenciaInputs = agenciaSection.querySelectorAll('input[type="radio"]');
            agenciaInputs.forEach(input => {
                input.disabled = pessoaTipo !== 'J';
                if (pessoaTipo === 'F') {
                    document.querySelector('input[name="pk_id_aux_agencia_pf"]').value = '2';
                }
            });
        }
        
        pessoaFisicaFields.forEach(field => {
            field.classList.toggle('hidden', pessoaTipo !== 'F');
            const inputs = field.querySelectorAll('input, select');
            inputs.forEach(input => input.required = pessoaTipo === 'F');
        });

        // Update placeholders and masks for CNPJ/CPF field
        const documentInput = document.querySelector('input[name="cnpj"]');
        if (documentInput) {
            // Detecta mudança de tipo para decidir se limpa ou não
            const prevTipo = documentInput.dataset.pessoaTipo || '';
            const changed = prevTipo && prevTipo !== pessoaTipo;
            if (pessoaTipo === 'F') {
                documentInput.placeholder = '000.000.000-00';
                documentInput.maxLength = 14;
            } else {
                documentInput.placeholder = '00.000.000/0000-00';
                documentInput.maxLength = 18;
            }
            // Só limpa quando houve troca real de tipo após inicialização
            if (changed) {
                documentInput.value = '';
            }
            documentInput.dataset.pessoaTipo = pessoaTipo;
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

        // Auto-preenchimento por CNPJ (Pessoa Jurídica)
        documentInput.addEventListener('blur', async function(e) {
            try {
                const pessoaTipo = document.querySelector('input[name="pessoa"]:checked').value;
                if (pessoaTipo !== 'J') return; // somente PJ
                const digits = (e.target.value || '').replace(/\D/g, '');
                if (digits.length !== 14) {
                    if (digits.length > 0) showToast('CNPJ inválido. Informe 14 dígitos.', 'warning');
                    return;
                }

                const resp = await fetch(`/api/cnpj/${digits}`, { credentials: 'same-origin' });
                const data = await resp.json();
                if (!data || data.ok !== true) {
                    console.warn('CNPJ API error:', data && data.error);
                    showToast(data && data.error ? `CNPJ: ${data.error}` : 'CNPJ não encontrado.', 'warning');
                    return;
                }
                const setIfEmpty = (selector, value) => {
                    const el = document.querySelector(selector);
                    if (!el) return;
                    if (!el.value) el.value = value || '';
                };
                setIfEmpty('input[name="razao_social"]', data.razao_social);
                setIfEmpty('input[name="nome_fantasia"]', data.nome_fantasia);
                setIfEmpty('input[name="inscricao_estadual"]', data.inscricao_estadual);
                setIfEmpty('input[name="inscricao_municipal"]', data.inscricao_municipal);
                showToast('Dados do CNPJ preenchidos com sucesso.', 'success');
            } catch (err) {
                console.error('Erro ao auto-preencher CNPJ:', err);
                showToast('Erro ao consultar CNPJ. Tente novamente.', 'error');
            }
        });
    }
    
    // Validação do formulário
    const form = document.querySelector('form');
    const clienteIdEl = document.getElementById('cliente_id');
    const currentClienteId = clienteIdEl ? parseInt(clienteIdEl.value) : null;

    function showFieldError(input, message) {
        if (!input) return;
        input.classList.add('border-red-500');
        let helper = input.parentElement.querySelector('.field-error');
        if (!helper) {
            helper = document.createElement('p');
            helper.className = 'field-error text-sm text-red-600 mt-1';
            input.parentElement.appendChild(helper);
        }
        helper.textContent = message || '';
    }

    function clearFieldError(input) {
        if (!input) return;
        input.classList.remove('border-red-500');
        const helper = input.parentElement.querySelector('.field-error');
        if (helper) helper.remove();
    }

    // Validador de CPF (algoritmo oficial)
    function isValidCPF(value) {
        if (!value) return false;
        const digits = String(value).replace(/\D/g, '');
        if (digits.length !== 11) return false;
        if (/^(\d)\1{10}$/.test(digits)) return false; // rejeita sequências
        // DV1
        let sum = 0;
        for (let i = 0; i < 9; i++) sum += parseInt(digits[i], 10) * (10 - i);
        let rest = sum % 11;
        const dv1 = rest < 2 ? 0 : 11 - rest;
        if (dv1 !== parseInt(digits[9], 10)) return false;
        // DV2
        sum = 0;
        for (let i = 0; i < 10; i++) sum += parseInt(digits[i], 10) * (11 - i);
        rest = sum % 11;
        const dv2 = rest < 2 ? 0 : 11 - rest;
        return dv2 === parseInt(digits[10], 10);
    }

    async function validateClienteUniqueness(fields) {
        try {
            const resp = await fetch('/api/clientes/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    cnpj: fields.cnpj || null,
                    razao_social: fields.razao_social || null,
                    nome_fantasia: fields.nome_fantasia || null,
                    cliente_id: currentClienteId,
                })
            });
            const data = await resp.json();
            return data;
        } catch (e) {
            console.error('Erro ao validar unicidade:', e);
            return { ok: false, error: 'Erro de comunicação' };
        }
    }
    if (form) {
        form.addEventListener('submit', async function(e) {
            const razaoInputEl = document.querySelector('input[name="razao_social"]');
            const fantasiaInputEl = document.querySelector('input[name="nome_fantasia"]');
            const cnpjInputEl = document.querySelector('input[name="cnpj"]');
            const razaoSocial = (razaoInputEl?.value || '').trim();
            const nomeFantasia = (fantasiaInputEl?.value || '').trim();
            const cnpjDigits = (cnpjInputEl?.value || '').replace(/\D/g, '');
            
            const pessoaTipo = document.querySelector('input[name="pessoa"]:checked').value;

            // Regras básicas obrigatórias
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
                // Pessoa Física: Razão Social não é obrigatória
                if (!nomeFantasia) {
                    alert('Nome Completo é obrigatório!');
                    e.preventDefault();
                    return false;
                }
                // CPF obrigatório válido quando Pessoa Física
                if (!isValidCPF(cnpjDigits)) {
                    e.preventDefault();
                    showFieldError(cnpjInputEl, 'CPF inválido.');
                    showToast('CPF inválido.', 'warning');
                    return false;
                }
            }

            // Validação de unicidade no submit (bloqueia envio se houver duplicatas)
            e.preventDefault();
            try {
                const res = await validateClienteUniqueness({
                    cnpj: cnpjDigits || null,
                    // Para PF ignorar checagem de duplicidade de Razão Social (pode ser 'NÃO REQUERIDO')
                    razao_social: pessoaTipo === 'F' ? null : (razaoSocial || null),
                    nome_fantasia: nomeFantasia || null,
                });

                // Limpa mensagens anteriores
                clearFieldError(cnpjInputEl);
                clearFieldError(razaoInputEl);
                clearFieldError(fantasiaInputEl);

                if (res && res.ok && res.duplicates) {
                    let hasDup = false;
                    if (res.duplicates.cnpj) {
                        showFieldError(cnpjInputEl, 'CNPJ já cadastrado.');
                        hasDup = true;
                    }
                    if (res.duplicates.razao_social) {
                        showFieldError(razaoInputEl, 'Razão Social já cadastrada.');
                        hasDup = true;
                    }
                    if (res.duplicates.nome_fantasia) {
                        showFieldError(fantasiaInputEl, 'Nome Fantasia já cadastrado.');
                        hasDup = true;
                    }
                    if (hasDup) {
                        showToast('Existem duplicidades no cadastro. Corrija antes de enviar.', 'error');
                        return false; // mantém bloqueado
                    }
                }

                // Se não houver duplicatas (ou API indisponível), envia normalmente
                console.log('Enviando formulário:', { razao_social: razaoSocial, nome_fantasia: nomeFantasia });
                form.submit();
            } catch (err) {
                console.warn('Falha ao validar unicidade no submit. Prosseguindo com envio.', err);
                form.submit();
            }
        });
    }

    // AJAX validações por campo (blur)
    const cnpjInput = document.querySelector('input[name="cnpj"]');
    const razaoInput = document.querySelector('input[name="razao_social"]');
    const fantasiaInput = document.querySelector('input[name="nome_fantasia"]');

    if (cnpjInput) {
        cnpjInput.addEventListener('blur', async () => {
            const cnpj = cnpjInput.value;
            if (!cnpj) return;
            const pessoaTipo = document.querySelector('input[name="pessoa"]:checked')?.value;
            const digits = cnpj.replace(/\D/g, '');
            if (pessoaTipo === 'F') {
                // Valida CPF antes de consultar unicidade
                if (!isValidCPF(digits)) {
                    showFieldError(cnpjInput, 'CPF inválido.');
                    showToast('CPF inválido.', 'warning');
                    return;
                } else {
                    clearFieldError(cnpjInput);
                }
            }
            const res = await validateClienteUniqueness({ cnpj });
            if (res && res.ok && res.duplicates) {
                if (res.duplicates.cnpj) {
                    showFieldError(cnpjInput, pessoaTipo === 'F' ? 'CPF já cadastrado.' : 'CNPJ já cadastrado.');
                    showToast(pessoaTipo === 'F' ? 'CPF já cadastrado.' : 'CNPJ já cadastrado.', 'warning');
                } else {
                    clearFieldError(cnpjInput);
                }
            }
        });
    }

    if (razaoInput) {
        razaoInput.addEventListener('blur', async () => {
            const razao_social = razaoInput.value;
            if (!razao_social) return;
            const res = await validateClienteUniqueness({ razao_social });
            if (res && res.ok && res.duplicates) {
                if (res.duplicates.razao_social) {
                    showFieldError(razaoInput, 'Razão Social já cadastrada.');
                    showToast('Razão Social já cadastrada.', 'warning');
                } else {
                    clearFieldError(razaoInput);
                }
            }
        });
    }

    if (fantasiaInput) {
        fantasiaInput.addEventListener('blur', async () => {
            const nome_fantasia = fantasiaInput.value;
            if (!nome_fantasia) return;
            const res = await validateClienteUniqueness({ nome_fantasia });
            if (res && res.ok && res.duplicates) {
                if (res.duplicates.nome_fantasia) {
                    showFieldError(fantasiaInput, 'Nome Fantasia já cadastrado.');
                    showToast('Nome Fantasia já cadastrado.', 'warning');
                } else {
                    clearFieldError(fantasiaInput);
                }
            }
        });
    }
    
    // Auto-focus no primeiro campo
    const firstInput = document.querySelector('input[autofocus]');
    if (firstInput) {
        firstInput.focus();
    }

    // Máscara de CEP
    const cepInput = document.getElementById('cep');
    if (cepInput) {
        cepInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            
            // Aplica máscara: 00000-000
            if (value.length <= 8) {
                value = value.replace(/^(\d{5})(\d)/, '$1-$2');
            }
            
            e.target.value = value;
        });

        // Busca endereço via CEP ao completar
        cepInput.addEventListener('blur', function(e) {
            const cep = e.target.value.replace(/\D/g, '');
            
            if (cep.length === 8) {
                fetch(`https://viacep.com.br/ws/${cep}/json/`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.erro) {
                            // Preenche os campos
                            const logradouroInput = document.getElementById('logradouro');
                            const bairroInput = document.getElementById('bairro');
                            const cidadeInput = document.getElementById('cidade');
                            const estadoSelect = document.getElementById('estado');
                            
                            if (logradouroInput && data.logradouro) {
                                logradouroInput.value = data.logradouro;
                            }
                            
                            if (bairroInput && data.bairro) {
                                bairroInput.value = data.bairro;
                            }
                            
                            if (cidadeInput && data.localidade) {
                                cidadeInput.value = data.localidade;
                            }
                            
                            if (estadoSelect && data.uf) {
                                // Seleciona o estado pela sigla
                                const options = estadoSelect.options;
                                for (let i = 0; i < options.length; i++) {
                                    if (options[i].text.startsWith(data.uf)) {
                                        estadoSelect.selectedIndex = i;
                                        break;
                                    }
                                }
                            }
                            
                            // Foca no campo número
                            const numeroInput = document.getElementById('numero');
                            if (numeroInput) {
                                numeroInput.focus();
                            }
                        } else {
                            console.warn('CEP não encontrado');
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao buscar CEP:', error);
                    });
            }
        });
        
        console.log('✓ CEP mask and auto-fill initialized');
    }

    // Dropdown de Executivo de Vendas (CentralComm) agora é único; nenhuma lógica adicional necessária
});

console.log('Cliente_form.js loaded successfully');