import React from 'react';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {sectionPath} from './shell/routes.js';

// Helpers shared by the Reports entry (main.jsx) and its pages.
export const flowEditorId = () => location.pathname.match(/^\/connect\/app\/flows\/([0-9a-f-]{36})(?:\/monitor)?\/?$/i)?.[1] || '';
export const reportUrl = (section, params = {}, siteId = '') => {
  // Old section names ('campaigns', 'pages', 'flow'…) resolve to their place in the new navigation.
  const url = new URL(`/connect/app/${sectionPath(section === 'flow' ? 'flows' : section)}${siteId ? `/sites/${encodeURIComponent(siteId)}` : ''}`, location.origin);
  // The signed-in session already knows the active client; keeping it out of the address bar keeps links short and shareable.
  Object.entries(params).forEach(([key, value]) => {if (key !== 'client_id' && value != null && value !== '') url.searchParams.set(key, String(value));});
  return `${url.pathname}${url.search}`;
};
export const flowEditorUrl = (id, params = {}) => reportUrl(`flows/${encodeURIComponent(id)}`, params);
/** The page route and the bootstrap call persist the chosen client in the session; after that the parameter is only noise in the URL. */
export const dropClientFromUrl = () => {
  const url = new URL(location.href);
  if (!url.searchParams.has('client_id')) return;
  url.searchParams.delete('client_id');
  history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
};
const formatter = new Intl.DateTimeFormat('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'});
export const shortDate = value => value ? formatter.format(new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value)) : '—';
export const integer = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0}).format(value || 0);
export const decimal = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value || 0);
export async function json(url, options = {}) {
  const response = await fetch(url, {credentials: 'same-origin', ...options});
  let body = {};
  try { body = await response.json(); } catch (_) { /* The response may be an HTML error page. */ }
  if (!response.ok) {
    const failure = new Error(body.error || body.description || `Falha HTTP ${response.status}`);
    failure.status = response.status;
    failure.details = body;
    throw failure;
  }
  return body;
}
export function Empty({message}) { return <CaduEmptyState className="reports-empty reports-empty-state" description={message}/>; }
export const FLOW_CHANNELS = [
  {id:'netflix_ads',label:'Netflix Ads',aliases:['netflix']},
  {id:'serasa',label:'Serasa',aliases:['serasa']},
  {id:'spotify_ads',label:'Spotify Ads',aliases:['spotify']},
  {id:'amazon_ads',label:'Amazon Ads',aliases:['amazon']},
  {id:'disney_ads',label:'Disney Ads',aliases:['disney','hulu','espn']},
  {id:'google_ads',label:'Google Ads',aliases:['google','adwords','youtube','dv360','gclid']},
  {id:'meta_ads',label:'Meta Ads',aliases:['meta','facebook','instagram','fbclid','ig','fb']},
  {id:'linkedin_ads',label:'LinkedIn Ads',aliases:['linkedin','licdn','li_fat_id']},
  {id:'tiktok',label:'TikTok Ads',aliases:['tiktok','ttclid']},
  {id:'email',label:'E-mail',aliases:['email','e-mail','newsletter','mailchimp','rdstation']},
  {id:'whatsapp',label:'WhatsApp',aliases:['whatsapp','wa.me']},
];
export function Kpi({label, value, detail}) {
  return <article className="reports-kpi"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}
