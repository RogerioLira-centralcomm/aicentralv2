import React, {useMemo, useState} from 'react';
import {SearchLg} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsFieldInput} from '../../ReportsFieldInput.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, Async, DataTable, EmptyState, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

const seconds = value => value == null ? '—' : value < 60 ? `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 0})} s` : `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;

/** "Quais páginas funcionam melhor?" — every monitored URL with entries, exits and conversions; a row opens the page. */
export function PagesList() {
  const {period, scope} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/navigation', {start_date: period.start, end_date: period.end}));
  const [query, setQuery] = useState('');
  const [host, setHost] = useState('');
  const pages = (state.body?.pages || []).filter(item => !scope.site || item.site_id === scope.site);
  const hosts = useMemo(() => [...new Set(pages.map(item => item.host))], [pages]);
  const visible = pages.filter(item => (!host || item.host === host) && (!query || item.path.toLowerCase().includes(query.trim().toLowerCase())));
  return <Section title="Páginas" description={pages.length ? `${pages.length} páginas com visitas no período${pages.length === 100 ? ' (as 100 mais vistas)' : ''}` : 'URLs reais do site, com visitas e resultado'}
    action={pages.length > 0 && <div className="rs-toolbar">
      {hosts.length > 1 && <div className="rs-segmented" role="group" aria-label="Domínio"><button type="button" aria-pressed={!host} onClick={() => setHost('')}>Todos</button>{hosts.map(item => <button type="button" key={item} aria-pressed={host === item} onClick={() => setHost(item)}>{item}</button>)}</div>}
      <label className="rs-search"><ReportsFieldInput leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>} type="search" placeholder="Buscar página" value={query} onChange={event => setQuery(event.target.value)} aria-label="Buscar página"/></label>
    </div>}>
    <Async state={state} onRetry={retry} rows={8} isEmpty={body => !body.pages.length}
      empty={<EmptyState title="Nenhuma visita registrada no período" description="As páginas aparecem aqui quando a Super Tag recebe visitas. Confira a instalação ou escolha outro período." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('supertag')}>Ver Super Tag</ReportsActionButton>}/>}>
      {() => <DataTable label="Páginas" rows={visible} rowKey={row => `${row.site_id}${row.path}`} initialSort={{key: 'views', dir: 'desc'}}
        empty={<p className="rs-muted">Nenhuma página corresponde à busca.</p>} columns={[
          {key: 'path', label: 'Página', render: row => <AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path: row.path})}>{row.path}{hosts.length > 1 && <small>{row.host}</small>}</AppLink>},
          {key: 'views', label: 'Visualizações', numeric: true, render: row => number(row.views)},
          {key: 'visitors', label: 'Usuários', numeric: true, render: row => number(row.visitors)},
          {key: 'entries', label: 'Entradas', numeric: true, render: row => number(row.entries)},
          {key: 'exit_rate', label: 'Saídas', numeric: true, render: row => `${row.exit_rate.toLocaleString('pt-BR')}%`},
          {key: 'conversions', label: 'Conversões', numeric: true, render: row => row.conversions ? <span title={`${percent(row.conversions, row.views)} das visualizações`}>{number(row.conversions)}</span> : '—'},
          {key: 'avg_active_seconds', label: 'Tempo médio', numeric: true, sort: row => Number(row.avg_active_seconds || 0), render: row => seconds(row.avg_active_seconds)},
        ]}/>}
    </Async>
  </Section>;
}
