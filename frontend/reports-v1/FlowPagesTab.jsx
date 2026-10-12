import React, {useMemo, useState} from 'react';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {reportUrl} from './reportsCommon.jsx';
import './flow-pages.css';

export const GRADE_LABELS = {good: 'Bom uso', attention: 'Atenção', critical: 'Crítico'};
const COMPONENT_LABELS = {time: 'Tempo ativo', scroll: 'Rolagem', advance: 'Avanço', exit: 'Permanência no site'};
const COMPONENT_SHORT = {time: 'Tempo', scroll: 'Rolagem', advance: 'Avanço', exit: 'Ficou'};
const TYPE_LABELS = {page: 'Página', form: 'Formulário', conversion: 'Conversão', error: 'Erro'};
const number = value => value == null ? '—' : Number(value).toLocaleString('pt-BR');
const percent = value => value == null ? '—' : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const seconds = value => {
  if (value == null) return '—';
  const total = Math.round(value);
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}min ${String(total % 60).padStart(2, '0')}s`;
};

/** The usage score as a pill; without a score it says why. */
export function UsageScore({row, compact = false}) {
  if (row.score == null) {
    const why = row.status === 'idle' ? 'Sem tráfego' : row.type === 'conversion' ? 'Etapa final' : row.small_sample ? 'Amostra pequena' : row.status === 'external' ? 'Outro domínio' : row.status === 'no_address' ? 'Sem endereço' : 'Sem nota';
    return <span className="flow-usage-score is-empty" title={row.small_sample ? 'Menos sessões que o mínimo para dar nota' : undefined}>{why}</span>;
  }
  const parts = Object.entries(row.components || {}).map(([key, value]) => `${COMPONENT_LABELS[key]}: ${value}`).join(' · ');
  return <span className={`flow-usage-score is-${row.grade}`} title={`Nota de uso ${row.score}/100 · ${parts}`}><b>{row.score}</b>{!compact && <span>{GRADE_LABELS[row.grade]}</span>}</span>;
}

function Components({row}) {
  const entries = Object.entries(row.components || {});
  if (!entries.length) return null;
  return <div className="flow-pages__components" aria-label="Composição da nota">{entries.map(([key, value]) =>
    <span key={key} title={`${COMPONENT_LABELS[key]}: ${value}/100`}><i><em style={{width: `${value}%`}}/></i><small>{COMPONENT_SHORT[key]} {value}</small></span>)}</div>;
}

const ORDERS = {score: 'Pior nota primeiro', sessions: 'Mais sessões', flow: 'Ordem do fluxo'};

/**
 * Pages of the flow for whoever manages the site: how each page is used (score from active time, scroll, moving on
 * and leaving) and which pages get no traffic at all, in the flow and in the sitemap.
 */
export function FlowPagesTab({state, days, onDaysChange, onRetry, onSelectNode}) {
  const [view, setView] = useState('usage');
  const [order, setOrder] = useState('score');
  const [query, setQuery] = useState('');
  const data = state.data;
  const rows = useMemo(() => {
    const list = (data?.pages || []).filter(row => row.status === 'measured');
    if (order === 'flow') return list;
    if (order === 'sessions') return [...list].sort((a, b) => (b.sessions || 0) - (a.sessions || 0));
    return [...list].sort((a, b) => (a.score ?? 101) - (b.score ?? 101) || (b.sessions || 0) - (a.sessions || 0));
  }, [data, order]);
  const scored = rows.filter(row => row.score != null);
  const average = scored.length ? Math.round(scored.reduce((sum, row) => sum + row.score * row.sessions, 0) / scored.reduce((sum, row) => sum + row.sessions, 0)) : null;
  const attention = scored.filter(row => row.grade !== 'good');
  const idleFlow = data?.idle?.flow || [];
  const idleSite = (data?.idle?.site || []).filter(page => `${page.title || ''} ${page.name || ''} ${page.path}`.toLowerCase().includes(query.trim().toLowerCase()));
  const pending = (data?.pages || []).filter(row => ['external', 'no_address'].includes(row.status));
  const pageLink = path => data?.site_id ? reportUrl('pages', {site_id: data.site_id, path, days}) : null;

  return <section className="flow-review flow-pages" aria-label="Páginas do fluxo">
    <header className="flow-pages__head">
      <div><h2>Páginas</h2><p>Como as páginas do fluxo são usadas e quais não recebem visitas. Dados da Super Tag do site{data?.host ? ` ${data.host}` : ''}, iguais aos da Página 360.</p></div>
      <ReportsNativeSelect aria-label="Período" value={days} onChange={event => onDaysChange(Number(event.target.value))}>{[7, 30, 90].map(value => <option key={value} value={value}>Últimos {value} dias</option>)}</ReportsNativeSelect>
    </header>
    {state.error && <div className="flow-workspace-notice" role="alert">{state.error} <Button color="link-color" size="sm" onClick={onRetry}>Tentar novamente</Button></div>}
    {!data && !state.error && <p className="flow-review__empty" role="status">Lendo as páginas…</p>}
    {data?.status === 'no_site' && <p className="flow-review__empty">Este fluxo ainda não tem um site com Super Tag. Instale a tag para ver o uso das páginas.</p>}
    {data?.status === 'ready' && <>
      <div className="flow-review__summary flow-pages__summary">
        <div className="flow-review__stat"><span>Nota média de uso</span><strong>{average ?? '—'}{average != null && <small> /100</small>}</strong><small>Ponderada pelas sessões{scored.length < rows.length ? ` · ${rows.length - scored.length} sem nota` : ''}</small></div>
        <div className="flow-review__stat"><span>Pedem atenção</span><strong>{attention.length}</strong><small>Nota abaixo de 70</small></div>
        <div className={`flow-review__stat${idleFlow.length ? ' is-warning' : ''}`}><span>Do fluxo sem tráfego</span><strong>{idleFlow.length}</strong><small>Nenhuma sessão em {days} dias</small></div>
        <div className="flow-review__stat"><span>Do site sem tráfego</span><strong>{number(data.idle.site_total)}</strong><small>{data.idle.catalog ? 'Páginas do sitemap sem visitas' : 'Sitemap ainda não lido'}</small></div>
      </div>
      <div className="flow-pages__tabs" role="tablist" aria-label="Visão das páginas">
        <button type="button" role="tab" aria-selected={view === 'usage'} onClick={() => setView('usage')}>Uso das páginas <small>{rows.length}</small></button>
        <button type="button" role="tab" aria-selected={view === 'idle'} onClick={() => setView('idle')}>Sem tráfego <small className={idleFlow.length ? 'is-warning' : ''}>{idleFlow.length + data.idle.site_total}</small></button>
      </div>
      {view === 'usage' && <>
        <div className="flow-pages__toolbar"><p>A nota vai de 0 a 100 e combina tempo ativo (mediana), rolagem até 50% e 75%, avanço para a próxima etapa do fluxo e permanência no site. Sinais que não se aplicam ficam de fora. Abaixo de {data.min_sessions} sessões não há nota.</p>
          <ReportsNativeSelect aria-label="Ordenar" value={order} onChange={event => setOrder(event.target.value)}>{Object.entries(ORDERS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></div>
        {rows.length ? <div className="flow-pages__table" role="table" aria-label="Uso das páginas do fluxo">
          <div role="row" className="flow-pages__row is-head"><span role="columnheader">Página</span><span role="columnheader">Nota</span><span role="columnheader">Sessões</span><span role="columnheader">Tempo ativo</span><span role="columnheader">Rolagem 50% · 75%</span><span role="columnheader">Avançou</span><span role="columnheader">Saiu do site</span><span role="columnheader"><span className="sr-only">Ações</span></span></div>
          {rows.map(row => <div role="row" key={row.node_id} className={`flow-pages__row is-${row.grade || 'none'}`}>
            <span role="cell" className="flow-pages__page"><strong>{row.title}</strong><small>{TYPE_LABELS[row.type]} · {row.path}</small><Components row={row}/></span>
            <span role="cell"><UsageScore row={row}/></span>
            <span role="cell">{number(row.sessions)}</span>
            <span role="cell">{seconds(row.median_active_seconds)}</span>
            <span role="cell">{percent(row.scroll_50)} · {percent(row.scroll_75)}</span>
            <span role="cell" title={row.next_steps?.length ? `Para: ${row.next_steps.join(', ')}` : 'Sem próxima etapa desenhada'}>{row.advance_rate == null ? '—' : percent(row.advance_rate)}</span>
            <span role="cell">{row.type === 'conversion' ? <small>Fim esperado</small> : percent(row.exit_rate)}</span>
            <span role="cell" className="flow-pages__actions"><Button color="tertiary" size="sm" onClick={() => onSelectNode(row.node_id)}>Ver no mapa</Button>{pageLink(row.path) && <a href={pageLink(row.path)}>Página 360</a>}</span>
          </div>)}
        </div> : <p className="flow-review__empty">Nenhuma página do fluxo recebeu visitas no período.</p>}
        {pending.length > 0 && <p className="flow-pages__note">{pending.length} {pending.length === 1 ? 'etapa fica' : 'etapas ficam'} de fora: {pending.map(row => `${row.title} (${row.status === 'external' ? 'outro domínio' : 'sem endereço'})`).join(', ')}.</p>}
      </>}
      {view === 'idle' && <div className="flow-pages__idle">
        <section aria-label="Páginas do fluxo sem tráfego">
          <h3>No fluxo</h3>
          {idleFlow.length ? <>
            <p>Estas etapas fazem parte do caminho, mas ninguém chegou a elas em {days} dias. Confira se há links que levam até elas, se as campanhas apontam para o endereço certo e se a página existe.</p>
            <ul className="flow-pages__list">{idleFlow.map(row => <li key={row.node_id} className="is-warning"><div><strong>{row.title}</strong><small>{TYPE_LABELS[row.type]} · {row.path}{row.planned ? ' · planejada' : ''}</small></div><Button color="secondary" size="sm" onClick={() => onSelectNode(row.node_id)}>Ver no mapa</Button></li>)}</ul>
          </> : <p className="flow-pages__ok">Todas as páginas do fluxo receberam visitas no período.</p>}
        </section>
        <section aria-label="Páginas do site sem tráfego">
          <h3>No site <small>{number(data.idle.site_total)} {data.idle.site_total === 1 ? 'página' : 'páginas'} do sitemap sem visitas</small></h3>
          {data.idle.catalog ? <>
            <ReportsFieldInput aria-label="Buscar página sem tráfego" placeholder="Buscar pelo nome ou endereço" value={query} onChange={event => setQuery(event.target.value)}/>
            {idleSite.length ? <ul className="flow-pages__list is-site">{idleSite.map(page => <li key={page.path}><div><strong>{page.title || page.name}</strong><small>{page.path}</small></div></li>)}</ul> : <p className="flow-pages__ok">{query ? 'Nenhuma página encontrada.' : 'Todas as páginas do sitemap receberam visitas no período.'}</p>}
            {data.idle.site_total > (data.idle.site || []).length && <p className="flow-pages__note">Mostrando as {number((data.idle.site || []).length)} mais próximas da raiz do site.</p>}
          </> : <p className="flow-pages__note">O sitemap deste site ainda não foi lido. Ele é lido quando alguém busca uma página no editor.</p>}
        </section>
      </div>}
    </>}
  </section>;
}
