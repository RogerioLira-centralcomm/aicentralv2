import React, {useMemo} from 'react';
import {sankeyLayout} from '../../sankeyLayout.js';
import {ArrowRight} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, Async, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

/** Most common steps as two columns of pages: where the visit was and where it went next. */
function PathsSankey({paths, sessions}) {
  const map = useMemo(() => {
    const top = paths.slice(0, 10);
    const nodes = new Map();
    top.forEach(row => {
      nodes.set(`f:${row.from_path}`, {id: `f:${row.from_path}`, column: 0, label: row.from_path});
      nodes.set(`t:${row.to_path}`, {id: `t:${row.to_path}`, column: 1, label: row.to_path});
    });
    return sankeyLayout({nodes: [...nodes.values()], links: top.map(row => ({source: `f:${row.from_path}`, target: `t:${row.to_path}`, value: Number(row.sessions)}))},
      {width: 960, height: Math.max(180, Math.min(420, nodes.size * 28)), labelPad: 220});
  }, [paths]);
  if (paths.length < 2) return null;
  const label = id => map.nodes.find(node => node.id === id)?.label;
  return <div className="page-detail-sankey-wrap"><svg className="page-detail-sankey" viewBox={`-4 -8 ${map.width + 8} ${map.height + 16}`} role="img"
    aria-label={`Os ${Math.min(10, paths.length)} caminhos mais comuns entre páginas`}>
    <g className="page-detail-sankey-links">{map.links.map(link => <path key={`${link.source}>${link.target}`} d={link.path} strokeWidth={Math.max(1, link.width)}>
      <title>{`${label(link.source)} → ${label(link.target)}: ${number(link.value)} sessões (${percent(link.value, sessions)})`}</title></path>)}</g>
    <g>{map.nodes.map(node => <g key={node.id}><rect x={node.x} y={node.y} width={node.w} height={Math.max(2, node.h)} rx="3"/>
      <text x={node.column === 0 ? node.x - 8 : node.x + node.w + 8} y={node.y + Math.max(2, node.h) / 2} dy="0.35em" textAnchor={node.column === 0 ? 'end' : 'start'}>
        <tspan>{node.label.length > 34 ? `${node.label.slice(0, 33)}…` : node.label}</tspan><tspan className="page-detail-sankey-count" dx="6">{number(node.value)}</tspan></text></g>)}</g>
  </svg></div>;
}

const pageLink = (row, path = row.path) => <AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path})}>{path}</AppLink>;

/** "Como os usuários se movimentam?" — observation only: where visits start, move next and leave. Modelling stays in Fluxos. */
export function Navigation() {
  const {period} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/navigation', {start_date: period.start, end_date: period.end}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const body = state.body;
  if (!body?.pages.length) return <EmptyState title="Sem navegação no período" description="Os caminhos aparecem quando a Super Tag recebe visitas com mais de uma página."/>;
  const totals = body.totals;
  const sessions = Number(totals.sessions || 0);
  const siteOf = Object.fromEntries(body.pages.map(page => [`${page.host}${page.path}`, page.site_id]));
  const entries = [...body.pages].filter(row => row.entries > 0).sort((a, b) => b.entries - a.entries);
  const exits = [...body.pages].filter(row => row.exits > 0).sort((a, b) => b.exits - a.exits);
  const pathRow = row => ({...row, site_id: siteOf[`${row.host}${row.from_path}`] || siteOf[`${row.host}${row.to_path}`]});
  return <div className="rs-stack">
    <MetricGroup label="Resumo da navegação" items={[
      {label: 'Sessões', value: number(sessions)},
      {label: 'Páginas por sessão', value: sessions ? (Number(totals.views) / sessions).toLocaleString('pt-BR', {maximumFractionDigits: 1}) : '—'},
      {label: 'Sessões de uma página', value: percent(totals.single_page_sessions, sessions), detail: 'Saíram sem visitar outra página'},
      {label: 'Caminhos diferentes', value: number(body.paths.length), detail: body.paths.length >= 25 ? 'Os 25 mais comuns' : undefined},
    ]}/>
    <Section title="Caminhos mais comuns" description="Página atual e a próxima visitada na mesma sessão" action={<AppLink className="rs-link" href={reportUrl('flows')}>Modelar em Fluxos<ArrowRight size={14} aria-hidden="true"/></AppLink>}>
      <PathsSankey paths={body.paths} sessions={sessions}/>
      <DataTable label="Caminhos mais comuns" rows={body.paths.map(pathRow)} rowKey={row => `${row.host}${row.from_path}>${row.to_path}`}
        empty={<p className="rs-muted">Nenhuma sessão passou por mais de uma página.</p>} columns={[
          {key: 'from_path', label: 'De', render: row => pageLink(row, row.from_path)},
          {key: 'to_path', label: 'Para', render: row => <span className="rs-step"><ArrowRight size={14} aria-hidden="true"/>{pageLink(row, row.to_path)}</span>},
          {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
          {key: 'share', label: 'Das sessões', numeric: true, sort: row => row.sessions, render: row => percent(row.sessions, sessions)},
        ]}/>
    </Section>
    <div className="rs-grid rs-grid--2">
      <Section title="Por onde entram" description="Primeira página da sessão">
        <DataTable label="Entradas" limit={10} rows={entries} rowKey={row => row.host + row.path} columns={[
          {key: 'path', label: 'Página', render: row => pageLink(row)},
          {key: 'entries', label: 'Entradas', numeric: true, render: row => number(row.entries)},
          {key: 'single_page', label: 'Saíram logo', numeric: true, render: row => percent(row.single_page, row.entries)},
        ]}/>
      </Section>
      <Section title="Onde abandonam" description="Última página da sessão">
        <DataTable label="Saídas" limit={10} rows={exits} rowKey={row => row.host + row.path} columns={[
          {key: 'path', label: 'Página', render: row => pageLink(row)},
          {key: 'exits', label: 'Saídas', numeric: true, render: row => number(row.exits)},
          {key: 'exit_rate', label: 'Taxa de saída', numeric: true, render: row => `${row.exit_rate.toLocaleString('pt-BR')}%`},
        ]}/>
      </Section>
    </div>
    <Section title="Origem das visitas" description="Primeiro contato de cada sessão">
      <Async state={state} onRetry={retry} isEmpty={value => !value.origins.length} empty={<p className="rs-muted">Sem origem identificada.</p>}>
        {value => <ul className="rs-bars">{value.origins.flatMap(item => [
          <li key={item.platform}><span>{item.label}</span><i><b style={{width: `${Math.max(2, item.sessions * 100 / (sessions || 1))}%`}}/></i><strong>{number(item.sessions)}</strong></li>,
          ...(item.engines || []).map(engine => <li key={`${item.platform}:${engine.engine}`} className="rs-bars__sub"><span>{engine.label}</span><i><b style={{width: `${Math.max(2, engine.sessions * 100 / (sessions || 1))}%`}}/></i><strong>{number(engine.sessions)}</strong></li>),
        ])}</ul>}
      </Async>
    </Section>
  </div>;
}
