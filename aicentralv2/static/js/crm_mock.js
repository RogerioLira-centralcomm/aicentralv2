(function () {
    'use strict';

    var API_BASE = '/teste-crm/api';

    var state = {
        clientes: [],
        clienteId: null,
        cliente: null,
        contatos: [],
        contatoId: null,
        atividades: [],
        objetivos: [],
        cotacoes: [],
        filtroPill: 'todos',
        buscaCliente: '',
        buscaContato: '',
        buscaAtividade: '',
        filtroAtivTab: 'todas',
        importRows: [],
        pendingObjetivoId: null,
        overlayTimer: null
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
                if (!res.ok || data.success === false) {
                    throw new Error(data.error || 'Erro na requisição');
                }
                return data;
            });
        });
    }

    function debounce(fn, ms) {
        var t;
        return function () {
            var args = arguments;
            var ctx = this;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(ctx, args); }, ms);
        };
    }

    function badgeDaisy(type) {
        var map = {
            success: 'badge-success', hoje: 'badge-success', negociacao: 'badge-success',
            warning: 'badge-warning', atrasado: 'badge-warning', amanha: 'badge-warning', media: 'badge-warning',
            info: 'badge-info', enviada: 'badge-info', seguindo: 'badge-info',
            danger: 'badge-error', error: 'badge-error', perdida: 'badge-error', alta: 'badge-error',
            muted: 'badge-ghost', sem-atividade: 'badge-ghost', baixa: 'badge-ghost'
        };
        return 'badge badge-sm ' + (map[(type || '').toLowerCase()] || 'badge-neutral');
    }

    function avatarTone(nome) {
        var s = (nome || '').trim();
        if (!s) return 'muted';
        var sum = 0;
        for (var i = 0; i < s.length; i++) sum += s.charCodeAt(i);
        return sum % 2 === 0 ? 'primary' : 'muted';
    }

    function avatarIniciais(nome) {
        var parts = (nome || '?').trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return (nome || '?').slice(0, 2).toUpperCase();
    }

    function avatarHtml(nome, sizeClass) {
        sizeClass = sizeClass || 'w-7 h-7';
        var tone = avatarTone(nome);
        var ini = avatarIniciais(nome);
        var bg = tone === 'primary' ? 'bg-primary text-primary-content' : 'bg-neutral text-neutral-content';
        return '<div class="avatar placeholder"><div class="rounded-full ' + sizeClass + ' ' + bg + '"><span class="text-xs font-semibold">' + escapeHtml(ini) + '</span></div></div>';
    }

    function normalizarTelefone(telefone, ddi) {
        ddi = ddi || '55';
        if (!telefone) return '';
        var digits = String(telefone).replace(/\D/g, '');
        if (!digits) return '';
        if (digits.indexOf(ddi) === 0 && digits.length > 11) return digits;
        if (digits.length >= 10 && digits.indexOf(ddi) !== 0) return ddi + digits;
        return digits;
    }

    function showToast(msg, isError) {
        var wrap = $('#crm-mock-toast');
        var text = $('#crm-mock-toast-text');
        var alert = wrap && wrap.querySelector('.alert');
        if (!wrap || !text) return;
        text.textContent = msg;
        if (alert) {
            alert.classList.toggle('alert-error', !!isError);
            alert.classList.toggle('alert-success', !isError);
        }
        wrap.hidden = false;
        wrap.classList.add('crm-mock-toast-visible');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(function () {
            wrap.classList.remove('crm-mock-toast-visible');
            setTimeout(function () { wrap.hidden = true; }, 250);
        }, 2800);
    }

    function showOverlay(msg) {
        var el = $('#crm-mock-global-overlay');
        var msgEl = $('#crm-mock-overlay-msg');
        if (!el) return;
        if (msgEl) msgEl.textContent = msg || 'Carregando…';
        el.hidden = false;
        clearTimeout(state.overlayTimer);
        state.overlayTimer = setTimeout(function () {
            if (msgEl) msgEl.textContent = 'A operação está demorando…';
        }, 8000);
    }

    function hideOverlay() {
        var el = $('#crm-mock-global-overlay');
        clearTimeout(state.overlayTimer);
        if (el) el.hidden = true;
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
        btn.classList.toggle('loading', loading);
        btn.disabled = loading;
        var spin = btn.querySelector('.crm-mock-btn-loading');
        if (spin) spin.hidden = !loading;
    }

    function showClientesSkeleton() {
        var container = $('#crm-mock-lista-clientes');
        if (!container) return;
        container.innerHTML =
            '<div class="crm-mock-skeleton-list p-2">' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '</div>';
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

        updatePillCounts();

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-mock-contatos-empty p-3 text-sm text-base-content/60">Nenhum cliente encontrado.</div>';
            return;
        }

        container.innerHTML = filtrados.map(function (c) {
            var ativo = c.id === state.clienteId;
            return (
                '<div class="crm-mock-cliente flex items-start gap-2 px-2 py-2 border-l-4 border-transparent cursor-pointer transition-colors hover:bg-base-200' +
                (ativo ? ' crm-mock-cliente-ativo border-primary bg-base-200' : '') + '"' +
                ' role="listitem" tabindex="0" data-cliente-id="' + escapeHtml(c.id) + '" data-status="' + escapeHtml(c.status) + '"' +
                ' aria-current="' + (ativo ? 'page' : 'false') + '">' +
                avatarHtml(c.nome, 'w-7 h-7') +
                '<div class="crm-mock-cliente-info min-w-0 flex-1">' +
                '<div class="crm-mock-cliente-nome truncate text-sm font-medium text-base-content" title="' + escapeHtml(c.nome) + '">' + escapeHtml(c.nome) + '</div>' +
                '<div class="crm-mock-cliente-sub text-xs text-base-content/60 truncate" title="' + escapeHtml(c.sub) + '">' + escapeHtml(c.sub) + '</div>' +
                '</div>' +
                '<div class="crm-mock-cliente-right shrink-0">' +
                '<span class="' + badgeDaisy(c.badge_type) + '">' + escapeHtml(c.badge) + '</span>' +
                '</div></div>'
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

    function updatePillCounts() {
        var counts = { todos: state.clientes.length, atrasado: 0, 'sem-atividade': 0, seguindo: 0 };
        state.clientes.forEach(function (c) {
            if (counts[c.status] !== undefined) counts[c.status]++;
        });
        $$('.crm-mock-pill').forEach(function (pill) {
            var f = pill.getAttribute('data-filter');
            var span = pill.querySelector('.crm-mock-pill-count');
            if (span && counts[f] !== undefined) span.textContent = counts[f];
        });
    }

    function updateDetailPanel(cliente) {
        if (!cliente) return;
        var title = $('.crm-mock-detail-title');
        if (title) {
            title.textContent = cliente.nome;
            title.title = cliente.nome;
        }

        var av = $('#crm-mock-detail-avatar');
        if (av) av.textContent = cliente.avatar || avatarIniciais(cliente.nome);

        var metaResp = $('#crm-mock-meta-responsavel');
        if (metaResp) metaResp.textContent = cliente.responsavel || '—';

        var metaCat = $('#crm-mock-meta-categoria');
        if (metaCat) metaCat.textContent = cliente.categoria || '—';

        var metaPri = $('#crm-mock-meta-prioridade');
        if (metaPri) {
            metaPri.textContent = 'Prioridade: ' + (cliente.prioridade || '—');
            metaPri.className = 'badge badge-sm ' + (cliente.prioridade === 'Alta' ? 'badge-error' : cliente.prioridade === 'Média' ? 'badge-warning' : 'badge-ghost');
        }

        var sidebarTitle = $('#crm-mock-sidebar-title');
        if (sidebarTitle) {
            sidebarTitle.textContent = cliente.nome.length > 32 ? cliente.nome.slice(0, 30) + '...' : cliente.nome;
            sidebarTitle.title = cliente.nome;
        }
        var sidebarSub = $('#crm-mock-sidebar-sub');
        if (sidebarSub) sidebarSub.textContent = cliente.tipo_label || '—';

        var avSidebar = $('#crm-mock-sidebar-avatar');
        if (avSidebar) avSidebar.textContent = cliente.avatar || avatarIniciais(cliente.nome);

        var m = cliente.metrics || {};
        var el;
        el = $('#crm-metric-contatos'); if (el) el.textContent = m.contatos != null ? m.contatos : cliente.qtd_contatos || 0;
        el = $('#crm-metric-oportunidades'); if (el) el.textContent = m.oportunidades != null ? m.oportunidades : 0;
        el = $('#crm-metric-faturamento'); if (el) el.textContent = m.faturamento || '—';
        el = $('#crm-metric-pis'); if (el) el.textContent = m.valor_pis || '—';
        el = $('#crm-metric-tarefas'); if (el) el.textContent = m.tarefas_abertas != null ? m.tarefas_abertas : 0;
        el = $('#crm-metric-ultimo'); if (el) el.textContent = m.ultimo_contato || '—';
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
        var mailto = $('#crm-mock-mailto-link');
        var whats = $('#crm-mock-whatsapp-link');
        var copyBtn = $('#crm-mock-copy-email');

        if (!contato) {
            if (nomeEl) nomeEl.textContent = '—';
            if (cargoEl) cargoEl.textContent = 'Selecione um contato';
            if (emailEl) { emailEl.textContent = '—'; emailEl.title = ''; }
            if (telEl) { telEl.textContent = '—'; telEl.title = ''; }
            if (badgeEl) badgeEl.hidden = true;
            if (hintEl) hintEl.textContent = '—';
            if (detalhesEl) detalhesEl.style.display = 'none';
            if (mailto) mailto.href = '#';
            if (whats) whats.href = '#';
            return;
        }

        if (nomeEl) nomeEl.textContent = contato.nome;
        if (cargoEl) cargoEl.textContent = contato.cargo || '—';
        if (emailEl) {
            emailEl.textContent = contato.email || '—';
            emailEl.title = contato.email || '';
        }
        if (telEl) {
            telEl.textContent = contato.telefone || '—';
            telEl.title = contato.telefone || '';
        }
        if (avatarEl) avatarEl.textContent = contato.avatar || avatarIniciais(contato.nome);
        if (badgeEl) {
            badgeEl.hidden = !contato.principal;
            badgeEl.textContent = 'Principal';
        }
        if (hintEl) hintEl.textContent = contato.nome;
        if (detalhesEl) detalhesEl.style.display = '';

        if (mailto && contato.email) mailto.href = 'mailto:' + encodeURIComponent(contato.email);
        if (whats && contato.telefone) {
            var digits = normalizarTelefone(contato.telefone);
            whats.href = digits ? 'https://wa.me/' + digits : '#';
        }
        if (copyBtn) {
            copyBtn.onclick = function () {
                if (contato.email && navigator.clipboard) {
                    navigator.clipboard.writeText(contato.email);
                    showToast('E-mail copiado');
                }
            };
        }
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
            container.innerHTML = '<div class="crm-mock-contatos-empty p-3 text-sm">Selecione um cliente.</div>';
            updateSidebarContato(null);
            return;
        }

        if (!state.contatos.length) {
            container.innerHTML =
                '<div class="crm-mock-contatos-empty p-3 text-sm text-center">' +
                'Nenhum contato cadastrado.<br>' +
                '<button type="button" class="btn btn-sm btn-primary mt-2" id="crm-mock-empty-add-contato">+ Adicionar contato</button>' +
                '</div>';
            var emptyBtn = $('#crm-mock-empty-add-contato');
            if (emptyBtn) emptyBtn.addEventListener('click', openContatoModal);
            updateSidebarContato(null);
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-mock-contatos-empty p-3 text-sm">Nenhum contato encontrado.</div>';
            return;
        }

        container.innerHTML = filtrados.map(function (c) {
            var ativo = c.id === state.contatoId;
            return (
                '<div class="crm-mock-contato-card' + (ativo ? ' crm-mock-contato-card-active is-expanded' : '') + '" role="listitem" tabindex="0" data-contato-id="' + escapeHtml(c.id) + '">' +
                '<div class="crm-mock-contato-main">' +
                avatarHtml(c.nome, ativo ? 'w-8 h-8' : 'w-8 h-8') +
                '<div class="crm-mock-contato-info min-w-0">' +
                '<div class="crm-mock-contato-nome truncate text-sm font-medium">' + escapeHtml(c.nome) + '</div>' +
                '<div class="crm-mock-contato-cargo text-xs text-base-content/60 truncate">' + escapeHtml(c.cargo) + '</div>' +
                '</div>' +
                '<div class="crm-mock-contato-actions">' +
                (c.principal ? '<span class="badge badge-sm badge-primary">Principal</span>' : '') +
                (c.conversas ? '<span class="badge badge-sm badge-info">' + c.conversas + '</span>' : '') +
                '<button type="button" class="crm-mock-contato-edit btn btn-ghost btn-xs btn-square" aria-label="Editar" data-contato-id="' + escapeHtml(c.id) + '"><i class="fa-solid fa-pen" aria-hidden="true"></i></button>' +
                '<button type="button" class="crm-mock-contato-toggle btn btn-ghost btn-xs btn-square" aria-expanded="' + (ativo ? 'true' : 'false') + '"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>' +
                '</div></div>' +
                '<div class="crm-mock-contato-details">' +
                (c.email ? (
                    '<div class="crm-mock-contato-email-row flex items-center gap-1"><span class="truncate">' + escapeHtml(c.email) + '</span>' +
                    '<button type="button" class="crm-mock-contato-copy btn btn-ghost btn-xs btn-square" data-copy="' + escapeHtml(c.email) + '" aria-label="Copiar"><i class="fa-regular fa-copy"></i></button></div>'
                ) : '') +
                '<div class="crm-mock-contato-phone-label text-xs text-base-content/50 mt-1">WhatsApp</div>' +
                (c.telefone ? '<button type="button" class="crm-mock-contato-phone-row crm-mock-contato-whats-row w-full text-left"><span>' + escapeHtml(c.telefone) + '</span></button>' : '') +
                (c.telefone_secundario ? '<button type="button" class="crm-mock-contato-phone-row crm-mock-contato-whats-row w-full text-left"><span>' + escapeHtml(c.telefone_secundario) + '</span></button>' : '') +
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
                if (e.target.closest('.crm-mock-contato-toggle, .crm-mock-contato-edit, .crm-mock-contato-copy, .crm-mock-contato-phone-row, .crm-mock-contato-whats-row')) return;
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

        $$('.crm-mock-contato-whats-row', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var tel = btn.querySelector('span').textContent;
                var digits = normalizarTelefone(tel);
                if (digits) window.open('https://wa.me/' + digits, '_blank', 'noopener');
            });
        });
    }

    function ativIconClass(tipo) {
        if (tipo === 'ligacao' || tipo === 'phone') return 'crm-mock-ativ-icon-phone';
        if (tipo === 'reuniao' || tipo === 'meeting') return 'crm-mock-ativ-icon-meeting';
        if (tipo === 'doc') return 'crm-mock-ativ-icon-doc';
        return 'crm-mock-ativ-icon-note';
    }

    function ativIconHtml(tipo) {
        var icons = {
            ligacao: 'fa-phone', phone: 'fa-phone',
            reuniao: 'fa-users', meeting: 'fa-users',
            doc: 'fa-file-lines', note: 'fa-note-sticky'
        };
        var ic = icons[tipo] || 'fa-circle';
        var solid = ic === 'fa-file-lines' ? 'fa-regular' : 'fa-solid';
        return '<span class="crm-mock-ativ-icon ' + ativIconClass(tipo) + '" aria-hidden="true"><i class="' + solid + ' ' + ic + '"></i></span>';
    }

    function prioridadeBadge(p) {
        var t = (p || '').toLowerCase();
        var type = t === 'alta' ? 'alta' : t === 'média' || t === 'media' ? 'media' : 'baixa';
        return '<span class="' + badgeDaisy(type) + '">' + escapeHtml(p) + '</span>';
    }

    function renderAtividades() {
        var container = $('#crm-mock-ativ-list');
        if (!container) return;

        var termo = state.buscaAtividade.toLowerCase().trim();
        var filtrados = state.atividades.filter(function (a) {
            if (state.filtroAtivTab === 'pendentes' && a.status === 'concluida') return false;
            if (state.filtroAtivTab === 'concluidas' && a.status !== 'concluida') return false;
            if (termo) {
                var blob = (a.titulo + ' ' + (a.descricao || '')).toLowerCase();
                if (blob.indexOf(termo) === -1) return false;
            }
            return true;
        });

        if (!state.clienteId) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Selecione um cliente.</div>';
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhuma atividade.</div>';
            return;
        }

        var groups = {};
        filtrados.forEach(function (a) {
            var label = a.data_label || 'Agendadas';
            if (!groups[label]) groups[label] = [];
            groups[label].push(a);
        });

        var html = '';
        Object.keys(groups).forEach(function (label) {
            html += '<div class="crm-mock-date-group"><div class="crm-mock-date-label text-xs font-semibold text-base-content/70 px-2 py-1">' + escapeHtml(label) + '</div>';
            groups[label].forEach(function (a) {
                var concluida = a.status === 'concluida';
                html += (
                    '<div class="crm-mock-ativ flex items-center gap-1 px-2 py-1' + (concluida ? ' crm-mock-ativ-concluida' : '') + '" role="listitem" data-status="' + escapeHtml(a.status) + '" data-atividade-id="' + escapeHtml(a.id) + '">' +
                    '<input type="checkbox" class="checkbox checkbox-xs checkbox-primary crm-mock-ativ-check" ' + (concluida ? 'checked' : '') + ' aria-label="Concluir: ' + escapeHtml(a.titulo) + '" />' +
                    ativIconHtml(a.tipo) +
                    '<div class="crm-mock-ativ-content min-w-0 flex-1">' +
                    '<div class="crm-mock-ativ-titulo text-sm truncate">' + escapeHtml(a.titulo) + '</div>' +
                    (a.descricao ? '<div class="crm-mock-ativ-desc text-xs text-base-content/60 truncate">' + escapeHtml(a.descricao) + '</div>' : '') +
                    '</div>' +
                    '<span class="crm-mock-ativ-time text-xs shrink-0">' + escapeHtml(a.hora || '') + '</span>' +
                    prioridadeBadge(a.prioridade) +
                    '<div class="crm-mock-avatar-mini shrink-0" title="' + escapeHtml(a.responsavel || '') + '">' + escapeHtml(a.responsavel || '') + '</div>' +
                    '<div class="dropdown dropdown-end shrink-0">' +
                    '<button type="button" class="btn btn-ghost btn-xs btn-square crm-mock-ativ-menu-btn" tabindex="0" aria-label="Mais opções"><i class="fa-solid fa-ellipsis-vertical"></i></button>' +
                    '<ul class="dropdown-content menu p-1 shadow bg-base-100 rounded-box w-40 border border-base-200 z-50 text-xs">' +
                    '<li><button type="button" class="crm-mock-ativ-action" data-action="concluir">Concluir</button></li>' +
                    '<li><button type="button" class="crm-mock-ativ-action" data-action="editar">Editar</button></li>' +
                    '<li><button type="button" class="crm-mock-ativ-action" data-action="reagendar">Reagendar</button></li>' +
                    '<li><button type="button" class="crm-mock-ativ-action" data-action="duplicar">Duplicar</button></li>' +
                    '<li><button type="button" class="crm-mock-ativ-action text-error" data-action="excluir">Excluir</button></li>' +
                    '</ul></div></div>'
                );
            });
            html += '</div>';
        });

        container.innerHTML = html;
        bindAtividadeEvents(container);
    }

    function bindAtividadeEvents(container) {
        $$('.crm-mock-ativ-check', container).forEach(function (cb) {
            cb.addEventListener('change', function () {
                var row = cb.closest('.crm-mock-ativ');
                var id = row.getAttribute('data-atividade-id');
                var status = cb.checked ? 'concluida' : 'pendente';
                api('/atividades/' + encodeURIComponent(id), { method: 'PATCH', body: { status: status } })
                    .then(function () {
                        row.classList.toggle('crm-mock-ativ-concluida', cb.checked);
                        row.setAttribute('data-status', status);
                        var a = state.atividades.find(function (x) { return x.id === id; });
                        if (a) a.status = status;
                        updateDetailPanel(state.cliente);
                    })
                    .catch(function (err) { showToast(err.message, true); cb.checked = !cb.checked; });
            });
        });

        $$('.crm-mock-ativ-action', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var row = btn.closest('.crm-mock-ativ');
                var id = row.getAttribute('data-atividade-id');
                var action = btn.getAttribute('data-action');
                var a = state.atividades.find(function (x) { return x.id === id; });
                if (!a) return;
                if (action === 'concluir') {
                    api('/atividades/' + encodeURIComponent(id), { method: 'PATCH', body: { status: 'concluida' } })
                        .then(function () { loadAtividades(state.clienteId); showToast('Atividade concluída'); })
                        .catch(function (err) { showToast(err.message, true); });
                } else if (action === 'editar' || action === 'reagendar') {
                    openAtividadeModal(a);
                } else if (action === 'duplicar') {
                    api('/clientes/' + encodeURIComponent(state.clienteId) + '/atividades', {
                        method: 'POST',
                        body: { titulo: a.titulo + ' (cópia)', descricao: a.descricao, prioridade: a.prioridade, hora: a.hora, data_label: a.data_label }
                    }).then(function () { loadAtividades(state.clienteId); showToast('Atividade duplicada'); })
                        .catch(function (err) { showToast(err.message, true); });
                } else if (action === 'excluir') {
                    api('/atividades/' + encodeURIComponent(id), { method: 'DELETE' })
                        .then(function () { loadAtividades(state.clienteId); showToast('Atividade excluída'); })
                        .catch(function (err) { showToast(err.message, true); });
                }
            });
        });
    }

    function renderObjetivos() {
        var container = $('#crm-mock-obj-list');
        if (!container) return;
        if (!state.objetivos.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhum objetivo.</div>';
            return;
        }
        container.innerHTML = state.objetivos.map(function (o) {
            return (
                '<div class="crm-mock-objetivo flex items-center gap-2 py-1" data-objetivo-id="' + escapeHtml(o.id) + '">' +
                '<input type="checkbox" class="checkbox checkbox-xs" aria-label="' + escapeHtml(o.texto) + '" />' +
                '<span class="crm-mock-obj-text text-sm flex-1 truncate" title="' + escapeHtml(o.texto) + '">' + escapeHtml(o.texto) + '</span>' +
                '<span class="crm-mock-obj-date text-xs text-base-content/60 shrink-0">' + escapeHtml(o.prazo || '') + '</span>' +
                '<div class="crm-mock-obj-actions flex gap-0">' +
                '<button type="button" class="crm-mock-obj-btn btn btn-ghost btn-xs btn-square" aria-label="Editar objetivo"><i class="fa-solid fa-pen"></i></button>' +
                '<button type="button" class="crm-mock-obj-delete btn btn-ghost btn-xs btn-square text-error" aria-label="Excluir objetivo" data-objetivo-id="' + escapeHtml(o.id) + '"><i class="fa-solid fa-trash"></i></button>' +
                '</div></div>'
            );
        }).join('');

        $$('.crm-mock-obj-delete', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                state.pendingObjetivoId = btn.getAttribute('data-objetivo-id');
                var o = state.objetivos.find(function (x) { return x.id === state.pendingObjetivoId; });
                var txt = $('#crm-mock-confirm-obj-text');
                if (txt && o) txt.textContent = 'Excluir objetivo “' + o.texto + '”?';
                openModal('crm-mock-modal-confirm-obj');
            });
        });
    }

    function renderCotacoes() {
        var container = $('#crm-mock-cotacao-list');
        if (!container) return;
        if (!state.cotacoes.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhuma cotação.</div>';
            return;
        }
        container.innerHTML = state.cotacoes.map(function (c) {
            return (
                '<article class="crm-mock-cotacao-card p-2 border border-base-200 rounded-lg mb-2">' +
                '<div class="crm-mock-cotacao-titulo text-sm font-medium truncate">' + escapeHtml(c.titulo) + '</div>' +
                '<div class="crm-mock-cotacao-valor text-sm font-semibold">' + escapeHtml(c.valor) + '</div>' +
                '<div class="crm-mock-cotacao-meta flex items-center gap-2 mt-1">' +
                '<span class="' + badgeDaisy(c.status) + '">' + escapeHtml(c.status_label || c.status) + '</span>' +
                '<span class="crm-mock-cotacao-data text-xs text-base-content/60">' + escapeHtml(c.data || '') + '</span>' +
                '</div></article>'
            );
        }).join('');
    }

    function selectContato(id) {
        state.contatoId = id;
        renderContatos();
    }

    function loadContatos(clienteId) {
        var container = $('#crm-mock-lista-contatos');
        if (container) {
            container.innerHTML = '<div class="p-3"><div class="skeleton h-12 w-full mb-2"></div><div class="skeleton h-12 w-full"></div></div>';
        }
        return api('/clientes/' + encodeURIComponent(clienteId) + '/contatos').then(function (data) {
            state.contatos = data.contatos || [];
            state.contatoId = state.contatos.length ? state.contatos[0].id : null;
            renderContatos();
        }).catch(function (err) {
            if (container) container.innerHTML = '<div class="crm-mock-contatos-empty p-3">Erro ao carregar contatos.</div>';
            showToast(err.message, true);
        });
    }

    function loadAtividades(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/atividades').then(function (data) {
            state.atividades = data.atividades || [];
            renderAtividades();
            if (state.cliente) {
                state.cliente.metrics = state.cliente.metrics || {};
                state.cliente.metrics.tarefas_abertas = state.atividades.filter(function (a) { return a.status !== 'concluida'; }).length;
                updateDetailPanel(state.cliente);
            }
        }).catch(function (err) { showToast(err.message, true); });
    }

    function loadObjetivos(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/objetivos').then(function (data) {
            state.objetivos = data.objetivos || [];
            renderObjetivos();
        }).catch(function (err) { showToast(err.message, true); });
    }

    function loadCotacoes(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/cotacoes').then(function (data) {
            state.cotacoes = data.cotacoes || [];
            renderCotacoes();
            if (state.cliente && state.cliente.metrics) {
                state.cliente.metrics.oportunidades = state.cotacoes.length;
                updateDetailPanel(state.cliente);
            }
        }).catch(function (err) { showToast(err.message, true); });
    }

    function selectCliente(clienteId) {
        state.clienteId = clienteId;
        state.cliente = state.clientes.find(function (c) { return c.id === clienteId; });
        renderClientes();
        updateDetailPanel(state.cliente);
        loadContatos(clienteId);
        loadAtividades(clienteId);
        loadObjetivos(clienteId);
        loadCotacoes(clienteId);
    }

    function loadClientes() {
        showClientesSkeleton();
        return api('/clientes').then(function (data) {
            state.clientes = data.clientes || [];
            renderClientes();
            if (state.clientes.length) {
                var first = state.clientes.find(function (c) { return c.id === state.clienteId; }) || state.clientes[0];
                selectCliente(first.id);
            }
        }).catch(function (err) {
            var container = $('#crm-mock-lista-clientes');
            if (container) container.innerHTML = '<div class="crm-mock-contatos-empty p-3">Erro ao carregar clientes.</div>';
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
        } else if (title) title.textContent = 'Novo contato';
        openModal('crm-mock-modal-contato');
    }

    function openClienteModal() {
        var form = $('#crm-mock-form-cliente');
        if (form) form.reset();
        openModal('crm-mock-modal-cliente');
    }

    function openAtividadeModal(ativ) {
        var form = $('#crm-mock-form-atividade');
        var title = $('#crm-mock-modal-atividade-title');
        if (!form) return;
        form.reset();
        $('#crm-mock-atividade-id').value = ativ ? ativ.id : '';
        if (title) title.textContent = ativ ? 'Editar atividade' : 'Nova atividade';
        if (ativ) {
            $('#crm-mock-atividade-titulo').value = ativ.titulo || '';
            $('#crm-mock-atividade-desc').value = ativ.descricao || '';
            $('#crm-mock-atividade-prioridade').value = ativ.prioridade || 'Média';
            $('#crm-mock-atividade-hora').value = ativ.hora || '';
        }
        openModal('crm-mock-modal-atividade');
    }

    function setImportStep(step) {
        var steps = $('#crm-mock-import-steps');
        if (steps) {
            $$('.step', steps).forEach(function (s) {
                var n = parseInt(s.getAttribute('data-step'), 10);
                s.classList.toggle('step-primary', n <= step);
            });
        }
        $('#crm-mock-import-step-1').hidden = step !== 1;
        $('#crm-mock-import-step-2').hidden = step !== 2;
        $('#crm-mock-import-step-3').hidden = step !== 3;
        var err = $('#crm-mock-import-error');
        if (err) err.hidden = true;
    }

    function openImportModal() {
        state.importRows = [];
        $('#crm-mock-import-texto').value = '';
        setImportStep(1);
        openModal('crm-mock-modal-import');
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
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
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
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formAtiv = $('#crm-mock-form-atividade');
        if (formAtiv) {
            formAtiv.addEventListener('submit', function (e) {
                e.preventDefault();
                if (!state.clienteId) {
                    showToast('Selecione um cliente', true);
                    return;
                }
                var btn = $('#crm-mock-atividade-submit');
                var ativId = $('#crm-mock-atividade-id').value;
                var body = {
                    titulo: $('#crm-mock-atividade-titulo').value,
                    descricao: $('#crm-mock-atividade-desc').value,
                    prioridade: $('#crm-mock-atividade-prioridade').value,
                    hora: $('#crm-mock-atividade-hora').value,
                    data_label: $('#crm-mock-atividade-data').value ? 'Agendada' : 'Hoje'
                };
                setBtnLoading(btn, true);
                var req = ativId
                    ? api('/atividades/' + encodeURIComponent(ativId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/atividades', { method: 'POST', body: body });
                req.then(function () {
                    closeModal('crm-mock-modal-atividade');
                    showToast(ativId ? 'Atividade atualizada' : 'Atividade criada');
                    return loadAtividades(state.clienteId);
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var processarBtn = $('#crm-mock-import-processar');
        if (processarBtn) {
            processarBtn.addEventListener('click', function () {
                var texto = ($('#crm-mock-import-texto').value || '').trim();
                if (!texto) {
                    showToast('Cole a lista de contatos', true);
                    return;
                }
                setBtnLoading(processarBtn, true);
                api('/contatos/parse-texto', { method: 'POST', body: { texto: texto } })
                    .then(function (data) {
                        state.importRows = data.contatos || [];
                        if (!state.importRows.length) {
                            var err = $('#crm-mock-import-error');
                            if (err) { err.textContent = 'Nenhum contato reconhecido.'; err.hidden = false; }
                            return;
                        }
                        renderImportTable();
                        setImportStep(2);
                    })
                    .catch(function (err) {
                        var el = $('#crm-mock-import-error');
                        if (el) { el.textContent = err.message; el.hidden = false; }
                    })
                    .finally(function () { setBtnLoading(processarBtn, false); });
            });
        }

        var next2 = $('#crm-mock-import-next-2');
        if (next2) next2.addEventListener('click', function () {
            collectImportRowsFromTable();
            var msg = $('#crm-mock-import-confirm-msg');
            if (msg) msg.textContent = 'Confirmar importação de ' + state.importRows.length + ' contato(s)?';
            setImportStep(3);
        });

        var back1 = $('#crm-mock-import-back-1');
        if (back1) back1.addEventListener('click', function () { setImportStep(1); });

        var back2 = $('#crm-mock-import-back-2');
        if (back2) back2.addEventListener('click', function () { setImportStep(2); });

        var importSubmit = $('#crm-mock-import-submit');
        if (importSubmit) {
            importSubmit.addEventListener('click', function () {
                if (!state.clienteId) {
                    showToast('Selecione um cliente', true);
                    return;
                }
                collectImportRowsFromTable();
                if (!state.importRows.length) {
                    showToast('Nenhum contato para importar', true);
                    return;
                }
                setBtnLoading(importSubmit, true);
                api('/clientes/' + encodeURIComponent(state.clienteId) + '/contatos/importar', {
                    method: 'POST',
                    body: { contatos: state.importRows }
                }).then(function (data) {
                    closeModal('crm-mock-modal-import');
                    showToast((data.importados || state.importRows.length) + ' contato(s) importado(s)');
                    return loadClientes();
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(importSubmit, false); });
            });
        }

        var confirmObj = $('#crm-mock-confirm-obj-btn');
        if (confirmObj) {
            confirmObj.addEventListener('click', function () {
                if (!state.pendingObjetivoId) return;
                api('/objetivos/' + encodeURIComponent(state.pendingObjetivoId), { method: 'DELETE' })
                    .then(function () {
                        closeModal('crm-mock-modal-confirm-obj');
                        showToast('Objetivo excluído');
                        return loadObjetivos(state.clienteId);
                    })
                    .catch(function (err) { showToast(err.message, true); });
            });
        }
    }

    function renderImportTable() {
        var tbody = $('#crm-mock-import-table tbody');
        var count = $('#crm-mock-import-review-count');
        if (!tbody) return;
        tbody.innerHTML = state.importRows.map(function (r, i) {
            return (
                '<tr data-row="' + i + '">' +
                '<td><input class="input input-xs input-bordered w-full crm-import-nome" value="' + escapeHtml(r.nome) + '" /></td>' +
                '<td><input class="input input-xs input-bordered w-full crm-import-email" value="' + escapeHtml(r.email) + '" /></td>' +
                '<td><input class="input input-xs input-bordered w-full crm-import-telefone" value="' + escapeHtml(r.telefone || '') + '" /></td>' +
                '<td><input class="input input-xs input-bordered w-full crm-import-cargo" value="' + escapeHtml(r.cargo || '') + '" /></td>' +
                '<td><input type="checkbox" class="checkbox checkbox-xs crm-import-principal" ' + (r.principal ? 'checked' : '') + ' /></td>' +
                '</tr>'
            );
        }).join('');
        if (count) count.textContent = state.importRows.length + ' contato(s) reconhecido(s). Edite se necessário.';
    }

    function collectImportRowsFromTable() {
        var rows = $$('#crm-mock-import-table tbody tr');
        state.importRows = rows.map(function (tr) {
            return {
                nome: (tr.querySelector('.crm-import-nome').value || '').trim(),
                email: (tr.querySelector('.crm-import-email').value || '').trim(),
                telefone: (tr.querySelector('.crm-import-telefone').value || '').trim(),
                cargo: (tr.querySelector('.crm-import-cargo').value || '').trim(),
                principal: tr.querySelector('.crm-import-principal').checked
            };
        }).filter(function (r) { return r.nome && r.email; });
    }

    function initTabs(groupName) {
        var tabContainer = document.querySelector('[data-tab-group="' + groupName + '"]');
        if (!tabContainer) return;
        var tabs = tabContainer.querySelectorAll('.crm-mock-tab, .tab');

        function activateTab(tab) {
            var target = tab.getAttribute('data-tab');
            tabs.forEach(function (t) {
                t.classList.remove('tab-active', 'crm-mock-tab-active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('tab-active', 'crm-mock-tab-active');
            tab.setAttribute('aria-selected', 'true');
            document.querySelectorAll('[data-panel-group="' + groupName + '"]').forEach(function (panel) {
                var isTarget = panel.getAttribute('data-panel') === target;
                panel.classList.toggle('crm-mock-tab-panel-active', isTarget);
                if (panel.hasAttribute('hidden')) panel.hidden = !isTarget;
            });
            if (groupName === 'atividades') {
                state.filtroAtivTab = target;
                renderAtividades();
            }
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

    function initFilters() {
        $$('.crm-mock-pill').forEach(function (pill) {
            pill.addEventListener('click', function () {
                $$('.crm-mock-pill').forEach(function (p) {
                    p.classList.remove('btn-active');
                    p.setAttribute('aria-pressed', 'false');
                });
                pill.classList.add('btn-active');
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

        var buscaAtiv = $('#busca-atividade');
        if (buscaAtiv) {
            buscaAtiv.addEventListener('input', debounce(function () {
                state.buscaAtividade = buscaAtiv.value;
                renderAtividades();
            }, 300));
        }
    }

    function initButtons() {
        var novoCliente = $('#crm-mock-btn-novo-cliente-header');
        if (novoCliente) novoCliente.addEventListener('click', openClienteModal);

        var novoContato = $('#crm-mock-btn-novo-contato');
        if (novoContato) novoContato.addEventListener('click', function () { openContatoModal(); });

        var importBtn = $('#crm-mock-btn-import-contatos');
        if (importBtn) importBtn.addEventListener('click', openImportModal);

        var novaAtiv = $('#crm-mock-btn-nova-atividade');
        if (novaAtiv) novaAtiv.addEventListener('click', function () { openAtividadeModal(null); });

        var agendar = $('#crm-mock-btn-agendar');
        if (agendar) agendar.addEventListener('click', function () { openAtividadeModal(null); });

        var verTodos = $('#crm-mock-ver-todos-contatos');
        if (verTodos) {
            verTodos.addEventListener('click', function () {
                var col = $('.crm-mock-col-contatos');
                if (col) col.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }

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
    showOverlay('Carregando CRM…');
    loadClientes().finally(hideOverlay);
})();
