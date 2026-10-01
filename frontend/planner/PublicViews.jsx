import React from 'react';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {MODULE_LABELS, objectiveLabel, plainText} from './api.js';

// Shared links open without the sidebar: a single readable column.
export function PublicPlan({plan}) {
  if (!plan) return <CaduEmptyState title="Plano indisponível" description="O link pode ter sido despublicado."/>;
  const briefing = plan.briefing || {};
  const facts = [['Objetivo', (briefing.objective || plan.objective) && objectiveLabel(briefing.objective || plan.objective)], ['Investimento', briefing.budget], ['Período', briefing.period], ['Praça', briefing.geography], ['KPIs', briefing.kpis]].filter(([, value]) => value);
  return <article className="planner-public">
    <span className="planner-section-label">Plano de mídia</span>
    <h1>{plan.title}</h1>
    {(plan.advertiser_name || plan.campaign_name) && <p>{[plan.advertiser_name, plan.campaign_name].filter(Boolean).join(' · ')}</p>}
    {facts.length > 0 && <dl className="planner-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
    <h2>Seleção de mídia</h2>
    <ul className="planner-items">{(plan.items || []).map(item => <li key={`${item.kind}:${item.resource_id}`}><span><strong>{item.snapshot?.name || item.resource_id}</strong><small>{MODULE_LABELS[item.kind] || item.kind}</small></span></li>)}</ul>
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
