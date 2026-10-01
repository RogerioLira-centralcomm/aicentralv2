import React, {useCallback, useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';

/** One status line at the top of the page; errors stay until dismissed. */
export function PlannerNotice({notice, onDismiss}) {
  if (!notice) return null;
  return <div className={`planner-notice planner-notice--${notice.tone || 'success'}`} role={notice.tone === 'error' ? 'alert' : 'status'}>
    <span>{notice.message}</span>
    <button type="button" onClick={onDismiss} aria-label="Fechar aviso">×</button>
  </div>;
}

/** A titled white surface, the unit every Planner page is built from. */
export function PlannerPanel({title, description, actions = null, className = '', children}) {
  return <section className={`planner-panel ${className}`.trim()}>
    {(title || actions) && <header className="planner-panel__header">
      <div>{title && <h2>{title}</h2>}{description && <p>{description}</p>}</div>
      {actions}
    </header>}
    {children}
  </section>;
}

/** Add or remove a catalog reference from the open plan (or the loose selection). */
export function SelectionButton({selected, onToggle, size = 'sm', className = ''}) {
  return <CaduButton variant={selected ? 'secondary' : 'primary'} size={size} className={`planner-selection-button${selected ? ' is-selected' : ''} ${className}`.trim()} aria-pressed={selected} onClick={onToggle}>
    {selected ? 'No plano' : 'Adicionar'}
  </CaduButton>;
}

/**
 * Selected references for the current plan, or for the visitor's loose
 * selection when no plan is open. Keys are `kind:resource_id`.
 */
export function usePlanSelection(request, plan, onPlanChange, notify, enabled = true) {
  const [keys, setKeys] = useState(() => new Set());
  const planId = plan?.id;

  useEffect(() => {
    if (!enabled) return undefined;
    let active = true;
    request(planId ? `/plans/${planId}` : '/selections')
      .then(data => {
        const items = planId ? (data.plan?.items || []) : (data.selections || []);
        if (active) setKeys(new Set(items.map(item => `${item.kind}:${item.resource_id}`)));
      })
      .catch(() => {});
    return () => { active = false; };
  }, [request, planId, enabled]);

  const toggle = useCallback(async (kind, id) => {
    try {
      const path = planId ? `/plans/${planId}/items/toggle` : '/selections/toggle';
      const data = await request(path, {method: 'POST', body: JSON.stringify({kind, resource_id: String(id)})});
      setKeys(current => {
        const next = new Set(current);
        const key = `${kind}:${id}`;
        if (data.selected) next.add(key); else next.delete(key);
        return next;
      });
      if (planId && onPlanChange) {
        const updated = await request(`/plans/${planId}`);
        onPlanChange(updated.plan);
      }
      notify?.({message: data.selected ? 'Adicionado ao plano.' : 'Removido do plano.'});
      return data.selected;
    } catch (error) {
      notify?.({tone: 'error', message: error.message});
      return undefined;
    }
  }, [request, planId, onPlanChange, notify]);

  const isSelected = useCallback((kind, id) => keys.has(`${kind}:${id}`), [keys]);
  return {isSelected, toggle};
}
