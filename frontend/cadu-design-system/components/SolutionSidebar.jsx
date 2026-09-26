import React, {useEffect, useState} from 'react';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {workspaceSolutionItems} from '../workspaceSolutions';
import './SolutionSidebar.css';

export function SolutionSidebar({solution, context = 'Cliente', icon, accent, groups = [], active, storageKey, footer, solutionUrls = {}, solutionIcons = {}, solutionLogo, activeSolutionId}) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(storageKey) === 'collapsed'; } catch (_) { return false; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const solutions = workspaceSolutionItems({urls:{solutions:solutionUrls}, solutionIcons});
  useEffect(() => {
    try { localStorage.setItem(storageKey, collapsed ? 'collapsed' : 'open'); } catch (_) { /* preference is optional */ }
  }, [collapsed, storageKey]);

  return <aside className={`cadu-solution-sidebar${collapsed ? ' is-collapsed' : ''}${mobileOpen ? ' is-mobile-open' : ''}`} style={{'--solution-accent': accent}} aria-label={`Navegação do ${solution}`}>
    <header className="cadu-solution-sidebar__header">
      <div className="cadu-solution-sidebar__switcher"><CaduSolutionSwitcher logo={solutionLogo} solutions={solutions} activeId={activeSolutionId}/></div>
      <div className="cadu-solution-sidebar__heading"><span>{solution}</span><strong title={context}>{context}</strong></div>
      <button type="button" className="cadu-solution-sidebar__toggle" onClick={() => {if (matchMedia('(max-width: 760px)').matches) setMobileOpen(value => !value); else setCollapsed(value => !value);}} aria-label={mobileOpen ? 'Fechar navegação' : collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={matchMedia('(max-width: 760px)').matches ? mobileOpen : !collapsed}>
        <span className="cadu-solution-sidebar__toggle-mobile">{mobileOpen ? 'Fechar' : 'Menu'}</span><span className="cadu-solution-sidebar__toggle-desktop" aria-hidden="true">{collapsed ? '›' : '‹'}</span>
      </button>
    </header>
    <nav className="cadu-solution-sidebar__nav" aria-label={`Seções do ${solution}`}>
      {groups.map(group => <section className="cadu-solution-sidebar__group" key={group.label}>
        {group.label && <span className="cadu-solution-sidebar__group-label">{group.label}</span>}
        {group.items.map(item => <a key={item.id} href={item.href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} title={collapsed ? item.label : undefined} onClick={() => setMobileOpen(false)}><Icon name={item.icon || 'file'} size={17}/><span>{item.label}</span></a>)}
      </section>)}
    </nav>
    {footer && <footer className="cadu-solution-sidebar__footer">{footer}</footer>}
  </aside>;
}
