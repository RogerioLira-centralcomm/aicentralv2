import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity.jsx';
import {CaduSolutionSwitcher} from '../cadu-design-system/components/WorkspaceSelectors.jsx';
import {useCreditUsage} from '../cadu-design-system/components/SidebarAccount.jsx';
import {workspaceSolutionItems} from '../cadu-design-system/workspaceSolutions';
import '../cadu-design-system/components/SolutionSidebar.css';
import {moduleUrl, newPlanUrl} from './api.js';

// Where people browse. Order follows the buying flow: who, where, how.
const DESTINATIONS = [
  ['inicio', 'Início', 'home', 'Vitrine de audiências com o seu plano sempre à mão.'],
  ['canais', 'Canais', 'share', 'Social, busca, vídeo, áudio e mídia exterior.'],
  ['audiencias', 'Audiências', 'users', 'Públicos com tamanho e contexto de uso.'],
  ['portais', 'Portais e veículos', 'library', 'Veículos com audiência pública verificável.'],
  ['places', 'Locais', 'browser', 'Pontos físicos e circulação.'],
  ['formatos', 'Formatos', 'table', 'Especificações e finalidade de cada peça.'],
  ['interativos', 'Interativos', 'plugin', 'Formatos com interação para engajar.'],
];
const PERCENT = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1});
const number = value => Number(value || 0).toLocaleString('pt-BR');

/** Facets of the audience shelf, fetched once when its mega menu first opens. */
function useAudienceFacets(request, wanted) {
  const [facets, setFacets] = useState(null);
  useEffect(() => {
    if (!wanted || facets) return undefined;
    let active = true;
    request('/catalog/audiencias?limit=1&offset=0')
      .then(data => { if (active) setFacets({total: Number(data.total || 0), ...(data.facets || {})}); })
      .catch(() => { if (active) setFacets({total: 0, categories: [], platforms: []}); });
    return () => { active = false; };
  }, [request, wanted, facets]);
  return facets;
}

function MegaPanel({item, urls, facets, onNavigate}) {
  const [id, label, icon, description] = item;
  const base = moduleUrl(urls, id === 'inicio' ? 'audiencias' : id);
  const link = (params, text, extra = null) => <a key={text} href={`${base}?${params}`} onClick={onNavigate}>{extra}<span>{text}</span></a>;
  const audience = id === 'audiencias' || id === 'inicio';
  return <div className="pn-mega" role="region" aria-label={label}>
    <div className="pn-mega__intro">
      <span className="pn-mega__icon"><Icon name={icon} size={20}/></span>
      <strong>{label}</strong>
      <p>{description}</p>
      <a className="pn-mega__all" href={base} onClick={onNavigate}>Ver tudo{audience && facets?.total ? ` · ${number(facets.total)}` : ''}<Icon name="chevron" size={14}/></a>
    </div>
    {audience ? <>
      <div className="pn-mega__col"><h3>Por categoria</h3>
        {!facets ? <span className="pn-mega__wait">Carregando…</span> : (facets.categories || []).slice(0, 8).map(entry =>
          link(new URLSearchParams({categoria: entry.value}), entry.value, <em>{number(entry.count)}</em>))}
      </div>
      <div className="pn-mega__col"><h3>Por canal de compra</h3>
        {!facets ? <span className="pn-mega__wait">Carregando…</span> : (facets.platforms || []).slice(0, 8).map(entry =>
          link(new URLSearchParams({canal: entry.value}), entry.value, <em>{number(entry.count)}</em>))}
      </div>
    </> : <div className="pn-mega__col pn-mega__col--wide"><h3>Atalhos</h3>
      <a href={base} onClick={onNavigate}><span>Explorar {label.toLowerCase()}</span></a>
      <a href={newPlanUrl(urls)} onClick={onNavigate}><span>Montar um plano com o Cadu</span></a>
    </div>}
  </div>;
}

function Menu({label, icon, items, align = 'right'}) {
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
    <button type="button" className="pn-action" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <Icon name={icon} size={16}/><span>{label}</span>
    </button>
    {open && <div className={`pn-menu__list pn-menu__list--${align}`} role="menu">
      {items.map(([text, href]) => <a key={text} role="menuitem" href={href}>{text}</a>)}
    </div>}
  </div>;
}

/**
 * The Planner's one navigation: destinations with a mega menu, the actions that
 * start work (radar, plans, new plan) and the account. Replaces the sidebar so the
 * shelves get the full width.
 */
export function PlannerNav({boot, request, active}) {
  const urls = boot.urls;
  const [openId, setOpenId] = useState(null);
  const [mobile, setMobile] = useState(false);
  const closeTimer = useRef(null);
  const rootRef = useRef(null);
  const usage = useCreditUsage(null);
  const solutions = workspaceSolutionItems({urls: {solutions: {workspace: urls.workspace, planner: urls.home, studio: urls.studio, connect: urls.reports, skills: urls.skills}}, solutionIcons: boot.solutionIcons || {
    workspace: '/static/images/cadu/products/cadu-icon.png', planner: '/static/images/cadu/products/planner-icon.png',
    studio: '/static/images/cadu/products/studio-icon.png', connect: '/static/images/cadu/products/connect-icon.png', skills: '/static/images/cadu/products/skills-icon.png'}});
  const facets = useAudienceFacets(request, openId === 'audiencias' || openId === 'inicio');

  const cancelClose = () => window.clearTimeout(closeTimer.current);
  const openNow = id => { cancelClose(); setOpenId(id); };
  const closeSoon = () => { cancelClose(); closeTimer.current = window.setTimeout(() => setOpenId(null), 140); };
  const close = useCallback(() => { setOpenId(null); setMobile(false); }, []);
  useEffect(() => () => window.clearTimeout(closeTimer.current), []);
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') close(); };
    const outside = event => { if (!rootRef.current?.contains(event.target)) setOpenId(null); };
    document.addEventListener('keydown', escape);
    document.addEventListener('pointerdown', outside);
    return () => { document.removeEventListener('keydown', escape); document.removeEventListener('pointerdown', outside); };
  }, [close]);

  const current = DESTINATIONS.find(([id]) => id === openId);
  const percent = usage === null ? null : Math.max(0, Math.min(100, usage));
  const first = String(boot.user?.name || 'Minha conta').trim().split(/\s+/)[0];
  const hrefFor = id => moduleUrl(urls, id);

  return <header className={`pn${mobile ? ' is-mobile-open' : ''}`} ref={rootRef} onMouseLeave={closeSoon} onMouseEnter={cancelClose}>
    <div className="pn__bar">
      <div className="pn__brand"><CaduSolutionSwitcher logo="/static/images/cadu/products/planner-icon.png" solutions={solutions} activeId="planner" showActiveLabel overlay overlayAccent="var(--cadu-accent)"/></div>
      <button type="button" className="pn__burger" aria-label={mobile ? 'Fechar navegação' : 'Abrir navegação'} aria-expanded={mobile} onClick={() => setMobile(value => !value)}>
        <Icon name={mobile ? 'close' : 'table'} size={20}/>
      </button>
      <nav className="pn__nav" aria-label="Seções do Planner">
        {DESTINATIONS.map(item => {
          const [id, label, icon] = item;
          const here = active === id;
          return <a key={id} href={hrefFor(id)} className={`pn__link${here ? ' is-active' : ''}${openId === id ? ' is-open' : ''}`} aria-current={here ? 'page' : undefined}
            aria-haspopup="true" aria-expanded={openId === id}
            onMouseEnter={() => openNow(id)} onFocus={() => openNow(id)}>
            <Icon name={icon} size={20}/><span>{label}</span>
          </a>;
        })}
      </nav>
      <div className="pn__actions">
        <Menu label="Radar" icon="pulse" items={[['Novo radar', hrefFor('radar')], ['Meus radares', hrefFor('radares')]]}/>
        <Menu label="Planos" icon="history" items={[['Todos os planos', urls.plans], ['Novo planejamento', newPlanUrl(urls)]]}/>
        <a className="pn-new" href={newPlanUrl(urls)}><Icon name="plus" size={16}/><span>Novo plano</span></a>
        {percent !== null && urls.credits && <a className={`pn-tokens${percent >= 80 ? ' is-high' : ''}`} href={urls.credits} title="Tokens e consumo do mês" aria-label={`Tokens: ${PERCENT.format(percent)}% usados no mês`}>
          <span>Tokens <b>{PERCENT.format(percent)}%</b></span><i aria-hidden="true"><u style={{width: `${percent}%`}}/></i>
        </a>}
        <a className="pn-user" href={urls.profile} title={boot.user?.name || first} aria-label={`Abrir conta de ${boot.user?.name || first}`}>
          <VisualIdentity src={boot.user?.avatar || ''} initials={boot.user?.name || first} label={boot.user?.name || first} imageAlt="" className="pn-user__avatar"/>
          <span>{first}</span>
        </a>
      </div>
    </div>
    {current && <div className="pn__panel" onMouseEnter={cancelClose} onMouseLeave={closeSoon}>
      <MegaPanel item={current} urls={urls} facets={facets} onNavigate={close}/>
    </div>}
  </header>;
}
