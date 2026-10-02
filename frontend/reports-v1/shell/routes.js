// Route table of the Reports SPA: product areas in the sidebar, sections as tabs inside each hub.
import {useEffect, useState} from 'react';

export const APP_BASE = '/connect/app';

/** Hubs that group sections behind tabs. Only these show a second navigation level. */
export const HUBS = {
  media: {
    title: 'Mídia', description: 'Investimento, alcance e resultado das campanhas.',
    tabs: [['media', 'Visão geral'], ['media/campaigns', 'Campanhas'], ['media/google-ads', 'Google Ads'], ['media/creatives', 'Criativos']],
  },
  journey: {
    title: 'Site & Jornada', description: 'O que as pessoas fazem depois que chegam ao site.',
    tabs: [['journey', 'Visão geral'], ['journey/flows', 'Fluxos'], ['journey/pages', 'Páginas'], ['journey/content', 'Conteúdos'], ['journey/navigation', 'Navegação'], ['journey/conversions', 'Conversões']],
  },
  data: {
    title: 'Fontes de dados', description: 'De onde vêm os dados de mídia, site, CRM e arquivos deste cliente.',
    tabs: [['data-sources', 'Visão geral'], ['data-sources/connect', 'Conexões e chaves'], ['supertag', 'Super Tag'], ['events', 'Eventos'], ['imports', 'Importações']],
  },
};

/**
 * path → page. `page` is the key App renders; `nav` is the sidebar item kept active;
 * `period` shows the global period picker in the header.
 */
export const ROUTES = {
  overview: {page: 'overview', nav: 'overview', title: 'Visão geral', description: 'Saúde dos dados, resultados e próxima ação.', period: true},
  media: {page: 'media', nav: 'media', hub: 'media', period: true, scope: true},
  'media/campaigns': {page: 'campaigns', nav: 'media', hub: 'media', period: true},
  'media/google-ads': {page: 'google-ads', nav: 'media', hub: 'media', period: true},
  'media/creatives': {page: 'creatives', nav: 'media', hub: 'media'},
  journey: {page: 'journey', nav: 'journey', hub: 'journey', period: true, scope: 'site'},
  'journey/flows': {page: 'flow', nav: 'journey', hub: 'journey'},
  'journey/pages': {page: 'pages', nav: 'journey', hub: 'journey', period: true, scope: 'site'},
  'journey/content': {page: 'content', nav: 'journey', hub: 'journey', period: true},
  'journey/navigation': {page: 'navigation', nav: 'journey', hub: 'journey', period: true},
  'journey/conversions': {page: 'conversions', nav: 'journey', hub: 'journey', period: true},
  reports: {page: 'reports', nav: 'reports', title: 'Relatórios', description: 'Análises salvas e entregáveis prontos para distribuir.'},
  alerts: {page: 'alerts', nav: 'alerts', title: 'Alertas', description: 'O que precisa da sua atenção, com responsável e histórico.'},
  'data-sources': {page: 'data-sources', nav: 'data-sources', hub: 'data'},
  'data-sources/connect': {page: 'monitor', nav: 'data-sources', hub: 'data'},
  supertag: {page: 'supertag', nav: 'data-sources', hub: 'data'},
  events: {page: 'events', nav: 'data-sources', hub: 'data', period: true},
  imports: {page: 'imports', nav: 'data-sources', hub: 'data'},
  'tools/link-tester': {page: 'links', nav: 'links', title: 'Link Tester', description: 'Verifique destinos e associe links às campanhas certas.'},
  'settings/clients': {page: 'accounts', nav: 'accounts', title: 'Clientes e contas', description: 'Clientes e marcas, contas de mídia e campanhas com seus projetos do Workspace.'},
  'settings/accounts': {page: 'accounts', nav: 'accounts', title: 'Clientes e contas', description: 'Clientes e marcas, contas de mídia e campanhas com seus projetos do Workspace.'},
  'settings/access': {page: 'access', nav: 'access', title: 'Acessos', description: 'Quem pode consultar e operar os dados deste cliente.'},
};

/** Old first-level sections and where they live now. */
export const LEGACY = {
  campaigns: 'media/campaigns', monitor: 'data-sources/connect', pages: 'journey/pages', flows: 'journey/flows', flow: 'journey/flows',
  conversions: 'journey/conversions', customers: 'settings/clients', accounts: 'settings/accounts', access: 'settings/access',
  links: 'tools/link-tester', 'data-library': 'imports',
};

const segments = pathname => {
  const parts = pathname.split('/').filter(Boolean);
  return parts[0] === 'connect' && parts[1] === 'app' ? parts.slice(2) : [];
};

/** Flow editor/monitor and Super Tag site pages keep their historical URLs. */
const isFlowEntity = parts => parts[0] === 'flows' && parts.length > 1;

export function resolveRoute(pathname = location.pathname) {
  const parts = segments(pathname);
  if (isFlowEntity(parts)) return {path: 'journey/flows', ...ROUTES['journey/flows'], entity: parts[1]};
  if (parts[0] === 'supertag' && parts[1] === 'sites') return {path: 'supertag', ...ROUTES.supertag, entity: parts[2] || ''};
  const two = parts.slice(0, 2).join('/');
  if (ROUTES[two]) return {path: two, ...ROUTES[two], entity: parts[2] || ''};
  const one = parts[0] || 'overview';
  if (ROUTES[one]) return {path: one, ...ROUTES[one], entity: parts[1] || ''};
  return {path: 'overview', ...ROUTES.overview, entity: '', unknown: true};
}

/** URL of the new location for an old address, or '' when the address is current. */
export function legacyRedirect(href = location.href) {
  const url = new URL(href, location.origin);
  const parts = segments(url.pathname);
  // Mídia → Desempenho became the Google Ads area.
  // Mídia → Dados became Fontes de dados → Conexões e chaves.
  if (parts[0] === 'media' && parts[1] === 'data') {url.pathname = `${APP_BASE}/data-sources/connect`; return `${url.pathname}${url.search}${url.hash}`;}
  if (parts[0] === 'media' && parts[1] === 'performance') {url.pathname = `${APP_BASE}/media/google-ads`; return `${url.pathname}${url.search}${url.hash}`;}
  if (!parts.length) {url.pathname = `${APP_BASE}/overview`; return `${url.pathname}${url.search}${url.hash}`;}
  if (isFlowEntity(parts) || ROUTES[parts.slice(0, 2).join('/')] || (ROUTES[parts[0]] && !LEGACY[parts[0]])) return '';
  const target = LEGACY[parts[0]];
  if (!target) return '';
  if (parts[0] === 'data-library') url.searchParams.set('view', 'library');
  if (parts[0] === 'campaigns' && url.searchParams.get('campaign_id')) {
    url.pathname = `${APP_BASE}/${target}/${encodeURIComponent(url.searchParams.get('campaign_id'))}`;
    url.searchParams.delete('campaign_id');
  } else url.pathname = `${APP_BASE}/${target}`;
  url.searchParams.delete('client_id');
  return `${url.pathname}${url.search}${url.hash}`;
}

/** Path for a section key, accepting both new paths and the old section names still used by older screens. */
export const sectionPath = section => {
  const [head, ...rest] = String(section).split('/');
  if (head === 'flows' && rest.length) return section;
  if (ROUTES[section]) return section;
  return LEGACY[head] ? [LEGACY[head], ...rest].join('/') : section;
};

/** Client-side navigation: same page, new URL, no reload. */
export function navigate(href, {replace = false} = {}) {
  if (replace) history.replaceState(null, '', href); else history.pushState(null, '', href);
  dispatchEvent(new PopStateEvent('popstate'));
}

/** Plain left clicks become client-side navigation; modified clicks keep the browser behaviour (new tab, etc.). */
export const navigateOnClick = (event, href) => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  event.preventDefault();
  navigate(href);
  return true;
};

/** Moves an old address to its new place before anything renders it. */
export function applyLegacyRedirect() {
  const target = legacyRedirect();
  if (target) history.replaceState(history.state, '', target);
}

export function useLocationKey() {
  const [key, setKey] = useState(() => {applyLegacyRedirect(); return location.pathname + location.search;});
  useEffect(() => {
    const sync = () => {applyLegacyRedirect(); setKey(location.pathname + location.search);};
    addEventListener('popstate', sync);
    return () => removeEventListener('popstate', sync);
  }, []);
  return key;
}
