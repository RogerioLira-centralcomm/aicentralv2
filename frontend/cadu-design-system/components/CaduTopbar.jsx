import React from 'react';
import {Icon} from '../../conversations-v2/lib/icons';

export function CaduTopbar({title, context, actions = [], onMenu}) {
  return <header className="cadu-ds-topbar"><button type="button" className="cadu-ds-topbar__menu" onClick={onMenu} aria-label="Abrir navegação"><Icon name="menu" size={18}/></button><h1>{title}</h1>{context && <span className="cadu-ds-topbar__context">{context}</span>}<div className="cadu-ds-topbar__actions">{actions.map(action => <button key={action.label} type="button" onClick={action.onClick} aria-label={action.label}>{action.icon && <Icon name={action.icon} size={16}/>} {action.text}</button>)}</div></header>;
}
