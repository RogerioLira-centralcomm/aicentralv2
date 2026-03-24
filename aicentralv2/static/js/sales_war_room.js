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

    // ==================== Column 1: Clientes ====================

    async function carregarClientes() {
        const execId = $('#filtro-executivo').value;
        const tipo = $('.filtro-tipo.active')?.dataset.tipo || '';
        const busca = $('#busca-cliente').value.trim();
        const container = $('#lista-clientes');

        if (!execId) {
            showEmpty(container, 'Selecione um executivo para carregar a carteira.');
            limparColunas();
            return;
        }

        showSpinner(container);
        try {
            const params = new URLSearchParams({ executivo_id: execId, tipo, busca });
            const data = await api(`/api/clientes?${params}`);
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
                            <div class="text-xs opacity-60">${c.is_agencia ? 'Agência' : 'Cliente direto'} · ${c.qtd_contatos} contato(s)</div>
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
                    <button class="btn btn-xs btn-outline w-full" id="btn-ver-mais-status">Ver mais dados</button>
                </div>
            `;

            bindStatusEvents(clienteId);
        } catch (e) {
            showEmpty(container, 'Erro ao carregar status.');
            console.error(e);
        }
    }

    function bindStatusEvents(clienteId) {
        $('#btn-ver-mais-status')?.addEventListener('click', () => abrirModalStatusCompleto(clienteId));
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

    function sortAtividades(list) {
        return list.slice().sort((a, b) => {
            const sa = a.status === 'concluida' ? 2 : (a.status === 'em_andamento' ? 1 : 0);
            const sb = b.status === 'concluida' ? 2 : (b.status === 'em_andamento' ? 1 : 0);
            if (sa !== sb) return sa - sb;
            const va = atividadeVencida(a) ? 0 : 1;
            const vb = atividadeVencida(b) ? 0 : 1;
            if (va !== vb) return va - vb;
            const da = a.data_prazo || '9999-12-31';
            const db = b.data_prazo || '9999-12-31';
            return da.localeCompare(db);
        });
    }

    async function carregarAtividades(clienteId, contatoId) {
        const container = $('#lista-atividades');
        showSpinner(container);
        try {
            const params = new URLSearchParams();
            if (contatoId) params.set('contato_id', contatoId);
            const data = await api(`/api/cliente/${clienteId}/atividades?${params}`);

            const sorted = sortAtividades(data.atividades);
            const pendentes = sorted.filter(a => a.status !== 'concluida');
            let html = '';

            if (!sorted.length) {
                html = '';
            } else {
                html = sorted.map(a => {
                    const statusBadge = { pendente: 'badge-warning', em_andamento: 'badge-info', concluida: 'badge-success' };
                    const statusLabel = { pendente: 'Pendente', em_andamento: 'Em andamento', concluida: 'Concluída' };
                    const vencida = atividadeVencida(a);
                    const hoje = atividadeHoje(a);
                    const tipo = a.tipo || 'atividade';
                    const extraClass = vencida ? 'swr-atividade-vencida' : (hoje ? 'swr-atividade-hoje' : '');
                    return `
                        <div class="swr-atividade-card swr-fade-in mb-1.5 ${extraClass}">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="swr-tipo-badge swr-tipo-${tipo}" title="${TIPO_LABELS[tipo] || tipo}">${TIPO_ICONS[tipo] || TIPO_ICONS.atividade}</span>
                                <span class="font-medium text-xs flex-1 truncate">${a.titulo || a.descricao}</span>
                                <span class="badge badge-xs ${statusBadge[a.status] || ''}">${statusLabel[a.status] || a.status}</span>
                            </div>
                            ${a.titulo && a.descricao ? `<div class="text-xs opacity-70 mb-1 ml-6">${a.descricao}</div>` : ''}
                            <div class="flex items-center justify-between ml-6">
                                <div class="flex items-center gap-2 text-xs opacity-50">
                                    <span>${fmtDate(a.data_atividade)}</span>
                                    ${a.data_prazo ? `<span class="${vencida ? 'text-error font-semibold' : (hoje ? 'text-warning font-semibold' : '')}">Prazo: ${fmtDate(a.data_prazo)}</span>` : ''}
                                </div>
                                <select class="text-xs bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5 text-gray-700 focus:outline-none focus:border-gray-400 appearance-none swr-status-select" data-id="${a.id}">
                                    <option value="pendente" ${a.status === 'pendente' ? 'selected' : ''}>Pendente</option>
                                    <option value="em_andamento" ${a.status === 'em_andamento' ? 'selected' : ''}>Em andamento</option>
                                    <option value="concluida" ${a.status === 'concluida' ? 'selected' : ''}>Concluída</option>
                                </select>
                            </div>
                            ${a.contato_nome ? `<div class="text-xs opacity-40 ml-6 mt-0.5">${a.contato_nome}</div>` : ''}
                        </div>
                    `;
                }).join('');
            }

            if (!pendentes.length) {
                html = `
                    <div class="swr-sugestao-card swr-fade-in mb-2">
                        <div class="text-xs text-center py-2 opacity-70">Nenhuma atividade pendente.</div>
                        <button class="btn btn-xs btn-outline btn-secondary w-full" id="btn-sugerir-atividade">Sugerir acompanhamento com IA</button>
                    </div>
                ` + html;
            }

            const hoje = new Date().toISOString().slice(0, 10);
            html += `
                <div class="divider text-xs my-2">Nova atividade</div>
                <div class="swr-form-nova-atividade">
                    <input type="text" id="input-atividade-titulo" class="swr-input" placeholder="Título" />
                    <textarea id="input-atividade" class="swr-textarea" rows="2" placeholder="Descrição..."></textarea>
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
                        <button class="btn btn-xs btn-primary flex-1" id="btn-add-atividade">Criar</button>
                        <button class="btn btn-xs btn-ghost btn-outline" id="btn-add-atividade-ia" title="Criar com IA">✨ IA</button>
                    </div>
                </div>
            `;

            container.innerHTML = html;

            $$('.swr-status-select', container).forEach(sel => {
                sel.addEventListener('change', async () => {
                    try {
                        await api(`/api/atividades/${sel.dataset.id}/status`, {
                            method: 'PATCH',
                            body: JSON.stringify({ status: sel.value })
                        });
                        carregarAtividades(clienteId, contatoId);
                    } catch (e) {
                        console.error(e);
                        showToast('Erro ao atualizar status.', 'error');
                    }
                });
            });

            async function criarAtividade(usarIA) {
                const titulo = $('#input-atividade-titulo').value.trim();
                const descricao = $('#input-atividade').value.trim();
                const dataAtiv = $('#input-atividade-data').value;
                const tipo = $('#input-atividade-tipo').value;
                const dataPrazo = $('#input-atividade-prazo').value || null;

                if (!descricao || !dataAtiv) { showToast('Preencha descrição e data.', 'warning'); return; }

                const btn = usarIA ? $('#btn-add-atividade-ia') : $('#btn-add-atividade');
                btn.classList.add('loading');
                try {
                    let tituloFinal = titulo;
                    let descFinal = descricao;
                    if (usarIA) {
                        try {
                            const ia = await api('/api/ia/melhorar-texto', {
                                method: 'POST',
                                body: JSON.stringify({ texto: `${titulo ? titulo + ': ' : ''}${descricao}`, contexto: 'atividade_comercial' })
                            });
                            const melhorado = ia.texto_melhorado || descricao;
                            if (titulo) {
                                const parts = melhorado.split(':');
                                tituloFinal = parts.length > 1 ? parts[0].trim() : titulo;
                                descFinal = parts.length > 1 ? parts.slice(1).join(':').trim() : melhorado;
                            } else {
                                descFinal = melhorado;
                            }
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
                        $('#input-atividade-titulo').value = data.sugestao.titulo || '';
                        $('#input-atividade').value = data.sugestao.descricao || '';
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
        const container = $('#lista-objetivos');
        showSpinner(container);
        try {
            const data = await api(`/api/cliente/${clienteId}/objetivos`);
            const ativos = data.objetivos.filter(o => !o.conquistado);
            const conquistados = data.objetivos.filter(o => o.conquistado);

            let html = `
                <div class="swr-form-novo-objetivo mb-2">
                    <input type="text" id="input-objetivo" class="swr-input" placeholder="Novo objetivo..." />
                    <div class="swr-form-row">
                        <label class="swr-date-field flex-1">
                            <span class="swr-date-label">Prazo</span>
                            <input type="date" id="input-objetivo-prazo" class="swr-date" />
                        </label>
                        <button class="btn btn-xs btn-primary" id="btn-add-objetivo" style="align-self:flex-end">+</button>
                    </div>
                </div>
                <div id="ia-sugestoes" class="hidden mb-2"></div>
            `;

            if (ativos.length) {
                html += '<div class="text-xs font-semibold opacity-60 mb-1">Ativos</div>';
                html += ativos.map(o => `
                    <div class="flex items-start gap-2 py-1 swr-fade-in">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check" data-id="${o.id}" />
                        <div class="flex-1 min-w-0">
                            <span class="text-xs">${o.texto}</span>
                            ${o.data_prazo ? `<div class="text-xs opacity-50">Prazo: ${fmtDate(o.data_prazo)}</div>` : ''}
                        </div>
                    </div>
                `).join('');
            }

            if (conquistados.length) {
                html += '<div class="divider text-xs my-2">Conquistados</div>';
                html += conquistados.map(o => `
                    <div class="flex items-start gap-2 py-1 opacity-50 swr-fade-in swr-obj-conquistado">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check" data-id="${o.id}" checked />
                        <div class="flex-1 min-w-0">
                            <span class="text-xs line-through">${o.texto}</span>
                            ${o.data_conquista ? `<div class="text-xs opacity-60">Conquistado em ${fmtDate(o.data_conquista)}</div>` : ''}
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

        kpisEl.innerHTML = '<span class="loading loading-spinner loading-sm col-span-4"></span>';
        try {
            const data = await api(`/api/cliente/${clienteId}/status-completo?ano=${ano}`);
            const rc = data.resumo_cotacoes || { total_cotacoes: 0, cotacoes_aprovadas: 0, valor_total: 0, pct_conversao: 0 };
            const rp = data.resumo_pis || { total_pis: 0, pis_concluidos: 0, valor_pis: 0 };

            kpisEl.innerHTML = `
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Cotações</div>
                    <div class="stat-value text-lg">${rc.total_cotacoes || 0}</div>
                    <div class="stat-desc text-xs">${fmtBRL(rc.valor_total)}</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Aprovadas</div>
                    <div class="stat-value text-lg">${rc.cotacoes_aprovadas || 0}</div>
                    <div class="stat-desc text-xs">${rc.pct_conversao || 0}% conversão</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">PIs</div>
                    <div class="stat-value text-lg">${rp.total_pis || 0}</div>
                    <div class="stat-desc text-xs">${rp.pis_concluidos || 0} concluídos</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Ticket Médio</div>
                    <div class="stat-value text-sm">${fmtBRL(data.ticket_medio)}</div>
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

            const ctxBar = $('#chart-cotacoes-mes');
            chartInstances['cotacoesMes'] = new Chart(ctxBar, {
                type: 'bar',
                data: {
                    labels: meses,
                    datasets: [{
                        label: 'Total',
                        data: dadosMes.map(d => d.total),
                        backgroundColor: 'rgba(99,102,241,0.6)'
                    }, {
                        label: 'Aprovadas',
                        data: dadosMes.map(d => d.aprovadas),
                        backgroundColor: 'rgba(34,197,94,0.6)'
                    }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
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

        } catch (e) {
            kpisEl.innerHTML = '<div class="text-xs opacity-50 col-span-4 text-center py-4">Nenhum dado encontrado para este período.</div>';
            tabelaEl.innerHTML = '<tr><td colspan="5" class="text-center opacity-50">Sem cotações neste período.</td></tr>';
            const pisTabelaEl = $('#modal-pis-tabela');
            if (pisTabelaEl) pisTabelaEl.innerHTML = '<tr><td colspan="5" class="text-center opacity-50">Sem PIs neste período.</td></tr>';
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

    // ==================== Init & Event Bindings ====================

    document.addEventListener('DOMContentLoaded', () => {
        $('#filtro-executivo').addEventListener('change', () => {
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
    });
})();
