import React from 'react';
import {ArrowRight} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {DomainsOverview} from '../../DomainsOverview.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, Async, DataTable, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {compact, number, percent, siteTotals} from '../shared.jsx';
import {SiteVisuals} from './SiteVisuals.jsx';

const link = (href, label) => <AppLink className="rs-link" href={href}>{label}<ArrowRight size={14} aria-hidden="true"/></AppLink>;

/** "O que as pessoas fazem depois de chegar?" — site totals, entries and origins, then each domain in detail. */
export function JourneyOverview({data, sites = []}) {
  const {period, setPeriod, scope} = useReportsContext();
  const range = {start_date: period.start, end_date: period.end};
  const [domains] = useApi(apiUrl('/pages/domains', range));
  const [navigation, retryNavigation] = useApi(apiUrl('/journey/navigation', {...range, site_id: scope.site}));
  const inScope = item => !scope.site || item.site_id === scope.site;
  const site = domains.body ? siteTotals(domains.body.domains.filter(inScope)) : null;
  const entries = (navigation.body?.pages || []).filter(inScope);
  return <div className="rs-stack">
    {!site ? <LoadingState rows={2}/> : <MetricGroup label="Resumo do site" items={[
      {label: 'Usuários', value: compact(site.visitors)},
      {label: 'Sessões', value: compact(site.sessions), change: site.sessionsChange},
      {label: 'Visualizações', value: compact(site.views), detail: site.sessions ? `${(site.views / site.sessions).toLocaleString('pt-BR', {maximumFractionDigits: 1})} por sessão` : undefined},
      {label: 'Conversões', value: number(site.conversions), detail: `${percent(site.conversions, site.sessions)} das sessões`},
    ]}/>}
    <div className="rs-grid rs-grid--2">
      <Section title="Principais entradas" description="Onde as visitas começam" action={link(reportUrl('journey/navigation'), 'Ver navegação')}>
        <Async state={navigation} onRetry={retryNavigation} isEmpty={() => !entries.length} empty={<p className="rs-muted">Sem visitas no período.</p>}>
          {() => <DataTable label="Principais entradas" limit={5} rows={[...entries].filter(row => row.entries > 0).sort((a, b) => b.entries - a.entries)} rowKey={row => row.host + row.path} columns={[
            {key: 'path', label: 'Página', sortable: false, render: row => <span className="rs-path" title={`${row.host}${row.path}`}>{row.path}</span>},
            {key: 'entries', label: 'Entradas', numeric: true, sortable: false, render: row => number(row.entries)},
            {key: 'exit_rate', label: 'Saída', numeric: true, sortable: false, render: row => `${row.exit_rate.toLocaleString('pt-BR')}%`},
          ]}/>}
        </Async>
      </Section>
      <Section title="Origem das visitas" description="Primeiro contato de cada sessão">
        <Async state={navigation} onRetry={retryNavigation} isEmpty={body => !body.origins.length} empty={<p className="rs-muted">Sem visitas no período.</p>}>
          {body => {const total = body.origins.reduce((sum, item) => sum + item.sessions, 0); return <ul className="rs-bars">{body.origins.slice(0, 6).map(item => <li key={item.platform}><span>{item.label}</span><i><b style={{width: `${Math.max(2, item.sessions * 100 / (total || 1))}%`}}/></i><strong>{percent(item.sessions, total)}</strong></li>)}</ul>;}}
        </Async>
      </Section>
    </div>
    <SiteVisuals data={data} pages={navigation.body?.pages || []} sites={sites}/>
    <DomainsOverview data={data} range={period} onRangeChange={setPeriod} siteId={scope.site}/>
  </div>;
}
