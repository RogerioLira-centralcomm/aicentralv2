import React from 'react';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {LogoTile} from '../PlannerUi.jsx';
import {moduleUrl} from '../api.js';

const KIND = {canais: ['canal', 'canais'], formatos: ['formato', 'formatos'], interativos: ['interativo', 'interativos'],
  audiencias: ['audiência', 'audiências'], portais: ['portal', 'portais'], places: ['place', 'places']};

/** "1 canal · 2 formatos": counts only. Reach is never summed (the same person sits in several channels). */
export function planCounts(items) {
  const counts = new Map();
  items.forEach(item => counts.set(item.kind, (counts.get(item.kind) || 0) + 1));
  return [...counts].map(([kind, total]) => `${total} ${(KIND[kind] || [kind, kind])[total === 1 ? 0 : 1]}`).join(' · ');
}

/** What is in the open plan, with a way out for each item and the way forward. */
export function PlanSidebar({plan, selection, boot, plansUrl}) {
  const items = plan?.items || [];
  const href = plan ? `${plansUrl}/${encodeURIComponent(plan.id)}` : plansUrl;
  return <div className="pd-plan">
    <header><h2>No seu plano</h2>{plan && <span className="pd-plan__count">{items.length}</span>}</header>
    {plan ? items.length ? <ul>{items.map(item => <li key={`${item.kind}:${item.resource_id}`}>
      <LogoTile src={item.logo} name={item.snapshot?.name} icon="plan" size="sm"/>
      <span><a href={`${moduleUrl(boot.urls, item.kind)}/${encodeURIComponent(item.resource_id)}`}>{item.snapshot?.name || item.resource_id}</a>
        <small>{(KIND[item.kind] || [item.kind])[0]}{item.snapshot?.dimensions ? ` · ${item.snapshot.dimensions}` : ''}</small></span>
      <button type="button" aria-label={`Remover ${item.snapshot?.name || 'item'} do plano`} onClick={() => selection.toggle(item.kind, item.resource_id)}><Icon name="trash" size={16}/></button>
    </li>)}</ul> : <p className="pd-plan__empty">Nada por aqui ainda. Adicione canais, formatos e audiências.</p>
      : <p className="pd-plan__empty">Nenhum plano aberto. Abra ou crie um plano para guardar estas escolhas.</p>}
    <a className="pd-plan__go" href={href}>{plan ? 'Revisar plano' : 'Ver planos'}<Icon name="chevron" size={14}/></a>
    {items.length > 0 && <p className="pd-plan__totals"><strong>No plano</strong>{planCounts(items)}<small>O alcance e o valor saem da cotação, não de uma soma.</small></p>}
  </div>;
}
