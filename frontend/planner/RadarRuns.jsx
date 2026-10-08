import React from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {RadarListPage} from './RadarList.jsx';

export const RUN_STATUS = {done: ['Concluído', 'success'], running: ['Em andamento', 'brand'], queued: ['Na fila', 'neutral'], failed: ['Falhou', 'neutral'], cancelled: ['Cancelado', 'neutral']};
const when = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}).replace(/\./g, '') : '';
const num = value => Number(value || 0).toLocaleString('pt-BR');

function RunCard({run, brand, href}) {
  const status = RUN_STATUS[run.status] || RUN_STATUS.done;
  const title = run.focus || brand || 'Busca sem tema';
  const done = run.status === 'done';
  return <a className="rr-card" href={href}>
    <div className="rr-card__top"><CaduBadge tone={status[1]}>{status[0]}</CaduBadge>
      {run.trigger === 'agendado' && <span className="rr-card__auto"><Icon name="pulse" size={12}/>Radar ativo</span>}
      <small>{when(run.created_at)}</small></div>
    <h3 title={title}>{title}</h3>
    <p>{[brand, run.params?.places, run.params?.recency_days && `últimos ${run.params.recency_days} dias`].filter(Boolean).join(' · ') || 'Sem marca'}</p>
    {run.error && <p className="rr-card__error">{run.error}</p>}
    {done ? <dl>
      <div><dt>Sinais</dt><dd>{num(run.signals)}</dd></div>
      {Number(run.media_angles) + Number(run.content_angles) + Number(run.intel_angles) > 0
        ? <div className="rr-card__types"><dt>Ângulos</dt><dd>{[[run.media_angles, 'mídia'], [run.content_angles, run.content_angles === 1 ? 'pauta' : 'pautas'],
          [run.intel_angles, 'para saber']].filter(([value]) => Number(value) > 0).map(([value, label]) => `${value} ${label}`).join(' · ')}</dd></div>
        : <div><dt>Ângulos</dt><dd>{num(run.opportunities)}</dd></div>}
      <div><dt>Em plano</dt><dd>{num(run.in_plan)}</dd></div>
      <div><dt>Custo</dt><dd>{num(run.tokens)}<small> tokens</small></dd></div>
    </dl> : <small className="rr-card__wait">{run.status === 'running' ? 'A busca está em andamento.' : 'Sem resultado nesta busca.'}</small>}
  </a>;
}

/**
 * Meus radares: os radares ativos (para pausar ou apagar) e, abaixo, cada busca já feita como um radar com seus números.
 * Os filtros de marca, status e período vêm da barra lateral.
 */
export function RadarRuns({boot, request, notify, runs, names, filters, firstUse}) {
  const list = (runs || []).filter(run => (!filters.brand || run.brand_ref === filters.brand)
    && (!filters.status || run.status === filters.status)
    && (!filters.days || (Date.now() - new Date(run.created_at).getTime()) / 86400000 <= filters.days));
  return <div className="rr">
    <RadarListPage boot={boot} request={request} notify={notify} embedded firstUse={firstUse}/>
    {runs === null ? null : runs.length > 0 && <section aria-labelledby="rr-title">
      <h2 id="rr-title" className="rr-h2">Radares<span>{list.length}</span></h2>
      {list.length === 0 ? <p className="planner-muted">Nenhum radar com esses filtros.</p> : <div className="rr-grid">
        {list.map(run => <RunCard key={run.id} run={run} brand={names[run.brand_ref] || names[run.project_ref] || ''} href={`${boot.urls.radar}?run=${encodeURIComponent(run.id)}`}/>)}</div>}
    </section>}
    {runs !== null && runs.length === 0 && boot.features?.radar && <CaduButton href={`${boot.urls.radar}?novo=1`}><Icon name="plus" size={16}/>Novo radar</CaduButton>}
  </div>;
}
