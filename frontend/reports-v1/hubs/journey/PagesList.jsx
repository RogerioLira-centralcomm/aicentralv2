import React, {useMemo, useState} from 'react';
import {SearchLg} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsFieldInput} from '../../ReportsFieldInput.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, Async, DataTable, EmptyState, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';
import {sectionName} from './Contents.jsx';
import {OriginPicker, useOrigin} from './origin.jsx';
import './journey.css';

const seconds = value => value == null ? '—' : value < 60 ? `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 0})} s` : `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
const ROLES = {
  conversion: ['Conversão', 'Sessões que passaram por esta página converteram.'],
  entry: ['Entrada', 'Metade ou mais das visualizações começam a visita aqui.'],
  exit: ['Saída', 'Metade ou mais das visualizações terminam a visita aqui.'],
  transit: ['Passagem', 'A maior parte das visitas chega e segue para outra página.'],
};
const sectionOf = path => path === '/' ? '/' : `/${path.split('/')[1]}`;
const initialSearch = () => {try {return (new URLSearchParams(location.search).get('busca') || '').slice(0, 120);} catch {return '';}};

/** "Quais páginas funcionam melhor?" — every monitored URL with its role, where its visitors come from and its result. */
export function PagesList() {
  const {period, scope} = useReportsContext();
  const [origin, setOrigin] = useOrigin();
  const [state, retry] = useApi(apiUrl('/journey/navigation', {start_date: period.start, end_date: period.end, site_id: scope.site || undefined, origin: origin || undefined}));
  const [query, setQuery] = useState(initialSearch);
  const [host, setHost] = useState('');
  const pages = (state.body?.pages || []).filter(item => !scope.site || item.site_id === scope.site);
  const groups = state.body?.origin_groups || [];
  const allSessions = groups.reduce((sum, item) => sum + item.sessions, 0);
  const hosts = useMemo(() => [...new Set(pages.map(item => item.host))], [pages]);
  const needle = query.trim().toLowerCase();
  // A search that starts with "/" is a section ("/contato" also finds "/contato/obrigado"); anything else matches inside the path.
  const matches = item => !needle || (needle.startsWith('/') ? item.path.toLowerCase().startsWith(needle) : item.path.toLowerCase().includes(needle));
  const visible = pages.filter(item => (!host || item.host === host) && matches(item));
  const chosen = groups.find(item => item.origin === origin);
  return <Section title="Páginas" description={pages.length ? `${pages.length} páginas com visitas no período${chosen ? ` · ${chosen.label}` : ''}${pages.length === 100 ? ' (as 100 mais vistas)' : ''}` : 'URLs reais do site, com visitas e resultado'}
    action={(pages.length > 0 || origin) && <div className="rs-toolbar">
      {hosts.length > 1 && <div className="rs-segmented" role="group" aria-label="Domínio"><button type="button" aria-pressed={!host} onClick={() => setHost('')}>Todos</button>{hosts.map(item => <button type="button" key={item} aria-pressed={host === item} onClick={() => setHost(item)}>{item}</button>)}</div>}
      <label className="rs-search"><ReportsFieldInput leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>} type="search" placeholder="Buscar página" value={query} onChange={event => setQuery(event.target.value)} aria-label="Buscar página"/></label>
    </div>}>
    {allSessions > 0 && <div className="rs-nav__bar rs-pages__origin"><OriginPicker groups={groups} value={origin} onChange={setOrigin} total={allSessions}/>{chosen && <p className="rs-nav__hint">{chosen.hint}</p>}</div>}
    <Async state={state} onRetry={retry} rows={8} isEmpty={body => !body.pages.length && !origin}
      empty={<EmptyState title="Nenhuma visita registrada no período" description="As páginas aparecem aqui quando a Super Tag recebe visitas. Confira a instalação ou escolha outro período." action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('supertag')}>Ver Super Tag</ReportsActionButton>}/>}>
      {() => <DataTable label="Páginas" rows={visible} rowKey={row => `${row.site_id}${row.path}`} initialSort={{key: 'views', dir: 'desc'}}
        empty={<p className="rs-muted">{origin && !pages.length ? `Nenhuma página vista por sessões de ${chosen?.label || 'esta origem'} no período.` : 'Nenhuma página corresponde à busca.'}</p>} columns={[
          {key: 'path', label: 'Página', render: row => <><AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path: row.path})}>{row.path}{hosts.length > 1 && <small>{row.host}</small>}</AppLink>
            <small className="rs-cell-sub"><AppLink className="rs-link" href={reportUrl('journey/content')}>{sectionName(sectionOf(row.path))}</AppLink></small></>},
          {key: 'role', label: 'Papel', sort: row => ROLES[row.role] ? ROLES[row.role][0] : '', render: row => ROLES[row.role]
            ? <span className={`rs-role rs-role--${row.role}`} title={ROLES[row.role][1]}>{ROLES[row.role][0]}</span> : <span className="rs-muted" title="Poucas visualizações para classificar a página.">—</span>},
          {key: 'origins', label: 'Origem principal', sortable: false, render: row => row.origins?.length
            ? <span title={row.origins.map(item => `${item.label}: ${number(item.sessions)} sessões (${item.share.toLocaleString('pt-BR')}%)`).join('\n')}>{row.origins[0].label} <span className="rs-muted">{Number(row.origins[0].share).toLocaleString('pt-BR', {maximumFractionDigits: 0})}%</span></span> : '—'},
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
