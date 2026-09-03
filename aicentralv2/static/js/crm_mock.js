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
        notas: [],
        filtroPill: 'todos',
        filtroExecutivo: '',
        filtroTipo: '',
        filtroPerfil: '',
        filtroAtivResponsavel: '',
        filtroAtivTipo: '',
        buscaCliente: '',
        buscaContato: '',
        buscaAtividade: '',
        filtroAtivTab: 'todas',
        paginaCliente: 1,
        clientesPorPagina: 8,
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
            return res.text().then(function (text) {
                var data;
                try {
                    data = text ? JSON.parse(text) : {};
                } catch (e) {
                    throw new Error('Resposta inválida do servidor (HTTP ' + res.status + ')');
                }
                if (!res.ok || data.success === false) {
                    throw new Error(data.error || 'Erro na requisição');
                }
                return data;
            });
        }).catch(function (err) {
            if (err instanceof TypeError) {
                throw new Error('Não foi possível conectar ao serviço mock.');
            }
            throw err;
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
            success: 'badge-success', hoje: 'badge-success',
            aprovada: 'badge-success',
            warning: 'badge-warning', atrasado: 'badge-warning', amanha: 'badge-warning', media: 'badge-warning',
            expirada: 'badge-warning',
            info: 'badge-info', enviada: 'badge-info', seguindo: 'badge-info', 'em acompanhamento': 'badge-info',
            danger: 'badge-error', error: 'badge-error', alta: 'badge-error', rejeitada: 'badge-error',
            muted: 'badge-ghost', 'sem-atividade': 'badge-ghost', baixa: 'badge-ghost', rascunho: 'badge-ghost'
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

    function dataParaInput(valor) {
        if (!valor) return '';
        if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return valor;
        var br = String(valor).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        return br ? br[3] + '-' + br[2] + '-' + br[1] : '';
    }

    function dataParaExibicao(valor) {
        if (!valor) return '';
        var iso = String(valor).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        return iso ? iso[3] + '/' + iso[2] + '/' + iso[1] : valor;
    }

    function copiarTexto(texto) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(texto);
        }
        var input = document.createElement('textarea');
        input.value = texto;
        input.setAttribute('readonly', '');
        input.style.position = 'fixed';
        input.style.opacity = '0';
        document.body.appendChild(input);
        input.select();
        var ok = document.execCommand('copy');
        input.remove();
        return ok ? Promise.resolve() : Promise.reject(new Error('Não foi possível copiar'));
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
            if (state.filtroPill === 'seguindo' && !c.seguindo) return false;
            if (state.filtroPill !== 'todos' && state.filtroPill !== 'seguindo' && c.status !== state.filtroPill) return false;
            if (state.filtroExecutivo && c.responsavel !== state.filtroExecutivo) return false;
            if (state.filtroTipo && String(c.tipo || c.categoria || '').toLowerCase() !== state.filtroTipo) return false;
            if (state.filtroPerfil && c.perfil !== state.filtroPerfil) return false;
            if (termo && c.nome.toLowerCase().indexOf(termo) === -1) return false;
            return true;
        });

        var countEl = $('.crm-mock-col-clientes .crm-mock-count');
        if (countEl) countEl.textContent = filtrados.length;

        updatePillCounts();
        var semContato = $('#crm-mock-sem-contato-count');
        if (semContato) semContato.textContent = state.clientes.filter(function (c) { return !c.qtd_contatos; }).length;

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-mock-contatos-empty p-3 text-sm text-base-content/60">Nenhum cliente encontrado.</div>';
            updatePagination(0);
            return;
        }

        var totalPaginas = Math.max(1, Math.ceil(filtrados.length / state.clientesPorPagina));
        if (state.paginaCliente > totalPaginas) state.paginaCliente = totalPaginas;
        var inicio = (state.paginaCliente - 1) * state.clientesPorPagina;
        var pagina = filtrados.slice(inicio, inicio + state.clientesPorPagina);
        updatePagination(totalPaginas);

        container.innerHTML = pagina.map(function (c) {
            var ativo = c.id === state.clienteId;
            return (
                '<div class="crm-mock-cliente flex items-start gap-2 px-2 py-2 cursor-pointer transition-colors' +
                (ativo ? ' crm-mock-cliente-ativo' : '') + '"' +
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
            if (c.status === 'atrasado') counts.atrasado++;
            if (c.status === 'sem-atividade') counts['sem-atividade']++;
            if (c.seguindo) counts.seguindo++;
        });
        $$('.crm-mock-pill').forEach(function (pill) {
            var f = pill.getAttribute('data-filter');
            var span = pill.querySelector('.crm-mock-pill-count');
            if (span && counts[f] !== undefined) span.textContent = counts[f];
        });
    }

    function updatePagination(totalPaginas) {
        var label = $('#crm-mock-page-label');
        var prev = $('#crm-mock-page-prev');
        var next = $('#crm-mock-page-next');
        totalPaginas = totalPaginas || 1;
        if (label) label.textContent = state.paginaCliente + '/' + totalPaginas;
        if (prev) prev.disabled = state.paginaCliente <= 1;
        if (next) next.disabled = state.paginaCliente >= totalPaginas;
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
        var star = $('.crm-mock-star');
        if (star) {
            star.classList.toggle('active', !!cliente.favorito);
            star.setAttribute('aria-pressed', cliente.favorito ? 'true' : 'false');
            star.setAttribute('aria-label', cliente.favorito ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
        }

        var metaResp = $('#crm-mock-meta-responsavel');
        if (metaResp) metaResp.textContent = cliente.responsavel || '—';

        var metaCat = $('#crm-mock-meta-categoria');
        if (metaCat) metaCat.textContent = cliente.tipo || cliente.categoria || '—';

        var metaPri = $('#crm-mock-meta-prioridade');
        if (metaPri) {
            metaPri.textContent = 'Prioridade: ' + (cliente.prioridade || '—');
            metaPri.className = 'badge badge-sm ' + (cliente.prioridade === 'Alta' ? 'badge-error' : cliente.prioridade === 'Média' ? 'badge-warning' : 'badge-ghost');
        }

        var infoCategoria = $('#crm-mock-info-categoria');
        var infoClassificacao = $('#crm-mock-info-classificacao');
        var infoTipo = $('#crm-mock-info-tipo');
        var infoPrioridade = $('#crm-mock-info-prioridade');
        var infoCnpj = $('#crm-mock-info-cnpj');
        var infoFonte = $('#crm-mock-info-fonte');
        var infoCriado = $('#crm-mock-info-criado');
        var infoSegmento = $('#crm-mock-info-segmento');
        var infoCidade = $('#crm-mock-info-cidade');
        if (infoCategoria) infoCategoria.textContent = cliente.tipo_label || '—';
        if (infoClassificacao) infoClassificacao.textContent = cliente.classificacao_cliente || cliente.classificacao || '—';
        if (infoTipo) infoTipo.textContent = cliente.tipo || cliente.categoria || '—';
        if (infoCnpj) infoCnpj.textContent = cliente.cnpj || '—';
        if (infoFonte) infoFonte.textContent = cliente.fonte || '—';
        if (infoCriado) infoCriado.textContent = dataParaExibicao(cliente.data_cadastro) || '—';
        if (infoSegmento) infoSegmento.textContent = cliente.segmento || '—';
        if (infoCidade) infoCidade.textContent = [cliente.cidade, cliente.uf].filter(Boolean).join(', ') || '—';
        if (infoPrioridade) {
            infoPrioridade.textContent = cliente.prioridade || '—';
            infoPrioridade.classList.toggle('text-error', cliente.prioridade === 'Alta');
        }
        var responsavelNome = $('#crm-mock-responsavel-nome');
        var responsavelAvatar = $('#crm-mock-responsavel-avatar');
        var responsavelEmail = $('#crm-mock-responsavel-email');
        if (responsavelNome) responsavelNome.textContent = cliente.responsavel || '—';
        if (responsavelAvatar) responsavelAvatar.textContent = avatarIniciais(cliente.responsavel);
        if (responsavelEmail) {
            responsavelEmail.textContent = cliente.responsavel
                ? cliente.responsavel.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '.') + '@centralcomm.media'
                : '—';
        }
        updateFollowButton(cliente);

        var m = cliente.metrics || {};
        var el;
        el = $('#crm-metric-contatos'); if (el) el.textContent = m.contatos != null ? m.contatos : cliente.qtd_contatos || 0;
        el = $('#crm-metric-oportunidades'); if (el) el.textContent = m.oportunidades != null ? m.oportunidades : 0;
        el = $('#crm-metric-faturamento'); if (el) el.textContent = m.faturamento || '—';
        el = $('#crm-metric-pis'); if (el) el.textContent = m.valor_pis || '—';
        el = $('#crm-metric-tarefas'); if (el) el.textContent = m.tarefas_abertas != null ? m.tarefas_abertas : 0;
        el = $('#crm-metric-ultimo'); if (el) el.textContent = m.ultimo_contato || '—';
    }

    function updateFollowButton(cliente) {
        var btn = $('#crm-mock-seguir-toggle');
        if (!btn || !cliente) return;
        btn.textContent = cliente.seguindo ? 'Deixar de seguir' : 'Seguir cliente';
        btn.setAttribute('aria-pressed', cliente.seguindo ? 'true' : 'false');
        btn.classList.toggle('btn-error', !!cliente.seguindo);
        btn.classList.toggle('btn-primary', !cliente.seguindo);
    }

    function updateSidebarContato(contato) {
        var nomeEl = $('#crm-mock-sidebar-contato-nome');
        var cargoEl = $('#crm-mock-sidebar-contato-cargo');
        var setorEl = $('#crm-mock-sidebar-contato-setor');
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
            if (setorEl) setorEl.textContent = '';
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
        if (setorEl) setorEl.textContent = contato.setor || contato.status || '';
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
                if (!contato.email) return;
                copiarTexto(contato.email)
                    .then(function () { showToast('E-mail copiado'); })
                    .catch(function (err) { showToast(err.message, true); });
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
                if (!text) return;
                copiarTexto(text)
                    .then(function () { showToast('E-mail copiado'); })
                    .catch(function (err) { showToast(err.message, true); });
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
            if (state.filtroAtivResponsavel && a.responsavel !== state.filtroAtivResponsavel) return false;
            if (state.filtroAtivTipo && a.tipo !== state.filtroAtivTipo) return false;
            if (termo) {
                var blob = (a.titulo + ' ' + (a.descricao || '')).toLowerCase();
                if (blob.indexOf(termo) === -1) return false;
            }
            return true;
        });

        if (!state.clienteId) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Selecione um cliente.</div>';
            renderSidebarAtividades();
            renderSugestao();
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhuma atividade.</div>';
            renderSidebarAtividades();
            renderSugestao();
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
        renderSidebarAtividades();
        renderSugestao();
    }

    function populateAtividadeResponsaveis() {
        var select = $('#filtro-resp-ativ');
        if (!select) return;
        var current = state.filtroAtivResponsavel;
        var values = [];
        state.atividades.forEach(function (a) {
            if (a.responsavel && values.indexOf(a.responsavel) === -1) values.push(a.responsavel);
        });
        select.innerHTML = '<option value="">Responsável: todos</option>' + values.map(function (v) {
            return '<option value="' + escapeHtml(v) + '">' + escapeHtml(v) + '</option>';
        }).join('');
        select.value = current;
    }

    function renderSidebarAtividades() {
        var container = $('#crm-mock-sidebar-atividades-list');
        if (!container) return;
        var items = state.atividades.slice(0, 6);
        if (!items.length) {
            container.innerHTML = '<p class="text-sm text-base-content/60">Nenhuma atividade registrada.</p>';
            return;
        }
        container.innerHTML = items.map(function (a) {
            return '<div class="crm-mock-mini-ativ">' +
                ativIconHtml(a.tipo) +
                '<div class="crm-mock-mini-ativ-text">' + escapeHtml(a.titulo) + '</div>' +
                '<span class="crm-mock-mini-ativ-time">' + escapeHtml((a.data_label || '') + (a.hora ? ' · ' + a.hora : '')) + '</span>' +
                '</div>';
        }).join('');
    }

    function renderSugestao() {
        var el = $('#crm-mock-sugestao-texto');
        if (!el) return;
        var pendentes = state.atividades.filter(function (a) { return a.status !== 'concluida'; });
        el.textContent = pendentes.length
            ? 'Há ' + pendentes.length + ' atividade(s) pendente(s). Priorize o próximo contato e mantenha o cliente atualizado.'
            : 'Sem atividades pendentes. Agende um contato para gerar novas oportunidades.';
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
                        body: {
                            titulo: a.titulo + ' (cópia)',
                            descricao: a.descricao,
                            prioridade: a.prioridade,
                            hora: a.hora,
                            data: a.data,
                            data_label: a.data_label,
                            tipo: a.tipo,
                            responsavel: a.responsavel
                        }
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
        var container = $('#crm-mock-sidebar-objetivos-list');
        if (!container) return;
        if (!state.objetivos.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60">Nenhum objetivo registrado.</div>';
            return;
        }
        container.innerHTML = state.objetivos.map(function (o) {
            return (
                '<div class="crm-mock-objetivo flex items-center gap-2 py-2" data-objetivo-id="' + escapeHtml(o.id) + '">' +
                '<input type="checkbox" class="checkbox checkbox-xs crm-mock-obj-toggle" ' + (o.concluido ? 'checked' : '') + ' aria-label="' + escapeHtml(o.texto) + '" />' +
                '<span class="crm-mock-obj-text text-sm flex-1" title="' + escapeHtml(o.texto) + '">' + escapeHtml(o.texto) + '</span>' +
                '<span class="crm-mock-obj-date text-xs text-base-content/60 shrink-0">' + escapeHtml(dataParaExibicao(o.prazo)) + '</span>' +
                '<div class="crm-mock-obj-actions flex gap-0">' +
                '<button type="button" class="crm-mock-obj-edit btn btn-ghost btn-xs btn-square" aria-label="Editar objetivo" data-objetivo-id="' + escapeHtml(o.id) + '"><i class="fa-solid fa-pen"></i></button>' +
                '<button type="button" class="crm-mock-obj-delete btn btn-ghost btn-xs btn-square text-error" aria-label="Excluir objetivo" data-objetivo-id="' + escapeHtml(o.id) + '"><i class="fa-solid fa-trash"></i></button>' +
                '</div></div>'
            );
        }).join('');

        $$('.crm-mock-obj-toggle', container).forEach(function (cb) {
            cb.addEventListener('change', function () {
                var id = cb.closest('[data-objetivo-id]').getAttribute('data-objetivo-id');
                api('/objetivos/' + encodeURIComponent(id), { method: 'PATCH', body: { concluido: cb.checked } })
                    .then(function () { return loadObjetivos(state.clienteId); })
                    .catch(function (err) { cb.checked = !cb.checked; showToast(err.message, true); });
            });
        });
        $$('.crm-mock-obj-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-objetivo-id');
                openObjetivoModal(state.objetivos.find(function (o) { return o.id === id; }));
            });
        });
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
            var titulo = c.nome_campanha || c.titulo || 'Cotação sem título';
            var numero = c.numero_cotacao || '';
            var periodo = [dataParaExibicao(c.periodo_inicio), dataParaExibicao(c.periodo_fim)].filter(Boolean).join(' – ');
            return (
                '<article class="crm-mock-cotacao-card p-2 border border-base-200 rounded-lg mb-2">' +
                '<div class="flex items-start gap-1"><div class="min-w-0 flex-1">' +
                (numero ? '<div class="crm-mock-cotacao-numero">' + escapeHtml(numero) + '</div>' : '') +
                '<div class="crm-mock-cotacao-titulo text-sm font-medium">' + escapeHtml(titulo) + '</div></div>' +
                '<div class="dropdown dropdown-end"><button type="button" class="btn btn-ghost btn-xs btn-square" tabindex="0" aria-label="Ações da cotação"><i class="fa-solid fa-ellipsis-vertical"></i></button>' +
                '<ul class="dropdown-content menu p-1 shadow bg-base-100 rounded-box w-32 border border-base-200 z-50 text-xs">' +
                '<li><button type="button" class="crm-mock-cotacao-edit" data-cotacao-id="' + escapeHtml(c.id) + '">Editar</button></li>' +
                '<li><button type="button" class="crm-mock-cotacao-delete text-error" data-cotacao-id="' + escapeHtml(c.id) + '">Excluir</button></li></ul></div></div>' +
                '<div class="crm-mock-cotacao-valor text-sm font-semibold">' + escapeHtml(c.valor) + '</div>' +
                '<div class="crm-mock-cotacao-meta flex items-center gap-2 mt-1">' +
                '<span class="' + badgeDaisy(c.status) + '">' + escapeHtml(c.status_label || c.status) + '</span>' +
                '<span class="crm-mock-cotacao-data text-xs text-base-content/60">' + escapeHtml(periodo || dataParaExibicao(c.data)) + '</span>' +
                '</div></article>'
            );
        }).join('');
        $$('.crm-mock-cotacao-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-cotacao-id');
                openCotacaoModal(state.cotacoes.find(function (c) { return c.id === id; }));
            });
        });
        $$('.crm-mock-cotacao-delete', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-cotacao-id');
                api('/cotacoes/' + encodeURIComponent(id), { method: 'DELETE' })
                    .then(function () { showToast('Cotação excluída'); return loadCotacoes(state.clienteId); })
                    .catch(function (err) { showToast(err.message, true); });
            });
        });
    }

    function renderNotas() {
        var container = $('#crm-mock-notas-list');
        if (!container) return;
        if (!state.notas.length) {
            container.innerHTML = '<p class="text-sm text-base-content/60">Nenhuma nota registrada para este cliente.</p>';
            return;
        }
        container.innerHTML = state.notas.map(function (nota) {
            return '<article class="rounded-lg border border-base-200 p-2" data-nota-id="' + escapeHtml(nota.id) + '">' +
                '<p class="text-sm whitespace-pre-wrap">' + escapeHtml(nota.texto) + '</p>' +
                '<div class="flex justify-between items-center mt-1"><span class="text-xs text-base-content/50">' +
                escapeHtml(dataParaExibicao(nota.data) || 'Agora') + '</span>' +
                '<span><button type="button" class="btn btn-ghost btn-xs crm-mock-nota-edit" aria-label="Editar nota"><i class="fa-solid fa-pen"></i></button>' +
                '<button type="button" class="btn btn-ghost btn-xs text-error crm-mock-nota-delete" aria-label="Excluir nota"><i class="fa-solid fa-trash"></i></button></span></div></article>';
        }).join('');
        $$('.crm-mock-nota-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.closest('[data-nota-id]').getAttribute('data-nota-id');
                openNotaModal(state.notas.find(function (n) { return n.id === id; }));
            });
        });
        $$('.crm-mock-nota-delete', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.closest('[data-nota-id]').getAttribute('data-nota-id');
                api('/notas/' + encodeURIComponent(id), { method: 'DELETE' })
                    .then(function () { showToast('Nota excluída'); return loadNotas(state.clienteId); })
                    .catch(function (err) { showToast(err.message, true); });
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
            container.innerHTML = '<div class="p-3"><div class="skeleton h-12 w-full mb-2"></div><div class="skeleton h-12 w-full"></div></div>';
        }
        return api('/clientes/' + encodeURIComponent(clienteId) + '/contatos').then(function (data) {
            if (state.clienteId !== clienteId) return;
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
            if (state.clienteId !== clienteId) return;
            state.atividades = data.atividades || [];
            populateAtividadeResponsaveis();
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
            if (state.clienteId !== clienteId) return;
            state.objetivos = data.objetivos || [];
            renderObjetivos();
        }).catch(function (err) { showToast(err.message, true); });
    }

    function loadCotacoes(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/cotacoes').then(function (data) {
            if (state.clienteId !== clienteId) return;
            state.cotacoes = data.cotacoes || [];
            renderCotacoes();
            if (state.cliente && state.cliente.metrics) {
                state.cliente.metrics.oportunidades = state.cotacoes.length;
                updateDetailPanel(state.cliente);
            }
        }).catch(function (err) { showToast(err.message, true); });
    }

    function loadNotas(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/notas').then(function (data) {
            if (state.clienteId !== clienteId) return;
            state.notas = data.notas || [];
            renderNotas();
        }).catch(function (err) {
            state.notas = [];
            renderNotas();
            showToast(err.message, true);
        });
    }

    function selectCliente(clienteId) {
        state.clienteId = clienteId;
        state.cliente = state.clientes.find(function (c) { return c.id === clienteId; });
        state.atividades = [];
        state.objetivos = [];
        state.cotacoes = [];
        state.notas = [];
        renderClientes();
        updateDetailPanel(state.cliente);
        renderAtividades();
        renderObjetivos();
        renderCotacoes();
        renderNotas();
        loadContatos(clienteId);
        loadAtividades(clienteId);
        loadObjetivos(clienteId);
        loadCotacoes(clienteId);
        loadNotas(clienteId);
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
            $('#crm-mock-contato-setor').value = c.setor || '';
            $('#crm-mock-contato-status').value = c.status || 'Ativo';
            $('#crm-mock-contato-telefone').value = c.telefone || '';
            $('#crm-mock-contato-telefone2').value = c.telefone_secundario || '';
            $('#crm-mock-contato-principal').checked = c.principal;
        } else if (title) title.textContent = 'Novo contato';
        openModal('crm-mock-modal-contato');
    }

    function openClienteModal(cliente) {
        var form = $('#crm-mock-form-cliente');
        if (form) form.reset();
        var id = $('#crm-mock-cliente-id');
        var title = $('#crm-mock-modal-cliente-title');
        var submitText = $('#crm-mock-cliente-submit .crm-mock-btn-text');
        if (id) id.value = cliente ? cliente.id : '';
        if (title) title.textContent = cliente ? 'Editar cliente' : 'Novo cliente';
        if (submitText) submitText.textContent = cliente ? 'Salvar alterações' : 'Criar cliente';
        if (cliente) {
            $('#crm-mock-cliente-nome').value = cliente.nome || '';
            $('#crm-mock-cliente-perfil').value = cliente.perfil || 'direto';
            $('#crm-mock-cliente-categoria').value = cliente.tipo || cliente.categoria || 'Privado';
            $('#crm-mock-cliente-prioridade').value = cliente.prioridade || 'Média';
            $('#crm-mock-cliente-responsavel').value = cliente.responsavel || 'Luisa Santana';
        }
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
            $('#crm-mock-atividade-data').value = ativ.data || '';
            $('#crm-mock-atividade-tipo').value = ativ.tipo || 'atividade';
            $('#crm-mock-atividade-responsavel').value = ativ.responsavel || 'LS';
        }
        openModal('crm-mock-modal-atividade');
    }

    function openObjetivoModal(objetivo) {
        var form = $('#crm-mock-form-objetivo');
        if (!form) return;
        form.reset();
        $('#crm-mock-objetivo-id').value = objetivo ? objetivo.id : '';
        $('#crm-mock-modal-objetivo-title').textContent = objetivo ? 'Editar objetivo' : 'Novo objetivo';
        if (objetivo) {
            $('#crm-mock-objetivo-texto').value = objetivo.texto || '';
            $('#crm-mock-objetivo-prazo').value = dataParaInput(objetivo.prazo);
        }
        openModal('crm-mock-modal-objetivo');
    }

    function openCotacaoModal(cotacao) {
        var form = $('#crm-mock-form-cotacao');
        if (form) form.reset();
        $('#crm-mock-cotacao-id').value = cotacao ? cotacao.id : '';
        $('#crm-mock-modal-cotacao-title').textContent = cotacao ? 'Editar cotação' : 'Nova cotação';
        var inicio = $('#crm-mock-cotacao-inicio');
        var fim = $('#crm-mock-cotacao-fim');
        if (inicio) inicio.value = cotacao ? dataParaInput(cotacao.periodo_inicio || cotacao.data) : new Date().toISOString().slice(0, 10);
        if (fim) fim.value = cotacao ? dataParaInput(cotacao.periodo_fim) : '';
        if (cotacao) {
            $('#crm-mock-cotacao-titulo').value = cotacao.nome_campanha || cotacao.titulo || '';
            $('#crm-mock-cotacao-valor').value = cotacao.valor_total || cotacao.valor || '';
            $('#crm-mock-cotacao-status').value = cotacao.status || 'rascunho';
        }
        openModal('crm-mock-modal-cotacao');
    }

    function openNotaModal(nota) {
        var form = $('#crm-mock-form-nota');
        if (!form) return;
        form.reset();
        $('#crm-mock-nota-id').value = nota ? nota.id : '';
        $('#crm-mock-modal-nota-title').textContent = nota ? 'Editar nota' : 'Nova nota';
        $('#crm-mock-nota-texto').value = nota ? nota.texto : '';
        openModal('crm-mock-modal-nota');
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
                    setor: $('#crm-mock-contato-setor').value,
                    status: $('#crm-mock-contato-status').value,
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
                var clienteId = $('#crm-mock-cliente-id').value;
                var perfil = $('#crm-mock-cliente-perfil').value;
                var tipoCliente = $('#crm-mock-cliente-categoria').value;
                var body = {
                    nome: $('#crm-mock-cliente-nome').value,
                    perfil: perfil,
                    tipo_label: perfil === 'agencia' ? 'Agência' : 'Cliente final',
                    categoria: tipoCliente,
                    tipo: tipoCliente,
                    prioridade: $('#crm-mock-cliente-prioridade').value,
                    responsavel: $('#crm-mock-cliente-responsavel').value
                };
                setBtnLoading(btn, true);
                var req = clienteId
                    ? api('/clientes/' + encodeURIComponent(clienteId), { method: 'PATCH', body: body })
                    : api('/clientes', { method: 'POST', body: body });
                req.then(function (data) {
                    closeModal('crm-mock-modal-cliente');
                    showToast(clienteId ? 'Cliente atualizado' : 'Cliente criado');
                    state.clienteId = (data.cliente && data.cliente.id) || clienteId;
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
                    data: $('#crm-mock-atividade-data').value,
                    data_label: $('#crm-mock-atividade-data').value ? 'Agendada' : 'Hoje',
                    tipo: $('#crm-mock-atividade-tipo').value,
                    responsavel: $('#crm-mock-atividade-responsavel').value
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

        var formObjetivo = $('#crm-mock-form-objetivo');
        if (formObjetivo) {
            formObjetivo.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-objetivo-submit');
                var objetivoId = $('#crm-mock-objetivo-id').value;
                var body = {
                    texto: $('#crm-mock-objetivo-texto').value,
                    prazo: $('#crm-mock-objetivo-prazo').value
                };
                setBtnLoading(btn, true);
                var req = objetivoId
                    ? api('/objetivos/' + encodeURIComponent(objetivoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/objetivos', { method: 'POST', body: body });
                req.then(function () {
                    closeModal('crm-mock-modal-objetivo');
                    showToast(objetivoId ? 'Objetivo atualizado' : 'Objetivo criado');
                    return loadObjetivos(state.clienteId);
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formCotacao = $('#crm-mock-form-cotacao');
        if (formCotacao) {
            formCotacao.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-cotacao-submit');
                var cotacaoId = $('#crm-mock-cotacao-id').value;
                var status = $('#crm-mock-cotacao-status').value;
                var titulo = $('#crm-mock-cotacao-titulo').value;
                var valor = $('#crm-mock-cotacao-valor').value;
                var inicio = $('#crm-mock-cotacao-inicio').value;
                var body = {
                    titulo: titulo,
                    nome_campanha: titulo,
                    valor: valor,
                    valor_total: valor,
                    status: status,
                    status_label: {
                        rascunho: 'Rascunho',
                        enviada: 'Enviada',
                        aprovada: 'Aprovada',
                        rejeitada: 'Rejeitada',
                        expirada: 'Expirada',
                        'em-acompanhamento': 'Em Acompanhamento'
                    }[status],
                    data: inicio,
                    periodo_inicio: inicio,
                    periodo_fim: $('#crm-mock-cotacao-fim').value
                };
                setBtnLoading(btn, true);
                var req = cotacaoId
                    ? api('/cotacoes/' + encodeURIComponent(cotacaoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/cotacoes', { method: 'POST', body: body });
                req
                    .then(function () {
                        closeModal('crm-mock-modal-cotacao');
                        showToast(cotacaoId ? 'Cotação atualizada' : 'Cotação criada');
                        return loadCotacoes(state.clienteId);
                    }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formNota = $('#crm-mock-form-nota');
        if (formNota) {
            formNota.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-mock-nota-submit');
                var notaId = $('#crm-mock-nota-id').value;
                setBtnLoading(btn, true);
                var req = notaId
                    ? api('/notas/' + encodeURIComponent(notaId), { method: 'PATCH', body: { texto: $('#crm-mock-nota-texto').value } })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/notas', { method: 'POST', body: { texto: $('#crm-mock-nota-texto').value } });
                req.then(function () {
                    closeModal('crm-mock-modal-nota');
                    showToast(notaId ? 'Nota atualizada' : 'Nota adicionada');
                    formNota.reset();
                    return loadNotas(state.clienteId);
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
            if (!validarImportRows()) return;
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
                if (!validarImportRows()) return;
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

    function validarImportRows() {
        var erro = $('#crm-mock-import-error');
        if (!state.importRows.length) {
            if (erro) {
                erro.textContent = 'Nenhum contato válido para importar.';
                erro.hidden = false;
            }
            return false;
        }
        var invalido = state.importRows.find(function (r) { return r.email.indexOf('@') === -1; });
        if (invalido) {
            setImportStep(2);
            if (erro) {
                erro.textContent = 'Revise o e-mail de ' + invalido.nome + '.';
                erro.hidden = false;
            }
            return false;
        }
        if (erro) erro.hidden = true;
        return true;
    }

    function initTabs(groupName) {
        var tabContainer = document.querySelector('[data-tab-group="' + groupName + '"]');
        if (!tabContainer) return;
        var tabs = tabContainer.querySelectorAll('.crm-mock-tab, .tab');

        function activateTab(tab) {
            var target = tab.getAttribute('data-tab');
            tabs.forEach(function (t) {
                t.classList.remove('is-active');
                t.setAttribute('aria-selected', 'false');
                t.setAttribute('tabindex', '-1');
            });
            tab.classList.add('is-active');
            tab.setAttribute('aria-selected', 'true');
            tab.setAttribute('tabindex', '0');
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
            tab.setAttribute('tabindex', tab.getAttribute('aria-selected') === 'true' ? '0' : '-1');
            tab.addEventListener('click', function () { activateTab(tab); });
            tab.addEventListener('keydown', function (e) {
                var next = index;
                if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
                else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
                else if (e.key === 'Home') next = 0;
                else if (e.key === 'End') next = tabs.length - 1;
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
                    p.classList.remove('is-active');
                    p.setAttribute('aria-pressed', 'false');
                });
                pill.classList.add('is-active');
                pill.setAttribute('aria-pressed', 'true');
                state.filtroPill = pill.getAttribute('data-filter') || 'todos';
                state.paginaCliente = 1;
                renderClientes();
            });
        });

        var buscaCliente = $('#crm-mock-busca');
        if (buscaCliente) {
            buscaCliente.addEventListener('input', function () {
                state.buscaCliente = buscaCliente.value;
                state.paginaCliente = 1;
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

        var executivo = $('#filtro-executivo');
        var tipo = $('#filtro-tipo');
        var perfil = $('#filtro-perfil');
        if (executivo) executivo.addEventListener('change', function () {
            state.filtroExecutivo = executivo.value;
            state.paginaCliente = 1;
            renderClientes();
        });
        if (tipo) tipo.addEventListener('change', function () {
            state.filtroTipo = tipo.value;
            state.paginaCliente = 1;
            renderClientes();
        });
        if (perfil) perfil.addEventListener('change', function () {
            state.filtroPerfil = perfil.value;
            state.paginaCliente = 1;
            renderClientes();
        });
        var respAtiv = $('#filtro-resp-ativ');
        var tipoAtiv = $('#filtro-tipo-ativ');
        if (respAtiv) respAtiv.addEventListener('change', function () {
            state.filtroAtivResponsavel = respAtiv.value;
            renderAtividades();
        });
        if (tipoAtiv) tipoAtiv.addEventListener('change', function () {
            state.filtroAtivTipo = tipoAtiv.value;
            renderAtividades();
        });
    }

    function exportarClientesCsv() {
        if (!state.clientes.length) {
            showToast('Não há clientes para exportar', true);
            return;
        }
        var rows = [['Nome', 'Tipo', 'Categoria', 'Responsável', 'Contatos', 'Seguindo']];
        state.clientes.forEach(function (c) {
            rows.push([c.nome, c.tipo_label, c.categoria, c.responsavel, c.qtd_contatos, c.seguindo ? 'Sim' : 'Não']);
        });
        var csv = rows.map(function (row) {
            return row.map(function (value) { return '"' + String(value == null ? '' : value).replace(/"/g, '""') + '"'; }).join(';');
        }).join('\n');
        var blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'clientes-crm-mock.csv';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showToast('CSV exportado');
    }

    function initButtons() {
        var novoCliente = $('#crm-mock-btn-novo-cliente-header');
        if (novoCliente) novoCliente.addEventListener('click', function () { openClienteModal(null); });
        var novoClienteLista = $('#crm-mock-btn-novo-cliente-lista');
        if (novoClienteLista) novoClienteLista.addEventListener('click', function () { openClienteModal(null); });

        var limpar = $('#crm-mock-btn-limpar-filtros');
        if (limpar) limpar.addEventListener('click', function () {
            state.filtroPill = 'todos';
            state.filtroExecutivo = '';
            state.filtroTipo = '';
            state.filtroPerfil = '';
            state.buscaCliente = '';
            state.paginaCliente = 1;
            $('#crm-mock-busca').value = '';
            $('#filtro-executivo').value = '';
            $('#filtro-tipo').value = '';
            $('#filtro-perfil').value = '';
            $$('.crm-mock-pill').forEach(function (pill) {
                var active = pill.getAttribute('data-filter') === 'todos';
                pill.classList.toggle('is-active', active);
                pill.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            renderClientes();
        });

        var exportar = $('#crm-mock-btn-exportar');
        if (exportar) exportar.addEventListener('click', exportarClientesCsv);
        var exportarHeader = $('.crm-mock-header-action-export');
        if (exportarHeader) exportarHeader.addEventListener('click', exportarClientesCsv);
        var editarHeader = $('.crm-mock-header-action-edit');
        if (editarHeader) editarHeader.addEventListener('click', function () { openClienteModal(state.cliente); });

        var prev = $('#crm-mock-page-prev');
        var next = $('#crm-mock-page-next');
        if (prev) prev.addEventListener('click', function () {
            if (state.paginaCliente > 1) { state.paginaCliente--; renderClientes(); }
        });
        if (next) next.addEventListener('click', function () {
            state.paginaCliente++;
            renderClientes();
        });

        var novoContato = $('#crm-mock-btn-novo-contato');
        if (novoContato) novoContato.addEventListener('click', function () { openContatoModal(); });

        var importBtn = $('#crm-mock-btn-import-contatos');
        if (importBtn) importBtn.addEventListener('click', openImportModal);

        var novaAtiv = $('#crm-mock-btn-nova-atividade');
        if (novaAtiv) novaAtiv.addEventListener('click', function () { openAtividadeModal(null); });

        var agendar = $('#crm-mock-btn-agendar');
        if (agendar) agendar.addEventListener('click', function () { openAtividadeModal(null); });

        var novoObjetivo = $('#crm-mock-btn-novo-objetivo');
        if (novoObjetivo) novoObjetivo.addEventListener('click', function () { openObjetivoModal(null); });
        var novaCotacao = $('#crm-mock-btn-nova-cotacao');
        if (novaCotacao) novaCotacao.addEventListener('click', function () { openCotacaoModal(null); });
        var novaNota = $('#crm-mock-btn-nova-nota');
        if (novaNota) novaNota.addEventListener('click', function () { openNotaModal(null); });
        var expandir = $('#crm-mock-btn-expandir-cotacoes');
        if (expandir) expandir.addEventListener('click', function () {
            var painel = $('.crm-mock-center-right');
            var expanded = painel.classList.toggle('is-expanded');
            expandir.setAttribute('aria-pressed', expanded ? 'true' : 'false');
            expandir.querySelector('i').className = expanded ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
        });

        var seguir = $('#crm-mock-seguir-toggle');
        if (seguir) seguir.addEventListener('click', function () {
            if (!state.cliente) return;
            seguir.disabled = true;
            api('/clientes/' + encodeURIComponent(state.cliente.id), {
                method: 'PATCH',
                body: { seguindo: !state.cliente.seguindo }
            }).then(function (data) {
                state.cliente = data.cliente;
                var idx = state.clientes.findIndex(function (c) { return c.id === state.cliente.id; });
                if (idx !== -1) state.clientes[idx] = data.cliente;
                updateDetailPanel(state.cliente);
                renderClientes();
                showToast(state.cliente.seguindo ? 'Cliente seguido' : 'Você deixou de seguir o cliente');
            }).catch(function (err) { showToast(err.message, true); })
                .finally(function () { seguir.disabled = false; });
        });

        var verTodos = $('#crm-mock-ver-todos-contatos');
        if (verTodos) {
            verTodos.addEventListener('click', function () {
                var col = $('.crm-mock-col-contatos');
                if (col) col.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }

        var verTodasAtividades = $('#crm-mock-ver-todas-atividades');
        if (verTodasAtividades) {
            verTodasAtividades.addEventListener('click', function () {
                var painel = $('.crm-mock-section-atividades');
                var tabTodas = $('#tab-atividades-todas');
                if (tabTodas) tabTodas.click();
                if (painel) {
                    painel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    painel.focus({ preventScroll: true });
                }
            });
        }

        $$('.crm-mock-star').forEach(function (star) {
            star.addEventListener('click', function () {
                if (!state.cliente) return;
                var active = !state.cliente.favorito;
                api('/clientes/' + encodeURIComponent(state.cliente.id), { method: 'PATCH', body: { favorito: active } })
                    .then(function (data) {
                        state.cliente = data.cliente;
                        star.classList.toggle('active', !!data.cliente.favorito);
                        star.setAttribute('aria-pressed', data.cliente.favorito ? 'true' : 'false');
                        star.setAttribute('aria-label', data.cliente.favorito ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
                    }).catch(function (err) { showToast(err.message, true); });
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
