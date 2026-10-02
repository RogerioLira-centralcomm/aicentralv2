// Every Planner call goes through the family API with the session cookie and,
// for writes, the CSRF token rendered in the bootstrap.
const API_ROOT = '/familia/api/planner';

export function createPlannerApi(csrf) {
  return async function request(path, options = {}) {
    const headers = {...(options.body ? {'Content-Type': 'application/json', 'X-CSRF-Token': csrf} : {}), ...(options.headers || {})};
    const response = await fetch(API_ROOT + path, {credentials: 'same-origin', ...options, headers});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.description || 'Não foi possível concluir a ação.');
    return body;
  };
}

export const CATALOG_KINDS = ['audiencias', 'canais', 'formatos', 'interativos', 'places', 'portais'];

export const MODULE_LABELS = {
  inicio: 'Início', planos: 'Planos de mídia', radar: 'Radar de Oportunidades', audiencias: 'Audiências', canais: 'Canais', formatos: 'Formatos',
  interativos: 'Interativos', places: 'Places', portais: 'Portais', monitoramento: 'Sites e funis', docs: 'Docs',
};

// Bootstrap URL keys for each module.
export const MODULE_URL_KEYS = {
  inicio: 'home', planos: 'plans', radar: 'radar', audiencias: 'audiences', canais: 'channels', formatos: 'formats',
  interativos: 'interactive', places: 'places', portais: 'portals', monitoramento: 'monitoring', docs: 'docs',
};

export function moduleUrl(urls, module) {
  return urls[MODULE_URL_KEYS[module]] || urls.home;
}

export function newPlanUrl(urls) {
  const url = new URL(urls.plans, window.location.origin);
  url.searchParams.set('create', '1');
  return url.pathname + url.search;
}

export function plainText(html) {
  return String(html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

export const OBJECTIVES = [
  ['', 'A definir'], ['awareness', 'Awareness'], ['consideracao', 'Consideração'], ['leads', 'Leads'], ['vendas', 'Vendas'], ['trafego', 'Tráfego'],
];

export function objectiveLabel(value) {
  return OBJECTIVES.find(([key]) => key === value)?.[1] || value || 'Objetivo a definir';
}

// Context API: brand/project selection is saved in the family session.
export async function saveContext(csrf, ref) {
  const response = await fetch('/familia/api/context', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
    body: JSON.stringify(ref),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || body.description || 'Não foi possível salvar o contexto.');
  return body.context;
}

export function contextQuery(selection) {
  const params = new URLSearchParams();
  if (selection?.brand_ref) params.set('brand_ref', selection.brand_ref);
  if (selection?.project_ref) params.set('project_ref', selection.project_ref);
  return params.toString();
}
