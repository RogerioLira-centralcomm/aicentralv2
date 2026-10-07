import React from 'react';
import {ArrowRight} from '@untitledui/icons';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {customerParam} from '../../shell/customerScope.js';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';
import {TechPanel} from './TechPanel.jsx';
import './journey.css';

const pct = (value, digits = 1) => `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: digits})}%`;
/** A rate that came back null has too small a base: say so instead of showing a misleading percentage. */
const rate = (value, base, minimum) => value == null
  ? <span className="rs-muted" title={`Base pequena (${number(base)}); a taxa aparece a partir de ${minimum}.`}>—</span> : pct(value);

/** Credit of the conversions by origin: who opened the visitor's path, who closed it and who helped in between. */
function Attribution({state}) {
  const data = state.body?.attribution;
  if (state.error || !data) return null;
  const rows = data.channels;
  return <Section title="Atribuição das conversões" description={data.conversions ? `${number(data.conversions)} ${data.conversions === 1 ? 'sessão converteu' : 'sessões converteram'} · primeiro toque, último toque e assistências por canal` : 'Primeiro toque, último toque e assistências por canal'}>
    {rows.length ? <>
      <DataTable label="Atribuição" rows={rows} rowKey={row => row.origin} initialSort={{key: 'last_touch', dir: 'desc'}} columns={[
        {key: 'label', label: 'Canal', sort: row => row.label},
        {key: 'first_touch', label: <span title="Origem da primeira visita do usuário no período.">Primeiro toque</span>, numeric: true, render: row => <>{number(row.first_touch)}{row.first_touch > 0 && <span className="rs-muted"> · {pct(row.first_share, 0)}</span>}</>},
        {key: 'last_touch', label: <span title="Última visita que não foi Direto nem Origem desconhecida; se todas foram diretas, a origem da própria visita.">Último toque</span>, numeric: true, render: row => <>{number(row.last_touch)}{row.last_touch > 0 && <span className="rs-muted"> · {pct(row.last_share, 0)}</span>}</>},
        {key: 'assisted', label: <span title="O canal apareceu no caminho do usuário, mas não abriu nem fechou a conversão.">Assistências</span>, numeric: true, render: row => number(row.assisted)},
      ]}/>
      <p className="rs-muted rs-chan__more">Usuários sem identificador contam como uma só visita. Visitas anteriores ao início do período não aparecem, então caminhos longos são cortados ali.</p>
    </> : <p className="rs-muted">Nenhuma conversão no período para atribuir.</p>}
  </Section>;
}

/** Google Ads spend (synced campaign metrics) against the site sessions that came from it. */
function AdsCost({state}) {
  const cost = state.body?.cost;
  if (state.error || !cost || (!cost.spend && !cost.clicks && !cost.mixed_currencies)) return null;
  const money = value => value == null ? '—' : Number(value).toLocaleString('pt-BR', {style: 'currency', currency: cost.currency || 'BRL'});
  return <Section title="Custo do Google Ads" description={cost.scope === 'customer' ? 'Investimento das campanhas do cliente deste site contra as sessões do Google Ads em todos os sites do cliente' : 'Investimento de todas as contas Google Ads contra as sessões que chegaram do Google Ads; escolha um site com cliente para separar'}>
    <MetricGroup label="Custo do Google Ads" items={[
      {label: 'Investimento', value: cost.mixed_currencies ? 'Moedas mistas' : money(cost.spend), detail: `${number(cost.clicks)} cliques`},
      {label: 'Custo por clique', value: money(cost.cost_per_click)},
      {label: 'Custo por sessão', value: money(cost.cost_per_session), detail: `${number(cost.sessions)} sessões do Google Ads no site`},
      {label: 'Custo por sessão convertida', value: money(cost.cost_per_converted_session), detail: cost.converted_sessions ? `${number(cost.converted_sessions)} convertidas` : 'Sem conversões vindas do Google Ads'},
    ]}/>
    {cost.sessions_per_click != null && <p className="rs-muted rs-chan__more">Sessões por clique: {cost.sessions_per_click.toLocaleString('pt-BR')}. Bem abaixo de 1 indica cliques que não chegam ao site com a Super Tag ou sem marcação de campanha.</p>}
  </Section>;
}

/** "De onde vêm as visitas?" — every origin group with volume, conversion, devices, campaigns and the pages people land on. */
export function Channels() {
  const {period, scope} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/channels', {start_date: period.start, end_date: period.end, site_id: scope.site || undefined, customer_id: customerParam()}));
  const [attribution] = useApi(apiUrl('/journey/attribution', {start_date: period.start, end_date: period.end, site_id: scope.site || undefined, customer_id: customerParam()}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const {channels, totals, quality, tech} = state.body;
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
        {key: 'sessions_change', label: <span title="Sessões contra o período anterior de mesma duração; só aparece com base suficiente nos dois períodos.">Variação</span>, numeric: true, sort: row => row.sessions_change ?? -1e9,
          render: row => row.sessions_change == null ? <span className="rs-muted" title={`Período anterior: ${number(row.previous_sessions)} sessões`}>—</span>
            : <span className={row.sessions_change >= 0 ? 'rs-chan__up' : 'rs-chan__down'} title={`Antes: ${number(row.previous_sessions)} sessões${row.conversion_rate_change == null ? '' : ` · conversão ${row.conversion_rate_change > 0 ? '+' : ''}${row.conversion_rate_change.toLocaleString('pt-BR')} p.p.`}`}>{row.sessions_change > 0 ? '+' : ''}{pct(row.sessions_change, 0)}</span>},
        {key: 'views_per_session', label: 'Páginas por sessão', numeric: true, sort: row => row.views_per_session ?? -1, render: row => row.views_per_session == null ? '—' : row.views_per_session.toLocaleString('pt-BR')},
        {key: 'single_page_rate', label: 'Sessões de uma página', numeric: true, sort: row => row.single_page_rate ?? -1, render: row => rate(row.single_page_rate, row.sessions, minimum)},
        {key: 'conversion_rate', label: 'Conversão', numeric: true, sort: row => row.conversion_rate ?? -1, render: row => row.conversion_rate == null && row.converted_sessions
          ? <span title="Base pequena para taxa">{number(row.converted_sessions)}<span className="rs-muted"> de {number(row.sessions)}</span></span> : rate(row.conversion_rate, row.sessions, minimum)},
        {key: 'open', label: <span className="sr-only">Ações</span>, sortable: false, render: row => row.sessions > 0 && <span className="rs-chan__actions">
          <AppLink className="rs-link" href={reportUrl('journey/pages', {origem: row.origin})}>Páginas<span className="sr-only"> de {row.label}</span></AppLink>
          <AppLink className="rs-link" href={reportUrl('journey/navigation', {origem: row.origin})}>Caminhos<span className="sr-only"> de {row.label}</span></AppLink></span>},
      ]}/>
    </Section>
    <div className="rs-stack">
      <Section title="Como ler" description="O que cada canal agrupa">
        <dl className="rs-chan__defs">{active.map(item => <React.Fragment key={item.origin}><dt>{item.label}</dt><dd>{item.hint}</dd></React.Fragment>)}</dl>
      </Section>
    </div>
    <AdsCost state={attribution}/>
    <Attribution state={attribution}/>
    <TechPanel tech={tech} devices={devices} minimum={minimum}/>
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
