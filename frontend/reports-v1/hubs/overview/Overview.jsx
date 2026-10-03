import {addDays, dayLabel, formatDay, formatRange, friendlyAgo, toIsoDay} from '../../friendlyDates.js';
import React, {useMemo} from 'react';
import {AlertCircle, AlertTriangle, ArrowDown, ArrowRight, ArrowUp, CheckCircle, InfoCircle} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Chart} from '../../shell/media.jsx';
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
  {key: 'conversions', label: 'Conversões (mídia)', get: w => w.media?.conversions},
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

/** Every day of the window, in order, with the matching value (0 when nothing happened that day). */
function daySeries(start, end, rows, field) {
  const values = new Map((rows || []).map(row => [toIsoDay(row.date), row[field]]));
  const out = [];
  for (let day = start; day <= end; day = addDays(day, 1)) out.push({date: day, value: values.has(day) ? Number(values.get(day) || 0) : 0});
  return out;
}

/** Data freshness and the alert monitor merged into one list, worst first. */
function collectAlerts(alerts, sources, sites, conflicts) {
  const items = (alerts || []).map(alert => ({
    key: `alert-${alert.id}`, severity: alert.severity, title: alert.title,
    detail: [alert.allowed_host, alert.page_path].filter(Boolean).join(' · ') || alert.summary,
    href: alert.page_path ? reportUrl('pages', {site_id: alert.site_id, path: alert.page_path}) : reportUrl('supertag', {}, alert.site_id),
    action: alert.page_path ? 'Ver página' : 'Ver coleta',
  }));
  (sources || []).filter(item => !item.revoked_at).forEach(item => {
    const label = item.label || (item.source_kind === 'google_ads_script' ? 'Google Ads' : 'Webhook de conversões');
    const stale = item.last_used_at && Date.now() - Date.parse(item.last_used_at) > 48 * 3600e3;
    if (stale) items.push({key: `source-${item.id}`, severity: 'medium', title: `${label} sem enviar dados`, detail: `Último envio ${friendlyAgo(item.last_used_at)}`, href: reportUrl('data-sources'), action: 'Ver fonte'});
    else if (!item.last_used_at) items.push({key: `source-${item.id}`, severity: 'low', title: `${label} aguardando o primeiro envio`, detail: 'Fonte conectada, sem dados ainda', href: reportUrl('data-sources'), action: 'Ver fonte'});
  });
  (sites || []).filter(item => !item.revoked_at && item.enabled).forEach(item => {
    const host = item.allowed_host || item.label;
    const stale = item.last_event_at && Date.now() - Date.parse(item.last_event_at) > 24 * 3600e3;
    // The monitor already raises "Super Tag sem enviar eventos" for this site: do not say it twice.
    if (stale && !(alerts || []).some(alert => alert.rule === 'collection_absent' && alert.site_id === item.id)) {
      items.push({key: `site-${item.id}`, severity: 'medium', title: 'Site sem eventos recentes', detail: `${host} · último evento ${friendlyAgo(item.last_event_at)}`, href: reportUrl('supertag', {}, item.id), action: 'Ver coleta'});
    } else if (!item.last_event_at) items.push({key: `site-${item.id}`, severity: 'low', title: 'Site aguardando eventos', detail: `${host} · confira a instalação da Super Tag`, href: reportUrl('supertag', {}, item.id), action: 'Ver coleta'});
  });
  if (conflicts) items.push({key: 'conflicts', severity: 'medium', title: `${number(conflicts)} ${conflicts === 1 ? 'valor divergente' : 'valores divergentes'} nas importações`, detail: 'Revise antes de usar nos relatórios', href: reportUrl('imports'), action: 'Revisar'});
  const rank = {high: 0, medium: 1, low: 2};
  return items.sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3));
}

const SEVERITY = {high: {label: 'Alta', icon: AlertCircle}, medium: {label: 'Média', icon: AlertTriangle}, low: {label: 'Baixa', icon: InfoCircle}};

function AlertsPanel({items, loading}) {
  const shown = items.slice(0, 5);
  return <Section className="ov-alerts" title="Alertas" id="ov-alerts"
    description={loading ? 'Verificando…' : items.length ? `${items.length} ${items.length === 1 ? 'ponto pede' : 'pontos pedem'} atenção` : 'Monitor e fontes de dados'}
    action={more(reportUrl('alerts'), 'Central de alertas')}>
    {loading ? <LoadingState rows={2}/> : !items.length
      ? <p className="ov-allgood"><CheckCircle size={16} aria-hidden="true"/>Tudo certo: nenhum alerta aberto e todas as fontes em dia.</p>
      : <ul className="ov-alert-list">{shown.map(item => {
        const meta = SEVERITY[item.severity] || SEVERITY.low;
        const Icon = meta.icon;
        return <li key={item.key} className={`is-${item.severity}`}>
          <Icon size={16} className="ov-alert-list__icon" aria-hidden="true"/>
          <span className="ov-alert-list__copy"><strong><span className="reports-sr-only">Severidade {meta.label.toLowerCase()}: </span>{item.title}</strong>{item.detail && <small>{item.detail}</small>}</span>
          <AppLink className="ov-alert-list__action" href={item.href}>{item.action}<span className="reports-sr-only">: {item.title}</span></AppLink>
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

function TrendCard({title, total, points, previous, format, href}) {
  const labels = points.map(item => dayLabel(item.date));
  const series = [{name: 'Período', data: points.map(item => item.value)}];
  const comparable = previous?.length === points.length && previous.some(value => value);
  if (comparable) series.push({name: 'Anterior', data: previous});
  return <article className="ov-chart">
    <header><h3>{title}</h3>{href ? <AppLink className="ov-chart__total" href={href}>{total}</AppLink> : <span className="ov-chart__total">{total}</span>}</header>
    <Chart type="area" height={150} labels={labels} series={series} dash={comparable ? [0, 4] : undefined} colors={['#175cd3', '#98a2b3']} format={format} legend={false}/>
  </article>;
}

/** Status of the whole ecosystem: the headline numbers, rolling comparisons, daily trends, alerts and data freshness. */
export function Overview({data}) {
  const {period} = useReportsContext();
  const media = useMedia(period);
  const [domains] = useApi(apiUrl('/pages/domains', {start_date: period.start, end_date: period.end}));
  const [compareState] = useApi(apiUrl('/overview/compare', {start_date: period.start, end_date: period.end}));
  const [alerts] = useApi(apiUrl('/alerts'));
  const [sites] = useApi(apiUrl('/supertag/sites'));
  const [sources] = useApi(apiUrl('/ingest-keys'));
  const site = domains.body ? siteTotals(domains.body.domains) : null;
  const summary = media.summary;
  const compare = compareState.body;
  const code = summary?.currency || compare?.currency || null;
  const settled = !media.loading && !domains.loading;
  const alertItems = useMemo(() => collectAlerts(alerts.body?.alerts, sources.body?.keys, sites.body?.sites, media.conflicts),
    [alerts.body, sources.body, sites.body, media.conflicts]);
  // Onboarding stays until there is something to read in either media or the site.
  if (settled && !summary && !site?.sessions) return <div className="rs-stack">
    <OverviewSetup data={data} sites={sites.body?.sites ?? (sites.error ? null : [])} sources={sources.body?.keys ?? (sources.error ? null : [])} imported={media.conflicts ? {conflicts: media.conflicts} : null}/>
  </div>;
  const current = {media: summary?.totals || null, site: site && domains.body.domains.length ? site : null};
  const money = value => currency(value, code);
  const integer = value => number(value);
  const previousMedia = compare?.previous_daily?.media || [];
  const previousSite = compare?.previous_daily?.site || [];
  const mediaCharts = summary ? [
    {key: 'cost', title: 'Investimento por dia', field: 'cost', format: money, metric: byKey.cost, skip: summary.totals.cost == null},
    {key: 'clicks', title: 'Cliques por dia', field: 'clicks', format: integer, metric: byKey.clicks},
    {key: 'conversions', title: 'Conversões (mídia) por dia', field: 'conversions', format: integer, metric: byKey.conversions},
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
    <div className="ov-row">
      {compare ? <RollingTable compare={compare} code={code}/> : <Section className="ov-rolling" title="7 dias × 30 dias">
        {compareState.error ? <p className="rs-muted">Não foi possível calcular os comparativos agora.</p> : <LoadingState rows={3}/>}
      </Section>}
      <AlertsPanel items={alertItems} loading={alerts.loading || sources.loading || sites.loading}/>
    </div>
    {charts.length > 0 && <section className="ov-charts" aria-label="Tendência diária no período">
      <header className="ov-charts__head"><h2>Tendência diária</h2><span><i className="ov-key"/>Período <i className="ov-key is-previous"/>Período anterior</span></header>
      <div className="ov-grid3">{charts.map(item => <TrendCard key={item.key} {...item}/>)}
        {platforms.length > 0 && <article className="ov-chart">
          <header><h3>Investimento por canal</h3>{more(reportUrl('media'), 'Mídia')}</header>
          <ul className="rs-bars ov-bars">{platforms.slice(0, 5).map(item => {
            const share = summary.totals.cost ? (item.cost || 0) / summary.totals.cost : summary.totals.impressions ? item.impressions / summary.totals.impressions : 0;
            return <li key={item.platform}><span>{item.label}</span><i><b style={{width: `${Math.max(2, share * 100)}%`}}/></i><strong>{item.cost != null ? compactCurrency(item.cost, summary.currency) : compact(item.impressions)}</strong></li>;
          })}</ul>
        </article>}
      </div>
    </section>}
    {!summary && settled && <EmptyState title="Sem dados de mídia neste período" description="Conecte uma fonte ou envie um arquivo para ver investimento e resultados." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/data')}>Conectar fonte</ReportsActionButton>}/>}
    <div className="ov-grid3 ov-grid3--cards">
      {domains.body?.domains?.length > 0 && <Section title="Sites" description="Visitas no período" action={more(reportUrl('journey'), 'Site & Jornada')}>
        <ul className="rs-kv ov-kv">{domains.body.domains.slice(0, 4).map(domain => <li key={domain.site_id}><span>{domain.host}</span><strong>{number(domain.metrics.sessions)}</strong></li>)}</ul>
      </Section>}
      <Section className="ov-health" title="Saúde dos dados" description="Última atualização de cada fonte" action={more(reportUrl('data-sources'), 'Fontes')}>
        {sources.loading || sites.loading ? <LoadingState rows={2}/> : <SourceHealth sources={sources.body?.keys} sites={sites.body?.sites} conflicts={media.conflicts}/>}
      </Section>
    </div>
  </div>;
}
