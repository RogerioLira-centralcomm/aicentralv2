import React, {useState} from 'react';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {SidebarAccount, useCreditUsage} from './SidebarAccount';
import {workspaceSolutionItems} from '../workspaceSolutions';
import './SolutionSidebar.css';

export function SolutionSidebar({solution, icon, accent, groups = [], active, storageKey, footer, solutionUrls = {}, solutionIcons = {}, solutionLogo, activeSolutionId, userName = 'Minha conta', accountLabel, userAvatar = '', creditsUrl, profileUrl, onNavigate, autoCollapse = false, context}) {
  // autoCollapse: focused pages (e.g. a plan) open collapsed without touching the saved preference.
  const [collapsed, setCollapsed] = useState(() => {
    if (autoCollapse) return true;
    try { return localStorage.getItem(storageKey) === 'collapsed'; } catch (_) { return false; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const usagePercent = useCreditUsage(null);
  // Collapsed links show only icons: name them in a tooltip placed outside the scrolling nav.
  const [tooltip, setTooltip] = useState(null);
  const showTooltip = event => {
    if (!collapsed || matchMedia('(max-width: 760px)').matches) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({label: event.currentTarget.dataset.label, top: rect.top + rect.height / 2, left: rect.right + 10});
  };
  const hideTooltip = () => setTooltip(null);
  const solutions = workspaceSolutionItems({urls:{solutions:solutionUrls}, solutionIcons});
  // Only a click is a preference; an automatic collapse must not leak into other pages.
  const toggleCollapsed = () => setCollapsed(value => {
    try { localStorage.setItem(storageKey, value ? 'open' : 'collapsed'); } catch (_) { /* preference is optional */ }
    return !value;
  });

  return <aside className={`cadu-solution-sidebar${collapsed ? ' is-collapsed' : ''}${mobileOpen ? ' is-mobile-open' : ''}`} style={{'--solution-accent': accent}} aria-label={`Navegação do ${solution}`}>
    <header className="cadu-solution-sidebar__header">
      <div className="cadu-solution-sidebar__switcher"><CaduSolutionSwitcher logo={solutionLogo} solutions={solutions} activeId={activeSolutionId} showActiveLabel={!collapsed} overlay overlayAccent={accent}/></div>
      <button type="button" className="cadu-solution-sidebar__toggle" onClick={() => {hideTooltip(); if (matchMedia('(max-width: 760px)').matches) setMobileOpen(value => !value); else toggleCollapsed();}} aria-label={mobileOpen ? 'Fechar navegação' : collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={matchMedia('(max-width: 760px)').matches ? mobileOpen : !collapsed}>
        <span className="cadu-solution-sidebar__toggle-mobile">{mobileOpen ? 'Fechar' : 'Menu'}</span><span className="cadu-solution-sidebar__toggle-desktop" aria-hidden="true">{collapsed ? '›' : '‹'}</span>
      </button>
    </header>
    {context && <div className="cadu-solution-sidebar__context">{typeof context === 'function' ? context({collapsed}) : context}</div>}
    <nav className="cadu-solution-sidebar__nav" aria-label={`Seções do ${solution}`}>
      {groups.map(group => <section className="cadu-solution-sidebar__group" key={group.label}>
        {group.label && <span className="cadu-solution-sidebar__group-label">{group.label}</span>}
        {group.items.map(item => <a key={item.id} href={item.href} className={active === item.id ? 'is-active' : ''} aria-current={active === item.id ? 'page' : undefined} aria-label={collapsed ? item.label : undefined} data-label={item.label}
          onMouseEnter={showTooltip} onFocus={showTooltip} onMouseLeave={hideTooltip} onBlur={hideTooltip}
          onClick={event => {hideTooltip(); setMobileOpen(false); onNavigate?.(event, item.href);}}><Icon name={item.icon || 'file'} size={17}/><span>{item.label}</span></a>)}
      </section>)}
    </nav>
    {tooltip && <span className="cadu-solution-sidebar__tooltip" role="tooltip" style={{top: tooltip.top, left: tooltip.left}}>{tooltip.label}</span>}
    <footer className="cadu-solution-sidebar__footer">
      {(profileUrl || creditsUrl) && <SidebarAccount userName={userName} agencyName={accountLabel} avatar={userAvatar} profileUrl={profileUrl} creditsUrl={creditsUrl} usagePercent={usagePercent}/>}
      {footer && <div className="cadu-solution-sidebar__footer-extra">{footer}</div>}
    </footer>
  </aside>;
}
