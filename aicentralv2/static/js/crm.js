(function () {
    'use strict';

    const BASE = '/crm';
    const CRM_EXECUTIVO_COOKIE = 'crm_executivo_id';
    let clienteSelecionadoId = null;
    let contatoSelecionadoId = null;
    let modalContatoId = null;
    let modalClienteId = null;
    let chartInstances = {};
    let crmCliCache = [];
    let crmContatosCache = [];
    let crmConversasCache = [];
    let crmConversaSelecionadaId = null;
    let telefoneSelecionado = null;
    let crmChatPollTimer = null;
    let crmChatLastMsgCount = 0;
    let crmContatoBusca = '';
    let crmChatBusca = '';
    let crmChatTab = 'todas';
    let crmCliPage = 0;
    const CRM_CLI_PAGE_SIZE = 12;


    // ==================== Helpers ====================

    function $(sel, ctx) { return (ctx || document).querySelector(sel); }
    function $$(sel, ctx) { return [...(ctx || document).querySelectorAll(sel)]; }

    function showSpinner(container) {
        container.innerHTML = '<div class="flex justify-center py-8"><span class="loading loading-spinner loading-md"></span></div>';
    }

    function showEmpty(container, msg) {
        container.innerHTML = `<div class="crm-empty-state">${msg}</div>`;
    }

    async function api(path, opts = {}) {
        const resp = await fetch(BASE + path, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            const error = new Error(err.error || `HTTP ${resp.status}`);
            error.data = err;
            throw error;
        }
        return resp.json();
    }

    function fmtBRL(v) {
        const n = Number(v) || 0;
        return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function fmtDate(iso) {
        if (!iso) return '-';
        const d = new Date(iso);
        return d.toLocaleDateString('pt-BR');
    }

    function fmtDateShort(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    }

    function debounce(fn, ms) {
        let t;
        return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }

    function scrollIntoViewSuave(el, options) {
        if (window.scrollIntoViewSuave) {
            window.scrollIntoViewSuave(el, options);
            return;
        }
        if (!el) return;
        el.scrollIntoView(Object.assign({
            behavior: window.getScrollBehavior ? window.getScrollBehavior() : 'smooth',
            block: 'nearest'
        }, options || {}));
    }

    function onlyDigits(value) {
        return String(value || '').replace(/\D/g, '');
    }

    function maskCpfCnpj(input) {
        let v = onlyDigits(input.value);
        if (v.length <= 11) {
            v = v.slice(0, 11)
                .replace(/(\d{3})(\d)/, '$1.$2')
                .replace(/(\d{3})(\d)/, '$1.$2')
                .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
        } else {
            v = v.slice(0, 14)
                .replace(/^(\d{2})(\d)/, '$1.$2')
                .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
                .replace(/\.(\d{3})(\d)/, '.$1/$2')
                .replace(/(\d{4})(\d)/, '$1-$2');
        }
        input.value = v;
    }

    function maskCep(input) {
        input.value = onlyDigits(input.value).slice(0, 8).replace(/(\d{5})(\d)/, '$1-$2');
    }

    function maskPercentual(input) {
        let v = onlyDigits(input.value).slice(0, 4);
        if (!v) {
            input.value = '';
            return;
        }
        input.value = (parseInt(v, 10) / 100).toFixed(2).replace('.', ',');
    }

    function maskMoneyBR(input, hiddenInput) {
        const digits = onlyDigits(input.value);
        if (!digits) {
            input.value = '';
            if (hiddenInput) hiddenInput.value = '';
            return;
        }
        const value = parseInt(digits, 10) / 100;
        input.value = value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        if (hiddenInput) hiddenInput.value = value.toFixed(2);
    }

    function isoDatePlusDays(days) {
        const d = new Date();
        d.setDate(d.getDate() + days);
        return d.toISOString().slice(0, 10);
    }

    /** Carteira: é agência (cadastro Sim), vem da API como eh_agencia boolean */
    function clienteEhAgencia(c) {
        if (c.eh_agencia === true) return true;
        if (c.eh_agencia === false) return false;
        return c.is_agencia === true;
    }

    function clienteEhParceiroRegional(c) {
        const tipo = String(c.tipo_cliente_display || '').toLowerCase();
        return tipo.includes('parceiro');
    }

    function subtituloCliente(c) {
        if (clienteEhAgencia(c)) return 'Agência';
        if (c.agencia_principal_nome) return `Agência principal: ${c.agencia_principal_nome}`;
        return 'Cliente final';
    }

    function atualizarContadoresCarteira(clientes, perfil) {
        const wrap = $('#crm-contador-carteira');
        const chipA = $('#crm-chip-ag');
        const chipC = $('#crm-chip-cli');
        const letraA = $('#crm-letra-a');
        const letraC = $('#crm-letra-c');
        const elA = $('#crm-n-agencias');
        const elC = $('#crm-n-clientes');
        if (!wrap || !chipA || !chipC || !elA || !elC) return;
        let nAg = 0;
        let nCli = 0;
        for (const c of clientes || []) {
            if (clienteEhAgencia(c)) nAg++;
            else nCli++;
        }
        elA.textContent = String(nAg);
        elC.textContent = String(nCli);

        // Perfil: todos → A e C com letras. Cliente final → só contagem (sem letra C). Agência → só contagem (sem letra A).
        if (perfil === 'direto') {
            chipA.classList.add('hidden');
            chipC.classList.remove('hidden');
            letraC?.classList.add('hidden');
            letraA?.classList.remove('hidden');
        } else if (perfil === 'agencia') {
            chipA.classList.remove('hidden');
            chipC.classList.add('hidden');
            letraA?.classList.add('hidden');
            letraC?.classList.remove('hidden');
        } else {
            chipA.classList.remove('hidden');
            chipC.classList.remove('hidden');
            letraA?.classList.remove('hidden');
            letraC?.classList.remove('hidden');
        }

        wrap.classList.remove('hidden');
    }

    function esconderContadoresCarteira() {
        const wrap = $('#crm-contador-carteira');
        if (!wrap) return;
        wrap.classList.add('hidden');
    }

    // ==================== Column 1: Clientes ====================

    async function carregarClientes() {
        const execId = $('#filtro-executivo').value;
        const tipo = $('#filtro-tipo')?.value || '';
        const perfil = $('#filtro-perfil')?.value || '';
        const busca = $('#busca-cliente').value.trim();
        const container = $('#lista-clientes');

        if (!execId) {
            esconderContadoresCarteira();
            showEmpty(container, 'Selecione um executivo para carregar a carteira.');
            limparColunas();
            return;
        }

        showSpinner(container);
        try {
            const params = new URLSearchParams({ executivo_id: execId, tipo, busca });
            if (perfil) params.set('perfil', perfil);
            const data = await api(`/api/clientes?${params}`);
            crmCliCache = data.clientes || [];
            crmCliPage = 0;
            atualizarContadoresCarteira(crmCliCache, perfil);
            if (!crmCliCache.length) {
                esconderPaginacaoClientes();
                showEmpty(container, 'Nenhum cliente encontrado.');
                return;
            }
            renderClientesPagina();
        } catch (e) {
            esconderContadoresCarteira();
            esconderPaginacaoClientes();
            showEmpty(container, 'Erro ao carregar clientes.');
            console.error(e);
        }
    }

    function esconderPaginacaoClientes() {
        $('#crm-clientes-paginacao')?.classList.add('hidden');
        $('#crm-contador-total')?.classList.add('hidden');
    }

    function renderClientesPagina() {
        const container = $('#lista-clientes');
        const total = crmCliCache.length;

        const order = ['Prospecção', 'Ativo', 'Geladeira'];
        const labelFor = (c) => {
            const v = (c.classificacao_cliente || '').trim();
            return order.includes(v) ? v : 'Sem classificação';
        };
        const nomeFor = (c) => (c.nome_fantasia || c.razao_social || '').trim();
        const grupos = new Map();
        for (const c of crmCliCache) {
            const label = labelFor(c);
            if (!grupos.has(label)) grupos.set(label, []);
            grupos.get(label).push(c);
        }
        for (const lista of grupos.values()) {
            lista.sort((a, b) => nomeFor(a).localeCompare(nomeFor(b), 'pt-BR', { sensitivity: 'base' }));
        }

        const labels = order.concat([...grupos.keys()].filter(k => !order.includes(k)).sort((a, b) => a.localeCompare(b, 'pt-BR')));
        const cardHtml = (c) => `
            <div class="crm-card ${c.id_cliente == clienteSelecionadoId ? 'crm-card-active' : ''}"
                 data-id="${c.id_cliente}">
                <div class="flex items-center justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="crm-cliente-nome truncate">${nomeFor(c).toUpperCase()}</div>
                        <div class="crm-cliente-subtitulo">${subtituloCliente(c)} · ${c.qtd_contatos} contato(s)</div>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                        <button type="button" class="crm-cliente-edit btn btn-ghost btn-xs btn-square h-5 w-5 min-h-0 p-0" data-id="${c.id_cliente}" title="Editar cliente" aria-label="Editar cliente">
                            ${ICON_EDIT}
                        </button>
                    </div>
                </div>
            </div>`;

        container.innerHTML = labels.map(label => {
            const lista = grupos.get(label) || [];
            if (!lista.length) return '';
            return `
                <details class="crm-classificacao-grupo" data-classificacao="${escapeHtml(label)}">
                    <summary class="crm-classificacao-header">
                        <span class="crm-classificacao-titulo">${escapeHtml(label)}</span>
                        <span class="crm-classificacao-count">${lista.length}</span>
                    </summary>
                    <div class="crm-classificacao-lista">
                        ${lista.map(cardHtml).join('')}
                    </div>
                </details>
            `;
        }).join('');

        $$('.crm-card', container).forEach(el => {
            el.addEventListener('click', () => selecionarCliente(parseInt(el.dataset.id)));
        });

        $$('.crm-cliente-edit', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                abrirModalEditarCliente(parseInt(btn.dataset.id, 10));
            });
        });

        const footer = $('#crm-clientes-paginacao');
        const totalEl = $('#crm-contador-total');
        if (totalEl) {
            totalEl.textContent = total;
            totalEl.classList.remove('hidden');
        }
        if (footer) footer.classList.add('hidden');
    }

    function selecionarCliente(id) {
        clienteSelecionadoId = id;
        contatoSelecionadoId = null;

        $$('.crm-card', $('#lista-clientes')).forEach(el => {
            el.classList.toggle('crm-card-active', parseInt(el.dataset.id) === id);
        });
        atualizarResumoObjetivosComunicacao();

        setTabAtividades('todas');
        carregarStatus(id);
        carregarContatos(id);
        if ($('#lista-atividades')) carregarAtividades(id);
        carregarCotacoesAbertas(id);
        if ($('#lista-objetivos')) carregarObjetivos(id);
        limparWhatsAppComercial();
        carregarPreviewConversasCliente(id);
    }

    function pararPollingMensagens() {
        if (crmChatPollTimer) {
            clearInterval(crmChatPollTimer);
            crmChatPollTimer = null;
        }
        crmChatLastMsgCount = 0;
    }

    function iniciarPollingMensagens() {
        pararPollingMensagens();
        crmChatPollTimer = setInterval(() => {
            if (crmConversaSelecionadaId) {
                carregarMensagensConversa(crmConversaSelecionadaId, { silent: true });
            }
        }, 4000);
    }

    function limparWhatsAppComercial() {
        pararPollingMensagens();
        crmConversaSelecionadaId = null;
        telefoneSelecionado = null;
        crmConversasCache = [];
        showEmpty($('#crm-conversas-lista'), contatoSelecionadoId ? 'Selecione um telefone.' : 'Selecione um contato.');
        showEmpty($('#crm-chat-mensagens'), contatoSelecionadoId ? 'Selecione um telefone para ver a conversa.' : 'Selecione um contato e telefone.');
        atualizarResumoObjetivosComunicacao();
    }

    async function carregarPreviewConversasCliente(clienteId) {
        const container = $('#crm-conversas-lista');
        if (!container || !clienteId) return;
        try {
            const data = await api(`/api/cliente/${clienteId}/comunicacao/conversas`);
            const conversas = data.conversas || [];
            if (!conversas.length) {
                showEmpty(container, 'Nenhuma conversa encontrada.');
                return;
            }
            // Popula cache global para que selecionarConversaComercial funcione
            crmConversasCache = conversas;
            container.innerHTML = conversas.slice(0, 15).map(cv => `
                <div class="crm-conversa" data-id="${cv.id}" data-contato-id="${cv.contato_id || ''}" data-preview="1" style="cursor:pointer">
                    <div class="crm-conversa-info">
                        <div class="crm-conversa-top">
                            <span>${escapeHtml(cv.contato_nome || cv.telefone || '—')}</span>
                            <small>${formatHoraMsg(cv.ultimo_evento_em)}</small>
                        </div>
                        <div class="crm-conversa-preview">${escapeHtml((cv.ultimo_preview || 'Sem mensagens ainda.').slice(0, 60))}</div>
                    </div>
                </div>
            `).join('');
            $$('.crm-conversa[data-preview]', container).forEach(el => {
                el.addEventListener('click', () => {
                    const contatoId = parseInt(el.dataset.contatoId, 10) || null;
                    if (contatoId) selecionarContatoCrm(contatoId, { manterWhatsApp: true });
                    selecionarConversaComercial(parseInt(el.dataset.id, 10));
                });
            });
        } catch (e) {
            showEmpty(container, 'Erro ao carregar conversas.');
        }
    }

    function limparColunas() {
        pararPollingMensagens();
        clienteSelecionadoId = null;
        contatoSelecionadoId = null;
        crmConversaSelecionadaId = null;
        telefoneSelecionado = null;
        crmContatosCache = [];
        crmConversasCache = [];
        showEmpty($('#area-status'), 'Selecione um cliente.');
        if ($('#lista-objetivos')) showEmpty($('#lista-objetivos'), 'Selecione um cliente.');
        showEmpty($('#lista-contatos'), 'Selecione um cliente.');
        if ($('#lista-atividades')) showEmpty($('#lista-atividades'), 'Selecione um cliente.');
        atualizarResumoObjetivosComunicacao();
        showEmpty($('#lista-cotacoes'), 'Selecione um cliente.');
        showEmpty($('#crm-conversas-lista'), 'Selecione um cliente.');
        showEmpty($('#crm-chat-mensagens'), 'Selecione uma conversa.');
        const count = $('#crm-cotacoes-count');
        if (count) count.textContent = '';
    }

    async function carregarCotacoesAbertas(clienteId) {
        const container = $('#lista-cotacoes');
        if (!container) return;
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/cotacoes-abertas`);
            renderCotacoesAbertas(data.cotacoes || []);
        } catch (e) {
            showEmpty(container, 'Erro ao carregar cotações.');
            console.error(e);
        }
    }

    function badgeStatusCotacao(status) {
        const s = status || 'Rascunho';
        const cls = s === 'Enviada' ? 'crm-cot-status-enviada' : 'crm-cot-status-rascunho';
        return `<span class="crm-cot-status ${cls}">${escapeHtml(s)}</span>`;
    }

    function renderCotacoesAbertas(cotacoes) {
        const container = $('#lista-cotacoes');
        const count = $('#crm-cotacoes-count');
        if (!container) return;
        if (count) count.textContent = cotacoes.length ? String(cotacoes.length) : '';
        if (!cotacoes.length) {
            showEmpty(container, 'Nenhuma cotação aberta para este cliente.');
            return;
        }
        container.innerHTML = cotacoes.map(c => {
            const titulo = c.numero_cotacao || `#${c.id}`;
            const campanha = c.nome_campanha || 'Campanha sem nome';
            return `
                <a class="crm-cot-card" href="/cotacoes/${c.id}/detalhes">
                    <div class="crm-cot-top">
                        <span class="crm-cot-numero">${escapeHtml(titulo)}</span>
                        ${badgeStatusCotacao(c.status)}
                    </div>
                    <div class="crm-cot-campanha">${escapeHtml(campanha)}</div>
                    <div class="crm-cot-meta">
                        <span>${fmtBRL(c.valor_total_proposta || 0)}</span>
                        <span>${fmtDate(c.created_at)}</span>
                    </div>
                </a>
            `;
        }).join('');
    }

    // ==================== Column 2: Status ====================

    /**
     * Badge de variação vs mês anterior.
     * pct null => sem base de comparação (mês anterior zerado): não renderiza badge.
     * lowerIsBetter inverte as cores (ex.: Erros).
     */
    function deltaText(pct, lowerIsBetter) {
        if (pct === null || pct === undefined) return { html: '', cls: '' };
        const positivo = pct >= 0;
        const bom = lowerIsBetter ? !positivo : positivo;
        const cls = pct === 0 ? '' : (bom ? 'crm-metric-delta-up' : 'crm-metric-delta-down');
        const arrow = pct === 0 ? '' : (positivo ? '↑' : '↓');
        return { html: `${arrow} ${Math.abs(pct)}% vs mês ant.`, cls };
    }

    function metricCard(valor, label, deltaPct, lowerIsBetter = false, isCurrency = false) {
        const delta = deltaText(deltaPct, lowerIsBetter);
        return `
            <div class="crm-metric-card">
                <span class="crm-metric-valor${isCurrency ? ' crm-metric-currency' : ''}">${valor}</span>
                ${delta.html ? `<span class="crm-metric-delta ${delta.cls}">${delta.html}</span>` : ''}
                <div class="crm-metric-label">${label}</div>
            </div>`;
    }

    function proximoPassoStatus(s) {
        if (s.erros > 0) {
            return `Você tem ${s.erros} cotação(ões) rejeitada(s)/expirada(s) no mês. Revise objeções e reabra a negociação.`;
        }
        if (s.total_cotacoes > 0 && s.pct_aprovadas < 50) {
            return `Conversão de ${s.pct_aprovadas}% abaixo do ideal. Priorize follow-up das cotações pendentes.`;
        }
        if (s.total_cotacoes === 0) {
            return 'Sem cotações neste mês. Agende um contato para gerar nova oportunidade.';
        }
        if (s.cotacoes_aprovadas > 0 && s.total_pis === 0) {
            return 'Cotações aprovadas sem PI emitido. Gere o PI para faturar.';
        }
        return 'Carteira em dia. Mantenha o relacionamento com contatos-chave.';
    }

    async function carregarStatus(clienteId) {
        const container = $('#area-status');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/status`);
            const s = data.status;
            const clienteData = crmCliCache.find(c => c.id_cliente === clienteId) || {};
            const nomeCliente = clienteData.nome_fantasia || clienteData.razao_social || 'Cliente';
            const tipoCliente = clienteData.eh_agencia ? 'Agência' : 'Cliente final';
            const categoria = s.tipo_mercado || 'Privado';
            const prioridade = s.prioridade || 'Alta';
            const inicial = nomeCliente.charAt(0).toUpperCase();
            const agora = new Date().toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' });

            container.innerHTML = `
                <div class="crm-status-section">
                    <!-- Header do cliente -->
                    <div class="crm-status-cliente-header">
                        <div class="crm-status-avatar-verde">${inicial}</div>
                        <div class="crm-status-cliente-info">
                            <div class="crm-status-cliente-nome">${escapeHtml(nomeCliente).toUpperCase()}</div>
                            <div class="crm-status-cliente-tipo">${tipoCliente}</div>
                        </div>
                        <span class="crm-badge-prioridade-alta">Prioridade: ${prioridade}</span>
                    </div>

                    <!-- Info contatos -->
                    <div class="crm-status-info-row">
                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <span class="crm-status-info-text">${s.total_contatos || 0} contato(s)</span>
                    </div>

                    <!-- Responsável e Categoria -->
                    <div class="crm-status-details">
                        <div class="crm-status-detail-row">
                            <span class="crm-status-detail-label">Responsável</span>
                            <span class="crm-status-detail-value">
                                ${s.executivo_nome || '-'}
                                <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                            </span>
                        </div>
                        <div class="crm-status-detail-row">
                            <span class="crm-status-detail-label">Categoria</span>
                            <span class="crm-status-detail-value">
                                ${categoria}
                                <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
                            </span>
                        </div>
                    </div>

                    <!-- Grid de métricas 3x2 -->
                    <div class="crm-metrics-grid">
                        ${metricCardNew('Contatos', s.total_contatos || 0, s.total_contatos_delta_pct, false)}
                        ${metricCardNew('Aprovações', s.cotacoes_aprovadas || 0, s.cotacoes_aprovadas_delta_pct, false)}
                        ${metricCardNew('Faturamento', fmtBRL(s.valor_bruto || 0), s.valor_bruto_delta_pct, false)}
                        ${metricCardNew('Erros', s.erros || 0, s.erros_delta_pct, true)}
                        ${metricCardNew('Líquido', fmtBRL(s.valor_liquido || 0), s.valor_liquido_delta_pct, false)}
                        ${metricCardNew('Valor PIs', fmtBRL(s.valor_pis || 0), s.valor_pis_delta_pct, false)}
                    </div>

                    <!-- Última atualização -->
                    <div class="crm-ultima-atualizacao-row">
                        <span>Última atualização</span>
                        <span>Hoje, ${agora}</span>
                    </div>

                    <!-- Próximo passo sugerido -->
                    <div class="crm-proximo-passo-section">
                        <div class="crm-proximo-passo-titulo">Próximo passo sugerido</div>
                        <div class="crm-proximo-passo-card">
                            <div class="crm-proximo-passo-icon-circle">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                            </div>
                            <div class="crm-proximo-passo-content-text">
                                <div class="crm-proximo-passo-main">${escapeHtml(proximoPassoStatus(s))}</div>
                                <div class="crm-proximo-passo-sub">Prazo sugerido: Hoje</div>
                            </div>
                            <svg class="w-4 h-4 text-yellow-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                        </div>
                    </div>

                    <!-- Nota sobre o cliente -->
                    <div class="crm-nota-cliente-section">
                        <div class="crm-nota-cliente-header">
                            <span class="crm-nota-cliente-titulo">Nota sobre o cliente</span>
                            <button type="button" class="crm-nota-menu-btn">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/></svg>
                            </button>
                        </div>
                        <div class="crm-nota-cliente-box">
                            <textarea id="crm-nota-cliente" class="crm-nota-textarea" maxlength="8000" placeholder="Anotações visíveis para a equipe comercial..."></textarea>
                        </div>
                        <div class="crm-nota-autor-info">
                            <div class="crm-nota-autor-avatar">JF</div>
                            <div class="crm-nota-autor-details">
                                <div class="crm-nota-autor-nome">Nota realizada por ${s.executivo_nome || 'Usuário'}</div>
                                <div class="crm-nota-autor-data">Hoje, ${agora}</div>
                            </div>
                        </div>
                        <button type="button" class="crm-ver-historico-link" id="crm-ver-historico-notas">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                            Ver histórico de notas
                        </button>
                    </div>

                    <!-- Botões de ação -->
                    <div class="crm-status-action-buttons">
                        <button type="button" class="crm-btn-outline" id="btn-ver-mais-status">Ver mais dados</button>
                    </div>
                </div>
            `;

            bindStatusEvents(clienteId);
            carregarNotaCliente(clienteId);
        } catch (e) {
            showEmpty(container, 'Erro ao carregar status.');
            console.error(e);
        }
    }

    function metricCardNew(label, valor, deltaPct, lowerIsBetter = false) {
        let deltaHtml = '';
        if (deltaPct !== null && deltaPct !== undefined) {
            const isPositive = deltaPct >= 0;
            const isGood = lowerIsBetter ? !isPositive : isPositive;
            const colorClass = deltaPct === 0 ? 'text-gray-400' : (isGood ? 'text-green-500' : 'text-red-500');
            const sign = isPositive ? '+' : '';
            deltaHtml = `<div class="crm-metric-delta-new ${colorClass}">${sign}${deltaPct}%</div>`;
        }
        return `
            <div class="crm-metric-card-new">
                <div class="crm-metric-label-new">${label}</div>
                <div class="crm-metric-value-new">${valor}</div>
                ${deltaHtml}
                <div class="crm-metric-sublabel-new">vs mês ant.</div>
            </div>`;
    }

    async function carregarNotaCliente(clienteId) {
        const ta = $('#crm-nota-cliente');
        if (!ta) return;
        try {
            const data = await api(`/api/cliente/${clienteId}/nota`);
            ta.value = data.nota || '';
        } catch (_) {
            ta.value = '';
        }
    }

    function bindStatusEvents(clienteId) {
        $('#btn-ver-mais-status')?.addEventListener('click', () => abrirModalStatusCompleto(clienteId));

        $('#btn-salvar-nota-cliente')?.addEventListener('click', async () => {
            const ta = $('#crm-nota-cliente');
            if (!ta) return;
            const btn = $('#btn-salvar-nota-cliente');
            btn?.classList.add('loading');
            try {
                await api(`/api/cliente/${clienteId}/nota`, {
                    method: 'PUT',
                    body: JSON.stringify({ nota: ta.value })
                });
                showToast('Nota salva.', 'success');
            } catch (e) {
                console.error(e);
                showToast(e.message || 'Erro ao salvar nota.', 'error');
            } finally {
                btn?.classList.remove('loading');
            }
        });

    }

    // ==================== Column 3: Contatos ====================

    async function carregarContatos(clienteId) {
        const container = $('#lista-contatos');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/contatos`);
            crmContatosCache = data.contatos || [];
            popularComunicacaoContatos(crmContatosCache);
            renderContatosCrm();
        } catch (e) {
            showEmpty(container, 'Erro ao carregar contatos.');
            console.error(e);
        }
    }

    function contatoAvatar(c) {
        if (c.foto_url) {
            return `<img class="crm-avatar-img" src="${escapeHtml(c.foto_url)}" alt="">`;
        }
        const nome = (c.nome_completo || '?').trim();
        const iniciais = nome.split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase() || '?';
        return `<span>${escapeHtml(iniciais)}</span>`;
    }

    function telefoneRow(contato, telefone, idx) {
        if (!telefone) return '';
        const digits = onlyDigits(telefone);
        const qtd = idx === 1 ? (contato.unread_count || contato.qtd_conversas || 0) : Math.max(0, (contato.qtd_conversas || 0) - 1);
        return `
            <button type="button" class="crm-phone-row ${telefoneSelecionado === telefone ? 'crm-phone-row-active' : ''}" data-contato-id="${contato.id_contato_cliente}" data-telefone="${escapeHtml(telefone)}">
                <span>${escapeHtml(telefone)}</span>
                <span class="crm-phone-status">Ativo</span>
                ${qtd ? `<span class="crm-phone-count">${qtd}</span>` : ''}
                ${digits ? `<span class="crm-phone-wa" title="Abrir conversa no CRM">abrir</span>` : ''}
            </button>
        `;
    }

    function renderContatosCrm() {
        const container = $('#lista-contatos');
        if (!container) return;
        const termo = crmContatoBusca.trim().toLowerCase();
        const contatos = crmContatosCache.filter(c => {
            if (!termo) return true;
            return [c.nome_completo, c.email, c.cargo, c.telefone, c.telefone_secundario]
                .some(v => String(v || '').toLowerCase().includes(termo));
        });
        if (!contatos.length) {
            showEmpty(container, crmContatosCache.length ? 'Nenhum contato encontrado.' : 'Nenhum contato cadastrado.');
            return;
        }
        container.innerHTML = contatos.map(c => {
            const ativo = String(c.id_contato_cliente) === String(contatoSelecionadoId);
            return `
                <div class="crm-contact-card ${ativo ? 'crm-contact-card-active' : ''}" data-id="${c.id_contato_cliente}">
                    <div class="crm-contact-main">
                        <div class="crm-avatar">${contatoAvatar(c)}</div>
                        <div class="crm-contact-info">
                            <div class="crm-contact-name">${escapeHtml(c.nome_completo || 'Contato')}</div>
                            <div class="crm-contact-role">${escapeHtml(c.cargo || '')}</div>
                        </div>
                        <div class="crm-contact-badges">
                            ${(c.qtd_conversas || c.unread_count) ? `<span>${c.qtd_conversas || 0}</span>` : ''}
                            <button type="button" class="crm-contact-edit-btn" data-id="${c.id_contato_cliente}" title="Editar contato"><svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 112.828 2.828L11.828 15.828A2 2 0 0110 16.414V18h1.586a2 2 0 001.414-.586l.018-.018"/></svg></button>
                            <button type="button" class="crm-contact-toggle" title="Expandir">⌄</button>
                        </div>
                    </div>
                    <div class="crm-contact-details ${ativo ? '' : 'hidden'}">
                        ${c.email ? `
                        <div class="crm-contact-email-row">
                            <span class="crm-contact-email-text">${escapeHtml(c.email)}</span>
                            <button type="button" class="crm-email-copy-btn" data-email="${escapeHtml(c.email)}" aria-label="Copiar e-mail" title="Copiar e-mail">${ICON_COPY}</button>
                        </div>` : ''}
                        <div class="crm-contact-details-title">Conversas no WhatsApp</div>
                        ${telefoneRow(c, c.telefone, 1)}
                        ${telefoneRow(c, c.telefone_secundario, 2)}
                        <button type="button" class="crm-see-more crm-contato-whats-btn" data-contato-id="${c.id_contato_cliente}">Abrir WhatsApp &gt;</button>
                    </div>
                </div>
            `;
        }).join('');

        $$('.crm-contact-card', container).forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.crm-phone-row, .crm-email-copy-btn, .crm-contato-whats-btn, .crm-contact-toggle, .crm-contact-edit-btn')) return;
                selecionarContatoCrm(parseInt(el.dataset.id, 10));
            });
        });
        $$('.crm-contact-edit-btn', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                abrirModalContato(parseInt(btn.dataset.id, 10));
            });
        });
        $$('.crm-phone-row', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const contatoId = parseInt(btn.dataset.contatoId, 10);
                const telefone = btn.dataset.telefone || null;
                selecionarContatoCrm(contatoId, { manterWhatsApp: true });
                abrirConversaTelefone(contatoId, telefone);
            });
        });
        $$('.crm-contato-whats-btn', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const id = parseInt(btn.dataset.contatoId, 10);
                selecionarContatoCrm(id, { manterWhatsApp: true });
                const contato = crmContatosCache.find(c => String(c.id_contato_cliente) === String(id));
                const telefone = contato?.telefone || contato?.telefone_secundario || null;
                abrirConversaTelefone(id, telefone).then(() => {
                    const col = $('#col-objetivos-comunicacao');
                    if (col) scrollIntoViewSuave(col);
                    $('#crm-chat-input')?.focus();
                });
            });
        });
        $$('.crm-email-copy-btn', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const email = btn.dataset.email;
                navigator.clipboard.writeText(email).then(() => {
                    btn.innerHTML = ICON_CHECK;
                    btn.classList.add('crm-email-copy-btn-ok');
                    showToast('E-mail copiado.', 'success');
                    setTimeout(() => {
                        btn.innerHTML = ICON_COPY;
                        btn.classList.remove('crm-email-copy-btn-ok');
                    }, 2000);
                }).catch(() => showToast('Erro ao copiar e-mail.', 'error'));
            });
        });
        
    }

    function selecionarContatoCrm(id, opts = {}) {
        contatoSelecionadoId = id;
        if (!opts.manterWhatsApp) {
            telefoneSelecionado = null;
            crmConversaSelecionadaId = null;
            crmConversasCache = [];
            showEmpty($('#crm-conversas-lista'), 'Selecione um telefone.');
            showEmpty($('#crm-chat-mensagens'), 'Selecione um telefone para ver a conversa.');
        }
        setTabAtividades('contato');
        carregarAtividades(clienteSelecionadoId, id);
        atualizarResumoObjetivosComunicacao();
        renderContatosCrm();
        if (!opts.manterWhatsApp) {
            carregarAutomacaoComercial(clienteSelecionadoId, id);
        }
    }

    async function abrirConversaTelefone(contatoId, telefone = null) {
        if (!clienteSelecionadoId || !contatoId) return null;
        telefoneSelecionado = telefone;
        contatoSelecionadoId = contatoId;
        renderContatosCrm();
        atualizarResumoObjetivosComunicacao();
        return criarOuSelecionarConversa(contatoId, telefone);
    }

    function formatDateContato(dateStr) {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        const hoje = new Date();
        const ontem = new Date(hoje);
        ontem.setDate(ontem.getDate() - 1);
        
        if (d.toDateString() === hoje.toDateString()) {
            return `Hoje, ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
        } else if (d.toDateString() === ontem.toDateString()) {
            return `Ontem, ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
        }
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }

    // ==================== Column 4: Atividades ====================

    function setTabAtividades(tab) {
        atividadesTab = tab;
        $$('#tabs-atividades .crm-tab-ativ').forEach(t => {
            t.classList.toggle('crm-tab-ativ-active', t.dataset.tab === tab);
        });
    }

    const TIPO_ICONS = {
        ligacao:      '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>',
        almoco:       '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6l4 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        reuniao:      '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
        projeto:      '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>',
        planejamento: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>',
        cadu:         '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>',
        atividade:    '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
    };

    const TIPO_LABELS = {
        ligacao: 'Ligação', almoco: 'Almoço', reuniao: 'Reunião',
        projeto: 'Projeto', planejamento: 'Planejamento', cadu: 'Cadu', atividade: 'Atividade'
    };

    function atividadeVencida(a) {
        if (a.status === 'concluida' || !a.data_prazo) return false;
        return a.data_prazo < new Date().toISOString().slice(0, 10);
    }

    function atividadeHoje(a) {
        if (a.status === 'concluida' || !a.data_prazo) return false;
        return a.data_prazo === new Date().toISOString().slice(0, 10);
    }

    /** Ativas (não concluídas): prazo ascendente; sem prazo por último; empate: vencidas primeiro. */
    function sortAtividadesPorPrazoAtivas(list) {
        return list.slice().sort((a, b) => {
            const da = a.data_prazo ? String(a.data_prazo).slice(0, 10) : '9999-12-31';
            const db = b.data_prazo ? String(b.data_prazo).slice(0, 10) : '9999-12-31';
            if (da !== db) return da.localeCompare(db);
            const va = atividadeVencida(a) ? 0 : 1;
            const vb = atividadeVencida(b) ? 0 : 1;
            if (va !== vb) return va - vb;
            return String(a.id).localeCompare(String(b.id));
        });
    }

    function sortAtividadesConcluidasPorData(list) {
        return list.slice().sort((a, b) => {
            const da = a.data_atividade ? String(a.data_atividade).slice(0, 10) : '';
            const db = b.data_atividade ? String(b.data_atividade).slice(0, 10) : '';
            return db.localeCompare(da);
        });
    }

    let crmActCtx = { clienteId: null, contatoId: null };
    let crmObjCtx = { clienteId: null };
    let crmActCache = [];
    let atividadesTab = 'todas';

    function _isoDateOnly(iso) {
        if (!iso) return '';
        return String(iso).slice(0, 10);
    }

    function escapeHtml(s) {
        if (s == null || s === '') return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    const ICON_EDIT = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>';
    const ICON_TRASH = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>';
    const ICON_COPY = '<svg class="crm-icon-copy" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" stroke-width="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke-width="2"/></svg>';
    const ICON_CHECK = '<svg class="crm-icon-copy" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>';

    function badgePrioridadeAtiv(prioridade) {
        const p = (prioridade || 'media').toLowerCase();
        const config = {
            alta: { label: 'A alta', color: '#ef4444', bg: '#fef2f2' },
            media: { label: 'Média', color: '#eab308', bg: '#fefce8' },
            baixa: { label: 'Baixa', color: '#22c55e', bg: '#f0fdf4' }
        };
        const c = config[p] || config.media;
        return `<span class="crm-badge-prioridade-ativ" style="background:${c.bg};color:${c.color}"><span class="crm-badge-dot" style="background:${c.color}"></span>${c.label}</span>`;
    }

    function renderAtividadeCard(a, clienteId, contatoId) {
        const vencida = atividadeVencida(a);
        const hoje = atividadeHoje(a);
        const tipo = a.tipo || 'atividade';
        const podeFeito = a.status !== 'concluida';
        const prioridade = a.prioridade || 'media';
        const tipoLabel = TIPO_LABELS[tipo] || tipo;
        const dataFormatada = formatDateAtiv(a.data_atividade);
        return `
            <div class="crm-ativ-card ${vencida ? 'crm-ativ-vencida' : ''}" data-aid="${a.id}">
                <div class="crm-ativ-card-left">
                    ${podeFeito ? `<input type="checkbox" class="crm-ativ-checkbox crm-act-feito" data-id="${a.id}" />` : '<span class="crm-ativ-checkbox-space"></span>'}
                    <span class="crm-ativ-tipo-dot crm-tipo-dot-${tipo}"></span>
                </div>
                <div class="crm-ativ-card-main">
                    <div class="crm-ativ-titulo">${escapeHtml(a.titulo || a.descricao || '—')}</div>
                    <div class="crm-ativ-subtipo">${tipoLabel}</div>
                </div>
                <div class="crm-ativ-card-right">
                    <div class="crm-ativ-contato">${a.contato_nome ? escapeHtml(a.contato_nome) : ''}</div>
                    <div class="crm-ativ-data">${dataFormatada}</div>
                </div>
                <div class="crm-ativ-card-badge">
                    ${badgePrioridadeAtiv(prioridade)}
                </div>
            </div>`;
    }

    function formatDateAtiv(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        const hoje = new Date();
        if (d.toDateString() === hoje.toDateString()) {
            return `Hoje, ${d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
        }
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }

    /** Filtra o cache de atividades conforme a aba ativa (client-side). */
    function filtrarAtividadesPorAba() {
        const lista = crmActCache;
        switch (atividadesTab) {
            case 'hoje':
                return lista.filter(atividadeHoje);
            case 'pendentes':
                return lista.filter(a => a.status !== 'concluida');
            case 'concluidas':
                return lista.filter(a => a.status === 'concluida');
            case 'contato':
                return contatoSelecionadoId
                    ? lista.filter(a => String(a.contato_id) === String(contatoSelecionadoId))
                    : [];
            default:
                return lista;
        }
    }

    async function carregarAtividades(clienteId, contatoId) {
        crmActCtx = { clienteId, contatoId };
        const container = $('#lista-atividades');
        if (!container) return;
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/atividades`);
            crmActCache = data.atividades || [];
            renderAtividades();
        } catch (e) {
            showEmpty(container, 'Erro ao carregar atividades.');
            console.error(e);
        }
    }

    function renderAtividades() {
        const container = $('#lista-atividades');
        if (!container) return;
        const clienteId = crmActCtx.clienteId;
        const contatoId = crmActCtx.contatoId;
        const lista = crmActCache;
        const filtrada = filtrarAtividadesPorAba();

        const mostraConcluidas = (atividadesTab === 'todas' || atividadesTab === 'contato' || atividadesTab === 'concluidas');
        const ativas = sortAtividadesPorPrazoAtivas(filtrada.filter(a => a.status !== 'concluida'));
        const concluidas = mostraConcluidas
            ? sortAtividadesConcluidasPorData(filtrada.filter(a => a.status === 'concluida'))
            : [];

        let html = '';

        if (atividadesTab === 'contato' && !contatoSelecionadoId) {
            html += `<div class="crm-ativ-vazio">Selecione um contato na coluna ao lado.</div>`;
        } else if (atividadesTab === 'concluidas') {
            html += concluidas.length
                ? `<div class="crm-ativ-lista">${concluidas.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`
                : `<div class="crm-ativ-vazio">Nenhuma atividade concluída.</div>`;
        } else {
            if (ativas.length) {
                const visiveis = ativas.slice(0, 8);
                html += `<div class="crm-ativ-lista">${visiveis.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
                if (ativas.length > 8) {
                    html += `<div class="crm-link-ver-mais" id="crm-ver-mais-atividades">+ Ver mais atividades</div>`;
                }
            } else {
                const vazio = atividadesTab === 'hoje' ? 'Nenhuma atividade para hoje.' : 'Nenhuma atividade pendente.';
                html += `<div class="crm-ativ-vazio">${vazio}</div>`;
            }
            if (concluidas.length && atividadesTab !== 'pendentes') {
                html += `<div class="crm-ativ-divider">Concluídas</div>`;
                html += `<div class="crm-ativ-lista crm-ativ-lista-done">${concluidas.slice(0, 3).map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
            }
        }

        {
            const hoje = new Date().toISOString().slice(0, 10);
            html += `
                <div class="crm-ativ-form-titulo">Nova atividade</div>
                <div class="crm-ativ-form">
                    <div class="crm-ativ-form-row">
                        <label class="crm-ativ-label">Título da atividade*</label>
                        <input type="text" id="input-atividade-titulo" class="crm-ativ-input" placeholder="Digite o título..." />
                    </div>
                    <div class="crm-ativ-form-row">
                        <label class="crm-ativ-label">Descrição</label>
                        <textarea id="input-atividade" class="crm-ativ-textarea" rows="2" placeholder="Descrição (opcional)..."></textarea>
                    </div>
                    <div class="crm-ativ-form-grid3">
                        <div>
                            <label class="crm-ativ-label">Tipo</label>
                            <select id="input-atividade-tipo" class="crm-ativ-select">
                                <option value="atividade">Atividade</option>
                                <option value="ligacao">Ligação</option>
                                <option value="almoco">Almoço</option>
                                <option value="reuniao">Reunião</option>
                                <option value="projeto">Projeto</option>
                            </select>
                        </div>
                        <div>
                            <label class="crm-ativ-label">Data</label>
                            <input type="date" id="input-atividade-data" class="crm-ativ-input" value="${hoje}" />
                        </div>
                        <div>
                            <label class="crm-ativ-label">Prazo</label>
                            <input type="date" id="input-atividade-prazo" class="crm-ativ-input" />
                        </div>
                    </div>
                    <div class="crm-ativ-form-grid3">
                        <div>
                            <label class="crm-ativ-label">Responsável</label>
                            <select id="input-atividade-responsavel" class="crm-ativ-select">
                                <option value="">Selecionar...</option>
                            </select>
                        </div>
                        <div>
                            <label class="crm-ativ-label">Objetivo vinculado</label>
                            <select id="input-atividade-objetivo" class="crm-ativ-select">
                                <option value="">Nenhum</option>
                            </select>
                        </div>
                        <div>
                            <label class="crm-ativ-label">Prioridade</label>
                            <select id="input-atividade-prioridade" class="crm-ativ-select">
                                <option value="media">● Média</option>
                                <option value="alta">● Alta</option>
                                <option value="baixa">● Baixa</option>
                            </select>
                        </div>
                    </div>
                    <button type="button" class="crm-ativ-btn-criar" id="btn-add-atividade">Criar atividade</button>
                    <div class="crm-ativ-ia-section">
                        <div class="crm-ativ-ia-titulo">Ações com IA</div>
                        <div class="crm-ativ-ia-btns">
                            <button type="button" class="crm-ativ-ia-btn" id="btn-sugerir-atividade">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                                Sugerir
                            </button>
                            <button type="button" class="crm-ativ-ia-btn" id="btn-add-atividade-ia">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                                Melhorar
                            </button>
                            <button type="button" class="crm-ativ-ia-btn" id="btn-gerar-followup">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                                Follow-up
                            </button>
                        </div>
                    </div>
                </div>
            `;

            container.innerHTML = html;

            $$('.crm-act-feito', container).forEach(cb => {
                cb.addEventListener('change', async () => {
                    if (!cb.checked) return;
                    try {
                        await api(`/api/atividades/${cb.dataset.id}/status`, {
                            method: 'PATCH',
                            body: JSON.stringify({ status: 'concluida' })
                        });
                        carregarAtividades(clienteId, contatoId);
                    } catch (e) {
                        console.error(e);
                        cb.checked = false;
                        showToast('Erro ao concluir.', 'error');
                    }
                });
            });

            $$('.crm-act-edit', container).forEach(btn => {
                btn.addEventListener('click', () => {
                    const a = lista.find(x => String(x.id) === btn.dataset.id);
                    if (!a) return;
                    $('#ea-id').value = a.id;
                    $('#ea-titulo').value = a.titulo || '';
                    $('#ea-desc').value = a.descricao || '';
                    $('#ea-data').value = _isoDateOnly(a.data_atividade);
                    $('#ea-prazo').value = _isoDateOnly(a.data_prazo);
                    $('#ea-tipo').value = a.tipo || 'atividade';
                    $('#ea-status').value = a.status || 'pendente';
                    $('#modal-editar-atividade').showModal();
                });
            });

            $$('.crm-act-del', container).forEach(btn => {
                btn.addEventListener('click', async () => {
                    if (!confirm('Excluir esta atividade?')) return;
                    try {
                        await api(`/api/atividades/${btn.dataset.id}`, { method: 'DELETE' });
                        carregarAtividades(clienteId, contatoId);
                    } catch (e) {
                        console.error(e);
                        showToast('Erro ao excluir.', 'error');
                    }
                });
            });

            async function criarAtividade(usarIA) {
                const descricao = $('#input-atividade').value.trim();
                const dataAtiv = $('#input-atividade-data').value;
                const tipo = $('#input-atividade-tipo').value;
                const dataPrazo = $('#input-atividade-prazo').value || null;

                if (!descricao || !dataAtiv) { showToast('Preencha descrição e data.', 'warning'); return; }

                const btn = usarIA ? $('#btn-add-atividade-ia') : $('#btn-add-atividade');
                btn.classList.add('loading');
                try {
                    let tituloFinal = null;
                    let descFinal = descricao;
                    if (usarIA) {
                        try {
                            const ia = await api('/api/ia/melhorar-texto', {
                                method: 'POST',
                                body: JSON.stringify({ texto: descricao, contexto: 'atividade_comercial' })
                            });
                            descFinal = ia.texto_melhorado || descricao;
                        } catch (_) { /* fallback */ }
                    }

                    await api(`/api/cliente/${clienteId}/atividades`, {
                        method: 'POST',
                        body: JSON.stringify({
                            titulo: tituloFinal || null,
                            descricao: descFinal,
                            data_atividade: dataAtiv,
                            tipo,
                            data_prazo: dataPrazo,
                            contato_id: contatoId || null
                        })
                    });
                    carregarAtividades(clienteId, contatoId);
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao criar atividade.', 'error');
                } finally {
                    btn.classList.remove('loading');
                }
            }

            $('#btn-add-atividade')?.addEventListener('click', () => criarAtividade(false));
            $('#btn-add-atividade-ia')?.addEventListener('click', () => criarAtividade(true));

            $('#btn-sugerir-atividade')?.addEventListener('click', async () => {
                const btn = $('#btn-sugerir-atividade');
                btn.classList.add('loading');
                try {
                    const data = await api('/api/ia/sugerir-atividade', {
                        method: 'POST',
                        body: JSON.stringify({ cliente_id: clienteId })
                    });
                    if (data.sugestao) {
                        const blocos = [data.sugestao.titulo, data.sugestao.descricao].filter(Boolean);
                        $('#input-atividade').value = blocos.join(blocos.length > 1 ? '\n\n' : '');
                        if (data.sugestao.tipo) $('#input-atividade-tipo').value = data.sugestao.tipo;
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao obter sugestão.', 'error');
                } finally {
                    btn.classList.remove('loading');
                }
            });
        }
    }

    // ==================== Column 5: Objetivos ====================

    function badgeStatusObjetivo(ativo) {
        if (ativo) {
            return '<span class="badge badge-xs badge-success gap-1"><span class="w-1.5 h-1.5 rounded-full bg-white"></span>Ativo</span>';
        }
        return '<span class="badge badge-xs badge-ghost gap-1"><span class="w-1.5 h-1.5 rounded-full bg-current opacity-50"></span>Conquistado</span>';
    }

    async function carregarObjetivos(clienteId) {
        crmObjCtx.clienteId = clienteId;
        const container = $('#lista-objetivos');
        if (!container) return;
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/objetivos`);
            const ativos = data.objetivos.filter(o => !o.conquistado);
            const conquistados = data.objetivos.filter(o => o.conquistado);
            const totalObjetivos = data.objetivos.length;
            const hojePrazo = new Date().toISOString().slice(0, 10);
            const maxVisiveis = 5;

            let html = `
                <div class="crm-obj-header">
                    <span class="crm-obj-titulo">Objetivos</span>
                    <button type="button" class="crm-obj-btn-novo" id="btn-toggle-form-obj">+ Novo objetivo</button>
                </div>
                <div class="crm-obj-input-row hidden" id="crm-obj-input-row">
                    <input type="text" id="input-objetivo" class="crm-obj-input" placeholder="Novo objetivo..." />
                    <input type="date" id="input-objetivo-prazo" class="crm-obj-input-data" value="${hojePrazo}" />
                    <button type="button" class="crm-obj-btn-add" id="btn-add-objetivo">+</button>
                </div>
                <div id="ia-sugestoes" class="hidden"></div>
            `;

            const ativosVisiveis = ativos.slice(0, maxVisiveis);
            if (ativosVisiveis.length) {
                html += `<div class="crm-obj-lista">`;
                html += ativosVisiveis.map(o => `
                    <div class="crm-obj-item crm-fade-in" data-id="${o.id}">
                        <input type="checkbox" class="crm-obj-checkbox crm-obj-check" data-id="${o.id}" />
                        <div class="crm-obj-content">
                            <div class="crm-obj-texto">${escapeHtml(o.texto)}</div>
                            <div class="crm-obj-meta">
                                ${o.data_prazo ? `<span class="crm-obj-data">${fmtDateShort(o.data_prazo)}</span>` : ''}
                                <span class="crm-badge-status-obj crm-badge-ativo">Ativo</span>
                            </div>
                        </div>
                        <div class="crm-obj-acoes">
                            <button type="button" class="crm-obj-acao-btn crm-obj-edit" data-id="${o.id}" title="Editar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>
                            <button type="button" class="crm-obj-acao-btn crm-obj-del" data-id="${o.id}" title="Excluir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>
                        </div>
                    </div>
                `).join('');
                html += `</div>`;
            }

            const conquistadosVisiveis = conquistados.slice(0, Math.max(0, maxVisiveis - ativosVisiveis.length));
            if (conquistadosVisiveis.length) {
                html += `<div class="crm-obj-lista" style="opacity:0.6">`;
                html += conquistadosVisiveis.map(o => `
                    <div class="crm-obj-item crm-fade-in crm-obj-conquistado" data-id="${o.id}">
                        <input type="checkbox" class="crm-obj-checkbox crm-obj-check" data-id="${o.id}" checked />
                        <div class="crm-obj-content">
                            <div class="crm-obj-texto" style="text-decoration:line-through">${escapeHtml(o.texto)}</div>
                            <div class="crm-obj-meta">
                                ${o.data_conquista ? `<span class="crm-obj-data">${fmtDateShort(o.data_conquista)}</span>` : ''}
                                <span class="crm-badge-status-obj crm-badge-pendente">Concluído</span>
                            </div>
                        </div>
                        <div class="crm-obj-acoes">
                            <button type="button" class="crm-obj-acao-btn crm-obj-edit" data-id="${o.id}" title="Editar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>
                            <button type="button" class="crm-obj-acao-btn crm-obj-del" data-id="${o.id}" title="Excluir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>
                        </div>
                    </div>
                `).join('');
                html += `</div>`;
            }

            if (!ativos.length && !conquistados.length) {
                html += '<div class="crm-ativ-vazio">Nenhum objetivo cadastrado.</div>';
            }

            if (totalObjetivos > maxVisiveis) {
                html += `<div class="crm-obj-ver-todos" id="crm-ver-todos-objetivos">Ver todos os objetivos</div>`;
            }

            container.innerHTML = html;

            $('#btn-toggle-form-obj')?.addEventListener('click', () => {
                const row = $('#crm-obj-input-row');
                if (!row) return;
                row.classList.toggle('hidden');
                if (!row.classList.contains('hidden')) $('#input-objetivo')?.focus();
            });

            $('#btn-add-objetivo')?.addEventListener('click', async () => {
                const texto = $('#input-objetivo').value.trim();
                if (!texto) return;
                const dataPrazo = $('#input-objetivo-prazo').value || null;
                try {
                    await api(`/api/cliente/${clienteId}/objetivos`, {
                        method: 'POST',
                        body: JSON.stringify({ texto, data_prazo: dataPrazo })
                    });
                    carregarObjetivos(clienteId);
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao criar objetivo.', 'error');
                }
            });

            $('#input-objetivo')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') $('#btn-add-objetivo')?.click();
            });

            $$('.crm-obj-check', container).forEach(cb => {
                cb.addEventListener('change', async () => {
                    try {
                        await api(`/api/objetivos/${cb.dataset.id}/conquistar`, {
                            method: 'PATCH',
                            body: JSON.stringify({ conquistado: cb.checked })
                        });
                        const card = cb.closest('.crm-fade-in');
                        if (cb.checked && card) {
                            card.classList.add('crm-obj-conquistado-anim');
                            setTimeout(() => carregarObjetivos(clienteId), 600);
                        } else {
                            carregarObjetivos(clienteId);
                        }
                    } catch (e) {
                        console.error(e);
                    }
                });
            });

            const olist = data.objetivos || [];
            $$('.crm-obj-edit', container).forEach(btn => {
                btn.addEventListener('click', () => {
                    const o = olist.find(x => String(x.id) === btn.dataset.id);
                    if (!o) return;
                    $('#eo-id').value = o.id;
                    $('#eo-texto').value = o.texto || '';
                    $('#eo-prazo').value = _isoDateOnly(o.data_prazo);
                    $('#modal-editar-objetivo').showModal();
                });
            });

            $$('.crm-obj-del', container).forEach(btn => {
                btn.addEventListener('click', async () => {
                    if (!confirm('Excluir este objetivo?')) return;
                    try {
                        await api(`/api/objetivos/${btn.dataset.id}`, { method: 'DELETE' });
                        carregarObjetivos(clienteId);
                    } catch (e) {
                        console.error(e);
                        showToast('Erro ao excluir objetivo.', 'error');
                    }
                });
            });

            $('#crm-ver-todos-objetivos')?.addEventListener('click', () => {
                window.location.href = `/clientes?open=${clienteId}&tab=objetivos`;
            });

            bindSugerirObjetivosIA(clienteId);
        } catch (e) {
            showEmpty(container, 'Erro ao carregar objetivos.');
            console.error(e);
        }
    }

    function bindSugerirObjetivosIA(clienteId) {
        $('#btn-sugerir-ia-header')?.addEventListener('click', async () => {
            const btn = $('#btn-sugerir-ia-header');
            btn.classList.add('loading');
            try {
                const data = await api('/api/ia/sugerir-objetivos', {
                    method: 'POST',
                    body: JSON.stringify({ cliente_id: clienteId })
                });
                const sugestoesDiv = $('#ia-sugestoes');
                sugestoesDiv.classList.remove('hidden');
                sugestoesDiv.innerHTML = `
                    <div class="text-xs font-semibold mb-1">Sugestões da IA:</div>
                    ${data.objetivos.map((o, i) => `
                        <label class="flex items-start gap-2 py-0.5 cursor-pointer">
                            <input type="checkbox" class="checkbox checkbox-xs crm-sug-check" data-texto="${o.replace(/"/g, '&quot;')}" checked />
                            <span class="text-xs">${o}</span>
                        </label>
                    `).join('')}
                    <button class="btn btn-xs btn-success w-full mt-1" id="btn-aceitar-sugestoes">Adicionar selecionados</button>
                `;

                $('#btn-aceitar-sugestoes')?.addEventListener('click', async () => {
                    const selecionados = $$('.crm-sug-check:checked', sugestoesDiv).map(cb => cb.dataset.texto);
                    for (const texto of selecionados) {
                        await api(`/api/cliente/${clienteId}/objetivos`, {
                            method: 'POST',
                            body: JSON.stringify({ texto })
                        });
                    }
                    carregarObjetivos(clienteId);
                });
            } catch (e) {
                console.error(e);
                showToast('Erro ao obter sugestões da IA.', 'error');
            } finally {
                btn.classList.remove('loading');
            }
        });
    }

    // ==================== Modal: Status Completo ====================

    function destroyChart(id) {
        if (chartInstances[id]) {
            chartInstances[id].destroy();
            delete chartInstances[id];
        }
    }

    async function abrirModalStatusCompleto(clienteId) {
        const modal = $('#modal-status-completo');
        const selAno = $('#modal-status-ano');
        const currentYear = new Date().getFullYear();

        selAno.innerHTML = '';
        for (let y = currentYear; y >= currentYear - 3; y--) {
            selAno.innerHTML += `<option value="${y}">${y}</option>`;
        }

        selAno.onchange = () => carregarDadosModalStatus(clienteId, parseInt(selAno.value));
        modal.showModal();
        carregarDadosModalStatus(clienteId, currentYear);
    }

    async function carregarDadosModalStatus(clienteId, ano) {
        const kpisEl = $('#modal-status-kpis');
        const tabelaEl = $('#modal-status-tabela');

        kpisEl.innerHTML = '<span class="loading loading-spinner loading-sm col-span-full"></span>';
        try {
            const data = await api(`/api/cliente/${clienteId}/status-completo?ano=${ano}`);
            const rc = data.resumo_cotacoes || { total_cotacoes: 0, cotacoes_aprovadas: 0, valor_total: 0, valor_aprovado: 0, pct_conversao: 0 };
            const rp = data.resumo_pis || { total_pis: 0, pis_concluidos: 0, valor_pis: 0 };
            const rb = data.resumo_briefings || { total_briefings: 0 };
            const valApr = Number(rc.valor_aprovado) || 0;

            kpisEl.innerHTML = `
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Cotações (ano)</div>
                    <div class="stat-value text-lg">${rc.total_cotacoes || 0}</div>
                    <div class="stat-desc text-xs">Pipeline ${fmtBRL(rc.valor_total || 0)}</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Aprovadas</div>
                    <div class="stat-value text-lg">${rc.cotacoes_aprovadas || 0}</div>
                    <div class="stat-desc text-xs">${fmtBRL(valApr)} · ${rc.pct_conversao || 0}% conv.</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">PIs</div>
                    <div class="stat-value text-lg">${rp.total_pis || 0}</div>
                    <div class="stat-desc text-xs">${rp.pis_concluidos || 0} concl. · ${fmtBRL(rp.valor_pis || 0)}</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Ticket médio</div>
                    <div class="stat-value text-sm">${fmtBRL(data.ticket_medio)}</div>
                    <div class="stat-desc text-xs">Só aprovadas</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Briefings</div>
                    <div class="stat-value text-lg">${rb.total_briefings || 0}</div>
                    <div class="stat-desc text-xs">Criados no ano</div>
                </div>
            `;

            const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
            const porMes = data.por_mes || [];
            const dadosMes = new Array(12).fill(null).map((_, i) => {
                const m = porMes.find(p => p.mes === i + 1);
                return m || { mes: i + 1, total: 0, aprovadas: 0, faturamento: 0 };
            });

            destroyChart('cotacoesMes');
            destroyChart('faturamento');
            destroyChart('conversao');

            const brMes = data.briefings_mensal || new Array(12).fill(0);
            const ctxBar = $('#chart-cotacoes-mes');
            chartInstances['cotacoesMes'] = new Chart(ctxBar, {
                type: 'bar',
                data: {
                    labels: meses,
                    datasets: [{
                        label: 'Cot. total',
                        data: dadosMes.map(d => d.total),
                        backgroundColor: 'rgba(99,102,241,0.6)'
                    }, {
                        label: 'Cot. aprovadas',
                        data: dadosMes.map(d => d.aprovadas),
                        backgroundColor: 'rgba(34,197,94,0.6)'
                    }, {
                        label: 'Briefings',
                        data: brMes,
                        backgroundColor: 'rgba(234,179,8,0.65)'
                    }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 9 } } } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
            });

            const ctxLine = $('#chart-faturamento');
            const fatMensal = data.faturamento_mensal || new Array(12).fill(0);
            chartInstances['faturamento'] = new Chart(ctxLine, {
                type: 'line',
                data: {
                    labels: meses,
                    datasets: [{
                        label: 'Faturamento (PIs)',
                        data: fatMensal,
                        borderColor: 'rgb(99,102,241)',
                        backgroundColor: 'rgba(99,102,241,0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });

            const aprovadas = rc.cotacoes_aprovadas || 0;
            const rejeitadas = (rc.total_cotacoes || 0) - aprovadas;
            const ctxPie = $('#chart-conversao');
            chartInstances['conversao'] = new Chart(ctxPie, {
                type: 'doughnut',
                data: {
                    labels: ['Aprovadas', 'Outras'],
                    datasets: [{
                        data: [aprovadas, rejeitadas],
                        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(239,68,68,0.4)']
                    }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } }
            });

            const cotacoes = data.cotacoes || [];
            tabelaEl.innerHTML = cotacoes.length
                ? cotacoes.map(c => `
                    <tr>
                        <td>${c.numero_cotacao || '-'}</td>
                        <td>${c.nome_campanha || '-'}</td>
                        <td>${fmtBRL(c.valor_total_proposta)}</td>
                        <td><span class="badge badge-xs">${c.status_descricao || '-'}</span></td>
                        <td>${fmtDate(c.created_at)}</td>
                    </tr>
                `).join('')
                : '<tr><td colspan="5" class="text-center opacity-50">Sem cotações neste período.</td></tr>';

            const pisTabelaEl = $('#modal-pis-tabela');
            const pisResumoEl = $('#modal-pis-resumo');
            const pisLista = data.pis_lista || [];
            if (pisTabelaEl) {
                pisTabelaEl.innerHTML = pisLista.length
                    ? pisLista.map(p => `
                        <tr>
                            <td>${p.numero_pi || '-'}</td>
                            <td>${p.campanha || '-'}</td>
                            <td>${fmtBRL(p.valor_bruto)}</td>
                            <td><span class="badge badge-xs">${p.status_descricao || '-'}</span></td>
                            <td>${fmtDate(p.created_at)}</td>
                        </tr>
                    `).join('')
                    : '<tr><td colspan="5" class="text-center opacity-50">Sem PIs neste período.</td></tr>';
            }
            if (pisResumoEl) {
                pisResumoEl.innerHTML = `${rp.total_pis || 0} PIs · ${rp.pis_concluidos || 0} concluídos · Total: ${fmtBRL(rp.valor_pis)}`;
            }

            const brTab = $('#modal-briefings-tabela');
            const brList = data.briefings_lista || [];
            if (brTab) {
                brTab.innerHTML = brList.length
                    ? brList.map(b => `
                        <tr>
                            <td>${(b.titulo || '-').replace(/</g, '&lt;')}</td>
                            <td><span class="badge badge-xs">${b.status || '-'}</span></td>
                            <td>${fmtDate(b.created_at)}</td>
                        </tr>
                    `).join('')
                    : '<tr><td colspan="3" class="text-center opacity-50">Sem briefings neste período.</td></tr>';
            }

        } catch (e) {
            kpisEl.innerHTML = '<div class="text-xs opacity-50 col-span-full text-center py-4">Nenhum dado encontrado para este período.</div>';
            tabelaEl.innerHTML = '<tr><td colspan="5" class="text-center opacity-50">Sem cotações neste período.</td></tr>';
            const pisTabelaEl = $('#modal-pis-tabela');
            if (pisTabelaEl) pisTabelaEl.innerHTML = '<tr><td colspan="5" class="text-center opacity-50">Sem PIs neste período.</td></tr>';
            const brTab = $('#modal-briefings-tabela');
            if (brTab) brTab.innerHTML = '<tr><td colspan="3" class="text-center opacity-50">Sem briefings neste período.</td></tr>';
            console.error(e);
        }
    }

    // ==================== Modal: Contato ====================

    async function abrirModalContato(contatoId) {
        const modal = $('#modal-contato');
        modalContatoId = contatoId;
        modalClienteId = clienteSelecionadoId;

        showTabDados();
        modal.showModal();

        try {
            const data = await api(`/api/contato/${contatoId}/detalhes`);
            const c = data.contato;
            modalClienteId = c.cliente_id;

            $('#modal-contato-nome').textContent = c.nome_completo;

            // Populate edit form
            $('#ce-nome').value = c.nome_completo || '';
            $('#ce-email').value = c.email || '';
            $('#ce-tel').value = c.telefone || '';
            $('#ce-tel2').value = c.telefone_secundario || '';

            $('#contato-info').innerHTML = `
                <div><span class="text-xs opacity-60">Nome</span><div class="text-sm">${c.nome_completo}</div></div>
                <div><span class="text-xs opacity-60">Cargo</span><div class="text-sm">${c.cargo || '-'}</div></div>
                <div>
                    <span class="text-xs opacity-60">Telefone</span>
                    <div class="flex items-center gap-1">
                        <span class="text-sm">${c.telefone || '-'}</span>
                        ${c.telefone ? `<button class="crm-copy-btn" data-copy="${c.telefone}" title="Copiar telefone"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button>` : ''}
                    </div>
                </div>
                ${c.telefone_secundario ? `
                <div>
                    <span class="text-xs opacity-60">Segundo telefone</span>
                    <div class="flex items-center gap-1">
                        <span class="text-sm">${c.telefone_secundario}</span>
                        <button class="crm-copy-btn" data-copy="${c.telefone_secundario}" title="Copiar telefone"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button>
                    </div>
                </div>` : ''}
                <div>
                    <span class="text-xs opacity-60">Email</span>
                    <div class="flex items-center gap-1">
                        <span class="text-sm">${c.email || '-'}</span>
                        ${c.email ? `<button class="crm-copy-btn" data-copy="${c.email}" title="Copiar email"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button>` : ''}
                        ${c.email ? `<a href="mailto:${c.email}" class="crm-copy-btn" title="Enviar email"><svg class="w-3.5 h-3.5 text-info" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg></a>` : ''}
                    </div>
                </div>
                <div class="col-span-2"><span class="text-xs opacity-60">Cliente</span><div class="text-sm">${c.cliente_nome || '-'}</div></div>
            `;

            $$('.crm-copy-btn[data-copy]', $('#contato-info')).forEach(btn => {
                btn.addEventListener('click', () => {
                    navigator.clipboard.writeText(btn.dataset.copy).then(() => {
                        const original = btn.innerHTML;
                        btn.innerHTML = '<span class="text-xs text-success">✓</span>';
                        setTimeout(() => btn.innerHTML = original, 1500);
                    });
                });
            });

            if (!data.atividades.length) {
                $('#contato-atividades-lista').innerHTML = '<div class="text-xs opacity-50 text-center py-2">Sem atividades.</div>';
            } else {
                $('#contato-atividades-lista').innerHTML = data.atividades.map(a => `
                    <div class="bg-base-200 rounded p-1.5 text-xs mb-1">
                        <span class="badge badge-xs mr-1">${a.status}</span>
                        ${a.descricao} <span class="opacity-50">(${fmtDate(a.data_atividade)})</span>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error(e);
            $('#contato-info').innerHTML = '<div class="text-error text-xs">Erro ao carregar contato.</div>';
        }
    }

    function showTabDados() {
        $('#tab-dados').classList.remove('hidden');
        $('#tab-comunicacao').classList.add('hidden');
        $('#tab-editar')?.classList.add('hidden');
        $$('[data-modal-tab]').forEach(t => t.classList.toggle('tab-active', t.dataset.modalTab === 'dados'));
    }

    function showTabComunicacao() {
        $('#tab-dados').classList.add('hidden');
        $('#tab-comunicacao').classList.remove('hidden');
        $('#tab-editar')?.classList.add('hidden');
        $$('[data-modal-tab]').forEach(t => t.classList.toggle('tab-active', t.dataset.modalTab === 'comunicacao'));
    }

    function showTabEditar() {
        $('#tab-dados').classList.add('hidden');
        $('#tab-comunicacao').classList.add('hidden');
        $('#tab-editar')?.classList.remove('hidden');
        $$('[data-modal-tab]').forEach(t => t.classList.toggle('tab-active', t.dataset.modalTab === 'editar'));
    }

    /**
     * Núcleo reutilizável de geração de comunicação via IA.
     * Usado tanto pelo modal de contato quanto pela seção fixa da coluna 5.
     */
    async function gerarComunicacaoCore({ contatoId, clienteId, tipo, tamanho, objetivo, produto, canal, btn, previewEl, textoEl }) {
        if (!clienteId) { showToast('Selecione um cliente.', 'warning'); return; }
        if (!contatoId) { showToast('Selecione um contato.', 'warning'); return; }
        if (!objetivo) { showToast('Preencha o objetivo da mensagem.', 'warning'); return; }

        btn?.classList.add('loading');
        try {
            const data = await api('/api/ia/gerar-comunicacao', {
                method: 'POST',
                body: JSON.stringify({
                    contato_id: contatoId,
                    cliente_id: clienteId,
                    tipo, tamanho, objetivo, produto, canal
                })
            });
            if (textoEl) textoEl.textContent = data.mensagem;
            previewEl?.classList.remove('hidden');
        } catch (e) {
            console.error(e);
            showToast('Erro ao gerar comunicação.', 'error');
        } finally {
            btn?.classList.remove('loading');
        }
    }

    function gerarComunicacao() {
        return gerarComunicacaoCore({
            contatoId: modalContatoId,
            clienteId: modalClienteId,
            tipo: $('input[name="com-tipo"]:checked')?.value || 'whatsapp',
            tamanho: $('input[name="com-tamanho"]:checked')?.value || 'medio',
            objetivo: $('#com-objetivo').value.trim(),
            produto: $('#com-produto').value,
            canal: $('#com-canal').value.trim(),
            btn: $('#btn-gerar-comunicacao'),
            previewEl: $('#com-preview'),
            textoEl: $('#com-texto')
        });
    }

    // ==================== Coluna 5: Seção Comunicação ====================

    /** Preenche o select de contatos da seção Comunicação. */
    function popularComunicacaoContatos(contatos) {
        const sel = $('#crmc-contato');
        if (!sel) return;
        const atual = sel.value;
        const opts = ['<option value="">Selecione um contato</option>']
            .concat((contatos || []).map(c => `<option value="${c.id_contato_cliente}">${escapeHtml(c.nome_completo)}</option>`));
        sel.innerHTML = opts.join('');
        if (atual && [...sel.options].some(o => o.value === atual)) {
            sel.value = atual;
        } else if (contatoSelecionadoId) {
            sel.value = String(contatoSelecionadoId);
        }
    }

    function contatoSelecionadoAtual() {
        if (!contatoSelecionadoId) return null;
        return crmContatosCache.find(c => String(c.id_contato_cliente) === String(contatoSelecionadoId)) || null;
    }

    function atualizarResumoObjetivosComunicacao() {
        const contato = contatoSelecionadoAtual();
        const card = $('#crm-oc-contato-card');
        if (!card) return;
        if (!contato || !telefoneSelecionado) {
            card.innerHTML = '';
            card.classList.add('hidden');
            return;
        }
        card.classList.remove('hidden');
        card.innerHTML = `
            <div class="crm-avatar crm-avatar-sm">${contatoAvatar(contato)}</div>
            <div class="crm-chat-contact-info">
                <span class="crm-oc-contato-nome">${escapeHtml(contato.nome_completo || 'Contato selecionado')}</span>
                ${contato.cargo ? `<span class="crm-oc-contato-sep">·</span><span class="crm-oc-contato-role">${escapeHtml(contato.cargo)}</span>` : ''}
                <span class="crm-oc-contato-sep">·</span>
                <span class="crm-oc-contato-tel">${escapeHtml(telefoneSelecionado)}</span>
            </div>
        `;
    }

    async function carregarConversasComerciais(clienteId, contatoId = null, telefone = null, opts = {}) {
        const container = $('#crm-conversas-lista');
        if (!container || !clienteId) return;
        if (!contatoId) {
            limparWhatsAppComercial();
            return;
        }
        const autoSelect = opts.autoSelect !== false;
        showSpinner(container);
        try {
            const qs = new URLSearchParams();
            qs.set('contato_id', String(contatoId));
            if (telefone) qs.set('telefone', telefone);
            const data = await api(`/api/cliente/${clienteId}/comunicacao/conversas?${qs.toString()}`);
            crmConversasCache = data.conversas || [];
            renderConversasComerciais();
            if (autoSelect && crmConversaSelecionadaId && crmConversasCache.some(c => String(c.id) === String(crmConversaSelecionadaId))) {
                carregarMensagensConversa(crmConversaSelecionadaId);
            } else if (autoSelect && telefone && crmConversasCache.length) {
                selecionarConversaComercial(crmConversasCache[0].id);
            } else if (autoSelect && crmConversasCache.length === 1) {
                selecionarConversaComercial(crmConversasCache[0].id);
            } else if (!crmConversasCache.length) {
                crmConversaSelecionadaId = null;
                showEmpty($('#crm-chat-mensagens'), telefone ? 'Nenhuma conversa para este telefone.' : 'Selecione um telefone para ver a conversa.');
            } else {
                crmConversaSelecionadaId = null;
                showEmpty($('#crm-chat-mensagens'), 'Selecione uma conversa ou telefone.');
            }
        } catch (e) {
            console.error(e);
            showEmpty(container, 'Erro ao carregar conversas.');
        }
    }

    function renderConversasComerciais() {
        const container = $('#crm-conversas-lista');
        if (!container) return;
        const termo = crmChatBusca.trim().toLowerCase();
        let conversas = crmConversasCache.filter(c => {
            if (crmChatTab === 'nao_lidas' && !(Number(c.unread_count) > 0)) return false;
            if (crmChatTab === 'grupos') return false;
            if (!termo) return true;
            return [c.contato_nome, c.telefone, c.ultimo_preview].some(v => String(v || '').toLowerCase().includes(termo));
        });
        const naoLidas = crmConversasCache.filter(c => Number(c.unread_count) > 0).length;
        if ($('#crm-chat-count-todas')) $('#crm-chat-count-todas').textContent = crmConversasCache.length;
        if ($('#crm-chat-count-nao-lidas')) $('#crm-chat-count-nao-lidas').textContent = naoLidas;
        if (!conversas.length) {
            showEmpty(container, crmConversasCache.length ? 'Nenhuma conversa encontrada.' : 'Nenhuma conversa criada.');
            return;
        }
        container.innerHTML = conversas.map(c => {
            const ativo = String(c.id) === String(crmConversaSelecionadaId);
            const hora = c.ultimo_evento_em ? new Date(c.ultimo_evento_em).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '';
            return `
                <button type="button" class="crm-conversa ${ativo ? 'crm-conversa-active' : ''}" data-id="${c.id}">
                    <div class="crm-avatar">${c.contato_foto_url ? `<img class="crm-avatar-img" src="${escapeHtml(c.contato_foto_url)}" alt="">` : '<span>WA</span>'}</div>
                    <div class="crm-conversa-info">
                        <div class="crm-conversa-top">
                            <span>${escapeHtml(c.contato_nome || c.telefone || 'Conversa')}</span>
                            <small>${escapeHtml(hora)}</small>
                        </div>
                        <div class="crm-conversa-preview">${escapeHtml(c.ultimo_preview || 'Sem mensagens ainda.')}</div>
                    </div>
                    ${Number(c.unread_count) > 0 ? `<span class="crm-unread">${c.unread_count}</span>` : ''}
                </button>
            `;
        }).join('');
        $$('.crm-conversa', container).forEach(btn => {
            btn.addEventListener('click', () => selecionarConversaComercial(parseInt(btn.dataset.id, 10)));
        });
    }

    function selecionarConversaComercial(conversaId) {
        const conversa = crmConversasCache.find(x => String(x.id) === String(conversaId));
        if (!conversa) return;
        crmConversaSelecionadaId = conversaId;
        if (conversa.contato_id) contatoSelecionadoId = conversa.contato_id;
        if (conversa.telefone) telefoneSelecionado = conversa.telefone;
        renderContatosCrm();
        renderConversasComerciais();
        atualizarResumoObjetivosComunicacao();
        carregarMensagensConversa(conversaId);
        iniciarPollingMensagens();
        api(`/api/comunicacao/conversas/${conversaId}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'aberta', unread_count: 0 })
        }).then(() => {
            const c = crmConversasCache.find(x => String(x.id) === String(conversaId));
            if (c) c.unread_count = 0;
            renderConversasComerciais();
        }).catch(() => {});
    }

    async function criarOuSelecionarConversa(contatoId, telefone = null) {
        if (!clienteSelecionadoId) return null;
        telefoneSelecionado = telefone;
        contatoSelecionadoId = contatoId;
        try {
            const data = await api(`/api/cliente/${clienteSelecionadoId}/comunicacao/conversas`, {
                method: 'POST',
                body: JSON.stringify({ contato_id: contatoId, telefone, canal: 'whatsapp' })
            });
            crmConversaSelecionadaId = data.id;
            await carregarConversasComerciais(clienteSelecionadoId, contatoId, telefone, { autoSelect: false });
            selecionarConversaComercial(data.id);
            return data.id;
        } catch (e) {
            console.error(e);
            showToast(e.message || 'Erro ao criar conversa.', 'error');
            return null;
        }
    }

    function formatHoraMsg(dateStr) {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    function metaStatusMsg(m) {
        if (m.direcao !== 'outbound') return '';
        if (m.status === 'erro') return '<span class="crm-msg-status crm-msg-status-erro" title="Falha no envio">!</span>';
        if (m.provider_status === 'read' || m.provider_status === 'READ') {
            return '<span class="crm-msg-status crm-msg-status-read" title="Lida">✓✓</span>';
        }
        if (m.provider_status === 'delivered' || m.provider_status === 'DELIVERED') {
            return '<span class="crm-msg-status crm-msg-status-delivered" title="Entregue">✓✓</span>';
        }
        return '<span class="crm-msg-status" title="Enviada">✓</span>';
    }

    function agruparMensagensWhatsApp(mensagens) {
        const grupos = [];
        let atual = null;
        for (const m of mensagens) {
            const dir = m.direcao === 'inbound' ? 'in' : 'out';
            const ts = m.created_at ? new Date(m.created_at).getTime() : 0;
            const quebra =
                !atual ||
                atual.dir !== dir ||
                (ts && atual.lastTs && Math.abs(ts - atual.lastTs) > 5 * 60 * 1000);
            if (quebra) {
                atual = { dir, items: [m], lastTs: ts };
                grupos.push(atual);
            } else {
                atual.items.push(m);
                atual.lastTs = ts;
            }
        }
        return grupos;
    }

    function posicaoBubble(total, index) {
        if (total === 1) return 'single';
        if (index === 0) return 'first';
        if (index === total - 1) return 'last';
        return 'middle';
    }

    function renderMensagensWhatsApp(mensagens) {
        return agruparMensagensWhatsApp(mensagens).map(grupo => {
            const total = grupo.items.length;
            const bubbles = grupo.items.map((m, i) => {
                const pos = posicaoBubble(total, i);
                const hora = formatHoraMsg(m.created_at);
                const status = metaStatusMsg(m);
                return `
                    <div class="crm-msg-bubble crm-msg-bubble-${grupo.dir} crm-msg-bubble-${pos}">
                        <span class="crm-msg-text">${escapeHtml(m.texto || '')}</span>
                        <span class="crm-msg-meta">${escapeHtml(hora)}${status}</span>
                    </div>
                `;
            }).join('');
            return `<div class="crm-msg-group crm-msg-group-${grupo.dir}">${bubbles}</div>`;
        }).join('');
    }

    async function carregarMensagensConversa(conversaId, opts = {}) {
        const box = $('#crm-chat-mensagens');
        if (!box) return;
        const wasAtBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
        if (!opts.silent) showSpinner(box);
        try {
            const data = await api(`/api/comunicacao/conversas/${conversaId}/mensagens`);
            const mensagens = data.mensagens || [];
            if (opts.silent && mensagens.length === crmChatLastMsgCount) return;
            crmChatLastMsgCount = mensagens.length;
            if (!mensagens.length) {
                if (!opts.silent) showEmpty(box, 'Nenhuma mensagem nesta conversa.');
                return;
            }
            box.innerHTML = renderMensagensWhatsApp(mensagens);
            if (!opts.silent || wasAtBottom) box.scrollTop = box.scrollHeight;
        } catch (e) {
            if (!opts.silent) {
                console.error(e);
                showEmpty(box, 'Erro ao carregar mensagens.');
            }
        }
    }

    async function enviarMensagemComercial() {
        const input = $('#crm-chat-input');
        const texto = input?.value.trim();
        if (!crmConversaSelecionadaId && contatoSelecionadoId) {
            const contato = contatoSelecionadoAtual();
            const telefone = telefoneSelecionado || contato?.telefone || contato?.telefone_secundario || null;
            if (!telefone) { showToast('Contato sem telefone para WhatsApp.', 'warning'); return; }
            await abrirConversaTelefone(contatoSelecionadoId, telefone);
        }
        if (!crmConversaSelecionadaId) { showToast('Selecione um contato ou uma conversa.', 'warning'); return; }
        if (!texto) return;
        try {
            input.value = '';
            await api(`/api/comunicacao/conversas/${crmConversaSelecionadaId}/mensagens`, {
                method: 'POST',
                body: JSON.stringify({ texto, direcao: 'outbound', status: 'enviado' })
            });
            await carregarMensagensConversa(crmConversaSelecionadaId);
            await carregarConversasComerciais(clienteSelecionadoId, contatoSelecionadoId, telefoneSelecionado);
        } catch (e) {
            console.error(e);
            if (e.data?.mensagens) {
                await carregarMensagensConversa(crmConversaSelecionadaId);
                await carregarConversasComerciais(clienteSelecionadoId, contatoSelecionadoId, telefoneSelecionado);
            } else if (input) {
                input.value = texto;
            }
            showToast(e.message || 'Erro ao enviar mensagem.', 'error');
        }
    }

    async function carregarAutomacaoComercial(clienteId, contatoId = null) {
        if (!clienteId) return;
        try {
            const qs = new URLSearchParams({ tipo: $('#crm-auto-tipo')?.value || 'proposta_enviada' });
            if (contatoId) qs.set('contato_id', contatoId);
            const data = await api(`/api/cliente/${clienteId}/comunicacao/automacao?${qs.toString()}`);
            const auto = data.automacao || {};
            if ($('#crm-auto-ativo')) $('#crm-auto-ativo').checked = !!auto.ativo;
            if ($('#crm-auto-template')) $('#crm-auto-template').value = auto.template || '';
        } catch (e) {
            console.warn('Erro ao carregar automação comercial.', e);
        }
    }

    async function salvarAutomacaoComercial(enviarAgora = false) {
        if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
        const template = $('#crm-auto-template')?.value.trim() || '';
        const ativo = $('#crm-auto-ativo')?.checked || false;
        const tipo = $('#crm-auto-tipo')?.value || 'proposta_enviada';
        try {
            await api(`/api/cliente/${clienteSelecionadoId}/comunicacao/automacao`, {
                method: 'PUT',
                body: JSON.stringify({ contato_id: contatoSelecionadoId, tipo, template, ativo })
            });
            if (enviarAgora && template) {
                if (!crmConversaSelecionadaId && contatoSelecionadoId) {
                    const contato = contatoSelecionadoAtual();
                    const telefone = telefoneSelecionado || contato?.telefone || contato?.telefone_secundario || null;
                    await abrirConversaTelefone(contatoSelecionadoId, telefone);
                }
                if (crmConversaSelecionadaId) {
                    $('#crm-chat-input').value = template;
                    await enviarMensagemComercial();
                }
            }
            showToast('Automação salva.', 'success');
        } catch (e) {
            console.error(e);
            showToast(e.message || 'Erro ao salvar automação.', 'error');
        }
    }

    // ==================== Links consolidadas + URL executivo ====================

    function queryExecutivoCrm() {
        const sel = $('#filtro-executivo');
        if (!sel) return '';
        const v = sel.value;
        return v ? `?executivo_id=${encodeURIComponent(v)}` : '';
    }

    function setCookieCrm(nome, valor, dias = 180) {
        const maxAge = dias * 24 * 60 * 60;
        document.cookie = `${nome}=${encodeURIComponent(valor || '')}; path=/; max-age=${maxAge}; SameSite=Lax`;
    }

    function getCookieCrm(nome) {
        const prefix = `${nome}=`;
        return document.cookie
            .split(';')
            .map(c => c.trim())
            .find(c => c.startsWith(prefix))
            ?.slice(prefix.length) || '';
    }

    function limparCookieCrm(nome) {
        document.cookie = `${nome}=; path=/; max-age=0; SameSite=Lax`;
    }

    function salvarExecutivoCookieCrm() {
        const valor = $('#filtro-executivo')?.value || '';
        if (valor) setCookieCrm(CRM_EXECUTIVO_COOKIE, valor);
        else limparCookieCrm(CRM_EXECUTIVO_COOKIE);
    }

    function atualizarLinksPaginasConsolidadas() {
        const q = queryExecutivoCrm();
        const a = $('#crm-link-atividades-consolidadas');
        const o = $('#crm-link-objetivos-consolidadas');
        if (a) a.setAttribute('href', `${BASE}/atividades-consolidadas${q}`);
        if (o) o.setAttribute('href', `${BASE}/objetivos-consolidadas${q}`);
    }

    function aplicarExecutivoDaUrlNaCrm() {
        const sel = $('#filtro-executivo');
        if (!sel) return;
        const id = new URLSearchParams(window.location.search).get('executivo_id');
        const idCookie = decodeURIComponent(getCookieCrm(CRM_EXECUTIVO_COOKIE));
        const idParaAplicar = id || idCookie;
        if (!idParaAplicar) return;
        const ok = [...sel.options].some(opt => opt.value === idParaAplicar);
        if (ok) {
            sel.value = idParaAplicar;
            salvarExecutivoCookieCrm();
        } else if (!id) {
            limparCookieCrm(CRM_EXECUTIVO_COOKIE);
        }
    }

    // ==================== Modal: Novo Cliente ====================

    function setPessoaClienteModal(pessoa) {
        const form = $('#crm-form-cliente');
        if (!form) return;
        const isPf = pessoa === 'F';
        $$('input[name="pessoa"]', form).forEach(r => { r.checked = r.value === pessoa; });
        $$('.crm-pessoa-toggle', form).forEach(label => {
            const active = label.dataset.pessoa === pessoa;
            label.classList.toggle('border-green-500', active);
            label.classList.toggle('bg-green-50', active);
            label.classList.toggle('text-green-700', active);
            label.classList.toggle('border-gray-300', !active);
            label.classList.toggle('bg-white', !active);
            label.classList.toggle('text-gray-500', !active);
        });

        $('#crm-label-cnpj').textContent = isPf ? 'CPF' : 'CNPJ';
        $('#crm-label-nome').textContent = isPf ? 'Nome Completo*' : 'Nome Fantasia*';
        $('#crm-input-cnpj').placeholder = isPf ? 'CPF' : 'CNPJ';

        const razaoWrap = $('#crm-razao-fields');
        const tipoWrap = $('#crm-tipo-cliente-fields');
        const agenciaWrap = $('#crm-agencia-fields');
        const percentualWrap = $('#crm-percentual-fields');
        const inscricoesWrap = $('#crm-inscricoes-fields');
        const razao = $('#crm-input-razao');
        const tipo = $('#crm-select-tipo-cliente');
        const agencia = $('#crm-cliente-agencia');

        razaoWrap?.classList.toggle('hidden', isPf);
        tipoWrap?.classList.toggle('hidden', isPf);
        agenciaWrap?.classList.toggle('hidden', isPf);
        percentualWrap?.classList.toggle('hidden', isPf);
        inscricoesWrap?.classList.toggle('hidden', isPf);

        if (razao) razao.required = !isPf;
        if (tipo) tipo.required = !isPf;
        if (agencia) agencia.required = !isPf;
        atualizarVisibilidadeAgenciasVinculadasCrm();
    }

    function setStatusClienteModal(ativo) {
        const form = $('#crm-form-cliente');
        if (!form) return;
        const statusValue = ativo ? '1' : '0';
        $$('input[name="status"]', form).forEach(r => { r.checked = r.value === statusValue; });
        $$('.crm-status-toggle', form).forEach(label => {
            const active = label.dataset.status === statusValue;
            const isAtivo = label.dataset.status === '1';
            label.classList.toggle('border-green-500', active && isAtivo);
            label.classList.toggle('bg-green-50', active && isAtivo);
            label.classList.toggle('text-green-700', active && isAtivo);
            label.classList.toggle('border-red-500', active && !isAtivo);
            label.classList.toggle('bg-red-50', active && !isAtivo);
            label.classList.toggle('text-red-700', active && !isAtivo);
            label.classList.toggle('border-gray-300', !active);
            label.classList.toggle('bg-white', !active);
            label.classList.toggle('text-gray-500', !active);
        });
    }

    function setClienteFormValue(name, value) {
        const el = $(`#crm-form-cliente [name="${name}"]`);
        if (el) el.value = value ?? '';
    }

    let crmAgenciasPickerCache = null;
    let crmAgenciasVinculadasState = [];

    async function carregarAgenciasPickerCrm() {
        if (crmAgenciasPickerCache) return crmAgenciasPickerCache;
        try {
            const response = await fetch('/api/clientes/agencias');
            crmAgenciasPickerCache = await response.json();
        } catch (e) {
            console.error(e);
            crmAgenciasPickerCache = [];
        }
        return crmAgenciasPickerCache;
    }

    async function popularPickerAgenciasVinculadasCrm() {
        const picker = $('#crm-agencias-vinculadas-picker');
        if (!picker) return;
        const agencias = await carregarAgenciasPickerCrm();
        const selected = new Set(crmAgenciasVinculadasState.map(a => String(a.id_agencia_cliente)));
        picker.innerHTML = '<option value="">Adicionar agência...</option>' +
            agencias.filter(a => !selected.has(String(a.id_cliente)))
                .map(a => `<option value="${a.id_cliente}">${escapeHtml(a.nome_fantasia || a.razao_social || '')}</option>`)
                .join('');
    }

    function renderAgenciasVinculadasFormCrm(agencias) {
        crmAgenciasVinculadasState = (agencias || []).map(a => ({
            id_agencia_cliente: a.id_agencia_cliente || a.id_cliente,
            nome_fantasia: a.nome_fantasia || '',
            razao_social: a.razao_social || '',
            is_principal: !!a.is_principal
        }));
        if (crmAgenciasVinculadasState.length === 1) {
            crmAgenciasVinculadasState[0].is_principal = true;
        }
        atualizarAgenciasVinculadasUICrm();
        popularPickerAgenciasVinculadasCrm();
    }

    function atualizarVisibilidadeAgenciasVinculadasCrm() {
        const block = $('#crm-agencias-vinculadas-fields');
        if (!block) return;
        const pessoa = $('#crm-form-cliente input[name="pessoa"]:checked')?.value || 'J';
        const opt = $('#crm-cliente-agencia')?.selectedOptions?.[0];
        const agenciaSim = opt && opt.getAttribute('data-agencia-sim') === '1';
        if (pessoa === 'J' && !agenciaSim) {
            block.style.display = '';
        } else {
            block.style.display = 'none';
            if (agenciaSim || pessoa === 'F') {
                crmAgenciasVinculadasState = [];
                atualizarAgenciasVinculadasUICrm();
            }
        }
    }

    function definirAgenciaPrincipalVinculadaCrm(id) {
        crmAgenciasVinculadasState.forEach(a => { a.is_principal = a.id_agencia_cliente === id; });
        atualizarAgenciasVinculadasUICrm();
    }

    function removerAgenciaVinculadaCrm(id) {
        crmAgenciasVinculadasState = crmAgenciasVinculadasState.filter(a => a.id_agencia_cliente !== id);
        if (crmAgenciasVinculadasState.length === 1) {
            crmAgenciasVinculadasState[0].is_principal = true;
        } else if (!crmAgenciasVinculadasState.some(a => a.is_principal)) {
            crmAgenciasVinculadasState.forEach(a => { a.is_principal = false; });
        }
        atualizarAgenciasVinculadasUICrm();
        popularPickerAgenciasVinculadasCrm();
    }

    async function adicionarAgenciaVinculadaCrm() {
        const picker = $('#crm-agencias-vinculadas-picker');
        if (!picker || !picker.value) return;
        const id = parseInt(picker.value, 10);
        if (crmAgenciasVinculadasState.some(a => a.id_agencia_cliente === id)) return;
        const agencias = await carregarAgenciasPickerCrm();
        const found = agencias.find(a => a.id_cliente === id);
        crmAgenciasVinculadasState.push({
            id_agencia_cliente: id,
            nome_fantasia: found?.nome_fantasia || '',
            razao_social: found?.razao_social || '',
            is_principal: crmAgenciasVinculadasState.length === 0
        });
        if (crmAgenciasVinculadasState.length === 1) {
            crmAgenciasVinculadasState[0].is_principal = true;
        }
        picker.value = '';
        atualizarAgenciasVinculadasUICrm();
        popularPickerAgenciasVinculadasCrm();
    }

    function atualizarAgenciasVinculadasUICrm() {
        const lista = $('#crm-agencias-vinculadas-lista');
        const hiddenWrap = $('#crm-agencias-vinculadas-hidden');
        if (!lista || !hiddenWrap) return;

        if (!crmAgenciasVinculadasState.length) {
            lista.innerHTML = '<div class="text-[10px] text-gray-400 italic">Nenhuma agência vinculada.</div>';
        } else {
            lista.innerHTML = crmAgenciasVinculadasState.map(a => {
                const nome = escapeHtml(a.nome_fantasia || a.razao_social || ('#' + a.id_agencia_cliente));
                return `
                    <div class="flex items-center gap-2 text-[10px] border border-gray-200 rounded px-2 py-1 bg-white">
                        <label class="flex items-center gap-1 cursor-pointer shrink-0">
                            <input type="radio" name="crm_agencia_principal_radio" value="${a.id_agencia_cliente}" ${a.is_principal ? 'checked' : ''}>
                            <span class="text-gray-500">Principal</span>
                        </label>
                        <span class="flex-1 truncate">${nome}</span>
                        <button type="button" class="text-red-500 hover:text-red-700 crm-agencia-vinculada-del" data-id="${a.id_agencia_cliente}" title="Remover">×</button>
                    </div>`;
            }).join('');
            $$('.crm-agencia-vinculada-del', lista).forEach(btn => {
                btn.addEventListener('click', () => removerAgenciaVinculadaCrm(parseInt(btn.dataset.id, 10)));
            });
            $$('input[name="crm_agencia_principal_radio"]', lista).forEach(radio => {
                radio.addEventListener('change', () => definirAgenciaPrincipalVinculadaCrm(parseInt(radio.value, 10)));
            });
        }

        const principal = crmAgenciasVinculadasState.find(a => a.is_principal);
        hiddenWrap.innerHTML = crmAgenciasVinculadasState.map(a =>
            `<input type="hidden" name="agencias_vinculadas[]" value="${a.id_agencia_cliente}">`
        ).join('') + (principal
            ? `<input type="hidden" name="agencia_principal_id" value="${principal.id_agencia_cliente}">`
            : '');
    }

    function atualizarBvClienteModal() {
        const tipo = $('#crm-select-tipo-cliente');
        const agencia = $('#crm-cliente-agencia');
        const wrap = $('#crm-percentual-fields');
        if (!tipo || !agencia || !wrap) return;
        const isParceiro = tipo.selectedOptions[0]?.dataset.parceiro === '1';
        const isAgencia = agencia.selectedOptions[0]?.dataset.agenciaSim === '1';
        const pessoa = $('#crm-form-cliente input[name="pessoa"]:checked')?.value || 'J';
        wrap.classList.toggle('hidden', pessoa === 'F' || (!isParceiro && !isAgencia));
        if (wrap.classList.contains('hidden')) {
            const pct = $('#crm-cliente-percentual');
            if (pct) pct.value = '';
        }
        atualizarVisibilidadeAgenciasVinculadasCrm();
    }

    function preselecionarExecutivoClienteModal() {
        const selectVendas = $('#crm-cliente-vendedor');
        if (!selectVendas) return;
        const logged = String(window.CRM_LOGGED_USER_ID || '');
        const filtro = $('#filtro-executivo')?.value || '';
        const alvo = logged && [...selectVendas.options].some(opt => opt.value === logged)
            ? logged
            : filtro;
        if (alvo && [...selectVendas.options].some(opt => opt.value === String(alvo))) {
            selectVendas.value = String(alvo);
        }
    }

    function abrirModalNovoCliente() {
        const modal = $('#crm-modal-cliente');
        const form = $('#crm-form-cliente');
        if (!modal || !form) return;
        form.reset();
        $('#crm-cliente-id').value = '';
        $('#crm-cliente-modal-title').textContent = 'Novo Cliente';
        $('#crm-cliente-submit').textContent = 'Cadastrar';
        $('#crm-status-fields')?.classList.add('hidden');
        $('#crm-classificacao-cliente').value = 'Prospecção';
        setClienteFormValue('opera_midia', '0');
        setClienteFormValue('demanda_dados', '0');
        setClienteFormValue('demanda_programatica_canais', '0');
        setClienteFormValue('observacoes_comerciais_adicionais', '');
        setStatusClienteModal(true);
        setPessoaClienteModal('J');
        preselecionarExecutivoClienteModal();
        renderAgenciasVinculadasFormCrm([]);
        atualizarBvClienteModal();
        modal.showModal();
        setTimeout(() => $('#crm-input-nome')?.focus(), 50);
    }

    async function abrirModalEditarCliente(clienteId) {
        const modal = $('#crm-modal-cliente');
        const form = $('#crm-form-cliente');
        if (!modal || !form || !clienteId) return;
        form.reset();
        $('#crm-cliente-modal-title').textContent = 'Carregando cliente...';
        $('#crm-cliente-submit').textContent = 'Atualizar';
        $('#crm-status-fields')?.classList.remove('hidden');
        modal.showModal();

        try {
            const response = await fetch(`/api/cliente/${clienteId}`);
            const cliente = await response.json();
            if (!response.ok || cliente.error) {
                throw new Error(cliente.error || 'Erro ao carregar cliente.');
            }

            $('#crm-cliente-modal-title').textContent = cliente.nome_fantasia || cliente.razao_social || 'Editar Cliente';
            $('#crm-cliente-id').value = clienteId;
            setPessoaClienteModal(cliente.pessoa || 'J');
            setStatusClienteModal(cliente.status !== false);

            setClienteFormValue('cnpj', cliente.cnpj || '');
            setClienteFormValue('nome_fantasia', cliente.nome_fantasia || '');
            setClienteFormValue('razao_social', cliente.razao_social || '');
            setClienteFormValue('id_tipo_cliente', cliente.id_tipo_cliente || '');
            setClienteFormValue('classificacao_cliente', cliente.classificacao_cliente || 'Prospecção');
            setClienteFormValue('opera_midia', cliente.opera_midia ? '1' : '0');
            setClienteFormValue('demanda_dados', cliente.demanda_dados ? '1' : '0');
            setClienteFormValue('demanda_programatica_canais', cliente.demanda_programatica_canais ? '1' : '0');
            setClienteFormValue('observacoes_comerciais_adicionais', cliente.observacoes_comerciais_adicionais || '');
            setClienteFormValue('vendas_central_comm', cliente.vendas_central_comm || '');
            setClienteFormValue('pk_id_tbl_agencia', cliente.pk_id_tbl_agencia || '');
            setClienteFormValue('margem_cc', cliente.margem_cc === null || cliente.margem_cc === undefined ? '' : String(parseInt(cliente.margem_cc, 10)));
            setClienteFormValue('percentual', cliente.percentual ? parseFloat(cliente.percentual).toFixed(2).replace('.', ',') : '');
            setClienteFormValue('inscricao_estadual', cliente.inscricao_estadual || '');
            setClienteFormValue('inscricao_municipal', cliente.inscricao_municipal || '');
            setClienteFormValue('cep', cliente.cep || '');
            setClienteFormValue('pk_id_aux_estado', cliente.estado || cliente.pk_id_aux_estado || '');
            setClienteFormValue('cidade', cliente.cidade || '');
            setClienteFormValue('bairro', cliente.bairro || '');
            setClienteFormValue('logradouro', cliente.logradouro || '');
            setClienteFormValue('numero', cliente.numero || '');
            setClienteFormValue('complemento', cliente.complemento || '');
            renderAgenciasVinculadasFormCrm(cliente.agencias_vinculadas || []);
            atualizarBvClienteModal();
        } catch (e) {
            console.error(e);
            modal.close();
            showToast(e.message || 'Erro ao carregar cliente.', 'error');
        }
    }

    async function salvarNovoClienteCrm(ev) {
        ev.preventDefault();
        const form = $('#crm-form-cliente');
        const modal = $('#crm-modal-cliente');
        const btn = $('#crm-cliente-submit');
        if (!form || !modal) return;
        const clienteId = $('#crm-cliente-id')?.value || '';
        const formData = new FormData(form);
        formData.set('_return_json', '1');

        btn?.classList.add('loading');
        if (btn) btn.disabled = true;
        try {
            const url = clienteId ? `/clientes/${clienteId}/editar` : '/clientes/novo';
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                redirect: 'manual'
            });
            const data = await response.json().catch(() => null);
            if (!response.ok || !data?.success) {
                throw new Error(data?.message || 'Erro ao salvar cliente.');
            }

            modal.close();
            if (data.warning) showToast(data.warning, 'warning');
            showToast(clienteId ? 'Cliente atualizado.' : `Cliente "${data.nome_fantasia || 'novo'}" criado.`, 'success');

            const vendedorId = formData.get('vendas_central_comm');
            const filtroExec = $('#filtro-executivo');
            if (!clienteId && filtroExec && !filtroExec.value && vendedorId) {
                filtroExec.value = vendedorId;
                salvarExecutivoCookieCrm();
                atualizarLinksPaginasConsolidadas();
            }
            await carregarClientes();
            const idParaSelecionar = data.id_cliente || clienteId;
            if (idParaSelecionar && crmCliCache.some(c => String(c.id_cliente) === String(idParaSelecionar))) {
                selecionarCliente(parseInt(idParaSelecionar, 10));
            }
        } catch (e) {
            console.error(e);
            showToast(e.message || 'Erro ao salvar cliente.', 'error');
        } finally {
            btn?.classList.remove('loading');
            if (btn) btn.disabled = false;
        }
    }

    // ==================== Modal: Nova Cotação ====================

    function preselecionarResponsavelCotacao(clienteData = {}) {
        const selectResp = $('#crm-cotacao-responsavel');
        if (!selectResp) return;
        const logged = String(window.CRM_LOGGED_USER_ID || '');
        const filtro = $('#filtro-executivo')?.value || '';
        const clienteResp = clienteData.vendas_central_comm ? String(clienteData.vendas_central_comm) : '';
        const candidatos = [logged, clienteResp, filtro].filter(Boolean);
        const alvo = candidatos.find(id => [...selectResp.options].some(opt => opt.value === String(id)));
        if (alvo) selectResp.value = String(alvo);
    }

    function atualizarDuracaoCotacao() {
        const inicio = $('#crm-cotacao-inicio')?.value;
        const fim = $('#crm-cotacao-fim')?.value;
        const out = $('#crm-cotacao-duracao');
        if (!out) return;
        if (!inicio || !fim) {
            out.value = '';
            return;
        }
        const d1 = new Date(`${inicio}T00:00:00`);
        const d2 = new Date(`${fim}T00:00:00`);
        const diff = Math.round((d2 - d1) / 86400000) + 1;
        out.value = diff > 0 ? `${diff} dia(s)` : '';
    }

    async function melhorarBriefingCotacaoCRM(acao) {
        const el = $('#crm-cotacao-briefing');
        if (!el) return;
        const texto = (el.value || '').trim();
        if (!texto) {
            showToast('Preencha o resumo do briefing antes de usar a IA.', 'warning');
            return;
        }
        const btnGroup = el.parentElement?.querySelector('[data-ia-group]');
        if (btnGroup) btnGroup.classList.add('opacity-50', 'pointer-events-none');
        try {
            const data = await api('/api/ia/cotacao-briefing', {
                method: 'POST',
                body: JSON.stringify({ texto, acao, campo: 'apresentacao_dados' }),
            });
            if (data?.success) {
                el.value = (data.texto || '').trim().slice(0, el.maxLength || 4000);
                showToast(acao === 'corrigir' ? 'Texto corrigido pela IA.' : 'Texto ampliado pela IA.', 'success');
            } else {
                showToast(data?.message || 'Falha na IA.', 'error');
            }
        } catch (e) {
            console.error('melhorarBriefingCotacaoCRM', e);
            showToast(e.message || 'Falha ao chamar a IA.', 'error');
        } finally {
            if (btnGroup) btnGroup.classList.remove('opacity-50', 'pointer-events-none');
        }
    }

    async function carregarContatosCotacao(clienteId, selectSelector = '#crm-cotacao-contato') {
        const selectContato = $(selectSelector);
        if (!selectContato) return;
        if (!clienteId) {
            selectContato.innerHTML = '<option value="">Selecione o contato</option>';
            return;
        }
        selectContato.innerHTML = '<option value="">Carregando contatos...</option>';
        try {
            const data = await api(`/api/cliente/${clienteId}/contatos`);
            const contatos = data.contatos || [];
            selectContato.innerHTML = '<option value="">Selecione o contato</option>' + contatos.map(c => (
                `<option value="${c.id_contato_cliente}">${escapeHtml(c.nome_completo)}${c.email ? ` · ${escapeHtml(c.email)}` : ''}</option>`
            )).join('');
        } catch (e) {
            console.error(e);
            selectContato.innerHTML = '<option value="">Erro ao carregar contatos</option>';
        }
    }

    async function abrirModalNovaCotacao(clienteId) {
        const modal = $('#crm-modal-cotacao');
        const form = $('#crm-form-cotacao');
        if (!modal || !form) return;
        const id = clienteId || clienteSelecionadoId;
        if (!id) {
            showToast('Selecione um cliente.', 'warning');
            return;
        }

        form.reset();
        $('#crm-cotacao-client-id').value = '';
        $('#crm-cotacao-inicio').value = isoDatePlusDays(7);
        $('#crm-cotacao-fim').value = isoDatePlusDays(37);
        $('#crm-cotacao-valor-total-hidden').value = '';
        $('#crm-cotacao-budget-hidden').value = '';
        $('#crm-cotacao-cliente-select').value = '';
        $('#crm-cotacao-agencia').value = '';
        $('#crm-cotacao-parceiro').value = '';
        $('#crm-cotacao-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#crm-cotacao-agencia-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#crm-cotacao-parceiro-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#crm-cotacao-briefing-nome')?.classList.add('hidden');
        if ($('#crm-cotacao-briefing-nome')) $('#crm-cotacao-briefing-nome').textContent = '';
        atualizarDuracaoCotacao();

        const clienteCache = crmCliCache.find(c => String(c.id_cliente) === String(id)) || {};
        preselecionarResponsavelCotacao(clienteCache);
        let focoInicial = '#crm-cotacao-nome';
        if (clienteEhAgencia(clienteCache)) {
            $('#crm-cotacao-agencia').value = String(id);
            carregarContatosCotacao(id, '#crm-cotacao-agencia-contato');
            focoInicial = '#crm-cotacao-agencia';
        } else if (clienteEhParceiroRegional(clienteCache)) {
            $('#crm-cotacao-parceiro').value = String(id);
            carregarContatosCotacao(id, '#crm-cotacao-parceiro-contato');
            focoInicial = '#crm-cotacao-parceiro';
        } else {
            $('#crm-cotacao-client-id').value = id;
            $('#crm-cotacao-cliente-select').value = String(id);
            carregarContatosCotacao(id);
            const principalId = clienteCache.agencia_principal_id;
            if (principalId) {
                $('#crm-cotacao-agencia').value = String(principalId);
                carregarContatosCotacao(principalId, '#crm-cotacao-agencia-contato');
            }
        }

        modal.showModal();
        setTimeout(() => $(focoInicial)?.focus(), 50);

        try {
            const response = await fetch(`/api/cliente/${id}`);
            if (response.ok) {
                const cliente = await response.json();
                preselecionarResponsavelCotacao(cliente);
                if (!clienteEhAgencia(cliente) && !clienteEhParceiroRegional(cliente)) {
                    const principal = (cliente.agencias_vinculadas || []).find(a => a.is_principal);
                    if (principal?.id_agencia_cliente) {
                        $('#crm-cotacao-agencia').value = String(principal.id_agencia_cliente);
                        carregarContatosCotacao(principal.id_agencia_cliente, '#crm-cotacao-agencia-contato');
                    }
                }
            }
        } catch (e) {
            console.warn('Não foi possível pré-selecionar responsável pelo cliente.', e);
        }
    }

    async function salvarNovaCotacaoCrm(ev) {
        ev.preventDefault();
        const form = $('#crm-form-cotacao');
        const modal = $('#crm-modal-cotacao');
        const btn = $('#crm-cotacao-submit');
        const clienteId = $('#crm-cotacao-client-id')?.value;
        if (!form || !modal || !clienteId) {
            showToast('Selecione um cliente.', 'warning');
            return;
        }

        const formData = new FormData(form);
        btn?.classList.add('loading');
        if (btn) btn.disabled = true;
        try {
            const response = await fetch(`${BASE}/api/cliente/${clienteId}/cotacoes`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json().catch(() => null);
            if (!response.ok || !data?.success) {
                throw new Error(data?.error || 'Erro ao criar cotação.');
            }
            modal.close();
            showToast(`Cotação ${data.numero_cotacao || ''} criada.`, 'success');
            if (data.warning) showToast(data.warning, 'warning');
            if (clienteSelecionadoId) {
                carregarStatus(parseInt(clienteSelecionadoId, 10));
                carregarCotacoesAbertas(parseInt(clienteSelecionadoId, 10));
            }
        } catch (e) {
            console.error(e);
            showToast(e.message || 'Erro ao criar cotação.', 'error');
        } finally {
            btn?.classList.remove('loading');
            if (btn) btn.disabled = false;
        }
    }

    // ==================== Init & Event Bindings ====================

    document.addEventListener('DOMContentLoaded', () => {
        aplicarExecutivoDaUrlNaCrm();
        atualizarLinksPaginasConsolidadas();

        $('#filtro-executivo').addEventListener('change', () => {
            salvarExecutivoCookieCrm();
            atualizarLinksPaginasConsolidadas();
            limparColunas();
            carregarClientes();
        });

        $('#filtro-tipo')?.addEventListener('change', carregarClientes);
        $('#filtro-perfil')?.addEventListener('change', carregarClientes);

        $('#busca-cliente').addEventListener('input', debounce(carregarClientes, 300));

        $$('#tabs-atividades .crm-tab-ativ').forEach(tab => {
            tab.addEventListener('click', () => {
                setTabAtividades(tab.dataset.tab);
                if (!clienteSelecionadoId) return;
                if (tab.dataset.tab === 'todas') {
                    contatoSelecionadoId = null;
                    $$('.crm-contact-card').forEach(e => e.classList.remove('crm-contact-card-active'));
                    renderContatosCrm();
                }
                // Filtragem client-side sobre o cache já carregado.
                renderAtividades();
            });
        });

        // ---- Paginação da coluna Clientes ----
        $('#crm-cli-prev')?.addEventListener('click', () => {
            if (crmCliPage > 0) { crmCliPage--; renderClientesPagina(); }
        });
        $('#crm-cli-next')?.addEventListener('click', () => {
            const totalPages = Math.ceil(crmCliCache.length / CRM_CLI_PAGE_SIZE);
            if (crmCliPage < totalPages - 1) { crmCliPage++; renderClientesPagina(); }
        });

        // ---- Botões de ação no header ----
        function focarColuna(sel, inputSel) {
            if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
            const col = $(sel);
            scrollIntoViewSuave(col);
            const inp = inputSel ? $(inputSel) : null;
            if (inp) setTimeout(() => inp.focus(), 250);
        }
        $('#crm-btn-novo-cliente')?.addEventListener('click', abrirModalNovoCliente);
        $('#btn-nova-cotacao-crm')?.addEventListener('click', () => abrirModalNovaCotacao(clienteSelecionadoId));
        $('#crm-btn-nova-atividade')?.addEventListener('click', () => {
            if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
            setTabAtividades('todas');
            renderAtividades();
            focarColuna('#col-atividades', '#input-atividade');
        });
        // ---- Exportar (CSV) ----
        function exportarCSV(tipo) {
            const execId = $('#filtro-executivo')?.value;
            if (!execId) { showToast('Selecione um executivo.', 'warning'); return; }
            const params = new URLSearchParams({ executivo_id: execId });
            if (clienteSelecionadoId) params.set('cliente_id', clienteSelecionadoId);
            const det = $('#crm-export'); if (det) det.open = false;
            window.location.href = `${BASE}/api/export/${tipo}?${params}`;
        }
        $('#crm-export-atividades')?.addEventListener('click', () => exportarCSV('atividades'));
        $('#crm-export-objetivos')?.addEventListener('click', () => exportarCSV('objetivos'));

        // ---- Modal Novo Cliente ----
        $('#crm-form-cliente')?.addEventListener('submit', salvarNovoClienteCrm);
        $('#crm-cliente-close')?.addEventListener('click', () => $('#crm-modal-cliente')?.close());
        $('#crm-cliente-cancel')?.addEventListener('click', () => $('#crm-modal-cliente')?.close());
        $$('#crm-form-cliente input[name="pessoa"]').forEach(radio => {
            radio.addEventListener('change', () => {
                setPessoaClienteModal(radio.value);
                atualizarBvClienteModal();
            });
        });
        $$('#crm-form-cliente input[name="status"]').forEach(radio => {
            radio.addEventListener('change', () => setStatusClienteModal(radio.value === '1'));
        });
        $('#crm-input-cnpj')?.addEventListener('input', ev => maskCpfCnpj(ev.target));
        $('#crm-cliente-cep')?.addEventListener('input', ev => maskCep(ev.target));
        $('#crm-cliente-percentual')?.addEventListener('input', ev => maskPercentual(ev.target));
        $('#crm-select-tipo-cliente')?.addEventListener('change', atualizarBvClienteModal);
        $('#crm-cliente-agencia')?.addEventListener('change', atualizarBvClienteModal);
        $('#crm-btn-agencia-vinculada-add')?.addEventListener('click', adicionarAgenciaVinculadaCrm);
        carregarAgenciasPickerCrm().then(() => popularPickerAgenciasVinculadasCrm());

        // ---- Modal Nova Cotação ----
        $('#crm-form-cotacao')?.addEventListener('submit', salvarNovaCotacaoCrm);
        $('#crm-cotacao-close')?.addEventListener('click', () => $('#crm-modal-cotacao')?.close());
        $('#crm-cotacao-cancel')?.addEventListener('click', () => $('#crm-modal-cotacao')?.close());
        $('#crm-cotacao-valor-total')?.addEventListener('input', ev => maskMoneyBR(ev.target, $('#crm-cotacao-valor-total-hidden')));
        $('#crm-cotacao-budget')?.addEventListener('input', ev => maskMoneyBR(ev.target, $('#crm-cotacao-budget-hidden')));
        $('#crm-cotacao-inicio')?.addEventListener('change', atualizarDuracaoCotacao);
        $('#crm-cotacao-fim')?.addEventListener('change', atualizarDuracaoCotacao);
        $('#crm-cotacao-cliente-select')?.addEventListener('change', ev => {
            $('#crm-cotacao-client-id').value = ev.target.value || '';
            carregarContatosCotacao(ev.target.value, '#crm-cotacao-contato');
        });
        $('#crm-cotacao-agencia')?.addEventListener('change', ev => carregarContatosCotacao(ev.target.value, '#crm-cotacao-agencia-contato'));
        $('#crm-cotacao-parceiro')?.addEventListener('change', ev => carregarContatosCotacao(ev.target.value, '#crm-cotacao-parceiro-contato'));
        $('#crm-cotacao-briefing-dropzone')?.addEventListener('click', () => $('#crm-cotacao-briefing-arquivo')?.click());
        $('#crm-cotacao-briefing-arquivo')?.addEventListener('change', ev => {
            const file = ev.target.files?.[0];
            const label = $('#crm-cotacao-briefing-nome');
            if (!label) return;
            label.textContent = file ? file.name : '';
            label.classList.toggle('hidden', !file);
        });
        $$('[data-ia-briefing]').forEach(btn => {
            btn.addEventListener('click', () => melhorarBriefingCotacaoCRM(btn.dataset.iaBriefing));
        });

        // ---- Seção WhatsApp (coluna 5) ----
        $('#crm-contato-busca')?.addEventListener('input', debounce(ev => {
            crmContatoBusca = ev.target.value || '';
            renderContatosCrm();
        }, 120));
        $('#crm-chat-busca')?.addEventListener('input', debounce(ev => {
            crmChatBusca = ev.target.value || '';
            renderConversasComerciais();
        }, 120));
        $$('#crm-chat-tabs [data-chat-tab]').forEach(btn => {
            btn.addEventListener('click', () => {
                crmChatTab = btn.dataset.chatTab;
                $$('#crm-chat-tabs [data-chat-tab]').forEach(b => b.classList.toggle('active', b === btn));
                renderConversasComerciais();
            });
        });
        $('#crm-btn-nova-conversa')?.addEventListener('click', () => {
            if (!contatoSelecionadoId) { showToast('Selecione um contato.', 'warning'); return; }
            const contato = contatoSelecionadoAtual();
            const telefone = telefoneSelecionado || contato?.telefone || contato?.telefone_secundario || null;
            if (!telefone) { showToast('Contato sem telefone para WhatsApp.', 'warning'); return; }
            abrirConversaTelefone(contatoSelecionadoId, telefone).then(id => {
                if (id) $('#crm-chat-input')?.focus();
            });
        });
        $('#crm-chat-enviar')?.addEventListener('click', enviarMensagemComercial);
        $('#crm-chat-input')?.addEventListener('keydown', ev => {
            if (ev.key === 'Enter' && !ev.shiftKey) {
                ev.preventDefault();
                enviarMensagemComercial();
            }
        });
        $('#crm-auto-tipo')?.addEventListener('change', () => carregarAutomacaoComercial(clienteSelecionadoId, contatoSelecionadoId));
        $('#crm-auto-salvar')?.addEventListener('click', () => salvarAutomacaoComercial(true));
        $('#crm-auto-ativo')?.addEventListener('change', () => salvarAutomacaoComercial(false));

        $$('[data-modal-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                if (tab.dataset.modalTab === 'dados') showTabDados();
                else if (tab.dataset.modalTab === 'editar') showTabEditar();
                else showTabComunicacao();
            });
        });

        $('#ce-btn-salvar')?.addEventListener('click', async () => {
            const nome = ($('#ce-nome')?.value || '').trim();
            const email = ($('#ce-email')?.value || '').trim();
            if (!nome || !email) { showToast('Nome e e-mail são obrigatórios.', 'warning'); return; }
            const btn = $('#ce-btn-salvar');
            btn.classList.add('loading');
            try {
                const r = await api(`/api/contato/${modalContatoId}/editar`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        nome_completo: nome,
                        email,
                        telefone: ($('#ce-tel')?.value || '').trim(),
                        telefone_secundario: ($('#ce-tel2')?.value || '').trim(),
                    })
                });
                showToast(r.message || 'Contato atualizado.', 'success');
                $('#modal-contato-nome').textContent = nome;
                carregarContatos(clienteSelecionadoId);
            } catch (e) {
                showToast(e.data?.message || e.message || 'Erro ao salvar.', 'error');
            } finally {
                btn.classList.remove('loading');
            }
        });

        $('#ce-btn-deletar')?.addEventListener('click', async () => {
            const nome = $('#ce-nome')?.value || 'este contato';
            if (!confirm(`Apagar "${nome}"? Esta ação não pode ser desfeita.`)) return;
            const btn = $('#ce-btn-deletar');
            btn.classList.add('loading');
            try {
                const r = await api(`/api/contato/${modalContatoId}/deletar`, { method: 'DELETE' });
                showToast(r.message || 'Contato apagado.', 'success');
                document.getElementById('modal-contato')?.close();
                contatoSelecionadoId = null;
                carregarContatos(clienteSelecionadoId);
            } catch (e) {
                const msg = e.data?.message || e.message || 'Erro ao apagar.';
                showToast(msg, e.data?.has_vinculos ? 'warning' : 'error');
            } finally {
                btn.classList.remove('loading');
            }
        });

        $('#btn-gerar-comunicacao')?.addEventListener('click', gerarComunicacao);
        $('#btn-regenerar')?.addEventListener('click', gerarComunicacao);

        $('#btn-copiar')?.addEventListener('click', () => {
            const text = $('#com-texto').textContent;
            navigator.clipboard.writeText(text).then(() => {
                const btn = $('#btn-copiar');
                btn.textContent = 'Copiado!';
                setTimeout(() => btn.textContent = 'Copiar', 1500);
            });
        });

        $('#btn-abrir-whatsapp')?.addEventListener('click', () => {
            const text = $('#com-texto').textContent.trim();
            const input = $('#crm-chat-input');
            if (input && text) {
                input.value = text;
                input.focus();
                showToast('Mensagem preenchida no WhatsApp do CRM.', 'success');
            } else if (text) {
                navigator.clipboard.writeText(text);
                showToast('Mensagem copiada.', 'success');
            }
        });

        $('#btn-abrir-email')?.addEventListener('click', () => {
            const text = $('#com-texto').textContent;
            const lines = text.split('\n');
            let subject = '';
            let body = text;
            const subjectMatch = lines[0]?.match(/^assunto:\s*(.+)/i);
            if (subjectMatch) {
                subject = subjectMatch[1].trim();
                body = lines.slice(1).join('\n').trim();
            }
            window.open(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`, '_blank');
        });

        $('#ea-save')?.addEventListener('click', async () => {
            const id = $('#ea-id').value;
            if (!id) return;
            const desc = $('#ea-desc').value.trim();
            if (!desc) { showToast('Descrição obrigatória.', 'warning'); return; }
            const btn = $('#ea-save');
            btn?.classList.add('loading');
            try {
                await api(`/api/atividades/${id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        titulo: $('#ea-titulo').value.trim() || null,
                        descricao: desc,
                        data_atividade: $('#ea-data').value,
                        data_prazo: $('#ea-prazo').value || null,
                        tipo: $('#ea-tipo').value,
                        status: $('#ea-status').value
                    })
                });
                $('#modal-editar-atividade').close();
                carregarAtividades(crmActCtx.clienteId, crmActCtx.contatoId);
            } catch (e) {
                console.error(e);
                showToast(e.message || 'Erro ao salvar.', 'error');
            } finally {
                btn?.classList.remove('loading');
            }
        });

        $('#eo-save')?.addEventListener('click', async () => {
            const id = $('#eo-id').value;
            if (!id) return;
            const tx = $('#eo-texto').value.trim();
            if (!tx) { showToast('Texto obrigatório.', 'warning'); return; }
            const btn = $('#eo-save');
            btn?.classList.add('loading');
            try {
                await api(`/api/objetivos/${id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        texto: tx,
                        data_prazo: $('#eo-prazo').value || null
                    })
                });
                $('#modal-editar-objetivo').close();
                if (crmObjCtx.clienteId) carregarObjetivos(crmObjCtx.clienteId);
            } catch (e) {
                console.error(e);
                showToast(e.message || 'Erro ao salvar objetivo.', 'error');
            } finally {
                btn?.classList.remove('loading');
            }
        });

        $('#btn-contato-novo')?.addEventListener('click', () => {
            if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
            $('#cr-nome').value = '';
            $('#cr-email').value = '';
            $('#cr-tel').value = '';
            $('#cr-tel2').value = '';
            $('#modal-contato-rapido').showModal();
        });

        $('#form-contato-rapido')?.addEventListener('submit', async (ev) => {
            ev.preventDefault();
            if (!clienteSelecionadoId) return;
            const sub = $('#cr-submit');
            sub?.classList.add('loading');
            try {
                await api(`/api/cliente/${clienteSelecionadoId}/contato-rapido`, {
                    method: 'POST',
                    body: JSON.stringify({
                        nome_completo: $('#cr-nome').value.trim(),
                        email: $('#cr-email').value.trim(),
                        telefone: $('#cr-tel').value.trim() || null,
                        telefone_secundario: $('#cr-tel2').value.trim() || null
                    })
                });
                $('#modal-contato-rapido').close();
                showToast('Contato criado.', 'success');
                carregarContatos(clienteSelecionadoId);
            } catch (e) {
                showToast(e.message || 'Erro ao criar contato.', 'error');
            } finally {
                sub?.classList.remove('loading');
            }
        });

        // ---- Contact Import: multi-step flow ----
        (function setupImportContatos() {

            // Heuristic: every non-empty line has a ";" and the second field contains "@"
            function detectaFormatoSimples(texto) {
                const linhas = texto.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
                if (!linhas.length) return false;
                return linhas.every(l => {
                    const parts = l.split(';');
                    return parts.length >= 2 && parts[1].trim().includes('@');
                });
            }

            // Parse structured "Nome;email;tel;tel2" text locally
            function parseFormatoSimples(texto) {
                const contatos = [];
                texto.split('\n').forEach(line => {
                    line = line.trim();
                    if (!line || line.startsWith('#')) return;
                    let parts = line.replace(/\t/g, ';').split(';').map(p => p.trim());
                    if (parts.length < 2) parts = line.split(',').map(p => p.trim());
                    const nome = parts[0] || '';
                    const email = (parts[1] || '').toLowerCase();
                    const telefone = parts[2] || '';
                    const telefone2 = parts[3] || '';
                    contatos.push({ nome, email, telefone, telefone2 });
                });
                return contatos;
            }

            function ciSetLoading(show, msg) {
                const actions = $('#ci-step1-actions');
                const loading = $('#ci-step1-loading');
                const msgEl = $('#ci-loading-msg');
                if (show) {
                    actions.classList.add('hidden');
                    loading.classList.remove('hidden');
                    if (msgEl && msg) msgEl.textContent = msg;
                } else {
                    actions.classList.remove('hidden');
                    loading.classList.add('hidden');
                }
            }

            function ciShowErroIA(msg) {
                const banner = $('#ci-erro-ia');
                const msgEl = $('#ci-erro-ia-msg');
                if (msgEl) msgEl.textContent = msg;
                banner?.classList.remove('hidden');
            }

            function ciHideErroIA() {
                $('#ci-erro-ia')?.classList.add('hidden');
            }

            function ciGoToStep1() {
                $('#ci-step-1')?.classList.remove('hidden');
                $('#ci-step-2')?.classList.add('hidden');
                ciSetLoading(false);
            }

            function ciGoToStep2() {
                $('#ci-step-1')?.classList.add('hidden');
                $('#ci-step-2')?.classList.remove('hidden');
                $('#ci-result')?.classList.add('hidden');
            }

            async function ciVerificarEExibir(contatos) {
                ciSetLoading(true, 'Verificando contatos na base…');
                try {
                    const r = await api(`/api/cliente/${clienteSelecionadoId}/contatos/verificar`, {
                        method: 'POST',
                        body: JSON.stringify({ contatos })
                    });
                    ciSetLoading(false);
                    renderPreviewTable(r.contatos);
                    ciGoToStep2();
                } catch (e) {
                    ciSetLoading(false);
                    ciShowErroIA(e.message || 'Erro ao verificar contatos.');
                }
            }

            // Build the preview table from the verified contacts array
            function renderPreviewTable(contatos) {
                const tbody = $('#ci-preview-tbody');
                if (!tbody) return;
                tbody.innerHTML = '';

                contatos.forEach((c, idx) => {
                    const tr = document.createElement('tr');
                    tr.dataset.idx = idx;

                    const statusLabels = { novo: 'Novo', existe: 'Já existe', incompleto: 'Incompleto' };
                    const statusClasses = { novo: 'badge-success', existe: 'badge-warning', incompleto: 'badge-error' };

                    // Determine default action
                    let defaultAcao = c.status === 'novo' ? 'criar'
                        : c.status === 'existe' ? 'atualizar'
                        : 'ignorar';

                    // Highlight fields that differ from existing record
                    function diffClass(field) {
                        if (c.status !== 'existe' || !c.dados_atuais) return '';
                        const atual = (c.dados_atuais[field] || '').toLowerCase().trim();
                        const novo = (c[field === 'telefone2' ? 'telefone2' : field] || '').toLowerCase().trim();
                        return atual && atual !== novo ? 'input-error' : '';
                    }

                    // Build diff tooltip text for existing contacts
                    let tooltipTitle = '';
                    if (c.status === 'existe' && c.dados_atuais) {
                        const d = c.dados_atuais;
                        tooltipTitle = `Atual: ${d.nome} | ${d.email} | ${d.telefone || '—'} | ${d.telefone2 || '—'}`;
                    }

                    tr.innerHTML = `
                        <td><input class="input input-bordered input-xs w-full ${diffClass('nome')} ci-nome" value="${escHtml(c.nome)}" data-orig="${escHtml(c.nome)}" /></td>
                        <td><input class="input input-bordered input-xs w-full ${diffClass('email')} ci-email" value="${escHtml(c.email)}" data-orig="${escHtml(c.email)}" /></td>
                        <td><input class="input input-bordered input-xs w-full ${diffClass('telefone')} ci-tel" value="${escHtml(c.telefone || '')}" /></td>
                        <td><input class="input input-bordered input-xs w-full ${diffClass('telefone2')} ci-tel2" value="${escHtml(c.telefone2 || '')}" /></td>
                        <td>
                            <span class="badge badge-xs ${statusClasses[c.status] || ''}"
                                title="${escHtml(tooltipTitle)}"
                                style="cursor:${tooltipTitle ? 'help' : 'default'}"
                            >${statusLabels[c.status] || c.status}</span>
                        </td>
                        <td>
                            <select class="select select-bordered select-xs w-full ci-acao"
                                data-status="${c.status}"
                                data-id="${c.id_contato_existente || ''}">
                                ${c.status !== 'incompleto' ? `<option value="criar" ${defaultAcao === 'criar' ? 'selected' : ''}>Criar</option>` : ''}
                                ${c.status === 'existe' ? `<option value="atualizar" ${defaultAcao === 'atualizar' ? 'selected' : ''}>Atualizar</option>` : ''}
                                <option value="ignorar" ${defaultAcao === 'ignorar' ? 'selected' : ''}>Ignorar</option>
                            </select>
                        </td>`;

                    tbody.appendChild(tr);
                });

                // Attach validation watcher
                tbody.addEventListener('input', () => ciValidarTabela());
                ciValidarTabela();
            }

            function escHtml(str) {
                return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            }

            // Enable/disable "Confirmar" based on whether all active rows have nome + valid email
            function ciValidarTabela() {
                const btn = $('#ci-btn-confirmar');
                if (!btn) return;
                const rows = document.querySelectorAll('#ci-preview-tbody tr');
                let ok = rows.length > 0;
                rows.forEach(tr => {
                    const acao = tr.querySelector('.ci-acao')?.value;
                    if (acao === 'ignorar') return;
                    const nome = tr.querySelector('.ci-nome')?.value.trim();
                    const email = tr.querySelector('.ci-email')?.value.trim();
                    if (!nome || !email || !email.includes('@')) ok = false;
                });
                btn.disabled = !ok;
            }

            // Open modal: reset to step 1
            $('#btn-contato-import')?.addEventListener('click', () => {
                if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
                $('#ci-texto').value = '';
                ciHideErroIA();
                ciGoToStep1();
                $('#modal-contato-import').showModal();
            });

            // "Organizar com IA"
            $('#ci-btn-ia')?.addEventListener('click', async () => {
                const texto = ($('#ci-texto').value || '').trim();
                if (!texto) { showToast('Cole algum texto primeiro.', 'warning'); return; }
                ciHideErroIA();

                if (detectaFormatoSimples(texto)) {
                    // Structured text — skip AI, parse locally
                    const contatos = parseFormatoSimples(texto);
                    await ciVerificarEExibir(contatos);
                } else {
                    ciSetLoading(true, 'Organizando com IA…');
                    try {
                        const r = await api('/api/ia/extrair-contatos', {
                            method: 'POST',
                            body: JSON.stringify({ texto })
                        });
                        ciSetLoading(false);
                        if (!r.contatos || r.contatos.length === 0) {
                            ciShowErroIA('A IA não encontrou contatos no texto. Verifique o conteúdo ou use o formato simples.');
                            return;
                        }
                        await ciVerificarEExibir(r.contatos);
                    } catch (e) {
                        ciSetLoading(false);
                        ciShowErroIA(e.message || 'Falha na chamada à IA. Tente novamente ou use o formato simples.');
                    }
                }
            });

            // "Usar formato simples"
            $('#ci-btn-simples')?.addEventListener('click', async () => {
                const texto = ($('#ci-texto').value || '').trim();
                if (!texto) { showToast('Cole algum texto primeiro.', 'warning'); return; }
                ciHideErroIA();
                const contatos = parseFormatoSimples(texto);
                if (!contatos.length) { showToast('Nenhuma linha encontrada.', 'warning'); return; }
                await ciVerificarEExibir(contatos);
            });

            // "Tentar novamente" (in error banner)
            $('#ci-btn-retry')?.addEventListener('click', () => {
                ciHideErroIA();
                $('#ci-btn-ia')?.click();
            });

            // "Voltar" from step 2
            $('#ci-btn-voltar')?.addEventListener('click', () => {
                ciGoToStep1();
            });

            // "Confirmar importação"
            $('#ci-btn-confirmar')?.addEventListener('click', async () => {
                const btn = $('#ci-btn-confirmar');
                btn.classList.add('loading');
                btn.disabled = true;

                const rows = document.querySelectorAll('#ci-preview-tbody tr');
                const contatos = [];
                rows.forEach(tr => {
                    const acao = tr.querySelector('.ci-acao')?.value || 'ignorar';
                    const idExistente = tr.querySelector('.ci-acao')?.dataset.id || null;
                    contatos.push({
                        nome: tr.querySelector('.ci-nome')?.value.trim() || '',
                        email: tr.querySelector('.ci-email')?.value.trim().toLowerCase() || '',
                        telefone: tr.querySelector('.ci-tel')?.value.trim() || '',
                        telefone2: tr.querySelector('.ci-tel2')?.value.trim() || '',
                        acao,
                        id_contato_existente: idExistente ? parseInt(idExistente, 10) : null,
                    });
                });

                try {
                    const r = await api(`/api/cliente/${clienteSelecionadoId}/contatos/importar-confirmado`, {
                        method: 'POST',
                        body: JSON.stringify({ contatos })
                    });

                    const partes = [];
                    if (r.criados) partes.push(`${r.criados} criado(s)`);
                    if (r.atualizados) partes.push(`${r.atualizados} atualizado(s)`);
                    if (r.ignorados) partes.push(`${r.ignorados} ignorado(s)`);
                    const resumo = partes.join(', ') || 'Nenhuma alteração';

                    const resultEl = $('#ci-result');
                    resultEl.className = `mt-2 alert text-xs p-2 ${r.erros && r.erros.length ? 'alert-warning' : 'alert-success'}`;
                    let texto = resumo;
                    if (r.erros && r.erros.length) {
                        texto += '\nErros:\n' + r.erros.map(e => `• Linha ${e.linha}: ${e.msg}`).join('\n');
                    }
                    resultEl.textContent = texto;
                    resultEl.classList.remove('hidden');

                    const tipo = (r.erros && r.erros.length) ? 'warning' : 'success';
                    showToast(resumo + '.', tipo);
                    carregarContatos(clienteSelecionadoId);
                } catch (e) {
                    showToast(e.message || 'Erro ao importar.', 'error');
                } finally {
                    btn.classList.remove('loading');
                    ciValidarTabela();
                }
            });

        })(); // end setupImportContatos

        if ($('#filtro-executivo')) carregarClientes();
    });
})();
