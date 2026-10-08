import React, {useEffect, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity.jsx';
import {CaduSolutionSwitcher} from '../cadu-design-system/components/WorkspaceSelectors.jsx';
import {useCreditUsage} from '../cadu-design-system/components/SidebarAccount.jsx';
import {workspaceSolutionItems} from '../cadu-design-system/workspaceSolutions';
import '../cadu-design-system/components/SolutionSidebar.css';
import {moduleUrl, newPlanUrl} from './api.js';

// Where people browse. The home page IS the channel shelf, so there is no separate "Início": the logo goes home and
// Canais lights up there.
const DESTINATIONS = [
  ['planos', 'Planos', 'history'],
  ['radar', 'Radar', 'pulse'],
  ['canais', 'Canais', 'share'],
  ['audiencias', 'Audiências', 'users'],
  ['portais', 'Portais', 'library'],
  ['places', 'Locais', 'browser'],
  ['formatos', 'Formatos', 'table'],
  ['interativos', 'Interativos', 'plugin'],
];
const PERCENT = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1});

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
  // The home page is the channel shelf: highlight Canais there.
  const section = active === 'inicio' ? 'canais' : active;

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
          const here = section === id || (id === 'planos' && section === 'novo-plano') || (id === 'radar' && section === 'radares');
          return <a key={id} href={id === 'planos' ? newPlanUrl(urls) : hrefFor(id)} title={label} className={`pn__link${here ? ' is-active' : ''}`} aria-current={here ? 'page' : undefined} onClick={close}>
            <Icon name={icon} size={16}/><span>{label}</span>
          </a>;
        })}
      </nav>
      <div className="pn__actions">
        {urls.credits && <a className={`pn-tokens${percent === null ? ' is-pending' : percent >= 80 ? ' is-high' : ''}`} href={urls.credits} title="Tokens e consumo do mês" aria-label={percent === null ? 'Tokens do mês' : `Tokens: ${PERCENT.format(percent)}% usados no mês`}>
          <span>Tokens <b>{percent === null ? '\u00a0' : `${PERCENT.format(percent)}%`}</b></span><i aria-hidden="true"><u style={{width: `${percent ?? 0}%`}}/></i>
        </a>}
        <a className="pn-user" href={urls.profile} title={boot.user?.name || first} aria-label={`Abrir conta de ${boot.user?.name || first}`}>
          <VisualIdentity src={boot.user?.avatar || ''} initials={boot.user?.name || first} label={boot.user?.name || first} imageAlt="" className="pn-user__avatar"/>
          <span>{first}</span>
        </a>
      </div>
    </div>
  </header>;
}
