/* Leads V2 — Dashboard de Prospecção (Reestruturado) */

const SEL_CLS = 'text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1 text-gray-700 focus:outline-none focus:border-gray-400 w-full';

let selectedLeadId = null;
let selectedLeadData = null;
let importParsedLeads = [];
let searchTimeout = null;
let showConcluidas = false;
let currentView = 'list';
let currentTab = 'dados';

const FREE_DOMAINS = ['gmail.com','yahoo.com','hotmail.com','outlook.com','live.com','icloud.com','aol.com','msn.com','uol.com.br','bol.com.br','terra.com.br','ig.com.br','globo.com','protonmail.com'];

const STATUS_LABELS = {inbox:'Inbox', contato:'Contato', qualificado:'Qualificado', nao_qualificado:'Não Qualificado', proposta:'Proposta', negociacao:'Negociação', fechado_ganho:'Fechado (Ganho)', fechado_perdido:'Fechado (Perdido)'};
const STATUS_LIST = ['inbox','contato','qualificado','proposta','negociacao'];
const KANBAN_STATUSES = ['inbox','contato','qualificado','proposta','negociacao','fechado_ganho'];
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
    loadLinksContent();
    initRelatorioAnos();
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
    document.getElementById('lead_tabs').style.display = 'none';
    document.getElementById('lead_detail_area').innerHTML = '<div class="leads-empty">Selecione um lead</div>';
    document.getElementById('lead_detail_area').style.display = '';
    ['tab_dados','tab_contatos','tab_atividades','tab_extracao','tab_comunicacao'].forEach(id => {
        document.getElementById(id).style.display = 'none';
    });
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

    try {
        const resp = await fetch(url + params.join('&'));
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        const leads = data.leads || [];
        document.getElementById('leads_count').textContent = leads.length;
        const container = document.getElementById('leads_cards');

        if (leads.length === 0) {
            container.innerHTML = '<div class="leads-empty">Nenhum lead encontrado</div>';
            return;
        }

        container.innerHTML = leads.map(l => {
            const scoreCls = (l.qualificacao_score || 0) >= 70 ? 'high' : (l.qualificacao_score || 0) >= 30 ? 'mid' : 'low';
            return `<div class="lead-card ${selectedLeadId === l.id ? 'lead-card-active' : ''}" onclick="selectLead(${l.id})">
                <div class="flex items-center justify-between">
                    <span class="font-semibold text-gray-800 truncate">${esc(l.nome_lead)}</span>
                    <span class="status-badge status-badge-${l.status}" style="font-size:9px;padding:1px 6px">${STATUS_LABELS[l.status] || l.status}</span>
                </div>
                <div class="flex items-center gap-2 mt-1" style="font-size:10px;color:#9ca3af">
                    ${l.contato_principal_nome ? `<span>${esc(l.contato_principal_nome)}</span>` : ''}
                    ${l.qtd_contatos > 0 ? `<span>${l.qtd_contatos} contato${l.qtd_contatos > 1 ? 's' : ''}</span>` : ''}
                </div>
                <div class="flex items-center gap-2 mt-1 flex-wrap">
                    ${l.potencial ? `<span class="potencial-badge-${l.potencial}" style="font-size:9px;padding:1px 6px;border-radius:9999px">${POTENCIAL_LABELS[l.potencial] || l.potencial}</span>` : ''}
                    ${l.fonte ? `<span style="font-size:9px;color:#6b7280">${esc(l.fonte)}</span>` : ''}
                    ${l.valor_estimado ? `<span style="font-size:9px;color:#059669;font-weight:600">R$ ${Number(l.valor_estimado).toLocaleString('pt-BR')}</span>` : ''}
                    ${l.qualificacao_score ? `<span class="score-gauge"><span class="score-gauge-bar"><span class="score-gauge-fill ${scoreCls}" style="width:${l.qualificacao_score}%"></span></span>${l.qualificacao_score}</span>` : ''}
                    ${l.dias_sem_atividade > 7 ? `<span style="font-size:9px;color:#ef4444">${l.dias_sem_atividade}d</span>` : ''}
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        document.getElementById('leads_cards').innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

function potencialBadge(p) {
    if (!p) return '';
    return `<span class="potencial-badge-${p}" style="font-size:9px;padding:1px 6px;border-radius:9999px">${POTENCIAL_LABELS[p] || p}</span>`;
}

// ======================== Select Lead & Tabs ========================

async function selectLead(leadId) {
    selectedLeadId = leadId;

    document.querySelectorAll('.lead-card').forEach(el => el.classList.remove('lead-card-active'));
    event?.target?.closest?.('.lead-card')?.classList.add('lead-card-active');

    document.getElementById('lead_tabs').style.display = 'flex';
    document.getElementById('lead_detail_area').style.display = 'none';

    const tabDados = document.getElementById('tab_dados');
    tabDados.innerHTML = skeletonHtml();
    tabDados.style.display = '';

    ['tab_contatos','tab_atividades','tab_extracao','tab_comunicacao'].forEach(id => {
        document.getElementById(id).style.display = 'none';
        document.getElementById(id).innerHTML = '';
    });

    currentTab = 'dados';
    document.querySelectorAll('.lead-tab').forEach(t => {
        t.classList.toggle('lead-tab-active', t.dataset.tab === 'dados');
    });

    await loadTabDados(leadId);
}

function switchTab(tabName) {
    currentTab = tabName;
    document.querySelectorAll('.lead-tab').forEach(t => {
        t.classList.toggle('lead-tab-active', t.dataset.tab === tabName);
    });

    const tabs = ['dados','contatos','atividades','extracao','comunicacao'];
    tabs.forEach(t => {
        document.getElementById('tab_' + t).style.display = t === tabName ? '' : 'none';
    });

    if (!selectedLeadId) return;

    const container = document.getElementById('tab_' + tabName);
    if (container.innerHTML.trim() === '' || container.innerHTML.includes('skeleton-line')) {
        switch(tabName) {
            case 'dados': loadTabDados(selectedLeadId); break;
            case 'contatos': loadTabContatos(selectedLeadId); break;
            case 'atividades': loadTabAtividades(selectedLeadId); break;
            case 'extracao': loadTabExtracao(selectedLeadId); break;
            case 'comunicacao': loadTabComunicacao(selectedLeadId); break;
        }
    }
}

// ======================== Tab: Dados ========================

async function loadTabDados(leadId) {
    const container = document.getElementById('tab_dados');
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

                <!-- Ações -->
                <div class="flex gap-2 flex-wrap" style="padding-top:8px;border-top:1px solid #f3f4f6">
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
    const container = document.getElementById('tab_contatos');
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

    return `<div class="contact-card">
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
    const container = document.getElementById('tab_atividades');
    container.innerHTML = skeletonHtml();

    try {
        const resp = await fetch(`/api/leads/${leadId}/atividades`);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);
        const atividades = data.atividades || [];

        const tipos = ['nota','ligacao','email_enviado','whatsapp','reuniao','follow_up','apresentacao','proposta_enviada','tentativa_contato','outro'];

        let sugestao = '';
        const lastAtiv = atividades.find(a => a.tipo !== 'status_change' && a.tipo !== 'importacao');
        if (!lastAtiv) {
            sugestao = `<div class="ativ-sugestao" onclick="applySugestao('ligacao', 'Primeiro contato com o lead')">
                <div style="font-size:10px;color:#92400e;font-weight:600">Sugestão</div>
                <div style="font-size:11px;color:#78350f">Registrar primeiro contato</div>
            </div>`;
        }

        let contatoOptions = '';
        try {
            const cr = await fetch(`/api/leads/${leadId}/contatos`);
            const cd = await cr.json();
            contatoOptions = (cd.contatos || []).map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('');
        } catch(e) {}

        const pendentes = atividades.filter(a => !a.concluida);
        const concluidas = atividades.filter(a => a.concluida);

        container.innerHTML = `
            <div class="space-y-2" style="font-size:12px">
                ${sugestao}
                <div id="ativ_form_area" style="display:none">
                    <div class="bg-base-200 rounded-lg p-2 space-y-1.5 mb-2">
                        <div class="flex gap-1.5">
                            <select id="ativ_tipo" class="${SEL_CLS}" onchange="onAtivTipoChange()" style="flex:1">
                                ${tipos.map(t => `<option value="${t}">${t.replace(/_/g, ' ')}</option>`).join('')}
                            </select>
                            <select id="ativ_contato" class="${SEL_CLS}" style="flex:1">
                                <option value="">Contato (opcional)</option>
                                ${contatoOptions}
                            </select>
                        </div>
                        <textarea id="ativ_desc" class="textarea textarea-xs textarea-bordered w-full" rows="2" placeholder="Descreva..."></textarea>
                        <div class="flex gap-1.5 items-center">
                            <input id="ativ_prazo" type="date" class="input input-xs input-bordered" style="flex:1">
                            <button onclick="addAtividade()" class="leads-action-btn leads-action-btn-incluir" style="flex:0;padding:4px 14px;font-size:11px">Registrar</button>
                        </div>
                    </div>
                </div>
                <button onclick="toggleAtivForm()" class="leads-action-btn leads-action-btn-nova" id="btn_toggle_ativ">+ Nova Atividade</button>
                <div id="ativ_list">
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
    const contatoLabel = a.contato_nome ? ` → ${esc(a.contato_nome)}` : '';

    return `<div class="ativ-card ${a.concluida ? 'ativ-card-concluida' : ''} ${isOverdue ? 'ativ-card-overdue' : ''}">
        <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-1.5">
                <span class="ativ-badge ${typeBadge}">${a.tipo.replace(/_/g, ' ')}</span>
                ${contatoLabel ? `<span style="font-size:10px;color:#6b7280">${contatoLabel}</span>` : ''}
            </div>
            <div class="flex items-center gap-2">
                ${prazoHtml}
                <span style="font-size:9px;color:#9ca3af">${dateStr}</span>
            </div>
        </div>
        <div class="ativ-desc" onclick="this.classList.toggle('expanded')">${esc(a.descricao || '')}</div>
        ${a.data_prazo && !a.concluida ? `
            <label style="display:flex;align-items:center;gap:4px;margin-top:4px;cursor:pointer;font-size:10px;color:#6b7280">
                <input type="checkbox" onchange="toggleConcluida(${a.id}, this.checked)" style="width:12px;height:12px"> Concluir
            </label>` : ''}
        ${a.concluida ? `
            <label style="display:flex;align-items:center;gap:4px;margin-top:4px;cursor:pointer;font-size:10px;color:#6b7280">
                <input type="checkbox" checked onchange="toggleConcluida(${a.id}, this.checked)" style="width:12px;height:12px"> Concluída
            </label>` : ''}
        ${a.usuario_nome ? `<div style="font-size:9px;color:#9ca3af;margin-top:2px">por ${esc(a.usuario_nome)}</div>` : ''}
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

async function melhorarTexto() {
    const desc = document.getElementById('ativ_desc');
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
    const container = document.getElementById('tab_extracao');
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
    const container = document.getElementById('tab_comunicacao');
    container.innerHTML = skeletonHtml();

    try {
        const conResp = await fetch(`/api/leads/${leadId}/contatos`);
        const conData = await conResp.json();
        const contatos = conData.contatos || [];
        const contatoOptions = contatos.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('');

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
    if (currentTab !== 'comunicacao') switchTab('comunicacao');
    setTimeout(() => {
        const obj = document.getElementById('comm_objetivo');
        if (obj) obj.value = t.objetivo;
        const radios = document.querySelectorAll('input[name="comm_tipo"]');
        radios.forEach(r => { r.checked = r.value === t.tipo; });
        gerarComunicacao();
    }, 100);
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
    if (!selectedLeadId || !confirm('Converter este lead em cliente?')) return;
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/converter-cliente`, {method: 'POST'});
        const data = await resp.json();
        if (data.success) {
            showToast('Lead convertido em cliente!', 'success');
            loadTabDados(selectedLeadId);
            loadLeads();
        } else showToast(data.message || 'Erro', 'error');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
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
        (data.leads || []).forEach(l => {
            if (grouped[l.status]) grouped[l.status].push(l);
        });

        KANBAN_STATUSES.forEach(status => {
            const col = document.querySelector(`[data-drop="${status}"]`);
            const countEl = document.querySelector(`[data-count="${status}"]`);
            if (!col) return;

            countEl.textContent = grouped[status].length;
            col.innerHTML = grouped[status].map(l => `
                <div class="kanban-card" draggable="true" data-lead-id="${l.id}" onclick="selectLeadFromKanban(${l.id})">
                    <div class="kanban-card-title">${esc(l.nome || l.empresa || 'Lead #' + l.id)}</div>
                    ${l.empresa ? `<div class="kanban-card-company">${esc(l.empresa)}</div>` : ''}
                    <div class="kanban-card-meta">
                        ${l.potencial ? potencialBadge(l.potencial) : ''}
                        ${l.qualificacao_score ? `<span style="font-size:10px;color:#6b7280">${l.qualificacao_score}pts</span>` : ''}
                        ${l.valor_estimado ? `<span class="kanban-card-value">R$ ${Number(l.valor_estimado).toLocaleString('pt-BR')}</span>` : ''}
                    </div>
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

function initKanbanDragDrop() {
    document.querySelectorAll('.kanban-card[draggable="true"]').forEach(card => {
        card.addEventListener('dragstart', e => {
            card.classList.add('dragging');
            e.dataTransfer.setData('text/plain', card.dataset.leadId);
            e.dataTransfer.effectAllowed = 'move';
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            document.querySelectorAll('.kanban-column').forEach(col => col.classList.remove('drag-over'));
        });
    });

    document.querySelectorAll('.kanban-column-scroll').forEach(dropZone => {
        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            dropZone.closest('.kanban-column').classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', e => {
            if (!dropZone.contains(e.relatedTarget)) {
                dropZone.closest('.kanban-column').classList.remove('drag-over');
            }
        });
        dropZone.addEventListener('drop', async e => {
            e.preventDefault();
            dropZone.closest('.kanban-column').classList.remove('drag-over');
            const leadId = e.dataTransfer.getData('text/plain');
            const newStatus = dropZone.dataset.drop;
            if (!leadId || !newStatus) return;

            try {
                const resp = await fetch(`/api/leads/${leadId}/kanban-move`, {
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

// ======================== Relatório Executivo ========================

function initRelatorioAnos() {
    const sel = document.getElementById('rel_ano');
    if (!sel) return;
    const year = new Date().getFullYear();
    for (let y = year; y >= year - 3; y--) {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = y;
        sel.appendChild(opt);
    }
    sel.value = year;
    document.getElementById('rel_mes').value = new Date().getMonth() + 1;
}

function openRelatorioExecutivo() {
    document.getElementById('modal_relatorio').showModal();
    loadRelatorio();
}

async function loadRelatorio() {
    const ano = document.getElementById('rel_ano').value;
    const mes = document.getElementById('rel_mes').value;
    const execId = document.getElementById('rel_executivo').value;
    const container = document.getElementById('relatorio_content');

    if (!ano || !mes) {
        container.innerHTML = '<div class="leads-empty">Selecione ano e mês</div>';
        return;
    }

    container.innerHTML = skeletonHtml();

    try {
        let url = `/api/leads/relatorio-executivo?ano=${ano}&mes=${mes}`;
        if (execId) url += `&id_executivo=${execId}`;

        const resp = await fetch(url);
        const data = await resp.json();
        if (!data.success) throw new Error(data.message);

        const pipeline = data.pipeline || [];
        const atividades = data.atividades || [];

        if (pipeline.length === 0 && atividades.length === 0) {
            container.innerHTML = '<div class="leads-empty">Sem dados para o período selecionado</div>';
            return;
        }

        const execNames = {};
        (window.EXECUTIVOS || []).forEach(e => execNames[e.id] = e.nome);

        let html = '<div class="space-y-6">';

        if (pipeline.length > 0) {
            const totals = pipeline.reduce((acc, r) => {
                acc.cadastrados += r.leads_cadastrados || 0;
                acc.ganhos += r.ganhos || 0;
                acc.perdidos += r.perdidos || 0;
                acc.receita += r.receita_fechada || 0;
                acc.pipeline += r.valor_pipeline || 0;
                return acc;
            }, {cadastrados:0, ganhos:0, perdidos:0, receita:0, pipeline:0});

            html += `<div>
                <h4 class="font-semibold text-gray-700 mb-3">Pipeline</h4>
                <div class="relatorio-grid">
                    <div class="relatorio-kpi-card"><div class="relatorio-kpi-value">${totals.cadastrados}</div><div class="relatorio-kpi-label">Leads Cadastrados</div></div>
                    <div class="relatorio-kpi-card"><div class="relatorio-kpi-value" style="color:#059669">${totals.ganhos}</div><div class="relatorio-kpi-label">Ganhos</div></div>
                    <div class="relatorio-kpi-card"><div class="relatorio-kpi-value" style="color:#dc2626">${totals.perdidos}</div><div class="relatorio-kpi-label">Perdidos</div></div>
                    <div class="relatorio-kpi-card"><div class="relatorio-kpi-value" style="color:#059669">R$ ${Number(totals.receita).toLocaleString('pt-BR')}</div><div class="relatorio-kpi-label">Receita Fechada</div></div>
                    <div class="relatorio-kpi-card"><div class="relatorio-kpi-value">R$ ${Number(totals.pipeline).toLocaleString('pt-BR')}</div><div class="relatorio-kpi-label">Pipeline Total</div></div>
                </div>
                <table class="relatorio-table">
                    <thead><tr>
                        <th>Executivo</th><th>Cadastrados</th><th>Inbox</th><th>Contato</th><th>Qualificados</th>
                        <th>Proposta</th><th>Negociação</th><th>Ganhos</th><th>Perdidos</th>
                        <th>Taxa Conv.</th><th>Receita</th><th>Tempo Resp. (h)</th>
                    </tr></thead>
                    <tbody>${pipeline.map(r => `<tr>
                        <td class="font-semibold">${esc(execNames[r.id_executivo] || '#' + r.id_executivo)}</td>
                        <td>${r.leads_cadastrados}</td><td>${r.inbox}</td><td>${r.em_contato}</td>
                        <td>${r.qualificados}</td><td>${r.com_proposta}</td><td>${r.em_negociacao}</td>
                        <td style="color:#059669;font-weight:600">${r.ganhos}</td>
                        <td style="color:#dc2626">${r.perdidos}</td>
                        <td>${r.taxa_conversao || 0}%</td>
                        <td>R$ ${Number(r.receita_fechada || 0).toLocaleString('pt-BR')}</td>
                        <td>${r.avg_horas_primeiro_contato || '-'}</td>
                    </tr>`).join('')}</tbody>
                </table>
            </div>`;
        }

        if (atividades.length > 0) {
            html += `<div>
                <h4 class="font-semibold text-gray-700 mb-3">Atividades</h4>
                <table class="relatorio-table">
                    <thead><tr>
                        <th>Executivo</th><th>Total</th><th>Ligações</th><th>WhatsApp</th><th>Emails</th>
                        <th>Reuniões</th><th>Propostas</th><th>Follow-ups</th>
                        <th>Leads Trab.</th><th>Ativ./Lead</th><th>Dias Ativos</th>
                    </tr></thead>
                    <tbody>${atividades.map(r => `<tr>
                        <td class="font-semibold">${esc(execNames[r.id_executivo] || '#' + r.id_executivo)}</td>
                        <td class="font-semibold">${r.total_atividades}</td>
                        <td>${r.ligacoes}</td><td>${r.whatsapp}</td><td>${r.emails_enviados}</td>
                        <td>${r.reunioes}</td><td>${r.propostas_enviadas}</td><td>${r.follow_ups}</td>
                        <td>${r.leads_trabalhados}</td><td>${r.atividades_por_lead || '-'}</td><td>${r.dias_ativos}</td>
                    </tr>`).join('')}</tbody>
                </table>
            </div>`;
        }

        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="leads-empty text-error">${e.message}</div>`;
    }
}

// ======================== Links Modal ========================

let linksData = [];

async function loadLinksContent() {
    try {
        const resp = await fetch('/api/leads/links-uteis');
        const data = await resp.json();
        if (data.success) linksData = data.links || [];
    } catch (e) { console.error('loadLinksContent:', e); }
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
                ${items.map(l => `<div class="link-item">
                    <a href="${esc(l.url)}" target="_blank" class="text-xs link link-primary truncate">${esc(l.titulo)}</a>
                    <button onclick="copyToClipboard('${esc(l.url)}', this)" title="Copiar" style="color:#9ca3af;background:none;border:none;cursor:pointer;display:inline-flex;flex-shrink:0;position:relative">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    </button>
                </div>`).join('')}
            </div>`).join('');
    }
    updateLinksSiteSection();
    document.getElementById('modal_links').showModal();
}

function updateLinksSiteSection() {
    const section = document.getElementById('links_site_section');
    if (!section) return;
    section.classList.toggle('hidden', !(selectedLeadData && selectedLeadData.url_site));
}

async function extrairLinksDoSite() {
    if (!selectedLeadId) return;
    const btn = document.getElementById('btn_extrair_links');
    const spinner = document.getElementById('extrair_links_spinner');
    btn.disabled = true;
    spinner.classList.remove('hidden');
    try {
        const resp = await fetch(`/api/leads/${selectedLeadId}/extrair-links`, {method: 'POST', headers: {'Content-Type': 'application/json'}});
        const data = await resp.json();
        if (data.success) {
            const links = data.links || [];
            const container = document.getElementById('links_site_resultado');
            container.innerHTML = links.length === 0 ? '<div class="text-xs text-gray-400">Nenhum link encontrado</div>' :
                links.slice(0, 30).map(url => `<div class="link-item"><a href="${esc(url)}" target="_blank" class="text-xs link link-primary truncate">${esc(url)}</a>
                    <button onclick="copyToClipboard('${esc(url)}', this)" title="Copiar" style="color:#9ca3af;background:none;border:none;cursor:pointer;display:inline-flex;flex-shrink:0;position:relative">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                    </button></div>`).join('');
        } else showToast(data.message || 'Erro', 'error');
    } catch (e) { showToast('Erro: ' + e.message, 'error'); }
    finally { btn.disabled = false; spinner.classList.add('hidden'); }
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
    document.getElementById('import_preview').innerHTML = importParsedLeads.map((l, i) => `
        <div class="bg-base-200 rounded-lg p-3">
            <label class="flex items-center gap-2 mb-2 cursor-pointer">
                <input type="checkbox" class="checkbox checkbox-sm checkbox-primary" ${l._selected ? 'checked' : ''} onchange="importParsedLeads[${i}]._selected = this.checked">
                <span class="font-semibold text-sm">${esc(l.empresa)}</span>
            </label>
            <div class="space-y-1 ml-6">
                ${(l.contatos || []).map(c => `<div class="text-xs text-gray-600">
                    ${esc(c.nome)}${c.cargo ? ` (${esc(c.cargo)})` : ''}${c.telefone ? ` | ${esc(c.telefone)}` : ''}${c.email ? ` | ${esc(c.email)}` : ''}${c.principal ? ' ★' : ''}
                </div>`).join('')}
            </div>
        </div>`).join('');
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
