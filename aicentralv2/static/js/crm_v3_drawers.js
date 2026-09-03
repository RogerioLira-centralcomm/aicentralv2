/**
 * CRM v3 Drawers — plug-in que substitui os modais grandes (cliente, atividade,
 * cotação e contato) por drawers off-canvas usando cxDrawer.
 *
 * Estratégia
 * ----------
 * O `crm_v3.js` continua abrindo os modais tradicionais como fallback; este
 * módulo intercepta os mesmos handlers (via wrappers das funções globais
 * exportadas em `window.crmV3.*`) e chama `cxDrawer.open()` com os templates
 * <template id="cx-drawer-*-tpl">. O submit envia via as mesmas APIs REST do CRM v3.
 */
(function () {
    'use strict';

    var API_BASE = '/crm-v3/api';

    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function cloneTpl(id) {
        var tpl = document.getElementById(id);
        if (!tpl || !tpl.content) return null;
        return tpl.content.cloneNode(true);
    }

    function apiFetch(path, opts) {
        opts = opts || {};
        var init = {
            method: opts.method || 'GET',
            headers: { 'Content-Type': 'application/json' }
        };
        if (opts.body) init.body = JSON.stringify(opts.body);
        return fetch(API_BASE + path, init).then(function (r) {
            return r.json().then(function (data) {
                if (!r.ok || (data && data.success === false)) {
                    var err = new Error((data && data.error) || 'Erro na requisição');
                    err.status = r.status;
                    throw err;
                }
                return data;
            });
        });
    }

    function fillForm(form, data) {
        if (!form || !data) return;
        $$('[data-field]', form).forEach(function (el) {
            var key = el.getAttribute('data-field');
            var val = readDeep(data, key);
            if (val === undefined || val === null) return;
            if (el.type === 'checkbox') el.checked = !!val;
            else el.value = String(val);
        });
    }

    function serializeForm(form) {
        var out = {};
        $$('[data-field]', form).forEach(function (el) {
            var key = el.getAttribute('data-field');
            var val = el.type === 'checkbox' ? el.checked : el.value;
            writeDeep(out, key, val);
        });
        return out;
    }

    function readDeep(obj, path) {
        return path.split('.').reduce(function (acc, k) {
            return (acc == null) ? acc : acc[k];
        }, obj);
    }

    function writeDeep(obj, path, value) {
        var parts = path.split('.');
        var last = parts.pop();
        var cursor = obj;
        parts.forEach(function (k) {
            if (!cursor[k] || typeof cursor[k] !== 'object') cursor[k] = {};
            cursor = cursor[k];
        });
        cursor[last] = value;
    }

    function toast(msg, err) {
        if (typeof window.showToast === 'function') window.showToast(msg, !!err);
        else console.log(msg);
    }

    /* -----------------------------------------------------------
       Drawer: Cliente
       ----------------------------------------------------------- */

    function openDrawerCliente(cliente) {
        var frag = cloneTpl('cx-drawer-cliente-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }

        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');
        fillForm(form, cliente || {});

        // Vínculos
        renderAgenciaRows(wrapper.querySelector('#cx-drawer-cliente-agencias'), cliente);
        wrapper.querySelector('[data-drawer-action="add-agencia"]').addEventListener('click', function () {
            addAgenciaRow(wrapper.querySelector('#cx-drawer-cliente-agencias'), '');
        });

        cxDrawer.open({
            title: cliente ? 'Editar cliente' : 'Novo cliente',
            breadcrumb: 'CRM v3 · Cadastro',
            size: 'lg',
            contentEl: wrapper,
            // Drawer sobreposto ao layout (não empurra o CRM). O backdrop
            // dá o contraste visual sem mover as colunas.
            split: false,
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: cliente ? 'Salvar alterações' : 'Criar cliente',
                    variant: 'primary',
                    id: 'cx-drawer-cliente-submit',
                    onClick: function (ev, id) { submitCliente(form, cliente, id); }
                }
            ]
        });
    }

    function submitCliente(form, cliente, drawerId) {
        var payload = serializeForm(form);
        payload.is_agencia = payload.perfil === 'agencia';
        payload.tipo_label = payload.is_agencia ? 'Agência' : 'Cliente final';
        if (payload.id_tipo_cliente === 'publico') payload.tipo = 'Público';
        else if (payload.id_tipo_cliente === 'privado') payload.tipo = 'Privado';
        payload.categoria = payload.tipo;
        payload.bv_percentual = parseFloat(payload.bv_percentual) || 0;
        payload.margem_cc = parseFloat(payload.margem_cc) || 0;
        payload.agencias_vinculadas = coletarAgenciasVinculadasFrom(form.closest('div').querySelector('#cx-drawer-cliente-agencias'));

        var isEdit = !!(cliente && cliente.id);
        var req = isEdit
            ? apiFetch('/clientes/' + encodeURIComponent(cliente.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes', { method: 'POST', body: payload });
        req.then(function (data) {
            toast(isEdit ? 'Cliente atualizado' : 'Cliente criado');
            cxDrawer.close(drawerId);
            var novoId = (data.cliente && data.cliente.id) || (cliente && cliente.id);
            if (window.crmV3 && typeof window.crmV3.reloadClientes === 'function') {
                window.crmV3.reloadClientes(novoId);
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    function renderAgenciaRows(container, cliente) {
        if (!container) return;
        container.innerHTML = '';
        var vinculos = [];
        if (cliente) {
            if (Array.isArray(cliente.agencias_vinculadas) && cliente.agencias_vinculadas.length) {
                vinculos = cliente.agencias_vinculadas;
            } else if (cliente.agencia_id) {
                vinculos = [{ agencia_id: cliente.agencia_id, is_principal: true }];
            }
        }
        if (!vinculos.length) vinculos.push({ agencia_id: '', is_principal: true });
        vinculos.forEach(function (v) { addAgenciaRow(container, v.agencia_id, v.is_principal); });
    }

    function addAgenciaRow(container, selectedId, isPrincipal) {
        if (!container) return;
        var agencias = getAgencias();
        var opts = ['<option value="">— Selecionar agência —</option>'].concat(
            agencias.map(function (a) {
                var sel = a.id === selectedId ? ' selected' : '';
                return '<option value="' + a.id + '"' + sel + '>' + a.nome + '</option>';
            })
        ).join('');
        var row = document.createElement('div');
        row.className = 'crm-v3-agencia-row';
        row.innerHTML = (
            '<select class="select select-bordered select-sm crm-v3-agencia-select">' + opts + '</select>' +
            '<label class="crm-v3-agencia-principal">' +
            '<input type="radio" name="cx-drawer-cliente-principal" class="radio radio-xs" ' + (isPrincipal ? 'checked' : '') + ' />' +
            '<span>Principal</span></label>' +
            '<button type="button" class="btn btn-ghost btn-xs btn-square crm-v3-agencia-remove"><i class="fa-solid fa-xmark"></i></button>'
        );
        container.appendChild(row);
        row.querySelector('.crm-v3-agencia-remove').addEventListener('click', function () {
            row.remove();
        });
    }

    function coletarAgenciasVinculadasFrom(container) {
        if (!container) return [];
        var out = [];
        $$('.crm-v3-agencia-row', container).forEach(function (row) {
            var sel = row.querySelector('.crm-v3-agencia-select');
            var principal = row.querySelector('input[name="cx-drawer-cliente-principal"]');
            if (sel && sel.value) {
                out.push({ agencia_id: sel.value, is_principal: !!(principal && principal.checked) });
            }
        });
        return out;
    }

    function getAgencias() {
        var lista = (window.crmV3 && window.crmV3.state && window.crmV3.state.clientes) || [];
        return lista.filter(function (c) { return c.is_agencia; })
            .map(function (c) { return { id: c.id, nome: c.nome }; });
    }

    /* -----------------------------------------------------------
       Drawer: Atividade + IA
       ----------------------------------------------------------- */

    function openDrawerAtividade(atividade, clienteId) {
        var frag = cloneTpl('cx-drawer-atividade-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');
        fillForm(form, atividade || {});

        // IA actions
        $$('[data-ia-action]', wrapper).forEach(function (btn) {
            btn.addEventListener('click', function () {
                runIA(btn, form, wrapper.querySelector('[data-ia-output]'), clienteId);
            });
        });

        cxDrawer.open({
            title: atividade ? 'Editar atividade' : 'Nova atividade',
            breadcrumb: 'CRM v3 · Atividade',
            size: 'md',
            contentEl: wrapper,
            // Sobreposto — não empurra as colunas do CRM.
            split: false,
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: atividade ? 'Salvar' : 'Criar atividade',
                    variant: 'primary',
                    onClick: function (ev, id) { submitAtividade(form, atividade, clienteId, id); }
                }
            ]
        });
    }

    function submitAtividade(form, atividade, clienteId, drawerId) {
        var payload = serializeForm(form);
        if (!payload.titulo) { toast('Título é obrigatório', true); return; }
        if (!payload.data) { toast('Data é obrigatória', true); return; }
        var isEdit = !!(atividade && atividade.id);
        var req = isEdit
            ? apiFetch('/atividades/' + encodeURIComponent(atividade.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', { method: 'POST', body: payload });
        req.then(function () {
            toast(isEdit ? 'Atividade atualizada' : 'Atividade criada');
            cxDrawer.close(drawerId);
            if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                window.crmV3.reloadAtividades();
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    function runIA(btn, form, output, clienteId) {
        var action = btn.getAttribute('data-ia-action');
        var payload = serializeForm(form);
        payload.cliente_id = clienteId;
        btn.disabled = true;
        output.classList.add('is-visible');
        output.textContent = 'Consultando assistente…';

        apiFetch('/ia/' + action, { method: 'POST', body: payload }).then(function (res) {
            var data = res.data || res;
            if (action === 'melhorar-texto') {
                if (data && data.texto) {
                    var desc = form.querySelector('[data-field="descricao"]');
                    if (desc) desc.value = data.texto;
                    output.textContent = 'Descrição atualizada com sugestão da IA.';
                } else {
                    output.textContent = 'Sem sugestões no momento.';
                }
            } else if (action === 'sugerir-atividade') {
                if (data) {
                    if (data.titulo) form.querySelector('[data-field="titulo"]').value = data.titulo;
                    if (data.descricao) form.querySelector('[data-field="descricao"]').value = data.descricao;
                    if (data.tipo) form.querySelector('[data-field="tipo"]').value = data.tipo;
                    if (data.prioridade) form.querySelector('[data-field="prioridade"]').value = data.prioridade;
                    if (data.data_sugerida) form.querySelector('[data-field="data"]').value = data.data_sugerida;
                    output.textContent = 'Sugestão preenchida no formulário.';
                }
            } else if (action === 'touchpoints') {
                var list = (data && data.touchpoints) || [];
                if (!list.length) { output.textContent = 'Sem sequência sugerida.'; }
                else {
                    output.textContent = 'Sequência sugerida:\n' + list.map(function (t) {
                        return '• ' + (t.data_sugerida || '') + ' · ' + (t.tipo || '') + ' — ' + (t.titulo || '');
                    }).join('\n') + '\n\nUse "Criar sequência" para inserir todas.';
                    // Adiciona botão dinâmico
                    if (!output.querySelector('.cx-drawer-ia-apply')) {
                        var apply = document.createElement('button');
                        apply.type = 'button';
                        apply.className = 'cx-drawer-ia-action cx-drawer-ia-apply';
                        apply.style.marginTop = '8px';
                        apply.textContent = 'Criar ' + list.length + ' atividades';
                        apply.addEventListener('click', function () {
                            Promise.all(list.map(function (t) {
                                return apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', {
                                    method: 'POST',
                                    body: {
                                        titulo: t.titulo,
                                        descricao: t.descricao || '',
                                        tipo: t.tipo || 'ligacao',
                                        prioridade: t.prioridade || 'Média',
                                        data: t.data_sugerida,
                                        hora: t.hora || '',
                                        responsavel: (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente && window.crmV3.state.cliente.responsavel) || 'Luisa Santana'
                                    }
                                });
                            })).then(function () {
                                toast('Sequência criada');
                                if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                                    window.crmV3.reloadAtividades();
                                }
                                apply.disabled = true;
                            }).catch(function (err) { toast(err.message, true); });
                        });
                        output.appendChild(document.createElement('br'));
                        output.appendChild(apply);
                    }
                }
            } else if (action === 'gerar-comunicacao') {
                if (data && data.mensagem) {
                    output.textContent = data.mensagem;
                    // Drawer aninhado com o e-mail pronto
                    setTimeout(function () { openDrawerComunicacao(data, clienteId); }, 200);
                } else {
                    output.textContent = 'Sem conteúdo gerado.';
                }
            }
        }).catch(function (err) {
            output.textContent = 'Erro: ' + err.message;
        }).finally(function () {
            btn.disabled = false;
        });
    }

    function openDrawerComunicacao(data, clienteId) {
        var wrap = document.createElement('div');
        wrap.innerHTML = (
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Assunto</div>' +
            '<div class="cx-drawer-field"><input type="text" id="cx-com-assunto" value="' + escapeHtml(data.assunto || '') + '" /></div>' +
            '</div>' +
            '<div class="cx-drawer-section">' +
            '<div class="cx-drawer-section-title">Mensagem</div>' +
            '<div class="cx-drawer-field"><textarea rows="12" id="cx-com-body">' + escapeHtml(data.mensagem || '') + '</textarea></div>' +
            '</div>'
        );

        cxDrawer.open({
            title: 'Preparar comunicação',
            breadcrumb: 'CRM v3 · IA · E-mail',
            size: 'md',
            contentEl: wrap,
            nested: true,
            actions: [
                { label: 'Fechar', variant: 'ghost', close: true },
                {
                    label: 'Registrar como atividade',
                    variant: 'primary',
                    onClick: function (ev, id) {
                        var assunto = wrap.querySelector('#cx-com-assunto').value;
                        var msg = wrap.querySelector('#cx-com-body').value;
                        apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/atividades', {
                            method: 'POST',
                            body: {
                                titulo: assunto || 'E-mail para contato principal',
                                descricao: msg,
                                tipo: 'email',
                                prioridade: 'Média',
                                data: new Date().toISOString().slice(0, 10),
                                responsavel: (window.crmV3 && window.crmV3.state && window.crmV3.state.cliente && window.crmV3.state.cliente.responsavel) || 'Luisa Santana'
                            }
                        }).then(function () {
                            toast('E-mail registrado como atividade');
                            cxDrawer.close(id);
                            if (window.crmV3 && typeof window.crmV3.reloadAtividades === 'function') {
                                window.crmV3.reloadAtividades();
                            }
                        }).catch(function (err) { toast(err.message, true); });
                    }
                }
            ]
        });
    }

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /* -----------------------------------------------------------
       Drawer: Contato
       ----------------------------------------------------------- */

    function openDrawerContato(contato, clienteId) {
        var frag = cloneTpl('cx-drawer-contato-tpl');
        if (!frag) return;
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');
        fillForm(form, contato || {});
        cxDrawer.open({
            title: contato ? 'Editar contato' : 'Novo contato',
            breadcrumb: 'CRM v3 · Contato',
            size: 'md',
            contentEl: wrapper,
            actions: [
                { label: 'Cancelar', variant: 'ghost', close: true },
                {
                    label: contato ? 'Salvar' : 'Criar contato',
                    variant: 'primary',
                    onClick: function (ev, id) {
                        var payload = serializeForm(form);
                        var isEdit = !!(contato && contato.id);
                        var req = isEdit
                            ? apiFetch('/contatos/' + encodeURIComponent(contato.id), { method: 'PATCH', body: payload })
                            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/contatos', { method: 'POST', body: payload });
                        req.then(function () {
                            toast(isEdit ? 'Contato atualizado' : 'Contato criado');
                            cxDrawer.close(id);
                            if (window.crmV3 && typeof window.crmV3.reloadClientes === 'function') {
                                window.crmV3.reloadClientes();
                            }
                        }).catch(function (err) { toast(err.message, true); });
                    }
                }
            ]
        });
    }

    /* -----------------------------------------------------------
       Drawer: Cotação — Caminho A
       -----------------------------------------------------------
       Só os campos essenciais do cabeçalho (mesma Seção 1 do form
       /cotacoes/nova). Após criar, redireciona para /cotacoes/<id>/detalhes
       para o usuário completar audiência/produtos/preço/comissões.

       Ações:
       - "Salvar rascunho": cria e permanece no CRM v3.
       - "Salvar e montar cotação": cria e navega para a tela dedicada.
       ----------------------------------------------------------- */

    function populateResponsaveis(select, cotacao) {
        if (!select) return;
        var ctx = window.CRM_V3_CONTEXT || {};
        var lista = Array.isArray(ctx.executivos) ? ctx.executivos : [];
        // Mantém o placeholder que já veio do template.
        var selectedId = cotacao && (cotacao.responsavel_comercial || cotacao.responsavel_id);
        // Se não veio da cotação (nova), usa o usuário logado.
        if (!selectedId && ctx.userId) selectedId = ctx.userId;
        lista.forEach(function (ex) {
            var opt = document.createElement('option');
            opt.value = String(ex.id_contato_cliente || ex.id || '');
            opt.textContent = ex.nome_completo || ex.nome || opt.value;
            if (selectedId && String(selectedId) === opt.value) opt.selected = true;
            select.appendChild(opt);
        });
    }

    function submitCotacaoCaminhoA(form, cotacao, clienteId, drawerId, abrirMontagem) {
        var payload = serializeForm(form);
        // Sanidade mínima do lado do cliente. O server valida definitivamente.
        var nome = (payload.nome_campanha || '').trim();
        if (!nome) { toast('Nome da campanha é obrigatório', true); return; }
        if (!payload.periodo_inicio) { toast('Data de início é obrigatória', true); return; }

        var isEdit = !!(cotacao && cotacao.id);
        var req = isEdit
            ? apiFetch('/cotacoes/' + encodeURIComponent(cotacao.id), { method: 'PATCH', body: payload })
            : apiFetch('/clientes/' + encodeURIComponent(clienteId) + '/cotacoes', { method: 'POST', body: payload });

        req.then(function (resp) {
            toast(isEdit ? 'Cotação atualizada' : 'Cotação criada');
            cxDrawer.close(drawerId);
            if (window.crmV3 && typeof window.crmV3.reloadCotacoes === 'function') {
                window.crmV3.reloadCotacoes();
            }
            if (abrirMontagem) {
                // Preferência: URL vinda do backend (mais seguro se a rota mudar).
                // Fallback: /cotacoes/<id>/detalhes (padrão do módulo legado).
                var url = (resp && resp.redirect_url)
                    || (resp && resp.cotacao && resp.cotacao.detalhes_url)
                    || null;
                if (!url) {
                    var novoId = (resp && resp.cotacao && resp.cotacao.id) || (cotacao && cotacao.id);
                    if (novoId) url = '/cotacoes/' + encodeURIComponent(novoId) + '/detalhes';
                }
                if (url) {
                    // Nova aba: o usuário mantém contexto no CRM v3 e volta
                    // com um "Ctrl+W" após montar. Comportamento amigável a
                    // multi-tarefa comercial.
                    window.open(url, '_blank', 'noopener');
                }
            }
        }).catch(function (err) { toast(err.message, true); });
    }

    function openDrawerCotacao(cotacao, clienteId) {
        var frag = cloneTpl('cx-drawer-cotacao-tpl');
        if (!frag) { toast('Template do drawer não encontrado', true); return; }
        var wrapper = document.createElement('div');
        wrapper.appendChild(frag);
        var form = wrapper.querySelector('form');

        // Populações antes do fill (o `data-field` do responsável precisa
        // ter as <option>s renderizadas para conseguir setar o valor).
        populateResponsaveis(wrapper.querySelector('#cx-cot-responsavel'), cotacao);

        fillForm(form, cotacao || {});

        var isEdit = !!(cotacao && cotacao.id);
        var actions = [
            { label: 'Cancelar', variant: 'ghost', close: true },
            {
                label: isEdit ? 'Salvar alterações' : 'Salvar rascunho',
                variant: 'ghost',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, cotacao, clienteId, id, false);
                }
            },
            {
                label: isEdit ? 'Salvar e abrir montagem' : 'Salvar e montar cotação',
                variant: 'primary',
                onClick: function (ev, id) {
                    submitCotacaoCaminhoA(form, cotacao, clienteId, id, true);
                }
            }
        ];

        cxDrawer.open({
            title: isEdit ? 'Editar cotação' : 'Nova cotação',
            breadcrumb: 'CRM v3 · Cotação · Cabeçalho',
            size: 'md',
            contentEl: wrapper,
            // Sobreposto ao layout — não empurra as colunas do CRM.
            split: false,
            actions: actions
        });
    }

    /* -----------------------------------------------------------
       Expose e integração
       ----------------------------------------------------------- */

    window.crmV3Drawer = {
        openCliente: openDrawerCliente,
        openAtividade: openDrawerAtividade,
        openContato: openDrawerContato,
        openCotacao: openDrawerCotacao,
    };

    // Redireciona os botões existentes para usar drawer no lugar dos modais grandes.
    document.addEventListener('DOMContentLoaded', function () {
        // Novo cliente (header e coluna)
        ['crm-v3-btn-novo-cliente-header', 'crm-v3-btn-novo-cliente-lista'].forEach(function (id) {
            var btn = document.getElementById(id);
            if (!btn) return;
            btn.addEventListener('click', function (ev) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                openDrawerCliente(null);
            }, true);
        });

        // Editar cliente (menu 3 pontinhos)
        document.addEventListener('click', function (ev) {
            var el = ev.target;
            if (!el) return;

            if (el.classList && el.classList.contains('crm-v3-header-action-edit')) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var cliente = window.crmV3 && window.crmV3.state && window.crmV3.state.cliente;
                openDrawerCliente(cliente);
                return;
            }

            // Nova atividade
            if (el.id === 'crm-v3-btn-nova-atividade' || (el.closest && el.closest('#crm-v3-btn-nova-atividade'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var clienteId = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!clienteId) { toast('Selecione um cliente', true); return; }
                openDrawerAtividade(null, clienteId);
                return;
            }

            // Nova cotação
            if (el.id === 'crm-v3-btn-nova-cotacao' || (el.closest && el.closest('#crm-v3-btn-nova-cotacao'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var cid = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!cid) { toast('Selecione um cliente', true); return; }
                openDrawerCotacao(null, cid);
                return;
            }

            // Novo contato
            if (el.id === 'crm-v3-btn-novo-contato' || (el.closest && el.closest('#crm-v3-btn-novo-contato'))) {
                ev.stopImmediatePropagation();
                ev.preventDefault();
                var ccid = window.crmV3 && window.crmV3.state && window.crmV3.state.clienteId;
                if (!ccid) { toast('Selecione um cliente', true); return; }
                openDrawerContato(null, ccid);
                return;
            }
        }, true);
    });
})();
