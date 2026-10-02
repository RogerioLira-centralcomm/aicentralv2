// How two origins of the same channel stay apart in the reports: a distinct utm_campaign for ads and
// messaging, distinct engines for organic search. Mirrors reports_flow_sources.py / reports_flow_validation.py.
import {isSearchSource, searchEnginesOf, sourceTrafficKey} from './flowValidation.js';
import {FLOW_PLATFORMS} from './FlowPlatformLogo.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';

export const SEARCH_ENGINES = Object.freeze([
  ['google', 'Google'], ['bing', 'Bing'], ['yahoo', 'Yahoo'], ['duckduckgo', 'DuckDuckGo'],
  ['ecosia', 'Ecosia'], ['yandex', 'Yandex'], ['baidu', 'Baidu'], ['brave', 'Brave Search'],
]);
export const searchEngineLabel = id => SEARCH_ENGINES.find(([value]) => value === id)?.[1] || id;

export const utmSlug = value => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 100);

// While typing: same alphabet as the server accepts, without trimming the separator being typed.
export const utmInput = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  .replace(/[^a-z0-9._-]+/g, '-').slice(0, 100);

export function channelLabel(node) {
  const source = node?.source || flowBlockFor(node || {}).source;
  return FLOW_PLATFORMS[source]?.label || flowBlockFor(node || {}).label || node?.title || 'Esta origem';
}

/** Engines no other search origin of the map has claimed. */
export function freeSearchEngines(nodes, exceptId = '') {
  const used = new Set(nodes.filter(node => node.id !== exceptId && isSearchSource(node)).flatMap(searchEnginesOf));
  if (used.has('*')) return [];
  return SEARCH_ENGINES.map(([id]) => id).filter(id => !used.has(id));
}

/** The existing node an added origin would be confused with, or null. */
export function conflictingSource(nodes, node) {
  if (node?.type !== 'source') return null;
  const others = nodes.filter(item => item.id !== node.id && item.type === 'source');
  if (isSearchSource(node)) {
    const engines = searchEnginesOf(node);
    return others.find(item => isSearchSource(item) && (engines.includes('*') || searchEnginesOf(item).some(engine => engine === '*' || engines.includes(engine)))) || null;
  }
  const key = sourceTrafficKey(node);
  return others.find(item => !isSearchSource(item) && sourceTrafficKey(item) === key) || null;
}

/** A utm_campaign no other origin of the same channel uses, based on the flow name and the audience. */
export function distinctCampaign(nodes, node, flowName = '') {
  const base = utmSlug(node?.media?.utm?.campaign || flowName || 'campanha') || 'campanha';
  const audience = utmSlug(node?.segment?.name);
  const taken = new Set(nodes.filter(item => item.id !== node.id && item.type === 'source').map(sourceTrafficKey));
  const keyFor = campaign => sourceTrafficKey({...node, media: {...(node.media || {}), utm: {...(node.media?.utm || {}), campaign}}});
  const first = audience && audience !== base ? `${base}-${audience}` : base;
  if (!taken.has(keyFor(first))) return first;
  for (let index = 2; index < 100; index += 1) {
    if (!taken.has(keyFor(`${first}-${index}`))) return `${first}-${index}`;
  }
  return `${first}-${crypto.randomUUID().slice(0, 6)}`;
}

export function withCampaign(node, campaign) {
  return {...node, media: {...(node.media || {}), utm: {...(node.media?.utm || {}), campaign}}};
}
