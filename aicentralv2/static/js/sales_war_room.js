(function () {
    'use strict';

    const BASE = '/sales-war-room';
    let clienteSelecionadoId = null;
    let contatoSelecionadoId = null;
    let modalContatoId = null;
    let modalClienteId = null;
    let chartInstances = {};


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

    function badgeABC(cat) {
        const colors = { A: 'badge-success', B: 'badge-warning', C: 'badge-error' };
        return `<span class="badge badge-sm ${colors[cat] || 'badge-ghost'}">${cat || '-'}</span>`;
    }

    function debounce(fn, ms) {
        let t;
        return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }

    /** Carteira: é agência (cadastro Sim), vem da API como eh_agencia boolean */
    function clienteEhAgencia(c) {
        if (c.eh_agencia === true) return true;
        if (c.eh_agencia === false) return false;
        return c.is_agencia === true;
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
        const tipo = $('.filtro-tipo.active')?.dataset.tipo || '';
        const perfil = $('.filtro-perfil.active')?.dataset.perfil || '';
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
            atualizarContadoresCarteira(data.clientes, perfil);
            if (!data.clientes.length) {
                showEmpty(container, 'Nenhum cliente encontrado.');
                return;
            }
            container.innerHTML = data.clientes.map(c => `
                <div class="swr-card ${c.id_cliente == clienteSelecionadoId ? 'swr-card-active' : ''}"
                     data-id="${c.id_cliente}">
                    <div class="flex items-start justify-between gap-2">
                        <div class="flex-1 min-w-0">
                            <div class="font-medium text-sm truncate">${c.nome_fantasia || c.razao_social}</div>
                            <div class="text-xs opacity-60">${clienteEhAgencia(c) ? 'Agência' : 'Cliente final'} · ${c.qtd_contatos} contato(s)</div>
                        </div>
                        <div class="flex items-center gap-1">
                            ${c.atividades_pendentes === 0 ? '<svg class="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z"/></svg>' : ''}
                            ${badgeABC(c.categoria_abc)}
                        </div>
                    </div>
                </div>
            `).join('');

            $$('.swr-card', container).forEach(el => {
                el.addEventListener('click', () => selecionarCliente(parseInt(el.dataset.id)));
            });
        } catch (e) {
            esconderContadoresCarteira();
            showEmpty(container, 'Erro ao carregar clientes.');
            console.error(e);
        }
    }

    function selecionarCliente(id) {
        clienteSelecionadoId = id;
        contatoSelecionadoId = null;

        $$('.swr-card', $('#lista-clientes')).forEach(el => {
            el.classList.toggle('swr-card-active', parseInt(el.dataset.id) === id);
        });

        setTabAtividades('todas');
        carregarStatus(id);
        carregarContatos(id);
        carregarAtividades(id);
        carregarObjetivos(id);
    }

    function limparColunas() {
        clienteSelecionadoId = null;
        contatoSelecionadoId = null;
        showEmpty($('#area-status'), 'Selecione um cliente.');
        showEmpty($('#lista-contatos'), 'Selecione um cliente.');
        showEmpty($('#lista-atividades'), 'Selecione um cliente.');
        showEmpty($('#lista-objetivos'), 'Selecione um cliente.');
    }

    // ==================== Column 2: Status ====================

    async function carregarStatus(clienteId) {
        const container = $('#area-status');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/status`);
            const s = data.status;
            container.innerHTML = `
                <div class="swr-status-section">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs opacity-60">Responsável</span>
                        <span class="text-sm font-medium">${s.executivo_nome || '-'}</span>
                    </div>
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs opacity-60">Categoria</span>
                        ${badgeABC(s.categoria_abc)}
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-center mb-3">
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-lg font-bold">${s.total_cotacoes}</div>
                            <div class="text-xs opacity-60">Cotações</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-lg font-bold">${s.cotacoes_aprovadas} <span class="text-xs font-normal opacity-60">(${s.pct_aprovadas}%)</span></div>
                            <div class="text-xs opacity-60">Aprovadas</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-sm font-bold">${fmtBRL(s.valor_bruto)}</div>
                            <div class="text-xs opacity-60">Bruto</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-sm font-bold">${fmtBRL(s.valor_liquido)}</div>
                            <div class="text-xs opacity-60">Líquido</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-lg font-bold">${s.total_pis} <span class="text-xs font-normal opacity-60">(${s.pis_concluidos} concl.)</span></div>
                            <div class="text-xs opacity-60">PIs</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-sm font-bold">${fmtBRL(s.valor_pis)}</div>
                            <div class="text-xs opacity-60">Valor PIs</div>
                        </div>
                    </div>
                    <div class="flex gap-1 mb-2">
                        <button type="button" class="btn btn-xs btn-outline flex-1 h-7 min-h-7 py-0 px-2 text-[11px] leading-none border-base-300" id="btn-ver-mais-status">Ver mais dados</button>
                        <button type="button" class="btn btn-xs btn-ghost btn-outline flex-1 h-7 min-h-7 py-0 px-2 text-[11px] leading-none" id="btn-editar-cliente-swr" title="Editar cadastro do cliente">Editar cliente</button>
                    </div>
                    <div class="border-t border-base-300 pt-2 mt-1">
                        <label class="text-xs font-medium opacity-70 block mb-1">Nota sobre o cliente</label>
                        <textarea id="swr-nota-cliente" class="textarea textarea-bordered textarea-xs w-full min-h-[4.5rem] text-xs" maxlength="8000" placeholder="Anotações visíveis para a equipe comercial..."></textarea>
                        <button type="button" class="btn btn-xs btn-primary w-full mt-1 h-7 min-h-7 py-0 px-2 text-[11px] leading-none" id="btn-salvar-nota-cliente">Salvar nota</button>
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

        $('#btn-editar-cliente-swr')?.addEventListener('click', () => {
            window.location.href = `/clientes?open=${clienteId}`;
        });
    }

    // ==================== Column 3: Contatos ====================

    async function carregarContatos(clienteId) {
        const container = $('#lista-contatos');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/contatos`);
            if (!data.contatos.length) {
                showEmpty(container, 'Nenhum contato cadastrado.');
                return;
            }
            container.innerHTML = data.contatos.map(c => {
                const tel = (c.telefone || '').replace(/\D/g, '');
                const semAtividade = !c.ultima_atividade;
                return `
                    <div class="swr-card swr-card-contato ${c.id_contato_cliente == contatoSelecionadoId ? 'swr-card-active' : ''}"
                         data-id="${c.id_contato_cliente}">
                        <div class="flex items-start justify-between gap-2">
                            <div class="flex-1 min-w-0">
                                <div class="font-medium text-sm truncate">${c.nome_completo}</div>
                                <div class="text-xs opacity-60">${c.cargo || 'Sem cargo'}</div>
                                ${c.email ? `<div class="text-xs opacity-70 truncate mt-0.5">${c.email}</div>` : ''}
                                ${c.telefone ? `<div class="text-xs opacity-70 mt-0.5">${c.telefone}</div>` : ''}
                            </div>
                            <div class="flex flex-col items-center gap-1">
                                ${semAtividade ? '<svg class="w-3.5 h-3.5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z"/></svg>' : ''}
                                <button class="btn btn-ghost btn-xs btn-circle swr-btn-detalhes" data-contato-id="${c.id_contato_cliente}" title="Ver detalhes" onclick="event.stopPropagation()">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            $$('.swr-card-contato', container).forEach(el => {
                el.addEventListener('click', () => {
                    const id = parseInt(el.dataset.id);
                    contatoSelecionadoId = id;
                    $$('.swr-card-contato', container).forEach(e => e.classList.remove('swr-card-active'));
                    el.classList.add('swr-card-active');
                    setTabAtividades('contato');
                    carregarAtividades(clienteSelecionadoId, id);
                });
            });

            $$('.swr-btn-detalhes', container).forEach(btn => {
                btn.addEventListener('click', () => {
                    abrirModalContato(parseInt(btn.dataset.contatoId));
                });
            });
        } catch (e) {
            showEmpty(container, 'Erro ao carregar contatos.');
            console.error(e);
        }
    }

    // ==================== Column 4: Atividades ====================

    function setTabAtividades(tab) {
        $$('#tabs-atividades .tab').forEach(t => {
            t.classList.toggle('tab-active', t.dataset.tab === tab);
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

    function renderAtividadeCard(a, clienteId, contatoId) {
        const vencida = atividadeVencida(a);
        const hoje = atividadeHoje(a);
        const tipo = a.tipo || 'atividade';
        const extraClass = vencida ? 'swr-atividade-vencida' : (hoje ? 'swr-atividade-hoje' : '');
        const podeFeito = a.status !== 'concluida';
        return `
            <div class="swr-atividade-card swr-fade-in mb-2 ${extraClass}" data-aid="${a.id}">
                <div class="flex items-start gap-2 min-w-0">
                    ${podeFeito ? `<input type="checkbox" class="checkbox checkbox-xs mt-1 swr-act-feito shrink-0" title="Marcar concluída" data-id="${a.id}" />` : '<span class="w-3.5 shrink-0"></span>'}
                    <span class="swr-tipo-badge swr-tipo-${tipo} shrink-0 mt-0.5" title="${TIPO_LABELS[tipo] || tipo}">${TIPO_ICONS[tipo] || TIPO_ICONS.atividade}</span>
                    <div class="min-w-0 flex-1 space-y-1">
                        <p class="swr-atividade-texto-principal font-medium break-words [overflow-wrap:anywhere]">${escapeHtml(a.titulo || a.descricao || '—')}</p>
                        ${a.titulo && a.descricao ? `<p class="swr-atividade-texto-sec opacity-75 break-words [overflow-wrap:anywhere]">${escapeHtml(a.descricao)}</p>` : ''}
                        <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] opacity-55">
                            <span>${fmtDate(a.data_atividade)}</span>
                            ${a.data_prazo ? `<span class="${vencida ? 'text-error font-semibold' : (hoje ? 'text-warning font-semibold' : '')}">Prazo ${fmtDate(a.data_prazo)}</span>` : ''}
                        </div>
                        ${a.contato_nome ? `<div class="text-[11px] opacity-45 truncate max-w-full" title="${escapeHtml(a.contato_nome)}">${escapeHtml(a.contato_nome)}</div>` : ''}
                        <div class="flex gap-0.5 pt-0.5">
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 swr-act-edit" data-id="${a.id}" title="Editar">${ICON_EDIT}</button>
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 text-error swr-act-del" data-id="${a.id}" title="Excluir">${ICON_TRASH}</button>
                        </div>
                    </div>
                </div>
            </div>`;
    }

    async function carregarAtividades(clienteId, contatoId) {
        swrActCtx = { clienteId, contatoId };
        const container = $('#lista-atividades');
        showSpinner(container);
        try {
            const params = new URLSearchParams();
            if (contatoId) params.set('contato_id', contatoId);
            const data = await api(`/api/cliente/${clienteId}/atividades?${params}`);

            const lista = data.atividades || [];
            const ativas = sortAtividadesPorPrazoAtivas(lista.filter(a => a.status !== 'concluida'));
            const concluidas = sortAtividadesConcluidasPorData(lista.filter(a => a.status === 'concluida'));

            let html = '';

            if (lista.length) {
                if (ativas.length) {
                    html += `<div class="swr-atividades-list mb-2">${ativas.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
                }
                if (concluidas.length) {
                    html += `<div class="divider text-xs my-2 opacity-70">Concluídas</div>`;
                    html += `<div class="swr-atividades-list swr-atividades-list--done mb-2">${concluidas.map(a => renderAtividadeCard(a, clienteId, contatoId)).join('')}</div>`;
                }
            }

            if (!ativas.length) {
                html = `
                    <div class="swr-sugestao-card swr-fade-in mb-2">
                        <div class="text-xs text-center py-2 opacity-70">Nenhuma atividade pendente.</div>
                    </div>
                ` + html;
            }

            const hoje = new Date().toISOString().slice(0, 10);
            html += `
                <div class="divider text-xs my-2">Nova atividade</div>
                <div class="swr-form-nova-atividade">
                    <textarea id="input-atividade" class="swr-textarea" rows="3" placeholder="Descrição da atividade..."></textarea>
                    <select id="input-atividade-tipo" class="swr-select">
                        <option value="atividade">Atividade</option>
                        <option value="ligacao">Ligação</option>
                        <option value="almoco">Almoço</option>
                        <option value="reuniao">Reunião</option>
                        <option value="projeto">Projeto</option>
                        <option value="planejamento">Planejamento</option>
                        <option value="cadu">Cadu</option>
                    </select>
                    <div class="swr-form-row">
                        <label class="swr-date-field">
                            <span class="swr-date-label">Data</span>
                            <input type="date" id="input-atividade-data" class="swr-date" value="${hoje}" />
                        </label>
                        <label class="swr-date-field">
                            <span class="swr-date-label">Prazo</span>
                            <input type="date" id="input-atividade-prazo" class="swr-date" />
                        </label>
                    </div>
                    <div class="swr-form-actions">
                        <button type="button" class="btn btn-xs btn-primary flex-1 h-7 min-h-7 py-0 px-2 text-[11px] leading-none" id="btn-add-atividade">Criar</button>
                    </div>
                    <details class="mt-1.5 group">
                        <summary class="text-[10px] cursor-pointer opacity-60 list-none flex items-center gap-1">
                            <span class="group-open:rotate-90 transition-transform">▸</span> IA (opcional)
                        </summary>
                        <div class="flex flex-col gap-1 pt-1">
                            <button type="button" class="btn btn-xs btn-outline btn-secondary w-full" id="btn-sugerir-atividade">Sugerir acompanhamento</button>
                            <button type="button" class="btn btn-xs btn-ghost btn-outline w-full" id="btn-add-atividade-ia">Melhorar texto e criar</button>
                        </div>
                    </details>
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
        } catch (e) {
            showEmpty(container, 'Erro ao carregar atividades.');
            console.error(e);
        }
    }

    // ==================== Column 5: Objetivos ====================

    async function carregarObjetivos(clienteId) {
        swrObjCtx.clienteId = clienteId;
        const container = $('#lista-objetivos');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/objetivos`);
            const ativos = data.objetivos.filter(o => !o.conquistado);
            const conquistados = data.objetivos.filter(o => o.conquistado);
            const hojePrazo = new Date().toISOString().slice(0, 10);

            let html = `
                <div class="swr-form-novo-objetivo mb-2">
                    <input type="text" id="input-objetivo" class="swr-input" placeholder="Novo objetivo..." />
                    <div class="swr-form-row items-end">
                        <label class="swr-date-field flex-1 min-w-0">
                            <span class="swr-date-label">Prazo</span>
                            <input type="date" id="input-objetivo-prazo" class="swr-date" value="${hojePrazo}" />
                        </label>
                        <button type="button" class="btn btn-xs btn-primary btn-square h-7 w-7 min-h-7 p-0 shrink-0" id="btn-add-objetivo" title="Adicionar objetivo" aria-label="Adicionar objetivo">+</button>
                    </div>
                </div>
                <div id="ia-sugestoes" class="hidden mb-2"></div>
            `;

            if (ativos.length) {
                html += '<div class="text-xs font-semibold opacity-60 mb-1">Ativos</div>';
                html += ativos.map(o => `
                    <div class="flex items-start gap-1.5 py-1.5 swr-fade-in min-w-0">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check shrink-0" data-id="${o.id}" />
                        <div class="flex-1 min-w-0">
                            <span class="text-xs leading-snug break-words [overflow-wrap:anywhere]">${escapeHtml(o.texto)}</span>
                            ${o.data_prazo ? `<div class="text-[10px] opacity-50 mt-0.5">Prazo: ${fmtDate(o.data_prazo)}</div>` : ''}
                        </div>
                        <div class="flex flex-row gap-0.5 shrink-0">
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 swr-obj-edit" data-id="${o.id}" title="Editar">${ICON_EDIT}</button>
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 text-error swr-obj-del" data-id="${o.id}" title="Excluir">${ICON_TRASH}</button>
                        </div>
                    </div>
                `).join('');
            }

            if (conquistados.length) {
                html += '<div class="divider text-xs my-2">Conquistados</div>';
                html += conquistados.map(o => `
                    <div class="flex items-start gap-1.5 py-1.5 opacity-50 swr-fade-in swr-obj-conquistado min-w-0">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check shrink-0" data-id="${o.id}" checked />
                        <div class="flex-1 min-w-0">
                            <span class="text-xs line-through leading-snug break-words [overflow-wrap:anywhere]">${escapeHtml(o.texto)}</span>
                            ${o.data_conquista ? `<div class="text-[10px] opacity-60 mt-0.5">Conquistado em ${fmtDate(o.data_conquista)}</div>` : ''}
                        </div>
                        <div class="flex flex-row gap-0.5 shrink-0">
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 swr-obj-edit" data-id="${o.id}" title="Editar">${ICON_EDIT}</button>
                            <button type="button" class="btn btn-ghost btn-xs btn-square h-7 w-7 min-h-0 p-0 text-error swr-obj-del" data-id="${o.id}" title="Excluir">${ICON_TRASH}</button>
                        </div>
                    </div>
                `).join('');
            }

            if (!ativos.length && !conquistados.length) {
                html += '<div class="swr-empty-state mt-2">Nenhum objetivo cadastrado.</div>';
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

    async function gerarComunicacao() {
        const tipo = $('input[name="com-tipo"]:checked')?.value || 'whatsapp';
        const tamanho = $('input[name="com-tamanho"]:checked')?.value || 'medio';
        const objetivo = $('#com-objetivo').value.trim();
        const produto = $('#com-produto').value;
        const canal = $('#com-canal').value.trim();

        if (!objetivo) { showToast('Preencha o objetivo da mensagem.', 'warning'); return; }

        const btn = $('#btn-gerar-comunicacao');
        btn.classList.add('loading');
        try {
            const data = await api('/api/ia/gerar-comunicacao', {
                method: 'POST',
                body: JSON.stringify({
                    contato_id: modalContatoId,
                    cliente_id: modalClienteId,
                    tipo, tamanho, objetivo, produto, canal
                })
            });
            $('#com-texto').textContent = data.mensagem;
            $('#com-preview').classList.remove('hidden');
        } catch (e) {
            console.error(e);
            showToast('Erro ao gerar comunicação.', 'error');
        } finally {
            btn.classList.remove('loading');
        }
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

    // ==================== Init & Event Bindings ====================

    document.addEventListener('DOMContentLoaded', () => {
        aplicarExecutivoDaUrlNaWarRoom();
        atualizarLinksPaginasConsolidadas();

        $('#filtro-executivo').addEventListener('change', () => {
            atualizarLinksPaginasConsolidadas();
            limparColunas();
            carregarClientes();
        });

        $$('.filtro-tipo').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('.filtro-tipo').forEach(b => b.classList.remove('active', 'btn-primary'));
                btn.classList.add('active', 'btn-primary');
                carregarClientes();
            });
        });

        $$('.filtro-perfil').forEach(btn => {
            btn.addEventListener('click', () => {
                $$('.filtro-perfil').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                carregarClientes();
            });
        });

        $('#busca-cliente').addEventListener('input', debounce(carregarClientes, 300));

        $$('#tabs-atividades .tab').forEach(tab => {
            tab.addEventListener('click', () => {
                setTabAtividades(tab.dataset.tab);
                if (!clienteSelecionadoId) return;
                if (tab.dataset.tab === 'todas') {
                    contatoSelecionadoId = null;
                    $$('.swr-card-contato').forEach(e => e.classList.remove('swr-card-active'));
                    carregarAtividades(clienteSelecionadoId);
                } else if (contatoSelecionadoId) {
                    carregarAtividades(clienteSelecionadoId, contatoSelecionadoId);
                }
            });
        });

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
