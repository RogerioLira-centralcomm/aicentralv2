const urls = {home: '/home', projects: '/projetos', brands: '/marcas', newConversation: '/conversas', conversations: '/conversas', docs: '/arquivos', agency: '/conta/agencia', profile: '/conta/perfil', usage: '/conta/uso', credits: '/conta/creditos', creditos: '/conta/creditos', solutions: {workspace: '/home', planner: '#', studio: '#', connect: '#'}};
const sidebar = {
  agency: {name: 'CENTRALCOMM'},
  brands: [{id: 'b1', name: 'Nike', detailUrl: '/marca-vazia', projects: []}, {id: 'b2', name: 'Cemig', detailUrl: '#', projects: [{id: 'p1', name: 'Cemig', href: '/projeto'}]}],
  projects: [{id: 'p1', name: 'Cemig', brandId: 'b2', href: '/projeto'}, {id: 'p2', name: 'Marketing', brandId: '', href: '#'}],
};
const user = {name: 'Apolo', email: 'apolo@example.com'};
const base = {sidebar, user, urls, usagePercent: 90.6, dock: {items: []}, brands: sidebar.brands, projects: sidebar.projects};

const nike = (extra = {}) => ({
  id: 'b1', name: 'Nike', sector: 'Artigos esportivos', websiteUrl: 'https://www.nike.com.br', detailUrl: '/marca-vazia', logoUrl: '', initials: 'NI',
  profile: {}, readiness: {score: 0, missing: []}, reviewPack: {status: 'not_started'}, auditHistory: [], assets: [], linkedProjects: [], analysisMetadata: {}, ...extra,
});
const brandLinks = {audit: '/x', reevaluate: '/x', identity: '/x', delete: '/x', link: '/x'};

const accountUrls = {...urls, team: '/conta-equipe', plans: '/conta-planos', perfil: '/conta/perfil', agencia: '/conta/agencia', equipe: '/conta/equipe', integracoes: '/conta/integracoes', planos: '/conta/planos', uso: '/conta/uso', creditos: '/conta/creditos', faturamento: '/conta/faturamento'};
const packages = [
  {slug: 'extra-essencial', name: 'Extra Essencial', tokens: 100000, price_brl: 49, description: 'Reforço pontual para uma operação em andamento.'},
  {slug: 'extra-equipe', name: 'Extra Equipe', tokens: 500000, price_brl: 179, description: 'Mais margem para planejamento, auditoria e produção.'},
  {slug: 'extra-agencia', name: 'Extra Agência', tokens: 1000000, price_brl: 299, description: 'Volume para múltiplos projetos e clientes.'}];
const usage = {cycle: {start: '2026-10-01', end: '2026-10-31', renews_on: '2026-11-01'}, allowance: {active: false, granted: 2000000, used: 180400, available: 1819600, percentage: 9},
  extras: {available: 320000, lots: 1}, cycle_tokens: 180400, by_tool: [{tool: 'Studio', tokens: 120000, interactions: 3}, {tool: 'Chat', tokens: 60400, interactions: 12}]};
const interactions = [{tool: 'Studio', tokens: 12400, steps: 4, created_at: '2026-10-05T14:20:00'}, {tool: 'Chat', tokens: 1, steps: 1, created_at: '2026-10-05T13:02:00'}, {tool: 'Planner', tokens: 8200, steps: 2, created_at: '2026-10-04T10:00:00'}];
const creditRequests = [{id: 9, package_name: 'Extra Equipe', tokens_amount: 500000, price_brl: 179, billing_mode: 'postpaid', status: 'approved', created_at: '2026-10-03T12:00:00'}];
const accountBase = {organization: {nome_fantasia: 'Centralcomm'}, people: [{status: true}], agency_context: {projects: [], brands: []}, insights: {tokens: {used: 180400, limit: 2000000, percentage: 9}}};
const accountPage = (section, account) => ({bootstrap: {...base, accountMode: true, section, contextName: 'Centralcomm', csrf: 'x', endpoints: {creditRequest: '/x'}, urls: accountUrls, account: {...accountBase, ...account}}});

export const pages = {
  'marca-vazia': {bootstrap: {...base, brandMode: true, canManageBrand: true, brand: nike(), brandLinks, availableProjects: []}},
  'marca-sem-dados': {bootstrap: {...base, brandMode: true, canManageBrand: true, brandLinks, availableProjects: [], brand: nike({auditHistory: [{job_id: 'j1', status: 'completed', created_at: '2026-10-05T12:00:00', completed_at: '2026-10-05T12:10:00', sources: 13, reviews: 3, tokens: 177634}]})}},
  'conta-integracoes': {bootstrap: {...base, accountMode: true, section: 'integracoes', contextName: 'Centralcomm', endpoints: {googleResourceBase: '/x', googleMeetArtifactBase: '/x'},
    urls: {...urls, perfil: '/conta/perfil', agencia: '/conta/agencia', equipe: '/conta/equipe', integracoes: '/conta/integracoes', planos: '/conta/planos', uso: '/conta/uso', creditos: '/conta/creditos', faturamento: '/conta/faturamento', observability: '/obs'},
    account: {organization: {nome_fantasia: 'Centralcomm'}, people: [], projects: [], brands: [],
      integrations: {connected_count: 0, accounts: [], priority_connectors: [{key:'ads', name:'Google Ads', description:'Contas e campanhas.'}], coming_soon_connectors: [], google: {summary: {enabled_count: 0}, authorizations: [], resources: [], meet_artifacts: [], connection: null, services: [
        {key: 'drive', name: 'Google Drive', description: 'Arquivos, pastas e links podem ser indexados e associados a projetos.', status: 'unavailable'},
        {key: 'calendar', name: 'Google Calendar', description: 'Eventos e agenda entram no contexto de reuniões e entregas.', status: 'unavailable'},
        {key: 'ga', name: 'Google Analytics', description: 'Propriedades e sinais de audiência podem alimentar o planejamento.', status: 'coming_soon'}]}}}}},
  'conta-planos': accountPage('planos', {packages, storage_packages: [], plans: [
    {slug: 'pro', name: 'Pro', tagline: 'Seu plano atual.', price_monthly: 1599, tokens_monthly: 2000000, storage_gb: null, users_unlimited: true, features: [], cta: 'current', highlight: false, current: true},
    {slug: 'essencial', name: 'Essencial', tagline: 'Para começar a operar com o Cadu no dia a dia.', price_monthly: 297, tokens_monthly: null, storage_gb: null, users_unlimited: true, features: ['Workspace, projetos e marcas ilimitados', 'Studio, Planner e Connect'], cta: 'contact', highlight: false, current: false},
    {slug: 'equipe', name: 'Equipe', tagline: 'Para equipes que produzem e planejam toda semana.', price_monthly: 697, tokens_monthly: null, storage_gb: null, users_unlimited: true, features: ['Tudo do Essencial', 'Mais tokens por mês'], cta: 'contact', highlight: true, current: false},
    {slug: 'agencia', name: 'Agência', tagline: 'Para agências com vários clientes e projetos.', price_monthly: 1497, tokens_monthly: null, storage_gb: null, users_unlimited: true, features: ['Tudo do Equipe', 'Maior franquia de tokens'], cta: 'contact', highlight: false, current: false}]}),
  'conta-creditos': accountPage('creditos', {packages, usage, interactions, credit_requests: creditRequests,
    purchases: [{id: 1, package_name: 'Tokens extras', available: 320000, credits: 500000, expires_at: null}]}),
  'conta-uso': accountPage('uso', {usage, interactions, space: {projects: 4, files: 37, bytes_used: 52428800}}),
  'conta-faturamento': accountPage('faturamento', {credit_requests: creditRequests, invoices: [], summary: {open_total: 0, open_count: 0, paid_count: 0, overdue_count: 0}}),
  'home': {bootstrap: {...base, homeMode: true, endpoints: {}, home: {resume: [], recent: [], usagePercent: 90.6}, resources: [
    {id: 'r1', title: '[CENTRAL] [D:CONTINUA] Plano', projectName: 'Media Hacks', href: '#'},
    {id: 'r2', title: 'Media Hacks — Imersão', projectName: 'Media Hacks', href: '#'},
    {id: 'r3', title: 'Dossiê do projeto', projectName: 'Netflix', href: '#'}]}},
  'projeto-vazio': {rootClass: 'cv-home-root cadu-project-root', bootstrap: {...base, projectMode: true, canEdit: true, canManageBrand: true, endpoints: {agentState: '/api/agent-state'}, sectionLinks: {}, projectLinks: {},
    project: {id: 'p1', name: 'Cemig', description: '', brand: null, files: [], resources: [], notes: [], links: [], tasks: [], reports: [], deliverables: [], conversations: [], members: [], context: {}, activity: []}}},
};

// Uma tela por visão do Projeto vazio: /projeto-direction, /projeto-tasks, ...
for (const view of ['direction', 'tasks', 'files', 'library', 'indexing', 'conversations', 'deliveries', 'reports', 'views']) {
  const source = pages['projeto-vazio'];
  pages[`projeto-${view}`] = {...source, bootstrap: {...source.bootstrap, projectView: view}};
}

// Telas preenchidas: marca analisada, projeto com conteúdo, listas e conta.
const fullProfile = {
  brandSummary: 'Marca global de artigos esportivos com foco em performance, inovação e cultura urbana.',
  positioning: 'Inspiração e inovação para todo atleta do mundo.', targetAudience: 'Jovens adultos de 18 a 34 anos, praticantes de corrida e basquete.',
  toneOfVoice: 'Direto, motivacional e confiante.', archetype: 'Herói', brandValues: ['Performance', 'Inovação', 'Inclusão'],
  colorPalette: [{hex: '#111111', name: 'Preto'}, {hex: '#FFFFFF', name: 'Branco'}, {hex: '#FA5400', name: 'Laranja'}],
  fonts: [{family: 'Helvetica Neue', role: 'Títulos'}, {family: 'Inter', role: 'Texto'}],
  productsServices: ['Tênis de corrida', 'Vestuário esportivo', 'Acessórios'], differentiators: ['Tecnologia de amortecimento', 'Atletas patrocinados'],
  proofPoints: ['Presença em 190 países'], competitors: ['Adidas', 'Puma', 'Mizuno'], personas: ['Corredora de fim de semana', 'Jogador amador de basquete'],
  adSegments: ['Corrida urbana', 'Basquete de rua'], audienceSegments: ['Esporte', 'Moda urbana'], campaigns: [{name: 'Just Do It', status: 'ativa'}],
  campaignOpportunities: ['Maratonas regionais'], creativeGuidelines: ['Atleta em movimento, fundo limpo'], visualMotifs: ['Swoosh', 'Contraste alto'],
  mandatoryElements: ['Logo em área de respiro'], forbiddenElements: ['Distorcer o logo'], contacts: ['sac@nike.com.br'], addresses: ['São Paulo, SP'], digitalPolicies: ['Política de privacidade publicada'],
};
const fullAssets = [
  {id: 'a1', role: 'logo', isPrimary: true, status: 'approved', reusable: true, mimeType: 'image/png', sourceKind: 'site', displayUrl: '/static/images/cadu/products/cadu-icon.png', metadata: {}},
  {id: 'a2', role: 'product', isPrimary: false, status: 'approved', reusable: true, mimeType: 'image/png', sourceKind: 'upload', displayUrl: '/static/images/cadu/products/studio-icon.png', metadata: {}},
];
pages['marca-completa'] = {bootstrap: {...base, brandMode: true, canManageBrand: true, brandLinks, availableProjects: [{id: 'p2', name: 'Marketing'}],
  brand: nike({profile: fullProfile, assets: fullAssets, readiness: {score: 86, missing: ['Política de marca']}, reviewPack: {status: 'completed'},
    linkedProjects: [{id: 'p1', name: 'Cemig', href: '/projeto-cheio'}], analysisMetadata: {verified: true, sources: ['https://www.nike.com.br/sobre', 'https://about.nike.com']},
    auditHistory: [{job_id: 'j1', status: 'completed', created_at: '2026-10-05T12:00:00', completed_at: '2026-10-05T12:10:00', sources: 13, reviews: 3, tokens: 177634}]})}};

const fullProject = {
  id: 'p1', name: 'Cemig — Campanha Verão 2027', description: 'Campanha integrada de eficiência energética para o verão.',
  brand: {id: 'b2', name: 'Cemig'},
  files: [
    {id: 'f1', name: 'briefing-verao-2027.pdf', title: 'Briefing Verão 2027', mime: 'application/pdf', size: 1832000, status: 'indexed', type: 'document', category: 'briefing', lastModified: '2026-10-04T10:00:00', canIndex: true},
    {id: 'f2', name: 'key-visual.png', title: 'Key visual aprovado', mime: 'image/png', size: 4200000, status: 'ready', type: 'image', category: 'creative', lastModified: '2026-10-05T09:30:00', colorPalette: ['#00A651', '#FFFFFF'], fonts: ['Inter']},
    {id: 'f3', name: 'planilha-de-midia-com-um-nome-muito-longo-para-testar-truncamento-final.xlsx', title: '', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', size: 92000, status: 'processing', type: 'sheet', lastModified: '2026-10-06T08:00:00', requiresReview: true},
  ],
  resources: [{id: 'r1', title: 'Plano de mídia', kind: 'document', resourceType: 'artifact', status: 'ready', href: '#', mime: 'text/html', locator: ''}],
  notes: [{id: 'n1', content: 'Cliente pediu foco em Minas Gerais.', createdAt: '2026-10-04T11:00:00'}],
  links: [{id: 'l1', url: 'https://www.cemig.com.br', iconUrl: '', iconStatus: 'pending'}, {id: 'l2', url: 'https://www.instagram.com/cemig', iconUrl: '', iconStatus: 'ready'}],
  tasks: [
    {id: 't1', title: 'Aprovar key visual', description: 'Revisar com o cliente.', status: 'todo', priority: 'high', dueAt: '2026-10-09T18:00:00', assignee: {name: 'Apolo'}, resourceRefs: [], evidence: []},
    {id: 't2', title: 'Fechar plano de mídia', description: '', status: 'doing', priority: 'medium', dueAt: '2026-10-12T18:00:00', assignee: null, resourceRefs: [], evidence: []},
    {id: 't3', title: 'Kickoff', description: '', status: 'done', priority: 'low', dueAt: '2026-10-01T10:00:00', assignee: {name: 'Ana'}, resourceRefs: [], evidence: []},
  ],
  reports: [{id: 'rp1', title: 'Relatório semanal', status: 'ready', href: '#', createdAt: '2026-10-05T10:00:00'}],
  deliverables: [{id: 'd1', title: 'Peças de lançamento', status: 'in_review', dueAt: '2026-10-10T18:00:00', href: '#'}],
  conversations: [{id: 'c1', title: 'Ideias de conceito', href: '/conversas/c1', updatedAt: '2026-10-05T16:00:00', includes: true}],
  members: [{id: 1, name: 'Apolo', email: 'apolo@example.com'}, {id: 2, name: 'Ana', email: 'ana@example.com'}],
  context: {objective: 'Reduzir consumo na ponta', audience: 'Residencial MG'}, activity: [{id: 'ac1', text: 'Arquivo indexado', createdAt: '2026-10-05T10:00:00'}],
};
pages['projeto-cheio'] = {rootClass: 'cv-home-root cadu-project-root', bootstrap: {...pages['projeto-vazio'].bootstrap, project: fullProject}};
for (const view of ['direction', 'tasks', 'files', 'library', 'indexing', 'conversations', 'deliveries', 'reports', 'views']) {
  pages[`projeto-cheio-${view}`] = {...pages['projeto-cheio'], bootstrap: {...pages['projeto-cheio'].bootstrap, projectView: view}};
}

const listUrls = {...urls, createProject: '/x', createBrand: '/x', inspectBrandSite: '/x'};
pages['projetos'] = {bootstrap: {...base, projectsMode: true, status: 'ativos', urls: listUrls, projects: [
  {id: 'p1', name: 'Cemig — Campanha Verão 2027', brandName: 'Cemig', description: 'Campanha integrada de eficiência energética.', href: '/projeto-cheio', status: 'active', sources: 12, visualInitials: 'CE', visualColor: '#00A651', contextItems: []},
  {id: 'p2', name: 'Marketing', brandName: '', description: '', href: '#', status: 'active', sources: 0, visualInitials: 'MA', visualColor: '#176b5e', contextItems: []},
  {id: 'p3', name: 'Projeto com um nome extremamente longo para verificar truncamento no cartão', brandName: 'Nike', description: 'Descrição longa '.repeat(12), href: '#', status: 'active', sources: 3, visualInitials: 'PR', visualColor: '#FA5400', contextItems: []}]}};
pages['projetos-vazio'] = {bootstrap: {...base, projectsMode: true, status: 'ativos', urls: listUrls, projects: []}};
pages['marcas'] = {bootstrap: {...base, brandsMode: true, status: 'ativas', urls: listUrls, brands: [
  {id: 'b1', name: 'Nike', sector: 'Artigos esportivos', summary: 'Marca global de artigos esportivos.', href: '/marca-completa', audited: true, archived: false, activeProjects: 1, fileCount: 8, conversationCount: 4, logoUrl: '', visualInitials: 'NI', visualColor: '#111111'},
  {id: 'b2', name: 'Cemig', sector: '', summary: '', href: '#', audited: false, archived: false, activeProjects: 0, fileCount: 0, conversationCount: 0, logoUrl: '', visualInitials: 'CE', visualColor: '#00A651'}]}};
pages['marcas-vazio'] = {bootstrap: {...base, brandsMode: true, status: 'ativas', urls: listUrls, brands: []}};

const people = [
  {id_contato_cliente: 1, nome_completo: 'Apolo Lira', email: 'apolo@example.com', cargo: 'Diretor', setor: 'Diretoria', telefone: '', status: true, user_type: 'admin', cadu_avatar_badge: 'badge-comet.png'},
  {id_contato_cliente: 2, nome_completo: 'Ana Souza', email: 'ana@example.com', cargo: '', setor: '', telefone: '', status: true, user_type: 'client'},
  {id_contato_cliente: 3, nome_completo: 'Bruno Leitura', email: 'bruno@example.com', cargo: 'Analista', setor: 'Mídia', telefone: '', status: false, user_type: 'readonly'}];
const teamEndpoints = {creditRequest: '/x', updateProfile: '/x', updateOrganization: '/x', invite: '/x', inviteBase: '/x', memberBase: '/x'};
const accountFull = (section, account, admin = true) => ({bootstrap: {...accountPage(section, account).bootstrap, admin, endpoints: teamEndpoints}});
const org = {nome_fantasia: 'Centralcomm', razao_social: 'Centralcomm Mídia Ltda', cnpj: '12345678000190', cep: '01310100', logradouro: 'Av. Paulista', numero: '1000', complemento: '', bairro: 'Bela Vista', cidade: 'São Paulo', estado_sigla: 'SP'};
pages['conta-equipe'] = accountFull('equipe', {people, invites: [{id: 7, email: 'novo@example.com', role: 'member', status: 'pending', expires_at: '2026-10-13T00:00:00'}, {id: 8, email: 'velho@example.com', role: 'admin', status: 'pending', expires_at: '2026-09-01T00:00:00'}]});
pages['conta-equipe-membro'] = accountFull('equipe', {people, invites: []}, false);
pages['conta-perfil'] = accountFull('perfil', {current_user: people[0], people});
pages['conta-agencia'] = accountFull('agencia', {organization: org, people, agency_context: {projects: [{id: 'p1', name: 'Cemig'}], brands: [{id: 'b1', name: 'Nike'}]}});
pages['conta-agencia-membro'] = accountFull('agencia', {organization: org, people, agency_context: {projects: [], brands: []}}, false);
