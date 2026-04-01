/* Leads V2 — Dashboard de Prospecção (Reestruturado) */

const SEL_CLS = 'text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1 text-gray-700 focus:outline-none focus:border-gray-400 w-full';

let selectedLeadId = null;
let selectedLeadData = null;
let importParsedLeads = [];
let searchTimeout = null;
let showConcluidas = false;
let currentView = 'list';
let sidebarCollapsed = false;
let modalAtivSelectedTipo = null;
let expandedLeadGroups = new Set();
let selectedContactId = null;

const FREE_DOMAINS = ['gmail.com','yahoo.com','hotmail.com','outlook.com','live.com','icloud.com','aol.com','msn.com','uol.com.br','bol.com.br','terra.com.br','ig.com.br','globo.com','protonmail.com'];

const STATUS_LABELS = {inbox:'Inbox', tentativa_contato:'Tentativa de Contato', reuniao_agendada:'Reunião Agendada', nutricao:'Nutrição', nao_qualificado:'Não Qualificado', fechado_ganho:'Fechado (Ganho)', fechado_perdido:'Fechado (Perdido)'};
const STATUS_LIST = ['inbox','tentativa_contato','reuniao_agendada','nutricao'];
const KANBAN_STATUSES = ['inbox','tentativa_contato','reuniao_agendada','nutricao'];
const POTENCIAL_LIST = ['alto','medio','baixo'];
const POTENCIAL_LABELS = {alto:'Alto', medio:'Médio', baixo:'Baixo'};

const TIPO_ATIV_COLORS = {
    reuniao:'ativ-badge-reuniao', ligacao:'ativ-badge-ligacao', whatsapp:'ativ-badge-whatsapp',
    email_enviado:'ativ-badge-email_enviado', email:'ativ-badge-email', nota:'ativ-badge-nota',
    follow_up:'ativ-badge-follow_up', apresentacao:'ativ-badge-apresentacao',
    proposta_enviada:'ativ-badge-proposta_enviada', tentativa_contato:'ativ-badge-tentativa_contato',
    status_change:'ativ-badge-status_change', importacao:'ativ-badge-importacao',
    contato_add:'ativ-badge-contato_add', contato_remove:'ativ-badge-contato_remove',
    outro:'ativ-badge-outro'
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
    initKanbanDragDrop();
});

function getExecutivoId() {
    return document.getElementById('filtro_executivo').value;
}

function onExecutivoChange() {
    selectedLeadId = null;
    selectedLeadData = null;
    clearDetail();
    if (currentView === 'list') {
        loadLeads();
    } else {
        loadKanban();
    }
}

function clearDetail() {
    selectedLeadId = null;
    selectedContactId = null;
    document.getElementById('mesa_trabalho').style.display = 'none';
    document.getElementById('lead_placeholder').style.display = '';
    ['col_dados_contatos','col_atividades','col_comunicacao'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });
    document.querySelectorAll('.contact-pipeline-item').forEach(el => el.classList.remove('contact-selected'));
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadLeads(), 350);
}

function skeletonHtml() {
    return '<div class="skeleton-block"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div></div>';
}

// ======================== View Toggle ========================

function toggleView(mode) {
    currentView = mode;
    const listEl = document.getElementById('view_list');
    const kanbanEl = document.getElementById('view_kanban');
    const btnList = document.getElementById('btn_view_list');
    const btnKanban = document.getElementById('btn_view_kanban');

    if (mode === 'kanban') {
        listEl.style.display = 'none';
        kanbanEl.style.display = 'flex';
        btnList.classList.remove('active');
        btnKanban.classList.add('active');
        loadKanban();
    } else {
        listEl.style.display = '';
        kanbanEl.style.display = 'none';
        btnList.classList.add('active');
        btnKanban.classList.remove('active');
        loadLeads();
    }
}

// ======================== List View: Load Leads ========================

async function loadLeads() {
    const execId = getExecutivoId();
    const potencial = document.getElementById('filtro_potencial').value;
    const search = document.getElementById('search_leads').value.trim();
    const status = document.getElementById('filtro_status').value;
    const fonte = document.getElementById('filtro_fonte').value;

    let url = '/api/leads?';
    const params = [];

    if (execId === '0') {
        params.push('sem_responsavel=1');
        if (!status) params.push('status=inbox');
    } else if (execId) {
        params.push(`id_executivo=${execId}`);
    } else {
        if (!status) params.push('status=inbox');
    }
    if (potencial) params.push(`potencial=${potencial}`);
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (status) params.push(`status=${status}`);
    if (fonte) params.push(`fonte=${fonte}`);

    let kanbanUrl = '/api/leads/kanban';
    if (execId && execId !== '0') kanbanUrl += `?id_executivo=${execId}`;
    else if (execId === '0') kanbanUrl += '?id_executivo=0';

    try {
        const [leadsResp, contatosResp] = await Promise.all([
            fetch(url + params.join('&')),
            fetch(kanbanUrl),
        ]);
        const leadsData = await leadsResp.json();
        const contatosData = await contatosResp.json();
        if (!leadsData.success) throw new Error(leadsData.message);

        const leads = leadsData.leads || [];
        const allContatos = contatosData.success ? (contatosData.contatos || []) : [];

        const contatosByLead = {};
        allContatos.forEach(c => {
            if (!contatosByLead[c.lead_id]) contatosByLead[c.lead_id] = [];
            contatosByLead[c.lead_id].push(c);
        });

        const totalContatos = leads.reduce((sum, l) => sum + (contatosByLead[l.id] || []).length, 0);
        document.getElementById('leads_count').textContent = totalContatos;
        const countCollapsed = document.getElementById('leads_count_collapsed');
        if (countCollapsed) countCollapsed.textContent = totalContatos;
        const container = document.getElementById('leads_cards');

        if (leads.length === 0) {
            container.innerHTML = '<div class="leads-empty">Nenhum lead encontrado</div>';
            return;
        }

        container.innerHTML = leads.map(l => {
            const contatos = contatosByLead[l.id] || [];
            const isExpanded = expandedLeadGroups.has(l.id) || selectedLeadId === l.id;
            const isActive = selectedLeadId === l.id;
            return `<div class="lead-group ${isActive ? 'lead-group-active' : ''}" data-lead-id="${l.id}">
                <div class="lead-group-header" onclick="selectLead(${l.id})">
                    <button class="lead-group-toggle ${isExpanded ? 'expanded' : ''}" onclick="event.stopPropagation();toggleLeadGroup(${l.id})" title="${isExpanded ? 'Recolher' : 'Expandir'}">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                    </button>
                    <div class="lead-group-info">
                        <div class="lead-group-name">${esc(l.nome_lead)}</div>
                        <div class="lead-group-meta">
                            ${contatos.length > 0 ? `<span>${contatos.length} contato${contatos.length > 1 ? 's' : ''}</span>` : '<span style="color:#d1d5db">Sem contatos</span>'}
                            ${l.potencial ? `<span class="potencial-badge-${l.potencial}" style="font-size:9px;padding:0 5px;border-radius:9999px">${POTENCIAL_LABELS[l.potencial] || l.potencial}</span>` : ''}
                            ${l.valor_estimado ? `<span style="color:#059669;font-weight:600">R$ ${Number(l.valor_estimado).toLocaleString('pt-BR')}</span>` : ''}
                        </div>
                    </div>
                    ${contatos.length > 0 ? `<div class="lead-group-dots">${contatos.map(c => `<span class="pipeline-dot pipeline-dot-${c.status_pipeline || 'inbox'}" title="${esc(c.contato_nome)}: ${STATUS_LABELS[c.status_pipeline] || c.status_pipeline || 'Inbox'}"></span>`).join('')}</div>` : ''}
                </div>
                <div class="lead-group-contacts" id="lead_contacts_${l.id}" style="${isExpanded ? '' : 'display:none'}">
                    ${contatos.map(c => `
                        <div class="contact-pipeline-item ${selectedContactId === c.contato_id ? 'contact-selected' : ''}" data-contato-sidebar="${c.contato_id}" onclick="event.stopPropagation();selectContact(${c.contato_id}, ${l.id})">
                            <span class="pipeline-status-dot pipeline-dot-${c.status_pipeline || 'inbox'}"></span>
                            <div class="contact-pipeline-info">
                                <span class="contact-pipeline-name">${esc(c.contato_nome)}${c.is_principal ? ' <span class="contact-principal-tag">Principal</span>' : ''}</span>
                                ${c.cargo ? `<span class="contact-pipeline-cargo">${esc(c.cargo)}</span>` : ''}
                            </div>
                            <span class="contact-pipeline-badge pipeline-badge-${c.status_pipeline || 'inbox'}">${STATUS_LABELS[c.status_pipeline] || c.status_pipeline || 'Inbox'}</span>
                        </div>
                    `).join('')}
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        document.getElementById('leads_cards').innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function toggleLeadGroup(leadId) {
    const el = document.getElementById(`lead_contacts_${leadId}`);
    if (!el) return;
    const isVisible = el.style.display !== 'none';
    el.style.display = isVisible ? 'none' : '';
    if (isVisible) expandedLeadGroups.delete(leadId);
    else expandedLeadGroups.add(leadId);
    const toggle = el.previousElementSibling?.querySelector('.lead-group-toggle');
    if (toggle) toggle.classList.toggle('expanded', !isVisible);
}

function potencialBadge(p) {
    if (!p) return '';
    return `<span class="potencial-badge-${p}" style="font-size:9px;padding:1px 6px;border-radius:9999px">${POTENCIAL_LABELS[p] || p}</span>`;
}

// ======================== Select Contact & Lead ========================

async function selectContact(contatoId, leadId) {
    const needsReload = selectedLeadId !== leadId;
    selectedContactId = contatoId;
    selectedLeadId = leadId;

    document.querySelectorAll('.contact-pipeline-item').forEach(el => el.classList.remove('contact-selected'));
    document.querySelectorAll('.lead-group').forEach(el => el.classList.remove('lead-group-active'));
    const sidebarItem = document.querySelector(`[data-contato-sidebar="${contatoId}"]`);
    if (sidebarItem) sidebarItem.classList.add('contact-selected');
    const activeGroup = document.querySelector(`.lead-group[data-lead-id="${leadId}"]`);
    if (activeGroup) activeGroup.classList.add('lead-group-active');

    expandedLeadGroups.add(leadId);
    const contactsEl = document.getElementById(`lead_contacts_${leadId}`);
    if (contactsEl && contactsEl.style.display === 'none') {
        contactsEl.style.display = '';
        const toggle = contactsEl.previousElementSibling?.querySelector('.lead-group-toggle');
        if (toggle) toggle.classList.add('expanded');
    }

    if (needsReload) {
        document.getElementById('lead_placeholder').style.display = 'none';
        document.getElementById('mesa_trabalho').style.display = '';

        const col1 = document.getElementById('col_dados_contatos');
        col1.innerHTML = `
            <div id="section_dados">${skeletonHtml()}</div>
            <div id="section_contatos" style="border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px"></div>
            <div id="section_extracao" style="border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px">
                <button onclick="loadTabExtracao(selectedLeadId)" class="extracao-toggle-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                    Extração IA
                </button>
            </div>
        `;

        document.getElementById('col_atividades').innerHTML = skeletonHtml();
        document.getElementById('col_comunicacao').innerHTML = skeletonHtml();

        await Promise.all([
            loadTabDados(leadId),
            loadTabContatos(leadId),
            loadTabAtividades(leadId),
            loadTabComunicacao(leadId),
        ]);
    } else {
        highlightContactInWorkspace(contatoId);
        preselectContactInComm(contatoId);
    }
}

async function selectLead(leadId) {
    selectedLeadId = leadId;
    selectedContactId = null;

    document.querySelectorAll('.contact-pipeline-item').forEach(el => el.classList.remove('contact-selected'));
    document.querySelectorAll('.lead-group').forEach(el => el.classList.remove('lead-group-active'));
    const activeGroup = document.querySelector(`.lead-group[data-lead-id="${leadId}"]`);
    if (activeGroup) activeGroup.classList.add('lead-group-active');

    document.getElementById('lead_placeholder').style.display = 'none';
    document.getElementById('mesa_trabalho').style.display = '';

    expandedLeadGroups.add(leadId);
    const contactsEl = document.getElementById(`lead_contacts_${leadId}`);
    if (contactsEl && contactsEl.style.display === 'none') {
        contactsEl.style.display = '';
        const toggle = contactsEl.previousElementSibling?.querySelector('.lead-group-toggle');
        if (toggle) toggle.classList.add('expanded');
    }

    const col1 = document.getElementById('col_dados_contatos');
    col1.innerHTML = `
        <div id="section_dados">${skeletonHtml()}</div>
        <div id="section_contatos" style="border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px"></div>
        <div id="section_extracao" style="border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px">
            <button onclick="loadTabExtracao(selectedLeadId)" class="extracao-toggle-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                Extração IA
            </button>
        </div>
    `;

    document.getElementById('col_atividades').innerHTML = skeletonHtml();
    document.getElementById('col_comunicacao').innerHTML = skeletonHtml();

    await Promise.all([
        loadTabDados(leadId),
        loadTabContatos(leadId),
        loadTabAtividades(leadId),
        loadTabComunicacao(leadId),
    ]);
}

function highlightContactInWorkspace(contatoId) {
    document.querySelectorAll('.contact-card').forEach(el => el.classList.remove('contact-card-selected'));
    const card = document.querySelector(`.contact-card[data-contact-id="${contatoId}"]`);
    if (card) {
        card.classList.add('contact-card-selected');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function preselectContactInComm(contatoId) {
    const commSelect = document.getElementById('comm_contato');
    if (commSelect) commSelect.value = contatoId;
}

function switchTab(tabName) {
    // Legacy no-op: tabs replaced by 3-column mesa de trabalho
}

// ======================== Tab: Dados ========================

async function loadTabDados(leadId) {
    const container = document.getElementById('section_dados');
    try {
        const resp = await fetch(`/api/leads/${leadId}/detalhes`);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);
        const l = data.lead;
        selectedLeadData = l;

        const execNome = l.executivo_nome || 'Sem responsável';
        const createdAt = l.created_at ? new Date(l.created_at).toLocaleDateString('pt-BR') : '-';
        const updatedAt = l.updated_at ? new Date(l.updated_at).toLocaleDateString('pt-BR') : '-';

        const scorePct = l.qualificacao_score || 0;
        const scoreCls = scorePct >= 70 ? 'high' : scorePct >= 30 ? 'mid' : 'low';

        container.innerHTML = `
            <div class="space-y-4" style="font-size:12px">
                <!-- Status / Potencial / Responsável -->
                <div class="flex flex-wrap gap-2 items-center">
                    <div class="status-row" style="position:relative">
                        <span class="status-row-label">Status</span>
                        <span class="status-badge status-badge-${l.status}" onclick="openMiniModal('status', this)">${STATUS_LABELS[l.status] || l.status} ▾</span>
                    </div>
                    <div class="status-row" style="position:relative">
                        <span class="status-row-label">Potencial</span>
                        <span class="potencial-badge-${l.potencial || 'medio'}" style="padding:3px 10px;border-radius:9999px;font-size:11px;cursor:pointer" onclick="openMiniModal('potencial', this)">${POTENCIAL_LABELS[l.potencial] || 'Médio'} ▾</span>
                    </div>
                    <div class="status-row" style="position:relative">
                        <span class="status-row-label">Responsável</span>
                        <span style="font-size:11px;cursor:pointer;color:#2563eb" onclick="openMiniModal('responsavel', this)">${esc(execNome)} ▾</span>
                    </div>
                </div>

                <!-- Ações -->
                <div class="flex gap-2 flex-wrap" style="padding:8px 0 4px;border-bottom:1px solid #f3f4f6;margin-bottom:4px">
                    <button onclick="openEditLead()" class="leads-action-btn" style="flex:1;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;font-size:11px">
                        Editar
                    </button>
                    <button onclick="converterCliente()" class="leads-action-btn leads-action-btn-convert" style="flex:1;font-size:11px">
                        Converter
                    </button>
                    <button onclick="openMergeModal()" class="leads-action-btn leads-action-btn-merge" style="flex:1;font-size:11px">
                        Mesclar
                    </button>
                    <button onclick="openDesqualificar()" class="leads-action-btn leads-action-btn-disqualify" style="flex:1;font-size:11px">
                        Desqualificar
                    </button>
                </div>

                <!-- Informações principais -->
                <div class="detail-section">
                    <div class="detail-section-title">Informações</div>
                    <div class="detail-field"><span class="detail-field-label">Empresa</span><span class="detail-field-value">${esc(l.empresa || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Nome</span><span class="detail-field-value">${esc(l.nome || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Email</span><span class="detail-field-value">${esc(l.email || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Telefone</span><span class="detail-field-value">${esc(l.telefone || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Cargo</span><span class="detail-field-value">${esc(l.cargo || '-')}</span></div>
                    ${l.mensagem ? `<div class="detail-field"><span class="detail-field-label">Mensagem</span><span class="detail-field-value">${esc(l.mensagem)}</span></div>` : ''}
                </div>

                <!-- Origem / Contexto -->
                <div class="detail-section">
                    <div class="detail-section-title">Origem</div>
                    <div class="detail-field"><span class="detail-field-label">Fonte</span><span class="detail-field-value">${esc(l.fonte || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Origem</span><span class="detail-field-value">${esc(l.origem || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Canal</span><span class="detail-field-value">${esc(l.canal || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Interesse</span><span class="detail-field-value">${esc(l.interesse || '-')}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Tipo Lead</span><span class="detail-field-value">${esc(l.tipo_lead || '-')}</span></div>
                </div>

                ${(l.utm_source || l.utm_medium || l.utm_campaign) ? `
                <div class="detail-section">
                    <div class="detail-section-title">UTMs</div>
                    ${l.utm_source ? `<div class="detail-field"><span class="detail-field-label">Source</span><span class="detail-field-value">${esc(l.utm_source)}</span></div>` : ''}
                    ${l.utm_medium ? `<div class="detail-field"><span class="detail-field-label">Medium</span><span class="detail-field-value">${esc(l.utm_medium)}</span></div>` : ''}
                    ${l.utm_campaign ? `<div class="detail-field"><span class="detail-field-label">Campaign</span><span class="detail-field-value">${esc(l.utm_campaign)}</span></div>` : ''}
                    ${l.utm_content ? `<div class="detail-field"><span class="detail-field-label">Content</span><span class="detail-field-value">${esc(l.utm_content)}</span></div>` : ''}
                    ${l.utm_term ? `<div class="detail-field"><span class="detail-field-label">Term</span><span class="detail-field-value">${esc(l.utm_term)}</span></div>` : ''}
                </div>` : ''}

                <!-- Qualificação -->
                <div class="detail-section">
                    <div class="detail-section-title">Qualificação</div>
                    <div class="detail-field">
                        <span class="detail-field-label">Score</span>
                        <span class="detail-field-value">
                            <span class="score-gauge">
                                <span class="score-gauge-bar" style="width:80px"><span class="score-gauge-fill ${scoreCls}" style="width:${scorePct}%"></span></span>
                                <strong>${scorePct}/100</strong>
                            </span>
                        </span>
                    </div>
                    ${l.qualificacao_notas ? `<div class="detail-field"><span class="detail-field-label">Notas</span><span class="detail-field-value">${esc(l.qualificacao_notas)}</span></div>` : ''}
                    ${l.motivo_desqualificacao ? `<div class="detail-field"><span class="detail-field-label">Motivo Desq.</span><span class="detail-field-value" style="color:#b91c1c">${esc(l.motivo_desqualificacao)}</span></div>` : ''}
                </div>

                <!-- Valores Comerciais -->
                <div class="detail-section">
                    <div class="detail-section-title">Valores Comerciais</div>
                    <div class="detail-field"><span class="detail-field-label">Valor Estimado</span><span class="detail-field-value">${l.valor_estimado ? 'R$ ' + Number(l.valor_estimado).toLocaleString('pt-BR', {minimumFractionDigits: 2}) : '-'}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Valor Fechado</span><span class="detail-field-value">${l.valor_fechado ? 'R$ ' + Number(l.valor_fechado).toLocaleString('pt-BR', {minimumFractionDigits: 2}) : '-'}</span></div>
                    ${l.notas_internas ? `<div class="detail-field"><span class="detail-field-label">Notas</span><span class="detail-field-value">${esc(l.notas_internas)}</span></div>` : ''}
                </div>

                <!-- Empresa (enrichment) -->
                ${(l.segmento || l.porte_estimado || l.descricao_empresa) ? `
                <div class="detail-section">
                    <div class="detail-section-title">Empresa</div>
                    ${l.segmento ? `<div class="detail-field"><span class="detail-field-label">Segmento</span><span class="detail-field-value">${esc(l.segmento)}</span></div>` : ''}
                    ${l.porte_estimado ? `<div class="detail-field"><span class="detail-field-label">Porte</span><span class="detail-field-value">${esc(l.porte_estimado)}</span></div>` : ''}
                    ${l.descricao_empresa ? `<div class="detail-field"><span class="detail-field-label">Descrição</span><span class="detail-field-value">${esc(l.descricao_empresa)}</span></div>` : ''}
                    ${l.url_site ? `<div class="detail-field"><span class="detail-field-label">Site</span><span class="detail-field-value"><a href="${esc(l.url_site)}" target="_blank" class="link link-primary">${esc(l.url_site)}</a></span></div>` : ''}
                </div>` : ''}

                <!-- Datas -->
                <div class="detail-section">
                    <div class="detail-section-title">Datas</div>
                    <div class="detail-field"><span class="detail-field-label">Criado em</span><span class="detail-field-value">${createdAt}</span></div>
                    <div class="detail-field"><span class="detail-field-label">Atualizado</span><span class="detail-field-value">${updatedAt}</span></div>
                    ${l.contatado_em ? `<div class="detail-field"><span class="detail-field-label">1o Contato</span><span class="detail-field-value">${new Date(l.contatado_em).toLocaleDateString('pt-BR')}</span></div>` : ''}
                    ${l.fechado_em ? `<div class="detail-field"><span class="detail-field-label">Fechado em</span><span class="detail-field-value">${new Date(l.fechado_em).toLocaleDateString('pt-BR')}</span></div>` : ''}
                    ${l.lote_importacao ? `<div class="detail-field"><span class="detail-field-label">Lote Import.</span><span class="detail-field-value">${esc(l.lote_importacao)}</span></div>` : ''}
                </div>

            </div>`;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

// ======================== Mini-modals (Status / Potencial / Responsável) ========================

function closeMiniModals() {
    document.querySelectorAll('.mini-modal, .mini-modal-backdrop').forEach(el => el.remove());
}

function openMiniModal(type, anchor) {
    closeMiniModals();
    const rect = anchor.getBoundingClientRect();
    const backdrop = document.createElement('div');
    backdrop.className = 'mini-modal-backdrop';
    backdrop.onclick = closeMiniModals;
    document.body.appendChild(backdrop);

    const modal = document.createElement('div');
    modal.className = 'mini-modal';
    modal.style.position = 'fixed';
    modal.style.top = (rect.bottom + 4) + 'px';
    modal.style.left = rect.left + 'px';

    let items = '';
    if (type === 'status') {
        items = STATUS_LIST.map(s => `<div class="mini-modal-item ${selectedLeadData?.status === s ? 'active' : ''}" onclick="updateStatus('${s}')">${STATUS_LABELS[s]}</div>`).join('');
    } else if (type === 'potencial') {
        items = POTENCIAL_LIST.map(p => `<div class="mini-modal-item ${selectedLeadData?.potencial === p ? 'active' : ''}" onclick="updatePotencial('${p}')">${POTENCIAL_LABELS[p]}</div>`).join('');
    } else if (type === 'responsavel') {
        items = `<div class="mini-modal-item ${!selectedLeadData?.id_executivo ? 'active' : ''}" onclick="updateResponsavel(0)">Sem responsável</div>`;
        items += (window.EXECUTIVOS || []).map(e => `<div class="mini-modal-item ${selectedLeadData?.id_executivo === e.id ? 'active' : ''}" onclick="updateResponsavel(${e.id})">${esc(e.nome)}</div>`).join('');
    }
    modal.innerHTML = items;
    document.body.appendChild(modal);
}

async function updateStatus(newStatus) {
    closeMiniModals();
    if (!selectedLeadId) return;
    try {
        await fetch(`/api/leads/${selectedLeadId}/status`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status: newStatus}),
        });
        await loadTabDados(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function updatePotencial(newPotencial) {
    closeMiniModals();
    if (!selectedLeadId) return;
    try {
        await fetch(`/api/leads/${selectedLeadId}/status`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({potencial: newPotencial}),
        });
        await loadTabDados(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function updateResponsavel(execId) {
    closeMiniModals();
    if (!selectedLeadId) return;
    try {
        await fetch(`/api/leads/${selectedLeadId}/status`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_executivo: execId}),
        });
        await loadTabDados(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Tab: Contatos ========================

async function loadTabContatos(leadId) {
    const container = document.getElementById('section_contatos');
    container.innerHTML = skeletonHtml();

    try {
        const resp = await fetch(`/api/leads/${leadId}/contatos`);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);
        const contatos = data.contatos || [];

        let html = '<div class="space-y-3" style="font-size:12px">';
        html += `<button onclick="showAddContato()" class="leads-action-btn leads-action-btn-nova">+ Adicionar Contato</button>`;
        html += '<div id="add_contato_form" style="display:none"></div>';

        if (contatos.length === 0) {
            html += '<div class="leads-empty">Nenhum contato</div>';
        } else {
            html += contatos.map(c => renderContato(c)).join('');
        }
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function renderContato(c) {
    const copyIcon = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>`;
    const phone = c.telefone ? c.telefone.replace(/\D/g, '') : '';
    const waLink = phone ? `https://wa.me/55${phone}` : '';

    return `<div class="contact-card ${selectedContactId === c.id ? 'contact-card-selected' : ''}" data-contact-id="${c.id}">
        <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-1.5">
                <span style="font-weight:600;font-size:12px">${esc(c.nome)}</span>
                ${c.is_principal ? '<span style="font-size:9px;background:#dcfce7;color:#15803d;padding:0px 5px;border-radius:9999px">Principal</span>' : ''}
            </div>
            <div class="contact-actions-hover flex items-center gap-1">
                <button onclick="editContato(${c.id}, '${esc(c.nome)}', '${esc(c.cargo || '')}', '${esc(c.telefone || '')}', '${esc(c.email || '')}', '${esc(c.departamento || '')}')" style="color:#6b7280;background:none;border:none;cursor:pointer;font-size:10px">Editar</button>
                ${!c.is_principal ? `<button onclick="setPrincipal(${c.id})" style="color:#2563eb;background:none;border:none;cursor:pointer;font-size:10px">★</button>` : ''}
                <button onclick="deleteContato(${c.id})" style="color:#ef4444;background:none;border:none;cursor:pointer;font-size:10px">×</button>
            </div>
        </div>
        <div class="contact-fields">
            ${c.cargo ? `<div class="contact-field-row"><span style="color:#9ca3af;font-size:10px">🏢</span><span class="contact-field-value">${esc(c.cargo)}</span></div>` : ''}
            ${c.departamento ? `<div class="contact-field-row"><span style="color:#9ca3af;font-size:10px">📋</span><span class="contact-field-value">${esc(c.departamento)}</span></div>` : ''}
            ${c.telefone ? `<div class="contact-field-row">
                <span style="color:#9ca3af;font-size:10px">📞</span>
                <span class="contact-field-value">${esc(c.telefone)}</span>
                <span class="contact-field-actions">
                    <button class="contact-copy-btn" onclick="copyToClipboard('${esc(c.telefone)}', this)">${copyIcon}</button>
                    ${waLink ? `<a href="${waLink}" target="_blank" class="contact-action-btn contact-action-wa">${SOCIAL_ICONS.instagram.replace('currentColor','#25D366').substring(0,5)}WA</a>` : ''}
                </span>
            </div>` : ''}
            ${c.email ? `<div class="contact-field-row">
                <span style="color:#9ca3af;font-size:10px">✉️</span>
                <span class="contact-field-value">${esc(c.email)}</span>
                <span class="contact-field-actions">
                    <button class="contact-copy-btn" onclick="copyToClipboard('${esc(c.email)}', this)">${copyIcon}</button>
                    <a href="mailto:${esc(c.email)}" class="contact-action-btn contact-action-email" style="font-size:10px">@</a>
                </span>
            </div>` : ''}
        </div>
    </div>`;
}

function showAddContato() {
    const form = document.getElementById('add_contato_form');
    if (!form) return;
    form.style.display = '';
    form.innerHTML = `<div class="bg-base-200 rounded-lg p-3 space-y-2 mb-2">
        <input id="ac_nome" class="input input-xs input-bordered w-full" placeholder="Nome *">
        <input id="ac_cargo" class="input input-xs input-bordered w-full" placeholder="Cargo">
        <input id="ac_departamento" class="input input-xs input-bordered w-full" placeholder="Departamento">
        <div class="grid grid-cols-2 gap-2">
            <input id="ac_telefone" class="input input-xs input-bordered w-full" placeholder="Telefone" oninput="applyPhoneMask(this)">
            <input id="ac_email" class="input input-xs input-bordered w-full" placeholder="Email">
        </div>
        <div class="flex gap-2 justify-end">
            <button onclick="document.getElementById('add_contato_form').style.display='none'" class="btn btn-xs btn-ghost">Cancelar</button>
            <button onclick="addContato()" class="leads-action-btn leads-action-btn-incluir" style="flex:0;padding:4px 14px;font-size:11px">Adicionar</button>
        </div>
    </div>`;
}

async function addContato() {
    if (!selectedLeadId) return;
    const nome = document.getElementById('ac_nome').value.trim();
    if (!nome) return showToast('Nome obrigatório', 'warning');

    try {
        await fetch(`/api/leads/${selectedLeadId}/contatos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome,
                cargo: document.getElementById('ac_cargo').value.trim() || null,
                departamento: document.getElementById('ac_departamento').value.trim() || null,
                telefone: document.getElementById('ac_telefone').value.trim() || null,
                email: document.getElementById('ac_email').value.trim() || null,
            }),
        });
        loadTabContatos(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

function editContato(id, nome, cargo, telefone, email, departamento) {
    document.getElementById('editc_id').value = id;
    document.getElementById('editc_nome').value = nome;
    document.getElementById('editc_cargo').value = cargo;
    document.getElementById('editc_telefone').value = telefone;
    document.getElementById('editc_email').value = email;
    document.getElementById('editc_departamento').value = departamento || '';
    document.getElementById('modal_editar_contato').showModal();
}

async function saveEditContato() {
    const id = document.getElementById('editc_id').value;
    try {
        await fetch(`/api/leads/contatos/${id}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome: document.getElementById('editc_nome').value.trim(),
                cargo: document.getElementById('editc_cargo').value.trim() || null,
                departamento: document.getElementById('editc_departamento').value.trim() || null,
                telefone: document.getElementById('editc_telefone').value.trim() || null,
                email: document.getElementById('editc_email').value.trim() || null,
            }),
        });
        document.getElementById('modal_editar_contato').close();
        loadTabContatos(selectedLeadId);
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function deleteContato(id) {
    if (!confirm('Excluir este contato?')) return;
    try {
        await fetch(`/api/leads/contatos/${id}`, {method: 'DELETE'});
        loadTabContatos(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function setPrincipal(contatoId) {
    if (!selectedLeadId) return;
    try {
        await fetch(`/api/leads/contatos/${contatoId}/principal`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lead_id: selectedLeadId}),
        });
        loadTabContatos(selectedLeadId);
        loadTabDados(selectedLeadId);
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Tab: Atividades ========================

async function loadTabAtividades(leadId) {
    const container = document.getElementById('col_atividades');
    if (!container) return;
    container.innerHTML = skeletonHtml();

    try {
        const resp = await fetch(`/api/leads/${leadId}/atividades`);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);
        const atividades = data.atividades || [];

        const pendentes = atividades.filter(a => !a.concluida);
        const concluidas = atividades.filter(a => a.concluida);

        container.innerHTML = `
            <div class="space-y-2" style="font-size:12px">
                <div id="ativ_list">
                    ${pendentes.length === 0 && concluidas.length === 0 ? '<div class="leads-empty" style="min-height:60px">Nenhuma atividade</div>' : ''}
                    ${pendentes.map(a => renderAtividade(a)).join('')}
                    ${concluidas.length > 0 ? `
                        <div class="concluidas-toggle" onclick="toggleConcluidas()">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                            <span>${concluidas.length} concluída(s)</span>
                        </div>
                        <div id="concluidas_area" style="display:${showConcluidas ? 'block' : 'none'}">
                            ${concluidas.map(a => renderAtividade(a)).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>`;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function renderAtividade(a) {
    const dateStr = a.created_at ? new Date(a.created_at).toLocaleString('pt-BR', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}) : '';
    const typeBadge = TIPO_ATIV_COLORS[a.tipo] || 'ativ-badge-outro';
    const isOverdue = isPrazoOverdue(a);
    const prazoHtml = getPrazoHtml(a);
    const contatoLabel = a.contato_nome ? `${esc(a.contato_nome)}` : '';
    const isSystem = a.tipo === 'status_change' || a.tipo === 'importacao' || a.tipo === 'contato_add' || a.tipo === 'contato_remove';

    return `<div class="ativ-card ${a.concluida ? 'ativ-card-concluida' : ''} ${isOverdue ? 'ativ-card-overdue' : ''}">
        <div class="flex items-start gap-2">
            ${!isSystem ? `<input type="checkbox" ${a.concluida ? 'checked' : ''} onchange="toggleConcluida(${a.id}, this.checked)" class="ativ-checkbox">` : '<div style="width:16px;flex-shrink:0"></div>'}
            <div style="flex:1;min-width:0">
                <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <span class="ativ-badge ${typeBadge}">${a.tipo.replace(/_/g, ' ')}</span>
                        ${contatoLabel ? `<span style="font-size:10px;color:#6b7280">→ ${contatoLabel}</span>` : ''}
                    </div>
                    <div class="flex items-center gap-2" style="flex-shrink:0">
                        ${prazoHtml}
                        <span style="font-size:9px;color:#9ca3af">${dateStr}</span>
                    </div>
                </div>
                <div class="ativ-desc" onclick="this.classList.toggle('expanded')">${esc(a.descricao || '')}</div>
                ${a.usuario_nome ? `<div style="font-size:9px;color:#9ca3af;margin-top:2px">por ${esc(a.usuario_nome)}</div>` : ''}
            </div>
        </div>
    </div>`;
}

function isPrazoOverdue(a) {
    if (!a.data_prazo || a.concluida) return false;
    const today = new Date(); today.setHours(0,0,0,0);
    return new Date(a.data_prazo) < today;
}

function getPrazoHtml(a) {
    if (!a.data_prazo) return '';
    const prazo = new Date(a.data_prazo);
    const today = new Date(); today.setHours(0,0,0,0);
    const diff = Math.ceil((prazo - today) / 86400000);
    const dateStr = prazo.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'});

    if (a.concluida) return `<span class="prazo-future" style="font-size:9px">${dateStr}</span>`;
    if (diff < 0) return `<span class="prazo-overdue" style="font-size:9px">${dateStr} (${Math.abs(diff)}d atrás)</span>`;
    if (diff === 0) return `<span class="prazo-today" style="font-size:9px">Hoje</span>`;
    if (diff <= 3) return `<span class="prazo-soon" style="font-size:9px">${dateStr}</span>`;
    return `<span class="prazo-future" style="font-size:9px">${dateStr}</span>`;
}

function toggleAtivForm() {
    const area = document.getElementById('ativ_form_area');
    area.style.display = area.style.display === 'none' ? '' : 'none';
}

function applySugestao(tipo, desc) {
    toggleAtivForm();
    document.getElementById('ativ_tipo').value = tipo;
    document.getElementById('ativ_desc').value = desc;
}

function onAtivTipoChange() {
    const tipo = document.getElementById('ativ_tipo').value;
    const desc = document.getElementById('ativ_desc');
    if (DEFAULT_DESCRIPTIONS[tipo] && !desc.value.trim()) {
        desc.value = DEFAULT_DESCRIPTIONS[tipo];
    }
}

async function addAtividade() {
    if (!selectedLeadId) return;
    const tipo = document.getElementById('ativ_tipo').value;
    const descricao = document.getElementById('ativ_desc').value.trim();
    if (!descricao) return showToast('Descreva a atividade', 'warning');

    try {
        await fetch(`/api/leads/${selectedLeadId}/atividades`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo,
                descricao,
                id_contato: document.getElementById('ativ_contato').value || null,
                data_prazo: document.getElementById('ativ_prazo').value || null,
            }),
        });
        loadTabAtividades(selectedLeadId);
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

function toggleConcluidas() {
    showConcluidas = !showConcluidas;
    const area = document.getElementById('concluidas_area');
    if (area) area.style.display = showConcluidas ? 'block' : 'none';
}

async function toggleConcluida(atividadeId, concluida) {
    try {
        await fetch(`/api/leads/atividades/${atividadeId}/concluir`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({concluida}),
        });
        loadTabAtividades(selectedLeadId);
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function melhorarTexto(textareaId) {
    const desc = document.getElementById(textareaId || 'modal_ativ_desc');
    if (!desc || !desc.value.trim()) return;
    try {
        const resp = await fetch('/api/ia/melhorar-texto', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texto: desc.value}),
        });
        const data = await resp.json();
        if (data.success) desc.value = data.texto;
    } catch (e) {}
}

// ======================== Tab: Extração ========================

async function loadTabExtracao(leadId) {
    const container = document.getElementById('section_extracao');
    container.innerHTML = skeletonHtml();

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

        container.innerHTML = `
            <div class="space-y-3" style="font-size:12px">
                <div class="bg-base-200 rounded-lg p-2 space-y-1.5">
                    <div class="flex items-center gap-1">
                        ${faviconHtml}
                        <input id="extrair_url" type="url" class="input input-xs input-bordered w-full" placeholder="https://..."
                               value="${esc(suggestedUrl)}" style="font-size:12px">
                    </div>
                    <button onclick="extractUrl()" class="leads-action-btn leads-action-btn-extrair" id="btn_extrair">
                        <span class="loading loading-spinner loading-xs hidden" id="extrair_spinner"></span>
                        Extrair com IA
                    </button>
                </div>
                <div id="extrair_resultado">${dadosHtml}</div>
            </div>`;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function getEmailDomainUrl(contatos) {
    if (!contatos || !contatos.length) return '';
    for (const c of contatos) {
        if (c.email) {
            const parts = c.email.split('@');
            if (parts.length === 2) {
                const domain = parts[1].toLowerCase();
                if (!FREE_DOMAINS.includes(domain)) return `https://${domain}`;
            }
        }
    }
    return '';
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
        ${descFull ? `<div><span id="${descId}" style="font-size:11px">${esc(descShort)}</span>${descFull.length > 150 ? ` <button onclick="document.getElementById('${descId}').textContent=\`${esc(descFull).replace(/`/g,'')}\`;this.remove()" style="color:#3b82f6;font-size:10px;background:none;border:none;cursor:pointer">ver mais</button>` : ''}</div>` : ''}
        <div class="flex flex-wrap gap-1.5">
            ${d.segmento ? `<span class="extract-pill" style="background:#f3f4f6;color:#4b5563">${esc(d.segmento)}</span>` : ''}
            ${d.porte_estimado || lead?.porte_estimado ? `<span class="extract-pill" style="background:#ede9fe;color:#6d28d9">${esc(d.porte_estimado || lead?.porte_estimado)}</span>` : ''}
        </div>
        ${d.mercado_alvo || lead?.mercado_alvo ? `<div style="font-size:11px"><span style="font-weight:600">Mercado alvo:</span> ${esc(d.mercado_alvo || lead?.mercado_alvo)}</div>` : ''}
        ${servicos.length ? `<div><span style="font-weight:600;font-size:11px">Serviços:</span><div class="extract-pills" style="margin-top:2px">${servicos.map(s => `<span class="extract-pill">${esc(s)}</span>`).join('')}</div></div>` : ''}
        ${redesHtml ? `<div style="display:flex;gap:4px;align-items:center">${redesHtml}</div>` : ''}
        ${d.presenca_digital || lead?.presenca_digital ? `<div style="font-size:11px"><span style="font-weight:600">Presença digital:</span> ${esc(d.presenca_digital || lead?.presenca_digital)}</div>` : ''}
        ${d.oportunidades_midia || lead?.oportunidades_midia ? `<div class="extract-oportunidades"><span style="font-weight:600">Oportunidades:</span> ${esc(d.oportunidades_midia || lead?.oportunidades_midia)}</div>` : ''}
        ${clientes.length ? `<div style="font-size:11px"><span style="font-weight:600">Clientes mencionados:</span> ${clientes.map(s => esc(s)).join(', ')}</div>` : ''}
        ${premios.length ? `<div style="font-size:11px"><span style="font-weight:600">Prêmios:</span> ${premios.map(s => esc(s)).join(', ')}</div>` : ''}
        ${contatos.length ? `
            <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin-top:4px">Contatos encontrados</div>
            ${contatos.map((c, i) => `<div style="background:#fff;border:1px solid #f3f4f6;border-radius:6px;padding:6px;display:flex;justify-content:space-between;align-items:center">
                <div><div style="font-weight:600;font-size:11px">${esc(c.nome || '?')}</div><div style="color:#9ca3af;font-size:10px">${[c.cargo, c.email, c.telefone].filter(Boolean).map(v => esc(v)).join(' | ')}</div></div>
                <button onclick="addExtractedContact(${i})" class="leads-action-btn leads-action-btn-merge" style="font-size:10px;flex:0;padding:4px 10px">+ Add</button>
            </div>`).join('')}
        ` : ''}
        <button onclick="saveExtracted()" class="leads-action-btn leads-action-btn-convert mt-2" style="width:100%">Salvar dados no lead</button>
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
    finally { btn.disabled = false; spinner.classList.add('hidden'); }
}

async function saveExtracted() {
    if (!selectedLeadId || !lastExtractedData) return showToast('Extraia dados primeiro', 'warning');
    const d = lastExtractedData;
    try {
        const url = d._url || '';
        let faviconUrl = '';
        if (url) { try { faviconUrl = `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=64`; } catch(e) {} }
        await fetch(`/api/leads/${selectedLeadId}/salvar-dados-extraidos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url_site: url, descricao_empresa: d.descricao || '', segmento: d.segmento || '',
                redes_sociais: d.redes_sociais || {}, servicos: d.servicos || [],
                clientes_mencionados: d.clientes_mencionados || [], dados_extraidos: d,
                favicon_url: faviconUrl, porte_estimado: d.porte_estimado || '',
                mercado_alvo: d.mercado_alvo || '', presenca_digital: d.presenca_digital || '',
                oportunidades_midia: d.oportunidades_midia || '', premios_certificacoes: d.premios_certificacoes || [],
            }),
        });
        showToast('Dados salvos!', 'success');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function addExtractedContact(idx) {
    if (!selectedLeadId || !lastExtractedData) return;
    const c = lastExtractedData.contatos_encontrados[idx];
    if (!c || !confirm(`Adicionar ${c.nome || '?'} como contato?`)) return;
    try {
        await fetch(`/api/leads/${selectedLeadId}/contatos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nome: c.nome || '', cargo: c.cargo || '', telefone: c.telefone || '', email: c.email || ''}),
        });
        loadTabContatos(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Tab: Comunicação IA ========================

async function loadTabComunicacao(leadId) {
    const container = document.getElementById('col_comunicacao');
    if (!container) return;
    container.innerHTML = skeletonHtml();

    try {
        const conResp = await fetch(`/api/leads/${leadId}/contatos`);
        const conData = await conResp.json();
        const contatos = conData.contatos || [];
        const contatoOptions = contatos.map(c => {
            const isSelected = selectedContactId ? c.id === selectedContactId : c.is_principal;
            return `<option value="${c.id}" ${isSelected ? 'selected' : ''}>${esc(c.nome)}</option>`;
        }).join('');

        const apresentacaoTemplates = COMM_TEMPLATES.filter((_, i) => i <= 4);
        const followupTemplates = COMM_TEMPLATES.filter((_, i) => i === 5 || i === 6);
        const eventoTemplates = COMM_TEMPLATES.filter((_, i) => i >= 7);

        function renderTemplateGroup(label, templates) {
            return `<div class="comm-group">
                <div style="font-size:9px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin-bottom:3px">${label}</div>
                <div class="flex flex-wrap gap-1">${templates.map(t => {
                    const globalIdx = COMM_TEMPLATES.indexOf(t);
                    const icon = t.tipo === 'whatsapp'
                        ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="#25D366" style="flex-shrink:0"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479c0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg>'
                        : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" style="flex-shrink:0"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>';
                    return `<button class="comm-template-btn" onclick="applyCommTemplate(${globalIdx})" style="display:inline-flex;align-items:center;gap:3px">${icon} ${esc(t.label)}</button>`;
                }).join('')}</div>
            </div>`;
        }

        container.innerHTML = `
            <div class="space-y-2" style="font-size:12px">
                <div class="space-y-2">
                    ${renderTemplateGroup('Apresentação', apresentacaoTemplates)}
                    ${renderTemplateGroup('Follow-up', followupTemplates)}
                    ${renderTemplateGroup('Eventos', eventoTemplates)}
                </div>
                <div style="border-top:1px solid #f3f4f6;padding-top:8px" class="space-y-1.5">
                    <div class="flex gap-1.5">
                        <select id="comm_contato" class="${SEL_CLS}" style="flex:1">
                            <option value="">Contato...</option>
                            ${contatoOptions}
                        </select>
                        <div class="flex gap-1.5 items-center" style="font-size:11px;flex-shrink:0">
                            <label style="display:flex;align-items:center;gap:2px;cursor:pointer"><input type="radio" name="comm_tipo" value="whatsapp" checked style="width:11px;height:11px"> WA</label>
                            <label style="display:flex;align-items:center;gap:2px;cursor:pointer"><input type="radio" name="comm_tipo" value="email" style="width:11px;height:11px"> Email</label>
                        </div>
                    </div>
                    <input id="comm_objetivo" class="input input-xs input-bordered w-full" placeholder="Objetivo personalizado..." style="font-size:11px">
                    <div class="flex gap-1.5">
                        <select id="comm_tamanho" class="${SEL_CLS}" style="flex:1"><option value="curto">Curto</option><option value="medio" selected>Médio</option><option value="longo">Longo</option></select>
                        <select id="comm_tom" class="${SEL_CLS}" style="flex:1"><option value="formal">Formal</option><option value="cordial" selected>Cordial</option><option value="descontraido">Descontraído</option></select>
                    </div>
                    <div class="flex flex-wrap gap-2" style="font-size:10px;color:#6b7280">
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer"><input type="checkbox" id="comm_incluir_dados" checked style="width:11px;height:11px"> Dados</label>
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer"><input type="checkbox" id="comm_incluir_servicos" style="width:11px;height:11px"> Serviços</label>
                        <label style="display:flex;align-items:center;gap:2px;cursor:pointer"><input type="checkbox" id="comm_incluir_oportunidades" style="width:11px;height:11px"> Oportunidades</label>
                    </div>
                    <button onclick="gerarComunicacao()" class="leads-action-btn leads-action-btn-gerar" id="btn_comm">
                        <span class="loading loading-spinner loading-xs hidden" id="comm_spinner"></span>
                        Gerar com IA
                    </button>
                </div>
            </div>`;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function applyCommTemplate(idx) {
    const t = COMM_TEMPLATES[idx];
    if (!t) return;
    const obj = document.getElementById('comm_objetivo');
    if (obj) obj.value = t.objetivo;
    const radios = document.querySelectorAll('input[name="comm_tipo"]');
    radios.forEach(r => { r.checked = r.value === t.tipo; });
    gerarComunicacao();
}

async function gerarComunicacao() {
    if (!selectedLeadId) return;
    const btn = document.getElementById('btn_comm');
    const spinner = document.getElementById('comm_spinner');
    if (!btn || !spinner) return;
    btn.disabled = true;
    spinner.classList.remove('hidden');

    const tipo = document.querySelector('input[name="comm_tipo"]:checked')?.value || 'whatsapp';
    const objetivo = document.getElementById('comm_objetivo')?.value?.trim();
    if (!objetivo) { showToast('Informe o objetivo', 'warning'); btn.disabled = false; spinner.classList.add('hidden'); return; }

    try {
        const resp = await fetch('/api/ia/gerar-comunicacao', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lead_id: selectedLeadId, tipo, objetivo,
                tamanho: document.getElementById('comm_tamanho')?.value || 'medio',
                tom: document.getElementById('comm_tom')?.value || 'cordial',
                incluir_dados_lead: document.getElementById('comm_incluir_dados')?.checked,
                incluir_servicos: document.getElementById('comm_incluir_servicos')?.checked,
                incluir_oportunidades: document.getElementById('comm_incluir_oportunidades')?.checked,
                contato_id: document.getElementById('comm_contato')?.value || null,
            }),
        });
        const data = await resp.json();
        if (data.success) openCommResultModal(data.texto, data.word_count, tipo);
        else showToast(data.message || 'Erro', 'error');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally { btn.disabled = false; spinner.classList.add('hidden'); }
}

function openCommResultModal(texto, wordCount, tipo) {
    const textEl = document.getElementById('modal_comm_text');
    textEl.textContent = texto;
    document.getElementById('modal_comm_word_count').textContent = wordCount + ' palavras';
    document.getElementById('modal_comm_preview').className = tipo === 'email' ? 'comm-preview comm-preview-email' : 'comm-preview';
    document.getElementById('modal_comunicacao_resultado').showModal();
}

function copyModalCommText() {
    const el = document.getElementById('modal_comm_text');
    if (el) navigator.clipboard.writeText(el.innerText).then(() => showToast('Copiado!', 'success'));
}

function openModalCommWA() {
    const el = document.getElementById('modal_comm_text');
    if (el) window.open(`https://wa.me/?text=${encodeURIComponent(el.innerText)}`, '_blank');
}

function openModalCommEmail() {
    const el = document.getElementById('modal_comm_text');
    if (!el) return;
    const text = el.innerText;
    const lines = text.split('\n');
    let subject = '', body = text;
    if (lines[0] && lines[0].toLowerCase().startsWith('assunto:')) {
        subject = lines[0].replace(/^assunto:\s*/i, '').trim();
        body = lines.slice(1).join('\n').trim();
    }
    window.open(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`);
}

// ======================== Edit / Merge / Desqualificar / Converter ========================

function openEditLead() {
    if (!selectedLeadData) return;
    const l = selectedLeadData;
    document.getElementById('edit_empresa').value = l.empresa || '';
    document.getElementById('edit_nome').value = l.nome || '';
    document.getElementById('edit_status').value = l.status || 'inbox';
    document.getElementById('edit_potencial').value = l.potencial || 'medio';
    document.getElementById('edit_tipo_lead').value = l.tipo_lead || 'cliente';
    document.getElementById('edit_fonte').value = l.fonte || 'manual';
    document.getElementById('edit_responsavel').value = l.id_executivo || '';
    document.getElementById('edit_origem').value = l.origem || '';
    document.getElementById('edit_canal').value = l.canal || '';
    document.getElementById('edit_interesse').value = l.interesse || '';
    document.getElementById('edit_segmento').value = l.segmento || '';
    document.getElementById('edit_porte_estimado').value = l.porte_estimado || '';
    document.getElementById('edit_url_site').value = l.url_site || '';
    document.getElementById('edit_valor_estimado').value = l.valor_estimado || '';
    document.getElementById('edit_valor_fechado').value = l.valor_fechado || '';
    document.getElementById('edit_qualificacao_score').value = l.qualificacao_score || 0;
    document.getElementById('edit_score_display').textContent = l.qualificacao_score || 0;
    document.getElementById('edit_qualificacao_notas').value = l.qualificacao_notas || '';
    document.getElementById('edit_notas_internas').value = l.notas_internas || '';
    document.getElementById('modal_editar_lead').showModal();
}

async function saveEditLead() {
    if (!selectedLeadId) return;
    try {
        const dados = {
            empresa: document.getElementById('edit_empresa').value.trim() || null,
            nome: document.getElementById('edit_nome').value.trim() || null,
            status: document.getElementById('edit_status').value,
            potencial: document.getElementById('edit_potencial').value,
            tipo_lead: document.getElementById('edit_tipo_lead').value,
            fonte: document.getElementById('edit_fonte').value,
            id_executivo: document.getElementById('edit_responsavel').value || null,
            origem: document.getElementById('edit_origem').value.trim() || null,
            canal: document.getElementById('edit_canal').value.trim() || null,
            interesse: document.getElementById('edit_interesse').value.trim() || null,
            segmento: document.getElementById('edit_segmento').value.trim() || null,
            porte_estimado: document.getElementById('edit_porte_estimado').value || null,
            url_site: document.getElementById('edit_url_site').value.trim() || null,
            valor_estimado: document.getElementById('edit_valor_estimado').value || null,
            valor_fechado: document.getElementById('edit_valor_fechado').value || null,
            qualificacao_score: parseInt(document.getElementById('edit_qualificacao_score').value) || 0,
            qualificacao_notas: document.getElementById('edit_qualificacao_notas').value.trim() || null,
            notas_internas: document.getElementById('edit_notas_internas').value.trim() || null,
        };
        await fetch(`/api/leads/${selectedLeadId}/editar`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(dados),
        });
        document.getElementById('modal_editar_lead').close();
        showToast('Lead atualizado!', 'success');
        loadTabDados(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function converterCliente() {
    if (!selectedLeadId || !selectedLeadData) return;
    const l = selectedLeadData;

    document.getElementById('cv_cnpj').value = '';
    document.getElementById('cv_cnpj_msg').textContent = '';
    document.getElementById('cv_nome_fantasia').value = l.empresa || '';
    document.getElementById('cv_razao_social').value = l.empresa || '';
    document.getElementById('cv_ie').value = '';
    document.getElementById('cv_im').value = '';
    document.getElementById('cv_cep').value = '';
    document.getElementById('cv_estado').value = '';
    document.getElementById('cv_cidade').value = '';
    document.getElementById('cv_bairro').value = '';
    document.getElementById('cv_logradouro').value = '';
    document.getElementById('cv_numero').value = '';
    document.getElementById('cv_complemento').value = '';

    if (l.id_executivo) {
        document.getElementById('cv_executivo').value = l.id_executivo;
    } else {
        document.getElementById('cv_executivo').value = '';
    }
    document.getElementById('cv_tipo_cliente').value = '';
    document.getElementById('cv_agencia').value = '';

    cvTogglePessoa('J');
    cvLoadContatos();

    document.getElementById('modal_converter').showModal();
}

// ======================== Converter: helpers ========================

function cvTogglePessoa(tipo) {
    const lblJ = document.getElementById('cv_label_pj');
    const lblF = document.getElementById('cv_label_pf');
    const lblCnpj = document.getElementById('cv_label_cnpj');
    const lblFantasia = document.getElementById('cv_label_fantasia');
    const razaoContainer = document.getElementById('cv_razao_container');
    const inscricoes = document.getElementById('cv_inscricoes');
    const agenciaContainer = document.getElementById('cv_agencia_container');

    if (tipo === 'J') {
        lblJ.querySelector('input').checked = true;
        lblJ.style.cssText = 'cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;padding:6px 12px;border:2px solid #22c55e;border-radius:8px 0 0 8px;font-size:12px;font-weight:600;background:#f0fdf4;color:#15803d';
        lblF.style.cssText = 'cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;padding:6px 12px;border:2px solid #d1d5db;border-radius:0 8px 8px 0;font-size:12px;font-weight:600;background:#fff;color:#6b7280';
        lblCnpj.textContent = 'CNPJ*';
        lblFantasia.textContent = 'Nome Fantasia*';
        razaoContainer.style.display = '';
        inscricoes.style.display = '';
        agenciaContainer.style.display = '';
        document.getElementById('cv_cnpj').placeholder = '00.000.000/0000-00';
        document.getElementById('cv_cnpj').maxLength = 18;
    } else {
        lblF.querySelector('input').checked = true;
        lblF.style.cssText = 'cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;padding:6px 12px;border:2px solid #22c55e;border-radius:0 8px 8px 0;font-size:12px;font-weight:600;background:#f0fdf4;color:#15803d';
        lblJ.style.cssText = 'cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;padding:6px 12px;border:2px solid #d1d5db;border-radius:8px 0 0 8px;font-size:12px;font-weight:600;background:#fff;color:#6b7280';
        lblCnpj.textContent = 'CPF*';
        lblFantasia.textContent = 'Nome Completo*';
        razaoContainer.style.display = 'none';
        inscricoes.style.display = 'none';
        agenciaContainer.style.display = 'none';
        document.getElementById('cv_cnpj').placeholder = '000.000.000-00';
        document.getElementById('cv_cnpj').maxLength = 14;
    }
    document.getElementById('cv_cnpj').value = '';
    document.getElementById('cv_cnpj_msg').textContent = '';
}

function cvMascaraCnpjCpf(input) {
    const pessoa = document.querySelector('input[name="cv_pessoa"]:checked')?.value || 'J';
    let v = input.value.replace(/\D/g, '');
    if (pessoa === 'F') {
        if (v.length > 11) v = v.slice(0, 11);
        v = v.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    } else {
        if (v.length > 14) v = v.slice(0, 14);
        v = v.replace(/(\d{2})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1/$2').replace(/(\d{4})(\d{1,2})$/, '$1-$2');
    }
    input.value = v;
}

function cvMascaraCep(input) {
    let v = input.value.replace(/\D/g, '');
    if (v.length > 8) v = v.slice(0, 8);
    if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5);
    input.value = v;
}

function cvValidarCPF(cpf) {
    cpf = cpf.replace(/\D/g, '');
    if (cpf.length !== 11 || /^([0-9])\1+$/.test(cpf)) return false;
    let soma = 0, resto;
    for (let i = 1; i <= 9; i++) soma += parseInt(cpf.substring(i-1, i)) * (11 - i);
    resto = (soma * 10) % 11;
    if (resto === 10 || resto === 11) resto = 0;
    if (resto !== parseInt(cpf.substring(9, 10))) return false;
    soma = 0;
    for (let i = 1; i <= 10; i++) soma += parseInt(cpf.substring(i-1, i)) * (12 - i);
    resto = (soma * 10) % 11;
    if (resto === 10 || resto === 11) resto = 0;
    return resto === parseInt(cpf.substring(10, 11));
}

async function cvOnCnpjBlur() {
    const pessoa = document.querySelector('input[name="cv_pessoa"]:checked')?.value || 'J';
    const doc = document.getElementById('cv_cnpj').value.replace(/\D/g, '');
    const msg = document.getElementById('cv_cnpj_msg');
    if (!doc) return;

    if (pessoa === 'F') {
        if (!cvValidarCPF(doc)) {
            msg.textContent = 'CPF inválido!';
            msg.style.color = '#dc2626';
            return;
        }
        msg.textContent = '';
        try {
            const resp = await fetch(`/api/verifica_documento?doc=${encodeURIComponent(doc)}&tipo=F`);
            const data = await resp.json();
            if (data.existe) {
                msg.textContent = 'CPF já cadastrado!';
                msg.style.color = '#dc2626';
            }
        } catch (e) { console.error(e); }
    } else {
        if (doc.length !== 14) {
            msg.textContent = 'CNPJ inválido!';
            msg.style.color = '#dc2626';
            return;
        }
        msg.textContent = 'Buscando dados do CNPJ...';
        msg.style.color = '#2563eb';
        try {
            const resp = await fetch('/api/buscar_cnpj/' + doc);
            const result = await resp.json();
            if (result.success) {
                const d = result.data;
                if (d.razao_social) document.getElementById('cv_razao_social').value = d.razao_social;
                if (d.nome_fantasia) document.getElementById('cv_nome_fantasia').value = d.nome_fantasia;
                else if (d.razao_social) document.getElementById('cv_nome_fantasia').value = d.razao_social;
                if (d.inscricao_estadual) document.getElementById('cv_ie').value = d.inscricao_estadual;
                if (d.inscricao_municipal) document.getElementById('cv_im').value = d.inscricao_municipal;
                if (d.cep) {
                    let cep = d.cep.replace(/\D/g, '');
                    if (cep.length === 8) cep = cep.slice(0, 5) + '-' + cep.slice(5);
                    document.getElementById('cv_cep').value = cep;
                }
                if (d.uf) {
                    const sel = document.getElementById('cv_estado');
                    for (const opt of sel.options) {
                        if (opt.dataset.sigla === d.uf) { sel.value = opt.value; break; }
                    }
                }
                if (d.municipio) document.getElementById('cv_cidade').value = d.municipio;
                if (d.bairro) document.getElementById('cv_bairro').value = d.bairro;
                if (d.logradouro) document.getElementById('cv_logradouro').value = d.logradouro;
                if (d.numero) document.getElementById('cv_numero').value = d.numero;
                if (d.complemento) document.getElementById('cv_complemento').value = d.complemento;
                msg.textContent = '';
                showToast('Dados do CNPJ carregados!', 'success');
            } else {
                msg.textContent = result.message || 'CNPJ inválido!';
                msg.style.color = '#dc2626';
                if (result.ja_cadastrado) showToast(result.message, 'error');
            }
        } catch (e) {
            msg.textContent = 'Erro ao consultar CNPJ';
            msg.style.color = '#dc2626';
        }
    }
}

async function cvLoadContatos() {
    const container = document.getElementById('cv_contatos_list');
    if (!selectedLeadId) { container.innerHTML = '<div class="text-xs text-gray-400">Nenhum contato</div>'; return; }
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/contatos`);
        const data = await resp.json();
        const contatos = data.contatos || [];
        if (contatos.length === 0) {
            container.innerHTML = '<div class="text-xs text-gray-400">Nenhum contato cadastrado neste lead</div>';
            return;
        }
        container.innerHTML = contatos.map(c => `
            <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;font-size:12px">
                <span style="font-weight:600;color:#111827;min-width:120px">${esc(c.nome || '-')}</span>
                <span style="color:#6b7280">${esc(c.cargo || '')}</span>
                <span style="color:#6b7280">${esc(c.telefone || '')}</span>
                <span style="color:#2563eb">${esc(c.email || '')}</span>
                ${c.is_principal ? '<span style="color:#059669;font-weight:600;font-size:10px">PRINCIPAL</span>' : ''}
            </div>`).join('');
    } catch (e) {
        container.innerHTML = '<div class="text-xs text-red-500">Erro ao carregar contatos</div>';
    }
}

async function cvSubmitConversao() {
    const pessoa = document.querySelector('input[name="cv_pessoa"]:checked')?.value || 'J';
    const cnpj = document.getElementById('cv_cnpj').value.replace(/\D/g, '');
    const nomeFantasia = document.getElementById('cv_nome_fantasia').value.trim();
    const razaoSocial = document.getElementById('cv_razao_social').value.trim();
    const tipoCliente = document.getElementById('cv_tipo_cliente').value;
    const executivo = document.getElementById('cv_executivo').value;
    const agencia = document.getElementById('cv_agencia').value;

    if (!cnpj) return showToast('Informe o CNPJ/CPF', 'warning');
    if (pessoa === 'F' && !cvValidarCPF(cnpj)) return showToast('CPF inválido', 'warning');
    if (pessoa === 'J' && cnpj.length !== 14) return showToast('CNPJ inválido', 'warning');
    if (!nomeFantasia) return showToast('Informe o Nome Fantasia', 'warning');
    if (pessoa === 'J' && !razaoSocial) return showToast('Informe a Razão Social', 'warning');
    if (!tipoCliente) return showToast('Selecione o Tipo de Cliente', 'warning');
    if (!executivo) return showToast('Selecione o Executivo', 'warning');
    if (pessoa === 'J' && !agencia) return showToast('Selecione a Agência', 'warning');

    const msgEl = document.getElementById('cv_cnpj_msg');
    if (msgEl.textContent.includes('já cadastrado')) return showToast('CNPJ/CPF já cadastrado', 'error');

    const payload = {
        pessoa,
        cnpj,
        nome_fantasia: nomeFantasia,
        razao_social: pessoa === 'J' ? razaoSocial : nomeFantasia,
        id_tipo_cliente: parseInt(tipoCliente),
        vendas_central_comm: parseInt(executivo),
        pk_id_tbl_agencia: pessoa === 'J' ? parseInt(agencia) : 2,
        inscricao_estadual: document.getElementById('cv_ie').value.trim() || null,
        inscricao_municipal: document.getElementById('cv_im').value.trim() || null,
        cep: document.getElementById('cv_cep').value.replace(/\D/g, '') || null,
        pk_id_aux_estado: document.getElementById('cv_estado').value || null,
        cidade: document.getElementById('cv_cidade').value.trim() || null,
        bairro: document.getElementById('cv_bairro').value.trim() || null,
        logradouro: document.getElementById('cv_logradouro').value.trim() || null,
        numero: document.getElementById('cv_numero').value.trim() || null,
        complemento: document.getElementById('cv_complemento').value.trim() || null,
    };

    const btn = document.getElementById('cv_btn_submit');
    btn.disabled = true;
    btn.textContent = 'Convertendo...';

    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/converter-cliente`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_converter').close();
            showToast('Lead convertido em cliente com sucesso!', 'success');
            loadTabDados(selectedLeadId);
            loadLeads();
            if (currentView === 'kanban') loadKanban();
        } else {
            showToast(data.message || 'Erro ao converter', 'error');
        }
    } catch (e) {
        showToast('Erro: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Converter em Cliente';
    }
}

function openMergeModal() {
    if (!selectedLeadId) return;
    document.getElementById('merge_search').value = '';
    document.getElementById('merge_results').innerHTML = '';
    document.getElementById('modal_mesclar').showModal();
}

async function searchMergeLeads() {
    const q = document.getElementById('merge_search').value.trim();
    if (!q) { document.getElementById('merge_results').innerHTML = ''; return; }
    try {
        const resp = await fetch(`/api/leads?search=${encodeURIComponent(q)}`);
        const data = await resp.json();
        const leads = (data.leads || []).filter(l => l.id !== selectedLeadId).slice(0, 10);
        document.getElementById('merge_results').innerHTML = leads.map(l => `
            <div class="bg-base-200 rounded p-2 flex items-center justify-between cursor-pointer hover:bg-base-300" onclick="confirmMerge(${l.id}, '${esc(l.nome_lead)}')">
                <div><div class="font-semibold text-sm">${esc(l.nome_lead)}</div><div class="text-xs text-gray-500">${l.status} | ${l.potencial || ''}</div></div>
                <span class="text-xs text-primary">Mesclar →</span>
            </div>`).join('');
    } catch(e) {}
}

async function confirmMerge(secundarioId, nome) {
    if (!confirm(`Mesclar "${nome}" no lead atual? O lead selecionado será excluído.`)) return;
    try {
        await fetch(`/api/leads/${selectedLeadId}/mesclar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lead_secundario_id: secundarioId}),
        });
        document.getElementById('modal_mesclar').close();
        showToast('Leads mesclados!', 'success');
        loadTabDados(selectedLeadId);
        loadTabContatos(selectedLeadId);
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

function openDesqualificar() {
    if (!selectedLeadId) return;
    document.getElementById('motivo_desqualificacao').value = '';
    document.getElementById('modal_desqualificar').showModal();
}

async function confirmDesqualificar() {
    const motivo = document.getElementById('motivo_desqualificacao').value;
    if (!motivo) return showToast('Selecione o motivo', 'warning');
    try {
        await fetch(`/api/leads/${selectedLeadId}/desqualificar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({motivo}),
        });
        document.getElementById('modal_desqualificar').close();
        showToast('Lead desqualificado', 'success');
        selectedLeadId = null;
        clearDetail();
        loadLeads();
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Novo Lead ========================

function openNewLeadModal() {
    ['new_nome','new_email','new_telefone','new_empresa','new_cargo','new_url_site',
     'new_origem','new_canal','new_interesse','new_segmento','new_notas_internas'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('new_fonte').value = 'manual';
    document.getElementById('new_potencial').value = 'medio';
    document.getElementById('new_tipo_lead').value = 'cliente';
    document.getElementById('new_responsavel').value = getExecutivoId() || '';
    document.getElementById('new_valor_estimado').value = '';
    document.getElementById('modal_novo_lead').showModal();
}

async function saveNewLead() {
    const nome = document.getElementById('new_nome').value.trim();
    if (!nome) return showToast('Nome é obrigatório', 'warning');

    try {
        const resp = await fetch('/api/leads/novo', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                nome,
                email: document.getElementById('new_email').value.trim(),
                telefone: document.getElementById('new_telefone').value.trim() || null,
                empresa: document.getElementById('new_empresa').value.trim() || null,
                cargo: document.getElementById('new_cargo').value.trim() || null,
                url_site: document.getElementById('new_url_site').value.trim() || null,
                fonte: document.getElementById('new_fonte').value,
                potencial: document.getElementById('new_potencial').value,
                tipo_lead: document.getElementById('new_tipo_lead').value,
                origem: document.getElementById('new_origem').value.trim() || null,
                canal: document.getElementById('new_canal').value.trim() || null,
                interesse: document.getElementById('new_interesse').value.trim() || null,
                segmento: document.getElementById('new_segmento').value.trim() || null,
                valor_estimado: document.getElementById('new_valor_estimado').value || null,
                id_executivo: document.getElementById('new_responsavel').value || null,
                notas_internas: document.getElementById('new_notas_internas').value.trim() || null,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_novo_lead').close();
            showToast('Lead criado!', 'success');
            loadLeads();
            if (currentView === 'kanban') loadKanban();
        } else showToast(data.message || 'Erro', 'error');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Kanban Board ========================

async function loadKanban() {
    const execId = getExecutivoId();
    let url = '/api/leads/kanban';
    if (execId) url += `?id_executivo=${execId}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        const grouped = {};
        KANBAN_STATUSES.forEach(s => grouped[s] = []);
        (data.contatos || []).forEach(c => {
            const st = c.status_pipeline || 'inbox';
            if (grouped[st]) grouped[st].push(c);
        });

        KANBAN_STATUSES.forEach(status => {
            const col = document.querySelector(`[data-drop="${status}"]`);
            const countEl = document.querySelector(`[data-count="${status}"]`);
            if (!col) return;

            countEl.textContent = grouped[status].length;

            const byClient = {};
            grouped[status].forEach(c => {
                const key = c.lead_id;
                if (!byClient[key]) byClient[key] = { empresa: c.empresa || 'Sem empresa', lead_id: c.lead_id, contatos: [] };
                byClient[key].contatos.push(c);
            });

            col.innerHTML = Object.values(byClient).map(group => `
                <div class="kanban-client-group">
                    <div class="kanban-client-header" onclick="selectLeadFromKanban(${group.lead_id})">
                        <span class="kanban-client-name">${esc(group.empresa)}</span>
                        <span class="kanban-client-count">${group.contatos.length}</span>
                    </div>
                    ${group.contatos.map(c => `
                        <div class="kanban-card" draggable="true" data-contato-id="${c.contato_id}" data-lead-id="${c.lead_id}" onclick="event.stopPropagation();selectContactFromKanban(${c.contato_id}, ${c.lead_id})">
                            <div class="kanban-card-title">${esc(c.contato_nome)}${c.is_principal ? ' <span style="font-size:8px;background:#dcfce7;color:#15803d;padding:0 4px;border-radius:9999px;vertical-align:middle">★</span>' : ''}</div>
                            ${c.cargo ? `<div style="font-size:10px;color:#6b7280">${esc(c.cargo)}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            `).join('');
        });

        initKanbanDragDrop();
    } catch (e) {
        console.error('loadKanban:', e);
    }
}

function selectLeadFromKanban(leadId) {
    toggleView('list');
    setTimeout(() => selectLead(leadId), 200);
}

function selectContactFromKanban(contatoId, leadId) {
    toggleView('list');
    setTimeout(() => selectContact(contatoId, leadId), 200);
}

function initKanbanDragDrop() {
    document.querySelectorAll('.kanban-card[draggable="true"]').forEach(card => {
        card.addEventListener('dragstart', e => {
            card.classList.add('dragging');
            e.dataTransfer.setData('text/plain', card.dataset.contatoId);
            e.dataTransfer.effectAllowed = 'move';
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            document.querySelectorAll('.kanban-column').forEach(c => c.classList.remove('drag-over'));
        });
    });

    document.querySelectorAll('.kanban-column').forEach(col => {
        col.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; col.classList.add('drag-over'); });
        col.addEventListener('dragleave', e => { if (e.relatedTarget && !col.contains(e.relatedTarget)) col.classList.remove('drag-over'); });
        col.addEventListener('drop', async e => {
            e.preventDefault();
            col.classList.remove('drag-over');
            const contatoId = e.dataTransfer.getData('text/plain');
            const newStatus = col.dataset.status;
            if (!contatoId || !newStatus) return;
            try {
                const resp = await fetch(`/api/leads/contatos/${contatoId}/pipeline-move`, {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: newStatus}),
                });
                const data = await resp.json();
                if (data.success) loadKanban();
                else showToast(data.message || 'Erro', 'error');
            } catch (err) { showToast('Erro: ' + err.message, 'error'); }
        });
    });
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
        const tipoLead = document.getElementById('import_tipo').value;
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
    finally { btn.disabled = false; spinner.classList.add('hidden'); }
}

function renderImportPreview() {
    const count = importParsedLeads.filter(l => l._selected).length;
    document.getElementById('import_preview').innerHTML =
        `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span class="text-sm text-gray-500">${count} de ${importParsedLeads.length} selecionado(s)</span>
            <button onclick="toggleAllImport()" style="font-size:12px;color:#2563eb;background:none;border:none;cursor:pointer;font-weight:500">
                ${count === importParsedLeads.length ? 'Desmarcar todos' : 'Selecionar todos'}
            </button>
        </div>` +
        importParsedLeads.map((l, i) => `
        <div style="background:#f9fafb;border:1px solid ${l._selected ? '#bfdbfe' : '#e5e7eb'};border-radius:10px;padding:12px;transition:border-color .15s">
            <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:6px">
                <input type="checkbox" style="width:18px;height:18px;accent-color:#2563eb;cursor:pointer;flex-shrink:0" ${l._selected ? 'checked' : ''} onchange="importParsedLeads[${i}]._selected=this.checked;renderImportPreview()">
                <span class="font-semibold text-sm">${esc(l.empresa || 'Sem empresa')}</span>
            </label>
            <div style="margin-left:28px" class="space-y-1">
                ${(l.contatos || []).map(c => `<div class="text-xs text-gray-600">
                    ${esc(c.nome || '')}${c.cargo ? ` (${esc(c.cargo)})` : ''}${c.telefone ? ` | ${esc(c.telefone)}` : ''}${c.email ? ` | ${esc(c.email)}` : ''}${c.principal ? ' ★' : ''}
                </div>`).join('')}
            </div>
        </div>`).join('');
}

function toggleAllImport() {
    const allSelected = importParsedLeads.every(l => l._selected);
    importParsedLeads.forEach(l => l._selected = !allSelected);
    renderImportPreview();
}

function backToStep1() {
    document.getElementById('import_step1').classList.remove('hidden');
    document.getElementById('import_step2').classList.add('hidden');
}

async function confirmImport() {
    const selected = importParsedLeads.filter(l => l._selected);
    if (selected.length === 0) return showToast('Selecione ao menos um lead', 'warning');
    const importExecId = document.getElementById('import_responsavel').value;
    const tipoLead = document.getElementById('import_tipo').value;
    const fonte = document.getElementById('import_fonte').value;
    try {
        const resp = await fetch('/api/leads/importar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                leads: selected.map(l => ({empresa: l.empresa, contatos: l.contatos})),
                id_executivo: importExecId ? parseInt(importExecId) : null,
                tipo_lead: tipoLead,
                fonte,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modal_importar').close();
            showToast(`${data.total} lead(s) importado(s)!`, 'success');
            loadLeads();
            if (currentView === 'kanban') loadKanban();
        } else showToast(data.message || 'Erro ao importar', 'error');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

// ======================== Utilities ========================

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const tooltip = document.createElement('span');
        tooltip.className = 'copy-tooltip show';
        tooltip.textContent = 'Copiado!';
        tooltip.style.top = '-20px';
        tooltip.style.left = '50%';
        tooltip.style.transform = 'translateX(-50%) translateY(-4px)';
        btn.style.position = 'relative';
        btn.appendChild(tooltip);
        setTimeout(() => tooltip.remove(), 1200);
    });
}

function maskPhone(v) {
    v = v.replace(/\D/g, '');
    if (v.length > 11) v = v.substring(0, 11);
    if (v.length > 6) return `(${v.substring(0,2)}) ${v.substring(2,7)}-${v.substring(7)}`;
    if (v.length > 2) return `(${v.substring(0,2)}) ${v.substring(2)}`;
    return v;
}

function applyPhoneMask(input) {
    input.value = maskPhone(input.value);
}

function esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showToast(msg, type) {
    if (typeof window.showToast === 'function' && window.showToast !== showToast) {
        window.showToast(msg, type);
        return;
    }
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'success'} fixed bottom-4 right-4 z-50 shadow-lg`;
    toast.style.cssText = 'max-width:400px;font-size:13px;padding:10px 16px;';
    toast.innerHTML = `<span>${esc(msg)}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ======================== Sidebar Toggle ========================

function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
    const sidebar = document.getElementById('leads_sidebar');
    const collapsed = document.getElementById('sidebar_collapsed');
    const grid = document.getElementById('view_list');

    if (sidebarCollapsed) {
        sidebar.style.display = 'none';
        collapsed.style.display = '';
        grid.classList.add('has-sidebar-collapsed');
        const count = document.getElementById('leads_count').textContent;
        document.getElementById('leads_count_collapsed').textContent = count;
    } else {
        sidebar.style.display = '';
        collapsed.style.display = 'none';
        grid.classList.remove('has-sidebar-collapsed');
    }
}

// ======================== Nova Atividade Modal ========================

const ATIV_TYPE_ICONS = {
    ligacao: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>',
    email_enviado: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 7l-10 7L2 7"/></svg>',
    whatsapp: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></svg>',
    reuniao: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    follow_up: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>',
    apresentacao: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h20v14H2z"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="8" y1="21" x2="16" y2="21"/></svg>',
    proposta_enviada: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    nota: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
};

const ATIV_TYPE_LABELS = {
    ligacao: 'Ligação', email_enviado: 'Email', whatsapp: 'WhatsApp',
    reuniao: 'Reunião', follow_up: 'Follow-up', apresentacao: 'Apresentação',
    proposta_enviada: 'Proposta', nota: 'Nota',
};

async function openNovaAtividadeModal() {
    if (!selectedLeadId) return showToast('Selecione um lead', 'warning');

    modalAtivSelectedTipo = null;
    const tiposGrid = document.getElementById('modal_ativ_tipos');
    tiposGrid.innerHTML = Object.entries(ATIV_TYPE_LABELS).map(([key, label]) => {
        return `<button type="button" class="ativ-type-btn" data-tipo="${key}" onclick="selectAtivType('${key}')">
            ${ATIV_TYPE_ICONS[key] || ''}
            <span>${label}</span>
        </button>`;
    }).join('');

    document.getElementById('modal_ativ_desc').value = '';
    document.getElementById('modal_ativ_prazo').value = '';
    document.getElementById('modal_ativ_prazo').style.display = 'none';
    document.querySelectorAll('.prazo-shortcut-btn').forEach(b => b.classList.remove('active'));

    try {
        const cr = await fetch(`/api/leads/${selectedLeadId}/contatos`);
        const cd = await cr.json();
        const contatos = cd.contatos || [];
        const sel = document.getElementById('modal_ativ_contato');
        sel.innerHTML = '<option value="">Selecione um contato...</option>' +
            contatos.map(c => {
                const isSelected = selectedContactId ? c.id === selectedContactId : c.is_principal;
                return `<option value="${c.id}" ${isSelected ? 'selected' : ''}>${esc(c.nome)}${c.cargo ? ' (' + esc(c.cargo) + ')' : ''}</option>`;
            }).join('');
    } catch (e) {}

    document.getElementById('modal_nova_atividade').showModal();

    fetchSugestaoIA(selectedLeadId);
}

function selectAtivType(tipo) {
    modalAtivSelectedTipo = tipo;
    document.querySelectorAll('.ativ-type-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tipo === tipo);
    });
    const desc = document.getElementById('modal_ativ_desc');
    if (DEFAULT_DESCRIPTIONS[tipo] && !desc.value.trim()) {
        desc.value = DEFAULT_DESCRIPTIONS[tipo];
    }
}

function setPrazoShortcut(days) {
    const input = document.getElementById('modal_ativ_prazo');
    document.querySelectorAll('.prazo-shortcut-btn').forEach(b => b.classList.remove('active'));

    if (days === -1) {
        input.style.display = '';
        input.focus();
        return;
    }

    const date = new Date();
    date.setDate(date.getDate() + days);
    const iso = date.toISOString().split('T')[0];
    input.value = iso;
    input.style.display = '';

    event?.target?.classList?.add('active');
}

async function saveNovaAtividade() {
    if (!selectedLeadId) return;
    if (!modalAtivSelectedTipo) return showToast('Selecione o tipo da atividade', 'warning');
    const contato = document.getElementById('modal_ativ_contato').value;
    if (!contato) return showToast('Selecione um contato', 'warning');
    const descricao = document.getElementById('modal_ativ_desc').value.trim();
    if (!descricao) return showToast('Descreva a atividade', 'warning');
    const prazo = document.getElementById('modal_ativ_prazo').value || null;

    try {
        await fetch(`/api/leads/${selectedLeadId}/atividades`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tipo: modalAtivSelectedTipo,
                descricao,
                id_contato: contato,
                data_prazo: prazo,
            }),
        });
        document.getElementById('modal_nova_atividade').close();
        showToast('Atividade registrada!', 'success');
        loadTabAtividades(selectedLeadId);
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function fetchSugestaoIA(leadId) {
    const container = document.getElementById('modal_ativ_sugestao');
    if (!container) return;
    container.innerHTML = '<div style="font-size:10px;color:#9ca3af;padding:4px 0">Buscando sugestão IA...</div>';

    try {
        const resp = await fetch('/api/ia/sugerir-atividade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lead_id: leadId}),
        });
        const data = await resp.json();
        if (data.success && data.sugestao) {
            const s = data.sugestao;
            container.innerHTML = `
                <div class="sugestao-ia-chip" onclick="applySugestaoIA(this)" data-tipo="${esc(s.tipo)}" data-desc="${esc(s.descricao)}" data-prazo="${s.prazo_dias || 0}">
                    <div>
                        <div class="sugestao-label">Sugestão IA</div>
                        <div class="sugestao-text">${esc(s.descricao)}</div>
                        <div style="font-size:9px;color:#a16207;margin-top:2px">${esc(s.motivo || '')}</div>
                    </div>
                </div>`;
        } else {
            container.innerHTML = '';
        }
    } catch (e) {
        container.innerHTML = '';
    }
}

function applySugestaoIA(chip) {
    const tipo = chip.dataset.tipo;
    const desc = chip.dataset.desc;
    const prazoDias = parseInt(chip.dataset.prazo) || 0;

    if (tipo) selectAtivType(tipo);
    if (desc) document.getElementById('modal_ativ_desc').value = desc;
    if (prazoDias > 0) setPrazoShortcut(prazoDias);

    chip.style.opacity = '0.5';
    chip.style.pointerEvents = 'none';
}

async function melhorarTextoModal() {
    const btn = document.getElementById('btn_melhorar_texto');
    const spinner = document.getElementById('melhorar_spinner');
    if (btn) btn.disabled = true;
    if (spinner) spinner.classList.remove('hidden');

    await melhorarTexto('modal_ativ_desc');

    if (btn) btn.disabled = false;
    if (spinner) spinner.classList.add('hidden');
}
