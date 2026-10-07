import React, {useMemo} from 'react';
import {AlertTriangle, ArrowRight, CheckCircle, XCircle} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {dayLabel} from '../../friendlyDates.js';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {customerParam} from '../../shell/customerScope.js';
import {Chart} from '../../shell/media.jsx';
import {AppLink, Async, DataTable, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {compact, number, percent, siteTotals} from '../shared.jsx';
import {sectionName} from './Contents.jsx';
import {Donut} from './TechPanel.jsx';
import './journey.css';

const MONITOR_ICON = {online: [CheckCircle, 'No ar'], degraded: [AlertTriangle, 'Instável'], offline: [XCircle, 'Fora do ar']};

/** One row per published flow: availability of its pages, linking straight to the flow's monitor. */
function FlowMonitors({flows}) {
  if (!flows.length) return null;
  return <Section title="Monitoramento dos fluxos" description="Disponibilidade das páginas de cada fluxo publicado">
    <ul className="rs-flow-monitors">
      {flows.map(flow => {
        const [Icon, label] = MONITOR_ICON[flow.monitor_status] || [AlertTriangle, flow.monitor_enabled ? 'Aguardando checagem' : 'Sem monitor'];
        const detail = !flow.monitor_enabled ? 'Monitor desligado' : flow.total ? (flow.failing ? `${flow.failing} de ${flow.total} páginas com problema` : `${flow.total} páginas no ar`) : 'Ainda sem verificação';
        return <li key={flow.id}><AppLink href={reportUrl(`flows/${flow.id}/monitor`)} className={`rs-flow-monitors__item is-${flow.monitor_enabled ? flow.monitor_status : 'off'}`}>
          <Icon size={20} aria-hidden="true"/><span><strong>{flow.name}</strong><small>{flow.host} · {detail}</small></span><b>{label}</b><ArrowRight size={14} aria-hidden="true"/>
        </AppLink></li>;
      })}
    </ul>
  </Section>;
}

const link = (href, label) => <AppLink className="rs-link" href={href}>{label}<ArrowRight size={14} aria-hidden="true"/></AppLink>;
const seconds = value => value == null ? '—' : value < 60 ? `${Math.round(value)} s` : `${Math.floor(value / 60)} min ${String(Math.round(value % 60)).padStart(2, '0')} s`;

/** Sum rows that share a key (the same page or device seen on several domains). */
function merge(rows, key, fields) {
  const map = new Map();
  rows.forEach(row => {
    const current = map.get(key(row)) || {...row, ...Object.fromEntries(fields.map(field => [field, 0]))};
    fields.forEach(field => {current[field] += Number(row[field] || 0);});
    map.set(key(row), current);
  });
  return [...map.values()];
}

/** Share of the total as a bar with its number, for the channel table. */
const Share = ({value, total}) => <span className="rs-share"><i><b style={{width: `${Math.max(2, value * 100 / (total || 1))}%`}}/></i><span>{percent(value, total)}</span></span>;

/** "O que as pessoas fazem depois de chegar?" — KPIs, traffic and channels, entries and devices, pages and contents. The heatmap lives in its own tab. */
export function JourneyOverview() {
  const {period, scope} = useReportsContext();
  const range = {start_date: period.start, end_date: period.end, customer_id: customerParam()};
  const [domains, retryDomains] = useApi(apiUrl('/pages/domains', range));
  const [navigation, retryNavigation] = useApi(apiUrl('/journey/navigation', {...range, site_id: scope.site, customer_id: customerParam()}));
  const [content, retryContent] = useApi(apiUrl('/journey/content', {...range, site_id: scope.site || undefined, customer_id: customerParam()}));
  const [monitors] = useApi(apiUrl('/journey/monitors', {site_id: scope.site || undefined}));
  const inScope = item => !scope.site || item.site_id === scope.site;
  const scoped = useMemo(() => (domains.body?.domains || []).filter(inScope), [domains.body, scope.site]);
  const site = domains.body ? siteTotals(scoped) : null;
  const entries = (navigation.body?.pages || []).filter(inScope).filter(row => row.entries > 0);
  const devices = useMemo(() => merge(scoped.flatMap(domain => domain.devices), item => item.device, ['sessions']).sort((a, b) => b.sessions - a.sessions), [scoped]);
  const pages = useMemo(() => merge(scoped.flatMap(domain => domain.top_pages.map(page => ({...page, site_id: domain.site_id, host: domain.host}))), page => `${page.site_id}${page.path}`, ['views', 'sessions', 'conversions']), [scoped]);
  const sections = (content.body?.sections || []).filter(inScope);
  if (domains.error) return <ErrorState message={domains.error} onRetry={retryDomains}/>;
  if (!site) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const deviceTotal = devices.reduce((sum, item) => sum + item.sessions, 0);
  const viewsPerSession = site.sessions ? (site.views / site.sessions).toLocaleString('pt-BR', {maximumFractionDigits: 1}) : null;
  return <div className="rs-stack rs-journey-overview">
    <MetricGroup label="Resumo do site" items={[
      {label: 'Usuários', value: compact(site.visitors), change: site.visitorsChange},
      {label: 'Sessões', value: compact(site.sessions), change: site.sessionsChange},
      {label: 'Visualizações', value: compact(site.views), change: site.viewsChange, detail: viewsPerSession ? `${viewsPerSession} por sessão` : undefined},
      {label: 'Conversões', value: number(site.conversions), change: site.conversionsChange, detail: `${percent(site.conversions, site.sessions)} das sessões`},
    ]}/>
    <FlowMonitors flows={monitors.body?.flows || []}/>
    <div className="rs-journey-overview__main">
      <Section title="Evolução de tráfego" description="Sessões por dia no período">
        {site.daily.length > 1
          ? <Chart type="area" height={240} labels={site.daily.map(day => dayLabel(day.date))} series={[{name: 'Sessões', data: site.daily.map(day => day.sessions)}]} legend={false}/>
          : <p className="rs-muted">Sem visitas suficientes no período.</p>}
      </Section>
      <Section title="Principais canais de origem" description="Primeiro contato de cada sessão" action={link(reportUrl('journey/navigation'), 'Ver navegação')}>
        <Async state={navigation} onRetry={retryNavigation} isEmpty={body => !body.origins.length} empty={<p className="rs-muted">Sem visitas no período.</p>}>
          {body => {
            const total = body.origins.reduce((sum, item) => sum + item.sessions, 0);
            return <DataTable label="Principais canais de origem" limit={7} rows={body.origins} rowKey={row => row.platform} initialSort={{key: 'sessions', dir: 'desc'}} columns={[
              {key: 'label', label: 'Canal', sortable: false},
              {key: 'sessions', label: 'Sessões', numeric: true, sortable: false, render: row => number(row.sessions)},
              {key: 'share', label: 'Participação', sortable: false, render: row => <Share value={row.sessions} total={total}/>},
            ]}/>;
          }}
        </Async>
      </Section>
    </div>
    <div className="rs-grid rs-grid--2">
      <Section title="Principais entradas" description="Páginas onde as visitas começam" action={link(reportUrl('journey/navigation'), 'Ver todas')}>
        <Async state={navigation} onRetry={retryNavigation} isEmpty={() => !entries.length} empty={<p className="rs-muted">Sem visitas no período.</p>}>
          {() => {
            const total = entries.reduce((sum, row) => sum + row.entries, 0);
            return <DataTable label="Principais entradas" limit={5} rows={entries} rowKey={row => row.host + row.path} initialSort={{key: 'entries', dir: 'desc'}} columns={[
              {key: 'path', label: 'Página', sortable: false, render: row => <span className="rs-path" title={`${row.host}${row.path}`}>{row.path}</span>},
              {key: 'entries', label: 'Entradas', numeric: true, sortable: false, render: row => number(row.entries)},
              {key: 'share', label: '%', numeric: true, sortable: false, sort: row => row.entries, render: row => percent(row.entries, total)},
              {key: 'exit_rate', label: 'Saída', numeric: true, sortable: false, render: row => `${row.exit_rate.toLocaleString('pt-BR')}%`},
            ]}/>;
          }}
        </Async>
      </Section>
      <Section title="Dispositivos" description="Sessões por tipo de aparelho">
        {devices.length
          ? <Donut items={devices.map(item => ({key: item.device, label: item.label, sessions: item.sessions}))} total={deviceTotal} label="Sessões por tipo de aparelho"/>
          : <p className="rs-muted">Sem dados de dispositivo.</p>}
      </Section>
    </div>
    <div className="rs-grid rs-grid--2">
      <Section title="Páginas mais vistas" description="Abra uma página para ver cliques, rolagem e origem" action={link(reportUrl('journey/pages'), 'Ver todas')}>
        {pages.length ? <DataTable label="Páginas mais vistas" limit={5} rows={pages} rowKey={row => `${row.site_id}${row.path}`} initialSort={{key: 'views', dir: 'desc'}} columns={[
          {key: 'path', label: 'Página', sortable: false, render: row => <AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path: row.path})}>{row.path}{scoped.length > 1 && <small>{row.host}</small>}</AppLink>},
          {key: 'views', label: 'Visualizações', numeric: true, sortable: false, render: row => number(row.views)},
          {key: 'sessions', label: 'Sessões', numeric: true, sortable: false, render: row => number(row.sessions)},
          {key: 'avg_active_seconds', label: 'Tempo médio', numeric: true, sortable: false, render: row => seconds(row.avg_active_seconds)},
        ]}/> : <p className="rs-muted">Nenhuma página vista no período.</p>}
      </Section>
      <Section title="Conteúdos em destaque" description="Seções do site que mais atraem e convertem" action={link(reportUrl('journey/content'), 'Ver todos')}>
        <Async state={content} onRetry={retryContent} isEmpty={() => !sections.length} empty={<p className="rs-muted">Sem conteúdos visitados no período.</p>}>
          {() => <DataTable label="Conteúdos em destaque" limit={5} rows={sections} rowKey={row => `${row.site_id}${row.section}`} initialSort={{key: 'views', dir: 'desc'}} columns={[
            {key: 'section', label: 'Conteúdo', sortable: false, render: row => <strong>{sectionName(row.section)}</strong>},
            {key: 'views', label: 'Visualizações', numeric: true, sortable: false, render: row => number(row.views)},
            {key: 'converted_sessions', label: 'Conversões', numeric: true, sortable: false, render: row => number(row.converted_sessions)},
            {key: 'rate', label: 'Taxa', numeric: true, sortable: false, sort: row => row.converted_sessions / (row.sessions || 1), render: row => percent(row.converted_sessions, row.sessions)},
          ]}/>}
        </Async>
      </Section>
    </div>
    {scoped.length > 1 && <Section title="Domínios" description={`${scoped.length} domínios monitorados`}>
      <DataTable label="Domínios" rows={scoped} rowKey={row => row.site_id} initialSort={{key: 'sessions', dir: 'desc'}} columns={[
        {key: 'host', label: 'Domínio', sort: row => row.host, render: row => <AppLink className="rs-path" href={reportUrl('journey/pages', {scope_site: row.site_id})}>{row.host}</AppLink>},
        {key: 'sessions', label: 'Sessões', numeric: true, sort: row => row.metrics.sessions, render: row => number(row.metrics.sessions)},
        {key: 'visitors', label: 'Usuários', numeric: true, sort: row => row.metrics.visitors, render: row => number(row.metrics.visitors)},
        {key: 'views', label: 'Visualizações', numeric: true, sort: row => row.metrics.views, render: row => number(row.metrics.views)},
        {key: 'conversions', label: 'Conversões', numeric: true, sort: row => row.metrics.conversions, render: row => number(row.metrics.conversions)},
      ]}/>
    </Section>}
  </div>;
}
