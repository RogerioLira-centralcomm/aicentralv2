import React, {useEffect, useRef, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity.jsx';
import {CaduSolutionSwitcher} from '../cadu-design-system/components/WorkspaceSelectors.jsx';
import {useCreditUsage} from '../cadu-design-system/components/SidebarAccount.jsx';
import {workspaceSolutionItems} from '../cadu-design-system/workspaceSolutions';
import '../cadu-design-system/components/SolutionSidebar.css';
import {moduleUrl, newPlanUrl} from './api.js';

// Where people browse. Order follows the buying flow: who, where, how. The home page IS the audience shelf, so there is no
// separate "Início": the logo goes home and Audiências lights up there.
const DESTINATIONS = [
  ['canais', 'Canais', 'share'],
  ['audiencias', 'Audiências', 'users'],
  ['portais', 'Portais e veículos', 'library'],
  ['places', 'Locais', 'browser'],
  ['formatos', 'Formatos', 'table'],
  ['interativos', 'Interativos', 'plugin'],
];
const PERCENT = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1});

function Menu({label, icon, items, active = false, align = 'right'}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const outside = event => { if (!ref.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  return <div className="pn-menu" ref={ref}>
    <button type="button" className={`pn-action${active ? ' is-active' : ''}`} aria-haspopup="true" aria-expanded={open} aria-current={active ? 'page' : undefined} onClick={() => setOpen(value => !value)}>
      <Icon name={icon} size={16}/><span>{label}</span>
    </button>
    {open && <div className={`pn-menu__list pn-menu__list--${align}`} role="menu">
      {items.map(([text, href]) => <a key={text} role="menuitem" href={href}>{text}</a>)}
    </div>}
  </div>;
}

/**
 * The Planner's one navigation: direct links to each section, the actions that
 * start work (radar, plans) and the account. Replaces the sidebar so the
 * shelves get the full width.
 */
export function PlannerNav({boot, request, active}) {
  const urls = boot.urls;
  const [mobile, setMobile] = useState(false);
  const usage = useCreditUsage(null);
  const solutions = workspaceSolutionItems({urls: {solutions: {workspace: urls.workspace, planner: urls.home, studio: urls.studio, connect: urls.reports, skills: urls.skills}}, solutionIcons: boot.solutionIcons || {
    workspace: '/static/images/cadu/products/cadu-icon.png', planner: '/static/images/cadu/products/planner-icon.png',
    studio: '/static/images/cadu/products/studio-icon.png', connect: '/static/images/cadu/products/connect-icon.png', skills: '/static/images/cadu/products/skills-icon.png'}});
  // The home page is the audience shelf: highlight Audiências there.
  const section = active === 'inicio' ? 'audiencias' : active;

  const close = () => setMobile(false);
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') setMobile(false); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, []);

  const percent = usage === null ? null : Math.max(0, Math.min(100, usage));
  const first = String(boot.user?.name || 'Minha conta').trim().split(/\s+/)[0];
  const hrefFor = id => moduleUrl(urls, id);

  return <header className={`pn${mobile ? ' is-mobile-open' : ''}`}>
    <div className="pn__bar">
      <div className="pn__brand"><CaduSolutionSwitcher logo="/static/images/cadu/products/planner-icon.png" solutions={solutions} activeId="planner" showActiveLabel overlay overlayAccent="var(--cadu-accent)"/></div>
      <button type="button" className="pn__burger" aria-label={mobile ? 'Fechar navegação' : 'Abrir navegação'} aria-expanded={mobile} onClick={() => setMobile(value => !value)}>
        <Icon name={mobile ? 'close' : 'table'} size={20}/>
      </button>
      <nav className="pn__nav" aria-label="Seções do Planner">
        {DESTINATIONS.map(item => {
          const [id, label, icon] = item;
          const here = section === id;
          return <a key={id} href={hrefFor(id)} className={`pn__link${here ? ' is-active' : ''}`} aria-current={here ? 'page' : undefined} onClick={close}>
            <Icon name={icon} size={16}/><span>{label}</span>
          </a>;
        })}
      </nav>
      <div className="pn__actions">
        <Menu label="Radar" icon="pulse" active={section === 'radar' || section === 'radares'} items={[['Novo radar', hrefFor('radar')], ['Meus radares', hrefFor('radares')]]}/>
        <Menu label="Planos" icon="history" active={section === 'planos' || section === 'novo-plano'} items={[['Todos os planos', urls.plans], ['Novo planejamento', newPlanUrl(urls)]]}/>
        {percent !== null && urls.credits && <a className={`pn-tokens${percent >= 80 ? ' is-high' : ''}`} href={urls.credits} title="Tokens e consumo do mês" aria-label={`Tokens: ${PERCENT.format(percent)}% usados no mês`}>
          <span>Tokens <b>{PERCENT.format(percent)}%</b></span><i aria-hidden="true"><u style={{width: `${percent}%`}}/></i>
        </a>}
        <a className="pn-user" href={urls.profile} title={boot.user?.name || first} aria-label={`Abrir conta de ${boot.user?.name || first}`}>
          <VisualIdentity src={boot.user?.avatar || ''} initials={boot.user?.name || first} label={boot.user?.name || first} imageAlt="" className="pn-user__avatar"/>
          <span>{first}</span>
        </a>
      </div>
    </div>
  </header>;
}
