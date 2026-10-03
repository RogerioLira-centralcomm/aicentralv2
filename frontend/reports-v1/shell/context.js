// Global Reports context: the active client and one analysis period shared by every analytic screen.
import {createContext, useContext} from 'react';
import {PRESETS, addDays, matchPreset, todayIso} from '../friendlyDates.js';

export const ReportsContext = createContext({period: null, setPeriod: () => {}, switchClient: () => {}, scope: {account: '', campaign: '', site: ''}, setScope: () => {}});
export const useReportsContext = () => useContext(ReportsContext);

const ISO = /^\d{4}-\d{2}-\d{2}$/;
const DEFAULT_PRESET = '30';

/** Period from the address bar: ?period=30, ?start_date=&end_date= or the older ?days=N. */
export function readPeriod(search = location.search) {
  const query = new URLSearchParams(search);
  const start = query.get('start_date'), end = query.get('end_date');
  if (ISO.test(start || '') && ISO.test(end || '') && start <= end && end <= todayIso()) return {start, end};
  const days = Number(query.get('days'));
  const preset = PRESETS.find(item => item.id === (query.get('period') || '')) ||
    (days > 0 && days <= 365 ? null : PRESETS.find(item => item.id === DEFAULT_PRESET));
  if (preset) return preset.range();
  return {start: addDays(todayIso(), -(days - 1)), end: todayIso()};
}

/** Keeps the period in the URL so reloads, back/forward and shared links show the same window. */
export function writePeriod(range) {
  const url = new URL(location.href);
  ['days', 'period', 'start_date', 'end_date'].forEach(key => url.searchParams.delete(key));
  const preset = matchPreset(range.start, range.end);
  if (preset && preset !== DEFAULT_PRESET) url.searchParams.set('period', preset);
  else if (!preset) {url.searchParams.set('start_date', range.start); url.searchParams.set('end_date', range.end);}
  history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
}

export const periodDays = ({start, end}) => Math.max(1, Math.round((Date.parse(`${end}T12:00:00Z`) - Date.parse(`${start}T12:00:00Z`)) / 86400000) + 1);

/** Older endpoints accept only 7/30/90 in `days`; the exact window travels in start/end dates. */
export const periodBucket = range => {const days = periodDays(range); return days <= 7 ? '7' : days <= 30 ? '30' : '90';};

/** The legacy `filters` shape (period/startDate/endDate) that older screens still read. */
export const periodFilters = range => ({period: periodBucket(range), startDate: range.start, endDate: range.end});

/** Data source (media account) and campaign the analysis is narrowed to; empty means everything of the client. */
export function readScope(search = location.search) {
  const query = new URLSearchParams(search);
  return {account: /^\d+$/.test(query.get('scope_account') || '') ? query.get('scope_account') : '',
    // A plain id is a registered campaign; "account:google id" is a Google Ads campaign nobody registered (Google Ads tab only).
    campaign: /^\d+(:\d+)?$/.test(query.get('scope_campaign') || '') ? query.get('scope_campaign') : '',
    site: /^[0-9a-f-]{36}$/i.test(query.get('scope_site') || '') ? query.get('scope_site') : ''};
}

export function writeScope(scope) {
  const url = new URL(location.href);
  ['scope_account', 'scope_campaign', 'scope_site'].forEach(key => url.searchParams.delete(key));
  if (scope.account) url.searchParams.set('scope_account', scope.account);
  if (scope.campaign) url.searchParams.set('scope_campaign', scope.campaign);
  if (scope.site) url.searchParams.set('scope_site', scope.site);
  history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
}

const savedKey = clientId => `reports-scope:${clientId}`;

/** The last choice made for this client, if the browser lets us read it. */
export function readSavedScope(clientId) {
  try {
    const saved = JSON.parse(localStorage.getItem(savedKey(clientId)) || 'null');
    return saved && typeof saved === 'object' ? {account: String(saved.account || ''), campaign: String(saved.campaign || ''), site: String(saved.site || '')} : null;
  } catch {return null;}
}

export function saveScope(clientId, scope) {
  try {localStorage.setItem(savedKey(clientId), JSON.stringify(scope));} catch {/* storage unavailable: the choice just won't be remembered */}
}

/**
 * Scope to show when the page opens: the link's own choice wins, then the last one used by this person for the
 * client (only if it still exists), then the only source or campaign when there is just one to pick from.
 */
export function initialScope({urlScope, saved, accounts, campaigns}) {
  const sources = accounts.filter(item => item.status !== 'disabled');
  const valid = scope => (!scope.account || sources.some(item => String(item.id) === scope.account))
    && (!scope.campaign || /^\d+:\d+$/.test(scope.campaign) || campaigns.some(item => String(item.id) === scope.campaign));
  if ((urlScope.account || urlScope.campaign) && valid(urlScope)) return urlScope;
  if (saved && valid(saved)) return saved;
  if (campaigns.length === 1) return {account: String(campaigns[0].account_id || ''), campaign: String(campaigns[0].id)};
  if (sources.length === 1) return {account: String(sources[0].id), campaign: ''};
  return {account: '', campaign: ''};
}

/** Site to show: the link's, then the last one used for this client, then the only one there is. */
export function initialSite({urlSite, savedSite, sites}) {
  const live = sites.filter(item => !item.revoked_at);
  const known = id => id && live.some(item => item.id === id);
  if (known(urlSite)) return urlSite;
  if (known(savedSite)) return savedSite;
  return live.length === 1 ? live[0].id : '';
}
