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

const accountUrls = {...urls, perfil: '/conta/perfil', agencia: '/conta/agencia', equipe: '/conta/equipe', integracoes: '/conta/integracoes', planos: '/conta/planos', uso: '/conta/uso', creditos: '/conta/creditos', faturamento: '/conta/faturamento'};
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
