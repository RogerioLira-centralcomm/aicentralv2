import React, {useCallback, useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

/** One status line at the top of the page; errors stay until dismissed. */
/**
 * Every logo in the Planner (cards, details, rails, filters) sits in the same
 * tile: white, hairline border, proportional radius and inner margin, image
 * contained — so wordmarks and app icons read as one family.
 */
export function LogoTile({src, name = '', icon = 'plan', size = 'sm', color}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  return <span className={`logo-tile logo-tile--${size}`} style={color ? {'--logo-tile-color': color} : undefined} role={name ? 'img' : undefined} aria-label={name || undefined}>
    {src && !failed ? <img src={src} alt="" loading="lazy" onError={() => setFailed(true)}/> : <Icon name={icon} size={size === 'lg' ? 24 : size === 'xs' ? 12 : 18}/>}
  </span>;
}

export function PlannerNotice({notice, onDismiss}) {
  if (!notice) return null;
  return <div className={`planner-notice planner-notice--${notice.tone || 'success'}`} role={notice.tone === 'error' ? 'alert' : 'status'}>
    <span>{notice.message}</span>
    <CaduButton variant="tertiary" size="sm" aria-label="Fechar aviso" onClick={onDismiss}><Icon name="close" size={16}/></CaduButton>
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
export function SelectionButton({selected, onToggle, size = 'sm', quiet = false, className = ''}) {
  // In lists the action is secondary (many items); on a detail page it is the main action.
  const variant = selected || quiet ? 'secondary' : 'primary';
  return <CaduButton variant={variant} size={size} className={`planner-selection-button${selected ? ' is-selected' : ''}${quiet ? ' is-quiet' : ''} ${className}`.trim()}
    aria-pressed={selected} aria-label={selected ? 'No plano. Remover do plano' : undefined} onClick={onToggle}>
    {selected ? <><Icon name="check" size={16}/>No plano</> : <><Icon name="plus" size={16}/>{size === 'md' ? 'Adicionar ao plano' : 'Adicionar'}</>}
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
