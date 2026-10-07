import React from 'react';
import {friendlyAgo} from '../friendlyDates.js';
import {apiUrl, useApi} from '../shell/useApi.js';
import {periodBucket} from '../shell/context.js';
import {customerParam} from '../shell/customerScope.js';
import {platformName} from '../shell/media.jsx';

export const number = value => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 0});
export const percent = (part, total) => total ? `${(Number(part) * 100 / Number(total)).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%` : '—';
export const currency = (value, code) => value == null || !code ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency: code, maximumFractionDigits: value >= 1000 ? 0 : 2}).format(value);
/** "R$ 428 mil", "31,4 mi" — headline numbers read at a glance. */
export const compact = value => value == null ? '—' : new Intl.NumberFormat('pt-BR', {notation: 'compact', maximumFractionDigits: 1}).format(value);
export const compactCurrency = (value, code) => value == null || !code ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency: code, notation: 'compact', maximumFractionDigits: 1}).format(value);

/** Period query for the media endpoints, which accept only 7/30/90 in `days` and the exact window in dates. */
export const periodQuery = period => ({days: periodBucket(period), start_date: period.start, end_date: period.end});

const row = (item, exported) => ({
  ...item,
  impressions: Number(item.impressions || 0), clicks: Number(item.clicks || 0), conversions: Number(item.conversions || 0),
  cost: exported ? (item.cost == null ? null : Number(item.cost)) : (item.cost_micros == null ? null : Number(item.cost_micros) / 1e6),
});

/** Media numbers in one shape, whether they came from the Google Ads script or from imported files. */
export function mediaSummary(metrics, imported) {
  const source = metrics?.days?.length ? metrics : imported?.days?.length ? imported : null;
  if (!source) return null;
  const exported = source.source === 'export';
  const totals = row(source.totals || {}, exported);
  return {
    origin: exported ? 'Arquivos importados' : 'Google Ads Script', currency: source.currency || null,
    totals, days: (source.days || []).map(item => row(item, exported)),
    platforms: (source.by_platform || []).map(item => ({...row(item, exported), label: platformName(item.platform)})),
    campaigns: exported ? [] : (source.by_campaign || []).map(item => row(item, false)),
    observed: metrics?.observed_conversions, confirmed: metrics?.confirmed_conversions,
  };
}

/** Script metrics and imported metrics for the period, loaded side by side. */
export function useMedia(period, scope = {}) {
  const query = {...periodQuery(period), account_id: scope.account, campaign_id: scope.campaign, customer_id: customerParam()};
  const [metrics, retryMetrics] = useApi(apiUrl('/metrics', query));
  const [imported, retryImported] = useApi(apiUrl('/import-metrics', query));
  const loading = metrics.loading || imported.loading;
  const error = metrics.error && imported.error ? metrics.error : '';
  return {
    loading, error, summary: loading ? null : mediaSummary(metrics.body, imported.body),
    conflicts: Number(imported.body?.conflicts || 0),
    retry: () => {retryMetrics(); retryImported();},
  };
}

/** Sum of every monitored domain for the period: the site totals used by the overview and Site & Jornada. */
export function siteTotals(domains = []) {
  const sum = key => domains.reduce((total, item) => total + Number(item.metrics?.[key] || 0), 0);
  const comparable = domains.length > 0 && domains.every(item => item.previous);
  const previousSum = key => comparable ? domains.reduce((total, item) => total + Number(item.previous[key] || 0), 0) : null;
  const change = (current, before) => before ? (current - before) * 100 / before : null;
  const previous = previousSum('sessions');
  const sessions = sum('sessions');
  const days = new Map();
  domains.forEach(domain => (domain.daily || []).forEach(day => {
    const current = days.get(day.date) || {date: day.date, sessions: 0, conversions: 0};
    current.sessions += day.sessions; current.conversions += day.conversions; days.set(day.date, current);
  }));
  return {
    sessions, visitors: sum('visitors'), views: sum('views'), conversions: sum('conversions'), formSubmits: sum('form_submits'),
    sessionsChange: change(sessions, previous),
    visitorsChange: change(sum('visitors'), previousSum('visitors')),
    viewsChange: change(sum('views'), previousSum('views')),
    conversionsChange: change(sum('conversions'), previousSum('conversions')),
    daily: [...days.values()].sort((a, b) => a.date.localeCompare(b.date)),
  };
}

/** Freshness of each data source — the "partial data" state: one line per source with its last update. */
export function SourceHealth({sources, sites, conflicts}) {
  const items = [
    ...(sources || []).filter(item => !item.revoked_at).map(item => ({
      key: `source-${item.id}`, label: item.label || (item.source_kind === 'google_ads_script' ? 'Google Ads' : 'Webhook de conversões'),
      kind: item.source_kind === 'google_ads_script' ? 'Mídia' : 'Negócio',
      tone: !item.last_used_at ? 'warning' : Date.now() - Date.parse(item.last_used_at) > 48 * 3600e3 ? 'error' : 'success',
      detail: item.last_used_at ? `Atualizado ${friendlyAgo(item.last_used_at)}` : 'Aguardando o primeiro envio',
    })),
    ...(sites || []).filter(item => !item.revoked_at).map(item => ({
      key: `site-${item.id}`, label: item.allowed_host || item.label, kind: 'Site',
      tone: !item.enabled ? 'gray' : !item.last_event_at ? 'warning' : Date.now() - Date.parse(item.last_event_at) > 24 * 3600e3 ? 'error' : 'success',
      detail: !item.enabled ? 'Coleta pausada' : item.last_event_at ? `Último evento ${friendlyAgo(item.last_event_at)}` : 'Aguardando eventos',
    })),
  ];
  if (conflicts) items.push({key: 'conflicts', label: 'Importações', kind: 'Arquivos', tone: 'warning', detail: `${number(conflicts)} ${conflicts === 1 ? 'valor divergente' : 'valores divergentes'} para revisar`});
  if (!items.length) return <p className="rs-muted">Nenhuma fonte conectada ainda.</p>;
  return <ul className="rs-health">{items.map(item => <li key={item.key}>
    <span className={`rs-dot is-${item.tone}`} aria-hidden="true"/>
    <span className="rs-health__copy"><strong>{item.label}</strong><small>{item.detail}</small></span>
    <span className="rs-health__kind">{item.kind}</span>
  </li>)}</ul>;
}
