const urls = {home: '/home', projects: '/projetos', brands: '/marcas', newConversation: '/conversas', conversations: '/conversas', docs: '/arquivos', agency: '/conta/agencia', profile: '/conta/perfil', usage: '/conta/uso', credits: '/conta/creditos', creditos: '/conta/creditos', solutions: {workspace: '/home', planner: '#', studio: '#', connect: '#', skills: '#'}};
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
  'home': {bootstrap: {...base, homeMode: true, endpoints: {}, home: {resume: [], recent: [], usagePercent: 90.6}, resources: [
    {id: 'r1', title: '[CENTRAL] [D:CONTINUA] Plano', projectName: 'Media Hacks', href: '#'},
    {id: 'r2', title: 'Media Hacks — Imersão', projectName: 'Media Hacks', href: '#'},
    {id: 'r3', title: 'Dossiê do projeto', projectName: 'Netflix', href: '#'}]}},
  'projeto-vazio': {rootClass: 'cv-home-root cadu-project-root', bootstrap: {...base, projectMode: true, canEdit: true, canManageBrand: true, endpoints: {agentState: '/api/agent-state'}, sectionLinks: {}, projectLinks: {},
    project: {id: 'p1', name: 'Cemig', description: '', brand: null, files: [], resources: [], notes: [], links: [], tasks: [], reports: [], deliverables: [], conversations: [], members: [], context: {}, activity: []}}},
};
