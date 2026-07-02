(function () {
    'use strict';

    const BASE = '/sales-war-room';
    let clienteSelecionadoId = null;
    let contatoSelecionadoId = null;
    let modalContatoId = null;
    let modalClienteId = null;
    let chartInstances = {};
    let swrCliCache = [];
    let swrContatosCache = [];
    let swrCliPage = 0;
    const SWR_CLI_PAGE_SIZE = 12;


    // ==================== Helpers ====================

    function $(sel, ctx) { return (ctx || document).querySelector(sel); }
    function $$(sel, ctx) { return [...(ctx || document).querySelectorAll(sel)]; }

    function showSpinner(container) {
        container.innerHTML = '<div class="flex justify-center py-8"><span class="loading loading-spinner loading-md"></span></div>';
    }

    function showEmpty(container, msg) {
        container.innerHTML = `<div class="swr-empty-state">${msg}</div>`;
    }

    async function api(path, opts = {}) {
        const resp = await fetch(BASE + path, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
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

    function atualizarContadoresCarteira(clientes, perfil) {
        const wrap = $('#swr-contador-carteira');
        const chipA = $('#swr-chip-ag');
        const chipC = $('#swr-chip-cli');
        const letraA = $('#swr-letra-a');
        const letraC = $('#swr-letra-c');
        const elA = $('#swr-n-agencias');
        const elC = $('#swr-n-clientes');
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
        const wrap = $('#swr-contador-carteira');
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
            swrCliCache = data.clientes || [];
            swrCliPage = 0;
            atualizarContadoresCarteira(swrCliCache, perfil);
            if (!swrCliCache.length) {
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
        $('#swr-clientes-paginacao')?.classList.add('hidden');
        $('#swr-contador-total')?.classList.add('hidden');
    }

    function renderClientesPagina() {
        const container = $('#lista-clientes');
        const total = swrCliCache.length;

        const order = ['Prospecção', 'Ativo', 'Geladeira'];
        const labelFor = (c) => {
            const v = (c.classificacao_cliente || '').trim();
            return order.includes(v) ? v : 'Sem classificação';
        };
        const nomeFor = (c) => (c.nome_fantasia || c.razao_social || '').trim();
        const grupos = new Map();
        for (const c of swrCliCache) {
            const label = labelFor(c);
            if (!grupos.has(label)) grupos.set(label, []);
            grupos.get(label).push(c);
        }
        for (const lista of grupos.values()) {
            lista.sort((a, b) => nomeFor(a).localeCompare(nomeFor(b), 'pt-BR', { sensitivity: 'base' }));
        }

        const labels = order.concat([...grupos.keys()].filter(k => !order.includes(k)).sort((a, b) => a.localeCompare(b, 'pt-BR')));
        const cardHtml = (c) => `
            <div class="swr-card ${c.id_cliente == clienteSelecionadoId ? 'swr-card-active' : ''}"
                 data-id="${c.id_cliente}">
                <div class="flex items-center justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="swr-cliente-nome truncate">${nomeFor(c).toUpperCase()}</div>
                        <div class="swr-cliente-subtitulo">${clienteEhAgencia(c) ? 'Agência' : 'Cliente final'} · ${c.qtd_contatos} contato(s)</div>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                        <button type="button" class="swr-cliente-edit btn btn-ghost btn-xs btn-square h-5 w-5 min-h-0 p-0" data-id="${c.id_cliente}" title="Editar cliente" aria-label="Editar cliente">
                            ${ICON_EDIT}
                        </button>
                    </div>
                </div>
            </div>`;

        container.innerHTML = labels.map(label => {
            const lista = grupos.get(label) || [];
            if (!lista.length) return '';
            const detailsOpen = label === 'Prospecção' || label === 'Ativo' || label === 'Geladeira';
            return `
                <details class="swr-classificacao-grupo" ${detailsOpen ? 'open' : ''} data-classificacao="${escapeHtml(label)}">
                    <summary class="swr-classificacao-header">
                        <span class="swr-classificacao-titulo">${escapeHtml(label)}</span>
                        <span class="swr-classificacao-count">${lista.length}</span>
                    </summary>
                    <div class="swr-classificacao-lista">
                        ${lista.map(cardHtml).join('')}
                    </div>
                </details>
            `;
        }).join('');

        $$('.swr-card', container).forEach(el => {
            el.addEventListener('click', () => selecionarCliente(parseInt(el.dataset.id)));
        });

        $$('.swr-cliente-edit', container).forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                abrirModalEditarCliente(parseInt(btn.dataset.id, 10));
            });
        });

        const footer = $('#swr-clientes-paginacao');
        const totalEl = $('#swr-contador-total');
        if (totalEl) {
            totalEl.textContent = total;
            totalEl.classList.remove('hidden');
        }
        if (footer) footer.classList.add('hidden');
    }

    function selecionarCliente(id) {
        clienteSelecionadoId = id;
        contatoSelecionadoId = null;

        $$('.swr-card', $('#lista-clientes')).forEach(el => {
            el.classList.toggle('swr-card-active', parseInt(el.dataset.id) === id);
        });
        atualizarResumoObjetivosComunicacao();

        setTabAtividades('todas');
        carregarStatus(id);
        carregarContatos(id);
        if ($('#lista-atividades')) carregarAtividades(id);
        carregarObjetivos(id);
        carregarCotacoesAbertas(id);
    }

    function limparColunas() {
        clienteSelecionadoId = null;
        contatoSelecionadoId = null;
        swrContatosCache = [];
        showEmpty($('#area-status'), 'Selecione um cliente.');
        showEmpty($('#lista-contatos'), 'Selecione um cliente.');
        if ($('#lista-atividades')) showEmpty($('#lista-atividades'), 'Selecione um cliente.');
        if ($('#lista-objetivos')) showEmpty($('#lista-objetivos'), 'Selecione um cliente.');
        atualizarResumoObjetivosComunicacao();
        showEmpty($('#lista-cotacoes'), 'Selecione um cliente.');
        const count = $('#swr-cotacoes-count');
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
        const cls = s === 'Enviada' ? 'swr-cot-status-enviada' : (s === 'Em Análise' ? 'swr-cot-status-analise' : 'swr-cot-status-rascunho');
        return `<span class="swr-cot-status ${cls}">${escapeHtml(s)}</span>`;
    }

    function renderCotacoesAbertas(cotacoes) {
        const container = $('#lista-cotacoes');
        const count = $('#swr-cotacoes-count');
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
                <a class="swr-cot-card" href="/cotacoes/${c.id}/detalhes">
                    <div class="swr-cot-top">
                        <span class="swr-cot-numero">${escapeHtml(titulo)}</span>
                        ${badgeStatusCotacao(c.status)}
                    </div>
                    <div class="swr-cot-campanha">${escapeHtml(campanha)}</div>
                    <div class="swr-cot-meta">
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
        const cls = pct === 0 ? '' : (bom ? 'swr-metric-delta-up' : 'swr-metric-delta-down');
        const arrow = pct === 0 ? '' : (positivo ? '↑' : '↓');
        return { html: `${arrow} ${Math.abs(pct)}% vs mês ant.`, cls };
    }

    function metricCard(valor, label, deltaPct, lowerIsBetter = false, isCurrency = false) {
        const delta = deltaText(deltaPct, lowerIsBetter);
        return `
            <div class="swr-metric-card">
                <span class="swr-metric-valor${isCurrency ? ' swr-metric-currency' : ''}">${valor}</span>
                ${delta.html ? `<span class="swr-metric-delta ${delta.cls}">${delta.html}</span>` : ''}
                <div class="swr-metric-label">${label}</div>
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
            const clienteData = swrCliCache.find(c => c.id_cliente === clienteId) || {};
            const nomeCliente = clienteData.nome_fantasia || clienteData.razao_social || 'Cliente';
            const tipoCliente = clienteData.eh_agencia ? 'Agência' : 'Cliente final';
            const categoria = s.tipo_mercado || 'Privado';
            const prioridade = s.prioridade || 'Alta';
            const inicial = nomeCliente.charAt(0).toUpperCase();
            const agora = new Date().toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' });

            container.innerHTML = `
                <div class="swr-status-section">
                    <!-- Header do cliente -->
                    <div class="swr-status-cliente-header">
                        <div class="swr-status-avatar-verde">${inicial}</div>
                        <div class="swr-status-cliente-info">
                            <div class="swr-status-cliente-nome">${escapeHtml(nomeCliente).toUpperCase()}</div>
                            <div class="swr-status-cliente-tipo">${tipoCliente}</div>
                        </div>
                        <span class="swr-badge-prioridade-alta">Prioridade: ${prioridade}</span>
                    </div>

                    <!-- Info contatos -->
                    <div class="swr-status-info-row">
                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <span class="swr-status-info-text">${s.total_contatos || 0} contato(s)</span>
                    </div>

                    <!-- Responsável e Categoria -->
                    <div class="swr-status-details">
                        <div class="swr-status-detail-row">
                            <span class="swr-status-detail-label">Responsável</span>
                            <span class="swr-status-detail-value">
                                ${s.executivo_nome || '-'}
                                <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                            </span>
                        </div>
                        <div class="swr-status-detail-row">
                            <span class="swr-status-detail-label">Categoria</span>
                            <span class="swr-status-detail-value">
                                ${categoria}
                                <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
                            </span>
                        </div>
                    </div>

                    <!-- Grid de métricas 3x2 -->
                    <div class="swr-metrics-grid">
                        ${metricCardNew('Contatos', s.total_contatos || 0, s.total_contatos_delta_pct, false)}
                        ${metricCardNew('Aprovações', s.cotacoes_aprovadas || 0, s.cotacoes_aprovadas_delta_pct, false)}
                        ${metricCardNew('Faturamento', fmtBRL(s.valor_bruto || 0), s.valor_bruto_delta_pct, false)}
                        ${metricCardNew('Erros', s.erros || 0, s.erros_delta_pct, true)}
                        ${metricCardNew('Líquido', fmtBRL(s.valor_liquido || 0), s.valor_liquido_delta_pct, false)}
                        ${metricCardNew('Valor PIs', fmtBRL(s.valor_pis || 0), s.valor_pis_delta_pct, false)}
                    </div>

                    <!-- Última atualização -->
                    <div class="swr-ultima-atualizacao-row">
                        <span>Última atualização</span>
                        <span>Hoje, ${agora}</span>
                    </div>

                    <!-- Próximo passo sugerido -->
                    <div class="swr-proximo-passo-section">
                        <div class="swr-proximo-passo-titulo">Próximo passo sugerido</div>
                        <div class="swr-proximo-passo-card">
                            <div class="swr-proximo-passo-icon-circle">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                            </div>
                            <div class="swr-proximo-passo-content-text">
                                <div class="swr-proximo-passo-main">${escapeHtml(proximoPassoStatus(s))}</div>
                                <div class="swr-proximo-passo-sub">Prazo sugerido: Hoje</div>
                            </div>
                            <svg class="w-4 h-4 text-yellow-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                        </div>
                    </div>

                    <!-- Nota sobre o cliente -->
                    <div class="swr-nota-cliente-section">
                        <div class="swr-nota-cliente-header">
                            <span class="swr-nota-cliente-titulo">Nota sobre o cliente</span>
                            <button type="button" class="swr-nota-menu-btn">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/></svg>
                            </button>
                        </div>
                        <div class="swr-nota-cliente-box">
                            <textarea id="swr-nota-cliente" class="swr-nota-textarea" maxlength="8000" placeholder="Anotações visíveis para a equipe comercial..."></textarea>
                        </div>
                        <div class="swr-nota-autor-info">
                            <div class="swr-nota-autor-avatar">JF</div>
                            <div class="swr-nota-autor-details">
                                <div class="swr-nota-autor-nome">Nota realizada por ${s.executivo_nome || 'Usuário'}</div>
                                <div class="swr-nota-autor-data">Hoje, ${agora}</div>
                            </div>
                        </div>
                        <button type="button" class="swr-ver-historico-link" id="swr-ver-historico-notas">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                            Ver histórico de notas
                        </button>
                    </div>

                    <!-- Botões de ação -->
                    <div class="swr-status-action-buttons">
                        <button type="button" class="swr-btn-outline" id="btn-ver-mais-status">Ver mais dados</button>
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
            deltaHtml = `<div class="swr-metric-delta-new ${colorClass}">${sign}${deltaPct}%</div>`;
        }
        return `
            <div class="swr-metric-card-new">
                <div class="swr-metric-label-new">${label}</div>
                <div class="swr-metric-value-new">${valor}</div>
                ${deltaHtml}
                <div class="swr-metric-sublabel-new">vs mês ant.</div>
            </div>`;
    }

    async function carregarNotaCliente(clienteId) {
        const ta = $('#swr-nota-cliente');
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
            const ta = $('#swr-nota-cliente');
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
            swrContatosCache = data.contatos || [];
            popularComunicacaoContatos(swrContatosCache);
            const totalContatos = swrContatosCache.length;
            if (!totalContatos) {
                showEmpty(container, 'Nenhum contato cadastrado.');
                return;
            }

            const contatosVisiveis = swrContatosCache.slice(0, 5);
            container.innerHTML = contatosVisiveis.map((c, idx) => {
                const tel = (c.telefone || '').replace(/\D/g, '');
                const telFormatado = c.telefone || '';
                const ehPrincipal = idx === 0 || c.principal;
                const ultimoContato = c.ultima_atividade_data ? formatDateContato(c.ultima_atividade_data) : null;
                return `
                    <div class="swr-contato-card ${c.id_contato_cliente == contatoSelecionadoId ? 'swr-contato-card-active' : ''}"
                         data-id="${c.id_contato_cliente}">
                        <div class="swr-contato-card-header">
                            <div class="swr-contato-card-info">
                                <div class="swr-contato-nome-row">
                                    <button type="button" class="swr-contato-nome-btn swr-contato-nome-modal" data-contato-id="${c.id_contato_cliente}">${escapeHtml(c.nome_completo)}</button>
                                    ${ehPrincipal ? '<span class="swr-badge-principal-new">Principal</span>' : ''}
                                </div>
                                <div class="swr-contato-subtitulo">${escapeHtml(c.cargo || '')}</div>
                                ${c.email ? `<div class="swr-contato-email">${escapeHtml(c.email)}</div>` : ''}
                                ${telFormatado ? `<div class="swr-contato-telefone">${escapeHtml(telFormatado)}</div>` : ''}
                            </div>
                            <div class="swr-contato-card-right">
                                <div class="swr-contato-acoes-new">
                                    <button type="button" class="swr-contato-icon swr-contato-objetivo-btn" data-contato-id="${c.id_contato_cliente}" title="Objetivos e comunicação" aria-label="Objetivos e comunicação">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 12l2 2 4-4"/></svg>
                                    </button>
                                    ${tel ? `<a href="https://wa.me/55${tel}" target="_blank" class="swr-contato-icon swr-contato-icon-whatsapp" title="WhatsApp"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg></a>` : ''}
                                    ${tel ? `<a href="tel:+55${tel}" class="swr-contato-icon" title="Ligar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg></a>` : ''}
                                    ${c.email ? `<a href="mailto:${c.email}" class="swr-contato-icon" title="E-mail"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg></a>` : ''}
                                </div>
                                ${ultimoContato ? `<div class="swr-contato-ultimo">Último contato<br><span class="swr-contato-ultimo-data">${ultimoContato}</span></div>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            if (totalContatos > 5) {
                container.innerHTML += `<div class="swr-link-ver-todos" id="swr-ver-todos-contatos">Ver todos os contatos (${totalContatos}) &gt;</div>`;
            }

            $('#swr-ver-todos-contatos')?.addEventListener('click', () => {
                window.location.href = `/clientes?open=${clienteId}&tab=contatos`;
            });

            $$('.swr-contato-card', container).forEach(el => {
                el.addEventListener('click', () => {
                    const id = parseInt(el.dataset.id);
                    contatoSelecionadoId = id;
                    $$('.swr-contato-card', container).forEach(e => e.classList.remove('swr-contato-card-active'));
                    el.classList.add('swr-contato-card-active');
                    setTabAtividades('contato');
                    carregarAtividades(clienteSelecionadoId, id);
                    atualizarResumoObjetivosComunicacao();
                });
            });

            $$('.swr-contato-objetivo-btn', container).forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const id = parseInt(btn.dataset.contatoId, 10);
                    contatoSelecionadoId = id;
                    $$('.swr-contato-card', container).forEach(e => {
                        e.classList.toggle('swr-contato-card-active', parseInt(e.dataset.id, 10) === id);
                    });
                    setTabAtividades('contato');
                    carregarAtividades(clienteSelecionadoId, id);
                    focarObjetivosComunicacao('gerar', '#input-objetivo');
                });
            });

            $$('.swr-contato-nome-modal', container).forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    abrirModalContato(parseInt(btn.dataset.contatoId, 10));
                });
            });
        } catch (e) {
            showEmpty(container, 'Erro ao carregar contatos.');
            console.error(e);
        }
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
        $$('#tabs-atividades .swr-tab-ativ').forEach(t => {
            t.classList.toggle('swr-tab-ativ-active', t.dataset.tab === tab);
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

    let swrActCtx = { clienteId: null, contatoId: null };
    let swrObjCtx = { clienteId: null };
    let swrActCache = [];
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

    function badgePrioridadeAtiv(prioridade) {
        const p = (prioridade || 'media').toLowerCase();
        const config = {
            alta: { label: 'A alta', color: '#ef4444', bg: '#fef2f2' },
            media: { label: 'Média', color: '#eab308', bg: '#fefce8' },
            baixa: { label: 'Baixa', color: '#22c55e', bg: '#f0fdf4' }
        };
        const c = config[p] || config.media;
        return `<span class="swr-badge-prioridade-ativ" style="background:${c.bg};color:${c.color}"><span class="swr-badge-dot" style="background:${c.color}"></span>${c.label}</span>`;
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
            <div class="swr-ativ-card ${vencida ? 'swr-ativ-vencida' : ''}" data-aid="${a.id}">
                <div class="swr-ativ-card-left">
                    ${podeFeito ? `<input type="checkbox" class="swr-ativ-checkbox swr-act-feito" data-id="${a.id}" />` : '<span class="swr-ativ-checkbox-space"></span>'}
                    <span class="swr-ativ-tipo-dot swr-tipo-dot-${tipo}"></span>
                </div>
                <div class="swr-ativ-card-main">
                    <div class="swr-ativ-titulo">${escapeHtml(a.titulo || a.descricao || '—')}</div>
                    <div class="swr-ativ-subtipo">${tipoLabel}</div>
                </div>
                <div class="swr-ativ-card-right">
                    <div class="swr-ativ-contato">${a.contato_nome ? escapeHtml(a.contato_nome) : ''}</div>
                    <div class="swr-ativ-data">${dataFormatada}</div>
                </div>
                <div class="swr-ativ-card-badge">
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
        const lista = swrActCache;
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
        swrActCtx = { clienteId, contatoId };
        const container = $('#lista-atividades');
        if (!container) return;
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/atividades`);
            swrActCache = data.atividades || [];
            renderAtividades();
        } catch (e) {
            showEmpty(container, 'Erro ao carregar atividades.');
            console.error(e);
        }
    }

    function renderAtividades() {
        const container = $('#lista-atividades');
        if (!container) return;
        const clienteId = swrActCtx.clienteId;
        const contatoId = swrActCtx.contatoId;
        const lista = swrActCache;
        const filtrada = filtrarAtividadesPorAba();

        const mostraConcluidas = (atividadesTab === 'todas' || atividadesTab === 'contato' || atividadesTab === 'concluidas');
        const ativas = sortAtividadesPorPrazoAtivas(filtrada.filter(a => a.status !== 'concluida'));
        const concluidas = mostraConcluidas
            ? sortAtividadesConcluidasPorData(filtrada.filter(a => a.status === 'concluida'))
            : [];

        let html = '';

        if (atividadesTab === 'contato' && !contatoSelecionadoId) {
            html += `<div class="swr-ativ-vazio">Selecione um contato na coluna ao lado.</div>`;
        } else if (atividadesTab === 'concluidas') {
            html += concluidas.length
                ? `<div class="swr-ativ-lista">${concluidas.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`
                : `<div class="swr-ativ-vazio">Nenhuma atividade concluída.</div>`;
        } else {
            if (ativas.length) {
                const visiveis = ativas.slice(0, 8);
                html += `<div class="swr-ativ-lista">${visiveis.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
                if (ativas.length > 8) {
                    html += `<div class="swr-link-ver-mais" id="swr-ver-mais-atividades">+ Ver mais atividades</div>`;
                }
            } else {
                const vazio = atividadesTab === 'hoje' ? 'Nenhuma atividade para hoje.' : 'Nenhuma atividade pendente.';
                html += `<div class="swr-ativ-vazio">${vazio}</div>`;
            }
            if (concluidas.length && atividadesTab !== 'pendentes') {
                html += `<div class="swr-ativ-divider">Concluídas</div>`;
                html += `<div class="swr-ativ-lista swr-ativ-lista-done">${concluidas.slice(0, 3).map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
            }
        }

        {
            const hoje = new Date().toISOString().slice(0, 10);
            html += `
                <div class="swr-ativ-form-titulo">Nova atividade</div>
                <div class="swr-ativ-form">
                    <div class="swr-ativ-form-row">
                        <label class="swr-ativ-label">Título da atividade*</label>
                        <input type="text" id="input-atividade-titulo" class="swr-ativ-input" placeholder="Digite o título..." />
                    </div>
                    <div class="swr-ativ-form-row">
                        <label class="swr-ativ-label">Descrição</label>
                        <textarea id="input-atividade" class="swr-ativ-textarea" rows="2" placeholder="Descrição (opcional)..."></textarea>
                    </div>
                    <div class="swr-ativ-form-grid3">
                        <div>
                            <label class="swr-ativ-label">Tipo</label>
                            <select id="input-atividade-tipo" class="swr-ativ-select">
                                <option value="atividade">Atividade</option>
                                <option value="ligacao">Ligação</option>
                                <option value="almoco">Almoço</option>
                                <option value="reuniao">Reunião</option>
                                <option value="projeto">Projeto</option>
                            </select>
                        </div>
                        <div>
                            <label class="swr-ativ-label">Data</label>
                            <input type="date" id="input-atividade-data" class="swr-ativ-input" value="${hoje}" />
                        </div>
                        <div>
                            <label class="swr-ativ-label">Prazo</label>
                            <input type="date" id="input-atividade-prazo" class="swr-ativ-input" />
                        </div>
                    </div>
                    <div class="swr-ativ-form-grid3">
                        <div>
                            <label class="swr-ativ-label">Responsável</label>
                            <select id="input-atividade-responsavel" class="swr-ativ-select">
                                <option value="">Selecionar...</option>
                            </select>
                        </div>
                        <div>
                            <label class="swr-ativ-label">Objetivo vinculado</label>
                            <select id="input-atividade-objetivo" class="swr-ativ-select">
                                <option value="">Nenhum</option>
                            </select>
                        </div>
                        <div>
                            <label class="swr-ativ-label">Prioridade</label>
                            <select id="input-atividade-prioridade" class="swr-ativ-select">
                                <option value="media">● Média</option>
                                <option value="alta">● Alta</option>
                                <option value="baixa">● Baixa</option>
                            </select>
                        </div>
                    </div>
                    <button type="button" class="swr-ativ-btn-criar" id="btn-add-atividade">Criar atividade</button>
                    <div class="swr-ativ-ia-section">
                        <div class="swr-ativ-ia-titulo">Ações com IA</div>
                        <div class="swr-ativ-ia-btns">
                            <button type="button" class="swr-ativ-ia-btn" id="btn-sugerir-atividade">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                                Sugerir
                            </button>
                            <button type="button" class="swr-ativ-ia-btn" id="btn-add-atividade-ia">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                                Melhorar
                            </button>
                            <button type="button" class="swr-ativ-ia-btn" id="btn-gerar-followup">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                                Follow-up
                            </button>
                        </div>
                    </div>
                </div>
            `;

            container.innerHTML = html;

            $$('.swr-act-feito', container).forEach(cb => {
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

            $$('.swr-act-edit', container).forEach(btn => {
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

            $$('.swr-act-del', container).forEach(btn => {
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
        swrObjCtx.clienteId = clienteId;
        const container = $('#lista-objetivos');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/objetivos`);
            const ativos = data.objetivos.filter(o => !o.conquistado);
            const conquistados = data.objetivos.filter(o => o.conquistado);
            const totalObjetivos = data.objetivos.length;
            const hojePrazo = new Date().toISOString().slice(0, 10);
            const maxVisiveis = 5;

            let html = `
                <div class="swr-obj-header">
                    <span class="swr-obj-titulo">Objetivos</span>
                    <button type="button" class="swr-obj-btn-novo" id="btn-toggle-form-obj">+ Novo objetivo</button>
                </div>
                <div class="swr-obj-input-row">
                    <input type="text" id="input-objetivo" class="swr-obj-input" placeholder="Novo objetivo..." />
                    <input type="date" id="input-objetivo-prazo" class="swr-obj-input-data" value="${hojePrazo}" />
                    <button type="button" class="swr-obj-btn-add" id="btn-add-objetivo">+</button>
                </div>
                <div id="ia-sugestoes" class="hidden"></div>
            `;

            const ativosVisiveis = ativos.slice(0, maxVisiveis);
            if (ativosVisiveis.length) {
                html += `<div class="swr-obj-lista">`;
                html += ativosVisiveis.map(o => `
                    <div class="swr-obj-item swr-fade-in" data-id="${o.id}">
                        <input type="checkbox" class="swr-obj-checkbox swr-obj-check" data-id="${o.id}" />
                        <div class="swr-obj-content">
                            <div class="swr-obj-texto">${escapeHtml(o.texto)}</div>
                            <div class="swr-obj-meta">
                                ${o.data_prazo ? `<span class="swr-obj-data">${fmtDateShort(o.data_prazo)}</span>` : ''}
                                <span class="swr-badge-status-obj swr-badge-ativo">Ativo</span>
                            </div>
                        </div>
                        <div class="swr-obj-acoes">
                            <button type="button" class="swr-obj-acao-btn swr-obj-edit" data-id="${o.id}" title="Editar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>
                            <button type="button" class="swr-obj-acao-btn swr-obj-del" data-id="${o.id}" title="Excluir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>
                        </div>
                    </div>
                `).join('');
                html += `</div>`;
            }

            const conquistadosVisiveis = conquistados.slice(0, Math.max(0, maxVisiveis - ativosVisiveis.length));
            if (conquistadosVisiveis.length) {
                html += `<div class="swr-obj-lista" style="opacity:0.6">`;
                html += conquistadosVisiveis.map(o => `
                    <div class="swr-obj-item swr-fade-in swr-obj-conquistado" data-id="${o.id}">
                        <input type="checkbox" class="swr-obj-checkbox swr-obj-check" data-id="${o.id}" checked />
                        <div class="swr-obj-content">
                            <div class="swr-obj-texto" style="text-decoration:line-through">${escapeHtml(o.texto)}</div>
                            <div class="swr-obj-meta">
                                ${o.data_conquista ? `<span class="swr-obj-data">${fmtDateShort(o.data_conquista)}</span>` : ''}
                                <span class="swr-badge-status-obj swr-badge-pendente">Concluído</span>
                            </div>
                        </div>
                        <div class="swr-obj-acoes">
                            <button type="button" class="swr-obj-acao-btn swr-obj-edit" data-id="${o.id}" title="Editar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>
                            <button type="button" class="swr-obj-acao-btn swr-obj-del" data-id="${o.id}" title="Excluir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>
                        </div>
                    </div>
                `).join('');
                html += `</div>`;
            }

            if (!ativos.length && !conquistados.length) {
                html += '<div class="swr-ativ-vazio">Nenhum objetivo cadastrado.</div>';
            }

            if (totalObjetivos > maxVisiveis) {
                html += `<div class="swr-obj-ver-todos" id="swr-ver-todos-objetivos">Ver todos os objetivos</div>`;
            }

            container.innerHTML = html;

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

            $$('.swr-obj-check', container).forEach(cb => {
                cb.addEventListener('change', async () => {
                    try {
                        await api(`/api/objetivos/${cb.dataset.id}/conquistar`, {
                            method: 'PATCH',
                            body: JSON.stringify({ conquistado: cb.checked })
                        });
                        const card = cb.closest('.swr-fade-in');
                        if (cb.checked && card) {
                            card.classList.add('swr-obj-conquistado-anim');
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
            $$('.swr-obj-edit', container).forEach(btn => {
                btn.addEventListener('click', () => {
                    const o = olist.find(x => String(x.id) === btn.dataset.id);
                    if (!o) return;
                    $('#eo-id').value = o.id;
                    $('#eo-texto').value = o.texto || '';
                    $('#eo-prazo').value = _isoDateOnly(o.data_prazo);
                    $('#modal-editar-objetivo').showModal();
                });
            });

            $$('.swr-obj-del', container).forEach(btn => {
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

            $('#swr-ver-todos-objetivos')?.addEventListener('click', () => {
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
                            <input type="checkbox" class="checkbox checkbox-xs swr-sug-check" data-texto="${o.replace(/"/g, '&quot;')}" checked />
                            <span class="text-xs">${o}</span>
                        </label>
                    `).join('')}
                    <button class="btn btn-xs btn-success w-full mt-1" id="btn-aceitar-sugestoes">Adicionar selecionados</button>
                `;

                $('#btn-aceitar-sugestoes')?.addEventListener('click', async () => {
                    const selecionados = $$('.swr-sug-check:checked', sugestoesDiv).map(cb => cb.dataset.texto);
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

            const tel = (c.telefone || '').replace(/\D/g, '');
            $('#contato-info').innerHTML = `
                <div><span class="text-xs opacity-60">Nome</span><div class="text-sm">${c.nome_completo}</div></div>
                <div><span class="text-xs opacity-60">Cargo</span><div class="text-sm">${c.cargo || '-'}</div></div>
                <div>
                    <span class="text-xs opacity-60">Telefone</span>
                    <div class="flex items-center gap-1">
                        <span class="text-sm">${c.telefone || '-'}</span>
                        ${c.telefone ? `<button class="swr-copy-btn" data-copy="${c.telefone}" title="Copiar telefone"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button>` : ''}
                        ${tel ? `<a href="https://wa.me/55${tel}" target="_blank" class="swr-copy-btn" title="WhatsApp"><svg class="w-3.5 h-3.5 text-success" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2z"/></svg></a>` : ''}
                    </div>
                </div>
                <div>
                    <span class="text-xs opacity-60">Email</span>
                    <div class="flex items-center gap-1">
                        <span class="text-sm">${c.email || '-'}</span>
                        ${c.email ? `<button class="swr-copy-btn" data-copy="${c.email}" title="Copiar email"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button>` : ''}
                        ${c.email ? `<a href="mailto:${c.email}" class="swr-copy-btn" title="Enviar email"><svg class="w-3.5 h-3.5 text-info" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg></a>` : ''}
                    </div>
                </div>
                <div class="col-span-2"><span class="text-xs opacity-60">Cliente</span><div class="text-sm">${c.cliente_nome || '-'}</div></div>
            `;

            $$('.swr-copy-btn[data-copy]', $('#contato-info')).forEach(btn => {
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
        $$('[data-modal-tab]').forEach(t => t.classList.toggle('tab-active', t.dataset.modalTab === 'dados'));
    }

    function showTabComunicacao() {
        $('#tab-dados').classList.add('hidden');
        $('#tab-comunicacao').classList.remove('hidden');
        $$('[data-modal-tab]').forEach(t => t.classList.toggle('tab-active', t.dataset.modalTab === 'comunicacao'));
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
        const sel = $('#swrc-contato');
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
        return swrContatosCache.find(c => String(c.id_contato_cliente) === String(contatoSelecionadoId)) || null;
    }

    function atualizarResumoObjetivosComunicacao() {
        const contato = contatoSelecionadoAtual();
        const resumo = $('#swr-oc-contato-resumo');
        const card = $('#swr-oc-contato-card');
        if (!resumo || !card) return;
        if (!contato) {
            resumo.textContent = 'Selecione um contato.';
            card.innerHTML = '';
            card.classList.add('hidden');
            return;
        }
        const tel = contato.telefone || '';
        resumo.textContent = contato.nome_completo || 'Contato selecionado';
        card.classList.remove('hidden');
        card.innerHTML = `
            <div class="swr-oc-contato-nome">${escapeHtml(contato.nome_completo || 'Contato selecionado')}</div>
            <div class="swr-oc-contato-meta">
                ${contato.cargo ? `<span>${escapeHtml(contato.cargo)}</span>` : ''}
                ${contato.email ? `<span>${escapeHtml(contato.email)}</span>` : ''}
                ${tel ? `<span>${escapeHtml(tel)}</span>` : ''}
            </div>
        `;
    }

    function focarObjetivosComunicacao(tab = 'gerar', focusSel = null) {
        if (!clienteSelecionadoId) {
            showToast('Selecione um cliente.', 'warning');
            return;
        }
        if (!contatoSelecionadoId) {
            showToast('Selecione um contato.', 'warning');
            return;
        }
        atualizarResumoObjetivosComunicacao();
        setTabComunicacao(tab);
        carregarObjetivos(clienteSelecionadoId);
        const col = $('#col-objetivos-comunicacao');
        if (col) scrollIntoViewSuave(col);
        if (focusSel) setTimeout(() => $(focusSel)?.focus(), 150);
    }

    function gerarComunicacaoSecao() {
        const objSel = $('#swrc-objetivo').value.trim();
        const tom = $('#swrc-tom').value.trim();
        const contexto = $('#swrc-contexto').value.trim();
        let objetivo = objSel;
        if (tom) objetivo += objetivo ? ` (tom ${tom})` : `Mensagem em tom ${tom}`;
        return gerarComunicacaoCore({
            contatoId: $('#swrc-contato')?.value || contatoSelecionadoId || null,
            clienteId: clienteSelecionadoId,
            tipo: $('.swr-com-canal-btn-active')?.dataset.canal || 'whatsapp',
            tamanho: 'medio',
            objetivo,
            produto: '',
            canal: contexto,
            btn: $('#swrc-gerar'),
            previewEl: $('#swrc-preview'),
            textoEl: $('#swrc-texto')
        });
    }

    function setTabComunicacao(tab) {
        $$('#swrc-tabs .swr-com-tab').forEach(t => {
            t.classList.toggle('swr-com-tab-active', t.dataset.ctab === tab);
        });
        const map = { historico: '#swrc-panel-historico', gerar: '#swrc-panel-gerar', modelos: '#swrc-panel-modelos' };
        Object.entries(map).forEach(([k, sel]) => {
            const el = $(sel);
            if (el) el.classList.toggle('hidden', k !== tab);
        });
    }

    function bindComunicacaoSecao() {
        $('#swrc-tabs')?.addEventListener('click', (e) => {
            const tab = e.target.closest('.swr-com-tab');
            if (tab) setTabComunicacao(tab.dataset.ctab);
        });

        $$('.swr-com-canal-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('.swr-com-canal-btn').forEach(b => b.classList.remove('swr-com-canal-btn-active'));
                btn.classList.add('swr-com-canal-btn-active');
            });
        });
        $('#swrc-gerar')?.addEventListener('click', gerarComunicacaoSecao);
        $('#swrc-regenerar')?.addEventListener('click', gerarComunicacaoSecao);
        $('#swrc-copiar')?.addEventListener('click', () => {
            navigator.clipboard.writeText($('#swrc-texto').textContent).then(() => {
                const b = $('#swrc-copiar');
                b.textContent = 'Copiado!';
                setTimeout(() => b.textContent = 'Copiar', 1500);
            });
        });
        $('#swrc-whatsapp')?.addEventListener('click', () => {
            const text = encodeURIComponent($('#swrc-texto').textContent);
            window.open(`https://wa.me/?text=${text}`, '_blank');
        });
        $('#swrc-email')?.addEventListener('click', () => {
            const text = $('#swrc-texto').textContent;
            const lines = text.split('\n');
            let subject = '';
            let body = text;
            const m = lines[0]?.match(/^assunto:\s*(.+)/i);
            if (m) { subject = m[1].trim(); body = lines.slice(1).join('\n').trim(); }
            window.open(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`, '_blank');
        });
    }

    // ==================== Links consolidadas + URL executivo ====================

    function queryExecutivoWarRoom() {
        const sel = $('#filtro-executivo');
        if (!sel) return '';
        const v = sel.value;
        return v ? `?executivo_id=${encodeURIComponent(v)}` : '';
    }

    function atualizarLinksPaginasConsolidadas() {
        const q = queryExecutivoWarRoom();
        const a = $('#swr-link-atividades-consolidadas');
        const o = $('#swr-link-objetivos-consolidadas');
        if (a) a.setAttribute('href', `${BASE}/atividades-consolidadas${q}`);
        if (o) o.setAttribute('href', `${BASE}/objetivos-consolidadas${q}`);
    }

    function aplicarExecutivoDaUrlNaWarRoom() {
        const sel = $('#filtro-executivo');
        if (!sel) return;
        const id = new URLSearchParams(window.location.search).get('executivo_id');
        if (!id) return;
        const ok = [...sel.options].some(opt => opt.value === id);
        if (ok) sel.value = id;
    }

    // ==================== Modal: Novo Cliente ====================

    function setPessoaClienteModal(pessoa) {
        const form = $('#swr-form-cliente');
        if (!form) return;
        const isPf = pessoa === 'F';
        $$('input[name="pessoa"]', form).forEach(r => { r.checked = r.value === pessoa; });
        $$('.swr-pessoa-toggle', form).forEach(label => {
            const active = label.dataset.pessoa === pessoa;
            label.classList.toggle('border-green-500', active);
            label.classList.toggle('bg-green-50', active);
            label.classList.toggle('text-green-700', active);
            label.classList.toggle('border-gray-300', !active);
            label.classList.toggle('bg-white', !active);
            label.classList.toggle('text-gray-500', !active);
        });

        $('#swr-label-cnpj').textContent = isPf ? 'CPF' : 'CNPJ';
        $('#swr-label-nome').textContent = isPf ? 'Nome Completo*' : 'Nome Fantasia*';
        $('#swr-input-cnpj').placeholder = isPf ? 'CPF' : 'CNPJ';

        const razaoWrap = $('#swr-razao-fields');
        const tipoWrap = $('#swr-tipo-cliente-fields');
        const agenciaWrap = $('#swr-agencia-fields');
        const percentualWrap = $('#swr-percentual-fields');
        const inscricoesWrap = $('#swr-inscricoes-fields');
        const razao = $('#swr-input-razao');
        const tipo = $('#swr-select-tipo-cliente');
        const agencia = $('#swr-cliente-agencia');

        razaoWrap?.classList.toggle('hidden', isPf);
        tipoWrap?.classList.toggle('hidden', isPf);
        agenciaWrap?.classList.toggle('hidden', isPf);
        percentualWrap?.classList.toggle('hidden', isPf);
        inscricoesWrap?.classList.toggle('hidden', isPf);

        if (razao) razao.required = !isPf;
        if (tipo) tipo.required = !isPf;
        if (agencia) agencia.required = !isPf;
    }

    function setStatusClienteModal(ativo) {
        const form = $('#swr-form-cliente');
        if (!form) return;
        const statusValue = ativo ? '1' : '0';
        $$('input[name="status"]', form).forEach(r => { r.checked = r.value === statusValue; });
        $$('.swr-status-toggle', form).forEach(label => {
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
        const el = $(`#swr-form-cliente [name="${name}"]`);
        if (el) el.value = value ?? '';
    }

    function atualizarBvClienteModal() {
        const tipo = $('#swr-select-tipo-cliente');
        const agencia = $('#swr-cliente-agencia');
        const wrap = $('#swr-percentual-fields');
        if (!tipo || !agencia || !wrap) return;
        const isParceiro = tipo.selectedOptions[0]?.dataset.parceiro === '1';
        const isAgencia = agencia.selectedOptions[0]?.dataset.agenciaSim === '1';
        const pessoa = $('#swr-form-cliente input[name="pessoa"]:checked')?.value || 'J';
        wrap.classList.toggle('hidden', pessoa === 'F' || (!isParceiro && !isAgencia));
        if (wrap.classList.contains('hidden')) {
            const pct = $('#swr-cliente-percentual');
            if (pct) pct.value = '';
        }
    }

    function preselecionarExecutivoClienteModal() {
        const selectVendas = $('#swr-cliente-vendedor');
        if (!selectVendas) return;
        const logged = String(window.SWR_LOGGED_USER_ID || '');
        const filtro = $('#filtro-executivo')?.value || '';
        const alvo = logged && [...selectVendas.options].some(opt => opt.value === logged)
            ? logged
            : filtro;
        if (alvo && [...selectVendas.options].some(opt => opt.value === String(alvo))) {
            selectVendas.value = String(alvo);
        }
    }

    function abrirModalNovoCliente() {
        const modal = $('#swr-modal-cliente');
        const form = $('#swr-form-cliente');
        if (!modal || !form) return;
        form.reset();
        $('#swr-cliente-id').value = '';
        $('#swr-cliente-modal-title').textContent = 'Novo Cliente';
        $('#swr-cliente-submit').textContent = 'Cadastrar';
        $('#swr-status-fields')?.classList.add('hidden');
        $('#swr-classificacao-cliente').value = 'Prospecção';
        setClienteFormValue('opera_midia', '0');
        setClienteFormValue('demanda_dados', '0');
        setClienteFormValue('demanda_programatica_canais', '0');
        setClienteFormValue('observacoes_comerciais_adicionais', '');
        setStatusClienteModal(true);
        setPessoaClienteModal('J');
        preselecionarExecutivoClienteModal();
        atualizarBvClienteModal();
        modal.showModal();
        setTimeout(() => $('#swr-input-nome')?.focus(), 50);
    }

    async function abrirModalEditarCliente(clienteId) {
        const modal = $('#swr-modal-cliente');
        const form = $('#swr-form-cliente');
        if (!modal || !form || !clienteId) return;
        form.reset();
        $('#swr-cliente-modal-title').textContent = 'Carregando cliente...';
        $('#swr-cliente-submit').textContent = 'Atualizar';
        $('#swr-status-fields')?.classList.remove('hidden');
        modal.showModal();

        try {
            const response = await fetch(`/api/cliente/${clienteId}`);
            const cliente = await response.json();
            if (!response.ok || cliente.error) {
                throw new Error(cliente.error || 'Erro ao carregar cliente.');
            }

            $('#swr-cliente-modal-title').textContent = cliente.nome_fantasia || cliente.razao_social || 'Editar Cliente';
            $('#swr-cliente-id').value = clienteId;
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
            atualizarBvClienteModal();
        } catch (e) {
            console.error(e);
            modal.close();
            showToast(e.message || 'Erro ao carregar cliente.', 'error');
        }
    }

    async function salvarNovoClienteWarRoom(ev) {
        ev.preventDefault();
        const form = $('#swr-form-cliente');
        const modal = $('#swr-modal-cliente');
        const btn = $('#swr-cliente-submit');
        if (!form || !modal) return;
        const clienteId = $('#swr-cliente-id')?.value || '';
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
                atualizarLinksPaginasConsolidadas();
            }
            await carregarClientes();
            const idParaSelecionar = data.id_cliente || clienteId;
            if (idParaSelecionar && swrCliCache.some(c => String(c.id_cliente) === String(idParaSelecionar))) {
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
        const selectResp = $('#swr-cotacao-responsavel');
        if (!selectResp) return;
        const logged = String(window.SWR_LOGGED_USER_ID || '');
        const filtro = $('#filtro-executivo')?.value || '';
        const clienteResp = clienteData.vendas_central_comm ? String(clienteData.vendas_central_comm) : '';
        const candidatos = [logged, clienteResp, filtro].filter(Boolean);
        const alvo = candidatos.find(id => [...selectResp.options].some(opt => opt.value === String(id)));
        if (alvo) selectResp.value = String(alvo);
    }

    function atualizarDuracaoCotacao() {
        const inicio = $('#swr-cotacao-inicio')?.value;
        const fim = $('#swr-cotacao-fim')?.value;
        const out = $('#swr-cotacao-duracao');
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

    async function carregarContatosCotacao(clienteId, selectSelector = '#swr-cotacao-contato') {
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
        const modal = $('#swr-modal-cotacao');
        const form = $('#swr-form-cotacao');
        if (!modal || !form) return;
        const id = clienteId || clienteSelecionadoId;
        if (!id) {
            showToast('Selecione um cliente.', 'warning');
            return;
        }

        form.reset();
        $('#swr-cotacao-client-id').value = '';
        $('#swr-cotacao-inicio').value = isoDatePlusDays(7);
        $('#swr-cotacao-fim').value = isoDatePlusDays(37);
        $('#swr-cotacao-valor-total-hidden').value = '';
        $('#swr-cotacao-budget-hidden').value = '';
        $('#swr-cotacao-cliente-select').value = '';
        $('#swr-cotacao-agencia').value = '';
        $('#swr-cotacao-parceiro').value = '';
        $('#swr-cotacao-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#swr-cotacao-agencia-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#swr-cotacao-parceiro-contato').innerHTML = '<option value="">Selecione o contato</option>';
        $('#swr-cotacao-briefing-nome')?.classList.add('hidden');
        if ($('#swr-cotacao-briefing-nome')) $('#swr-cotacao-briefing-nome').textContent = '';
        atualizarDuracaoCotacao();

        const clienteCache = swrCliCache.find(c => String(c.id_cliente) === String(id)) || {};
        preselecionarResponsavelCotacao(clienteCache);
        let focoInicial = '#swr-cotacao-nome';
        if (clienteEhAgencia(clienteCache)) {
            $('#swr-cotacao-agencia').value = String(id);
            carregarContatosCotacao(id, '#swr-cotacao-agencia-contato');
            focoInicial = '#swr-cotacao-agencia';
        } else if (clienteEhParceiroRegional(clienteCache)) {
            $('#swr-cotacao-parceiro').value = String(id);
            carregarContatosCotacao(id, '#swr-cotacao-parceiro-contato');
            focoInicial = '#swr-cotacao-parceiro';
        } else {
            $('#swr-cotacao-client-id').value = id;
            $('#swr-cotacao-cliente-select').value = String(id);
            carregarContatosCotacao(id);
        }

        modal.showModal();
        setTimeout(() => $(focoInicial)?.focus(), 50);

        try {
            const response = await fetch(`/api/cliente/${id}`);
            if (response.ok) {
                const cliente = await response.json();
                preselecionarResponsavelCotacao(cliente);
            }
        } catch (e) {
            console.warn('Não foi possível pré-selecionar responsável pelo cliente.', e);
        }
    }

    async function salvarNovaCotacaoWarRoom(ev) {
        ev.preventDefault();
        const form = $('#swr-form-cotacao');
        const modal = $('#swr-modal-cotacao');
        const btn = $('#swr-cotacao-submit');
        const clienteId = $('#swr-cotacao-client-id')?.value;
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
        aplicarExecutivoDaUrlNaWarRoom();
        atualizarLinksPaginasConsolidadas();

        $('#filtro-executivo').addEventListener('change', () => {
            atualizarLinksPaginasConsolidadas();
            limparColunas();
            carregarClientes();
        });

        $('#filtro-tipo')?.addEventListener('change', carregarClientes);
        $('#filtro-perfil')?.addEventListener('change', carregarClientes);

        $('#busca-cliente').addEventListener('input', debounce(carregarClientes, 300));

        $$('#tabs-atividades .swr-tab-ativ').forEach(tab => {
            tab.addEventListener('click', () => {
                setTabAtividades(tab.dataset.tab);
                if (!clienteSelecionadoId) return;
                if (tab.dataset.tab === 'todas') {
                    contatoSelecionadoId = null;
                    $$('.swr-contato-card').forEach(e => e.classList.remove('swr-contato-card-active'));
                }
                // Filtragem client-side sobre o cache já carregado.
                renderAtividades();
            });
        });

        // ---- Paginação da coluna Clientes ----
        $('#swr-cli-prev')?.addEventListener('click', () => {
            if (swrCliPage > 0) { swrCliPage--; renderClientesPagina(); }
        });
        $('#swr-cli-next')?.addEventListener('click', () => {
            const totalPages = Math.ceil(swrCliCache.length / SWR_CLI_PAGE_SIZE);
            if (swrCliPage < totalPages - 1) { swrCliPage++; renderClientesPagina(); }
        });

        // ---- Botões de ação no header ----
        function focarColuna(sel, inputSel) {
            if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
            const col = $(sel);
            scrollIntoViewSuave(col);
            const inp = inputSel ? $(inputSel) : null;
            if (inp) setTimeout(() => inp.focus(), 250);
        }
        $('#swr-btn-novo-cliente')?.addEventListener('click', abrirModalNovoCliente);
        $('#btn-nova-cotacao-swr')?.addEventListener('click', () => abrirModalNovaCotacao(clienteSelecionadoId));
        $('#swr-btn-nova-atividade')?.addEventListener('click', () => {
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
            const det = $('#swr-export'); if (det) det.open = false;
            window.location.href = `${BASE}/api/export/${tipo}?${params}`;
        }
        $('#swr-export-atividades')?.addEventListener('click', () => exportarCSV('atividades'));
        $('#swr-export-objetivos')?.addEventListener('click', () => exportarCSV('objetivos'));

        // ---- Modal Novo Cliente ----
        $('#swr-form-cliente')?.addEventListener('submit', salvarNovoClienteWarRoom);
        $('#swr-cliente-close')?.addEventListener('click', () => $('#swr-modal-cliente')?.close());
        $('#swr-cliente-cancel')?.addEventListener('click', () => $('#swr-modal-cliente')?.close());
        $$('#swr-form-cliente input[name="pessoa"]').forEach(radio => {
            radio.addEventListener('change', () => {
                setPessoaClienteModal(radio.value);
                atualizarBvClienteModal();
            });
        });
        $$('#swr-form-cliente input[name="status"]').forEach(radio => {
            radio.addEventListener('change', () => setStatusClienteModal(radio.value === '1'));
        });
        $('#swr-input-cnpj')?.addEventListener('input', ev => maskCpfCnpj(ev.target));
        $('#swr-cliente-cep')?.addEventListener('input', ev => maskCep(ev.target));
        $('#swr-cliente-percentual')?.addEventListener('input', ev => maskPercentual(ev.target));
        $('#swr-select-tipo-cliente')?.addEventListener('change', atualizarBvClienteModal);
        $('#swr-cliente-agencia')?.addEventListener('change', atualizarBvClienteModal);

        // ---- Modal Nova Cotação ----
        $('#swr-form-cotacao')?.addEventListener('submit', salvarNovaCotacaoWarRoom);
        $('#swr-cotacao-close')?.addEventListener('click', () => $('#swr-modal-cotacao')?.close());
        $('#swr-cotacao-cancel')?.addEventListener('click', () => $('#swr-modal-cotacao')?.close());
        $('#swr-cotacao-valor-total')?.addEventListener('input', ev => maskMoneyBR(ev.target, $('#swr-cotacao-valor-total-hidden')));
        $('#swr-cotacao-budget')?.addEventListener('input', ev => maskMoneyBR(ev.target, $('#swr-cotacao-budget-hidden')));
        $('#swr-cotacao-inicio')?.addEventListener('change', atualizarDuracaoCotacao);
        $('#swr-cotacao-fim')?.addEventListener('change', atualizarDuracaoCotacao);
        $('#swr-cotacao-cliente-select')?.addEventListener('change', ev => {
            $('#swr-cotacao-client-id').value = ev.target.value || '';
            carregarContatosCotacao(ev.target.value, '#swr-cotacao-contato');
        });
        $('#swr-cotacao-agencia')?.addEventListener('change', ev => carregarContatosCotacao(ev.target.value, '#swr-cotacao-agencia-contato'));
        $('#swr-cotacao-parceiro')?.addEventListener('change', ev => carregarContatosCotacao(ev.target.value, '#swr-cotacao-parceiro-contato'));
        $('#swr-cotacao-briefing-dropzone')?.addEventListener('click', () => $('#swr-cotacao-briefing-arquivo')?.click());
        $('#swr-cotacao-briefing-arquivo')?.addEventListener('change', ev => {
            const file = ev.target.files?.[0];
            const label = $('#swr-cotacao-briefing-nome');
            if (!label) return;
            label.textContent = file ? file.name : '';
            label.classList.toggle('hidden', !file);
        });

        // ---- Seção Comunicação (coluna 5) ----
        bindComunicacaoSecao();
        setTabComunicacao('gerar');

        $$('[data-modal-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                if (tab.dataset.modalTab === 'dados') showTabDados();
                else showTabComunicacao();
            });
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
            const text = encodeURIComponent($('#com-texto').textContent);
            window.open(`https://wa.me/?text=${text}`, '_blank');
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
                carregarAtividades(swrActCtx.clienteId, swrActCtx.contatoId);
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
                if (swrObjCtx.clienteId) carregarObjetivos(swrObjCtx.clienteId);
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
                        telefone: $('#cr-tel').value.trim() || null
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

        $('#btn-contato-import')?.addEventListener('click', () => {
            if (!clienteSelecionadoId) { showToast('Selecione um cliente.', 'warning'); return; }
            $('#ci-texto').value = '';
            $('#ci-result').classList.add('hidden');
            $('#modal-contato-import').showModal();
        });

        $('#ci-submit')?.addEventListener('click', async () => {
            if (!clienteSelecionadoId) return;
            const btn = $('#ci-submit');
            btn?.classList.add('loading');
            try {
                const r = await api(`/api/cliente/${clienteSelecionadoId}/contatos/importar`, {
                    method: 'POST',
                    body: JSON.stringify({ texto: $('#ci-texto').value })
                });
                const pre = $('#ci-result');
                pre.textContent = `Criados: ${r.criados}\n` + (r.erros || []).map(e => `Linha ${e.linha}: ${e.msg}`).join('\n');
                pre.classList.remove('hidden');
                showToast(`${r.criados} contato(s) importado(s).`, (r.erros && r.erros.length) ? 'warning' : 'success');
                carregarContatos(clienteSelecionadoId);
            } catch (e) {
                showToast(e.message || 'Erro na importação.', 'error');
            } finally {
                btn?.classList.remove('loading');
            }
        });

        if ($('#filtro-executivo')) carregarClientes();
    });
})();
