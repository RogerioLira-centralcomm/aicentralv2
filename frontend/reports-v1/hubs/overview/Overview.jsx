import {formatDay, formatRange, friendlyAgo} from '../../friendlyDates.js';
import React, {useMemo, useState} from 'react';
import {AlertCircle, AlertTriangle, ArrowDown, ArrowRight, ArrowUp, CheckCircle, InfoCircle} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {json, reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {customerParam} from '../../shell/customerScope.js';
import {platformName} from '../../shell/media.jsx';
import {TrendAside, TrendGrid, daySeries} from '../../shell/TrendGrid.jsx';
import {AppLink, EmptyState, LoadingState, Section} from '../../shell/primitives.jsx';
import {SourceHealth, compact, compactCurrency, currency, number, siteTotals, useMedia} from '../shared.jsx';
import {OverviewSetup} from './OverviewSetup.jsx';
import './overview.css';

const more = (href, label) => <AppLink className="rs-link" href={href}>{label}<ArrowRight size={14} aria-hidden="true"/></AppLink>;
const ratio = (part, total) => part != null && total ? Number(part) / Number(total) : null;

/**
 * Indicators read the same way in every block. `tone`: up is good (default), `inverse` (a cost: up is bad) or
 * `neutral` (more investment is a decision, not a result). `rate` values compare in percentage points.
 */
const METRICS = [
  {key: 'cost', label: 'Investimento', money: true, tone: 'neutral', get: w => w.media?.cost},
  {key: 'impressions', label: 'Impressões', get: w => w.media?.impressions},
  {key: 'clicks', label: 'Cliques', get: w => w.media?.clicks},
  {key: 'ctr', label: 'CTR', rate: true, get: w => ratio(w.media?.clicks, w.media?.impressions)},
  {key: 'cpc', label: 'Custo por clique', money: true, tone: 'inverse', get: w => ratio(w.media?.cost, w.media?.clicks)},
  {key: 'conversions', label: 'Conversões (campanhas)', get: w => w.media?.conversions},
  {key: 'cpa', label: 'Custo por conversão', money: true, tone: 'inverse', get: w => ratio(w.media?.cost, w.media?.conversions)},
  {key: 'sessions', label: 'Visitas no site', get: w => w.site?.sessions},
  {key: 'site_conversions', label: 'Conversões no site', get: w => w.site?.conversions},
];
const byKey = Object.fromEntries(METRICS.map(item => [item.key, item]));
const STRIP = ['cost', 'clicks', 'cpc', 'conversions', 'cpa', 'sessions', 'site_conversions'];
const ROLLING = ['cost', 'clicks', 'ctr', 'conversions', 'cpa', 'sessions', 'site_conversions'];

const formatValue = (metric, value, code, short = true) => {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  if (metric.rate) return `${(value * 100).toLocaleString('pt-BR', {maximumFractionDigits: 2})}%`;
  if (metric.money) return short && value >= 10000 ? compactCurrency(value, code) : currency(value, code);
  return short && value >= 100000 ? compact(value) : number(value);
};

/** Relative change (or percentage points for rates); null when there is nothing to compare against. */
function change(metric, current, previous) {
  if (current == null || previous == null) return null;
  if (metric.rate) return (current - previous) * 100;
  return previous ? (current - previous) * 100 / previous : null;
}

function Delta({metric, value, suffix}) {
  if (value == null || !Number.isFinite(value)) return <small className="ov-delta is-none">Sem base de comparação</small>;
  const rounded = Math.abs(value) < 0.05 ? 0 : value;
  const tone = !rounded || metric.tone === 'neutral' ? 'neutral' : (rounded > 0) !== (metric.tone === 'inverse') ? 'good' : 'bad';
  const amount = `${Math.abs(rounded).toLocaleString('pt-BR', {maximumFractionDigits: 1})}${metric.rate ? ' p.p.' : '%'}`;
  const spoken = !rounded ? 'estável' : `${rounded > 0 ? 'alta' : 'queda'} de ${amount}`;
  return <small className={`ov-delta is-${tone}`} aria-label={`${spoken}${suffix ? ` ${suffix}` : ''}`}>
    {rounded > 0 ? <ArrowUp size={12} aria-hidden="true"/> : rounded < 0 ? <ArrowDown size={12} aria-hidden="true"/> : null}
    <span aria-hidden="true">{rounded ? amount : 'Estável'}</span>{suffix && <em aria-hidden="true">{suffix}</em>}
  </small>;
}

/**
 * Open monitor alerts, worst first. Acknowledged or silenced ones stay in the Central de alertas; data freshness is
 * shown once, in Saúde dos dados, instead of being repeated here as an alert.
 */
function collectAlerts(alerts, conflicts) {
  const items = (alerts || []).filter(alert => alert.status === 'open').map(alert => ({
    key: `alert-${alert.id}`, id: alert.id, severity: alert.severity, title: alert.title,
    detail: [alert.allowed_host, alert.page_path].filter(Boolean).join(' · ') || alert.summary,
    href: alert.page_path ? reportUrl('pages', {site_id: alert.site_id, path: alert.page_path}) : reportUrl('supertag', {scope_site: alert.site_id}),
    action: alert.page_path ? 'Ver página' : 'Ver coleta',
  }));
  if (conflicts) items.push({key: 'conflicts', severity: 'medium', title: `${number(conflicts)} ${conflicts === 1 ? 'valor divergente' : 'valores divergentes'} nas importações`, detail: 'Revise antes de usar nos relatórios', href: reportUrl('imports'), action: 'Revisar'});
  const rank = {high: 0, medium: 1, low: 2};
  return items.sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3));
}

const SEVERITY = {high: {label: 'Alta', icon: AlertCircle}, medium: {label: 'Média', icon: AlertTriangle}, low: {label: 'Baixa', icon: InfoCircle}};

function AlertsPanel({items, loading, onAct, busy}) {
  const shown = items.slice(0, 5);
  return <Section className="ov-alerts" title="Alertas" id="ov-alerts"
    description={loading ? 'Verificando…' : items.length ? `${items.length} ${items.length === 1 ? 'ponto pede' : 'pontos pedem'} atenção` : 'Monitor do site e importações'}
    action={more(reportUrl('alerts'), 'Central de alertas')}>
    {loading ? <LoadingState rows={2}/> : !items.length
      ? <p className="ov-allgood"><CheckCircle size={16} aria-hidden="true"/>Nenhum alerta pendente. Os lidos e silenciados ficam na Central de alertas.</p>
      : <ul className="ov-alert-list">{shown.map(item => {
        const meta = SEVERITY[item.severity] || SEVERITY.low;
        const Icon = meta.icon;
        return <li key={item.key} className={`is-${item.severity}`}>
          <Icon size={16} className="ov-alert-list__icon" aria-hidden="true"/>
          <span className="ov-alert-list__copy"><strong><span className="reports-sr-only">Severidade {meta.label.toLowerCase()}: </span>{item.title}</strong>{item.detail && <small>{item.detail}</small>}</span>
          <span className="ov-alert-list__actions">
            <AppLink className="ov-alert-list__action" href={item.href}>{item.action}<span className="reports-sr-only">: {item.title}</span></AppLink>
            {item.id && <>
              <button type="button" className="ov-alert-list__dismiss" disabled={busy === item.id} onClick={() => onAct(item, 'acknowledge', {})}>Marcar como lido<span className="reports-sr-only">: {item.title}</span></button>
              <button type="button" className="ov-alert-list__dismiss" disabled={busy === item.id} onClick={() => onAct(item, 'silence', {permanent: true})} title="Silencia sem prazo. Some daqui e da contagem; fica na Central de alertas e se resolve sozinho quando o problema acabar">Não recomendar<span className="reports-sr-only">: {item.title}</span></button>
            </>}
          </span>
        </li>;
      })}</ul>}
    {items.length > shown.length && <p className="ov-alerts__more">{more(reportUrl('alerts'), `Ver todos os ${items.length}`)}</p>}
  </Section>;
}

const isSite = metric => metric.key === 'sessions' || metric.key === 'site_conversions';

function KpiStrip({current, compare, code, loading}) {
  const previousPeriod = compare?.windows?.period_previous;
  const now = {media: compare?.media?.period, site: compare?.site?.period};
  const before = {media: compare?.media?.period_previous, site: compare?.site?.period_previous};
  const items = STRIP.map(key => byKey[key]).filter(metric => isSite(metric) ? current.site : current.media);
  return <section className="ov-kpis" aria-label="Resumo do período">
    <div className="ov-kpis__row">{items.map(metric => <article key={metric.key} className="ov-kpi">
      <span className="ov-kpi__label">{metric.label}</span>
      <strong className="ov-kpi__value">{formatValue(metric, metric.get(current), code)}</strong>
      {loading ? <small className="ov-delta is-none">Comparando…</small>
        : <Delta metric={metric} value={compare ? change(metric, metric.get(now), metric.get(before)) : null} suffix="vs anterior"/>}
    </article>)}</div>
    {previousPeriod && <p className="ov-kpis__note">Variação contra {formatRange(previousPeriod.start, previousPeriod.end)}, o período anterior de mesma duração.</p>}
  </section>;
}

function RollingTable({compare, code}) {
  const rows = ROLLING.map(key => byKey[key]).filter(metric => isSite(metric) ? compare.site?.last30 : compare.media?.last30);
  const win = key => ({media: compare.media?.[key], site: compare.site?.[key]});
  const anchor = compare.windows.last7.end;
  return <Section className="ov-rolling" title="7 dias × 30 dias" id="ov-rolling" description={`Dias completos até ${formatDay(anchor)}, sempre contra a janela anterior de mesma duração`}>
    {!rows.length ? <p className="rs-muted">Sem dados de mídia ou do site nos últimos 60 dias.</p> : <div className="ov-rolling__wrap"><table className="ov-rolling__table">
      <caption className="reports-sr-only">Últimos 7 e 30 dias comparados às janelas anteriores</caption>
      <thead><tr><th scope="col">Indicador</th><th scope="col">Últimos 7 dias</th><th scope="col">vs 7 anteriores</th><th scope="col">Últimos 30 dias</th><th scope="col">vs 30 anteriores</th></tr></thead>
      <tbody>{rows.map(metric => <tr key={metric.key}>
        <th scope="row">{metric.label}</th>
        <td>{formatValue(metric, metric.get(win('last7')), code)}</td>
        <td><Delta metric={metric} value={change(metric, metric.get(win('last7')), metric.get(win('previous7')))}/></td>
        <td>{formatValue(metric, metric.get(win('last30')), code)}</td>
        <td><Delta metric={metric} value={change(metric, metric.get(win('last30')), metric.get(win('previous30')))}/></td>
      </tr>)}</tbody>
    </table></div>}
  </Section>;
}

const RUNNING = new Set(['ENABLED', 'active']);
const FLOW_MONITOR = {online: ['Online', 'is-success'], degraded: ['Com falhas', 'is-warning'], offline: ['Offline', 'is-error']};

/**
 * Campaigns running for this client, with what each one spent in the period; running without delivery is flagged.
 * `spend` is null when per-campaign numbers are unknown (imported files, failed load): then nothing is flagged.
 */
function CampaignsCard({campaigns, spend, code, loading}) {
  const byId = new Map((spend || []).map(item => [String(item.id), item]));
  const running = campaigns.filter(item => RUNNING.has(item.status)).map(item => ({...item, metrics: byId.get(String(item.id)) || null}))
    .sort((a, b) => Number(b.metrics?.cost ?? b.metrics?.clicks ?? -1) - Number(a.metrics?.cost ?? a.metrics?.clicks ?? -1));
  const idle = spend ? running.filter(item => !item.metrics?.impressions).length : 0;
  return <Section title="Campanhas em execução" description={loading ? 'Carregando…' : running.length ? `${running.length} ${running.length === 1 ? 'ativa' : 'ativas'}${idle ? ` · ${idle} sem entrega no período` : ''}` : 'Nenhuma campanha ativa'}
    action={more(reportUrl('media/campaigns'), 'Campanhas')}>
    {loading ? <LoadingState rows={3}/> : !running.length ? <p className="rs-muted">Cadastre ou reative campanhas em Mídia › Campanhas.</p>
      : <ul className="ov-list">{running.slice(0, 5).map(item => <li key={item.id}>
        <span className="ov-list__copy"><AppLink href={reportUrl('campaigns', {campaign_id: item.id})}>{item.name}</AppLink><small>{platformName(item.platform)}{item.account_name ? ` · ${item.account_name}` : ''}</small></span>
        {item.metrics?.impressions ? <strong>{item.metrics.cost != null ? compactCurrency(item.metrics.cost, code) : `${compact(item.metrics.clicks)} cliques`}</strong> : spend ? <span className="rs-badge is-warning">Sem entrega</span> : null}
      </li>)}</ul>}
    {running.length > 5 && <p className="ov-list__more">{more(reportUrl('media/campaigns'), `Ver as ${running.length}`)}</p>}
  </Section>;
}

/** Each site with the Super Tag: visits in the period and whether events are still arriving. */
function SitesCard({domains, sites, loading}) {
  const live = (sites || []).filter(item => !item.revoked_at);
  const visits = new Map((domains || []).map(item => [String(item.site_id), item.metrics.sessions]));
  const state = item => {
    if (!item.enabled) return ['Pausado', ''];
    if (!item.last_event_at) return ['Aguardando', 'is-low'];
    return Date.now() - Date.parse(item.last_event_at) > 24 * 3600e3 ? ['Sem eventos', 'is-warning'] : ['Coletando', 'is-success'];
  };
  return <Section title="Sites e Super Tag" description={loading ? 'Carregando…' : live.length ? `${live.length} ${live.length === 1 ? 'site conectado' : 'sites conectados'}` : 'Nenhum site conectado'}
    action={more(reportUrl('journey'), 'Site & Jornada')}>
    {loading ? <LoadingState rows={3}/> : !live.length ? <div className="ov-empty"><p className="rs-muted"><strong>Super Tag não instalada.</strong> Conecte o site do cliente e instale a Super Tag para medir sessões, origens e conversões.</p>{more(reportUrl('supertag'), 'Instalar Super Tag')}</div>
      : <ul className="ov-list">{live.slice(0, 5).map(item => {
        const [label, tone] = state(item);
        return <li key={item.id}>
          <span className="ov-list__copy"><AppLink href={reportUrl('journey', {scope_site: item.id})}>{item.allowed_host || item.label}</AppLink>
            <small>{number(visits.get(String(item.id)) || 0)} visitas{item.last_event_at ? ` · último evento ${friendlyAgo(item.last_event_at)}` : ''}</small></span>
          <span className={`rs-badge ${tone}`}>{label}</span>
        </li>;
      })}</ul>}
  </Section>;
}

/** Published flows (with their monitor) and drafts still being built. */
function FlowsCard({state}) {
  const flows = state.body?.flows || [];
  const published = flows.filter(item => item.status === 'published');
  const drafts = flows.length - published.length;
  return <Section title="Fluxos" description={state.loading && !state.body ? 'Carregando…' : flows.length ? `${published.length} ${published.length === 1 ? 'publicado' : 'publicados'} · ${drafts} ${drafts === 1 ? 'rascunho' : 'rascunhos'}` : 'Nenhum fluxo criado'}
    action={more(reportUrl('journey/flows'), 'Fluxos')}>
    {state.loading && !state.body ? <LoadingState rows={3}/> : state.error ? <p className="rs-muted">Fluxos indisponíveis agora.</p>
      : !published.length ? <p className="rs-muted">{drafts ? 'Publique um rascunho para começar a medir a jornada.' : 'Crie um fluxo para medir a jornada entre anúncio, site e conversão.'}</p>
      : <ul className="ov-list">{published.slice(0, 5).map(item => {
        const [label, tone] = item.monitor_enabled ? FLOW_MONITOR[item.monitor_status] || ['Verificando', 'is-low'] : ['Sem monitor', ''];
        return <li key={item.id}>
          <span className="ov-list__copy"><AppLink href={reportUrl('journey/flows', {flow_id: item.id})}>{item.name}</AppLink><small>{item.allowed_host || 'Sem site'}{item.campaign_names ? ` · ${item.campaign_names}` : ''}</small></span>
          <span className={`rs-badge ${tone}`}>{label}</span>
        </li>;
      })}</ul>}
  </Section>;
}

/** The client at a glance: headline numbers, daily trend of campaigns and site, what is running (campaigns, sites, flows), alerts and data health. */
export function Overview({data}) {
  const {period} = useReportsContext();
  // Everything here is the chosen client's (sidebar picker); the API narrows each list and metric to it.
  const customer_id = customerParam();
  const media = useMedia(period);
  const [domains] = useApi(apiUrl('/pages/domains', {start_date: period.start, end_date: period.end, customer_id}));
  const [compareState] = useApi(apiUrl('/overview/compare', {start_date: period.start, end_date: period.end, customer_id}));
  const [alerts, retryAlerts] = useApi(apiUrl('/alerts', {customer_id, per_page: 50}));
  const [sites] = useApi(apiUrl('/supertag/sites', {customer_id}));
  const [sources] = useApi(apiUrl('/ingest-keys', {customer_id}));
  const [flows] = useApi(apiUrl('/flow', {view: 'edit', customer_id}));
  const campaigns = (data.campaigns || []).filter(item => !customer_id || String(item.customer_id || '') === customer_id);
  const [busy, setBusy] = useState('');
  const [actionError, setActionError] = useState('');
  const site = domains.body ? siteTotals(domains.body.domains) : null;
  const summary = media.summary;
  const compare = compareState.body;
  const code = summary?.currency || compare?.currency || null;
  const settled = !media.loading && !domains.loading;
  const alertItems = useMemo(() => collectAlerts(alerts.body?.alerts, media.conflicts), [alerts.body, media.conflicts]);
  const act = async (item, action, body) => {
    setBusy(item.id); setActionError('');
    try {
      await json(`/connect/api/v2/reports/alerts/${item.id}/${action}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(body)});
      retryAlerts();
    } catch (failure) {setActionError(failure.message);} finally {setBusy('');}
  };
  // Onboarding stays until there is something to read in either media or the site.
  if (settled && !summary && !site?.sessions) return <div className="rs-stack">
    <OverviewSetup data={{...data, campaigns}} sites={sites.body?.sites ?? (sites.error ? null : [])} sources={sources.body?.keys ?? (sources.error ? null : [])} imported={media.conflicts ? {conflicts: media.conflicts} : null}/>
  </div>;
  const current = {media: summary?.totals || null, site: site && domains.body.domains.length ? site : null};
  const money = value => currency(value, code);
  const integer = value => number(value);
  const previousMedia = compare?.previous_daily?.media || [];
  const previousSite = compare?.previous_daily?.site || [];
  const mediaCharts = summary ? [
    {key: 'cost', title: 'Investimento em campanhas por dia', field: 'cost', format: money, metric: byKey.cost, skip: summary.totals.cost == null},
    {key: 'clicks', title: 'Cliques por dia', field: 'clicks', format: integer, metric: byKey.clicks},
    {key: 'conversions', title: 'Conversões (campanhas) por dia', field: 'conversions', format: integer, metric: byKey.conversions},
  ].filter(item => !item.skip).map(item => ({...item, href: reportUrl('media'), points: daySeries(period.start, period.end, summary.days, item.field),
    previous: previousMedia.map(row => row[item.field] == null ? null : Number(row[item.field])), total: formatValue(item.metric, item.metric.get(current), code)})) : [];
  const siteCharts = current.site ? [
    {key: 'sessions', title: 'Visitas no site por dia', field: 'sessions', metric: byKey.sessions},
    {key: 'site_conversions', title: 'Conversões no site por dia', field: 'conversions', metric: byKey.site_conversions},
  ].map(item => ({...item, format: integer, href: reportUrl('journey'), points: daySeries(period.start, period.end, site.daily, item.field),
    previous: previousSite.map(row => Number(row[item.field] || 0)), total: formatValue(item.metric, item.metric.get(current), code)})) : [];
  const charts = [...mediaCharts, ...siteCharts];
  const platforms = summary?.platforms || [];
  return <div className="rs-stack ov-page">
    {!settled ? <LoadingState rows={2}/> : <KpiStrip current={current} compare={compare} code={code} loading={compareState.loading && !compare}/>}
    <TrendGrid description="Campanhas e site, contra o período anterior de mesma duração" charts={charts}>
      {platforms.length > 0 && <TrendAside title="Investimento por canal" action={more(reportUrl('media'), 'Mídia')}>
        <ul className="rs-bars">{platforms.slice(0, 5).map(item => {
          const share = summary.totals.cost ? (item.cost || 0) / summary.totals.cost : summary.totals.impressions ? item.impressions / summary.totals.impressions : 0;
          return <li key={item.platform}><span>{item.label}</span><i><b style={{width: `${Math.max(2, share * 100)}%`}}/></i><strong>{item.cost != null ? compactCurrency(item.cost, summary.currency) : compact(item.impressions)}</strong></li>;
        })}</ul>
      </TrendAside>}
    </TrendGrid>
    {!summary && settled && <EmptyState title="Sem dados de mídia neste período" description="Conecte uma fonte ou envie um arquivo para ver investimento e resultados." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/data')}>Conectar fonte</ReportsActionButton>}/>}
    <div className="ov-grid3">
      <CampaignsCard campaigns={campaigns} spend={summary && summary.origin === 'Google Ads Script' ? summary.campaigns : null} code={code} loading={media.loading}/>
      <SitesCard domains={domains.body?.domains} sites={sites.body?.sites} loading={sites.loading && !sites.body}/>
      <FlowsCard state={flows}/>
    </div>
    <div className="ov-row ov-row--even">
      <div className="ov-alerts-wrap">
        {actionError && <div className="reports-error" role="alert">{actionError}</div>}
        <AlertsPanel items={alertItems} loading={alerts.loading && !alerts.body} onAct={act} busy={busy}/>
      </div>
      <Section className="ov-health" title="Saúde dos dados" description="Última atualização de cada fonte" action={more(reportUrl('data-sources'), 'Fontes')}>
        {sources.loading || sites.loading ? <LoadingState rows={2}/> : <SourceHealth sources={sources.body?.keys} sites={sites.body?.sites} conflicts={media.conflicts}/>}
      </Section>
    </div>
    <details className="ov-more">
      <summary>Comparar últimos 7 × 30 dias</summary>
      {compare ? <RollingTable compare={compare} code={code}/> : <Section className="ov-rolling" title="7 dias × 30 dias">
        {compareState.error ? <p className="rs-muted">Não foi possível calcular os comparativos agora.</p> : <LoadingState rows={3}/>}
      </Section>}
    </details>
  </div>;
}
