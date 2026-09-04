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
        filtroPill: 'classif-ativo',
        filtroSecundario: '',
        filtroExecutivo: '',
        filtroTipo: '',
        filtroPerfil: '',
        filtroAtivResponsavel: '',
        filtroAtivTipo: '',
        buscaCliente: '',
        buscaAtividade: '',
        paginaCliente: 1,
        // Set/2026: subimos de 8 → 40 clientes por página. O time
        // pediu ver toda a base do executivo direto (~200 clientes)
        // sem paginar manualmente. A coluna tem overflow-y:auto, então
        // dá scroll suave e vem paginação só quando estoura ~40+ itens
        // no filtro atual.
        clientesPorPagina: 40,
        importRows: [],
        pendingObjetivoId: null,
        overlayTimer: null,
        // Cache do web-info por cliente. Chave = clienteId, valor =
        // registro do endpoint /web-info. Guardamos aqui para:
        //   (1) evitar refetch quando o usuário alterna entre tabs
        //       Info/Obj/Web do mesmo cliente;
        //   (2) usar o `logo_url` (og:image real) no header/cards no
        //       lugar da cascata frágil de favicons (Clearbit/Google).
        // Invalidação: qualquer POST /web-info/refresh substitui a
        // entrada. Trocar de cliente na coluna 1 não invalida (o
        // dicionário é por clienteId).
        webInfoCache: {}
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

    var CRM_MOBILE_MQ = window.matchMedia('(max-width: 767px)');

    function isMobileCrm() {
        return CRM_MOBILE_MQ.matches;
    }

    function clienteIdFromHash() {
        var m = String(location.hash || '').match(/^#cliente=([^&]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function setMobileView(view) {
        var page = $('.crm-v3-page');
        if (!page) return;
        if (!isMobileCrm() || !view) {
            page.classList.remove('is-mobile-list', 'is-mobile-detail');
            return;
        }
        page.classList.toggle('is-mobile-list', view === 'list');
        page.classList.toggle('is-mobile-detail', view === 'detail');
        if (view === 'detail') {
            window.scrollTo(0, 0);
        }
    }

    function syncClienteHash(clienteId, replace) {
        if (!isMobileCrm()) return;
        var next = clienteId ? '#cliente=' + encodeURIComponent(clienteId) : '';
        if (next === location.hash) return;
        var url = location.pathname + location.search + next;
        if (replace) history.replaceState({ crmV3: true }, '', url);
        else history.pushState({ crmV3: true }, '', url);
    }

    function openMobileList() {
        setMobileView('list');
        if (location.hash) {
            history.pushState({ crmV3: true }, '', location.pathname + location.search);
        }
        var ativo = $('#crm-v3-lista-clientes .crm-v3-cliente-ativo');
        if (ativo && ativo.scrollIntoView) ativo.scrollIntoView({ block: 'nearest' });
    }

    function applyMobileFromUrl() {
        if (!isMobileCrm()) {
            setMobileView(null);
            return;
        }
        var hid = clienteIdFromHash();
        if (hid) {
            if (String(state.clienteId) !== String(hid)) selectCliente(hid, { fromHistory: true });
            else setMobileView('detail');
        } else {
            setMobileView('list');
        }
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Flag global: uma vez que o backend retornar HTTP 503 com
    // `store_unavailable: true`, para de bombardear o usuário com
    // toasts a cada chamada seguinte e dá uma mensagem única e clara.
    var _storeUnavailableNotified = false;

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
                // 503 + store_unavailable: banco fora do ar em produção.
                // Não faz sentido tentar outras APIs — o CRM v3 não vai
                // funcionar até o Postgres voltar. Lançamos um erro
                // "silencioso" (marcado) para o caller decidir se mostra
                // ou não. O banner do template já explica a situação.
                if (res.status === 503 && data && data.store_unavailable) {
                    var err = new Error(data.error || 'Banco indisponível.');
                    err.storeUnavailable = true;
                    err.reason = data.reason;
                    err.dbError = data.db_error;
                    throw err;
                }
                if (!res.ok || data.success === false) {
                    throw new Error(data.error || 'Erro na requisição');
                }
                return data;
            });
        }).catch(function (err) {
            if (err instanceof TypeError) {
                throw new Error('Não foi possível conectar ao serviço.');
            }
            throw err;
        });
    }

    // Handler global para erros de "banco indisponível" — só mostra
    // toast uma vez por sessão. Chamado em pontos de entrada (carregar
    // clientes, atividades, cotações) que já detectam o err.storeUnavailable.
    function _handleStoreUnavailable(err) {
        if (!err || !err.storeUnavailable) return false;
        if (_storeUnavailableNotified) return true;
        _storeUnavailableNotified = true;
        var msg = 'Banco indisponível — CRM v3 não pode carregar dados. ' +
                  (err.dbError ? '(' + err.dbError + ')' : '');
        try {
            if (typeof showToast === 'function') showToast(msg, true);
        } catch (_) { /* noop */ }
        return true;
    }

    function formatarCep(value, whileTyping) {
        var d = String(value || '').replace(/\D/g, '').slice(0, 8);
        if (whileTyping && d.length <= 5) return d;
        if (d.length > 5) return d.slice(0, 5) + '-' + d.slice(5);
        return d;
    }

    function buscarEnderecoPorCep(cep) {
        var digits = String(cep || '').replace(/\D/g, '');
        if (digits.length !== 8) return Promise.resolve(null);
        return api('/cep/' + encodeURIComponent(digits)).then(function (resp) {
            return (resp && resp.data) || null;
        }).catch(function () { return null; });
    }

    function ufPorCapitalOperacao(cidade) {
        var key = String(cidade || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/\s+/g, ' ')
            .trim();
        if (key === 'belo horizonte') return 'MG';
        if (key === 'rio de janeiro') return 'RJ';
        if (key === 'sao paulo') return 'SP';
        return '';
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
    /**
     * Situação da próxima atividade — badge estilo Pipedrive.
     *
     * Set/2026: redesenhado para uma **bolinha circular** compacta
     * (22x22) com apenas o ícone dentro + tooltip completo no hover,
     * inspirada na coluna de atividades do Pipedrive. Antes era
     * ícone + label texto ("atrasado", "hoje"), o que criava dois
     * problemas: (a) ocupava largura demais na coluna 1 estreita
     * e (b) todos os clientes sem `badge` no backend caíam num
     * "—" cinza inútil.
     *
     * Fonte da verdade: `c.badge` (texto humanizado) e
     * `c.proxima_atividade` (objeto com data/título/dias). O backend
     * popula ambos em list_clientes → _metrics_for.
     *
     * Variantes visuais (ver crm_v3.css .crm-v3-sit--*):
     *   - atrasado : amarelo com !  → há atividade vencida
     *   - alert    : amarelo com !  → cliente SEM atividade agendada
     *   - hoje     : verde com sino → atividade prevista pra hoje
     *   - agenda   : azul com cal.  → atividade futura (amanhã / em N dias)
     *   - Se cliente é geladeira / sem info, retorna string vazia
     *     (sem badge — comportamento igual ao Pipedrive).
     */
    /** Situação comercial do card: atrasado | sem-atividade | agenda.
     *  NÃO usar `c.status` (boolean da ficha tbl_cliente.status). */
    function situacaoCliente(c) {
        var proxima = c.proxima_atividade;
        var badge = String(c.badge || '');
        var dias = proxima && proxima.dias != null ? Number(proxima.dias) : null;
        if ((dias != null && dias < 0) || /atrasad/i.test(badge)) return 'atrasado';
        if (/conclu/i.test(badge)) return 'concluida';
        if (!proxima || /sem atividade/i.test(badge)) return 'sem-atividade';
        return 'agenda';
    }

    function isoDateOnly(raw) {
        if (!raw) return '';
        var s = String(raw);
        return s.length >= 10 ? s.slice(0, 10) : s;
    }

    function diasAteIso(iso) {
        if (!iso || iso.length < 10) return null;
        var parts = iso.split('-');
        if (parts.length < 3) return null;
        var alvo = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        var hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        alvo.setHours(0, 0, 0, 0);
        return Math.round((alvo.getTime() - hoje.getTime()) / 86400000);
    }

    /** Recalcula badge do card a partir das atividades em memória. */
    function situacaoFromAtividades(atividades) {
        var atrasadas = [];
        var hojeList = [];
        var futuras = [];
        var temConcluida = false;
        (atividades || []).forEach(function (a) {
            if (!a) return;
            var status = String(a.status || '').toLowerCase();
            if (status === 'concluida') {
                temConcluida = true;
                return;
            }
            var iso = isoDateOnly(a.data_prazo || a.data);
            var dias = diasAteIso(iso);
            if (dias == null) return;
            var reg = {
                id: a.id,
                data: iso,
                titulo: (a.titulo || a.descricao || '').trim().slice(0, 120),
                dias: dias
            };
            if (dias < 0) atrasadas.push(reg);
            else if (dias === 0) hojeList.push(reg);
            else futuras.push(reg);
        });
        var proxima = null;
        if (atrasadas.length) {
            proxima = atrasadas.reduce(function (m, r) { return r.dias < m.dias ? r : m; });
        } else if (hojeList.length) {
            proxima = hojeList[0];
        } else if (futuras.length) {
            proxima = futuras.reduce(function (m, r) { return r.dias < m.dias ? r : m; });
        }
        if (!proxima) {
            return temConcluida
                ? { badge: 'Concluída', badge_type: 'success', proxima_atividade: null }
                : { badge: 'Sem atividade', badge_type: 'danger', proxima_atividade: null };
        }
        var d = proxima.dias;
        var badge;
        var badgeType;
        if (d < 0) {
            var abs = Math.abs(d);
            badge = abs === 1 ? '1 dia atrasado' : abs + ' dias atrasado';
            badgeType = 'warning';
        } else if (d === 0) {
            badge = 'Hoje';
            badgeType = 'success';
        } else if (d === 1) {
            badge = 'Amanhã';
            badgeType = 'info';
        } else {
            badge = 'Em ' + d + ' dias';
            badgeType = 'info';
        }
        return { badge: badge, badge_type: badgeType, proxima_atividade: proxima };
    }

    function syncClienteSituacao(clienteId, atividades) {
        if (!clienteId) return;
        var sit = situacaoFromAtividades(atividades || state.atividades);
        function patch(c) {
            if (!c) return;
            c.badge = sit.badge;
            c.badge_type = sit.badge_type;
            c.proxima_atividade = sit.proxima_atividade;
            if (!c.metrics) c.metrics = {};
            c.metrics.proxima_atividade = sit.proxima_atividade;
        }
        if (state.cliente && String(state.cliente.id) === String(clienteId)) {
            patch(state.cliente);
        }
        var idx = (state.clientes || []).findIndex(function (c) {
            return String(c.id) === String(clienteId);
        });
        if (idx !== -1) {
            patch(state.clientes[idx]);
            if (state.cliente && String(state.cliente.id) === String(clienteId)) {
                state.cliente = state.clientes[idx];
            }
        }
        updateClienteCardBadge(clienteId);
    }

    function findClienteCard(container, clienteId) {
        if (!container || clienteId == null) return null;
        var cards = container.querySelectorAll('.crm-v3-cliente[data-cliente-id]');
        for (var i = 0; i < cards.length; i++) {
            if (String(cards[i].getAttribute('data-cliente-id')) === String(clienteId)) {
                return cards[i];
            }
        }
        return null;
    }

    /** Atualiza só a classe ativa — evita reescrever a lista inteira ao clicar. */
    function updateClienteActiveCard() {
        var container = $('#crm-v3-lista-clientes');
        if (!container) return;
        $$('.crm-v3-cliente', container).forEach(function (card) {
            var ativo = String(card.getAttribute('data-cliente-id')) === String(state.clienteId);
            card.classList.toggle('crm-v3-cliente-ativo', ativo);
            card.setAttribute('aria-current', ativo ? 'page' : 'false');
        });
    }

    function updateClienteCardBadge(clienteId) {
        var container = $('#crm-v3-lista-clientes');
        if (!container || !clienteId) return;
        var card = findClienteCard(container, clienteId);
        if (!card) return;
        var c = (state.clientes || []).find(function (x) {
            return String(x.id) === String(clienteId);
        });
        if (!c) return;
        var right = card.querySelector('.crm-v3-cliente-right');
        if (right) right.innerHTML = situacaoHtml(c);
    }

    function updateClienteCardLogo(clienteId) {
        var container = $('#crm-v3-lista-clientes');
        if (!container || !clienteId) return;
        var card = findClienteCard(container, clienteId);
        if (!card) return;
        var c = (state.clientes || []).find(function (x) {
            return String(x.id) === String(clienteId);
        });
        if (!c) return;
        var src = logoRealDoCliente(c);
        if (!src) return;
        var wrap = card.querySelector('.crm-v3-card-logo-wrap');
        if (wrap) {
            var img = wrap.querySelector('img[data-crm-logo]');
            if (img && img.getAttribute('src') !== src) img.src = src;
            return;
        }
        card.insertAdjacentHTML('afterbegin', logoCardHtml(c));
        bindLogoImgs(card);
    }

    function bindClientesListDelegation() {
        var container = $('#crm-v3-lista-clientes');
        if (!container || container._crmV3ListBound) return;
        container._crmV3ListBound = true;
        container.addEventListener('click', function (e) {
            var card = e.target.closest('.crm-v3-cliente[data-cliente-id]');
            if (!card || !container.contains(card)) return;
            selectCliente(card.getAttribute('data-cliente-id'));
        });
        container.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            var card = e.target.closest('.crm-v3-cliente[data-cliente-id]');
            if (!card || !container.contains(card)) return;
            e.preventDefault();
            selectCliente(card.getAttribute('data-cliente-id'));
        });
    }

    function bindLogoImgs(root) {
        $$('img[data-crm-logo]', root || document).forEach(function (img) {
            function reveal() {
                if (!img.naturalWidth) return;
                img.hidden = false;
                var ini = img.previousElementSibling;
                if (ini) ini.style.display = 'none';
                var wrap = img.closest('.crm-v3-card-logo-wrap');
                if (wrap) wrap.hidden = false;
            }
            img.addEventListener('load', reveal);
            img.addEventListener('error', function () {
                img.hidden = true;
                var wrap = img.closest('.crm-v3-card-logo-wrap');
                if (wrap) wrap.hidden = true;
            });
            if (img.complete) reveal();
        });
    }

    function situacaoHtml(c) {
        var badge = c.badge || '';
        if (!badge) return '';

        var proxima = c.proxima_atividade || null;
        var m = badge.match(/(\d+)\s*dias?/i);
        var dias = m ? m[1] : '';
        var icon, variante, title;

        if (/sem atividade/i.test(badge)) {
            // Cliente SEM atividade pendente — no Pipedrive isso aparece
            // como bolinha âmbar com "!" indicando que o executivo
            // precisa marcar próximo passo. Não é erro, é chamado à ação.
            icon = 'fa-solid fa-exclamation';
            variante = 'alert';
            title = 'Sem atividade agendada · marque um próximo passo';
        } else if (/conclu/i.test(badge)) {
            icon = 'fa-solid fa-check';
            variante = 'ok';
            title = 'Atividades em dia';
        } else if (/atrasad/i.test(badge)) {
            icon = 'fa-solid fa-exclamation';
            variante = 'atrasado';
            title = (proxima && proxima.titulo)
                ? proxima.titulo + ' · ' + badge.toLowerCase()
                : badge.charAt(0).toUpperCase() + badge.slice(1);
        } else if (/^hoje/i.test(badge)) {
            icon = 'fa-solid fa-bell';
            variante = 'hoje';
            title = (proxima && proxima.titulo)
                ? proxima.titulo + ' · hoje'
                : 'Atividade agendada para hoje';
        } else if (/^amanh/i.test(badge)) {
            icon = 'fa-regular fa-calendar';
            variante = 'agenda';
            title = (proxima && proxima.titulo)
                ? proxima.titulo + ' · amanhã'
                : 'Atividade agendada para amanhã';
        } else if (/^em\s+\d+/i.test(badge)) {
            icon = 'fa-regular fa-calendar';
            variante = 'agenda';
            title = (proxima && proxima.titulo)
                ? proxima.titulo + ' · em ' + dias + ' dias'
                : 'Atividade em ' + dias + ' dias';
        } else if (/novo/i.test(badge)) {
            icon = 'fa-solid fa-sparkles';
            variante = 'agenda';
            title = 'Cliente novo';
        } else {
            return '';
        }
        return (
            '<span class="crm-v3-sit crm-v3-sit--' + variante + '"' +
            ' title="' + escapeHtml(title) + '"' +
            ' aria-label="' + escapeHtml(title) + '">' +
            '<i class="' + icon + '" aria-hidden="true"></i>' +
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

    function logoCardHtml(c) {
        var src = logoRealDoCliente(c);
        if (!src) return '';
        return (
            '<div class="crm-v3-card-logo-wrap" hidden>' +
            '<img class="crm-v3-card-logo" alt="" hidden data-crm-logo="1" src="' + escapeHtml(src) + '" />' +
            '</div>'
        );
    }

    function avatarHtml(nome, sizeClass, dominio, clienteId, webLogoUrl) {
        sizeClass = sizeClass || 'w-7 h-7';
        var tone = avatarTone(nome);
        var ini = avatarIniciais(nome);
        var bg = tone === 'primary' ? 'bg-primary text-primary-content' : 'bg-neutral text-neutral-content';
        // Ordem de preferência:
        // 1) `webLogoUrl` / og:image do scrape
        // 2) webInfoCache.logo_url
        // Sem logo real: só iniciais. Não usar Clearbit/Google/DDG
        // (globo genérico).
        var srcPrincipal = '';
        if (webLogoUrl) {
            srcPrincipal = webLogoUrl;
        }
        if (!srcPrincipal && clienteId && state.webInfoCache) {
            var wi = state.webInfoCache[clienteId] || state.webInfoCache[String(clienteId)];
            if (wi && wi.status === 'ok' && wi.logo_url) {
                srcPrincipal = wi.logo_url;
            }
        }
        var imgHtml = '';
        if (srcPrincipal) {
            imgHtml =
                '<img class="crm-v3-card-logo" alt="" hidden data-crm-logo="1" ' +
                'src="' + escapeHtml(srcPrincipal) + '" />';
        }
        return (
            '<div class="avatar placeholder crm-v3-card-avatar">' +
            '<div class="rounded-full ' + sizeClass + ' ' + bg + ' crm-v3-card-avatar-inner">' +
            '<span class="text-xs font-semibold">' + escapeHtml(ini) + '</span>' +
            imgHtml +
            '</div></div>'
        );
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

    /**
     * Formata uma data ISO 8601 (com ou sem hora) em rótulo humano.
     * - Hoje / Ontem / Nd atrás (até 7 dias) / dd/MM/yyyy.
     * Usada no header do CRM v3 para "Última atualização".
     */
    function formatarDataRelativa(valor) {
        if (!valor) return '';
        var s = String(valor);
        // Aceita 'YYYY-MM-DD' ou ISO com T; extrai a data.
        var iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!iso) return dataParaExibicao(s);
        var d = new Date(iso[1] + '-' + iso[2] + '-' + iso[3] + 'T00:00:00');
        if (isNaN(d.getTime())) return dataParaExibicao(s);
        var hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        var diff = Math.round((hoje.getTime() - d.getTime()) / 86400000);
        if (diff === 0) return 'Hoje';
        if (diff === 1) return 'Ontem';
        if (diff > 1 && diff <= 7) return diff + ' dias atrás';
        return iso[3] + '/' + iso[2] + '/' + iso[1];
    }

    /**
     * Formata uma data em rótulo "há N unidade(s)" cobrindo dias,
     * semanas, meses e anos. Usado nos campos "Criado em" e
     * "Atualizado em" da sidebar Info, onde antes aparecia o ISO cru
     * (ex.: "2025-08-28T23:05:54.515997") porque `dataParaExibicao`
     * só sabia lidar com "YYYY-MM-DD" e devolvia a string sem casar
     * o regex.
     *
     * Aceita:
     * - "YYYY-MM-DD"
     * - "YYYY-MM-DDTHH:MM:SS[.fff]" (Postgres/JSON)
     * - "dd/MM/yyyy" (fallback pt-BR já formatado)
     *
     * Regra de arredondamento (compatível com o "sentir intuitivo"
     * pt-BR que o usuário pediu):
     *   0 dias   → "hoje"
     *   1 dia    → "ontem"
     *   2-6 dias → "há N dias"
     *   7-29 d   → "há N semanas"     (N = round(dias/7), mín 1)
     *   30-59 d  → "há 1 mês"
     *   60-364 d → "há N meses"       (N = round(dias/30))
     *   365-729d → "há 1 ano"
     *   730+ dias→ "há N anos"        (N = floor(dias/365))
     */
    function formatarHaTempo(valor) {
        if (!valor) return '—';
        var s = String(valor);
        var iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
        var d;
        if (iso) {
            d = new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
        } else {
            var br = s.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
            if (br) {
                d = new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1]));
            }
        }
        if (!d || isNaN(d.getTime())) return '—';
        var hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        d.setHours(0, 0, 0, 0);
        var diff = Math.round((hoje.getTime() - d.getTime()) / 86400000);
        // Datas futuras (raras) — mostra "em breve" para não devolver
        // "há -3 dias".
        if (diff < 0) return 'em breve';
        if (diff === 0) return 'hoje';
        if (diff === 1) return 'ontem';
        if (diff < 7) return 'há ' + diff + ' dias';
        if (diff < 30) {
            var semanas = Math.round(diff / 7);
            if (semanas < 1) semanas = 1;
            return 'há ' + semanas + (semanas === 1 ? ' semana' : ' semanas');
        }
        if (diff < 60) return 'há 1 mês';
        if (diff < 365) {
            var meses = Math.round(diff / 30);
            return 'há ' + meses + ' meses';
        }
        if (diff < 730) return 'há 1 ano';
        var anos = Math.floor(diff / 365);
        return 'há ' + anos + ' anos';
    }

    function parseDataValor(valor) {
        var s = String(valor || '').trim();
        if (!s) return null;
        var m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?/);
        if (m) {
            return {
                date: new Date(
                    Number(m[1]), Number(m[2]) - 1, Number(m[3]),
                    Number(m[4] || 0), Number(m[5] || 0), Number(m[6] || 0)
                ),
                hasTime: !!m[4]
            };
        }
        var br = s.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        if (br) {
            return {
                date: new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1])),
                hasTime: false
            };
        }
        var d = new Date(s);
        if (isNaN(d.getTime())) return null;
        return { date: d, hasTime: true };
    }

    function formatarAtualizadoHa(valor) {
        var parsed = parseDataValor(valor);
        if (!parsed || isNaN(parsed.date.getTime())) return '';
        if (parsed.hasTime) {
            var mins = Math.floor((Date.now() - parsed.date.getTime()) / 60000);
            if (mins < 0) mins = 0;
            if (mins < 1) return 'Atualizado agora';
            if (mins < 60) return 'Atualizado há ' + mins + ' min';
            var horas = Math.floor(mins / 60);
            if (horas < 24) return 'Atualizado há ' + horas + ' h';
        }
        var rel = formatarHaTempo(valor);
        if (!rel || rel === '—') return '';
        if (rel === 'hoje') return 'Atualizado hoje';
        if (rel === 'ontem') return 'Atualizado ontem';
        if (rel.indexOf('há') === 0 || rel.indexOf('em ') === 0) return 'Atualizado ' + rel;
        return 'Atualizado ' + rel;
    }

    /**
     * Deriva o domínio de e-mail do contato principal (ou primeiro
     * contato com e-mail) do cliente selecionado. Usado como chave para
     * a Clearbit Logo API — retorna string vazia quando não há e-mail
     * disponível. Ignora domínios de webmail comuns porque geram
     * logos de gmail.com / hotmail.com em vez do cliente.
     */
    var _AVATAR_DOMINIOS_IGNORADOS = new Set([
        'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com',
        'yahoo.com.br', 'live.com', 'icloud.com', 'me.com',
        'terra.com.br', 'uol.com.br', 'bol.com.br', 'msn.com'
    ]);
    function extrairDominioContato(cliente) {
        var lista = Array.isArray(state.contatos) ? state.contatos : [];
        if (!lista.length) return '';
        // Ordena: principal primeiro; depois só quem tem e-mail.
        var ordenados = lista.slice().sort(function (a, b) {
            var pa = a && a.principal ? -1 : 0;
            var pb = b && b.principal ? -1 : 0;
            return pa - pb;
        });
        for (var i = 0; i < ordenados.length; i++) {
            var email = (ordenados[i] && ordenados[i].email || '').trim().toLowerCase();
            var at = email.indexOf('@');
            if (at <= 0 || at === email.length - 1) continue;
            var dominio = email.slice(at + 1).replace(/[\s>]+$/, '');
            if (!dominio || _AVATAR_DOMINIOS_IGNORADOS.has(dominio)) continue;
            return dominio;
        }
        return '';
    }

    // Normaliza qualquer input do usuário ("https://Cliente.com.br/#a")
    // para um domínio limpo pronto para o Clearbit.
    function normalizarDominio(raw) {
        if (!raw) return '';
        var s = String(raw).trim().toLowerCase();
        if (!s) return '';
        // Remove protocolo, "www." e paths/queries/hashes.
        s = s.replace(/^[a-z]+:\/\//, '');
        if (/^www(?!\.)/i.test(s)) s = 'www.' + s.slice(3);
        s = s.replace(/^www\./, '');
        s = s.split('/')[0].split('?')[0].split('#')[0];
        // Valida shape mínimo: precisa ter pelo menos um ponto e nenhum espaço.
        if (!s || s.indexOf('.') === -1 || /\s/.test(s)) return '';
        return s;
    }

    /**
     * Retorna o domínio a ser usado como fonte do logo do cliente,
     * na seguinte ordem de prioridade (set/2026):
     *   1. `cliente.site_url` salvo em tbl_cliente (confirmado pelo usuário).
     *   2. Domínio inferido do e-mail do contato principal (fallback
     *      automático).
     * Retorna string vazia se nenhuma fonte válida existir — nesse caso
     * o avatar mostra iniciais.
     */
    function dominioConfirmado(cliente) {
        var salvo = normalizarDominio(cliente && cliente.site_url);
        if (salvo) return salvo;
        var cid = cliente && cliente.id;
        var wi = cid != null ? (state.webInfoCache[cid] || state.webInfoCache[String(cid)]) : null;
        return normalizarDominio(wi && wi.dominio);
    }

    /** Domínio visível no editor Web / cache — o que o executivo já vê. */
    function dominioNaTela(cliente) {
        var d = dominioConfirmado(cliente);
        if (d) return d;
        var confirmed = $('#crm-v3-site-confirmed-domain');
        d = normalizarDominio(confirmed && confirmed.textContent);
        if (d) return d;
        var inp = $('#crm-v3-site-input');
        d = normalizarDominio(inp && inp.value);
        if (d) return d;
        var hero = $('#crm-v3-web-domain span');
        d = normalizarDominio(hero && hero.textContent);
        if (d) return d;
        return extrairDominioContato(cliente);
    }

    function logoRealDoCliente(cliente) {
        if (cliente && cliente.web_logo_url) return cliente.web_logo_url;
        var cid = cliente && cliente.id;
        var wi = cid != null && state.webInfoCache
            ? (state.webInfoCache[cid] || state.webInfoCache[String(cid)])
            : null;
        if (wi && wi.status === 'ok' && wi.logo_url) return wi.logo_url;
        return '';
    }

    function dominioParaLogo(cliente) {
        var salvo = dominioConfirmado(cliente);
        if (salvo) return salvo;
        return extrairDominioContato(cliente);
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
        // Popula qualquer <select data-lookup=""> DENTRO do modal usando
        // o cache central de lookups (tipos_cliente, estados, executivos
        // reais, etc). Antes esses combos tinham options hardcoded
        // ("Luisa Santana", "João Paulo") — set/2026.
        try {
            if (window.crmV3Drawer && window.crmV3Drawer.lookups) {
                window.crmV3Drawer.lookups.applyToRoot(dialog);
            }
        } catch (_) { /* fallback silencioso: options ficam como placeholders */ }
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
            var sitFiltro = state.filtroSecundario || '';
            // Arquivo = Geladeira. Classificação Ativo/Prospecção não se aplica.
            if (sitFiltro === 'arquivo') {
                if (!isGeladeira) return false;
            } else {
                if (isGeladeira) return false;
                if (state.filtroPill === 'classif-ativo') {
                    if (classif !== 'ativo') return false;
                } else if (state.filtroPill === 'classif-prospeccao') {
                    var isProsp = classif === 'prospeccao'
                        || classif === 'prospecção'
                        || classif.indexOf('prospec') === 0;
                    if (!isProsp) return false;
                }
                if (sitFiltro === 'atrasado' && situacaoCliente(c) !== 'atrasado') return false;
                if (sitFiltro === 'sem-atividade' && situacaoCliente(c) !== 'sem-atividade') return false;
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

        // Função para renderizar um card de cliente
        function renderClienteCard(c) {
            var ativo = c.id === state.clienteId;
            var classificacao = c.classificacao_cliente || c.classificacao || '';
            var isAgencia = !!c.is_agencia;
            var agenciaNome = '';
            var vinculos = Array.isArray(c.agencias_vinculadas) ? c.agencias_vinculadas : [];
            var principal = vinculos.filter(function (v) { return v && v.is_principal; })[0] || vinculos[0];
            if (principal) agenciaNome = principal.nome || '';

            var subText = c.sub || '';
            if (agenciaNome && !isAgencia) {
                subText = agenciaNome;
            }

            // Linha de metadados compacta abaixo do nome — set/2026.
            // Motivação (imagem-referência do usuário): os cards antes
            // ficavam só com nome+badge, deixando o executivo sem
            // contexto para escolher qual cliente abrir. Agora damos
            // 2-3 chips relevantes que respondem "vale abrir?":
            //   - Cotações abertas (destaque azul, priorizado)
            //   - Contatos (com destaque quando é 0 = "precisa
            //     cadastrar gente")
            //   - Último contato (relativo, ex.: "3d atrás")
            //   - Localização (fallback quando não há métricas)
            // Ordem/limite baseado em prioridade comercial: sinal de
            // pipeline > histórico > geografia. Máx. 3 itens para
            // caber em 1 linha na coluna estreita.
            var m = c.metrics || {};
            var metaChips = [];

            // 1) Cotações em andamento — mais crítico para o comercial.
            var cotAbertas = Number(m.cotacoes_abertas || 0);
            if (cotAbertas > 0) {
                metaChips.push({
                    icon: 'fa-file-lines',
                    text: cotAbertas + (cotAbertas === 1 ? ' cot.' : ' cots.'),
                    cls: 'is-cot',
                    title: cotAbertas === 1
                        ? '1 cotação em andamento'
                        : cotAbertas + ' cotações em andamento'
                });
            }

            // 2) Contatos — número com aviso visual quando é zero
            //    ("0 contatos" em vermelho suave = ação recomendada:
            //    cadastrar gente).
            var contatos = Number(m.contatos_total || m.contatos || c.qtd_contatos || 0);
            if (contatos > 0) {
                metaChips.push({
                    icon: 'fa-user-group',
                    text: contatos,
                    title: contatos === 1
                        ? '1 contato cadastrado'
                        : contatos + ' contatos cadastrados'
                });
            } else {
                metaChips.push({
                    icon: 'fa-user-slash',
                    text: '0',
                    cls: 'is-warn',
                    title: 'Nenhum contato cadastrado — considere adicionar um contato'
                });
            }

            // 3) Último contato — só quando existe registro real.
            //    m.ultimo_contato vem já formatado do backend
            //    ("Hoje" / "Ontem" / "12d atrás") — só normalizamos
            //    para minúscula para casar com o visual "há X dias".
            var uc = String(m.ultimo_contato || '').trim();
            if (uc && uc !== '—' && metaChips.length < 3) {
                metaChips.push({
                    icon: 'fa-clock-rotate-left',
                    text: uc.toLowerCase(),
                    cls: 'is-muted',
                    title: 'Última interação: ' + uc
                });
            }

            // 4) Fallback: localização (cidade/UF). Só usa se sobrou
            //    espaço nos 3 slots — informação de contexto, não é
            //    ação. Ex.: quando um cliente novo ainda não tem
            //    contatos nem cotações mas tem endereço cadastrado.
            if (metaChips.length < 3) {
                var loc = '';
                if (c.cidade) loc = c.cidade;
                if (c.uf) loc += (loc ? '/' : '') + c.uf;
                if (loc) {
                    metaChips.push({
                        icon: 'fa-location-dot',
                        text: loc,
                        cls: 'is-muted',
                        title: 'Localização: ' + loc
                    });
                }
            }

            var metaHtml = metaChips.length
                ? '<div class="crm-v3-cliente-meta">' +
                  metaChips.map(function (chip) {
                      return '<span class="crm-v3-cliente-meta-chip' +
                          (chip.cls ? ' ' + chip.cls : '') + '"' +
                          ' title="' + escapeHtml(chip.title) + '">' +
                          '<i class="fa-solid ' + chip.icon + '" aria-hidden="true"></i>' +
                          '<span>' + escapeHtml(String(chip.text)) + '</span>' +
                          '</span>';
                  }).join('') +
                  '</div>'
                : '';

            return (
                '<div class="crm-v3-cliente' + (ativo ? ' crm-v3-cliente-ativo' : '') + '"' +
                ' role="listitem" tabindex="0"' +
                ' data-cliente-id="' + escapeHtml(c.id) + '"' +
                ' data-status="' + escapeHtml(c.status) + '"' +
                ' data-classificacao="' + escapeHtml(classificacao) + '"' +
                ' aria-current="' + (ativo ? 'page' : 'false') + '">' +
                logoCardHtml(c) +
                '<div class="crm-v3-cliente-info min-w-0 flex-1">' +
                '<div class="crm-v3-cliente-headline">' +
                '<div class="crm-v3-cliente-nome" title="' + escapeHtml(c.nome) + '">' + escapeHtml(c.nome) + '</div>' +
                '</div>' +
                (subText ? '<div class="crm-v3-cliente-sub" title="' + escapeHtml(subText) + '">' + escapeHtml(subText) + '</div>' : '') +
                metaHtml +
                '</div>' +
                '<div class="crm-v3-cliente-right shrink-0">' +
                situacaoHtml(c) +
                '</div></div>'
            );
        }

        // Agrupar por classificação quando filtro = todos
        var mostrarGrupos = state.filtroPill === 'todos';
        var html = '';

        if (mostrarGrupos) {
            // Separar em grupos: Ativo, Prospecção
            var grupos = {
                'Ativo': [],
                'Prospecção': []
            };
            pagina.forEach(function (c) {
                var classif = String(c.classificacao_cliente || c.classificacao || '').toLowerCase();
                if (classif === 'ativo') {
                    grupos['Ativo'].push(c);
                } else {
                    grupos['Prospecção'].push(c);
                }
            });

            // Renderizar cada grupo com header
            ['Ativo', 'Prospecção'].forEach(function (grupoNome) {
                var clientes = grupos[grupoNome];
                if (clientes.length) {
                    html += '<div class="crm-v3-cliente-grupo">' +
                        '<div class="crm-v3-cliente-grupo-header">' +
                        '<span class="crm-v3-cliente-grupo-label">' + grupoNome + '</span>' +
                        '<span class="crm-v3-cliente-grupo-count">' + clientes.length + '</span>' +
                        '</div>' +
                        clientes.map(renderClienteCard).join('') +
                        '</div>';
                }
            });
        } else {
            // Sem agrupamento
            html = pagina.map(renderClienteCard).join('');
        }

        container.innerHTML = html;
        bindLogoImgs(container);
    }

    function updateTabCounts() {
        // Contadores da sidebar principal. Em set/2026 foram consolidadas
        // as abas "Atividades" (redundante com a coluna central) e
        // "Notas" (agora vive dentro da aba Info). Só sobrou "Objetivos".
        // Contador de notas continua sendo atualizado num badge inline
        // no título da seção "Notas" (crm-v3-notas-count-inline).
        var counts = {
            objetivos: (state.objetivos || []).length,
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
        var counts = {
            'classif-ativo': 0,
            'classif-prospeccao': 0,
            atrasado: 0,
            'sem-atividade': 0,
            arquivo: 0
        };
        base.forEach(function (c) {
            var classif = String(c.classificacao_cliente || c.classificacao || '').toLowerCase();
            var isGeladeira = classif === 'geladeira';
            if (isGeladeira) {
                counts.arquivo++;
                return;
            }
            var isAtivo = classif === 'ativo';
            var isProsp = classif === 'prospeccao'
                || classif === 'prospecção'
                || classif.indexOf('prospec') === 0;
            if (isAtivo) counts['classif-ativo']++;
            if (isProsp) counts['classif-prospeccao']++;
            // Contagens secundárias no recorte da classificação ativa
            // (Ativos ou Prospecção), para o número bater com a lista.
            var noRecorte = (state.filtroPill === 'classif-prospeccao') ? isProsp : isAtivo;
            if (noRecorte) {
                var sit = situacaoCliente(c);
                if (sit === 'atrasado') counts.atrasado++;
                if (sit === 'sem-atividade') counts['sem-atividade']++;
            }
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
        // Set/2026: com clientesPorPagina=40 a paginação some quase
        // sempre. Escondemos o rodapé inteiro quando cabe em 1 página
        // para dar mais espaço para a lista respirar.
        var pager = document.getElementById('crm-v3-pager');
        if (pager) pager.hidden = totalPaginas <= 1;
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

        var cotacoes = Array.isArray(state.cotacoes) ? state.cotacoes : [];
        var cotAbertas = cotacoes.filter(cotacaoEstaAberta);
        var cotAprovadas = cotacoes.filter(function (c) {
            return String(c.status || '').toLowerCase() === 'aprovada';
        });
        var oportunidades = cotAbertas.length;
        var faturamento = cotAprovadas.reduce(function (s, c) { return s + _cotValor(c); }, 0);
        var pipeline = cotAbertas.reduce(function (s, c) { return s + _cotValor(c); }, 0);
        if (!cotacoes.length) {
            if (fallback.oportunidades != null) oportunidades = fallback.oportunidades;
        }
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

        // Logo: só aparece com og:image válido. Sem logo o slot some
        // para o nome alinhar à esquerda (iniciais no header não ajudam).
        var wrap = $('#crm-v3-detail-avatar-wrap');
        var img = $('#crm-v3-detail-avatar-img');
        var logoCanonico = logoRealDoCliente(cliente) || '';
        if (wrap) wrap.hidden = !logoCanonico;
        if (img) {
            img.hidden = true;
            img.removeAttribute('src');
            img.alt = '';
            img.onload = null;
            img.onerror = null;
            if (logoCanonico) {
                img.onload = function () {
                    if (!img.naturalWidth || !img.naturalHeight) {
                        img.hidden = true;
                        if (wrap) wrap.hidden = true;
                        return;
                    }
                    img.hidden = false;
                    if (wrap) wrap.hidden = false;
                };
                img.onerror = function () {
                    img.hidden = true;
                    if (wrap) wrap.hidden = true;
                };
                img.src = logoCanonico;
            }
        }

        // Meta — todos os campos aqui vêm da base real (backend).
        var metaResp = $('#crm-v3-meta-responsavel');
        if (metaResp) metaResp.textContent = cliente.responsavel || '—';

        var metaCat = $('#crm-v3-meta-categoria');
        if (metaCat) metaCat.textContent = cliente.tipo || cliente.categoria || '—';

        // Substitui a "Prioridade" (mock) por Classificação (real).
        var classifWrap = $('#crm-v3-meta-classif-wrap');
        var classifChip = $('#crm-v3-meta-classif');
        var classif = cliente.classificacao_cliente || cliente.classificacao || '';
        if (classifWrap) classifWrap.hidden = !classif;
        if (classifChip) {
            classifChip.textContent = classif || '—';
            classifChip.setAttribute('data-classif', classif);
        }

        // Atualizado há N min / h / dias — data_modificacao com hora.
        var metaDate = $('#crm-v3-meta-date');
        var metaDateText = $('#crm-v3-meta-date-text');
        if (metaDate) {
            var rel = formatarAtualizadoHa(cliente.data_modificacao);
            if (metaDateText) metaDateText.textContent = rel;
            else metaDate.textContent = rel;
            metaDate.hidden = !rel;
            if (rel && cliente.data_modificacao) {
                metaDate.title = String(cliente.data_modificacao);
            } else {
                metaDate.removeAttribute('title');
            }
        }

        // Aba Info — populada pelo backend (`_map_cliente` do repositório
        // real) e enriquecida ao vivo pelos edit-in-place (initInfoEditable).
        // Read-only fields são setados via textContent; editáveis passam
        // por `setEditableDisplay` que aplica classe `.is-empty` e
        // placeholder quando o valor vem vazio (Pipedrive-style).
        var setText = function (sel, val) {
            var el = $(sel);
            if (el) el.textContent = (val == null || val === '') ? '—' : val;
        };
        setText('#crm-v3-info-categoria', cliente.tipo_label);
        setText('#crm-v3-info-tipo', cliente.tipo || cliente.categoria);
        // Datas de auditoria em formato relativo pt-BR ("há 6 meses",
        // "há 1 ano"). O ISO cru (ex.: 2025-08-28T23:05:54.515997)
        // fica no atributo title para quem quiser o valor exato via
        // hover. Antes ficava visível na tela — feio e sem valor
        // executivo. Ver `formatarHaTempo` para as faixas.
        var setDataRelativa = function (sel, val) {
            var el = $(sel);
            if (!el) return;
            if (val == null || val === '') {
                el.textContent = '—';
                el.removeAttribute('title');
                return;
            }
            el.textContent = formatarHaTempo(val);
            el.setAttribute('title', String(val));
        };
        setDataRelativa('#crm-v3-info-criado', cliente.data_cadastro);
        setDataRelativa('#crm-v3-info-atualizado', cliente.data_modificacao);
        setText('#crm-v3-info-uf', cliente.uf);

        // Perfil comercial — formatação amigável para o display.
        var fmtPct = function (v) {
            var n = parseFloat(v);
            if (!isFinite(n) || n === 0) return '';
            return n.toFixed(2).replace('.', ',') + '%';
        };
        var yesno = function (v) { return v ? 'Sim' : 'Não'; };

        // Campos editáveis: propagam o valor real via helper.
        setEditableDisplay('#crm-v3-info-classificacao',
            cliente.classificacao_cliente || cliente.classificacao);
        setEditableDisplay('#crm-v3-info-cnpj', cliente.cnpj);
        setEditableDisplay('#crm-v3-info-cidade-only', cliente.cidade);
        setEditableDisplay('#crm-v3-info-bv', fmtPct(cliente.bv_percentual));
        setEditableDisplay('#crm-v3-info-margem', fmtPct(cliente.margem_cc));
        setEditableDisplay('#crm-v3-info-opera', yesno(cliente.opera_midia), { alwaysFilled: true });
        setEditableDisplay('#crm-v3-info-demanda-dados', yesno(cliente.demanda_dados), { alwaysFilled: true });
        setEditableDisplay('#crm-v3-info-demanda-prog', yesno(cliente.demanda_programatica_canais), { alwaysFilled: true });
        setEditableDisplay('#crm-v3-info-obs', cliente.observacoes_comerciais_adicionais);
        // Endereço
        setEditableDisplay('#crm-v3-info-cep', cliente.cep || (cliente.endereco && cliente.endereco.cep));
        setEditableDisplay('#crm-v3-info-bairro', cliente.bairro || (cliente.endereco && cliente.endereco.bairro));
        setEditableDisplay('#crm-v3-info-logradouro', cliente.logradouro || (cliente.endereco && cliente.endereco.logradouro));
        setEditableDisplay('#crm-v3-info-numero', cliente.numero || (cliente.endereco && cliente.endereco.numero));
        setEditableDisplay('#crm-v3-info-complemento', cliente.complemento || (cliente.endereco && cliente.endereco.complemento));
        // Campo "Nota do executivo" (tbl_cliente.nota_executivo_vendas)
        // removido da UI em set/2026 — o histórico de notas
        // (sales_historico_cliente) é a fonte única. A coluna continua
        // no banco por retrocompat, mas ninguém edita mais por aqui.

        var responsavelNome = $('#crm-v3-responsavel-nome');
        var responsavelAvatar = $('#crm-v3-responsavel-avatar');
        var responsavelEmail = $('#crm-v3-responsavel-email');
        if (responsavelNome) responsavelNome.textContent = cliente.responsavel || '—';
        if (responsavelAvatar) responsavelAvatar.textContent = avatarIniciais(cliente.responsavel);
        if (responsavelEmail) {
            // Prefere email real (tbl_contato_cliente.email do executivo).
            // Fallback: derivar de "nome.sobrenome@centralcomm.media" — só se
            // o email real não estiver disponível na base.
            var emailReal = (cliente.responsavel_email || '').trim();
            if (emailReal) {
                responsavelEmail.textContent = emailReal;
            } else if (cliente.responsavel) {
                responsavelEmail.textContent = cliente.responsavel
                    .toLowerCase()
                    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
                    .replace(/\s+/g, '.') + '@centralcomm.media';
            } else {
                responsavelEmail.textContent = '—';
            }
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

        updateVinculos(cliente);
        // Editor de "Site & logo" na sidebar — hidrata com valor salvo
        // ou domínio inferido do contato e prepara o preview do logo.
        renderSiteEditor(cliente);
    }

    /**
     * Hidrata o editor de "Site & logo" (sidebar Info) para o cliente
     * atual. Mostra o valor salvo em `cliente.site_url`; se estiver
     * vazio, sugere o domínio inferido do contato principal como
     * placeholder editável. O preview do logo usa o mesmo Clearbit do
     * header e cai em iniciais quando falha.
     */
    function renderSiteEditor(cliente) {
        var editor = $('#crm-v3-site-editor');
        var input = $('#crm-v3-site-input');
        var hint = $('#crm-v3-site-hint');
        var confirmar = $('#crm-v3-site-confirmar');
        var limpar = $('#crm-v3-site-limpar');
        var openA = $('#crm-v3-site-open');
        var img = $('#crm-v3-site-logo-img');
        var fallback = $('#crm-v3-site-logo-fallback');
        var confirmed = $('#crm-v3-site-confirmed');
        var confirmedDom = $('#crm-v3-site-confirmed-domain');
        if (!input || !confirmar) return;

        var salvo = dominioConfirmado(cliente);
        var inferido = extrairDominioContato(cliente);
        var valorEfetivo = salvo || inferido || '';
        input.value = valorEfetivo;
        input.placeholder = inferido
            ? ('ex.: ' + inferido)
            : 'ex.: cliente.com.br';
        if (!salvo && inferido) {
            input.dataset.autoFill = inferido;
            input.classList.add('is-auto-fill');
        } else {
            delete input.dataset.autoFill;
            input.classList.remove('is-auto-fill');
        }

        if (editor) editor.classList.toggle('is-confirmed', !!salvo);
        if (confirmed) confirmed.hidden = !salvo;
        if (confirmedDom) confirmedDom.textContent = salvo || '';

        if (hint) {
            if (salvo) {
                hint.className = 'crm-v3-site-hint crm-v3-site-hint-ok';
                hint.innerHTML = '<i class="fa-solid fa-circle-check" aria-hidden="true"></i> Site confirmado.';
            } else if (inferido) {
                hint.className = 'crm-v3-site-hint';
                hint.innerHTML = '<i class="fa-regular fa-lightbulb" aria-hidden="true"></i> Sugestão do contato: <strong>' + escapeHtml(inferido) + '</strong>. Confirme ou edite.';
                _atualizarPreviewSite(inferido, img, fallback, cliente);
            } else {
                hint.className = 'crm-v3-site-hint';
                hint.innerHTML = '<i class="fa-regular fa-lightbulb" aria-hidden="true"></i> Informe o domínio para aplicar o logo e buscar o site.';
            }
        }

        if (salvo) _atualizarPreviewSite(salvo, img, fallback, cliente);
        else if (!inferido) _mostrarSiteFallback(img, fallback, cliente);

        confirmar.disabled = !salvo && !inferido;
        confirmar.dataset.mode = salvo ? 'update' : 'create';
        if (limpar) limpar.hidden = !salvo;
        if (openA) {
            if (salvo) {
                openA.hidden = false;
                openA.href = 'https://' + salvo;
            } else {
                openA.hidden = true;
                openA.href = '#';
            }
        }
    }

    function _mostrarSiteFallback(img, fallback, cliente) {
        if (img) {
            img.hidden = true;
            img.removeAttribute('src');
            img.alt = '';
        }
        if (fallback) {
            fallback.hidden = false;
            fallback.textContent = (cliente && cliente.avatar) || avatarIniciais(cliente && cliente.nome || '');
        }
    }

    function _atualizarPreviewSite(dominio, img, fallback, cliente) {
        var d = normalizarDominio(dominio);
        if (!d) { _mostrarSiteFallback(img, fallback, cliente); return; }
        if (!img || !fallback) return;
        fallback.textContent = (cliente && cliente.avatar) || avatarIniciais(cliente && cliente.nome || '');
        img.alt = '';
        img.hidden = true;
        fallback.hidden = false;

        var canonico = logoRealDoCliente(cliente);
        if (!canonico) {
            return;
        }
        img.onload = function () {
            if (!img.naturalWidth) return;
            img.hidden = false;
            fallback.hidden = true;
        };
        img.onerror = function () {
            img.hidden = true;
            fallback.hidden = false;
        };
        img.src = canonico;
    }

    /* ================================================================
     * Aba Web — Fase B (set/2026)
     * ----------------------------------------------------------------
     * Consome os endpoints `/crm-v3/api/clientes/<id>/web-info` (GET
     * e /refresh POST) que servem dados da tabela `cliente_web_info`,
     * populada por scrape do site do cliente via Firecrawl. Objetivo:
     * substituir a cascata frágil de favicons genéricos (Clearbit /
     * Google / DDG) — que devolvia globos azuis para clientes fora
     * do catálogo global — por og:image real do próprio site do
     * cliente, além de mostrar título, descrição e menu principal
     * numa aba dedicada da sidebar.
     *
     * Fluxo:
     *   1. selectCliente() dispara loadWebInfo(id) em paralelo com
     *      os outros loads (contatos, atividades, cotações, notas).
     *   2. Resposta é guardada em state.webInfoCache[clienteId].
     *   3. renderWebInfo() é chamado tanto pelo load quanto quando
     *      o usuário clica no tab Web (bindTabWeb).
     *   4. updateDetailPanel usa webInfoCache[id].logo_url como
     *      primeira tentativa para o avatar do header — só cai na
     *      cascata favicon se web_info não tem logo canônico.
     *   5. Confirmar site em "Site & logo" (bindSiteEditor) dispara
     *      atualizarWebInfo() automaticamente para popular o cache
     *      logo após o cliente ganhar site.
     * ================================================================ */

    function aplicarLogoLista(clienteId, info) {
        if (!clienteId || !info) return;
        var logo = (info && info.logo_url) || '';
        var dominio = normalizarDominio(info.dominio);
        (state.clientes || []).forEach(function (c) {
            if (String(c.id) === String(clienteId)) {
                if (logo) c.web_logo_url = logo;
                if (dominio && !c.site_url) c.site_url = dominio;
            }
        });
        if (state.cliente && String(state.cliente.id) === String(clienteId)) {
            if (logo) state.cliente.web_logo_url = logo;
            if (dominio && !state.cliente.site_url) state.cliente.site_url = dominio;
        }
    }

    function loadWebInfo(clienteId) {
        if (!clienteId) return;
        var cacheKey = String(clienteId);
        if (Object.prototype.hasOwnProperty.call(state.webInfoCache, cacheKey)
            || Object.prototype.hasOwnProperty.call(state.webInfoCache, clienteId)) {
            var cached = Object.prototype.hasOwnProperty.call(state.webInfoCache, cacheKey)
                ? state.webInfoCache[cacheKey]
                : state.webInfoCache[clienteId];
            renderWebInfo(cached);
            updateTabBadgeWeb(cached);
            if (state.cliente) renderSiteEditor(state.cliente);
            return;
        }
        api('/clientes/' + encodeURIComponent(clienteId) + '/web-info')
            .then(function (data) {
                if (String(state.clienteId) !== String(clienteId)) return;
                var info = (data && data.web_info) || null;
                state.webInfoCache[cacheKey] = info;
                aplicarLogoLista(clienteId, info);
                renderWebInfo(info);
                updateTabBadgeWeb(info);
                if (state.cliente) {
                    renderSiteEditor(state.cliente);
                    if (info && info.logo_url) {
                        updateDetailPanel(state.cliente);
                        updateClienteCardLogo(clienteId);
                    }
                }
            })
            .catch(function () {
                if (String(state.clienteId) !== String(clienteId)) return;
                state.webInfoCache[cacheKey] = null;
                renderWebInfo(null);
                updateTabBadgeWeb(null);
                if (state.cliente) renderSiteEditor(state.cliente);
            });
    }

    /**
     * Incentivos PI na sidebar (Perfil comercial) — set/2026.
     * Só exibe faixas quando a agência (própria ou vinculada) tem
     * cadastro em cadu_pi_incentivos. Sem cadastro → bloco hidden.
     */
    function renderIncentivosSidebar(inc) {
        var block = $('#crm-v3-incentivos-block');
        var container = $('#crm-v3-incentivos-faixas');
        var hint = $('#crm-v3-incentivos-hint');
        var link = $('#crm-v3-incentivos-link');
        if (!block || !container) return;

        if (!inc || !inc.faixas || !inc.faixas.length) {
            block.hidden = true;
            container.innerHTML = '';
            if (hint) hint.hidden = true;
            return;
        }

        block.hidden = false;
        if (link && inc.link) link.href = inc.link;

        if (hint) {
            if (inc.via_vinculo && inc.agencia_nome) {
                hint.textContent = 'Agência: ' + inc.agencia_nome;
                hint.hidden = false;
            } else {
                hint.hidden = true;
            }
        }

        container.innerHTML = inc.faixas.map(function (f) {
            return (
                '<div class="crm-v3-incentivo-faixa">' +
                '<span class="crm-v3-incentivo-faixa-label">' + escapeHtml(f.label) + '</span>' +
                '<span class="crm-v3-incentivo-faixa-val">' + escapeHtml(String(f.percentual)) + '%</span>' +
                '</div>'
            );
        }).join('');
    }

    function loadIncentivos(clienteId) {
        renderIncentivosSidebar(null);
        if (!clienteId) return;
        return api('/clientes/' + encodeURIComponent(clienteId) + '/incentivos')
            .then(function (data) {
                if (String(state.clienteId) !== String(clienteId)) return;
                renderIncentivosSidebar((data && data.incentivo) || null);
            })
            .catch(function () {
                if (String(state.clienteId) === String(clienteId)) {
                    renderIncentivosSidebar(null);
                }
            });
    }

    function atualizarWebInfo() {
        var cid = state.clienteId;
        if (!cid) return;
        var btn = $('#crm-v3-web-refresh');
        var btnNow = $('#crm-v3-web-fetch-now');
        var origHTML = btn ? btn.innerHTML : '';
        [btn, btnNow].forEach(function (b) {
            if (!b) return;
            b.disabled = true;
        });
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Buscando…';
        }
        // Troca para estado de loading enquanto o Firecrawl roda (pode
        // levar até ~10s dependendo do site).
        setWebTabState('loading');
        var dominio = dominioNaTela(state.cliente);
        if (!dominio) {
            showToast('Informe o site nesta aba para buscar as informações.', true);
            renderWebInfo(state.webInfoCache[cid] || state.webInfoCache[String(cid)] || null);
            [btn, btnNow].forEach(function (b) {
                if (!b) return;
                b.disabled = false;
            });
            if (btn && origHTML) btn.innerHTML = origHTML;
            return;
        }
        api('/clientes/' + encodeURIComponent(cid) + '/web-info/refresh', {
            method: 'POST',
            body: { dominio: dominio }
        }).then(function (data) {
            if (state.clienteId !== cid) return;
            var info = (data && data.web_info) || null;
            state.webInfoCache[String(cid)] = info;
            state.webInfoCache[cid] = info;
            renderWebInfo(info);
            updateTabBadgeWeb(info);
            aplicarLogoLista(cid, info);
            if (state.cliente) {
                renderSiteEditor(state.cliente);
                if (info && info.logo_url) {
                    updateDetailPanel(state.cliente);
                    updateClienteCardLogo(cid);
                }
            }
            if (info && info.status === 'ok') {
                showToast('Informações do site atualizadas.');
            } else if (info && info.status === 'erro') {
                showToast('Não foi possível ler o site — ' + (info.erro_mensagem || 'erro desconhecido'), true);
            }
        }).catch(function (err) {
            showToast(err.message || 'Falha ao atualizar informações do site.', true);
            // Restaura estado anterior (o cache não muda em caso de erro).
            renderWebInfo(state.webInfoCache[cid] || null);
        }).finally(function () {
            [btn, btnNow].forEach(function (b) {
                if (!b) return;
                b.disabled = false;
            });
            if (btn && origHTML) btn.innerHTML = origHTML;
        });
    }

    // Renderiza o painel Web baseado no info retornado pela API.
    // Estados possíveis (setados via data-state no wrap):
    //   loading, empty, no-cache, ok, error.
    function renderWebInfo(info) {
        var wrap = $('#crm-v3-web-tab');
        if (!wrap) return;

        // Sem info: decide entre "empty" (sem site) e "no-cache" (com site).
        if (!info) {
            var cliente = state.cliente;
            if (dominioConfirmado(cliente)) {
                setWebTabState('no-cache');
            } else {
                setWebTabState('empty');
            }
            return;
        }

        // Info com status = erro.
        if (info.status === 'erro') {
            setWebTabState('error');
            var errEl = $('#crm-v3-web-error-msg');
            if (errEl) errEl.textContent = info.erro_mensagem || 'Erro desconhecido';
            return;
        }

        // Info com status = ok — popula hero, sobre e menu.
        setWebTabState('ok');

        // Título (fallback: domínio se o site não publicou <title>).
        var titleEl = $('#crm-v3-web-title');
        if (titleEl) {
            titleEl.textContent = info.titulo || info.dominio || '—';
            titleEl.title = info.titulo || '';
        }

        // Domínio clicável (target=_blank).
        var domEl = $('#crm-v3-web-domain');
        if (domEl) {
            var d = info.dominio || '';
            domEl.href = d ? 'https://' + d : '#';
            var spanD = domEl.querySelector('span');
            if (spanD) spanD.textContent = d;
        }

        // Logo do hero: só og:image real. Sem globo/favicon genérico.
        var img = $('#crm-v3-web-logo-img');
        var fb = $('#crm-v3-web-logo-fallback');
        var wrapLogo = $('#crm-v3-web-logo-wrap');
        if (img) {
            img.hidden = true;
            img.removeAttribute('src');
        }
        if (fb) fb.hidden = true;
        var logoSrc = (info && info.logo_url) || '';
        if (wrapLogo) wrapLogo.hidden = !logoSrc;
        if (logoSrc && img) {
            img.onload = function () {
                if (!img.naturalWidth || !img.naturalHeight) {
                    img.hidden = true;
                    if (wrapLogo) wrapLogo.hidden = true;
                    return;
                }
                img.hidden = false;
                if (fb) fb.hidden = true;
                if (wrapLogo) wrapLogo.hidden = false;
            };
            img.onerror = function () {
                img.hidden = true;
                if (wrapLogo) wrapLogo.hidden = true;
            };
            img.src = logoSrc;
        }

        // Sobre — meta description.
        var descEl = $('#crm-v3-web-descricao');
        if (descEl) {
            descEl.textContent = info.descricao || 'Sem descrição disponível no site.';
        }

        // Menu principal — chips clicáveis.
        var menuSec = $('#crm-v3-web-menu-section');
        var menuWrap = $('#crm-v3-web-menu-links');
        var links = Array.isArray(info.menu_links) ? info.menu_links : [];
        if (menuSec && menuWrap) {
            if (links.length === 0) {
                menuSec.hidden = true;
            } else {
                menuSec.hidden = false;
                menuWrap.innerHTML = links.map(function (link) {
                    return '<a class="crm-v3-web-link" href="' + escapeHtml(link.url) + '" target="_blank" rel="noopener">' +
                        '<span class="crm-v3-web-link-label">' + escapeHtml(link.label || link.url) + '</span>' +
                        '<i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i>' +
                        '</a>';
                }).join('');
            }
        }

        // Timestamp da atualização — humaniza para "há X".
        var atualEl = $('#crm-v3-web-atualizado');
        if (atualEl) {
            var quando = info.atualizado_em ? formatarHaTempo(info.atualizado_em) : '';
            atualEl.textContent = quando
                ? 'Atualizado ' + quando + ' — do site oficial do cliente'
                : 'Extraído do site oficial do cliente';
            if (info.atualizado_em) atualEl.title = info.atualizado_em;
        }
    }

    // Atualiza o data-state no wrap e sincroniza a visibilidade dos
    // blocos filhos. Cada bloco tem data-web-state="..." — mostramos
    // só os que casam com o estado atual (permite múltiplos blocos
    // no mesmo estado, útil para o "ok" que tem hero + sobre + menu).
    function setWebTabState(estado) {
        var wrap = $('#crm-v3-web-tab');
        if (!wrap) return;
        wrap.dataset.state = estado;
        wrap.querySelectorAll('[data-web-state]').forEach(function (bloco) {
            bloco.hidden = (bloco.dataset.webState !== estado);
        });
    }

    // Atualiza o badge no botão do tab Web indicando o status do
    // último scrape. Verde = ok, amarelo = erro, cinza = vazio.
    function updateTabBadgeWeb(info) {
        var badge = document.querySelector('[data-tab-badge="web"]');
        if (!badge) return;
        badge.classList.remove('is-ok', 'is-error', 'is-empty');
        if (!info) {
            badge.hidden = true;
            return;
        }
        badge.hidden = false;
        if (info.status === 'ok') badge.classList.add('is-ok');
        else if (info.status === 'erro') badge.classList.add('is-error');
        else badge.classList.add('is-empty');
    }

    // Liga os botões do painel Web. Chamado uma vez no boot.
    function bindTabWeb() {
        var btnRefresh = $('#crm-v3-web-refresh');
        if (btnRefresh) btnRefresh.addEventListener('click', atualizarWebInfo);

        var btnNow = $('#crm-v3-web-fetch-now');
        if (btnNow) btnNow.addEventListener('click', atualizarWebInfo);
    }


    // Bind único (event delegation) do editor de site. Chamado uma vez
    // no boot; opera sobre o cliente atual em `state.clienteId`.
    function bindSiteEditor() {
        var input = $('#crm-v3-site-input');
        var confirmar = $('#crm-v3-site-confirmar');
        var limpar = $('#crm-v3-site-limpar');
        var hint = $('#crm-v3-site-hint');
        var img = $('#crm-v3-site-logo-img');
        var fallback = $('#crm-v3-site-logo-fallback');
        if (!input || !confirmar) return;

        // Preview em tempo real enquanto o usuário digita (debounced).
        var previewDebounced = debounce(function () {
            var cliente = state.clientes.find(function (c) { return c.id === state.clienteId; });
            var d = normalizarDominio(input.value);
            if (d) _atualizarPreviewSite(d, img, fallback, cliente);
            else _mostrarSiteFallback(img, fallback, cliente);
            confirmar.disabled = !d;
        }, 250);
        input.addEventListener('input', function () {
            // Usuário editou manualmente — some a marca de auto-fill
            // e o estilo azulado. A partir daqui o valor é dele.
            if (input.classList.contains('is-auto-fill')) {
                input.classList.remove('is-auto-fill');
                delete input.dataset.autoFill;
            }
            previewDebounced();
        });

        // Enter no campo → dispara confirmação.
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                confirmar.click();
            }
        });

        var alterar = $('#crm-v3-site-alterar');
        if (alterar) {
            alterar.addEventListener('click', function () {
                var editor = $('#crm-v3-site-editor');
                var confirmed = $('#crm-v3-site-confirmed');
                if (editor) editor.classList.remove('is-confirmed');
                if (confirmed) confirmed.hidden = true;
                confirmar.disabled = !normalizarDominio(input.value);
                input.focus();
                input.select();
            });
        }

        confirmar.addEventListener('click', function () {
            if (!state.clienteId) return;
            var dominio = normalizarDominio(input.value);
            if (!dominio) {
                showToast('Informe um site válido (ex.: cliente.com.br).', true);
                return;
            }
            confirmar.disabled = true;
            var prev = confirmar.innerHTML;
            confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Salvando…';
            api('/clientes/' + encodeURIComponent(state.clienteId), {
                method: 'PATCH',
                body: { site_url: dominio }
            }).then(function () {
                // Atualiza o estado local + propaga em todos os pontos
                // da página (header, cards, sidebar Info).
                var idx = state.clientes.findIndex(function (c) { return String(c.id) === String(state.clienteId); });
                if (idx >= 0) state.clientes[idx].site_url = dominio;
                if (state.cliente) state.cliente.site_url = dominio;
                var cliente = state.cliente || state.clientes[idx];
                if (cliente) {
                    renderSiteEditor(cliente);
                    updateDetailPanel(cliente);
                }
                renderClientes();
                showToast('Site do cliente atualizado.');
                if (state.webInfoCache) {
                    delete state.webInfoCache[state.clienteId];
                    delete state.webInfoCache[String(state.clienteId)];
                }
                if (typeof atualizarWebInfo === 'function') {
                    atualizarWebInfo();
                }
            }).catch(function (err) {
                showToast(err.message || 'Falha ao salvar site.', true);
            }).finally(function () {
                confirmar.disabled = false;
                confirmar.innerHTML = prev;
            });
        });

        if (limpar) {
            limpar.addEventListener('click', function () {
                if (!state.clienteId) return;
                if (!confirm('Remover o site salvo? O logo volta a ser inferido do contato principal.')) return;
                limpar.disabled = true;
                api('/clientes/' + encodeURIComponent(state.clienteId), {
                    method: 'PATCH',
                    body: { site_url: '' }
                }).then(function () {
                    var idx = state.clientes.findIndex(function (c) { return String(c.id) === String(state.clienteId); });
                    if (idx >= 0) {
                        state.clientes[idx].site_url = '';
                        state.clientes[idx].web_logo_url = '';
                    }
                    if (state.cliente) {
                        state.cliente.site_url = '';
                        state.cliente.web_logo_url = '';
                    }
                    if (state.webInfoCache) {
                        delete state.webInfoCache[state.clienteId];
                        delete state.webInfoCache[String(state.clienteId)];
                    }
                    var cliente = state.cliente || state.clientes[idx];
                    if (cliente) {
                        renderSiteEditor(cliente);
                        updateDetailPanel(cliente);
                        renderWebInfo(null);
                    }
                    renderClientes();
                    showToast('Site removido.');
                }).catch(function (err) {
                    showToast(err.message || 'Falha ao remover site.', true);
                }).finally(function () {
                    limpar.disabled = false;
                });
            });
        }
    }

    /**
     * Avatar do header vira atalho para editar site/logo.
     *
     * Fluxo (set/2026): quando o executivo vê a logo do cliente errada
     * (ou placeholder com iniciais quando o cliente tem site cadastrado),
     * um clique no avatar leva direto para o input de "Site & logo" —
     * antes precisava rolar a sidebar manualmente até o final.
     *
     * Passos:
     *   1. Ativa a aba "Info" se estiver em outra (Objetivos, Cotações).
     *   2. Rola a sidebar até `#crm-v3-site-logo-section` com behavior
     *      smooth. Usa scroll do container (aside.crm-v3-sidebar) e não
     *      da janela, senão a página toda se move.
     *   3. Aplica uma classe de destaque temporária (flash 1.6s) para
     *      indicar visualmente onde o usuário caiu.
     *   4. Foca o input após a animação (600ms) — se focar antes, o
     *      scroll é cancelado no Chrome/Firefox.
     */
    function bindAvatarShortcut() {
        var avatar = $('#crm-v3-detail-avatar-wrap');
        if (!avatar) return;
        avatar.addEventListener('click', function (ev) {
            ev.preventDefault();
            if (!state.clienteId) return;
            var btnWeb = document.getElementById('tab-sidebar-web')
                || document.querySelector('[role="tab"][data-tab="web"]');
            if (btnWeb) btnWeb.click();
            var target = $('#crm-v3-site-logo-section');
            if (target) {
                target.classList.remove('crm-v3-site-logo-flash');
                void target.offsetWidth;
                target.classList.add('crm-v3-site-logo-flash');
                var scroller = target.closest('.crm-v3-sidebar-panel-wrap')
                    || document.querySelector('.crm-v3-sidebar-panel-wrap');
                if (scroller && scroller.scrollTo) scroller.scrollTo({ top: 0, behavior: 'smooth' });
            }
            if (!dominioConfirmado(state.cliente)) {
                setTimeout(function () {
                    var input = $('#crm-v3-site-input');
                    if (input) input.focus();
                }, 200);
            }
        });
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
                return state.clientes.find(function (c) {
                    return String(c.id) === String(id);
                });
            }).filter(Boolean);
        }

        var isAgencia = !!cliente.is_agencia;
        var vinculos = Array.isArray(cliente.agencias_vinculadas) ? cliente.agencias_vinculadas : [];
        var principal = vinculos.filter(function (v) { return v && v.is_principal; })[0] || vinculos[0];
        var agenciaId = (principal && principal.agencia_id) || '';
        var agenciaNome = (principal && principal.nome) || '';
        if (!agenciaNome && agenciaId && Array.isArray(state.clientes)) {
            var pai = state.clientes.find(function (c) {
                return String(c.id) === String(agenciaId);
            });
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

    function renderContatos() {
        var container = $('#crm-v3-lista-contatos');
        if (!container) return;

        var lista = state.contatos || [];

        if (!state.clienteId) {
            container.innerHTML = '<div class="crm-v3-contatos-empty p-3 text-sm">Selecione um cliente.</div>';
            return;
        }

        if (!state.contatos.length) {
            container.innerHTML =
                '<div class="crm-v3-contatos-empty p-3 text-sm text-center">' +
                'Nenhum contato cadastrado.' +
                '</div>';
            return;
        }

        container.innerHTML = lista.map(function (c, idx) {
            var ativo = String(c.id) === String(state.contatoId);
            var expandirTodos = lista.length <= 5;
            var expandido = expandirTodos || ativo || (!state.contatoId && idx === 0);
            var nomeExibido = (c.nome && String(c.nome).trim()) || (c.email ? String(c.email).split('@')[0] : 'Contato sem nome');
            var subLinha = [c.cargo, c.setor].filter(Boolean).join(' · ');
            return (
                '<div class="crm-v3-contato-card' + (ativo ? ' crm-v3-contato-card-active' : '') + (expandido ? ' is-expanded' : '') + '" role="listitem" tabindex="0" data-contato-id="' + escapeHtml(c.id) + '">' +
                '<div class="crm-v3-contato-main">' +
                avatarHtml(nomeExibido, 'w-8 h-8') +
                '<div class="crm-v3-contato-info min-w-0">' +
                '<div class="crm-v3-contato-nome-row">' +
                '<button type="button" class="crm-v3-contato-nome" data-contato-id="' + escapeHtml(c.id) + '" title="Editar ' + escapeHtml(nomeExibido) + '">' + escapeHtml(nomeExibido) + '</button>' +
                (c.principal ? '<span class="crm-v3-contato-badge crm-v3-contato-badge-principal" title="Contato principal"><i class="fa-solid fa-star" aria-hidden="true"></i></span>' : '') +
                '</div>' +
                (subLinha ? '<div class="crm-v3-contato-cargo">' + escapeHtml(subLinha) + '</div>' : '') +
                '</div>' +
                '<div class="crm-v3-contato-actions">' +
                '<button type="button" class="crm-v3-contato-toggle crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" aria-expanded="' + (expandido ? 'true' : 'false') + '" aria-label="' + (expandido ? 'Recolher contato' : 'Expandir contato') + '"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>' +
                '</div></div>' +
                contatoDetailsHtml(c) +
                '</div>'
            );
        }).join('');

        bindContatoEvents(container);
    }

    function contatoDetailsHtml(c) {
        var id = escapeHtml(c.id);
        var rows = '';
        if (c.email) {
            rows +=
                '<div class="crm-v3-contato-email-row">' +
                '<i class="fa-regular fa-envelope crm-v3-contato-row-icon" aria-hidden="true"></i>' +
                '<span class="crm-v3-contato-row-text" title="' + escapeHtml(c.email) + '">' + escapeHtml(c.email) + '</span>' +
                '<button type="button" class="crm-v3-contato-copy crm-v3-icon-btn crm-v3-icon-btn-xs crm-v3-icon-btn-ghost" data-copy="' + escapeHtml(c.email) + '" aria-label="Copiar e-mail"><i class="fa-regular fa-copy"></i></button>' +
                '</div>';
        } else {
            rows +=
                '<button type="button" class="crm-v3-contato-quick-add" data-field="email" data-contato-id="' + id + '">' +
                '<i class="fa-regular fa-envelope" aria-hidden="true"></i>' +
                '+ Adicionar e-mail' +
                '</button>';
        }
        if (c.telefone) {
            rows +=
                '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row">' +
                '<i class="fa-brands fa-whatsapp" aria-hidden="true"></i>' +
                '<span>' + escapeHtml(c.telefone) + '</span>' +
                '</button>';
        } else {
            rows +=
                '<button type="button" class="crm-v3-contato-quick-add" data-field="telefone" data-contato-id="' + id + '">' +
                '<i class="fa-solid fa-phone" aria-hidden="true"></i>' +
                '+ Adicionar telefone' +
                '</button>';
        }
        if (c.telefone_secundario) {
            rows +=
                '<button type="button" class="crm-v3-contato-phone-row crm-v3-contato-whats-row">' +
                '<i class="fa-brands fa-whatsapp" aria-hidden="true"></i>' +
                '<span>' + escapeHtml(c.telefone_secundario) + '</span>' +
                '</button>';
        }
        return '<div class="crm-v3-contato-details">' + rows + '</div>';
    }

    function patchContatoCampo(contatoId, field, value) {
        var payload = {};
        payload[field] = value;
        return api('/contatos/' + encodeURIComponent(contatoId), {
            method: 'PATCH',
            body: payload
        }).then(function (resp) {
            var atualizado = (resp && resp.contato) || payload;
            var idx = state.contatos.findIndex(function (c) { return String(c.id) === String(contatoId); });
            if (idx >= 0) {
                state.contatos[idx] = Object.assign({}, state.contatos[idx], atualizado);
            }
            showToast(field === 'email' ? 'E-mail salvo.' : 'Telefone salvo.');
            renderContatos();
            if (state.cliente) updateDetailPanel(state.cliente);
        }).catch(function (err) {
            showToast(err.message || 'Não foi possível salvar o contato.', true);
            renderContatos();
        });
    }

    function iniciarQuickAddContato(btn) {
        var field = btn.getAttribute('data-field');
        var contatoId = btn.getAttribute('data-contato-id');
        if (!field || !contatoId) return;
        var wrap = document.createElement('div');
        wrap.className = 'crm-v3-contato-quick-edit';
        var icon = document.createElement('i');
        icon.className = field === 'email' ? 'fa-regular fa-envelope crm-v3-contato-row-icon' : 'fa-solid fa-phone crm-v3-contato-row-icon';
        icon.setAttribute('aria-hidden', 'true');
        var input = document.createElement('input');
        input.className = 'crm-v3-contato-quick-input';
        input.type = field === 'email' ? 'email' : 'tel';
        input.placeholder = field === 'email' ? 'nome@empresa.com' : '(31) 99999-0000';
        input.setAttribute('aria-label', field === 'email' ? 'E-mail do contato' : 'Telefone do contato');
        wrap.appendChild(icon);
        wrap.appendChild(input);
        btn.replaceWith(wrap);
        input.focus();

        var done = false;
        function finish(save) {
            if (done) return;
            done = true;
            var val = String(input.value || '').trim();
            if (!save || !val) {
                renderContatos();
                return;
            }
            if (field === 'email' && val.indexOf('@') === -1) {
                showToast('Informe um e-mail válido.', true);
                done = false;
                return;
            }
            wrap.classList.add('is-saving');
            patchContatoCampo(contatoId, field, val);
        }
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') {
                ev.preventDefault();
                finish(true);
            } else if (ev.key === 'Escape') {
                ev.preventDefault();
                finish(false);
            }
        });
        input.addEventListener('blur', function () { finish(true); });
    }

    function bindContatoEvents(container) {
        $$('.crm-v3-contato-card', container).forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.closest('.crm-v3-contato-toggle, .crm-v3-contato-nome, .crm-v3-contato-copy, .crm-v3-contato-phone-row, .crm-v3-contato-whats-row, .crm-v3-contato-quick-add, .crm-v3-contato-quick-edit')) return;
                selectContato(card.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-v3-contato-nome', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                openContatoModal(btn.getAttribute('data-contato-id'));
            });
        });

        $$('.crm-v3-contato-toggle', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var card = btn.closest('.crm-v3-contato-card');
                var expanded = card.classList.toggle('is-expanded');
                btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                btn.setAttribute('aria-label', expanded ? 'Recolher contato' : 'Expandir contato');
            });
        });

        $$('.crm-v3-contato-quick-add', container).forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                iniciarQuickAddContato(btn);
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
        var t = (tipo || '').toLowerCase();
        if (t === 'ligacao' || t === 'phone') return 'crm-v3-ativ-icon-phone';
        if (t === 'reuniao' || t === 'meeting') return 'crm-v3-ativ-icon-meeting';
        if (t === 'doc') return 'crm-v3-ativ-icon-doc';
        if (t === 'email') return 'crm-v3-ativ-icon-email';
        if (t === 'whatsapp') return 'crm-v3-ativ-icon-whatsapp';
        if (t === 'planejamento') return 'crm-v3-ativ-icon-plan';
        return 'crm-v3-ativ-icon-note';
    }

    function ativIconHtml(tipo) {
        var t = (tipo || '').toLowerCase();
        var icons = {
            ligacao: { ic: 'fa-solid fa-phone', cls: 'phone' },
            phone: { ic: 'fa-solid fa-phone', cls: 'phone' },
            reuniao: { ic: 'fa-solid fa-video', cls: 'meeting' },
            meeting: { ic: 'fa-solid fa-video', cls: 'meeting' },
            doc: { ic: 'fa-regular fa-file-lines', cls: 'doc' },
            note: { ic: 'fa-regular fa-note-sticky', cls: 'note' },
            email: { ic: 'fa-solid fa-envelope', cls: 'email' },
            whatsapp: { ic: 'fa-brands fa-whatsapp', cls: 'whatsapp' },
            planejamento: { ic: 'fa-solid fa-diagram-project', cls: 'plan' },
            atividade: { ic: 'fa-regular fa-circle-check', cls: 'note' }
        };
        var spec = icons[t] || { ic: 'fa-regular fa-circle-check', cls: 'note' };
        return '<span class="crm-v3-ativ-icon ' + ativIconClass(t) + '" aria-hidden="true"><i class="' + spec.ic + '"></i></span>';
    }

    function stripMarkdown(s) {
        s = String(s == null ? '' : s);
        s = s.replace(/```[\s\S]*?```/g, function (m) { return m.replace(/```/g, ''); });
        s = s.replace(/^#{1,6}\s+/gm, '');
        s = s.replace(/\*\*(.+?)\*\*/g, '$1');
        s = s.replace(/__(.+?)__/g, '$1');
        s = s.replace(/`([^`]+)`/g, '$1');
        s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        s = s.replace(/^\s{0,3}>\s?/gm, '');
        s = s.replace(/\*\*/g, '');
        return s.trim();
    }

    function tituloAtividadeLista(a) {
        var t = stripMarkdown(a && a.titulo).split('\n')[0].trim();
        if (!t) t = stripMarkdown(a && a.descricao).split('\n')[0].trim();
        if (!t) return 'Atividade';
        return t.length > 88 ? t.slice(0, 87) + '…' : t;
    }

    function fotoExecutivoAtividade(a) {
        if (a && a.responsavel_foto_url) return a.responsavel_foto_url;
        var lista = (window.CRM_V3_CONTEXT && window.CRM_V3_CONTEXT.executivos) || [];
        var nome = String((a && a.responsavel) || '').toLowerCase();
        var id = a && a.executivo_id ? String(a.executivo_id) : '';
        for (var i = 0; i < lista.length; i++) {
            var ex = lista[i] || {};
            var foto = ex.foto_url || '';
            if (!foto) continue;
            if (id && String(ex.id_contato_cliente || ex.id) === id) return foto;
            var n = String(ex.nome_completo || ex.nome || '').toLowerCase();
            if (n && nome && n === nome) return foto;
        }
        return '';
    }

    function execAvatarHtml(a) {
        var nome = (a && a.responsavel) || '';
        if (!nome) return '';
        var foto = fotoExecutivoAtividade(a);
        if (foto) {
            return '<img class="crm-v3-avatar-mini crm-v3-ativ-owner" src="' + escapeHtml(foto) + '" alt="" title="' + escapeHtml(nome) + '">';
        }
        return '<div class="crm-v3-avatar-mini crm-v3-ativ-owner" title="' + escapeHtml(nome) + '">' + escapeHtml(avatarIniciais(nome)) + '</div>';
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
        var dataStr = formatarDataAtividade(a);
        var horaStr = a.hora || '';
        var quando = [dataStr, horaStr].filter(Boolean).join(' · ');
        var titulo = tituloAtividadeLista(a);
        return (
            '<div class="crm-v3-ativ' + (concluida ? ' crm-v3-ativ-concluida' : '') + '" role="listitem" data-status="' + escapeHtml(a.status) + '" data-atividade-id="' + escapeHtml(a.id) + '"' + (a._pending ? ' data-pending="true"' : '') + '>' +
                '<button type="button" class="crm-v3-ativ-check" data-ativ-action="toggle" aria-label="' + (concluida ? 'Reabrir' : 'Marcar como feita') + ': ' + escapeHtml(titulo) + '" title="' + (concluida ? 'Reabrir' : 'Marcar como feita') + '">' +
                    '<i class="' + (concluida ? 'fa-solid fa-circle-check' : 'fa-regular fa-circle') + '" aria-hidden="true"></i>' +
                '</button>' +
                ativIconHtml(a.tipo) +
                '<button type="button" class="crm-v3-ativ-content" data-ativ-action="editar" title="Editar atividade">' +
                    '<div class="crm-v3-ativ-titulo">' + escapeHtml(titulo) + '</div>' +
                '</button>' +
                (quando ? '<span class="crm-v3-ativ-when" title="' + escapeHtml(quando) + '">' + escapeHtml(quando) + '</span>' : '') +
                execAvatarHtml(a) +
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

        // Sem filtro por aba: a coluna mostra tudo agrupado por data
        // (Atrasadas, Hoje, Amanhã, Esta semana, Próximas, Sem data,
        // Concluídas). Abas de filtro (Todas / Pendentes / Concluídas)
        // foram removidas por decisão de UX — o agrupamento por data já
        // segrega pendentes e concluídas visualmente.
        var filtrados = state.atividades.slice();

        if (!state.clienteId) {
            container.innerHTML = '<div class="crm-v3-ativ-empty">Selecione um cliente.</div>';
            updateTabCounts();
            return;
        }

        if (!filtrados.length) {
            // Empty state: sugestões em destaque com heading grande.
            // O composer fica em cima; aqui embaixo vem o convite.
            container.innerHTML = renderQuickAtividadesHTML({ compact: false });
            bindQuickAtividades(container);
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

        // Set/2026: sugestões SEMPRE visíveis (não só no empty state).
        // Filosofia do CRM v3: o executivo de vendas tem que ter um
        // próximo passo à mão a cada momento — mais touchpoints =
        // mais vendas. As sugestões vão no rodapé da coluna, em
        // modo compacto (sem heading grande, sem competir visualmente
        // com as atividades reais acima), e só as que ainda NÃO
        // foram feitas pelo cliente (filtro em getSuggestionsForClient).
        html += renderQuickAtividadesHTML({ compact: true });

        container.innerHTML = html;
        bindAtividadeEvents(container);
        bindQuickAtividades(container);
        updateTabCounts();
    }

    // renderSidebarAtividades removida em set/2026: a aba "Atividades"
    // da sidebar foi eliminada por ser redundante com a coluna central
    // (que é o foco do CRM v3). Nada mais renderiza uma mini-lista.

    // renderSugestao removida em set/2026 — a seção "Próximos passos
    // sugeridos" foi removida da UI (repetia mensagens vazias). O
    // empty state do composer agora oferece 4 sugestões clicáveis
    // (renderQuickAtividadesHTML / bindQuickAtividades logo abaixo).

    /* ------------------------------------------------------------------
     * Sugestões rápidas de atividade (empty state)
     * ------------------------------------------------------------------
     * Quando o cliente não tem NENHUMA atividade cadastrada, mostramos 4
     * cards clicáveis com os próximos passos mais comuns do funil
     * comercial. Cada card, ao ser clicado, PRÉ-PREENCHE o composer
     * (título, tipo, data) e foca o input — o usuário só ajusta e dá
     * Enter para salvar. Não salva sozinho para preservar controle
     * humano (o executivo pode ajustar o título antes de commitar).
     * ------------------------------------------------------------------ */
    var QUICK_ATIV_SUGGESTIONS = [
        // Canais / marcas — uma linha cada, título curto (o cliente já está selecionado)
        { titulo: 'Apresentar Netflix', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar Serasa', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar Logan', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar Uber', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar iFood', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar 99', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar Amazon', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar Disney', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar HBO', tipo: 'reuniao', icon: 'fa-solid fa-tv', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Apresentar a CentralComm', tipo: 'reuniao', icon: 'fa-solid fa-building', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Agendar café da manhã interativo', tipo: 'reuniao', icon: 'fa-solid fa-mug-hot', hint: 'Evento · esta semana', daysAhead: 5 },
        { titulo: 'Convidar para o Media Hacks Training 2026', tipo: 'atividade', icon: 'fa-solid fa-graduation-cap', hint: 'Convite · este mês', daysAhead: 14 },
        // Funil — no fim, para não esconder as marcas depois da 1ª atividade
        { titulo: 'Ligar para apresentar propostas', tipo: 'ligacao', icon: 'fa-solid fa-phone', hint: 'Ligação · hoje' },
        { titulo: 'Enviar e-mail de acompanhamento', tipo: 'atividade', icon: 'fa-regular fa-envelope', hint: 'E-mail · hoje' },
        { titulo: 'Agendar reunião de descoberta', tipo: 'reuniao', icon: 'fa-solid fa-users', hint: 'Reunião · esta semana', daysAhead: 3 },
        { titulo: 'Preparar proposta comercial', tipo: 'planejamento', icon: 'fa-solid fa-diagram-project', hint: 'Planejamento · amanhã', daysAhead: 1 }
    ];

    /**
     * Normaliza string para comparação: lowercase, sem acentos, sem espaços extras.
     */
    function normalizarTitulo(str) {
        return String(str || '')
            .toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    /**
     * Retorna sugestões filtradas: exclui as que já foram usadas pelo cliente atual.
     * A comparação é feita pelo título base (sem {cliente}).
     */
    function getSuggestionsForClient() {
        var usados = (state.atividades || []).map(function (a) {
            return normalizarTitulo((a.titulo || '') + ' ' + (a.descricao || ''));
        });

        return QUICK_ATIV_SUGGESTIONS.filter(function (s) {
            var tituloBase = normalizarTitulo(s.titulo);
            return !usados.some(function (usado) {
                return usado.indexOf(tituloBase) !== -1;
            });
        });
    }

    /**
     * Renderiza o bloco de sugestões rápidas.
     *
     * @param {Object} opts
     * @param {boolean} [opts.compact=false]
     *   - false (empty state): heading grande "Sugestões rápidas — clique
     *     para começar" com ícone, mostra TODAS as sugestões disponíveis.
     *   - true (rodapé da coluna quando o cliente já tem atividades):
     *     heading pequeno "Próximos passos", lista em uma coluna as
     *     sugestões ainda não usadas (marcas + eventos + funil).
     */
    function renderQuickAtividadesHTML(opts) {
        opts = opts || {};
        var compact = !!opts.compact;
        var sugestoes = getSuggestionsForClient();

        if (!sugestoes.length) {
            // Filtro removeu tudo (raro — só quando o cliente fez
            // todas as 15 sugestões possíveis). No modo compact
            // isso é OK: rodapé fica limpo. No empty state precisamos
            // dizer algo — o executivo abriu a coluna sem nada e não
            // vamos deixar em branco.
            if (compact) return '';
            return (
                '<div class="crm-v3-ativ-empty-suggest">' +
                '<div class="crm-v3-ativ-empty-heading">' +
                    '<i class="fa-solid fa-circle-check" aria-hidden="true"></i>' +
                    '<span>Este cliente já teve todos os touchpoints sugeridos. Use o composer acima para adicionar uma atividade personalizada.</span>' +
                '</div></div>'
            );
        }

        var VISIVEIS = 5;
        var total = sugestoes.length;
        var visiveis = sugestoes.slice(0, VISIVEIS);
        var resto = Math.max(0, total - visiveis.length);

        var cards = visiveis.map(function (s) {
            return (
                '<button type="button" class="crm-v3-quick-ativ" data-suggestion-titulo="' + escapeHtml(s.titulo) + '"' +
                ' data-suggestion-tipo="' + escapeHtml(s.tipo) + '"' +
                ' data-suggestion-days="' + (s.daysAhead || 0) + '"' +
                ' title="' + escapeHtml(s.titulo) + '"' +
                ' aria-label="' + escapeHtml(s.titulo) + '">' +
                '<span class="crm-v3-quick-ativ-icon"><i class="' + s.icon + '" aria-hidden="true"></i></span>' +
                '<span class="crm-v3-quick-ativ-body">' +
                '<span class="crm-v3-quick-ativ-title">' + escapeHtml(s.titulo) + '</span>' +
                '<span class="crm-v3-quick-ativ-hint">' + escapeHtml(s.hint) + '</span>' +
                '</span>' +
                '<i class="fa-solid fa-arrow-right crm-v3-quick-ativ-arrow" aria-hidden="true"></i>' +
                '</button>'
            );
        }).join('');
        var more = resto
            ? '<button type="button" class="crm-v3-quick-ativ-more" data-open-sugestoes="1">' +
              'Ver mais ' + resto + ' sugestões' +
              '</button>'
            : '<button type="button" class="crm-v3-quick-ativ-more" data-open-sugestoes="1">' +
              'Ver todas as sugestões' +
              '</button>';

        if (compact) {
            return (
                '<div class="crm-v3-ativ-empty-suggest is-compact">' +
                '<div class="crm-v3-ativ-empty-heading is-compact">' +
                    '<i class="fa-solid fa-lightbulb" aria-hidden="true"></i>' +
                    '<span>Próximos passos sugeridos</span>' +
                    '<span class="crm-v3-quick-ativ-count">' + total + '</span>' +
                '</div>' +
                '<div class="crm-v3-quick-ativ-grid is-compact">' + cards + '</div>' +
                more +
                '</div>'
            );
        }

        return (
            '<div class="crm-v3-ativ-empty-suggest">' +
            '<div class="crm-v3-ativ-empty-heading">' +
                '<i class="fa-solid fa-lightbulb" aria-hidden="true"></i>' +
                '<span>Próximos passos sugeridos</span>' +
            '</div>' +
            '<div class="crm-v3-quick-ativ-grid">' + cards + '</div>' +
            more +
            '</div>'
        );
    }

    function bindQuickAtividades(root) {
        $$('[data-open-sugestoes]', root).forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (window.crmV3Drawer && typeof window.crmV3Drawer.openSugestoes === 'function') {
                    window.crmV3Drawer.openSugestoes(state.clienteId);
                }
            });
        });

        var titulo = $('#crm-v3-composer-titulo');
        var tipoBtn = $('#crm-v3-composer-tipo');
        var dataInput = $('#crm-v3-composer-data');
        if (!titulo || !tipoBtn) return;

        $$('.crm-v3-quick-ativ', root).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var sTitulo = btn.getAttribute('data-suggestion-titulo') || '';
                var sTipo = btn.getAttribute('data-suggestion-tipo') || 'atividade';
                var sDays = parseInt(btn.getAttribute('data-suggestion-days') || '0', 10);
                var d = new Date();
                d.setDate(d.getDate() + sDays);
                var dataISO = d.toISOString().slice(0, 10);

                if (window.crmV3Drawer && typeof window.crmV3Drawer.openAtividade === 'function') {
                    window.crmV3Drawer.openAtividade({
                        titulo: sTitulo,
                        tipo: sTipo,
                        data: dataISO,
                        status: 'pendente'
                    }, state.clienteId, { gerarRoteiro: true });
                    return;
                }

                titulo.value = sTitulo;

                // Sincroniza o botão de tipo (mesma sequência do composer).
                var tipos = ['atividade', 'ligacao', 'reuniao', 'email', 'whatsapp', 'doc', 'planejamento'];
                var tipoIdx = tipos.indexOf(sTipo);
                if (tipoIdx === -1) tipoIdx = 0;
                tipoBtn.setAttribute('data-tipo', sTipo);
                tipoBtn.setAttribute('data-tipo-idx', String(tipoIdx));
                var icons = {
                    atividade: 'fa-regular fa-circle-check',
                    ligacao: 'fa-solid fa-phone',
                    reuniao: 'fa-solid fa-video',
                    email: 'fa-solid fa-envelope',
                    whatsapp: 'fa-brands fa-whatsapp',
                    doc: 'fa-regular fa-file-lines',
                    planejamento: 'fa-solid fa-diagram-project'
                };
                tipoBtn.innerHTML = '<i class="' + icons[sTipo] + '" aria-hidden="true"></i>';
                // Data sugerida (hoje + daysAhead).
                if (dataInput) {
                    var d = new Date();
                    d.setDate(d.getDate() + sDays);
                    dataInput.value = d.toISOString().slice(0, 10);
                }
                titulo.focus();
                titulo.select();
            });
        });
    }

    function bindAtividadeEvents(container) {
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
                        syncClienteSituacao(state.clienteId, state.atividades);
                        showToast(novoStatus === 'concluida' ? 'Atividade concluída' : 'Atividade reaberta');
                    })
                    .catch(function (err) { showToast(err.message, true); });
            } else if (action === 'editar') {
                // Prefere o drawer novo (design system cx-*) — só cai
                // no modal legado se o plugin de drawers não carregou.
                if (window.crmV3Drawer && typeof window.crmV3Drawer.openAtividade === 'function') {
                    window.crmV3Drawer.openAtividade(a, state.clienteId);
                } else {
                    openAtividadeModal(a);
                }
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
        // Hora foi removida do composer em set/2026 — só faz sentido no
        // drawer de edição. Ver `_drawer_atividade.html`.
        var tipoBtn = $('#crm-v3-composer-tipo');

        // Data padrão = hoje, mínimo = hoje. Impede escolher datas
        // passadas para atividades novas (que são sempre "a fazer").
        var hojeISO = new Date().toISOString().slice(0, 10);
        if (dataInput) {
            dataInput.min = hojeISO;
            if (!dataInput.value) dataInput.value = hojeISO;
        }

        // Ciclo de tipos de atividade
        var tipos = [
            { id: 'atividade', icon: 'fa-regular fa-circle-check', label: 'Atividade' },
            { id: 'ligacao',   icon: 'fa-solid fa-phone',          label: 'Ligação' },
            { id: 'reuniao',   icon: 'fa-solid fa-video',          label: 'Reunião' },
            { id: 'email',     icon: 'fa-solid fa-envelope',       label: 'E-mail' },
            { id: 'whatsapp',  icon: 'fa-brands fa-whatsapp',      label: 'WhatsApp' },
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
                data: dataInput.value || hoje,
                data_label: dataInput.value && dataInput.value !== hoje ? 'Agendada' : 'Hoje',
                responsavel: responsavelIniciais,
                responsavel_nome: responsavelNome || undefined,
                status: 'pendente'
            };

            // Otimista: cria placeholder e re-renderiza imediatamente
            var tempId = 'tmp-' + Date.now();
            var placeholder = Object.assign({ id: tempId, _pending: true }, body);
            state.atividades.unshift(placeholder);
            renderAtividades();
            syncClienteSituacao(state.clienteId, state.atividades);
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
                syncClienteSituacao(state.clienteId, state.atividades);
                showToast('Atividade adicionada');
            }).catch(function (err) {
                var idx = state.atividades.findIndex(function (a) { return a.id === tempId; });
                if (idx !== -1) state.atividades.splice(idx, 1);
                renderAtividades();
                syncClienteSituacao(state.clienteId, state.atividades);
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

    // Classificação de cotações em 3 grupos visuais (set/2026):
    //  - EM_ANDAMENTO: trabalho ativo (rascunho / enviada / em acompanhamento)
    //  - APROVADA:     ganho comercial confirmado (destaque verde separado)
    //  - HISTORICO:    rejeitada / expirada / demais status (cinza compacto)
    // A separação de "aprovada" num grupo próprio veio da imagem
    // reference do usuário — no Pipedrive/HubSpot ganhos ficam
    // destacados em verde, atalhando revisão de pipeline fechado.
    var COT_STATUS_EM_ANDAMENTO = ['rascunho', 'enviada', 'em-acompanhamento', 'em_acompanhamento'];
    var COT_STATUS_APROVADA = ['aprovada', 'ganha', 'fechada'];

    function cotacaoGrupo(c) {
        var s = String(c.status || '').toLowerCase();
        if (COT_STATUS_EM_ANDAMENTO.indexOf(s) !== -1) return 'em_andamento';
        if (COT_STATUS_APROVADA.indexOf(s) !== -1) return 'aprovada';
        return 'historico';
    }

    // Compat: `cotacaoEstaAberta` continua exportada por outros pontos do
    // arquivo (updateTabCounts etc.). Marcamos como "em andamento" —
    // aprovada NÃO conta como aberta.
    function cotacaoEstaAberta(c) {
        return cotacaoGrupo(c) === 'em_andamento';
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
        // Badge de vínculo: mostra se cotação é de cliente vinculado (agência/final)
        var origemBadge = '';
        if (c.origem === 'vinculado' && c.cliente_nome) {
            origemBadge = '<span class="crm-v3-cotacao-origem" title="Cotação de cliente vinculado: ' + escapeHtml(c.cliente_nome) + '">' +
                '<i class="fas fa-link" aria-hidden="true"></i> ' + escapeHtml(c.cliente_nome) +
            '</span>';
        }
        return (
            '<article class="crm-v3-cotacao-card crm-v3-cotacao-card-aberta' + (c.origem === 'vinculado' ? ' crm-v3-cotacao-vinculada' : '') + '" data-cotacao-id="' + escapeHtml(c.id) + '">' +
            origemBadge +
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
        // Badge de vínculo para cotações de clientes vinculados
        var origemLabel = '';
        if (c.origem === 'vinculado' && c.cliente_nome) {
            origemLabel = '<span class="crm-v3-cotacao-linha-origem" title="' + escapeHtml(c.cliente_nome) + '"><i class="fas fa-link" aria-hidden="true"></i></span>';
        }
        return (
            '<button type="button" class="crm-v3-cotacao-linha crm-v3-cotacao-detalhes' + (c.origem === 'vinculado' ? ' crm-v3-cotacao-linha-vinculada' : '') + '" data-cotacao-id="' + escapeHtml(c.id) + '" title="' + (c.origem === 'vinculado' ? 'Cotação de ' + escapeHtml(c.cliente_nome) : 'Abrir detalhes') + '">' +
                origemLabel +
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

    /**
     * Render da coluna "Cotações recentes" — 3 grupos visuais.
     *
     * Set/2026: refatorado por pedido do usuário. Antes tinha 2 grupos
     * (Em aberto / Histórico) e não distinguia visualmente cotações
     * ganhas. Agora:
     *
     *   1. **Em andamento** — cards em tom neutro, mostram todos os
     *      detalhes (título, plataformas, período, valor). São o foco
     *      de trabalho do executivo. Sempre visíveis com header, mesmo
     *      vazias, para dar previsibilidade da estrutura da coluna.
     *
     *   2. **Aprovadas** — cards em VERDE (background suave), sinalizam
     *      pipeline realizado. Só aparecem quando há aprovadas — não
     *      confundem a UI com header vazio.
     *
     *   3. **Histórico** — linhas CINZA compactas (rejeitadas, expiradas,
     *      demais). Sem cores fortes, é arquivo de referência. Igual
     *      antes mas visualmente mais discreto (mesma paleta cinza pra
     *      todas as linhas).
     *
     * Vínculos (agência ↔ cliente final): cada cotação vem com
     * `origem: 'proprio' | 'vinculado'` do backend. `cliente_nome`
     * aparece no card como pill "🔗 Griletto" quando vinculado.
     * Nada muda aqui — só a agrupação.
     */
    function renderCotacoes() {
        var container = $('#crm-v3-cotacao-list');
        if (!container) return;
        updateTabCounts();

        // Separa por grupo em uma única passada (mais barato que 3 filters).
        var emAndamento = [];
        var aprovadas = [];
        var historico = [];
        (state.cotacoes || []).forEach(function (c) {
            var g = cotacaoGrupo(c);
            if (g === 'em_andamento') emAndamento.push(c);
            else if (g === 'aprovada') aprovadas.push(c);
            else historico.push(c);
        });

        // Ordena aprovadas e histórico por período_fim desc → cotações
        // mais recentes primeiro (fica melhor para revisão comercial).
        function porDataDesc(a, b) {
            var da = a.periodo_fim || a.data || '';
            var db = b.periodo_fim || b.data || '';
            if (db > da) return 1;
            if (db < da) return -1;
            return 0;
        }
        aprovadas.sort(porDataDesc);
        historico.sort(porDataDesc);

        // Se realmente não há nada em nenhum grupo, mostra empty state
        // único no lugar dos 3 headers vazios.
        if (!state.cotacoes.length) {
            container.innerHTML =
                '<div class="crm-v3-cotacao-empty">' +
                    '<i class="fa-regular fa-file-lines" aria-hidden="true"></i>' +
                    '<p>Nenhuma cotação registrada para este cliente</p>' +
                    '<span class="crm-v3-cotacao-empty-hint">Cotações da agência vinculada também aparecem aqui.</span>' +
                '</div>';
            return;
        }

        var html = '';

        // -------- Grupo 1: Em andamento --------
        html += '<div class="crm-v3-cotacao-grupo crm-v3-cotacao-grupo-em-andamento">' +
                '<div class="crm-v3-cotacao-grupo-title">' +
                    '<i class="fa-solid fa-circle-play crm-v3-cotacao-grupo-icon" aria-hidden="true"></i>' +
                    '<span>Em andamento</span>' +
                    '<span class="crm-v3-cotacao-grupo-count">' + emAndamento.length + '</span>' +
                '</div>';
        if (emAndamento.length) {
            html += emAndamento.map(cotacaoCardAberta).join('');
        } else {
            html += '<div class="crm-v3-cotacao-empty crm-v3-cotacao-empty-inline">Nenhuma cotação em andamento.</div>';
        }
        html += '</div>';

        // -------- Grupo 2: Aprovadas (destaque verde) --------
        if (aprovadas.length) {
            html += '<div class="crm-v3-cotacao-grupo crm-v3-cotacao-grupo-aprovadas">' +
                    '<div class="crm-v3-cotacao-grupo-title">' +
                        '<i class="fa-solid fa-circle-check crm-v3-cotacao-grupo-icon" aria-hidden="true"></i>' +
                        '<span>Aprovadas</span>' +
                        '<span class="crm-v3-cotacao-grupo-count">' + aprovadas.length + '</span>' +
                    '</div>' +
                    aprovadas.map(cotacaoCardAprovada).join('') +
                    '</div>';
        }

        // -------- Grupo 3: Histórico (cinza compacto) --------
        if (historico.length) {
            html += '<div class="crm-v3-cotacao-grupo crm-v3-cotacao-grupo-historico">' +
                    '<div class="crm-v3-cotacao-grupo-title">' +
                        '<i class="fa-solid fa-clock-rotate-left crm-v3-cotacao-grupo-icon" aria-hidden="true"></i>' +
                        '<span>Histórico</span>' +
                        '<span class="crm-v3-cotacao-grupo-count">' + historico.length + '</span>' +
                    '</div>' +
                    '<div class="crm-v3-cotacao-historico-list">' +
                        historico.map(cotacaoLinhaHistorico).join('') +
                    '</div>' +
                    '</div>';
        }
        container.innerHTML = html;

        // Delegação de clique para abrir detalhes (funciona para todos
        // os grupos: card aberto, card aprovada e linha histórico).
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

    /**
     * Card compacto para cotação APROVADA — destaque verde estilo
     * Pipedrive-won. Mostra título + valor + período; sem plataformas
     * detalhadas (já foi ganha, o executivo revisa se quiser detalhe
     * clicando). Se for cotação vinculada, pill do cliente.
     */
    function cotacaoCardAprovada(c) {
        var titulo = c.nome_campanha || c.titulo || 'Cotação sem título';
        var numero = c.numero_cotacao || '';
        var valor = c.valor || (c.valor_total != null ? formatBRL(Number(c.valor_total)) : '');
        var periodo = dataParaExibicao(c.periodo_fim) || dataParaExibicao(c.data) || '';
        var origemPill = '';
        if (c.origem === 'vinculado' && c.cliente_nome) {
            origemPill = '<span class="crm-v3-cotacao-origem" title="Cotação de ' + escapeHtml(c.cliente_nome) + '">' +
                '<i class="fas fa-link" aria-hidden="true"></i> ' + escapeHtml(c.cliente_nome) +
                '</span>';
        }
        return (
            '<article class="crm-v3-cotacao-card crm-v3-cotacao-card-aprovada crm-v3-cotacao-detalhes"' +
                ' data-cotacao-id="' + escapeHtml(c.id) + '"' +
                ' role="button" tabindex="0"' +
                ' title="Ver detalhes da cotação aprovada">' +
            '<div class="crm-v3-cotacao-aprovada-topline">' +
                '<i class="fa-solid fa-circle-check crm-v3-cotacao-aprovada-icon" aria-hidden="true"></i>' +
                '<span class="crm-v3-cotacao-aprovada-titulo">' + escapeHtml(titulo) + '</span>' +
                (valor ? '<span class="crm-v3-cotacao-aprovada-valor">' + escapeHtml(valor) + '</span>' : '') +
            '</div>' +
            '<div class="crm-v3-cotacao-aprovada-meta">' +
                (numero ? '<span>' + escapeHtml(numero) + '</span>' : '') +
                (periodo ? '<span>' + escapeHtml(periodo) + '</span>' : '') +
                origemPill +
            '</div>' +
            '</article>'
        );
    }

    function renderNotas() {
        // Nova estrutura (set/2026): "Notas" vive na sidebar Info como
        // uma única seção com composer + última nota em destaque +
        // histórico expansível. A aba "Notas" separada foi removida.
        // O histórico é append-only (paridade com sales_historico_cliente
        // do CRM legado) — sem edição/exclusão.
        var destaque = $('#crm-v3-nota-destaque');
        var destaqueTexto = $('#crm-v3-nota-destaque-texto');
        var destaqueMeta = $('#crm-v3-nota-destaque-meta');
        var toggle = $('#crm-v3-nota-anteriores-toggle');
        var toggleLabel = $('#crm-v3-nota-anteriores-label');
        var anterioresList = $('#crm-v3-nota-anteriores-list');
        var countInline = $('#crm-v3-notas-count-inline');

        updateTabCounts();

        var notas = state.notas || [];

        // Ordena mais recentes primeiro (defensivo — backend já entrega
        // ordenado, mas alguns mocks podem não fazer isso).
        var ordenadas = notas.slice().sort(function (a, b) {
            var da = a.data || '';
            var db = b.data || '';
            if (db < da) return -1;
            if (db > da) return 1;
            return 0;
        });

        // Contador ao lado do título ("Notas 3").
        if (countInline) {
            if (ordenadas.length > 0) {
                countInline.textContent = String(ordenadas.length);
                countInline.hidden = false;
            } else {
                countInline.hidden = true;
            }
        }

        if (!ordenadas.length) {
            if (destaque) destaque.hidden = true;
            if (toggle) toggle.hidden = true;
            if (anterioresList) { anterioresList.hidden = true; anterioresList.innerHTML = ''; }
            return;
        }

        // ---- Última nota (destaque) ----
        var ultima = ordenadas[0];
        if (destaque) destaque.hidden = false;
        if (destaqueTexto) destaqueTexto.textContent = ultima.texto || '';
        if (destaqueMeta) {
            var autor = (ultima.autor || '').trim();
            var dataStr = dataParaExibicao(ultima.data) || '';
            destaqueMeta.textContent = [autor, dataStr].filter(Boolean).join(' · ');
        }

        // ---- Anteriores (colapsadas) ----
        var anteriores = ordenadas.slice(1);
        if (toggle) {
            if (!anteriores.length) {
                toggle.hidden = true;
                if (anterioresList) { anterioresList.hidden = true; anterioresList.innerHTML = ''; }
            } else {
                toggle.hidden = false;
                if (toggleLabel) {
                    toggleLabel.textContent =
                        (toggle.getAttribute('aria-expanded') === 'true' ? 'Ocultar' : 'Ver') +
                        ' anteriores (' + anteriores.length + ')';
                }
            }
        }
        if (anterioresList) {
            anterioresList.innerHTML = anteriores.map(function (nota) {
                var autor = (nota.autor || '').trim();
                var dataStr = dataParaExibicao(nota.data) || '';
                var meta = [autor, dataStr].filter(Boolean).join(' · ');
                return (
                    '<article class="crm-v3-nota-anterior" data-nota-id="' + escapeHtml(nota.id) + '">' +
                    (meta
                        ? '<div class="crm-v3-nota-anterior-meta"><i class="fa-regular fa-user" aria-hidden="true"></i>' + escapeHtml(meta) + '</div>'
                        : '') +
                    '<p class="crm-v3-nota-anterior-texto">' + escapeHtml(nota.texto || '') + '</p>' +
                    '</article>'
                );
            }).join('');
        }
    }

    /**
     * Bind único (no boot) do composer inline de notas + toggle
     * "Ver anteriores". Toda interação usa `state.clienteId` atual.
     *
     * Fluxo do submit:
     *   1) Validação simples (texto não vazio).
     *   2) POST /clientes/<id>/notas.
     *   3) Recarrega state.notas e re-renderiza a seção.
     *   4) Limpa o textarea; foco fica no campo para próxima nota.
     */
    function bindNotasComposer() {
        var form = $('#crm-v3-nota-composer');
        var input = $('#crm-v3-nota-composer-input');
        var submit = $('#crm-v3-nota-composer-submit');
        var toggle = $('#crm-v3-nota-anteriores-toggle');
        var anterioresList = $('#crm-v3-nota-anteriores-list');
        var toggleLabel = $('#crm-v3-nota-anteriores-label');

        if (form && input && submit) {
            var updateSubmitState = function () {
                submit.disabled = !input.value.trim() || !state.clienteId;
            };
            input.addEventListener('input', updateSubmitState);
            // Cmd/Ctrl + Enter envia rapidamente.
            input.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) {
                    ev.preventDefault();
                    if (!submit.disabled) form.dispatchEvent(new Event('submit', { cancelable: true }));
                }
                if (ev.key === 'Escape') {
                    input.value = '';
                    updateSubmitState();
                }
            });

            form.addEventListener('submit', function (ev) {
                ev.preventDefault();
                if (!state.clienteId) {
                    showToast('Selecione um cliente antes de adicionar uma nota.', true);
                    return;
                }
                var texto = (input.value || '').trim();
                if (!texto) return;
                var prev = submit.innerHTML;
                submit.disabled = true;
                submit.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Salvando…';
                api('/clientes/' + encodeURIComponent(state.clienteId) + '/notas', {
                    method: 'POST',
                    body: { texto: texto }
                }).then(function () {
                    input.value = '';
                    updateSubmitState();
                    // Recarrega o histórico completo para incluir a nova
                    // nota em destaque + refletir metadados do backend
                    // (autor real, timestamp exato). Autoclose do
                    // "anteriores" para o usuário ver a última no topo.
                    if (toggle && toggle.getAttribute('aria-expanded') === 'true') {
                        toggle.setAttribute('aria-expanded', 'false');
                        if (anterioresList) anterioresList.hidden = true;
                    }
                    return loadNotas(state.clienteId);
                }).then(function () {
                    showToast('Nota adicionada.');
                    input.focus();
                }).catch(function (err) {
                    showToast(err.message || 'Falha ao adicionar nota.', true);
                }).finally(function () {
                    submit.innerHTML = prev;
                    updateSubmitState();
                });
            });
        }

        if (toggle && anterioresList) {
            toggle.addEventListener('click', function () {
                var expanded = toggle.getAttribute('aria-expanded') === 'true';
                var novoEstado = !expanded;
                toggle.setAttribute('aria-expanded', String(novoEstado));
                anterioresList.hidden = !novoEstado;
                if (toggleLabel) {
                    var total = anterioresList.querySelectorAll('.crm-v3-nota-anterior').length;
                    toggleLabel.textContent =
                        (novoEstado ? 'Ocultar' : 'Ver') +
                        ' anteriores (' + total + ')';
                }
            });
        }
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
            syncClienteSituacao(clienteId, state.atividades);
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

    function selectCliente(clienteId, opts) {
        opts = opts || {};
        if (!clienteId) return;
        if (String(state.clienteId) === String(clienteId) && state.cliente) {
            if (isMobileCrm() && !opts.fromHistory) {
                setMobileView('detail');
                syncClienteHash(clienteId, !!opts.replaceUrl);
            }
            return;
        }
        state.clienteId = clienteId;
        state.cliente = state.clientes.find(function (c) { return String(c.id) === String(clienteId); });
        state.atividades = [];
        state.objetivos = [];
        state.cotacoes = [];
        state.notas = [];
        updateClienteActiveCard();
        updateDetailPanel(state.cliente);
        renderAtividades();
        renderObjetivos();
        renderCotacoes();
        renderNotas();
        showSidebarInformacoes();
        if (isMobileCrm()) {
            setMobileView('detail');
            if (!opts.fromHistory) syncClienteHash(clienteId, !!opts.replaceUrl);
        }
        api('/clientes/' + encodeURIComponent(clienteId)).then(function (data) {
            if (state.clienteId !== clienteId) return; // trocou enquanto carregava
            if (data && data.cliente) {
                var prevSite = state.cliente && state.cliente.site_url;
                var prevLogo = state.cliente && state.cliente.web_logo_url;
                var prevBadge = state.cliente && state.cliente.badge;
                var prevBadgeType = state.cliente && state.cliente.badge_type;
                var prevProx = state.cliente && state.cliente.proxima_atividade;
                state.cliente = Object.assign({}, state.cliente || {}, data.cliente);
                if (!state.cliente.site_url && prevSite) state.cliente.site_url = prevSite;
                if (!state.cliente.web_logo_url && prevLogo) state.cliente.web_logo_url = prevLogo;
                if (!state.cliente.badge && prevBadge) {
                    state.cliente.badge = prevBadge;
                    state.cliente.badge_type = prevBadgeType;
                    state.cliente.proxima_atividade = prevProx;
                }
                var idx = state.clientes.findIndex(function (c) { return String(c.id) === String(clienteId); });
                if (idx !== -1) state.clientes[idx] = state.cliente;
                updateDetailPanel(state.cliente);
                updateClienteCardBadge(clienteId);
                var cachedWeb = state.webInfoCache[String(clienteId)] || state.webInfoCache[clienteId];
                if (cachedWeb !== undefined) renderWebInfo(cachedWeb);
            }
        }).catch(function () { /* já temos um cliente base do listing */ });
        loadContatos(clienteId);
        loadAtividades(clienteId);
        loadObjetivos(clienteId);
        loadCotacoes(clienteId);
        loadNotas(clienteId);
        loadIncentivos(clienteId);
        // Fase B (set/2026): dispara em paralelo o fetch do web-info
        // cacheado. Se não houver cache no backend (nunca scrapeamos),
        // o GET retorna 404 e renderWebInfo mostra o CTA "Buscar
        // informações". Um logo canônico já em cache é aplicado no
        // header do cliente automaticamente (via updateDetailPanel
        // que checa state.webInfoCache).
        loadWebInfo(clienteId);
        saveSession({ lastClientId: clienteId });
    }

    function loadClientes() {
        showClientesSkeleton();
        return api('/clientes').then(function (data) {
            state.clientes = data.clientes || [];
            renderClientes();
            if (state.clientes.length) {
                var hashId = clienteIdFromHash();
                if (isMobileCrm()) {
                    var doHash = hashId && state.clientes.some(function (c) {
                        return String(c.id) === String(hashId);
                    });
                    if (doHash) {
                        selectCliente(hashId, { replaceUrl: true, fromHistory: true });
                        setMobileView('detail');
                    } else {
                        setMobileView('list');
                    }
                } else {
                    var sess = loadSession();
                    var candidato =
                        state.clientes.find(function (c) { return c.id === state.clienteId; }) ||
                        state.clientes.find(function (c) { return c.id === sess.lastClientId; }) ||
                        state.clientes[0];
                    selectCliente(candidato.id);
                }
            }
        }).catch(function (err) {
            var container = $('#crm-v3-lista-clientes');
            if (err && err.storeUnavailable) {
                if (container) {
                    container.innerHTML =
                        '<div class="crm-v3-contatos-empty p-3">' +
                        '<i class="fa-solid fa-circle-exclamation" aria-hidden="true"></i> ' +
                        'Banco indisponível. Nada carregado — verifique o Postgres.' +
                        '</div>';
                }
                _handleStoreUnavailable(err);
                return;
            }
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

        // Popula os selects com dados reais ANTES do setVal — senão o
        // select ainda está com placeholder "Carregando…" e o valor
        // selecionado se perde. Passamos o cliente para o helper pré-
        // selecionar via data-field.
        var _modal = document.getElementById('crm-v3-modal-cliente');
        if (_modal && window.crmV3Drawer && window.crmV3Drawer.lookups) {
            try { window.crmV3Drawer.lookups.applyToRoot(_modal, cliente); } catch (_) {}
        }

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
            // O select de Tipo agora usa id_tipo_cliente numérico direto
            // (populado por /crm-v3/api/lookups). Antes convertíamos label
            // → "publico"/"privado" — inconsistente com a base real. As
            // options são reescritas em `openModal` via applyToRoot, então
            // o setVal aqui só precisa passar o id.
            setVal('#crm-v3-cliente-tipo', cliente.id_tipo_cliente || '');
            // Executivo: select agora usa executivo_id (int). Convertemos
            // string→string do mesmo id que já vem no _map_cliente.
            setVal('#crm-v3-cliente-responsavel', cliente.executivo_id || '');
            setVal('#crm-v3-cliente-perfil', cliente.perfil || (cliente.is_agencia ? 'agencia' : 'direto'));

            setVal('#crm-v3-cliente-cep', endereco.cep || cliente.cep || '');
            setVal('#crm-v3-cliente-uf', endereco.uf || cliente.uf || '');
            setVal('#crm-v3-cliente-cidade', endereco.cidade || cliente.cidade || '');
            setVal('#crm-v3-cliente-bairro', endereco.bairro || cliente.bairro || '');
            setVal('#crm-v3-cliente-logradouro', endereco.logradouro || cliente.logradouro || '');
            setVal('#crm-v3-cliente-numero', endereco.numero || cliente.numero || '');
            setVal('#crm-v3-cliente-complemento', endereco.complemento || cliente.complemento || '');

            setVal('#crm-v3-cliente-classificacao', cliente.classificacao_cliente || cliente.classificacao || 'Prospecção');
            // (Executivo já foi setado acima com o id numérico do lookup.)
            // Prioridade removida do modelo do cliente em set/2026 —
            // não existe na base (`tbl_cliente`). Mantido setChk/setVal
            // para os campos que realmente existem.
            setVal('#crm-v3-cliente-bv', cliente.bv_percentual != null ? cliente.bv_percentual : '');
            setVal('#crm-v3-cliente-margem', cliente.margem_cc != null ? cliente.margem_cc : '');
            setChk('#crm-v3-cliente-opera-midia', cliente.opera_midia);
            setChk('#crm-v3-cliente-demanda-dados', cliente.demanda_dados);
            setChk('#crm-v3-cliente-programatica', cliente.demanda_programatica_canais);
            setVal('#crm-v3-cliente-obs', cliente.observacoes_comerciais_adicionais || cliente.observacoes || '');

            renderAgenciasVinculadas(cliente);
        } else {
            // Novo cliente: pré-preencher executivo do filtro atual
            if (state.filtroExecutivo) {
                setVal('#crm-v3-cliente-responsavel', state.filtroExecutivo);
            }
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
        } else {
            // Nova atividade: pré-preencher executivo do filtro atual
            var respSelect = $('#crm-v3-atividade-responsavel');
            if (respSelect && state.filtroExecutivo) {
                respSelect.value = state.filtroExecutivo;
            }
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
        var responsavelSelect = $('#crm-v3-cotacao-responsavel');
        if (cotacao) {
            $('#crm-v3-cotacao-titulo').value = cotacao.nome_campanha || cotacao.titulo || '';
            $('#crm-v3-cotacao-valor').value = cotacao.valor_total || cotacao.valor || '';
            $('#crm-v3-cotacao-status').value = cotacao.status || 'rascunho';
            if (objetivoInput) objetivoInput.value = cotacao.objetivo || '';
            if (plataformasInput) plataformasInput.value = Array.isArray(cotacao.plataformas) ? cotacao.plataformas.join(', ') : (cotacao.plataformas || '');
            if (responsavelSelect) responsavelSelect.value = cotacao.responsavel_id || cotacao.executivo_id || '';
        } else {
            if (objetivoInput) objetivoInput.value = '';
            if (plataformasInput) plataformasInput.value = '';
            // Nova cotação: pré-preencher executivo do filtro atual
            if (responsavelSelect && state.filtroExecutivo) {
                responsavelSelect.value = state.filtroExecutivo;
            }
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
        // Guard-rail: sem cliente selecionado, o modal abre em modo
        // "vazio" (alerta vermelho + botão Processar desabilitado)
        // em vez de crashar no submit. Antes o usuário só descobria
        // que faltava selecionar cliente após colar 100 linhas.
        var cliente = state.clienteId
            ? state.clientes.find(function (c) { return c.id === state.clienteId; })
            : null;

        renderImportTarget(cliente);

        state.importRows = [];
        var texto = $('#crm-v3-import-texto');
        if (texto) texto.value = '';
        setImportDropzoneState('idle');
        setImportStep(1);
        openModal('crm-v3-modal-import');
    }

    /* ================================================================
     * Importar contatos — Dropzone de IMAGEM + OCR (Gemini 2.5 Flash)
     * ----------------------------------------------------------------
     * Novo fluxo (set/2026): usuário arrasta / cola (⌘V) / faz upload
     * de um print (WhatsApp, LinkedIn, cartão, assinatura de e-mail)
     * e a IA extrai os contatos automaticamente. Cai direto no step 2
     * (revisão) sem precisar formatar Nome;email;telefone;cargo à mão.
     *
     * Fontes de imagem suportadas:
     *   1. Drag-and-drop → dragover/drop no #crm-v3-import-dropzone
     *   2. Paste (⌘V) → listener no document quando o modal está open
     *   3. Click → input file oculto (#crm-v3-import-file)
     *   4. Keyboard (Enter/Space no dropzone) → mesma coisa que click
     *
     * A rota /crm-v3/api/ia/ocr-contatos aceita multipart/form-data
     * (mais eficiente que base64 no wire). Se der erro, a mensagem
     * vai pra #crm-v3-import-error e o usuário pode cair no
     * fluxo tradicional (colar texto).
     * ================================================================ */

    // Troca o estado visual do dropzone: idle | loading | preview.
    // Também escreve o texto contextual do preview (msg + count).
    function setImportDropzoneState(estado, extras) {
        var wrap = $('#crm-v3-import-dropzone');
        if (!wrap) return;
        wrap.dataset.dropzoneState = estado;
        wrap.querySelectorAll('[data-dropzone-state]').forEach(function (bloco) {
            bloco.hidden = (bloco.dataset.dropzoneState !== estado);
        });
        if (estado === 'preview' && extras) {
            var imgEl = $('#crm-v3-import-preview-img');
            if (imgEl && extras.previewUrl) imgEl.src = extras.previewUrl;
            var msgEl = $('#crm-v3-import-preview-msg');
            if (msgEl) msgEl.textContent = extras.msg || 'Imagem processada.';
            var countEl = $('#crm-v3-import-preview-count');
            if (countEl) countEl.textContent = extras.hint || '';
        }
    }

    // Processa um File/Blob: valida, mostra loading, chama a rota OCR,
    // popula state.importRows + textarea + vai pra step 2.
    // Retorna Promise para permitir chained testing (não usado hoje).
    function processarImagemImport(file) {
        if (!file) return Promise.resolve();

        // Validações rápidas no cliente pra não desperdiçar OCR.
        var TIPOS_OK = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/heic', 'image/heif'];
        var TAM_MAX_MB = 8;
        if (TIPOS_OK.indexOf((file.type || '').toLowerCase()) === -1) {
            showToast('Formato não suportado: ' + (file.type || 'desconhecido') + '. Use PNG, JPG, WEBP ou HEIC.', true);
            return Promise.resolve();
        }
        if (file.size > TAM_MAX_MB * 1024 * 1024) {
            showToast('Imagem muito grande (máx ' + TAM_MAX_MB + ' MB).', true);
            return Promise.resolve();
        }
        if (!state.clienteId) {
            showToast('Selecione um cliente antes de importar.', true);
            return Promise.resolve();
        }

        // URL local (blob:) pra preview instantâneo — não usa base64.
        var previewUrl = URL.createObjectURL(file);
        setImportDropzoneState('loading');

        // Limpa erros antigos.
        var errEl = $('#crm-v3-import-error');
        if (errEl) { errEl.textContent = ''; errEl.hidden = true; }

        // multipart/form-data direto — o helper api() é JSON, então
        // usamos fetch cru aqui (mesma URL base, mesmo login cookie).
        var formData = new FormData();
        formData.append('file', file, file.name || 'contatos.png');

        return fetch(API_BASE + '/ia/ocr-contatos', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData,
        }).then(function (resp) {
            return resp.json().then(function (body) {
                if (!resp.ok || (body && body.success === false)) {
                    var msg = (body && body.error) || ('Erro HTTP ' + resp.status);
                    throw new Error(msg);
                }
                return body;
            });
        }).then(function (body) {
            var data = body.data || {};
            var contatos = data.contatos || [];

            // Preview + contagem.
            setImportDropzoneState('preview', {
                previewUrl: previewUrl,
                msg: contatos.length
                    ? contatos.length + ' contato(s) reconhecido(s) pela IA'
                    : 'Nenhum contato reconhecido na imagem',
                hint: 'Fonte: Gemini 2.5 Flash · revise abaixo antes de importar',
            });

            if (!contatos.length) {
                // Se o modelo trouxe raw_text, joga no textarea pra
                // dar chance do usuário limpar manualmente.
                if (data.raw_text) {
                    var ta = $('#crm-v3-import-texto');
                    if (ta) ta.value = data.raw_text;
                }
                showToast(data.message || 'Nenhum contato reconhecido — tente colar como texto.', true);
                return;
            }

            // Normaliza para o mesmo shape que o parse-texto usa.
            state.importRows = contatos.map(function (c) {
                return {
                    nome: c.nome || '',
                    email: c.email || '',
                    telefone: c.telefone || '',
                    cargo: c.cargo || '',
                    principal: false,
                };
            });
            renderImportTable();
            setImportStep(2);
            showToast(contatos.length + ' contato(s) reconhecido(s) pela IA — revise abaixo.');
        }).catch(function (err) {
            setImportDropzoneState('idle');
            var el = $('#crm-v3-import-error');
            if (el) {
                el.textContent = 'IA falhou: ' + (err.message || 'erro desconhecido');
                el.hidden = false;
            }
            showToast(err.message || 'Falha ao processar imagem', true);
        });
    }

    // Bind único (chamado em initModals) para os handlers do dropzone.
    function bindImportDropzone() {
        var zone = $('#crm-v3-import-dropzone');
        var fileInput = $('#crm-v3-import-file');
        var resetBtn = $('#crm-v3-import-preview-reset');
        if (!zone || !fileInput) return;

        // Click no dropzone → abre file picker. Só no estado idle
        // (evita reabrir picker durante loading / preview).
        zone.addEventListener('click', function () {
            if (zone.dataset.dropzoneState === 'idle') {
                fileInput.click();
            }
        });
        // Enter/Space no dropzone com foco → mesma coisa (a11y).
        zone.addEventListener('keydown', function (ev) {
            if ((ev.key === 'Enter' || ev.key === ' ') && zone.dataset.dropzoneState === 'idle') {
                ev.preventDefault();
                fileInput.click();
            }
        });

        // File picker → processa.
        fileInput.addEventListener('change', function () {
            var f = fileInput.files && fileInput.files[0];
            if (f) processarImagemImport(f);
            // Reset pra permitir o mesmo arquivo ser selecionado depois.
            fileInput.value = '';
        });

        // Reset preview → volta pro idle. O user pode enviar outra
        // imagem sem fechar o modal.
        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                setImportDropzoneState('idle');
                state.importRows = [];
                var ta = $('#crm-v3-import-texto');
                if (ta) ta.value = '';
                var errEl = $('#crm-v3-import-error');
                if (errEl) errEl.hidden = true;
            });
        }

        // Drag-and-drop. Prevent default nos eventos globais também
        // (senão o browser abre a imagem em uma nova aba se o usuário
        // errar o dropzone).
        ['dragover', 'dragenter'].forEach(function (evtName) {
            zone.addEventListener(evtName, function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                if (zone.dataset.dropzoneState === 'idle') {
                    zone.classList.add('is-drag-over');
                }
            });
        });
        ['dragleave', 'dragend'].forEach(function (evtName) {
            zone.addEventListener(evtName, function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                zone.classList.remove('is-drag-over');
            });
        });
        zone.addEventListener('drop', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            zone.classList.remove('is-drag-over');
            if (zone.dataset.dropzoneState !== 'idle') return;
            var dt = ev.dataTransfer;
            var f = dt && dt.files && dt.files[0];
            if (f) processarImagemImport(f);
        });

        // Paste no document quando o modal está aberto.
        // Feito no document (não no zone) porque paste não bubble bem
        // em elementos sem foco de input. Filtra pra só disparar
        // quando o modal está open (visualmente relevante).
        document.addEventListener('paste', function (ev) {
            var dialog = $('#crm-v3-modal-import');
            if (!dialog || !dialog.open) return;
            // Se o foco está no textarea, deixa o paste normal (texto).
            var alvo = document.activeElement;
            if (alvo && alvo.tagName === 'TEXTAREA') return;
            var items = ev.clipboardData && ev.clipboardData.items;
            if (!items) return;
            for (var i = 0; i < items.length; i++) {
                var it = items[i];
                if (it.kind === 'file' && it.type.indexOf('image/') === 0) {
                    var f = it.getAsFile();
                    if (f) {
                        ev.preventDefault();
                        processarImagemImport(f);
                        return;
                    }
                }
            }
        });
    }

    /**
     * Mostra o "chip" do cliente-alvo no topo do modal Importar contatos.
     *
     * Reaproveita o mesmo raciocínio do avatar principal (Clearbit logo
     * do domínio → fallback iniciais). Se o cliente for null, mostra
     * o estado de erro e desabilita os controles do modal.
     */
    function renderImportTarget(cliente) {
        var ok = $('#crm-v3-import-target-ok');
        var empty = $('#crm-v3-import-target-empty');
        var processar = $('#crm-v3-import-processar');
        var submit = $('#crm-v3-import-submit');
        var textarea = $('#crm-v3-import-texto');

        if (!cliente) {
            if (ok) ok.hidden = true;
            if (empty) empty.hidden = false;
            if (processar) processar.disabled = true;
            if (submit) submit.disabled = true;
            if (textarea) textarea.disabled = true;
            return;
        }

        if (empty) empty.hidden = true;
        if (ok) ok.hidden = false;
        if (processar) processar.disabled = false;
        if (submit) submit.disabled = false;
        if (textarea) textarea.disabled = false;

        // Nome + subtítulo (perfil/classificação).
        var nomeEl = $('#crm-v3-import-target-nome');
        if (nomeEl) nomeEl.textContent = cliente.nome || cliente.nome_fantasia || cliente.razao_social || 'Cliente sem nome';
        var metaEl = $('#crm-v3-import-target-meta');
        if (metaEl) {
            var partes = [];
            if (cliente.classificacao_cliente) partes.push(cliente.classificacao_cliente);
            if (cliente.tipo_label) partes.push(cliente.tipo_label);
            if (cliente.responsavel) partes.push(cliente.responsavel);
            metaEl.textContent = partes.join(' · ');
        }

        // Iniciais como fallback + logo Clearbit (mesma regra do header).
        var iniciaisEl = $('#crm-v3-import-target-initials');
        var img = $('#crm-v3-import-target-logo');
        var nomeCliente = (cliente.nome || cliente.nome_fantasia || cliente.razao_social || '?').trim();
        var partesNome = nomeCliente.split(/\s+/);
        var iniciais = (
            (partesNome[0] || '').charAt(0) +
            (partesNome[1] || '').charAt(0)
        ).toUpperCase() || '?';
        if (iniciaisEl) iniciaisEl.textContent = iniciais;

        // Logo real (og:image). Sem Clearbit/globo.
        if (img) {
            img.hidden = true;
            img.alt = '';
            var logo = logoRealDoCliente(cliente);
            if (logo) {
                img.onload = function () {
                    if (img.naturalWidth > 0) img.hidden = false;
                };
                img.onerror = function () { img.hidden = true; };
                img.src = logo;
            }
        }
    }

    function initModals() {
        $$('[data-close-modal]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeModal(btn.getAttribute('data-close-modal'));
            });
        });

        // Dropzone de imagem no modal "Importar contatos" — bind único.
        // Drag-and-drop, paste (⌘V) e upload; OCR via Gemini 2.5 Flash.
        bindImportDropzone();

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
                var tipoSelect = $('#crm-v3-cliente-tipo');
                var tipoValue = tipoSelect ? tipoSelect.value : '';
                // O select agora usa o id_tipo_cliente numérico da base
                // (via /crm-v3/api/lookups). Antes eram strings hardcoded
                // "privado"/"publico" — set/2026.
                var tipoLabelOpt = tipoSelect && tipoSelect.options[tipoSelect.selectedIndex];
                var tipoLabel = tipoLabelOpt ? tipoLabelOpt.textContent.trim() : '';
                var tipoIntVal = parseInt(tipoValue, 10);
                if (!isNaN(tipoIntVal)) tipoValue = tipoIntVal;
                // Executivo agora usa id_contato_cliente (executivo_id).
                var execSelect = $('#crm-v3-cliente-responsavel');
                var execIdVal = execSelect ? parseInt(execSelect.value, 10) : NaN;
                var execIdSend = isNaN(execIdVal) ? null : execIdVal;
                var execNomeSend = '';
                if (execSelect && execSelect.selectedIndex >= 0) {
                    var _opt = execSelect.options[execSelect.selectedIndex];
                    if (_opt) execNomeSend = _opt.textContent.trim();
                }
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
                    responsavel: execNomeSend,
                    executivo_id: execIdSend,
                    prioridade: null,
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

    function showSidebarInformacoes() {
        var btn = document.getElementById('tab-sidebar-info');
        if (btn && !btn.classList.contains('is-active')) btn.click();
        var wrap = document.querySelector('.crm-v3-sidebar-panel-wrap');
        if (wrap) wrap.scrollTop = 0;
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
            // Grupo "atividades" foi removido do UI — a coluna agrupa
            // por data e não usa mais aba Todas/Pendentes/Concluídas.
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
        if (sess.filtroSecundario != null) state.filtroSecundario = sess.filtroSecundario;
        // Sessões antigas gravavam atrasado/sem-atividade/arquivo em filtroPill.
        if (state.filtroPill === 'todos') state.filtroPill = 'classif-ativo';
        if (state.filtroPill === 'atrasado' || state.filtroPill === 'sem-atividade' || state.filtroPill === 'arquivo') {
            state.filtroSecundario = state.filtroPill;
            state.filtroPill = 'classif-ativo';
        }
        if (state.filtroPill !== 'classif-ativo' && state.filtroPill !== 'classif-prospeccao') {
            state.filtroPill = 'classif-ativo';
        }
        if (sess.filtroTipo != null) state.filtroTipo = sess.filtroTipo;
        if (sess.filtroPerfil != null) state.filtroPerfil = sess.filtroPerfil;

        // Executivo: se o usuário nunca escolheu um valor específico (chave
        // `filtroExecutivo` ausente do storage — não é o mesmo que "vazio"),
        // pré-seleciona o executivo logado (window.CRM_V3_CONTEXT.userName).
        // Assim ele já entra vendo a base dele; se depois marcar "Executivo:
        // todos" e voltar, aquela escolha fica salva.
        if ('filtroExecutivo' in sess) {
            state.filtroExecutivo = sess.filtroExecutivo;
        } else {
            var ctx = window.CRM_V3_CONTEXT || {};
            var selfName = ctx.userName || '';
            var options = $$('#filtro-executivo option');
            var eu = options.filter(function (o) { return o.hasAttribute('data-eu'); })[0];
            if (eu) {
                state.filtroExecutivo = eu.value;
            } else if (selfName && options.some(function (o) { return o.value === selfName; })) {
                state.filtroExecutivo = selfName;
            }
        }
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
            var f = p.getAttribute('data-filter');
            var isClassif = f === 'classif-ativo' || f === 'classif-prospeccao';
            var active = isClassif
                ? (f === state.filtroPill && state.filtroSecundario !== 'arquivo')
                : (f === state.filtroSecundario);
            p.classList.toggle('is-active', active);
            p.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function initFilters() {
        $$('.crm-v3-pill').forEach(function (pill) {
            pill.addEventListener('click', function () {
                var f = pill.getAttribute('data-filter') || 'classif-ativo';
                var isClassif = f === 'classif-ativo' || f === 'classif-prospeccao';
                if (isClassif) {
                    state.filtroPill = f;
                    if (state.filtroSecundario === 'arquivo') state.filtroSecundario = '';
                } else if (state.filtroSecundario === f) {
                    state.filtroSecundario = '';
                } else {
                    state.filtroSecundario = f;
                }
                state.paginaCliente = 1;
                syncFiltrosParaDom();
                renderClientes();
                saveSession({
                    filtroPill: state.filtroPill,
                    filtroSecundario: state.filtroSecundario
                });
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

    // `exportarClientesCsv` (set/2026): removida junto com o botão
    // "Exportar" do header. Os exports do CRM v3 agora usam as rotas
    // reais do backend do CRM legado:
    //   • /crm/api/export/atividades  → Exportar atividades (CSV)
    //   • /crm/api/export/objetivos   → Exportar objetivos (CSV)
    // Se quiser reintroduzir "Exportar clientes", basta reviver a
    // função a partir do git log e adicionar um item no dropdown
    // "Visões" no template.

    function initButtons() {
        var novoCliente = $('#crm-v3-btn-novo-cliente-header');
        if (novoCliente) novoCliente.addEventListener('click', function () { openClienteModal(null); });

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

        // Editor de "Site & logo" da sidebar Info — binda uma vez;
        // opera sobre state.clienteId em cada interação.
        bindSiteEditor();

        // Fase B (set/2026): liga botões da aba Web da sidebar
        // (Atualizar, Buscar informações, Cadastrar site).
        bindTabWeb();

        // Avatar do header vira atalho para editar site/logo: clica no
        // avatar → sidebar rola até "Site & logo" e foca o input.
        // (set/2026) Fluxo natural: usuário vê logo errada → clica →
        // já está pronto para digitar o domínio correto.
        bindAvatarShortcut();

        // Composer inline de notas + toggle "Ver anteriores".
        bindNotasComposer();

        var novoObjetivo = $('#crm-v3-btn-novo-objetivo');
        if (novoObjetivo) novoObjetivo.addEventListener('click', function () { openObjetivoModal(null); });
        var novaCotacao = $('#crm-v3-btn-nova-cotacao');
        if (novaCotacao) novaCotacao.addEventListener('click', function () { openCotacaoModal(null); });
        // Handler do botão "Nova nota" removido em set/2026: a criação
        // "Seguindo" continua funcional via pill de status no header.

        // Handler do botão "Ver todas atividades" removido em set/2026
        // junto com a aba "Atividades" da sidebar (redundante com a
        // coluna central).

        // O botão "estrela / favorito" foi removido da UI (setembro/2026)
        // porque `tbl_cliente` não possui coluna `favorito`. Preferimos
        // não persistir estado sintético no CRM v3 até que exista uma
        // pin/estrela por usuário no schema real.
    }

    /* ==================================================================
     * Edit-in-place (Pipedrive-style) para a aba Info da sidebar.
     * ------------------------------------------------------------------
     * Registro único de listeners via event delegation em document. Cada
     * `.crm-v3-editable-row` com `data-field` vira clicável — abre o
     * editor apropriado (text/number/select/textarea/bool). O PATCH é
     * enviado no blur/Enter; a UI recebe feedback visual (spinner /
     * check) para confirmar o auto-save. Campos vazios ficam colapsados
     * com placeholder '+ Adicionar X'.
     * ================================================================== */

    // Aplica valor + estado (empty/filled) num display. Alguns campos
    // (booleans, datas) nunca ficam "vazios" no sentido do UI (Sim/Não).
    function setEditableDisplay(sel, value, opts) {
        opts = opts || {};
        var el = typeof sel === 'string' ? $(sel) : sel;
        if (!el) return;
        var row = el.closest ? el.closest('.crm-v3-editable-row') : null;
        var placeholder = row ? (row.getAttribute('data-placeholder') || '') : '';
        var suffix = row ? (row.getAttribute('data-suffix') || '') : '';
        var raw = value;
        // Trata string vazia / null / undefined como "sem valor".
        var isEmpty = !opts.alwaysFilled && (raw === null || raw === undefined || String(raw).trim() === '');
        if (row) row.classList.toggle('is-empty', !!isEmpty);
        if (isEmpty) {
            el.textContent = placeholder ? '+ ' + placeholder : '—';
        } else {
            var txt = String(raw);
            // Se o backend já formatou (ex.: "5,00%"), não duplica sufixo.
            if (suffix && txt && txt.indexOf(suffix) === -1) txt = txt + suffix;
            el.textContent = txt;
        }
    }

    // Retorna o valor "cru" do campo para inicializar o editor (não o
    // valor formatado do display). Usa state.cliente como fonte da verdade.
    function rawFieldValue(field) {
        var c = state.cliente || {};
        // Aliases de rótulo → coluna do banco.
        switch (field) {
            case 'nome': return c.nome_fantasia || c.nome;
            case 'observacoes_comerciais_adicionais':
                return c.observacoes_comerciais_adicionais;
            case 'nota_executivo_vendas': return c.nota_executivo;
            case 'percentual': return c.bv_percentual;
            case 'cnpj': return c.cnpj;
            case 'cidade': return c.cidade || (c.endereco && c.endereco.cidade);
            case 'cep': return c.cep || (c.endereco && c.endereco.cep);
            case 'bairro': return c.bairro || (c.endereco && c.endereco.bairro);
            case 'logradouro': return c.logradouro || (c.endereco && c.endereco.logradouro);
            case 'numero': return c.numero || (c.endereco && c.endereco.numero);
            case 'complemento': return c.complemento || (c.endereco && c.endereco.complemento);
            case 'classificacao_cliente':
                return c.classificacao_cliente || c.classificacao;
            case 'opera_midia':
            case 'demanda_dados':
            case 'demanda_programatica_canais':
            case 'margem_cc':
                return c[field];
            default:
                return c[field];
        }
    }

    // Constrói o editor apropriado para o tipo do campo. Retorna
    // {editor, getValue, focus} para uso pelo controlador.
    function buildEditor(row) {
        var type = row.getAttribute('data-type') || 'text';
        var field = row.getAttribute('data-field');
        var currentValue = rawFieldValue(field);
        var editor;
        if (type === 'select') {
            editor = document.createElement('select');
            editor.className = 'crm-v3-editable-input';
            var options = [];
            try { options = JSON.parse(row.getAttribute('data-options') || '[]'); }
            catch (e) { options = []; }
            options.forEach(function (opt) {
                var o = document.createElement('option');
                o.value = opt.value;
                o.textContent = opt.label;
                if (String(currentValue || '') === String(opt.value)) o.selected = true;
                editor.appendChild(o);
            });
        } else if (type === 'textarea') {
            editor = document.createElement('textarea');
            editor.className = 'crm-v3-editable-input crm-v3-editable-textarea';
            editor.rows = 4;
            editor.value = currentValue == null ? '' : String(currentValue);
        } else if (type === 'bool') {
            // Toggle inline via par de radios com aparência de segmented control.
            editor = document.createElement('div');
            editor.className = 'crm-v3-editable-bool';
            editor.setAttribute('role', 'group');
            ['true', 'false'].forEach(function (v) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.dataset.value = v;
                btn.className = 'crm-v3-editable-bool-btn';
                btn.textContent = v === 'true' ? 'Sim' : 'Não';
                if ((v === 'true' && !!currentValue) || (v === 'false' && !currentValue)) {
                    btn.classList.add('is-active');
                }
                editor.appendChild(btn);
            });
        } else {
            editor = document.createElement('input');
            editor.type = type === 'number' ? 'number' : 'text';
            if (type === 'number') { editor.step = '0.01'; editor.min = '0'; }
            editor.className = 'crm-v3-editable-input';
            editor.value = currentValue == null ? '' : String(currentValue);
            if (field === 'cep') {
                editor.setAttribute('inputmode', 'numeric');
                editor.setAttribute('maxlength', '9');
                editor.placeholder = '00000-000';
                editor.addEventListener('input', function () {
                    editor.value = formatarCep(editor.value, true);
                });
            }
        }
        return {
            editor: editor,
            getValue: function () {
                if (type === 'bool') {
                    var active = editor.querySelector('.is-active');
                    return active ? (active.dataset.value === 'true') : false;
                }
                if (type === 'number') {
                    var v = String(editor.value || '').trim();
                    if (!v) return null;
                    return parseFloat(v.replace(',', '.'));
                }
                return String(editor.value || '').trim();
            },
            focus: function () {
                if (type === 'bool') {
                    var active = editor.querySelector('.is-active') || editor.firstElementChild;
                    if (active) active.focus();
                } else {
                    editor.focus();
                    if (typeof editor.select === 'function') editor.select();
                }
            }
        };
    }

    function _isSameValue(a, b) {
        // Igualdade leniente: '' == null, número/string equivalentes.
        if (a === b) return true;
        var aa = a == null || a === '' ? '' : String(a);
        var bb = b == null || b === '' ? '' : String(b);
        return aa === bb;
    }

    // Persiste o valor via PATCH /api/clientes/<id>. Atualiza o display
    // e o state.cliente. Se o server der 4xx/5xx, reverte o display
    // para o valor anterior e exibe toast — comportamento previsível.
    function saveEditableField(row, newValue) {
        var field = row.getAttribute('data-field');
        var display = row.querySelector('[data-editable-display]');
        if (!field || !state.clienteId) return Promise.resolve();
        var prev = rawFieldValue(field);
        if (_isSameValue(prev, newValue)) return Promise.resolve(); // no-op

        row.classList.add('is-saving');
        row.classList.remove('is-error');

        var payload = {};
        payload[field] = newValue;

        var ready = Promise.resolve(payload);
        if (field === 'cep') {
            payload.cep = formatarCep(newValue);
            ready = buscarEnderecoPorCep(payload.cep).then(function (end) {
                if (!end) return payload;
                if (end.bairro) payload.bairro = end.bairro;
                if (end.logradouro) payload.logradouro = end.logradouro;
                if (end.cidade) payload.cidade = end.cidade;
                if (end.uf) payload.uf = end.uf;
                return payload;
            });
        }
        if (field === 'cidade') {
            var ufCap = ufPorCapitalOperacao(newValue);
            if (ufCap) payload.uf = ufCap;
        }

        return ready.then(function (body) {
            var preencheuEndereco = field === 'cep' && !!(body.bairro || body.logradouro || body.cidade);
            return api('/clientes/' + encodeURIComponent(state.clienteId), {
                method: 'PATCH',
                body: body
            }).then(function (resp) {
            row.classList.remove('is-saving');
            row.classList.add('is-saved');
            setTimeout(function () { row.classList.remove('is-saved'); }, 1200);
            // Atualiza state a partir do cliente que o backend devolveu.
            if (resp && resp.cliente) {
                state.cliente = Object.assign({}, state.cliente || {}, resp.cliente);
                var idx = state.clientes.findIndex(function (c) { return c.id === state.clienteId; });
                if (idx !== -1) state.clientes[idx] = state.cliente;
            } else if (state.cliente) {
                Object.keys(body).forEach(function (k) { state.cliente[k] = body[k]; });
            }
            // Re-formata o display com base no state atualizado.
            updateDetailPanel(state.cliente);
            if (preencheuEndereco) showToast('Endereço atualizado pelo CEP');
        }).catch(function (err) {
            row.classList.remove('is-saving');
            row.classList.add('is-error');
            setTimeout(function () { row.classList.remove('is-error'); }, 1600);
            showToast(err.message || 'Falha ao salvar', true);
            // Reverte o texto para o valor original.
            if (display) updateDetailPanel(state.cliente);
        });
        });
    }

    // Abre o editor inline para uma linha. Um único editor aberto por vez.
    var _activeEditable = null;
    function closeActiveEditable(save) {
        if (!_activeEditable) return;
        var ctx = _activeEditable;
        _activeEditable = null;
        var row = ctx.row;
        row.classList.remove('is-editing');
        if (ctx.editorWrap && ctx.editorWrap.parentNode) {
            ctx.editorWrap.parentNode.removeChild(ctx.editorWrap);
        }
        if (ctx.display) ctx.display.hidden = false;
        if (save) {
            var val = ctx.getValue();
            saveEditableField(row, val);
        }
    }

    function openEditable(row) {
        if (_activeEditable && _activeEditable.row === row) return;
        // Fecha o editor anterior (salvando).
        closeActiveEditable(true);

        var type = row.getAttribute('data-type');
        if (!type || type === 'readonly') return;
        var display = row.querySelector('[data-editable-display]');
        if (!display) return;

        var built = buildEditor(row);
        var wrap = document.createElement('div');
        wrap.className = 'crm-v3-editable-editor';
        wrap.appendChild(built.editor);
        row.classList.add('is-editing');
        display.hidden = true;
        display.parentNode.insertBefore(wrap, display.nextSibling);

        _activeEditable = { row: row, editorWrap: wrap, display: display, getValue: built.getValue, type: type };

        // Handlers: Enter/blur/Escape.
        var handleKeydown = function (e) {
            if (e.key === 'Escape') {
                e.preventDefault();
                closeActiveEditable(false);
            } else if (e.key === 'Enter' && type !== 'textarea') {
                e.preventDefault();
                closeActiveEditable(true);
            }
        };
        var handleChange = function () {
            if (type === 'select' || type === 'bool') closeActiveEditable(true);
        };
        var handleBoolClick = function (ev) {
            var btn = ev.target.closest('.crm-v3-editable-bool-btn');
            if (!btn) return;
            $$('.crm-v3-editable-bool-btn', built.editor).forEach(function (b) {
                b.classList.remove('is-active');
            });
            btn.classList.add('is-active');
            // Salva imediatamente após clique.
            closeActiveEditable(true);
        };
        var handleBlur = function () {
            // Delay para permitir click em <option>/<button> antes do blur.
            setTimeout(function () {
                if (_activeEditable && _activeEditable.row === row
                    && !row.contains(document.activeElement)) {
                    closeActiveEditable(true);
                }
            }, 100);
        };

        built.editor.addEventListener('keydown', handleKeydown);
        if (type === 'select') built.editor.addEventListener('change', handleChange);
        if (type === 'bool') built.editor.addEventListener('click', handleBoolClick);
        built.editor.addEventListener('blur', handleBlur, true);

        built.focus();
    }

    function initInfoEditable() {
        // Delegação: um único listener no sidebar cobre todas as linhas.
        var sidebar = document.getElementById('crm-v3-sidebar');
        if (!sidebar) return;
        sidebar.addEventListener('click', function (ev) {
            var row = ev.target.closest && ev.target.closest('.crm-v3-editable-row');
            if (!row) return;
            var type = row.getAttribute('data-type');
            if (!type || type === 'readonly') return;
            // Clique já dentro de um editor aberto — ignora.
            if (row.classList.contains('is-editing') && ev.target.closest('.crm-v3-editable-editor')) return;
            ev.preventDefault();
            openEditable(row);
        });
    }

    function initMobileNav() {
        var back = $('#crm-v3-mobile-back');
        if (back) {
            back.addEventListener('click', function (e) {
                e.preventDefault();
                openMobileList();
            });
        }
        window.addEventListener('popstate', function () {
            applyMobileFromUrl();
        });
        var onMq = function () {
            if (!isMobileCrm()) {
                setMobileView(null);
                return;
            }
            if (state.clienteId && clienteIdFromHash()) {
                setMobileView('detail');
            } else if (state.clienteId) {
                setMobileView('detail');
                syncClienteHash(state.clienteId, true);
            } else {
                setMobileView('list');
            }
        };
        if (CRM_MOBILE_MQ.addEventListener) CRM_MOBILE_MQ.addEventListener('change', onMq);
        else if (CRM_MOBILE_MQ.addListener) CRM_MOBILE_MQ.addListener(onMq);
        if (isMobileCrm()) setMobileView('list');
    }

    initModals();
    initMobileNav();
    initTabs('sidebar');
    // Restaura filtros do localStorage antes de bindar handlers para não
    // disparar renders extras — o `syncFiltrosParaDom` só ajusta valores
    // e o primeiro `renderClientes` (dentro de `loadClientes`) já usa o
    // state consolidado.
    restoreFiltros();
    syncFiltrosParaDom();
    initFilters();
    initButtons();
    initInfoEditable();
    bindClientesListDelegation();
    showOverlay('Carregando CRM…');
    loadClientes().finally(hideOverlay);

    // Exporta uma superfície mínima para módulos externos (crm_v3_drawers.js, atalhos)
    window.crmV3 = {
        state: state,
        reloadClientes: function (clienteIdParaSelecionar) {
            if (clienteIdParaSelecionar) state.clienteId = clienteIdParaSelecionar;
            return loadClientes();
        },
        getQuickSuggestions: getSuggestionsForClient,
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
