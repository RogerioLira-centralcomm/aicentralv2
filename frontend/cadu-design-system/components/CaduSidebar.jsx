import React from 'react';
import {Icon} from '../../conversations-v2/lib/icons';

export function CaduSidebar({brand = 'Cadu', subtitle = 'Workspace', items = [], active, footer, collapsed = false, onToggle}) {
  return <aside className={`cadu-ds-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label="Navegação principal">
    <header className="cadu-ds-sidebar__brand"><span className="cadu-ds-mark">C</span>{!collapsed && <span><strong>{brand}</strong><small>{subtitle}</small></span>}{onToggle && <button type="button" onClick={onToggle} aria-label={collapsed ? 'Expandir navegação' : 'Recolher navegação'}><Icon name="chevron" size={15}/></button>}</header>
    <nav>{items.map(item => <a key={item.id || item.label} href={item.href} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined}><Icon name={item.icon || 'file'} size={16}/>{!collapsed && <span>{item.label}</span>}</a>)}</nav>
    {footer && !collapsed && <footer>{footer}</footer>}
  </aside>;
}
