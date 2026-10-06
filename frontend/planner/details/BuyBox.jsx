import React from 'react';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {SelectionButton} from '../PlannerUi.jsx';
import {hasValue, tidy} from './DetailLayout.jsx';

/**
 * The one place to decide on a detail page: what it is, the facts that matter and a single
 * action. It stays in view while the person reads; the plan itself lives in the floating dock.
 */
export function BuyBox({kind, id, name, pitch, facts = [], selection, note = 'A cotação é pedida no plano, sem compromisso.'}) {
  const selected = selection.isSelected(kind, id);
  const shown = facts.filter(([, value]) => hasValue(value));
  return <div className={`buybox${selected ? ' is-selected' : ''}`}>
    {pitch && <p className="buybox__pitch">{pitch}</p>}
    {shown.length > 0 && <dl className="buybox__facts">{shown.map(([label, value, icon]) => <div key={label}>
      {icon && <Icon name={icon} size={16}/>}<dt>{label}</dt><dd>{tidy(value)}</dd></div>)}</dl>}
    <SelectionButton size="md" selected={selected} onToggle={() => selection.toggle(kind, id)} className="buybox__cta"/>
    <small className="buybox__note">{selected ? `${name} está no seu plano.` : note}</small>
  </div>;
}
