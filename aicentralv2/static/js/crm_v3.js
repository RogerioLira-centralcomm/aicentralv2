(function () {
    'use strict';

    var API_BASE = '/crm-v3/api';

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

    /* ------------------------------------------------------------------
     * Persistência de sessão (last-client + filtros) via localStorage.
     * Objetivo: ao abrir o CRM, restaurar a experiência anterior do
     * usuário sem forçar re-render caro. Somente atalhos leves;
     * dados sempre vêm da API.
     * ------------------------------------------------------------------ */
    var LS_KEY = 'crm-v3.session.v1';

    function loadSession() {
        try {
            var raw = window.localStorage && window.localStorage.getItem(LS_KEY);
            if (!raw) return {};
            var parsed = JSON.parse(raw);
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (e) { return {}; }
    }

    function saveSession(patch) {
        try {
            if (!window.localStorage) return;
            var current = loadSession();
            var next = Object.assign({}, current, patch || {});
            window.localStorage.setItem(LS_KEY, JSON.stringify(next));
        } catch (e) { /* no-op: quota / privacy mode */ }
    }

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

    /**
     * Converte o badge textual do cliente ("Sem atividade 18 dias",
     * "Atrasado 2 dias", "Em 3 dias", "Hoje", "Amanhã", "Sem contato",
     * "Novo") em um sinalizador compacto no estilo Pipedrive:
     *   [ícone] [Nd | rótulo curto]
     * O tipo é dado pela cor sutil do ícone; o texto principal fica neutro.
     */
    function situacaoHtml(c) {
        var badge = c.badge || '';
        var type = (c.badge_type || '').toLowerCase();
        var m = badge.match(/(\d+)\s*dias?/i);
        var dias = m ? m[1] + 'd' : '';
        var icon, label, variante;

        if (type === 'danger' || /sem atividade/i.test(badge)) {
            icon = 'fa-solid fa-circle-question';
            label = dias || 'sem ativ.';
            variante = 'alert';
        } else if (type === 'warning' || /atrasad/i.test(badge)) {
            icon = 'fa-solid fa-triangle-exclamation';
            label = dias || 'atrasado';
            variante = 'atrasado';
        } else if (/^hoje/i.test(badge)) {
            icon = 'fa-regular fa-calendar-check';
            label = 'hoje';
            variante = 'hoje';
        } else if (/^amanh/i.test(badge)) {
            icon = 'fa-regular fa-calendar';
            label = 'amanhã';
            variante = 'agenda';
        } else if (/^em\s+\d+/i.test(badge)) {
            icon = 'fa-regular fa-calendar';
            label = dias || 'agendado';
            variante = 'agenda';
        } else if (/sem contato/i.test(badge)) {
            icon = 'fa-regular fa-circle';
            label = 'sem contato';
            variante = 'neutro';
        } else if (/novo/i.test(badge)) {
            icon = 'fa-solid fa-sparkles';
            label = 'novo';
            variante = 'agenda';
        } else {
            icon = 'fa-regular fa-circle';
            label = badge || '—';
            variante = 'neutro';
        }
        return (
            '<span class="crm-v3-sit crm-v3-sit--' + variante + '" title="' + escapeHtml(badge) + '">' +
            '<i class="' + icon + '" aria-hidden="true"></i>' +
            '<span class="crm-v3-sit-label">' + escapeHtml(label) + '</span>' +
            '</span>'
        );
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
        var wrap = $('#crm-v3-toast');
        var text = $('#crm-v3-toast-text');
        var alert = wrap && wrap.querySelector('.alert');
        if (!wrap || !text) return;
        text.textContent = msg;
        if (alert) {
            alert.classList.toggle('alert-error', !!isError);
            alert.classList.toggle('alert-success', !isError);
        }
        wrap.hidden = false;
        wrap.classList.add('crm-v3-toast-visible');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(function () {
            wrap.classList.remove('crm-v3-toast-visible');
            setTimeout(function () { wrap.hidden = true; }, 250);
        }, 2800);
    }

    function showOverlay(msg) {
        var el = $('#crm-v3-global-overlay');
        var msgEl = $('#crm-v3-overlay-msg');
        if (!el) return;
        if (msgEl) msgEl.textContent = msg || 'Carregando…';
        el.hidden = false;
        clearTimeout(state.overlayTimer);
        state.overlayTimer = setTimeout(function () {
            if (msgEl) msgEl.textContent = 'A operação está demorando…';
        }, 8000);
    }

    function hideOverlay() {
        var el = $('#crm-v3-global-overlay');
        clearTimeout(state.overlayTimer);
        if (el) el.hidden = true;
    }

    function openModal(id) {
        var dialog = document.getElementById(id);
        if (!dialog) return;
        dialog.classList.remove('crm-v3-modal-visible');
        dialog.showModal();
        requestAnimationFrame(function () {
            dialog.classList.add('crm-v3-modal-visible');
        });
    }

    function closeModal(id) {
        var dialog = document.getElementById(id);
        if (!dialog) return;
        dialog.classList.remove('crm-v3-modal-visible');
        setTimeout(function () {
            if (dialog.open) dialog.close();
        }, 180);
    }

    function setBtnLoading(btn, loading) {
        if (!btn) return;
        btn.classList.toggle('loading', loading);
        btn.disabled = loading;
        var spin = btn.querySelector('.crm-v3-btn-loading');
        if (spin) spin.hidden = !loading;
    }

    function showClientesSkeleton() {
        var container = $('#crm-v3-lista-clientes');
        if (!container) return;
        container.innerHTML =
            '<div class="crm-v3-skeleton-list p-2">' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '<div class="skeleton h-10 w-full mb-2"></div>' +
            '</div>';
    }

    function renderClientes() {
        var container = $('#crm-v3-lista-clientes');
        if (!container) return;

        var termo = state.buscaCliente.toLowerCase();
        var filtrados = state.clientes.filter(function (c) {
            var classif = String(c.classificacao_cliente || c.classificacao || '').toLowerCase();
            var isGeladeira = classif === 'geladeira';
            // Pill "arquivo" mostra somente Geladeira.
            if (state.filtroPill === 'arquivo') {
                if (!isGeladeira) return false;
            } else {
                // Demais pills (todos/atrasado/sem-atividade) escondem Geladeira.
                if (isGeladeira) return false;
                if (state.filtroPill !== 'todos' && c.status !== state.filtroPill) return false;
            }
            if (state.filtroExecutivo && c.responsavel !== state.filtroExecutivo) return false;
            if (state.filtroTipo && String(c.tipo || c.categoria || '').toLowerCase() !== state.filtroTipo) return false;
            if (state.filtroPerfil && c.perfil !== state.filtroPerfil) return false;
            if (termo && c.nome.toLowerCase().indexOf(termo) === -1) return false;
            return true;
        });

        var countEl = $('.crm-v3-col-clientes .crm-v3-count');
        if (countEl) {
            var total = state.clientes.length;
            countEl.textContent = filtrados.length === total ? String(total) : filtrados.length + ' de ' + total;
        }

        updatePillCounts();
        var semContato = $('#crm-v3-sem-contato-count');
        if (semContato) semContato.textContent = state.clientes.filter(function (c) { return !c.qtd_contatos; }).length;

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-v3-contatos-empty p-3 text-sm text-base-content/60">Nenhum cliente encontrado.</div>';
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
            var classificacao = c.classificacao_cliente || c.classificacao || '';
            var classifSlug = classificacao.replace(/ç/g, 'c').replace(/ã/g, 'a');
            var isAgencia = !!c.is_agencia;
            var clientesFinaisCount = Number(c.clientes_finais_count || 0);
            var agenciaNome = c.agencia_nome || '';

            var chips = [];
            if (classificacao) {
                chips.push(
                    '<span class="crm-v3-chip crm-v3-chip-classificacao--' + escapeHtml(classifSlug) + '" title="Classificação">' +
                    escapeHtml(classificacao) +
                    '</span>'
                );
            }
            if (isAgencia && clientesFinaisCount > 0) {
                chips.push(
                    '<span class="crm-v3-chip crm-v3-chip-agencia" title="Agência com ' + clientesFinaisCount + ' cliente(s) final(is)">' +
                    '<i class="fa-solid fa-sitemap" aria-hidden="true"></i>' +
                    clientesFinaisCount +
                    '</span>'
                );
            } else if (agenciaNome) {
                chips.push(
                    '<span class="crm-v3-chip crm-v3-chip-filho" title="Vinculado à agência ' + escapeHtml(agenciaNome) + '">' +
                    '<i class="fa-solid fa-code-branch" aria-hidden="true"></i>' +
                    escapeHtml(agenciaNome) +
                    '</span>'
                );
            }

            return (
                '<div class="crm-v3-cliente' + (ativo ? ' crm-v3-cliente-ativo' : '') + '"' +
                ' role="listitem" tabindex="0"' +
                ' data-cliente-id="' + escapeHtml(c.id) + '"' +
                ' data-status="' + escapeHtml(c.status) + '"' +
                ' data-classificacao="' + escapeHtml(classificacao) + '"' +
                ' aria-current="' + (ativo ? 'page' : 'false') + '">' +
                avatarHtml(c.nome, 'w-7 h-7') +
                '<div class="crm-v3-cliente-info min-w-0 flex-1">' +
                '<div class="crm-v3-cliente-headline">' +
                '<div class="crm-v3-cliente-nome" title="' + escapeHtml(c.nome) + '">' + escapeHtml(c.nome) + '</div>' +
                '</div>' +
                '<div class="crm-v3-cliente-sub" title="' + escapeHtml(c.sub) + '">' + escapeHtml(c.sub) + '</div>' +
                (chips.length ? '<div class="crm-v3-cliente-meta">' + chips.join('') + '</div>' : '') +
                '</div>' +
                '<div class="crm-v3-cliente-right shrink-0">' +
                situacaoHtml(c) +
                '</div></div>'
            );
        }).join('');

        $$('.crm-v3-cliente', container).forEach(function (card) {
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

    function updateTabCounts() {
        var counts = {
            notas: (state.notas || []).length,
            objetivos: (state.objetivos || []).length,
            atividades: (state.atividades || []).length,
            'ativ-todas': (state.atividades || []).length,
            'ativ-pendentes': (state.atividades || []).filter(function (a) { return a.status !== 'concluida'; }).length,
            'ativ-concluidas': (state.atividades || []).filter(function (a) { return a.status === 'concluida'; }).length,
        };
        $$('.crm-v3-tab-count').forEach(function (el) {
            var key = el.getAttribute('data-tab-count');
            if (key && counts[key] !== undefined) el.textContent = counts[key];
        });
    }

    function updatePillCounts() {
        // Aplica os mesmos filtros de executivo/tipo/perfil da lista principal
        // para que as contagens reflitam apenas o escopo atual do usuário.
        // Geladeira sempre fica separada em "Arquivo".
        var base = state.clientes.filter(function (c) {
            if (state.filtroExecutivo && c.responsavel !== state.filtroExecutivo) return false;
            if (state.filtroTipo && String(c.tipo || c.categoria || '').toLowerCase() !== state.filtroTipo) return false;
            if (state.filtroPerfil && c.perfil !== state.filtroPerfil) return false;
            return true;
        });
        var counts = { todos: 0, atrasado: 0, 'sem-atividade': 0, arquivo: 0 };
        base.forEach(function (c) {
            var isGeladeira = String(c.classificacao_cliente || c.classificacao || '').toLowerCase() === 'geladeira';
            if (isGeladeira) {
                counts.arquivo++;
                return; // Geladeira não conta nas outras pills
            }
            counts.todos++;
            if (c.status === 'atrasado') counts.atrasado++;
            if (c.status === 'sem-atividade') counts['sem-atividade']++;
        });
        $$('.crm-v3-pill').forEach(function (pill) {
            var f = pill.getAttribute('data-filter');
            var span = pill.querySelector('.crm-v3-pill-count');
            if (span && counts[f] !== undefined) span.textContent = counts[f];
        });
    }

    function updatePagination(totalPaginas) {
        var label = $('#crm-v3-page-label');
        var prev = $('#crm-v3-page-prev');
        var next = $('#crm-v3-page-next');
        totalPaginas = totalPaginas || 1;
        if (label) label.textContent = state.paginaCliente + '/' + totalPaginas;
        if (prev) prev.disabled = state.paginaCliente <= 1;
        if (next) next.disabled = state.paginaCliente >= totalPaginas;
    }

    /* ------------------------------------------------------------------
     * Métricas do cliente (derivadas do estado + fallback do backend).
     * - contatos: state.contatos (o que aparece na coluna)
     * - oportunidades: cotações em aberto (rascunho/enviada/em acomp.)
     * - faturamento: soma de valor_total das cotações aprovadas
     * - valor_pis: soma de valor_total das cotações em aberto (pipeline)
     * - tarefas_abertas: atividades com status != concluida
     * - ultimo_contato: max(data das atividades concluídas) ou fallback
     * ------------------------------------------------------------------ */
    function _cotValor(c) {
        var v = c.valor_total;
        if (v == null || v === '') {
            // Parse do "R$ 12.500,00" quando valor_total não vier do backend.
            var raw = String(c.valor || '').replace(/[^\d,.-]/g, '').replace(/\./g, '').replace(',', '.');
            v = parseFloat(raw);
        }
        return isFinite(v) ? Number(v) : 0;
    }

    function formatBRL(v) {
        if (!isFinite(v)) v = 0;
        try {
            return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        } catch (e) {
            return 'R$ ' + v.toFixed(2).replace('.', ',');
        }
    }

    function computeMetricas(cliente) {
        var fallback = (cliente && cliente.metrics) || {};
        var contatos = state.contatos && state.contatos.length
            ? state.contatos.length
            : (fallback.contatos != null ? fallback.contatos : (cliente && cliente.qtd_contatos) || 0);

        var cotAbertas = (state.cotacoes || []).filter(cotacaoEstaAberta);
        var cotAprovadas = (state.cotacoes || []).filter(function (c) {
            return String(c.status || '').toLowerCase() === 'aprovada';
        });
        var oportunidades = cotAbertas.length || (fallback.oportunidades != null ? fallback.oportunidades : 0);
        var faturamento = cotAprovadas.reduce(function (s, c) { return s + _cotValor(c); }, 0);
        var pipeline = cotAbertas.reduce(function (s, c) { return s + _cotValor(c); }, 0);
        var tarefas = (state.atividades || []).filter(function (a) {
            return a.status !== 'concluida';
        }).length;
        if (!state.atividades || !state.atividades.length) {
            tarefas = fallback.tarefas_abertas != null ? fallback.tarefas_abertas : tarefas;
        }

        // Último contato = max data entre atividades concluídas.
        var ultimo = fallback.ultimo_contato || '—';
        var maxData = (state.atividades || [])
            .filter(function (a) { return a.status === 'concluida' && a.data; })
            .map(function (a) { return a.data; })
            .sort()
            .pop();
        if (maxData) {
            var d = new Date(maxData + 'T00:00:00');
            if (!isNaN(d)) {
                var hoje = new Date(); hoje.setHours(0, 0, 0, 0);
                var diff = Math.round((hoje - d) / 86400000);
                ultimo = diff === 0 ? 'Hoje' : diff === 1 ? 'Ontem' : diff + 'd atrás';
            }
        }

        return {
            contatos: contatos,
            oportunidades: oportunidades,
            faturamento: faturamento,
            faturamento_label: faturamento > 0 ? formatBRL(faturamento) : (fallback.faturamento || 'R$ 0,00'),
            valor_pis: pipeline,
            valor_pis_label: pipeline > 0 ? formatBRL(pipeline) : (fallback.valor_pis || 'R$ 0,00'),
            tarefas_abertas: tarefas,
            ultimo_contato: ultimo
        };
    }

    function updateDetailPanel(cliente) {
        if (!cliente) return;
        var title = $('.crm-v3-detail-title');
        if (title) {
            title.textContent = cliente.nome;
            title.title = cliente.nome;
        }

        var av = $('#crm-v3-detail-avatar');
        if (av) av.textContent = cliente.avatar || avatarIniciais(cliente.nome);
        var star = $('.crm-v3-star');
        if (star) {
            star.classList.toggle('active', !!cliente.favorito);
            star.setAttribute('aria-pressed', cliente.favorito ? 'true' : 'false');
            star.setAttribute('aria-label', cliente.favorito ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
        }

        var metaResp = $('#crm-v3-meta-responsavel');
        if (metaResp) metaResp.textContent = cliente.responsavel || '—';

        var metaCat = $('#crm-v3-meta-categoria');
        if (metaCat) metaCat.textContent = cliente.tipo || cliente.categoria || '—';

        var metaPri = $('#crm-v3-meta-prioridade');
        if (metaPri) {
            metaPri.textContent = 'Prioridade: ' + (cliente.prioridade || '—');
            metaPri.className = 'badge badge-sm ' + (cliente.prioridade === 'Alta' ? 'badge-error' : cliente.prioridade === 'Média' ? 'badge-warning' : 'badge-ghost');
        }

        var infoCategoria = $('#crm-v3-info-categoria');
        var infoClassificacao = $('#crm-v3-info-classificacao');
        var infoTipo = $('#crm-v3-info-tipo');
        var infoPrioridade = $('#crm-v3-info-prioridade');
        var infoCnpj = $('#crm-v3-info-cnpj');
        var infoFonte = $('#crm-v3-info-fonte');
        var infoCriado = $('#crm-v3-info-criado');
        var infoSegmento = $('#crm-v3-info-segmento');
        var infoCidade = $('#crm-v3-info-cidade');
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
        var responsavelNome = $('#crm-v3-responsavel-nome');
        var responsavelAvatar = $('#crm-v3-responsavel-avatar');
        var responsavelEmail = $('#crm-v3-responsavel-email');
        if (responsavelNome) responsavelNome.textContent = cliente.responsavel || '—';
        if (responsavelAvatar) responsavelAvatar.textContent = avatarIniciais(cliente.responsavel);
        if (responsavelEmail) {
            responsavelEmail.textContent = cliente.responsavel
                ? cliente.responsavel.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '.') + '@centralcomm.media'
                : '—';
        }
        updateFollowButton(cliente);

        // Métricas derivadas do estado atual do cliente (fonte da verdade
        // é o que já foi carregado das APIs). Isso garante que o número
        // mostrado bate com o que o usuário vê nas outras colunas.
        var m = computeMetricas(cliente);
        var el;
        el = $('#crm-metric-contatos');
        if (el) { el.textContent = m.contatos; el.title = m.contatos + ' contato(s) cadastrado(s)'; }
        el = $('#crm-metric-oportunidades');
        if (el) { el.textContent = m.oportunidades; el.title = 'Cotações em aberto (rascunho, enviada, em acompanhamento)'; }
        el = $('#crm-metric-faturamento');
        if (el) { el.textContent = m.faturamento_label; el.title = 'Soma das cotações aprovadas para este cliente'; }
        el = $('#crm-metric-pis');
        if (el) { el.textContent = m.valor_pis_label; el.title = 'Soma das cotações em aberto (pipeline)'; }
        el = $('#crm-metric-tarefas');
        if (el) { el.textContent = m.tarefas_abertas; el.title = 'Atividades pendentes (não concluídas)'; }
        el = $('#crm-metric-ultimo');
        if (el) { el.textContent = m.ultimo_contato; el.title = 'Data da atividade concluída mais recente'; }

        updateStatusComercial(cliente);
        updateVinculos(cliente);
    }

    function updateStatusComercial(cliente) {
        var badge = $('#crm-v3-status-badge');
        var hint = $('#crm-v3-status-hint');
        var classificacao = cliente.classificacao_cliente || cliente.classificacao || '';
        if (badge) {
            badge.textContent = classificacao || '—';
            badge.setAttribute('data-classificacao', classificacao || '');
        }
        if (hint) {
            var mapaHint = {
                'Prospecção': 'Foco em qualificação e cadência de touchpoints.',
                'Prospeccao': 'Foco em qualificação e cadência de touchpoints.',
                'Ativo': 'Manter relacionamento e detectar novas oportunidades.',
                'Geladeira': 'Cliente em pausa; retomar quando fizer sentido comercial.'
            };
            hint.textContent = mapaHint[classificacao] || '';
        }
    }

    function updateVinculos(cliente) {
        var section = $('#crm-v3-sidebar-vinculos');
        var titulo = $('#crm-v3-vinculos-titulo');
        var badge = $('#crm-v3-vinculos-count');
        var list = $('#crm-v3-vinculos-list');
        if (!section || !list) return;

        var filhos = Array.isArray(cliente.clientes_finais) ? cliente.clientes_finais : [];
        var filhosIds = Array.isArray(cliente.clientes_finais_ids) ? cliente.clientes_finais_ids : [];
        // Se veio só array de ids, resolver pelo state.clientes
        if (!filhos.length && filhosIds.length && Array.isArray(state.clientes)) {
            filhos = filhosIds.map(function (id) {
                return state.clientes.find(function (c) { return c.id === id; });
            }).filter(Boolean);
        }

        var isAgencia = !!cliente.is_agencia;
        var agenciaId = cliente.agencia_id;
        var agenciaNome = cliente.agencia_nome;
        // Resolver por id se não veio nome
        if (agenciaId && !agenciaNome && Array.isArray(state.clientes)) {
            var pai = state.clientes.find(function (c) { return c.id === agenciaId; });
            if (pai) agenciaNome = pai.nome;
        }

        if (isAgencia && filhos.length) {
            section.hidden = false;
            if (titulo) titulo.textContent = 'Clientes vinculados';
            if (badge) badge.textContent = String(filhos.length);
            list.innerHTML = filhos.map(function (f) {
                return (
                    '<button type="button" class="crm-v3-vinculo-item" data-cliente-id="' + escapeHtml(f.id) + '">' +
                    '<i class="fa-solid fa-code-branch" aria-hidden="true"></i>' +
                    '<span class="crm-v3-vinculo-item-nome" title="' + escapeHtml(f.nome) + '">' + escapeHtml(f.nome) + '</span>' +
                    (f.classificacao_cliente ? '<span class="crm-v3-vinculo-item-classif">' + escapeHtml(f.classificacao_cliente) + '</span>' : '') +
                    '</button>'
                );
            }).join('');
            $$('.crm-v3-vinculo-item', list).forEach(function (btn) {
                btn.addEventListener('click', function () {
                    selectCliente(btn.getAttribute('data-cliente-id'));
                });
            });
        } else if (!isAgencia && agenciaNome) {
            section.hidden = false;
            if (titulo) titulo.textContent = 'Agência principal';
            if (badge) badge.textContent = '';
            list.innerHTML = (
                '<button type="button" class="crm-v3-vinculo-item"' +
                (agenciaId ? ' data-cliente-id="' + escapeHtml(agenciaId) + '"' : '') + '>' +
                '<i class="fa-solid fa-sitemap" aria-hidden="true"></i>' +
                '<span class="crm-v3-vinculo-item-nome" title="' + escapeHtml(agenciaNome) + '">' + escapeHtml(agenciaNome) + '</span>' +
                '</button>'
            );
            var btn = list.querySelector('.crm-v3-vinculo-item');
            if (btn && agenciaId) {
                btn.addEventListener('click', function () {
                    selectCliente(agenciaId);
                });
            }
        } else {
            section.hidden = true;
            list.innerHTML = '';
            if (badge) badge.textContent = '';
        }
    }

    // updateFollowButton removido: botão Seguir/Deixar de seguir foi retirado da UI
    // do CRM v3. O campo `seguindo` continua no modelo para preservar filtros
    // existentes (pill "Seguindo") e paridade com o CRM legado.
    function updateFollowButton() { /* noop */ }

    function updateSidebarContato(contato) {
        var nomeEl = $('#crm-v3-sidebar-contato-nome');
        var cargoEl = $('#crm-v3-sidebar-contato-cargo');
        var setorEl = $('#crm-v3-sidebar-contato-setor');
        var emailEl = $('#crm-v3-sidebar-contato-email');
        var telEl = $('#crm-v3-sidebar-contato-telefone');
        var avatarEl = $('#crm-v3-sidebar-contato-avatar');
        var badgeEl = $('#crm-v3-sidebar-contato-badge');
        var hintEl = $('#crm-v3-contato-principal-hint');
        var detalhesEl = $('#crm-v3-sidebar-contato-detalhes');
        var mailto = $('#crm-v3-mailto-link');
        var whats = $('#crm-v3-whatsapp-link');
        var copyBtn = $('#crm-v3-copy-email');

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
        var container = $('#crm-v3-lista-contatos');
        var countEl = $('#crm-v3-contatos-count');
        if (!container) return;

        var termo = state.buscaContato.toLowerCase().trim();
        var filtrados = state.contatos.filter(function (c) {
            if (!termo) return true;
            return [c.nome, c.cargo, c.email, c.telefone, c.telefone_secundario]
                .some(function (v) { return String(v || '').toLowerCase().indexOf(termo) !== -1; });
        });

        if (countEl) countEl.textContent = filtrados.length;

        if (!state.clienteId) {
            container.innerHTML = '<div class="crm-v3-contatos-empty p-3 text-sm">Selecione um cliente.</div>';
            updateSidebarContato(null);
            return;
        }

        if (!state.contatos.length) {
            container.innerHTML =
                '<div class="crm-v3-contatos-empty p-3 text-sm text-center">' +
                'Nenhum contato cadastrado.<br>' +
                '<button type="button" class="btn btn-sm btn-primary mt-2" id="crm-v3-empty-add-contato">+ Adicionar contato</button>' +
                '</div>';
            var emptyBtn = $('#crm-v3-empty-add-contato');
            if (emptyBtn) emptyBtn.addEventListener('click', openContatoModal);
            updateSidebarContato(null);
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-v3-contatos-empty p-3 text-sm">Nenhum contato encontrado.</div>';
            return;
        }

        container.innerHTML = filtrados.map(function (c) {
            var ativo = c.id === state.contatoId;
            var nomeExibido = (c.nome && String(c.nome).trim()) || (c.email ? String(c.email).split('@')[0] : 'Contato sem nome');
            var subLinha = [c.cargo, c.setor].filter(Boolean).join(' · ');
            return (
                '<div class="crm-v3-contato-card' + (ativo ? ' crm-v3-contato-card-active is-expanded' : '') + '" role="listitem" tabindex="0" data-contato-id="' + escapeHtml(c.id) + '">' +
                '<div class="crm-v3-contato-main">' +
                avatarHtml(nomeExibido, 'w-8 h-8') +
                '<div class="crm-v3-contato-info min-w-0">' +
                '<div class="crm-v3-contato-nome-row">' +
                '<span class="crm-v3-contato-nome" title="' + escapeHtml(nomeExibido) + '">' + escapeHtml(nomeExibido) + '</span>' +
                (c.principal ? '<span class="crm-v3-contato-badge crm-v3-contato-badge-principal" title="Contato principal"><i class="fa-solid fa-star" aria-hidden="true"></i></span>' : '') +
                (c.conversas ? '<span class="crm-v3-contato-badge crm-v3-contato-badge-count" title="' + c.conversas + ' conversa(s)">' + c.conversas + '</span>' : '') +
                '</div>' +
                (subLinha ? '<div class="crm-v3-contato-cargo">' + escapeHtml(subLinha) + '</div>' : '') +
                '</div>' +
                '<div class="crm-v3-contato-actions">' +
                '<button type="button" class="crm-v3-contato-edit crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" aria-label="Editar contato" data-contato-id="' + escapeHtml(c.id) + '"><i class="fa-solid fa-pen" aria-hidden="true"></i></button>' +
                '<button type="button" class="crm-v3-contato-toggle crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" aria-expanded="' + (ativo ? 'true' : 'false') + '" aria-label="Expandir contato"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>' +
                '</div></div>' +
                '<div class="crm-v3-contato-details">' +
                (c.email ? (
                    '<div class="crm-v3-contato-email-row"><i class="fa-regular fa-envelope crm-v3-contato-row-icon" aria-hidden="true"></i><span class="crm-v3-contato-row-text" title="' + escapeHtml(c.email) + '">' + escapeHtml(c.email) + '</span>' +
                    '<button type="button" class="crm-v3-contato-copy crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" data-copy="' + escapeHtml(c.email) + '" aria-label="Copiar e-mail"><i class="fa-regular fa-copy"></i></button></div>'
                ) : '') +
                (c.telefone ? '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row"><i class="fa-brands fa-whatsapp" aria-hidden="true"></i><span>' + escapeHtml(c.telefone) + '</span></button>' : '') +
                (c.telefone_secundario ? '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row"><i class="fa-brands fa-whatsapp" aria-hidden="true"></i><span>' + escapeHtml(c.telefone_secundario) + '</span></button>' : '') +
                '</div></div>'
            );
        }).join('');

        bindContatoEvents(container);
        var contato = state.contatos.find(function (c) { return c.id === state.contatoId; });
        updateSidebarContato(contato);
    }

    function bindContatoEvents(container) {
        $$('.crm-v3-contato-card', container).forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.closest('.crm-v3-contato-toggle, .crm-v3-contato-edit, .crm-v3-contato-copy, .crm-v3-contato-phone-row, .crm-v3-contato-whats-row')) return;
                selectContato(card.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-v3-contato-toggle', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var card = btn.closest('.crm-v3-contato-card');
                var expanded = card.classList.toggle('is-expanded');
                btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            });
        });

        $$('.crm-v3-contato-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openContatoModal(btn.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-v3-contato-copy', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var text = btn.getAttribute('data-copy');
                if (!text) return;
                copiarTexto(text)
                    .then(function () { showToast('E-mail copiado'); })
                    .catch(function (err) { showToast(err.message, true); });
            });
        });

        $$('.crm-v3-contato-whats-row', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var tel = btn.querySelector('span').textContent;
                var digits = normalizarTelefone(tel);
                if (digits) window.open('https://wa.me/' + digits, '_blank', 'noopener');
            });
        });
    }

    function ativIconClass(tipo) {
        if (tipo === 'ligacao' || tipo === 'phone') return 'crm-v3-ativ-icon-phone';
        if (tipo === 'reuniao' || tipo === 'meeting') return 'crm-v3-ativ-icon-meeting';
        if (tipo === 'doc') return 'crm-v3-ativ-icon-doc';
        return 'crm-v3-ativ-icon-note';
    }

    function ativIconHtml(tipo) {
        var icons = {
            ligacao: 'fa-phone', phone: 'fa-phone',
            reuniao: 'fa-users', meeting: 'fa-users',
            doc: 'fa-file-lines', note: 'fa-note-sticky'
        };
        var ic = icons[tipo] || 'fa-circle';
        var solid = ic === 'fa-file-lines' ? 'fa-regular' : 'fa-solid';
        return '<span class="crm-v3-ativ-icon ' + ativIconClass(tipo) + '" aria-hidden="true"><i class="' + solid + ' ' + ic + '"></i></span>';
    }

    function prioridadeBadge(p) {
        var t = (p || '').toLowerCase();
        var type = t === 'alta' ? 'alta' : t === 'média' || t === 'media' ? 'media' : 'baixa';
        return '<span class="' + badgeDaisy(type) + '">' + escapeHtml(p) + '</span>';
    }

    // Buckets de agrupamento por data. Os buckets seguem a ordem lógica:
    // Atrasadas > Hoje > Amanhã > Esta semana > Próximas > Sem data > Concluídas.
    var ATIV_BUCKETS = ['atrasada', 'hoje', 'amanha', 'semana', 'proxima', 'sem-data', 'concluida'];
    var ATIV_BUCKET_LABEL = {
        atrasada: 'Atrasadas',
        hoje: 'Hoje',
        amanha: 'Amanhã',
        semana: 'Esta semana',
        proxima: 'Próximas',
        'sem-data': 'Sem data',
        concluida: 'Concluídas'
    };

    /** Retorna a chave de bucket de uma atividade. Espera `a.data` em ISO. */
    function bucketAtividade(a) {
        if (a.status === 'concluida') return 'concluida';
        if (!a.data) return 'sem-data';
        var hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        var dt = new Date(a.data + 'T00:00:00');
        if (isNaN(dt.getTime())) return 'sem-data';
        dt.setHours(0, 0, 0, 0);
        var diff = Math.round((dt - hoje) / 86400000);
        if (diff < 0) return 'atrasada';
        if (diff === 0) return 'hoje';
        if (diff === 1) return 'amanha';
        if (diff <= 7) return 'semana';
        return 'proxima';
    }

    function formatarDataAtividade(a) {
        if (!a.data) return '';
        var dt = new Date(a.data + 'T00:00:00');
        if (isNaN(dt.getTime())) return '';
        var meses = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
        return dt.getDate().toString().padStart(2, '0') + ' ' + meses[dt.getMonth()];
    }

    function renderAtividadeItem(a) {
        var concluida = a.status === 'concluida';
        var responsavel = a.responsavel || '';
        var dataStr = formatarDataAtividade(a);
        var horaStr = a.hora || '';
        var quando = [dataStr, horaStr].filter(Boolean).join(' · ');
        return (
            '<div class="crm-v3-ativ' + (concluida ? ' crm-v3-ativ-concluida' : '') + '" role="listitem" data-status="' + escapeHtml(a.status) + '" data-atividade-id="' + escapeHtml(a.id) + '"' + (a._pending ? ' data-pending="true"' : '') + '>' +
                '<button type="button" class="crm-v3-ativ-check" data-ativ-action="toggle" aria-label="' + (concluida ? 'Reabrir' : 'Marcar como feita') + ': ' + escapeHtml(a.titulo) + '" title="' + (concluida ? 'Reabrir' : 'Marcar como feita') + '">' +
                    '<i class="' + (concluida ? 'fa-solid fa-circle-check' : 'fa-regular fa-circle') + '" aria-hidden="true"></i>' +
                '</button>' +
                ativIconHtml(a.tipo) +
                '<div class="crm-v3-ativ-content">' +
                    '<div class="crm-v3-ativ-titulo" data-editable="titulo" data-atividade-id="' + escapeHtml(a.id) + '">' + escapeHtml(a.titulo) + '</div>' +
                    (a.descricao ? '<div class="crm-v3-ativ-desc" data-editable="descricao" data-atividade-id="' + escapeHtml(a.id) + '">' + escapeHtml(a.descricao) + '</div>' : '') +
                '</div>' +
                (quando ? '<span class="crm-v3-ativ-when" title="' + escapeHtml(quando) + '">' + escapeHtml(quando) + '</span>' : '') +
                (responsavel ? '<div class="crm-v3-avatar-mini crm-v3-ativ-owner" title="' + escapeHtml(responsavel) + '">' + escapeHtml(avatarIniciais(responsavel)) + '</div>' : '') +
                '<div class="crm-v3-ativ-actions">' +
                    '<button type="button" class="crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" data-ativ-action="editar" aria-label="Editar" title="Editar"><i class="fa-solid fa-pen" aria-hidden="true"></i></button>' +
                    '<button type="button" class="crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost crm-v3-icon-btn-danger" data-ativ-action="excluir" aria-label="Excluir" title="Excluir"><i class="fa-solid fa-trash" aria-hidden="true"></i></button>' +
                '</div>' +
            '</div>'
        );
    }

    function renderAtividades() {
        var container = $('#crm-v3-ativ-list');
        if (!container) return;

        // Filtro apenas pela aba (Todas / Pendentes / Concluídas).
        // Busca, responsável e tipo foram removidos por decisão de UX:
        // a coluna mostra tudo agrupado por data.
        var filtrados = state.atividades.filter(function (a) {
            if (state.filtroAtivTab === 'pendentes' && a.status === 'concluida') return false;
            if (state.filtroAtivTab === 'concluidas' && a.status !== 'concluida') return false;
            return true;
        });

        if (!state.clienteId) {
            container.innerHTML = '<div class="crm-v3-ativ-empty">Selecione um cliente.</div>';
            renderSidebarAtividades();
            renderSugestao();
            updateTabCounts();
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="crm-v3-ativ-empty">Nenhuma atividade nesta aba.</div>';
            renderSidebarAtividades();
            renderSugestao();
            updateTabCounts();
            return;
        }

        // Agrupa por bucket e ordena: atrasadas/pendentes por data ascendente,
        // concluídas por data descendente (mais recente primeiro).
        var groups = {};
        filtrados.forEach(function (a) {
            var key = bucketAtividade(a);
            (groups[key] = groups[key] || []).push(a);
        });
        Object.keys(groups).forEach(function (k) {
            groups[k].sort(function (a, b) {
                var da = a.data || '';
                var db = b.data || '';
                return k === 'concluida' ? (db.localeCompare(da)) : (da.localeCompare(db));
            });
        });

        var html = '';
        ATIV_BUCKETS.forEach(function (key) {
            var items = groups[key];
            if (!items || !items.length) return;
            html += '<div class="crm-v3-date-group" data-bucket="' + key + '">' +
                '<div class="crm-v3-date-label">' +
                    '<span>' + escapeHtml(ATIV_BUCKET_LABEL[key]) + '</span>' +
                    '<span class="crm-v3-date-count">' + items.length + '</span>' +
                '</div>' +
                items.map(renderAtividadeItem).join('') +
            '</div>';
        });

        container.innerHTML = html;
        bindAtividadeEvents(container);
        renderSidebarAtividades();
        renderSugestao();
        updateTabCounts();
    }

    function renderSidebarAtividades() {
        var container = $('#crm-v3-sidebar-atividades-list');
        if (!container) return;
        var items = state.atividades.slice(0, 6);
        if (!items.length) {
            container.innerHTML = '<p class="text-sm text-base-content/60">Nenhuma atividade registrada.</p>';
            return;
        }
        container.innerHTML = items.map(function (a) {
            return '<div class="crm-v3-mini-ativ">' +
                ativIconHtml(a.tipo) +
                '<div class="crm-v3-mini-ativ-text">' + escapeHtml(a.titulo) + '</div>' +
                '<span class="crm-v3-mini-ativ-time">' + escapeHtml((a.data_label || '') + (a.hora ? ' · ' + a.hora : '')) + '</span>' +
                '</div>';
        }).join('');
    }

    function renderSugestao() {
        var el = $('#crm-v3-sugestao-texto');
        if (!el) return;
        var pendentes = state.atividades.filter(function (a) { return a.status !== 'concluida'; });
        el.textContent = pendentes.length
            ? 'Há ' + pendentes.length + ' atividade(s) pendente(s). Priorize o próximo contato e mantenha o cliente atualizado.'
            : 'Sem atividades pendentes. Agende um contato para gerar novas oportunidades.';
    }

    function bindAtividadeEvents(container) {
        // Edição inline (título/descrição via contenteditable) — clicar edita.
        bindAtividadeInlineEdit(container);

        // Uma delegação de eventos para toggle/editar/excluir cobre todas as
        // ações; simplifica manutenção quando renderizamos por grupos de data.
        container.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-ativ-action]');
            if (!btn || !container.contains(btn)) return;
            e.stopPropagation();
            var row = btn.closest('.crm-v3-ativ');
            if (!row) return;
            var id = row.getAttribute('data-atividade-id');
            var action = btn.getAttribute('data-ativ-action');
            var a = state.atividades.find(function (x) { return x.id === id; });
            if (!a) return;
            if (action === 'toggle') {
                var novoStatus = a.status === 'concluida' ? 'pendente' : 'concluida';
                api('/atividades/' + encodeURIComponent(id), { method: 'PATCH', body: { status: novoStatus } })
                    .then(function () {
                        a.status = novoStatus;
                        renderAtividades();
                        showToast(novoStatus === 'concluida' ? 'Atividade concluída' : 'Atividade reaberta');
                    })
                    .catch(function (err) { showToast(err.message, true); });
            } else if (action === 'editar') {
                openAtividadeModal(a);
            } else if (action === 'excluir') {
                if (!window.confirm('Excluir esta atividade?')) return;
                api('/atividades/' + encodeURIComponent(id), { method: 'DELETE' })
                    .then(function () { loadAtividades(state.clienteId); showToast('Atividade excluída'); })
                    .catch(function (err) { showToast(err.message, true); });
            }
        });
    }

    // Edição inline: transforma título/descrição em contenteditable ao clicar.
    // Enter salva, Escape cancela, blur salva se houve alteração.
    function bindAtividadeInlineEdit(container) {
        ['titulo', 'desc'].forEach(function (campo) {
            var sel = '.crm-v3-ativ-' + campo;
            $$(sel, container).forEach(function (el) {
                var originalText = el.textContent;
                el.setAttribute('contenteditable', 'true');
                el.setAttribute('spellcheck', 'false');
                el.setAttribute('data-original', originalText);
                el.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        el.blur();
                    } else if (e.key === 'Escape') {
                        el.textContent = el.getAttribute('data-original') || '';
                        el.blur();
                    }
                });
                el.addEventListener('blur', function () {
                    var row = el.closest('.crm-v3-ativ');
                    if (!row) return;
                    var id = row.getAttribute('data-atividade-id');
                    var novo = el.textContent.trim();
                    var atual = (el.getAttribute('data-original') || '').trim();
                    if (novo === atual) return;
                    if (campo === 'titulo' && !novo) {
                        el.textContent = atual;
                        return;
                    }
                    var body = {};
                    body[campo === 'titulo' ? 'titulo' : 'descricao'] = novo;
                    api('/atividades/' + encodeURIComponent(id), { method: 'PATCH', body: body })
                        .then(function () {
                            el.setAttribute('data-original', novo);
                            var a = state.atividades.find(function (x) { return x.id === id; });
                            if (a) { a[campo === 'titulo' ? 'titulo' : 'descricao'] = novo; }
                            showToast('Atividade atualizada');
                        })
                        .catch(function (err) {
                            showToast(err.message, true);
                            el.textContent = atual;
                        });
                });
            });
        });
    }

    // Composer inline: cria atividade rapidamente e insere no state sem refresh.
    function bindComposerAtividade() {
        var form = $('#crm-v3-ativ-composer');
        if (!form) return;
        var titulo = $('#crm-v3-composer-titulo');
        var dataInput = $('#crm-v3-composer-data');
        var horaInput = $('#crm-v3-composer-hora');
        var tipoBtn = $('#crm-v3-composer-tipo');

        // Ciclo de tipos de atividade
        var tipos = [
            { id: 'atividade', icon: 'fa-regular fa-circle-check', label: 'Atividade' },
            { id: 'ligacao',   icon: 'fa-solid fa-phone',          label: 'Ligação' },
            { id: 'reuniao',   icon: 'fa-solid fa-users',          label: 'Reunião' },
            { id: 'doc',       icon: 'fa-regular fa-file-lines',   label: 'Documento' },
            { id: 'planejamento', icon: 'fa-solid fa-diagram-project', label: 'Planejamento' }
        ];
        function setTipoIdx(idx) {
            var t = tipos[idx % tipos.length];
            tipoBtn.setAttribute('data-tipo', t.id);
            tipoBtn.setAttribute('data-tipo-idx', String(idx % tipos.length));
            tipoBtn.setAttribute('title', 'Tipo: ' + t.label + ' (clique para trocar)');
            tipoBtn.setAttribute('aria-label', 'Tipo: ' + t.label);
            tipoBtn.innerHTML = '<i class="' + t.icon + '" aria-hidden="true"></i>';
        }
        setTipoIdx(0);
        tipoBtn.addEventListener('click', function () {
            var next = (parseInt(tipoBtn.getAttribute('data-tipo-idx') || '0', 10) + 1) % tipos.length;
            setTipoIdx(next);
            titulo && titulo.focus();
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!state.clienteId) { showToast('Selecione um cliente', true); return; }
            var tituloVal = (titulo.value || '').trim();
            if (!tituloVal) { titulo.focus(); return; }

            var hoje = new Date().toISOString().slice(0, 10);
            // Responsável default = executivo de vendas do cliente (iniciais).
            // Cai para o usuário logado ou "LS" se não houver contexto.
            var responsavelNome = (state.cliente && state.cliente.responsavel) || '';
            var responsavelIniciais = avatarIniciais(responsavelNome) || 'LS';
            var body = {
                titulo: tituloVal,
                descricao: '',
                tipo: tipoBtn.getAttribute('data-tipo') || 'atividade',
                prioridade: 'Média',
                data: dataInput.value || hoje,
                data_label: dataInput.value && dataInput.value !== hoje ? 'Agendada' : 'Hoje',
                hora: horaInput.value || '',
                responsavel: responsavelIniciais,
                responsavel_nome: responsavelNome || undefined,
                status: 'pendente'
            };

            // Otimista: cria placeholder e re-renderiza imediatamente
            var tempId = 'tmp-' + Date.now();
            var placeholder = Object.assign({ id: tempId, _pending: true }, body);
            state.atividades.unshift(placeholder);
            renderAtividades();
            titulo.value = '';
            titulo.focus();

            api('/clientes/' + encodeURIComponent(state.clienteId) + '/atividades', {
                method: 'POST', body: body
            }).then(function (resp) {
                var real = resp.atividade || resp.data || resp;
                var idx = state.atividades.findIndex(function (a) { return a.id === tempId; });
                if (idx !== -1 && real && real.id) {
                    state.atividades[idx] = real;
                } else {
                    // fallback: recarrega
                    return loadAtividades(state.clienteId);
                }
                renderAtividades();
                showToast('Atividade adicionada');
            }).catch(function (err) {
                var idx = state.atividades.findIndex(function (a) { return a.id === tempId; });
                if (idx !== -1) state.atividades.splice(idx, 1);
                renderAtividades();
                showToast(err.message || 'Falha ao criar atividade', true);
            });
        });

        // Atalhos: Ctrl+T alterna tipo, Escape limpa
        titulo.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { titulo.value = ''; titulo.blur(); }
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 't') {
                e.preventDefault();
                tipoBtn.click();
            }
        });
    }

    function renderObjetivos() {
        var container = $('#crm-v3-sidebar-objetivos-list');
        if (!container) return;
        updateTabCounts();
        if (!state.objetivos.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60">Nenhum objetivo registrado.</div>';
            return;
        }
        container.innerHTML = state.objetivos.map(function (o) {
            return (
                '<div class="crm-v3-objetivo flex items-center gap-2 py-2" data-objetivo-id="' + escapeHtml(o.id) + '">' +
                '<input type="checkbox" class="checkbox checkbox-xs crm-v3-obj-toggle" ' + (o.concluido ? 'checked' : '') + ' aria-label="' + escapeHtml(o.texto) + '" />' +
                '<span class="crm-v3-obj-text text-sm flex-1" title="' + escapeHtml(o.texto) + '">' + escapeHtml(o.texto) + '</span>' +
                '<span class="crm-v3-obj-date text-xs text-base-content/60 shrink-0">' + escapeHtml(dataParaExibicao(o.prazo)) + '</span>' +
                '<div class="crm-v3-obj-actions flex gap-0">' +
                '<button type="button" class="crm-v3-obj-edit btn btn-ghost btn-xs btn-square" aria-label="Editar objetivo" data-objetivo-id="' + escapeHtml(o.id) + '"><i class="fa-solid fa-pen"></i></button>' +
                '<button type="button" class="crm-v3-obj-delete btn btn-ghost btn-xs btn-square text-error" aria-label="Excluir objetivo" data-objetivo-id="' + escapeHtml(o.id) + '"><i class="fa-solid fa-trash"></i></button>' +
                '</div></div>'
            );
        }).join('');

        $$('.crm-v3-obj-toggle', container).forEach(function (cb) {
            cb.addEventListener('change', function () {
                var id = cb.closest('[data-objetivo-id]').getAttribute('data-objetivo-id');
                api('/objetivos/' + encodeURIComponent(id), { method: 'PATCH', body: { concluido: cb.checked } })
                    .then(function () { return loadObjetivos(state.clienteId); })
                    .catch(function (err) { cb.checked = !cb.checked; showToast(err.message, true); });
            });
        });
        $$('.crm-v3-obj-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-objetivo-id');
                openObjetivoModal(state.objetivos.find(function (o) { return o.id === id; }));
            });
        });
        $$('.crm-v3-obj-delete', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                state.pendingObjetivoId = btn.getAttribute('data-objetivo-id');
                var o = state.objetivos.find(function (x) { return x.id === state.pendingObjetivoId; });
                var txt = $('#crm-v3-confirm-obj-text');
                if (txt && o) txt.textContent = 'Excluir objetivo “' + o.texto + '”?';
                openModal('crm-v3-modal-confirm-obj');
            });
        });
    }

    // Status considerados "em aberto" (trabalho ativo do executivo).
    // Restante entra no histórico.
    var COT_STATUS_ABERTO = ['rascunho', 'enviada', 'em-acompanhamento', 'em_acompanhamento'];

    function cotacaoEstaAberta(c) {
        var s = String(c.status || '').toLowerCase();
        return COT_STATUS_ABERTO.indexOf(s) !== -1;
    }

    /**
     * Ícone monocromático por status (sem badge colorido).
     * Segue orientação do usuário: histórico sem cores para status.
     */
    function cotacaoStatusIcon(status) {
        switch (String(status || '').toLowerCase()) {
            case 'aprovada': return 'fa-solid fa-circle-check';
            case 'rejeitada': return 'fa-solid fa-circle-xmark';
            case 'expirada': return 'fa-regular fa-clock';
            case 'enviada': return 'fa-solid fa-paper-plane';
            case 'em-acompanhamento':
            case 'em_acompanhamento': return 'fa-solid fa-arrows-rotate';
            case 'rascunho': return 'fa-regular fa-file-lines';
            default: return 'fa-regular fa-circle';
        }
    }

    function cotacaoCardAberta(c) {
        var titulo = c.nome_campanha || c.titulo || 'Cotação sem título';
        var numero = c.numero_cotacao || '';
        var periodo = [dataParaExibicao(c.periodo_inicio), dataParaExibicao(c.periodo_fim)].filter(Boolean).join(' – ');
        var plataformas = Array.isArray(c.plataformas) ? c.plataformas : [];
        var objetivo = c.objetivo || '';
        var statusLabel = c.status_label || c.status_canonico || c.status || '';
        var plataformasHtml = plataformas.length
            ? '<div class="crm-v3-cotacao-plataformas">' +
                plataformas.slice(0, 4).map(function (p) {
                    return '<span class="crm-v3-cotacao-plataforma">' + escapeHtml(p) + '</span>';
                }).join('') +
                (plataformas.length > 4 ? '<span class="crm-v3-cotacao-plataforma crm-v3-cotacao-plataforma-more">+' + (plataformas.length - 4) + '</span>' : '') +
              '</div>'
            : '';
        return (
            '<article class="crm-v3-cotacao-card crm-v3-cotacao-card-aberta" data-cotacao-id="' + escapeHtml(c.id) + '">' +
            '<div class="crm-v3-cotacao-topline">' +
                (numero ? '<span class="crm-v3-cotacao-numero">' + escapeHtml(numero) + '</span>' : '') +
                '<span class="crm-v3-cotacao-status-chip" title="' + escapeHtml(statusLabel) + '">' +
                    '<i class="' + cotacaoStatusIcon(c.status) + '" aria-hidden="true"></i>' +
                    escapeHtml(statusLabel) +
                '</span>' +
                '<button type="button" class="crm-v3-icon-btn crm-v3-icon-btn-sm crm-v3-cotacao-detalhes" data-cotacao-id="' + escapeHtml(c.id) + '" aria-label="Abrir detalhes da cotação" title="Abrir detalhes">' +
                    '<i class="fa-solid fa-up-right-from-square" aria-hidden="true"></i>' +
                '</button>' +
            '</div>' +
            '<button type="button" class="crm-v3-cotacao-titulo crm-v3-cotacao-detalhes" data-cotacao-id="' + escapeHtml(c.id) + '">' +
                escapeHtml(titulo) +
            '</button>' +
            (objetivo ? '<div class="crm-v3-cotacao-objetivo"><i class="fa-solid fa-bullseye" aria-hidden="true"></i>' + escapeHtml(objetivo) + '</div>' : '') +
            plataformasHtml +
            '<div class="crm-v3-cotacao-rodape">' +
                '<span class="crm-v3-cotacao-valor">' + escapeHtml(c.valor) + '</span>' +
                (periodo ? '<span class="crm-v3-cotacao-data">' + escapeHtml(periodo) + '</span>' : '') +
            '</div>' +
            '</article>'
        );
    }

    function cotacaoLinhaHistorico(c) {
        var titulo = c.nome_campanha || c.titulo || 'Cotação sem título';
        var numero = c.numero_cotacao || '';
        var statusLabel = c.status_label || c.status_canonico || c.status || '';
        var periodo = dataParaExibicao(c.periodo_fim) || dataParaExibicao(c.data) || '';
        var valor = c.valor || (c.valor_total != null ? formatBRL(Number(c.valor_total)) : '');
        // Metadata compacta em uma linha só, separada por bullets. Cada item
        // é opcional (o `filter(Boolean)` evita "· ·" quando algum campo vem
        // vazio do backend).
        var meta = [numero, statusLabel, periodo].filter(Boolean).join(' · ');
        return (
            '<button type="button" class="crm-v3-cotacao-linha crm-v3-cotacao-detalhes" data-cotacao-id="' + escapeHtml(c.id) + '" title="Abrir detalhes">' +
                '<i class="crm-v3-cotacao-linha-icon ' + cotacaoStatusIcon(c.status) + '" aria-hidden="true"></i>' +
                '<span class="crm-v3-cotacao-linha-body">' +
                    '<span class="crm-v3-cotacao-linha-row1">' +
                        '<span class="crm-v3-cotacao-linha-nome">' + escapeHtml(titulo) + '</span>' +
                        (valor ? '<span class="crm-v3-cotacao-linha-valor">' + escapeHtml(valor) + '</span>' : '') +
                    '</span>' +
                    (meta ? '<span class="crm-v3-cotacao-linha-meta">' + escapeHtml(meta) + '</span>' : '') +
                '</span>' +
                '<i class="fa-solid fa-chevron-right crm-v3-cotacao-linha-chevron" aria-hidden="true"></i>' +
            '</button>'
        );
    }

    function renderCotacoes() {
        var container = $('#crm-v3-cotacao-list');
        if (!container) return;
        updateTabCounts();
        if (!state.cotacoes.length) {
            container.innerHTML = '<div class="crm-v3-cotacao-empty">Nenhuma cotação registrada.</div>';
            return;
        }

        var abertas = state.cotacoes.filter(cotacaoEstaAberta);
        var historico = state.cotacoes.filter(function (c) { return !cotacaoEstaAberta(c); });

        var html = '';
        html += '<div class="crm-v3-cotacao-grupo crm-v3-cotacao-grupo-abertas">' +
                '<div class="crm-v3-cotacao-grupo-title">' +
                    '<span>Em aberto</span>' +
                    '<span class="crm-v3-cotacao-grupo-count">' + abertas.length + '</span>' +
                '</div>';
        if (abertas.length) {
            html += abertas.map(cotacaoCardAberta).join('');
        } else {
            html += '<div class="crm-v3-cotacao-empty crm-v3-cotacao-empty-inline">Sem cotações em aberto.</div>';
        }
        html += '</div>';

        if (historico.length) {
            html += '<div class="crm-v3-cotacao-grupo crm-v3-cotacao-grupo-historico">' +
                    '<div class="crm-v3-cotacao-grupo-title">' +
                        '<span>Histórico</span>' +
                        '<span class="crm-v3-cotacao-grupo-count">' + historico.length + '</span>' +
                    '</div>' +
                    '<div class="crm-v3-cotacao-historico-list">' +
                        historico.map(cotacaoLinhaHistorico).join('') +
                    '</div>' +
                    '</div>';
        }
        container.innerHTML = html;

        $$('.crm-v3-cotacao-detalhes', container).forEach(function (btn) {
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                var id = btn.getAttribute('data-cotacao-id');
                if (!id) return;
                var cot = state.cotacoes.find(function (c) { return c.id === id; });
                if (cot) openCotacaoModal(cot);
            });
        });
    }

    function renderNotas() {
        var container = $('#crm-v3-notas-list');
        if (!container) return;
        updateTabCounts();
        if (!state.notas.length) {
            container.innerHTML = '<p class="text-sm text-base-content/60">Nenhuma nota registrada para este cliente.</p>';
            return;
        }
        container.innerHTML = state.notas.map(function (nota) {
            return '<article class="rounded-lg border border-base-200 p-2" data-nota-id="' + escapeHtml(nota.id) + '">' +
                '<p class="text-sm whitespace-pre-wrap">' + escapeHtml(nota.texto) + '</p>' +
                '<div class="flex justify-between items-center mt-1"><span class="text-xs text-base-content/50">' +
                escapeHtml(dataParaExibicao(nota.data) || 'Agora') + '</span>' +
                '<span><button type="button" class="btn btn-ghost btn-xs crm-v3-nota-edit" aria-label="Editar nota"><i class="fa-solid fa-pen"></i></button>' +
                '<button type="button" class="btn btn-ghost btn-xs text-error crm-v3-nota-delete" aria-label="Excluir nota"><i class="fa-solid fa-trash"></i></button></span></div></article>';
        }).join('');
        $$('.crm-v3-nota-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.closest('[data-nota-id]').getAttribute('data-nota-id');
                openNotaModal(state.notas.find(function (n) { return n.id === id; }));
            });
        });
        $$('.crm-v3-nota-delete', container).forEach(function (btn) {
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
        var container = $('#crm-v3-lista-contatos');
        if (container) {
            container.innerHTML = '<div class="p-3"><div class="skeleton h-12 w-full mb-2"></div><div class="skeleton h-12 w-full"></div></div>';
        }
        return api('/clientes/' + encodeURIComponent(clienteId) + '/contatos').then(function (data) {
            if (state.clienteId !== clienteId) return;
            state.contatos = data.contatos || [];
            state.contatoId = state.contatos.length ? state.contatos[0].id : null;
            renderContatos();
            if (state.cliente) updateDetailPanel(state.cliente);
        }).catch(function (err) {
            if (container) container.innerHTML = '<div class="crm-v3-contatos-empty p-3">Erro ao carregar contatos.</div>';
            showToast(err.message, true);
        });
    }

    function loadAtividades(clienteId) {
        return api('/clientes/' + encodeURIComponent(clienteId) + '/atividades').then(function (data) {
            if (state.clienteId !== clienteId) return;
            state.atividades = data.atividades || [];
            renderAtividades();
            if (state.cliente) updateDetailPanel(state.cliente);
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
            if (state.cliente) updateDetailPanel(state.cliente);
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
        if (!clienteId) return;
        // Evita re-render se já é o mesmo cliente selecionado.
        if (state.clienteId === clienteId && state.cliente) return;
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
        saveSession({ lastClientId: clienteId });
    }

    function loadClientes() {
        showClientesSkeleton();
        return api('/clientes').then(function (data) {
            state.clientes = data.clientes || [];
            renderClientes();
            if (state.clientes.length) {
                // Preferência: (1) cliente já selecionado no state; (2) último
                // cliente usado (localStorage); (3) primeiro da lista.
                var sess = loadSession();
                var candidato =
                    state.clientes.find(function (c) { return c.id === state.clienteId; }) ||
                    state.clientes.find(function (c) { return c.id === sess.lastClientId; }) ||
                    state.clientes[0];
                selectCliente(candidato.id);
            }
        }).catch(function (err) {
            var container = $('#crm-v3-lista-clientes');
            if (container) container.innerHTML = '<div class="crm-v3-contatos-empty p-3">Erro ao carregar clientes.</div>';
            showToast(err.message, true);
        });
    }

    // Abre contato como drawer flutuante (design system vanilla cx-*).
    // Se por algum motivo o drawer não estiver disponível, cai para o
    // modal legado (dialog `crm-v3-modal-contato`) como fallback.
    function openContatoModal(contatoId) {
        if (!state.clienteId) {
            showToast('Selecione um cliente primeiro', true);
            return;
        }
        var contato = contatoId
            ? state.contatos.find(function (x) { return x.id === contatoId; })
            : null;
        if (contatoId && !contato) return;

        if (typeof window.crmV3Drawer === 'object' && typeof window.crmV3Drawer.openContato === 'function') {
            window.crmV3Drawer.openContato(contato, state.clienteId);
            return;
        }

        // Fallback: modal legado.
        var form = $('#crm-v3-form-contato');
        var title = $('#crm-v3-modal-contato-title');
        if (!form) return;
        form.reset();
        $('#crm-v3-contato-id').value = contatoId || '';
        if (contato) {
            if (title) title.textContent = 'Editar contato';
            $('#crm-v3-contato-nome').value = contato.nome;
            $('#crm-v3-contato-email').value = contato.email;
            $('#crm-v3-contato-cargo').value = contato.cargo || '';
            $('#crm-v3-contato-setor').value = contato.setor || '';
            $('#crm-v3-contato-status').value = contato.status || 'Ativo';
            $('#crm-v3-contato-telefone').value = contato.telefone || '';
            $('#crm-v3-contato-telefone2').value = contato.telefone_secundario || '';
            $('#crm-v3-contato-principal').checked = contato.principal;
        } else if (title) title.textContent = 'Novo contato';
        openModal('crm-v3-modal-contato');
    }

    function openClienteModal(cliente) {
        var form = $('#crm-v3-form-cliente');
        if (form) form.reset();
        var id = $('#crm-v3-cliente-id');
        var title = $('#crm-v3-modal-cliente-title');
        var submitText = $('#crm-v3-cliente-submit .crm-v3-btn-text');
        if (id) id.value = cliente ? cliente.id : '';
        if (title) title.textContent = cliente ? 'Editar cliente' : 'Novo cliente';
        if (submitText) submitText.textContent = cliente ? 'Salvar alterações' : 'Criar cliente';

        var setVal = function (sel, val) {
            var el = $(sel);
            if (el) el.value = val == null ? '' : val;
        };
        var setChk = function (sel, val) {
            var el = $(sel);
            if (el) el.checked = !!val;
        };

        if (cliente) {
            var endereco = cliente.endereco || {};
            setVal('#crm-v3-cliente-pessoa', cliente.pessoa || 'J');
            setVal('#crm-v3-cliente-cnpj', cliente.cnpj || cliente.cpf || '');
            setVal('#crm-v3-cliente-nome', cliente.nome || cliente.nome_fantasia || '');
            setVal('#crm-v3-cliente-razao', cliente.razao_social || '');
            setVal('#crm-v3-cliente-ie', cliente.inscricao_estadual || '');
            setVal('#crm-v3-cliente-im', cliente.inscricao_municipal || '');
            var tipoLower = (cliente.tipo || cliente.categoria || '').toLowerCase();
            setVal('#crm-v3-cliente-tipo', tipoLower === 'público' ? 'publico' : (tipoLower === 'privado' ? 'privado' : (cliente.id_tipo_cliente || '')));
            setVal('#crm-v3-cliente-perfil', cliente.perfil || (cliente.is_agencia ? 'agencia' : 'direto'));

            setVal('#crm-v3-cliente-cep', endereco.cep || cliente.cep || '');
            setVal('#crm-v3-cliente-uf', endereco.uf || cliente.uf || '');
            setVal('#crm-v3-cliente-cidade', endereco.cidade || cliente.cidade || '');
            setVal('#crm-v3-cliente-bairro', endereco.bairro || cliente.bairro || '');
            setVal('#crm-v3-cliente-logradouro', endereco.logradouro || cliente.logradouro || '');
            setVal('#crm-v3-cliente-numero', endereco.numero || cliente.numero || '');
            setVal('#crm-v3-cliente-complemento', endereco.complemento || cliente.complemento || '');

            setVal('#crm-v3-cliente-classificacao', cliente.classificacao_cliente || cliente.classificacao || 'Prospecção');
            setVal('#crm-v3-cliente-responsavel', cliente.responsavel || 'Luisa Santana');
            setVal('#crm-v3-cliente-prioridade', cliente.prioridade || 'Média');
            setVal('#crm-v3-cliente-bv', cliente.bv_percentual != null ? cliente.bv_percentual : '');
            setVal('#crm-v3-cliente-margem', cliente.margem_cc != null ? cliente.margem_cc : '');
            setChk('#crm-v3-cliente-opera-midia', cliente.opera_midia);
            setChk('#crm-v3-cliente-demanda-dados', cliente.demanda_dados);
            setChk('#crm-v3-cliente-programatica', cliente.demanda_programatica_canais);
            setVal('#crm-v3-cliente-obs', cliente.observacoes_comerciais_adicionais || cliente.observacoes || '');

            renderAgenciasVinculadas(cliente);
        } else {
            renderAgenciasVinculadas(null);
        }
        openModal('crm-v3-modal-cliente');
    }

    function renderAgenciasVinculadas(cliente) {
        var list = $('#crm-v3-cliente-agencias-list');
        if (!list) return;
        var agencias = (state.clientes || []).filter(function (c) { return c.is_agencia; });
        var vinculos = [];
        if (cliente) {
            if (Array.isArray(cliente.agencias_vinculadas) && cliente.agencias_vinculadas.length) {
                vinculos = cliente.agencias_vinculadas.slice();
            } else if (cliente.agencia_id) {
                vinculos.push({ agencia_id: cliente.agencia_id, is_principal: true });
            }
        }
        if (!vinculos.length) vinculos.push({ agencia_id: '', is_principal: true });

        list.innerHTML = vinculos.map(function (v, idx) {
            var opts = ['<option value="">— Selecionar agência —</option>'].concat(
                agencias.map(function (a) {
                    var sel = a.id === v.agencia_id ? ' selected' : '';
                    return '<option value="' + escapeHtml(a.id) + '"' + sel + '>' + escapeHtml(a.nome) + '</option>';
                })
            ).join('');
            return (
                '<div class="crm-v3-agencia-row" data-idx="' + idx + '">' +
                '<select class="select select-bordered select-sm crm-v3-agencia-select">' + opts + '</select>' +
                '<label class="crm-v3-agencia-principal">' +
                '<input type="radio" name="crm-v3-agencia-principal" class="radio radio-xs" ' + (v.is_principal ? 'checked' : '') + ' />' +
                '<span>Principal</span></label>' +
                '<button type="button" class="btn btn-ghost btn-xs btn-square crm-v3-agencia-remove" aria-label="Remover"><i class="fa-solid fa-xmark"></i></button>' +
                '</div>'
            );
        }).join('');

        $$('.crm-v3-agencia-remove', list).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var row = btn.closest('.crm-v3-agencia-row');
                if (row) row.remove();
                // Garantir que sempre haja um marcado como principal
                var radios = $$('input[name="crm-v3-agencia-principal"]', list);
                if (radios.length && !radios.some(function (r) { return r.checked; })) {
                    radios[0].checked = true;
                }
            });
        });

        var addBtn = $('#crm-v3-cliente-agencia-add');
        if (addBtn && !addBtn.__bound) {
            addBtn.__bound = true;
            addBtn.addEventListener('click', function () {
                var idx = list.children.length;
                var opts = ['<option value="">— Selecionar agência —</option>'].concat(
                    (state.clientes || []).filter(function (c) { return c.is_agencia; })
                        .map(function (a) { return '<option value="' + escapeHtml(a.id) + '">' + escapeHtml(a.nome) + '</option>'; })
                ).join('');
                var wrap = document.createElement('div');
                wrap.className = 'crm-v3-agencia-row';
                wrap.setAttribute('data-idx', String(idx));
                wrap.innerHTML = (
                    '<select class="select select-bordered select-sm crm-v3-agencia-select">' + opts + '</select>' +
                    '<label class="crm-v3-agencia-principal">' +
                    '<input type="radio" name="crm-v3-agencia-principal" class="radio radio-xs" />' +
                    '<span>Principal</span></label>' +
                    '<button type="button" class="btn btn-ghost btn-xs btn-square crm-v3-agencia-remove" aria-label="Remover"><i class="fa-solid fa-xmark"></i></button>'
                );
                list.appendChild(wrap);
                wrap.querySelector('.crm-v3-agencia-remove').addEventListener('click', function () {
                    wrap.remove();
                });
            });
        }
    }

    function coletarAgenciasVinculadas() {
        var list = $('#crm-v3-cliente-agencias-list');
        if (!list) return [];
        var rows = $$('.crm-v3-agencia-row', list);
        var vinculos = [];
        rows.forEach(function (row) {
            var sel = row.querySelector('.crm-v3-agencia-select');
            var principal = row.querySelector('input[name="crm-v3-agencia-principal"]');
            var val = sel ? sel.value : '';
            if (val) {
                vinculos.push({ agencia_id: val, is_principal: !!(principal && principal.checked) });
            }
        });
        return vinculos;
    }

    function openAtividadeModal(ativ) {
        var form = $('#crm-v3-form-atividade');
        var title = $('#crm-v3-modal-atividade-title');
        if (!form) return;
        form.reset();
        $('#crm-v3-atividade-id').value = ativ ? ativ.id : '';
        if (title) title.textContent = ativ ? 'Editar atividade' : 'Nova atividade';
        if (ativ) {
            $('#crm-v3-atividade-titulo').value = ativ.titulo || '';
            $('#crm-v3-atividade-desc').value = ativ.descricao || '';
            $('#crm-v3-atividade-prioridade').value = ativ.prioridade || 'Média';
            $('#crm-v3-atividade-hora').value = ativ.hora || '';
            $('#crm-v3-atividade-data').value = ativ.data || '';
            $('#crm-v3-atividade-tipo').value = ativ.tipo || 'atividade';
            $('#crm-v3-atividade-responsavel').value = ativ.responsavel || 'LS';
        }
        openModal('crm-v3-modal-atividade');
    }

    function openObjetivoModal(objetivo) {
        var form = $('#crm-v3-form-objetivo');
        if (!form) return;
        form.reset();
        $('#crm-v3-objetivo-id').value = objetivo ? objetivo.id : '';
        $('#crm-v3-modal-objetivo-title').textContent = objetivo ? 'Editar objetivo' : 'Novo objetivo';
        if (objetivo) {
            $('#crm-v3-objetivo-texto').value = objetivo.texto || '';
            $('#crm-v3-objetivo-prazo').value = dataParaInput(objetivo.prazo);
        }
        openModal('crm-v3-modal-objetivo');
    }

    function openCotacaoModal(cotacao) {
        var form = $('#crm-v3-form-cotacao');
        if (form) form.reset();
        $('#crm-v3-cotacao-id').value = cotacao ? cotacao.id : '';
        $('#crm-v3-modal-cotacao-title').textContent = cotacao ? 'Editar cotação' : 'Nova cotação';
        var inicio = $('#crm-v3-cotacao-inicio');
        var fim = $('#crm-v3-cotacao-fim');
        if (inicio) inicio.value = cotacao ? dataParaInput(cotacao.periodo_inicio || cotacao.data) : new Date().toISOString().slice(0, 10);
        if (fim) fim.value = cotacao ? dataParaInput(cotacao.periodo_fim) : '';
        var objetivoInput = $('#crm-v3-cotacao-objetivo');
        var plataformasInput = $('#crm-v3-cotacao-plataformas');
        if (cotacao) {
            $('#crm-v3-cotacao-titulo').value = cotacao.nome_campanha || cotacao.titulo || '';
            $('#crm-v3-cotacao-valor').value = cotacao.valor_total || cotacao.valor || '';
            $('#crm-v3-cotacao-status').value = cotacao.status || 'rascunho';
            if (objetivoInput) objetivoInput.value = cotacao.objetivo || '';
            if (plataformasInput) plataformasInput.value = Array.isArray(cotacao.plataformas) ? cotacao.plataformas.join(', ') : (cotacao.plataformas || '');
        } else {
            if (objetivoInput) objetivoInput.value = '';
            if (plataformasInput) plataformasInput.value = '';
        }
        openModal('crm-v3-modal-cotacao');
    }

    function openNotaModal(nota) {
        var form = $('#crm-v3-form-nota');
        if (!form) return;
        form.reset();
        $('#crm-v3-nota-id').value = nota ? nota.id : '';
        $('#crm-v3-modal-nota-title').textContent = nota ? 'Editar nota' : 'Nova nota';
        $('#crm-v3-nota-texto').value = nota ? nota.texto : '';
        openModal('crm-v3-modal-nota');
    }

    function setImportStep(step) {
        var steps = $('#crm-v3-import-steps');
        if (steps) {
            $$('.step', steps).forEach(function (s) {
                var n = parseInt(s.getAttribute('data-step'), 10);
                s.classList.toggle('step-primary', n <= step);
            });
        }
        $('#crm-v3-import-step-1').hidden = step !== 1;
        $('#crm-v3-import-step-2').hidden = step !== 2;
        $('#crm-v3-import-step-3').hidden = step !== 3;
        var err = $('#crm-v3-import-error');
        if (err) err.hidden = true;
    }

    function openImportModal() {
        state.importRows = [];
        $('#crm-v3-import-texto').value = '';
        setImportStep(1);
        openModal('crm-v3-modal-import');
    }

    function initModals() {
        $$('[data-close-modal]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeModal(btn.getAttribute('data-close-modal'));
            });
        });

        $$('.crm-v3-modal').forEach(function (dialog) {
            dialog.addEventListener('click', function (e) {
                if (e.target === dialog) closeModal(dialog.id);
            });
        });

        var formContato = $('#crm-v3-form-contato');
        if (formContato) {
            formContato.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-v3-contato-submit');
                var contatoId = $('#crm-v3-contato-id').value;
                var body = {
                    nome: $('#crm-v3-contato-nome').value,
                    email: $('#crm-v3-contato-email').value,
                    cargo: $('#crm-v3-contato-cargo').value,
                    setor: $('#crm-v3-contato-setor').value,
                    status: $('#crm-v3-contato-status').value,
                    telefone: $('#crm-v3-contato-telefone').value,
                    telefone_secundario: $('#crm-v3-contato-telefone2').value,
                    principal: $('#crm-v3-contato-principal').checked
                };
                setBtnLoading(btn, true);
                var req = contatoId
                    ? api('/contatos/' + encodeURIComponent(contatoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/contatos', { method: 'POST', body: body });
                req.then(function (data) {
                    closeModal('crm-v3-modal-contato');
                    showToast(contatoId ? 'Contato atualizado' : 'Contato criado');
                    if (data.cliente_id) state.clienteId = data.cliente_id;
                    return loadClientes();
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formCliente = $('#crm-v3-form-cliente');
        if (formCliente) {
            formCliente.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-v3-cliente-submit');
                var clienteId = $('#crm-v3-cliente-id').value;
                var perfil = $('#crm-v3-cliente-perfil').value;
                var tipoValue = $('#crm-v3-cliente-tipo').value;
                var tipoLabel = tipoValue === 'publico' ? 'Público' : (tipoValue === 'privado' ? 'Privado' : '');
                var body = {
                    // Identificação
                    pessoa: $('#crm-v3-cliente-pessoa').value,
                    cnpj: $('#crm-v3-cliente-cnpj').value,
                    nome: $('#crm-v3-cliente-nome').value,
                    razao_social: $('#crm-v3-cliente-razao').value,
                    inscricao_estadual: $('#crm-v3-cliente-ie').value,
                    inscricao_municipal: $('#crm-v3-cliente-im').value,
                    id_tipo_cliente: tipoValue,
                    perfil: perfil,
                    is_agencia: perfil === 'agencia',
                    tipo_label: perfil === 'agencia' ? 'Agência' : 'Cliente final',
                    tipo: tipoLabel,
                    categoria: tipoLabel,
                    // Endereço
                    endereco: {
                        cep: $('#crm-v3-cliente-cep').value,
                        uf: $('#crm-v3-cliente-uf').value,
                        cidade: $('#crm-v3-cliente-cidade').value,
                        bairro: $('#crm-v3-cliente-bairro').value,
                        logradouro: $('#crm-v3-cliente-logradouro').value,
                        numero: $('#crm-v3-cliente-numero').value,
                        complemento: $('#crm-v3-cliente-complemento').value
                    },
                    // Comercial
                    classificacao_cliente: $('#crm-v3-cliente-classificacao').value,
                    responsavel: $('#crm-v3-cliente-responsavel').value,
                    prioridade: $('#crm-v3-cliente-prioridade').value,
                    bv_percentual: parseFloat($('#crm-v3-cliente-bv').value) || 0,
                    margem_cc: parseFloat($('#crm-v3-cliente-margem').value) || 0,
                    opera_midia: $('#crm-v3-cliente-opera-midia').checked,
                    demanda_dados: $('#crm-v3-cliente-demanda-dados').checked,
                    demanda_programatica_canais: $('#crm-v3-cliente-programatica').checked,
                    observacoes_comerciais_adicionais: $('#crm-v3-cliente-obs').value,
                    // Vínculos
                    agencias_vinculadas: coletarAgenciasVinculadas()
                };
                setBtnLoading(btn, true);
                var req = clienteId
                    ? api('/clientes/' + encodeURIComponent(clienteId), { method: 'PATCH', body: body })
                    : api('/clientes', { method: 'POST', body: body });
                req.then(function (data) {
                    closeModal('crm-v3-modal-cliente');
                    showToast(clienteId ? 'Cliente atualizado' : 'Cliente criado');
                    state.clienteId = (data.cliente && data.cliente.id) || clienteId;
                    return loadClientes();
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formAtiv = $('#crm-v3-form-atividade');
        if (formAtiv) {
            formAtiv.addEventListener('submit', function (e) {
                e.preventDefault();
                if (!state.clienteId) {
                    showToast('Selecione um cliente', true);
                    return;
                }
                var btn = $('#crm-v3-atividade-submit');
                var ativId = $('#crm-v3-atividade-id').value;
                var body = {
                    titulo: $('#crm-v3-atividade-titulo').value,
                    descricao: $('#crm-v3-atividade-desc').value,
                    prioridade: $('#crm-v3-atividade-prioridade').value,
                    hora: $('#crm-v3-atividade-hora').value,
                    data: $('#crm-v3-atividade-data').value,
                    data_label: $('#crm-v3-atividade-data').value ? 'Agendada' : 'Hoje',
                    tipo: $('#crm-v3-atividade-tipo').value,
                    responsavel: $('#crm-v3-atividade-responsavel').value
                };
                setBtnLoading(btn, true);
                var req = ativId
                    ? api('/atividades/' + encodeURIComponent(ativId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/atividades', { method: 'POST', body: body });
                req.then(function () {
                    closeModal('crm-v3-modal-atividade');
                    showToast(ativId ? 'Atividade atualizada' : 'Atividade criada');
                    return loadAtividades(state.clienteId);
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formObjetivo = $('#crm-v3-form-objetivo');
        if (formObjetivo) {
            formObjetivo.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-v3-objetivo-submit');
                var objetivoId = $('#crm-v3-objetivo-id').value;
                var body = {
                    texto: $('#crm-v3-objetivo-texto').value,
                    prazo: $('#crm-v3-objetivo-prazo').value
                };
                setBtnLoading(btn, true);
                var req = objetivoId
                    ? api('/objetivos/' + encodeURIComponent(objetivoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/objetivos', { method: 'POST', body: body });
                req.then(function () {
                    closeModal('crm-v3-modal-objetivo');
                    showToast(objetivoId ? 'Objetivo atualizado' : 'Objetivo criado');
                    return loadObjetivos(state.clienteId);
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formCotacao = $('#crm-v3-form-cotacao');
        if (formCotacao) {
            formCotacao.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-v3-cotacao-submit');
                var cotacaoId = $('#crm-v3-cotacao-id').value;
                var status = $('#crm-v3-cotacao-status').value;
                var titulo = $('#crm-v3-cotacao-titulo').value;
                var valor = $('#crm-v3-cotacao-valor').value;
                var inicio = $('#crm-v3-cotacao-inicio').value;
                var objetivo = ($('#crm-v3-cotacao-objetivo') || {}).value || '';
                var plataformasRaw = ($('#crm-v3-cotacao-plataformas') || {}).value || '';
                var plataformas = plataformasRaw
                    .split(',')
                    .map(function (p) { return p.trim(); })
                    .filter(function (p) { return p.length > 0; });
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
                    periodo_fim: $('#crm-v3-cotacao-fim').value,
                    objetivo: objetivo,
                    plataformas: plataformas
                };
                setBtnLoading(btn, true);
                var req = cotacaoId
                    ? api('/cotacoes/' + encodeURIComponent(cotacaoId), { method: 'PATCH', body: body })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/cotacoes', { method: 'POST', body: body });
                req
                    .then(function () {
                        closeModal('crm-v3-modal-cotacao');
                        showToast(cotacaoId ? 'Cotação atualizada' : 'Cotação criada');
                        return loadCotacoes(state.clienteId);
                    }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var formNota = $('#crm-v3-form-nota');
        if (formNota) {
            formNota.addEventListener('submit', function (e) {
                e.preventDefault();
                var btn = $('#crm-v3-nota-submit');
                var notaId = $('#crm-v3-nota-id').value;
                setBtnLoading(btn, true);
                var req = notaId
                    ? api('/notas/' + encodeURIComponent(notaId), { method: 'PATCH', body: { texto: $('#crm-v3-nota-texto').value } })
                    : api('/clientes/' + encodeURIComponent(state.clienteId) + '/notas', { method: 'POST', body: { texto: $('#crm-v3-nota-texto').value } });
                req.then(function () {
                    closeModal('crm-v3-modal-nota');
                    showToast(notaId ? 'Nota atualizada' : 'Nota adicionada');
                    formNota.reset();
                    return loadNotas(state.clienteId);
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(btn, false); });
            });
        }

        var processarBtn = $('#crm-v3-import-processar');
        if (processarBtn) {
            processarBtn.addEventListener('click', function () {
                var texto = ($('#crm-v3-import-texto').value || '').trim();
                if (!texto) {
                    showToast('Cole a lista de contatos', true);
                    return;
                }
                setBtnLoading(processarBtn, true);
                api('/contatos/parse-texto', { method: 'POST', body: { texto: texto } })
                    .then(function (data) {
                        state.importRows = data.contatos || [];
                        if (!state.importRows.length) {
                            var err = $('#crm-v3-import-error');
                            if (err) { err.textContent = 'Nenhum contato reconhecido.'; err.hidden = false; }
                            return;
                        }
                        renderImportTable();
                        setImportStep(2);
                    })
                    .catch(function (err) {
                        var el = $('#crm-v3-import-error');
                        if (el) { el.textContent = err.message; el.hidden = false; }
                    })
                    .finally(function () { setBtnLoading(processarBtn, false); });
            });
        }

        var next2 = $('#crm-v3-import-next-2');
        if (next2) next2.addEventListener('click', function () {
            collectImportRowsFromTable();
            if (!validarImportRows()) return;
            var msg = $('#crm-v3-import-confirm-msg');
            if (msg) msg.textContent = 'Confirmar importação de ' + state.importRows.length + ' contato(s)?';
            setImportStep(3);
        });

        var back1 = $('#crm-v3-import-back-1');
        if (back1) back1.addEventListener('click', function () { setImportStep(1); });

        var back2 = $('#crm-v3-import-back-2');
        if (back2) back2.addEventListener('click', function () { setImportStep(2); });

        var importSubmit = $('#crm-v3-import-submit');
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
                    closeModal('crm-v3-modal-import');
                    showToast((data.importados || state.importRows.length) + ' contato(s) importado(s)');
                    return loadClientes();
                }).catch(function (err) { showToast(err.message, true); })
                    .finally(function () { setBtnLoading(importSubmit, false); });
            });
        }

        var confirmObj = $('#crm-v3-confirm-obj-btn');
        if (confirmObj) {
            confirmObj.addEventListener('click', function () {
                if (!state.pendingObjetivoId) return;
                api('/objetivos/' + encodeURIComponent(state.pendingObjetivoId), { method: 'DELETE' })
                    .then(function () {
                        closeModal('crm-v3-modal-confirm-obj');
                        showToast('Objetivo excluído');
                        return loadObjetivos(state.clienteId);
                    })
                    .catch(function (err) { showToast(err.message, true); });
            });
        }
    }

    function renderImportTable() {
        var tbody = $('#crm-v3-import-table tbody');
        var count = $('#crm-v3-import-review-count');
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
        var rows = $$('#crm-v3-import-table tbody tr');
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
        var erro = $('#crm-v3-import-error');
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
        var tabs = tabContainer.querySelectorAll('.crm-v3-tab, .tab');

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
                panel.classList.toggle('crm-v3-tab-panel-active', isTarget);
                if (panel.hasAttribute('hidden')) panel.hidden = !isTarget;
            });
            if (groupName === 'atividades') {
                state.filtroAtivTab = target;
                renderAtividades();
                saveSession({ filtroAtivTab: target });
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

    /**
     * Restaura filtros do localStorage antes de bindar os handlers.
     * Só carrega valores que existam nos controles atuais para evitar
     * ficar com filtro "fantasma" no state que a UI não reflete.
     */
    function restoreFiltros() {
        var sess = loadSession();
        if (sess.filtroPill) state.filtroPill = sess.filtroPill;
        if (sess.filtroExecutivo != null) state.filtroExecutivo = sess.filtroExecutivo;
        if (sess.filtroTipo != null) state.filtroTipo = sess.filtroTipo;
        if (sess.filtroPerfil != null) state.filtroPerfil = sess.filtroPerfil;
        if (sess.filtroAtivTab) state.filtroAtivTab = sess.filtroAtivTab;
    }

    /**
     * Reflete o `state.filtro*` restaurado nos controles do DOM logo
     * após montar a página; evita renders extras porque só ajusta o
     * value dos selects/pills, o `renderClientes` roda uma única vez
     * depois de `loadClientes`.
     */
    function syncFiltrosParaDom() {
        var executivo = $('#filtro-executivo');
        var tipo = $('#filtro-tipo');
        var perfil = $('#filtro-perfil');
        if (executivo && state.filtroExecutivo) executivo.value = state.filtroExecutivo;
        if (tipo && state.filtroTipo) tipo.value = state.filtroTipo;
        if (perfil && state.filtroPerfil) perfil.value = state.filtroPerfil;
        $$('.crm-v3-pill').forEach(function (p) {
            var active = p.getAttribute('data-filter') === state.filtroPill;
            p.classList.toggle('is-active', active);
            p.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        // Sincroniza aba ativa de atividades (todas/pendentes/concluidas)
        $$('[data-tab-group="atividades"] .crm-v3-tab').forEach(function (tab) {
            var active = tab.getAttribute('data-tab') === state.filtroAtivTab;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
            tab.setAttribute('tabindex', active ? '0' : '-1');
        });
    }

    function initFilters() {
        $$('.crm-v3-pill').forEach(function (pill) {
            pill.addEventListener('click', function () {
                $$('.crm-v3-pill').forEach(function (p) {
                    p.classList.remove('is-active');
                    p.setAttribute('aria-pressed', 'false');
                });
                pill.classList.add('is-active');
                pill.setAttribute('aria-pressed', 'true');
                state.filtroPill = pill.getAttribute('data-filter') || 'todos';
                state.paginaCliente = 1;
                renderClientes();
                saveSession({ filtroPill: state.filtroPill });
            });
        });

        var buscaCliente = $('#crm-v3-busca');
        if (buscaCliente) {
            buscaCliente.addEventListener('input', function () {
                state.buscaCliente = buscaCliente.value;
                state.paginaCliente = 1;
                renderClientes();
            });
        }

        var buscaContato = $('#crm-v3-busca-contato');
        if (buscaContato) {
            buscaContato.addEventListener('input', function () {
                state.buscaContato = buscaContato.value;
                renderContatos();
            });
        }

        // Filtros textuais/select da coluna de atividades foram removidos por
        // decisão de UX: a coluna mostra tudo agrupado por data.

        var executivo = $('#filtro-executivo');
        var tipo = $('#filtro-tipo');
        var perfil = $('#filtro-perfil');
        if (executivo) executivo.addEventListener('change', function () {
            state.filtroExecutivo = executivo.value;
            state.paginaCliente = 1;
            renderClientes();
            saveSession({ filtroExecutivo: state.filtroExecutivo });
        });
        if (tipo) tipo.addEventListener('change', function () {
            state.filtroTipo = tipo.value;
            state.paginaCliente = 1;
            renderClientes();
            saveSession({ filtroTipo: state.filtroTipo });
        });
        if (perfil) perfil.addEventListener('change', function () {
            state.filtroPerfil = perfil.value;
            state.paginaCliente = 1;
            renderClientes();
            saveSession({ filtroPerfil: state.filtroPerfil });
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
        link.download = 'clientes-crm-v3.csv';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showToast('CSV exportado');
    }

    function initButtons() {
        var novoCliente = $('#crm-v3-btn-novo-cliente-header');
        if (novoCliente) novoCliente.addEventListener('click', function () { openClienteModal(null); });
        var novoClienteLista = $('#crm-v3-btn-novo-cliente-lista');
        if (novoClienteLista) novoClienteLista.addEventListener('click', function () { openClienteModal(null); });

        var limpar = $('#crm-v3-btn-limpar-filtros');
        if (limpar) limpar.addEventListener('click', function () {
            state.filtroPill = 'todos';
            state.filtroExecutivo = '';
            state.filtroTipo = '';
            state.filtroPerfil = '';
            state.buscaCliente = '';
            state.paginaCliente = 1;
            $('#crm-v3-busca').value = '';
            $('#filtro-executivo').value = '';
            $('#filtro-tipo').value = '';
            $('#filtro-perfil').value = '';
            $$('.crm-v3-pill').forEach(function (pill) {
                var active = pill.getAttribute('data-filter') === 'todos';
                pill.classList.toggle('is-active', active);
                pill.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            renderClientes();
        });

        var exportar = $('#crm-v3-btn-exportar');
        if (exportar) exportar.addEventListener('click', exportarClientesCsv);
        var exportarHeader = $('.crm-v3-header-action-export');
        if (exportarHeader) exportarHeader.addEventListener('click', exportarClientesCsv);
        var editarHeader = $('.crm-v3-header-action-edit');
        if (editarHeader) editarHeader.addEventListener('click', function () { openClienteModal(state.cliente); });

        var prev = $('#crm-v3-page-prev');
        var next = $('#crm-v3-page-next');
        if (prev) prev.addEventListener('click', function () {
            if (state.paginaCliente > 1) { state.paginaCliente--; renderClientes(); }
        });
        if (next) next.addEventListener('click', function () {
            state.paginaCliente++;
            renderClientes();
        });

        var novoContato = $('#crm-v3-btn-novo-contato');
        if (novoContato) novoContato.addEventListener('click', function () { openContatoModal(); });

        var importBtn = $('#crm-v3-btn-import-contatos');
        if (importBtn) importBtn.addEventListener('click', openImportModal);

        // Os botões "+ Nova" e "Detalhes" do header foram removidos.
        // A criação acontece exclusivamente pelo composer inline abaixo.
        bindComposerAtividade();

        var novoObjetivo = $('#crm-v3-btn-novo-objetivo');
        if (novoObjetivo) novoObjetivo.addEventListener('click', function () { openObjetivoModal(null); });
        var novaCotacao = $('#crm-v3-btn-nova-cotacao');
        if (novaCotacao) novaCotacao.addEventListener('click', function () { openCotacaoModal(null); });
        var novaNota = $('#crm-v3-btn-nova-nota');
        if (novaNota) novaNota.addEventListener('click', function () { openNotaModal(null); });
        var expandir = $('#crm-v3-btn-expandir-cotacoes');
        if (expandir) expandir.addEventListener('click', function () {
            var painel = $('.crm-v3-center-right');
            var expanded = painel.classList.toggle('is-expanded');
            expandir.setAttribute('aria-pressed', expanded ? 'true' : 'false');
            expandir.querySelector('i').className = expanded ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
        });

        // O toggle Seguir/Deixar de seguir foi removido da UI. Filtro por
        // "Seguindo" continua funcional via pill de status no header.

        var verTodos = $('#crm-v3-ver-todos-contatos');
        if (verTodos) {
            verTodos.addEventListener('click', function () {
                var col = $('.crm-v3-col-contatos');
                if (col) col.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }

        var verTodasAtividades = $('#crm-v3-ver-todas-atividades');
        if (verTodasAtividades) {
            verTodasAtividades.addEventListener('click', function () {
                var painel = $('.crm-v3-section-atividades');
                var tabTodas = $('#tab-atividades-todas');
                if (tabTodas) tabTodas.click();
                if (painel) {
                    painel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    painel.focus({ preventScroll: true });
                }
            });
        }

        $$('.crm-v3-star').forEach(function (star) {
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
    // Restaura filtros do localStorage antes de bindar handlers para não
    // disparar renders extras — o `syncFiltrosParaDom` só ajusta valores
    // e o primeiro `renderClientes` (dentro de `loadClientes`) já usa o
    // state consolidado.
    restoreFiltros();
    syncFiltrosParaDom();
    initFilters();
    initButtons();
    showOverlay('Carregando CRM…');
    loadClientes().finally(hideOverlay);

    // Exporta uma superfície mínima para módulos externos (crm_v3_drawers.js, atalhos)
    window.crmV3 = {
        state: state,
        reloadClientes: function (clienteIdParaSelecionar) {
            if (clienteIdParaSelecionar) state.clienteId = clienteIdParaSelecionar;
            return loadClientes();
        },
        reloadAtividades: function () {
            if (!state.clienteId) return Promise.resolve();
            return loadAtividades(state.clienteId);
        },
        reloadCotacoes: function () {
            if (!state.clienteId) return Promise.resolve();
            return loadCotacoes(state.clienteId);
        },
        selectCliente: selectCliente,
    };
})();
