import React from 'react';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

export const sectionName = path => path === '/' ? 'Página inicial' : path.slice(1).replace(/[-_]+/g, ' ').replace(/^./, letter => letter.toUpperCase());

/**
 * "Quais conteúdos influenciam comportamento e conversão?" — each site section is read as one content:
 * reach, sessions that converted after seeing it, and the paid campaigns that send people there.
 */
export function Contents() {
  const {period, scope} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/content', {start_date: period.start, end_date: period.end, site_id: scope.site || undefined}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const sections = state.body.sections;
  if (!sections.length) return <EmptyState title="Sem conteúdos visitados no período" description="Os conteúdos aparecem quando a Super Tag registra visitas. Cada seção do site (por exemplo /blog ou /produtos) vira um conteúdo."/>;
  const sessions = sections.reduce((sum, item) => sum + Number(item.sessions), 0);
  const best = [...sections].filter(item => item.sessions >= 20).sort((a, b) => b.converted_sessions / b.sessions - a.converted_sessions / a.sessions)[0];
  const paid = sections.filter(item => item.campaigns.length);
  const hosts = new Set(sections.map(item => item.host));
  return <div className="rs-stack">
    <MetricGroup label="Resumo dos conteúdos" items={[
      {label: 'Conteúdos visitados', value: number(sections.length), detail: `${hosts.size} ${hosts.size === 1 ? 'site' : 'sites'}`},
      {label: 'Mais visto', value: sectionName(sections[0].section), detail: `${number(sections[0].views)} visualizações`},
      {label: 'Maior influência', value: best ? sectionName(best.section) : '—', detail: best ? `${percent(best.converted_sessions, best.sessions)} das sessões converteram` : 'Amostra pequena'},
      {label: 'Com mídia paga', value: number(paid.length), detail: 'Recebem tráfego de campanhas'},
    ]}/>
    <Section title="Conteúdos" description="Seções do site com alcance, conversão das sessões que passaram por elas e campanhas que levam até lá">
      <DataTable label="Conteúdos" rows={sections} rowKey={row => `${row.site_id}${row.section}`} initialSort={{key: 'views', dir: 'desc'}} columns={[
        {key: 'section', label: 'Conteúdo', render: row => <><strong>{sectionName(row.section)}</strong><small className="rs-cell-sub">{hosts.size > 1 ? `${row.host} · ` : ''}{row.section === '/' ? '/' : `${row.section}/…`} · {row.pages} {row.pages === 1 ? 'página' : 'páginas'}</small></>},
        {key: 'views', label: 'Visualizações', numeric: true, render: row => number(row.views)},
        {key: 'visitors', label: 'Usuários', numeric: true, render: row => number(row.visitors)},
        {key: 'share', label: 'Alcance', numeric: true, sort: row => row.sessions, render: row => percent(row.sessions, sessions)},
        {key: 'converted_sessions', label: 'Sessões que converteram', numeric: true, render: row => row.converted_sessions ? `${number(row.converted_sessions)} · ${percent(row.converted_sessions, row.sessions)}` : '—'},
        {key: 'campaigns', label: 'Campanhas', sortable: false, render: row => row.campaigns.length ? <span title={row.campaigns.join(', ')}>{row.campaigns[0]}{row.campaigns.length > 1 ? ` +${row.campaigns.length - 1}` : ''}</span> : '—'},
        {key: 'top_path', label: 'Página principal', sortable: false, render: row => row.top_path ? <AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path: row.top_path})}>{row.top_path}</AppLink> : '—'},
      ]}/>
    </Section>
  </div>;
}
