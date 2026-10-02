import React, {useEffect, useState} from 'react';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {VisualIdentity} from './VisualIdentity';
import {workspaceSolutionItems} from '../workspaceSolutions';
import './SolutionSidebar.css';

function CreditsLink({percent, href}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const formatted = new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(value);
  return <a className="cadu-solution-sidebar__usage" href={href} aria-label={`Créditos e consumo: utilização de ${formatted}%`} title="Créditos e consumo"><span>{formatted}%</span><i aria-hidden="true"><b style={{width:`${value}%`}}/></i></a>;
}

export function SolutionSidebar({solution, icon, accent, groups = [], active, storageKey, footer, solutionUrls = {}, solutionIcons = {}, solutionLogo, activeSolutionId, userName = 'Minha conta', accountLabel, userAvatar = '', creditsUrl, profileUrl, onNavigate}) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(storageKey) === 'collapsed'; } catch (_) { return false; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [usagePercent, setUsagePercent] = useState(0);
  // Collapsed links show only icons: name them in a tooltip placed outside the scrolling nav.
  const [tooltip, setTooltip] = useState(null);
  const showTooltip = event => {
    if (!collapsed || matchMedia('(max-width: 760px)').matches) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({label: event.currentTarget.dataset.label, top: rect.top + rect.height / 2, left: rect.right + 10});
  };
  const hideTooltip = () => setTooltip(null);
  const solutions = workspaceSolutionItems({urls:{solutions:solutionUrls}, solutionIcons});
  useEffect(() => {
    try { localStorage.setItem(storageKey, collapsed ? 'collapsed' : 'open'); } catch (_) { /* preference is optional */ }
  }, [collapsed, storageKey]);
  useEffect(() => {
    let current = true;
    const refresh = () => fetch('/workspace/api/creditos/resumo', {credentials:'same-origin', headers:{Accept:'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Resumo indisponível')))
      .then(value => { if (current && Number.isFinite(Number(value.monthly_usage_percentage))) setUsagePercent(Number(value.monthly_usage_percentage)); })
      .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => { current = false; window.clearInterval(timer); };
  }, []);

  return <aside className={`cadu-solution-sidebar${collapsed ? ' is-collapsed' : ''}${mobileOpen ? ' is-mobile-open' : ''}`} style={{'--solution-accent': accent}} aria-label={`Navegação do ${solution}`}>
    <header className="cadu-solution-sidebar__header">
      <div className="cadu-solution-sidebar__switcher"><CaduSolutionSwitcher logo={solutionLogo} solutions={solutions} activeId={activeSolutionId} showActiveLabel={!collapsed} overlay overlayAccent={accent}/></div>
      <button type="button" className="cadu-solution-sidebar__toggle" onClick={() => {hideTooltip(); if (matchMedia('(max-width: 760px)').matches) setMobileOpen(value => !value); else setCollapsed(value => !value);}} aria-label={mobileOpen ? 'Fechar navegação' : collapsed ? 'Expandir navegação' : 'Recolher navegação'} aria-expanded={matchMedia('(max-width: 760px)').matches ? mobileOpen : !collapsed}>
        <span className="cadu-solution-sidebar__toggle-mobile">{mobileOpen ? 'Fechar' : 'Menu'}</span><span className="cadu-solution-sidebar__toggle-desktop" aria-hidden="true">{collapsed ? '›' : '‹'}</span>
      </button>
    </header>
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
      {profileUrl && <a className="cadu-solution-sidebar__account" href={profileUrl} aria-label={`Abrir perfil de ${userName}`} title={userName}>
        <VisualIdentity src={userAvatar} initials={userName} label={userName} className="cadu-solution-sidebar__avatar" imageAlt={`Foto de ${userName || 'usuário'}`}/>
        <span className="cadu-solution-sidebar__account-name">{accountLabel || userName || 'Minha conta'}</span>
      </a>}
      {creditsUrl && <CreditsLink percent={usagePercent} href={creditsUrl}/>}
      {footer && <div className="cadu-solution-sidebar__footer-extra">{footer}</div>}
    </footer>
  </aside>;
}
