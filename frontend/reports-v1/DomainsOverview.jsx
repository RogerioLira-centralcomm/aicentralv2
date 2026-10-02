import React, {useEffect, useMemo, useState} from 'react';
import {ArrowDown, ArrowUp, ArrowUpRight, Globe01} from '@untitledui/icons';
import {Empty, integer, json, reportUrl} from './reportsCommon.jsx';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsDateRange} from './ReportsDateRange.jsx';
import {PRESETS, formatDay, formatRange, friendlyAgo} from './friendlyDates.js';
import './domains-overview.css';

const dash = '—';
const percent = value => value == null ? dash : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const seconds = value => {
  if (value == null) return dash;
  const total = Math.round(value);
  return total >= 60 ? `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, '0')} s` : `${total} s`;
};
const initialRange = () => {
  const query = new URLSearchParams(location.search);
  const start = query.get('start_date'), end = query.get('end_date');
  if (/^\d{4}-\d{2}-\d{2}$/.test(start || '') && /^\d{4}-\d{2}-\d{2}$/.test(end || '')) return {start, end};
  const days = Number(query.get('days'));
  const preset = PRESETS.find(item => item.id === String(days)) || PRESETS[2];
  return preset.range();
};

/** Change chip: relative for counts, percentage points for rates. Nothing is drawn when there is no comparable period. */
function Delta({change, rate = false}) {
  if (!change || change.absolute == null) return <small className="do-delta is-none">Sem período anterior</small>;
  const value = rate ? change.absolute : change.relative;
  if (value == null) return <small className="do-delta is-none">Novo no período</small>;
  if (!value) return <small className="do-delta is-flat">Estável</small>;
  const up = value > 0;
  return <small className={`do-delta ${up ? 'is-up' : 'is-down'}`}>{up ? <ArrowUp size={12} aria-hidden="true"/> : <ArrowDown size={12} aria-hidden="true"/>}{Math.abs(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}{rate ? ' p.p.' : '%'}<span> vs. anterior</span></small>;
}

function Stat({label, value, hint, change, rate}) {
  return <article className="do-stat"><span>{label}</span><strong>{value}</strong>{hint && <em>{hint}</em>}<Delta change={change} rate={rate}/></article>;
}

function TrendChart({daily}) {
  const width = 640, height = 250, padLeft = 34, padBottom = 24, padTop = 10;
  const max = Math.max(1, ...daily.map(item => item.sessions));
  const step = (width - padLeft - 8) / Math.max(1, daily.length - 1);
  const x = index => padLeft + index * step;
  const y = value => padTop + (height - padTop - padBottom) * (1 - value / max);
  const line = daily.map((item, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(item.sessions).toFixed(1)}`).join(' ');
  const area = `${line} L${x(daily.length - 1).toFixed(1)},${height - padBottom} L${padLeft},${height - padBottom} Z`;
  const labelAt = [0, Math.floor((daily.length - 1) / 2), daily.length - 1].filter((value, index, all) => all.indexOf(value) === index);
  const gradientId = useMemo(() => `do-grad-${Math.random().toString(36).slice(2, 8)}`, []);
  const ticks = [0, 0.5, 1].map(ratio => Math.round(max * ratio));
  return <svg className="do-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sessões por dia no período">
    <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#175cd3" stopOpacity=".22"/><stop offset="100%" stopColor="#175cd3" stopOpacity="0"/></linearGradient></defs>
    {ticks.map((tick, index) => <g key={index}><line x1={padLeft} x2={width - 8} y1={y(tick)} y2={y(tick)} className="do-grid"/><text x={padLeft - 8} y={y(tick) + 4} textAnchor="end" className="do-axis">{integer(tick)}</text></g>)}
    <path d={area} fill={`url(#${gradientId})`}/><path d={line} className="do-line"/>
    {daily.map((item, index) => <g key={item.date}>
      {item.conversions > 0 && <circle cx={x(index)} cy={y(item.sessions)} r="4" className="do-conversion"/>}
      <rect x={x(index) - step / 2} y={padTop} width={Math.max(step, 4)} height={height - padTop - padBottom} fill="transparent"><title>{`${formatDay(item.date)}: ${integer(item.sessions)} sessões · ${integer(item.conversions)} conversões`}</title></rect>
    </g>)}
    {labelAt.map(index => <text key={index} x={x(index)} y={height - 6} textAnchor={index === 0 ? 'start' : index === daily.length - 1 ? 'end' : 'middle'} className="do-axis">{formatDay(daily[index].date).replace(/ \d{4}$/, '')}</text>)}
  </svg>;
}

function Bars({rows, empty}) {
  const total = rows.reduce((sum, row) => sum + row.sessions, 0);
  if (!rows.length) return <p className="do-muted">{empty}</p>;
  return <ul className="do-bars">{rows.map(row => <li key={row.key}>
    <span>{row.label}</span><b>{percent(100 * row.sessions / total)}</b>
    <div className="do-bar" role="img" aria-label={`${row.label}: ${integer(row.sessions)} sessões`}><i style={{width: `${Math.max(3, 100 * row.sessions / total)}%`}}/></div>
  </li>)}</ul>;
}

function DomainAvatar({host}) {
  const [failed, setFailed] = useState(false);
  return <span className="do-avatar">{failed ? <Globe01 size={20} aria-hidden="true"/> : <img src={`https://${host}/favicon.ico`} alt="" onError={() => setFailed(true)}/>}</span>;
}

function DomainCard({domain, range}) {
  const {metrics: m, change = {}} = domain;
  const empty = !m.sessions && !m.views;
  const maxViews = Math.max(1, ...domain.top_pages.map(page => page.views));
  const link = path => reportUrl('pages', {site_id: domain.site_id, path, start_date: range.start, end_date: range.end});
  return <section className="do-domain" id={`dominio-${domain.site_id}`} aria-labelledby={`dominio-titulo-${domain.site_id}`}>
    <header className="do-domain__head">
      <DomainAvatar host={domain.host}/>
      <div><h2 id={`dominio-titulo-${domain.site_id}`}>{domain.host}</h2><p>{domain.label}{domain.last_event_at ? ` · último evento ${friendlyAgo(domain.last_event_at)}` : ' · sem eventos ainda'}</p></div>
      <ReportsActionButton color="secondary" iconTrailing={ArrowUpRight} href={reportUrl('supertag', {}, domain.site_id)}>Instalação</ReportsActionButton>
    </header>
    {empty ? <div className="do-empty"><strong>Sem visitas neste período</strong><p>Os números aparecem quando a Super Tag receber eventos consentidos neste domínio. Tente um período maior ou confira a instalação.</p></div> : <>
      <div className="do-stats">
        <Stat label="Sessões" value={integer(m.sessions)} change={change.sessions}/>
        <Stat label="Visitantes únicos" value={integer(m.visitors)} change={change.visitors}/>
        <Stat label="Visualizações" value={integer(m.views)} change={change.views}/>
        <Stat label="Conversões" value={integer(m.conversions)} hint={m.conversion_rate != null ? `${percent(m.conversion_rate)} das sessões` : null} change={change.conversions}/>
        <Stat label="Tempo ativo médio" value={seconds(m.avg_active_seconds)} change={change.avg_active_seconds}/>
      </div>
      <div className="do-grid2">
        <article className="do-card"><header><h3>Sessões por dia</h3><span><i className="do-key"/>Dia com conversão</span></header><TrendChart daily={domain.daily}/></article>
        <article className="do-card"><header><h3>Origem do tráfego</h3></header><Bars rows={domain.sources.map(item => ({key: item.platform, label: item.label, sessions: item.sessions}))} empty="Origem ainda não identificada."/>
          <header className="do-card__sub"><h3>Dispositivos</h3></header><Bars rows={domain.devices.map(item => ({key: item.device, label: item.label, sessions: item.sessions}))} empty="Sem dados de dispositivo."/></article>
      </div>
      <article className="do-card"><header><h3>Páginas mais vistas</h3><span>Abra uma página para ver cliques, rolagem e origem</span></header>
        {domain.top_pages.length ? <div className="do-table-wrap"><table className="cadu-table"><thead><tr><th>Página</th><th>Visualizações</th><th>Sessões</th><th>Conversões</th><th>Tempo ativo</th></tr></thead><tbody>
          {domain.top_pages.map(page => <tr key={page.path}><td><a href={link(page.path)}>{page.path}</a></td>
            <td><span className="do-inline-bar"><i style={{width: `${Math.max(4, 100 * page.views / maxViews)}%`}}/><b>{integer(page.views)}</b></span></td>
            <td>{integer(page.sessions)}</td><td>{integer(page.conversions)}</td><td>{seconds(page.avg_active_seconds)}</td></tr>)}</tbody></table></div> : <p className="do-muted">Nenhuma página vista no período.</p>}
      </article>
    </>}
  </section>;
}

/** Overview of Páginas: one block per monitored domain, built the way an analytics home reads. */
export function DomainsOverview({data, range: controlledRange, onRangeChange}) {
  // Inside Site & Jornada the period comes from the header; standalone, the block keeps its own picker.
  const [ownRange, setOwnRange] = useState(initialRange);
  const controlled = Boolean(controlledRange);
  const range = controlledRange || ownRange;
  const setRange = onRangeChange || setOwnRange;
  const [state, setState] = useState({loading: true, error: '', body: null});
  const client = data.client.client_id;
  useEffect(() => {
    let active = true;
    setState(current => ({...current, loading: true, error: ''}));
    json(`/connect/api/v2/reports/pages/domains?${new URLSearchParams({start_date: range.start, end_date: range.end})}`)
      .then(body => {if (active) setState({loading: false, error: '', body});})
      .catch(failure => {if (active) setState({loading: false, error: failure.message, body: null});});
    if (!controlled) {
      const url = new URL(location.href);
      url.searchParams.delete('days'); url.searchParams.set('start_date', range.start); url.searchParams.set('end_date', range.end);
      history.replaceState(null, '', `${url.pathname}${url.search}`);
    }
    return () => {active = false;};
  }, [client, range.start, range.end, controlled]);
  const domains = state.body?.domains || [];
  return <div className="do-page">
    <div className="do-toolbar">
      <div><h2>Resumo por domínio</h2><p>{domains.length ? `${domains.length} ${domains.length === 1 ? 'domínio monitorado' : 'domínios monitorados'} · ${formatRange(range.start, range.end)}` : 'Visitas, origem e páginas de cada site com a Super Tag.'}</p></div>
      <div className="do-toolbar__side">
        {domains.length > 1 && <nav className="do-jump" aria-label="Ir para o domínio">{domains.map(domain => <a key={domain.site_id} href={`#dominio-${domain.site_id}`}>{domain.host}</a>)}</nav>}
        {!controlled && <ReportsDateRange value={range} onChange={setRange}/>}
      </div>
    </div>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && !state.body && <div className="reports-loading" role="status">Carregando domínios…</div>}
    {state.body && !domains.length && <div className="do-empty do-empty--page"><strong>Nenhum domínio monitorado</strong><p>Conecte um site pela Super Tag para acompanhar as páginas aqui.</p><ReportsActionButton color="primary" href={reportUrl('supertag')}>Conectar site</ReportsActionButton></div>}
    {domains.map(domain => <DomainCard key={domain.site_id} domain={domain} range={range}/>)}
    {state.body && state.body.previous_available === false && domains.length > 0 && <p className="do-muted do-foot">A comparação com o período anterior depende dos 90 dias de retenção dos eventos.</p>}
  </div>;
}
