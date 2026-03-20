/* Leads V2 — Dashboard de Prospecção */

const SEL_CLS = 'text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1 text-gray-700 focus:outline-none focus:border-gray-400 w-full';

let selectedLeadId = null;
let selectedLeadData = null;
let importParsedLeads = [];
let searchTimeout = null;

// ======================== Init ========================

document.addEventListener('DOMContentLoaded', () => {
    loadLinks();
});

function getExecutivoId() {
    return document.getElementById('filtro_executivo').value;
}

function onExecutivoChange() {
    selectedLeadId = null;
    selectedLeadData = null;
    loadLeads();
    clearColumns();
}

function clearColumns() {
    document.getElementById('col_status').innerHTML = '<div class="leads-empty">Selecione um lead</div>';
    document.getElementById('col_atividades').innerHTML = '<div class="leads-empty">Selecione um lead</div>';
    document.getElementById('col_extrair').innerHTML = '<div class="leads-empty">Selecione um lead</div>';
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadLeads(), 350);
}

// ======================== Col 1: Cards ========================

async function loadLeads() {
    const execId = getExecutivoId();
    if (!execId) {
        document.getElementById('leads_cards').innerHTML = '<div class="leads-empty">Selecione um executivo</div>';
        document.getElementById('leads_count').textContent = '0';
        return;
    }
    const potencial = document.getElementById('filtro_potencial').value;
    const search = document.getElementById('search_leads').value;
    let url = `/api/leads?id_executivo=${execId}`;
    if (potencial) url += `&potencial=${potencial}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        const container = document.getElementById('leads_cards');
        document.getElementById('leads_count').textContent = data.leads.length;

        if (data.leads.length === 0) {
            container.innerHTML = '<div class="leads-empty">Nenhum lead encontrado</div>';
            return;
        }

        container.innerHTML = data.leads.map(l => `
            <div class="lead-card ${l.id === selectedLeadId ? 'lead-card-active' : ''}"
                 onclick="selectLead(${l.id})" data-lead-id="${l.id}">
                <div class="flex justify-between items-start mb-1">
                    <span class="font-semibold text-sm truncate flex-1">${esc(l.nome_lead)}</span>
                    <span class="badge badge-xs ${l.tipo_lead === 'agencia' ? 'badge-secondary' : 'badge-accent'}">${l.tipo_lead === 'agencia' ? 'AG' : 'CL'}</span>
                </div>
                ${l.contato_principal_nome ? `<div class="text-xs text-gray-500 truncate">${esc(l.contato_principal_nome)}</div>` : ''}
                <div class="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    <span class="badge badge-xs badge-outline">${esc(l.fonte || '-')}</span>
                    <span class="badge badge-xs ${potencialBadge(l.potencial)}">${esc(l.potencial || 'medio')}</span>
                    <span class="text-[10px] text-gray-400">${l.qtd_contatos} contato${l.qtd_contatos !== 1 ? 's' : ''}</span>
                    <span class="text-[10px] ml-auto ${l.dias_sem_atividade > 7 ? 'text-error font-semibold' : 'text-gray-400'}">
                        ${l.dias_sem_atividade != null ? l.dias_sem_atividade + 'd' : '-'}
                    </span>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('loadLeads:', e);
    }
}

function potencialBadge(p) {
    if (p === 'alto') return 'badge-success';
    if (p === 'baixo') return 'badge-warning';
    return 'badge-ghost';
}

async function selectLead(leadId) {
    selectedLeadId = leadId;
    document.querySelectorAll('.lead-card').forEach(c => c.classList.remove('lead-card-active'));
    const card = document.querySelector(`[data-lead-id="${leadId}"]`);
    if (card) card.classList.add('lead-card-active');

    await Promise.all([
        loadLeadStatus(leadId),
        loadLeadAtividades(leadId),
        loadLeadExtrair(leadId),
    ]);
}

// ======================== Col 2: Status + Contatos ========================

async function loadLeadStatus(leadId) {
    const col = document.getElementById('col_status');
    col.innerHTML = '<div class="flex justify-center p-4"><span class="loading loading-spinner"></span></div>';

    try {
        const [detResp, conResp] = await Promise.all([
            fetch(`/api/leads/${leadId}/detalhes`),
            fetch(`/api/leads/${leadId}/contatos`),
        ]);
        const det = await detResp.json();
        const con = await conResp.json();
        if (!det.success) throw new Error(det.message);

        selectedLeadData = det.lead;
        const lead = det.lead;
        const contatos = con.contatos || [];

        const statusOptions = ['inbox','contato','qualificado','proposta','negociacao'].map(s =>
            `<option value="${s}" ${lead.status === s ? 'selected' : ''}>${s.replace('_',' ')}</option>`
        ).join('');

        const potencialOptions = ['alto','medio','baixo'].map(p =>
            `<option value="${p}" ${lead.potencial === p ? 'selected' : ''}>${p}</option>`
        ).join('');

        let html = `
            <div class="p-3 space-y-3">
                <div class="font-semibold text-sm">${esc(lead.empresa || lead.nome || 'Sem nome')}</div>

                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="text-[10px] text-gray-400 uppercase">Status</label>
                        <select onchange="updateStatus('status', this.value)" class="${SEL_CLS}">${statusOptions}</select>
                    </div>
                    <div>
                        <label class="text-[10px] text-gray-400 uppercase">Potencial</label>
                        <select onchange="updateStatus('potencial', this.value)" class="${SEL_CLS}">${potencialOptions}</select>
                    </div>
                </div>

                ${lead.executivo_nome ? `<div class="text-xs text-gray-500">Responsável: ${esc(lead.executivo_nome)}</div>` : ''}

                <div class="divider text-xs m-0">Contatos (${contatos.length})</div>

                <div class="space-y-2" id="contatos_list">
                    ${contatos.map(c => renderContato(c)).join('')}
                </div>

                <button onclick="showAddContato()" class="btn btn-xs btn-outline btn-primary w-full">+ Adicionar contato</button>
                <div id="form_add_contato" class="hidden"></div>

                <div class="divider text-xs m-0">Ações</div>

                <div class="flex gap-2">
                    <button onclick="converterCliente()" class="btn btn-xs btn-success flex-1">Converter em Cliente</button>
                    <button onclick="openDesqualificar()" class="btn btn-xs btn-error flex-1">Desqualificar</button>
                </div>
            </div>
        `;
        col.innerHTML = html;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function renderContato(c) {
    const whatsappLink = c.telefone ? `https://wa.me/${c.telefone.replace(/\D/g, '')}` : '';
    const mailtoLink = c.email ? `mailto:${c.email}` : '';
    return `
        <div class="bg-base-200 rounded-lg p-2 text-xs relative group">
            <div class="flex items-center gap-1">
                <span class="font-semibold">${esc(c.nome)}</span>
                ${c.principal ? '<span class="badge badge-xs badge-primary">principal</span>' : ''}
            </div>
            ${c.cargo ? `<div class="text-gray-500">${esc(c.cargo)}</div>` : ''}
            <div class="flex gap-2 mt-1">
                ${whatsappLink ? `<a href="${whatsappLink}" target="_blank" class="link link-success text-[10px]">WhatsApp</a>` : ''}
                ${mailtoLink ? `<a href="${mailtoLink}" class="link link-info text-[10px]">Email</a>` : ''}
            </div>
            <div class="absolute top-1 right-1 hidden group-hover:flex gap-1">
                ${!c.principal ? `<button onclick="setPrincipal(${c.id})" class="btn btn-ghost btn-xs" title="Tornar principal">★</button>` : ''}
                <button onclick="editContato(${c.id}, ${JSON.stringify(esc(c.nome)).replace(/"/g, '&quot;')}, ${JSON.stringify(esc(c.cargo||'')).replace(/"/g, '&quot;')}, ${JSON.stringify(esc(c.telefone||'')).replace(/"/g, '&quot;')}, ${JSON.stringify(esc(c.email||'')).replace(/"/g, '&quot;')})" class="btn btn-ghost btn-xs" title="Editar">✎</button>
                <button onclick="deleteContato(${c.id})" class="btn btn-ghost btn-xs text-error" title="Excluir">✕</button>
            </div>
        </div>
    `;
}

async function updateStatus(field, value) {
    if (!selectedLeadId) return;
    try {
        const body = {};
        body[field] = value;
        await fetch(`/api/leads/${selectedLeadId}/status`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        loadLeads();
    } catch (e) { console.error('updateStatus:', e); }
}

function showAddContato() {
    const div = document.getElementById('form_add_contato');
    div.classList.remove('hidden');
    div.innerHTML = `
        <div class="bg-base-200 rounded-lg p-2 space-y-1 mt-2">
            <input id="nc_nome" class="input input-xs input-bordered w-full" placeholder="Nome *">
            <input id="nc_cargo" class="input input-xs input-bordered w-full" placeholder="Cargo">
            <input id="nc_telefone" class="input input-xs input-bordered w-full" placeholder="Telefone">
            <input id="nc_email" class="input input-xs input-bordered w-full" placeholder="Email">
            <div class="flex gap-1 mt-1">
                <button onclick="addContato()" class="btn btn-xs btn-primary flex-1">Salvar</button>
                <button onclick="document.getElementById('form_add_contato').classList.add('hidden')" class="btn btn-xs btn-ghost flex-1">Cancelar</button>
            </div>
        </div>
    `;
}

async function addContato() {
    if (!selectedLeadId) return;
    const nome = document.getElementById('nc_nome').value.trim();
    if (!nome) return alert('Nome obrigatório');
    try {
        await fetch(`/api/leads/${selectedLeadId}/contatos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome,
                cargo: document.getElementById('nc_cargo').value.trim(),
                telefone: document.getElementById('nc_telefone').value.trim(),
                email: document.getElementById('nc_email').value.trim(),
            }),
        });
        loadLeadStatus(selectedLeadId);
        loadLeads();
    } catch (e) { console.error('addContato:', e); }
}

function editContato(id, nome, cargo, telefone, email) {
    const newNome = prompt('Nome:', nome);
    if (newNome === null) return;
    const newCargo = prompt('Cargo:', cargo);
    const newTelefone = prompt('Telefone:', telefone);
    const newEmail = prompt('Email:', email);
    fetch(`/api/leads/contatos/${id}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome: newNome, cargo: newCargo, telefone: newTelefone, email: newEmail}),
    }).then(() => { loadLeadStatus(selectedLeadId); loadLeads(); });
}

async function deleteContato(id) {
    if (!confirm('Excluir este contato?')) return;
    await fetch(`/api/leads/contatos/${id}`, {method: 'DELETE'});
    loadLeadStatus(selectedLeadId);
    loadLeads();
}

async function setPrincipal(contatoId) {
    if (!selectedLeadId) return;
    await fetch(`/api/leads/contatos/${contatoId}/principal`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({lead_id: selectedLeadId}),
    });
    loadLeadStatus(selectedLeadId);
    loadLeads();
}

async function converterCliente() {
    if (!selectedLeadId) return;
    if (!confirm('Converter este lead em cliente? Esta ação não pode ser desfeita.')) return;
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/converter-cliente`, {method: 'POST'});
        const data = await resp.json();
        if (data.success) {
            alert('Lead convertido em cliente com sucesso!');
            selectedLeadId = null;
            clearColumns();
            loadLeads();
        } else {
            alert(data.message || 'Erro ao converter');
        }
    } catch (e) { alert('Erro: ' + e.message); }
}

function openDesqualificar() {
    if (!selectedLeadId) return;
    document.getElementById('motivo_desqualificacao').value = '';
    document.getElementById('modal_desqualificar').showModal();
}

async function confirmDesqualificar() {
    const motivo = document.getElementById('motivo_desqualificacao').value;
    if (!motivo) return alert('Selecione um motivo');
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/desqualificar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({motivo}),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_desqualificar').close();
            selectedLeadId = null;
            clearColumns();
            loadLeads();
        } else {
            alert(data.message || 'Erro');
        }
    } catch (e) { alert('Erro: ' + e.message); }
}

// ======================== Col 3: Atividades ========================

async function loadLeadAtividades(leadId) {
    const col = document.getElementById('col_atividades');
    col.innerHTML = '<div class="flex justify-center p-4"><span class="loading loading-spinner"></span></div>';

    try {
        const [ativResp, conResp] = await Promise.all([
            fetch(`/api/leads/${leadId}/atividades`),
            fetch(`/api/leads/${leadId}/contatos`),
        ]);
        const ativData = await ativResp.json();
        const conData = await conResp.json();
        const contatos = conData.contatos || [];
        const atividades = ativData.atividades || [];

        const tipoOptions = [
            'nota','tentativa_contato','ligacao','reuniao','email_enviado',
            'whatsapp','apresentacao','follow_up','proposta_enviada','outro'
        ].map(t => `<option value="${t}">${t.replace('_',' ')}</option>`).join('');

        const contatoOptions = `<option value="">Geral</option>` +
            contatos.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('');

        let html = `
            <div class="p-3 space-y-3">
                <div class="bg-base-200 rounded-lg p-2 space-y-1">
                    <select id="ativ_tipo" class="${SEL_CLS}">${tipoOptions}</select>
                    <select id="ativ_contato" class="${SEL_CLS}">${contatoOptions}</select>
                    <textarea id="ativ_descricao" rows="3" class="textarea textarea-xs textarea-bordered w-full" placeholder="Descrição da atividade..."></textarea>
                    <div class="flex gap-1">
                        <button onclick="melhorarTexto()" class="btn btn-xs btn-ghost flex-1">Melhorar com IA</button>
                        <button onclick="addAtividade()" class="btn btn-xs btn-primary flex-1">Incluir</button>
                    </div>
                </div>

                <div class="divider text-xs m-0">Histórico</div>

                <div class="space-y-2">
                    ${atividades.length === 0 ? '<div class="text-xs text-gray-400 text-center">Nenhuma atividade</div>' :
                      atividades.map(a => `
                        <div class="border-l-2 border-primary pl-2 py-1">
                            <div class="flex items-center gap-1">
                                <span class="badge badge-xs badge-outline">${esc(a.tipo.replace('_',' '))}</span>
                                <span class="text-[10px] text-gray-400">${esc(a.created_at)}</span>
                            </div>
                            <div class="text-xs mt-0.5">${esc(a.descricao || '')}</div>
                            ${a.contato_nome ? `<div class="text-[10px] text-gray-400">→ ${esc(a.contato_nome)}</div>` : ''}
                            ${a.usuario_nome ? `<div class="text-[10px] text-gray-400">por ${esc(a.usuario_nome)}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        col.innerHTML = html;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

async function addAtividade() {
    if (!selectedLeadId) return;
    const descricao = document.getElementById('ativ_descricao').value.trim();
    if (!descricao) return alert('Descrição obrigatória');
    const tipo = document.getElementById('ativ_tipo').value;
    const id_contato = document.getElementById('ativ_contato').value || null;

    try {
        await fetch(`/api/leads/${selectedLeadId}/atividades`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tipo, descricao, id_contato}),
        });
        loadLeadAtividades(selectedLeadId);
        loadLeads();
    } catch (e) { console.error('addAtividade:', e); }
}

async function melhorarTexto() {
    const textarea = document.getElementById('ativ_descricao');
    const texto = textarea.value.trim();
    if (!texto) return alert('Digite um texto primeiro');

    try {
        textarea.disabled = true;
        const resp = await fetch('/api/ia/melhorar-texto', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texto}),
        });
        const data = await resp.json();
        if (data.success) {
            const usar = confirm('Texto sugerido:\n\n' + data.texto + '\n\nUsar este texto?');
            if (usar) textarea.value = data.texto;
        } else {
            alert(data.message || 'Erro ao melhorar texto');
        }
    } catch (e) { alert('Erro: ' + e.message); }
    finally { textarea.disabled = false; }
}

// ======================== Col 4: Extrair Informações ========================

async function loadLeadExtrair(leadId) {
    const col = document.getElementById('col_extrair');

    try {
        const resp = await fetch(`/api/leads/${leadId}/detalhes`);
        const data = await resp.json();
        const lead = data.lead;

        let dadosHtml = '';
        if (lead.dados_extraidos) {
            const d = typeof lead.dados_extraidos === 'string' ? JSON.parse(lead.dados_extraidos) : lead.dados_extraidos;
            dadosHtml = renderDadosExtraidos(d, lead);
        }

        col.innerHTML = `
            <div class="p-3 space-y-3">
                <div class="bg-base-200 rounded-lg p-2 space-y-1">
                    <input id="extrair_url" type="url" class="input input-xs input-bordered w-full" placeholder="https://..."
                           value="${esc(lead.url_site || '')}">
                    <button onclick="extractUrl()" class="btn btn-xs btn-primary w-full" id="btn_extrair">
                        <span class="loading loading-spinner loading-xs hidden" id="extrair_spinner"></span>
                        Extrair com IA
                    </button>
                </div>
                <div id="extrair_resultado">${dadosHtml}</div>
            </div>
        `;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function renderDadosExtraidos(d, lead) {
    const redes = d.redes_sociais || lead?.redes_sociais || {};
    const redesLinks = Object.entries(redes)
        .filter(([, v]) => v)
        .map(([k, v]) => `<a href="${v}" target="_blank" class="link link-primary text-xs">${k}</a>`)
        .join(' ');

    const servicos = (d.servicos || lead?.servicos || []);
    const clientes = (d.clientes_mencionados || lead?.clientes_mencionados || []);
    const contatos = d.contatos_encontrados || [];

    return `
        <div class="space-y-2 text-xs">
            ${d.nome_empresa ? `<div><span class="font-semibold">Empresa:</span> ${esc(d.nome_empresa)}</div>` : ''}
            ${d.descricao ? `<div><span class="font-semibold">Descrição:</span> ${esc(d.descricao)}</div>` : ''}
            ${d.segmento ? `<div><span class="font-semibold">Segmento:</span> ${esc(d.segmento)}</div>` : ''}
            ${redesLinks ? `<div><span class="font-semibold">Redes:</span> ${redesLinks}</div>` : ''}
            ${servicos.length ? `<div><span class="font-semibold">Serviços:</span> ${servicos.map(s => esc(s)).join(', ')}</div>` : ''}
            ${clientes.length ? `<div><span class="font-semibold">Clientes mencionados:</span> ${clientes.map(s => esc(s)).join(', ')}</div>` : ''}
            ${d.telefones_gerais?.length ? `<div><span class="font-semibold">Telefones:</span> ${d.telefones_gerais.join(', ')}</div>` : ''}
            ${d.emails_gerais?.length ? `<div><span class="font-semibold">Emails:</span> ${d.emails_gerais.join(', ')}</div>` : ''}
            ${d.endereco ? `<div><span class="font-semibold">Endereço:</span> ${esc(d.endereco)}</div>` : ''}

            ${contatos.length ? `
                <div class="divider text-xs m-0">Contatos encontrados</div>
                ${contatos.map((c, i) => `
                    <div class="bg-base-100 rounded p-1.5 flex justify-between items-center">
                        <div>
                            <div class="font-semibold">${esc(c.nome || '?')}</div>
                            <div class="text-gray-500">${[c.cargo, c.email, c.telefone].filter(Boolean).map(v => esc(v)).join(' | ')}</div>
                        </div>
                        <button onclick="addExtractedContact(${i})" class="btn btn-xs btn-outline btn-primary">+ Adicionar</button>
                    </div>
                `).join('')}
            ` : ''}

            <button onclick="saveExtracted()" class="btn btn-xs btn-success w-full mt-2">Salvar dados no lead</button>
        </div>
    `;
}

let lastExtractedData = null;

async function extractUrl() {
    if (!selectedLeadId) return;
    const url = document.getElementById('extrair_url').value.trim();
    if (!url) return alert('Cole uma URL');

    const btn = document.getElementById('btn_extrair');
    const spinner = document.getElementById('extrair_spinner');
    btn.disabled = true;
    spinner.classList.remove('hidden');

    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/extrair-url`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url}),
        });
        const data = await resp.json();
        if (data.success) {
            lastExtractedData = data.dados;
            lastExtractedData._url = url;
            document.getElementById('extrair_resultado').innerHTML = renderDadosExtraidos(data.dados, selectedLeadData);
        } else {
            alert(data.message || 'Erro na extração');
        }
    } catch (e) { alert('Erro: ' + e.message); }
    finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

async function saveExtracted() {
    if (!selectedLeadId || !lastExtractedData) return alert('Extraia dados primeiro');
    const d = lastExtractedData;
    try {
        await fetch(`/api/leads/${selectedLeadId}/salvar-dados-extraidos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url_site: d._url || '',
                descricao_empresa: d.descricao || '',
                segmento: d.segmento || '',
                redes_sociais: d.redes_sociais || {},
                servicos: d.servicos || [],
                clientes_mencionados: d.clientes_mencionados || [],
                dados_extraidos: d,
            }),
        });
        alert('Dados salvos!');
    } catch (e) { alert('Erro: ' + e.message); }
}

async function addExtractedContact(idx) {
    if (!selectedLeadId || !lastExtractedData) return;
    const c = lastExtractedData.contatos_encontrados[idx];
    if (!c) return;
    if (!confirm(`Adicionar ${c.nome || '?'} como contato?`)) return;

    try {
        await fetch(`/api/leads/${selectedLeadId}/contatos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome: c.nome || '',
                cargo: c.cargo || '',
                telefone: c.telefone || '',
                email: c.email || '',
            }),
        });
        loadLeadStatus(selectedLeadId);
        loadLeads();
    } catch (e) { alert('Erro: ' + e.message); }
}

// ======================== Col 5: Links Úteis ========================

async function loadLinks() {
    const col = document.getElementById('col_links');
    try {
        const resp = await fetch('/api/leads/links-uteis');
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        const links = data.links || [];
        if (links.length === 0) {
            col.innerHTML = '<div class="leads-empty">Nenhum link cadastrado</div>';
            return;
        }

        const grouped = {};
        links.forEach(l => {
            const cat = l.categoria || 'Outros';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(l);
        });

        col.innerHTML = `<div class="p-3 space-y-3">` +
            Object.entries(grouped).map(([cat, items]) => `
                <div>
                    <div class="text-[10px] font-semibold text-gray-400 uppercase mb-1">${esc(cat)}</div>
                    ${items.map(l => `
                        <a href="${esc(l.url)}" target="_blank" class="block text-xs link link-primary py-0.5 truncate">${esc(l.titulo)}</a>
                    `).join('')}
                </div>
            `).join('') +
        `</div>`;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

// ======================== Import Modal ========================

function openImportModal() {
    if (!getExecutivoId()) return alert('Selecione um executivo primeiro');
    document.getElementById('import_step1').classList.remove('hidden');
    document.getElementById('import_step2').classList.add('hidden');
    document.getElementById('import_texto').value = '';
    document.getElementById('modal_importar').showModal();
}

async function processImport() {
    const texto = document.getElementById('import_texto').value.trim();
    if (!texto) return alert('Cole os dados dos leads');

    const btn = document.getElementById('btn_processar');
    const spinner = document.getElementById('import_spinner');
    btn.disabled = true;
    spinner.classList.remove('hidden');

    try {
        const tipoLead = document.querySelector('input[name="tipo_lead_import"]:checked').value;
        const resp = await fetch('/api/leads/processar-importacao', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texto_bruto: texto, tipo_lead: tipoLead}),
        });
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        importParsedLeads = data.leads.map((l, i) => ({...l, _selected: true, _idx: i}));
        renderImportPreview();

        document.getElementById('import_step1').classList.add('hidden');
        document.getElementById('import_step2').classList.remove('hidden');
    } catch (e) { alert('Erro ao processar: ' + e.message); }
    finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

function renderImportPreview() {
    const container = document.getElementById('import_preview');
    container.innerHTML = importParsedLeads.map((l, i) => `
        <div class="bg-base-200 rounded-lg p-3">
            <label class="flex items-center gap-2 mb-2 cursor-pointer">
                <input type="checkbox" class="checkbox checkbox-sm checkbox-primary"
                       ${l._selected ? 'checked' : ''} onchange="importParsedLeads[${i}]._selected = this.checked">
                <span class="font-semibold text-sm">${esc(l.empresa)}</span>
            </label>
            <div class="space-y-1 ml-6">
                ${(l.contatos || []).map(c => `
                    <div class="text-xs text-gray-600">
                        ${esc(c.nome)}${c.cargo ? ` (${esc(c.cargo)})` : ''}
                        ${c.telefone ? ` | ${esc(c.telefone)}` : ''}
                        ${c.email ? ` | ${esc(c.email)}` : ''}
                        ${c.principal ? ' ★' : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function backToStep1() {
    document.getElementById('import_step1').classList.remove('hidden');
    document.getElementById('import_step2').classList.add('hidden');
}

async function confirmImport() {
    const selected = importParsedLeads.filter(l => l._selected);
    if (selected.length === 0) return alert('Selecione ao menos um lead');

    const execId = getExecutivoId();
    const tipoLead = document.querySelector('input[name="tipo_lead_import"]:checked').value;

    try {
        const resp = await fetch('/api/leads/importar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                leads: selected.map(l => ({empresa: l.empresa, contatos: l.contatos})),
                id_executivo: parseInt(execId),
                tipo_lead: tipoLead,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_importar').close();
            alert(`${data.total} lead(s) importado(s)!`);
            loadLeads();
        } else {
            alert(data.message || 'Erro ao importar');
        }
    } catch (e) { alert('Erro: ' + e.message); }
}

// ======================== Util ========================

function esc(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}
