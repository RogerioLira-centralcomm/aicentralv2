import React from 'react';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {MODULE_LABELS, objectiveLabel, plainText} from './api.js';
import {MetricTiles} from './details/DetailLayout.jsx';

const KIND_ORDER = ['audiencias', 'canais', 'formatos', 'interativos', 'portais', 'places'];
const money = value => Number(value) ? Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: 0}) : '';

// Shared links open without the sidebar: a single readable column.
// "R$ 300.000 (alocação a confirmar)" → tile "R$ 300.000", hint "alocação a confirmar".
const labelParts = value => String(value || '').replace(/\s*\(([^)]*)\)/g, '; $1').split(/\s*[;—]\s*/).filter(Boolean);
const shortLabel = value => labelParts(value)[0] || '';
const restLabel = value => labelParts(value).slice(1).join(' · ');
const day = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}).replace('.', '') : '';

/** "Objetivo: … Público-alvo: … Canais e função: …" → [[title, text], …]; plain text stays one block. */
export function strategyBlocks(notes) {
  const text = String(notes || '').trim();
  if (!text) return [];
  const pattern = /(?:^|(?<=[.!?\n]))\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.:\n]{2,48}):\s/g;
  const marks = [...text.matchAll(pattern)];
  if (marks.length < 2) return [['Estratégia', text]];
  return marks.map((mark, index) => [mark[1].trim(),
    text.slice(mark.index + mark[0].length, index + 1 < marks.length ? marks[index + 1].index : text.length).trim()])
    .filter(([, body]) => body);
}
// KPIs come as "1) … 2) …", "a; b" or "a, b, c": one chip each (commas inside parentheses stay).
const kpiList = value => {
  const text = String(value || '');
  const strong = text.split(/\s*(?:;|\d\)\s*|\n)\s*/);
  const parts = strong.filter(item => item.trim()).length > 1 ? strong : text.split(/,\s*(?![^()]*\))/);
  return parts.map(item => item.trim().replace(/[.;,]$/, '')).filter(item => item.length > 2);
};

/**
 * The plan as the client receives it: why now, the strategy, the KPIs, where the money goes and why,
 * the audiences and formats, and what still needs the client's answer. Media is quoted, never priced here.
 */
export function PublicPlan({plan}) {
  if (!plan) return <CaduEmptyState title="Plano indisponível" description="O link pode ter sido despublicado."/>;
  const briefing = plan.briefing || {};
  const objective = briefing.objective || plan.objective;
  const allocations = plan.allocation_by_channel || {};
  const items = plan.items || [];
  const channels = items.filter(item => item.kind === 'canais');
  const split = channels.map(item => ({item, allocation: allocations[String(item.resource_id)]})).filter(row => row.allocation);
  const total = split.reduce((sum, row) => sum + Number(row.allocation.investment || 0), 0);
  const groups = KIND_ORDER.filter(kind => kind !== 'canais' || !split.length)
    .map(kind => [kind, items.filter(item => item.kind === kind)]).filter(([, list]) => list.length);
  const blocks = strategyBlocks(briefing.notes);
  const kpis = kpiList(briefing.kpis);
  const story = plan.story;
  const pending = plan.pending || [];
  return <article className="planner-public planner-public--v2">
    <header className="planner-public__brand"><img src="/static/images/cadu/products/planner-icon.png" alt="" width="24" height="24"/><span>Plano de mídia compartilhado pelo Cadu Planner</span>
      {plan.updated_at && <small>Atualizado em {day(plan.updated_at)}</small>}</header>
    <div className="pp-head">
      {objective && <span className="pp-chip">{objectiveLabel(objective)}</span>}
      <h1>{plan.title}</h1>
      {(plan.advertiser_name || plan.campaign_name) && <p>{[plan.advertiser_name, plan.campaign_name !== plan.title && plan.campaign_name].filter(Boolean).join(' · ')}</p>}
    </div>
    <MetricTiles items={[
      {label: 'Investimento', value: shortLabel(briefing.budget), hint: restLabel(briefing.budget)},
      {label: 'Período', value: shortLabel(briefing.period), hint: restLabel(briefing.period)},
      {label: 'Praça', value: shortLabel(briefing.geography), hint: restLabel(briefing.geography)},
      {label: 'Canais', value: channels.length || null},
    ]}/>

    {story && (story.why_now || story.buzz.length > 0) && <section className="pp-section pp-why">
      <h2>Por que agora</h2>
      {story.why_now && <p>{story.why_now}</p>}
      {story.window && <p className="pp-muted">Janela: {story.window}</p>}
      {story.buzz.length > 0 && <ul className="pp-buzz">{story.buzz.map(item => <li key={item.url}>
        <a href={item.url} target="_blank" rel="noreferrer noopener">{item.title}</a><small>{[item.source, item.date && day(item.date)].filter(Boolean).join(' · ')}</small>
      </li>)}</ul>}
    </section>}

    {blocks.length > 0 && <section className="pp-section">
      <h2>A estratégia</h2>
      <div className="pp-blocks">{blocks.map(([title, body]) => <div key={title} className="pp-block"><h3>{title}</h3><p>{body}</p></div>)}</div>
    </section>}

    {kpis.length > 0 && <section className="pp-section">
      <h2>Como vamos medir</h2>
      <ul className="pp-kpis">{kpis.map(kpi => <li key={kpi}>{kpi}</li>)}</ul>
    </section>}

    {split.length > 0 && <section className="pp-section">
      <h2>Para onde vai a verba<small>{money(total)}</small></h2>
      <ul className="pp-split">{split.map(({item, allocation}) => {
        const share = total ? Math.round(Number(allocation.investment || 0) * 100 / total) : Number(allocation.weight || 0);
        return <li key={item.resource_id}>
          <div className="pp-split__head"><strong>{item.snapshot?.name || item.resource_id}</strong><span>{money(allocation.investment)} · {share}%</span></div>
          <span className="pp-split__bar"><b style={{width: `${share}%`}}/></span>
          <small>{[allocation.notes, item.snapshot?.category, allocation.flight].filter(Boolean).join(' · ')}</small>
        </li>;
      })}</ul>
    </section>}

    {groups.map(([kind, list]) => <section key={kind} className="pp-section">
      <h2>{MODULE_LABELS[kind] || kind}<small>{list.length}</small></h2>
      <ul className="pp-items">{list.map(item => <li key={`${kind}:${item.resource_id}`}>
        <strong>{item.snapshot?.name || item.resource_id}</strong>
        {[item.snapshot?.category, item.snapshot?.audience].filter(value => value && String(value).length <= 40).length > 0
          && <small>{[item.snapshot?.category, item.snapshot?.audience].filter(value => value && String(value).length <= 40).join(' · ')}</small>}
      </li>)}</ul>
    </section>)}

    {pending.length > 0 && <section className="pp-section pp-pending">
      <h2>Para alinharmos</h2>
      <ul>{pending.map(item => <li key={item}>{item}</li>)}</ul>
    </section>}
    <p className="pp-muted pp-foot">Valores de mídia sujeitos a cotação e disponibilidade de inventário.</p>
  </article>;
}

export function PublicDoc({document}) {
  const doc = document || {};
  return <article className="planner-public">
    <span className="planner-section-label">{doc.type || 'Documento'}</span>
    <h1>{doc.title || 'Documento'}</h1>
    <p className="planner-doc-preview">{plainText(doc.html) || 'Este documento não contém texto para exibição.'}</p>
  </article>;
}
