(function () {
    'use strict';

    const BASE = '/sales-war-room';
    let clienteSelecionadoId = null;
    let contatoSelecionadoId = null;
    let modalContatoId = null;
    let modalClienteId = null;
    let chartInstances = {};
    let historicoPage = 1;

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
        historicoPage = 1;
        carregarStatus(id);
        carregarHistorico(id);
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
                            <div class="text-lg font-bold">${s.total_pis}</div>
                            <div class="text-xs opacity-60">PIs</div>
                        </div>
                        <div class="bg-base-200 rounded p-2">
                            <div class="text-lg font-bold">${s.pis_concluidos}</div>
                            <div class="text-xs opacity-60">PIs Concluídos</div>
                        </div>
                    </div>
                    <button class="btn btn-xs btn-outline w-full" id="btn-ver-mais-status">Ver mais dados</button>
                </div>

                <div class="divider text-xs my-2">Histórico</div>

                <div id="historico-container"></div>

                <div class="mt-2">
                    <div class="flex gap-1">
                        <input type="text" id="input-historico" class="input input-bordered input-xs flex-1" placeholder="Novo registro..." />
                        <button class="btn btn-xs btn-primary" id="btn-add-historico">Incluir</button>
                    </div>
                    <div id="ia-historico-preview" class="hidden mt-2 bg-base-200 rounded p-2 text-xs">
                        <div id="ia-historico-texto"></div>
                        <div class="flex gap-1 mt-1">
                            <button class="btn btn-xs btn-success" id="btn-ia-hist-aceitar">Aceitar</button>
                            <button class="btn btn-xs btn-ghost" id="btn-ia-hist-editar">Editar</button>
                            <button class="btn btn-xs btn-ghost" id="btn-ia-hist-cancelar">Cancelar</button>
                        </div>
                    </div>
                </div>
            `;

            carregarHistoricoTabela(clienteId);
            bindStatusEvents(clienteId);
        } catch (e) {
            showEmpty(container, 'Erro ao carregar status.');
            console.error(e);
        }
    }

    async function carregarHistoricoTabela(clienteId) {
        const container = $('#historico-container');
        if (!container) return;
        try {
            const data = await api(`/api/cliente/${clienteId}/historico?page=${historicoPage}`);
            if (!data.registros.length) {
                container.innerHTML = '<div class="text-xs opacity-50 text-center py-2">Sem histórico.</div>';
                return;
            }
            container.innerHTML = `
                <div class="space-y-2">
                    ${data.registros.map(r => `
                        <div class="bg-base-200 rounded p-2 text-xs swr-fade-in">
                            <div class="flex justify-between opacity-60 mb-1">
                                <span>${fmtDate(r.data_registro)}</span>
                                <span>${r.autor || ''}</span>
                            </div>
                            <div>${r.texto}</div>
                        </div>
                    `).join('')}
                </div>
                ${data.pages > 1 ? `
                    <div class="flex justify-center gap-1 mt-2">
                        ${historicoPage > 1 ? '<button class="btn btn-xs btn-ghost" id="hist-prev">Anterior</button>' : ''}
                        <span class="text-xs opacity-60 self-center">${historicoPage}/${data.pages}</span>
                        ${historicoPage < data.pages ? '<button class="btn btn-xs btn-ghost" id="hist-next">Próxima</button>' : ''}
                    </div>
                ` : ''}
            `;

            const btnPrev = $('#hist-prev');
            const btnNext = $('#hist-next');
            if (btnPrev) btnPrev.addEventListener('click', () => { historicoPage--; carregarHistoricoTabela(clienteId); });
            if (btnNext) btnNext.addEventListener('click', () => { historicoPage++; carregarHistoricoTabela(clienteId); });
        } catch (e) {
            container.innerHTML = '<div class="text-xs text-error">Erro ao carregar histórico.</div>';
        }
    }

    function bindStatusEvents(clienteId) {
        let textoOriginal = '';
        let textoMelhorado = '';

        $('#btn-ver-mais-status')?.addEventListener('click', () => abrirModalStatusCompleto(clienteId));

        $('#btn-add-historico')?.addEventListener('click', async () => {
            textoOriginal = $('#input-historico').value.trim();
            if (!textoOriginal) return;

            const btn = $('#btn-add-historico');
            btn.classList.add('loading');
            try {
                const data = await api('/api/ia/melhorar-texto', {
                    method: 'POST',
                    body: JSON.stringify({ texto: textoOriginal, contexto: 'historico_comercial' })
                });
                textoMelhorado = data.texto_melhorado;
                $('#ia-historico-texto').textContent = textoMelhorado;
                $('#ia-historico-preview').classList.remove('hidden');
            } catch (e) {
                textoMelhorado = textoOriginal;
                await salvarHistorico(clienteId, textoOriginal);
            } finally {
                btn.classList.remove('loading');
            }
        });

        $('#btn-ia-hist-aceitar')?.addEventListener('click', () => salvarHistorico(clienteId, textoMelhorado));
        $('#btn-ia-hist-editar')?.addEventListener('click', () => {
            $('#input-historico').value = textoMelhorado;
            $('#ia-historico-preview').classList.add('hidden');
        });
        $('#btn-ia-hist-cancelar')?.addEventListener('click', () => {
            $('#ia-historico-preview').classList.add('hidden');
        });
    }

    async function salvarHistorico(clienteId, texto) {
        try {
            await api(`/api/cliente/${clienteId}/historico`, {
                method: 'POST',
                body: JSON.stringify({ texto })
            });
            $('#input-historico').value = '';
            $('#ia-historico-preview')?.classList.add('hidden');
            historicoPage = 1;
            carregarHistoricoTabela(clienteId);
        } catch (e) {
            console.error(e);
            alert('Erro ao salvar histórico.');
        }
    }

    function carregarHistorico(clienteId) {
        carregarHistoricoTabela(clienteId);
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
                            </div>
                            <div class="flex items-center gap-1">
                                ${semAtividade ? '<svg class="w-3.5 h-3.5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z"/></svg>' : ''}
                                ${tel ? `<a href="https://wa.me/55${tel}" target="_blank" class="btn btn-ghost btn-xs btn-circle" title="WhatsApp" onclick="event.stopPropagation()"><svg class="w-3.5 h-3.5 text-success" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2z"/></svg></a>` : ''}
                                ${c.email ? `<a href="mailto:${c.email}" class="btn btn-ghost btn-xs btn-circle" title="Email" onclick="event.stopPropagation()"><svg class="w-3.5 h-3.5 text-info" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg></a>` : ''}
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
                el.addEventListener('dblclick', () => {
                    abrirModalContato(parseInt(el.dataset.id));
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

    async function carregarAtividades(clienteId, contatoId) {
        const container = $('#lista-atividades');
        showSpinner(container);
        try {
            const params = new URLSearchParams();
            if (contatoId) params.set('contato_id', contatoId);
            const data = await api(`/api/cliente/${clienteId}/atividades?${params}`);

            let html = '';
            if (!data.atividades.length) {
                html = '<div class="swr-empty-state">Nenhuma atividade.</div>';
            } else {
                html = data.atividades.map(a => {
                    const statusBadge = {
                        pendente: 'badge-warning',
                        em_andamento: 'badge-info',
                        concluida: 'badge-success'
                    };
                    const statusLabel = {
                        pendente: 'Pendente',
                        em_andamento: 'Em andamento',
                        concluida: 'Concluída'
                    };
                    return `
                        <div class="bg-base-200 rounded p-2 text-xs swr-fade-in mb-1.5">
                            <div class="flex items-center justify-between mb-1">
                                <span class="badge badge-xs ${statusBadge[a.status] || ''}">${statusLabel[a.status] || a.status}</span>
                                <span class="opacity-50">${fmtDate(a.data_atividade)}</span>
                            </div>
                            <div class="mb-1">${a.descricao}</div>
                            <div class="flex items-center justify-between">
                                <span class="opacity-50">${a.contato_nome ? 'Contato: ' + a.contato_nome : ''}</span>
                                <select class="text-xs bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5 text-gray-700 focus:outline-none focus:border-gray-400 appearance-none swr-status-select" data-id="${a.id}">
                                    <option value="pendente" ${a.status === 'pendente' ? 'selected' : ''}>Pendente</option>
                                    <option value="em_andamento" ${a.status === 'em_andamento' ? 'selected' : ''}>Em andamento</option>
                                    <option value="concluida" ${a.status === 'concluida' ? 'selected' : ''}>Concluída</option>
                                </select>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            html += `
                <div class="divider text-xs my-2">Nova atividade</div>
                <div class="space-y-1">
                    <textarea id="input-atividade" class="textarea textarea-bordered textarea-xs w-full" rows="2" placeholder="Descrição..."></textarea>
                    <div class="flex gap-1">
                        <input type="date" id="input-atividade-data" class="input input-bordered input-xs flex-1" />
                        <button class="btn btn-xs btn-primary" id="btn-add-atividade">Incluir</button>
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
                    } catch (e) {
                        console.error(e);
                        alert('Erro ao atualizar status.');
                    }
                });
            });

            $('#btn-add-atividade')?.addEventListener('click', async () => {
                const descricao = $('#input-atividade').value.trim();
                const dataAtiv = $('#input-atividade-data').value;
                if (!descricao || !dataAtiv) { alert('Preencha descrição e data.'); return; }

                const btn = $('#btn-add-atividade');
                btn.classList.add('loading');
                try {
                    let textoFinal = descricao;
                    try {
                        const ia = await api('/api/ia/melhorar-texto', {
                            method: 'POST',
                            body: JSON.stringify({ texto: descricao, contexto: 'atividade_comercial' })
                        });
                        textoFinal = ia.texto_melhorado || descricao;
                    } catch (_) { /* fallback to original */ }

                    await api(`/api/cliente/${clienteId}/atividades`, {
                        method: 'POST',
                        body: JSON.stringify({
                            descricao: textoFinal,
                            data_atividade: dataAtiv,
                            contato_id: contatoId || null
                        })
                    });
                    carregarAtividades(clienteId, contatoId);
                } catch (e) {
                    console.error(e);
                    alert('Erro ao criar atividade.');
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
                <div class="mb-2">
                    <div class="flex gap-1">
                        <input type="text" id="input-objetivo" class="input input-bordered input-xs flex-1" placeholder="Novo objetivo..." />
                        <button class="btn btn-xs btn-primary" id="btn-add-objetivo">+</button>
                    </div>
                </div>
                <button class="btn btn-xs btn-outline btn-secondary w-full mb-2" id="btn-sugerir-ia">
                    Sugerir objetivos com IA
                </button>
                <div id="ia-sugestoes" class="hidden mb-2"></div>
            `;

            if (ativos.length) {
                html += '<div class="text-xs font-semibold opacity-60 mb-1">Ativos</div>';
                html += ativos.map(o => `
                    <div class="flex items-start gap-2 py-1 swr-fade-in">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check" data-id="${o.id}" />
                        <span class="text-xs flex-1">${o.texto}</span>
                    </div>
                `).join('');
            }

            if (conquistados.length) {
                html += '<div class="divider text-xs my-2">Conquistados</div>';
                html += conquistados.map(o => `
                    <div class="flex items-start gap-2 py-1 opacity-50 swr-fade-in">
                        <input type="checkbox" class="checkbox checkbox-xs checkbox-success mt-0.5 swr-obj-check" data-id="${o.id}" checked />
                        <span class="text-xs flex-1 line-through">${o.texto}</span>
                        <span class="text-xs opacity-60">${fmtDate(o.data_conquista)}</span>
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
                try {
                    await api(`/api/cliente/${clienteId}/objetivos`, {
                        method: 'POST',
                        body: JSON.stringify({ texto })
                    });
                    carregarObjetivos(clienteId);
                } catch (e) {
                    console.error(e);
                    alert('Erro ao criar objetivo.');
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
                        carregarObjetivos(clienteId);
                    } catch (e) {
                        console.error(e);
                    }
                });
            });

            $('#btn-sugerir-ia')?.addEventListener('click', async () => {
                const btn = $('#btn-sugerir-ia');
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
                    alert('Erro ao obter sugestões da IA.');
                } finally {
                    btn.classList.remove('loading');
                }
            });
        } catch (e) {
            showEmpty(container, 'Erro ao carregar objetivos.');
            console.error(e);
        }
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
            const rc = data.resumo_cotacoes;
            const rp = data.resumo_pis;

            kpisEl.innerHTML = `
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Cotações</div>
                    <div class="stat-value text-lg">${rc.total_cotacoes}</div>
                    <div class="stat-desc text-xs">${fmtBRL(rc.valor_total)}</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Aprovadas</div>
                    <div class="stat-value text-lg">${rc.cotacoes_aprovadas}</div>
                    <div class="stat-desc text-xs">${rc.pct_conversao}% conversão</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">PIs</div>
                    <div class="stat-value text-lg">${rp.total_pis}</div>
                    <div class="stat-desc text-xs">${rp.pis_concluidos} concluídos</div>
                </div>
                <div class="stat bg-base-200 rounded p-2">
                    <div class="stat-title text-xs">Ticket Médio</div>
                    <div class="stat-value text-sm">${fmtBRL(data.ticket_medio)}</div>
                </div>
            `;

            const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
            const dadosMes = new Array(12).fill(null).map((_, i) => {
                const m = data.por_mes.find(p => p.mes === i + 1);
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
            chartInstances['faturamento'] = new Chart(ctxLine, {
                type: 'line',
                data: {
                    labels: meses,
                    datasets: [{
                        label: 'Faturamento',
                        data: dadosMes.map(d => d.faturamento),
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

            tabelaEl.innerHTML = data.cotacoes.map(c => `
                <tr>
                    <td>${c.numero_cotacao || '-'}</td>
                    <td>${c.nome_campanha || '-'}</td>
                    <td>${fmtBRL(c.valor_total_proposta)}</td>
                    <td><span class="badge badge-xs">${c.status_descricao || '-'}</span></td>
                    <td>${fmtDate(c.created_at)}</td>
                </tr>
            `).join('') || '<tr><td colspan="5" class="text-center opacity-50">Sem cotações.</td></tr>';

        } catch (e) {
            kpisEl.innerHTML = '<div class="text-error text-xs col-span-4">Erro ao carregar dados.</div>';
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
                <div><span class="text-xs opacity-60">Telefone</span><div class="text-sm">${c.telefone || '-'}</div></div>
                <div><span class="text-xs opacity-60">Email</span><div class="text-sm">${c.email || '-'}</div></div>
                <div><span class="text-xs opacity-60">Cliente</span><div class="text-sm">${c.cliente_nome || '-'}</div></div>
            `;

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

        if (!objetivo) { alert('Preencha o objetivo da mensagem.'); return; }

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
            alert('Erro ao gerar comunicação.');
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
