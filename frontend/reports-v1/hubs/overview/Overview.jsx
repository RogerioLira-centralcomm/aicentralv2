import {dayLabel} from '../../friendlyDates.js';
import React from 'react';
import {ArrowRight} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Chart} from '../../shell/media.jsx';
import {AppLink, Async, EmptyState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {SourceHealth, compact, compactCurrency, currency, number, percent, siteTotals, useMedia} from '../shared.jsx';
import {OverviewSetup} from './OverviewSetup.jsx';

const SEVERITY = {high: 'Alta', medium: 'Média', low: 'Baixa'};
const more = (href, label) => <AppLink className="rs-link" href={href}>{label}<ArrowRight size={14} aria-hidden="true"/></AppLink>;

/** Status of the whole ecosystem: the headline numbers, one summary per area, what needs attention and data freshness. */
export function Overview({data}) {
  const {period} = useReportsContext();
  const media = useMedia(period);
  const [domains, retryDomains] = useApi(apiUrl('/pages/domains', {start_date: period.start, end_date: period.end}));
  const [alerts] = useApi(apiUrl('/alerts'));
  const [sites] = useApi(apiUrl('/supertag/sites'));
  const [sources] = useApi(apiUrl('/ingest-keys'));
  const site = domains.body ? siteTotals(domains.body.domains) : null;
  const summary = media.summary;
  const activeAlerts = alerts.body?.alerts || [];
  const settled = !media.loading && !domains.loading;
  // Onboarding stays until there is something to read in either media or the site.
  if (settled && !summary && !site?.sessions) return <div className="rs-stack">
    <OverviewSetup data={data} sites={sites.body?.sites ?? (sites.error ? null : [])} sources={sources.body?.keys ?? (sources.error ? null : [])} imported={media.conflicts ? {conflicts: media.conflicts} : null}/>
  </div>;
  const totals = summary?.totals;
  return <div className="rs-stack">
    {!settled ? <LoadingState rows={2}/> : <MetricGroup label="Resumo do período" items={[
      {label: 'Investimento', value: totals ? compactCurrency(totals.cost, summary.currency) : '—', detail: summary ? summary.origin : 'Sem dados de mídia'},
      {label: 'Impressões', value: totals ? compact(totals.impressions) : '—', detail: totals ? `${compact(totals.clicks)} cliques` : undefined},
      {label: 'Visitas', value: site ? compact(site.sessions) : '—', change: site?.sessionsChange, detail: site ? 'Sessões no site' : 'Sem Super Tag'},
      {label: 'Conversões', value: site ? number(site.conversions) : '—', detail: site?.sessions ? `${percent(site.conversions, site.sessions)} das visitas` : undefined},
    ]}/>}
    <div className="rs-grid rs-grid--2">
      <Section title="Mídia" description="Canais com maior investimento no período" action={more(reportUrl('media'), 'Abrir Mídia')}>
        {media.loading ? <LoadingState/> : !summary ? <EmptyState title="Sem dados de mídia neste período" description="Conecte uma fonte ou envie um arquivo para ver investimento e resultados." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/data')}>Conectar fonte</ReportsActionButton>}/>
          : <ul className="rs-bars">{summary.platforms.slice(0, 5).map(item => {
            const share = summary.totals.cost ? (item.cost || 0) / summary.totals.cost : summary.totals.impressions ? item.impressions / summary.totals.impressions : 0;
            return <li key={item.platform}><span>{item.label}</span><i><b style={{width: `${Math.max(2, share * 100)}%`}}/></i><strong>{item.cost != null ? currency(item.cost, summary.currency) : compact(item.impressions)}</strong></li>;
          })}</ul>}
      </Section>
      <Section title="Site & Jornada" description="Visitas por dia em todos os domínios" action={more(reportUrl('journey'), 'Abrir Site & Jornada')}>
        <Async state={domains} onRetry={retryDomains} isEmpty={body => !body.domains.length}
          empty={<EmptyState title="Nenhum site monitorado" description="Instale a Super Tag para acompanhar o que acontece depois do clique." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('supertag')}>Conectar site</ReportsActionButton>}/>}>
          {() => <>
            <Chart type="area" height={180} labels={site.daily.map(item => dayLabel(item.date))} values={site.daily.map(item => item.sessions)}/>
            <ul className="rs-kv">{domains.body.domains.slice(0, 3).map(domain => <li key={domain.site_id}><span>{domain.host}</span><strong>{number(domain.metrics.sessions)} visitas</strong></li>)}</ul>
          </>}
        </Async>
      </Section>
    </div>
    <div className="rs-grid rs-grid--2">
      <Section title="Alertas" description={activeAlerts.length ? `${activeAlerts.length} ${activeAlerts.length === 1 ? 'aberto' : 'abertos'}` : 'Nada pede atenção agora'} action={more(reportUrl('alerts'), 'Ver alertas')}>
        {alerts.loading ? <LoadingState rows={2}/> : activeAlerts.length ? <ul className="rs-list">{activeAlerts.slice(0, 3).map(alert => <li key={alert.id}>
          <span className={`rs-badge is-${alert.severity}`}>{SEVERITY[alert.severity] || alert.severity}</span>
          <span className="rs-list__copy"><strong>{alert.title}</strong><small>{alert.allowed_host}{alert.page_path ? ` · ${alert.page_path}` : ''}</small></span>
        </li>)}</ul> : <p className="rs-muted">Nenhum alerta aberto para este cliente.</p>}
      </Section>
      <Section title="Saúde dos dados" description="Última atualização de cada fonte" action={more(reportUrl('data-sources'), 'Fontes de dados')}>
        {sources.loading || sites.loading ? <LoadingState rows={2}/> : <SourceHealth sources={sources.body?.keys} sites={sites.body?.sites} conflicts={media.conflicts}/>}
      </Section>
    </div>
  </div>;
}
