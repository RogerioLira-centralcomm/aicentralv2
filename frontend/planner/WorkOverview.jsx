import React, {useEffect, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

const LIMIT = 5;
const when = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short'}).replace('.', '') : '';

/**
 * "Visão geral" column of the creation screens: the plans and radars this person already has, each a link.
 * Shows `children` (the illustration) while loading and when there is nothing yet.
 */
export function WorkOverview({request, urls, radarEnabled = false, children}) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let current = true;
    Promise.all([
      request('/plans').then(body => body.plans || []).catch(() => []),
      radarEnabled ? request(`/radar/runs?limit=${LIMIT}`).then(body => body.runs || []).catch(() => []) : Promise.resolve([]),
    ]).then(([plans, runs]) => { if (current) setData({plans, runs}); });
    return () => { current = false; };
  }, [request, radarEnabled]);

  if (!data || (!data.plans.length && !data.runs.length)) return children;
  const plans = data.plans.slice(0, LIMIT);
  const runs = data.runs.slice(0, LIMIT);
  return <div className="work-overview">
    <span className="wizard__eyebrow">Visão geral</span>
    {plans.length > 0 && <section aria-labelledby="wo-plans">
      <h2 id="wo-plans">Seus planos<span>{data.plans.length}</span></h2>
      <ul>{plans.map(plan => <li key={plan.id}><a href={`${urls.plans}/${encodeURIComponent(plan.id)}`}>
        <Icon name="history" size={16}/><span><strong>{plan.title || 'Plano sem título'}</strong>
          <small>{[plan.status === 'ready' ? 'Pronto para revisão' : 'Rascunho', plan.item_count ? `${plan.item_count} itens` : '', when(plan.updated_at)].filter(Boolean).join(' · ')}</small></span>
      </a></li>)}</ul>
      <a className="work-overview__all" href={urls.plans}>Ver todos os planos<Icon name="chevron" size={14}/></a>
    </section>}
    {runs.length > 0 && <section aria-labelledby="wo-radars">
      <h2 id="wo-radars">Radares recentes</h2>
      <ul>{runs.map(run => <li key={run.id}><a href={`${urls.radar}?run=${encodeURIComponent(run.id)}`}>
        <Icon name="pulse" size={16}/><span><strong>{run.focus || 'Radar da marca'}</strong>
          <small>{[run.opportunities ? `${run.opportunities} ângulos` : '', when(run.created_at)].filter(Boolean).join(' · ')}</small></span>
      </a></li>)}</ul>
      <a className="work-overview__all" href={urls.radars}>Ver todos os radares<Icon name="chevron" size={14}/></a>
    </section>}
  </div>;
}
