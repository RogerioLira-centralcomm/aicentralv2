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
            if (state.filtroPill === 'seguindo' && !c.seguindo) return false;
            if (state.filtroPill !== 'todos' && state.filtroPill !== 'seguindo' && c.status !== state.filtroPill) return false;
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
                '<span class="' + badgeDaisy(c.badge_type) + '">' + escapeHtml(c.badge) + '</span>' +
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
        if (state.cliente) updateSinalizadores(state.cliente);
    }

    function updatePillCounts() {
        var counts = { todos: state.clientes.length, atrasado: 0, 'sem-atividade': 0, seguindo: 0 };
        state.clientes.forEach(function (c) {
            if (c.status === 'atrasado') counts.atrasado++;
            if (c.status === 'sem-atividade') counts['sem-atividade']++;
            if (c.seguindo) counts.seguindo++;
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

        var m = cliente.metrics || {};
        var el;
        el = $('#crm-metric-contatos'); if (el) el.textContent = m.contatos != null ? m.contatos : cliente.qtd_contatos || 0;
        el = $('#crm-metric-oportunidades'); if (el) el.textContent = m.oportunidades != null ? m.oportunidades : 0;
        el = $('#crm-metric-faturamento'); if (el) el.textContent = m.faturamento || '—';
        el = $('#crm-metric-pis'); if (el) el.textContent = m.valor_pis || '—';
        el = $('#crm-metric-tarefas'); if (el) el.textContent = m.tarefas_abertas != null ? m.tarefas_abertas : 0;
        el = $('#crm-metric-ultimo'); if (el) el.textContent = m.ultimo_contato || '—';

        updateStatusComercial(cliente);
        updateVinculos(cliente);
        updateSinalizadores(cliente);
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

    function updateSinalizadores(cliente) {
        var m = cliente.metrics || {};
        var notas = (state.notas || []).length;
        var objetivos = (state.objetivos || []).length;
        var pend = (state.atividades || []).filter(function (a) { return a.status !== 'concluida'; }).length;
        var cot = m.cotacoes_abertas != null ? m.cotacoes_abertas : (state.cotacoes || []).length;

        var set = function (id, val, alert) {
            var el = document.getElementById(id);
            if (!el) return;
            el.textContent = String(val);
            var parent = el.parentElement;
            if (parent) parent.classList.toggle('is-alert', !!alert);
        };
        set('crm-v3-sinal-notas', notas);
        set('crm-v3-sinal-objetivos', objetivos);
        set('crm-v3-sinal-atividades', pend, pend > 0);
        set('crm-v3-sinal-cotacoes', cot);
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
            return (
                '<div class="crm-v3-contato-card' + (ativo ? ' crm-v3-contato-card-active is-expanded' : '') + '" role="listitem" tabindex="0" data-contato-id="' + escapeHtml(c.id) + '">' +
                '<div class="crm-v3-contato-main">' +
                avatarHtml(c.nome, ativo ? 'w-8 h-8' : 'w-8 h-8') +
                '<div class="crm-v3-contato-info min-w-0">' +
                '<div class="crm-v3-contato-nome truncate text-sm font-medium">' + escapeHtml(c.nome) + '</div>' +
                '<div class="crm-v3-contato-cargo text-xs text-base-content/60 truncate">' + escapeHtml(c.cargo) + '</div>' +
                '</div>' +
                '<div class="crm-v3-contato-actions">' +
                (c.principal ? '<span class="badge badge-sm badge-primary">Principal</span>' : '') +
                (c.conversas ? '<span class="badge badge-sm badge-info">' + c.conversas + '</span>' : '') +
                '<button type="button" class="crm-v3-contato-edit btn btn-ghost btn-xs btn-square" aria-label="Editar" data-contato-id="' + escapeHtml(c.id) + '"><i class="fa-solid fa-pen" aria-hidden="true"></i></button>' +
                '<button type="button" class="crm-v3-contato-toggle btn btn-ghost btn-xs btn-square" aria-expanded="' + (ativo ? 'true' : 'false') + '"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>' +
                '</div></div>' +
                '<div class="crm-v3-contato-details">' +
                (c.email ? (
                    '<div class="crm-v3-contato-email-row flex items-center gap-1"><span class="truncate">' + escapeHtml(c.email) + '</span>' +
                    '<button type="button" class="crm-v3-contato-copy btn btn-ghost btn-xs btn-square" data-copy="' + escapeHtml(c.email) + '" aria-label="Copiar"><i class="fa-regular fa-copy"></i></button></div>'
                ) : '') +
                '<div class="crm-v3-contato-phone-label text-xs text-base-content/50 mt-1">WhatsApp</div>' +
                (c.telefone ? '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row w-full text-left"><span>' + escapeHtml(c.telefone) + '</span></button>' : '') +
                (c.telefone_secundario ? '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row w-full text-left"><span>' + escapeHtml(c.telefone_secundario) + '</span></button>' : '') +
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

    function renderAtividades() {
        var container = $('#crm-v3-ativ-list');
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
            updateTabCounts();
            return;
        }

        if (!filtrados.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhuma atividade.</div>';
            renderSidebarAtividades();
            renderSugestao();
            updateTabCounts();
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
            html += '<div class="crm-v3-date-group"><div class="crm-v3-date-label text-xs font-semibold text-base-content/70 px-2 py-1">' + escapeHtml(label) + '</div>';
            groups[label].forEach(function (a) {
                var concluida = a.status === 'concluida';
                html += (
                    '<div class="crm-v3-ativ flex items-center gap-1 px-2 py-1' + (concluida ? ' crm-v3-ativ-concluida' : '') + '" role="listitem" data-status="' + escapeHtml(a.status) + '" data-atividade-id="' + escapeHtml(a.id) + '">' +
                    '<input type="checkbox" class="checkbox checkbox-xs checkbox-primary crm-v3-ativ-check" ' + (concluida ? 'checked' : '') + ' aria-label="Concluir: ' + escapeHtml(a.titulo) + '" />' +
                    ativIconHtml(a.tipo) +
                    '<div class="crm-v3-ativ-content min-w-0 flex-1">' +
                    '<div class="crm-v3-ativ-titulo text-sm truncate">' + escapeHtml(a.titulo) + '</div>' +
                    (a.descricao ? '<div class="crm-v3-ativ-desc text-xs text-base-content/60 truncate">' + escapeHtml(a.descricao) + '</div>' : '') +
                    '</div>' +
                    '<span class="crm-v3-ativ-time text-xs shrink-0">' + escapeHtml(a.hora || '') + '</span>' +
                    prioridadeBadge(a.prioridade) +
                    '<div class="crm-v3-avatar-mini shrink-0" title="' + escapeHtml(a.responsavel || '') + '">' + escapeHtml(a.responsavel || '') + '</div>' +
                    '<div class="dropdown dropdown-end shrink-0">' +
                    '<button type="button" class="btn btn-ghost btn-xs btn-square crm-v3-ativ-menu-btn" tabindex="0" aria-label="Mais opções"><i class="fa-solid fa-ellipsis-vertical"></i></button>' +
                    '<ul class="dropdown-content menu p-1 shadow bg-base-100 rounded-box w-40 border border-base-200 z-50 text-xs">' +
                    '<li><button type="button" class="crm-v3-ativ-action" data-action="concluir">Concluir</button></li>' +
                    '<li><button type="button" class="crm-v3-ativ-action" data-action="editar">Editar</button></li>' +
                    '<li><button type="button" class="crm-v3-ativ-action" data-action="reagendar">Reagendar</button></li>' +
                    '<li><button type="button" class="crm-v3-ativ-action" data-action="duplicar">Duplicar</button></li>' +
                    '<li><button type="button" class="crm-v3-ativ-action text-error" data-action="excluir">Excluir</button></li>' +
                    '</ul></div></div>'
                );
            });
            html += '</div>';
        });

        container.innerHTML = html;
        bindAtividadeEvents(container);
        renderSidebarAtividades();
        renderSugestao();
        updateTabCounts();
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
        $$('.crm-v3-ativ-check', container).forEach(function (cb) {
            cb.addEventListener('change', function () {
                var row = cb.closest('.crm-v3-ativ');
                var id = row.getAttribute('data-atividade-id');
                var status = cb.checked ? 'concluida' : 'pendente';
                api('/atividades/' + encodeURIComponent(id), { method: 'PATCH', body: { status: status } })
                    .then(function () {
                        row.classList.toggle('crm-v3-ativ-concluida', cb.checked);
                        row.setAttribute('data-status', status);
                        var a = state.atividades.find(function (x) { return x.id === id; });
                        if (a) a.status = status;
                        updateDetailPanel(state.cliente);
                    })
                    .catch(function (err) { showToast(err.message, true); cb.checked = !cb.checked; });
            });
        });

        $$('.crm-v3-ativ-action', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var row = btn.closest('.crm-v3-ativ');
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

    function renderCotacoes() {
        var container = $('#crm-v3-cotacao-list');
        if (!container) return;
        updateTabCounts();
        if (!state.cotacoes.length) {
            container.innerHTML = '<div class="text-sm text-base-content/60 p-2">Nenhuma cotação.</div>';
            return;
        }
        container.innerHTML = state.cotacoes.map(function (c) {
            var titulo = c.nome_campanha || c.titulo || 'Cotação sem título';
            var numero = c.numero_cotacao || '';
            var periodo = [dataParaExibicao(c.periodo_inicio), dataParaExibicao(c.periodo_fim)].filter(Boolean).join(' – ');
            return (
                '<article class="crm-v3-cotacao-card p-2 border border-base-200 rounded-lg mb-2">' +
                '<div class="flex items-start gap-1"><div class="min-w-0 flex-1">' +
                (numero ? '<div class="crm-v3-cotacao-numero">' + escapeHtml(numero) + '</div>' : '') +
                '<div class="crm-v3-cotacao-titulo text-sm font-medium">' + escapeHtml(titulo) + '</div></div>' +
                '<div class="dropdown dropdown-end"><button type="button" class="btn btn-ghost btn-xs btn-square" tabindex="0" aria-label="Ações da cotação"><i class="fa-solid fa-ellipsis-vertical"></i></button>' +
                '<ul class="dropdown-content menu p-1 shadow bg-base-100 rounded-box w-32 border border-base-200 z-50 text-xs">' +
                '<li><button type="button" class="crm-v3-cotacao-edit" data-cotacao-id="' + escapeHtml(c.id) + '">Editar</button></li>' +
                '<li><button type="button" class="crm-v3-cotacao-delete text-error" data-cotacao-id="' + escapeHtml(c.id) + '">Excluir</button></li></ul></div></div>' +
                '<div class="crm-v3-cotacao-valor text-sm font-semibold">' + escapeHtml(c.valor) + '</div>' +
                '<div class="crm-v3-cotacao-meta flex items-center gap-2 mt-1">' +
                '<span class="' + badgeDaisy(c.status) + '">' + escapeHtml(c.status_label || c.status) + '</span>' +
                '<span class="crm-v3-cotacao-data text-xs text-base-content/60">' + escapeHtml(periodo || dataParaExibicao(c.data)) + '</span>' +
                '</div></article>'
            );
        }).join('');
        $$('.crm-v3-cotacao-edit', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-cotacao-id');
                openCotacaoModal(state.cotacoes.find(function (c) { return c.id === id; }));
            });
        });
        $$('.crm-v3-cotacao-delete', container).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-cotacao-id');
                api('/cotacoes/' + encodeURIComponent(id), { method: 'DELETE' })
                    .then(function () { showToast('Cotação excluída'); return loadCotacoes(state.clienteId); })
                    .catch(function (err) { showToast(err.message, true); });
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
        }).catch(function (err) {
            if (container) container.innerHTML = '<div class="crm-v3-contatos-empty p-3">Erro ao carregar contatos.</div>';
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
            var container = $('#crm-v3-lista-clientes');
            if (container) container.innerHTML = '<div class="crm-v3-contatos-empty p-3">Erro ao carregar clientes.</div>';
            showToast(err.message, true);
        });
    }

    function openContatoModal(contatoId) {
        if (!state.clienteId) {
            showToast('Selecione um cliente primeiro', true);
            return;
        }
        var form = $('#crm-v3-form-contato');
        var title = $('#crm-v3-modal-contato-title');
        if (!form) return;
        form.reset();
        $('#crm-v3-contato-id').value = contatoId || '';
        if (contatoId) {
            var c = state.contatos.find(function (x) { return x.id === contatoId; });
            if (!c) return;
            if (title) title.textContent = 'Editar contato';
            $('#crm-v3-contato-nome').value = c.nome;
            $('#crm-v3-contato-email').value = c.email;
            $('#crm-v3-contato-cargo').value = c.cargo || '';
            $('#crm-v3-contato-setor').value = c.setor || '';
            $('#crm-v3-contato-status').value = c.status || 'Ativo';
            $('#crm-v3-contato-telefone').value = c.telefone || '';
            $('#crm-v3-contato-telefone2').value = c.telefone_secundario || '';
            $('#crm-v3-contato-principal').checked = c.principal;
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
        if (cotacao) {
            $('#crm-v3-cotacao-titulo').value = cotacao.nome_campanha || cotacao.titulo || '';
            $('#crm-v3-cotacao-valor').value = cotacao.valor_total || cotacao.valor || '';
            $('#crm-v3-cotacao-status').value = cotacao.status || 'rascunho';
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
                    periodo_fim: $('#crm-v3-cotacao-fim').value
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

        var novaAtiv = $('#crm-v3-btn-nova-atividade');
        if (novaAtiv) novaAtiv.addEventListener('click', function () { openAtividadeModal(null); });

        var agendar = $('#crm-v3-btn-agendar');
        if (agendar) agendar.addEventListener('click', function () { openAtividadeModal(null); });

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
