import React from 'react';
import {ArrowRight} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';
import './journey.css';

const DEVICE_LABELS = {mobile: 'Celular', tablet: 'Tablet', desktop: 'Computador', unknown: 'Não identificado'};
const pct = (value, digits = 1) => `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: digits})}%`;
/** A rate that came back null has too small a base: say so instead of showing a misleading percentage. */
const rate = (value, base, minimum) => value == null
  ? <span className="rs-muted" title={`Base pequena (${number(base)}); a taxa aparece a partir de ${minimum}.`}>—</span> : pct(value);

/** "De onde vêm as visitas?" — every origin group with volume, conversion, devices, campaigns and the pages people land on. */
export function Channels() {
  const {period, scope} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/channels', {start_date: period.start, end_date: period.end, site_id: scope.site || undefined}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const {channels, totals, quality} = state.body;
  if (!totals.sessions) return <EmptyState title="Sem visitas no período" description="Os canais aparecem quando a Super Tag recebe visitas. Confira a instalação ou escolha outro período."/>;
  const minimum = quality.rate_min_base;
  const active = channels.filter(item => item.sessions > 0);
  const top = active[0] && [...active].sort((a, b) => b.sessions - a.sessions)[0];
  const best = [...active].filter(item => item.conversion_rate != null && item.converted_sessions > 0).sort((a, b) => b.conversion_rate - a.conversion_rate)[0];
  const devices = ['mobile', 'tablet', 'desktop', 'unknown'].map(device => ({device, sessions: channels.reduce((sum, item) => sum + (item.devices.find(line => line.device === device)?.sessions || 0), 0)})).filter(item => item.sessions > 0);
  return <div className="rs-stack rs-chan">
    {quality.low_sample && <p className="rs-nav__note" role="status">Amostra pequena: {number(totals.sessions)} {totals.sessions === 1 ? 'sessão' : 'sessões'} (o recomendado é a partir de {quality.min_sessions}). Leia as taxas como indício; abaixo de {minimum} sessões elas não aparecem.</p>}
    <MetricGroup label="Resumo dos canais" items={[
      {label: 'Sessões', value: number(totals.sessions), detail: `${active.length} ${active.length === 1 ? 'canal ativo' : 'canais ativos'}`},
      {label: 'Canal principal', value: top ? top.label : '—', detail: top ? `${pct(top.share, 0)} das sessões` : undefined},
      {label: 'Melhor conversão', value: best ? best.label : '—', detail: best ? `${pct(best.conversion_rate)} das sessões converteram` : 'Sem conversões com base suficiente'},
      {label: 'Sessões que converteram', value: totals.conversion_rate == null ? '—' : pct(totals.conversion_rate), detail: `${number(totals.converted_sessions)} de ${number(totals.sessions)}`},
    ]}/>
    <Section title="Canais de origem" description="Origem da primeira página vista em cada sessão">
      <DataTable label="Canais de origem" rows={channels.filter(item => item.sessions > 0 || ['direct', 'unknown'].includes(item.origin))} rowKey={row => row.origin} initialSort={{key: 'sessions', dir: 'desc'}} columns={[
        {key: 'label', label: 'Canal', sort: row => row.label, render: row => <span title={row.hint}>{row.label}</span>},
        {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
        {key: 'share', label: 'Participação', render: row => <span className="rs-share"><i><b style={{width: `${Math.max(row.sessions ? 2 : 0, row.share)}%`}}/></i><span>{pct(row.share, 0)}</span></span>},
        {key: 'views_per_session', label: 'Páginas por sessão', numeric: true, sort: row => row.views_per_session ?? -1, render: row => row.views_per_session == null ? '—' : row.views_per_session.toLocaleString('pt-BR')},
        {key: 'single_page_rate', label: 'Sessões de uma página', numeric: true, sort: row => row.single_page_rate ?? -1, render: row => rate(row.single_page_rate, row.sessions, minimum)},
        {key: 'conversion_rate', label: 'Conversão', numeric: true, sort: row => row.conversion_rate ?? -1, render: row => row.conversion_rate == null && row.converted_sessions
          ? <span title="Base pequena para taxa">{number(row.converted_sessions)}<span className="rs-muted"> de {number(row.sessions)}</span></span> : rate(row.conversion_rate, row.sessions, minimum)},
        {key: 'open', label: <span className="sr-only">Ações</span>, sortable: false, render: row => row.sessions > 0 && <span className="rs-chan__actions">
          <AppLink className="rs-link" href={reportUrl('journey/pages', {origem: row.origin})}>Páginas<span className="sr-only"> de {row.label}</span></AppLink>
          <AppLink className="rs-link" href={reportUrl('journey/navigation', {origem: row.origin})}>Caminhos<span className="sr-only"> de {row.label}</span></AppLink></span>},
      ]}/>
    </Section>
    <div className="rs-grid rs-grid--2">
      <Section title="Dispositivos" description="Tipo de aparelho pela largura da tela na primeira página da sessão">
        <ul className="rs-bars">{devices.map(item => <li key={item.device}><span>{DEVICE_LABELS[item.device]}</span><i><b style={{width: `${Math.max(2, item.sessions * 100 / totals.sessions)}%`}}/></i><strong>{percent(item.sessions, totals.sessions)}</strong></li>)}</ul>
      </Section>
      <Section title="Como ler" description="O que cada canal agrupa">
        <dl className="rs-chan__defs">{active.map(item => <React.Fragment key={item.origin}><dt>{item.label}</dt><dd>{item.hint}</dd></React.Fragment>)}</dl>
      </Section>
    </div>
    <Section title="Detalhe por canal" description="Aparelhos, campanhas e páginas de entrada de cada origem">
      <div className="rs-chan__cards">{active.map(item => <article key={item.origin} className="rs-chan__card" aria-label={item.label}>
        <header><strong>{item.label}</strong><span>{number(item.sessions)} {item.sessions === 1 ? 'sessão' : 'sessões'}</span></header>
        <h3>Aparelhos</h3>
        <ul className="rs-chan__list">{item.devices.map(line => <li key={line.device}><span>{line.label}</span><strong>{pct(line.share, 0)}</strong></li>)}</ul>
        <h3>Campanhas (utm_campaign)</h3>
        {item.campaigns.length ? <ul className="rs-chan__list">{item.campaigns.map(line => <li key={line.name}><span title={line.name}>{line.name}</span><strong>{number(line.sessions)}</strong></li>)}</ul>
          : <p className="rs-muted">Sem campanha identificada.</p>}
        <h3>Principais entradas</h3>
        <ul className="rs-chan__list">{item.landings.map(line => <li key={`${line.site_id}${line.path}`}><AppLink className="rs-path" href={reportUrl('pages', {site_id: line.site_id, path: line.path})}>{line.path}</AppLink><strong>{number(line.sessions)}</strong></li>)}</ul>
      </article>)}</div>
    </Section>
    <p className="rs-muted rs-chan__more">Quer ver o caminho que cada canal percorre? <AppLink className="rs-link" href={reportUrl('journey/navigation')}>Abrir Navegação<ArrowRight size={14} aria-hidden="true"/></AppLink></p>
  </div>;
}
