/* Leads V2 — Dashboard de Prospecção (Redesign) */

const SEL_CLS = 'text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1 text-gray-700 focus:outline-none focus:border-gray-400 w-full';

let selectedLeadId = null;
let selectedLeadData = null;
let importParsedLeads = [];
let searchTimeout = null;
let showConcluidas = false;

const FREE_DOMAINS = ['gmail.com','yahoo.com','hotmail.com','outlook.com','live.com','icloud.com','aol.com','msn.com','uol.com.br','bol.com.br','terra.com.br','ig.com.br','globo.com','protonmail.com'];

const STATUS_LABELS = {inbox:'Inbox', contato:'Contato', qualificado:'Qualificado', proposta:'Proposta', negociacao:'Negociação'};
const STATUS_LIST = ['inbox','contato','qualificado','proposta','negociacao'];
const POTENCIAL_LIST = ['alto','medio','baixo'];
const POTENCIAL_LABELS = {alto:'Alto', medio:'Médio', baixo:'Baixo'};

const TIPO_ATIV_COLORS = {
    reuniao:'ativ-badge-reuniao', ligacao:'ativ-badge-ligacao', whatsapp:'ativ-badge-whatsapp',
    email_enviado:'ativ-badge-email_enviado', email:'ativ-badge-email', nota:'ativ-badge-nota',
    follow_up:'ativ-badge-follow_up', apresentacao:'ativ-badge-apresentacao',
    proposta_enviada:'ativ-badge-proposta_enviada', tentativa_contato:'ativ-badge-tentativa_contato',
    status_change:'ativ-badge-status_change', outro:'ativ-badge-outro'
};

const DEFAULT_DESCRIPTIONS = {
    ligacao: 'Ligar para o contato para...',
    email_enviado: 'Enviar email de apresentação para...',
    whatsapp: 'Enviar mensagem WhatsApp para...',
    reuniao: 'Agendar reunião com...',
    follow_up: 'Follow-up sobre...',
    apresentacao: 'Apresentação de serviços para...',
    proposta_enviada: 'Enviar proposta comercial para...',
    tentativa_contato: 'Tentativa de contato com...',
    nota: '',
    outro: '',
};

const COMM_TEMPLATES = [
    {label: 'Apresentar CentralComm', objetivo: 'Apresentar a CentralComm como parceira estratégica em comunicação e mídia, destacando expertise em assessoria de imprensa, produção de conteúdo, gestão de redes sociais e formatos inovadores de mídia', tipo: 'email'},
    {label: 'Apresentar Cadu (IA)', objetivo: 'Apresentar o Cadu, assistente de inteligência artificial da CentralComm, destacando como ele automatiza e potencializa a comunicação corporativa com análise de dados, geração de conteúdo e insights estratégicos', tipo: 'whatsapp'},
    {label: 'Detalhar Funcionalidades', objetivo: 'Detalhar as funcionalidades e serviços completos da CentralComm: assessoria de imprensa, produção audiovisual, gestão de redes sociais, planejamento de mídia, comunicação corporativa, eventos e branding', tipo: 'email'},
    {label: 'Apresentar Canais', objetivo: 'Apresentar os canais de comunicação e mídia da CentralComm, incluindo portais, redes sociais, newsletters, podcasts, vídeos e parcerias estratégicas com veículos de imprensa', tipo: 'email'},
    {label: 'Formatos Interativos', objetivo: 'Apresentar os formatos interativos e inovadores de mídia disponíveis na CentralComm: branded content, infográficos interativos, webinars, lives, stories patrocinados e experiências imersivas', tipo: 'email'},
    {label: 'Follow-up pós Reunião', objetivo: 'Follow-up após reunião realizada, reforçar os pontos discutidos, alinhar expectativas e definir próximos passos concretos para a parceria', tipo: 'email'},
    {label: 'Follow-up sem Contato', objetivo: 'Follow-up cordial após tentativas sem retorno, reforçar o valor da parceria e oferecer uma nova oportunidade de conversa sem pressão', tipo: 'whatsapp'},
    {label: 'Convite Evento RJ', objetivo: 'Convite para evento ou encontro exclusivo da CentralComm no Rio de Janeiro, com networking e apresentação de cases e novidades em comunicação e mídia', tipo: 'email'},
    {label: 'Convite Evento BH', objetivo: 'Convite para evento ou encontro exclusivo da CentralComm em Belo Horizonte, com networking e apresentação de cases e novidades em comunicação e mídia', tipo: 'email'},
];

const SOCIAL_ICONS = {
    instagram: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none"/></svg>',
    linkedin: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-4 0v7h-4v-7a6 6 0 016-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
    facebook: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>',
    twitter: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 3a10.9 10.9 0 01-3.14 1.53A4.48 4.48 0 0012 7.5v1A10.66 10.66 0 013 4s-4 9 5 13a11.64 11.64 0 01-7 2c9 5 20 0 20-11.5a4.5 4.5 0 00-.08-.83A7.72 7.72 0 0023 3z"/></svg>',
    youtube: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22.54 6.42a2.78 2.78 0 00-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 00-1.94 2A29 29 0 001 11.75a29 29 0 00.46 5.33A2.78 2.78 0 003.4 19.1c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 001.94-2 29 29 0 00.46-5.25 29 29 0 00-.46-5.33z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02" fill="currentColor" stroke="none"/></svg>'
};

// ======================== Init ========================

document.addEventListener('DOMContentLoaded', () => {
    loadLeads();
    loadLinksContent();
    document.addEventListener('click', closeMiniModals);
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
    document.getElementById('col_comunicacao').innerHTML = '<div class="leads-empty">Selecione um lead</div>';
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadLeads(), 350);
}

function skeletonHtml() {
    return `<div class="skeleton-block">
        <div class="skeleton-line"></div><div class="skeleton-line"></div>
        <div class="skeleton-line"></div><div class="skeleton-line"></div>
    </div>`;
}

// ======================== Col 1: Inbox / Cards ========================

async function loadLeads() {
    const execId = getExecutivoId();
    const potencial = document.getElementById('filtro_potencial').value;
    const search = document.getElementById('search_leads').value;
    const statusFilter = document.getElementById('filtro_status').value;

    let url = '/api/leads?';
    const params = [];

    if (execId) {
        params.push(`id_executivo=${execId}`);
    } else {
        params.push('sem_responsavel=1');
        if (!statusFilter) params.push('status=inbox');
    }

    if (potencial) params.push(`potencial=${potencial}`);
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (statusFilter) params.push(`status=${statusFilter}`);

    url += params.join('&');

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

        container.innerHTML = data.leads.map(l => {
            const alertDays = l.dias_sem_atividade != null && l.dias_sem_atividade > 7;
            return `
            <div class="lead-card ${l.id === selectedLeadId ? 'lead-card-active' : ''}"
                 onclick="selectLead(${l.id})" data-lead-id="${l.id}">
                <div class="flex justify-between items-start mb-0.5">
                    <span class="font-semibold truncate flex-1" style="font-size:12px">${esc(l.nome_lead)}</span>
                    <span class="badge badge-xs ${l.tipo_lead === 'agencia' ? 'badge-secondary' : 'badge-accent'}" style="font-size:9px">${l.tipo_lead === 'agencia' ? 'AG' : 'CL'}</span>
                </div>
                <div class="flex items-center gap-1.5 mt-1 flex-wrap">
                    <span class="badge badge-xs badge-outline" style="font-size:9px">${esc(l.fonte || '-')}</span>
                    <span class="badge badge-xs ${potencialBadge(l.potencial)}" style="font-size:9px">${esc(l.potencial || 'medio')}</span>
                    <span class="status-badge status-badge-${l.status || 'inbox'}" style="font-size:9px;padding:1px 6px">${esc(STATUS_LABELS[l.status] || 'Inbox')}</span>
                    <span style="font-size:10px;color:#9ca3af;display:inline-flex;align-items:center;gap:2px">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                        ${l.qtd_contatos}
                    </span>
                    <span style="font-size:10px;margin-left:auto" class="${alertDays ? 'text-error font-semibold' : 'text-gray-400'}">
                        ${alertDays ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:inline;vertical-align:-1px;margin-right:1px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' : ''}
                        ${l.dias_sem_atividade != null ? l.dias_sem_atividade + 'd' : '-'}
                    </span>
                </div>
            </div>`;
        }).join('');
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

    const skel = skeletonHtml();
    document.getElementById('col_status').innerHTML = skel;
    document.getElementById('col_atividades').innerHTML = skel;
    document.getElementById('col_extrair').innerHTML = skel;
    document.getElementById('col_comunicacao').innerHTML = skel;

    await Promise.all([
        loadLeadStatus(leadId),
        loadLeadAtividades(leadId),
        loadLeadExtrair(leadId),
        loadLeadComunicacao(leadId),
    ]);

    updateLinksSiteSection();
}

// ======================== Mini-modal system ========================

function closeMiniModals(e) {
    if (e && e.target.closest('.mini-modal')) return;
    document.querySelectorAll('.mini-modal-backdrop').forEach(b => b.remove());
    document.querySelectorAll('.mini-modal').forEach(m => m.remove());
}

function openMiniModal(anchorEl, options, currentValue, onSelect) {
    closeMiniModals();
    const rect = anchorEl.getBoundingClientRect();
    const backdrop = document.createElement('div');
    backdrop.className = 'mini-modal-backdrop';
    backdrop.onclick = () => closeMiniModals();

    const modal = document.createElement('div');
    modal.className = 'mini-modal';
    modal.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    modal.style.left = (rect.left + window.scrollX) + 'px';
    modal.innerHTML = options.map(o =>
        `<div class="mini-modal-item ${o.value === currentValue ? 'active' : ''}"
              onclick="event.stopPropagation()" data-value="${o.value}">
            ${o.dot ? `<span style="width:8px;height:8px;border-radius:50%;background:${o.dot};flex-shrink:0"></span>` : ''}
            ${esc(o.label)}
        </div>`
    ).join('');

    modal.querySelectorAll('.mini-modal-item').forEach(item => {
        item.addEventListener('click', () => {
            onSelect(item.dataset.value);
            closeMiniModals();
        });
    });

    document.body.appendChild(backdrop);
    document.body.appendChild(modal);

    const modalRect = modal.getBoundingClientRect();
    if (modalRect.right > window.innerWidth) {
        modal.style.left = (window.innerWidth - modalRect.width - 8) + 'px';
    }
    if (modalRect.bottom > window.innerHeight) {
        modal.style.top = (rect.top + window.scrollY - modalRect.height - 4) + 'px';
    }
}

// ======================== Col 2: Dados do Lead ========================

async function loadLeadStatus(leadId) {
    const col = document.getElementById('col_status');

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

        let html = `<div class="p-3 space-y-3" style="font-size:12px">
            <div class="flex items-center gap-2">
                <span class="font-semibold" style="font-size:13px">${esc(lead.empresa || lead.nome || 'Sem nome')}</span>
                <button onclick="openEditLead()" title="Editar lead" style="color:#9ca3af;background:none;border:none;cursor:pointer;font-size:14px;display:inline-flex;align-items:center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
            </div>

            <div class="status-row">
                <span class="status-row-label">Status</span>
                <span class="status-badge status-badge-${lead.status || 'inbox'}" onclick="openStatusModal(this, '${lead.status || 'inbox'}')">
                    ${esc(STATUS_LABELS[lead.status] || lead.status || 'inbox')} ▾
                </span>
            </div>

            <div class="status-row">
                <span class="status-row-label">Potencial</span>
                <span class="status-badge potencial-badge-${lead.potencial || 'medio'}" onclick="openPotencialModal(this, '${lead.potencial || 'medio'}')">
                    ${esc(POTENCIAL_LABELS[lead.potencial] || 'Médio')} ▾
                </span>
            </div>

            <div class="status-row">
                <span class="status-row-label">Responsável</span>
                <span class="status-badge" style="background:#f3f4f6;color:#374151;cursor:pointer" onclick="openResponsavelModal(this, ${lead.id_executivo || 'null'})">
                    ${lead.executivo_nome ? esc(lead.executivo_nome) : '<span style="color:#9ca3af">Não atribuído</span>'} ▾
                </span>
            </div>

            <div style="border-top:1px solid #f3f4f6;padding-top:8px;margin-top:4px">
                <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin-bottom:6px">Contatos (${contatos.length})</div>
                <div class="space-y-2" id="contatos_list">
                    ${contatos.map((c, i) => renderContato(c, contatos.length)).join('')}
                </div>
            </div>

            <div class="flex items-center gap-3 mt-1">
                <span onclick="showAddContato()" style="font-size:11px;color:#9ca3af;cursor:pointer" class="hover:text-gray-500">+ adicionar contato</span>
                <span onclick="openMergeModal()" style="font-size:11px;color:#9ca3af;cursor:pointer" class="hover:text-gray-500">⤵ mesclar com outro lead</span>
            </div>
            <div id="form_add_contato" class="hidden"></div>

            <div style="border-top:1px solid #f3f4f6;padding-top:8px;margin-top:8px">
                <div style="display:flex;gap:6px;overflow:hidden;max-width:100%">
                    <button onclick="converterCliente()" class="leads-action-btn leads-action-btn-convert" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1 1 0;min-width:0">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0"><polyline points="20 6 9 17 4 12"/></svg>
                        <span style="overflow:hidden;text-overflow:ellipsis">Converter</span>
                    </button>
                    <button onclick="openDesqualificar()" class="leads-action-btn leads-action-btn-disqualify" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1 1 0;min-width:0">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>
                        <span style="overflow:hidden;text-overflow:ellipsis">Desqualificar</span>
                    </button>
                </div>
            </div>
        </div>`;
        col.innerHTML = html;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function openStatusModal(el, currentValue) {
    const statusDots = {inbox:'#9ca3af', contato:'#3b82f6', qualificado:'#22c55e', proposta:'#eab308', negociacao:'#f97316'};
    openMiniModal(el,
        STATUS_LIST.map(s => ({value: s, label: STATUS_LABELS[s], dot: statusDots[s]})),
        currentValue,
        (val) => updateStatus('status', val)
    );
}

function openPotencialModal(el, currentValue) {
    const dots = {alto:'#22c55e', medio:'#eab308', baixo:'#ef4444'};
    openMiniModal(el,
        POTENCIAL_LIST.map(p => ({value: p, label: POTENCIAL_LABELS[p], dot: dots[p]})),
        currentValue,
        (val) => updateStatus('potencial', val)
    );
}

function openResponsavelModal(el, currentId) {
    const executivos = window.EXECUTIVOS || [];
    const options = [
        {value: '0', label: 'Remover responsável', dot: '#ef4444'},
        ...executivos.map(e => ({value: String(e.id), label: e.nome, dot: '#3b82f6'}))
    ];
    openMiniModal(el, options, currentId ? String(currentId) : '', (val) => {
        updateStatus('id_executivo', parseInt(val));
    });
}

function renderContato(c, totalContatos) {
    const phone = c.telefone ? c.telefone.replace(/\D/g, '') : '';
    const whatsappLink = phone ? `https://wa.me/${phone}` : '';
    const mailtoLink = c.email ? `mailto:${c.email}` : '';

    return `
        <div class="contact-card">
            <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-1.5 flex-wrap">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" style="flex-shrink:0"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    <span class="font-semibold" style="font-size:12px">${esc(c.nome)}</span>
                    ${c.principal ? '<span style="background:#dcfce7;color:#15803d;font-size:9px;padding:1px 6px;border-radius:9999px;font-weight:500">principal</span>' : ''}
                </div>
                <div class="contact-actions-hover flex gap-0.5">
                    ${!c.principal ? `<button onclick="setPrincipal(${c.id})" class="btn btn-ghost btn-xs" title="Tornar principal" style="min-height:0;height:22px;padding:0 4px">★</button>` : ''}
                    <button onclick="editContato(${c.id})" class="btn btn-ghost btn-xs" title="Editar" style="min-height:0;height:22px;padding:0 4px">✎</button>
                    ${totalContatos > 1 ? `<button onclick="deleteContato(${c.id})" class="btn btn-ghost btn-xs" title="Excluir" style="min-height:0;height:22px;padding:0 4px;color:#9ca3af">✕</button>` : ''}
                </div>
            </div>
            ${c.cargo ? `<div style="color:#9ca3af;font-size:11px;margin-bottom:6px;padding-left:22px">${esc(c.cargo)}</div>` : ''}
            <div class="contact-fields">
                ${c.email ? `<div class="contact-field-row">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="2" style="flex-shrink:0"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>
                    <span class="contact-field-value">${esc(c.email)}</span>
                    <div class="contact-field-actions">
                        <button onclick="copyToClipboard('${esc(c.email)}', this)" title="Copiar email" class="contact-copy-btn">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                        ${mailtoLink ? `<a href="${mailtoLink}" title="Enviar email" class="contact-action-btn contact-action-email">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9z"/></svg>
                        </a>` : ''}
                    </div>
                </div>` : ''}
                ${c.telefone ? `<div class="contact-field-row">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="2" style="flex-shrink:0"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
                    <span class="contact-field-value">${esc(c.telefone)}</span>
                    <div class="contact-field-actions">
                        <button onclick="copyToClipboard('${esc(c.telefone)}', this)" title="Copiar telefone" class="contact-copy-btn">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                        ${whatsappLink ? `<a href="${whatsappLink}" target="_blank" title="WhatsApp" class="contact-action-btn contact-action-wa">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.025.506 3.934 1.395 5.608L0 24l6.587-1.344A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.882 0-3.674-.508-5.24-1.47l-.376-.222-3.898.795.83-3.756-.244-.388A9.956 9.956 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>
                        </a>` : ''}
                    </div>
                </div>` : ''}
                ${!c.email && !c.telefone ? '<div style="font-size:10px;color:#d1d5db;padding-left:22px">Sem dados de contato</div>' : ''}
            </div>
        </div>`;
}

function copyToClipboard(text, btnEl) {
    navigator.clipboard.writeText(text).then(() => {
        const tip = document.createElement('span');
        tip.className = 'copy-tooltip show';
        tip.textContent = 'Copiado!';
        tip.style.bottom = '100%';
        tip.style.left = '50%';
        tip.style.transform = 'translateX(-50%) translateY(-4px)';
        btnEl.style.position = 'relative';
        btnEl.appendChild(tip);
        setTimeout(() => tip.remove(), 1200);
    });
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
        loadLeadStatus(selectedLeadId);
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
                <button onclick="addContato()" class="leads-action-btn leads-action-btn-incluir" style="flex:1">Salvar</button>
                <button onclick="document.getElementById('form_add_contato').classList.add('hidden')" class="leads-action-btn" style="flex:1;background:#f3f4f6;color:#6b7280">Cancelar</button>
            </div>
        </div>`;
}

async function addContato() {
    if (!selectedLeadId) return;
    const nome = document.getElementById('nc_nome').value.trim();
    if (!nome) return showToast('Nome obrigatório', 'warning');
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

function editContato(id) {
    fetch(`/api/leads/${selectedLeadId}/contatos`).then(r => r.json()).then(data => {
        const c = (data.contatos || []).find(ct => ct.id === id);
        if (!c) return;
        document.getElementById('editc_id').value = c.id;
        document.getElementById('editc_nome').value = c.nome || '';
        document.getElementById('editc_cargo').value = c.cargo || '';
        document.getElementById('editc_telefone').value = c.telefone || '';
        document.getElementById('editc_email').value = c.email || '';
        document.getElementById('modal_editar_contato').showModal();
    });
}

async function saveEditContato() {
    const id = document.getElementById('editc_id').value;
    const nome = document.getElementById('editc_nome').value.trim();
    if (!nome) return showToast('Nome obrigatório', 'warning');
    try {
        await fetch(`/api/leads/contatos/${id}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome,
                cargo: document.getElementById('editc_cargo').value.trim(),
                telefone: document.getElementById('editc_telefone').value.trim(),
                email: document.getElementById('editc_email').value.trim(),
            }),
        });
        document.getElementById('modal_editar_contato').close();
        loadLeadStatus(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
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

// ======================== Lead Edit Modal ========================

function openEditLead() {
    if (!selectedLeadData) return;
    const lead = selectedLeadData;
    document.getElementById('edit_empresa').value = lead.empresa || '';
    document.getElementById('edit_nome').value = lead.nome || '';
    document.getElementById('edit_fonte').value = lead.fonte || '';
    document.getElementById('edit_tipo_lead').value = lead.tipo_lead || 'cliente';
    document.getElementById('edit_url_site').value = lead.url_site || '';
    document.getElementById('edit_segmento').value = lead.segmento || '';
    document.getElementById('edit_observacoes').value = lead.observacoes || '';
    document.getElementById('edit_status').value = lead.status || 'inbox';
    document.getElementById('edit_potencial').value = lead.potencial || 'medio';
    document.getElementById('edit_responsavel').value = lead.id_executivo || '';
    document.getElementById('modal_editar_lead').showModal();
}

async function saveEditLead() {
    if (!selectedLeadId) return;
    try {
        const editExecVal = document.getElementById('edit_responsavel').value;
        const resp = await fetch(`/api/leads/${selectedLeadId}/editar`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                empresa: document.getElementById('edit_empresa').value.trim(),
                nome: document.getElementById('edit_nome').value.trim(),
                fonte: document.getElementById('edit_fonte').value.trim(),
                tipo_lead: document.getElementById('edit_tipo_lead').value,
                url_site: document.getElementById('edit_url_site').value.trim(),
                segmento: document.getElementById('edit_segmento').value.trim(),
                observacoes: document.getElementById('edit_observacoes').value.trim(),
                status: document.getElementById('edit_status').value,
                potencial: document.getElementById('edit_potencial').value,
                id_executivo: editExecVal ? parseInt(editExecVal) : 0,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_editar_lead').close();
            showToast('Lead atualizado!', 'success');
            loadLeadStatus(selectedLeadId);
            loadLeads();
        } else {
            showToast(data.message || 'Erro ao atualizar', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function converterCliente() {
    if (!selectedLeadId) return;
    if (!confirm('Converter este lead em cliente? Esta ação não pode ser desfeita.')) return;
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/converter-cliente`, {method: 'POST'});
        const data = await resp.json();
        if (data.success) {
            showToast('Lead convertido em cliente com sucesso!', 'success');
            selectedLeadId = null;
            clearColumns();
            loadLeads();
        } else {
            showToast(data.message || 'Erro ao converter', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Merge Leads ========================

function openMergeModal() {
    if (!selectedLeadId) return;
    document.getElementById('merge_search').value = '';
    document.getElementById('merge_results').innerHTML = '<div class="text-xs text-gray-400 text-center py-4">Digite para buscar leads...</div>';
    document.getElementById('modal_mesclar').showModal();
    if (selectedLeadData) {
        document.getElementById('merge_search').value = selectedLeadData.empresa || '';
        searchMergeLeads();
    }
}

let mergeSearchTimeout = null;
async function searchMergeLeads() {
    clearTimeout(mergeSearchTimeout);
    mergeSearchTimeout = setTimeout(async () => {
        const q = document.getElementById('merge_search').value.trim();
        if (q.length < 2) {
            document.getElementById('merge_results').innerHTML = '<div class="text-xs text-gray-400 text-center py-4">Digite ao menos 2 caracteres...</div>';
            return;
        }
        try {
            const resp = await fetch(`/api/leads?search=${encodeURIComponent(q)}`);
            const data = await resp.json();
            const leads = (data.leads || []).filter(l => l.id !== selectedLeadId);
            const container = document.getElementById('merge_results');
            if (leads.length === 0) {
                container.innerHTML = '<div class="text-xs text-gray-400 text-center py-4">Nenhum lead encontrado</div>';
                return;
            }
            container.innerHTML = leads.map(l => `
                <div class="flex items-center justify-between p-2 rounded hover:bg-gray-50 cursor-pointer" onclick="confirmMerge(${l.id}, '${esc(l.nome_lead).replace(/'/g, "\\'")}')">
                    <div>
                        <div class="text-sm font-medium">${esc(l.nome_lead)}</div>
                        <div class="text-xs text-gray-400">${esc(l.fonte || '-')} | ${l.qtd_contatos} contato(s)</div>
                    </div>
                    <span class="badge badge-xs badge-ghost">Mesclar</span>
                </div>
            `).join('');
        } catch (e) { console.error('searchMergeLeads:', e); }
    }, 350);
}

async function confirmMerge(secundarioId, nome) {
    if (!confirm(`Mesclar "${nome}" com o lead atual? Contatos e atividades serão movidos e "${nome}" será excluído.`)) return;
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/mesclar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lead_secundario_id: secundarioId}),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_mesclar').close();
            showToast('Leads mesclados com sucesso!', 'success');
            loadLeadStatus(selectedLeadId);
            loadLeadAtividades(selectedLeadId);
            loadLeads();
        } else {
            showToast(data.message || 'Erro ao mesclar', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

function openDesqualificar() {
    if (!selectedLeadId) return;
    document.getElementById('motivo_desqualificacao').value = '';
    document.getElementById('modal_desqualificar').showModal();
}

async function confirmDesqualificar() {
    const motivo = document.getElementById('motivo_desqualificacao').value;
    if (!motivo) return showToast('Selecione um motivo', 'warning');
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
            showToast(data.message || 'Erro', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Col 3: Ações ========================

let lastAtivTipoDefault = '';
let showNewAtivForm = false;

async function loadLeadAtividades(leadId) {
    const col = document.getElementById('col_atividades');

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
        ].map(t => `<option value="${t}">${t.replace(/_/g,' ')}</option>`).join('');

        const contatoOptions = `<option value="">Geral</option>` +
            contatos.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('');

        const today = new Date().toISOString().split('T')[0];

        const pendentes = atividades.filter(a => !a.concluida);
        const concluidas = atividades.filter(a => a.concluida);

        let sugestaoHtml = '';
        if (pendentes.length === 0) {
            const principal = contatos.find(c => c.principal) || contatos[0];
            if (principal) {
                const hasEmail = !!principal.email;
                const hasPhone = !!principal.telefone;
                if (hasEmail || hasPhone) {
                    const sugTipo = hasEmail ? 'email_enviado' : 'whatsapp';
                    const sugLabel = hasEmail ? 'Enviar email' : 'Enviar WhatsApp';
                    const sugDesc = hasEmail
                        ? `Enviar email de apresentação para ${principal.nome}`
                        : `Enviar mensagem WhatsApp para ${principal.nome}`;
                    const sugIcon = hasEmail
                        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>'
                        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.025.506 3.934 1.395 5.608L0 24l6.587-1.344A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.882 0-3.674-.508-5.24-1.47l-.376-.222-3.898.795.83-3.756-.244-.388A9.956 9.956 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>';
                    sugestaoHtml = `
                        <div class="ativ-sugestao" onclick="applySugestao('${sugTipo}', '${sugDesc.replace(/'/g, "\\'")}')">
                            <div class="flex items-center gap-2">
                                <span style="color:#f59e0b;flex-shrink:0">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                                </span>
                                <div>
                                    <div style="font-weight:600;font-size:11px">Sugestão: ${sugLabel}</div>
                                    <div style="font-size:10px;color:#6b7280">para ${esc(principal.nome)}</div>
                                </div>
                                <span class="ml-auto">${sugIcon}</span>
                            </div>
                        </div>`;
                }
            }
        }

        const formDisplay = showNewAtivForm ? 'block' : 'none';
        const toggleBtnText = showNewAtivForm ? '' : '+ Nova Ação';

        let html = `<div class="p-3" style="display:flex;flex-direction:column;height:100%;font-size:12px">
            ${sugestaoHtml}

            ${!showNewAtivForm ? `<button onclick="toggleAtivForm()" class="leads-action-btn leads-action-btn-nova">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14m-7-7h14"/></svg>
                Nova Ação
            </button>` : ''}

            <div id="ativ_form_container" style="display:${formDisplay};flex-shrink:0">
                <div class="bg-base-200 rounded-lg p-2 space-y-1.5 mb-2">
                    <div class="flex items-center justify-between mb-1">
                        <span style="font-size:10px;font-weight:600;color:#6b7280;text-transform:uppercase">Nova Ação</span>
                        <button onclick="toggleAtivForm()" class="btn btn-ghost btn-xs" style="min-height:0;height:18px;padding:0 4px;font-size:14px">✕</button>
                    </div>
                    <div class="flex gap-1.5">
                        <select id="ativ_tipo" class="${SEL_CLS}" style="flex:1" onchange="onAtivTipoChange()">${tipoOptions}</select>
                        <select id="ativ_contato" class="${SEL_CLS}" style="flex:1">${contatoOptions}</select>
                    </div>
                    <div class="flex gap-1.5 items-center">
                        <label style="font-size:10px;color:#9ca3af;flex-shrink:0">Prazo:</label>
                        <input id="ativ_prazo" type="date" value="${today}" class="${SEL_CLS}" style="flex:1">
                    </div>
                    <textarea id="ativ_descricao" rows="2" class="textarea textarea-xs textarea-bordered w-full" placeholder="Descrição da ação..." style="font-size:12px"></textarea>
                    <div class="flex gap-1 items-center">
                        <span onclick="melhorarTexto()" style="font-size:10px;color:#6b7280;cursor:pointer;text-decoration:underline" class="hover:text-gray-900">Melhorar com IA</span>
                        <button onclick="addAtividade()" class="leads-action-btn leads-action-btn-incluir ml-auto">Incluir</button>
                    </div>
                </div>
            </div>

            <div style="flex:1;overflow-y:auto;min-height:0">
                ${pendentes.length === 0 && concluidas.length === 0 && !sugestaoHtml ? '<div class="text-xs text-gray-400 text-center" style="padding:20px">Nenhuma ação registrada</div>' : ''}
                ${pendentes.map(a => renderAtividade(a)).join('')}
                ${concluidas.length > 0 ? `
                    <div class="concluidas-toggle" onclick="toggleConcluidas()">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" id="concluidas_chevron" style="transition:transform 0.2s;${showConcluidas ? 'transform:rotate(90deg)' : ''}"><path d="M9 18l6-6-6-6"/></svg>
                        Concluídas (${concluidas.length})
                    </div>
                    <div id="concluidas_list" style="display:${showConcluidas ? 'block' : 'none'}">
                        ${concluidas.map(a => renderAtividade(a)).join('')}
                    </div>
                ` : ''}
            </div>
        </div>`;
        col.innerHTML = html;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function toggleAtivForm() {
    showNewAtivForm = !showNewAtivForm;
    if (selectedLeadId) loadLeadAtividades(selectedLeadId);
}

function applySugestao(tipo, descricao) {
    showNewAtivForm = true;
    if (selectedLeadId) {
        loadLeadAtividades(selectedLeadId).then(() => {
            const tipoEl = document.getElementById('ativ_tipo');
            const descEl = document.getElementById('ativ_descricao');
            if (tipoEl) tipoEl.value = tipo;
            if (descEl) descEl.value = descricao;
        });
    }
}

function onAtivTipoChange() {
    const tipo = document.getElementById('ativ_tipo').value;
    const textarea = document.getElementById('ativ_descricao');
    const currentVal = textarea.value.trim();
    const isDefault = !currentVal || Object.values(DEFAULT_DESCRIPTIONS).includes(currentVal);
    if (isDefault && DEFAULT_DESCRIPTIONS[tipo]) {
        textarea.value = DEFAULT_DESCRIPTIONS[tipo];
    }
}

const TIPO_ATIV_ICONS = {
    reuniao: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
    ligacao: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6A19.79 19.79 0 012.12 4.18 2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>',
    whatsapp: '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg>',
    email_enviado: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>',
    email: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>',
    nota: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    follow_up: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>',
    apresentacao: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    proposta_enviada: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/></svg>',
    tentativa_contato: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15.05 5A5 5 0 0119 8.95M15.05 1A9 9 0 0123 8.94"/><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6A19.79 19.79 0 012.12 4.18 2 2 0 014.11 2h3"/></svg>',
    status_change: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>',
    importacao: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    outro: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></svg>',
};

function renderAtividade(a) {
    const tipo = a.tipo || 'outro';
    const badgeCls = TIPO_ATIV_COLORS[tipo] || 'ativ-badge-outro';
    const prazoHtml = a.data_prazo ? getPrazoHtml(a.data_prazo) : '';
    const descId = `desc_${a.id}`;
    const icon = TIPO_ATIV_ICONS[tipo] || TIPO_ATIV_ICONS.outro;

    return `
        <div class="ativ-card ${a.concluida ? 'ativ-card-concluida' : ''} ${a.data_prazo && !a.concluida && isPrazoOverdue(a.data_prazo) ? 'ativ-card-overdue' : ''}">
            <div class="flex items-center gap-1.5 mb-1">
                <label style="display:flex;align-items:center;cursor:pointer;flex-shrink:0">
                    <input type="checkbox" ${a.concluida ? 'checked' : ''} onchange="toggleConcluida(${a.id}, this.checked)"
                           style="width:14px;height:14px;cursor:pointer;accent-color:#22c55e">
                </label>
                <span class="ativ-badge ${badgeCls}" style="display:inline-flex;align-items:center;gap:3px">${icon} ${tipo.replace(/_/g, ' ')}</span>
                <span style="font-size:10px;color:#9ca3af;margin-left:auto">${esc(a.created_at)}</span>
            </div>
            <div class="ativ-desc" id="${descId}" onclick="this.classList.toggle('expanded')" style="cursor:pointer">${esc(a.descricao || '')}</div>
            <div class="flex items-center gap-2 mt-1" style="font-size:10px;color:#9ca3af">
                ${a.contato_nome ? `<span>→ ${esc(a.contato_nome)}</span>` : ''}
                ${a.usuario_nome ? `<span>por ${esc(a.usuario_nome)}</span>` : ''}
                ${prazoHtml}
            </div>
        </div>`;
}

function isPrazoOverdue(prazoStr) {
    const prazo = new Date(prazoStr + 'T00:00:00');
    const today = new Date();
    today.setHours(0,0,0,0);
    return prazo < today;
}

function getPrazoHtml(prazoStr) {
    const prazo = new Date(prazoStr + 'T00:00:00');
    const today = new Date();
    today.setHours(0,0,0,0);
    const diff = Math.floor((prazo - today) / (1000*60*60*24));
    let cls = 'prazo-future';
    let icon = '';
    if (diff < 0) { cls = 'prazo-overdue'; icon = '⚠'; }
    else if (diff === 0) { cls = 'prazo-today'; icon = '●'; }
    else if (diff <= 3) { cls = 'prazo-soon'; }

    const formatted = prazo.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'});
    return `<span class="${cls}" style="margin-left:auto;font-size:10px">${icon} Prazo: ${formatted}</span>`;
}

function toggleConcluidas() {
    showConcluidas = !showConcluidas;
    const list = document.getElementById('concluidas_list');
    const chevron = document.getElementById('concluidas_chevron');
    if (list) list.style.display = showConcluidas ? 'block' : 'none';
    if (chevron) chevron.style.transform = showConcluidas ? 'rotate(90deg)' : '';
}

async function toggleConcluida(atividadeId, concluida) {
    try {
        await fetch(`/api/leads/atividades/${atividadeId}/concluir`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({concluida}),
        });
        if (selectedLeadId) loadLeadAtividades(selectedLeadId);
    } catch (e) { console.error('toggleConcluida:', e); }
}

async function addAtividade() {
    if (!selectedLeadId) return;
    const descricao = document.getElementById('ativ_descricao').value.trim();
    if (!descricao) return showToast('Descrição obrigatória', 'warning');
    const tipo = document.getElementById('ativ_tipo').value;
    const id_contato = document.getElementById('ativ_contato').value || null;
    const data_prazo = document.getElementById('ativ_prazo').value || null;

    try {
        await fetch(`/api/leads/${selectedLeadId}/atividades`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tipo, descricao, id_contato, data_prazo}),
        });
        loadLeadAtividades(selectedLeadId);
        loadLeads();
    } catch (e) { console.error('addAtividade:', e); }
}

async function melhorarTexto() {
    const textarea = document.getElementById('ativ_descricao');
    const texto = textarea.value.trim();
    if (!texto) return showToast('Digite um texto primeiro', 'warning');

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
            showToast(data.message || 'Erro ao melhorar texto', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally { textarea.disabled = false; }
}

// ======================== Col 4: Extrair Informações ========================

function getEmailDomainUrl(contatos) {
    if (!contatos || !contatos.length) return '';
    for (const c of contatos) {
        if (c.email) {
            const parts = c.email.split('@');
            if (parts.length === 2) {
                const domain = parts[1].toLowerCase();
                if (!FREE_DOMAINS.includes(domain)) {
                    return `https://${domain}`;
                }
            }
        }
    }
    return '';
}

async function loadLeadExtrair(leadId) {
    const col = document.getElementById('col_extrair');

    try {
        const [detResp, conResp] = await Promise.all([
            fetch(`/api/leads/${leadId}/detalhes`),
            fetch(`/api/leads/${leadId}/contatos`),
        ]);
        const detData = await detResp.json();
        const conData = await conResp.json();
        const lead = detData.lead;
        const contatos = conData.contatos || [];

        let suggestedUrl = lead.url_site || getEmailDomainUrl(contatos);
        let faviconHtml = '';
        if (suggestedUrl) {
            try {
                const domain = new URL(suggestedUrl).hostname;
                faviconHtml = `<img src="https://www.google.com/s2/favicons?domain=${domain}&sz=64" style="width:16px;height:16px;border-radius:2px;vertical-align:middle;margin-right:4px" onerror="this.style.display='none'">`;
            } catch(e) {}
        }

        let dadosHtml = '';
        if (lead.dados_extraidos) {
            const d = typeof lead.dados_extraidos === 'string' ? JSON.parse(lead.dados_extraidos) : lead.dados_extraidos;
            dadosHtml = renderDadosExtraidos(d, lead);
        }

        col.innerHTML = `
            <div class="p-3 space-y-3" style="font-size:12px">
                <div class="bg-base-200 rounded-lg p-2 space-y-1.5">
                    <div class="flex items-center gap-1">
                        ${faviconHtml}
                        <input id="extrair_url" type="url" class="input input-xs input-bordered w-full" placeholder="https://..."
                               value="${esc(suggestedUrl)}" style="font-size:12px">
                    </div>
                    <button onclick="extractUrl()" class="leads-action-btn leads-action-btn-extrair" id="btn_extrair">
                        <span class="loading loading-spinner loading-xs hidden" id="extrair_spinner"></span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                        Extrair com IA
                    </button>
                </div>
                <div id="extrair_resultado">${dadosHtml}</div>
            </div>`;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function renderDadosExtraidos(d, lead) {
    const redes = d.redes_sociais || lead?.redes_sociais || {};
    const redesHtml = Object.entries(redes)
        .filter(([, v]) => v)
        .map(([k, v]) => `<a href="${v}" target="_blank" class="social-icon-link" title="${k}">${SOCIAL_ICONS[k] || k}</a>`)
        .join(' ');

    const servicos = d.servicos || lead?.servicos || [];
    const clientes = d.clientes_mencionados || lead?.clientes_mencionados || [];
    const contatos = d.contatos_encontrados || [];
    const premios = d.premios_certificacoes || lead?.premios_certificacoes || [];

    let faviconImg = '';
    const urlSite = d._url || lead?.url_site || '';
    if (urlSite) {
        try {
            const domain = new URL(urlSite).hostname;
            faviconImg = `<img src="https://www.google.com/s2/favicons?domain=${domain}&sz=64" style="width:20px;height:20px;border-radius:3px" onerror="this.style.display='none'">`;
        } catch(e) {}
    }

    const descFull = d.descricao || lead?.descricao_empresa || '';
    const descShort = descFull.length > 150 ? descFull.substring(0, 150) + '...' : descFull;
    const descId = 'desc_extract_' + Date.now();

    return `<div class="extract-section space-y-2">
        ${d.nome_empresa ? `<h4>${faviconImg} ${esc(d.nome_empresa)}</h4>` : ''}
        ${descFull ? `<div>
            <span id="${descId}" style="font-size:11px">${esc(descShort)}</span>
            ${descFull.length > 150 ? `<button onclick="document.getElementById('${descId}').textContent='${esc(descFull).replace(/'/g, "\\'")}';this.remove()" style="color:#3b82f6;font-size:10px;background:none;border:none;cursor:pointer">ver mais</button>` : ''}
        </div>` : ''}

        <div class="flex flex-wrap gap-1.5">
            ${d.segmento ? `<span class="extract-pill" style="background:#f3f4f6;color:#4b5563">${esc(d.segmento)}</span>` : ''}
            ${d.porte_estimado || lead?.porte_estimado ? `<span class="extract-pill" style="background:#ede9fe;color:#6d28d9">${esc(d.porte_estimado || lead?.porte_estimado)}</span>` : ''}
        </div>

        ${d.mercado_alvo || lead?.mercado_alvo ? `<div style="font-size:11px"><span style="font-weight:600">Mercado alvo:</span> ${esc(d.mercado_alvo || lead?.mercado_alvo)}</div>` : ''}

        ${servicos.length ? `<div>
            <span style="font-weight:600;font-size:11px">Serviços:</span>
            <div class="extract-pills" style="margin-top:2px">${servicos.map(s => `<span class="extract-pill">${esc(s)}</span>`).join('')}</div>
        </div>` : ''}

        ${redesHtml ? `<div style="display:flex;gap:4px;align-items:center">${redesHtml}</div>` : ''}

        ${d.presenca_digital || lead?.presenca_digital ? `<div style="font-size:11px"><span style="font-weight:600">Presença digital:</span> ${esc(d.presenca_digital || lead?.presenca_digital)}</div>` : ''}

        ${d.oportunidades_midia || lead?.oportunidades_midia ? `<div class="extract-oportunidades"><span style="font-weight:600">Oportunidades:</span> ${esc(d.oportunidades_midia || lead?.oportunidades_midia)}</div>` : ''}

        ${clientes.length ? `<div style="font-size:11px"><span style="font-weight:600">Clientes mencionados:</span> ${clientes.map(s => esc(s)).join(', ')}</div>` : ''}

        ${premios.length ? `<div style="font-size:11px"><span style="font-weight:600">Prêmios/Certificações:</span> ${premios.map(s => esc(s)).join(', ')}</div>` : ''}

        ${d.telefones_gerais?.length ? `<div style="font-size:11px;display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-weight:600">Telefones:</span>
            ${d.telefones_gerais.map(t => `<span>${esc(t)}</span><button onclick="copyToClipboard('${esc(t)}', this)" style="color:#6b7280;background:none;border:none;cursor:pointer;position:relative"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></button>`).join(' ')}
        </div>` : ''}

        ${d.emails_gerais?.length ? `<div style="font-size:11px;display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            <span style="font-weight:600">Emails:</span>
            ${d.emails_gerais.map(e => `<span>${esc(e)}</span><button onclick="copyToClipboard('${esc(e)}', this)" style="color:#6b7280;background:none;border:none;cursor:pointer;position:relative"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></button>`).join(' ')}
        </div>` : ''}

        ${d.endereco ? `<div style="font-size:11px"><span style="font-weight:600">Endereço:</span> ${esc(d.endereco)}</div>` : ''}

        ${contatos.length ? `
            <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin-top:4px">Contatos encontrados</div>
            ${contatos.map((c, i) => `
                <div style="background:#fff;border:1px solid #f3f4f6;border-radius:6px;padding:6px;display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-weight:600;font-size:11px">${esc(c.nome || '?')}</div>
                        <div style="color:#9ca3af;font-size:10px">${[c.cargo, c.email, c.telefone].filter(Boolean).map(v => esc(v)).join(' | ')}</div>
                    </div>
                    <button onclick="addExtractedContact(${i})" class="leads-action-btn leads-action-btn-merge" style="font-size:10px;flex:0;padding:4px 10px">+ Add</button>
                </div>
            `).join('')}
        ` : ''}

        <button onclick="saveExtracted()" class="leads-action-btn leads-action-btn-convert mt-2" style="width:100%">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            Salvar dados no lead
        </button>
    </div>`;
}

let lastExtractedData = null;

async function extractUrl() {
    if (!selectedLeadId) return;
    const url = document.getElementById('extrair_url').value.trim();
    if (!url) return showToast('Cole uma URL', 'warning');

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
            showToast(data.message || 'Erro na extração', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

async function saveExtracted() {
    if (!selectedLeadId || !lastExtractedData) return showToast('Extraia dados primeiro', 'warning');
    const d = lastExtractedData;
    try {
        const url = d._url || '';
        let faviconUrl = '';
        if (url) {
            try { faviconUrl = `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=64`; } catch(e) {}
        }

        await fetch(`/api/leads/${selectedLeadId}/salvar-dados-extraidos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url_site: url,
                descricao_empresa: d.descricao || '',
                segmento: d.segmento || '',
                redes_sociais: d.redes_sociais || {},
                servicos: d.servicos || [],
                clientes_mencionados: d.clientes_mencionados || [],
                dados_extraidos: d,
                favicon_url: faviconUrl,
                porte_estimado: d.porte_estimado || '',
                mercado_alvo: d.mercado_alvo || '',
                presenca_digital: d.presenca_digital || '',
                oportunidades_midia: d.oportunidades_midia || '',
                premios_certificacoes: d.premios_certificacoes || [],
            }),
        });
        showToast('Dados salvos!', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
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
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Col 5: Comunicação IA ========================

async function loadLeadComunicacao(leadId) {
    const col = document.getElementById('col_comunicacao');

    try {
        const conResp = await fetch(`/api/leads/${leadId}/contatos`);
        const conData = await conResp.json();
        const contatos = conData.contatos || [];

        const contatoOptions = contatos.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('');

        const apresentacaoTemplates = COMM_TEMPLATES.filter((_, i) => i <= 4);
        const followupTemplates = COMM_TEMPLATES.filter((_, i) => i === 5 || i === 6);
        const eventoTemplates = COMM_TEMPLATES.filter((_, i) => i >= 7);

        function renderTemplateGroup(label, templates, startIdx) {
            return `<div class="comm-group">
                <div style="font-size:9px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin-bottom:3px">${label}</div>
                <div class="flex flex-wrap gap-1">${templates.map((t, i) => {
                    const globalIdx = COMM_TEMPLATES.indexOf(t);
                    const icon = t.tipo === 'whatsapp' ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="#25D366" style="flex-shrink:0"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479c0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg>'
                        : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" style="flex-shrink:0"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>';
                    return `<button class="comm-template-btn" onclick="applyCommTemplate(${globalIdx})" style="display:inline-flex;align-items:center;gap:3px">${icon} ${esc(t.label)}</button>`;
                }).join('')}</div>
            </div>`;
        }

        col.innerHTML = `
            <div class="p-3 space-y-2" style="font-size:12px">
                <div class="space-y-2">
                    ${renderTemplateGroup('Apresentação', apresentacaoTemplates, 0)}
                    ${renderTemplateGroup('Follow-up', followupTemplates, 5)}
                    ${renderTemplateGroup('Eventos', eventoTemplates, 7)}
                </div>
                <div style="border-top:1px solid #f3f4f6;padding-top:8px" class="space-y-1.5">
                    <div class="flex gap-1.5">
                        <select id="comm_contato" class="${SEL_CLS}" style="flex:1">
                            <option value="">Contato...</option>
                            ${contatoOptions}
                        </select>
                        <div class="flex gap-1.5 items-center" style="font-size:11px;flex-shrink:0">
                            <label style="display:flex;align-items:center;gap:2px;cursor:pointer">
                                <input type="radio" name="comm_tipo" value="whatsapp" checked style="width:11px;height:11px"> WA
                            </label>
                            <label style="display:flex;align-items:center;gap:2px;cursor:pointer">
                                <input type="radio" name="comm_tipo" value="email" style="width:11px;height:11px"> Email
                            </label>
                        </div>
                    </div>
                    <input id="comm_objetivo" class="input input-xs input-bordered w-full" placeholder="Objetivo personalizado..." style="font-size:11px">
                    <div class="flex gap-1.5">
                        <select id="comm_tamanho" class="${SEL_CLS}" style="flex:1">
                            <option value="curto">Curto</option>
                            <option value="medio" selected>Médio</option>
                            <option value="longo">Longo</option>
                        </select>
                        <select id="comm_tom" class="${SEL_CLS}" style="flex:1">
                            <option value="formal">Formal</option>
                            <option value="cordial" selected>Cordial</option>
                            <option value="descontraido">Descontraído</option>
                        </select>
                    </div>
                    <div class="flex flex-wrap gap-2" style="font-size:10px;color:#6b7280">
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer">
                            <input type="checkbox" id="comm_incluir_dados" checked style="width:11px;height:11px"> Dados
                        </label>
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer">
                            <input type="checkbox" id="comm_incluir_servicos" style="width:11px;height:11px"> Serviços
                        </label>
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer">
                            <input type="checkbox" id="comm_incluir_oportunidades" style="width:11px;height:11px"> Oportunidades
                        </label>
                    </div>
                    <button onclick="gerarComunicacao()" class="leads-action-btn leads-action-btn-gerar" id="btn_comm">
                        <span class="loading loading-spinner loading-xs hidden" id="comm_spinner"></span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                        Gerar com IA
                    </button>
                </div>
            </div>`;
    } catch (e) {
        col.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function applyCommTemplate(idx) {
    const t = COMM_TEMPLATES[idx];
    if (!t) return;
    document.getElementById('comm_objetivo').value = t.objetivo;
    const radios = document.querySelectorAll('input[name="comm_tipo"]');
    radios.forEach(r => { r.checked = r.value === t.tipo; });
    gerarComunicacao();
}

async function gerarComunicacao() {
    if (!selectedLeadId) return;
    const btn = document.getElementById('btn_comm');
    const spinner = document.getElementById('comm_spinner');
    btn.disabled = true;
    spinner.classList.remove('hidden');

    const tipo = document.querySelector('input[name="comm_tipo"]:checked')?.value || 'whatsapp';
    const objetivo = document.getElementById('comm_objetivo').value.trim();
    if (!objetivo) { showToast('Informe o objetivo', 'warning'); btn.disabled = false; spinner.classList.add('hidden'); return; }

    try {
        const resp = await fetch('/api/ia/gerar-comunicacao', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lead_id: selectedLeadId,
                tipo,
                objetivo,
                tamanho: document.getElementById('comm_tamanho').value,
                tom: document.getElementById('comm_tom').value,
                incluir_dados_lead: document.getElementById('comm_incluir_dados').checked,
                incluir_servicos: document.getElementById('comm_incluir_servicos').checked,
                incluir_oportunidades: document.getElementById('comm_incluir_oportunidades').checked,
                contato_id: document.getElementById('comm_contato').value || null,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            openCommResultModal(data.texto, data.word_count, tipo);
        } else {
            showToast(data.message || 'Erro ao gerar comunicação', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

function openCommResultModal(texto, wordCount, tipo) {
    const modal = document.getElementById('modal_comunicacao_resultado');
    const preview = document.getElementById('modal_comm_preview');
    const textEl = document.getElementById('modal_comm_text');
    const countEl = document.getElementById('modal_comm_word_count');

    textEl.textContent = texto;
    countEl.textContent = wordCount + ' palavras';

    if (tipo === 'email') {
        preview.className = 'comm-preview comm-preview-email';
    } else {
        preview.className = 'comm-preview';
    }

    modal.showModal();
}

function copyModalCommText() {
    const el = document.getElementById('modal_comm_text');
    if (el) {
        navigator.clipboard.writeText(el.innerText).then(() => {
            showToast('Texto copiado!', 'success');
        });
    }
}

function openModalCommWA() {
    const el = document.getElementById('modal_comm_text');
    if (!el) return;
    const text = el.innerText;
    const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
    window.open(url, '_blank');
}

function openModalCommEmail() {
    const el = document.getElementById('modal_comm_text');
    if (!el) return;
    const text = el.innerText;
    const lines = text.split('\n');
    let subject = '';
    let body = text;
    if (lines[0] && lines[0].toLowerCase().startsWith('assunto:')) {
        subject = lines[0].replace(/^assunto:\s*/i, '').trim();
        body = lines.slice(1).join('\n').trim();
    }
    const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.open(mailto);
}

// ======================== Links Úteis Modal ========================

let linksData = [];

async function loadLinksContent() {
    try {
        const resp = await fetch('/api/leads/links-uteis');
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);
        linksData = data.links || [];
    } catch (e) {
        console.error('loadLinksContent:', e);
    }
}

function openLinksModal() {
    const container = document.getElementById('links_content');

    if (linksData.length === 0) {
        container.innerHTML = '<div class="leads-empty">Nenhum link cadastrado</div>';
    } else {
        const grouped = {};
        linksData.forEach(l => {
            const cat = l.categoria || 'Outros';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(l);
        });

        container.innerHTML = Object.entries(grouped).map(([cat, items]) => `
            <div>
                <div style="font-size:10px;font-weight:600;color:#9ca3af;text-transform:uppercase;margin-bottom:4px">${esc(cat)}</div>
                ${items.map(l => `
                    <div class="link-item">
                        <a href="${esc(l.url)}" target="_blank" class="text-xs link link-primary truncate">${esc(l.titulo)}</a>
                        <button onclick="copyToClipboard('${esc(l.url)}', this)" title="Copiar link" style="color:#9ca3af;background:none;border:none;cursor:pointer;display:inline-flex;flex-shrink:0;position:relative">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    updateLinksSiteSection();
    document.getElementById('modal_links').showModal();
}

function updateLinksSiteSection() {
    const section = document.getElementById('links_site_section');
    if (!section) return;
    if (selectedLeadData && selectedLeadData.url_site) {
        section.classList.remove('hidden');
    } else {
        section.classList.add('hidden');
    }
}

async function extrairLinksDoSite() {
    if (!selectedLeadId) return;
    const btn = document.getElementById('btn_extrair_links');
    const spinner = document.getElementById('extrair_links_spinner');
    btn.disabled = true;
    spinner.classList.remove('hidden');

    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/extrair-links`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
        });
        const data = await resp.json();
        if (data.success) {
            const links = data.links || [];
            const container = document.getElementById('links_site_resultado');
            if (links.length === 0) {
                container.innerHTML = '<div class="text-xs text-gray-400">Nenhum link encontrado</div>';
            } else {
                container.innerHTML = links.slice(0, 30).map(url => `
                    <div class="link-item">
                        <a href="${esc(url)}" target="_blank" class="text-xs link link-primary truncate">${esc(url)}</a>
                        <button onclick="copyToClipboard('${esc(url)}', this)" title="Copiar" style="color:#9ca3af;background:none;border:none;cursor:pointer;display:inline-flex;flex-shrink:0;position:relative">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                `).join('');
            }
        } else {
            showToast(data.message || 'Erro ao buscar links', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

// ======================== Import Modal ========================

function openImportModal() {
    document.getElementById('import_step1').classList.remove('hidden');
    document.getElementById('import_step2').classList.add('hidden');
    document.getElementById('import_texto').value = '';
    document.getElementById('modal_importar').showModal();
}

async function processImport() {
    const texto = document.getElementById('import_texto').value.trim();
    if (!texto) return showToast('Cole os dados dos leads', 'warning');

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
    } catch (e) { showToast('Erro ao processar: ' + e.message, 'error'); }
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
    if (selected.length === 0) return showToast('Selecione ao menos um lead', 'warning');

    const importExecId = document.getElementById('import_responsavel').value;
    const tipoLead = document.querySelector('input[name="tipo_lead_import"]:checked').value;
    const fonte = document.getElementById('import_fonte').value;

    try {
        const resp = await fetch('/api/leads/importar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                leads: selected.map(l => ({empresa: l.empresa, contatos: l.contatos})),
                id_executivo: importExecId ? parseInt(importExecId) : null,
                tipo_lead: tipoLead,
                fonte: fonte,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_importar').close();
            showToast(`${data.total} lead(s) importado(s)!`, 'success');
            loadLeads();
        } else {
            showToast(data.message || 'Erro ao importar', 'error');
        }
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Util ========================

function esc(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}
