import React, {useMemo} from 'react';
import {sankeyLayout} from '../../sankeyLayout.js';
import {ArrowRight} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {customerParam} from '../../shell/customerScope.js';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';
import {OriginPicker, useOrigin} from './origin.jsx';
import './journey.css';

/** Short definitions shown as header tooltips and, for keyboard and screen readers, in "Como ler estas métricas". */
const HINTS = {
  entries: 'Sessões que começaram nesta página.',
  exits: 'Sessões que terminaram nesta página (última página vista).',
  exit_rate: 'Saídas ÷ visualizações da página.',
  bounce_rate: 'Das sessões que entraram aqui, quantas não viram outra página.',
  conversion_rate: 'Das sessões que passaram pela página (ou fizeram o caminho), quantas converteram na mesma sessão.',
  avg_active: 'Tempo médio com a aba visível e ativa, medido na saída da página.',
  path: 'Sequência das primeiras páginas da sessão; recarregar a mesma página conta uma vez.',
  share: 'Parte das sessões do período (na origem escolhida).',
  leak: 'Taxa de saída acima da média do site e conversão abaixo da metade da média.',
};

const term = (label, hint) => <span className="rs-term" title={hint}>{label}</span>;
const seconds = value => value == null ? '—' : value < 60 ? `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 0})} s` : `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
/** A rate with too small a base comes back as null: show a dash that says why instead of a misleading percentage. */
const rate = (value, base, minimum) => value == null
  ? <span className="rs-muted rs-nav__dash" title={`Base pequena (${number(base)}); a taxa aparece a partir de ${minimum}.`}>—</span>
  : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const ratio = (part, total, minimum) => Number(total) >= minimum ? percent(part, total) : '—';

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
    aria-label={`Os ${Math.min(10, paths.length)} passos mais comuns entre páginas`}>
    <g className="page-detail-sankey-links">{map.links.map(link => <path key={`${link.source}>${link.target}`} d={link.path} strokeWidth={Math.max(1, link.width)}>
      <title>{`${label(link.source)} → ${label(link.target)}: ${number(link.value)} sessões (${percent(link.value, sessions)})`}</title></path>)}</g>
    <g>{map.nodes.map(node => <g key={node.id}><rect x={node.x} y={node.y} width={node.w} height={Math.max(2, node.h)} rx="3"/>
      <text x={node.column === 0 ? node.x - 8 : node.x + node.w + 8} y={node.y + Math.max(2, node.h) / 2} dy="0.35em" textAnchor={node.column === 0 ? 'end' : 'start'}>
        <tspan>{node.label.length > 34 ? `${node.label.slice(0, 33)}…` : node.label}</tspan><tspan className="page-detail-sankey-count" dx="6">{number(node.value)}</tspan></text></g>)}</g>
  </svg></div>;
}

const pageLink = (row, path = row.path) => <AppLink className="rs-path" href={reportUrl('pages', {site_id: row.site_id, path})}>{path}</AppLink>;

/** "Como os usuários se movimentam?" — where visits start, move next and leave, by origin. Modelling stays in Fluxos. */
export function Navigation() {
  const {period, scope} = useReportsContext();
  const [origin, setOrigin] = useOrigin();
  const [state, retry] = useApi(apiUrl('/journey/navigation', {start_date: period.start, end_date: period.end, site_id: scope.site, customer_id: customerParam(), origin: origin || undefined}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const body = state.body;
  const groups = body?.origin_groups || [];
  const allSessions = groups.reduce((sum, item) => sum + item.sessions, 0);
  if (!body || !allSessions) return <EmptyState title="Sem navegação no período" description="Os caminhos aparecem quando a Super Tag recebe visitas com mais de uma página."/>;
  const {totals, quality, changes} = body;
  const minimum = quality.rate_min_base;
  const sessions = Number(totals.sessions || 0);
  const chosen = groups.find(item => item.origin === origin);
  const entries = body.pages.filter(row => row.entries > 0).sort((a, b) => b.entries - a.entries);
  const exits = body.pages.filter(row => row.exits > 0).sort((a, b) => b.exits - a.exits || b.exit_rate - a.exit_rate);
  const leaks = exits.filter(row => row.leak);
  const siteOf = Object.fromEntries(body.pages.map(page => [`${page.host}${page.path}`, page.site_id]));
  const pathRow = row => ({...row, site_id: siteOf[`${row.host}${row.from_path}`] || siteOf[`${row.host}${row.to_path}`]});
  const previous = body.previous;
  const compared = changes ? 'vs período anterior' : previous ? `Anterior: ${number(previous.sessions)} sessões · base pequena para comparar` : undefined;
  return <div className="rs-stack rs-nav">
    <div className="rs-nav__bar">
      <OriginPicker groups={groups} value={origin} onChange={setOrigin} total={allSessions}/>
      {chosen && <p className="rs-nav__hint">{chosen.hint}</p>}
    </div>
    {quality.low_sample && <p className="rs-nav__note" role="status">Amostra pequena: {number(sessions)} {sessions === 1 ? 'sessão' : 'sessões'}{chosen ? ` em ${chosen.label}` : ''} (o recomendado é a partir de {quality.min_sessions}). Leia as taxas como indício; abaixo de {minimum} visitas elas não aparecem.</p>}
    {sessions === 0 ? <EmptyState title={`Nenhuma sessão de ${chosen?.label || 'esta origem'} no período`} description="Escolha outra origem ou um período maior."/> : <>
    <MetricGroup label="Resumo da navegação" items={[
      {label: 'Sessões', value: number(sessions), change: changes?.sessions, detail: compared},
      {label: 'Páginas por sessão', value: (Number(totals.views) / sessions).toLocaleString('pt-BR', {maximumFractionDigits: 1}), change: changes?.views_per_session},
      {label: 'Sessões de uma página', value: ratio(totals.single_page_sessions, sessions, minimum), change: changes?.single_page_rate, inverse: true, detail: 'Saíram sem ver outra página'},
      {label: 'Sessões que converteram', value: ratio(totals.converted_sessions, sessions, minimum), change: changes?.conversion_rate, detail: `${number(totals.converted_sessions)} de ${number(sessions)}`},
    ]}/>
    <div className="rs-grid rs-grid--3 rs-nav__grid">
      <Section title="Origem das sessões" description="Primeira página vista em cada sessão">
        <ul className="rs-bars rs-nav__bars">{groups.filter(item => item.sessions > 0 || ['direct', 'unknown'].includes(item.origin)).map(item => <li key={item.origin} className={item.origin === origin ? 'is-active' : undefined}>
          <button type="button" className="rs-nav__bar-label" title={item.hint} aria-pressed={item.origin === origin} onClick={() => setOrigin(item.origin === origin ? '' : item.origin)}>{item.label}</button>
          <i><b style={{width: `${Math.max(item.sessions ? 2 : 0, item.sessions * 100 / (allSessions || 1))}%`}}/></i>
          <strong title={item.conversion_rate == null ? undefined : `${item.conversion_rate.toLocaleString('pt-BR')}% converteram`}>{number(item.sessions)}</strong>
        </li>)}</ul>
      </Section>
      <Section title="Por onde entram" description="Primeira página da sessão">
        <DataTable label="Entradas" limit={8} rows={entries} rowKey={row => row.host + row.path} empty={<p className="rs-muted">Sem entradas.</p>} columns={[
          {key: 'path', label: 'Página', render: row => pageLink(row)},
          {key: 'entries', label: term('Entradas', HINTS.entries), numeric: true, render: row => number(row.entries)},
          {key: 'bounce_rate', label: term('Rejeição', HINTS.bounce_rate), numeric: true, sort: row => row.bounce_rate ?? -1, render: row => rate(row.bounce_rate, row.entries, minimum)},
        ]}/>
      </Section>
      <Section title="Próximo passo" description="Página seguinte na mesma sessão">
        <DataTable label="Próximo passo" limit={8} rows={body.paths.map(pathRow)} rowKey={row => `${row.host}${row.from_path}>${row.to_path}`}
          empty={<p className="rs-muted">Nenhuma sessão passou por mais de uma página.</p>} columns={[
            {key: 'from_path', label: 'De → para', render: row => <span className="rs-nav__pair">{pageLink(row, row.from_path)}<span className="rs-step"><ArrowRight size={14} aria-hidden="true"/><span className="sr-only">para</span>{pageLink(row, row.to_path)}</span></span>},
            {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
          ]}/>
      </Section>
    </div>
    <Section title="Onde saem" description={leaks.length ? `${leaks.length} ${leaks.length === 1 ? 'página perde' : 'páginas perdem'} muitas visitas e ${leaks.length === 1 ? 'converte' : 'convertem'} pouco` : 'Páginas ordenadas pelo número de saídas'}>
      <DataTable label="Saídas por página" limit={15} rows={exits} rowKey={row => row.host + row.path} initialSort={{key: 'exits', dir: 'desc'}}
        empty={<p className="rs-muted">Sem saídas registradas.</p>} columns={[
          {key: 'path', label: 'Página', render: row => <span className="rs-nav__page">{pageLink(row)}{row.leak && <span className="rs-nav__flag" title={HINTS.leak}>Sai muito · converte pouco</span>}</span>},
          {key: 'entries', label: term('Entradas', HINTS.entries), numeric: true, render: row => number(row.entries)},
          {key: 'exits', label: term('Saídas', HINTS.exits), numeric: true, render: row => number(row.exits)},
          {key: 'exit_rate', label: term('Taxa de saída', HINTS.exit_rate), numeric: true, sort: row => row.small_base ? -1 : row.exit_rate, render: row => rate(row.small_base ? null : row.exit_rate, row.views, minimum)},
          {key: 'bounce_rate', label: term('Rejeição na entrada', HINTS.bounce_rate), numeric: true, sort: row => row.bounce_rate ?? -1, render: row => rate(row.bounce_rate, row.entries, minimum)},
          {key: 'conversion_rate', label: term('Conversão', HINTS.conversion_rate), numeric: true, sort: row => row.conversion_rate ?? -1, render: row => rate(row.conversion_rate, row.sessions, minimum)},
          {key: 'avg_active_seconds', label: term('Tempo ativo', HINTS.avg_active), numeric: true, sort: row => Number(row.avg_active_seconds ?? -1), render: row => seconds(row.avg_active_seconds)},
        ]}/>
    </Section>
    <Section title="Caminhos completos" description={`Sequências de 2 a 5 páginas por sessão${chosen ? ` · ${chosen.label}` : ''}`}
      action={<AppLink className="rs-link" href={reportUrl('flows')}>Ver Fluxos<ArrowRight size={14} aria-hidden="true"/></AppLink>}>
      <DataTable label="Caminhos completos" rows={body.sequences} rowKey={row => `${row.site_id}:${row.pages.join('>')}`}
        empty={<p className="rs-muted">Nenhuma sessão passou por duas páginas diferentes.</p>} columns={[
          {key: 'pages', label: term('Caminho', HINTS.path), sortable: false, render: row => <ol className="rs-nav__path" aria-label={`Caminho: ${row.pages.join(', depois ')}`}>
            {row.pages.map((path, index) => <li key={`${index}${path}`}>{index > 0 && <ArrowRight size={12} aria-hidden="true"/>}<span className="rs-path" title={`${row.host}${path}`}>{path}</span></li>)}
            {row.continued > 0 && <li className="rs-nav__more" title={`${number(row.continued)} ${row.continued === 1 ? 'sessão seguiu' : 'sessões seguiram'} para mais páginas`}>+</li>}
          </ol>},
          {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
          {key: 'share', label: term('Das sessões', HINTS.share), numeric: true, sort: row => row.sessions, render: row => rate(sessions >= minimum ? row.share : null, sessions, minimum)},
          {key: 'conversion_rate', label: term('Conversão', HINTS.conversion_rate), numeric: true, sort: row => row.conversion_rate ?? -1,
            render: row => row.conversion_rate == null ? <span title={`${number(row.converted_sessions)} de ${number(row.sessions)} converteram; base pequena para taxa`}>{number(row.converted_sessions)}<span className="rs-muted"> de {number(row.sessions)}</span></span> : rate(row.conversion_rate, row.sessions, minimum)},
          {key: 'flow', label: <span className="sr-only">Ação</span>, sortable: false, render: row => <AppLink className="rs-link" href={reportUrl('flows', {site_host: row.host, caminho: JSON.stringify(row.pages)})}>Criar fluxo<span className="sr-only"> a partir deste caminho</span></AppLink>},
        ]}/>
    </Section>
    {body.paths.length > 1 && <Section title="Mapa de passos" description="Os 10 passos entre páginas mais comuns"><PathsSankey paths={body.paths} sessions={sessions}/></Section>}
    </>}
    <details className="rs-nav__defs">
      <summary>Como ler estas métricas</summary>
      <dl>
        <dt>Entradas</dt><dd>{HINTS.entries}</dd>
        <dt>Saídas e taxa de saída</dt><dd>{HINTS.exits} {HINTS.exit_rate}</dd>
        <dt>Rejeição na entrada</dt><dd>{HINTS.bounce_rate}</dd>
        <dt>Conversão</dt><dd>{HINTS.conversion_rate}</dd>
        <dt>Tempo ativo</dt><dd>{HINTS.avg_active}</dd>
        <dt>Caminho</dt><dd>{HINTS.path} Sessões que foram além de 5 páginas aparecem com “+”.</dd>
        <dt>Sai muito · converte pouco</dt><dd>{HINTS.leak}</dd>
        <dt>Bases pequenas</dt><dd>Taxas só aparecem com pelo menos {minimum} visualizações, entradas ou sessões; abaixo de {quality.min_sessions} sessões no total a aba avisa que a amostra é pequena. A comparação usa o período anterior de mesma duração e só aparece quando os dois têm amostra suficiente.</dd>
        {groups.map(item => <React.Fragment key={item.origin}><dt>{item.label}</dt><dd>{item.hint}</dd></React.Fragment>)}
      </dl>
    </details>
  </div>;
}
