(function () {
    'use strict';

    var API_BASE = '/teste-crm/api';

    var state = {
        clientes: [],
        clienteId: null,
        cliente: null,
        contatos: [],
        contatoId: null,
        filtroPill: 'todos',
        buscaCliente: '',
        buscaContato: ''
    };

    function $(sel, root) {
        return (root || document).querySelector(sel);
    }

    function $$(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function api(path, opts) {
        opts = opts || {};
        return fetch(API_BASE + path, {
            method: opts.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json'
            },
            body: opts.body ? JSON.stringify(opts.body) : undefined
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok) throw new Error(data.error || 'Erro na requisição');
                return data;
            });
        });
    }

    function showToast(msg, isError) {
        var el = $('#crm-mock-toast');
        if (!el) return;
        el.textContent = msg;
        el.classList.toggle('crm-mock-toast-error', !!isError);
        el.hidden = false;
        el.classList.add('crm-mock-toast-visible');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(function () {
            el.classList.remove('crm-mock-toast-visible');
            setTimeout(function () { el.hidden = true; }, 250);
        }, 2800);
    }

    function openModal(id) {
        var dialog = document.getElementById(id);
        if (!dialog) return;
        dialog.classList.remove('crm-mock-modal-visible');
        dialog.showModal();
        requestAnimationFrame(function () {
            dialog.classList.add('crm-mock-modal-visible');
        });
    }

    function closeModal(id) {
        var dialog = document.getElementById(id);
        if (!dialog) return;
        dialog.classList.remove('crm-mock-modal-visible');
        setTimeout(function () {
            if (dialog.open) dialog.close();
        }, 180);
    }

    function setBtnLoading(btn, loading) {
        if (!btn) return;
        btn.classList.toggle('is-loading', loading);
        btn.disabled = loading;
    }

    function badgeClass(type) {
        return 'crm-mock-badge crm-mock-badge-' + (type || 'muted');
    }

    function renderClientes() {
        var container = $('#crm-mock-lista-clientes');
        if (!container) return;

        var termo = state.buscaCliente.toLowerCase();
        var filtrados = state.clientes.filter(function (c) {
            if (state.filtroPill !== 'todos' && c.status !== state.filtroPill) return false;
            if (termo && c.nome.toLowerCase().indexOf(termo) === -1) return false;
            return true;
        });

        var countEl = $('.crm-mock-col-clientes .crm-mock-count');
        if (countEl) countEl.textContent = filtrados.length;

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-mock-contatos-empty">Nenhum cliente encontrado.</div>';
            return;
        }

        container.innerHTML = filtrados.map(function (c) {
            var ativo = c.id === state.clienteId;
            return (
                '<div class="crm-mock-cliente' + (ativo ? ' crm-mock-cliente-ativo' : '') + '" role="listitem" tabindex="0"' +
                ' data-cliente-id="' + escapeHtml(c.id) + '" data-status="' + escapeHtml(c.status) + '"' +
                ' aria-current="' + (ativo ? 'true' : 'false') + '">' +
                '<div class="crm-mock-avatar" aria-hidden="true">' + escapeHtml(c.avatar) + '</div>' +
                '<div class="crm-mock-cliente-info">' +
                '<div class="crm-mock-cliente-nome">' + escapeHtml(c.nome) + '</div>' +
                '<div class="crm-mock-cliente-sub">' + escapeHtml(c.sub) + '</div>' +
                '</div>' +
                '<div class="crm-mock-cliente-right">' +
                '<span class="' + badgeClass(c.badge_type) + '">' + escapeHtml(c.badge) + '</span>' +
                '</div>' +
                '</div>'
            );
        }).join('');

        $$('.crm-mock-cliente', container).forEach(function (card) {
            card.addEventListener('click', function () {
                selectCliente(card.getAttribute('data-cliente-id'));
            });
            card.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectCliente(card.getAttribute('data-cliente-id'));
                }
            });
        });
    }

    function updateDetailPanel(cliente) {
        if (!cliente) return;
        var title = $('.crm-mock-detail-title');
        if (title) title.textContent = cliente.nome;

        var avatars = $$('.crm-mock-detail-header .crm-mock-avatar-lg');
        avatars.forEach(function (a) {
            a.textContent = cliente.avatar;
        });

        var metaResp = $('.crm-mock-detail-meta .crm-mock-meta-item strong');
        if (metaResp) metaResp.textContent = cliente.responsavel || '—';

        var sidebarTitle = $('.crm-mock-sidebar-title');
        if (sidebarTitle) {
            sidebarTitle.textContent = cliente.nome.length > 32 ? cliente.nome.slice(0, 30) + '...' : cliente.nome;
        }
        var sidebarSub = $('.crm-mock-sidebar-sub');
        if (sidebarSub) sidebarSub.textContent = cliente.tipo_label || '—';

        var avSidebar = $('.crm-mock-sidebar-header .crm-mock-avatar');
        if (avSidebar) avSidebar.textContent = cliente.avatar;

        var metricContato = $('.crm-mock-metrics .crm-mock-metric:first-child .crm-mock-metric-val');
        if (metricContato) metricContato.textContent = cliente.qtd_contatos || 0;
    }

    function updateSidebarContato(contato) {
        var nomeEl = $('#crm-mock-sidebar-contato-nome');
        var cargoEl = $('#crm-mock-sidebar-contato-cargo');
        var emailEl = $('#crm-mock-sidebar-contato-email');
        var telEl = $('#crm-mock-sidebar-contato-telefone');
        var avatarEl = $('#crm-mock-sidebar-contato-avatar');
        var badgeEl = $('#crm-mock-sidebar-contato-badge');
        var hintEl = $('#crm-mock-contato-principal-hint');
        var detalhesEl = $('#crm-mock-sidebar-contato-detalhes');

        if (!contato) {
            if (nomeEl) nomeEl.textContent = '—';
            if (cargoEl) cargoEl.textContent = 'Selecione um contato';
            if (emailEl) emailEl.textContent = '—';
            if (telEl) telEl.textContent = '—';
            if (badgeEl) badgeEl.hidden = true;
            if (hintEl) hintEl.textContent = '—';
            if (detalhesEl) detalhesEl.style.display = 'none';
            return;
        }

        if (nomeEl) nomeEl.textContent = contato.nome;
        if (cargoEl) cargoEl.textContent = contato.cargo || '—';
        if (emailEl) emailEl.textContent = contato.email || '—';
        if (telEl) telEl.textContent = contato.telefone || '—';
        if (avatarEl) {
            avatarEl.textContent = contato.avatar || contato.nome.charAt(0);
            avatarEl.className = 'crm-mock-avatar crm-mock-avatar-muted';
        }
        if (badgeEl) {
            badgeEl.hidden = !contato.principal;
            badgeEl.textContent = 'Principal';
        }
        if (hintEl) hintEl.textContent = contato.nome;
        if (detalhesEl) detalhesEl.style.display = '';
    }

    function renderContatos() {
        var container = $('#crm-mock-lista-contatos');
        var countEl = $('#crm-mock-contatos-count');
        if (!container) return;

        var termo = state.buscaContato.toLowerCase().trim();
        var filtrados = state.contatos.filter(function (c) {
            if (!termo) return true;
            return [c.nome, c.cargo, c.email, c.telefone, c.telefone_secundario]
                .some(function (v) { return String(v || '').toLowerCase().indexOf(termo) !== -1; });
        });

        if (countEl) countEl.textContent = filtrados.length;

        if (!state.clienteId) {
            container.innerHTML = '<div class="crm-mock-contatos-empty">Selecione um cliente.</div>';
            updateSidebarContato(null);
            return;
        }

        if (!state.contatos.length) {
            container.innerHTML =
                '<div class="crm-mock-contatos-empty">' +
                'Nenhum contato cadastrado.<br>' +
                '<button type="button" class="crm-mock-btn crm-mock-btn-primary crm-mock-btn-sm crm-mock-contatos-empty-btn" id="crm-mock-empty-add-contato">+ Adicionar contato</button>' +
                '</div>';
            var emptyBtn = $('#crm-mock-empty-add-contato');
            if (emptyBtn) emptyBtn.addEventListener('click', openContatoModal);
            updateSidebarContato(null);
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-mock-contatos-empty">Nenhum contato encontrado.</div>';
            return;
        }

        container.innerHTML = filtrados.map(function (c) {
            var ativo = c.id === state.contatoId;
            return (
                '<div class="crm-mock-contato-card' + (ativo ? ' crm-mock-contato-card-active is-expanded' : '') + '" role="listitem" tabindex="0" data-contato-id="' + escapeHtml(c.id) + '">' +
                '<div class="crm-mock-contato-main">' +
                '<div class="crm-mock-avatar' + (ativo ? '' : ' crm-mock-avatar-muted') + '" aria-hidden="true">' + escapeHtml(c.avatar) + '</div>' +
                '<div class="crm-mock-contato-info">' +
                '<div class="crm-mock-contato-nome">' + escapeHtml(c.nome) + '</div>' +
                '<div class="crm-mock-contato-cargo">' + escapeHtml(c.cargo) + '</div>' +
                '</div>' +
                '<div class="crm-mock-contato-actions">' +
                (c.principal ? '<span class="crm-mock-badge crm-mock-badge-primary">Principal</span>' : '') +
                (c.conversas ? '<span class="crm-mock-badge crm-mock-badge-info">' + c.conversas + '</span>' : '') +
                '<button type="button" class="crm-mock-contato-edit" aria-label="Editar" data-contato-id="' + escapeHtml(c.id) + '"><i class="fa-solid fa-pen" aria-hidden="true"></i></button>' +
                '<button type="button" class="crm-mock-contato-toggle" aria-expanded="' + (ativo ? 'true' : 'false') + '"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>' +
                '</div></div>' +
                '<div class="crm-mock-contato-details">' +
                (c.email ? (
                    '<div class="crm-mock-contato-email-row"><span>' + escapeHtml(c.email) + '</span>' +
                    '<button type="button" class="crm-mock-contato-copy" data-copy="' + escapeHtml(c.email) + '" aria-label="Copiar"><i class="fa-regular fa-copy"></i></button></div>'
                ) : '') +
                '<div class="crm-mock-contato-phone-label">WhatsApp</div>' +
                (c.telefone ? '<button type="button" class="crm-mock-contato-phone-row' + (ativo ? ' crm-mock-contato-phone-row-active' : '') + '"><span>' + escapeHtml(c.telefone) + '</span><span class="crm-mock-contato-phone-status">Ativo</span></button>' : '') +
                (c.telefone_secundario ? '<button type="button" class="crm-mock-contato-phone-row"><span>' + escapeHtml(c.telefone_secundario) + '</span><span class="crm-mock-contato-phone-status">Ativo</span></button>' : '') +
                '<button type="button" class="crm-mock-contato-whats-link"><i class="fa-brands fa-whatsapp"></i> Abrir WhatsApp</button>' +
                '</div></div>'
            );
        }).join('');

        bindContatoEvents(container);
        var contato = state.contatos.find(function (c) { return c.id === state.contatoId; });
        updateSidebarContato(contato);
    }

    function bindContatoEvents(container) {
        $$('.crm-mock-contato-card', container).forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.closest('.crm-mock-contato-toggle, .crm-mock-contato-edit, .crm-mock-contato-copy, .crm-mock-contato-phone-row, .crm-mock-contato-whats-link')) return;
                selectContato(card.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-mock-contato-toggle', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var card = btn.closest('.crm-mock-contato-card');
                var expanded = card.classList.toggle('is-expanded');
                btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            });
        });

        $$('.crm-mock-contato-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openContatoModal(btn.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-mock-contato-copy', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var text = btn.getAttribute('data-copy');
                if (text && navigator.clipboard) navigator.clipboard.writeText(text);
                showToast('E-mail copiado');
            });
        });
    }

    function selectContato(id) {
        state.contatoId = id;
        renderContatos();
    }

    function loadContatos(clienteId) {
        var container = $('#crm-mock-lista-contatos');
        if (container) {
            container.classList.add('is-loading');
            container.innerHTML = '<div class="crm-mock-loading"><i class="fa-solid fa-spinner fa-spin"></i> Carregando…</div>';
        }
        return api('/clientes/' + encodeURIComponent(clienteId) + '/contatos').then(function (data) {
            state.contatos = data.contatos || [];
            state.contatoId = state.contatos.length ? state.contatos[0].id : null;
            if (container) container.classList.remove('is-loading');
            renderContatos();
        }).catch(function (err) {
            if (container) {
                container.classList.remove('is-loading');
                container.innerHTML = '<div class="crm-mock-contatos-empty">Erro ao carregar contatos.</div>';
            }
            showToast(err.message, true);
        });
    }

    function selectCliente(clienteId) {
        state.clienteId = clienteId;
        state.cliente = state.clientes.find(function (c) { return c.id === clienteId; });
        renderClientes();
        updateDetailPanel(state.cliente);
        loadContatos(clienteId);
    }

    function loadClientes() {
        var container = $('#crm-mock-lista-clientes');
        return api('/clientes').then(function (data) {
            state.clientes = data.clientes || [];
            renderClientes();
            if (state.clientes.length) {
                var first = state.clientes.find(function (c) { return c.id === state.clienteId; }) || state.clientes[0];
                selectCliente(first.id);
            }
        }).catch(function (err) {
            if (container) {
                container.innerHTML = '<div class="crm-mock-contatos-empty">Erro ao carregar clientes.</div>';
            }
            showToast(err.message, true);
        });
    }

    function openContatoModal(contatoId) {
        if (!state.clienteId) {
            showToast('Selecione um cliente primeiro', true);
            return;
        }
        var form = $('#crm-mock-form-contato');
        var title = $('#crm-mock-modal-contato-title');
        if (!form) return;

        form.reset();
        $('#crm-mock-contato-id').value = contatoId || '';

        if (contatoId) {
            var c = state.contatos.find(function (x) { return x.id === contatoId; });
            if (!c) return;
            if (title) title.textContent = 'Editar contato';
            $('#crm-mock-contato-nome').value = c.nome;
            $('#crm-mock-contato-email').value = c.email;
            $('#crm-mock-contato-cargo').value = c.cargo || '';
            $('#crm-mock-contato-telefone').value = c.telefone || '';
            $('#crm-mock-contato-telefone2').value = c.telefone_secundario || '';
            $('#crm-mock-contato-principal').checked = c.principal;
        } else {
            if (title) title.textContent = 'Novo contato';
        }

        openModal('crm-mock-modal-contato');
    }

    function openClienteModal() {
        var form = $('#crm-mock-form-cliente');
        if (form) form.reset();
        openModal('crm-mock-modal-cliente');
    }

    function initModals() {
        $$('[data-close-modal]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeModal(btn.getAttribute('data-close-modal'));
            });
        });

        $$('.crm-mock-modal').forEach(function (dialog) {
            dialog.addEventListener('click', function (e) {
                if (e.target === dialog) closeModal(dialog.id);
            });
            var backdrop = dialog.querySelector('.crm-mock-modal-backdrop');
            if (backdrop) {
                backdrop.addEventListener('click', function () { closeModal(dialog.id); });
            }
        });

        var formContato = $('#crm-mock-form-contato');
        if (formContato) {
            formContato.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-contato-submit');
                var contatoId = $('#crm-mock-contato-id').value;
                var body = {
                    nome: $('#crm-mock-contato-nome').value,
                    email: $('#crm-mock-contato-email').value,
                    cargo: $('#crm-mock-contato-cargo').value,
                    telefone: $('#crm-mock-contato-telefone').value,
                    telefone_secundario: $('#crm-mock-contato-telefone2').value,
                    principal: $('#crm-mock-contato-principal').checked
                };
                setBtnLoading(btn, true);
                var req = contatoId
                    ? api('/contatos/' + encodeURIComponent(contatoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/contatos', { method: 'POST', body: body });

                req.then(function (data) {
                    closeModal('crm-mock-modal-contato');
                    showToast(contatoId ? 'Contato atualizado' : 'Contato criado');
                    if (data.cliente_id) state.clienteId = data.cliente_id;
                    return loadClientes();
                }).catch(function (err) {
                    showToast(err.message, true);
                }).finally(function () {
                    setBtnLoading(btn, false);
                });
            });
        }

        var formCliente = $('#crm-mock-form-cliente');
        if (formCliente) {
            formCliente.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-cliente-submit');
                var perfil = $('#crm-mock-cliente-perfil').value;
                var body = {
                    nome: $('#crm-mock-cliente-nome').value,
                    perfil: perfil,
                    tipo_label: perfil === 'agencia' ? 'Agência' : 'Cliente final',
                    categoria: $('#crm-mock-cliente-categoria').value,
                    prioridade: $('#crm-mock-cliente-prioridade').value,
                    responsavel: $('#crm-mock-cliente-responsavel').value
                };
                setBtnLoading(btn, true);
                api('/clientes', { method: 'POST', body: body }).then(function (data) {
                    closeModal('crm-mock-modal-cliente');
                    showToast('Cliente criado');
                    state.clienteId = data.cliente.id;
                    return loadClientes();
                }).catch(function (err) {
                    showToast(err.message, true);
                }).finally(function () {
                    setBtnLoading(btn, false);
                });
            });
        }

        var formAtiv = $('#crm-mock-form-atividade');
        if (formAtiv) {
            formAtiv.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-atividade-submit');
                setBtnLoading(btn, true);
                setTimeout(function () {
                    closeModal('crm-mock-modal-atividade');
                    showToast('Atividade agendada (protótipo)');
                    setBtnLoading(btn, false);
                    formAtiv.reset();
                }, 600);
            });
        }

        var importBtn = $('#crm-mock-import-submit');
        if (importBtn) {
            importBtn.addEventListener('click', function () {
                if (!state.clienteId) {
                    showToast('Selecione um cliente', true);
                    return;
                }
                var texto = ($('#crm-mock-import-texto').value || '').trim();
                if (!texto) {
                    showToast('Cole a lista de contatos', true);
                    return;
                }
                setBtnLoading(importBtn, true);
                var linhas = texto.split('\n').filter(function (l) { return l.trim(); });
                var chain = Promise.resolve();
                var count = 0;
                linhas.forEach(function (linha) {
                    var parts = linha.split(/[;|,]/).map(function (p) { return p.trim(); });
                    if (parts.length < 2) return;
                    chain = chain.then(function () {
                        return api('/clientes/' + encodeURIComponent(state.clienteId) + '/contatos', {
                            method: 'POST',
                            body: {
                                nome: parts[0],
                                email: parts[1],
                                telefone: parts[2] || ''
                            }
                        }).then(function () { count++; });
                    });
                });
                chain.then(function () {
                    closeModal('crm-mock-modal-import');
                    showToast(count + ' contato(s) importado(s)');
                    return loadClientes();
                }).catch(function (err) {
                    showToast(err.message, true);
                }).finally(function () {
                    setBtnLoading(importBtn, false);
                });
            });
        }
    }

    function initTabs(groupName) {
        var tabContainer = document.querySelector('[data-tab-group="' + groupName + '"]');
        if (!tabContainer) return;
        var tabs = tabContainer.querySelectorAll('.crm-mock-tab');

        function activateTab(tab) {
            var target = tab.getAttribute('data-tab');
            tabs.forEach(function (t) {
                t.classList.remove('crm-mock-tab-active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('crm-mock-tab-active');
            tab.setAttribute('aria-selected', 'true');
            document.querySelectorAll('[data-panel-group="' + groupName + '"]').forEach(function (panel) {
                var isTarget = panel.getAttribute('data-panel') === target;
                panel.classList.toggle('crm-mock-tab-panel-active', isTarget);
                if (panel.hasAttribute('hidden')) panel.hidden = !isTarget;
            });
            if (groupName === 'atividades') filterAtividades(target);
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function () { activateTab(tab); });
            tab.addEventListener('keydown', function (e) {
                var next = index;
                if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
                else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
                else return;
                e.preventDefault();
                tabs[next].focus();
                activateTab(tabs[next]);
            });
        });
    }

    function filterAtividades(filtro) {
        $$('.crm-mock-ativ-list .crm-mock-ativ').forEach(function (item) {
            var status = item.getAttribute('data-status') || 'pendente';
            var show = filtro === 'todas' || (filtro === 'pendentes' && status !== 'concluida') || (filtro === 'concluidas' && status === 'concluida');
            item.classList.toggle('hidden-by-tab', !show);
        });
        $$('.crm-mock-date-group').forEach(function (group) {
            var n = group.querySelectorAll('.crm-mock-ativ:not(.hidden-by-tab)').length;
            group.style.display = n > 0 ? '' : 'none';
        });
    }

    function initFilters() {
        $$('.crm-mock-pill').forEach(function (pill) {
            pill.addEventListener('click', function () {
                $$('.crm-mock-pill').forEach(function (p) {
                    p.classList.remove('crm-mock-pill-active');
                    p.setAttribute('aria-pressed', 'false');
                });
                pill.classList.add('crm-mock-pill-active');
                pill.setAttribute('aria-pressed', 'true');
                state.filtroPill = pill.getAttribute('data-filter') || 'todos';
                renderClientes();
            });
        });

        var buscaCliente = $('#crm-mock-busca');
        if (buscaCliente) {
            buscaCliente.addEventListener('input', function () {
                state.buscaCliente = buscaCliente.value;
                renderClientes();
            });
        }

        var buscaContato = $('#crm-mock-busca-contato');
        if (buscaContato) {
            buscaContato.addEventListener('input', function () {
                state.buscaContato = buscaContato.value;
                renderContatos();
            });
        }
    }

    function initButtons() {
        var novoCliente = $('#crm-mock-btn-novo-cliente-header');
        if (novoCliente) novoCliente.addEventListener('click', openClienteModal);

        var novoContato = $('#crm-mock-btn-novo-contato');
        if (novoContato) novoContato.addEventListener('click', function () { openContatoModal(); });

        var importBtn = $('#crm-mock-btn-import-contatos');
        if (importBtn) importBtn.addEventListener('click', function () { openModal('crm-mock-modal-import'); });

        var novaAtiv = $('#crm-mock-btn-nova-atividade');
        if (novaAtiv) novaAtiv.addEventListener('click', function () { openModal('crm-mock-modal-atividade'); });

        var verTodos = $('#crm-mock-ver-todos-contatos');
        if (verTodos) {
            verTodos.addEventListener('click', function () {
                var col = $('.crm-mock-col-contatos');
                if (col) col.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }

        $$('.crm-mock-ativ-check').forEach(function (cb) {
            cb.addEventListener('change', function () {
                var row = cb.closest('.crm-mock-ativ');
                if (row) {
                    row.classList.toggle('crm-mock-ativ-concluida', cb.checked);
                    row.setAttribute('data-status', cb.checked ? 'concluida' : 'pendente');
                }
            });
        });

        $$('.crm-mock-star').forEach(function (star) {
            star.addEventListener('click', function () {
                var active = star.classList.toggle('active');
                star.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
        });
    }

    initModals();
    initTabs('atividades');
    initTabs('sidebar');
    initFilters();
    initButtons();
    loadClientes();
})();
