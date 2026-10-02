import React from 'react';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {MODULE_LABELS, objectiveLabel, plainText} from './api.js';
import {MetricTiles} from './details/DetailLayout.jsx';

const KIND_ORDER = ['audiencias', 'canais', 'formatos', 'interativos', 'portais', 'places'];
const money = value => Number(value) ? Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: 0}) : '';

// Shared links open without the sidebar: a single readable column.
export function PublicPlan({plan}) {
  if (!plan) return <CaduEmptyState title="Plano indisponível" description="O link pode ter sido despublicado."/>;
  const briefing = plan.briefing || {};
  const objective = briefing.objective || plan.objective;
  const allocations = plan.allocation_by_channel || {};
  const groups = KIND_ORDER.map(kind => [kind, (plan.items || []).filter(item => item.kind === kind)]).filter(([, items]) => items.length);
  return <article className="planner-public">
    <header className="planner-public__brand"><img src="/static/images/cadu/products/planner-icon.png" alt="" width="24" height="24"/><span>Plano de mídia compartilhado pelo Cadu Planner</span></header>
    <div>
      <h1>{plan.title}</h1>
      {(plan.advertiser_name || plan.campaign_name) && <p>{[plan.advertiser_name, plan.campaign_name].filter(Boolean).join(' · ')}</p>}
    </div>
    <MetricTiles items={[
      {label: 'Investimento', value: briefing.budget}, {label: 'Período', value: briefing.period},
      {label: 'Praça', value: briefing.geography}, {label: 'Objetivo', value: objective && objectiveLabel(objective)},
    ]}/>
    {briefing.kpis && <p className="planner-public__kpis"><strong>KPIs:</strong> {briefing.kpis}</p>}
    {groups.map(([kind, items]) => <section key={kind} className="planner-public__group">
      <h2>{MODULE_LABELS[kind] || kind}<small>{items.length}</small></h2>
      <ul>{items.map(item => {
        const allocation = allocations[String(item.resource_id)];
        return <li key={`${kind}:${item.resource_id}`}>
          <span><strong>{item.snapshot?.name || item.resource_id}</strong>
            {(item.snapshot?.category || item.snapshot?.audience) && <small>{[item.snapshot?.category, item.snapshot?.audience].filter(Boolean).join(' · ')}</small>}</span>
          {allocation && <span className="planner-public__alloc">{money(allocation.investment)}{Number(allocation.weight) ? ` · ${Number(allocation.weight)}%` : ''}</span>}
        </li>;
      })}</ul>
    </section>)}
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
